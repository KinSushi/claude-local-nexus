# ============================================================
# stop.ps1 - Arret de la stack sans suppression des volumes
# ============================================================
# Arrete et supprime les conteneurs, mais conserve les volumes
# (donnees PostgreSQL, modeles Ollama, cache Redis).
# Utilisation : executer depuis le dossier contenant docker-compose.yml
# ============================================================

# Verifier que Docker est disponible
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Error "Docker n'est pas installe ou pas dans le PATH."
    exit 1
}

# Arreter les conteneurs
Write-Host "Arret des conteneurs..."
docker compose down
if ($LASTEXITCODE -ne 0) {
    Write-Error "docker compose down a echoue (code $LASTEXITCODE)."
    exit 1
}

# Verifier que les services ne repondent plus (max 30 s)
Write-Host "Verification de l'arret des services..." -NoNewline
$serviceStillUp = $false
for ($i = 0; $i -lt 30; $i++) {
    Start-Sleep -Seconds 1
    try {
        $null = Invoke-WebRequest -Uri "http://localhost:4000/health/liveliness" `
                                    -TimeoutSec 2 -UseBasicParsing -ErrorAction Stop
        # Si la requete reussit, le service répond encore
        $serviceStillUp = $true
        Write-Host "." -NoNewline
    } catch {
        # La requete a echoue : le service n'est plus accessible
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
