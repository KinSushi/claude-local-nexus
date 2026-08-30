<#
.SYNOPSIS
    Demarre la pile Claude-Local-Nexus, apres controle de conformite.

.DESCRIPTION
    Le controle passe AVANT le demarrage, et il est bloquant. La raison
    n'est pas formelle : `Update-NexusModels.ps1` refusait deja de
    redemarrer sur une configuration invalide, mais un `docker compose
    restart litellm` tape a la main contournait entièrement cette garde —
    et c'est la commande que l'on tape réellement. Une garde que le chemin
    le plus court evite ne protege de rien.

    Ce que le controle couvre, et qu'un simple `docker compose up` ignore :

        configuration valide     aucun alias declare sans poids sur le moteur
        moteur coherent          toutes les declarations visent le MEME moteur
        moteur joignable         demarrer devant un moteur eteint produit une
                                 passerelle qui accepte tout et echoue tout
        marqueurs AUTOGEN        zones generees appariees
        secrets presents         .env renseigne, variables non vides
        .env hors de git         refait a chaque fois : un `git add -A` suffit
        espace disque            avertissement

    Ce script ne telecharge plus de modeles. La version precedente les
    tirait par `docker exec ollama-server`, conteneur qui n'existe plus
    depuis la sortie du moteur hors de Docker — elle attendait soixante
    secondes un conteneur absent, puis echouait sur chaque modele. Le
    rapatriement appartient a `nexus_pull_host.py`, qui sait mesurer la
    place avant de tirer.

.PARAMETER Force
    Demarre malgré un controle bloquant. A n'employer qu'en connaissance
    de cause : la non-conformite reste affichee.

.PARAMETER Verifier
    Enchaine `Test-NexusSmoke.ps1 -IncludeRouters` : execution locale,
    execution cloud, embeddings et les trois routeurs, contre la pile qui
    vient de demarrer. Hors du chemin par defaut, parce que charger un
    modele local prend des minutes sur cette machine -- redemarrer vite et
    verifier a fond sont deux besoins distincts.

.PARAMETER Restart
    Redemarre LiteLLM seul au lieu de monter toute la pile. Le controle
    s'applique de la meme facon — c'est precisely le chemin qui
    l'evitait.

.EXAMPLE
    .\scripts\start.ps1
    .\scripts\start.ps1 -Restart
    .\scripts\start.ps1 -Force
    .\scripts\start.ps1 -Verifier
#>
[CmdletBinding()]
param(
    [switch]$Force,
    [switch]$Restart,
    [switch]$Verifier
)

# Gestion des erreurs locale : on garde le comportement "Stop" pour les blocs critiques
$ErrorActionPreference = 'Stop'

# Une erreur terminante interrompt le script mais ne fixe AUCUN code de
# sortie : PowerShell rend alors 0, et la reprise passe pour reussie alors
# que rien n'a demarre. C'est arrive. Le piege se ferme ici.
trap {
    Write-Host ""
    Write-Host "  Interruption : $_" -ForegroundColor Red
    Write-Host ""
    exit 1
}

# Encodage complet pour les flux PowerShell et les processus externes
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

$RepoRoot = Split-Path -Parent $PSScriptRoot

