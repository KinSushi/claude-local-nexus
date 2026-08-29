<#
.SYNOPSIS
    Orchestrateur de mise à jour Claude-Local-Nexus.

.DESCRIPTION
    Enchaîne le cycle complet, dans l'ordre imposé par le contrat
    d'exploitation (§44) : INSPECTER -> GENERER -> VALIDER -> APPLIQUER -> TESTER.

        1. synchronisation de l'inventaire local (Ollama)
        2. découverte du catalogue Ollama Cloud
        3. validation réelle des droits du compte (par défaut)
        4. régénération des zones AUTOGEN de litellm_config.yaml
        5. validation d'intégrité de la configuration
        6. redémarrage de LiteLLM et smoke test (option -Restart)

    LiteLLM n'est JAMAIS redémarré si la validation d'intégrité échoue :
    une configuration douteuse ne remplace pas une configuration qui tourne.

    Le pool cloud n'est pas figé. La validation étant rejouée à chaque
    exécution, souscrire un palier Ollama Cloud supérieur suffit : les
    modèles débloqués rejoignent le routeur à la mise à jour suivante,
    sans aucune retouche manuelle.

.PARAMETER DryRun
    Simulation complète : affiche ce qui serait généré, n'écrit rien.
.PARAMETER Validate
    Conservé pour compatibilité. La validation des droits est désormais
    le comportement par défaut ; omettre ce commutateur ne la désactive pas.
.PARAMETER NoValidate
    Désactive la vérification des droits Ollama Cloud. Déconseillé : le pool
    peut alors contenir des modèles que le compte ne peut pas exécuter.
.PARAMETER SyncLocal
    Télécharge dans Ollama les modèles de model_list.txt encore absents.
.PARAMETER Restart
    Redémarre LiteLLM puis exécute le smoke test.
.PARAMETER LogPath
    Fichier de journal. Par défaut logs/update-<horodatage>.log.

.EXAMPLE
    .\scripts\Update-NexusModels.ps1 -DryRun
.EXAMPLE
    .\scripts\Update-NexusModels.ps1 -Validate -Restart
.EXAMPLE
    # Cycle complet, tel que l'exécute la tâche planifiée
    .\scripts\Update-NexusModels.ps1 -SyncLocal -Validate -Restart
