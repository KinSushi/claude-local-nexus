# Associer les modèles locaux et l'abonnement Claude

Ce document explique la contrainte qui structure toute l'architecture, les
trois montages possibles, et ce qui est effectivement déployé.

---

## 1. La contrainte de départ

L'intuition naturelle est de router Claude Code vers LiteLLM pour que la
passerelle arbitre entre local, cloud et Claude. **Cette voie ne permet pas
d'utiliser l'abonnement.**

La documentation Anthropic est explicite :

> *Setting only `ANTHROPIC_BASE_URL`, without a gateway credential, doesn't
> replace the subscription. […] While a gateway credential variable or
> `apiKeyHelper` is active, a developer's claude.ai subscription isn't used :
> the credential replaces the subscription login for that session […]. That
> traffic is billed per token to whoever owns the credential.*

Deux conséquences :

1. Ce n'est pas `ANTHROPIC_BASE_URL` qui neutralise l'abonnement, c'est le
   **jeton** (`ANTHROPIC_AUTH_TOKEN`). Poser les deux — ce que faisait
   l'ancien `Set-ClaudeModel.ps1` en mode automatique — bascule la
   facturation vers les crédits API sans le dire.
2. Anthropic ne prend pas en charge le routage de Claude Code vers des
   **modèles non-Claude** à travers une passerelle.

La conclusion n'est pas que la combinaison est impossible : c'est qu'elle ne
doit pas passer par le plan d'authentification.

---

## 2. Les trois montages

| | Principe | Abonnement utilisé | Combinaison en session |
|---|---|---|---|
| **A** | Les modèles de la passerelle deviennent des **outils** MCP | oui | oui |
| **B** | Deux profils étanches, l'un natif, l'autre passerelle | alternativement | non |
| **C** | Le local **réduit le contexte** en amont de Claude | oui | oui |

**A** et **C** sont complémentaires et constituent le déploiement principal.
**B** reste un filet de sécurité pour les fins de quota.

---

## 3. Ce qui est déployé — montage A + C

```
        Claude Code  (abonnement claude.ai, natif — orchestrateur)
              |
              |  outils MCP (stdio)
              v
        nexus-local  (tools/nexus-mcp/server.js, sans dépendance)
              |
              |  HTTP
              v
        LiteLLM 127.0.0.1:4000
              |
    +---------+-----------+------------------+
    v                     v                  v
  LOCAL                OLLAMA CLOUD       ANTHROPIC
  40 alias             6 alias            4 alias
  coût 0               abonnement Ollama  crédits API
  rien ne sort         sort vers          facturé au token
                       ollama.com
```

Claude Code reste sur l'abonnement et **orchestre**. La passerelle devient un
banc de modèles qu'il appelle à la demande. L'arbitrage coût /
confidentialité / capacité redevient une décision explicite, prise appel par
appel.

### Les outils exposés

Base volontairement réduite, vouée à s'étendre :

| Famille | Outil | Rôle |
|---|---|---|
| Exécution | `nexus_ask` | Déléguer à un modèle, ou à un **profil de tâche** |
| | `nexus_route` | Laisser le routeur adaptatif choisir dans un plan |
| | `nexus_batch` | Enchaîner plusieurs tâches, chacune sur son modèle |
| | `nexus_compare` | Poser la même question à plusieurs modèles, côte à côte |
| Contexte | `nexus_context` | Traiter un corpus plus grand que toute fenêtre |
| | `nexus_summarize` | Réduire des fichiers en synthèse, en local |
| | `nexus_index_build` | Indexer le dépôt en embeddings locaux |
| | `nexus_search` | Recherche hybride sémantique + lexicale |
| Modalité | `nexus_vision` | Analyser une image avec un modèle multimodal local |
| Inspection | `nexus_models` | Inventaire annoté par plan, coût et confidentialité |
| | `nexus_profile` | Limites réelles de la machine, verdict par modèle |
| | `nexus_savings` | Ce que la délégation fait économiser |

### Demander une classe de tâche, pas un modèle