# ------------------------------------------------------------
# Moteur Ollama : hors de la pile, donc a rallumer soi-meme
#
# Le moteur ne tourne plus dans Docker (service `ollama` sous profile
# `embedded`, non lance) mais sur l'hote. Or il n'a AUCUNE entree de
# demarrage automatique, la ou Docker Desktop en a une : apres un
# redemarrage de la machine, la pile remonte seule et le moteur non.
# Le controle de conformite echouait alors sur « moteur joignable » et
# start.ps1 s'arretait sans remede -- un chemin de reprise qui constate
# la panne sans la reparer ne fait pas gagner de temps.
# ------------------------------------------------------------
function Confirm-MoteurOllama {
    $sonde = "http://127.0.0.1:11434/api/version"

    # On teste AVANT d'attendre : quand le moteur tourne deja, ce chemin
    # ne coute rien.
    try {
        Invoke-WebRequest -Uri $sonde -TimeoutSec 3 -ErrorAction Stop | Out-Null
        Write-Host "  Moteur Ollama deja en service." -ForegroundColor Green
        return $true
    } catch { }

    $ollama = (Get-Command ollama -ErrorAction SilentlyContinue).Source
    if (-not $ollama) {
        $repli = Join-Path $env:LOCALAPPDATA "Programs\Ollama\ollama.exe"
        if (Test-Path $repli) { $ollama = $repli }
    }
    if (-not $ollama) {
        Write-Host "  Moteur Ollama introuvable : ni dans le PATH, ni dans" -ForegroundColor Red
        Write-Host "  $env:LOCALAPPDATA\Programs\Ollama\ollama.exe" -ForegroundColor Red
        Write-Host "  Installer depuis https://ollama.com/download, ou basculer la" -ForegroundColor Yellow
        Write-Host "  pile sur le moteur embarque : docker compose --profile embedded up -d" -ForegroundColor Yellow
        return $false
    }

    Write-Host "  Moteur eteint, demarrage de $ollama serve..." -ForegroundColor Cyan
    # -WindowStyle Hidden et non -NoNewWindow : ce dernier rattache le
    # serveur a la console courante, ou il mourrait avec elle. Le moteur
    # doit survivre a ce script.
    Start-Process -FilePath $ollama -ArgumentList "serve" -WindowStyle Hidden | Out-Null

    for ($i = 0; $i -lt 30; $i++) {
        Start-Sleep -Seconds 1
        try {
            Invoke-WebRequest -Uri $sonde -TimeoutSec 2 -ErrorAction Stop | Out-Null
            Write-Host "  Moteur Ollama pret apres $($i + 1) s." -ForegroundColor Green
            return $true
        } catch { }
    }

    Write-Host "  Moteur Ollama lance mais muet apres 30 s." -ForegroundColor Red
    Write-Host "  Diagnostic : ollama serve  (en avant-plan, pour voir l'erreur)" -ForegroundColor Yellow
    return $false
}

# ------------------------------------------------------------
# Verification de la disponibilite de Docker Compose (V2 ou V1)
# ------------------------------------------------------------
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Error "Docker n'est pas installe ou pas dans le PATH."
    exit 1
}

# Determiner la commande Docker Compose a utiliser.
#
# Executable et arguments sont separes a dessein. La version precedente
# gardait la chaine 'docker compose' entiere, et `& $cmd up -d` cherchait
# alors une commande NOMMEE « docker compose » : elle echouait toujours,
# aucun conteneur ne demarrait, et le script rendait pourtant 0.
$composeExe  = $null
$composeArgs = @()
try {
    docker compose version > $null 2>&1
    if ($LASTEXITCODE -eq 0) { $composeExe = 'docker'; $composeArgs = @('compose') }
} catch { }

if (-not $composeExe) {
    if (Get-Command 'docker-compose' -ErrorAction SilentlyContinue) {
        $composeExe = 'docker-compose'
    } else {
        Write-Error "Docker Compose (v2) ou docker-compose (v1) introuvable."
        exit 1
    }
}
# Pour les messages uniquement.
$composeNom = (@($composeExe) + $composeArgs) -join ' '

# ------------------------------------------------------------
# Verification de Python (python, py, python3)
# ------------------------------------------------------------
$python = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $python) { $python = (Get-Command py -ErrorAction SilentlyContinue).Source }
if (-not $python) { $python = (Get-Command python3 -ErrorAction SilentlyContinue).Source }
if (-not $python) {
    Write-Error "Python introuvable : le controle de conformite ne peut pas s'executer."
    exit 1
}

