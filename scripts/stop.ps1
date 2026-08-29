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
# Arrêter les conteneurs
Write-Host "Arrêt des conteneurs..."
docker compose down
if ($LASTEXITCODE -ne 0) {
    Write-Error "docker compose down a échoué (code $LASTEXITCODE)."
    exit 1
}

# Vérifier que les services ne répondent plus (max 30 s)
Write-Host "Vérification de l'arrêt des services..." -NoNewline
$serviceStillUp = $false
for ($i = 0; $i -lt 30; $i++) {
    Start-Sleep -Seconds 1
    try {
        $null = Invoke-WebRequest -Uri "http://localhost:4000/health/liveliness" `
                                    -TimeoutSec 2 -UseBasicParsing -ErrorAction Stop
        # Si la requête réussit, le service répond encore
        $serviceStillUp = $true
        Write-Host "." -NoNewline
    } catch {
        # La requête a échoué : le service n'est plus accessible
        $serviceStillUp = $false
        break
    }
}
Write-Host ""

if ($serviceStillUp) {
    Write-Error "Les conteneurs répondent toujours après 30 s d'attente."
    exit 1
}

Write-Host "✅ Stack arrêtée. Les volumes sont conservés."
Write-Host "Pour tout redémarrer, utilisez start.ps1."
Write-Host "Pour supprimer aussi les volumes, utilisez 'docker compose down -v'."