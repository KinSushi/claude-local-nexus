# Set-ClaudeModel.ps1

**Choisit explicitement le mode d'exécution de Claude Code.**

> ⚠️ Ce script a été réécrit. La version précédente basculait
> automatiquement sur `claude-sonnet-5` « si Anthropic était disponible » en
> posant `ANTHROPIC_BASE_URL` **et** `ANTHROPIC_AUTH_TOKEN`. Or poser le jeton
> désactive l'abonnement claude.ai : le script consommait donc des **crédits
> API facturés au token** tout en laissant croire qu'il utilisait
> l'abonnement. La bascule automatique a été supprimée.

---

## Ce qu'il faut savoir avant de l'utiliser

La documentation Anthropic distingue deux variables :

| Variable | Effet |
|---|---|
| `ANTHROPIC_BASE_URL` seule | Le trafic passe par la passerelle, **l'abonnement reste la credential active** |
| `ANTHROPIC_AUTH_TOKEN` (ou `apiKeyHelper`) | **Remplace l'abonnement** : facturation au token sur la clé |

Par ailleurs, Anthropic ne prend pas en charge le routage de Claude Code vers
des **modèles non-Claude** à travers une passerelle.

**Pour combiner abonnement et modèles locaux dans une même session, ce script
n'est pas la bonne voie.** La voie supportée est le serveur MCP
`nexus-local` — voir [docs/pont-local-abonnement.md](docs/pont-local-abonnement.md).
Ce script sert au cas d'usage complémentaire : basculer délibérément toute la
session sur un autre plan d'exécution, typiquement en fin de quota.

---

## Utilisation

### État courant (défaut, ne modifie rien)

```powershell
.\Set-ClaudeModel.ps1
```

Affiche le mode actif, l'inventaire de la passerelle et le rappel des outils
MCP disponibles.

### Revenir à l'abonnement

```powershell
.\Set-ClaudeModel.ps1 -Mode Subscription
```

Retire les variables de passerelle de la session. Claude Code réutilise la
connexion claude.ai.

### Basculer sur un modèle local

```powershell
.\Set-ClaudeModel.ps1 -Mode Local
.\Set-ClaudeModel.ps1 -Mode Local -Model qwen3-coder-30b-local
```

Sans `-Model`, le script retient le premier disponible par ordre de
préférence : `glm-4.7-flash-local` (MoE, peu de paramètres actifs — le plus
utilisable des gros modèles sur un hôte CPU), puis les Qwen Coder, puis des
modèles plus légers.

> Réserve : les fenêtres locales sont à 8K/32K alors que Claude Code est
> gourmand en contexte. Les sessions longues risquent de saturer. C'est un
> mode de dépannage, pas un remplacement.

### Basculer sur Claude via la passerelle

```powershell
.\Set-ClaudeModel.ps1 -Mode Gateway
```

**Facturé au token** sur les crédits API, pas sur l'abonnement. Le script
l'affiche explicitement.

---

## Portée

Les variables ne valent que pour la **session PowerShell courante**. Ouvrir un
nouveau terminal revient au mode abonnement natif.

Pour un raccourci permanent, ajouter à votre `$PROFILE` :

```powershell
function Set-ClaudeLocal { & "C:\local-llm-docker\Set-ClaudeModel.ps1" @args }
```

---

**Auteur** : KinSushi – Enzo – Sovralys LLC
