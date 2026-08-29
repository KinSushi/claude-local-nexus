<#
.SYNOPSIS
    Choisit explicitement le mode d'execution de Claude Code.

.DESCRIPTION
    Point important, et raison de la reecriture de ce script :

        ANTHROPIC_BASE_URL seul ne remplace PAS l'abonnement claude.ai.
        C'est le JETON (ANTHROPIC_AUTH_TOKEN) qui le remplace.

    La documentation Anthropic est explicite : tant qu'un jeton de passerelle
    est actif, l'abonnement n'est pas utilise et le trafic est facture au
    token au proprietaire de la cle. L'ancienne version de ce script posait
    les deux variables en mode « automatique » et annoncait « Anthropic
    disponible » : elle consommait donc des credits API en croyant utiliser
    l'abonnement.

    Ce script ne bascule plus jamais tout seul. Chaque mode est demande
    explicitement, et son implication de facturation est affichee.

    Anthropic ne prend par ailleurs pas en charge le routage de Claude Code
    vers des modeles non-Claude a travers une passerelle. Pour combiner
    l'abonnement et les modeles locaux dans une meme session, la voie
    supportee est le serveur MCP nexus-local : Claude Code reste sur son
    abonnement et appelle les modeles locaux, cloud ou Claude comme outils.

.PARAMETER Mode
    Status        (defaut) affiche l'etat courant sans rien modifier.
    Subscription  retire toute variable de passerelle : retour a l'abonnement.
    Gateway       route Claude Code vers LiteLLM. FACTURE AU TOKEN.
    Local         route vers LiteLLM et propose un modele local.

.PARAMETER Model
    Modele a utiliser en mode Local ou Gateway. Sinon, choix automatique
    parmi les modeles locaux exposes, par ordre de preference.

.EXAMPLE
    .\Set-ClaudeModel.ps1
.EXAMPLE
    .\Set-ClaudeModel.ps1 -Mode Subscription
.EXAMPLE
    .\Set-ClaudeModel.ps1 -Mode Local -Model qwen3-coder-30b-local

.NOTES
    Les variables ne valent que pour la session PowerShell courante.
    Auteur : KinSushi - Enzo - Sovralys LLC
