<#
.SYNOPSIS
    Validation d'intégrité de litellm_config.yaml (détection de dérive).

.DESCRIPTION
    Enveloppe PowerShell de scripts/nexus_validate.py. Vérifie :
      - unicité des alias déclarés
      - existence de tous les candidats de routeur et de tous les fallbacks
      - absence de cycle dans le graphe de fallback
      - compatibilité de modalité des fallbacks (embedding, vision)
      - présence des variables d'environnement référencées
      - cohérence entre l'inventaire Ollama et la configuration

    Sort en code 1 si la configuration est invalide, ce qui bloque tout
    redémarrage automatique de LiteLLM.

.EXAMPLE
    .\scripts\Test-NexusConfig.ps1
#>
[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) { $python = Get-Command python3 -ErrorAction SilentlyContinue }
if (-not $python) {
    Write-Error "Python est introuvable : la validation ne peut pas s'exécuter."
    exit 1
}

& $python.Source (Join-Path $PSScriptRoot "nexus_validate.py")
exit $LASTEXITCODE
