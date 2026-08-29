<#
.SYNOPSIS
    Lance Claude Code et bascule l'orchestrateur en local si nécessaire.

.DESCRIPTION
    La plateforme sait déjà se replier vers le local quand un quota Ollama
    Cloud s'épuise : les chaînes de fallback y conduisent. Mais
    l'orchestrateur lui-même — le modèle qui décide — échappait à cette
    logique : si l'abonnement Claude expire ou atteint sa limite, la
    session s'arrête, quelle que soit la capacité locale disponible.

    Ce lanceur comble ce trou. Il démarre Claude Code sur l'abonnement, et
    si la session se termine sur une erreur de quota ou d'authentification,
    il la relance sur le modèle local de relève.

    Ce qui reste vrai et qu'il ne faut pas se cacher :

      - la bascule se fait ENTRE deux sessions, pas au milieu de l'une
        d'elles : le jeton d'une passerelle remplace la connexion
        claude.ai, et cela ne se décide pas en cours de route ;
      - le modèle de relève est un modèle local sur CPU. Il prend la
        suite, il ne prend pas la place.

    Le pont MCP, lui, reste identique dans les deux modes : les modèles
    locaux, cloud et Claude restent accessibles comme outils.

.PARAMETER Mode
    Auto          (défaut) abonnement, puis relève locale en cas d'échec.
    Subscription  abonnement uniquement, sans repli.
    Local         relève locale directement.

.PARAMETER MaxRetries
    Nombre de bascules autorisées. Défaut 1.

.EXAMPLE
    .\Start-Claude.ps1
.EXAMPLE
    .\Start-Claude.ps1 -Mode Local
#>
[CmdletBinding()]
param(
    [ValidateSet("Auto", "Subscription", "Local")]
    [string]$Mode = "Auto",
    [int]$MaxRetries = 1
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$RepoRoot = $PSScriptRoot
$BaseUrl  = "http://localhost:4000"

function Write-Info { param($m) Write-Host "  $m" -ForegroundColor Gray }
function Write-Ok   { param($m) Write-Host "  $m" -ForegroundColor Green }
function Write-Warn2{ param($m) Write-Host "  $m" -ForegroundColor Yellow }

function Get-MasterKey {
    if ($env:LITELLM_MASTER_KEY) { return $env:LITELLM_MASTER_KEY }
    $envFile = Join-Path $RepoRoot ".env"
    if (Test-Path $envFile) {
        foreach ($line in Get-Content $envFile) {
            if ($line -match '^\s*LITELLM_MASTER_KEY=(.*)$') { return $matches[1].Trim() }
        }
    }
    return $null
}

function Test-ReleveDisponible {
    param([string]$Key)
    try {
        $models = (Invoke-RestMethod -Uri "$BaseUrl/v1/models" `
            -Headers @{ Authorization = "Bearer $Key" } -TimeoutSec 20).data.id
        return @($models) -contains "releve-locale"
    } catch {
        return $false
    }
}

# Motifs qui signent une fin de quota ou d'abonnement, par opposition a
# une sortie normale ou a une erreur de code : on ne bascule que sur ce
# qu'une releve locale peut effectivement resoudre.
$MotifsDeReleve = @(
    "usage limit", "rate limit", "quota",
    "credit balance", "insufficient",
    "authentication_error", "subscription",
    "429", "402"
)

function Invoke-ClaudeCode {
    param([string[]]$Arguments)
    $journal = Join-Path $env:TEMP ("claude-session-{0}.log" -f (Get-Date -Format "HHmmss"))
    # La sortie est dupliquee : l'utilisateur la voit, le lanceur l'analyse.
    & claude @Arguments 2>&1 | Tee-Object -FilePath $journal
    $code = $LASTEXITCODE
    $trace = if (Test-Path $journal) { Get-Content $journal -Raw } else { "" }
    Remove-Item $journal -ErrorAction SilentlyContinue
    return [pscustomobject]@{ Code = $code; Trace = $trace }
}

function Test-MotifDeReleve {
    param([string]$Trace)
    foreach ($motif in $MotifsDeReleve) {
        if ($Trace -match [regex]::Escape($motif)) { return $motif }
    }
    return $null
}

# ------------------------------------------------------------
$key = Get-MasterKey
$releveDisponible = if ($key) { Test-ReleveDisponible -Key $key } else { $false }

Write-Host "`n=== Orchestrateur ===" -ForegroundColor Cyan
if ($releveDisponible) {
    Write-Ok "Releve locale disponible : basculement possible sans abonnement."
} else {
    Write-Warn2 "Releve locale indisponible : verifier la passerelle."
    Write-Info "  .\scripts\Test-NexusSmoke.ps1"
}

if ($Mode -eq "Local") {
    if (-not $releveDisponible) {
        Write-Error "Mode Local demande mais 'releve-locale' n'est pas expose."
        exit 1
    }
    Write-Warn2 "Mode local : l'abonnement n'est pas utilise, la facturation ne s'applique pas."
    $env:ANTHROPIC_BASE_URL   = $BaseUrl
    $env:ANTHROPIC_AUTH_TOKEN = $key
    Write-Host ""
    $resultat = Invoke-ClaudeCode -Arguments @("--model", "releve-locale")
    exit $resultat.Code
}

Write-Ok "Demarrage sur l'abonnement claude.ai."
Write-Host ""
$resultat = Invoke-ClaudeCode -Arguments @()

if ($resultat.Code -eq 0 -or $Mode -eq "Subscription") { exit $resultat.Code }

$motif = Test-MotifDeReleve -Trace $resultat.Trace
if (-not $motif) {
    # Sortie non nulle sans motif reconnu : ce n'est pas un probleme de
    # quota, une releve n'y changerait rien.
    exit $resultat.Code
}

Write-Host "`n=== Bascule ===" -ForegroundColor Cyan
Write-Warn2 "Session terminee sur un motif de quota ou d'abonnement : « $motif »."

if (-not $releveDisponible -or $MaxRetries -lt 1) {
    Write-Warn2 "Aucune releve disponible : arret."
    exit $resultat.Code
}

Write-Ok "Reprise sur 'releve-locale' — 64K de contexte, aucune donnee ne sort."
Write-Info "Le pont MCP reste identique : les modeles restent accessibles comme outils."
$env:ANTHROPIC_BASE_URL   = $BaseUrl
$env:ANTHROPIC_AUTH_TOKEN = $key
Write-Host ""
$reprise = Invoke-ClaudeCode -Arguments @("--model", "releve-locale")
exit $reprise.Code
