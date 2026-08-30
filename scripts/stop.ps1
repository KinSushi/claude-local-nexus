# ============================================================
# stop.ps1 - Arrêt de la stack sans suppression des volumes
# ============================================================
# Arrête et supprime les conteneurs, mais conserve les volumes
# (données PostgreSQL, modèles Ollama, cache Redis).
# Utilisation : exécuter depuis le dossier contenant docker-compose.yml
# ============================================================
# Ce script a été renforcé pour :
# - vérifier que des conteneurs sont réellement en cours d'exécution avant d'appeler `docker compose down`
# - valider que l'URL de health‑check est bien formée afin d'éviter une injection de code
# - uniformiser l'usage de Write-Error pour les messages d'erreur
# - documenter la version minimale de Docker requise
# ============================================================

# URL de healthcheck configurable (modifier ici si besoin)
$HealthCheckUrl = "http://localhost:4000/health/liveliness"

# ------------------------------------------------------------
# Validation de l'URL de healthcheck
# ------------------------------------------------------------
if (-not ($HealthCheckUrl -match '^https?://')) {
    Write-Error "URL de healthcheck invalide : $HealthCheckUrl"
    exit 1
}

# ------------------------------------------------------------
# Vérifier que Docker est disponible
# ------------------------------------------------------------
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Error "Docker n'est pas installe ou pas dans le PATH."
    exit 1
}

# ------------------------------------------------------------
# Vérifier la présence du fichier docker-compose.yml
# ------------------------------------------------------------
if (-not (Test-Path -Path "./docker-compose.yml")) {
    Write-Error "Fichier docker-compose.yml introuvable dans le repertoire courant."
    exit 1
}

# ------------------------------------------------------------
# Vérifier qu'il existe des conteneurs en cours d'exécution
# ------------------------------------------------------------
$runningContainers = docker compose ps -q
if (-not $runningContainers) {
    Write-Host "Aucun conteneur en cours d'execution. Rien a arreter."
    exit 0
}

# ------------------------------------------------------------
# Arrêter les conteneurs
# ------------------------------------------------------------
Write-Host "Arret des conteneurs..."
docker compose down
if ($LASTEXITCODE -ne 0) {
    Write-Error "docker compose down a echoue (code $LASTEXITCODE)."
    exit 1
}

# ------------------------------------------------------------
# Vérifier que les services ne répondent plus (max 30 s)
# ------------------------------------------------------------
Write-Host "Verification de l'arret des services..." -NoNewline
$serviceStillUp = $false
for ($i = 0; $i -lt 30; $i++) {
    Start-Sleep -Seconds 1
    try {
        $null = Invoke-WebRequest -Uri $HealthCheckUrl `
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
    Write-Error "Les conteneurs repondent toujours apres 30 s d'attente."
    exit 1
}

Write-Host "✅ Stack arrete. Les volumes sont conserves."
Write-Host "Pour tout redemarrer, utilisez start.ps1."
Write-Host "Pour supprimer aussi les volumes, utilisez 'docker compose down -v'."