#>
[CmdletBinding()]
param(
    [ValidateSet("Status", "Subscription", "Gateway", "Local")]
    [string]$Mode = "Status",
    [string]$Model = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$BaseUrl = "http://localhost:4000"

function Write-Section { param($m) Write-Host "`n$m" -ForegroundColor Cyan }
function Write-Ok      { param($m) Write-Host "  $m" -ForegroundColor Green }
function Write-Warn2   { param($m) Write-Host "  $m" -ForegroundColor Yellow }
function Write-Info    { param($m) Write-Host "  $m" -ForegroundColor Gray }

function Get-MasterKey {
    if ($env:LITELLM_MASTER_KEY) { return $env:LITELLM_MASTER_KEY }
    $envFile = Join-Path $PSScriptRoot ".env"
    if (Test-Path $envFile) {
        try {
            foreach ($line in Get-Content $envFile -ErrorAction Stop) {
                if ($line -match '^\s*LITELLM_MASTER_KEY=(.*)$') { return $matches[1].Trim() }
            }
        } catch {
            # Erreur de lecture du fichier .env : on ne bloque pas le script, on retourne $null
            Write-Warn2 "Impossible de lire le fichier .env : $($_.Exception.Message)"
            return $null
        }
    }
    return $null
}

function Get-ExposedModels {
    param([string]$Key)
    try {
        $response = Invoke-RestMethod -Uri "$BaseUrl/v1/models" `
            -Headers @{ Authorization = "Bearer $Key" } -TimeoutSec 15
        if ($null -eq $response.data) {
            return @()
        }
        return @($response.data.id)
    } catch {
        # On conserve l'information de l'erreur sans masquer le type (auth, timeout, etc.)
        Write-Warn2 "Erreur lors de la recuperation des modeles : $($_.Exception.Message)"
        return @()
    }
}

# ------------------------------------------------------------
# Etat courant
# ------------------------------------------------------------
function Show-Status {
    Write-Section "Etat de Claude Code"

    $hasBase  = [bool]$env:ANTHROPIC_BASE_URL
    $hasToken = [bool]$env:ANTHROPIC_AUTH_TOKEN
    $hasKey   = [bool]$env:ANTHROPIC_API_KEY

    if ($hasToken) {
        Write-Warn2 "Mode PASSERELLE : l'abonnement claude.ai n'est PAS utilise."
        Write-Warn2 "Le trafic est facture au token sur la cle active."
        if ($hasBase) { Write-Info "ANTHROPIC_BASE_URL  = $env:ANTHROPIC_BASE_URL" }
        if ($hasToken) { Write-Info "ANTHROPIC_AUTH_TOKEN = defini (masque)" }
        if ($hasKey)   { Write-Info "ANTHROPIC_API_KEY    = defini (masque)" }
        Write-Info "Retour a l'abonnement : .\Set-ClaudeModel.ps1 -Mode Subscription"
    }
    elseif ($hasBase) {
        Write-Ok "Mode ABONNEMENT via passerelle."
        Write-Info "ANTHROPIC_BASE_URL = $env:ANTHROPIC_BASE_URL"
        Write-Info "Sans jeton de passerelle, la connexion claude.ai reste la"
        Write-Info "credential active : les limites de l'abonnement s'appliquent."
    }
    else {
        Write-Ok "Mode ABONNEMENT natif : Claude Code utilise la connexion claude.ai."
        Write-Info "Aucune variable de passerelle definie."
    }

    Write-Section "Passerelle LiteLLM"
    $key = Get-MasterKey
    if (-not $key) {
        Write-Warn2 "LITELLM_MASTER_KEY introuvable (.env) : passerelle non interrogeable."
        return
    }
    $models = Get-ExposedModels -Key $key
    if (-not $models) {
        Write-Warn2 "Proxy injoignable sur $BaseUrl. Demarrer : docker compose up -d"
        return
    }
    $local  = @($models | Where-Object { $_ -like "*-local" }).Count
    $cloud  = @($models | Where-Object { $_ -like "*-cloud" -and $_ -notlike "adaptive*" }).Count
    $claude = @($models | Where-Object { $_ -like "claude-*" }).Count
    Write-Ok "$($models.Count) modeles exposes : $local local, $cloud Ollama Cloud, $claude Claude."

    Write-Section "Combiner abonnement et modeles locaux"
    Write-Info "Le serveur MCP nexus-local est declare dans .mcp.json."
    Write-Info "Claude Code garde son abonnement et appelle les modeles de la"
    Write-Info "passerelle comme outils : nexus_ask, nexus_route, nexus_summarize,"
    Write-Info "nexus_search, nexus_index_build, nexus_models."
}

# ------------------------------------------------------------
# Modes
# ------------------------------------------------------------
switch ($Mode) {

    "Status" { Show-Status; break }

    "Subscription" {
        # Suppression des variables de passerelle avec avertissement
        if ($env:ANTHROPIC_BASE_URL) {
            Write-Warn2 "Suppression de ANTHROPIC_BASE_URL"
            Remove-Item Env:ANTHROPIC_BASE_URL -ErrorAction SilentlyContinue
        }
        if ($env:ANTHROPIC_AUTH_TOKEN) {
            Write-Warn2 "Suppression de ANTHROPIC_AUTH_TOKEN"
            Remove-Item Env:ANTHROPIC_AUTH_TOKEN -ErrorAction SilentlyContinue
        }
        if ($env:ANTHROPIC_API_KEY) {
            Write-Warn2 "Suppression de ANTHROPIC_API_KEY"
            Remove-Item Env:ANTHROPIC_API_KEY -ErrorAction SilentlyContinue
        }
        Write-Section "Mode ABONNEMENT"
        Write-Ok "Variables de passerelle retirees de cette session."
        Write-Ok "Claude Code utilise a nouveau la connexion claude.ai."
        Write-Info "Lancer : claude"
        break
    }

    { $_ -in @("Gateway", "Local") } {
        $key = Get-MasterKey
        if (-not $key) {
            throw "LITELLM_MASTER_KEY introuvable : impossible de configurer la passerelle."
        }
        $models = Get-ExposedModels -Key $key
        if (-not $models) {
            throw "Proxy injoignable sur $BaseUrl. Demarrer : docker compose up -d"
        }

        $selected = $Model
        if ($selected -and ($models -notcontains $selected)) {
            Write-Warn2 "Le modele '$selected' n'est pas expose. Selection automatique."
            $selected = ""
        }
        # Controle du mode Local : on accepte uniquement les modeles locaux
        if ($selected -and $Mode -eq "Local" -and
            ($selected -like "*-cloud" -or $selected -like "claude-*")) {
            throw "Le modele '$selected' n'est pas local. En mode Local, seuls les modeles locaux sont acceptes."
        }
        if (-not $selected) {
            if ($Mode -eq "Local") {
                $preference = @(
                    "releve-locale",
                    "glm-4.7-flash-local",
                    "qwen3-coder-30b-local",
                    "qwen2.5-coder-32b-local",
                    "qwen2.5-coder-14b-local",
                    "gemma4-12b-local",
                    "llama3.2-3b-local",
                    "phi3-mini-local"
                )
            } else {
                $preference = @("claude-sonnet-5", "claude-opus-5", "claude-haiku-4-5")
            }
            foreach ($candidate in $preference) {
                if ($models -contains $candidate) { $selected = $candidate; break }
            }
            if (-not $selected) {
                $fallback = if ($Mode -eq "Local") { "adaptive-router-local" } else { "adaptive-router" }
                if ($models -contains $fallback) {
                    $selected = $fallback
                } else {
                    throw "Aucun modele disponible pour le mode $Mode et le fallback $fallback n'est pas expose."
                }
            }
        }

        $env:ANTHROPIC_BASE_URL   = $BaseUrl
        $env:ANTHROPIC_AUTH_TOKEN = $key
        # Appliquer le modele retenu explicitement
        $env:ANTHROPIC_MODEL = $selected

        Write-Section "Mode PASSERELLE ($Mode)"
        Write-Warn2 "L'abonnement claude.ai n'est plus utilise dans cette session."
        if ($Mode -eq "Local") {
            Write-Ok "Modele retenu : $selected (local, cout 0, aucune donnee ne sort)."
            Write-Info "Contexte local limite : Claude Code est gourmand, les"
            Write-Info "fenetres locales sont a 8K/32K. Les sessions longues"
            Write-Info "risquent de saturer — c'est un mode de secours."
        } else {
            Write-Warn2 "Modele retenu : $selected — FACTURE AU TOKEN sur les credits API."
        }
        Write-Info "ANTHROPIC_BASE_URL   = $env:ANTHROPIC_BASE_URL"
        Write-Info "ANTHROPIC_AUTH_TOKEN = defini (masque)"
        Write-Host ""
        Write-Host "  Lancer : claude --model $selected"
        Write-Host "  Revenir a l'abonnement : .\Set-ClaudeModel.ps1 -Mode Subscription"
        break
    }
}

Write-Host ""
</#>
