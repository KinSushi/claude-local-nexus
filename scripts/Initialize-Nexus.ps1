<#
.SYNOPSIS
    Amorce la plateforme sur une machine neuve, ou vérifie une installation.

.DESCRIPTION
    Conçu pour que ce dépôt serve de base opérationnelle réutilisable :
    rien n'y est supposé de la machine, tout est vérifié puis mesuré.

    Déroulé, dans l'ordre :

        1. prérequis          docker, node, python, PyYAML
        2. secrets            .env créé depuis .env.example si absent
        3. profil matériel    CPU, GPU, RAM, disque — et ce qu'ils autorisent
        4. services           démarrage de la pile Docker
        5. moteur             detection Docker / hôte, et son budget réel
        6. configuration      génération puis validation bloquante
        7. vérification       smoke test runtime
        8. pont               rappel de l'approbation MCP

    Le script s'arrête au premier prérequis manquant plutôt que de laisser
    une installation à moitié faite : un échec franc coûte moins cher qu'un
    état ambigu.

.PARAMETER SkipPull
    N'installe aucun modèle. Utile pour vérifier une machine sans rien
    télécharger.

.PARAMETER CheckOnly
    Ne modifie rien : diagnostic seul.

.EXAMPLE
    .\scripts\Initialize-Nexus.ps1 -CheckOnly
.EXAMPLE
    .\scripts\Initialize-Nexus.ps1
#>
[CmdletBinding()]
param(
    [switch]$SkipPull,
    [switch]$CheckOnly
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

# ------------------------------------------------------------
# Vérification des droits administrateur (défaut de robustesse)
# ------------------------------------------------------------
if (-not ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Host "  [stop] Droits administrateur requis." -ForegroundColor Red
    exit 1
}

$RepoRoot = Split-Path -Parent $PSScriptRoot
$Scripts  = $PSScriptRoot

$script:Problemes = 0

function Write-Etape { param($m) Write-Host "`n=== $m ===" -ForegroundColor Cyan }
function Write-Ok    { param($m) Write-Host "  [ok]   $m" -ForegroundColor Green }
function Write-Manque{ param($m) Write-Host "  [!]    $m" -ForegroundColor Yellow; $script:Problemes++ }
function Write-Stop  { param($m) Write-Host "  [stop] $m" -ForegroundColor Red; $script:Problemes++ }

# ------------------------------------------------------------
# 1. Prerequis
# ------------------------------------------------------------
Write-Etape "Prerequis"

$requis = @(
    @{ Nom = "docker"; Test = { docker --version };  Aide = "Installer Docker Desktop" },
    @{ Nom = "node";   Test = { node --version };    Aide = "Installer Node.js 18 ou plus" },
    @{ Nom = "python"; Test = { python --version };  Aide = "Installer Python 3.10 ou plus" }
)
$bloquant = $false
foreach ($outil in $requis) {
    $cmd = Get-Command $outil.Nom -ErrorAction SilentlyContinue
    if ($cmd) {
        $version = (& $outil.Test 2>&1 | Select-Object -First 1)
        Write-Ok "$($outil.Nom) — $version"
    } else {
        Write-Stop "$($outil.Nom) introuvable. $($outil.Aide)"
        $bloquant = $true
    }
}

$yaml = python -c "import yaml; print(yaml.__version__)" 2>$null
if ($LASTEXITCODE -eq 0) {
    Write-Ok "PyYAML — $yaml"
} else {
    Write-Stop "PyYAML absent. Installer : python -m pip install pyyaml"
    $bloquant = $true
}

if ($bloquant) {
    Write-Host "`nPrerequis manquants : arret avant toute modification.`n" -ForegroundColor Red
    exit 1
}

# ------------------------------------------------------------
# 2. Secrets
# ------------------------------------------------------------
Write-Etape "Secrets"
$envFile = Join-Path $RepoRoot ".env"
$envModel = Join-Path $RepoRoot ".env.example"
if (Test-Path $envFile) {
    $manquantes = @()
    $contenu = Get-Content $envFile -Raw
    foreach ($cle in @("LITELLM_MASTER_KEY", "POSTGRES_PASSWORD")) {
        # La regex ignore les lignes commentées (commençant par #)
        if ($contenu -notmatch "(?m)^\s*$cle\s*=\s*\S") { $manquantes += $cle }
    }
    if ($manquantes) {
        Write-Manque ".env incomplet : $($manquantes -join ', ')"
    } else {
        Write-Ok ".env present et renseigne"
    }
    foreach ($cle in @("ANTHROPIC_API_KEY", "OLLAMA_CLOUD_API_KEY", "LANGFUSE_PUBLIC_KEY")) {
        if ($contenu -notmatch "(?m)^\s*$cle\s*=\s*\S") {
            Write-Host "         $cle non renseignee — le plan correspondant restera inactif" -ForegroundColor DarkGray
        }
    }
} elseif ($CheckOnly) {
    Write-Manque ".env absent"
} elseif (Test-Path $envModel) {
    Copy-Item $envModel $envFile
    Write-Manque ".env cree depuis .env.example — les valeurs sont a renseigner AVANT de demarrer"
    Write-Host "         Editer : $envFile" -ForegroundColor DarkGray
    exit 1
} else {
    Write-Stop ".env et .env.example absents"
    exit 1
}

# ------------------------------------------------------------
# 3. Profil materiel
# ------------------------------------------------------------
Write-Etape "Profil materiel"
$capabilityScript = Join-Path $Scripts "nexus_capability.py"
if (Test-Path $capabilityScript) {
    python "`"$capabilityScript`"" | Select-Object -First 16
} else {
    Write-Stop "Script nexus_capability.py introuvable."
}

# ------------------------------------------------------------
# 4. Services
# ------------------------------------------------------------
Write-Etape "Services"
if ($CheckOnly) {
    $composePs = docker compose ps 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Stop "docker compose ps a échoué : $composePs"
    } else {
        Write-Ok "docker compose ps exécuté"
        $composePs
    }
} else {
    Push-Location $RepoRoot
    try {
        $upResult = docker compose up -d 2>&1
        if ($LASTEXITCODE -ne 0) {
            Write-Stop "docker compose up a échoué : $upResult"
            exit 1
        }
        Start-Sleep -Seconds 10
        $psResult = docker compose ps --format "{{.Name}}`t{{.Status}}" 2>&1
        if ($LASTEXITCODE -ne 0) {
            Write-Stop "docker compose ps a échoué : $psResult"
        } else {
            Write-Ok "docker compose up terminé"
            $psResult
        }
    } finally { Pop-Location }
}

