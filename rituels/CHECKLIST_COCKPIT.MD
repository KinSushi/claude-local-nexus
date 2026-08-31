# Cockpit — sujets ouverts

> ## Une règle non mécanisée ne protège pas, même celui qui l'a écrite le matin.
>
> Ce n'est pas une maxime, c'est un constat daté du 30 août 2026, et la preuve
> est la journée elle-même. Le matin, §112.3 était corrigée : une règle
> généralisait **deux relevés à toute une classe**. L'après-midi, la même main
> voyait un modèle résident dans `ollama ps` et écrivait que le moteur **en
> garde un** — l'erreur identique, commise en documentant sa correction, puis
> propagée dans quatre fichiers dont un contrôle qui la répétait à chaque
> exécution.
>
> Trois autres fois le même jour : la confusion chargement/mesure corrigée sur
> un banc puis reproduite sur le suivant ; l'angle mort `bge-m3` corrigé dans
> deux fichiers avant de l'être à sa source ; l'avertissement « ne rien mesurer
> sous charge » violé pendant un téléchargement de 28 Go.
>
> **Aucune n'était une faute de compréhension.** Les règles étaient écrites,
> récentes, du même auteur.
>
> **Conséquence pour toute entrée de cette liste** : un sujet n'est clos que
> lorsqu'un contrôle échoue si la règle est enfreinte. Tant qu'il n'existe
> qu'un paragraphe, le sujet reste `OUVERT` — quelle que soit la qualité du
> paragraphe.


> Tenu à jour pendant la refonte du 29 août 2026. Sert de mémoire externe :
> rien d'important ne doit dépendre du fil de conversation.
>
> Statuts : `FAIT` vérifié par un test · `PRÊT` livré, pas encore exécuté ·
> `OUVERT` à traiter · `DÉCIDÉ` tranché, sans action requise.
>
> **Les correctifs identifiés mais non appliqués sont détaillés dans
> [`RESTE-A-FAIRE.md`](RESTE-A-FAIRE.md)** — 27 entrées, chacune vérifiée par
> exécution lors des audits, avec sa gravité et sa correction.

---

## Session du 30 août 2026 — sujets ouverts

> Trente-cinq commits. Ce qui suit est ce qui **reste**, pas ce qui a été fait :
> l'historique est dans git, le cockpit ne sert qu'à ne rien perdre.

### Bloqué sur une décision qui ne m'appartient pas

| Sujet | État | Ce qui manque |
|---|---|---|
| Réglages du moteur Ollama | `OUVERT` | `OLLAMA_KEEP_ALIVE` non défini → défaut 5 min. Une session parallèle a montré que **les 61,8 s attribuées à `glm-4.7-flash` sont du rechargement disque**, pas de l'inférence. Décision d'environnement hôte. |
| Taille du pool local | `OUVERT` | **Couplé au point ci-dessus.** Borné à 4 modèles alors que le moteur en gardait 3 résidents. Si `OLLAMA_MAX_LOADED_MODELS=1`, il faut 1–2, sinon chaque choix évince. Les deux réglages sont **une** décision. |

### Mesures incomplètes

| Sujet | État | Reste |
|---|---|---|
| Débit (jetons/s) | `OUVERT` | 7 modèles mesurés sur 58. Le tri des pools en dépend. |
| Fidélité des embeddings | `PRÊT` | `mesurer_embedding()` écrite et intégrée, **jamais exécutée** — toutes les tentatives ont expiré sous charge. |
| Coût fixe binaire | `PRÊT` | `mesurer_binaire()` écrite, **jamais exécutée**. C'est elle qui prouvera qu'un modèle local minuscule bat le cloud, sans aller-retour réseau. |
| Qualité de résumé | `OUVERT` | Grandeur manquante pour trancher `DEFAULT_CHAT_MODEL`. Piste retenue : similarité sémantique résumé↔source par embedding local, sans référence humaine. |

### Capacités déclarées, non exploitées

| Sujet | État | Reste |
|---|---|---|
| `tools` | `PRÊT` | 19 modèles sur 54 ne l'ont pas ; 6 sont dans les profils MCP, **annotés mais pas triés dessus**. |
| `thinking` | `OUVERT` | Déclarée par le moteur, lue nulle part. |
| Niveau de qualité | `OUVERT` | 21 modèles sur 36 restent à `tier 0` — jamais déclaré, jamais déduit. |

### Traque mécanique

| Sujet | État | Reste |
|---|---|---|
| 38 constats | `OUVERT` | Classe 1 examinée : **1 vrai défaut sur 9**, corrigé. Restent 21 constats classe 2, 5 classe 3, 3 classe 4. |
| Taux de faux positifs | `DÉCIDÉ` | Classe 1 : 5 faux positifs sur 6 examinés. Trop large, mais conservée — elle a trouvé le défaut réel. Le taux est écrit pour qui la lit. |

### Mécanisé le 30/08 — ce qui ne dépend plus de personne

| Mécanisme | Ce qu'il garantit |
|---|---|
| `nexus_rituel.py` + hook `Stop` | les cinq gestes de fin de tour sont **exécutés**, plus lus |
| Tâche `NexusTraque`, PT10M | traque + cockpit régénérés sans session |
| `nexus_state.py` dans `Update-NexusModels` | le cockpit ne peut plus dater |
| Magasin d'observations | chaque appel MCP devient une mesure |
| `nexus_posterior.py` | les observations deviennent un posterior, qui mesure sans décider |
| Objectif en §0 du contrat | lu avant tout, ne se redemande pas |
| `nexus_garde_shell.py` + hook `PreToolUse` sur Bash | le shell ne peut plus manger un antislash de heredoc Python ni substituer un accent grave entre guillemets doubles |
| `nexus_garde_lecture.py` + hook | on n'écrit plus dans un fichier existant qu'on n'a pas lu |
| `nexus_cablage.py` lancé par le RITUEL | le sixième geste est exécuté, non rappelé : la liste des orphelins ne peut plus s'allonger |
| `nexus_vitrine.py` + tâche `NexusVitrine`, PT6H | le dépôt public ne part que **sain** : sept contrôles bloquants avant tout push |
| `nexus_vitrine.py --epreuve` | le détecteur de secrets est lui-même éprouvé — quatre faux secrets vus, un texte anodin ignoré |
| `test_vitrine` dans `nexus_test.py` | trois régressions gardées : détection, verdict honnête, récupération de configuration |
| `recover_swapped_config` corrigée | une suite tuée ne peut plus laisser sa configuration de test à la place de la vraie |
| `choisir_pool_exact` | le pool est optimal sous budget, non plus glouton |

> **La mesure était vraie et partielle.** Avant de câbler la détection de
> secrets, j'ai mesuré les faux positifs sur les 121 fichiers suivis : zéro
> déclenchement. Le chiffre était exact — et ne couvrait que **trois des quatre
> motifs**. L'affectation `.env`, le seul non testé, a bloqué la première
> publication réelle sur `POSTGRES_PASSWORD`, `LITELLM_MASTER_KEY` et
> `LANGFUSE_HOST` : deux marque-places « REMPLACER… » et une URL publique.
> Trois blocages, zéro secret.
>
> Ce n'est pas bénin : un garde-fou qui bloque toujours finit désactivé, et
> c'est alors le vrai secret qui passe. L'épreuve compte désormais sept cas, et
> les deux nouveaux sont les cas réels — **ce qui ne doit pas déclencher compte
> autant que ce qui doit déclencher**. Un détecteur n'est pas éprouvé par ses
> seules détections.

> Le rituel s'applique à lui-même : à sa première exécution il a refusé de
> clore le tour — quatre fichiers non commités, dont lui-même — puis, une fois
> commité, il a refusé à nouveau parce que le commit rendait ce cockpit
> périmé. C'est exactement ce qu'on attend de lui.

### Fermé depuis — vérifié, plus supposé

| Sujet | Preuve |
|---|---|
| `coding → releve-locale` | 0 occurrence ; le profil commence par `qwen3-coder-30b-local` |
| `releve-locale` sans repli | `{'releve-locale': ['qwen3-coder-30b-local', 'qwen2.5-coder-32b-local']}` |
| `nexus_worktree.py` racine figée | `--racine` existe, défaut = projet courant, vérifié depuis deux répertoires |
| Sentinelle embedding | **cycle bouclé** — la passerelle refuse (HTTP 400), exigence rétablie |
| Sentinelle image | **cycle bouclé** — HTTP 400, exigence rétablie |
| Défaut d'embedding 8 Go | `all-minilm` (46 Mo), marge 0,289 contre 0,204 — index construit en 42 fichiers |
| Température absente du YAML | 49 modèles en portent une ; par profil dans le MCP, journalisée `T=` |
| Configuration écrasée par la suite de tests | cause trouvée : `run_validator_on` échange les fichiers, un `finally` ne survit pas à un `kill`, et la récupération lisait « CONFIG présent » comme « CONFIG sain ». Reproduit puis récupéré : 13 marqueurs, 0 trace de test |
| Pool choisi par glouton | contre-exemple mesuré (budget 20 Go ; 19/10/10 Go pour 22/20/20) : glouton 22, exact 40. 110 033 combinaisons examinées en une fraction de seconde |
| Pool exact appliqué au runtime | LiteLLM relancé ; `adaptive-router-local` répond, `x-litellm-adaptive-router-model: codestral-local`, `api_base` local — non-fuite prouvée par l'en-tête |

> **Un serveur MCP démarré avant un correctif sert l'ancien code.** Node lit
> `server.js` une seule fois. Empreinte du disque au 30/08 : `b8c406f53489`.
> `controle_mcp_a_jour` la rappelle à chaque conformité — une session dont le
> serveur est plus ancien que le dernier commit doit redémarrer, sinon elle
> diagnostique un état qui n'existe plus.

### Briques de l'AIC — architecture reçue le 30/08

| Brique | État |
|---|---|
| Magasin d'observations | **fait** — chaque appel MCP écrit une ligne mesurée |
| Posterior | **fait** — `nexus_posterior.py`, médianes, confiance sous 5 obs. |
| Task Classifier | absent |
| Complexity Estimator | absent |
| Validator / Critic | absent |
| Bandit | absent — attend que le magasin se remplisse |

### Pistes de recherche permanentes — inscrites au contrat le 30/08

| Piste | État |
|---|---|
| Métaheuristiques et hybrides | `OUVERT` — routage, pool et température sont des problèmes de recherche sous contrainte, résolus à la main |
| Inférence adaptative (bandits, bayésien) | `OUVERT` — le magasin est prêt, la politique non |
| Travaux MQL5 sur les métaheuristiques | `OUVERT` — corpus publié et mesuré, méthode à reprendre |

### Pistes ouvertes par l'opérateur, jamais traitées

| Sujet | État | Où en est-ce |
|---|---|---|
| Meta-learner | `OUVERT` | Demandé explicitement. Rien de fait. Le routeur choisit sur des poids figés (`quality 1.0, cost 0.0`) ; §75 décrit une boucle de rétroaction jamais construite. |
| Harnais | `OUVERT` | Demandé explicitement. Rien de fait. |
| AST | `PARTIEL` | `nexus_traque.py` emploie `ast`. Mais aucune analyse AST du code **produit par le banc** avant application — `nexus_patch.py` vérifie la syntaxe, pas la sémantique. |
| Température des modèles locaux | `PARTIEL` | Corrigée côté MCP (0,2). **Aucun modèle du YAML ne fixe de température** — 0 occurrence. Un appel direct à la passerelle tourne toujours au défaut du modèle. |

### Modèles téléchargés, non intégrés

| Sujet | État |
|---|---|
| `command-r`, `sqlcoder`, `codegemma:7b` | `OUVERT` — installés, déclarés au YAML, **jamais mesurés** donc hors pool |
| 9 modèles légers (0,4–1,8 Go) | `OUVERT` — `qwen2.5:0.5b`, `qwen3:0.6b`, `smollm2:360m`, `tinyllama`… installés, **jamais mesurés**. C'est le rôle « réponse binaire » qui reste à prouver. |
| Capacités qu'ils apportent | `OUVERT` — `sqlcoder` (SQL) et `command-r` (outils) ne sont dans **aucun** profil MCP |

### Défauts constatés, non corrigés

| Sujet | État | Fait mesuré |
|---|---|---|
| `nexus_index_build` expire | `OUVERT` | 600 s sur `scripts/` seul. Défaut : `qwen3-embedding-8b-local`, 8 Go pour des vecteurs, alors qu'`all-minilm` fait 46 Mo. |
| `nexus_search` expire | `OUVERT` | 600 s. Même cause probable. |
| `releve-locale` expire dans le MCP | `OUVERT` | HTTP 408 après 180 s sur un `nexus_ask` profil coding. |
| Tâches de fond tuées | `OUVERT` | Trois fois de suite. Cause non identifiée — limite système ou harnais. Contourné en mesurant au premier plan, jamais résolu. |
| `nexus_essaim` : 3 échecs sur 6 | `OUVERT` | Palier porté à 16384 jetons, **jamais revérifié** depuis. |
| Biais systématique du validateur | `OUVERT` | La double passe protège de la variance, **pas du biais de format** — les deux passes concordaient sur le faux positif. |
| `qwen3-vl-32b` hors classement | `OUVERT` | Absent des entrées classées. Écarté par le verdict matériel ? Non vérifié. |
| Sentinelles image et embedding | `OUVERT` | Posées, **jamais vues passer** dans une suite complète non interrompue. |
| Asymétrie des pools | `DÉCIDÉ` | Cloud 19 candidats, local 4. Justifié — aucun poids chargé côté cloud — et documenté dans le code. |

### Règles du 30/08 encore OUVERTES — celles qu'aucun contrôle ne garde

Deux des quatre règles inscrites ici le matin ont été fermées depuis et ont
donc quitté ce tableau : elles figurent au point d'étape, avec leur preuve.
Les y laisser faisait annoncer par la reprise de session, à chaque
démarrage, des sujets clos comme ouverts — un tableau de bord qui ment sur
son propre état est pire qu'un tableau de bord absent.

Le critère en tête de ce document s'applique à elles comme aux autres : tant
qu'aucun contrôle n'échoue quand la règle est enfreinte, le sujet reste ouvert,
quelle que soit la qualité du paragraphe.

| Règle | Où elle est écrite | Ce qui manque pour la fermer |
|---|---|---|
| Chaque worker dans un **worktree isolé** | contrat §0.4 | l'essaim écrit désormais hors du dépôt, à côté de `.nexus-arbres` — mais c'est un répertoire, **pas un worktree git**. Le dire plutôt que de laisser croire la case cochée |

