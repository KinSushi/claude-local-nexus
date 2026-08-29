<#
.SYNOPSIS
    Démarre la pile Claude-Local-Nexus, après contrôle de conformité.

.DESCRIPTION
    Le contrôle passe AVANT le démarrage, et il est bloquant. La raison
    n'est pas formelle : `Update-NexusModels.ps1` refusait déjà de
    redémarrer sur une configuration invalide, mais un `docker compose
    restart litellm` tapé à la main contournait entièrement cette garde —
    et c'est la commande que l'on tape réellement. Une garde que le chemin
    le plus court évite ne protège de rien.

    Ce que le contrôle couvre, et qu'un simple `docker compose up` ignore :

        configuration valide     aucun alias déclaré sans poids sur le moteur
        moteur cohérent          toutes les déclarations visent le MÊME moteur
        moteur joignable         démarrer devant un moteur éteint produit une
                                 passerelle qui accepte tout et échoue tout
        marqueurs AUTOGEN        zones générées appariées
        secrets présents         .env renseigné, variables non vides
        .env hors de git         refait à chaque fois : un `git add -A` suffit
        espace disque            avertissement

    Ce script ne télécharge plus de modèles. La version précédente les
    tirait par `docker exec ollama-server`, conteneur qui n'existe plus
    depuis la sortie du moteur hors de Docker — elle attendait soixante
    secondes un conteneur absent, puis échouait sur chaque modèle. Le
    rapatriement appartient à `nexus_pull_host.py`, qui sait mesurer la
    place avant de tirer.

.PARAMETER Force
    Démarre malgré un contrôle bloquant. À n'employer qu'en connaissance
    de cause : la non-conformité reste affichée.

.PARAMETER Restart
    Redémarre LiteLLM seul au lieu de monter toute la pile. Le contrôle
    s'applique de la même façon — c'est précisément le chemin qui
    l'évitait.

.EXAMPLE
    .\scripts\start.ps1
    .\scripts\start.ps1 -Restart
    .\scripts\start.ps1 -Force
#>
[CmdletBinding()]
param(
    [switch]$Force,
    [switch]$Restart
)

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$RepoRoot = Split-Path -Parent $PSScriptRoot

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Error "Docker n'est pas installe ou pas dans le PATH."
    exit 1
}

$python = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $python) { $python = (Get-Command py -ErrorAction SilentlyContinue).Source }
if (-not $python) {
    Write-Error "Python introuvable : le controle de conformite ne peut pas s'executer."
    exit 1
}

# ------------------------------------------------------------
# 1. Conformité — bloquant
# ------------------------------------------------------------
Write-Host ""
Write-Host "Controle de conformite avant demarrage..." -ForegroundColor Cyan
Push-Location $RepoRoot
try {
    & $python (Join-Path $PSScriptRoot "nexus_conformite.py") --avant-demarrage
    $conforme = ($LASTEXITCODE -eq 0)
} finally { Pop-Location }

if (-not $conforme) {
    if (-not $Force) {
        Write-Host ""
        Write-Host "  Demarrage refuse : la configuration n'est pas conforme." -ForegroundColor Red
        Write-Host "  Corrigez, ou forcez en connaissance de cause :" -ForegroundColor Yellow
        Write-Host "      .\scripts\start.ps1 -Force" -ForegroundColor Yellow
        Write-Host ""
        exit 1
    }
    # `-Force` ne rend pas la configuration conforme : il rend la decision
    # explicite. Le rappel reste affiche pour que personne ne decouvre
    # l'etat degrade trois heures plus tard dans un journal.
    Write-Host ""
    Write-Host "  -Force : demarrage malgre la non-conformite." -ForegroundColor Yellow
    Write-Host ""
}

# ------------------------------------------------------------
# 2. Démarrage
# ------------------------------------------------------------
Push-Location $RepoRoot
try {
    if ($Restart) {
        Write-Host "Redemarrage de LiteLLM..." -ForegroundColor Cyan
        docker compose restart litellm | Out-Null
    } else {
        Write-Host "Demarrage des conteneurs..." -ForegroundColor Cyan
        docker compose up -d | Out-Null
    }
} finally { Pop-Location }

# ------------------------------------------------------------
# 3. Attente de la passerelle
# ------------------------------------------------------------
Write-Host "Attente de la passerelle..." -NoNewline
$pret = $false
for ($i = 0; $i -lt 30; $i++) {
    Start-Sleep -Seconds 4
    try {
        $r = Invoke-WebRequest -Uri "http://localhost:4000/health/liveliness" `
            -TimeoutSec 5 -UseBasicParsing -ErrorAction Stop
        if ($r.StatusCode -eq 200) { $pret = $true; break }
    } catch { Write-Host "." -NoNewline }
}
Write-Host ""

if (-not $pret) {
    Write-Host "  LiteLLM ne repond pas apres 120 s." -ForegroundColor Red
    Write-Host "  Diagnostic : docker compose logs litellm --tail 80" -ForegroundColor Yellow
    exit 1
}
Write-Host "  Passerelle prete sur http://localhost:4000" -ForegroundColor Green

# ------------------------------------------------------------
# 4. Conformité runtime — la relève, qu'aucun contrôle statique ne couvre
# ------------------------------------------------------------
Push-Location $RepoRoot
try {
    & $python (Join-Path $PSScriptRoot "nexus_releve.py") | Out-Null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  Releve locale operationnelle." -ForegroundColor Green
    } else {
        Write-Host "  RELEVE INOPERANTE : le travail s'arreterait avec l'abonnement." -ForegroundColor Red
        Write-Host "  Diagnostic : python scripts/nexus_releve.py --tous" -ForegroundColor Yellow
    }
} finally { Pop-Location }

Write-Host ""
Write-Host "Modeles manquants : python scripts/nexus_pull_host.py --manquants" -ForegroundColor Gray
Write-Host ""
