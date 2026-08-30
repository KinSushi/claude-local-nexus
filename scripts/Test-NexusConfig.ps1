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
$exitCode = 1   # valeur par défaut en cas d'échec
try {
    # Construction des paramètres de Start-Process. -NoNewWindow n'est ajouté que sous Windows.
    $startParams = @{
        FilePath          = $pythonCmd.Source
        ArgumentList      = @($scriptPath)          # tableau pour gérer correctement les espaces et caractères spéciaux
        PassThru          = $true
        Wait              = $true
        ErrorAction       = 'Stop'
        RedirectStandardOutput = $null            # éviter la perte de sortie dans certains environnements CI
        RedirectStandardError  = $null
    }
    # Compatibilité PowerShell 5.1 et Core : utiliser $PSVersionTable.PSEdition si disponible
    if ($PSVersionTable.PSEdition -eq 'Desktop' -or $IsWindows) {
        $startParams.NoNewWindow = $true
    }

    $proc = Start-Process @startParams
    $exitCode = $proc.ExitCode
    if ($null -eq $exitCode) { $exitCode = 1 }
}
catch {
    # En cas d'exception (ex. lancement impossible), on conserve le code d'erreur 1
    $exitCode = 1
}
finally {
    Pop-Location
}

exit $exitCode
