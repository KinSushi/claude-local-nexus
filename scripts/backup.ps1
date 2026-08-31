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
    [switch]$IncludeVolumes,
    [string]$BackupRoot = "C:\backups"   # chemin configurable, valeur par défaut
)

# L'encodage de sortie, fixe avant le premier caractere affiche.
#
# Sans cela la console rend « ? » a la place de chaque coche, croix ou
# accent : une sauvegarde reussie s'affiche alors comme une suite de points
# d'interrogation, que l'operateur lit comme des erreurs.
#
# Enveloppe dans un try : certains hotes refusent de changer l'encodage
# d'un flux redirige. Un souci d'affichage ne doit jamais faire echouer une
# sauvegarde -- ce serait echanger un defaut cosmetique contre un vrai.
try { [Console]::OutputEncoding = [Text.Encoding]::UTF8 } catch { }

# ------------------------------------------------------------
# Variables globales
# ------------------------------------------------------------
# PORTEE SCRIPT, ET NON GLOBALE.
#
# CE QUI ETAIT FAUX. `$global:` fait vivre la variable dans la SESSION de
# l'operateur, bien apres la fin du script -- une sauvegarde ne doit rien
# laisser derriere elle.
#
# Et la globale ne servait meme pas : la ligne qui assigne reellement le
# repertoire, plus bas, cree une variable de portee SCRIPT, que
# `Cleanup-And-Exit` lit par la portee parente. La globale etait donc
# vestigiale, et polluait pour rien.
$script:backupDir = $null   # initialise pour Cleanup-And-Exit

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
function Cleanup-And-Exit([int]$code, [string]$msg) {
    if ($null -ne $backupDir -and (Test-Path $backupDir)) {
        try {
            Remove-Item -Recurse -Force $backupDir -ErrorAction Stop
        } catch {
            # Si le nettoyage échoue, on ne bloque pas l'arrêt du script
        }
    }
    Write-ErrorMsg $msg
    exit $code
}

# ------------------------------------------------------------
# Vérifications préliminaires
# ------------------------------------------------------------
# Docker doit être installé ET le daemon doit être actif
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Cleanup-And-Exit 1 "Docker n'est pas installe ou pas dans le PATH."
}
docker info > $null 2>&1
if ($LASTEXITCODE -ne 0) {
    Cleanup-And-Exit 1 "Le daemon Docker ne semble pas etre disponible."
}

# Espace disque libre (exigence minimale 200 Go) -> abort si insuffisant
$drive = Get-PSDrive -PSProvider FileSystem |
         Where-Object { $BackupRoot -like "$($_.Root)*" }
if (-not $drive) {
    Cleanup-And-Exit 1 "Impossible de determiner le lecteur du chemin de sauvegarde."
}
if ($drive.Free -lt 200GB) {
    Cleanup-And-Exit 1 "Espace disque libre insuffisant (moins de 200 Go). La sauvegarde ne peut pas continuer."
}

# ------------------------------------------------------------
# Chemins de travail
# ------------------------------------------------------------
# Le script se trouve dans le dossier scripts, on remonte d'un niveau pour atteindre la racine du projet
$scriptRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Definition)

# Vérifier que le répertoire racine de sauvegarde existe ou le créer
if (-not (Test-Path $BackupRoot)) {
    try {
        New-Item -ItemType Directory -Path $BackupRoot -Force -ErrorAction Stop | Out-Null
    } catch {
        Cleanup-And-Exit 1 "Impossible de creer le repertoire racine de sauvegarde $BackupRoot."
    }
}

$timestamp   = Get-Date -Format "yyyyMMdd-HHmmss"
$backupDir   = Join-Path $BackupRoot "litellm-backup-$timestamp"

# Création du répertoire de sauvegarde (arrêt en cas d'échec)
try {
    New-Item -ItemType Directory -Path $backupDir -Force -ErrorAction Stop | Out-Null
} catch {
    Cleanup-And-Exit 1 "Impossible de creer le repertoire de sauvegarde $backupDir."
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
    Cleanup-And-Exit 1 "Sauvegarde incomplete : un ou plusieurs fichiers de configuration sont manquants ou non copies."
}

