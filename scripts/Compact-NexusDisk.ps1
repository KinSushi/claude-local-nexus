<#
.SYNOPSIS
    Rend au disque l'espace libéré par la sortie des modèles hors de Docker.

.DESCRIPTION
    Après la suppression du volume `local-llm-docker_ollama_data`, le disque
    virtuel WSL2 de Docker garde sa taille : Windows ignore quels blocs sont
    libres à l'intérieur du système de fichiers ext4. Deux opérations sont
    nécessaires, dans cet ordre, et une seule d'entre elles exige des droits
    administrateur :

        1. fstrim, DEPUIS l'intérieur — marque les blocs comme libres ;
        2. Optimize-VHD, DEPUIS Windows — rétracte réellement le fichier.

    Faire la seconde sans la première ne libère rien : c'est exactement le
    résultat observé ici, 553 Go avant, 553 Go après.

    Le script arrête la pile, effectue les deux opérations, puis la remonte.

.NOTES
    À lancer dans une console PowerShell ELEVEE. Le script refuse de
    s'exécuter autrement plutôt que d'échouer à mi‑parcours, un disque
    virtuel abandonné entre deux états étant une bien plus mauvaise
    situation qu'un refus net.

.EXAMPLE
    .\scripts\Compact-NexusDisk.ps1
    .\scripts\Compact-NexusDisk.ps1 -SkipTrim     # si le TRIM a déjà été fait
#>
[CmdletBinding()]
param(
    [switch]$SkipTrim,
    [string]$VhdPath = "$env:LOCALAPPDATA\Docker\wsl\disk\docker_data.vhdx",
    [string]$HealthCheckUrl = "http://localhost:4000/health/liveliness"
)

# Forcer l'encodage UTF-8 de la console (comme dans Initialize-Nexus.ps1)
$OutputEncoding = [System.Text.UTF8Encoding]::new()
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()

$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot

function Ecrire($texte, $couleur = 'Gray') { Write-Host "  $texte" -ForegroundColor $couleur }

Write-Host ""
Write-Host "=== Compaction du disque virtuel Docker ===" -ForegroundColor Cyan
Write-Host ""

# --- Élévation -----------------------------------------------------------
$eleve = ([Security.Principal.WindowsPrincipal] `
    [Security.Principal.WindowsIdentity]::GetCurrent()
).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

if (-not $eleve) {
    Ecrire "Cette console n'est pas elevee." 'Red'
    Ecrire ""
    Ecrire "Optimize-VHD refuse de s'executer sans droits administrateur, et" 'Red'
    Ecrire "echoue SILENCIEUSEMENT : il rend un code de succes sans avoir" 'Red'
    Ecrire "rien compacte. C'est ce qui s'est produit ici -- 553 Go avant," 'Red'
    Ecrire "553 Go apres, aucune erreur." 'Red'
    Ecrire ""
    Ecrire "Ouvrez PowerShell en tant qu'administrateur, puis :" 'Yellow'
    Ecrire "    cd '$repo'" 'Yellow'
    Ecrire "    .\scripts\Compact-NexusDisk.ps1" 'Yellow'
    exit 1
}

# Vérifier la présence de la cmdlet Optimize-VHD
if (-not (Get-Command Optimize-VHD -ErrorAction SilentlyContinue)) {
    Ecrire "Optimize-VHD introuvable. Installez le module Hyper-V." 'Red'
    exit 1
}

if (-not (Test-Path $VhdPath)) {
    Ecrire "Disque virtuel introuvable : $VhdPath" 'Red'
    Ecrire "Verifiez le chemin -- il change selon la version de Docker Desktop."
    exit 1
}

$avant = (Get-Item $VhdPath).Length / 1GB
Ecrire ("Disque virtuel : {0:N1} Go" -f $avant)
Ecrire "Chemin         : $VhdPath"
Write-Host ""

# --- 1. TRIM depuis l'interieur -----------------------------------------
if (-not $SkipTrim) {
    Ecrire "1/4  TRIM depuis l'interieur du moteur..."
    try {
        $sortie = docker run --rm --privileged --pid=host alpine `
            nsenter -t 1 -m -u -i -n fstrim -av 2>&1
        $trimLines = $sortie | Where-Object { $_ -match 'trimmed' }
        if ($trimLines) {
            $trimLines | ForEach-Object { Ecrire "     $_" 'Green' }
        } else {
            Ecrire "     Aucun resultat TRIM detecte." 'Yellow'
        }
    } catch {
        Ecrire "     TRIM impossible : $_" 'Yellow'
        Ecrire "     Le moteur Docker doit tourner pour cette etape."
        Ecrire "     Relancez avec -SkipTrim si le TRIM a deja ete fait."
        exit 1
    }
} else {
    Ecrire "1/4  TRIM ignore (-SkipTrim)"
}