`nexus_ask` accepte un `profile` à la place d'un `model`. La plateforme
retient alors le premier candidat réellement exposé, en privilégiant le
local :

| Profil | Pour | Retenu sur cette machine |
|---|---|---|
| `coding` | implémentation, débogage, refactorisation | `releve-locale` (64K) |
| `reasoning` | architecture, arbitrages | `glm-4.7-flash-local` |
| `rapide` | classification, extraction, transformation | `llama3.2-3b-local` |
| `multimodal` | image, capture d'écran, OCR | `llava-7b-local` |

Demander `coding` plutôt que `qwen3-coder-30b-local` laisse la plateforme
arbitrer selon ce qui est réellement disponible **et exécutable** : le
verdict matériel s'applique aussi ici.

Chaque réponse est préfixée du modèle réellement retenu, du plan et du mode
de facturation — une décision de routage qui ne s'explique pas est
opérationnellement incomplète.

### Le montage C en pratique

`nexus_index_build` puis `nexus_search` permettent de répondre à « où se
trouve X » sans charger les fichiers entiers dans le contexte de
l'abonnement. `nexus_summarize` distille un fichier volumineux localement et
ne fait remonter que la synthèse. Le volume est absorbé gratuitement ; les
tokens de l'abonnement ne paient que le raisonnement.

**Choix du modèle d'embedding — mesuré, pas supposé.** Le défaut est
`qwen3-embedding-8b-local`. `nomic-embed-text`, plus léger et longtemps
retenu par défaut dans la plateforme, a été écarté après mesure : sur une
paire française, il classe la phrase **sans rapport au-dessus de la
paraphrase**.

| Modèle | paraphrase | phrase sans rapport | verdict |
|---|---|---|---|
| `nomic-embed-text` | 0,520 | 0,555 | incohérent |
| `nomic-embed-text` + préfixes | 0,623 | 0,640 | incohérent |
| `all-minilm` | 0,527 | 0,434 | faible marge |
| `qwen3-embedding:8b` | 0,875 | 0,417 | net |

Un index construit sur un modèle incohérent ne serait pas seulement
médiocre : il serait **trompeur**, en remontant avec assurance des extraits
hors sujet. Le prix est la lenteur — 8 milliards de paramètres sur CPU —, et
il est assumé.

La recherche impose d'utiliser le modèle qui a construit l'index : deux
modèles ne partagent pas d'espace vectoriel, et comparer leurs vecteurs
produirait des scores silencieusement faux.

**Secrets exclus explicitement.** Les extraits de l'index et les synthèses
remontent vers l'orchestrateur, donc quittent la machine. `.env`, clés,
certificats et fichiers nommés `secret`/`credentials` sont refusés à
l'indexation **et** à la synthèse. C'est une interdiction déclarée, pas le
simple effet de bord d'une extension non reconnue.

---

## 3 bis. Atteindre 1 M de contexte sans qu'aucun modèle ne l'offre

Aucun modèle local ne propose 1 M de contexte, et lui en allouer coûterait
une mémoire dont la machine ne dispose pas. `nexus_context` obtient
l'équivalent autrement :

```
   corpus (illimité)
        │
        ├── découpage en fenêtres qui tiennent réellement
        │
   MAP  ├── fragment 1 ──> analyse partielle
        ├── fragment 2 ──> analyse partielle
        └── fragment N ──> analyse partielle
                │
   REDUCE       └── fusion par paliers jusqu'à une seule fenêtre
                        │
                        └──> synthèse
```

Le découpage se fait sur des frontières naturelles (paragraphe, ligne,
phrase) pour ne pas amputer le sens, et chaque fragment est traité comme un
fragment : le modèle a pour consigne de ne rien conclure sur l'ensemble,
puisque d'autres fragments existent.

**Le plafond n'est donc plus la fenêtre, mais le temps** — qui, en local,
ne coûte rien d'autre que de l'attente. C'est ce qui rend le montage
utilisable même sans abonnement.

## 3 ter. La relève : se passer de l'abonnement

