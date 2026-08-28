# ============================================================
# stop.ps1 - Arrêt de la stack sans suppression des volumes
# ============================================================
# Arrête et supprime les conteneurs, mais conserve les volumes
# (données PostgreSQL, modèles Ollama, cache Redis).
# Utilisation : exécuter depuis le dossier contenant docker-compose.yml
# ============================================================

# Vérifier que Docker est disponible
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Error "Docker n'est pas installé ou pas dans le PATH."
    exit 1
}

# Arrêter les conteneurs
Write-Host "Arrêt des conteneurs..."
docker compose down

Write-Host "✅ Stack arrêtée. Les volumes sont conservés."
Write-Host "Pour tout redémarrer, utilisez start.ps1."
Write-Host "Pour supprimer aussi les volumes, utilisez 'docker compose down -v'."