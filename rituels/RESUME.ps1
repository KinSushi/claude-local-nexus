<#
.SYNOPSIS
    Reprend le fil : régénère l'état mesuré et rappelle les sujets ouverts.

.DESCRIPTION
    À lancer en début de session. Le fichier d'état n'est pas relu tel quel :
    il est reconstruit à partir de mesures — services, moteur d'inférence,
    inventaire exposé, budget matériel, empreintes SHA-256. Un état saisi à
    la main décrirait ce qu'on croyait au moment de l'écrire ; celui-ci
    décrit ce qui est.

    Affiche ensuite les sujets ouverts du cockpit, pour ne pas repartir
    de mémoire.

.PARAMETER Full
    Ajoute la validation d'intégrité détaillée et le smoke test runtime.

.EXAMPLE
    .\rituels\RESUME.ps1
.EXAMPLE
    .\rituels\RESUME.ps1 -Full
#>
[CmdletBinding()]
param([switch]$Full)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$RepoRoot = Split-Path -Parent $PSScriptRoot
$Scripts  = Join-Path $RepoRoot "scripts"

function Resolve-Python {
    foreach ($candidate in @("python", "python3")) {
        $cmd = Get-Command $candidate -ErrorAction SilentlyContinue
        if ($cmd) { return $cmd.Source }
    }
    throw "Python introuvable."
}
$python = Resolve-Python

Write-Host "`n=== Regeneration de l'etat mesure ===" -ForegroundColor Cyan
& $python (Join-Path $Scripts "nexus_state.py")

Write-Host "`n=== Profil materiel ===" -ForegroundColor Cyan
& $python (Join-Path $Scripts "nexus_capability.py") |
    Select-Object -First 16

Write-Host "`n=== Moteur d'inference ===" -ForegroundColor Cyan
& $python (Join-Path $Scripts "nexus_switch_engine.py") --status |
    Select-Object -First 8

Write-Host "`n=== Sujets ouverts ===" -ForegroundColor Cyan
$cockpit = Join-Path $PSScriptRoot "CHECKLIST_COCKPIT.MD"
if (Test-Path $cockpit) {
    $ouverts = Get-Content $cockpit | Where-Object { $_ -match '`OUVERT`' }
    if ($ouverts) {
        Write-Host "  $($ouverts.Count) sujet(s) a traiter :" -ForegroundColor Yellow
        foreach ($ligne in $ouverts) {
            # On ne garde que l'intitule, pas la mise en forme du tableau.
            $cellules = $ligne -split '\|'
            if ($cellules.Count -ge 3) {
                Write-Host ("    {0,-6} {1}" -f $cellules[1].Trim(), $cellules[2].Trim())
            }
        }
    } else {
        Write-Host "  Aucun sujet ouvert." -ForegroundColor Green
    }
} else {
    Write-Host "  CHECKLIST_COCKPIT.MD introuvable." -ForegroundColor Yellow
}

if ($Full) {
    Write-Host "`n=== Integrite de la configuration ===" -ForegroundColor Cyan
    & (Join-Path $Scripts "Test-NexusConfig.ps1")

    Write-Host "`n=== Verification runtime ===" -ForegroundColor Cyan
    & (Join-Path $Scripts "Test-NexusSmoke.ps1") -IncludeRouters
}

Write-Host "`nEtat : rituels\STATE.md   Sujets : rituels\CHECKLIST_COCKPIT.MD   Historique : rituels\PROGRESS.md`n"