# ------------------------------------------------------------
# 5. Moteur d'inference
# ------------------------------------------------------------
Write-Etape "Moteur d'inference"
$switchEngineScript = Join-Path $Scripts "nexus_switch_engine.py"
if (Test-Path $switchEngineScript) {
    python "`"$switchEngineScript`"" --status | Select-Object -First 6
} else {
    Write-Stop "Script nexus_switch_engine.py introuvable."
}

# ------------------------------------------------------------
# 6. Modeles
# ------------------------------------------------------------
if (-not $SkipPull -and -not $CheckOnly) {
    # Vérification de l'espace disque (défaut de robustesse)
    $drive = Get-PSDrive -Name ($RepoRoot.Substring(0,1))
    if ($drive.Free -lt 5GB) {
        Write-Stop "Espace disque insuffisant (moins de 5 GB) pour télécharger les modèles."
        exit 1
    }

    Write-Etape "Inventaire local"
    Write-Host "  Le telechargement suit model_list.txt et respecte le verdict materiel :"
    Write-Host "  un modele que la machine ne peut pas executer n'est pas telecharge."
    $updateScript = Join-Path $Scripts "Update-NexusModels.ps1"
    if (Test-Path $updateScript) {
        & "`"$updateScript`"" -SyncLocal
        if ($LASTEXITCODE -ne 0) {
            Write-Manque "Update-NexusModels -SyncLocal a echoue (code $LASTEXITCODE)"
        }
    } else {
        Write-Stop "Script Update-NexusModels.ps1 introuvable."
    }
} else {
    Write-Etape "Inventaire local"
    Write-Host "  Ignore (-SkipPull ou -CheckOnly)." -ForegroundColor DarkGray
}

# ------------------------------------------------------------
# 7. Configuration et verification
# ------------------------------------------------------------
Write-Etape "Configuration"
if ($CheckOnly) {
    $testConfig = Join-Path $Scripts "Test-NexusConfig.ps1"
    if (Test-Path $testConfig) {
        & "`"$testConfig`""
        if ($LASTEXITCODE -ne 0) {
            Write-Manque "Test-NexusConfig a echoue (code $LASTEXITCODE)"
        }
    } else {
        Write-Stop "Script Test-NexusConfig.ps1 introuvable."
    }
} else {
    $updateScript = Join-Path $Scripts "Update-NexusModels.ps1"
    if (Test-Path $updateScript) {
        & "`"$updateScript`"" -Restart
        if ($LASTEXITCODE -ne 0) {
            Write-Manque "Update-NexusModels -Restart a echoue (code $LASTEXITCODE)"
        }
    } else {
        Write-Stop "Script Update-NexusModels.ps1 introuvable."
    }
}

# ------------------------------------------------------------
# 8. Pont MCP
# ------------------------------------------------------------
Write-Etape "Pont Claude Code"
$mcp = Join-Path $RepoRoot ".mcp.json"
if (Test-Path $mcp) {
    Write-Ok "nexus-local declare dans .mcp.json"
    Write-Host "         Un serveur de portee projet demande une approbation :" -ForegroundColor DarkGray
    Write-Host "         lancer 'claude' une fois et approuver nexus-local." -ForegroundColor DarkGray
} else {
    Write-Manque ".mcp.json absent : le pont ne sera pas propose a Claude Code"
}

# ------------------------------------------------------------
Write-Etape "Bilan"
if ($script:Problemes -eq 0) {
    Write-Host "  Installation coherente." -ForegroundColor Green
} else {
    Write-Host "  $($script:Problemes) point(s) a regler." -ForegroundColor Yellow
}
Write-Host ""
Write-Host "  Etat mesure     : .\rituels\RESUME.ps1"
Write-Host "  Sujets ouverts  : rituels\CHECKLIST_COCKPIT.MD"
Write-Host "  Suite de tests  : python scripts\nexus_test.py"
Write-Host ""
exit ([int]($script:Problemes -gt 0))
</#>