> **Où la règle est enfreinte, mesuré le 30/08.** En cherchant à mécaniser
> §0.4, le défaut trouvé n'était pas celui attendu. Le pont MCP, lui, est
> borné : `insideRepo()` refuse tout chemin hors de `WORK_ROOT`, et
> `NEXUS_WORK_ROOT` permet de le pointer sur un worktree — la voie propre
> existe, rien ne l'impose.
>
> C'est `nexus_essaim.py` qui enfreint la règle : il travaille sur **la cible
> elle-même**, sauvegarde en `.nexus/backup-*.bak`, laisse le banc réécrire,
> puis restaure. Et sa racine était fausse : `racine_depot()` rendait
> `scripts/` en se nommant « racine du dépôt ». Elle servait à deux fins
> contradictoires — localiser `.nexus` (racine) et `nexus_patch.py`
> (`scripts`) — donc chaque appel était juste pour son besoin et faux pour
> l'autre, et aucun n'échouait. **Quarante sauvegardes** avaient atterri dans
> `scripts/.nexus/`, invisibles à qui cherchait à la racine.
>
> Rien n'a fuité, vérifié et non supposé : le motif `.nexus/` du .gitignore
> n'a pas de barre oblique initiale, donc s'applique à tous les niveaux
> (`git check-ignore -v`, `git ls-files` vide). Aucune cible n'a été laissée
> abîmée : l'arbre était propre. Les quarante fichiers ne sont **pas**
> supprimés — ce sont des données, et leur sort appartient à l'opérateur.
>
> Un reste est désormais un signal : `controle_travail_sur_original` le voit
> aux deux emplacements, en AVERTISSEMENT — bloquer punirait l'opérateur venu
> nettoyer.
>
> **Puis l'écart a été supprimé, pas seulement rendu visible.** Le cycle est
> renversé : copier, corriger la copie, promouvoir après vérification de
> syntaxe. La différence ne se voit pas quand tout va bien — dans les deux
> ordres, un cycle réussi laisse le même fichier. Elle se voit quand rien ne
> va : un processus tué laissait l'original **écrasé** par une sortie de
> modèle jamais relue ; il le laisse désormais **intact**, n'ayant jamais été
> ouvert en écriture.
>
> Le backup n'est pas supprimé mais **réduit à ce qu'il protège vraiment** :
> la fenêtre de promotion. Le `finally` restaurait auparavant dans tous les
> cas non gérés — ce qui, après renversement, réécrirait par-dessus un fichier
> sain. Une protection au mauvais endroit devient une régression.
| Préserver le contexte de l'orchestrateur | contrat §0.4 | mesurable (jetons facturés par jeton délégué) mais non mesuré par tour |

### Inspiré des dépôts voisins le 30/08 — repris, et ce qui reste à reprendre

**Ce projet est PRIORITAIRE sur les mécanismes des autres dépôts.** Il n'en
est pas le suiveur : il en est la source. Les plus-values construites ici —
gardes, cliquets, épreuves, contrôles — ont vocation à **redescendre** vers
les dépôts voisins, jamais l'inverse. Quand un mécanisme d'ici et un
mécanisme d'ailleurs se contredisent, c'est celui d'ici qui tranche.

S'en inspirer n'est pas interdit — **au contraire**, c'est attendu : ce qui a
déjà été payé une fois ne doit pas l'être deux. Mais on emprunte une idée, on
ne s'y subordonne pas. Un mécanisme repris est réécrit selon les règles de ce
dépôt, éprouvé selon ses épreuves, et n'entre que s'il ne double ni ne
concurrence ce qui existe déjà ici.

Source : `D:\SAS\sovereign-ai-system1.104\sovereign-ai-system` (hooks et
ACL) et `D:\EA MT5 PYTHON RENTABLE ROBUSTE`. **Lecture seule** : on s'en
inspire, on n'y touche pas.

| Mécanisme SAS | État ici |
|---|---|
| hook `SessionStart` → reprise imprimée au démarrage | **repris** : `nexus_reprise.py`, tout dérivé, ne lance rien de long, n'échoue jamais |
| ACL `deny` sur secrets et clés (101 règles là-bas) | **repris**, réduit à ce dépôt : 11 refus de lecture |
| ACL `ask` sur les gestes irréversibles | **repris** : 15 gestes (push, reset --hard, clean, docker down -v, volume rm, prune, rm -rf, ollama rm) |
| `garde_heredoc_echappements.py` | **repris** → `nexus_garde_shell.py`, 10/10 dans les deux sens |
| `hook_lecture_avant_ecriture.py` | **repris** → `nexus_garde_lecture.py`, 7/7 |
| `wiring_check.py` (cliquet de câblage) | **repris** → `nexus_cablage.py`, cliquet par nom, éprouvé |
| `garde_perimetre_agent.py` | à reprendre — ACL de périmètre par agent |
| `hook_anti_derive_pollution.py` | à reprendre — refuse les fichiers hors périmètre |
| `recolter_rapports_agents.py --hook` | **à reprendre** — récolte automatique des worktrees des workers en fin de tour |

> **Défaut vécu le jour même où il était inscrit « à reprendre ».** Le message
> de commit du garde d'édition est passé par un heredoc shell : deux passages
> ont été VIDÉS par la substitution des accents graves, amputant le commit de
> ses noms techniques. Réparé par fichier. La leçon est celle du contrat
> §106.1 : la règle était écrite, récente, et son auteur l'a enfreinte dans
> l'heure. Seul un contrôle protège.

> **Non-concurrence, règle posée le 30/08.** Un mécanisme neuf ne doit ni
> doubler ni concurrencer les automatismes déjà en place. `NexusTraque`
> (PT10M) régénère le cockpit, `NexusVitrine` (PT6H) commite et pousse : un
> hook qui écrirait ces mêmes cibles se marcherait dessus avec eux.
> `nexus_garde_edition.py` est écrit sous cette contrainte — il **n'écrit
> aucun fichier**, il lit et compile en mémoire.
>
> **Une porte ne mute pas l'arbre qu'elle juge.** Principe rapporté par
> l'instance voisine, qui a mesuré 88 répertoires `__pycache__` créés par sa
> propre porte. Vérifié ici : `py_compile` n'est employé nulle part, les
> `__pycache__` sont gitignorés, et `nexus_cablage.py` ne modifie aucun
> fichier suivi pendant son exécution (mesuré avant/après).

> **Limite du garde de lecture, écrite plutôt que tue.** `nexus_garde_lecture.py`
> ne voit que les outils passant par le hook. Les correctifs de cette session
> sont appliqués par des scripts Python lancés depuis le shell : ils
> **échappent** au garde. Ce n'est pas un défaut du mécanisme, c'est sa portée
> — et s'en croire protégé serait la vraie faute.

### Ce que l'usage a appris — et qu'aucune relecture n'aurait trouvé

Inscrit au contrat §0 le 30/08 : se servir de la plateforme est en soi une
source d'améliorations, et la plus riche. Un audit lit le code, l'usage
l'exerce. Quatre défauts ce jour, tous venus de l'usage, **aucun** d'une
relecture :

| Défaut | Comment il s'est révélé |
|---|---|
| Le détecteur de secrets bloquait trois marque-places et zéro secret | en lançant la toute première publication réelle |
| Le garde d'édition était **structurellement aveugle** sous Windows | en lui donnant délibérément un fichier cassé ; invisible autrement, car silencieux dans les deux cas |
| Le contrôle de câblage prenait une mention en commentaire pour un appel — puis son remède produisait 18 faux négatifs | en le lançant sur ce dépôt plutôt qu'en raisonnant dessus |
| Le shell mutilait quatre commandes, dont un message de commit | en relisant ce qui avait réellement été commité |

> **Un jet du banc peut détruire ce qui marchait.** Le garde shell avait passé
> huit cas sur huit. Un second appel, ne demandant que trois *ajouts* à logique
> constante, a rendu un script qui ne lisait plus le JSON du hook, refusait
> tout heredoc quoté portant un antislash, et sortait en code 1 sur stderr au
> lieu d'imprimer un refus. Demander une retouche coûte parfois l'acquis :
> l'épreuve précède l'intégration, et l'arbitrage garde le dernier mot.

### Ce que la suite complète a trouvé — un défaut en masquait un autre

Le sujet « suite complète après tous les changements » était ouvert depuis le
matin. Jouée une fois, elle a **payé immédiatement**, et deux fois :

| Défaut | Portée réelle |
|---|---|
| `nexus_ruche.py` employait `nexus_agent.racine_travail()` **sans jamais importer le module** | toute exécution sans `--racine` levait `NameError`. Ni `sys.path` posé, ni import : le chemin par défaut était mort |
| Le test substituait `decouvrir_cibles` par une `lambda:` sans argument, alors que la vraie signature prend la racine | défaut du TEST, invisible tant que le premier plantait avant lui |

> **Le premier masquait le second.** C'est l'argument le plus solide pour
> jouer la suite ENTIÈRE plutôt que la famille qu'on vient de toucher : un
> plantage précoce protège les défauts situés derrière lui, et les rend
> indiscernables du code sain.

> **Vérification gratuite obtenue au passage.** La première exécution s'est
> terminée par une exception non rattrapée — exactement le cas qui, ce matin,
> laissait `litellm_config.yaml` remplacé par la configuration de test.
> Constaté après : 26 marqueurs AUTOGEN, aucun `.testswap` résiduel. La
> correction de `recover_swapped_config` tient en conditions réelles, et non
> seulement sur l'accident reproduit à la main.

### CE DONT JE DISPOSE — inventaire mesuré le 30/08, jamais supposé

Comptés par `find`, dans
`D:\SAS\sovereign-ai-system\v1.104\sovereign-ai-system`. **Plus de 33 000
fichiers** de documentation et de bibliothèques sont là, à disposition, et
n'ont jamais servi une seule fois à ce projet.

| Corpus | Volume | Nature dominante |
|---|---|---|
| `_REFERENCE_LIVRES` | **12 793** fichiers | 12 749 `.txt` — les livres |
| `_REFERENCE_PYTHON_LIBS` | **11 034** fichiers | 10 161 `.md` sous `python_libs_docs` — documentation de bibliothèques Python |
| `_REFERENCE_CODE_LIVRES` | **5 381** fichiers | le code source accompagnant les livres |
| `_REFERENCE_NOYAU_EXTERNE` | 1 538 fichiers | noyau externe |
| `_REFERENCE_MQL5_KB` | 680 fichiers | base MQL5 — la piste métaheuristiques du contrat §0 |
| `_REFERENCE_SHELL_DOCS` | **624** fichiers | 318 `.md` + 302 `.txt` — bash et shell |
| `_REFERENCE_JEDHA` | 612 fichiers | cours |
| `_REFERENCE_DOCS_PROJET` | 490 fichiers | documentation de projet |
| `_REFERENCE_LECONS` | 109 fichiers | leçons tirées, déjà payées là-bas |

**COPIES UNIQUEMENT.** On prend une copie de ce dont on a besoin ; jamais une
lecture en place, jamais une dépendance à leur chemin. Une dépendance au
chemin d'un voisin casse le jour où ce dépôt bouge, et travailler en place
risque d'écrire là où rien ne doit l'être. Même règle que §0.4 pour les
workers : une copie, jamais la source.

**Ce que cela change concrètement.** Les documentations shell et Python
répondent directement à des défauts déjà payés ici — quatre commandes
mutilées par le shell en une journée, une racine relative prise pour absolue
trois fois, `py_compile` structurellement aveugle sous Windows. Ces réponses
existent, écrites, à quelques répertoires d'ici. Les ignorer revient à
repayer ce qui est déjà acquis.

**Et le reste de l'environnement, également disponible et sous-employé** :

| Ressource | État |
|---|---|
| Banc local — 71 modèles mesurés | employé, mais le débit n'est mesuré que sur 7 d'entre eux |
| Banc cloud Ollama — abonnement payé | employé ; parallélise sans contention, 2–3 s de réponse |
| Douze outils voisins repérés (ci-dessous) | aucun évalué au-delà des cinq repris |
| Internet, autorisé par le contrat §0 | jamais employé cette session |
| Espace disque `C:` — **320 Go libres** sur 930 | sous-exploité : place pour d'autres modèles, sous réserve du verdict matériel |
| 54 modèles locaux, 434 Go installés | 71 mesurés en latence, **7 seulement en débit** |
| RAM 66,2 Go, aucun offload GPU | c'est ELLE qui décide de ce qui tourne, pas le disque |

### Outils voisins repérés, non encore évalués — par ordre de rendement

Relevé le 30/08 dans `D:\SAS\sovereign-ai-system\v1.104\sovereign-ai-system`.
Les intitulés viennent de leurs propres docstrings, **non d'une supposition**.
Chacun doit d'abord passer le test de non-empiètement : il n'entre que s'il ne
double ni ne concurrence ce qui existe ici (contrat §0).

| Outil | Ce qu'il fait, d'après lui-même | Pourquoi il nous intéresse |
|---|---|---|
| `import_smoke.py` (114 l.) | importe chaque script de `scripts/` et échoue si l'un ne s'importe pas | **le plus rentable** : nous avons 43 scripts, et un import cassé ne se voit qu'à l'exécution. À rapprocher du `NameError` de `nexus_ruche.py`, resté invisible jusqu'à la suite complète |
| `avec_verrou.py` / `verrou_machine.py` | verrou machine inter-projets | **repris** → `nexus_verrou_machine.py`, copie conforme octet pour octet, nom du mutex gardé par `controle_verrou_machine` (éprouvé 5/5), et **pris par le banc** (éprouvé 3/3) |
| `garde_cardinal.py` (279 l.) | « un témoin ne doit pas sceller une croyance par un COMPTE » | nos épreuves affirment des comptes (`8/8`, `10/10`, `26 marqueurs`). Un compte survit à la réfutation de ce qu'il compte |
| `compile_tout.py` (213 l.) | compile l'arbre en une commande, et **distingue COMPILER d'IMPORTER** | complète `nexus_garde_edition.py`, qui ne voit qu'un fichier à la fois |
| `verdict_gate.py` (293 l.) | rend un verdict sur un journal, et **refuse de conclure quand il ne peut pas** | doctrine que nous appliquons déjà (`IGNORE` ≠ `OK`), mécanisée là-bas |
| `garde_append_only.py` (300 l.) | le contenu commité doit rester un **préfixe** du contenu courant | attraperait une réécriture destructrice d'un fichier de doctrine |
| `garde_chemins_bruts.py` (298 l.) | une chaîne en rôle de CHEMIN doit être brute si elle porte un antislash | même famille que le garde des heredocs, déjà repris |
| `mypy_ratchet.py` (190 l.) | cliquet de typage, « mécanique, parce qu'il ne l'était pas » | même forme que notre cliquet de câblage |
| `token_meter.py` (108 l.) | mesure la consommation de jetons par agent | recoupe `nexus_savings.py` : à comparer avant de reprendre |
| `declarer_les_gardes.py` (300 l.) | déclare les gardes dans `.claude/settings.json` | nos hooks sont écrits à la main ; ceci les dériverait |
| `garde_tracabilite.py`, `garde_reprise_coherente.py` | traçabilité, cohérence des points de reprise | à évaluer après les précédents |

> **Un compte rendu trompeur trompe aussi celui qui l'écrit.** De cet
> affichage j'ai conclu « `--modele` ne filtre pas », et je l'ai inscrit ici
> comme un fait. C'était faux, et il a fallu comparer les valeurs affichées
> au fichier de relevé pour le voir. Le code portait pourtant déjà la règle,
> écrite pour un autre mode : *« un compte rendu qui exagère ce qu'il a fait
> est une forme de mensonge, même involontaire »*. Elle valait ici aussi.
>
> Une entrée de checklist se vérifie comme un correctif. Celle-ci est barrée
> plutôt que supprimée : effacer une erreur d'analyse fait perdre ce qu'elle
> enseigne.

> **Une fausse accusation, écartée par la mesure.** Après avoir câblé le
> verrou, le banc rendait des échecs en série et semblait ne plus filtrer :
> j'ai cru à ma régression. La version restaurée depuis `HEAD`, **sans** mes
> changements, se comportait à l'identique — ce n'était donc pas moi.
> Restaurer avant d'accuser vaut mieux que corriger au juge, et coûte une
> commande.

> **Deux refusés, et c'est un résultat.** `garde_perimetre_agent.py`
> empiéterait sur `nexus_garde_agent.py` — même hook `PreToolUse: Agent`,
> deux gardes qui se marcheraient dessus. `hook_anti_derive_pollution.py`
> recoupe `nexus_traque.py`, qui analyse déjà le dépôt toutes les dix
> minutes. Le projet primant, c'est le nôtre qu'on étendrait le jour où le
> besoin se confirme.

