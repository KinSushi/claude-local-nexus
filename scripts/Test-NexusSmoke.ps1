<#
.SYNOPSIS
    Smoke test de bout en bout de la plateforme Claude-Local-Nexus.

.DESCRIPTION
    Vérifie que la configuration n'est pas seulement correcte sur disque
    mais réellement active en runtime (§82) : santé du proxy, inventaire
    exposé, exécution locale, exécution cloud, embeddings, routeurs.

    Anthropic n'est PAS testé par défaut : chaque appel consomme des
    crédits API facturés au token. Utilisez -IncludeAnthropic pour l'inclure.

.PARAMETER IncludeAnthropic
    Ajoute un appel Claude réel (facturé sur le compte API, pas l'abonnement).
.PARAMETER IncludeRouters
    Teste également les routeurs adaptatifs.

.EXAMPLE
    .\scripts\Test-NexusSmoke.ps1
.EXAMPLE
    .\scripts\Test-NexusSmoke.ps1 -IncludeRouters
#>
[CmdletBinding()]
param(
    [switch]$IncludeAnthropic,
    [switch]$IncludeRouters
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$RepoRoot = Split-Path -Parent $PSScriptRoot
$BaseUrl  = "http://localhost:4000"

# --- Clé maître -------------------------------------------------------
if (-not $env:LITELLM_MASTER_KEY) {
    $envFile = Join-Path $RepoRoot ".env"
    if (Test-Path $envFile) {
        foreach ($line in Get-Content $envFile) {
            if ($line -match '^\s*LITELLM_MASTER_KEY=(.*)$') {
                # Supprimer les espaces et les éventuels guillemets autour de la valeur
                $env:LITELLM_MASTER_KEY = $matches[1].Trim().Trim('"').Trim("'")
            }
        }
    }
}
if (-not $env:LITELLM_MASTER_KEY) {
    Write-Error "LITELLM_MASTER_KEY introuvable (.env)."
    exit 1
}
$headers = @{ Authorization = "Bearer $env:LITELLM_MASTER_KEY" }

$script:Passed = 0
$script:Failed = 0

function Invoke-Check {
    param([string]$Name, [scriptblock]$Body)
    Write-Host -NoNewline ("  {0,-42}" -f $Name)
    try {
        $detail = & $Body
        Write-Host "OK" -ForegroundColor Green -NoNewline
        if ($detail) { Write-Host "  $detail" -ForegroundColor DarkGray } else { Write-Host "" }
        $script:Passed++
    } catch {
        Write-Host "ECHEC" -ForegroundColor Red -NoNewline
        Write-Host "  $($_.Exception.Message)" -ForegroundColor DarkGray
        $script:Failed++
    }
}

function Invoke-Chat {
    # 900 s par defaut : sur un hote CPU, le premier appel a un gros modele
    # local paie son chargement en memoire (plusieurs dizaines de Go). Un
    # delai serre ferait echouer un test qui n'a rien de defaillant.
    param([string]$Model, [int]$TimeoutSec = 900)

    # Le plafond de 16 jetons était suffisant tant que le pool ne contenait
    # que des modèles ordinaires. Les modèles à raisonnement (ex : kimi-k3,
    # deepseek-v4, qwen3.5) utilisent le champ `reasoning_content` et épuisent
    # rapidement ce budget, ce qui provoque des faux négatifs. Les jetons
    # supplémentaires sont gratuits, on les augmente donc à 512 pour
    # éviter que le test échoue à cause d'un budget trop court.
    $maxTokens = 512

    $body = @{
        model      = $Model
        messages   = @(@{ role = "user"; content = "Reponds exactement: OK" })
        max_tokens = $maxTokens
    } | ConvertTo-Json -Depth 6

    $bytes = [System.Text.Encoding]::UTF8.GetBytes($body)
    $response = Invoke-RestMethod -Uri "$BaseUrl/v1/chat/completions" -Method Post `
        -Headers $headers -ContentType "application/json; charset=utf-8" `
        -Body $bytes -TimeoutSec $TimeoutSec

    $msg = $response.choices[0].message
    $content = $msg.content

    # Acces a reasoning_content peut lever une exception sous Set-StrictMode
    # si le champ n'existe pas (modèles ordinaires). On teste son existence
    # avant d'y accéder pour éviter que le smoke échoue inutilement.
    $reasoning = if ($msg.PSObject.Properties.Name -contains 'reasoning_content') {
        $msg.reasoning_content
    } else {
        $null
    }

    # Un modèle qui a raisonné (reasoning_content non vide) mais n'a pas pu
    # écrire dans `content` a bien produit une réponse. Le smoke doit donc
    # accepter l'un ou l'autre comme preuve de fonctionnement.
    if (-not $content -and -not $reasoning) {
        throw "reponse vide (content et reasoning_content vides) - plafond max_tokens=$maxTokens"
    }

    $display = if ($content) { $content } else { $reasoning }
    return "<- $($display -replace '\s+', ' ')".Trim()
}

Write-Host "`n============================================================"
Write-Host " Smoke test Claude-Local-Nexus"
Write-Host "============================================================`n"

Invoke-Check "Sante du proxy" {
    $r = Invoke-WebRequest -Uri "$BaseUrl/health/liveliness" -Headers $headers -TimeoutSec 20 -UseBasicParsing
    if ($r.StatusCode -ne 200) { throw "HTTP $($r.StatusCode)" }
    return $null
}

$exposed = @()
Invoke-Check "Inventaire expose" {
    # 90 s : juste apres un redemarrage, l'inventaire de plusieurs dizaines
    # de modeles n'est pas servi instantanement.
    $r = Invoke-RestMethod -Uri "$BaseUrl/v1/models" -Headers $headers -TimeoutSec 90

    # 1️⃣ Vérifier que la réponse possède bien la propriété « data » et qu'elle n'est pas $null
    if (-not ($r.PSObject.Properties.Name -contains 'data') -or $null -eq $r.data) {
        throw "reponse du endpoint /v1/models ne contient pas de propriete 'data'"
    }

    # 2️⃣ Extraire les identifiants des modèles uniquement lorsqu'ils existent
    $script:exposed = @(
        foreach ($item in $r.data) {
            # $item peut être un objet PSCustomObject ou un hashtable
            if ($null -ne $item -and ($item.PSObject.Properties.Name -contains 'id')) {
                $item.id
            }
        }
    )

    # 3️⃣ S'assurer qu'on a réellement au moins un identifiant valide
    if ($script:exposed.Count -eq 0) {
        throw "aucun modele expose detecte"
    }

    return "$($script:exposed.Count) modeles"
}

Invoke-Check "Execution locale (phi3-mini-local)" { Invoke-Chat -Model "phi3-mini-local" }

# Un inventaire vide n'est pas une exception a laisser remonter : c'est un
# resultat de test, deja consigne plus haut.
$candidatsCloud = @($script:exposed |
    Where-Object { $_ -like "*-cloud" -and $_ -notlike "adaptive-router*" } |
    Sort-Object)
$firstCloud = if ($candidatsCloud.Count -gt 0) { $candidatsCloud[0] } else { $null }
if ($firstCloud) {
    Invoke-Check "Execution cloud ($firstCloud)" { Invoke-Chat -Model $firstCloud }
}

Invoke-Check "Embeddings (nomic-embed-text-local)" {
    $body = @{ model = "nomic-embed-text-local"; input = "test" } | ConvertTo-Json -Depth 5
    $bytes = [System.Text.Encoding]::UTF8.GetBytes($body)
    $r = Invoke-RestMethod -Uri "$BaseUrl/v1/embeddings" -Method Post -Headers $headers `
        -ContentType "application/json; charset=utf-8" -Body $bytes -TimeoutSec 120
    $dim = $r.data[0].embedding.Count
    if ($dim -lt 1) { throw "vecteur vide" }
    return "$dim dimensions"
}

if ($IncludeRouters) {
    foreach ($router in @("adaptive-router-local", "adaptive-router-cloud", "adaptive-router")) {
        Invoke-Check "Routeur $router" { Invoke-Chat -Model $router }
    }
}

if ($IncludeAnthropic) {
    Invoke-Check "Anthropic (claude-haiku-4-5, FACTURE)" { Invoke-Chat -Model "claude-haiku-4-5" }
}

Write-Host "`n------------------------------------------------------------"
Write-Host " Reussis : $script:Passed   Echecs : $script:Failed"
Write-Host "------------------------------------------------------------`n"

if ($script:Failed -gt 0) { exit 1 }
exit 0
