<#
.SYNOPSIS
    Enregistre la boucle de traque : elle tourne sans personne.

.DESCRIPTION
    « Une regle non mecanisee ne protege pas, meme celui qui l'a ecrite le
    matin. » Une boucle tenue par une session meurt avec elle, et l'objectif
    -- traquer toutes les ameliorations possibles -- redevient alors une
    intention. Cette tache le rend durable.

    Elle lance, a intervalle regulier :
      nexus_traque.py    analyse statique, six classes de defauts
      nexus_state.py     regenere le cockpit, traque incluse

    Elle ne lance AUCUNE mesure. Le banc charge la machine et fausserait ce
    qu'il mesure s'il tournait pendant qu'on travaille -- piege deja paye ce
    jour-la, une mesure prise pendant un telechargement de 28 Go.

.EXAMPLE
    .\scripts\Register-NexusTraque.ps1
    .\scripts\Register-NexusTraque.ps1 -Minutes 30
    .\scripts\Register-NexusTraque.ps1 -Supprimer
#>
[CmdletBinding()]
param(
    [int]$Minutes = 10,
    [switch]$Supprimer
)

$ErrorActionPreference = "Stop"
try { [Console]::OutputEncoding = [Text.Encoding]::UTF8 } catch { }

$NomTache = "NexusTraque"

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
    [Console]::Error.WriteLine("Intervalle trop court : la traque relit tous les fichiers.")
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
    [Console]::Error.WriteLine("Python introuvable : la traque ne peut pas s'executer.")
    exit 1
}

$log = Join-Path $racine "logs\traque.log"
New-Item -ItemType Directory -Force (Split-Path $log) | Out-Null

# -Command et non -File : avec -File, tout ce qui suit le chemin du script lui
# est passe comme ARGUMENTS, et la redirection n'atteint jamais PowerShell.
# Mesure anterieure de ce depot : LastTaskResult 1, et aucun log -- un echec
# silencieux, precisement ce que le log devait empecher.
$py = $pythonCmd.Source.Replace("'", "''")
$rac = $racine.Replace("'", "''")
$lg = $log.Replace("'", "''")
$commande = "Set-Location '$rac'; " +
            "& '$py' scripts/nexus_traque.py --muet; " +
            "& '$py' scripts/nexus_state.py"
$arguments = "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden " +
             "-Command ""& { $commande } *> '$lg'"""

# Repetition sans fin, a partir de maintenant. La duree maximale est fixee a
# (rien) : une repetition bornee s'arreterait au bout d'un jour sans que rien
# ne le signale.
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) `
    -RepetitionInterval (New-TimeSpan -Minutes $Minutes)

$action = New-ScheduledTaskAction -Execute $pwshCmd.Source -Argument $arguments `
    -WorkingDirectory $racine

# Interactive, comme les autres taches de ce depot : la traque lit des
# fichiers du profil utilisateur, et un contexte sans session n'y accede pas
# de la meme facon.
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME `
    -LogonType Interactive -RunLevel Limited

$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable `
    -DontStopIfGoingOnBatteries -AllowStartIfOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 15)

if (Get-ScheduledTask -TaskName $NomTache -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName $NomTache -Confirm:$false
}
Register-ScheduledTask -TaskName $NomTache -Trigger $trigger -Action $action `
    -Principal $principal -Settings $settings `
    -Description "Traque des defauts et regeneration du cockpit, toutes les $Minutes min." | Out-Null

Write-Host "Tache $NomTache enregistree : toutes les $Minutes minutes." -ForegroundColor Green
Write-Host "  Journal   : $log" -ForegroundColor Gray
Write-Host "  Cockpit   : rituels/STATE.md" -ForegroundColor Gray
Write-Host "  Supprimer : .\scripts\Register-NexusTraque.ps1 -Supprimer" -ForegroundColor Gray
exit 0
