<#
.SYNOPSIS
    Installe (ou retire) la mise a jour automatique de Claude-Local-Nexus.

.DESCRIPTION
    Enregistre une tache planifiee Windows qui execute chaque jour :

        Update-NexusModels.ps1 -SyncLocal -SyncWeights -Validate -Restart

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

# Aucune elevation exigee, et ce n'est pas un relachement.
#
# La tache est enregistree POUR l'utilisateur courant (UserId = $env:USERNAME)
# avec RunLevel Limited : Windows ne demande pas de droits administrateur pour
# cela. La garde precedente refusait donc l'operation ordinaire, et il fallait
# ouvrir un terminal eleve pour un geste qui n'en avait pas besoin -- une
# friction suffisante pour que la tache reste des mois dans son etat initial.
#
# Si un droit venait reellement a manquer, Register-ScheduledTask echoue plus
# bas avec son propre message, deja rattrape et affiche.

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
#
# [TimeSpan]::Zero et non $null : TimeSpan est un type VALEUR, et lui affecter
# $null leve « Cannot convert null to type System.TimeSpan ». Le script
# s'arretait donc ici -- mais nul ne le voyait, la verification des droits
# administrateur sortant quelques lignes plus haut. Le premier defaut masquait
# le second, et la tache planifiee restait celle d'une version anterieure.
[TimeSpan]$heureAnalysee = [TimeSpan]::Zero
$timeFormats = @('hh\:mm','h\:mm')
$validTime = $false
foreach ($fmt in $timeFormats) {
    if ([TimeSpan]::TryParseExact($Time, $fmt, $null, [ref]$heureAnalysee)) {
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

# Echappe le chemin pour une chaine PowerShell entre apostrophes.
#
# La methode appelee ici s'appelait EscapeSingleQuotedString, qui n'existe
# pas : la classe expose EscapeSingleQuotedStringContent. L'appel levait donc
# a chaque execution -- invisible, puisque la verification des droits
# administrateur puis une conversion TimeSpan fautive sortaient avant de
# l'atteindre. Trois defauts en file, chacun cachant le suivant, et une tache
# planifiee restee celle d'une version anterieure.
$escapedUpdater = $Updater -replace "'", "''"

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
# Nom FIXE, et non horodate a l'enregistrement : l'horodatage etait celui du
# jour ou la tache fut inscrite, pas de son execution, si bien que toutes les
# executions ecrivaient dans un fichier portant une date trompeuse. On veut
# savoir si LA derniere mise a jour a reussi.
$logFile = Join-Path $logDir "update.log"

# -Command et non -File. Avec -File, tout ce qui suit le chemin du script lui
# est passe EN ARGUMENTS : la redirection `*>` partait vers Update-NexusModels
# comme parametre inconnu, et la tache echouait sans ecrire la moindre ligne.
# Verifie sur la tache de demarrage, ou le meme montage donnait
# LastTaskResult 1 et zero journal -- une panne muette, exactement ce que le
# journal existait pour rendre visible.
$escapedLog = $logFile -replace "'", "''"
$arguments = "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -Command ""& '$escapedUpdater' -SyncLocal -SyncWeights -Validate -Restart *> '$escapedLog'"""

$action = New-ScheduledTaskAction -Execute $shell -Argument $arguments -WorkingDirectory $RepoRoot
$trigger = New-ScheduledTaskTrigger -Daily -At $Time
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Hours 3) `
    -MultipleInstances IgnoreNew

# Interactive, et non S4U -- mais pas pour la raison qu'on croit.
#
# Rectification : l'espace de noms des tubes nommes est GLOBAL a la machine,
# pas cloisonne par session. Une tache S4U atteindrait donc parfaitement
# \\.\pipe\dockerDesktopLinuxEngine, la DACL admettant le meme SID. Le
# commentaire precedent affirmait l'inverse ; il etait faux.
#
# La vraie raison tient a ce que S4U apporte : tourner sans session ouverte.
# Or ici cet avantage ne vaut rien. Sans session, le tube n'est pas
# inaccessible, il est INEXISTANT -- Docker Desktop ne demarre qu'a
# l'ouverture de session. Une tache S4U se lancerait a 04:00, ne trouverait
# aucun moteur, se terminerait proprement, et la journee serait perdue sur
# une execution reussie qui n'a rien fait.
#
# Interactive ne se lance pas dans ce cas, et StartWhenAvailable la rattrape
# a l'ouverture suivante -- precisement quand Docker Desktop revient. Le
# rattrapage produit une execution UTILE la ou la tolerance S4U produit une
# execution VIDE.
#
# Contrepartie assumee : aucune mise a jour tant qu'aucune session ne
# s'ouvre. Rien n'etait possible de toute facon.
$taskPrincipal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited

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
