# ============================================================
# restore.ps1 - Script de restauration/reconstruction
# ============================================================
# Ce script arrête les conteneurs existants, supprime les volumes,
# recrée la stack et télécharge les modèles locaux.
# Utilisation : exécuter depuis le dossier contenant docker-compose.yml
# ============================================================

# Vérifier que Docker est disponible
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Error "Docker n'est pas installé ou pas dans le PATH."
    exit 1
}

# Avertissement : suppression des volumes
Write-Host "⚠️  Attention : cette opération va supprimer les volumes Docker (données PostgreSQL, modèles Ollama, cache Redis)."
Write-Host "Appuyez sur Ctrl+C pour annuler, ou Entrée pour continuer..."
Read-Host

# Arrêter et supprimer les conteneurs et volumes
docker compose down -v

# Créer le fichier .env à partir de .env.example si absent
if (-not (Test-Path .env)) {
    Copy-Item .env.example .env
    Write-Host "Fichier .env créé depuis .env.example. Veuillez éditer .env et renseigner vos clés API avant de relancer ce script."
    exit 0
}

# Démarrer la stack
docker compose up -d

# Attendre que le conteneur Ollama soit prêt
Write-Host "Attente du démarrage d'Ollama..."
$maxAttempts = 30
$attempt = 0
do {
    $attempt++
    Start-Sleep -Seconds 2
    $ollamaStatus = docker inspect --format='{{.State.Health.Status}}' ollama-server 2>$null
} while ($ollamaStatus -ne "healthy" -and $attempt -lt $maxAttempts)

if ($ollamaStatus -ne "healthy") {
    Write-Warning "Ollama n'est pas prêt après $($maxAttempts * 2) secondes. Vérifiez les logs avec 'docker logs ollama-server'."
}

# Télécharger les modèles locaux
$models = Get-Content model_list.txt | Where-Object { $_ -notmatch '^NAME$' -and $_ -notmatch ':cloud$' -and $_ -notmatch '^\s*$' }
foreach ($model in $models) {
    $model = $model.Trim()
    if ($model -eq "") { continue }
    Write-Host "Téléchargement de $model..."
    docker exec ollama-server ollama pull $model
}

Write-Host "✅ Restauration terminée."