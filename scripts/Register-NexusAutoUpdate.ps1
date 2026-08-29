<#
.SYNOPSIS
    Installe (ou retire) la mise à jour automatique de Claude-Local-Nexus.

.DESCRIPTION
    Enregistre une tâche planifiée Windows qui exécute chaque jour :

        Update-NexusModels.ps1 -SyncLocal -Validate -Restart

    Concrètement, chaque nuit la plateforme :
      - retélécharge les modèles locaux manquants ;
      - redécouvre le catalogue Ollama Cloud ;
      - re-teste les droits réels du compte Ollama Cloud ;
      - régénère routeurs et graphes de fallback ;
      - refuse d'appliquer une configuration invalide ;
      - redémarre LiteLLM et vérifie le résultat en runtime.

    C'est ce qui rend l'abonnement Ollama Cloud auto-suivi : le jour où un
    palier supérieur est souscrit, les modèles débloqués entrent d'eux-mêmes
    dans le routeur à l'exécution suivante. Aucune édition de configuration.

    La tâche s'exécute sous le compte courant, sans élévation, et ne
    démarre que si Docker Desktop tourne (sinon elle se termine proprement).

.PARAMETER Time
    Heure d'exécution quotidienne (format HH:mm). Défaut 04:00.
.PARAMETER TaskName
    Nom de la tâche planifiée. Défaut "Claude-Local-Nexus - Mise a jour".
.PARAMETER RunNow
    Déclenche immédiatement une exécution après l'enregistrement.
.PARAMETER Unregister
    Supprime la tâche planifiée au lieu de l'installer.

.EXAMPLE
    .\scripts\Register-NexusAutoUpdate.ps1
.EXAMPLE
    .\scripts\Register-NexusAutoUpdate.ps1 -Time "03:30" -RunNow
.EXAMPLE
    .\scripts\Register-NexusAutoUpdate.ps1 -Unregister
#>
[CmdletBinding()]
param(
    [string]$Time = "04:00",
    [string]$TaskName = "Claude-Local-Nexus - Mise a jour",
    [switch]$RunNow,
    [switch]$Unregister
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$RepoRoot = Split-Path -Parent $PSScriptRoot
$Updater  = Join-Path $PSScriptRoot "Update-NexusModels.ps1"

if (-not (Test-Path $Updater)) {
    Write-Error "Introuvable : $Updater"
    exit 1
}

# ------------------------------------------------------------
# Désinstallation
# ------------------------------------------------------------
if ($Unregister) {
    $existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if (-not $existing) {
        Write-Host "Aucune tache '$TaskName' enregistree." -ForegroundColor Yellow
        exit 0
    }
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "Tache '$TaskName' supprimee." -ForegroundColor Green
    exit 0
}

# ------------------------------------------------------------
# Interpréteur : PowerShell 7 si disponible, sinon Windows PowerShell
# ------------------------------------------------------------
$shell = (Get-Command pwsh -ErrorAction SilentlyContinue)?.Source
if (-not $shell) { $shell = (Get-Command powershell -ErrorAction SilentlyContinue)?.Source }
if (-not $shell) {
    Write-Error "Aucun interpreteur PowerShell trouve."
    exit 1
}

if ($Time -notmatch '^\d{2}:\d{2}$') {
    Write-Error "Heure invalide : '$Time' (format attendu HH:mm)."
    exit 1
}

$arguments = '-NoProfile -ExecutionPolicy Bypass -File "{0}" -SyncLocal -Validate -Restart' -f $Updater

$action = New-ScheduledTaskAction -Execute $shell -Argument $arguments -WorkingDirectory $RepoRoot
$trigger = New-ScheduledTaskTrigger -Daily -At $Time
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Hours 3) `
    -MultipleInstances IgnoreNew
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited

if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "Ancienne tache remplacee." -ForegroundColor Yellow
}

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
    -Settings $settings -Principal $principal `
    -Description "Synchronise l'inventaire local et Ollama Cloud, regenere les routeurs LiteLLM, valide puis redemarre la plateforme Claude-Local-Nexus." | Out-Null

Write-Host ""
Write-Host "Tache planifiee installee." -ForegroundColor Green
Write-Host "  Nom       : $TaskName"
Write-Host "  Frequence : tous les jours a $Time"
Write-Host "  Commande  : $shell $arguments"
Write-Host "  Journaux  : $(Join-Path $RepoRoot 'logs')"
Write-Host ""
Write-Host "Retrait : .\scripts\Register-NexusAutoUpdate.ps1 -Unregister"
Write-Host ""

if ($RunNow) {
    Write-Host "Declenchement immediat..." -ForegroundColor Cyan
    Start-ScheduledTask -TaskName $TaskName
    Write-Host "Lancee. Suivre : Get-Content (Get-ChildItem '$RepoRoot\logs' | Sort-Object LastWriteTime | Select-Object -Last 1).FullName -Wait"
}