L'alias `releve-locale` est dédié au cas où l'abonnement expire ou que son
quota est atteint. Il est dimensionné sur une mesure, pas sur une estimation :

```
glm-4.7-flash à 65 536 de contexte  ->  23 Go occupés
   19 Go de poids  +  ~4 Go de cache KV        (relevé par `ollama ps`)
```

Trois raisons à ce choix : 64K est la fenêtre minimale pour que Claude Code
reste utilisable sur un dépôt réel ; c'est un MoE 30B-A3B dont peu de
paramètres sont actifs, donc praticable sur CPU ; et il gère l'appel
d'outils, sans lequel la boucle agentique ne fonctionne pas.

```powershell
.\Set-ClaudeModel.ps1 -Mode Local    # retient releve-locale en priorité
```

Ce profil est volontairement **hors des pools de routage** : ce n'est pas un
candidat parmi d'autres, c'est un rôle qu'on endosse explicitement.

## 3 quater. Garde-fou matériel

La machine est mesurée, jamais supposée, et son verdict s'impose
automatiquement à chaque modèle :

| Verdict | Condition | Effet |
|---|---|---|
| `ACCEPT` | poids ≤ 60 % de la mémoire du moteur | éligible au routage automatique |
| `DEGRADED` | ≤ 85 % | adressable, mais hors pools et hors chaînes de fallback |
| `REJECT` | > 85 % | pas déclaré du tout, et non téléchargé |

```powershell
python scripts/nexus_capability.py          # rapport lisible
python scripts/nexus_capability.py --json   # profil exploitable
```

Un modèle trop lourd n'échoue pas franchement : il pagine, et la réponse
n'arrive jamais utilement. Le laisser sélectionnable automatiquement revient
à tirer au sort une réponse qui ne viendra pas. Le cas a été observé ici :
le routeur avait choisi `llama3.3:70b` (42 Go) alors que le moteur n'en
avait que 32.

## 3 quinquies. Quand un quota s'épuise

La plateforme dégrade au lieu de s'interrompre, et la règle qui gouverne
ce repli est **asymétrique** :

| Sens | Verdict | Raison |
|---|---|---|
| `cloud → local` | autorisé | ne fait perdre que de la capacité |
| `anthropic → local` | autorisé | idem, et évite l'interruption |
| `local → cloud` | interdit | les données sortiraient |
| `local → anthropic` | interdit | idem, et engage une dépense |

Un repli est **subi**, jamais choisi. Il ne doit ni élargir l'exposition des
données, ni décider d'une dépense à la place de l'utilisateur. C'est
pourquoi interdire *tout* franchissement de fournisseur — la règle
initiale — était une erreur : elle supprimait précisément le repli utile.

Concrètement, `adaptive-router-cloud` et `adaptive-router-anthropic`
s'achèvent sur `adaptive-router-local`, et chaque chaîne cloud se termine
sur les deux meilleurs modèles locaux.

### L'orchestrateur aussi

Le même principe vaut pour le modèle qui décide. `Start-Claude.ps1` démarre
sur l'abonnement et, si la session se termine sur un motif de quota ou
d'authentification, la relance sur `releve-locale` :

```powershell
.\Start-Claude.ps1                 # abonnement, puis relève si nécessaire
.\Start-Claude.ps1 -Mode Local     # relève directement
```

Deux limites qu'il ne faut pas se cacher : la bascule se fait **entre** deux
sessions et non au milieu de l'une d'elles — un jeton de passerelle remplace
la connexion claude.ai, ce qui ne se décide pas en cours de route ; et le
modèle de relève tourne sur CPU. Il prend la suite, il ne prend pas la place.

Le pont MCP, lui, est identique dans les deux modes : les modèles locaux,
cloud et Claude restent accessibles comme outils.

## 4. Le montage B — filet de sécurité

`Set-ClaudeModel.ps1` ne bascule plus jamais tout seul :

