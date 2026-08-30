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

param(
    [switch]$WhatIf
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
# Configuration des chemins (utilisation de $PSScriptRoot)
# ------------------------------------------------------------
$scriptDir = $PSScriptRoot
$configPath = Join-Path $scriptDir "..\litellm_config.yaml"
$cloudModelsPath = Join-Path $scriptDir "cloud_models.txt"

# ------------------------------------------------------------
# Verifications preliminaires
# ------------------------------------------------------------
Set-StrictMode -Version Latest

if ((Test-Path $configPath) -and (Select-String -Path $configPath -Pattern "AUTOGEN:" -Quiet -CaseSensitive:$false)) {
    Write-Host ""
    Write-Host "  Script remplace et desactive." -ForegroundColor Yellow
    Write-Host "  litellm_config.yaml utilise des zones AUTOGEN que ce script detruirait." -ForegroundColor Yellow
    Write-Host ""
    Write-Host "  Utiliser :  .\scripts\Update-NexusModels.ps1 -Validate -Restart" -ForegroundColor Cyan
    Write-Host ""
    exit 1
}

# ------------------------------------------------------------
# Verification de la presence de la cle API
# ------------------------------------------------------------
if (-not $env:OLLAMA_CLOUD_API_KEY) {
    Write-Warning "Variable d'environnement OLLAMA_CLOUD_API_KEY non definie."
}

# ------------------------------------------------------------
# Verification du fichier cloud_models.txt
# ------------------------------------------------------------
if (-not (Test-Path $cloudModelsPath)) {
    Write-Error "Fichier cloud_models.txt introuvable."
    exit 1
}

# ------------------------------------------------------------
# Lecture des modeles cloud souhaites
# ------------------------------------------------------------
$desiredCloudModels = Get-Content $cloudModelsPath |
    Where-Object {
        $_ -notmatch '^\s*#' -and      # ligne ne commençant pas par # (commentaire)
        $_ -notmatch '^\s*$'           # ligne non vide
    } |
    ForEach-Object { $_.Trim() } |
    Where-Object { $_ -ne "" }

if (-not $desiredCloudModels) {
    Write-Warning "Aucun modele cloud defini dans cloud_models.txt."
    exit 0
}

# ------------------------------------------------------------
# Recuperation de la liste officielle des modeles via API
# ------------------------------------------------------------
Write-Host "Recuperation de la liste officielle des modeles..." -ForegroundColor Cyan
$apiUrl = "https://ollama.com/api/tags"

try {
    $data = Invoke-RestMethod -Uri $apiUrl -Method Get -MaximumRetryCount 2 -TimeoutSec 10 -ErrorAction Stop
} catch {
    Write-Error "Echec de la recuperation des modeles depuis $apiUrl"
    exit 1
}

# ------------------------------------------------------------
# Verification de l'existence de chaque modele (sans suffixe cloud)
# ------------------------------------------------------------
$availableModelNames = $data.models | Select-Object -ExpandProperty name
$validCloudModels = @()

foreach ($model in $desiredCloudModels) {
    $baseModel = $model -replace ':cloud$', ''
    if ($availableModelNames -contains $baseModel) {
        Write-Host "  ✔ $baseModel existe" -ForegroundColor Green
        $validCloudModels += $baseModel
    } else {
        Write-Warning "  ❌ $baseModel n'existe pas dans l'API, ignore."
    }
}

if (-not $validCloudModels) {
    Write-Warning "Aucun modele cloud valide trouve."
    exit 0
}

Write-Host "`nModeles cloud valides : $($validCloudModels.Count)"

# ------------------------------------------------------------
# Mise a jour de cloud_models.txt (avec suffixe :cloud)
# ------------------------------------------------------------
$cloudListContent = $validCloudModels | ForEach-Object { "$_:cloud" }

if ($WhatIf) {
    Write-Host "`n[Simulation] cloud_models.txt serait mis a jour avec :" -ForegroundColor Yellow
    Write-Host ($cloudListContent -join "`n")
} else {
    # sauvegarde avant ecriture
    Copy-Item -Path $cloudModelsPath -Destination "$cloudModelsPath.bak" -Force
    $cloudListContent | Set-Content -Path $cloudModelsPath -Encoding utf8NoBOM
    Write-Host "`ncloud_models.txt mis a jour." -ForegroundColor Cyan
}

# ------------------------------------------------------------
# Generation du bloc YAML
# ------------------------------------------------------------
$yamlBlock = @"
  # ==========================================================
  # OLLAMA CLOUD (auto-genere par update_cloud_models.ps1)
  # ==========================================================
"@

foreach ($baseModel in $validCloudModels) {
    $cloudName = "$baseModel`:cloud"
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
      description: "`"$baseModel (cloud)`""
"@
}

# ------------------------------------------------------------
# Mise a jour de litellm_config.yaml
# ------------------------------------------------------------
if ($WhatIf) {
    Write-Host "`n[Simulation] litellm_config.yaml (section OLLAMA CLOUD) serait remplace par :" -ForegroundColor Yellow
    Write-Host $yamlBlock
    exit 0
}

if (-not (Test-Path $configPath)) {
    Write-Error "Fichier $configPath introuvable."
    exit 1
}

# sauvegarde avant modification
Copy-Item -Path $configPath -Destination "$configPath.bak" -Force

$lines = Get-Content $configPath

$startMatch = $lines | Select-String -Pattern "OLLAMA CLOUD" -SimpleMatch -CaseSensitive:$false | Select-Object -First 1
$endMatch   = $lines | Select-String -Pattern "ROUTEURS ADAPTATIFS" -SimpleMatch -CaseSensitive:$false | Select-Object -First 1

if ($null -eq $startMatch) {
    Write-Error "Section OLLAMA CLOUD non trouvee dans $configPath. Ajoutez un commentaire '# OLLAMA CLOUD' avant la liste des modeles cloud."
    exit 1
}
$startIndex = $startMatch.LineNumber - 1   # convertir en indice zero-base

if ($null -eq $endMatch) {
    $endIndex = $lines.Count - 1
} else {
    $endIndex = $endMatch.LineNumber - 3   # on veut la ligne avant le commentaire suivant
    if ($endIndex -lt $startIndex) {
        $endIndex = $startIndex
    }
}

# reconstruction du fichier
$newLines = @()
if ($startIndex -gt 0) {
    $newLines += $lines[0..($startIndex-1)]
}
$newLines += $yamlBlock -split "`n"
if ($endIndex -lt $lines.Count - 1) {
    $newLines += $lines[($endIndex+1)..($lines.Count-1)]
}
$newContent = $newLines -join [Environment]::NewLine
$newContent | Set-Content -Path $configPath -Encoding utf8NoBOM

Write-Host "`n✅ Mise a jour terminee." -ForegroundColor Green
