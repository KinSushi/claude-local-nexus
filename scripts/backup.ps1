# ============================================================
# backup.ps1 - Sauvegarde de la configuration et des volumes
# ============================================================
# Crée une archive horodatée contenant :
#   - les fichiers essentiels (docker-compose.yml, litellm_config.yaml, model_list.txt, cloud_models.txt, .env.example, .mcp.json)
#     .env est volontairement exclu : voir le commentaire de $configFiles
#   - en option (-IncludeVolumes), les volumes Docker (PostgreSQL, Ollama, Redis)
# Utilisation :
#   .\backup.ps1                # sauvegarde des fichiers uniquement
#   .\backup.ps1 -IncludeVolumes # sauvegarde fichiers + volumes Docker
# ============================================================

param(
    [switch]$IncludeVolumes
)

# Vérifier que Docker est disponible
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Error "Docker n'est pas installé ou pas dans le PATH."
    exit 1
}

$backupRoot = "C:\backups"
$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$backupDir = Join-Path $backupRoot "litellm-backup-$timestamp"
New-Item -ItemType Directory -Path $backupDir -Force | Out-Null

Write-Host "Création de la sauvegarde dans $backupDir..."

# --- Sauvegarde des fichiers de configuration ---
$configFiles = @(
    "docker-compose.yml",
    "litellm_config.yaml",
    "model_list.txt",
    "cloud_models.txt",
    ".env.example",
    # .mcp.json manquait a cette liste alors qu'il declare le pont par
    # lequel Claude Code atteint les modeles locaux. Sa corruption ne
    # produit aucune erreur visible : le serveur demarre, s'annonce
    # connecte, et sept outils sur douze cessent d'atteindre le disque.
    # Une sauvegarde qui omet le fichier dont la panne est silencieuse
    # protege precisement du mauvais risque.
    ".mcp.json"
    # .env est volontairement ABSENT de cette liste.
    #
    # Il était copié dans le dossier de sauvegarde, qui hérite de l'ACL de
    # la racine du disque : le groupe Utilisateurs y dispose de
    # ReadAndExecute avec héritage. Autrement dit, tout compte local
    # pouvait lire la clé maîtresse, le mot de passe PostgreSQL et les
    # clés API. Le commentaire d'origine — « pensez à le sécuriser » —
    # reconnaissait le problème sans le traiter.
    #
    # Un secret ne se sauvegarde pas à côté du dépôt : il se conserve
    # ailleurs, délibérément, dans un gestionnaire de secrets.
)

foreach ($file in $configFiles) {
    if (Test-Path $file) {
        Copy-Item $file -Destination $backupDir -Force
        Write-Host "  ✔ $file"
    } else {
        Write-Warning "  ⚠ Fichier introuvable : $file"
    }
}

# --- Sauvegarde des volumes Docker (optionnel) ---
if ($IncludeVolumes) {
    Write-Host "`nSauvegarde des volumes Docker..."

    $volumeDir = Join-Path $backupDir "volumes"
    New-Item -ItemType Directory -Path $volumeDir -Force | Out-Null

    # Le volume Ollama est volontairement absent de cette liste.
    #
    # Il pèse 541 Go pour 155 Go de disque libre : l'archiver échouerait, et
    # réussirait-il qu'il serait inutile. Les poids de modèles ont une source
    # publique et un manifeste local — `model_list.txt` les reconstitue par
    # `ollama pull`. Sauvegarder ce qui se retélécharge coûte du disque pour
    # ne rien préserver.
    #
    # Ce qui n'a aucune source de reconstruction — l'historique de dépense,
    # les sessions de routage, les clés — tient dans 84 Mo et se sauvegarde
    # mieux en dump SQL qu'en archive de volume :
    #     python scripts/nexus_preserve.py --backup
    $volumes = @(
        @{ Name = "local-llm-docker_pgdata";      File = "pgdata.tar.gz" },
        @{ Name = "local-llm-docker_redis_data";  File = "redis_data.tar.gz" }
    )

    foreach ($vol in $volumes) {
        Write-Host "  Archivage du volume $($vol.Name)..."
        docker run --rm -v "${($vol.Name)}:/volume" -v "${volumeDir}:/backup" alpine tar czf "/backup/$($vol.File)" -C /volume .
        if ($LASTEXITCODE -eq 0) {
            Write-Host "    ✔ $($vol.File)"
        } else {
            Write-Warning "    ❌ Échec de sauvegarde du volume $($vol.Name)"
        }
    }

    Write-Host ""
    Write-Host "  Volume Ollama non archivé : 541 Go retéléchargeables depuis model_list.txt." -ForegroundColor DarkGray
    Write-Host "  Sauvegarde de l'irremplaçable : python scripts\nexus_preserve.py --backup" -ForegroundColor DarkGray
}

Write-Host "`n✅ Sauvegarde terminée dans $backupDir"