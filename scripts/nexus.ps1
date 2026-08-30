<#
.SYNOPSIS
    Point d'entree unique de la plateforme, appelable depuis n'importe ou.

.DESCRIPTION
    Les outils de la plateforme s'appellent par chemin absolu depuis un autre
    projet. C'est correct mais long a taper et facile a oublier. Ce script
    rassemble les gestes courants derriere un mot.

    La racine est deduite de $PSScriptRoot et jamais ecrite en dur : deplacer
    l'installation ne demande donc aucune retouche ici.

    Les chemins de fichiers passes aux sous-commandes restent relatifs au
    REPERTOIRE COURANT, c'est-a-dire au projet appelant, pas a la plateforme.

.EXAMPLE
    nexus                       # monte la pile
    nexus check                 # local, cloud et les trois routeurs
    nexus mcp                   # branche le projet courant sur le banc
    nexus ask "resume ce code" src/module.py
    nexus valide --base main
#>
[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [string]$Commande = 'start',

    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$Reste
)

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$racine = Split-Path -Parent $PSScriptRoot
if (-not $Reste) { $Reste = @() }

function Show-Aide {
    Write-Host ""
    Write-Host "  nexus <sous-commande> [arguments]" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "    start     monte la pile : moteur, conformite, conteneurs, passerelle"
    Write-Host "              (sous-commande par defaut, 'nexus' seul suffit)"
    Write-Host "    check     verifie le runtime : local, cloud et les trois routeurs"
    Write-Host "    status    controle de conformite, sans rien demarrer"
    Write-Host "    stop      arrete la pile"
    Write-Host "    mcp       ecrit .mcp.json dans le projet courant, pour que Claude"
    Write-Host "              Code y dispose des outils nexus_ask et consorts"
    Write-Host "    ask       interroge le banc gratuit :"
    Write-Host "                  nexus ask `"la consigne`" fichier1 fichier2"
    Write-Host "    valide    valide le PROJET COURANT sans agent ni cout :"
    Write-Host "                  nexus valide --base main"
    Write-Host "    help      cette aide"
    Write-Host ""
    Write-Host "  Plateforme : $racine" -ForegroundColor DarkGray
    Write-Host ""
}

function Get-Python {
    foreach ($nom in @('python', 'py', 'python3')) {
        $trouve = (Get-Command $nom -ErrorAction SilentlyContinue).Source
        if ($trouve) { return $trouve }
    }
    Write-Host "  Python introuvable dans le PATH." -ForegroundColor Red
    exit 1
}

# Un script PowerShell qui se termine sans `exit` laisse $LASTEXITCODE a sa
# valeur precedente, voire a $null. On ne propage donc que ce qui est
# reellement un code.
function Exit-Avec($code) {
    if ($null -eq $code) { exit 0 }
    exit $code
}

switch ($Commande.ToLower()) {

    'start' {
        & (Join-Path $PSScriptRoot 'start.ps1') @Reste
        Exit-Avec $LASTEXITCODE
    }

    'check' {
        & (Join-Path $PSScriptRoot 'Test-NexusSmoke.ps1') -IncludeRouters
        Exit-Avec $LASTEXITCODE
    }

    'status' {
        & (Get-Python) (Join-Path $PSScriptRoot 'nexus_conformite.py') @Reste
        Exit-Avec $LASTEXITCODE
    }

    'stop' {
        & (Join-Path $PSScriptRoot 'stop.ps1') @Reste
        Exit-Avec $LASTEXITCODE
    }

    'ask' {
        if ($Reste.Count -lt 1) {
            Write-Host "  Aucune consigne. Exemple :" -ForegroundColor Red
            Write-Host '      nexus ask "resume ce fichier" src/module.py' -ForegroundColor Yellow
            exit 1
        }
        $consigne = $Reste[0]
        # Decoupage explicite : $Reste[1..($Reste.Count-1)] sur un tableau
        # d'un seul element donne les indices 1 PUIS 0, donc $null suivi de
        # la consigne elle-meme -- qui partirait alors comme nom de fichier.
        $fichiers = @()
        if ($Reste.Count -gt 1) { $fichiers = $Reste[1..($Reste.Count - 1)] }

        $arguments = @(
            (Join-Path $PSScriptRoot 'nexus_agent.py')
            '--tache', $consigne
            '--modele', 'gpt-oss-120b-cloud'
            '--max-tokens', '2000'
        )
        if ($fichiers.Count -gt 0) { $arguments += '--fichiers'; $arguments += $fichiers }

        & (Get-Python) @arguments
        Exit-Avec $LASTEXITCODE
    }

    'valide' {
        & (Get-Python) (Join-Path $PSScriptRoot 'nexus_valide.py') @Reste
        Exit-Avec $LASTEXITCODE
    }

    'mcp' {
        $courant = (Get-Location).Path

        # Ce test passe AVANT celui du fichier existant : la plateforme a
        # deja son .mcp.json, et signaler « il existe deja » masquerait la
        # vraie raison du refus.
        if ([System.IO.Path]::GetFullPath($courant).TrimEnd('\','/') -ieq
            [System.IO.Path]::GetFullPath($racine).TrimEnd('\','/')) {
            Write-Host "  Refuse : vous etes dans la plateforme elle-meme," -ForegroundColor Red
            Write-Host "  qui possede deja son .mcp.json. Placez-vous dans le" -ForegroundColor Red
            Write-Host "  projet a brancher, puis relancez 'nexus mcp'." -ForegroundColor Yellow
            exit 1
        }

        $cible = Join-Path $courant '.mcp.json'
        $serveur = ($racine -replace '\\', '/') + '/tools/nexus-mcp/server.js'
        $contenu = @"
{
  "mcpServers": {
    "nexus-local": {
      "command": "node",
      "args": ["$serveur"],
      "env": { "NEXUS_LITELLM_URL": "http://127.0.0.1:4000" }
    }
  }
}
"@

        if (Test-Path $cible) {
            Write-Host "  .mcp.json existe deja ici : il n'est pas ecrase." -ForegroundColor Yellow
            Write-Host "  Ajoutez cette entree a la main dans 'mcpServers' :" -ForegroundColor Yellow
            Write-Host ""
            Write-Host $contenu -ForegroundColor DarkGray
            exit 0
        }

        [System.IO.File]::WriteAllText($cible, $contenu, (New-Object System.Text.UTF8Encoding($false)))
        Write-Host "  .mcp.json ecrit dans $courant" -ForegroundColor Green
        Write-Host "  Relancez Claude Code dans ce projet et approuvez 'nexus-local'." -ForegroundColor Gray
        exit 0
    }

    { $_ -in @('help', '-h', '--help', '/?') } { Show-Aide; exit 0 }

    default {
        Write-Host ""
        Write-Host "  Sous-commande inconnue : '$Commande'" -ForegroundColor Red
        Show-Aide
        exit 1
    }
}