#>
[CmdletBinding()]
param(
    [switch]$DryRun,
    [switch]$Validate,
    [switch]$NoValidate,
    [switch]$SyncLocal,
    [switch]$Restart,
    [string]$LogPath
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$RepoRoot  = Split-Path -Parent $PSScriptRoot
$LogDir    = Join-Path $RepoRoot "logs"
$BackupDir = Join-Path $RepoRoot "backups"
$Config    = Join-Path $RepoRoot "litellm_config.yaml"

if (-not $LogPath) {
    if (-not (Test-Path $LogDir)) { New-Item -ItemType Directory -Path $LogDir | Out-Null }
    $LogPath = Join-Path $LogDir ("update-{0}.log" -f (Get-Date -Format "yyyyMMdd-HHmmss"))
}

function Write-Log {
    param([string]$Message, [string]$Level = "INFO")
    $line = "[{0}] [{1}] {2}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $Level, $Message
    Add-Content -Path $LogPath -Value $line -Encoding UTF8
    $color = switch ($Level) {
        "ERROR" { "Red" }
        "WARN"  { "Yellow" }
        "OK"    { "Green" }
        default { "Cyan" }
    }
    Write-Host $line -ForegroundColor $color
}

function Resolve-Python {
    foreach ($candidate in @("python", "python3")) {
        $cmd = Get-Command $candidate -ErrorAction SilentlyContinue
        if ($cmd) { return $cmd.Source }
    }
    throw "Python est introuvable : la mise à jour ne peut pas s'exécuter."
}

$python = Resolve-Python
Write-Log "Demarrage de la mise a jour (journal : $LogPath)"

# ------------------------------------------------------------
# 1. Inventaire local
# ------------------------------------------------------------
if ($SyncLocal) {
    Write-Log "Synchronisation de l'inventaire local Ollama"
    $health = docker inspect --format "{{.State.Health.Status}}" ollama-server 2>$null
    if ($health -ne "healthy") {
        Write-Log "Conteneur ollama-server indisponible ($health) : synchronisation ignoree" "WARN"
    } else {
        $present = @(docker exec ollama-server ollama list |
                     Select-Object -Skip 1 |
                     ForEach-Object { ($_ -split '\s+')[0] })
        $wanted = @(Get-Content (Join-Path $RepoRoot "model_list.txt") |
                    Where-Object { $_ -notmatch '^\s*#' -and $_.Trim() -ne "" } |
                    ForEach-Object { $_.Trim() })
        $missing = @($wanted | Where-Object { $present -notcontains $_ })
        if (-not $missing) {
            Write-Log "Inventaire local deja complet ($($present.Count) modeles)" "OK"
        } elseif ($DryRun) {
            Write-Log "[Simulation] a telecharger : $($missing -join ', ')" "WARN"
        } else {
            foreach ($model in $missing) {
                Write-Log "Telechargement de $model"
                docker exec ollama-server ollama pull $model
                if ($LASTEXITCODE -ne 0) { Write-Log "Echec du telechargement de $model" "WARN" }
            }
        }
    }
}

# ------------------------------------------------------------
# 2/3/4. Génération (découverte + validation + réécriture AUTOGEN)
# ------------------------------------------------------------
if (-not $DryRun) {
    if (-not (Test-Path $BackupDir)) { New-Item -ItemType Directory -Path $BackupDir | Out-Null }
    $backup = Join-Path $BackupDir ("litellm_config.yaml.{0}.bak" -f (Get-Date -Format "yyyyMMdd-HHmmss"))
    Copy-Item $Config $backup
    Write-Log "Sauvegarde : $backup" "OK"
}

$genArgs = @((Join-Path $PSScriptRoot "nexus_generate.py"))
if ($DryRun)  { $genArgs += "--dry-run" }
# La validation des droits est le comportement par defaut du generateur.
# On ne la desactive que sur demande explicite : generer sans elle
# remplirait le pool de modeles que le compte ne peut pas executer.
if ($NoValidate) { $genArgs += "--no-validate" }

Write-Log "Generation de la configuration"
& $python @genArgs 2>&1 | Tee-Object -FilePath $LogPath -Append
if ($LASTEXITCODE -ne 0) {
    Write-Log "Generation en echec : configuration inchangee" "ERROR"
    exit 1
}

if ($DryRun) {
    Write-Log "Simulation terminee : aucun fichier modifie" "OK"
    exit 0
}

# ------------------------------------------------------------
# 5. Validation d'intégrité — garde-fou avant tout redémarrage
# ------------------------------------------------------------
Write-Log "Validation d'integrite"
& $python (Join-Path $PSScriptRoot "nexus_validate.py") 2>&1 | Tee-Object -FilePath $LogPath -Append
if ($LASTEXITCODE -ne 0) {
    Write-Log "Configuration invalide : LiteLLM n'a PAS ete redemarre" "ERROR"
    Write-Log "Restauration possible depuis $backup" "WARN"
    exit 1
}
Write-Log "Configuration valide" "OK"

# ------------------------------------------------------------
# 6. Application et vérification runtime
# ------------------------------------------------------------
if ($Restart) {
    Write-Log "Redemarrage de LiteLLM"
    Push-Location $RepoRoot
    try { docker compose restart litellm 2>&1 | Out-Null } finally { Pop-Location }
    Start-Sleep -Seconds 25

    Write-Log "Smoke test"
    & (Join-Path $PSScriptRoot "Test-NexusSmoke.ps1") -IncludeRouters 2>&1 |
        Tee-Object -FilePath $LogPath -Append
    if ($LASTEXITCODE -ne 0) {
        Write-Log "Smoke test en echec : verifier 'docker compose logs litellm'" "ERROR"
        exit 1
    }
    Write-Log "Smoke test reussi" "OK"

    # La releve est verifiee A CHAQUE mise a jour, et non une fois pour
    # toutes. C'est precisement une mise a jour qui peut la casser : un
    # modele retire de l'inventaire, un alias regenere vers un autre poids,
    # une chaine de repli redessinee. Une releve dont on croit a tort
    # qu'elle fonctionne est pire qu'une releve absente -- on ne s'apercoit
    # de rien jusqu'au jour ou l'abonnement s'arrete.
    Write-Log "Verification de la releve locale"
    & $python (Join-Path $PSScriptRoot "nexus_releve.py") 2>&1 |
        Tee-Object -FilePath $LogPath -Append
    if ($LASTEXITCODE -ne 0) {
        # Avertissement et non arret : la passerelle reste utilisable, et
        # bloquer la mise a jour laisserait une configuration a moitie
        # appliquee. Mais le message doit etre sans ambiguite.
        Write-Log "RELEVE INOPERANTE : le travail s'arreterait avec l'abonnement" "ERROR"
        Write-Log "Diagnostic : python scripts/nexus_releve.py --tous" "ERROR"
    } else {
        Write-Log "Releve operationnelle" "OK"
    }
}

Write-Log "Mise a jour terminee" "OK"
exit 0
