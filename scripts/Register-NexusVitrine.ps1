<#
.SYNOPSIS
    Enregistre la sauvegarde vitrine : le depot public reste presentable seul.

.DESCRIPTION
    « Quand tout est stable et sain, sauvegarde GitHub vitrine pro. » Tenue a
    la main, cette regle depend de quelqu'un qui y pense ; et une regle non
    mecanisee ne protege personne, pas meme celui qui l'a ecrite le matin.

    La tache lance nexus_vitrine.py, qui REFUSE de publier tant que l'etat
    n'est pas sain : arbre propre, .env non suivi, aucun motif de secret parmi
    les fichiers suivis, conformite a 0, rituel a 0, remote et amont presents.
    Un intervalle qui passe sans rien publier n'est donc pas un echec : c'est
    le garde-fou qui fait son travail, et le journal le dit.

    Elle ne mesure rien et ne corrige rien. Publier est le seul geste de ce
    depot a la fois sortant et IRREVERSIBLE -- ce qui part est indexable, et
    le retirer ensuite ne le retire pas des caches -- d'ou une tache qui
    n'ajoute aucune permission au script, seulement la regularite.

.EXAMPLE
    .\scripts\Register-NexusVitrine.ps1
    .\scripts\Register-NexusVitrine.ps1 -Heures 12
    .\scripts\Register-NexusVitrine.ps1 -Simulation
    .\scripts\Register-NexusVitrine.ps1 -Supprimer
#>
[CmdletBinding()]
param(
    [int]$Heures = 6,
    [switch]$Simulation,
    [switch]$Supprimer
)

$ErrorActionPreference = "Stop"
try { [Console]::OutputEncoding = [Text.Encoding]::UTF8 } catch { }

$NomTache = "NexusVitrine"

if ($Supprimer) {
    if (Get-ScheduledTask -TaskName $NomTache -ErrorAction SilentlyContinue) {
        Unregister-ScheduledTask -TaskName $NomTache -Confirm:$false
        Write-Host "Tache $NomTache supprimee." -ForegroundColor Green
    } else {
        Write-Host "Tache $NomTache absente : rien a supprimer." -ForegroundColor Yellow
    }
    exit 0
}

# Une heure au minimum. La vitrine enchaine conformite et rituel, qui appellent
# eux-memes le validateur et la passerelle : plus court, les executions se
# chevaucheraient et se mesureraient les unes les autres.
if ($Heures -lt 1) {
    [Console]::Error.WriteLine("Intervalle trop court : la vitrine enchaine conformite et rituel.")
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
    [Console]::Error.WriteLine("Python introuvable : la vitrine ne peut pas s'executer.")
    exit 1
}

# Refuser d'enregistrer une tache qui echouera a chaque reveil. Sans remote,
# le script bloquerait indefiniment sur son dernier controle, et le journal
# repeterait la meme ligne toutes les six heures sans que personne ne la lise.
$remote = & git -C $racine remote get-url origin 2>$null
if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($remote)) {
    [Console]::Error.WriteLine("Aucun remote 'origin' : rien a sauvegarder. Tache non enregistree.")
    exit 1
}

$log = Join-Path $racine "logs\vitrine.log"
New-Item -ItemType Directory -Force (Split-Path $log) | Out-Null

# -Command et non -File : avec -File, tout ce qui suit le chemin du script lui
# est passe comme ARGUMENTS, et la redirection n'atteint jamais PowerShell.
# Mesure anterieure de ce depot : LastTaskResult 1, et aucun log.
$py = $pythonCmd.Source.Replace("'", "''")
$rac = $racine.Replace("'", "''")
$lg = $log.Replace("'", "''")
$drapeau = if ($Simulation) { " --simulation" } else { "" }
$commande = "Set-Location '$rac'; " +
            "Write-Output ('=== ' + (Get-Date -Format s) + ' ==='); " +
            "& '$py' scripts/nexus_vitrine.py$drapeau"
$arguments = "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden " +
             "-Command ""& { $commande } *>> '$lg'"""

# Repetition sans fin. Une repetition bornee s'arreterait au bout d'un jour
# sans que rien ne le signale, et la vitrine vieillirait en silence.
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(5) `
    -RepetitionInterval (New-TimeSpan -Hours $Heures)

$action = New-ScheduledTaskAction -Execute $pwshCmd.Source -Argument $arguments `
    -WorkingDirectory $racine

# Interactive : git lit les identifiants dans le profil utilisateur, et un
# contexte sans session ouverte n'y accede pas de la meme facon -- le push
# echouerait sur une authentification absente plutot que sur un vrai defaut.
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME `
    -LogonType Interactive -RunLevel Limited

$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable `
    -DontStopIfGoingOnBatteries -AllowStartIfOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 30)

if (Get-ScheduledTask -TaskName $NomTache -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName $NomTache -Confirm:$false
}
$mode = if ($Simulation) { "simulation" } else { "publication reelle" }
Register-ScheduledTask -TaskName $NomTache -Trigger $trigger -Action $action `
    -Principal $principal -Settings $settings `
    -Description "Sauvegarde vitrine ($mode) toutes les $Heures h, si et seulement si l'etat est sain." | Out-Null

Write-Host "Tache $NomTache enregistree : toutes les $Heures heures ($mode)." -ForegroundColor Green
Write-Host "  Journal    : $log" -ForegroundColor Gray
Write-Host "  Remote     : $remote" -ForegroundColor Gray
Write-Host "  A la main  : python scripts/nexus_vitrine.py --simulation" -ForegroundColor Gray
Write-Host "  Supprimer  : .\scripts\Register-NexusVitrine.ps1 -Supprimer" -ForegroundColor Gray
exit 0
