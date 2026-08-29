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
    résultat observé ici, 553 Go avant, 553 Go après.

    Le script arrête la pile, effectue les deux opérations, puis la remonte.

.NOTES
    À lancer dans une console PowerShell ELEVEE. Le script refuse de
    s'exécuter autrement plutôt que d'échouer à mi-parcours, un disque
    virtuel abandonné entre deux états étant une bien plus mauvaise
    situation qu'un refus net.

.EXAMPLE
    .\scripts\Compact-NexusDisk.ps1
    .\scripts\Compact-NexusDisk.ps1 -SkipTrim     # si le TRIM a déjà été fait
#>
[CmdletBinding()]
param(
    [switch]$SkipTrim,
    [string]$VhdPath = "$env:LOCALAPPDATA\Docker\wsl\disk\docker_data.vhdx"
)

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
    Ecrire "Optimize-VHD refuse de s'executer sans droits administrateur, et"
    Ecrire "echoue SILENCIEUSEMENT : il rend un code de succes sans avoir"
    Ecrire "rien compacte. C'est ce qui s'est produit ici -- 553 Go avant,"
    Ecrire "553 Go apres, aucune erreur."
    Ecrire ""
    Ecrire "Ouvrez PowerShell en tant qu'administrateur, puis :" 'Yellow'
    Ecrire "    cd '$repo'" 'Yellow'
    Ecrire "    .\scripts\Compact-NexusDisk.ps1" 'Yellow'
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
# Le conteneur voit le systeme de fichiers que Windows ne sait pas lire.
# Sans cette etape, Optimize-VHD n'a aucun bloc a recuperer.
if (-not $SkipTrim) {
    Ecrire "1/4  TRIM depuis l'interieur du moteur..."
    try {
        $sortie = docker run --rm --privileged --pid=host alpine `
            nsenter -t 1 -m -u -i -n fstrim -av 2>&1
        $sortie | Where-Object { $_ -match 'trimmed' } | ForEach-Object { Ecrire "     $_" 'Green' }
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
try { docker compose down 2>&1 | Out-Null } finally { Pop-Location }
wsl --shutdown
Start-Sleep -Seconds 10

# --- 3. Compaction -------------------------------------------------------
Ecrire "3/4  Compaction (plusieurs minutes)..."
Optimize-VHD -Path $VhdPath -Mode Full

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
try {
    docker compose up -d 2>&1 | Out-Null
    for ($i = 0; $i -lt 20; $i++) {
        Start-Sleep -Seconds 6
        try {
            $r = Invoke-WebRequest -Uri "http://localhost:4000/health/liveliness" `
                -TimeoutSec 5 -UseBasicParsing -ErrorAction Stop
            if ($r.StatusCode -eq 200) { Ecrire "     LiteLLM repond." 'Green'; break }
        } catch { }
    }
} finally { Pop-Location }

$libre = (Get-PSDrive C).Free / 1GB
Write-Host ""
Ecrire ("Espace libre sur C: : {0:N0} Go" -f $libre)
Write-Host ""
Ecrire "Suite -- rapatrier les modeles dont les poids manquent :" 'Cyan'
Ecrire "    python scripts/nexus_pull_host.py" 'Cyan'
Ecrire "    python scripts/nexus_validate.py" 'Cyan'
Write-Host ""
