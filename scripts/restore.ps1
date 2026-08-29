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
$scriptDir      = Split-Path -Parent $MyInvocation.MyCommand.Definition
$envFile        = Join-Path $scriptDir '.env'
$envExampleFile = Join-Path $scriptDir '.env.example'
$modelListFile  = Join-Path $scriptDir 'model_list.txt'

# Nom du conteneur Ollama (modifiable dans docker-compose.yml)
$ollamaContainer = 'ollama-server'

# Détermination de la commande docker compose (v2 ou v1)
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
    exit 1
}

if (-not (Test-Path $modelListFile)) {
    Write-Error "Fichier model_list.txt introuvable. Abort."
    exit 1
}

# ------------------------------------------------------------
# Confirmation explicite de la suppression des volumes
# ------------------------------------------------------------
Write-Host "⚠️  Attention : cette operation va supprimer les volumes Docker (donnees PostgreSQL, modeles Ollama, cache Redis)."
Write-Host "Tapez 'OUI' pour confirmer, ou toute autre chose pour annuler."
$confirmation = Read-Host
if ($confirmation -ne 'OUI') {
    Write-Host "Operation annulee par l'utilisateur."
    exit 0
}

# ------------------------------------------------------------
# Arrêter et supprimer les conteneurs et volumes
# ------------------------------------------------------------
& $dockerComposeCmd down -v
if ($LASTEXITCODE -ne 0) {
    Write-Error "Echec lors du docker compose down."
    exit 1
}

# ------------------------------------------------------------
# Démarrer la stack
# ------------------------------------------------------------
& $dockerComposeCmd up -d
if ($LASTEXITCODE -ne 0) {
    Write-Error "Echec lors du docker compose up. La pile n'est pas demarree."
    exit 1
}

# ------------------------------------------------------------
# Attendre que le conteneur Ollama soit ready
# ------------------------------------------------------------
Write-Host "Attente du demarrage d'Ollama..."
$maxAttempts = 30
$attempt = 0
do {
    $attempt++
    Start-Sleep -Seconds 2
    $ollamaStatus = docker inspect --format='{{.State.Health.Status}}' $ollamaContainer 2>$null
} while ($ollamaStatus -ne 'healthy' -and $attempt -lt $maxAttempts)

if ($ollamaStatus -ne 'healthy') {
    Write-Error "Ollama n'est pas en etat 'healthy' après $($maxAttempts * 2) secondes. Verifiez les logs avec 'docker logs $ollamaContainer'."
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
    docker exec $ollamaContainer ollama pull "$model"

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
    exit 1
}

# ------------------------------------------------------------
# Etat final de la stack (observabilite)
# ------------------------------------------------------------
Write-Host "Etat final de la stack :"
& $dockerComposeCmd ps

Write-Host "✅ Restauration terminee."
