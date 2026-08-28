```markdown
# Set-ClaudeModel.ps1

**Configure automatiquement Claude Code pour utiliser le meilleur modèle disponible via le proxy LiteLLM.**

Ce script prépare votre session PowerShell afin que Claude Code puisse interagir avec votre plateforme **Claude-Local-Nexus**. Il sélectionne intelligemment le modèle à utiliser selon la disponibilité d'Anthropic, la présence de modèles locaux et le cloud gratuit. Il définit les variables d'environnement nécessaires à Claude Code (`ANTHROPIC_BASE_URL` et `ANTHROPIC_AUTH_TOKEN`).

## Fonctionnalités

- ✅ Détection automatique de la disponibilité d'Anthropic (clé valide, quota non épuisé).
- 🔄 Bascule automatique vers un modèle local robuste si Anthropic est indisponible.
- ☁️ Utilisation possible du cloud gratuit (`gpt-oss-20b-cloud`).
- 🛠️ Possibilité de forcer un modèle local, cloud ou spécifique.
- 🧠 Préparation de l'environnement pour Claude Code.

## Prérequis

- Le proxy LiteLLM doit être en cours d'exécution sur `http://localhost:4000`.
- La variable d'environnement `LITELLM_MASTER_KEY` doit être définie dans votre session PowerShell.
- Le script doit être exécuté depuis le dossier où se trouve `Set-ClaudeModel.ps1` (ou utiliser le chemin complet).

## Utilisation

Placez le script dans `C:\local-llm-docker` et exécutez-le selon vos besoins.

### Détection automatique (recommandé)

```powershell
.\Set-ClaudeModel.ps1
```

Le script testera si Anthropic est joignable et utilisera `claude-sonnet-5` si possible. Sinon, il basculera automatiquement sur un modèle local comme `qwen3-coder-30b-local` ou `gemma4-31b-local`.

### Forcer un modèle local

```powershell
.\Set-ClaudeModel.ps1 -ForceLocal
```

Choisit le premier modèle local disponible parmi une liste prioritaire (Qwen3-Coder-30B, Qwen2.5-Coder-32B, Gemma4-31B, etc.).

### Forcer le cloud gratuit

```powershell
.\Set-ClaudeModel.ps1 -ForceCloud
```

Utilise `gpt-oss-20b-cloud` s'il est présent dans la configuration.

### Utiliser un modèle spécifique

```powershell
.\Set-ClaudeModel.ps1 -Model "qwen3-coder-30b-local"
```

Remplacez par le nom exact d'un modèle listé par le proxy.

## Après exécution

Une fois le script terminé, les variables d'environnement sont définies. Vous pouvez lancer Claude Code normalement :

```powershell
claude
```

Ou forcer le modèle choisi :

```powershell
claude --model qwen3-coder-30b-local
```

## Intégration permanente dans PowerShell

Pour pouvoir appeler ce script de n'importe où, ajoutez la fonction suivante à votre `$PROFILE` :

```powershell
function Set-ClaudeLocal {
    & "C:\local-llm-docker\Set-ClaudeModel.ps1" @args
}
```

Ensuite, utilisez simplement :

```powershell
Set-ClaudeLocal                  # détection automatique
Set-ClaudeLocal -ForceLocal      # forcer local
```

## Gestion de la fin de session hebdomadaire Anthropic

Le principal avantage de ce script est sa capacité à **maintenir Claude Code opérationnel même lorsque votre quota Anthropic est épuisé**. Grâce à la détection automatique, le script bascule sur un modèle local ou cloud gratuit sans intervention manuelle. Vous n'avez donc jamais à vous soucier de l'interruption du service.

---

**Auteur** : KinSushi – Enzo – Sovralys LLC
```