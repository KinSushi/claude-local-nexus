# ============================================================
# start.ps1 - Démarrage de la stack et vérification des modèles
# ============================================================
# Démarre les conteneurs, attend qu'ils soient prêts,
# puis télécharge les modèles locaux manquants.
# Utilisation : exécuter depuis le dossier contenant docker-compose.yml
# ============================================================

# Vérifier que Docker est disponible
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Error "Docker n'est pas installé ou pas dans le PATH."
    exit 1
}

# Démarrer la stack
Write-Host "Démarrage des conteneurs..."
docker compose up -d

# Attendre que le conteneur Ollama soit healthy
Write-Host "Attente du démarrage d'Ollama..."
$maxAttempts = 30
$attempt = 0
$ollamaStatus = ""
do {
    $attempt++
    Start-Sleep -Seconds 2
    $ollamaStatus = docker inspect --format='{{.State.Health.Status}}' ollama-server 2>$null
} while ($ollamaStatus -ne "healthy" -and $attempt -lt $maxAttempts)

if ($ollamaStatus -ne "healthy") {
    Write-Warning "Ollama n'est pas prêt après $($maxAttempts * 2) secondes. Vérifiez les logs avec 'docker logs ollama-server'."
}

# Télécharger les modèles locaux si nécessaire
$models = Get-Content model_list.txt | Where-Object { $_ -notmatch '^NAME$' -and $_ -notmatch ':cloud$' -and $_ -notmatch '^\s*$' }
foreach ($model in $models) {
    $model = $model.Trim()
    if ($model -eq "") { continue }
    $exists = docker exec ollama-server ollama list | Select-String -Pattern "^$([regex]::Escape($model))\s"
    if (-not $exists) {
        Write-Host "Téléchargement de $model..."
        docker exec ollama-server ollama pull $model
    } else {
        Write-Host "$model déjà présent, ignoré."
    }
}

Write-Host "✅ Stack démarrée et modèles prêts."