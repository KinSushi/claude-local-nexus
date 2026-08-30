# Claude-Local-Nexus

![Banner](https://raw.githubusercontent.com/KinSushi/claude-local-nexus/main/images/banner.png)

> **Passerelle d'orchestration LLM hybride — locale, cloud et Anthropic —
> avec garde-fous matériels et politique de confidentialité vérifiée par des tests.**

Claude Code garde son abonnement et orchestre ; les modèles locaux et cloud
deviennent des outils qu'il appelle. Le volume part en local, gratuitement ;
les tokens payants ne financent que le raisonnement. Quand un quota s'épuise,
la plateforme dégrade au lieu de s'interrompre — jusqu'à remplacer
l'orchestrateur lui-même par un modèle local.

---

## Le problème

Router Claude Code vers une passerelle pour arbitrer entre local, cloud et
Claude semble la voie évidente. Elle ne fonctionne pas :

> *« While a gateway credential variable or `apiKeyHelper` is active, a
> developer's claude.ai subscription isn't used : the credential replaces the
> subscription login for that session. That traffic is billed per token. »*
> — Anthropic, [*Other LLM gateways*](https://code.claude.com/docs/en/llm-gateway)

Poser un jeton de passerelle **désactive l'abonnement** et bascule la
facturation au token. Anthropic ne prend par ailleurs pas en charge le
routage de Claude Code vers des modèles non-Claude à travers une passerelle.

## La solution retenue

Prendre le problème par l'autre bout : ne pas router l'orchestrateur, mais
lui donner les modèles **comme outils**.

```
   Claude Code  ·  abonnement claude.ai, natif  ·  orchestre
        │
        │  MCP (stdio, 12 outils, zéro dépendance npm)
        ▼
   nexus-local
        │
        │  HTTP
        ▼
   LiteLLM  127.0.0.1:4000
        │
   ┌────┴──────────────┬──────────────────┐
   ▼                   ▼                  ▼
 LOCAL              OLLAMA CLOUD       ANTHROPIC
 33 alias           19 alias           4 alias
 coût 0             abonnement Ollama  crédits API
 rien ne sort       sort vers          facturé au token
                    ollama.com
```

L'arbitrage coût / confidentialité / capacité redevient une décision
explicite, prise appel par appel — et chaque réponse annonce le modèle
réellement retenu, son plan et son mode de facturation.

---

## Ce qui distingue ce projet

**Rien n'est supposé, tout est mesuré.** La machine est profilée — RAM
offerte au moteur d'inférence, CPU, GPU, disque — et son verdict s'impose
automatiquement à chaque modèle :

| Verdict | Condition | Effet |
|---|---|---|
| `ACCEPT` | poids ≤ 60 % de la mémoire du moteur | éligible au routage automatique |
| `DEGRADED` | ≤ 85 % | adressable, mais hors des pools et des chaînes de repli |
| `REJECT` | > 85 % | jamais généré ni téléchargé automatiquement |

Un modèle trop lourd n'échoue pas franchement : il pagine, et la réponse
n'arrive jamais utilement. Le laisser sélectionnable automatiquement revient
à tirer au sort une réponse qui ne viendra pas.

Le verdict gouverne la génération, les pools, les chaînes de repli et les
téléchargements. Il ne supprime pas rétroactivement une déclaration écrite à
la main avant lui : deux alias hérités subsistent, hors de tout pool et de
toute chaîne, et le validateur les signale à chaque exécution plutôt que de
les taire.

**Le repli est asymétrique, par principe.** Un repli est subi, jamais
choisi : il ne doit ni élargir l'exposition des données, ni engager une
dépense que personne n'a demandée.

| Direction | Verdict |
|---|---|
| `cloud → local`, `anthropic → local` | autorisé — ne coûte que de la capacité |
| `local → cloud`, `local → anthropic` | interdit — les données sortiraient |

**Les graphes de routage sont dérivés, jamais écrits à la main.** Ils sont
donc acycliques par construction et incapables de franchir une frontière de
modalité. Une validation bloquante refuse tout redémarrage sur une
configuration douteuse.

**Le contexte n'a pas de plafond.** Aucun modèle local n'offre 1 M de
contexte ; `nexus_context` l'obtient par découpage et réduction — le plafond
devient le temps, qui en local ne coûte rien.

---

## Démarrage

Prérequis : Docker Desktop, Node 18+, Python 3.10+ avec PyYAML.

```powershell
git clone https://github.com/KinSushi/claude-local-nexus.git
cd claude-local-nexus
Copy-Item .env.example .env      # puis renseigner les clés

.\scripts\Initialize-Nexus.ps1   # prérequis, services, modèles, vérification
```

Puis lancer `claude` et approuver le serveur MCP `nexus-local`.

```powershell
.\scripts\Initialize-Nexus.ps1 -CheckOnly   # diagnostic sans rien modifier
.\rituels\RESUME.ps1                        # état mesuré et sujets ouverts
```

### Reprise

En temps normal, **rien à taper** : une tâche planifiée monte la pile à
l'ouverture de la session Windows, 120 s après — le délai laisse à Docker
Desktop le temps de démarrer. Le compte rendu est écrit dans
`logs/demarrage.log`.

Pour le reste, une commande unique, disponible depuis n'importe quel
répertoire :

```powershell
nexus                       # monte la pile — 46 s mesurées
nexus check                 # local, cloud et les trois routeurs
nexus status                # conformité, sans rien démarrer
nexus mcp                   # branche le projet courant sur le banc
nexus ask "consigne" f1 f2  # interroge le banc gratuit
nexus valide --base main    # valide le projet courant, sans agent ni coût
nexus help                  # rappelle tout ceci
```

Les deux commodités s'installent une fois, et se retirent avec `-Remove` :

```powershell
.\scripts\Install-NexusCommande.ps1     # la commande `nexus`
.\scripts\Register-NexusDemarrage.ps1   # le démarrage automatique
```

Sans rien installer, la forme longue reste valable :
`C:\local-llm-docker\scripts\start.ps1`, appelable de n'importe où, avec
`-Verifier` pour enchaîner la vérification complète et `-Restart` pour
relancer LiteLLM seul.

Le contrôle de conformité passe **avant** le démarrage, et il est bloquant :
une passerelle qui monte devant une configuration fausse accepte toutes les
requêtes et les fait toutes échouer. `start.ps1` rallume aussi le moteur
Ollama, qui vit sur l'hôte et n'a **aucun** démarrage automatique là où
Docker Desktop en a un — sans quoi la pile remonte seule et le moteur reste
éteint.

---

## Les outils exposés à Claude Code

| Famille | Outils |
|---|---|
| **Exécution** | `nexus_ask` (modèle ou profil de tâche), `nexus_route`, `nexus_batch`, `nexus_compare` |
| **Contexte** | `nexus_context`, `nexus_summarize`, `nexus_index_build`, `nexus_search` |
| **Modalité** | `nexus_vision` |
| **Inspection** | `nexus_models`, `nexus_profile`, `nexus_savings` |

`nexus_ask` accepte un **profil** plutôt qu'un modèle — `coding`,
`reasoning`, `rapide`, `multimodal` — et la plateforme retient le premier
candidat réellement exposé **et exécutable**, en privilégiant le local.

---

## Vérification

```powershell
python scripts/nexus_test.py                   # suite complète (~10 min, pile démarrée)
python scripts/nexus_test.py --only reverse    # chemins interdits
.\scripts\Test-NexusSmoke.ps1 -IncludeRouters  # runtime de bout en bout
```

Quatre familles, aux questions volontairement distinctes :

| Famille | Question posée |
|---|---|
| **Forward** | Le chemin nominal produit-il le bon résultat ? |
| **Reverse** | Les chemins interdits échouent-ils **proprement, sans emprunter d'autre voie** ? |
| **Policy** | Les frontières de coût et de confidentialité tiennent-elles ? |
| **Code** | Les scripts de la plateforme se tiennent-ils ? |

Quelques garanties que ces tests établissent : aucune **fuite transitive**
dans la fermeture du graphe de repli ; la preuve de non-sortie par
`x-litellm-model-api-base`, qui dit où la requête est réellement partie ;
l'**idempotence du générateur** ; le refus d'indexer ou de résumer un fichier
susceptible de contenir des secrets ; et le rejet franc d'une image envoyée à
un modèle textuel, plutôt qu'une description inventée.

---

## Mise à jour automatique

```powershell
.\scripts\Update-NexusModels.ps1 -Restart      # cycle complet
.\scripts\Register-NexusAutoUpdate.ps1         # tous les jours à 04:00
```

Découverte → validation des droits réels → régénération → **contrôle
d'intégrité bloquant** → redémarrage → smoke test. LiteLLM n'est jamais
redémarré sur une configuration invalide.

Deux propriétés qui évitent la dérive :

- **Le pool cloud n'est pas figé.** Chaque exécution teste réellement les
  droits du compte. Un `402` écarte un modèle ; un `429` ou un délai dépassé
  ne l'écarte **pas** — un quota momentanément épuisé ne prouve rien sur les
  droits, et amputer le pool sur la foi d'un incident terminé serait faux.
- **L'inventaire local n'a pas de plafond.** Tout modèle présent dans Ollama
  est exposé automatiquement, dans la limite de ce que la machine peut
  exécuter.

Le compte rendu de chaque exécution est écrit dans `logs/update.log`, comme
`logs/demarrage.log` pour le démarrage. Les deux tâches s'exécutent dans la
session ouverte, parce que le client Docker dialogue avec Docker Desktop par
un tube nommé propre à cette session ; si la machine dort à 04:00, la mise à
jour est rattrapée à l'ouverture suivante.

---

## Sauvegarde : ce qui se retélécharge, et ce qui ne se retélécharge pas

```powershell
python scripts/nexus_preserve.py             # audit
python scripts/nexus_preserve.py --backup    # sauvegarde l'irremplaçable
```

La question n'est jamais « est-ce volumineux » mais **« existe-t-il une
source pour le reconstruire »**. Depuis la sortie d'Ollama du périmètre
Docker, ce script n'audite plus que les volumes conteneurisés : sur cette
installation, 10,8 Go se retéléchargent — images Docker, cache Redis —
tandis que **88 Mo n'ont aucune source** : l'historique de dépense, les
sessions, les clés (volume PostgreSQL). L'irremplaçable représente 0,79 %
du volume mesuré, et c'est lui seul qui mérite une sauvegarde. Les poids
Ollama, hors de Docker, se retéléchargent séparément depuis `model_list.txt`.

C'est ce même critère qui décide de l'implantation : PostgreSQL reste
conteneurisé, Ollama en sort.

---

## Structure

```
├── docker-compose.yml         Services : LiteLLM, PostgreSQL, Redis, Ollama (profil)
├── litellm_config.yaml        Configuration — zones AUTOGEN + blocs curés à la main
├── model_list.txt             Inventaire local souhaité
├── cloud_models.txt           Catalogue Ollama Cloud, généré, droits annotés
├── Set-ClaudeModel.ps1        Choix explicite du mode d'exécution
├── Start-Claude.ps1           Lance Claude Code, bascule en relève si le quota s'épuise
├── scripts/                   Génération, validation, tests, migration, sauvegarde
├── tools/nexus-mcp/           Serveur MCP — les modèles comme outils
├── docs/                      Documentation et notes d'architecture
└── rituels/                   État mesuré, sujets ouverts, historique, boussole
```

Les zones délimitées par `# >>> AUTOGEN:<NOM>` sont réécrites à chaque mise
à jour. Les profils de capacité et les fenêtres de contexte restent curés à la
main. L'appartenance aux pools, elle, est **calculée** — à partir de deux
mesures qui ne répondent pas à la même question :

| Relevé | Question | Produit par |
|---|---|---|
| `.nexus/latences.json` | combien de temps avant qu'il *commence* à répondre ? | `nexus_bench.py` |
| `.nexus/epreuves.json` | sait-il réellement faire le travail ? | `nexus_releve.py` |

Un modèle entre au pool s'il tient le budget matériel **et** le seuil de
latence, **ou** s'il a passé les épreuves réelles en entier. Jamais mesuré
vaut jamais promu : **être installé ne vaut pas être éligible au routage
automatique**.

---

## Limites connues

Elles sont documentées plutôt que tues.

- **Hôte CPU.** La latence reste la contrainte dominante. Elle ne se déduit
  pas du nombre de paramètres : sur les 40 modèles locaux mesurés,
  `qwen3-coder:30b` commence à répondre en **2,4 s** et `llava:34b` en
  **3,1 s**, quand `qwen3.5:9b` demande **71 s** et `gemma4:12b` **51 s**.
  Un seuil fondé sur la taille aurait gardé les lents et écarté les rapides ;
  c'est pourquoi le seuil porte sur la mesure.
- **Ce que cette mesure ne dit pas.** Le banc demande seize jetons : il
  chronomètre le démarrage, pas le débit d'une tâche réelle. Le critère est
  donc *nécessaire et non suffisant* — il écarte à coup sûr l'inutilisable,
  il ne prouve pas utilisable ce qu'il laisse passer.
- **Ollama dans Docker est plafonné** par la mémoire allouée à la VM WSL2 —
  sur la machine de référence, la moitié de la RAM lui est inaccessible. La
  sortie du moteur hors du conteneur est outillée et réversible.
- **La relève locale prend la suite, pas la place.** 64K de contexte contre
  1 M, sur CPU.
- **La bascule de l'orchestrateur se fait entre deux sessions**, pas au
  milieu de l'une d'elles : un jeton de passerelle remplace la connexion
  claude.ai, ce qui ne se décide pas en cours de route.

---

## Documentation

| Document | Contenu |
|---|---|
| [Associer local et abonnement](docs/pont-local-abonnement.md) | La contrainte, les trois montages, ce qui est déployé |
| [Notes d'architecture](docs/architecture/README.md) | La cible et les idées où puiser |
| [Set-ClaudeModel](docs/set-claude-model.md) | Basculer délibérément toute une session |
| [État mesuré](rituels/STATE.md) | Généré, jamais saisi à la main |
| [Sujets ouverts](rituels/CHECKLIST_COCKPIT.MD) | Ce qui reste à faire, et pourquoi |

---

## Licence

Copyright © 2026 Sovralys LLC — distribué sous [GNU AGPL v3.0](LICENSE).

Le code est ouvert et vérifiable. En contrepartie, toute personne qui
propose ce logiciel — ou un dérivé — **comme service en réseau** doit en
publier le code source modifié sous la même licence.

Pour un usage sous d'autres conditions, notamment une intégration
propriétaire ou une exploitation commerciale sans obligation de
publication, une licence distincte peut être négociée : **contactez
l'auteur**.

---

**Auteur** — KinSushi · Enzo · Sovralys LLC
