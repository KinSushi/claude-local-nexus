# ============================================================
# SCRIPT REMPLACE - NE PLUS UTILISER
# ============================================================
# litellm_config.yaml est desormais regenere par zones delimitees
# (marqueurs AUTOGEN). Ce script reecrit un bloc entier repere par
# de simples commentaires : il detruit les marqueurs et duplique la
# configuration. Il souffrait par ailleurs d'un defaut d'idempotence
# qui reinjectait une ligne de commentaire a chaque execution.
#
# Utiliser a la place :
#     .\scripts\Update-NexusModels.ps1 -Validate -Restart
# ============================================================
exit 1

$__config = Join-Path (Split-Path -Parent $PSScriptRoot) "litellm_config.yaml"
if ((Test-Path $__config) -and (Select-String -Path $__config -Pattern "AUTOGEN:" -Quiet)) {
    Write-Host ""
    Write-Host "  Script remplace et desactive." -ForegroundColor Yellow
    Write-Host "  litellm_config.yaml utilise des zones AUTOGEN que ce script detruirait." -ForegroundColor Yellow
    Write-Host ""
    Write-Host "  Utiliser :  .\scripts\Update-NexusModels.ps1 -Validate -Restart" -ForegroundColor Cyan
    Write-Host ""
    exit 1
}

# ============================================================
# update_local_models.ps1
# Télécharge les modèles locaux listés dans model_list.txt
# dans le conteneur Ollama.
#
# Utilisation :
#   .\update_local_models.ps1           # télécharge uniquement les absents
#   .\update_local_models.ps1 -Force    # force le retéléchargement de tous
# ============================================================

param(
    [switch]$Force
)

# --- Vérification de Docker ---
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Error "Docker n'est pas installé ou pas dans le PATH."
    exit 1
}

# --- Vérification du conteneur Ollama ---
$ollamaStatus = docker inspect --format='{{.State.Health.Status}}' ollama-server 2>$null
if ($ollamaStatus -ne "healthy") {
    Write-Warning "Le conteneur Ollama n'est pas prêt. Démarrez-le avec 'docker compose up -d ollama' puis réessayez."
    exit 1
}

# --- Vérification du fichier model_list.txt ---
$__modelList = Join-Path $PSScriptRoot "model_list.txt"
if (-not (Test-Path $__modelList)) {
    Write-Error "Fichier model_list.txt introuvable."
    exit 1
}

# --- Lecture et filtrage ---
$models = Get-Content $__modelList |
    Where-Object {
        $_ -notmatch '^\s*#' -and      # ignorer les commentaires
        $_ -notmatch '^\s*$' -and      # ignorer les lignes vides
        $_ -notmatch ':cloud$'         # ignorer les modèles cloud
    } |
    ForEach-Object { $_.Trim() } |
    Where-Object { $_ -ne "" }

if (-not $models) {
    Write-Warning "Aucun modèle local valide trouvé dans model_list.txt."
    exit 0
}

Write-Host "============================================================"
Write-Host " Synchronisation des modèles locaux ($($models.Count) modèle(s))"
Write-Host "============================================================"

# --- Récupération de la liste des modèles déjà présents ---
$existingModelsRaw = docker exec ollama-server ollama list
$existingModels = $existingModelsRaw |
    Select-Object -Skip 1 |
    ForEach-Object { ($_ -split '\s+')[0] }

$successCount = 0
$failCount = 0

foreach ($model in $models) {
    Write-Host ""
    Write-Host "── Modèle : $model ──"

    $alreadyExists = $existingModels -contains $model

    if ($alreadyExists -and -not $Force) {
        Write-Host "   ✅ Déjà présent, ignoré (utilisez -Force pour retélécharger)."
        continue
    }

    if ($alreadyExists -and $Force) {
        Write-Host "   ⚠️  Présent mais -Force activé : retéléchargement..."
        docker exec ollama-server ollama rm $model | Out-Null
    }

    Write-Host "   📥 Téléchargement de $model..."
    docker exec ollama-server ollama pull $model

    if ($LASTEXITCODE -eq 0) {
        Write-Host "   ✔ Téléchargement réussi."
        $successCount++
    } else {
        Write-Warning "   ❌ Échec du téléchargement de $model. Vérifiez le nom et la connexion."
        $failCount++
    }
}

Write-Host ""
Write-Host "============================================================"
Write-Host " Synchronisation terminée."
Write-Host "   Réussis : $successCount"
Write-Host "   Échecs  : $failCount"
Write-Host "============================================================"