```powershell
.\Set-ClaudeModel.ps1                       # état courant, ne modifie rien
.\Set-ClaudeModel.ps1 -Mode Subscription    # retour à l'abonnement natif
.\Set-ClaudeModel.ps1 -Mode Local           # passerelle + modèle local
.\Set-ClaudeModel.ps1 -Mode Gateway         # passerelle + Claude (FACTURÉ)
```

Chaque mode affiche son implication de facturation. Les variables ne valent
que pour la session PowerShell courante.

Réserve honnête sur le mode `Local` : les fenêtres locales sont à 8K/32K
alors que Claude Code est gourmand en contexte. C'est un mode de dépannage,
pas un remplacement.

---

## 5. Mise à jour automatique

```
  ollama list  ─────┐
                    ├──> nexus_generate.py ──> zones AUTOGEN du YAML
  ollama.com/api/tags ┘         │
                                v
                      nexus_validate.py  ──(invalide)──> arrêt, rien n'est appliqué
                                │
                            (valide)
                                v
                      redémarrage + smoke test
```

Une tâche planifiée exécute ce cycle chaque jour à 04:00 :

```powershell
.\scripts\Register-NexusAutoUpdate.ps1              # installer
.\scripts\Register-NexusAutoUpdate.ps1 -Unregister  # retirer
.\scripts\Update-NexusModels.ps1 -Validate -Restart # à la demande
```

Deux propriétés importantes :

- **Le pool cloud n'est pas figé.** Chaque exécution re-teste réellement les
  droits du compte Ollama Cloud. Les modèles hors palier sont écartés avec
  leur motif et consignés en commentaire dans `cloud_models.txt`. Le jour où
  un palier supérieur est souscrit, ils rejoignent le routeur d'eux-mêmes.
- **L'inventaire local n'a pas de plafond.** Tout modèle présent dans Ollama
  et non déclaré à la main est exposé automatiquement. Un modèle téléchargé
  après coup apparaît à l'exécution suivante.

**Un échec n'est pas l'autre.** La validation distingue deux natures de
refus, et c'est ce qui rend le pool stable :

| Code | Interprétation | Effet |
|---|---|---|
| `402`, `401`, `403`, `404` | droit manquant | le modèle est écarté |
| `429`, `5xx`, timeout | condition passagère | le modèle est **conservé** |

Un quota momentanément épuisé ne prouve rien sur les droits du compte.
Amputer le pool sur la foi d'un incident déjà terminé le priverait de
modèles utilisables jusqu'à la mise à jour suivante. Le fait a été observé :
le pool est passé de 6 à 9 modèles en une heure, sans aucun changement
d'abonnement.

Ce qui reste **curé à la main** : les profils de capacité, les fenêtres de
contexte et l'appartenance aux pools de routage. Être installé ne vaut pas
être éligible au routage automatique.

---

## 6. Garanties vérifiées par les tests

```powershell
python scripts/nexus_test.py                  # tout
python scripts/nexus_test.py --only reverse   # chemins interdits
```

- **FORWARD** — le chemin nominal donne le bon résultat : arithmétique
  vérifiable sur modèles locaux et cloud, cohérence des embeddings, appel
  d'outil, vision sur image réelle, routeurs.
- **REVERSE** — les chemins interdits échouent **proprement et sans emprunter
  d'autre voie** : modèle inexistant non rattrapé par un fallback, clé
  invalide rejetée, embedding refusé sur un modèle de chat, et surtout
  **absence de fuite transitive** — la fermeture transitive du graphe de
  fallback est calculée pour vérifier qu'aucun modèle local n'atteint le
  cloud ou Anthropic, même à plusieurs sauts.
- **POLICY** — les frontières tiennent : le routeur local ne répond jamais
  depuis le cloud, le routeur global ne bascule jamais vers Anthropic, aucun
  secret n'est écrit en dur.
- **CODE** — le code lui-même : règles de nommage des alias, refus d'écrire
  sur un marqueur absent ou non fermé, **idempotence du générateur**,
  conformité MCP, syntaxe des scripts PowerShell.

Le test d'idempotence répond à un défaut réel : l'ancien générateur
réinjectait une ligne de commentaire à chaque exécution et en avait accumulé
sept.
