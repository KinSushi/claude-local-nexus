# ============================================================
# Set-ClaudeModel.ps1
# Configure l'environnement pour que Claude Code utilise le proxy LiteLLM.
# Sélectionne automatiquement le meilleur modèle disponible :
#   - Anthropic (claude-sonnet-5) si la clé est valide et le quota disponible,
#   - sinon un modèle local (qwen3-coder-30b, gemma4-31b, etc.),
#   - ou le cloud gratuit (gpt-oss-20b-cloud).
#
# Ce script définit les variables d'environnement requises par Claude Code :
#   ANTHROPIC_BASE_URL = http://localhost:4000
#   ANTHROPIC_AUTH_TOKEN = LITELLM_MASTER_KEY
#
# Utilisation :
#   .\Set-ClaudeModel.ps1                   # Détection automatique
#   .\Set-ClaudeModel.ps1 -ForceLocal        # Force un modèle local robuste
#   .\Set-ClaudeModel.ps1 -ForceCloud        # Force le cloud gratuit
#   .\Set-ClaudeModel.ps1 -Model "nom_modele"# Utilise un modèle précis
# ============================================================

# ============================================================
# Set-ClaudeModel.ps1
# Configure l'environnement pour Claude Code via le proxy LiteLLM.
# Sélectionne automatiquement le meilleur modèle selon disponibilité.
# ============================================================

param(
    [string]$Model,
    [switch]$ForceLocal,
    [switch]$ForceCloud
)

# ---------- Chargement des variables depuis .env ----------
if (-not $env:LITELLM_MASTER_KEY) {
    if (Test-Path .env) {
        Get-Content .env | ForEach-Object {
            if ($_ -match '^\s*([^#=]+)=(.*)$') {
                $name = $matches[1].Trim()
                $value = $matches[2].Trim()
                if (-not (Get-Item "env:$name" -ErrorAction SilentlyContinue)) {
                    Set-Item -Path "env:$name" -Value $value
                }
            }
        }
    }
}

if (-not $env:LITELLM_MASTER_KEY) {
    Write-Error "LITELLM_MASTER_KEY est introuvable. Définissez-la ou assurez-vous que .env la contient."
    exit 1
}

# Supprimer ANTHROPIC_API_KEY pour éviter le conflit avec le token du proxy
Remove-Item Env:ANTHROPIC_API_KEY -ErrorAction SilentlyContinue

$headers = @{ "Authorization" = "Bearer $env:LITELLM_MASTER_KEY" }

# ---------- Vérifier que le proxy est en ligne ----------
Write-Host "Vérification du proxy LiteLLM..." -ForegroundColor Cyan
try {
    $healthResponse = Invoke-WebRequest -Uri "http://localhost:4000/health" -Headers $headers -TimeoutSec 10 -UseBasicParsing
    if ($healthResponse.StatusCode -ne 200) { throw "HTTP $($healthResponse.StatusCode)" }
} catch {
    Write-Error "Le proxy LiteLLM ne répond pas correctement : $($_.Exception.Message)"
    exit 1
}

# ---------- Récupérer la liste des modèles ----------
Write-Host "Récupération de la liste des modèles..." -ForegroundColor Cyan
try {
    $modelsResponse = Invoke-WebRequest -Uri "http://localhost:4000/v1/models" -Headers $headers -TimeoutSec 10 -UseBasicParsing
    $allModels = ($modelsResponse.Content | ConvertFrom-Json).data.id
} catch {
    Write-Error "Impossible de récupérer la liste des modèles : $($_.Exception.Message)"
    exit 1
}

Write-Host "Modèles disponibles sur le proxy :" -ForegroundColor Cyan
$allModels | ForEach-Object { Write-Host "   - $_" }
Write-Host ""

# ---------- Déterminer le modèle final ----------
$selectedModel = $null

if ($ForceLocal) {
    # Choisir un modèle local avec la plus grande fenêtre de contexte possible
    $localCandidates = @(
        "qwen3-coder-30b-local",
        "qwen2.5-coder-32b-local",
        "gemma4-31b-local",
        "qwen2.5-32b-local",
        "llama3.3-70b-local",
        "gemma4-12b-local",
        "phi3-mini-local"
    )
    foreach ($m in $localCandidates) {
        if ($allModels -contains $m) { $selectedModel = $m; break }
    }
    if (-not $selectedModel) {
        Write-Warning "Aucun modèle local performant trouvé. Utilisation du routeur adaptatif."
        $selectedModel = "adaptive-router"
    }
}
elseif ($ForceCloud) {
    if ($allModels -contains "gpt-oss-20b-cloud") {
        $selectedModel = "gpt-oss-20b-cloud"
    } else {
        Write-Warning "Modèle cloud gratuit introuvable. Utilisation du routeur adaptatif."
        $selectedModel = "adaptive-router"
    }
}
elseif ($Model) {
    if ($allModels -contains $Model) {
        $selectedModel = $Model
    } else {
        Write-Warning "Le modèle '$Model' n'existe pas. Utilisation du routeur adaptatif."
        $selectedModel = "adaptive-router"
    }
}
else {
    # Détection automatique : tester Anthropic, sinon cloud gratuit, sinon local
    $anthropicAvailable = $false
    if ($env:ANTHROPIC_API_KEY) {
        $testBody = @{
            model = "claude-sonnet-5"
            messages = @(@{ role = "user"; content = "ping" })
            max_tokens = 5
        } | ConvertTo-Json -Depth 5
        $testBytes = [System.Text.Encoding]::UTF8.GetBytes($testBody)
        try {
            $testResponse = Invoke-WebRequest -Uri "http://localhost:4000/v1/chat/completions" `
                -Method Post -Headers $headers -ContentType "application/json; charset=utf-8" `
                -Body $testBytes -TimeoutSec 15 -UseBasicParsing
            $anthropicAvailable = $true
        } catch {
            $anthropicAvailable = $false
        }
    }

    if ($anthropicAvailable) {
        $selectedModel = "claude-sonnet-5"
        Write-Host "✔ Anthropic est disponible. Utilisation de $selectedModel" -ForegroundColor Green
    }
    elseif ($allModels -contains "gpt-oss-20b-cloud") {
        $selectedModel = "gpt-oss-20b-cloud"
        Write-Warning "Anthropic indisponible. Bascule sur le cloud gratuit $selectedModel."
    }
    else {
        Write-Warning "Anthropic et cloud gratuit indisponibles. Bascule sur un modèle local."
        $localCandidates = @(
            "qwen3-coder-30b-local",
            "qwen2.5-coder-32b-local",
            "gemma4-31b-local",
            "qwen2.5-32b-local",
            "llama3.3-70b-local",
            "gemma4-12b-local",
            "phi3-mini-local"
        )
        foreach ($m in $localCandidates) {
            if ($allModels -contains $m) { $selectedModel = $m; break }
        }
        if (-not $selectedModel) { $selectedModel = "adaptive-router" }
    }
}

# ---------- Configurer l'environnement pour Claude Code ----------
$env:ANTHROPIC_BASE_URL = "http://localhost:4000"
$env:ANTHROPIC_AUTH_TOKEN = $env:LITELLM_MASTER_KEY

Write-Host ""
Write-Host "✅ Claude Code est configuré pour utiliser le modèle : $selectedModel" -ForegroundColor Green
Write-Host "   Base URL : $env:ANTHROPIC_BASE_URL"
Write-Host "   Auth Token : défini (masqué)"
Write-Host ""
Write-Host "Lancez 'claude' ou 'claude --model $selectedModel'."