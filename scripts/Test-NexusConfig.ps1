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
    $candidates = @('python', 'python3', 'py')
    foreach ($cmdName in $candidates) {
        $cmd = Get-Command $cmdName -ErrorAction SilentlyContinue
        if ($null -eq $cmd) { continue }

        # On ne veut que des exécutables (Application). Les alias ou fonctions ne sont pas adaptés.
        if ($cmd.CommandType -ne 'Application') { continue }

        # Exclure les chemins du Windows Store (WindowsApps)
        $path = $cmd.Source
        if ($path -match 'WindowsApps') { continue }

        return $cmd
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
# Exécution du script Python avec restauration du répertoire de travail
# ----------------------------------------------------------------------
Push-Location $PSScriptRoot
try {
    # Construction des paramètres de Start-Process. -NoNewWindow n'est ajouté que sous Windows.
    $startParams = @{
        FilePath    = $pythonCmd.Source
        ArgumentList= "`"$scriptPath`""
        PassThru    = $true
        Wait        = $true
        ErrorAction = 'Stop'
    }
    if ($IsWindows) { $startParams.NoNewWindow = $true }

    $proc = Start-Process @startParams

    $exitCode = $proc.ExitCode
    # Si le processus n'a pas renvoyé de code (ex. processus tué), on considère une erreur.
    if ($null -eq $exitCode) { $exitCode = 1 }
}
finally {
    Pop-Location
}

exit $exitCode