### Sujets ouverts consolidés — l'état au 30/08 au soir

Tout ce qui reste, en un seul endroit. Rappel du critère en tête de document :
un sujet ne se clôt que lorsqu'un **contrôle échoue** si la règle est
enfreinte. Un paragraphe ne ferme rien.

| Sujet | Pourquoi il reste ouvert | Prochain geste |
|---|---|---|
| **33 000 fichiers de documentation et bibliothèques** jamais exploités | repérés et mesurés ce soir, aucune copie encore prise | copier le corpus shell (624 fichiers) et Python (11 034) qui répondent aux défauts déjà payés |
| Les livres — 12 793 fichiers, plus 5 381 de code associé | jamais lus par ce projet | indexer une copie via `nexus_index_build`, puis interroger par `nexus_search` |
| Douze outils voisins repérés | aucun évalué au-delà des cinq repris | `import_smoke` fait ; `avec_verrou` ensuite — trois dépôts tournent sur cette machine sans se connaître |
| Chaque worker dans un **worktree isolé** | la copie est hors du dépôt, mais c'est un répertoire, pas un worktree git | dire ou faire, pas cocher |
| Préserver le contexte de l'orchestrateur | mesurable par `nexus_savings`, non mesuré par tour | un contrôle de rituel comparant jetons facturés et délégués |
| `nexus_test_outillage.py` orphelin | seul script que personne n'appelle | le câbler ou le retirer |
| 40 sauvegardes résiduelles dans `scripts/.nexus/` | ce sont des **données** | la suppression appartient à l'opérateur, pas à l'agent |
| `import subprocess` en portée locale (`nexus_ruche.py:205`) | même famille qu'un défaut déjà payé | à corriger seul, sans le mêler à un autre sujet |
| ~~`--modele` ne filtre pas~~ — **inscription FAUSSE, corrigée** | le filtre marchait ; c'est l'AFFICHAGE qui trompait. Le banc mesurait bien le seul modèle demandé puis imprimait les 71 lignes du relevé stocké. Prouvé en comparant : « phi3-mini-local 2.518 » était exactement le `latence_ms=2518` déjà enregistré, pas une mesure du jour | **corrigé** : la restriction d'affichage portait sur `--manquants` seul, elle porte désormais sur tout sous-ensemble demandé |
| Les modèles **cloud** échouent en série | **DIAGNOSTIQUÉ le 30/08 au soir : `429 Too Many Requests` sur `https://ollama.com/api/chat`, lu dans les journaux de la passerelle.** Ni réseau ni configuration : une limite de débit | reste à borner la concurrence cloud, comme le local l'est déjà |
| 9 appels Anthropic sur 9 échouent | **le repli masque la cause** : la lire exige de le désactiver temporairement | à faire hors de toute exécution de suite |
| `Start-Claude.ps1` jamais joué de bout en bout | le lancer démarre une session Claude | ne se teste pas à la légère |
| Débit mesuré sur 7 modèles sur 71 | le banc n'a jamais tourné en entier | `nexus_bench.py --debit`, machine au repos |
| Coût binaire mesuré sur aucun modèle | jamais lancé | idem |
| Briques AIC restantes — classifieur, estimateur, critique, bandit | architecture reçue, non construite | le posterior existe et attend des observations |
| Métaheuristiques, bandits, MQL5 | pistes permanentes du contrat §0 | `_REFERENCE_MQL5_KB`, 680 fichiers, à portée |
| Internet, autorisé | jamais employé | vérifier une doctrine contre la documentation d'éditeur |

### Sujets neufs, ouverts le 30/08 au soir

| Sujet | Pourquoi il reste ouvert |
|---|---|
| Documentation et bibliothèques des dépôts voisins | ressource massive, jamais exploitée. Règle posée : **copies uniquement**, jamais de lecture en place ni de dépendance à leur chemin |
| `nexus_test_outillage.py` orphelin | seul script que personne n'appelle. Le cliquet l'a figé dans la référence : il ne peut plus être rejoint, mais il n'est pas résolu |
| 40 sauvegardes résiduelles dans `scripts/.nexus/` | signalées par `controle_travail_sur_original`. Ce sont des **données** : leur suppression appartient à l'opérateur, pas à l'agent |
| `import subprocess` en portée locale (`nexus_ruche.py:205`) | même famille que le défaut déjà payé ce jour ; non corrigé pour ne pas mêler deux sujets dans un correctif |

