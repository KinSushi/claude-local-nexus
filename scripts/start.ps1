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

# ------------------------------------------------------------
# Vérification de la disponibilité de Docker Compose (V2 ou V1)
# ------------------------------------------------------------
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Error "Docker n'est pas installe ou pas dans le PATH."
    exit 1
}

# Déterminer la commande Docker Compose à utiliser
$dockerComposeCmd = $null
try {
    docker compose version > $null 2>&1
    if ($LASTEXITCODE -eq 0) { $dockerComposeCmd = 'docker compose' }
} catch { }

if (-not $dockerComposeCmd) {
    if (Get-Command 'docker-compose' -ErrorAction SilentlyContinue) {
        $dockerComposeCmd = 'docker-compose'
    } else {
        Write-Error "Docker Compose (v2) ou docker-compose (v1) introuvable."
        exit 1
    }
}

# ------------------------------------------------------------
# Vérification de Python
# ------------------------------------------------------------
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
    $conformiteScript = Join-Path $PSScriptRoot "nexus_conformite.py"
    if (-not (Test-Path $conformiteScript)) {
        Write-Error "Fichier manquant : $conformiteScript"
        exit 1
    }
    & $python $conformiteScript --avant-demarrage
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
    Write-Host ""
    Write-Host "  -Force : demarrage malgre la non-conformite." -ForegroundColor Yellow
    Write-Host ""
}

# ------------------------------------------------------------
# 2. Demarrage
# ------------------------------------------------------------
Push-Location $RepoRoot
try {
    if ($Restart) {
        Write-Host "Redemarrage de LiteLLM..." -ForegroundColor Cyan
        & $dockerComposeCmd restart litellm
        $exitCode = $LASTEXITCODE
        if ($exitCode -ne 0) {
            Write-Host "Erreur: $dockerComposeCmd restart litellm a renvoye un code $exitCode" -ForegroundColor Red
            exit $exitCode
        }
    } else {
        Write-Host "Demarrage des conteneurs..." -ForegroundColor Cyan
        & $dockerComposeCmd up -d
        $exitCode = $LASTEXITCODE
        if ($exitCode -ne 0) {
            Write-Host "Erreur: $dockerComposeCmd up -d a renvoye un code $exitCode" -ForegroundColor Red
            exit $exitCode
        }
    }
} finally { Pop-Location }

# ------------------------------------------------------------
# 3. Attente de la passerelle
# ------------------------------------------------------------
$HealthUrl = "http://localhost:4000/health/liveliness"
Write-Host "Attente de la passerelle..." -NoNewline
$pret = $false
# Timeout configurable : 40 itérations de 4s = 160s
for ($i = 0; $i -lt 40; $i++) {
    Start-Sleep -Seconds 4
    try {
        $r = Invoke-WebRequest -Uri $HealthUrl -TimeoutSec 5 -ErrorAction Stop
        if ($r.StatusCode -eq 200) { $pret = $true; break }
    } catch { Write-Host "." -NoNewline }
}
Write-Host ""

if (-not $pret) {
    Write-Host "  LiteLLM ne repond pas apres 160 s." -ForegroundColor Red
    Write-Host "  Diagnostic : $dockerComposeCmd logs litellm --tail 80" -ForegroundColor Yellow
    exit 1
}
Write-Host "  Passerelle prete sur $HealthUrl" -ForegroundColor Green

# ------------------------------------------------------------
# 4. Conformité runtime — la relève, qu'aucun contrôle statique ne couvre
# ------------------------------------------------------------
Push-Location $RepoRoot
try {
    $releveScript = Join-Path $PSScriptRoot "nexus_releve.py"
    if (-not (Test-Path $releveScript)) {
        Write-Error "Fichier manquant : $releveScript"
        exit 1
    }
    & $python $releveScript | Out-Null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  Releve locale operationnelle." -ForegroundColor Green
    } else {
        Write-Host "  RELEVE INOPERANTE : le travail s'arreterait avec l'abonnement." -ForegroundColor Red
        Write-Host "  Diagnostic : python scripts/nexus_releve.py --tous" -ForegroundColor Yellow
        exit $LASTEXITCODE
    }
} finally { Pop-Location }

Write-Host ""
Write-Host "Modeles manquants : python scripts/nexus_pull_host.py --manquants" -ForegroundColor Gray
Write-Host ""
