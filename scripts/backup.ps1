# ============================================================
# backup.ps1 - Sauvegarde de la configuration et des volumes
# ============================================================
# Crée une archive horodatée contenant :
#   - les fichiers essentiels (docker-compose.yml, litellm_config.yaml,
#     model_list.txt, cloud_models.txt, .env.example, .mcp.json)
#     .env est volontairement exclu : voir le commentaire de $configFiles
#   - en option (-IncludeVolumes), les volumes Docker (PostgreSQL, Redis)
# Utilisation :
#   .\backup.ps1                # sauvegarde des fichiers uniquement
#   .\backup.ps1 -IncludeVolumes # sauvegarde fichiers + volumes Docker
# ============================================================

param(
    [switch]$IncludeVolumes
)

# ------------------------------------------------------------
# Fonctions utilitaires
# ------------------------------------------------------------
function Write-Info($msg) {
    Write-Host $msg
}
function Write-Warn($msg) {
    Write-Host $msg -ForegroundColor Yellow
}
function Write-ErrorMsg($msg) {
    Write-Host $msg -ForegroundColor Red
}

# ------------------------------------------------------------
# Vérifications préliminaires
# ------------------------------------------------------------
# Docker doit être installé ET le daemon doit être actif
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-ErrorMsg "Docker n'est pas installé ou pas dans le PATH."
    exit 1
}
if (-not (docker info -ErrorAction SilentlyContinue)) {
    Write-ErrorMsg "Le daemon Docker ne semble pas être disponible."
    exit 1
}

# Espace disque libre (exigence minimale 200 Go)
$drive = Get-PSDrive -PSProvider FileSystem | Where-Object { $_.Root -eq 'C:\' }
if ($drive.Free -lt 200GB) {
    Write-Warn "Espace disque libre insuffisant (moins de 200 Go). La sauvegarde peut echouer."
}

# ------------------------------------------------------------
# Chemins de travail
# ------------------------------------------------------------
$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Definition
$backupRoot = "C:\backups"
$timestamp   = Get-Date -Format "yyyyMMdd-HHmmss"
$backupDir   = Join-Path $backupRoot "litellm-backup-$timestamp"

# Création du répertoire de sauvegarde (arrêt en cas d'échec)
try {
    New-Item -ItemType Directory -Path $backupDir -Force -ErrorAction Stop | Out-Null
} catch {
    Write-ErrorMsg "Impossible de creer le repertoire de sauvegarde $backupDir."
    exit 1
}

Write-Info "Creation de la sauvegarde dans $backupDir..."

# ------------------------------------------------------------
# Sauvegarde des fichiers de configuration
# ------------------------------------------------------------
$configFiles = @(
    "docker-compose.yml",
    "litellm_config.yaml",
    "model_list.txt",
    "cloud_models.txt",
    ".env.example",
    ".mcp.json"
)

$missingFile = $false
foreach ($file in $configFiles) {
    $fullPath = Join-Path $scriptRoot $file
    if (Test-Path $fullPath) {
        try {
            Copy-Item $fullPath -Destination $backupDir -Force -ErrorAction Stop
            Write-Info "  ✔ $file"
        } catch {
            Write-ErrorMsg "  ❌ Echec de copie du fichier $file"
            $missingFile = $true
        }
    } else {
        Write-Warn "  ⚠ Fichier introuvable : $file"
        $missingFile = $true
    }
}
if ($missingFile) {
    Write-ErrorMsg "Sauvegarde incomplete : un ou plusieurs fichiers de configuration sont manquants ou non copies."
    exit 1
}

# ------------------------------------------------------------
# Sauvegarde des volumes Docker (optionnel)
# ------------------------------------------------------------
$volumeEchoue = $false
if ($IncludeVolumes) {
    Write-Info "`nSauvegarde des volumes Docker..."

    $volumeDir = Join-Path $backupDir "volumes"
    try {
        New-Item -ItemType Directory -Path $volumeDir -Force -ErrorAction Stop | Out-Null
    } catch {
        Write-ErrorMsg "Impossible de creer le repertoire $volumeDir."
        exit 1
    }

    $volumes = @(
        @{ Name = "local-llm-docker_pgdata";      File = "pgdata.tar.gz" },
        @{ Name = "local-llm-docker_redis_data";  File = "redis_data.tar.gz" }
    )

    foreach ($vol in $volumes) {
        # Vérifier que le volume existe
        if (-not (docker volume inspect $vol.Name -ErrorAction SilentlyContinue)) {
            Write-Warn "  ⚠ Volume $($vol.Name) introuvable."
            $volumeEchoue = $true
            continue
        }

        Write-Info "  Archivage du volume $($vol.Name)..."
        docker run --rm -v "$($vol.Name):/volume" -v "${volumeDir}:/backup" alpine `
            tar czf "/backup/$($vol.File)" -C /volume . 2>$null

        if ($LASTEXITCODE -eq 0) {
            $archivePath = Join-Path $volumeDir $vol.File
            # Vérifier que l'archive n'est pas vide
            if ((Get-Item $archivePath).Length -gt 0) {
                Write-Info "    ✔ $($vol.File)"
            } else {
                Write-Warn "    ⚠ Archive vide pour $($vol.Name)"
                $volumeEchoue = $true
            }
        } else {
            Write-Warn "    ❌ Echec de sauvegarde du volume $($vol.Name)"
            $volumeEchoue = $true
        }
    }

    Write-Info ""
    Write-Info "  Volume Ollama non archive : 541 Go retéléchargeables depuis model_list.txt." -ForegroundColor DarkGray
    Write-Info "  Sauvegarde de l'irremplaçable : python scripts\nexus_preserve.py --backup" -ForegroundColor DarkGray
}

# ------------------------------------------------------------
# Rapport final
# ------------------------------------------------------------
if ($IncludeVolumes -and $volumeEchoue) {
    Write-ErrorMsg "`n❌ Sauvegarde INCOMPLETE dans $backupDir : au moins un volume n'a pas ete archive."
    exit 1
}

Write-Info "`n✅ Sauvegarde terminee dans $backupDir"
exit 0