# --- 2. Arret de la pile -------------------------------------------------
Ecrire "2/4  Arret de la pile et de WSL..."
Push-Location $repo
try { docker compose down } finally { Pop-Location }
wsl --shutdown
Start-Sleep -Seconds 10

# --- 3. Compaction -------------------------------------------------------
Ecrire "3/4  Compaction (plusieurs minutes)..."

# Réessayer Optimize-VHD tant que le fichier est verrouillé
$maxRetries = 5
$retry = 0
while ($true) {
    try {
        Optimize-VHD -Path $VhdPath -Mode Full -ErrorAction Stop
        break
    } catch {
        if ($retry -ge $maxRetries) {
            Ecrire "Echec de la compaction du VHDX : $_" 'Red'
            exit 1
        }
        $retry++
        Ecrire "VHDX verrouille, attente avant nouvelle tentative ($retry/$maxRetries)..." 'Yellow'
        Start-Sleep -Seconds 5
    }
}

$apres = (Get-Item $VhdPath).Length / 1GB
$gagne = $avant - $apres
Write-Host ""
Ecrire ("Avant  : {0:N1} Go" -f $avant)
Ecrire ("Apres  : {0:N1} Go" -f $apres)
if ($gagne -gt 1) {
    Ecrire ("Libere : {0:N1} Go" -f $gagne) 'Green'
} else {
    Ecrire "Aucun espace libere." 'Yellow'
    Ecrire "Le TRIM n'a probablement pas ete execute, ou le disque etait deja compact."
}
Write-Host ""

# --- 4. Remise en route --------------------------------------------------
Ecrire "4/4  Redemarrage de la pile..."
Push-Location $repo
$pileDebout = $false
$daemonReady = $false

try {
    # Attente du daemon Docker
    for ($d = 0; $d -lt 30; $d++) {
        docker info --format '{{.ServerVersion}}' 2>$null | Out-Null
        if ($LASTEXITCODE -eq 0) {
            $daemonReady = $true
            break
        }
        Start-Sleep -Seconds 4
    }

    if (-not $daemonReady) {
        Ecrire "Daemon Docker ne repond pas, abandon du demarrage." 'Red'
    } else {
        # Lancer la pile
        $composeOut = docker compose up -d 2>&1
        if ($LASTEXITCODE -ne 0) {
            Ecrire "Erreur lors du demarrage de la pile :" 'Red'
            $composeOut | ForEach-Object { Ecrire "     $_" 'Red' }
        } else {
            $composeOut | ForEach-Object { Ecrire "     $_" 'Gray' }

            # Vérifier la disponibilité du service via healthcheck
            for ($i = 0; $i -lt 25; $i++) {
                Start-Sleep -Seconds 6
                try {
                    $r = Invoke-WebRequest -Uri $HealthCheckUrl -TimeoutSec 5 -ErrorAction Stop
                    if ($r.StatusCode -eq 200) { $pileDebout = $true; break }
                } catch { }
            }
        }
    }
} finally { Pop-Location }

if ($pileDebout) {
    Ecrire "     LiteLLM repond." 'Green'
} else {
    Ecrire "     LiteLLM NE REPOND PAS apres 150 s." 'Red'
    Ecrire "     La compaction a reussi, mais la pile est restee a terre." 'Red'
    Ecrire "     Relancez :  .\scripts\start.ps1" 'Yellow'
    Ecrire "     Diagnostic : docker compose logs litellm --tail 80" 'Yellow'
    # Retourner un code de succes car la compaction elle‑meme a reussi
    exit 0
}

$libre = (Get-PSDrive C).Free / 1GB
Write-Host ""
Ecrire ("Espace libre sur C: : {0:N0} Go" -f $libre)
Write-Host ""
Ecrire "Suite -- rapatrier les modeles dont les poids manquent :" 'Cyan'
Ecrire "    python scripts/nexus_pull_host.py" 'Cyan'
Ecrire "    python scripts/nexus_conformite.py" 'Cyan'
Ecrire "    .\scripts\start.ps1 -Restart" 'Cyan'
Write-Host ""
