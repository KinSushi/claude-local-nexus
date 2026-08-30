# ============================================================
# restore.ps1 - Script de restauration/reconstruction
# ============================================================
# Ce script arrete les conteneurs existants, supprime les volumes,
# recree la stack et telecharge les modeles locaux.
# Utilisation : executer depuis le dossier contenant docker-compose.yml
# ============================================================

param(
    [switch]$Force   # Si indique, la confirmation interactive est sautee
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
# Configuration
# ------------------------------------------------------------
# Chemins absolus bases sur le repertoire du script
$scriptDir       = $PSScriptRoot
$envFile         = Join-Path $scriptDir '.env'
$envExampleFile = Join-Path $scriptDir '.env.example'
$modelListFile   = Join-Path $scriptDir 'model_list.txt'

# Nom du conteneur Ollama (modifiable dans docker-compose.yml)
$ollamaContainer = 'ollama-server'

# ------------------------------------------------------------
# Parametres de robustesse
# ------------------------------------------------------------
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

# Demarrage du transcript (log)
$logFile = Join-Path $scriptDir ("restore_{0:yyyyMMdd_HHmmss}.log" -f (Get-Date))
Start-Transcript -Path $logFile -Append

try {
    # ------------------------------------------------------------
    # Verification de la presence de Docker
    # ------------------------------------------------------------
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        Write-Error "Docker n'est pas installe ou pas dans le PATH."
        exit 1
    }

    # ------------------------------------------------------------
    # Determination de la commande docker compose (v2 ou v1)
    # ------------------------------------------------------------
    # Executable et arguments separes : `& 'docker compose' down -v` cherchait
    # une commande NOMMEE « docker compose », donc la restauration ne
    # supprimait ni ne remontait rien. Et `& docker compose version` ne peut
    # pas lever, docker existant : seul $LASTEXITCODE dit la verite.
    $composeExe  = 'docker'
    $composeArgs = @('compose')
    docker compose version > $null 2>&1
    if ($LASTEXITCODE -ne 0) {
        if (Get-Command 'docker-compose' -ErrorAction SilentlyContinue) {
            $composeExe = 'docker-compose'; $composeArgs = @()
        } else {
            Write-Error "Docker Compose (v2) ou docker-compose (v1) introuvable. Rien n'a ete detruit."
            exit 1
        }
    }

    # ------------------------------------------------------------
    # Verification des prerequis avant toute destruction
    # ------------------------------------------------------------
    if (-not (Test-Path $envFile)) {
        if (Test-Path $envExampleFile) {
            Copy-Item $envExampleFile $envFile
            Write-Host "Fichier .env cree depuis .env.example. Renseignez vos cles API, puis relancez ce script."
        } else {
            Write-Error "Ni .env ni .env.example ne sont presentes. Rien n'a ete detruit."
            exit 1
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
    if (-not $Force) {
        Write-Host "⚠️  Attention : cette operation va supprimer les volumes Docker (donnees PostgreSQL, modeles Ollama, cache Redis)."
        Write-Host "Tapez 'OUI' pour confirmer, ou toute autre chose pour annuler."
        $confirmation = Read-Host
        if ($confirmation.Trim().ToUpper() -ne 'OUI') {
            Write-Host "Operation annulee par l'utilisateur."
            exit 0
        }
    }

    # ------------------------------------------------------------
    # Arreter et supprimer les conteneurs et volumes
    # ------------------------------------------------------------
    & $composeExe @composeArgs down -v
    if ($LASTEXITCODE -ne 0) { throw "docker compose down returned non-zero exit code." }

    # ------------------------------------------------------------
    # Demarrer la stack
    # ------------------------------------------------------------
    & $composeExe @composeArgs up -d
    if ($LASTEXITCODE -ne 0) { throw "docker compose up returned non-zero exit code." }

    # ------------------------------------------------------------
    # Attendre que le conteneur Ollama soit ready
    # ------------------------------------------------------------
    Write-Host "Attente du demarrage d'Ollama..."
    $maxAttempts = 30
    $attempt = 0
    $ollamaStatus = $null

    do {
        $attempt++
        Start-Sleep -Seconds 2

        $inspectResult = docker inspect --format='{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' $ollamaContainer 2>$null
        if ($inspectResult) {
            $ollamaStatus = $inspectResult.Trim()
        } else {
            $ollamaStatus = $null
        }
    } while ($ollamaStatus -ne 'healthy' -and $ollamaStatus -ne 'running' -and $attempt -lt $maxAttempts)

    if ($ollamaStatus -ne 'healthy' -and $ollamaStatus -ne 'running') {
        Write-Error "Ollama n'est pas en etat 'healthy' ou 'running' apres $($maxAttempts * 2) secondes. Verifiez les logs avec 'docker logs $ollamaContainer'."
        exit 1
    }

    # ------------------------------------------------------------
    # Telecharger les modeles locaux
    # ------------------------------------------------------------
    $models = Get-Content -Path $modelListFile -Encoding UTF8 |
              Where-Object { $_ -notmatch '^NAME$' -and $_ -notmatch ':cloud$' -and $_ -notmatch '^\s*$' }

    $successCount = 0
    $failCount    = 0

    foreach ($model in $models) {
        $model = $model.Trim()
        if ($model -eq '') { continue }

        Write-Host "Telechargement de $model..."
        & docker exec $ollamaContainer ollama pull "$model"
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
    & $composeExe @composeArgs ps

    Write-Host "✅ Restauration terminee."
}
finally {
    # Nettoyage du transcript, garantit la fermeture même en cas d'erreur
    Stop-Transcript
}
