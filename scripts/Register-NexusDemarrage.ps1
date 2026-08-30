<#
.SYNOPSIS
    Enregistre une tache planifiee qui monte la pile a l'ouverture de session.

.DESCRIPTION
    Sans cette tache, la reprise reste un geste a faire. Or le moteur Ollama
    vit sur l'hote et n'a aucun demarrage automatique, la ou Docker Desktop
    en a un : apres un redemarrage de Windows, les conteneurs reviennent
    seuls et le moteur reste eteint. La panne n'apparait alors qu'au premier
    appel de modele, loin de sa cause.

    La tache appelle `scripts/start.ps1`, qui fait le travail complet :
    moteur, controle de conformite bloquant, conteneurs, attente de la
    passerelle, releve locale.

    Deux choix expliques, parce qu'ils ne vont pas de soi :

    * LogonType Interactive, et non S4U. Attention au faux motif : les tubes
      nommes sont GLOBAUX a la machine, pas cloisonnes par session, donc une
      tache S4U atteindrait tres bien Docker Desktop. Le vrai motif est que
      sans session le tube n'est pas inaccessible mais INEXISTANT -- Docker
      Desktop ne demarre qu'a l'ouverture de session. Le seul avantage de
      S4U, tourner sans session, ne vaut donc rien ici : la tache se
      lancerait pour ne rien trouver. La fenetre est masquee par
      -WindowStyle Hidden cote pwsh.

    * Un delai avant declenchement. A l'ouverture de session, Docker Desktop
      n'a pas fini de demarrer ; lancer la pile immediatement echouerait sur
      un moteur Docker absent. Le delai par defaut lui laisse le temps.

    La sortie est ecrite dans logs/demarrage.log. Une tache silencieuse dont
    on ne peut pas constater l'echec ne vaut pas mieux que pas de tache.

.PARAMETER Remove
    Supprime la tache au lieu de l'installer.

.PARAMETER DelaiSecondes
    Attente entre l'ouverture de session et le lancement. Defaut 120 s.

.PARAMETER TaskName
    Nom de la tache planifiee.

.EXAMPLE
    .\scripts\Register-NexusDemarrage.ps1
    .\scripts\Register-NexusDemarrage.ps1 -DelaiSecondes 180
    .\scripts\Register-NexusDemarrage.ps1 -Remove
#>
[CmdletBinding()]
param(
    [switch]$Remove,
    [ValidateRange(0, 3600)]
    [int]$DelaiSecondes = 120,
    [string]$TaskName = "Claude-Local-Nexus - Demarrage"
)

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$RepoRoot = Split-Path -Parent $PSScriptRoot
$Demarreur = Join-Path $PSScriptRoot "start.ps1"

# ------------------------------------------------------------
# Desinstallation
# ------------------------------------------------------------
if ($Remove) {
    $existante = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if (-not $existante) {
        Write-Host "Aucune tache '$TaskName' enregistree." -ForegroundColor Yellow
        exit 0
    }
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "Tache '$TaskName' supprimee." -ForegroundColor Green
    exit 0
}

# ------------------------------------------------------------
# Verifications avant d'inscrire quoi que ce soit
# ------------------------------------------------------------
if (-not (Test-Path $Demarreur)) {
    Write-Error "Introuvable : $Demarreur"
    exit 1
}

$shell = (Get-Command pwsh -ErrorAction SilentlyContinue).Source
if (-not $shell) { $shell = (Get-Command powershell -ErrorAction SilentlyContinue).Source }
if (-not $shell) {
    Write-Error "Ni pwsh ni powershell dans le PATH."
    exit 1
}

$logDir = Join-Path $RepoRoot 'logs'
if (-not (Test-Path $logDir)) {
    New-Item -ItemType Directory -Path $logDir | Out-Null
}
# Journal unique, ecrase a chaque demarrage : on veut savoir si LE dernier
# demarrage a reussi, pas accumuler un fichier par ouverture de session.
$logFile = Join-Path $logDir 'demarrage.log'

# -Command et non -File : avec -File, tout ce qui suit le chemin du script
# lui est passe en ARGUMENT au lieu d'etre interprete par PowerShell. La
# redirection `*>` partait donc comme parametre inconnu vers start.ps1, la
# tache echouait avec le code 1, et aucun journal n'etait ecrit -- une panne
# muette, exactement ce que le journal devait empecher. Mesure avant
# correction : LastTaskResult 1, zero fichier produit.
$escDem = $Demarreur -replace "'", "''"
$escLog = $logFile   -replace "'", "''"
$arguments = '-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -Command "& ''{0}'' *> ''{1}''"' -f $escDem, $escLog

$action = New-ScheduledTaskAction -Execute $shell -Argument $arguments -WorkingDirectory $RepoRoot

$trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
# Le delai n'est pas exposé par New-ScheduledTaskTrigger : il se pose sur
# l'objet, au format ISO 8601.
$trigger.Delay = "PT{0}S" -f $DelaiSecondes

$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 30) `
    -MultipleInstances IgnoreNew

$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited

if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "Ancienne tache remplacee." -ForegroundColor Yellow
}

try {
    Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
        -Settings $settings -Principal $principal `
        -Description "Monte la pile Claude-Local-Nexus a l'ouverture de session : moteur Ollama, conformite, conteneurs, passerelle, releve." `
        -ErrorAction Stop | Out-Null
} catch {
    Write-Error "Echec de l'enregistrement : $($_.Exception.Message)"
    exit 1
}

Write-Host ""
Write-Host "Tache de demarrage installee." -ForegroundColor Green
Write-Host "  Nom      : $TaskName"
Write-Host "  Moment   : ouverture de session, apres $DelaiSecondes s"
Write-Host "  Journal  : $logFile"
Write-Host ""
Write-Host "  Essai immediat  : Start-ScheduledTask -TaskName `"$TaskName`"" -ForegroundColor Gray
Write-Host "  Desinstallation : .\scripts\Register-NexusDemarrage.ps1 -Remove" -ForegroundColor Gray
Write-Host ""