> **Trois défauts de l'extracteur de sujets, corrigés en série** — et chacun
> trouvé en *lisant sa sortie*, jamais en relisant son code. Il prenait le
> séparateur `| --- |` pour un préfixe (zéro sujet extrait, en silence) ; puis
> le numéro de la première colonne pour le sujet (« # », « 1.1 ») ; puis, sous
> un critère de LONGUEUR, il sautait « AST » et retenait le statut à sa place.
> Le bon critère n'était pas la forme mais le sens : ni un numéro, ni un
> intitulé de colonne.

### Trouvé en se servant du pont, le 30/08 — cinq défauts, cinq contrôles

| Sujet | Statut | Ce qui le garde |
|---|---|---|
| `nexus-local` déclaré dans **deux portées** | `FAIT` | `controle_mcp_double_portee` dans `nexus_conformite.py` |
| `nexus_agent.py` refusait un fichier sans nommer l'issue | `FAIT` | le refus cite désormais `--racine` ; prouvé en le rejouant |
| `cockpit_frais` était insatisfiable dans le tour qu'il prescrit | `FAIT` | trois cas joués sur un dépôt jetable : ensemble, périmé, retouché |
| Le garde de lecture refusait un fichier **créé par la session** | `FAIT` | deux cas dans `test_garde_lecture` : création retenue, autre session refusée |
| Aucun garde sur l'import en portée dangereuse | `FAIT` | `nexus_portee_import.py`, `controle_portee_import`, six cas dans `--only portee` |

> **Ni l'un ni l'autre ne vient d'un audit.** Le premier est apparu dans la
> sortie de `/mcp` au démarrage de la session : le serveur était déclaré en
> portée *utilisateur* (chemin absolu, posé à la main) **et** en portée projet
> (`${CLAUDE_PROJECT_DIR:-.}`, écrit par `nexus mcp`). Claude Code range ses
> jetons par point d'entrée : deux écritures du même chemin sont pour lui deux
> serveurs, et l'opérateur ignore laquelle le sert.
>
> **Le premier jet du contrôle ne détectait pas le défaut qui l'avait fait
> naître.** Il résolvait `${CLAUDE_PROJECT_DIR}` *avant* de comparer, concluait
> « même fichier, doublon inoffensif », et se taisait. Comparer les chemins
> résolus répond à une question que personne ne pose ; c'est le texte déclaré
> qu'il fallait comparer, puisque c'est lui que Claude Code indexe. L'épreuve
> positive a été faite **avant** la correction de la cause, précisément pour
> que le silence d'après prouve quelque chose.
>
> L'entrée en portée utilisateur a été retirée, non par préférence mais sur
> constat : les deux dépôts voisins possèdent déjà leur propre `.mcp.json`
> valide, vérifié point d'entrée par point d'entrée. Elle ne couvrait donc
> rien qui ne le fût déjà, et `nexus mcp` mécanise ce qu'elle faisait à la
> main.
>
> Le second est né du même tour : le banc a refusé le fichier de contexte que
> l'orchestrateur lui tendait, parce que le répertoire de brouillon documenté
> est hors de la racine de travail. **La garde a raison** — elle empêche qu'un
> fichier quelconque de la machine parte vers ollama.com — et elle n'a pas été
> touchée. Ce qui manquait était l'issue : `--racine` existait, le message ne
> le disait pas. Une garde qui refuse sans dire par où passer se fait
> contourner, ou renoncer.
>
> **Le troisième défaut est celui du rituel lui-même**, et il n'est apparu
> qu'en le jouant après les deux premières corrections. `cockpit_frais`
> comparait le **mtime du fichier** cockpit à la **date du commit** du dernier
> changement de code : deux horloges différentes. Or le rituel prescrit
> d'écrire le cockpit *puis* de commiter — donc, chaque fois que cockpit et
> code partent dans le même commit, le fichier est nécessairement antérieur à
> ce commit. Mesuré ce jour : commit du code 17:27:47, commit du cockpit
> 17:27:47 — le même — et mtime 17:26:37, soit `MANQUE` sur un cockpit
> parfaitement à jour. **Le contrôle rendait impossible le tour qu'il
> exigeait**, et la seule façon de le contenter était de commiter deux fois.
>
> Corrigé par un second critère tiré de la seule horloge de git : le commit du
> cockpit au moins aussi récent que celui du code. Le premier critère est
> conservé pour l'édition pas encore commitée. Trois cas joués sur un dépôt
> jetable — partis ensemble, code commité seul, cockpit retouché — et le cas
> périmé rend toujours `MANQUE` : la correction n'a pas acheté le silence en
> désarmant le contrôle.
>
> **Le quatrième défaut a mordu l'orchestrateur lui-même**, à l'instant où il
> corrigeait un script d'extraction : le garde « lire avant d'écrire » a refusé
> un fichier que la session venait pourtant d'**écrire**, au motif qu'elle en
> ignorerait le contenu. Il n'alimentait sa mémoire que sur `Read`, jamais sur
> une création. Le correctif n'enregistre que l'écriture sur un fichier
> **inexistant**, et c'est ce qui le rend sûr : si l'écriture échoue, le
> fichier reste absent, donc la suivante est une création, autorisée de toute
> façon — aucun contenu non vu ne peut devenir écrasable. Un second cas de test
> vérifie qu'une *autre* session reste refusée : sans lui, le correctif aurait
> pu transformer la mémoire en passoire sans que rien ne le dise.
>
> **Le cinquième n'était pas un défaut, et c'est le résultat.** Le cockpit
> portait depuis la veille « `import subprocess` en portée locale
> (`nexus_ruche.py:205`) ». Vérifié dans le code réel : l'import est local,
> mais l'usage l'est aussi — cela fonctionne. Le corriger n'aurait protégé de
> rien. Une règle « pas d'import local » aurait été pire : le dépôt en compte
> une trentaine, tous légitimes (import paresseux, dépendance optionnelle,
> fixture de test), et un contrôle qui les signalerait serait désarmé le jour
> même.
>
> Ce qui mérite un garde est la forme **dangereuse**, voisine et invisible : un
> nom importé dans une fonction et employé dans une **autre**. Le module
> s'importe alors proprement — `controle_imports`, qui charge les modules, ne
> peut rien voir — et le `NameError` tombe plus tard, sur le seul chemin qui
> emploie le nom. `nexus_portee_import.py` rend `OK` sur le dépôt : le silence
> ne prouvant rien, six cas fabriqués le complètent, un dangereux et cinq
> légitimes, un par règle de non-signalement.



### Charge massive sur le pont MCP, 30/08 — ce que l'usage a montré

> Workflow `wf_b08fc212-efb`, **terminé** : 60 agents, 34 appels réels, 22
> minutes. Ce qui suit a été **vérifié dans le code réel**, jamais cru sur
> parole — et il a fallu le faire, car la synthèse du banc était fausse.

| Trouvaille | Statut | Ce qui la garde |
|---|---|---|
| Le plan local n'avait **aucune borne de concurrence** | `FAIT` | sémaphore FIFO dans `server.js`, `--only semaphore`, 7 cas dont une contre-épreuve |
| La synthèse a conclu « sain » sur 19 échecs | `OUVERT` | défaut de MON harnais, pas du dépôt : voir plus bas |
| Un corps vidé par `sansRaisonnement()` était rendu **sans explication** | `FAIT` | `mentionsReponse()`, `--only mentions`, 7 cas dont une contre-épreuve |
| 12 refus du pont ne nomment pas l'issue (vague 2) | `OUVERT` | à vérifier un par un dans `server.js` avant d'y croire |

> **LE RÉSULTAT CENTRAL, et il était caché sous une synthèse rassurante.**
> Le banc a rendu « RIEN n'a cassé », « 34/34, 100 % de complétude », « état
> opérationnel : sain ». Les compteurs calculés sur les mêmes données disent
> **19 échecs sur 34**. La synthèse donnait en outre trois nombres différents
> pour une même quantité — 20 dans son texte, 30 dans son propre tableau, 25
> dans les compteurs.
>
> Ses *faits* étaient pourtant exacts : `DEFAULT_TIMEOUT_MS` est bien à
> `server.js:135`, et `litellm_config.yaml:1847` porte bien
> `request_timeout: 180`. Vérifiés tous les deux. **C'est son verdict qui
> était faux**, par un sophisme : un délai configuré à 600 s ne rend pas sain
> le fait de l'atteindre. §112.4 disait « l'analyse est un signal, jamais une
> preuve » ; ici l'analyse était juste et la *conclusion* inventée, ce qui est
> une variante plus dangereuse, parce qu'elle résiste à la vérification des
> citations.
>
> **La répartition des échecs, elle, ne laisse aucun doute :**
>
> | plan | réussites | échecs |
> |---|---|---|
> | local | 8 | **14** — toutes des expirations à 600 s |
> | cloud | 7 | **0** |
>
> Ont expiré : un résumé de `README.md` (15 Ko), une extraction dite
> *triviale* via `nexus_route`, deux `nexus_context`. Ce n'est donc pas la
> taille des tâches qui a décidé, c'est le **nombre d'inférences
> concurrentes** sur un hôte à mémoire partagée dont le moteur ne garde que
> trois modèles résidents.
>
> **La règle existait déjà — en paragraphe.** `nexus_batch` est séquentiel à
> dessein, et sa description dit exactement pourquoi : « deux inférences
> simultanées se disputent la même bande passante mémoire et finissent plus
> tard que si elles s'étaient suivies ». Mais cette discipline ne valait qu'à
> l'INTÉRIEUR d'un appel. Rien n'empêchait dix appelants de faire précisément
> ce que `nexus_batch` refuse. C'est §0.2.1 dans sa forme la plus pure : une
> règle écrite, juste, et qui ne protégeait rien.
>
> Le sémaphore ne borne **que** le plan local : le cloud a rendu 7 sur 7 en
> parallèle, et le brider gâcherait l'abonnement payé pour cela. Le plan
> inconnu n'est pas sérialisé non plus — le coût d'un faux négatif est une
> contention, celui d'un faux positif une lenteur imposée au cloud sur une
> simple lacune de table.
>
> **Deux défauts arbitrés dans le jet du banc.** Le sémaphore prenait son
> jeton APRÈS l'`await` : deux appels partis dans le même tick voyaient tous
> deux zéro jeton pris et passaient ensemble — inopérant précisément sous la
> charge qui le motive. La contre-épreuve le chiffre : la variante fautive
> atteint **20 appels simultanés** là où la corrigée reste à 1. Et `depart`
> étant pris avant l'attente, `observer()` aurait compté le temps de file
> dans `duree_ms` et `debit_jps`, faussant les relevés mêmes dont ce dépôt
> tire sa doctrine ; l'attente est mesurée à part et rendue visible.
>
> **Le corps vide, corrigé.** `chat()` détenait déjà de quoi expliquer le vide
> — `tokens` et `tronquee` — et aucun appelant ne s'en servait pour cela.
> Vérifié ligne à ligne plutôt que sur parole : le banc annonçait *trois*
> appelants portant la mention de troncature, il y en avait **deux**
> (`nexus_ask`, `nexus_vision`) ; `nexus_route` et `nexus_compare`
> n'annonçaient rien. La règle vit désormais dans `mentionsReponse()`, à un
> seul endroit — elle était recopiée deux fois et absente deux fois, ce qui
> est exactement ainsi que deux copies divergent.
>
> Un défaut du jet du banc aurait été une **régression** :
> `REPONSE TRONQUEE a ${result.max_tokens} tokens`, sur un champ inexistant.
> Le libellé actuel dit « a max_tokens » en nommant le *paramètre*, non une
> valeur ; la suggestion aurait affiché « a undefined tokens ».
>
> **Vague 2 (`wf_b59cedb3-3ad`), signal brut, non encore arbitré :** 17 refus
> propres, 10 entrées malformées *acceptées*, 3 erreurs brutes — et surtout
> **12 refus qui ne nomment pas l'issue**, au regard du critère que ce dépôt
> s'applique à lui-même. Rien de tout cela n'est cru avant lecture du code.




| Sujet | Statut | Ce qu'il faudra pour le clore |
|---|---|---|
| Une réponse vidée par le retrait du raisonnement est rendue **sans le dire** | `OUVERT` | un signalement explicite dans les quatre appelants, et un test qui échoue s'il disparaît |
| `nexus_compare` perd le drapeau `tronquee` que `chat()` calcule pour lui | `OUVERT` | même test |
| Le profil `reasoning` a répondu entièrement hors sujet | `OUVERT` | une épreuve de compréhension par profil ; aucune n'existe |
| `nexus_search` rend 8 extraits à score 0,205 sur une requête absurde | `OUVERT` | à vérifier : seuil ou mention explicite du score |

> **Le premier défaut est confirmé ligne à ligne.** `chat()` rend
> `text: sansRaisonnement(content)`, qui vaut `""` lorsqu'une balise de pensée
> est ouverte et jamais refermée — et son commentaire justifie ce choix, à
> raison : livrer le brouillon serait pire. Mais le même `chat()` rend aussi
> `tokens` et `tronquee`. Mesuré par la charge : `glm-5.3-cloud`, 50,4 s,
> **8234 jetons**, et un corps vide sous le titre `### glm-5.3-cloud`.
> L'agent a conclu « réponse tronquée ». C'est la conclusion normale : l'outil
> détient la raison et ne la dit pas.
>
> `nexus_ask`, `nexus_route` et `nexus_vision` annoncent bien
> `· REPONSE TRONQUEE a max_tokens` ; **`nexus_compare` est le seul à perdre
> ce drapeau**. Mais aucun des quatre ne dit qu'un corps vide vient du retrait
> du raisonnement. C'est la même famille que le refus de `nexus_agent.py` qui
> ne nommait pas `--racine` : le code sait, et se tait.
>
> **Le profil `reasoning` n'est PAS un défaut du pont.** Son ordre est
> documenté dans `server.js` et fut corrigé par la mesure de débit — le
> commentaire reconnaît lui-même que ses deux premiers candidats sont des
> *spécialistes du code*. La charge y a mis un arbitrage d'infrastructure ;
> `qwen3-coder-30b-local` l'a lu comme une question de **finance DeFi**
> (« pools de liquidités », « taux de rendement »). Une observation ne fait pas
> une propriété — §112.3 l'a assez coûté ici — mais elle désigne un vide réel :
> l'ordre des profils est établi sur le démarrage et le débit, et **rien ne
> mesure la compréhension du domaine**. Un banc de plus manque, pas un
> réglage.
>
> **Trois remontées rejetées à l'arbitrage**, et le motif compte autant que le
> rejet : le refus d'un modèle inexistant est clair et nomme l'issue (la garde
> fonctionne) ; deux « anomalies » jugeaient la qualité d'un modèle local, pas
> le pont ; une troisième, classée *bloquante*, disait « impossible d'invoquer
> l'outil MCP sans outils shell » — c'est une limite du sous-agent, jamais du
> serveur.

### Le plan cloud est tombé sous mes propres vagues — diagnostic, 30/08 au soir

| Sujet | Statut | Ce qui le fermera |
|---|---|---|
| Concurrence **cloud** non bornée | `FAIT` | `NEXUS_CLOUD_CONCURRENCE`, défaut 4, deux files indépendantes ; `--only semaphore`, 9 cas dont une contre-épreuve |
| `This model isn't mapped yet` sur les alias `ollama_chat/*` | `OUVERT` | la passerelle ignore tarif et fenêtre de ces modèles ; effet réel à établir |
| Refus qui ne nomment pas l'issue | `FAIT` | `--only protocole`, 9 cas dont un contrôle structurel |

> **Ce qui a été mesuré, machine au repos et vagues arrêtées :**
>
> | appel | résultat |
> |---|---|
> | `llama3.2-3b-local` | **OK en 18,3 s** |
> | `glm-5.3-cloud` | expire à 102 s |
> | `kimi-k2.7-code-cloud` | expire à 102 s |
> | `https://ollama.com/api/tags` | **200 en 0,23 s** |
> | `/health/liveliness` de la passerelle | **200 en 0,22 s** |
>
> Ni le réseau, ni l'hôte amont, ni la passerelle. Le journal de LiteLLM donne
> le mot : **`Client error '429 Too Many Requests' for url
> 'https://ollama.com/api/chat'`**. Le sujet « les modèles cloud échouent en
> série », ouvert depuis la veille avec pour seul indice « Remote end closed
> connection, 2,0 s », est donc diagnostiqué — et son symptôme a changé : il
> pend désormais au lieu de fermer.
>
> **DEUX ERREURS DE MA PART, et elles s'annulent presque.**
>
> La première : j'ai écrit dans ce cockpit, il y a une heure, que « le cloud
> n'est PAS borné : il a rendu 7 sur 7 en parallèle ». C'était vrai **à sept
> appels simultanés**. Je l'ai généralisé à cent cinquante en lançant deux
> vagues qui appelaient toutes `gpt-oss-120b-cloud`. C'est très exactement
> l'erreur que §112.3 corrige — deux relevés érigés en propriété d'une classe
> — commise deux heures après l'avoir citée.
>
> La seconde, en sens inverse : constatant que le service ne revenait pas
> aussitôt les vagues arrêtées, j'ai conclu « ce n'est donc pas une saturation
> que j'aurais causée ». Faux : un 429 s'accompagne d'une fenêtre de
> refroidissement, et l'absence de retour immédiat ne prouve rien. Le journal
> a dit ce que l'inférence ne pouvait pas dire. **La leçon n'est pas d'avoir
> eu tort deux fois, c'est que les deux fois j'ai conclu sans regarder les
> journaux, qui étaient à une commande de distance.**
>
> **Conséquence mécanique, et elle est symétrique du sémaphore local.** La
> borne locale existe parce que le moteur partage sa mémoire ; il en faut une
> pour le cloud parce que l'abonnement partage un débit. Elle doit être plus
> haute — sept appels simultanés ont tenu — mais elle ne peut pas être absente.
> Le sémaphore est déjà écrit et éprouvé : seule manque une seconde borne,
> distincte, et le prédicat qui l'aiguille.
>
> **Fait le soir même.** Deux files, jamais une seule : un appel cloud qui
> attendrait derrière un appel local paierait la lenteur du local — 600 s
> d'expiration mesurées — et annulerait l'intérêt d'avoir deux plans.
> L'épreuve le chiffre : **cloud rendu à 14 ms pendant que le local prenait
> 202 ms**. Anthropic et le plan inconnu ne sont bornés par personne : le
> premier se limite par le portefeuille, le second n'est pas assez connu pour
> qu'on lui impose quoi que ce soit.
>
> Une mécanique, deux instances — `creerSemaphore`. Deux copies de la même
> règle finiraient par diverger, ce qui est exactement le défaut corrigé le
> même soir sur les mentions de réponse, où une règle vivait en deux copies
> et manquait aux deux autres appelants.
>
> **Un défaut de ma délégation, pas du banc, et il vaut d'être noté** : le
> premier envoi joignait les 102 Ko de `server.js` pour une tâche qui avait
> besoin de quarante lignes. Trois fenêtres de MAP-REDUCE, toutes perdues,
> sept minutes. Le même travail avec le seul extrait utile : **19 s, coût 0**.
> Déléguer ne suffit pas ; ce qu'on joint décide du résultat.


### La vague bornée a trouvé un vrai défaut — 30/08, tard

| Sujet | Statut | Ce qui le garde |
|---|---|---|
| `socket` employé deux fois dans `nexus_bench.py`, importé nulle part | `FAIT` | seconde famille de `nexus_portee_import.py` ; `--only portee` passe de 6 à 13 cas |
| Un module standard employé sans être importé | `FAIT` | même contrôle, volontairement étroit |

> **Le défaut.** `scripts/nexus_bench.py` employait `socket.timeout` aux lignes
> 127 et 195 sans jamais importer `socket`. L'effet est plus grave que ce que
> le banc en disait : les deux usages sont dans un bloc
> `except urllib.error.URLError`, et **une exception levée dans un `except`
> n'est pas rattrapée par les `except` frères du même `try`**. Le `NameError`
> ne tombait donc pas dans le `except Exception` qui suit — il s'échappait de
> la fonction. Le banc de latence, dont §105.2 et §112.3 tirent la sélection
> des modèles, plantait sur la condition même qu'il mesure.
>
> **Aucun contrôle existant ne pouvait le voir.** `controle_imports` charge
> les modules, et celui-ci s'importe proprement : l'import n'est pas mal
> placé, il est absent. `nexus_portee_import.py` cherchait un nom importé
> dans une fonction et employé dans une autre ; ici le nom n'est nulle part.
>
> **Le premier jet du garde a été rejeté, et son chiffre mérite d'être
> gardé** : il tentait l'analyse *générale* des noms non définis et rendait
> **581 faux positifs** sur ce dépôt — variables de compréhension prises pour
> non liées, `__file__` ignoré, et un code de sortie 0 affiché sous un
> « DEFAUTS: 581 ». Un détecteur qui crie à tort est désarmé le jour même.
> Aucun linter n'est installé, et en installer un contredirait la règle
> « stdlib seule » des gardes : la bonne réponse était de **rétrécir la
> question**, non d'élargir l'outil. Le contrôle ne signale donc qu'un nom
> employé en attribut, figurant dans `sys.stdlib_module_names`, et lié nulle
> part. Six pièges à faux positifs sont éprouvés à chaque exécution.
>
> **La borne, elle, se voit dans les chiffres.** Vague non bornée : 19 échecs
> sur 34. Vague bornée à quatre : **1 échec sur 28**.

### L'audit des 38 scripts, arbitré — 30/08, tard

> Vague `wf_ec9ac764-a7e` close : **105 agents, 38 audits, 1 seul échec
> d'appel**. Elle a rendu **43 défauts « réels et cités »**. Voici ce qu'ils
> valaient après lecture du code réel.

| Verdict du banc | Nombre | Arbitrage |
|---|---|---|
| Motif avouant lui-même un comportement délibéré | 12 | écartés d'office : le drapeau contredit le motif |
| Vérifiés et **retenus** | 2 | `socket` jamais importé ; `UnicodeDecodeError` non attrapé |
| Vérifiés et **rejetés** | 3 | voir ci-dessous |
| Non encore relus | 26 | restent à arbitrer, et comptés comme tels |

> **Le défaut le plus instructif visait le fichier livré une heure plus tôt.**
> `nexus_portee_import.py` lisait ses fichiers avec `except (OSError,
> IOError)`. Or `UnicodeDecodeError` est un **ValueError**, jamais un
> OSError : un fichier non UTF-8 faisait tomber le détecteur avec une trace.
> Et la porte de conformité l'appelle — **un seul fichier mal encodé dans
> `scripts/` aurait bloqué le démarrage**, ce que ce dépôt nomme exactement
> « un garde qui plante arrête le travail qu'il protégeait ». Éprouvé sur un
> fichier UTF-16 fabriqué, avant et après.
>
> **Trois rejets, et leurs motifs valent autant que les retenues :**
>
> * `nexus_relais.py` — « `subprocess.run` avec `encoding` sans `text=True` ».
>   **Faux** : préciser `encoding` implique le mode texte depuis Python 3.6.
> * `nexus_portee_import.py` — « `ast.AugAssign` non collecté au niveau
>   module ». **Impossible** : un `X += 1` au niveau module exige que `X`
>   existe déjà, il ne peut donc jamais être la seule liaison.
> * `nexus_cablage.py` — « `except Exception` attrape `KeyboardInterrupt` ».
>   **Faux** : `KeyboardInterrupt` dérive de `BaseException`, non de
>   `Exception`.
>
> Un quatrième est réel mais mineur, et n'appelle aucun correctif :
> `nexus_releve.py:242` ouvre un fichier sans `with`. En CPython le compteur
> de références ferme le descripteur aussitôt la ligne finie.
>
> **CE QUE CETTE VAGUE APPREND SUR LE HARNAIS, et c'est le plus utile.** Douze
> vérificateurs sur quarante-trois ont marqué `reel: true` tout en
> **expliquant dans leur propre motif** que le comportement était délibéré et
> commenté. Ma consigne disait pourtant « un commentaire qui l'explique fait
> foi » : ils l'ont appliquée au motif et pas au drapeau. Un champ booléen
> demandé à côté d'un champ libre se remplit sans être pesé. La leçon pour la
> prochaine vague : **ne jamais lire le drapeau seul**, et de préférence ne
> plus demander de drapeau du tout — faire répondre à la question « quel
> commentaire ou quelle ligne rend ce comportement délibéré ? », dont
> l'absence de réponse vaut rejet.

### L'amplification des replis — la cause racine, 30/08 au soir

| Sujet | Statut | Ce qui le garde |
|---|---|---|
| Un `-cloud` repliait sur un autre `-cloud` du même compte | `FAIT` (générateur) | `--only terminal`, 7 cas dont une contre-épreuve |
| La LOI 1 dépendait d'un seul plan | `FAIT` | `--modele` / `NEXUS_VALIDE_MODELE` |
| `num_retries: 2` sur un 429 | `OUVERT` | exige de vérifier la politique par type d'erreur dans la doc LiteLLM |
| `litellm_config.yaml` porte toujours les 37 chaînes | `OUVERT` | régénération + redémarrage, à la main de l'opérateur |

> **Le chiffre qui explique toute la soirée**, mesuré par une session voisine
> et vérifié ici : chaque appel client devient **~13 requêtes vers
> ollama.com** — une, fois trois tentatives (`num_retries: 2`), fois trois
> groupes (l'original plus deux replis cloud→cloud). Constaté : **40
> connexions sortantes pour 3 appels clients**. Le plafond du compte porte
> sur ces 40, jamais sur les 3.
>
> Vérifié dans ma propre configuration avant d'y croire : **37 replis
> cloud→cloud contre 4 cloud→local**. Le chiffre annoncé était exact.
>
> Et il explique ce que j'ai mesuré indépendamment : six tâches simultanées,
> **36 refus 429 et zéro succès en six minutes**. Le régime encadré par la
> session voisine dit la même chose : 3 appels en vol → 752/h sans un échec ;
> 8 à 32 → **0**.
>
> **Deux défauts distincts dans le générateur.** Le premier : la sortie
> locale n'était greffée que s'il restait de la place, donc uniquement sur
> les deux derniers maillons — alors que le docstring *et* le commentaire de
> l'appelant affirmaient tous deux que « toute chaîne externe s'achève en
> local ». Le second, découvert en corrigeant le premier : même greffée, la
> chaîne gardait un successeur cloud. Or un voisin cloud n'aide **jamais**
> sous 429, puisque le refus frappe le quota du compte. Les chaînes cloud
> sont désormais rendues avec `width=1` : un seul groupe atteint ollama.com,
> le repli part sur la machine et ne consomme aucun quota.
>
> **Ce que je n'ai pas touché, et pourquoi.** `num_retries: 2` reste en
> place. La demande d'un `num_retries: 0` sur 429 est juste dans le principe,
> mais la politique de tentatives *par type d'erreur* est une capacité de
> LiteLLM qu'il faut **vérifier dans sa documentation** avant de l'écrire —
> le contrat interdit d'inventer une capacité d'un fournisseur.
>
> **La LOI 1 dépendait du plan le plus fragile.** `nexus_valide.py` nommait
> `gpt-oss-120b-cloud` en dur à deux endroits. Pendant le 429, la validation
> obligatoire avant tout commit est devenue **impossible à exécuter** — deux
> tentatives sont restées dix minutes sans rendre. Une validation qui ne
> s'exécute pas ne protège de rien. Le commit qui corrige cela a été validé
> par `qwen3-coder-30b-local`, cloud indisponible : c'est sa propre preuve.

### La sélection naturelle tournait sur une jambe — 30/08, nuit

| Sujet | Statut | Ce qui le ferme |
|---|---|---|
| J'ai supprimé deux fonctions encore appelées | `FAIT` | `--only noms`, avec contre-épreuve rejouant la suppression réelle |
| Les replis cloud→cloud, dans la config **active** | `FAIT` | régénéré : 37 → 2, et LiteLLM redémarré |
| Un amont qui **pend** attend 3 × 180 s avant tout repli | `OUVERT` | distinct de l'amplification ; le repli existe, il arrive trop tard |
| `epreuves.json` ne juge qu'**un** modèle sur 71 | `EN COURS` | `nexus_releve.py --tous` lancé |

> **La panne que j'ai causée, et les quatre contrôles qui ne l'ont pas vue.**
> Le correctif du sémaphore remplaçait une *région* de `server.js` délimitée
> par deux commentaires ; cette région contenait aussi `sansRaisonnement()`
> et `mentionsReponse()`, restées appelées en six endroits. Le serveur a
> planté au redémarrage suivant, chez une session voisine.
>
> Aucun garde ne pouvait le voir : `node --check` valide la syntaxe et non la
> résolution des noms ; les trois épreuves JS extraient chacune un **bloc
> isolé** ; le cliquet de câblage ne juge que le Python ; la porte de
> conformité ne charge pas le pont. Quatre contrôles, **un angle mort
> commun**. Le garde `--only noms` le ferme.
>
> **La configuration active, enfin.** Le correctif des replis vivait dans le
> générateur et n'avait aucun effet. Mesuré sur le fichier réel, avant/après :
> cloud→cloud **37 → 2**, cloud→local **3 → 19**. Les deux restants sont
> légitimes : chaînes de vision ou d'embedding, où greffer un terminal
> *textuel* enverrait une image à un modèle aveugle — qui ne rend pas une
> erreur, mais une réponse fausse.
>
> **CE QUI RESTE, et que le correctif ne traite pas.** `gpt-oss-120b-cloud`
> pend toujours au-delà de 120 s. L'amplification est corrigée ; l'**attente**
> ne l'est pas. Avec `request_timeout: 180` et `num_retries: 2`, un amont qui
> pend sans jamais répondre fait attendre trois fois 180 s **avant** que le
> repli local ne soit tenté. Le repli existe désormais ; il arrive trop tard.
>
> **L'INCOHÉRENCE LA PLUS LOURDE, trouvée en cherchant où enrichir le local.**
> `latences.json` porte **71 entrées** : tout le parc est mesuré en vitesse.
> `epreuves.json` en porte **2** — et ce sont le même modèle et son alias.
> Donc **un seul modèle sur 71** a jamais prouvé qu'il sait orchestrer :
> parler le protocole, demander un outil, exploiter le retour, enchaîner.
>
> Or §105.2 fait reposer la promotion sur deux jambes, latence **ou**
> capacité. La seconde n'a jamais servi. Et c'est sur elle que repose la
> promesse centrale de la plateforme — *le jour où l'abonnement expire, le
> travail continue*. Ajouter des modèles avant de faire tourner cette
> jambe-là reviendrait à grossir un tas que le mécanisme ne sait pas juger.

### La jambe manquante, et ce qu'elle a révélé — 30/08, nuit

| Sujet | Statut | Ce qui le garde |
|---|---|---|
| `retry_policy` : ne pas rejouer un 429 ni une expiration | `FAIT` | clés vérifiées dans la doc LiteLLM avant écriture |
| Un embedding déclaré `mode: chat` | `FAIT` | `mode: embedding` déclaré ; le filtre lit la déclaration |
| Un **échec d'appel** enregistré comme un **échec de capacité** | `FAIT` | `--only registre`, 6 cas dont une contre-épreuve |
| Les épreuves sur les 71 modèles | `EN COURS` | 14 rendus |

> **Le plan cloud est rétabli, et mesuré :** `gpt-oss-120b-cloud` **10,6 s**
> — il pendait au-delà de 120 s ; `glm-5.3-cloud` 2,1 s ; le local 2,0 s.
> Réserve d'honnêteté : la fenêtre de refroidissement du 429 a pu expirer en
> parallèle. Mécanisme et mesure concordent, ce n'est pas une preuve.
>
> **L'angle mort corrigé à sa source, enfin.** `bge-m3-local`, modèle
> d'embedding, a été soumis à une épreuve d'**orchestration** et a enregistré
> 0/4 — un score qu'il ne peut pas obtenir autrement, par construction. Le
> filtre excluait sur le *nom* (`embed|minilm|llava`), que `bge-m3` ne porte
> pas. Mais le nom n'aurait jamais dû servir : la modalité est *déclarée* —
> sauf qu'elle ne l'était pas. La documentation LiteLLM le dit : `mode` non
> défini, le proxy **retombe sur une complétion de conversation**. C'est
> l'angle mort que §106.1 dit avoir déjà été corrigé **deux fois ailleurs
> qu'à sa source**.
>
> **Un second effet, non cherché et plus sérieux :** les trois embeddings
> portent `litellm_health_check: true` sans `mode`. Leur sonde de santé les
> interrogeait donc **en conversation**, endpoint qu'ils ne servent pas. Le
> contrôle de santé se trompait sur eux depuis le début.
>
> **CE QUI RESTE OUVERT, du même genre.** Un **échec d'appel** est enregistré
> comme un **échec de capacité** : les 0/4 portant `plan: inconnu` et
> `servi: ?` signifient que l'appel n'a jamais abouti. Rien ne les distingue
> d'un vrai échec, alors que §105.2 dit exactement l'inverse — l'absence de
> preuve n'est pas une preuve d'absence. La contradiction est flagrante :
> `glm-4.7-flash-local` rend 0/4 quand `releve-locale`, **servi par le même
> modèle**, rend 4/4.
>
> **Deux erreurs de méthode, les miennes.** J'ai conclu que la passerelle ne
> remontait pas alors que ma boucle d'attente était fautive : sur connexion
> refusée, `curl` rend la main instantanément, donc quarante essais
> s'épuisaient en une seconde. Et j'ai lancé les épreuves **puis redémarré la
> passerelle deux fois sous elles** — les « Remote end closed connection »
> n'étaient pas un défaut du parc, c'était moi. Le manuel interdit de mesurer
> sous charge.

### Six modèles savent orchestrer, contre un mesuré — 30/08, nuit

> **Le pire défaut de la soirée, et il était invisible dans le fichier.**
> `consigner` écrit sous **deux** noms — l'alias demandé et l'alias servi —
> à juste titre, c'est le même modèle. `releve-locale` a passé 4/4, donc
> `glm-4.7-flash-local` portait 4/4. Puis `--tous` l'a interrogé
> directement, l'appel n'a jamais abouti, et le **0/4 a écrasé le 4/4**.
>
> Le registre affirmait simultanément que le même modèle orchestre et
> n'orchestre pas. Ce n'est pas un étiquetage trompeur : c'est une **preuve
> détruite**. Et le script distinguait pourtant déjà les deux cas *à
> l'écran* — « Rien n'est prouvé, rien n'est infirmé » — pour tout perdre à
> l'écriture.
>
> Une tentative non concluante ne remplace plus un verdict concluant ; elle
> est tracée à part. Un échec **réel**, lui, remplace toujours : sans quoi un
> modèle qui se dégrade resterait promu sur une mesure périmée.
>
> **Le registre est réparé sans rien fabriquer.** Trois entrées portaient 0/4
> avec `plan: inconnu` : elles sont **effacées**, non corrigées en 4/4
> supposé. « Jamais mesuré » est l'état vrai, et jamais mesuré n'est jamais
> promu.
>
> **CE QUE LA JAMBE MANQUANTE A RENDU, et c'est le résultat de la nuit.** La
> capacité d'orchestration n'avait jamais été éprouvée que sur **un** modèle
> sur 71. Onze verdicts tiennent désormais, dont **six complets** :
>
> | 4/4 | 3/4 | 1/4 |
> |---|---|---|
> | codestral, gemma3-1b, gemma4-12b, gemma4-26b, glm-4.7-flash, relais déclaré | command-r, deepseek-coder-33b | codegemma-7b, codestral-22b, deepseek-coder-6.7b |
>
> Le parc sait orchestrer **bien plus largement** qu'on ne le mesurait — et
> deux modèles à 3/4 sont à un pas. La sélection naturelle avait la donnée
> qu'il lui fallait ; personne ne la lui avait fournie.

### Trois lancements pour douze modèles — la reprise manquait

| Sujet | Statut | Ce qui le garde |
|---|---|---|
| `--tous` ne reprenait pas | `FAIT` | `--only registre`, 10 cas dont un contrôle structurel sur l'annonce |
| Deux tâches de fond tuées sans cause connue | `OUVERT` | ce n'était pas moi ; la reprise en réduit le coût sans l'expliquer |

> **Le chiffre dit tout mieux qu'une analyse.** Trois lancements de `--tous`,
> interrompus chacun avant la fin, ont mesuré les **mêmes douze premiers
> modèles par ordre alphabétique** — codegemma, codestral, command-r,
> deepseek, gemma, glm — et ne sont jamais allés au-delà. Le parc en compte
> soixante-et-onze.
>
> La cause était à nu : `cibles = candidats_locaux(cle)` puis une boucle sur
> tout, sans jamais consulter les verdicts acquis. Or le registre persiste
> après **chaque** modèle : **la donnée était là, personne ne la lisait.**
>
> Ce n'est pas une lenteur, c'est un **plafond** : refaire une épreuve déjà
> acquise n'ajoute rien *et* empêche le reste d'être mesuré.
>
> Seuls les verdicts **concluants** sont sautés — une tentative qui n'a pas
> atteint le modèle sera rejouée. C'est la règle du commit précédent,
> appliquée cette fois à la *lecture* et non à l'écriture. Et le saut est
> **dit** : une reprise muette se lirait comme « tout a été mesuré », ce qui
> est exactement le contraire.

### Le plafond mesuré, et l'audit qui m'a retourné ma propre phrase

| Sujet | Statut | Ce qui le garde |
|---|---|---|
| Mes épreuves pouvaient passer **à vide** | `FAIT` | seuil de taille + nom de fonction exigés sur les trois extractions |
| Une contre-épreuve qui acceptait une régression | `FAIT` | `maximum > 1` au lieu de `!== 1` |
| Le pont MCP est **beaucoup plus lent** que LiteLLM en direct | `OUVERT` | mesuré, non expliqué |

> **LE PLAFOND, enfin mesuré.** Sous **deux charges simultanées** — vague MCP
> sur le plan cloud, épreuves de capacité sur le plan local — la passerelle a
> servi **27 requêtes avec ZÉRO 429 en dix minutes**. Avant correction, six
> tâches produisaient 36 refus et zéro succès. L'amplification est supprimée,
> et les deux files du sémaphore séparent bien les plans.
>
> **L'audit délégué m'a retourné la phrase que j'avais mise dans sa
> consigne** : une épreuve fausse rassure au lieu de protéger. Trois
> faiblesses, toutes dans du code écrit ce soir. `fin < debut` laissait
> passer une tranche **vide** — les huit cas suivants auraient rendu
> « épreuve tenue » sans tester une ligne. Et ma contre-épreuve exigeait
> `maximum !== 1`, or `maximum` vaut **zéro** quand la variante fautive ne
> laisse passer aucun appel : elle acceptait donc une régression au lieu de
> la voir. Il fallait exiger qu'elle **dépasse** la borne, pas qu'elle en
> diffère.
>
> **Ce que j'ai rejeté de la même vague, et le motif vaut autant.** Elle
> signalait `</#>` avec pour conséquence « le script ne démarre jamais ». Le
> token existe ; la conséquence est **fausse** — mesuré, le fichier se parse,
> et un fichier ne contenant que ce token aussi. J'ai moi-même cru ensuite
> que le code était enfermé dans un commentaire ouvert ligne 1 : **faux
> également**, la documentation se ferme ligne 35. Deux conclusions hâtives,
> la sienne et la mienne, arrêtées par la même vérification.
>
> **Sujet ouvert, mesuré et non expliqué.** Un `nexus_ask` **via le pont** a
> mis plus de 120 s pour rendre « PRET », quand le même modèle en **direct
> sur LiteLLM** répond en 10,6 s. La vague a subi 16 expirations à 600 s sans
> un seul 429. Le pont ajoute un coût que je n'attribue à rien tant que je ne
> l'ai pas mesuré.

### Dix modèles complets, et les faux zéros vengés

> Les épreuves reprennent bien : **18 éprouvés, 10 complets** — codestral,
> gemma3-1b, gemma4, gemma4-12b, gemma4-26b, gemma4-31b, glm-4.7-flash,
> gpt-oss-20b, llama3.1-8b, et le relais déclaré.
>
> **Deux de ces dix portaient les faux 0/4 que j'avais effacés** plutôt que
> corrigés en 4/4 supposé : `gemma4-31b-local` et `gemma4-local`. Remesurés,
> ils rendent 4/4 par eux-mêmes. Ne rien fabriquer était la bonne décision,
> et le parc vient de le démontrer.
>
> **Les tâches de fond longues sont tuées ici** — trois fois, sans cause
> connue et sans que ce soit moi. La reprise rend l'incident peu coûteux :
> chaque relance avance. C'est une contrainte de l'environnement à laquelle
> on s'adapte, non un défaut à corriger dans le dépôt.
>
> **Sur le surcoût du pont, je m'arrête à ce qui est mesuré.** Un fait
> discriminant : à 19 h, ce serveur refusait déjà `max_tokens: -1` avec le
> message écrit ce soir. Il n'est donc pas aussi ancien que je le supposais.
> Établir la cause demanderait d'instrumenter le serveur en cours, que je ne
> peux pas redémarrer moi-même. La spéculation s'arrête là.

### Combien ont échoué ne dit pas laquelle — 30/08, nuit

| Sujet | Statut | Ce qui le garde |
|---|---|---|
| Le registre gardait le score, pas la lacune | `FAIT` | `--only registre`, 12 cas |
| Le détail des sept modèles déjà partiels | `OUVERT` | perdu ; il reviendra à leur prochaine mesure |

> **Trouvé en essayant de faire ce que l'objectif demande** — enrichir le parc
> d'après les lacunes révélées. **La donnée n'existait pas.** Sept modèles
> partiels, dont **trois à 3/4** — à une seule épreuve d'être promouvables —
> et rien ne disait laquelle leur manquait.
>
> Or les quatre épreuves mesurent des capacités **différentes** : parler le
> protocole, demander un outil, exploiter le résultat, enchaîner. Échouer sur
> la première rend un modèle inutilisable ; échouer sur la quatrième laisse un
> répondeur parfaitement utile. Un « 3/4 » ne distingue pas ces deux mondes.
>
> **C'est la troisième fois ce soir que ce script sait quelque chose à
> l'écran et l'oublie au disque** — après la distinction échec/non-mesuré, et
> après le non-écrasement. Le rapport portait l'information ; seule l'écriture
> la perdait.
>
> `epreuves_echouees` et `epreuves_non_mesurees` restent **distinctes** : une
> épreuve non tentée n'est pas une épreuve ratée. C'est la même règle que le
> non-écrasement, appliquée au détail.
>
> **Ce que cela ne donne pas encore, et il faut le dire** : les sept modèles
> partiels ont été mesurés *avant* ce changement. Leur détail est perdu et ne
> reviendra qu'à leur prochaine mesure.
>
> **Une confirmation au passage** : `derniere_tentative_vaine` apparaît sur
> les entrées anciennes. Le non-écrasement travaille pour de bon — ces
> modèles ont subi une tentative sans lendemain après leur vrai verdict, et
> l'ont gardée.

### Le champ censé rendre la reprise sûre la rendait vaine

| Sujet | Statut | Ce qui le garde |
|---|---|---|
| `concluante` jugé sur l'adresse au lieu de `servi` | `FAIT` | `--only registre`, 14 cas dont un contrôle structurel |
| Les embeddings encore candidats | `FAIT` | configuration rechargée : 44 candidats → 43, plus aucun embedding |
| Les tâches de fond tuées ici | `CONTOURNÉ` | mesure en premier plan, bornée ; chaque modèle achevé est consigné |

> **Défaut de mon fait, posé il y a une heure, trouvé en lisant les données
> qu'il produisait.** J'avais écrit `concluante = plan connu ET adresse
> != "?"`. Or l'adresse amont n'est pas toujours résolvable **même quand
> l'appel aboutit**. `qwen2.5-0.5b-local` a rendu 3/4, servi par
> `ollama_chat/qwen2.5:0.5b`, et se voyait marquer `concluante: false`.
>
> **Huit entrées dans ce cas, dont trois à 4/4** — gemma4-31b, gemma4,
> gpt-oss-20b.
>
> **La conséquence n'était pas cosmétique.** `deja_mesures()` ne reprend que
> les verdicts concluants : ces huit modèles auraient été remesurés
> **indéfiniment**. C'est très exactement le plafond que la reprise devait
> lever, réintroduit par le champ censé la rendre sûre.
>
> Le bon signal était sous la main : `servi`, le nom du modèle qui a
> réellement répondu. Le registre est réparé **sans rien fabriquer** — le
> champ dérivé est recalculé à partir de données déjà stockées. Effet
> immédiat : la reprise passe de 11 à **19** entrées.
>
> **Comment il a été trouvé.** Les tâches de fond sont tuées ici, cinq fois,
> cause inconnue. Plutôt que de relancer une sixième fois à l'identique, j'ai
> changé de méthode — mesure en premier plan, bornée par le délai de l'outil.
> C'est en lisant les entrées fraîches que le défaut est apparu. Contourner un
> défaut est la façon dont il survit.

### Six relevés dans le même registre — une heure passée à poursuivre des ombres

| Sujet | Statut | Ce qui le garde |
|---|---|---|
| Aucun verrou sur `nexus_releve` | `FAIT` | `--only registre`, 17 cas dont trois structurels |
| Une mesure qui ne s'achève jamais | `FAIT` | `--limite N`, tranche bornée + reprise |
| La lacune dominante du parc | `EN COURS` | le détail arrive enfin, 4 modèles l'ont |

> **Six processus de relevé tournaient ensemble**, issus de trois lancements
> — 22:51, 23:21, 00:02 — chacun portant la version du code chargée à *son*
> démarrage, et tous écrivant dans le même `epreuves.json`.
>
> **J'ai poursuivi leurs symptômes pendant une heure comme s'il s'agissait de
> défauts distincts** : champs neufs absents d'entrées pourtant fraîches,
> `concluante` qui régressait après correction, compte de complets qui montait
> puis redescendait. **Un seul** était un vrai défaut — le critère fondé sur
> l'adresse. Les autres n'étaient que le recouvrement.
>
> Ce qui a rendu le diagnostic si long : le signal « killed » tue le shell,
> mais **l'enfant Python survit** et continue d'écrire. Les processus étaient
> réputés morts.
>
> **Le verrou existait déjà** et servait au banc de latence. Il manquait ici,
> alors que ce script écrit un registre partagé — exactement ce que le banc
> fait aussi. Son refus **ne lève pas** : il se lit sur `obtenu`. Piège
> documenté dans `nexus_bench.py`, et tenace parce qu'un mutex nommé est
> **réentrant** dans le même processus : un essai en un seul interpréteur
> donne à croire que tout va bien. D'où trois contrôles **structurels**.
>
> `--limite N` répond à l'autre moitié : six lancements de `--tous`
> interrompus sans qu'aucun n'atteigne le bout. Chaque modèle achevé était
> consigné, mais rien ne se terminait — et un processus qui ne s'achève jamais
> ne rend jamais de verdict global. Une épreuve coûte plus de trois minutes,
> soit ~2 h pour 43 candidats.
>
> **Vérifié de bout en bout, en une invocation qui S'ACHÈVE** : verrou pris,
> 21 modèles repris, tranche de 1 sur 22 restants, 4/4.
>
> **Et la première donnée de lacune**, impossible à obtenir il y a deux
> heures : `llama3.2-1b-local` rend 1/4 — il passe le protocole et échoue sur
> *demande un outil*, *exploite le résultat*, *enchaîne deux outils*. C'est
> cela qui dira quel modèle ajouter, jamais la taille.

### La lacune se dessine : demander un outil, pas la taille — 31/08

> **Premier relevé des lacunes**, sur les six modèles qui portent le détail
> (34 éprouvés, 13 complets) :
>
> | épreuve | échecs |
> |---|---|
> | demande un outil | **4** |
> | enchaîne deux outils | **4** |
> | exploite le résultat d'outil | 2 (+ 2 *non mesurées*) |
> | parle le protocole `/v1/messages` | 1 |
>
> **L'échec cascade, et c'est mécanique, non statistique.** « Exploite le
> résultat » apparaît *non mesurée* chez deux modèles : on ne peut pas tester
> l'exploitation d'un résultat qu'aucun outil n'a produit. L'épreuve 2 commande
> les épreuves 3 et 4. Un « 1/4 » et un « 0/4 » sont donc parfois plus proches
> qu'ils n'en ont l'air, et un modèle qui franchirait la seule demande d'outil
> pourrait gagner trois points d'un coup.
>
> **La taille ne prédit rien, une fois de plus.** `gemma3-1b` passe **4/4**
> quand `llama3.2-1b` rend **1/4** — même ordre de grandeur, verdicts opposés.
> C'est la même leçon que §112.3 sur la latence et §107.3 sur le débit, cette
> fois sur la capacité d'orchestration : elle tient à l'entraînement, non au
> nombre de paramètres.
>
> **Ce que cela commence à dire pour enrichir le parc** : ce qui manque n'est
> pas un gros modèle, c'est un modèle *entraîné à l'appel d'outils*. Six
> modèles restent un signal, pas une loi — la conclusion attendra que huit à
> dix portent le détail, comme §112.3 l'exige.

### La moitié du pool d'orchestration ne sait pas orchestrer — 31/08

| Sujet | Statut | Ce qui le garde |
|---|---|---|
| Le verdict de capacité invisible à la promotion | `FAIT` | le générateur l'annonce désormais |
| Les épreuves promeuvent mais ne rétrogradent jamais | `OUVERT` | **décision de politique, réservée à l'opérateur** |
| La lacune dominante du parc | `MESURÉE` | 10 modèles détaillés : l'appel d'outil |

> **Sur dix modèles détaillés :**
>
> | épreuve | échecs | non mesurées |
> |---|---|---|
> | parle le protocole `/v1/messages` | 2 | 0 |
> | **demande un outil** | **7** | 0 |
> | exploite le résultat d'outil | 3 | **4** |
> | **enchaîne deux outils** | **7** | 0 |
>
> Le goulot n'est pas le protocole — huit sur dix savent parler — c'est
> **l'appel d'outil**. Et l'échec cascade : « exploite le résultat » est *non
> mesurable* quand aucun outil n'a été demandé.
>
> **Le pool du routeur local, confronté à ces verdicts :**
>
> | membre | verdict |
> |---|---|
> | `codestral-local` | **4/4** |
> | `llama3.2-3b-local` | **4/4** |
> | `deepseek-coder-33b-local` | 3/4 — échoue |
> | `phi3-mini-local` | **1/4** — jamais éprouvé jusqu'ici |
>
> **La moitié du pool qui sert l'orchestration est prouvée incapable
> d'orchestrer**, pendant que onze modèles prouvés 4/4 restent dehors.
>
> **La cause, vérifiée ligne 648 de `nexus_generate.py`** :
> `eligible_au_pool` rend vrai si l'épreuve est *complète*, sinon il retombe
> sur la latence. Une épreuve réussie ouvre la porte ; une épreuve **échouée
> ne la ferme pas**. Les épreuves promeuvent et ne rétrogradent jamais — et
> cette asymétrie n'était écrite nulle part.
>
> **Ce que je n'ai pas fait, et pourquoi.** Je n'ai pas changé la règle.
> Exclure un modèle parce qu'il échoue supposerait qu'un modèle incapable
> d'appeler un outil est inutile au pool — or il peut parfaitement résumer.
> Ce qui manque pour trancher n'est pas une décision mais une **mesure** :
> personne ne sait ce que coûterait cette exclusion. Changer la politique de
> routage sur une intuition serait exactement ce que cette nuit a passé son
> temps à corriger ailleurs.
>
> Le générateur **annonce** désormais le verdict quand il promeut sur la
> latence un modèle dont l'épreuve a échoué. La décision lui reste ; le
> constat revient à l'opérateur, qui ne pouvait le voir qu'en ouvrant le
> registre à la main.

### Un 4/4 obtenu une fois n'est pas un 4/4 confirmé — 31/08

| Sujet | Statut | Ce qui le garde |
|---|---|---|
| Une promotion sur une seule passe | `FAIT` (rendu lisible) | `mesures`, `historique`, `stable` ; `--only registre`, 21 cas |
| La politique de promotion elle-même | `OUVERT` | **décision réservée à l'opérateur** |

> **`qwen3-0.6b-local` a rendu 4/4 puis 3/4** sur deux passages, échouant la
> seconde fois sur « exploite le résultat d'outil ». Même modèle, mêmes
> épreuves, deux verdicts.
>
> Or `eligible_au_pool` promeut sur un `complet` obtenu en **une seule
> passe** : un modèle peut entrer dans le pool d'orchestration sur un coup de
> chance. §97 l'écrit déjà pour les modèles — ne pas surinterpréter une
> exécution — mais la mesure de capacité ne suivait pas sa propre règle.
>
> Chaque entrée porte désormais `mesures`, `historique` et `stable`. **On ne
> décide rien** : comme pour l'asymétrie promotion/rétrogradation, la
> politique appartient à l'opérateur. On rend lisible ce qui ne l'était pas.
>
> **Une suspicion vérifiée puis rejetée, et le motif compte.** J'ai soupçonné
> une incohérence : « exploite le résultat » est comptée *non mesurable* quand
> aucun outil n'a été demandé, tandis qu'« enchaîne deux outils » est comptée
> *en échec* dans la même situation. Vérifié dans le code :
> `epreuve_exploite_retour` **reçoit le résultat précédent en paramètre** —
> sans appel, il n'y a littéralement rien à exploiter ;
> `epreuve_enchainement`, lui, **refait ses propres appels**, donc le modèle y
> a une chance neuve et son échec en est un vrai. L'asymétrie est délibérée.
>
> Et elle **renforce** la conclusion : deux mesures *indépendantes* de la
> capacité d'outil tombent toutes deux sur **10 échecs sur 14**. Ce n'est pas
> un test qui se fait écho.
>
> | épreuve | échecs / 14 | non mesurées |
> |---|---|---|
> | parle le protocole | 2 | 0 |
> | **demande un outil** | **10** | 0 |
> | exploite le résultat | 4 | 7 |
> | **enchaîne deux outils** | **10** | 0 |

### J'ai parlé trop tôt, et la mesure me corrige — 31/08

| Sujet | Statut | Ce qui le garde |
|---|---|---|
| `stable` vrai dès la première passe | `FAIT` | `--only registre`, 22 cas ; deux mesures exigées |
| « sept échecs sur dix » | **CORRIGÉ** | 10 sur 18, soit 56 % et non 71 % |

> **Le champ censé empêcher de conclure sur une passe unique concluait sur
> une passe unique.** `stable` valait `len(set(historique)) == 1` : avec une
> seule mesure, un ensemble d'un élément est trivialement uniforme. Quatre
> modèles portaient « mesures=1, stable=True ».
>
> C'est une fausse assurance, **pire qu'aucun champ** — un lecteur s'y serait
> fié, alors que le champ existait précisément pour l'en empêcher. Et **mes
> deux cas de test ne l'attrapaient pas** : tous deux portaient sur *deux*
> mesures. Le piège s'est refermé sur son auteur, une heure après avoir été
> posé.
>
> **CE QUI CORRIGE MA PROPRE FORMULATION**, et c'est le résultat le plus utile
> du tour. J'ai annoncé « sept échecs sur dix » pour l'appel d'outil. Les
> modèles détaillés sont passés de 14 à 18, et les compteurs d'échec sont
> **restés à 10** : les quatre nouveaux réussissent tous l'appel d'outil.
>
> | épreuve | échecs / 18 |
> |---|---|
> | parle le protocole | 2 |
> | demande un outil | **10** |
> | exploite le résultat | 5 (+ 7 non mesurées) |
> | enchaîne deux outils | **10** |
>
> Le taux tombe de **71 % à 56 %**. La lacune reste majoritaire et reste la
> même, mais elle est **moins massive que je ne l'ai écrit**. C'est très
> exactement ce que §112.3 impose d'attendre, et j'ai parlé trop tôt.
>
> Note : la tranche partie en tâche de fond s'est **achevée** cette fois,
> exit 0. Le verrou fait son office — un second relevé ne peut plus écrire
> par-dessus, ce qui était le vrai danger.

### Le parc entier est mesuré, pour la première fois — 31/08

> **« Tous les candidats ont déjà un verdict concluant. »** 44 modèles
> éprouvés, 25 avec le détail de leurs lacunes. Au début de la nuit, **un
> seul modèle sur 71** avait jamais prouvé qu'il sait orchestrer.

**Dix-huit modèles capables**, prouvés sur les quatre épreuves :
codestral · gemma3-1b · gemma4 · gemma4-12b · gemma4-26b · gemma4-31b ·
glm-4.7-flash · gpt-oss-20b · llama3.1-8b · llama3.2-3b · qwen2.5-32b ·
qwen3-8b · qwen3-14b · qwen3-32b · qwen3-coder-30b · qwen3.5-9b ·
qwen3.6-27b · relais déclaré.

| épreuve | échecs / 25 | |
|---|---|---|
| parle le protocole `/v1/messages` | 2 | 8 % |
| **demande un outil** | 14 | **56 %** |
| exploite le résultat d'outil | 5 (+ 11 non mesurées) | 20 % |
| **enchaîne deux outils** | 14 | **56 %** |

> Le goulot n'est pas le protocole — **92 % des modèles savent parler** —
> c'est l'appel d'outil, et il bloque mécaniquement l'exploitation du
> résultat, d'où les onze non mesurées.
>
> **Six modèles sont à une épreuve près**, dont deux dont on sait exactement
> ce qui manque : `qwen3-0.6b` et `qwen3-1.7b` échouent sur « exploite le
> résultat d'outil » seul.
>
> **MA CORRECTION ÉTAIT PRÉMATURÉE, et c'est la troisième fois cette nuit.**
> La série a donné 71 % (n=10), 56 % (n=18), 52 % (n=23), puis **56 %**
> (n=25). J'ai annoncé 71 % trop tôt, puis corrigé à 52 % trop tôt également.
> La valeur oscillait ; seul l'échantillon complet la fixe. **§112.3 vaut
> aussi contre l'empressement à se corriger.**
>
> **Ce que cela ne dit pas.** Aucun verdict n'a été confirmé par un *second*
> passage : `stable` exige deux mesures, et aucun modèle n'en a. `qwen3-0.6b`
> a déjà rendu 4/4 puis 3/4 — la capacité varie. Dix-huit « capables » sont
> donc dix-huit résultats uniques, pas dix-huit certitudes.

### Les trois premiers verdicts confirmés — 31/08

> **Le second passage a commencé par ce qui décide** : les membres capables du
> pool. `codestral-local`, `llama3.2-3b-local` et `glm-4.7-flash-local` — le
> modèle par défaut du pont — rendent 4/4 **une seconde fois**. Ce sont les
> trois premiers verdicts *confirmés* de la plateforme, là où dix-huit
> « capables » n'étaient que dix-huit résultats uniques.
>
> **Une mesure sauvée du rebut au passage.** Le compteur affichait
> « mesures=1 » *après* un second passage : les entrées écrites avant
> l'existence du champ n'avaient pas d'historique, et la nouvelle écriture
> repartait de zéro — jetant le `reussies` qu'elles portaient pourtant,
> c'est-à-dire une mesure réelle déjà faite. Il aurait fallu deux passages de
> plus pour retrouver ce que l'on savait déjà.
>
> L'historique s'amorce désormais sur ce score stocké. **On ne fabrique
> rien** : on lit ce qui est écrit, exactement comme pour `concluante`.
>
> C'est le quatrième champ dérivé de cette nuit à se révéler faux avant d'être
> juste — après le détail perdu à l'écriture, `concluante` jugé sur l'adresse,
> et `stable` vrai dès la première passe. Le motif est constant : **le calcul
> était juste, la donnée qu'il lisait ne l'était pas.**

### Le pool confirmé sur deux mesures — et le code le savait déjà

| membre du pool local | verdict ×2 | ce qui manque |
|---|---|---|
| `codestral-local` | **4/4** | — |
| `llama3.2-3b-local` | **4/4** | — |
| `deepseek-coder-33b-local` | **3/4** | **parle le protocole `/v1/messages`** |
| `phi3-mini-local` | **1/4** | les trois épreuves d'outils |

> **Chaque verdict tient sur deux mesures identiques.** Ce n'est plus une
> impression tirée d'une passe unique : la moitié du pool qui sert
> l'orchestration est *confirmée* incapable de l'assurer.
>
> **Plus grave que je ne le croyais.** `deepseek-coder-33b` échoue sur
> « parle le protocole `/v1/messages` » — l'API que Claude Code emploie — et
> c'est l'un des **deux seuls modèles sur vingt-cinq** dans ce cas. Un modèle
> qui ne parle pas le protocole n'est pas une relève dégradée : **il n'est pas
> une relève**. Je l'annonçais en échec sur les outils ; la mesure dit autre
> chose, et pire.
>
> **ET LE CODE LE SAVAIT DÉJÀ.** Les deux modèles portent, en commentaire à
> côté de leur nom dans les profils de `server.js`, la mention `outils=non` :
>
> ```
> profil coding  : deepseek-coder-33b-local   // 3,9 s, outils=non
> profil rapide  : phi3-mini-local            // 2,5 s, outils=non
> ```
>
> Le fait était **écrit**, et il n'agissait pas. §0.2.1 dans sa forme la plus
> nue — une règle non mécanisée ne protège personne, pas même celui qui l'a
> écrite. Les épreuves confirment ce que le commentaire annonçait, et
> ajoutent ce qu'il ne disait pas : l'échec de protocole.
>
> **Je ne retire toujours personne.** La décision reste à l'opérateur, pour la
> même raison qu'il y a deux heures : rien ne mesure ce que coûterait
> l'exclusion, et un modèle incapable d'orchestrer peut parfaitement résumer
> ou compléter du code. Ce qui a changé, c'est que le constat repose désormais
> sur **deux mesures par modèle**, corroborées par les commentaires du code.

### La vague qui produit — 41 défauts, 4 correctifs appliqués — 31/08

| état du reste-à-faire | nombre |
|---|---|
| **déjà corrigé** | **18** |
| corrigeable | 14 |
| pas un défaut | 5 |
| introuvable | 3 |
| trop risqué | 1 |

> **55 agents, 41 défauts rouverts dans le code actuel, 6 min 30.** Près de la
> moitié du reste-à-faire était **périmée**, et cinq entrées n'étaient pas des
> défauts : ce fichier décrivait un dépôt qui n'existe plus.
>
> **L'étape de vérification a payé son écot.** Le patch M5 était marqué
> applicable — occurrence unique, syntaxe valide — et son vérificateur
> écrivait « BREAKAGE CRITIQUE » : il déplace les vecteurs dans un fichier
> séparé sans toucher `loadIndex`, donc `nexus_search` cesserait de
> fonctionner.
>
> **Mais mon propre filtre était faux, deux fois.** D'abord il ne regardait
> que l'applicabilité et **ignorait le champ `effet_de_bord` que j'avais
> pourtant demandé** — appliquer les « prêts » tels quels aurait cassé la
> recherche. Puis, corrigé, il cherchait le mot d'alarme n'importe où et
> écartait « Aucun identifié. Le patch supprime un cas spécial **sans
> casser** aucun appelant » — une absence d'effet de bord prise pour une
> alarme, parce que le mot figurait dans une négation. Le verdict se lit en
> **tête** de phrase.
>
> **Appliqués** : `M2` le MAP-REDUCE qui dégénérait en concaténation, `K2`
> une fonction jamais appelée, `P6` une empreinte mal titrée, `K1` un dernier
> recours périmé. Un cinquième refusé à l'écriture — doublon dont le texte
> avait déjà été remplacé, occurrences réelles = 0. **Le recomptage final
> appartient à qui écrit**, jamais au contrôle qui l'a précédé.
>
> Vérifications : 75 cas de test, zéro échec ; `Test-NexusConfig` valide ;
> LOI 1 sans régression.

### Le lot ne rendait rien avant la fin — et un fichier vide mentait

> Signalé par une session voisine, et le défaut était ici. `nexus_agent --lot`
> accumulait tout en mémoire : une interruption perdait **tout le travail déjà
> payé**, et un fichier de sortie vide se lisait comme « rien ne se passe »
> alors que douze réponses avaient été servies. J'ai moi-même conclu trop vite.
>
> `--sortie` écrit une ligne JSON **dès qu'une tâche aboutit**, et l'avancement
> va sur stderr — jamais sur stdout, qui porte le rapport.
>
> **Un défaut de ma manœuvre, noté parce qu'il a failli passer** : mon premier
> correctif portait deux modifications, et son assertion sur la seconde a
> échoué **avant l'écriture**. Seule l'option a été posée, pas le comportement
> — une option documentée qui ne faisait rien. **Un patch qui échoue à
> mi-chemin est plus dangereux qu'un patch qui échoue tout net.**

### La documentation Python absorbée, et ce qu'un linter a vu en une seconde

| Sujet | Statut | Ce qui le garde |
|---|---|---|
| Documentation Python officielle | `FAIT` | `controle_doc_python` + annonce à chaque reprise de session |
| Un drapeau mort maintenu à 9 endroits | `FAIT` | retiré ; `ruff` échoue s'il revient |
| Une option documentée sans effet | `FAIT` | son aide dit désormais « sans effet » |

> **166 507 symboles** sur 63 couches, ancrés sur les versions *réellement
> installées*. Repris du dépôt voisin par **copie**, jamais par dépendance à
> son chemin.
>
> « Toujours en contexte » ne veut pas dire *chargé* : le corpus fait 136 Mo,
> et l'index à offsets lit l'entrée demandée par `seek`. Mesuré sur
> `subprocess.run` : **1 114 octets, ~280 jetons**, signature et version
> d'ancrage comprises — moins cher que relire trois lignes de code.
>
> **L'index a été RECONSTRUIT et non copié** : des offsets ne survivent pas à
> un changement de fichier, et les recopier aurait produit un index qui ment.
> 201 offsets relus par `seek`, tous concordants.
>
> La règle qu'elle sert vient d'une panne réelle chez le voisin : un `axis`
> refusé par `scipy.stats.bootstrap`, un `TypeError` avalé par un `except`,
> et le tout présenté comme une **impossibilité statistique**. Un résultat
> scientifique faux, né d'un défaut de signature.

### Ce qu'un linter a vu que des heures de vagues n'avaient pas vu

> **`ruff`, une seconde, onze défauts** — et deux n'étaient pas des scories.
>
> **`backup_gere`** était initialisé puis mis à `True` dans **huit branches**
> de `nexus_essaim.py`, et lu **nulle part**. Le `finally` consulte
> `promotion_en_cours`, et son commentaire explique le changement. Le refactor
> a changé la condition et laissé neuf assignations derrière lui : un lecteur
> y voit un drapeau qui compte, et se trouve **invité à rebrancher la
> régression que le commentaire dit avoir corrigée**.
>
> **`--etat`** était déclaré dans `nexus_verrou_machine.py`, cité dans l'usage,
> et jamais consulté. C'est le défaut que j'ai moi-même commis deux heures
> plus tôt avec `--sortie`. Conservé — un appelant pourrait le passer — mais
> son aide dit maintenant la vérité.
>
> **La distinction qui manquait.** J'avais *écarté* cette nuit un détecteur
> général de noms non définis, faute de linter, en invoquant la règle « stdlib
> seule ». Elle vaut pour les **gardes**, pas pour l'**outillage d'audit**.
> L'environnement UV lève la contrainte sans salir le dépôt.

### Point d'étape du 30/08 au soir — ce qui a été tranché

| Sujet ouvert | État |
|---|---|
| Ne jamais fournir les fichiers originaux au MCP | **FERMÉ des deux côtés** : `test_isolation` 8/8 pour l'essaim, `controle_pont_lecture_seule` pour le pont |
| Tout mécaniser, ne rien oublier dans les câblages | **FERMÉ** : `nexus_cablage.py` (cliquet par nom) lancé par le rituel, geste 6 |
| Récolte des worktrees | **FERMÉ** : le rituel appelle `nexus_worktree.py --lister`, et a trouvé un arbre oublié le jour de sa pose |
| Récupérer verbatim ce que les agents laissent | **FERMÉ** : `nexus_verbatim.py`, câblé dans `appeler()`, 7/7, vérifié par un appel réel |
| Le repli `anthropic → local` fonctionne-t-il ? | **VÉRIFIÉ pour la première fois** : `attempted-fallbacks: 1`, `api_base` local, réponse servie. §108 tient en conditions réelles |
| Chaque worker dans un worktree isolé | **partiel** : la copie est hors du dépôt, mais c'est un répertoire, pas un worktree git. Dit plutôt que coché |
| Préserver le contexte de l'orchestrateur | ouvert : mesurable par `nexus_savings`, mais aucun contrôle par tour |
| 9 appels Anthropic sur 9 échouent | **mieux caractérisé, non résolu** — voir ci-dessous |
| `Start-Claude.ps1` jamais exécuté de bout en bout | ouvert : le lancer démarre une session Claude, ce qui ne se teste pas à la légère |
| Meta-learner, harnais, AST, températures | chantiers de recherche, non défauts. Ouverts délibérément |

> **Le repli masque la cause, et c'est le vrai constat sur Anthropic.** Un
> appel à `adaptive-router-anthropic` rend **200** — servi par
> `glm-4.7-flash`, en local. Le routeur avait choisi `claude-sonnet-5`,
> `attempted-fallbacks: 1` : l'appel Anthropic a échoué et le repli l'a
> rattrapé. Même en appelant l'alias `claude-sonnet-5` directement, le repli
> intercepte. La clé est posée (108 caractères), donc la cause est ailleurs —
> et pour la lire il faut désactiver temporairement le repli.
>
> Deux choses en découlent. La bonne : §108 est vérifié en conditions
> réelles, ce qui n'avait jamais été fait — pas de fuite, pas d'échec visible.
> La gênante : un appelant qui demande Claude reçoit du local **sans le
> savoir**, et seul l'en-tête le dit. C'est conforme au contrat (« un repli
> est subi, jamais choisi ») mais mérite d'être su.

### Vérifications jamais faites

| Sujet | État |
|---|---|
| `Start-Claude.ps1` | `OUVERT` — corrigé, **jamais exécuté de bout en bout** |
| Suite complète après tous les changements | `OUVERT` — trois lancements interrompus ; dernier état connu 24 PASS, 0 FAIL |
| 9 appels Anthropic sur 9 échouent | `OUVERT` — le plan de dernier ressort ne répond pas. Non testé par appel réel : ce serait facturé. |

---

## Reprise immédiate — à lire en premier dans une nouvelle session

Trois commandes suffisent à savoir où l'on en est. Aucune ne suppose quoi
que ce soit :

```powershell
python scripts/nexus_conformite.py    # peut-on démarrer ? et sinon, pourquoi
python scripts/nexus_releve.py        # le local remplace-t-il l'orchestrateur ?
python scripts/nexus_pull_host.py     # ce qui manque encore, relançable
```

**La seule action qui vous revient** : approuver le serveur MCP
`nexus-local` au démarrage de `claude` dans ce dossier. Tant qu'il est en
`⏸ Pending approval`, l'orchestrateur lit les fichiers lui-même — sur
l'abonnement — au lieu de les faire lire gratuitement en local. C'est le
plus gros levier d'économie encore fermé.

**Deux secrets à faire tourner**, passés en clair dans une conversation :
la clé Ollama Cloud (ollama.com) et un jeton GitHub.

**Travailler gratuitement**, en arbre isolé, sans toucher l'arbre principal :

```powershell
python scripts/nexus_worktree.py --fichiers <cible.py> `
    --consigne "..." --modele qwen3-coder-30b-local
python scripts/nexus_worktree.py --fusionner <nom>   # retenir
python scripts/nexus_worktree.py --jeter <nom>       # jeter
```

Ce que valent réellement ces relectures est mesuré dans
[`EVALUATION-LOCALE.md`](EVALUATION-LOCALE.md) : **5 propositions retenues
sur 15**, et **3 des 10 rejets auraient introduit une panne**. La règle qui
en découle : le local détecte, l'orchestrateur arbitre — et l'analyse d'un
modèle ne garantit pas que son diff porte sur la même chose.

---

## 0. Objectif directeur

Trois exigences, dans cet ordre :

1. **Économiser ~93 % de l'abonnement Claude** — déléguer le volume au local
   et au cloud, ne payer que le raisonnement.
2. **Rester opérationnel sans abonnement** — un modèle local doit pouvoir
   remplacer l'orchestrateur dès l'expiration ou le dépassement de quota.
3. **Plateforme multi-tâche et multimodale, sans limitation** — y compris un
   contexte effectif de 1 M, obtenu par distribution.

Contrainte transverse : **contraintes machine opposables**, acceptation ou
rejet automatique selon CPU, GPU, RAM et disque.

---

## 1. Migration du moteur hors de Docker

**Migration terminée.** Le moteur sert depuis l'hôte, le volume Docker
est supprimé, le disque virtuel est compacté.

| # | Sujet | Statut | Preuve |
|---|---|---|---|
| 1.1 | Plan de migration chiffré | `FAIT` | `model_list.host.txt` |
| 1.2 | Bascule du moteur | `FAIT` | `x-litellm-model-api-base: http://host.docker.internal:11434` sur une inférence réelle |
| 1.3 | Téléchargement sur l'hôte | `FAIT` | 19 téléchargés, 0 échec |
| 1.4 | Vérification post-bascule | `FAIT` | forward 11/0, reverse 15/0, policy 5/0, relève 5/0 |
| 1.5 | Suppression du volume Docker | `FAIT` — irréversible | 541 Go, après vérification que les 17 modèles restants sont publiés au registre |
| 1.6 | Compaction du disque virtuel | `FAIT` | 553 Go → 12,9 Go, **540 Go rendus** |
| 1.7 | Retéléchargement des 6 modèles reportés | `EN COURS` | `python scripts/nexus_pull_host.py` — relançable, il reprend où il s'est arrêté |

**Ce qu'il reste à voir arriver seul** : les 4 derniers modèles
(`deepseek-coder:33b`, `codestral`, `qwen2.5:32b`, `llava:34b`). Tant
qu'ils manquent, `nexus_conformite.py` marque la configuration **non
conforme**, ce qui interdit tout redémarrage — comportement voulu, la
panne étant réelle. Elle se résout d'elle-même à la fin du téléchargement.

**Deux enseignements de la compaction**, à ne pas réapprendre :

* `Optimize-VHD` seul ne libère **rien** — Windows ignore quels blocs sont
  libres dans l'ext4. Il faut `fstrim` depuis l'intérieur d'abord. Mesuré :
  553 Go avant, 553 Go après, sans erreur ;
* sans élévation, `Optimize-VHD` échoue **silencieusement** en rendant un
  code de succès. `Compact-NexusDisk.ps1` refuse donc de démarrer plutôt
  que d'abandonner le disque entre deux états.

---

## 1 bis. Critère de reproductibilité — tranché

La question n'est jamais « est-ce volumineux » mais **« existe-t-il une
source pour le reconstruire »**. Mesuré :

| Artefact | Taille | Source de reconstruction |
|---|---|---|
| `ollama_data` | **541,2 Go** | `ollama pull`, piloté par `model_list.txt` |
| images Docker | 10,7 Go | `docker pull`, déclarées dans le compose |
| `redis_data` | 9 Mo | cache — se reconstitue à l'usage, par définition |
| fichiers du dépôt | 1 Mo | git : l'historique **est** la sauvegarde |
| `.nexus/index.json` | 1 Mo | `nexus_index_build` — lent, mais refaisable |
| **`pgdata`** | **83,8 Mo** | **aucune** — dépense, sessions, clés |
| **`.git`** | **1,2 Mo** | **partielle** — un `clone` ne ramène que ce que le distant a reçu |
| **`.env`** | 1 Ko | **aucune** — exclu de git à dessein |

`.git` mérite une mention particulière : le dépôt distant existe
(`github.com/KinSushi/Claude-Local-Nexus`), mais **aucun amont n'est
configuré pour `main`**, **2 commits ne sont pas poussés**, et **40 entrées
ne sont pas commitées**. Un `git clone` ne ramènerait donc pas le travail le
plus récent — c'est-à-dire le plus coûteux à refaire.

**L'irremplaçable représente 0,015 % du volume.** 84 Mo méritent une
sauvegarde ; 552 Go n'en méritent aucune.

| # | Sujet | Statut | Détail |
|---|---|---|---|
| 1.7 | Audit reconstructible / irremplaçable | `FAIT` | `nexus_preserve.py` |
| 1.8 | Sauvegarde de l'irremplaçable | `FAIT` | Dump SQL de 18,2 Mo — lisible, comparable, restaurable sur une autre version de PostgreSQL |
| 1.9 | `backup.ps1` tentait d'archiver 541 Go | `FAIT` | Volume Ollama retiré : l'archivage aurait échoué faute de disque, et n'aurait rien préservé |
| 1.10 | Ollama sous profil Docker | `FAIT` | `COMPOSE_PROFILES=embedded` — comportement inchangé aujourd'hui, sortie en retirant une ligne |
| 1.11 | `depends_on: ollama` retiré de LiteLLM | `FAIT` | Exiger sa santé au démarrage empêcherait de tourner avec un Ollama sur l'hôte |
| 1.12 | `.env` à sauvegarder hors dépôt | `OUVERT` | **Action utilisateur** — non copié dans `backups/` à dessein : dupliquer un secret sur le même disque multiplie les endroits où il peut fuir |
| 1.13 | Historique git sauvegardé | `FAIT` | Bundle de 1,2 Mo, vérifié « complete history », clonable directement |
| 1.14 | Travail non commité sauvegardé | `FAIT` | 38 fichiers, 0,2 Mo — un bundle ne contient que ce qui est commité |
| 1.15 | Aucun amont configuré pour `main` | `OUVERT` | **Action utilisateur** — `git push -u origin main` ; sans cela le distant reste en retard de 2 commits et de tout le travail du jour |
| 1.16 | `backups/` vit sur le même disque | `OUVERT` | Protège de l'effacement accidentel, **pas d'une panne de disque**. Copier hors machine |

Reste donc dans Docker : **PostgreSQL** (seul volume irremplaçable), **Redis**
(cache, mais lié à LiteLLM et minuscule), **LiteLLM** (sa valeur est sa
configuration, versionnée). Sort de Docker : **Ollama** et ses 541 Go.

---

## 2. Limites matérielles

| # | Sujet | Statut | Détail |
|---|---|---|---|
| 2.1 | Garde-fou ACCEPT / DEGRADED / REJECT | `FAIT` | `nexus_capability.py`, câblé au générateur et au validateur |
| 2.2 | Docker plafonne le moteur à 32 Go sur 61,6 | `DÉCIDÉ` | 29 Go de la machine hors d'atteinte — motif principal de la migration |
| 2.3 | `.wslconfig` absent → WSL2 applique 50 % | `OUVERT` | Palliatif immédiat : `memory=52GB` + `wsl --shutdown` (coupe Docker) |
| 2.4 | 3 modèles inexécutables ici (163 Go) | `OUVERT` | `llama4:scout` 67 Go, `llama3.2-vision:90b` 54 Go, `llama3.3:70b` 42 Go |
| 2.5 | 4 modèles dégradés | `DÉCIDÉ` | `mixtral:8x7b`, `qwen3:32b`, `qwen3-vl:32b`, `llava:34b` — adressables, hors pools |
| 2.6 | GPU Radeon 890M via Vulkan | `OUVERT` | Non listé officiellement ; à tester sur l'Ollama natif — seul gain de vitesse structurel possible |
| 2.7 | Docker comme extension mémoire | `DÉCIDÉ` | **Mirage** pour la mémoire (la VM prélève sur la même RAM) ; **réel** pour la résidence simultanée et la continuité pendant la migration |

---

## 3. Contexte et relève

| # | Sujet | Statut | Détail |
|---|---|---|---|
| 3.1 | Profil `releve-locale` à 64K | `FAIT` | Exposé et vérifié |
| 3.2 | Coût mémoire mesuré à 64K | `FAIT` | glm-4.7-flash = 23 Go (19 poids + ~4 KV), relevé par `ollama ps` |
| 3.3 | Test réel de la relève via LiteLLM | `FAIT` | 143+208 = 351 en 61 s à 65 536 de contexte, 23 Go chargés, endpoint local prouvé |
| 3.4 | Contexte distribué (1 M par map-reduce) | `FAIT` | Éprouvé sur un corpus réel : 24 fichiers lus pour 5 464 tokens à coût nul |
| 3.5 | Modèles locaux encore à 8K | `OUVERT` | À relever après migration ; 8K est inexploitable pour une charge agentique |
| 3.6 | Distribution multi-moteur du map-reduce | `OUVERT` | Aujourd'hui séquentiel ; parallélisable une fois deux moteurs disponibles |
| 3.7 | Bascule automatique de l'orchestrateur | `PRÊT` | `Start-Claude.ps1` — relance en relève locale sur motif de quota. La bascule est **entre** deux sessions, pas au milieu de l'une |

---

## 4. Pont Claude Code ↔ modèles locaux

| # | Sujet | Statut | Détail |
|---|---|---|---|
| 4.1 | Serveur MCP `nexus-local`, 12 outils | `FAIT` | Quatre familles : exécution, contexte, modalité, inspection |
| 4.2 | Approbation du serveur dans Claude Code | `OUVERT` | **Action utilisateur** : lancer `claude` et approuver |
| 4.3 | `nexus_vision` multimodal | `FAIT` | Testé ; **llava-7b est instable** sur la même image : lecture correcte une fois, description erronée la suivante |
| 4.7 | Amorçage sur machine neuve | `PRÊT` | `Initialize-Nexus.ps1` — prérequis, secrets, profil, services, config, vérification |
| 4.4 | Index RAG sur le dépôt complet | `OUVERT` | Construit sur `docs/` et vérifié (recherche hybride pertinente) ; reste à étendre au dépôt |
| 4.8 | Profils d'exécution | `FAIT` | `coding`→releve-locale, `reasoning`→glm-4.7-flash, `rapide`→llama3.2-3b, `multimodal`→llava-7b |
| 4.9 | Reprise sur incident passager | `FAIT` | Un `socket hang up` ne jette plus une phase MAP de quinze minutes |
| 4.5 | Portabilité de `.mcp.json` | `FAIT` | `${CLAUDE_PROJECT_DIR}` — plus aucun chemin en dur |
| 4.6 | Extension à d'autres classes de tâches | `OUVERT` | Les 8 outils sont une base, pas la cible |

---

## 5. Configuration et automatisation

| # | Sujet | Statut | Détail |
|---|---|---|---|
| 5.1 | Zones AUTOGEN, générateur idempotent | `FAIT` | Test d'idempotence dans la suite |
| 5.2 | Validation bloquante avant redémarrage | `FAIT` | `Test-NexusConfig.ps1`, code 1 = pas de redémarrage |
| 5.3 | Tâche planifiée quotidienne 04:00 | `FAIT` | `Register-NexusAutoUpdate.ps1` |
| 5.4 | Anciens `update_*.ps1` neutralisés | `FAIT` | Garde-fou après incident réel de corruption |
| 5.5 | Pool cloud variable (6 → 9 modèles) | `DÉCIDÉ` | 402 écarte, 429/timeout conserve — un quota épuisé ne prouve rien |
| 5.6 | Suppression des anciens scripts | `OUVERT` | Après une période de confiance |
| 5.7 | Redémarrage LiteLLM | `FAIT` | Cycle complet rejoué, smoke test 8/8 |
| 5.8 | Health checks en boucle continue | `FAIT` | Cycles de 60 s pour un intervalle de 30 s : la sonde tournait sans arrêt et chargeait les modèles. Intervalle porté à 900 s |
| 5.9 | Validation des droits par défaut | `FAIT` | Générer sans elle remplissait le pool de modèles inexécutables |
| 5.10 | Version de politique de routage | `FAIT` | `NEXUS-ROUTER-VERSION`, empreinte des pools et des chaînes — rattache un résultat aux règles qui l'ont produit |
| 5.11 | Portabilité HTTPS du pont | `FAIT` | Le transport suit l'URL au lieu de supposer HTTP et le port 80 |

---

## 6. Vérification

| # | Sujet | Statut | Détail |
|---|---|---|---|
| 6.1 | Suite forward / reverse / policy / code | `FAIT` | 12+10+4+12 au dernier passage complet |
| 6.2 | Passage complet après les derniers changements | `FAIT` | **44/44** — forward 11, reverse 12, policy 5, code 16 |
| 6.8 | Faux négatifs corrigés dans les tests | `FAIT` | Appel d'outil vérifié avec ses arguments ; image refusée par un modèle textuel (HTTP 400, pas de description hallucinée) |
| 6.9 | Tests d'implantation | `FAIT` | Pile minimale valide sans Ollama, profil réversible, sauvegarde ciblée — **19/19** en famille code |
| 6.7 | Règle asymétrique de repli | `FAIT` | Policy 5/5 : 8 replis vers le local, aucun vers l'extérieur |
| 6.3 | Cache neutralisé dans les tests | `FAIT` | Sans quoi les tests validaient Redis, pas les modèles |
| 6.4 | Preuve de non-fuite par `x-litellm-model-api-base` | `FAIT` | Plus forte que le nom du modèle |
| 6.5 | Test Anthropic réel | `OUVERT` | Non joué : consomme des crédits API — `-IncludeAnthropic` |
| 6.6 | Langfuse configuré mais jamais vérifié | `OUVERT` | L'observabilité conditionne la mesure des 93 % |

---

## 7. Mesure de l'objectif des 93 %

| # | Sujet | Statut | Détail |
|---|---|---|---|
| 7.1 | Rapport de délégation | `FAIT` | `nexus_savings.py` — ventilation par plan et coût contrefactuel |
| 7.4 | Échantillon encore trop faible | `OUVERT` | 178 requêtes réelles, dominées par quelques grosses : le taux n'est pas encore significatif |
| 7.5 | Health checks faussaient la mesure | `FAIT` | 2552 requêtes sur 2730 étaient la sonde ; désormais exclues du rapport |
| 7.2 | Comptabiliser par plan | `OUVERT` | Les outils MCP annoncent déjà modèle, plan et coût par appel |
| 7.3 | Exploiter Langfuse pour l'agrégat | `OUVERT` | Dépend de 6.6 |

---

## 7 bis. Doctrine de repli — tranchée

La règle initiale « aucun fallback ne franchit une frontière de
fournisseur » était trop rigide : elle interdisait précisément ce qu'il
fallait obtenir, un repli vers le local quand un quota s'épuise.

Règle retenue, **asymétrique** :

| Sens | Verdict | Raison |
|---|---|---|
| `cloud → local` | autorisé | ne fait perdre que de la capacité |
| `anthropic → local` | autorisé | idem, et évite l'interruption |
| `local → cloud` | interdit | les données sortiraient |
| `local → anthropic` | interdit | idem, et engage une dépense |

Un repli est **subi**, jamais choisi : il ne doit ni élargir l'exposition
des données, ni décider d'une dépense à la place de l'utilisateur.

---

## 7 ter. Ce que la délégation a déjà produit

Premiers usages réels des outils, à coût nul :

| Tâche déléguée | Volume | Résultat |
|---|---|---|
| Relecture de `server.js` (38 Ko) | 12 531 tokens | 7 défauts signalés, **4 réels** et corrigés |
| Lecture des 24 notes d'architecture | 5 464 tokens | Backlog de 20 capacités décrites mais non implémentées |
| Relecture de `nexus_test.py` (40 Ko) | 12 180 tokens | Faux négatifs identifiés dans 3 tests, corrigés |

Enseignement : la délégation trouve de vrais défauts, **et se trompe aussi**.
Sur les sept points du premier retour, trois étaient infondés — un `||` jugé
dangereux qui fait ce qu'il doit, une boucle infinie impossible, un
compteur mal analysé. Le rendement vient du tri, pas de l'acceptation.

---

## 8. Dettes et vigilances

- **Faux positifs `:latest`** dans le validateur — corrigés, à surveiller.
- **`nexus_test.py` déplace la configuration** le temps d'un test ; une
  récupération automatique existe, mais l'opération reste sensible.
- **Deux moteurs Ollama actifs simultanément** (Docker et hôte) : état
  transitoire acceptable pour la migration, à ne pas laisser s'installer
  sans décision.
- **`llava-34b` et assimilés** sortis des chaînes de fallback par le
  garde-fou : à réévaluer après la migration, la mémoire changeant.
