# ============================================================
# restore.ps1 - Script de restauration/reconstruction
# ============================================================
# Ce script arrête les conteneurs existants, supprime les volumes,
# recrée la stack et télécharge les modèles locaux.
# Utilisation : exécuter depuis le dossier contenant docker-compose.yml
# ============================================================

# Vérifier que Docker est disponible
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Error "Docker n'est pas installé ou pas dans le PATH."
    exit 1
}

# Le prérequis est vérifié AVANT toute destruction.
#
# L'ordre était inverse : les volumes étaient supprimés, puis seulement
# ensuite l'absence de .env était constatée — et le script invitait alors à
# le renseigner « avant de relancer ce script », en sortant 0. Sur une
# machine neuve, c'est-à-dire le cas d'usage nominal que ce message décrit
# lui-même, PostgreSQL, Redis et les poids Ollama venaient d'être détruits,
# rien n'était redémarré, et le code de sortie disait succès.
if (-not (Test-Path .env)) {
    # Test-Path sur la SOURCE, comme backup.ps1 le fait pour chaque fichier :
    # sans lui, un .env.example manquant produisait une erreur non bloquante,
    # aucun .env créé, et une sortie affirmant pourtant l'avoir créé.
    if (Test-Path .env.example) {
        Copy-Item .env.example .env
        Write-Host "Fichier .env créé depuis .env.example. Renseignez vos clés API, puis relancez ce script."
    } else {
        Write-Error "Ni .env ni .env.example ne sont présents. Rien n'a été détruit."
    }
    # 1 et non 0 : rien n'a été restauré. Un appelant automatisé doit pouvoir
    # distinguer « restauration faite » de « prérequis manquant ».
    exit 1
}

# Avertissement : suppression des volumes
Write-Host "⚠️  Attention : cette opération va supprimer les volumes Docker (données PostgreSQL, modèles Ollama, cache Redis)."
Write-Host "Appuyez sur Ctrl+C pour annuler, ou Entrée pour continuer..."
Read-Host

# Arrêter et supprimer les conteneurs et volumes
docker compose down -v

# Démarrer la stack
docker compose up -d

# Attendre que le conteneur Ollama soit prêt
Write-Host "Attente du démarrage d'Ollama..."
$maxAttempts = 30
$attempt = 0
do {
    $attempt++
    Start-Sleep -Seconds 2
    $ollamaStatus = docker inspect --format='{{.State.Health.Status}}' ollama-server 2>$null
} while ($ollamaStatus -ne "healthy" -and $attempt -lt $maxAttempts)

# Vérifier que le conteneur Ollama est bien en état « healthy » après la boucle d'attente.
if ($ollamaStatus -ne "healthy") {
    Write-Error "Ollama n'est pas en état 'healthy' après $($maxAttempts * 2) secondes. Vérifiez les logs avec 'docker logs ollama-server'."
    exit 1
}

# Télécharger les modèles locaux
$models = Get-Content model_list.txt | Where-Object { $_ -notmatch '^NAME$' -and $_ -notmatch ':cloud$' -and $_ -notmatch '^\s*$' }
$successCount = 0
$failCount = 0
foreach ($model in $models) {
    $model = $model.Trim()
    if ($model -eq "") { continue }
    Write-Host "Téléchargement de $model..."
    docker exec ollama-server ollama pull $model

    if ($LASTEXITCODE -eq 0) {
        Write-Host "   ✔ Téléchargement réussi."
        $successCount++
    } else {
        Write-Warning "   ❌ Échec du téléchargement de $model."
        $failCount++
    }
}

Write-Host ""
Write-Host "============================================================"
Write-Host " Bilan du téléchargement des modèles locaux"
Write-Host "   Réussis : $successCount"
Write-Host "   Échecs  : $failCount"
Write-Host "============================================================"

if ($failCount -gt 0) {
    exit 1
}

Write-Host "✅ Restauration terminée."