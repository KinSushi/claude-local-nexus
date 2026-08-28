# ============================================================
# update_cloud_models.ps1
# Met à jour les modèles cloud listés dans cloud_models.txt
# en vérifiant leur existence sur l'API officielle d'Ollama.
# Régénère la section OLLAMA CLOUD de litellm_config.yaml
#
# Utilisation :
#   .\update_cloud_models.ps1                # Mise à jour réelle
#   .\update_cloud_models.ps1 -WhatIf        # Simulation sans écrire
# ============================================================

param(
    [switch]$WhatIf
)

# --- Vérification de curl.exe ---
if (-not (Get-Command curl.exe -ErrorAction SilentlyContinue)) {
    Write-Error "curl.exe n'est pas trouvé. Installez curl ou utilisez Invoke-RestMethod."
    exit 1
}

# --- Vérification du fichier cloud_models.txt ---
if (-not (Test-Path cloud_models.txt)) {
    Write-Error "Fichier cloud_models.txt introuvable."
    exit 1
}

# --- Lecture des modèles cloud souhaités ---
# On ignore les commentaires (#) et les lignes vides, on accepte tout le reste.
$desiredCloudModels = Get-Content cloud_models.txt |
    Where-Object {
        $_ -notmatch '^\s*#' -and      # ligne ne commençant pas par # (commentaire)
        $_ -notmatch '^\s*$'           # ligne non vide
    } |
    ForEach-Object { $_.Trim() } |
    Where-Object { $_ -ne "" }

if (-not $desiredCloudModels) {
    Write-Warning "Aucun modèle cloud défini dans cloud_models.txt."
    exit 0
}

# --- Récupération de la liste officielle des modèles via API ---
Write-Host "Récupération de la liste officielle des modèles..." -ForegroundColor Cyan
$apiUrl = "https://ollama.com/api/tags"
$response = & curl.exe -s $apiUrl
if ($LASTEXITCODE -ne 0) {
    Write-Error "Échec de la récupération des modèles depuis $apiUrl"
    exit 1
}

try {
    $data = $response | ConvertFrom-Json
} catch {
    Write-Error "Impossible de parser la réponse JSON."
    exit 1
}

# --- Vérification de l'existence de chaque modèle (sans suffixe cloud) ---
$availableModelNames = $data.models | Select-Object -ExpandProperty name
$validCloudModels = @()

foreach ($model in $desiredCloudModels) {
    # Retirer le suffixe :cloud si présent
    $baseModel = $model -replace ':cloud$', ''
    if ($availableModelNames -contains $baseModel) {
        Write-Host "  ✔ $baseModel existe" -ForegroundColor Green
        $validCloudModels += $baseModel
    } else {
        Write-Warning "  ❌ $baseModel n'existe pas dans l'API, ignoré."
    }
}

if (-not $validCloudModels) {
    Write-Warning "Aucun modèle cloud valide trouvé."
    exit 0
}

Write-Host "`nModèles cloud valides : $($validCloudModels.Count)"

# --- Mise à jour de cloud_models.txt (avec suffixe :cloud pour clarté) ---
$cloudListContent = $validCloudModels | ForEach-Object { "$_:cloud" }
if ($WhatIf) {
    Write-Host "`n[Simulation] cloud_models.txt serait mis à jour avec :" -ForegroundColor Yellow
    Write-Host ($cloudListContent -join "`n")
} else {
    $cloudListContent | Set-Content -Path cloud_models.txt -Encoding UTF8
    Write-Host "`ncloud_models.txt mis à jour." -ForegroundColor Cyan
}

# --- Génération de la section YAML ---
$yamlBlock = @"
  # ==========================================================
  # OLLAMA CLOUD (auto-généré par update_cloud_models.ps1)
  # ==========================================================
"@

foreach ($baseModel in $validCloudModels) {
    $cloudName = "$baseModel`:cloud"
    # Nom LiteLLM interne : on remplace les caractères problématiques par des tirets
    $modelName = ($baseModel -replace '[:.]', '-') + "-cloud"
    $yamlBlock += @"

  - model_name: $modelName
    litellm_params:
      model: ollama/$cloudName
      api_base: https://ollama.com
      api_key: os.environ/OLLAMA_CLOUD_API_KEY
      num_ctx: 131072
      num_predict: 4096
    model_info:
      max_input_tokens: 131072
      description: "$baseModel (cloud)"
"@
}

# --- Mise à jour de litellm_config.yaml ---
$configPath = "litellm_config.yaml"
if ($WhatIf) {
    Write-Host "`n[Simulation] litellm_config.yaml (section OLLAMA CLOUD) serait remplacée par :" -ForegroundColor Yellow
    Write-Host $yamlBlock
    exit 0
}

if (-not (Test-Path $configPath)) {
    Write-Error "Fichier $configPath introuvable."
    exit 1
}

$lines = Get-Content $configPath
$startIndex = ($lines | Select-String -Pattern "OLLAMA CLOUD" | Select-Object -First 1).LineNumber
if (-not $startIndex) {
    Write-Error "Section OLLAMA CLOUD non trouvée dans $configPath. Ajoutez un commentaire '# OLLAMA CLOUD' avant la liste des modèles cloud."
    exit 1
}
$startIndex--

$endIndex = ($lines | Select-String -Pattern "ROUTEURS ADAPTATIFS" | Select-Object -First 1).LineNumber - 2
if (-not $endIndex) {
    $endIndex = $lines.Count
}

$newLines = $lines[0..($startIndex-1)] + $yamlBlock + $lines[$endIndex..($lines.Count-1)]
$newContent = $newLines -join "`n"
$newContent | Set-Content -Path $configPath -Encoding UTF8

Write-Host "`n✅ Mise à jour terminée." -ForegroundColor Green