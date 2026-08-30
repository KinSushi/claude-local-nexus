<#
.SYNOPSIS
    Rend la commande `nexus` disponible depuis n'importe quel repertoire.

.DESCRIPTION
    Ajoute au profil PowerShell une fonction `nexus` qui relaie vers
    scripts/nexus.ps1. Sans elle, chaque appel demande le chemin absolu de
    l'installation -- exact, mais long et facile a oublier.

    Le bloc insere est encadre de marqueurs, si bien qu'une reinstallation
    le remplace au lieu de l'empiler. Sans marqueurs, chaque passage
    ajouterait une definition de plus, et la derniere lue gagnerait
    silencieusement.

    La fonction verifie l'existence du script avant d'appeler. Ce n'est pas
    de la prudence gratuite : les profils PowerShell sont frequemment places
    dans un dossier Documents synchronise (OneDrive), donc repliques sur des
    machines ou cette installation n'existe pas. Mieux vaut un avertissement
    qu'une erreur a chaque ouverture de terminal.

.PARAMETER Remove
    Retire le bloc du profil au lieu de l'installer.

.PARAMETER Profil
    Chemin du profil a modifier. Defaut : $PROFILE de la session courante.

.EXAMPLE
    .\scripts\Install-NexusCommande.ps1
    .\scripts\Install-NexusCommande.ps1 -Remove
#>
[CmdletBinding()]
param(
    [switch]$Remove,
    [string]$Profil = $PROFILE
)

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$racine = Split-Path -Parent $PSScriptRoot
$cible  = (Join-Path $PSScriptRoot 'nexus.ps1') -replace '\\', '/'

$debut = '# >>> CLAUDE-LOCAL-NEXUS'
$fin   = '# <<< CLAUDE-LOCAL-NEXUS'

# ------------------------------------------------------------
# Retrait du bloc existant, commun aux deux modes
# ------------------------------------------------------------
$contenu = ''
if (Test-Path $Profil) {
    $contenu = Get-Content $Profil -Raw
    if ($null -eq $contenu) { $contenu = '' }
}

$motif = [regex]::Escape($debut) + '.*?' + [regex]::Escape($fin) + '\r?\n?'
$sansBloc = [regex]::Replace($contenu, $motif, '', 'Singleline')

if ($Remove) {
    if ($sansBloc -eq $contenu) {
        Write-Host "Aucun bloc Claude-Local-Nexus dans $Profil" -ForegroundColor Yellow
        exit 0
    }
    [System.IO.File]::WriteAllText($Profil, $sansBloc, (New-Object System.Text.UTF8Encoding($false)))
    Write-Host "Commande 'nexus' retiree de $Profil" -ForegroundColor Green
    Write-Host "Ouvrez un nouveau terminal pour que le retrait prenne effet." -ForegroundColor Gray
    exit 0
}

# ------------------------------------------------------------
# Installation
# ------------------------------------------------------------
if (-not (Test-Path (Join-Path $PSScriptRoot 'nexus.ps1'))) {
    Write-Error "Introuvable : $(Join-Path $PSScriptRoot 'nexus.ps1')"
    exit 1
}

$dossier = Split-Path -Parent $Profil
if ($dossier -and -not (Test-Path $dossier)) {
    New-Item -ItemType Directory -Path $dossier -Force | Out-Null
}

$bloc = @"
$debut
function nexus {
    `$script = "$cible"
    if (-not (Test-Path `$script)) {
        Write-Host "Claude-Local-Nexus introuvable : `$script" -ForegroundColor Yellow
        return
    }
    & `$script @args
}
$fin
"@

$nouveau = $sansBloc.TrimEnd()
if ($nouveau) { $nouveau += [Environment]::NewLine + [Environment]::NewLine }
$nouveau += $bloc + [Environment]::NewLine

[System.IO.File]::WriteAllText($Profil, $nouveau, (New-Object System.Text.UTF8Encoding($false)))

Write-Host ""
Write-Host "Commande 'nexus' installee." -ForegroundColor Green
Write-Host "  Profil     : $Profil"
Write-Host "  Relais     : $cible"
if ($Profil -like '*OneDrive*') {
    Write-Host ""
    Write-Host "  Note : ce profil est dans OneDrive, donc synchronise sur vos" -ForegroundColor Yellow
    Write-Host "  autres machines. La fonction y avertira sans echouer si" -ForegroundColor Yellow
    Write-Host "  l'installation n'y existe pas." -ForegroundColor Yellow
}
Write-Host ""
Write-Host "  Actif dans un NOUVEAU terminal, ou tout de suite avec :" -ForegroundColor Gray
Write-Host "      . `$PROFILE" -ForegroundColor Gray
Write-Host "  Desinstallation : .\scripts\Install-NexusCommande.ps1 -Remove" -ForegroundColor Gray
Write-Host ""