# ------------------------------------------------------------
# 0. Moteur — avant la conformite, qui le controle
# ------------------------------------------------------------
Write-Host ""
Write-Host "Moteur d'inference..." -ForegroundColor Cyan
if (-not (Confirm-MoteurOllama)) {
    if (-not $Force) {
        Write-Host ""
        Write-Host "  Demarrage refuse : sans moteur, la passerelle accepterait" -ForegroundColor Red
        Write-Host "  toutes les requetes et les ferait toutes echouer." -ForegroundColor Red
        Write-Host "  Passer outre en connaissance de cause : .\scripts\start.ps1 -Force" -ForegroundColor Yellow
        Write-Host ""
        exit 1
    }
    Write-Host "  -Force : poursuite sans moteur local." -ForegroundColor Yellow
}

# ------------------------------------------------------------
# 1. Conformite — bloquant
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
        & $composeExe @composeArgs restart litellm
        $exitCode = $LASTEXITCODE
        if ($exitCode -ne 0) {
            Write-Host "Erreur: $composeNom restart litellm a renvoye un code $exitCode" -ForegroundColor Red
            exit $exitCode
        }
    } else {
        Write-Host "Demarrage des conteneurs..." -ForegroundColor Cyan
        & $composeExe @composeArgs up -d
        $exitCode = $LASTEXITCODE
        if ($exitCode -ne 0) {
            Write-Host "Erreur: $composeNom up -d a renvoye un code $exitCode" -ForegroundColor Red
            exit $exitCode
        }
    }
} finally { Pop-Location }

# ------------------------------------------------------------
# 3. Attente de la passerelle
# ------------------------------------------------------------
# URL de santé configurable via la variable d'environnement HEALTH_URL
$HealthUrl = $env:HEALTH_URL
if (-not $HealthUrl) { $HealthUrl = "http://localhost:4000/health/liveliness" }

Write-Host "Attente de la passerelle..." -NoNewline
$pret = $false
# Timeout configurable : 60 iterations de 4s = 240s
for ($i = 0; $i -lt 60; $i++) {
    # L'attente vient APRES le premier essai : sur un `-Restart`, la
    # passerelle repond souvent tout de suite, et dormir d'abord ajoutait
    # quatre secondes a chaque reprise sans jamais rien verifier.
    if ($i -gt 0) { Start-Sleep -Seconds 4 }
    try {
        $r = Invoke-WebRequest -Uri $HealthUrl -TimeoutSec 5 -ErrorAction Stop
        if ($r.StatusCode -eq 200) { $pret = $true; break }
    } catch { Write-Host "." -NoNewline }
}
Write-Host ""

if (-not $pret) {
    Write-Host "  LiteLLM ne repond pas apres 240 s." -ForegroundColor Red
    Write-Host "  Diagnostic : $composeNom logs litellm --tail 80" -ForegroundColor Yellow
    exit 1
}
Write-Host "  Passerelle prete sur $HealthUrl" -ForegroundColor Green

# ------------------------------------------------------------
# 4. Conformite runtime — la releve, qu'aucun controle statique ne couvre
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

# ------------------------------------------------------------
# 5. Verification de bout en bout — sur demande
# ------------------------------------------------------------
if ($Verifier) {
    Write-Host ""
    Write-Host "Verification de bout en bout (local, cloud, routeurs)..." -ForegroundColor Cyan
    $smoke = Join-Path $PSScriptRoot "Test-NexusSmoke.ps1"
    if (-not (Test-Path $smoke)) {
        Write-Host "  Fichier manquant : $smoke" -ForegroundColor Red
        exit 1
    }
    & $smoke -IncludeRouters
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  Pile demarree, mais la verification a echoue." -ForegroundColor Red
        exit $LASTEXITCODE
    }
}

Write-Host ""
Write-Host "Modeles manquants : python scripts/nexus_pull_host.py --manquants" -ForegroundColor Gray
Write-Host ""