# ------------------------------------------------------------
# Les releves de mesure (.nexus) -- facultatifs, jamais bloquants
# ------------------------------------------------------------
# Depuis que la promotion est mecanisee, ces fichiers ne sont plus des
# traces : ce sont des ENTREES DE DECISION. Sans eux, regenerer la
# configuration ne redonne pas la meme composition de pools. Les remesurer
# coute des heures de machine -- une seule epreuve a demande 447 s.
#
# Ils sont volontairement hors du depot (.gitignore) parce qu'ils mesurent
# CETTE machine ; une sauvegarde locale est donc le seul endroit ou ils ont
# leur place.
#
# Leur absence n'est PAS une erreur, et c'est tout l'interet de les traiter
# a part : une machine neuve n'a encore rien mesure. Les glisser dans
# $configFiles aurait fait echouer sa toute premiere sauvegarde.
$mesureFiles = @(
    ".nexus/latences.json",
    ".nexus/epreuves.json"
)

$mesureDir = Join-Path $backupDir ".nexus"
foreach ($file in $mesureFiles) {
    $fullPath = Join-Path $scriptRoot $file
    if (Test-Path $fullPath) {
        if (-not (Test-Path $mesureDir)) {
            New-Item -ItemType Directory -Path $mesureDir -Force | Out-Null
        }
        try {
            Copy-Item $fullPath -Destination $mesureDir -Force -ErrorAction Stop
            Write-Info "  + $file"
        } catch {
            # Signale, ne bloque pas : la configuration, elle, est deja sauve.
            Write-Warn "  ! releve non copie : $file"
        }
    } else {
        Write-Info "  - $file (pas encore mesure)"
    }
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
        Cleanup-And-Exit 1 "Impossible de creer le repertoire $volumeDir."
    }

    $volumes = @(
        @{ Name = "local-llm-docker_pgdata";      File = "pgdata.tar.gz" },
        @{ Name = "local-llm-docker_redis_data";  File = "redis_data.tar.gz" }
    )

    foreach ($vol in $volumes) {
        # Tenter l'archivage directement ; docker renverra une erreur si le volume n'existe pas
        Write-Info "  Archivage du volume $($vol.Name)..."
        docker run --rm -v "$($vol.Name):/volume" -v "${volumeDir}:/backup" alpine `
            tar czf "/backup/$($vol.File)" -C /volume . 2>$null
        $exitCode = $LASTEXITCODE

        if ($exitCode -eq 0) {
            $archivePath = Join-Path $volumeDir $vol.File
            try {
                $size = (Get-Item $archivePath -ErrorAction Stop).Length
                if ($size -gt 0) {
                    Write-Info "    ✔ $($vol.File)"
                } else {
                    Write-Warn "    ⚠ Archive vide pour $($vol.Name)"
                    $volumeEchoue = $true
                }
            } catch {
                Write-Warn "    ⚠ Impossible de verifier l'archive $($vol.File)"
                $volumeEchoue = $true
            }
        } else {
            Write-Warn "    ❌ Echec de sauvegarde du volume $($vol.Name) (code sortie $exitCode)"
            $volumeEchoue = $true
        }
    }

    Write-Host "  Volume Ollama non archive : 541 Go retéléchargeables depuis model_list.txt." -ForegroundColor DarkGray
    Write-Host "  Sauvegarde de l'irremplaçable : python scripts\nexus_preserve.py --backup" -ForegroundColor DarkGray
}

# ------------------------------------------------------------
# Rapport final
# ------------------------------------------------------------
if ($IncludeVolumes -and $volumeEchoue) {
    Cleanup-And-Exit 1 "`n❌ Sauvegarde INCOMPLETE dans $backupDir : au moins un volume n'a pas ete archive."
}

Write-Info "`n✅ Sauvegarde terminee dans $backupDir"
exit 0
