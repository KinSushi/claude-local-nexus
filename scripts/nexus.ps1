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
    Write-Host "    mcp       branche le projet courant sur le banc, pour que Claude"
    Write-Host "              Code y dispose de nexus_ask et consorts. Fusionne avec"
    Write-Host "              un .mcp.json existant : les autres serveurs declares"
    Write-Host "              sont preserves, et l'ancien fichier sauvegarde"
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

        # Ce test passe AVANT tout autre : la plateforme a deja son .mcp.json,
        # et signaler « il existe deja » masquerait la vraie raison du refus.
        if ([System.IO.Path]::GetFullPath($courant).TrimEnd('\','/') -ieq
            [System.IO.Path]::GetFullPath($racine).TrimEnd('\','/')) {
            Write-Host "  Refuse : vous etes dans la plateforme elle-meme," -ForegroundColor Red
            Write-Host "  qui possede deja son .mcp.json. Placez-vous dans le" -ForegroundColor Red
            Write-Host "  projet a brancher, puis relancez 'nexus mcp'." -ForegroundColor Yellow
            exit 1
        }

        $cible = Join-Path $courant '.mcp.json'
        # Barres obliques : un chemin Windows en antislashes traverse mal le
        # JSON, ou chaque separateur devrait etre double.
        $serveur = ($racine -replace '\\', '/') + '/tools/nexus-mcp/server.js'

        # NEXUS_WORK_ROOT n'est deliberement PAS fixe ici.
        #
        # Le serveur resout sa racine de travail par NEXUS_WORK_ROOT, puis
        # CLAUDE_PROJECT_DIR, puis le repertoire courant. Claude Code fournit
        # toujours la deuxieme, qui suit le projet meme s'il est deplace ou
        # renomme. Figer un chemin absolu ici reintroduirait exactement le
        # defaut que cette commande repare : une configuration qui ne suit
        # plus son projet.
        $attendu = [ordered]@{
            command = 'node'
            args    = @($serveur)
            env     = [ordered]@{ NEXUS_LITELLM_URL = 'http://127.0.0.1:4000' }
        }

        function Write-JsonSansBom($chemin, $objet) {
            $texte = ($objet | ConvertTo-Json -Depth 10)
            [System.IO.File]::WriteAllText($chemin, $texte,
                (New-Object System.Text.UTF8Encoding($false)))
        }

        # Comparaison champ par champ plutot que par serialisation : l'ordre
        # des proprietes d'un objet relu depuis JSON n'est pas garanti, et une
        # comparaison de chaines conclurait a tort a une divergence.
        function Test-EntreeConforme($entree, $serveurAttendu) {
            if ($null -eq $entree) { return $false }
            if ($entree.command -ne 'node') { return $false }
            $entryArgs = @($entree.args)
            if ($entryArgs.Count -ne 1 -or $entryArgs[0] -ne $serveurAttendu) { return $false }
            if ($null -eq $entree.env) { return $false }
            return $entree.env.NEXUS_LITELLM_URL -eq 'http://127.0.0.1:4000'
        }

        # --- Aucun fichier : creation simple -----------------------------
        if (-not (Test-Path $cible)) {
            Write-JsonSansBom $cible ([ordered]@{
                mcpServers = [ordered]@{ 'nexus-local' = $attendu }
            })
            Write-Host "  .mcp.json ecrit dans $courant" -ForegroundColor Green
            Write-Host "  Relancez Claude Code dans ce projet et approuvez 'nexus-local'." -ForegroundColor Gray
            exit 0
        }

        # --- Fichier present : fusionner, jamais ecraser en bloc ----------
        #
        # L'ancienne version refusait d'ecrire et sortait en code 0. Un
        # .mcp.json copie a la main depuis la plateforme porte un chemin
        # RELATIF ; le serveur ne demarre alors jamais, et comme la portee
        # projet l'emporte sur la portee utilisateur, ce fichier casse masque
        # une declaration saine. Le code 0 faisait croire qu'il n'y avait rien
        # a faire : la commande etait bloquee par le fichier meme qu'elle
        # devait reparer.
        try {
            $json = Get-Content -Path $cible -Raw -Encoding UTF8 | ConvertFrom-Json
        } catch {
            Write-Host "  .mcp.json illisible : $($_.Exception.Message)" -ForegroundColor Red
            Write-Host "  Rien n'a ete ecrit. Corrigez le JSON, puis relancez." -ForegroundColor Yellow
            exit 1
        }
        if ($null -eq $json) { $json = [pscustomobject]@{} }

        # Parentheses obligatoires : sans elles, -not s'applique a la liste
        # des noms avant le -contains, et la condition ne vaut jamais ce que
        # l'on croit.
        if (-not ($json.PSObject.Properties.Name -contains 'mcpServers') -or
            $null -eq $json.mcpServers) {
            $json | Add-Member -MemberType NoteProperty -Name 'mcpServers' `
                               -Value ([pscustomobject]@{}) -Force
        }

        if (Test-EntreeConforme $json.mcpServers.'nexus-local' $serveur) {
            Write-Host "  .mcp.json deja conforme : rien a ecrire." -ForegroundColor Green
            exit 0
        }

        $horodatage = Get-Date -Format 'yyyyMMddTHHmmss'
        # Suffixe APRES l'extension : une sauvegarde nommee .json risquerait
        # d'etre relue comme une configuration.
        $sauvegarde = "$cible.avant-nexus-$horodatage"
        Copy-Item -Path $cible -Destination $sauvegarde -Force

        # Add-Member -Force et non une affectation directe : sur un
        # PSCustomObject, affecter une propriete qui n'existe pas encore
        # echoue. C'est precisement le cas d'un .mcp.json qui declare
        # d'autres serveurs mais pas nexus-local.
        $json.mcpServers | Add-Member -MemberType NoteProperty -Name 'nexus-local' `
                                      -Value $attendu -Force

        Write-JsonSansBom $cible $json
        Write-Host "  .mcp.json mis a jour : entree 'nexus-local' corrigee." -ForegroundColor Green
        Write-Host "  Sauvegarde : $(Split-Path -Leaf $sauvegarde)" -ForegroundColor Gray
        Write-Host "  Les autres serveurs declares sont preserves." -ForegroundColor Gray
        exit 0
    }

    'sujets' {
        # Recupere les sujets restes ouverts au fil de la session, depuis la
        # transcription, les messages de commit et le cockpit. Une session
        # longue perd ses sujets ouverts, et les deviner de memoire produit
        # des oublis silencieux ; ce qui est sur disque ne se perd pas.
        & python (Join-Path $PSScriptRoot 'nexus_sujets.py') @Reste
        Exit-Avec $LASTEXITCODE
    }

    'maj-modeles' {
        # Rafraichit les modeles Ollama DEJA INSTALLES. Le depot savait
        # rapatrier un modele ABSENT (-SyncLocal) ; il ne savait pas mettre a
        # jour ceux qui sont la.
        #
        # SIMULATION PAR DEFAUT, et c'est deliberé : un rafraichissement du
        # parc entier represente des centaines de gigaoctets. Il faut
        # `--appliquer` pour qu'un octet soit telecharge.
        #
        # Non arme dans la tache quotidienne : engager la bande passante et
        # le disque sans que personne l'ait demande n'est pas une decision
        # d'outil.
        & python (Join-Path $PSScriptRoot 'nexus_maj_modeles.py') @Reste
        Exit-Avec $LASTEXITCODE
    }

    'rendu-vide' {
        # Livre par le banc, cable ici : un outil que personne n'appelle est
        # un fichier. Il MESURE le rendu vide sur longue generation au lieu
        # de le supposer, et fait DEUX passes par modele -- un modele froid
        # paie le chargement de ses poids, et une lecture en une seule phase
        # attribue ce chargement au modele (contrat 112.3).
        & python (Join-Path $PSScriptRoot 'mesure_rendu_vide.py') @Reste
        Exit-Avec $LASTEXITCODE
    }

    { $_ -in @('help', '-h', '--help', '/?') } { Show-Aide; exit 0 }

    default {
        Write-Host ""
        Write-Host "  Sous-commande inconnue : '$Commande'" -ForegroundColor Red
        Show-Aide
        exit 1
    }
}
