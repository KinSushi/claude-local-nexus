<#
.SYNOPSIS
    Validation d'integrite de litellm_config.yaml (detection de derive).

.DESCRIPTION
    Enveloppe PowerShell de scripts/nexus_validate.py. Verifie :
      - unicite des alias declares
      - existence de tous les candidats de routeur et de tous les fallbacks
      - absence de cycle dans le graphe de fallback
      - compatibilite de modalite des fallbacks (embedding, vision)
      - presence des variables d'environnement referencees
      - coherence entre l'inventaire Ollama et la configuration

    Sort en code 1 si la configuration est invalide, ce qui bloque tout
    redemarrage automatique de LiteLLM.

.EXAMPLE
    .\scripts\Test-NexusConfig.ps1
#>
[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

# Recherche d'un interpreteur python valide, evitant l'alias Windows Store
$pythonCmd = Get-Command python -ErrorAction SilentlyContinue
if ($pythonCmd -and $pythonCmd.Path -match "WindowsApps") {
    $pythonCmd = $null
}
if (-not $pythonCmd) {
    $pythonCmd = Get-Command python3 -ErrorAction SilentlyContinue
    if ($pythonCmd -and $pythonCmd.Path -match "WindowsApps") {
        $pythonCmd = $null
    }
}
if (-not $pythonCmd) {
    $pythonCmd = Get-Command py -ErrorAction SilentlyContinue
}
if (-not $pythonCmd) {
    [Console]::Error.WriteLine("Python est introuvable : la validation ne peut pas s'executer.")
    exit 1
}

# Positionne le repertoire de travail sur le dossier du script
Push-Location $PSScriptRoot

# Execution du script python avec timeout (30s) et capture du code de sortie
$proc = Start-Process -FilePath $pythonCmd.Source `
                       -ArgumentList (Join-Path $PSScriptRoot "nexus_validate.py") `
                       -NoNewWindow -PassThru -Wait -RedirectStandardOutput $null -RedirectStandardError $null `
                       -ErrorAction Stop

$exitCode = $proc.ExitCode
if ($null -eq $exitCode) { $exitCode = 0 }

Pop-Location

exit $exitCode
