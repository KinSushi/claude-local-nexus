<#
.SYNOPSIS
    Validation d'intégrité de litellm_config.yaml (détection de dérive).

.DESCRIPTION
    Enveloppe PowerShell du script Python *nexus_validate.py*. Vérifie :
      - unicité des alias déclarés
      - existence de tous les candidats de routeur et de tous les fallbacks
      - absence de cycle dans le graphe de fallback
      - compatibilité de modalité des fallbacks (embedding, vision)
      - présence des variables d'environnement référencées
      - cohérence entre l'inventaire Ollama et la configuration

    Retourne le code de sortie du script Python ; 1 indique une configuration invalide,
    ce qui bloque tout redémarrage automatique de LiteLLM.

.EXAMPLE
    .\scripts\Test-NexusConfig.ps1
#>

[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

# ----------------------------------------------------------------------
# Recherche d'un interpréteur Python valide, en évitant l'alias Windows Store
# ----------------------------------------------------------------------
function Get-ValidPython {
    # Juge sur le COMPORTEMENT, pas sur le chemin.
    #
    # Le filtre precedent ecartait tout ce qui vit sous WindowsApps, pour
    # eviter le stub du Microsoft Store qui ouvre une page au lieu
    # d'executer. Mais sur cette machine les TROIS candidats y pointent, et
    # ce sont des redirections fonctionnelles : verifie a l'execution, ce
    # python.exe rend bien C:\...\pythoncore-3.14-64\python.exe.
    #
    # La garde rejetait donc un interprete valide, la fonction rendait $null,
    # et le script s'arretait sur « Python est introuvable » -- or c'est la
    # porte d'integrite qui empeche de redemarrer la passerelle sur une
    # configuration fausse. Une garde qui se bloque elle-meme ne protege rien.
    #
    # Un stub echoue au test ci-dessous, une redirection le passe.
    foreach ($cmdName in @('python', 'python3', 'py')) {
        $cmd = Get-Command $cmdName -ErrorAction SilentlyContinue
        if ($null -eq $cmd) { continue }
        if ($cmd.CommandType -ne 'Application') { continue }
        try {
            # -ErrorAction ne s'applique pas a un executable natif : il lui
            # serait passe comme argument. On lit le code de sortie.
            $sortie = & $cmd.Source -c "import sys; print(sys.version_info[0])" 2>$null
            if ($LASTEXITCODE -eq 0 -and "$sortie".Trim() -eq '3') { return $cmd }
        } catch {
            continue
        }
    }
    return $null
}


$pythonCmd = Get-ValidPython
if (-not $pythonCmd) {
    [Console]::Error.WriteLine("Python est introuvable : la validation ne peut pas s'executer.")
    exit 1
}

# ----------------------------------------------------------------------
# Vérification de l'existence du script Python
# ----------------------------------------------------------------------
$scriptPath = Join-Path $PSScriptRoot "nexus_validate.py"
if (-not (Test-Path $scriptPath)) {
    [Console]::Error.WriteLine("Le fichier nexus_validate.py est introuvable.")
    exit 1
}

# ----------------------------------------------------------------------
# Forcer l'encodage UTF8 du processus Python (Python 3.7+)
# ----------------------------------------------------------------------
$env:PYTHONUTF8 = '1'

# ----------------------------------------------------------------------
# Exécution du script Python avec restauration du répertoire de travail
# ----------------------------------------------------------------------
Push-Location $PSScriptRoot
try {
    # Appel DIRECT, et non Start-Process.
    #
    # L'ancienne version passait RedirectStandardOutput = $null et
    # RedirectStandardError = $null a Start-Process, en commentant que
    # c'etait pour « eviter la perte de sortie ». Ces parametres refusent
    # $null : PowerShell levait « Cannot validate argument on parameter
    # RedirectStandardOutput ». Avec ErrorAction = Stop, l'exception filait
    # dans le catch, qui rendait 1 sans rien afficher.
    #
    # Resultat mesure le 2026-08-30 : cette porte d'integrite rendait 1 et
    # ZERO octet de sortie, alors que le validateur Python qu'elle enveloppe
    # rendait 0. Elle criait au loup, en silence, sur une configuration
    # saine -- et c'est elle qui bloque le redemarrage de la passerelle.
    #
    # L'operateur d'appel n'a aucun de ces travers : la sortie du validateur
    # arrive telle quelle sur les flux du script, et $LASTEXITCODE porte le
    # code du processus. Start-Process n'apportait rien ici : il sert a
    # lancer un processus detache, ce que precisement on ne veut pas.
    & $pythonCmd.Source $scriptPath
    $exitCode = $LASTEXITCODE
    if ($null -eq $exitCode) { $exitCode = 1 }
}
catch {
    [Console]::Error.WriteLine("La validation n'a pas pu s'executer : $($_.Exception.Message)")
    $exitCode = 1
}
finally {
    Pop-Location
}

exit $exitCode
