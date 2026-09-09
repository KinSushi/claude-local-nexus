<#
.SYNOPSIS
    Enregistre la boucle agentique locale : elle tourne sans personne.

.DESCRIPTION
    Quand la session Claude s'arrete faute de quota, son pouls de presence
    vieillit. Cette tache lance a intervalle regulier :
      nexus_boucle_locale.py --tour
    qui lit ce pouls. Si Claude est VIVANT, elle se retire immediatement sans
    rien faire. Si le pouls est MORT et que la file .nexus/file_locale.jsonl
    contient des taches, elle les traite en deleguant a un banc de modeles
    locaux (pilote et auditeur DISTINCTS, LOI 1) et DEPOSE des propositions
    auditees dans .nexus/propositions -- elle ne modifie JAMAIS le depot.

    Inoffensive tant que le pouls est vivant ou la file vide.

.EXAMPLE
    .\outillage\Register-NexusBoucleLocale.ps1
    .\outillage\Register-NexusBoucleLocale.ps1 -Minutes 30
    .\outillage\Register-NexusBoucleLocale.ps1 -Supprimer
#>
[CmdletBinding()]
param(
    [int]$Minutes = 10,
    [switch]$Supprimer
)

$ErrorActionPreference = "Stop"
try { [Console]::OutputEncoding = [Text.Encoding]::UTF8 } catch { Write-Verbose "encodage de sortie non modifie" }

$NomTache = "NexusBoucleLocale"

if ($Supprimer) {
    if (Get-ScheduledTask -TaskName $NomTache -ErrorAction SilentlyContinue) {
        Unregister-ScheduledTask -TaskName $NomTache -Confirm:$false
        Write-Host "Tache $NomTache supprimee." -ForegroundColor Green
    } else {
        Write-Host "Tache $NomTache absente : rien a supprimer." -ForegroundColor Yellow
    }
    exit 0
}

if ($Minutes -lt 5) {
    [Console]::Error.WriteLine("Intervalle trop court : la boucle delegue au banc local.")
    exit 1
}

$racine = Split-Path -Parent $PSScriptRoot
$pwshCmd = Get-Command pwsh -ErrorAction SilentlyContinue
if (-not $pwshCmd) { $pwshCmd = Get-Command powershell -ErrorAction SilentlyContinue }
if (-not $pwshCmd) {
    [Console]::Error.WriteLine("Aucun interpreteur PowerShell trouve.")
    exit 1
}

$pythonCmd = $null
foreach ($c in @('python', 'python3', 'py')) {
    $cmd = Get-Command $c -ErrorAction SilentlyContinue
    if ($null -eq $cmd -or $cmd.CommandType -ne 'Application') { continue }
    $sortie = & $cmd.Source -c "import sys; print(sys.version_info[0])" 2>$null
    if ($LASTEXITCODE -eq 0 -and "$sortie".Trim() -eq '3') { $pythonCmd = $cmd; break }
}
if (-not $pythonCmd) {
    [Console]::Error.WriteLine("Python introuvable : la boucle locale ne peut pas s'executer.")
    exit 1
}

$log = Join-Path $racine "logs\boucle_locale.log"
New-Item -ItemType Directory -Force (Split-Path $log) | Out-Null

# -Command et non -File : avec -File, tout ce qui suit le chemin du script lui
# est passe comme ARGUMENTS, et la redirection n'atteint jamais PowerShell.
# Mesure anterieure de ce depot : LastTaskResult 1, et aucun log -- un echec
# silencieux, precisement ce que le log devait empecher.
$py = $pythonCmd.Source.Replace("'", "''")
$rac = $racine.Replace("'", "''")
$lg = $log.Replace("'", "''")
$commande = "Set-Location '$rac'; " +
            "& '$py' scripts/nexus_boucle_locale.py --tour"
$arguments = "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden " +
             "-Command ""& { $commande } *> '$lg'"""

# Repetition sans fin, a partir de maintenant. La duree maximale est fixee a
# (rien) : une repetition bornee s'arreterait au bout d'un jour sans que rien
# ne le signale.
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) `
    -RepetitionInterval (New-TimeSpan -Minutes $Minutes)

$action = New-ScheduledTaskAction -Execute $pwshCmd.Source -Argument $arguments `
    -WorkingDirectory $racine

# Interactive, comme les autres taches de ce depot : la boucle lit des
# fichiers du profil utilisateur, et un contexte sans session n'y accede pas
# de la meme facon.
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME `
    -LogonType Interactive -RunLevel Limited

# 60 minutes et non 15 : un tour peut deleguer plusieurs cycles au banc local.
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable `
    -DontStopIfGoingOnBatteries -AllowStartIfOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 60)

if (Get-ScheduledTask -TaskName $NomTache -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName $NomTache -Confirm:$false
}
Register-ScheduledTask -TaskName $NomTache -Trigger $trigger -Action $action `
    -Principal $principal -Settings $settings `
    -Description "Boucle agentique locale : reprend le travail quand le pouls Claude est mort, toutes les $Minutes min." | Out-Null

Write-Host "Tache $NomTache enregistree : toutes les $Minutes minutes." -ForegroundColor Green
Write-Host "  Journal      : $log" -ForegroundColor Gray
Write-Host "  Propositions : .nexus\propositions" -ForegroundColor Gray
Write-Host "  Supprimer    : .\outillage\Register-NexusBoucleLocale.ps1 -Supprimer" -ForegroundColor Gray
exit 0