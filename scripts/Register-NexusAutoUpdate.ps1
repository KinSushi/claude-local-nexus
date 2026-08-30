<#
.SYNOPSIS
    Installe (ou retire) la mise a jour automatique de Claude-Local-Nexus.

.DESCRIPTION
    Enregistre une tache planifiee Windows qui execute chaque jour :

        Update-NexusModels.ps1 -SyncLocal -Validate -Restart

    Concretement, chaque nuit la plateforme :
      - retélécharge les modeles locaux manquants ;
      - redécouvre le catalogue Ollama Cloud ;
      - re-teste les droits reels du compte Ollama Cloud ;
      - regenere routeurs et graphes de fallback ;
      - refuse d'appliquer une configuration invalide ;
      - redemarre LiteLLM et verifie le resultat en runtime.

    C'est ce qui rend l'abonnement Ollama Cloud auto-suivi : le jour ou un
    palier superieur est souscrit, les modeles debloques entrent d'eux-memes
    dans le routeur a l'execution suivante. Aucune edition de configuration.

    La tache s'execute sous le compte courant, sans elevation, et ne
    demarre que si Docker Desktop tourne (sinon elle se termine proprement).

.PARAMETER Time
    Heure d'execution quotidienne (format HH:mm ou H:mm). Defaut 04:00.
.PARAMETER TaskName
    Nom de la tache planifiee. Defaut "Claude-Local-Nexus - Mise a jour".
.PARAMETER RunNow
    Declenche immediatement une execution apres l'enregistrement.
.PARAMETER Unregister
    Supprime la tache planifiee au lieu de l'installer.

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

# Verifier que le script est lance avec les droits administrateur
$principalIdentity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = New-Object Security.Principal.WindowsPrincipal $principalIdentity
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Error "Ce script doit etre execute avec les droits administrateur."
    exit 1
}

$RepoRoot = Split-Path -Parent $PSScriptRoot
$Updater  = Join-Path $PSScriptRoot "Update-NexusModels.ps1"

# Verifier l'existence du script updater
if (-not (Test-Path $Updater)) {
    Write-Error "Introuvable : $Updater"
    exit 1
}
# Verifier que le fichier a bien l'extension .ps1
if ((Get-Item $Updater).Extension -ne '.ps1') {
    Write-Error "Le fichier updater doit etre un script PowerShell (.ps1) : $Updater"
    exit 1
}

# ------------------------------------------------------------
# Desinstallation
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
# Interpreteur : PowerShell 7 si disponible, sinon Windows PowerShell
# ------------------------------------------------------------
$pwshCmd = Get-Command pwsh -ErrorAction SilentlyContinue
if ($pwshCmd) {
    $shell = $pwshCmd.Source
} else {
    $psCmd = Get-Command powershell -ErrorAction SilentlyContinue
    if ($psCmd) {
        $shell = $psCmd.Source
    } else {
        $shell = $null
    }
}
if (-not $shell) {
    Write-Error "Aucun interpreteur PowerShell trouve."
    exit 1
}

# Validation de l'heure (format HH:mm ou H:mm)
[TimeSpan]$nullSpan = $null
$timeFormats = @('hh\:mm','h\:mm')
$validTime = $false
foreach ($fmt in $timeFormats) {
    if ([TimeSpan]::TryParseExact($Time, $fmt, $null, [ref]$nullSpan)) {
        $validTime = $true
        break
    }
}
if (-not $validTime) {
    Write-Error "Heure invalide : '$Time' (format attendu HH:mm)."
    exit 1
}

# Validation du nom de tache (pas de caracteres interdits)
if ($TaskName -match '[\\/:*?"<>|]') {
    Write-Error "Nom de tache invalide : il ne doit pas contenir \ / : * ? "" < > |"
    exit 1
}

# Echappe correctement le chemin du script updater
$escapedUpdater = [System.Management.Automation.Language.CodeGeneration]::EscapeSingleQuotedString($Updater)

# Preparation du fichier de log unique
$logDir = Join-Path $RepoRoot 'logs'
if (-not (Test-Path $logDir)) {
    try {
        New-Item -ItemType Directory -Path $logDir -ErrorAction Stop | Out-Null
    } catch {
        Write-Error "Impossible de creer le repertoire de logs : $logDir"
        exit 1
    }
}
$logFile = Join-Path $logDir ("update-{0}.log" -f (Get-Date -Format "yyyyMMdd-HHmmss"))

# Arguments incluant la redirection des flux vers le log
$arguments = "-NoProfile -ExecutionPolicy Bypass -File `"$escapedUpdater`" -SyncLocal -Validate -Restart *> `"$logFile`""

$action = New-ScheduledTaskAction -Execute $shell -Argument $arguments -WorkingDirectory $RepoRoot
$trigger = New-ScheduledTaskTrigger -Daily -At $Time
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Hours 3) `
    -MultipleInstances IgnoreNew

# Utiliser S4U (service for user) afin d'executer sans session interactive
$taskPrincipal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType S4U -RunLevel Limited

# Remplacer une tache existante le cas echeant
if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "Ancienne tache remplacee." -ForegroundColor Yellow
}

# Enregistrement de la tache avec gestion d'erreur explicite
try {
    Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
        -Settings $settings -Principal $taskPrincipal `
        -Description "Synchronise l'inventaire local et Ollama Cloud, regenere les routeurs LiteLLM, valide puis redemarre la plateforme Claude-Local-Nexus." `
        -ErrorAction Stop
} catch {
    Write-Error "Echec de l'enregistrement de la tache planifiee : $($_.Exception.Message)"
    exit 1
}

Write-Host ""
Write-Host "Tache planifiee installee." -ForegroundColor Green
Write-Host "  Nom       : $TaskName"
Write-Host "  Frequence : tous les jours a $Time"
Write-Host "  Commande  : $shell $arguments"
Write-Host "  Journaux  : $logDir"
Write-Host ""
Write-Host "Retrait : .\scripts\Register-NexusAutoUpdate.ps1 -Unregister"
Write-Host ""

if ($RunNow) {
    Write-Host "Declenchement immediat..." -ForegroundColor Cyan
    try {
        Start-ScheduledTask -TaskName $TaskName -ErrorAction Stop
        Write-Host "Lancee. Suivre : Get-Content (Get-ChildItem '$logDir' | Sort-Object LastWriteTime | Select-Object -Last 1).FullName -Wait"
    } catch {
        Write-Error "Impossible de demarrer la tache immédiatement : $($_.Exception.Message)"
    }
}
