# ============================================================
# restore.ps1 - Script de restauration/reconstruction
# ============================================================
# Ce script arrête les conteneurs existants, supprime les volumes,
# recrée la stack et télécharge les modèles locaux.
# Utilisation : exécuter depuis le dossier contenant docker-compose.yml
# ============================================================

# ------------------------------------------------------------
# Configuration
# ------------------------------------------------------------
# Chemins absolus basés sur le répertoire du script
$scriptDir      = $PSScriptRoot
$envFile        = Join-Path $scriptDir '.env'
$envExampleFile = Join-Path $scriptDir '.env.example'
$modelListFile  = Join-Path $scriptDir 'model_list.txt'

# Nom du conteneur Ollama (modifiable dans docker-compose.yml)
$ollamaContainer = 'ollama-server'

# ------------------------------------------------------------
# Paramètres de robustesse
# ------------------------------------------------------------
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

# Démarrage du transcript (log)
$logFile = Join-Path $scriptDir ("restore_{0:yyyyMMdd_HHmmss}.log" -f (Get-Date))
Start-Transcript -Path $logFile -Append

# ------------------------------------------------------------
# Détermination de la commande docker compose (v2 ou v1)
# ------------------------------------------------------------
$dockerComposeCmd = 'docker compose'
try {
    & docker compose version *>$null
} catch {
    $dockerComposeCmd = 'docker-compose'
}

# ------------------------------------------------------------
# Vérifier que Docker est disponible
# ------------------------------------------------------------
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Error "Docker n'est pas installé ou pas dans le PATH."
    Stop-Transcript
    exit 1
}

# ------------------------------------------------------------
# Vérifier les prérequis avant toute destruction
# ------------------------------------------------------------
if (-not (Test-Path $envFile)) {
    if (Test-Path $envExampleFile) {
        Copy-Item $envExampleFile $envFile
        Write-Host "Fichier .env cree depuis .env.example. Renseignez vos cles API, puis relancez ce script."
    } else {
        Write-Error "Ni .env ni .env.example ne sont presentes. Rien n'a ete detruit."
    }
    Stop-Transcript
    exit 1
}

if (-not (Test-Path $modelListFile)) {
    Write-Error "Fichier model_list.txt introuvable. Abort."
    Stop-Transcript
    exit 1
}

# ------------------------------------------------------------
# Confirmation explicite de la suppression des volumes
# ------------------------------------------------------------
Write-Host "⚠️  Attention : cette operation va supprimer les volumes Docker (donnees PostgreSQL, modeles Ollama, cache Redis)."
Write-Host "Tapez 'OUI' pour confirmer, ou toute autre chose pour annuler."
$confirmation = Read-Host
if ($confirmation.Trim().ToUpper() -ne 'OUI') {
    Write-Host "Operation annulee par l'utilisateur."
    Stop-Transcript
    exit 0
}

# ------------------------------------------------------------
# Arrêter et supprimer les conteneurs et volumes
# ------------------------------------------------------------
try {
    & $dockerComposeCmd down -v
    if ($LASTEXITCODE -ne 0) { throw "docker compose down returned non-zero exit code." }
} catch {
    Write-Error "Echec lors du docker compose down. $_"
    Stop-Transcript
    exit 1
}

# ------------------------------------------------------------
# Démarrer la stack
# ------------------------------------------------------------
try {
    & $dockerComposeCmd up -d
    if ($LASTEXITCODE -ne 0) { throw "docker compose up returned non-zero exit code." }
} catch {
    Write-Error "Echec lors du docker compose up. La pile n'est pas demarree. $_"
    Stop-Transcript
    exit 1
}

# ------------------------------------------------------------
# Attendre que le conteneur Ollama soit ready
# ------------------------------------------------------------
Write-Host "Attente du demarrage d'Ollama..."
$maxAttempts = 30
$attempt = 0
$ollamaStatus = $null

do {
    $attempt++
    Start-Sleep -Seconds 2

    # Récupérer le statut health si défini, sinon le statut général
    $inspectResult = docker inspect --format='{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' $ollamaContainer 2>$null
    $ollamaStatus = $inspectResult.Trim()
} while ($ollamaStatus -ne 'healthy' -and $ollamaStatus -ne 'running' -and $attempt -lt $maxAttempts)

if ($ollamaStatus -ne 'healthy' -and $ollamaStatus -ne 'running') {
    Write-Error "Ollama n'est pas en etat 'healthy' ou 'running' après $($maxAttempts * 2) secondes. Verifiez les logs avec 'docker logs $ollamaContainer'."
    Stop-Transcript
    exit 1
}

# ------------------------------------------------------------
# Télécharger les modèles locaux
# ------------------------------------------------------------
$models = Get-Content -Path $modelListFile -Encoding UTF8 |
          Where-Object { $_ -notmatch '^NAME$' -and $_ -notmatch ':cloud$' -and $_ -notmatch '^\s*$' }

$successCount = 0
$failCount    = 0

foreach ($model in $models) {
    $model = $model.Trim()
    if ($model -eq '') { continue }

    Write-Host "Telechargement de $model..."
    & docker exec $ollamaContainer ollama pull "$model"
    if ($LASTEXITCODE -eq 0) {
        Write-Host "   ✔ Telechargement reussi."
        $successCount++
    } else {
        Write-Warning "   ❌ Echec du telechargement de $model."
        $failCount++
    }
}

# ------------------------------------------------------------
# Bilan du telechargement
# ------------------------------------------------------------
Write-Host ""
Write-Host "============================================================"
Write-Host " Bilan du telechargement des modeles locaux"
Write-Host "   Reussis : $successCount"
Write-Host "   Echecs  : $failCount"
Write-Host "============================================================"

if ($failCount -gt 0) {
    Stop-Transcript
    exit 1
}

# ------------------------------------------------------------
# Etat final de la stack (observabilite)
# ------------------------------------------------------------
Write-Host "Etat final de la stack :"
& $dockerComposeCmd ps

Write-Host "✅ Restauration terminee."

# ------------------------------------------------------------
# Nettoyage
# ------------------------------------------------------------
Stop-Transcript
