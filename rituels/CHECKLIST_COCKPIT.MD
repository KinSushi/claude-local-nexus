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

---

## 9. Tour du 31/08 — le plan payé, et quatre détecteurs qui se taisaient

### 9.1 Ce qui est FERMÉ — un contrôle échoue désormais si la règle est enfreinte

| Ce qui était faux | Mesure | Le contrôle qui garde |
|---|---|---|
| Le garde des sous-agents ne surveillait que `Agent` ; `Workflow` ne l'était par rien | **460 sous-agents, 32 119 213 jetons facturés** en huit vagues, contre 475 000 déjà cités comme « l'inverse du but » | matcher `Agent\|Workflow`, `nexus_test.py --only plan`, 8 cas |
| Le garde n'exigeait que l'EXPLICITE : ses quatre modèles connus sont tous facturés, nommer `haiku` suffisait à passer | La règle centrale du dépôt — banc gratuit d'abord — n'était mécanisée **nulle part** | refus sauf `NEXUS_AGENT_LIBRE=1` ou `NEXUS_JUSTIFIE_PAYANT <motif>` |
| Le refus s'imprimait et **ne bloquait rien** : code 0 au lieu de 2 | 3 refus sur 3 traversaient | `epreuve_garde_plan.py`, cas « un REFUS sort en 2 » |
| Le rempart `except BaseException` **avalait le refus** : `SystemExit` en est une | idem | code calculé hors du `try` |
| Le cliquet de câblage comptait en RÉGRESSION la première épreuve Python du dépôt | il punissait le mécanisme que le contrat 0.2.1 exige | `nexus_test.py --only cablage`, 4 cas, dont 3 garde-fous |
| L'outillage annonçait « 0 violation » à trois étages superposés | **108 violations réelles** invisibles : ruff 91, PSScriptAnalyzer 17 | `nexus_outillage.py --cliquet`, câblé au rituel |
| La traque cherchait un refus écrit en MOTS ; celui du garde était écrit en DONNÉES | classes 5 et 6 à **0** pendant que le trou coûtait 32 M de jetons | motifs A et B, éprouvés par sonde |

### 9.2 La leçon du tour, et elle est unique

**Aucun de ces sept défauts ne se voyait à la lecture.** Tous ont été
trouvés en EXÉCUTANT — en soumettant au détecteur le cas qu'il devait
attraper. Deux détecteurs ont même été corrigés à faux d'abord :

* le motif du rempart exigeait une constante là où le cas réel portait un
  appel (`sys.exit(main())`) — il ratait précisément ce pour quoi il
  existait ;
* le motif du refus structurel, élargi à la fonction englobante, accusait
  un chemin de SUCCÈS.

Un détecteur qui crie sur du code juste finit désarmé, et emporte ses
vraies détections avec lui. La contre-épreuve n'est donc pas un
supplément : c'est la seule preuve qu'un silence veut dire quelque chose.

### 9.3 Ce qui reste OUVERT — aucun contrôle ne le garde encore

* **Les 108 violations ne sont pas arbitrées.** Un linter signale, il ne
  juge pas. Parmi elles des classes de vrai bug : `B023` (fonction ne
  capturant pas la variable de boucle), `B904`, `B905`. Le cliquet
  empêche qu'elles augmentent, rien n'exige qu'elles baissent.
* **`eslint` n'est pas provisionné** (npm hors du PATH). Il le DIT, mais
  le JavaScript du pont n'est donc mesuré par personne — et c'est là que
  vivent les 11 constats de la vague JS, toujours non arbitrés.
* **Trois scripts « mieux câblés »** (`nexus_ruche`, `nexus_worktree`,
  `nexus_test_outillage`) apparus sans que la cause soit établie. La
  référence n'est pas rebaselinée tant qu'on ne sait pas pourquoi.
* **Le garde ne couvre que les deux outils qui lancent aujourd'hui.** Un
  troisième, demain, serait à nouveau aveugle. Rien ne surveille
  l'apparition d'un lanceur.
* **Le matcher élargi n'est pas prouvé in vivo** : les hooks se chargent
  au démarrage de session. La preuve tenue est mécanique — l'épreuve et
  le contrôle de conformité exercent le garde — pas encore vécue.
* **40 sauvegardes résiduelles** dans `scripts/.nexus/`, signalées en
  ALERTE à chaque passage de la porte. Données de l'opérateur.

---

## 10. Tour autonome — les trois plans mesurés, et une hypothèse réfutée

### 10.1 Fermé

* **`eslint` provisionné.** Trois défauts empilés l'en empêchaient, les
  mêmes classes que pour `ruff` : `npm` appelé sans `.cmd`, une
  configuration au format `.eslintrc` que la version installée (**10.9.1**)
  ne lit plus, et un drapeau `--no-eslintrc` supprimé. Les 2500 lignes du
  pont MCP n'avaient **jamais** été regardées par un outil.
* **Les trois plans ensemble** : ruff 91, eslint 11, PSScriptAnalyzer 17.
* **Le cliquet distingue « jamais mesuré » de « aggravé ».** Il annonçait
  « 2 RÉGRESSION(S) » sur un outil qui venait d'être branché. Faux : la
  dette était là, personne ne la voyait. Et la confusion forçait un
  `--rebaseline` alors indiscernable d'une dégradation réellement assumée.
* **Trois `catch` du pont jetaient la cause** de l'échec qu'ils
  rapportaient — la classe 1 de `nexus_traque`, écrite en JavaScript.
  eslint 11 → 8, les quatre épreuves du pont passent.

### 10.2 Arbitrage des onze constats JavaScript

Un linter signale, il ne juge pas. Sur onze : **trois** vrais défauts
(corrigés), **trois** faux positifs ou intentionnels, **cinq** requalifiés.

Le `group` de `mapReduce` est un faux positif net : `flush()` est attendu
dans une boucle `for...of` séquentielle, deux `flush` ne se chevauchent
jamais. La règle est statique et ignore l'ordonnancement.

**L'hypothèse commode, et sa réfutation.** Cinq `require-atomic-updates`
décrivent une ruée sur le cache. Il était tentant d'y voir la cause de la
lenteur du pont mesurée cette session — **>120 s contre 10,6 s en
direct**. L'arithmétique la refuse : `CACHE_MS` vaut 60 s et le sémaphore
borne la concurrence à 1 local / 4 cloud, soit au plus ~5 requêtes
`/v1/models` en double **par minute**. Négligeable devant 120 s par appel.

**La lenteur du pont reste donc mesurée et inexpliquée.** L'écrire vaut
mieux que de laisser une explication plausible tenir lieu de mesure.

### 10.3 Ouvert, et nommé

* **Le cliquet ne RESSERRE pas.** Il enregistre l'amélioration (eslint
  5 → 2) mais laisse la référence à 5 : un retour à 4 passerait. Un
  cliquet qui ne resserre est un seuil. `nexus_cablage.py` porte le même
  trou, et la raison en est probablement bonne — écrire la référence
  pendant le rituel salirait l'arbre au moment même où le rituel vérifie
  qu'il est propre. **Question posée, non tranchée seul.**
* **Le `B023` de `nexus_validate.py` n'est pas un défaut** : la fermeture
  est consommée dans la même itération. Mais `graph` est **réaffectée huit
  lignes plus bas dans la même portée** — inoffensif aujourd'hui,
  silencieux demain. Liaison explicite à envisager.
* **Les 88 violations Python et 17 PowerShell restantes** ne sont pas
  arbitrées. Le cliquet empêche qu'elles augmentent ; rien n'exige
  qu'elles baissent.
* **La lenteur du pont MCP** — mesurée, inexpliquée, hypothèse principale
  réfutée ci-dessus.

---

## 11. Documentation shell absorbée, et « conclure sans avoir vu »

### 11.1 Absorbé par copie, jamais lu en place

`references/shell_docs/` (61 primitives bash, 306 cmdlets PowerShell) et
`references/lecons/` (306 leçons, erreurs, remèdes), depuis le dépôt voisin.
Index à offsets déjà construits, de même forme que celui bâti ici pour
Python : on ne les reconstruit pas, on les **vérifie** — 25 offsets relus par
`seek`, zéro discordance.

Une seule entrée : `nexus_doc.py <symbole>` répond désormais pour `New-Item`,
`trap` et les leçons. Le compte affiché à la reprise est **dérivé**
(166 507 Python + 673 annexes) et non plus récité en dur.

Le dépôt porte dix-sept scripts PowerShell et a déjà payé deux fois la règle
« ne jamais écrire de mémoire » : `pwsh -File` passe tout en arguments,
`New-Item -Force` tronque un fichier existant. Deux faits d'une ligne, qu'aucune
documentation locale ne portait.

### 11.2 Cinq défauts, tous trouvés en CONSULTANT

| Ce qui était faux | Effet |
|---|---|
| le `code` d'un exemple est une **liste**, `notes` une **chaîne** | `New-Item` levait `TypeError` ; la rubrique notes ne s'affichait jamais |
| une leçon n'a **aucune clé `type`** (sa nature est dans `methode`) | rendu **vide** sous un en-tête normal, 1888 octets juste dessous |
| le tri LOCALFIRST triait la liste **entière** au lieu de départager à rang égal | `trap` rendait `scipy.stats.BootstrapMethod` — défaut **antérieur** à ce tour |
| `console_tools` importé dans un `try/except` alors que **le module n'existait pas** | le forçage UTF-8 promis depuis le 2026-08-10 n'avait **jamais** tourné |
| mon propre `try` enveloppait le `print` | `UnicodeEncodeError` dérive de `ValueError` : une console cp1252 faisait rapporter « ENTRÉE ILLISIBLE » sur une entrée lisible |

### 11.3 Conclure sans avoir vu — deux étages, la même faute

Échange avec la session voisine. Elle a rapporté, puis **rétracté**, un défaut
de `nexus_summarize` : `fusionner:true` fusionne des **résumés**, jamais les
fichiers, et c'est documenté. Sa rétractation est juste.

Ce qui est corrigé ici est autre chose, et mesuré :

* **la fusion inventait** — deux résumés d'une ligne, et des paragraphes
  d'inférence en sortie (« semblent être liés à la gestion de données »).
  Réduire du contexte est le but ; composer ce qu'on n'a pas ne l'est pas.
* **l'étage par fichier concluait sur ce qu'il ne voyait pas** — il recevait
  la consigne entière avec « si une information est absente, tu le dis », en
  ne voyant qu'un fichier sur N. D'où des « absent » **faux** sur ce qui
  existait à côté, hérités ensuite par la fusion. C'est la cause amont, et
  elle a coûté à la session voisine trois diagnostics successifs.

Le remède n'est pas de tout donner à chacun — ce serait renoncer au découpage
qui fait tenir le contexte — mais de **dire à chacun ce qu'il ne voit pas**.

### 11.4 Le compte est nécessaire, il n'est pas suffisant

Le cliquet de câblage déclarait orphelin tout module Python, puisqu'un module
s'importe **sans son extension**. Corrigé — et le correctif ouvrait aussitôt
un piège que la session voisine a nommé à l'instant même :

```
from models.gguf_vram import estimate_gguf_vram_mb  # noqa: F401
```

Un import inutilisé ferait passer un module d'orphelin à câblé **sans que le
produit change**. Le chiffre bouge, rien n'est joint. Un import ne compte
donc que s'il est **employé** hors de sa propre ligne.

### 11.5 Ouvert

* **P3 du rapport voisin, et il est à moi** : 37 replis cloud → cloud sur un
  **quota unique** (même compte ollama.com), contre 4 vers le local. Un 429
  ne peut pas être rattrapé par un alias qui partage la ressource épuisée :
  le repli triple la charge qui a causé le refus. Le validateur refuse déjà
  qu'un modèle replie sur lui-même ; il lui manque de savoir que **tous les
  alias d'un même compte sont un seul amont**. Mesuré côté voisin : 40
  connexions sortantes pour 3 appels clients, 46 refus en 5 min.
* **P2** : `nexus_index_build` expire à 180 s sur cet hôte sans GPU, donc
  `nexus_search` est hors service — alors que `nexus_savings` le cite en tête
  des leviers de rendement. Le modèle d'embedding n'a **aucun repli déclaré**.
* **P4** : six familles sur neuf rendent vide à 2 200 jetons demandés ; la
  bascule sauve le travail mais **détruit la décorrélation des familles**, et
  seule la ligne BASCULE le dit.
* Les 88 violations Python et 17 PowerShell restent non arbitrées.
* Le cliquet **ne resserre toujours pas** (question posée au §10.3).

---

## 12. P0 — la sonde du pont rendait SUCCÈS sur ses propres échecs

Signalé par la session voisine, reproduit ici avant toute correction.

| Cas | Sortie | Code avant | Code après |
|---|---|---|---|
| fichier hors dépôt | `(refuse : hors du depot)` | **0** | 1 |
| fichier inexistant | `(introuvable)` | **0** | 1 |
| délai expiré | `ERROR: timeout expired after 60s` | **0** | 1 |
| résumé réel réussi | en-tête + contenu | 0 | 0 |

**Cause** : `_probe_success` ne testait que des **préfixes** de la sortie
entière. Or le pont écrit son en-tête, puis `## Par fichier`, puis le corps —
le marqueur d'échec est *toujours* au corps. Et le `startswith(" [ERREUR]")`,
avec son espace initial, n'a probablement jamais été vrai une seule fois.

Un garde dont le vert ne signifie rien est pire que pas de garde : il consomme
de l'attention et confère une fausse assurance.

**Le piège symétrique, refusé au brouillon.** Chercher les marqueurs n'importe
où aurait condamné tout résumé d'un fichier qui *parle* de délais — plusieurs
fichiers d'ici sont dans ce cas. Les marqueurs sont donc cherchés **en début
de ligne**, et seule la phrase que la sonde émet elle-même compte. Et une
regex proposée exigeait des **tirets** comme séparateurs là où le pont écrit
un **point médian** — elle n'aurait jamais rien reconnu, se comportant
exactement comme le défaut qu'elle devait corriger.

**Second défaut, trouvé en vérifiant que le SUCCÈS passait encore — il ne
passait plus.** Le délai de la sonde porté à 900 s, mais le serveur se ferme
seul après `NEXUS_GRACE_MS`, 120 s par défaut :

```
[nexus-local] fermeture forcee : 1 appel(s) toujours en vol
ERROR: aucune reponse
```

Deux budgets indépendants que **rien** ne faisait s'accorder : porter l'un
sans l'autre fabriquait une panne à partir d'un réglage. La sonde transmet
désormais son délai au serveur.

**Épreuve** : `epreuve_sonde_mcp.py`, 10 cas, câblée en `--only sonde`. Preuve
positive : jouée contre le code d'avant, elle échoue sur les cas 1 à 3 et ne
compile pas le cas 7.

### 12.1 Ce que cet échange a montré, au-delà du défaut

Trois rapports successifs de la session voisine, dont **deux rétractés par
elle-même** — et les deux rétractations étaient justes. Ce qui les a produits :
une clause d'échappement dans une consigne (« si vide, dis VIDE ») est plus
facile à satisfaire qu'une tâche, d'autant plus que la consigne s'allonge. Le
modèle prenait la porte offerte.

Ce qui restait après tri était réel, et de mon côté : un vert qui ne signifie
rien, et deux étages qui concluaient au-delà de ce qu'ils voyaient.

---

## 13. P3 vérifié plutôt que repris — et le chiffre ne tenait pas

### 13.1 La vérification change la conclusion

Le rapport voisin annonçait **37 replis cloud → cloud** contre 4 vers le local.
Compté dans la configuration réelle, sur 108 arcs :

| Direction | Arcs |
|---|---|
| `local → local` | 72 |
| `cloud → local` | **20** — la bonne direction |
| `anthropic → local` | 4 |
| `anthropic → anthropic` | 3 |
| `cloud → cloud` | **2** — et tous deux sur `adaptive-router-cloud` |

Deux, non trente-sept, et les deux appartiennent au **routeur**, dont c'est la
définition d'avoir des candidats cloud. Le chiffre décrivait très probablement
l'état d'avant le correctif d'amplification posé plus tôt dans cette session.

L'analyse est un signal, jamais une preuve (§112.4). Ici elle ne tenait pas —
et le dire vaut mieux que corriger un défaut qui n'existe plus.

### 13.2 La préoccupation, elle, tenait — et rien ne la gardait

Le validateur contrôle la **direction** des replis en comparant des
**domaines**. Or `cloud → cloud` a le même domaine des deux côtés : la
comparaison `src != dst` est fausse et la règle ne se déclenche **jamais**.

Tous les modèles Ollama Cloud partagent un compte, donc un plafond. Un 429 ne
peut pas être rattrapé par un alias qui partage la ressource épuisée : le repli
**triple** la charge qui a causé le refus. Le validateur refusait déjà qu'un
modèle se replie sur lui-même ; il lui manquait de savoir que deux alias d'un
même compte tombent ensemble tout autant.

**Cliquet, non réparation** : zéro cas hors routeur aujourd'hui. Le contrôle ne
corrige rien, il empêche le retour d'un état qui a réellement existé.

**Non touché, et signalé** : les 3 arcs `anthropic → anthropic` relèvent du même
raisonnement, mais §17 prescrit explicitement le repli dans la famille
Anthropic. Changer cela serait une décision de doctrine, pas une correction.

### 13.3 Deux défauts nés d'une vérification, pas d'un audit

En vérifiant en vivo le correctif de fusion :

* **la synthèse ne synthétisait plus.** En serrant contre l'invention, j'avais
  supprimé sa raison d'être — « dégage ce qui relie les fichiers ». Elle rendait
  une reconcaténation quasi mot pour mot, ~7 000 jetons pour redire ce qui
  figurait juste au-dessus. La distinction juste n'est pas « ne rien ajouter »
  mais « n'ajouter aucun **fait** ».
* **la sonde n'exerçait que le plan le plus lent.** Elle ne pouvait pas choisir
  son modèle et prenait toujours `glm-4.7-flash-local` : résumer deux fichiers
  ordinaires a dépassé **dix minutes** sans GPU, quand le cloud rend en quinze
  secondes. La seule sonde du dépôt expirait donc avant d'avoir rien exercé —
  cause plausible des « pannes du pont » rapportées alors que le pont
  travaillait. `NEXUS_PROBE_MODEL` ouvre le choix ; le défaut reste **local**.

### 13.4 Reste du rapport voisin

* **P2** — `nexus_index_build` expire à 180 s sur cet hôte sans GPU, donc
  `nexus_search` est hors service. Une part est mécanisable tout de suite : le
  modèle d'embedding **n'a aucun repli déclaré**, et cela se vérifie.
* **P4** — six familles sur neuf rendent vide à 2 200 jetons ; la bascule sauve
  le travail mais détruit la décorrélation des familles, et seule la ligne
  BASCULE le dit.

* **Le cliquet a mordu son auteur une troisième fois** le même jour, sur
  l'épreuve du quota écrite une heure plus tôt : deux `io.open` sans
  gestionnaire de contexte et un `except OSError: pass`. Réparé, jamais
  rebaseliné — une dégradation assumée le jour de la pose viderait le cliquet
  de son sens.

---

## 14. Chaud contre froid — la mesure qui invalide trois conclusions

L'opérateur a posé la règle : **ne pas conclure « le cloud est plus rapide »
sans distinguer un modèle résident d'un modèle froid.** Appliquée, elle a
démoli trois affirmations que j'avais écrites le jour même.

| Mesure | À froid | À chaud |
|---|---|---|
| 32 embeddings, `all-minilm` | **HTTP 408, 180,3 s** | **2,90 s** puis 0,26 s |
| sonde `summarize`, plan local | **233,8 s** | **60,9 s** |

**Ce qui était faux, et que j'avais écrit :**

* « Un lot de 32 embeddings coûte 127 s, soit 71 % du plafond » — lecture
  **contaminée par un chargement partiel**. Le coût réel est de 3 s. J'avais
  rapetissé le lot de 32 à 16 : inutile, puisqu'un lot de **un** expirerait
  identiquement sur un modèle froid.
* « La sonde locale met dix minutes là où le cloud rend en quinze secondes » —
  attribuait au **plan** ce qui était un **chargement de poids**.

C'est mot pour mot l'erreur que le contrat documente en **§112.3**, recommise
par la main qui l'avait relue le matin même. Le remède, lui, était déjà dans
le dépôt : `nexus_bench.py` réveille le modèle sur un budget séparé avant de
mesurer. `buildIndex` le fait désormais aussi.

**Résultat : `nexus_search` est de retour** — 63 fichiers, 969 extraits, là où
l'indexation expirait. Le levier que `nexus_savings` cite en tête des trois
était hors service.

### 14.1 L'index fusionne au lieu d'écraser

Signalé par la session voisine : indexer `src/host` puis `src/compute` faisait
**disparaître** src/host, sans un mot.

Et la fusion naïve aurait été pire : les chemins étaient relatifs à la
**racine d'indexation**, donc `src/host/broker.py` devenait `broker.py` —
indiscernable d'un homonyme ailleurs. Les chemins s'ancrent maintenant sur la
racine du dépôt. Deux gardes : un **modèle** différent fait remplacer (des
vecteurs de deux espaces ne se comparent pas), un **format** antérieur aussi,
et les deux le disent.

Mesuré : 969 puis 1095 extraits, les deux tranches interrogeables.

### 14.2 Réponses aux quatre points du rapport voisin

| Point | État |
|---|---|
| sonde `exit 0` sur ses propres échecs | **corrigé**, 10 cas d'épreuve, câblé `--only sonde` |
| index qui écrase au lieu de fusionner | **corrigé**, prouvé sur deux tranches |
| délai 180 s sur les embeddings | **corrigé autrement** — ce n'était pas le délai mais le chargement ; relever le délai l'aurait masqué |
| **37 replis cloud → cloud** | **NON REPRODUIT** — comptés dans la configuration réelle : **2**, tous deux sur `adaptive-router-cloud`, contre 20 `cloud → local`. Le contrôle a tout de même été posé, en cliquet |

### 14.3 La leçon, et elle est partagée

La session voisine écrit avoir « six fois attribué à l'outil, à la machine ou
au modèle ce qui venait de son propre usage ». J'ai fait de même trois fois ce
tour, sur des mesures que je croyais propres.

Ce n'est pas un défaut d'attention : c'est que **l'instrument répond
correctement à la question réellement posée**, et qu'on lit sa réponse comme
si elle portait sur la question qu'on croyait poser. Seule une mesure en deux
phases — froid, puis chaud — sépare les deux.

---

## 15. Capacites locales elargies, et la modalite enfin ecrite

**Mission** : doter le plan local de capacites manquantes.

* Le banc a propose trois modeles pour combler les manques -- `whisper`,
  `deepseek-math-7b`, `bge-reranker-base`. **Les trois sont inventes** :
  « pull model manifest: file does not exist » pour chacun, malgre une
  consigne interdisant explicitement d'inventer un tag. Il declarait aussi
  « CATEGORIE OCR : AUCUN MODELE SUR » alors que la bibliotheque en porte au
  moins trois. Le tirage tranche ; la memoire d'un modele ne prouve rien.
* `deepseek-ocr` installe (6,7 Go), verdict materiel ACCEPT.

**Le cablage automatique, observe et non relu** : au tirage la configuration
ne bouge pas ; apres regeneration le modele est declare et marque « hors
pool : non mesure ». Il fonctionne, et la selection naturelle joue. Mais il
n'est **pas declenche par le tirage** -- il attend la tache de 04:00. Delai
nomme, pas panne.

**Defaut trouve par ce meme usage** : la modalite etait **calculee** (le bloc
ligne 866 fait deja primer `ollama show` sur le nom) mais **jamais ecrite**
sur le chemin auto-expose. Un modele de vision restait invisible aux
controles de modalite. Corrige : `mode: vision` est desormais emis, et rien
n'est ecrit quand la capacite est inconnue -- un `mode` faux serait pire
qu'un `mode` absent.

**Deux erreurs de ma part**, dites plutot que tues : j'ai affirme que
`capacites_ollama` n'existait pas alors que la commande de la meme phrase
prouvait le contraire, et conclu a la disparition d'un modele sur un
`grep -A9` dont la fenetre s'arretait une ligne trop tot. Deux fois,
l'affirmation a precede la verification.

---

## 16. Ce que six passes de délégation apprennent sur la FORME à demander

### 16.1 Les cinq pistes ML, arbitrées

| Piste | Verdict |
|---|---|
| Bandit pour le choix du modèle | **retenue, sous prérequis** — voir 16.2 |
| Optimisation bayésienne de la température | retenue, mais sa réfutation cite « une règle fixe à 0,7 serait plus stable » — or **0,7 est précisément la valeur que ce dépôt a mesurée catastrophique** : toutes les mesures inventées et une boucle de 589 s, là où 0,2 réussit en 11 s |
| Arbre de décision pour la composition du pool | **rejetée** — §106.2 a déjà tranché : sac à dos 0-1, énumération complète, optimum **garanti** en 0,00 s sur 4,5 M de combinaisons. La consigne interdisait explicitement ce type de piste ; elle a été proposée quand même |
| Quantisation INT8 via `torch.quantization` | **rejetée sur un fait** : les modèles sont des GGUF servis par Ollama, déjà quantisés — Q4_K_M et F16 vérifiés par `ollama show`. Le pipeline PyTorch n'existe pas ici |
| Apprentissage par renforcement pour l'allocation CPU | ajournée : la concurrence est déjà bornée par un sémaphore mesuré |

### 16.2 Le prérequis manque, et il est à moitié construit

Mesure décisive :

| Relevé | Comportement |
|---|---|
| `.nexus/epreuves.json` | **accumule** — `historique` de 5 entrées, compteur `mesures: 6` |
| `.nexus/latences.json` | **écrase** — une lecture par modèle, un horodatage global |

Or §106.2 le dit : sans répétitions accumulées, aucun intervalle de confiance
n'est calculable, et **toute méthode d'apprentissage optimiserait du bruit**.
Le patron existe donc dans le dépôt, appliqué à un relevé et pas à l'autre.
C'est le prérequis de toute piste ML, et il reste **ouvert**.

### 16.3 La forme de la délégation compte plus que le modèle

Six passes sur le même patch, mesurées :

| Forme demandée | Modèle | Résultat |
|---|---|---|
| diff AVANT/APRÈS | `gpt-oss-120b-cloud` | bloc AVANT **inventé**, inapplicable |
| diff AVANT/APRÈS | `gpt-oss-120b-cloud` | défaut logique : le repli par le nom **écrasait** la déclaration du moteur |
| diff AVANT/APRÈS | `gpt-oss-120b-cloud` | patchs **vides** (accents seuls), et déni d'un défaut qu'il avait lui-même écrit |
| fonctions **complètes** | `qwen3-coder-30b-local` | **Python correct**, structure juste, un seul défaut (un `None` empilé) |
| reprise | `qwen3-coder-30b-local` | **pseudo-code français** (`fonction`, `si`, `retourner`), inapplicable |
| reprise, contrainte de langage | `qwen3-coder-30b-local` | Python valide mais **structure détruite** : `historique` global au lieu de par modèle |

**Ce que cela établit** — et c'est un résultat sur la plateforme, pas sur un
modèle : les livraisons **autonomes et complètes** réussissent (fichier
entier, fonction entière) ; les **diffs verbatim** échouent, parce que le
modèle doit recopier un texte à l'identique que le découpage MAP-REDUCE lui
interdit de tenir ; et les **reprises dégradent** — chaque tour perd de la
structure du précédent.

**Conséquence pratique** : demander un livrable complet du premier coup, et
en cas de défaut **relancer à neuf** plutôt que demander une reprise.

Le choix délibéré du modèle a compté aussi : un spécialiste du code, local et
privé, a produit en 72 s ce que trois passes du plan cloud n'avaient pas
donné.

### 16.4 Et le shell a mutilé la commande qui écrivait ceci

Cette section a d'abord été perdue : un `printf` portant des accents graves a
vu le shell exécuter leur contenu (« n: command not found »). Le fichier est
resté intact et rien n'a été écrit. C'est la classe que le contrat documente
déjà — et elle vient d'être recommise par la main qui la relisait.

---

## 17. La porte qui se refermait sur ce qu'elle venait d'écrire

`nexus_vitrine.py` joue `nexus_rituel.py`, dont les contrôles régénèrent
`rituels/STATE.md`. L'arbre devenait sale **pendant** la vérification, le
contrôle « travail commité » échouait, et la publication était refusée —
alors que le même rituel, joué une seconde plus tôt, rendait « tenu ».

### 17.1 Quatre champs, trouvés un par un

| # | Champ | Pourquoi il empêchait la stabilité |
|---|---|---|
| 1 | horodatage de génération | change à chaque exécution |
| 2 | empreinte du dernier commit | **un fichier qui enregistre le commit dont il fait partie ne peut jamais être propre** : le régénérer après un commit change son contenu, et le commiter change le commit qu'il devrait enregistrer — une dérive sans fin |
| 3 | « Arbre de travail : propre / modifié » | écrire le fichier **salit** l'arbre, donc la valeur qu'il inscrit devient fausse à l'instant où il l'inscrit — une **oscillation** |
| 4 | durée de fonctionnement des conteneurs (`Up 8 hours`) | n'est **pas** auto-référentiel : il avance avec l'**horloge**. Tant qu'il comptait, le fichier ne pouvait être propre plus d'une heure |

### 17.2 La méthode qui a échoué trois fois, et celle qui a tranché

J'ai conclu **trois fois** « c'est corrigé » en lisant `git diff` — le diff
entre le fichier et sa version commitée. Il mélangeait les changements de
plusieurs passages et masquait le quatrième champ. Trois fois la vitrine a
redit non.

Ce qui a tranché : **comparer deux régénérations consécutives entre elles**,
sans passer par git. Zéro ligne différente après correction, là où l'écart
était garanti.

La leçon est générale : pour savoir ce qu'une opération change, comparer
**avant et après cette opération** — pas l'état courant à une référence qui
englobe autre chose.

### 17.3 Le remède

`ecrire_si_change` compare les contenus **après** avoir retiré les lignes
volatiles, et n'écrit **rien** quand le reste est identique — pas même à
l'identique, un simple changement de date de modification suffisant à
inquiéter certains outils. Les lignes volatiles restent écrites et lisibles ;
elles cessent seulement de décider d'une réécriture.

Le contrat §0.2 le disait déjà sans en tirer la conséquence : STATE et le
cockpit « se régénèrent sans être demandés, ce qui est précisément pourquoi
ce ne sont pas des rituels ». **Un fichier dérivé n'a pas à bloquer une
publication.**

Écrit par le banc gratuit (`qwen3-coder-30b-local`) en un seul jet complet —
la forme qui réussit (§16.3). Deux défauts d'application corrigés ici : trois
`\r` induits par une consigne ambiguë de ma part, et une coquille
`for v v in`.

### 17.4 Ce qui n'est PAS clos, et que j'ai d'abord annoncé comme clos

Cette section a d'abord affirmé « le rituel ne bloque plus sur STATE.md ».
**C'est faux, et la mesure suivante l'a démenti dans la minute.**

État réel, mesuré :

* **l'oscillation a disparu** — deux régénérations consécutives donnent zéro
  ligne différente, là où l'écart était garanti ;
* **le blocage subsiste** — juste après un commit, le fichier est réécrit
  (mtime modifié) alors que le diff ne montre que **deux lignes, toutes deux
  volatiles** : l'horodatage et l'empreinte du commit.

La cause de cette réécriture n'est **pas identifiée**. `ecrire_si_change`,
éprouvée isolément, refuse bien d'écrire quand seules des volatiles diffèrent
— et repère bien les six lignes volatiles du fichier réel. Quelque chose
diffère donc entre les lignes que `main()` construit et celles qui sont sur
le disque, sans apparaître au diff.

**La publication fonctionne** en commitant `STATE.md` juste avant — c'est ce
qui a été fait, et la vitrine est publiée et prouvée (`6635b086` des deux
côtés). Mais c'est un contournement, pas une fermeture.

### 17.5 La cause, trouvée — et aucune des trois hypothèses n'était la bonne

Les trois hypothèses posées ci-dessus (écart de lignes en fin de fichier,
normalisation d'encodage, champ invisible au diff) étaient **toutes fausses**.
Aucune n'aurait été départagée par relecture.

Ce qui a tranché : **instrumenter la comparaison pour qu'elle dise elle-même
où elle diverge**, plutôt que de raisonner dessus. Le verdict est tombé en une
exécution :

```
83 lignes proposées, 91 lignes relues
écart au rang 68
   disque  : '47 fichier(s) analyse(s)'
   proposé : '47 fichier(s) analyse(s)\n  classe 1  handler muet...\n  classe 2...'
```

**Un élément de liste n'est pas une ligne de fichier.** Certains éléments
portent des sauts de ligne **internes** — un bloc entier de sortie de commande
tenu dans une seule chaîne. Écrits, ils deviennent plusieurs lignes physiques ;
relus, ils reviennent séparés. Les deux listes ne pouvaient donc **jamais**
coïncider, et le fichier était réécrit à chaque appel.

Les deux côtés sont désormais normalisés en lignes physiques **sans** leurs
fins de ligne. La symétrie compte : `readlines()` conserve le `\n` final,
`'\n'.join()` n'en met pas après la dernière — le dernier élément aurait
toujours différé, et le défaut serait revenu sous une autre forme.

**Mesure après correction** : après un commit, deux régénérations consécutives
ne réécrivent **pas** le fichier (`mtime` inchangé), l'arbre reste propre, et
la vitrine ne bloque plus que sur ce qu'elle doit bloquer — la fraîcheur du
cockpit.

**La leçon de méthode, et c'est la même qu'au §17.2 poussée d'un cran** : j'ai
posé trois hypothèses plausibles et je me suis trompé trois fois. Ce qui a
marché n'est pas une meilleure hypothèse, c'est d'avoir fait **parler
l'instrument** — lui faire imprimer le rang et le contenu de la divergence.
Une comparaison qui échoue sait toujours où elle échoue ; encore faut-il le
lui demander.

Note sur le banc : la même coquille exacte, `for v v in volatiles`, a été
produite **deux fois au même endroit** par `qwen3-coder-30b-local` sur deux
sollicitations distinctes. Singularité reproductible, à connaître avant
d'appliquer un livrable de ce modèle.

---

## 18. Le relevé de latences accumule — le prérequis des pistes ML est posé

`.nexus/latences.json` ne gardait qu'**une** lecture par modèle. Or une mesure
isolée ne dit pas laquelle de deux réalités très différentes elle a attrapée :
le même appel a rendu **180 300 ms à froid et 2 900 ms à chaud**.

Sans répétitions, aucune dispersion n'est calculable, donc aucun intervalle de
confiance : toute méthode qui apprendrait sur ces mesures **optimiserait du
bruit** (§106.2). C'était le prérequis des cinq pistes arbitrées au §16 — et
`epreuves.json` accumulait déjà. Le patron existait, appliqué à un relevé et
pas à l'autre.

**Mesuré, quatre propriétés :**

| Cas | Résultat |
|---|---|
| 71 alias avant / après | aucun modèle perdu |
| deux lectures proches | `stable: true`, historique accumulé |
| une mesure **échouée** (`latence_ms: None`) | historique et compteur **inchangés** |
| un écart énorme (95 000 ms) | `stable: false` |

`stable` se calcule sur la **dispersion**, jamais sur l'égalité : une latence
est continue, et exiger deux valeurs égales au millième rendrait l'indicateur
toujours faux — miroir exact d'un défaut déjà corrigé ailleurs, où un ensemble
à un élément était trivialement uniforme et le rendait toujours vrai.

### 18.1 Quatre défauts refusés avant intégration

| Jet | Défaut | Effet |
|---|---|---|
| 1 | confondait « fichier absent » et « illisible » | n'écrivait **jamais** rien sur une machine neuve |
| 1 | supprimait les modèles absents du lot courant | détruisait l'historique qu'il devait accumuler — le relevé se fait par lots |
| 2 | n'écrivait jamais les champs de la mesure courante | un fichier qui grossit en perdant ce qu'on vient d'y mesurer ; `nexus_generate` lit `latence_ms` pour les pools |
| 2 | n'initialisait l'historique que pour les alias **neufs** | `KeyError` sur les 71 alias de l'ancien format — un format nouveau qui refuse celui qu'il remplace |

### 18.2 La méthode du §16.3 se confirme

Le premier jet a été **relancé à neuf** plutôt que repris, en pliant les deux
défauts dans une spécification complète. Le second est arrivé en Python valide
du premier coup, structure juste.

Et la singularité relevée au §17.5 — la coquille `for v v in`, produite deux
fois au même endroit par `qwen3-coder-30b-local` — a été **corrigée
préventivement** avant même de lire le livrable. Elle n'est pas réapparue.
Connaître les défauts reproductibles d'un modèle vaut une passe entière.

---

## 19. Le parc déclare ses capacités — personne ne les lisait

Mesuré en interrogeant le **moteur** plutôt qu'en devinant. `ollama show`
déclare ce que chaque modèle sait faire ; sur les 54 modèles installés :

| Capacité | Modèles |
|---|---|
| `completion` | 51 |
| `tools` | 35 |
| `thinking` | 18 |
| `vision` | **14** |
| `insert` (complétion au milieu) | 5 |
| `embedding` | 4 |
| `audio` | **2** |

**Deux faits que personne n'avait vus** :

* le parc porte **déjà** deux modèles `audio` — `gemma4:latest` et
  `gemma4:12b` — alors que le banc avait affirmé « CATÉGORIE TRAITEMENT
  AUDIO : AUCUN MODÈLE SÛR ». Encore une affirmation de modèle démentie par
  une mesure ;
* cinq modèles déclarent `insert`, la complétion au milieu, que **rien** dans
  la plateforme n'expose ni ne route. Capacité installée, invisible.

### 19.1 L'écart, et le huitième cas que je n'avais pas vu

Sur **quatorze** modèles dont le moteur déclare `vision`, **sept** seulement
portaient `mode: vision`. Les autres sont déclarés **à la main**, hors de la
zone générée — donc hors de portée du correctif posé le matin même, qui
n'émet la modalité que sur le chemin auto-exposé.

La règle du contrat §17 — un modèle de vision ne retombe jamais sur un modèle
texte — ne pouvait donc pas s'appliquer, faute de savoir lesquels sont des
modèles de vision.

Le contrôle a trouvé un **huitième** cas absent de mon relevé manuel :
`qwen3-embedding-8b-local` déclare `embedding` sans porter `mode: embedding`.
Les huit sont comblés.

### 19.2 Ce qui dure : un contrôle, pas huit lignes corrigées

`controle_modalites` confronte à chaque validation ce que la configuration
déclare à ce que le moteur déclare. Il ne signale **pas** l'inverse — un mode
présent que le moteur ne déclare pas — car un modèle peut être absent du
moteur sans que la configuration soit fausse.

« ollama injoignable » part en **avertissement** et non en erreur : sur une
machine sans moteur, bloquer refuserait une configuration parfaitement saine.
Mais le fait reste **visible** — se taire serait indiscernable d'un dépôt
vérifié.

**Preuve positive** : un seul `mode: vision` retiré, et `Test-NexusConfig`
rend « Configuration INVALIDE » en nommant le modèle fautif.

### 19.3 Trois défauts refusés, et deux fois la même erreur de fenêtre

Refusés au livrable du banc :

* le parseur cherchait `Capabilities:` **avec deux-points**, or la sortie
  réelle affiche `  Capabilities` indenté et sans deux-points — la liste
  serait restée vide et le contrôle n'aurait **rien** signalé. Un contrôle
  muet est indiscernable d'un dépôt sain ;
* accès direct `model['litellm_params']['model']`, qui tombe sur une entrée de
  routeur sans `litellm_params` ;
* `model_info` pouvant valoir `None`.

Et le sous-processus était lu en **cp1252** : un octet indécodable faisait
tomber un fil de lecture.

**Deux fois une fenêtre mal bornée, le même jour.** Un `grep -A9` qui
s'arrêtait avant le champ cherché — d'où une conclusion fausse sur un modèle
« disparu » — puis une garde de 1 400 caractères qui débordait sur le bloc
voisin, y trouvait un `mode:` et sautait trois blocs à tort. **La borne juste
est le bloc suivant, jamais un nombre de caractères.**

### 19.4 Le cliquet d'outillage a mordu le code délégué, dans l'heure

`RET507`, `RET508` et `SIM108` introduits par le livrable du banc, attrapés
par `nexus_outillage.py --cliquet` au rituel de clôture. Corrigés par
`ruff --fix`, jamais rebaselinés : assumer une dégradation le jour de la pose
viderait le cliquet de son sens.

**Quatrième fois aujourd'hui** qu'un contrôle de ce dépôt mord le travail du
tour même — après la porte de conformité, le cliquet de câblage, et déjà une
fois l'outillage. Le contrat §106.1 dit que la discipline ne survit pas à une
longue session ; la mesure du jour est plus dure : **elle ne survit pas à
l'heure**, et elle ne survit pas non plus à la délégation. Le code du banc
n'est pas plus discipliné que le mien ; seul le contrôle l'est.

---

## 20. Mettre à jour la stack locale — le geste n'existait pas

`Update-NexusModels.ps1 -SyncLocal` rapatrie les modèles **absents**. Rien ne
rafraîchissait ceux **déjà installés** : la tâche quotidienne de 04:00
régénère la configuration, jamais les poids.

**Mécanisme.** Ollama n'a pas de commande « vérifier les mises à jour », mais
`ollama pull` ne retélécharge que les couches **changées** et annonce sinon
que le modèle est à jour. Rafraîchir = rejouer le tirage et **lire** la
réponse : `DÉJÀ À JOUR`, `MIS À JOUR`, `ÉCHEC`.

**Simulation par défaut, et c'est délibéré** : le parc pèse 430 Go. Sans
`--appliquer`, aucun octet ne part. Le geste est câblé à l'entrée unique
(`nexus maj-modeles`) mais **n'est pas armé dans la tâche quotidienne** —
engager la bande passante et le disque sans que personne l'ait demandé n'est
pas une décision d'outil.

**Garde disque** : refus sous 50 Go libres, **et** refus si l'espace n'a pas
pu être mesuré. Une garde qui abandonne en silence vaut moins que pas de
garde, parce qu'elle donne confiance.

### 20.1 Quatre défauts, tous trouvés en l'exécutant

| # | Défaut | Ce que cela produisait |
|---|---|---|
| 1 | `os.statvfs` n'existe pas sous Windows | la garde disque échouait, annonçait « impossible de déterminer », **et continuait** |
| 2 | `text=False` **et** `encoding=` se contredisent | le `.decode()` suivant levait `AttributeError`, avalé par un `except` générique et affiché comme **« Ollama introuvable »** — alors qu'Ollama répondait |
| 3 | la taille tient en **deux** champs (`6.7` puis `GB`) | total de **0,00 Go** pour cinquante modèles, comparé tel quel au seuil de la garde |
| 4 | `--limite` ne bornait que la boucle d'application | la simulation affichait cinquante modèles là où l'application en aurait traité quatre |

Le quatrième mérite d'être retenu : **une simulation dont le chiffre ne
correspond pas à sa liste ne simule rien** — et c'est précisément le geste
censé protéger de la surprise.

Le deuxième aussi : un diagnostic faux né d'un défaut interne envoie chercher
au mauvais endroit. C'est la troisième fois aujourd'hui qu'un outil de ce
dépôt accuse son environnement d'une panne qui venait de lui (après « entrée
illisible » sur une console cp1252, et « casse » sur un PSScriptAnalyzer sain).

### 20.2 Ce qui n'est pas prouvé

Le chemin `--appliquer` n'a pas encore rendu son verdict : le tirage réel
tournait toujours à la clôture du tour. La **simulation** et la **garde**
sont éprouvées ; le tirage ne l'est pas.

### 20.3 Le cliquet a mordu, cinquième fois du jour

`B007`, `RET504` et deux autres introduits par le livrable du banc, attrapés
au rituel de clôture et corrigés par `ruff --fix`. Cinquième fois aujourd hui
qu un contrôle de ce dépôt mord le travail du tour même. Le code du banc n est
pas plus discipliné que le mien ; seul le contrôle l est.

---

## 21. Le chemin `--appliquer`, mis à l'épreuve — il aurait inventé cent pour cent de pannes

Livré non prouvé au tour précédent, et je l'avais écrit. Mis à l'épreuve, il
portait deux défauts dont l'un rendait l'outil **nuisible**.

### 21.1 La classification ne pouvait jamais être vraie

Mesuré sur la **vraie sortie** de la commande. Un `ollama pull` sur un modèle
déjà à jour affiche :

```
pulling manifest
pulling 548455b72658: 100% ▕████████▏ 407 B
verifying sha256 digest
writing manifest
success
```

…et sort en code 0. Il ne dit **jamais** « already up to date », et jamais
« done ». Or la classification était :

| Condition | Verdict |
|---|---|
| `'already up to date'` présent | déjà à jour |
| `'pulling'` **et** `'done'` présents | mis à jour |
| sinon | **ÉCHEC** |

Aucune des deux premières ne pouvait être vraie. **Chaque modèle aurait été
classé ÉCHEC** — l'outil aurait annoncé cent pour cent de pannes sur un parc
parfaitement sain. Un outil qui invente des pannes est pire qu'un outil
absent : il envoie réparer ce qui fonctionne.

La seule méthode exacte est de comparer l'**empreinte** avant et après :
identique, le modèle n'a pas bougé ; différente, il a été mis à jour. Le texte
de la sortie ne distingue pas les deux cas.

### 21.2 Le sommeil de trente minutes

`time.sleep(1800)` **entre** chaque tirage. Le nombre avait été spécifié comme
un **délai d'expiration** par modèle, pas comme une pause. Le script dormait
donc une demi-heure après chaque modèle, et l'exécution lancée au tour
précédent n'a jamais rendu la main — fichier de sortie à **zéro octet**, que
j'aurais pu prendre pour une panne du tirage lui-même.

Le délai est désormais passé à `subprocess.run(timeout=...)`, où il a toujours
eu sa place.

### 21.3 Mesure après correction

| Cas | Résultat |
|---|---|
| empreinte de `all-minilm` et `all-minilm:latest` | `1b226e2802db` (les deux) |
| modèle inexistant | `None` |
| rafraîchissement d'un modèle à jour | `a_jour` en **0,7 s** |
| modèle absent | `echec` en 0,1 s |
| `--limite 1 --appliquer` en réel | 1 déjà à jour, 0 échec, code 0 |

**Ce qui a permis la correction** : avoir cité la **sortie réelle de la
commande** dans la spécification. C'est elle qui a fait proposer la
comparaison d'empreintes plutôt qu'une énième tentative de lecture du texte.
Mesurer avant de spécifier vaut mieux que corriger après avoir supposé.

### 21.4 L'ancienne exécution a confirmé les deux diagnostics, d'elle-même

L'exécution lancée deux ticks plus tôt — avec le code **d'avant** correction —
a fini par rendre, et sa sortie est une confirmation empirique :

```
Traitement de : deepseek-ocr:latest
Attente de 1800 secondes...

Rapport final :
  Deja a jour : 0
  Mises a jour : 0
  Echecs       : 1
```

Les deux défauts s'y lisent directement : la **pause de 1 800 secondes**, et
**`deepseek-ocr` classé en échec** alors que je l'avais tiré moi-même deux
heures plus tôt et qu'il fonctionnait. Le diagnostic n'était pas une
déduction : la trace le montre.

**Une réserve d'honnêteté sur le code de sortie.** Ma commande d'alors
enchaînait deux invocations, et le `code = 0` affiché venait de la seconde,
pas de celle dont on lit le rapport. Je ne peux donc pas attribuer proprement
ce zéro à l'ancien code, et je ne le fais pas.

En revanche le contrat **actuel** est mesuré, pas lu : en forçant un échec
sans rien télécharger, le script rend **1**. C'est la même classe que le
`exit 0` de la sonde MCP corrigé le matin même — un vert sur un échec
rapporté — et elle ne se vérifie qu'en la provoquant.

---

## 22. Les 17 violations PowerShell, arbitrées — deux vraies, quinze rejetées

Jamais examinées jusqu'ici, alors que ce dépôt tourne sur ces scripts.

### 22.1 Le seul défaut sérieux était du théâtre de sécurité

`Set-ClaudeModel.ps1` portait :

```powershell
$env:ANTHROPIC_AUTH_TOKEN = $key        # le token, EN CLAIR
# Masquer le token en memoire : on supprime la variable plain après usage
$secureKey = ConvertTo-SecureString $key -AsPlainText -Force
$key = $null
```

`$secureKey` apparaît **une seule fois** dans tout le fichier — l'affectation
elle-même. Il n'est jamais relu, donc il ne protège rien. Et il ne **pouvait**
rien protéger : deux lignes plus haut le token est écrit en clair dans la
variable d'environnement, où il doit rester puisque c'est par là que la
passerelle s'authentifie — le script la relit lui-même trois fois plus bas.

Vider `$key` pendant que l'environnement garde la valeur ne cache rien : tout
processus fils la voit.

**Un masquage décoratif est pire qu'aucun masquage : il donne confiance sans
rien fournir.** La ligne est retirée et le commentaire dit désormais ce qui se
passe réellement.

### 22.2 `$global:` fuyait dans la session de l'opérateur

`backup.ps1` déclarait `$global:backupDir`, qui survit à la fin du script dans
la session — une sauvegarde ne doit rien laisser derrière elle. Et la globale
ne servait même pas : la ligne qui assigne réellement le répertoire crée une
variable de portée **script**, que `Cleanup-And-Exit` lit par la portée
parente. Elle était vestigiale, et polluait pour rien.

### 22.3 Quinze rejets, chacun vérifié

| Règle | Occurrences | Verdict |
|---|---|---|
| `PSAvoidUsingEmptyCatchBlock` | **9** | **rejetées** — voir ci-dessous |
| `PSUseApprovedVerbs` (`Cleanup-And-Exit`) | 1 | cosmétique ; le nommage approuvé sert la découvrabilité d'un **module**, pas d'un script autonome |
| `PSAvoidOverwritingBuiltInCmdlets` (`Write-Log`) | 1 | **faux positif vérifié** : `Get-Command Write-Log` ne rend **rien** sur cet hôte. La règle compare à une liste statique |

**Les neuf `catch` vides sont légitimes**, et c'est vérifié un par un :

* `start.ps1:99`, `:126`, `:153` et `Update-NexusModels.ps1:211` — le `catch`
  est la **branche négative d'une sonde** (« le moteur répond-il ? »). Y écrire
  une erreur en ferait crier une sur le chemin **normal** ;
* `backup.ps1:28`, `restore.ps1:22`, `Register-NexusTraque.ps1:31`,
  `Register-NexusVitrine.ps1:35`, `Initialize-Nexus.ps1:150` — ajustement
  d'encodage de console, **déjà documenté** comme volontaire : « un souci
  d'affichage ne doit jamais faire échouer une sauvegarde ».

**Et le remède est de ne rien faire.** Le cliquet d'outillage gèle déjà ces
neuf comme dette acceptée ; un **dixième** serait une régression et
échouerait. Retirer la règle ferait perdre cette protection ; la « corriger »
ferait crier le linter sur des chemins sains. Le ratchet est exactement
l'outil pour ce cas.

C'est la même conclusion que pour `SIM105` en Python : **le linter signale, il
ne juge pas** — et sur 17 signaux, deux étaient des défauts.

---

## 23. `SIM115` arbitré — trois fuites qui comptaient sur dix-neuf signaux

Dix-neuf descripteurs non fermés signalés ; tous ne se valent pas. Dix vivent
dans un harnais de test à courte durée. Trois méritaient une correction.

| Fuite | Où | Pourquoi elle compte |
|---|---|---|
| 1 | `nexus_traque.py` — `analyser()` | appelée sur **chaque fichier suivi, toutes les dix minutes** par tâche planifiée. Sous Windows un descripteur ouvert **verrouille** le fichier |
| 2 | `nexus_agent.py` — lecture du `.env` | le `break` sortait dès la première ligne utile : le descripteur restait ouvert dans le **chemin nominal**, pas dans un cas rare |
| 3 | `nexus_agent.py` — sortie incrémentale | le `close()` était **après** la boucle : si elle levait, on n'y arrivait jamais |

### 23.1 Le remède que le banc a proposé ne remédiait à rien

Pour la troisième, le banc a proposé d'envelopper le `close()` dans un
`try/except`. Cela ne change **rien** : le problème n'est pas que la
fermeture échoue, c'est qu'on **n'y arrive pas**. C'est la **boucle** qu'il
faut envelopper.

Et un simple `with` ne convient pas ici : l'ouverture est **conditionnelle**
et le descripteur traverse tout le bloc. `try/finally` est la forme juste.

**Conséquence que je n'avais pas anticipée** : ajouter un `try:` impose de
**réindenter son corps**. Quatorze lignes — faites, et les bornes repérées par
leur **contenu**, jamais par un numéro de ligne, qui devient faux dès la
première insertion ailleurs dans le fichier.

### 23.2 Mesure

| Vérification | Résultat |
|---|---|
| `SIM115` global | 21 → **17** |
| `nexus_traque` rejoué | code 0, six classes rapportées comme avant |
| lot de test | rend `OK`, 185 jetons, 0 échec |
| sortie incrémentale | **1 ligne écrite** — le chemin traverse le `try/finally` intact |

Le `SIM115` restant sur l'ouverture conditionnelle ne disparaîtra pas : le
linter signale l'absence de `with`, **non** l'absence de fermeture. La
correctitude passe avant le compteur — et elle est désormais garantie.

---

## 24. `B023`, `B904`, `B905` — cinq signaux, cinq décisions distinctes

Ce n'est pas une correction en bloc : chaque signal demandait son propre
arbitrage.

### 24.1 `B905` — le score plausible et faux

Les deux `zip()` sont des **similarités cosinus**. Tronquer sur la plus courte
rendrait un score *plausible et faux* — le pire résultat possible pour une
recherche. Et le risque est réel dans ce dépôt : quatre modèles d'embedding de
dimensions **différentes** (bge-m3 1024, nomic 768, all-minilm 384), reliés
entre eux par des chaînes de repli.

Vérifié : les deux cas sont **sûrs** — l'un garde ses dimensions quatre lignes
plus haut, l'autre les tient par construction. Mais l'invariant y était **non
local** : un lecteur du `zip` ne le sait pas, et une suppression de la garde
passerait inaperçue. `strict=True` le rend local pour zéro coût.

**Le pont JavaScript gardait déjà ce cas**, et son commentaire disait mot pour
mot ce qu'il fallait argumenter : *« tronquer silencieusement sur la plus
courte donnerait un score plausible mais faux »*. La leçon existait dans le
dépôt, appliquée d'un côté et pas de l'autre — exactement comme pour
l'accumulation des mesures (§18).

### 24.2 `B904` — trois raise, trois décisions

| Cas | Décision | Pourquoi |
|---|---|---|
| deux `raise SystemExit(2)` | `from None` | la cause est **déjà** dans le message juste au-dessus ; accrocher une trace à une sortie de contrôle n'ajoute que du bruit à un arrêt volontaire |
| un `raise RuntimeError(f"… {e}")` | `from e` | ici la trace est **ce qui manque** : le message dit *que* l'appel a échoué, seule la trace dit *où* — réseau, passerelle, décodage |

### 24.3 `B023` — une fermeture sur un nom réaffecté

`visit()` est définie dans une boucle et capture `graph`, `color`, `label` par
leur **nom**. Sans conséquence aujourd'hui — elle est appelée dans la même
itération. Mais `graph` est **réaffectée huit lignes plus bas, dans la même
portée**. Un déplacement d'appel la ferait parcourir silencieusement le
mauvais graphe, et rendre un verdict de cycle portant sur autre chose.

Liaison par arguments par défaut : les valeurs sont capturées à la définition,
l'appel récursif hérite des mêmes défauts, le comportement est inchangé —
seule la fragilité disparaît.

**Preuve positive**, car j'avais touché la détection de cycles : un cycle
injecté est bien nommé — `cycle dans fallbacks : qwen3-8b-local ->
llama3.2-3b-local -> qwen3-8b-local` — la configuration refusée, puis
restaurée et valide.

### 24.4 État des compteurs

| Règle | Avant | Après |
|---|---|---|
| `B023` | 5 | **0** |
| `B904` | 4 | **0** |
| `B905` | 2 | **0** |
| `SIM115` | 21 | 17 |

---

# 25. POINT DE REPRISE — 31/08/2026, contexte saturé

Écrit pour survivre à une perte de contexte. **Rien ici ne dépend de ma
mémoire** : `nexus sujets` régénère cette liste depuis la transcription, les
messages de commit et ce fichier.

## 25.1 Ce qui est FERMÉ par un contrôle qui échoue si la règle est enfreinte

| Fermé | Contrôle qui garde |
|---|---|
| le garde des sous-agents ne voyait pas `Workflow` (460 sous-agents, 32,1 M de jetons facturés) | matcher `Agent\|Workflow`, `--only plan`, 8 cas |
| un refus sortait en 0 — il s'affichait sans bloquer | `epreuve_garde_plan`, cas « un REFUS sort en 2 » |
| le cliquet de câblage punissait la première épreuve Python | `--only cablage`, 8 cas dont 4 garde-fous |
| l'outillage annonçait « 0 violation » à trois étages (108 défauts cachés) | `nexus_outillage --cliquet`, câblé au rituel |
| la traque cherchait un refus en MOTS, celui du garde était en DONNÉES | motifs A et B, éprouvés par sonde |
| la sonde MCP rendait SUCCÈS sur ses propres échecs | `--only sonde`, 10 cas |
| un repli pouvait viser un quota déjà épuisé | `--only quota`, contre-épreuve par injection |
| `STATE.md` ne pouvait être propre plus d'une heure | écriture idempotente, 4 champs volatils |
| l'index écrasait au lieu de fusionner | fusion + 2 gardes (modèle, format) |
| le relevé de latences écrasait | accumulation + dispersion, 4 propriétés |
| 7 modèles mentaient sur leur modalité | `controle_modalites`, câblé au validateur |
| l'orchestrateur écrivait sans le dire | `nexus_redaction`, câblé au rituel — **71 MUETS** affichés |

## 25.2 Ce qui reste OUVERT — aucun contrôle ne le garde

| Sujet | Pourquoi il reste ouvert | Prochain geste |
|---|---|---|
| **Le cliquet ne RESSERRE pas** | il note les améliorations sans abaisser la référence : un retour en arrière passerait. `nexus_cablage` a le même trou | décider si écrire la référence pendant le rituel est acceptable — cela salit l'arbre au moment où le rituel le vérifie |
| **~85 violations Python non arbitrées** | `SIM115` ×17 (dont 10 dans le harnais de test), `B007` ×12, `RET503` ×9 | arbitrer par classe, comme pour PowerShell : 2 vrais défauts sur 17 |
| **`insert` et `audio` mesurés, exposés par rien** | 5 modèles déclarent `insert`, 2 déclarent `audio`. Les exposer demande des chemins d'API nouveaux | décision d'architecture — **je ne la prends pas seul** |
| **Lenteur du pont MCP** | >120 s contre 10,6 s en direct. L'hypothèse de la ruée sur le cache est **réfutée** (CACHE_MS 60 s, concurrence bornée) | mesurée, inexpliquée |
| **P4 : six familles rendent vide à 2 200 jetons** | `mesure_rendu_vide.py` livré et câblé, jamais joué sur les neuf familles | jouer l'outil, deux passes par modèle |
| **`--fusionner` : cause non établie** | sous `true`, deux familles ont déclaré les fichiers vides ; la session voisine a rétracté sa cause | reproduire sans clause d'échappement |
| ~~Contrat §3 périmé~~ | **FERMÉ le 31/08** : 11434 répond (`{"version":"0.33.1"}`), 11435 non. Le contrat confondait le moteur natif et le conteneur du profil `embedded`, que §22 dit lui-même non démarré | corrigé, avec la mesure inscrite en §3.1 |
| **40 `.bak` dans `scripts/.nexus/`** | signalés en ALERTE à chaque passage de la porte | données de l'opérateur |
| **Promotion sans démotion** | les épreuves promeuvent, ne démeuvent jamais ; une promotion peut tenir sur un seul passage | décisions réservées à l'opérateur |

## 25.3 Les cinq propositions de la session voisine, arbitrées

| # | Verdict |
|---|---|
| P1 garde d'indexation au mauvais niveau | **retenu** — la raison était fausse, le garde reste, le motif est réécrit |
| P2 exposer les modèles résidents | **retenu** — `OLLAMA_URL` + `modelesResidents()` |
| P3 traces verbatim dans l'arbre | **pas de mon ressort** — `_RAPPORTS_VERBATIM` n'existe pas ici |
| P4 l'échec a la forme d'un résultat | **pas de mon ressort** — `Task failed:` vient de l'enveloppe Claude Code |
| P5 un brief doit porter le sol entier | **déjà mesuré ici** (§16.3), convergence indépendante |

## 25.4 Les quatre leçons que la journée a payées

1. **Une leçon appliquée d'un côté et pas de l'autre** — six occurrences :
   accumulation des mesures, garde sur les vecteurs, sortie machine sur
   stderr, deux critères d'exclusion cloud, réveil du modèle, et le cliquet.
   *Chercher systématiquement le jumeau d'un correctif.*
2. **Un artefact d'observation pris pour un défaut** — trois fois : un
   `grep -A9` trop court, un `2>&1` qui fusionne les flux, une fenêtre de
   1 400 caractères débordant sur le bloc voisin. *Borner par le contenu.*
3. **La forme de la délégation compte plus que le modèle** — les livrables
   **complets** réussissent, les **diffs verbatim** échouent, les **reprises**
   dégradent. *Relancer à neuf plutôt que reprendre.*
4. **Un vert qui ne peut pas rougir ne mesure rien** — construit deux fois
   sans le voir avant de l'exécuter. *La contre-épreuve est le livrable.*

---

## 26. FAIL-OPEN PAR CONSTRUCTION — la classe, nommee par la session voisine

Un etat pose AVANT la tentative qu'il est cense enregistrer. La branche non
prevue — l'echec — prend alors la valeur « autoriser », et le second passage
ne peut plus rien corriger puisque l'etat dit que tout va bien.

Trois occurrences mesurees dans ce depot, toutes trouvees par l'USAGE :

| Ou | Ce qui etait pose trop tot | Ce que cela cachait |
| --- | --- | --- |
| `nexus_garde_agent.py` | `return 0` sur un refus | « deny » imprime, sous-agent lance quand meme |
| `tools/nexus-mcp/server.js` | `_modelesReveilles.add()` avant le reveil | un reveil expire enregistre comme reussi |
| ma contre-epreuve, le meme jour | filtre lisant `ECHEC` apres passage au format `[RATE]` | trois defauts declares non detectes |

Le troisieme est le plus instructif : c'est le VERIFICATEUR du verificateur
qui s'est casse, sur le meme motif, dans l'heure. Un controle dont le lecteur
est casse rend exactement le meme silence qu'un depot sain.

**Le remede n'est pas une regle, c'est la contre-epreuve.** On remet le defaut
UN PAR UN dans le fichier sain et on exige un rouge QUI NOMME LE CAS. Un rouge
sur la garde de structure, ou un rouge par ecrasement du harnais, ne prouvent
rien : le premier tombe avant les cas, le second ne dit pas ce qui a lache.
Les deux sont arrives ici, dans cet ordre.

### 26.1 Le budget de reveil, mesure sur le PARC — et le chiffre corrige

Premier chiffre annonce : « 9 sur 48, soit 18,8 % ». **Faux par construction** :
48 est un nombre d'ALIAS MESURES, pas de modeles installes. L'operateur l'a
conteste — « a voir reellement avec ollama list » — et il avait raison.

Confrontation faite, et elle a demande DEUX passes :

| | |
| --- | --- |
| modeles locaux installes (`ollama list`) | **52** |
| alias mesures portant `local` | 48 |
| alias visant un modele installe | **47** |
| installes sans mesure de demarrage | 5 |

La premiere passe annoncait 8 alias orphelins et 12 modeles jamais mesures.
**Egalement faux, et de mon fait** : ma normalisation ne retirait pas le
suffixe `:latest`, si bien que `codestral:latest` et `codestral-local` ne
s'appariaient pas. Exactement l'artefact de nommage que la session voisine
avait rencontre le matin meme, francais contre anglais. Un inventaire produit
par un apparieur naif dit l'etat de l'apparieur, pas celui du parc.

Les cinq sans mesure ne sont pas un trou : `ollama show` les donne
**embedding** (all-minilm, bge-m3, nomic-embed-text, qwen3-embedding:8b) et
**vision/OCR** (deepseek-ocr). Un banc de demarrage *chat* ne les mesure pas,
et ne le devrait pas.

Le seul veritable orphelin, `ultime-recourse-local`, vise `llama3.2:1b` — ce
qui **corrige le contrat** : §18 affirmait `ollama_chat/phi3:mini`. Le depot
fait foi (§5).

**Les chiffres tenus, sur les 47 modeles chat mesures ET installes :**

| Seuil | Modeles au-dessus | Part |
| --- | --- | --- |
| 15 s — l'ancien budget grave | **9** | **19,1 %** |
| 31 s | 6 | 12,8 % |
| 60 s | 3 | 6,4 % |

Le pire, `qwen3-32b-local`, demarre en **102,9 s** — pres de sept fois le
budget. Un nombre grave ne pouvait pas couvrir cette dispersion ; le budget
vient desormais de l'appelant, qui s'y adapte seul.

Mesure directe contre le moteur, `qwen3.6:27b` : **31 s a froid, 2 s a chaud**.
Un facteur 15 entre deux etats du MEME modele — ce que la session voisine
avait d'abord attribue a sa taille.

### 26.2 Ferme par un controle qui echoue

`tools/nexus-mcp/epreuve_reveil.js`, cablee a `nexus_test.py --only reveil`,
11 cas remontes au harnais commun. Contre-epreuve jouee sur les trois defauts
remis separement : chacun rougit en nommant son cas.

### 26.3 Reste OUVERT

* La classe fail-open n'a **pas** de motif dans `nexus_traque.py` : les trois
  occurrences ont ete trouvees a la main. Un crible AST la verrait-il ? La
  session voisine construit exactement cela de son cote.
* Un apparieur de noms n'a **aucune epreuve** ici, alors qu'il vient de rendre
  deux inventaires faux en un jour, dans deux depots. Le motif est le meme :
  suffixe implicite, langue differente.
* La garde « lire avant d'ecrire » ne reconnait que l'outil Read. Le harnais
  oriente desormais les lectures vers `cat` : un fichier reellement lu est
  donc refuse a l'ecriture. Ce n'est PAS un defaut de la garde — elle ne peut
  pas verifier un `cat` — mais la friction va croitre, et l'affaiblir serait
  echanger une vraie protection contre du confort.
* `nexus_context` hors depot : rendre fichier + ligne + score sans contenu.
  Tranche par la session voisine — **non par defaut, oui sur opt-in explicite
  et trace**, registre vide garde par un test qui rougit a la premiere
  addition. Non implemente ici.

---

## 27. LA MISE A JOUR DU PARC — deux questions, deux defauts

L'operateur a demande de *verifier* que la mise a jour est cablee **et**
qu'elle se deroule. Les deux moities ont rendu deux defauts distincts, et
seule la seconde etait le vrai trou.

### 27.1 « Se deroule-t-elle ? » — non, et la cause est datee

`Claude-Local-Nexus - Mise a jour` : **LastTaskResult = 1**. Le journal du
2026-08-31 04:02 nomme la cause :

```
[BLOQUE] garde agent   sous-agent sans modele accepte (code 0 au lieu de 2)
=> NON CONFORME : LiteLLM n'a PAS ete redemarre
```

C'est le fail-open du garde d'agent (§26), corrige plus tot le meme jour. Le
garde rend maintenant 2, la conformite est verte, et la chaine rejouee en
simulation sort 0. **La tache repassera d'elle-meme le 01/09 a 04:00.**

Note au passage : `Claude-Local-Nexus - Demarrage` porte 267011, soit
`SCHED_S_TASK_HAS_NOT_RUN`. Ce n'est pas un echec — elle se declenche au
logon et n'a pas encore eu l'occasion.

### 27.2 « Est-elle cablee ? » — non, et c'etait le vrai trou

La tache ne lance **pas** `nexus_maj_modeles.py`. Elle lance
`Update-NexusModels.ps1 -SyncLocal`, et `-SyncLocal` appelle
`nexus_pull_host.py --manquants` : cela tire les modeles **declares et
absents**. Rien ne rafraichissait un modele **deja installe**.

Le script qui le fait n'avait qu'un appelant : `nexus.ps1`, a la main. Un
script sans appelant automatique est un fichier, pas un mecanisme — et c'est
le maillon que §0.2.1 designe comme le plus souvent manquant.

Ferme par `-SyncWeights`, place AVANT la generation, ajoute a la tache **et**
au script qui l'enregistre. Ne corriger que la tache vivante aurait ete un
cablage a moitie : le prochain enregistrement l'aurait effacee.

### 27.3 La consequence qu'un cablage a moitie aurait manquee

Un modele dont les poids changent rend **perimees ses propres mesures**. Sans
invalidation, le parc aurait ete rafraichi et le routage aurait continue sur
la preuve des anciens poids. `invalider_mesures()` retire donc les entrees
des seuls modeles reellement changes — compares par **empreinte**, jamais par
le texte de la sortie.

Deux defauts rejetes dans ce que le banc a rendu :

| Defaut | Ce qu'il aurait cause |
| --- | --- |
| drapeau `found` partage entre les deux relevés | preuve de CAPACITE survivant au changement de poids |
| cle `illisibles` presente seulement parfois | `KeyError` chez le premier appelant en acces direct, le jour ou tout va bien |

Le second a ete impose par **l'epreuve, contre mon code** — elle avait raison.

### 27.4 Ferme par un controle qui echoue

`scripts/epreuve_maj_modeles.py`, **23 cas**, cablee par un lanceur commun
`jouer_epreuve_python()` ou une epreuve MUETTE compte comme un echec. Trois
defauts remis un par un : chacun rougit en nommant son cas.

### 27.5 Reste OUVERT — la cecite d'un tour du cliquet de cablage

`nexus_cablage.py` enumere par `git ls-files` : **un script neuf et non
commite lui est invisible**. Or le rituel tourne AVANT le commit, donc une
orpheline creee dans le tour n'est jamais vue dans ce tour.

Mesure faite : une fois commite, le cliquet voit le fichier. **La cecite dure
un tour, elle n'est pas permanente** — et c'est pourquoi ce point est inscrit
ici plutot que corrige dans l'urgence : elargir a l'arbre de travail ferait
juger des brouillons, ce qui produirait du bruit a chaque tour.

### 27.6 Le cliquet d'outillage a rougi sur MON code, dans le meme tour

Le rituel a refuse de clore :

```
[MANQUE] outillage tenu   Outillage : 2 REGRESSION(S).
                          | ruff : B007 12 -> 13 | ruff : F401 2 -> 3
```

Sur du code applique quelques minutes plus tot. C'est precisement son office,
et il faut le dire : **la seule autre issue etait de relever la reference**,
c'est-a-dire d'acheter le silence en figeant la dette. Un cliquet qui ne
rougit jamais sur le code de son auteur ne mesure rien.

* `F401` — la consigne donnee au banc reclamait `io` parmi les imports de
  l'epreuve ; le rendu ne l'emploie pas. Mon erreur de specification, pas la
  sienne.
* `B007` — depuis que le drapeau d'invalidation est **par fichier** et non
  partage, la boucle n'emploie plus son nom de modele. Renomme `_nom` : dire
  l'intention vaut mieux que laisser croire a un oubli.

Les 23 cas restent verts et la contre-epreuve reste rouge sur les trois
defauts. La correction n'a rien desarme.

---

## 28. LA RECOLTE DES SUJETS — un marqueur n'est pas un sujet

L'operateur a demande de recuperer les sujets ouverts **par l'outil bati pour
cela**, plutot que de deviner. L'outil rendait **499 occurrences**, et le
premier coup d'oeil a suffi : il ne distingue pas une phrase contenant le mot
« ouvert » d'un sujet ouvert.

| Sortie reelle | Ce que c'etait | Marqueur qui l'a fait passer |
| --- | --- | --- |
| `docs(doctrine): une regle non mecanisee ne protege pas` | de la doctrine | « non mecanise » |
| `Reste a l'appeler -- une fonction que personne n'invoque` | ma narration d'un travail **fait** | « reste a » |
| `grep -n "aucun contenu a traiter" -B14 server.js` | une ligne de commande | « a traiter » |

L'outil bati pour eviter de deviner obligeait a deviner. **Defaut trouve en
s'en servant, pas en le relisant** — il ne se voyait qu'au moment ou il genait.

### 28.1 Le remede, et les cinq defauts arbitres

Un marqueur **fort** se suffit ; un marqueur **faible** exige une
corroboration dans les 200 caracteres qui l'entourent. Plus deux rejets
francs : lignes de commande, doctrine.

Cinq defauts dans le premier jet, **dont deux auraient supprime des sujets en
silence** :

| Defaut | Effet |
| --- | --- |
| `--` compte comme marque de commande | il sert de tiret cadratin partout ici : la prose legitime aurait ete rejetee |
| `OUVERT` en capitales compare a du texte minuscule | **controle mort**, dont la presence donnait a croire qu'il jouait |
| `FAIT` en minuscule | attrapait « en fait », « il a fait » |
| l'exemption du marqueur fort **confiee a l'appelant** par un commentaire | les appelants existent deja et ne l'auraient pas lue |
| « desormais » emportait la moitie ouverte d'une phrase | *impose par l'epreuve, contre mon code* |

Le dernier merite d'etre lu deux fois. Le fragment « le generateur l'ANNONCE
**desormais** ; la decision de politique **reste a l'operateur** » etait
rejete : le mot de cloture decrivait la moitie faite et emportait la moitie
ouverte avec elle. **Une decision renvoyee a l'operateur n'est jamais close,
quoi que dise le reste.** C'est la meme exemption que pour le marqueur fort,
sur une variante manquee — sixieme occurrence du jour d'une lecon appliquee
d'un cote et pas de son jumeau.

**Mesure : 499 -> 231**, et les 17 vrais sujets qu'une premiere version du
filtre emportait sont revenus.

### 28.2 Ferme par un controle qui echoue

`scripts/epreuve_sujets_filtre.py`, 9 cas, cablee (`--only sujets`). Ses
fragments **ne sont pas inventes** : ce sont les sorties reelles de
l'execution bruitee, et l'une d'elles est un VRAI sujet qui doit **survivre**.
Sans elle l'epreuve ne prouverait que la severite — un filtre qui rejette tout
est aussi inutile qu'un filtre qui passe tout. Contre-epreuve : quatre defauts
remis un par un, chacun rougit en nommant son cas.

### 28.3 Deux defauts de MON outillage, trouves en chemin

* **L'epreuve jouait a l'import**, et son `sys.exit()` aurait **tue**
  l'importateur. Trouve par le controle de conformite, qui importe tous les
  scripts. Referme derriere `main()`.
* **Trois pieges d'extraction**, notes parce qu'ils se reproduiront :
  `str.find` rend `-1` quand le marqueur manque et un `min` naif retient ce
  `-1` ; le **code extrait contenait son propre delimiteur** (la chaine des
  trois accents graves figure dans les motifs de commande), coupant
  l'extraction a 486 octets au lieu de 2878 ; et le banc emploie parfois un
  tiret **insecable** dans ses marqueurs.

### 28.4 Ce qui n'est PAS un defaut, et que j'ai failli « corriger »

Le rapport humain sort sur `stderr`, `stdout` restant pur pour `--json`. J'ai
d'abord cru a un defaut. **C'est la meme confusion qui m'a fait accuser
`nexus_savings` a tort ce matin**, en fusionnant les flux par un `2>&1`. Une
convention n'est pas un bug, et se tromper deux fois de la meme facon dans la
journee valait d'etre inscrit.

### 28.5 Reste OUVERT

La transcription demeure la source la plus bruyante : **193 des 231**
occurrences en viennent, contre 13 du cockpit et 10 des commits. Le cockpit
est structure, la transcription ne l'est pas — et aucun filtre lexical ne
rendra structure ce qui ne l'est pas. La piste serait de ne miner que les
messages de l'OPERATEUR dans la transcription, jamais ma propre prose ; elle
n'est pas ouverte ici.

---

## 29. LE GARDE SHELL NE JUGEAIT QUE BASH — deux etages, et une lecon empruntee

L'operateur : « il ne faut pas seulement graver, mais l'appliquer ». Applique,
apres avoir chiffre le vecteur — on ne colmate pas un fail-open qu'on n'a pas
mesure.

### 29.1 La mesure

La meme commande dangereuse, soumise sous deux noms d'outil :

```
tool_name = "Bash"        -> REFUSE
tool_name = "PowerShell"  -> PASSE
```

L'outil PowerShell est actif dans cette session et sert en permanence. Tout ce
que ce garde protege etait donc contournable **en changeant d'outil**, sans
rien d'autre.

### 29.2 Deux etages, et c'est le point

| Etage | Ce qu'il portait |
| --- | --- |
| `.claude/settings.json` | matcher `Bash` seul |
| `nexus_garde_shell.py` | `if tool_name != "Bash": return` |

En elargir **un seul** aurait laisse l'autre fermer la porte, et le correctif
aurait paru fait. C'est la forme la plus courante du cablage a moitie.

### 29.3 Elargir sans adapter aurait ete PIRE que le trou

Les deux regles existantes sont propres a bash : le heredoc du CAS A n'existe
pas en PowerShell, et l'accent grave du CAS B y est le caractere
d'**echappement ordinaire**, la ou bash en fait une substitution de commande.

Les appliquer a PowerShell aurait refuse du travail parfaitement normal. **Un
garde qui refuse le travail normal se fait desarmer** — c'est le risque
principal, plus grave que le trou. Les regles sont donc choisies selon
l'outil.

La regle propre a PowerShell : le delimiteur de fermeture d'une here-string
doit etre en **colonne zero** ; l'indenter est une erreur de syntaxe.

### 29.4 Un controle MORT, rejete dans le rendu du banc

Sa fonction cherchait la fermeture sous la forme `@'` — qui est la forme
**d'ouverture**. La fermeture s'ecrit `'@`, inversee. Le controle ne se serait
**jamais** declenche, tout en donnant a croire qu'il jouait. Meme classe que
le motif en capitales compare a du texte minuscule (§28.1), **le meme jour**.

### 29.5 Prouve en vrai, et honnetete sur la portee

Le hook vivant, sans redemarrage de session : la here-string indentee est
refusee en nommant le remede ; la here-string correcte et l'accent grave
d'echappement passent.

`scripts/epreuve_garde_shell_ps.py` porte dix cas, mais rejouee contre le
garde d'avant elle n'en rougit qu'**un**. Les neuf autres sont des
**anti-controles** : ils doivent passer dans les deux versions, c'est leur
office. Sans eux, un garde qui refuserait tout paraitrait parfait — et serait
desarme le lendemain. Le dire vaut mieux que compter dix cas comme dix
preuves.

### 29.6 Ce qui autorise un agent a ecrire dans settings.json

La session voisine refuse d'y toucher, et elle a raison sur le principe. La
distinction qui autorise ce commit : **ce changement elargit la portee du
garde, il ne la desserre pas.** Etendre ce qui me contraint n'est pas
desserrer ce qui me contraint. Toute modification qui RETIRERAIT un outil du
matcher releverait, elle, de l'operateur.

### 29.7 Le garde a mordu pendant sa propre correction

La commande composee qui posait ce correctif portait un heredoc a antislash :
refusee. Le script n'a donc pas tourne, laissant un moment le **matcher
elargi et le garde inchange** — incoherent mais sans danger, le garde se
contentant de sortir. Repose seul ensuite. Un garde qui gene son auteur au
moment ou celui-ci le repare est un garde qui fonctionne.

### 29.8 Reste OUVERT

* **`nexus_garde_lecture.py` couvre `Read|Edit|Write` — pas `Bash`.** Or le
  harnais oriente desormais les lectures vers `cat` et les ecritures vers
  `sed`. La garde « lire avant d'ecrire » est donc contournable par
  construction, et je l'ai contournee sans le vouloir plusieurs fois
  aujourd'hui. Le vecteur n'est PAS chiffre : ce sujet reste ouvert tant qu'il
  ne l'est pas, car corriger avant de mesurer est ce que §29 vient de refuser.
* **La classe fail-open n'a toujours pas de motif dans `nexus_traque.py`.**
  Quatre occurrences connues maintenant, toutes trouvees a la main.

---

## 30. REVUE DES SUJETS OUVERTS — demandee, et elle a rapporte plus que prevu

L'operateur : « recupere tous les sujets ouverts de la conversation, ils
doivent etre traites avant de partir sur d'autres sujets ».

### 30.1 D'abord verifier lesquels sont PERIMES

Un tableau de bord qui ment sur son propre etat est pire qu'un tableau absent
— sa propre regle. Quatre entrees etaient perimees :

| Entree | Etat reel |
| --- | --- |
| `B023` dans `nexus_validate.py` | **ferme** — `All checks passed`, 5 → 0 |
| Le matcher elargi non prouve in vivo | **ferme** — prouve ce jour, hook vivant, sans redemarrage (§29.5) |
| Contrat §3 perime | **ferme** le 31/08 |
| « eslint n'est pas provisionne » | **faux** — il l'est... et c'est la que tout a bascule |

### 30.2 « eslint : 0 violation » etait un vert qui ne pouvait pas rougir

La quatrieme entree paraissait perimee : eslint EST provisionne et rapporte
`JOUE (0 violations)`. **Zero violation sur 2 600 lignes de JavaScript** — ce
dépot a paye assez cher pour ne plus croire un zero sans l'eprouver. eslint
lance directement, memes arguments : **neuf problemes**.

**La cause, trouvee en instrumentant `_run_cmd`** :

```
returncode   : 1
stdout (len) : 0
stderr (len) : 0
```

`text=True` sans `encoding` fait decoder avec la page de code de la console —
cp1252 ici. Le JSON d'eslint porte un octet `0x81`, venant des commentaires
accentues **UTF-8** de `server.js`. Le decodage leve `UnicodeDecodeError`
**dans le thread lecteur** de `subprocess`, exception que `subprocess` avale :
`communicate()` rend des chaines **vides**. Puis `json.loads(stdout or "[]")`
rend zero violation, etat « joue ».

**Un outil incapable de lire sa propre sortie rapportait un depot propre.**

Le signe qui aurait du trahir etait la : eslint sort **1 quand il a trouve**
des problemes. Un code 1 avec un flux vide est une contradiction — et c'est
desormais la garde, celle qui aurait rougi **meme sans** la correction
d'encodage.

### 30.3 Ce que la mesure a revele, et c'est le plus lourd

```
server.js:1429  'modelesResidents' is defined but never used
```

C'est la fonction posee le matin meme pour le **P2** de la session voisine —
exposer les modeles residents, pour qu'un appelant choisisse ce qui est deja
chaud plutot que de payer 31 s de chargement. Le point lui avait ete annonce
**« retenu et applique »**.

**Elle etait ecrite et jamais appelee.** La capacite n'existait pas. Aucun
humain ne l'a vu, et le seul outil qui l'aurait vu rendait « 0 violation ».

Branchee a `nexus_models`, verifiee en vrai :

```
MODELES CHAUDS — deja en memoire, repondent sans payer le chargement (2)
  qwen3:1.7b
  llava:34b
```

« Moteur injoignable » et « aucun modele chaud » sont dits **separement**.

La session voisine a mesure de son cote qu'elle ne voit **pas** la capacite :
son pont est l'ancien. La reconnexion reste due — et sans cette verification
elle aurait cru P2 actif et choisi ses modeles a l'aveugle.

### 30.4 Arbitrage des neuf, dans le code reel

| Classe | Verdict |
| --- | --- |
| 3 `no-unused-vars` | **corriges** — dont un ecrit par moi dix minutes plus tot, dans le branchement ci-dessus : preuve que la mesure marche |
| 6 `require-atomic-updates` | **conserves** — caches memo : deux appelants concurrents ecrivent la MEME valeur. Un appel duplique, pas une corruption |

Et il n'est **pas** affirme qu'ils expliquent la lenteur du pont : cette
hypothese a ete refutee par l'arithmetique le 30/08, et un linter ne la
ressuscite pas.

### 30.5 Le verdict LOI 1, verifie plutot qu'ecarte

« REGRESSION : le nouveau garde peut renvoyer `casse` alors que l'appelant
attendait `joue` ». Eprouve en cassant eslint pour de vrai :

```
eslint : NON JOUE (absent)
eslint : NON COMPARE (absent) -- reference conservee
code de sortie = 0
```

Ni blocage, ni fausse amelioration, ni reference corrompue. **Verdict
plausible, infonde** — mais il fallait le mesurer pour le dire.

### 30.6 Ce qui RESTE ouvert apres cette revue

| Sujet | Pourquoi il reste ouvert |
| --- | --- |
| **`nexus_garde_lecture` ne couvre pas `Bash`** | le harnais oriente les lectures vers `cat`. La session voisine a chiffre le meme angle mort chez elle : **30,4 % des ecritures d'une session reelle passent par le shell**, mesure le 21/08 — et laisse ouvert. « Declarer n'est pas proteger », deja joue une fois ici |
| **Le cliquet ne RESSERRE pas** | ecrire la reference pendant le rituel salit l'arbre au moment ou il le verifie. Question posee, non tranchee |
| **~75 violations Python non arbitrees** | `SIM115` ×17, `B007` ×12, `RET503` ×9 |
| **6 `require-atomic-updates`** | arbitres non-defauts ; la voie propre serait une promesse en vol partagee. Nomme, non fait |
| **Lenteur du pont MCP** | mesuree, inexpliquee, hypothese principale refutee |
| **P4 : six familles rendent vide** | `mesure_rendu_vide.py` livre et cable, jamais joue sur les neuf familles |
| **`--fusionner` : cause non etablie** | reproduire sans clause d'echappement |
| **40 `.bak` dans `scripts/.nexus/`** | donnees de l'operateur |
| **`insert` et `audio` exposes par rien** | decision d'architecture — **pas prise seul** |
| **Promotion sans demotion** | reservee a l'operateur |
| **Worker dans un worktree git** | `nexus_essaim.py` ecrit hors du depot, mais dans un repertoire, **pas un worktree** |
| **Un troisieme lanceur, demain** | rien ne surveille l'apparition d'un outil shell non garde |

---

## 31. LES DEUX ETAGES D'UN GARDE — et un defaut de METHODE plus lourd

### 31.1 Le defaut, cree puis ferme dans le meme tour

Le matcher de `.claude/settings.json` disait `Bash|PowerShell` pendant que le
garde disait `!= "Bash"`. PowerShell etait **route** vers un garde qui
refusait de le juger — un correctif a moitie, qui **se lit** comme fait.
Trouve seulement en soumettant a la main la meme commande sous deux noms
d'outil.

Ferme par `controle_gardes_accordes` : chaque garde **declare** ce qu'il juge
(`OUTILS_JUGES`), et la declaration est comparee au routage, **sans importer**
le garde — l'importer executerait son code. Il a mordu dans la minute :
`nexus_garde_edition.py` ne declarait rien.

Le **sens** du desaccord decide de la severite : route mais non declare
**BLOQUE** ; declare mais non route **ALERTE**. Bloquer sur le second
arreterait le travail pour une capacite inemployee.

### 31.2 Le .pyc perime — un faux vert sur le mecanisme anti-faux-vert

La contre-epreuve a attribue un echec au **mauvais cas**. Deux hypotheses
posees puis **refutees par la mesure** avant la bonne. La cause, prouvee en
supprimant `__pycache__` :

> Python valide un `.pyc` sur la paire **(mtime, taille)** de la source.
> « ALERTE » et « BLOQUE » font **six caracteres** chacune. Une reecriture
> dans la meme seconde laisse les deux valeurs inchangees, et Python sert le
> bytecode **perime**.

La premiere hypothese etait juste sur le fond et **fausse sur le test** :
`PYTHONDONTWRITEBYTECODE` empeche d'**ecrire** un cache, pas de **lire** celui
qui existe. *Une refutation par le mauvais instrument est pire qu'aucune
refutation — elle ferme une piste correcte.*

**Portee.** Toute contre-epreuve qui echange des chaines de **meme longueur**
dans un module et le rejoue dans la seconde peut declarer un defaut **non
detecte**. C'est un faux vert sur le mecanisme meme qui existe pour detecter
les faux verts.

Mecanise : `jouer_epreuve_python` purge `scripts/__pycache__` avant chaque
epreuve. L'echec de purge n'est pas bloquant.

La session voisine a transpose immediatement, et sa cible est pire que la
mienne : **un testeur de mutation est concu pour muter a l'identique**. Elle a
trouve chez elle un commentaire declarant le phenomene « n'affecte AUCUN
verdict » — affirmation non mesuree — et a decouvert que sa protection reelle
venait d'ailleurs (exclusion de `__pycache__` a la copie). *Une protection
attribuee au mauvais mecanisme est une protection qu'on peut retirer par
inadvertance.*

Elle a aussi corrige un point qui vaut ici : `os.environ["PYTHONDONTWRITEBYTECODE"]`
pose **apres** le demarrage n'a aucun effet — Python lit ce reglage une seule
fois, au lancement. `sys.dont_write_bytecode` agit vraiment.

### 31.3 L'angle mort du garde « lire avant d'ecrire », CHIFFRE

Promis au tour precedent, mesure ici :

| | |
| --- | --- |
| `Write` sur un fichier non lu | **REFUSE** — le garde fonctionne |
| `sed -i` par Bash | **PASSE** |
| `echo >` par Bash | **PASSE** |
| `Set-Content` par PowerShell | **PASSE** |
| part shell des invocations de cette session | **79,5 %** (1416 Bash / 353 Write) |

Reserve d'honnetete : « invocation » n'est pas « ecriture » — la plupart des
appels Bash lisent. **Le fait decisif est le 3 sur 3, pas le pourcentage.**

**Ce que je ne fais PAS, et pourquoi.** Elargir naivement le garde a Bash
demande d'extraire les cibles d'ecriture d'une ligne de commande. La session
voisine l'a tente aujourd'hui : sa greffe a atteint l'effet (6/6 -> 1/6) et a
**casse `ls > /dev/null` et la restauration depuis sauvegarde**. Elle a
restaure immediatement — *on ne laisse pas un garde trop large en production
le temps de reflechir.*

Sa formule resume l'etat : **« voir l'outil et voir la cible sont deux choses
distinctes »**. Elargir le matcher a PowerShell etait le premier etage ; le
second reste entier, et il est ouvert.

### 31.4 Le garde shell a mordu son auteur, sur une forme qu'il ne couvre pas

Un `cat > x.py <<'ZZ'` portant `\n` a coupe une chaine en deux dans
`nexus_test.py`. **Meme mecanisme que le CAS A** — mais `detecter_cas_a` ne
vise que `python - <<'EOF'`, pas `cat > fichier.py <<'EOF'`. Motif aveugle a
une forme equivalente. **Ouvert.**

### 31.5 Reste OUVERT apres ce tour

* extraire les cibles d'ecriture d'une ligne shell — **decision de conception**,
  avec un echec mesure chez le voisin le jour meme ;
* `detecter_cas_a` aveugle a `cat > f.py <<'EOF'` ;
* rien ne surveille l'apparition d'un **troisieme lanceur** ;
* les 6 `require-atomic-updates`, arbitres non-defauts, sans promesse en vol.

---

## 32. SECURITE 1 — le garde ne voyait pas le shell

### 32.1 Le P0, chiffre avant d'etre corrige

| | |
| --- | --- |
| `Write` sur un fichier non lu | **REFUSE** — le garde fonctionnait |
| `sed -i` par Bash | **PASSE** |
| `echo >` par Bash | **PASSE** |
| `Set-Content` par PowerShell | **PASSE** |
| part shell des invocations de la session | **79,5 %** (1416 Bash / 353 Write) |

Reserve : « invocation » n'est pas « ecriture » — la plupart des appels Bash
lisent. **Le fait decisif est le 3 sur 3, pas le pourcentage.**

### 32.2 Ce qui est pose NE REFUSE RIEN — et c'est une decision

Le garde **journalise** dans `.nexus/ecritures_shell.jsonl`.

Une session voisine a tente le refus direct le meme jour. Sa greffe a atteint
son effet (6/6 → 1/6 de vecteurs aveugles) **et** a refuse `ls > /dev/null` et
bloque une restauration depuis sauvegarde. Retiree de la production dans
l'heure.

> *Un garde trop large se fait desarmer, et c'est pire que le trou.*

On produit donc la mesure sur laquelle decider la politique de refus, au lieu
de la deviner. **Le journal est l'entree de cette decision, pas un substitut.**

### 32.3 Le banc d'acceptation, ecrit AVANT de juger le rendu

Il a paye immediatement : **9 echecs sur 17** au premier jet.

| commande | rendu | attendu |
| --- | --- | --- |
| `echo x > rapport.txt` | `['r']` | `['rapport.txt']` |
| `sed -i 's/a/b/' bench.py` | `['s/a/b/']` | `['bench.py']` |
| `python - < entree.txt` | `['e']` | `[]` — c'est une **lecture** |
| `ls > /dev/null` | `['/']` | `[]` |

### 32.4 Deux defauts de plus, MASQUES PAR UN REMPART

C'est le point le plus instructif du lot.

* Un **decalage d'un cran** dans la numerotation des groupes. Il ne se voyait
  **que** dans le cas guillemets doubles : le `or` court-circuitant, l'index
  invalide n'etait atteint que la, et son `IndexError` etait avale par le
  `except` global qui rend `([], True)`.
* **Deux constantes de module** laissees dehors par mon extraction, meme
  effet.

Dans les deux cas, un filet de securite transformait un bug en
« indetermine » **parfaitement plausible**. *Un rempart qui empeche de planter
empeche aussi de VOIR.*

Et ma garde d'idempotence visait a cote : `"_IGNORED" not in source` rendait
« deja pose » alors que le nom n'y figurait que par ses **usages**, jamais par
sa **definition**.

### 32.5 Trois epreuves, et l'anti-controle qui compte le plus

| | |
| --- | --- |
| **forward** | `Write` sur un fichier non lu reste REFUSE — rien n'est affaibli |
| **reverse** | une redirection non lue est JOURNALISEE, le chemin nomme |
| **fuite** | cinq commandes, dont `ls > /dev/null`, **PASSENT** |

Plus : une commande sans ecriture n'inscrit **rien** — sinon le journal
mesurerait le bruit. `scripts/epreuve_cibles_shell.py`, 16 cas, cablee
(`--only cibles`). Les anti-controles portent **la moitie** du banc.

**Prouve en vrai** : le hook a capte une ecriture reelle de la session, avec
son identifiant. Le premier essai avait echoue pour une raison instructive —
sa premiere action etait `rm -f` sur le journal, execute **apres** que le hook
y eut ecrit. *Une mesure qui s'efface elle-meme.*

### 32.6 Ce qui RESTE ouvert

| Sujet | Etat |
| --- | --- |
| **la politique de refus** | attend les chiffres du journal — c'est son objet |
| **pas de garde de PERIMETRE ici** | le confinement d'un sous-agent n'existe pas dans ce depot ; l'emprunt SAS « agent-perimeter » est toujours ouvert |
| `detecter_cas_a` aveugle a `cat > f.py <<'EOF'` | meme mecanisme, forme non couverte — il a mordu son auteur ce jour |
| un **troisieme lanceur**, demain | rien ne surveille son apparition |
| 6 `require-atomic-updates` | arbitres non-defauts, sans promesse en vol |

La formule de la session voisine resume les deux tours : **« voir l'outil et
voir la cible sont deux choses distinctes »**. Le premier etage a ete ferme
en §31, le second l'est ici — en observation.

---

## 33. LA SECURITE EST DELEGUEE — et le besoin qu'elle renvoie

Decide par l'operateur le 2026-08-31 : **une instance voisine est
temporairement chargee de la securite**, et notamment de recolter la
documentation de securite.

Ce depot cesse donc d'ouvrir des chantiers de securite de son propre chef. Ce
qui est deja pose ici reste en place et continue de mesurer :

| Pose ici | Etat |
| --- | --- |
| `nexus_garde_shell` juge Bash **et** PowerShell, regles par shell | actif, 10 cas |
| `controle_gardes_accordes` — les deux etages ne peuvent plus diverger | actif, 7 cas |
| journal des ecritures shell non lues | actif, **observation seule** |

**Ce qui reste ouvert cote securite est transmis, pas abandonne** : la
politique de refus attend les chiffres du journal ; ce depot n'a **aucun**
garde de perimetre pour un sous-agent ; `detecter_cas_a` est aveugle a
`cat > f.py <<'EOF'`.

### 33.1 Le besoin renvoye : une documentation ingerable par un petit modele

L'instance de securite demande *une documentation complete, parsee, prete a
l'ingestion par des agents, digeste **meme pour un qwen 1b ou 3b***.

Ce depot possede deja la moitie de la reponse et l'ignorait : `nexus_doc.py`
sert **166 507 symboles** par `seek`, a **~280 jetons la consultation** —
l'entree est lue a son offset, jamais le fichier. C'est exactement le profil
qu'un modele de 1 a 3 milliards de parametres peut absorber.

**Mais la voie d'INGESTION n'existait pas.** Les trois corpus annexes — bash,
PowerShell, lecons — sont arrives **deja indexes** depuis un depot voisin. Le
format est CONSOMME ici, jamais PRODUIT :

```
references/<corpus>/index.tsv       id, offset_octets, longueur_octets, type, resume
references/<corpus>/symbols.jsonl   une entree JSON par ligne
```

C'est la capacite a construire, et elle sert les deux besoins a la fois : la
securite obtient son corpus ingerable, et ce depot gagne le moyen d'absorber
n'importe quelle documentation — les **33 000 fichiers** repertories et jamais
exploites en tete de ce cockpit.

---

# 34. LA LISTE UNIQUE DES SUJETS OUVERTS — au 2026-08-31

> Onze sections « Reste OUVERT » etaient dispersees dans ce cockpit
> (§184, §9.3, §10.3, §25.2, §26.3, §27.5, §28.5, §29.8, §30.6, §31.5, §32.6).
> Elles gardent leur contexte et leurs mesures ; **cette table les reunit**, et
> c'est elle qu'on lit d'abord.
>
> Rappel du critere : un sujet ne se clot que lorsqu'un **controle echoue** si
> la regle est enfreinte. Un paragraphe ne ferme rien.

## 34.1 DECISIONS DE L'OPERATEUR — je ne les prends pas seul

| Sujet | Ce qui est en jeu |
| --- | --- |
| Exposer `insert` et `audio` | 5 modeles declarent `insert`, 2 declarent `audio`. Les exposer demande des chemins d'API nouveaux |
| Promotion sans demotion | les epreuves promeuvent, ne demeuvent jamais ; une promotion peut tenir sur un seul passage |
| 40 `.bak` dans `scripts/.nexus/` | signales en ALERTE a chaque passage de la porte — ce sont vos donnees |
| Le cliquet ne RESSERRE pas | ecrire la reference pendant le rituel salit l'arbre au moment ou il le verifie |
| Indexation hors depot | la session voisine a tranche « non par defaut, oui sur opt-in trace ». Non implemente ici |

## 34.2 SECURITE — delegue a l'instance voisine (§33), transmis et non abandonne

| Sujet | Etat |
| --- | --- |
| La politique de REFUS des ecritures shell | attend les chiffres du journal `.nexus/ecritures_shell.jsonl` — c'est son objet |
| **Aucun garde de PERIMETRE** ici | le confinement d'un sous-agent n'existe pas dans ce depot ; l'emprunt SAS « agent-perimeter » est toujours ouvert |
| `detecter_cas_a` aveugle a `cat > f.py <<'EOF'` | meme mecanisme que le CAS A, forme non couverte. **A mordu son auteur le 31/08** |
| Un TROISIEME lanceur, demain | rien ne surveille l'apparition d'un outil shell non garde |
| Anti-drift, recolte automatique des worktrees | empruntes a SAS, jamais poses |

## 34.3 MESURE ET OUTILLAGE — mesures faites, causes non etablies

| Sujet | Ce qui est mesure | Ce qui manque |
| --- | --- | --- |
| Lenteur du pont MCP | >120 s contre 10,6 s en direct | cause. L'hypothese de la ruee sur le cache est **refutee** |
| P4 : six familles rendent vide a 2200 jetons | `mesure_rendu_vide.py` livre et cable | **jamais joue** sur les neuf familles |
| `--fusionner` : deux familles ont declare les fichiers vides | la session voisine a retracte sa cause | reproduire sans clause d'echappement |
| ~75 violations Python | `SIM115` x17, `B007` x12, `RET503` x9 | arbitrage par classe |
| 6 `require-atomic-updates` | arbitres **non-defauts** : caches memo, appel duplique et non corruption | la promesse en vol partagee, si on la veut |
| Cecite d'un tour du cliquet de cablage | `git ls-files` ignore un script neuf non commite | **mesure : la cecite dure UN TOUR**, pas plus |
| Un apparieur de noms sans epreuve | a rendu **deux inventaires faux en un jour**, dans deux depots | une epreuve |

## 34.4 CAPACITES LOCALES — le gisement, et ce qui n'est pas branche

| Sujet | Chiffre |
| --- | --- |
| **La voie d'INGESTION de documentation n'existe pas** | le format `index.tsv` + `symbols.jsonl` est CONSOMME ici, jamais PRODUIT. C'est le besoin renvoye par l'instance de securite (§33.1) |
| 33 000 fichiers de documentation et bibliotheques | jamais exploites |
| Les livres | 12 793 fichiers, plus 5 381 de code associe |
| Douze outils voisins reperes | jamais repris |
| 5 modeles installes sans mesure | 4 embeddings + 1 OCR/vision — un banc *chat* ne les mesure pas, et ne le devrait pas |
| `deepseek-ocr` installe | **vision + completion declarees** ; exposition a verifier |

## 34.5 REGLES ECRITES QUE RIEN NE GARDE

| Regle | Ou elle est ecrite | Ce qui manque |
| --- | --- | --- |
| Chaque worker dans un **worktree git isole** | contrat §0.4 | `nexus_essaim.py` ecrit hors du depot, mais dans un repertoire — **pas un worktree** |
| Preserver le contexte de l'orchestrateur | contrat §0.4 | aucun controle |
| L'orchestrateur n'ecrit pas le correctif | contrat §0.1.5 | `controle_delegation` mesure les REQUETES, qu'un patch ecrit a la main ne bouge pas |
| La classe **fail-open** | §26 | aucun motif dans `nexus_traque.py` — **quatre occurrences trouvees a la main** |

## 34.6 PISTES OUVERTES PAR L'OPERATEUR, jamais traitees

* **Meta-learner** — apprendre le routage depuis les traces
* **Harnais** — au sens large
* **AST** — crible syntaxique plutot que lexical
* **Temperature des modeles locaux** — territoire metaheuristique reconnu (§106.2), observation store construit, jamais exploite
* **Reseaux de neurones et apprentissage automatique pour ce projet**
* **Metaheuristiques hybrides**, bandits, optimisation bayesienne (§0)

## 34.7 VERIFICATIONS JAMAIS FAITES

* `Start-Claude.ps1` jamais joue de bout en bout
* Les modeles cloud echouent en serie — cause non etablie
* 9 appels Anthropic sur 9 echouent
* `nexus_test_outillage.py` orphelin
* `import subprocess` en portee locale (`nexus_ruche.py:205`)
* Trois scripts « mieux cables » sans cause etablie

---

## 35. LA VOIE D'INGESTION — le format etait consomme, jamais produit

Repond au besoin renvoye par l'instance de securite (§33.1), et ouvre le
gisement des **33 000 fichiers** de §34.4.

### 35.1 Ce qui existait, et ce qui manquait

`nexus_doc.py` sert **166 507 symboles par `seek`**, a ~280 jetons la
consultation. C'est exactement le profil qu'un modele de 1 a 3 milliards de
parametres peut absorber. Mais les trois corpus annexes etaient arrives
**deja indexes** d'un depot voisin : le format etait **consomme ici, jamais
produit**.

`scripts/nexus_ingerer.py` le produit desormais :

```
python scripts/nexus_ingerer.py --source docs/securite --nom securite \
       --resumer glm-4.7-flash-local --appliquer
```

### 35.2 Quatre defauts, tous trouves EN S'EN SERVANT

| Defaut | Ce qu'il causait |
| --- | --- |
| identifiants finissant par un **compteur** | le chercheur matche le DERNIER segment (`bash.trap` → « trap ») : corpus correct et **introuvable** |
| chargeur portant `("shell_docs", "lecons")` **grave** | corpus neuf indexe et pourtant invisible a la consultation |
| `type` ecrit dans l'index, **pas dans l'objet** | chaque entree d'un corpus sain s'annoncait « type non reconnu » |
| resume du modele local ecrit dans l'objet, **pas dans l'index** | « 4 resumes produits » et **aucun** dans la colonne que le petit modele lit |

Le deuxieme a produit **deux verites contradictoires dont aucune ne mentait** :
« 201 offsets verifies » et « aucun symbole ne correspond ». Elles portaient
sur deux chemins de code differents -- et le « 201 » ne portait meme pas sur
les annexes : il vient de l'index PYTHON. Corrige en §36.

Le quatrieme est la **troisieme occurrence du jour** de « produit, non
consomme » — apres `modelesResidents` ecrite et jamais appelee, et le format
d'index lui-meme.

**Le piege PRINCIPAL, lui, a ete tenu du premier jet** : les offsets sont en
octets, jamais en caracteres. Parce qu'il etait **dit dans la consigne**. Le
document d'essai de l'epreuve porte des accents : sur un corpus sans accent,
octets et caracteres coincident et l'epreuve serait verte a tort.

### 35.3 Le resume est produit par un MODELE LOCAL

Mesure avec `glm-4.7-flash-local` : **4 resumes, 0 echec, 68 s** chargement a
froid compris. Ce que l'index porte desormais, la ou il portait un titre :

> « Highlights measured improvements and the necessity of rejecting bad tasks,
> advocating for over-exploiting MCP tools on both planes »

**Le seul defaut invisible de ce mecanisme** est le glissement : si la reponse
est plus courte que le lot, redistribuer les lignes dans l'ordre donne a
chaque entree le resume d'une AUTRE. L'index annonce un contenu, le seek en
rend un different, et **rien ne signale la discordance puisque les offsets
sont exacts**. Le cas est joue en premier, ligne manquante au milieu.

### 35.4 Deux defauts de ma propre main, attrapes avant la production

* j'ai **invente un nom de variable** — la boucle s'appelle `ent`, pas
  `entree`. Exactement le reproche fait au banc trois fois ce jour ;
* mon bloc de collision a ete pose **a la mauvaise indentation** : sorti du
  `for`, il a fait avaler la construction de l'objet par le `else`. Le fichier
  **compilait**. *Une substitution textuelle dans du Python doit porter son
  indentation, sinon elle deplace la portee sans rien dire.*

Deux gardes de pose ont **refuse de deviner** et montre les formes reelles
plutot que d'ecrire au hasard dans un fichier qui fonctionne.

### 35.5 Reste OUVERT

| Sujet | Etat |
| --- | --- |
| **quel corpus ingerer** | le corpus d'essai a ete retire : c'etait une copie du contrat, et une copie ment des que l'original bouge |
| la securite recolte sa documentation | l'outil l'attend ; c'est son geste (§33) |
| les 33 000 fichiers | l'outil existe maintenant ; le choix de ce qu'on absorbe reste entier |
| resumer un GROS corpus | mesure sur 4 entrees. 200 entrees feraient ~17 lots ; le cout reste a mesurer |

---

## 36. LE CORPUS VOISIN ABSORBE — et ce qu'un producteur INDEPENDANT revele

L'instance chargee de la securite (§33) a livre son corpus et son extracteur.
Emprunte **par copie**, jamais lu en place, conformement au contrat §0.

### 36.1 Le contrat de format tient des deux bouts

`references/securite_confinement/` — **28 entrees**, produites par un outil
que je n'ai pas ecrit, absorbees par le lecteur bati ici : decouvertes, lues
a leur offset, rendues. Leur index porte meme **six colonnes** au lieu de cinq
— une colonne `convention` inseree — et le lecteur tient, ne lisant que les
trois premieres.

C'est la validation que mon propre essai ne pouvait pas donner : le producteur
etait moi.

### 36.2 Une affirmation FAUSSE de ma part, corrigee

J'ai ecrit deux fois — dans un commentaire de code et au cockpit §35 — que le
corpus ingere etait « **verifie**, 201 offsets relus par seek ». **C'etait
faux.** Ce nombre vient de `construire_index`, qui indexe la documentation
PYTHON. Il ne dit rien des annexes.

J'ai lu 201 au moment ou j'ingerais 201 entrees, et attribue la coincidence.
La classe est nommee dans ce depot : *l'instrument qui repond a la question
voisine*.

### 36.3 Le fait grave etait derriere : rien ne verifiait les annexes

`verifier_offsets_annexe` etait **definie et appelee nulle part**. Un corpus
etranger aux offsets decales — calcules en caracteres au lieu d'octets, **le**
piege du format — aurait ete servi en silence : chaque consultation rendant le
contenu d'une AUTRE entree, sans que rien ne le signale, le fichier etant
parfaitement lisible.

**Et une fois cablee, la verification NE MORDAIT PAS.** Contre-epreuve : les
28 offsets du corpus voisin tous decales de 7 octets → construction verte,
code 0, aucun mot. **60 tirages repartis sur une liste a plat de 3769 entrees
ne touchent jamais un corpus de 28.** Je venais de poser un vert qui ne peut
pas rougir.

Le remede n'est pas d'agrandir l'echantillon — a 1,6 % de couverture il
faudrait le multiplier par soixante pour *esperer* — mais de le **repartir par
corpus**. Un corpus est produit par un outil unique : s'il se trompe, il se
trompe sur TOUTES ses entrees.

Ferme par `scripts/epreuve_offsets_annexes.py`, 5 cas, cablee
(`--only offsets`), avec son corpus jetable a offsets decales.

### 36.4 La confrontation des deux extracteurs — 26 commandes

| | |
| --- | --- |
| accords | **19** |
| desaccords | **4** |
| indetermines | 3 |

L'arbitrage donne tort **aux deux**, sur des cas differents :

| commande | le mien | le leur | verdict |
| --- | --- | --- | --- |
| `Set-Content f.txt 'x'` | `[]` | `['f.txt']` | **eux** — trou chez moi |
| `Out-File -FilePath f.txt` | `[]` | `['f.txt']` | **eux** |
| `bash -c 'echo x > f.txt'` | `["f.txt'"]` | `[]` | **ni l'un ni l'autre** |
| `eval 'echo x > f.txt'` | `["f.txt'"]` | `[]` | idem |

Le troisieme est le plus instructif : mon chemin est **malforme** —
l'apostrophe fermante de l'argument y est collee — et leur liste vide est un
**fail-open**, l'ecriture devenant invisible. La bonne reponse est `['f.txt']`.

### 36.5 Le correctif a ete TENTE et RETIRE

Le rendu du banc a casse **13 cas sur 16**. Restaure immediatement : *on ne
laisse pas un correctif regressif en place le temps de reflechir* — la meme
regle que la session voisine a appliquee a sa greffe le matin. 16/16 apres
restauration.

### 36.6 Reste OUVERT, avec son sol exact

* **Set-Content, Add-Content, Out-File** ne sont pas reconnus par mon
  extracteur. Le sol est ci-dessus, mesure ; le correctif reste a produire.
* **L'apostrophe orpheline** en fin de cible non citee. Anti-controle a tenir :
  un nom de fichier peut legitimement contenir une apostrophe au MILIEU.
* **Leur fail-open sur `bash -c`** — a leur transmettre : leur extracteur rend
  `[]` la ou l'ecriture a lieu.
* Leur `cibles_shell.py`, `eprouver_cibles.py` (19 cas) et `mesurer_classes.py`
  (28 vecteurs mesures) sont **sur disque** ici, jamais encore joues en entier.

---

## 37. LE SCHEMA D'ARCHITECTURE SOUMIS — a examiner

Transmis par l'operateur le 2026-08-31. **Inscrit ici comme SOUMISSION, pas
comme fait etabli** : c'est ce qu'il a demande, et le contrat veut qu'on
verifie avant d'adopter.

### 37.1 Ce qu'il affirme, et qui est JUSTE

**Les trois voies ne sont pas symetriques**, et c'est le point central :

```
CLAUDE CODE (abonnement claude.ai)   -->  orchestrateur, NE passe PAS par LiteLLM
        |
       MCP
        |
   nexus-local  -->  LiteLLM  -->  Ollama local / Ollama Cloud / Anthropic API
```

Cela concorde avec le contrat §106 : mettre une clef de passerelle devant
Claude Code lui ferait employer cette clef plutot que l'abonnement. La
formulation exacte du contrat est plus fine — `ANTHROPIC_BASE_URL` seul ne
remplace PAS l'abonnement ; `ANTHROPIC_AUTH_TOKEN` (ou `apiKeyHelper`) si.

La distinction **Anthropic API != abonnement Claude** est juste, et elle
merite d'etre repetee : la branche `LiteLLM -> Anthropic` est facturee au
jeton sur le compte API, jamais sur l'abonnement.

### 37.2 Ce qui est FAUX, et d'ou cela vient

| Affirmation | Mesure du 2026-08-31 |
| --- | --- |
| « 33 alias locaux » | **53** |
| « 19 alias cloud » | 19 — juste |
| « 4 alias Anthropic » | 4 — juste |
| six outils MCP cites | **12** exposes (la liste etait illustrative) |

**Le schema cite fidelement le README. C'est le README qui est perime** — et
il est la VITRINE PUBLIEE. Deux chiffres y ont gele :

* ligne 49 : « 33 alias » pour le plan local, contre 53 mesures ;
* ligne 304 : « sur les 40 modeles locaux mesures », contre 47 mesures et
  installes (52 installes, dont 5 embeddings et OCR qu'un banc *chat* ne
  mesure pas).

C'est la regle de ce depot retournee contre lui : *une mesure gelee ment le
lendemain*. Elle a ete empruntee au depot voisin, appliquee aux pools, au
port du moteur, aux corpus annexes — et pas au README.

### 37.3 Ce qui reste a EXAMINER, et que je ne tranche pas

* **A2A — Agent2Agent.** Le schema le place « plus tard et au-dessus » de
  MCP, pour faire cooperer des agents specialises (dev, test, securite). Rien
  n'existe ici pour cela, et il ne faut pas le confondre avec MCP : *MCP
  branche un agent a des CAPACITES ; A2A branche des agents ENTRE EUX.* Ce
  depot pratique deja une forme artisanale d'A2A — deux sessions qui
  s'echangent des mesures, des refutations et du code par l'operateur — et
  cette journee en montre le rendement : la confrontation de deux extracteurs
  a trouve cinq defauts qu'aucun des deux bancs internes ne voyait, chacun
  ayant ete ecrit par l'auteur de sa fonction. **Ce qu'il faut examiner n'est
  donc pas « faut-il de l'A2A » — il y en a — mais s'il doit etre MECANISE.**
  L'operateur signale des livres sur A2A et MCP, plus du code source, dans les
  depots voisins : matiere a emprunter PAR COPIE, et matiere a INGERER
  (§35).

* **MCP : ce que le schema dit, et ce que la mesure dit.** Il affirme que
  « Nexus decide ensuite quel backend/modele utiliser ». Mesure sur les douze
  outils du pont : **un seul** (`nexus_ask`) accepte un **profil**, et
  `nexus_route` route par la tache. Tous les autres prennent un **modele
  nomme par l'appelant**. *L'architecture decrite est donc plus automatique
  que celle qui est implementee* — l'orchestrateur choisit, Nexus execute.
  C'est un ecart a trancher : etendre les profils, ou corriger la description.
* **« Nexus doit rester une infrastructure generique »**, socle des futurs
  projets, et ne pas devenir un projet de negoce ou de science des donnees.
  C'est une orientation, pas un fait mesurable — et elle a des consequences
  concretes : ce qui entre dans `scripts/` doit servir toute plateforme, pas
  un domaine.
* Le schema ne mentionne pas les **4 routeurs** adaptatifs, qui sont pourtant
  une voie a part entiere — un alias de routeur ne designe pas un moteur mais
  une politique.

### 37.4 Ce que cela ouvre immediatement

**Aucun controle ne garde les chiffres du README.** Ils sont publies, cites
par d'autres — ce schema en est la preuve vivante — et rien ne rougit quand
ils divergent du parc reel. C'est un sujet ouvert, et il est mecanisable.

---

## 38. LE SUJET OUVERT DE §36.6, CLOS — cinq defauts, un a la fois

### 38.1 Le resultat

| | avant | apres |
| --- | --- | --- |
| notre banc interne | 16 cas | **28 cas, 0 echec** |
| leurs 19 cas independants | **17/19** | **19/19** |
| confrontation croisee, 26 commandes | 19 accords, 4 desaccords | **21 accords, 2 desaccords** |

Et les **deux desaccords restants sont des cas ou nous avons raison et eux
non** : sur `bash -c 'echo x > f.txt'` nous rendons `['f.txt']`, ils rendent
`[]` — leur ecriture devient invisible. **A leur transmettre.**

### 38.2 Les cinq defauts fermes

| Defaut | Rendu mesure | Attendu |
| --- | --- | --- |
| trois verbes PowerShell absents | `[]` | `['f.txt']` |
| `sed` ne prenait que le DERNIER fichier | `['b.py']` | `['a.py','b.py']` |
| `sed` sans `-i` — l'anti-controle | — | `[]`, il LIT |
| citation non fermee | `['"non']` | `[]`, **indetermine** |
| apostrophe orpheline collee | `["f.txt'"]` | `['f.txt']` |

Les deux derniers sont la meme classe : **un chemin malforme rendu comme s'il
etait sur**. Le journal en porterait la trace, et l'analyse qui en decoulerait
serait fausse.

### 38.3 LA LECON DU TOUR : la forme de la delegation etait le defaut

| Forme | Resultat |
| --- | --- |
| une consigne portant les **cinq** defauts | **13 cas casses sur 16**, retiree |
| une seconde, memes cinq, avec les echecs mesures | **13 casses**, retiree |
| **un defaut a la fois**, trois fois de suite | **0 regression**, chaque fois |

Le delegue n'etait pas en cause. Une consigne large invite a une reecriture
globale, et une reecriture globale casse ce qu'elle ne vise pas. *Un defaut
par consigne, avec la liste de non-regression en entier.*

C'est mesurable et il faut le dire : **deux jets larges, deux echecs ; trois
jets etroits, trois reussites.**

### 38.4 Trois defauts de MES propres outils, trouves en chemin

* Le harnais qui lit leurs cas s'ancrait sur le **premier crochet apres
  `CAS`** — celui de l'ANNOTATION `list[tuple[...]]`, pas de la liste. Le
  message d'erreur etait exact et se lisait « leur fichier est illisible ».
* Mon extracteur de rendu a **rejete un rendu correct** de 592 octets : son
  plancher visait de gros blocs. Pire, son message accusait le banc — « n'a
  probablement rien rendu » — alors qu'il avait rendu juste. *Un garde qui
  diagnostique a la place envoie chercher au mauvais endroit.*
* Ma garde d'idempotence a vu « Set-Content » **dans la docstring** et conclu
  « cas deja graves » sur un fichier ou aucun ne l'etait. **Troisieme fois du
  jour** que je vise un nom au lieu de sa forme reelle.

Et le motif d'extraction, retape six fois dans la journee avec une variante et
parfois un defaut a chaque fois, a ete pose UNE fois dans le bac a sable.

---

## 39. DEUX SOURCES QUI MENTAIENT — et un emoji coupe en deux

### 39.1 Les chiffres du README, gardes par un controle qui BLOQUE

Le README est la **vitrine publiee**. Il portait « 33 alias » la ou la
configuration en declare **54**, et « 40 modeles locaux mesures » pour **48**.
Ces chiffres ont ete **cites par un tiers** qui lisait le README, et repris
comme vrais — c'est ainsi qu'ils ont ete decouverts.

`controle_readme_chiffres` compare desormais les trois nombres a la
**configuration declaree** — et non a la passerelle, car la conformite tourne
AVANT le demarrage : lire la passerelle exigerait qu'elle soit allumee
precisement quand elle ne l'est pas.

Severite raisonnee : **BLOQUE**, parce que le fichier est publie et que
corriger un nombre est trivial. La phrase « NN modeles mesures » n'est
qu'une **ALERTE** : les modeles mesures sont une sous-population des alias, et
les deux peuvent legitimement differer.

### 39.2 Ce que ce controle a trouve dans la minute suivante

Il annoncait **54 declares** contre **53 exposes**. L'ecart tenait a un seul
alias : **`deepseek-ocr-local`, declare sur le disque et repondant « Invalid
model name »**. Une capacite d'OCR installee, declaree, inutilisable — et
c'est l'entree « exposition a verifier » de §34.4, fermee par la mesure.

### 39.3 La cause : DIX HEURES ET QUARANTE MINUTES de derive

```
litellm_config.yaml modifie a   10:22
conteneur litellm demarre a     23:41 la veille
```

Le contrat §82 dit « ne jamais supposer que la configuration est active parce
que le fichier est correct ». **Rien ne le mecanisait** — mesure : zero
occurrence dans les controles.

Consequence plus large : **toute mesure prise contre la passerelle ce jour-la
decrivait un processus perime**, y compris des comptes que j'ai inscrits en
documentation.

`controle_config_active` le dit desormais, **en ALERTE et jamais en BLOQUE** :
bloquer sur « la passerelle sert une configuration perimee » empecherait
precisement la sequence qui la redemarre. Le detail porte le geste :
`docker compose restart litellm`.

**Et j'ai accuse ce controle a tort** : son instant m'a paru faux de cinq
heures. La machine est en **UTC−5**, pas UTC+2 — j'avais deduit le fuseau de
la langue de l'interface. Inferer d'un signal voisin, exactement la classe que
ce depot nomme.

### 39.4 Un emoji coupe en deux — defaut signale par l'instance voisine

Rapport exemplaire : symptome verbatim, differentiel, reproduction minimale.

```
corpus AVEC emojis (10 fichiers sur 184) -> HTTP 500 « surrogates not allowed »
corpus SANS emoji  (0 sur 106)           -> SUCCES, 470 extraits
```

Ils ont d'abord soupconne le corpus. Leur scan a rendu **zero fichier fautif
sur 184**, et c'est ce zero qui a retourne l'enquete vers l'outil. *Avant
d'accuser une matiere, mesurer si elle porte vraiment le defaut qu'on lui
prete.*

**Cause confirmee ici, ligne 958** : une chaine JavaScript est stockee en
UTF-16, et `slice` coupe en **unites de code**, pas en points de code. Un
emoji en occupe **deux**. La frontiere a `CHUNK_CHARS = 1400` tombait entre
les deux — d'ou la « position 1425 » de leur message.

**Prouve en vrai** : un corpus portant un emoji **exactement a la frontiere**
s'indexe maintenant, 5 extraits, aucun 500.

Ce que l'epreuve garde **en plus** du defaut : qu'on ne PERDE RIEN. Un `break`
sur cas degenere abandonnerait la fin du texte **sans le dire**, et l'erreur
d'origine, elle, se voyait.

### 39.5 Un FAUX ANTI-CONTROLE dans l'epreuve que je livrais

```python
for case in ["FORWARD", "REVERSE", "DETAIL COMPLET", "FUITE"]:
    # nothing to do, verifier already checked
    pass
```

Une boucle vide se declarant « deja couverte ». Elle n'affirmait **rien** — un
vert qui ne peut pas rougir, dans l'epreuve meme qui garde les autres. Le
cliquet l'a signalee comme variable de boucle inemployee : **un motif de style
pointant un defaut de fond**. Remplacee par un anti-controle qui joue les
quatre situations.

### 39.6 Reste OUVERT

| Sujet | Etat |
| --- | --- |
| **`.nexus/index.json` est un index UNIQUE** | signale par l'instance voisine : en construire un second ECRASE le premier. Indexer plusieurs corpus demande une racine commune ou un choix. Non traite |
| la derive de configuration mesuree | le redemarrage est un geste d'operateur ; la tache quotidienne le fait a 04:00 |
| assertions visant un MOT plutot qu'une valeur | une l'a fait ici, et a casse au premier reformulage. Aucun controle ne garde ce motif |

---

## 40. `nexus` INTROUVABLE DANS UNE EDITION DE POWERSHELL — incident vecu

### 40.1 Le blocage

L'operateur ouvre un terminal sur un autre projet :

```
PS G:\TRADING_LIVE_IA> nexus mcp
nexus : Le terme «nexus» n'est pas reconnu...
```

Bloque : sans cette commande, impossible de brancher le pont sur un nouveau
projet. **Trouve en se servant, pas en relisant.**

### 40.2 La cause, mesuree

Windows porte **deux editions** de PowerShell, avec **deux profils** dans deux
repertoires distincts :

| profil | edition | `nexus` |
| --- | --- | --- |
| `Documents/PowerShell/...` | pwsh 7 | 5 occurrences |
| `Documents/WindowsPowerShell/...` | **5.1** | **0** |

`Install-NexusCommande.ps1` vise le `$PROFILE` de la session **qui le lance**.
Il avait ete lance depuis pwsh 7 ; l'edition 5.1 ne l'a jamais eue, et rien ne
le disait.

**Complication qui aurait fait chercher au mauvais endroit** : le dossier
Documents est **redirige vers OneDrive** sur cette machine. Les profils vivent
sous `~/OneDrive/Documents/`, pas sous `~/Documents/`. Un controle naif ne
verrait rien et conclurait a tort que la commande est absente **partout**.

### 40.3 Ferme par un controle qui echoue

`controle_commande_nexus` examine les **huit** chemins possibles — deux bases,
deux editions, deux noms de profil — regroupe par EDITION, et **dit laquelle
manque et quel geste repare**. ALERTE et non blocage : une commande de confort
absente n'empeche pas la plateforme de fonctionner.

`scripts/epreuve_commande_nexus.py`, 7 cas, cablee (`--only commande`), dont le
piege OneDrive et le cas « aucun profil » qui doit rendre IGNORE — *une machine
neuve n'est pas une machine mal configuree.*

Verifie apres correction : les deux editions sont servies.

## 41. LE RAPPORT VOISIN SUR L'INDEX — juste sur l'effet, faux sur la cause

L'instance voisine rapporte : « `.nexus/index.json` est un seul index — en
construire un autre ecrase le precedent ».

**Mesure faite, et elle les corrige :**

| situation | resultat |
| --- | --- |
| second corpus, **meme modele** | **s'AJOUTE** — 2 fichiers, 8 extraits |
| second corpus, **modele different** | **remplace** — 2 fichiers → 1 |

Le remplacement est **correct** : des vecteurs produits par deux modeles ne
sont pas comparables. **Le defaut est qu'il est SILENCIEUX.**

Le code calcule bien un motif — « modele different : vecteurs non
comparables » — mais l'envoie dans `log()`, donc sur **stderr**, invisible a
l'appelant MCP. La reponse annonce « Index construit » sans dire que le
precedent a ete detruit.

Leur rapport est donc **juste sur l'effet, faux sur la cause — et le vrai
defaut est pire que celui qu'ils decrivaient** : ils croyaient a un ecrasement
systematique ; c'est une perte conditionnelle et muette.

### 41.1 OUVERT

Le correctif — porter le motif et le nombre d'extraits perdus dans la reponse
rendue — a ete redige mais **non greffe** : le rendu du banc n'a pas respecte
le separateur demande, et la greffe a ete refusee par son propre assert plutot
qu'appliquee au hasard. Le sol est mesure et inscrit ici ; rien n'a ete pose a
moitie.

---

## 42. LA PERTE D'INDEX CESSE D'ETRE SILENCIEUSE — §41.1 ferme

Ce que l'appelant lit desormais quand un remplacement a lieu :

```
Index construit.
  fichiers: 1
  extraits: 4
  modele  : nomic-embed-text-local
  ATTENTION : l'index precedent a ete REMPLACE, non fusionne.
    motif   : modele different (bge-m3-local -> nomic-embed-text-local)
    perdus  : 8 extrait(s)
```

Le cas de fusion reste intact : deux corpus au meme modele donnent toujours
2 fichiers et 8 extraits, sans avertissement.

**Le compte se prend AVANT la perte.** Quand il y a remplacement, la liste des
anciens est deja vide : compter dessus donnerait toujours zero — un chiffre
FAUX plutot qu'une absence de chiffre.

**Et quand l'index precedent est ILLISIBLE, le compte est INCONNU.** Le motif
le dit, et le compte reste a zero. Rendre un chiffre serait mentir ; le taire
ferait croire a zero perte.

### 42.1 TROIS DEFAUTS DE L'EPREUVE ELLE-MEME, et le second certifie a tort

| Defaut de la fixture | Effet |
| --- | --- |
| champ `modele` au lieu de `model` | le modele du precedent valait toujours `undefined` |
| modele courant passe comme **objet** | un objet n'est jamais egal a une chaine |
| enregistrements portant `id` au lieu de `file` | le code levait, et le rempart transformait la levee en « index illisible » |

Les deux premiers se combinent : la comparaison des modeles etait **toujours
vraie**, et **deux cas passaient par coincidence** — ils attendaient
precisement cette branche.

**Deux verts pour la mauvaise raison, dans l'epreuve censee garder les
autres.** Une epreuve verte a tort est pire qu'une epreuve absente : elle
certifie.

Le troisieme est du meme ordre : la fixture faisait lever le code, et le
diagnostic rendu — « index precedent illisible » — accusait le code d'une
panne qui n'existait pas. Le rempart, en transformant la levee en motif
plausible, l'a rendue credible.

### 42.2 Et mon extracteur ne connaissait que Python

Il cherchait l'ouverture de bloc `python` et rendait « aucun debut de code
reconnu » sur un rendu **JavaScript parfaitement bon**. Elargi une fois, aux
six ouvertures possibles — plutot que contourne.

---

## 43. LES LIVRES A2A / MCP, EMPRUNTES PAR COPIE — et le risque qu'ils portaient

L'operateur signale des livres sur A2A et MCP dans les depots voisins, « et
meme du code source ». Emprunte, mais pas sans mesurer d'abord.

### 43.1 Ce qui a ete trouve

`_REFERENCE_LIVRES/` du depot voisin porte des corpus **deja au format que ce
lecteur consomme** — `index.tsv` + `symbols.jsonl`. Aucune ingestion
necessaire : une copie suffit.

| corpus | entrees | matiere A2A / MCP / agents |
| --- | --- | --- |
| `epub` | 11 376 | **502 lignes d'index** |
| `packt` | 6 697 | **373 lignes** |
| `pdf_references` | 21 | 0 |

**875 entrees** de matiere pertinente.

### 43.2 LE RISQUE, ET IL ETAIT REEL

La matiere est faite de **livres commerciaux** — « 30 Agents Every AI Engineer
Must Build » est un titre Packt. Or `references/` **est publie** : sept
fichiers y etaient deja suivis.

Copier 51 Mo d'oeuvres sous droits dans une vitrine **publique** aurait ete une
faute irreversible : *ce qui part sur GitHub reste indexe meme efface ensuite*
— la raison d'etre du controle absolu de §0.3.

**L'ignorance a donc ete posee AVANT la copie, et prouvee avant :**

```
.gitignore:62:references/livres/   references/livres/x/essai.txt
```

Puis verifie apres : **0 fichier suivi** sous `references/livres/`. Le depot
avait deja la convention — `python_libs_docs`, `shell_docs` et `lecons` sont
ignores individuellement — et elle a ete suivie plutot qu'inventee.

### 43.3 Ce que cela donne

L'index couvre desormais **21 842 entrees sur 7 corpus**, offsets verifies par
corpus. Le contenu des livres remonte a son offset, verifie.

### 43.4 Un troisieme corpus qui s'annoncait casse

`[type de corpus non reconnu : 'section']` sur **chacune** des 18 000 entrees.
La meme classe que pour le type `doc`, corrigee une premiere fois en ajoutant
une branche.

**Ajouter une branche PAR TYPE est un remede qui se represente a chaque corpus
neuf** — le troisieme l'a montre. Le repli distingue maintenant deux etats que
le cri confondait :

* l'objet porte de quoi etre rendu -> on le rend, en NOMMANT le type sans le
  declarer fautif ;
* l'objet ne porte rien -> le cri est justifie, et il enumere les champs
  presents.

LOI 1 a signale que **la branche neuve n'etait couverte par rien** — le cas
existant testait un objet SANS contenu et exercait toujours l'alarme. Deux cas
ajoutes, dont **l'anti-controle** : l'alarme doit RESTER quand elle dit vrai,
sans quoi un objet reellement vide se lirait comme une absence de contenu.

### 43.6 Le CODE SOURCE des livres, ajoute — et pourquoi la projection

L'operateur : « il y a des codes sources aussi ». Deux formes existaient chez
le voisin :

| forme | volume | etat |
| --- | --- | --- |
| depots bruts | **1,87 Go** | inexploitable tel quel |
| **projection** | **17,8 Mo** | deja au format consommable |

La projection a ete prise : **2 231 entrees, dont 1 277 portant sur les
agents, MCP ou A2A** — 57 % du corpus. Sous le meme chemin ignore, verifie a
zero fichier suivi.

**Ses identifiants finissent par un NOM DE SYMBOLE REEL**, ce qui les rend
directement consultables — a la difference des livres, dont l'identifiant est
un slug de titre.

Preuve, sur `nexus_doc.py build_react_agent` :

```
### code.0117127e.Context-Engineering-for-Multi-Agent-Systems.langchain.lc_boot.build_react_agent
    source : references/livres/code/symbols.jsonl (offset 15339, 2861 o)
[type « function », rendu generique]
def build_react_agent(engine: ContextEngine):
    The same four tools handed to LangChain's standard agent builder.
    Difference from Route A: there is no plan object...
```

Le code source d'un livre sur les systemes multi-agents, sa docstring et son
commentaire de conception, a ~280 jetons la consultation. **L'index couvre
desormais 24 073 entrees sur 8 corpus.**

Et le rendu generique pose au meme tour (§43.4) sert immediatement : le type
`function` n'aurait pas ete reconnu autrement.

### 43.5 Reste OUVERT — et c'est une limite de nature, pas un defaut

`nexus_doc.py` est une **recherche par IDENTIFIANT**, pas par contenu. On
atteint un chapitre en connaissant le nom du livre ; on n'atteint pas « ce que
les livres disent d'A2A » par le sujet.

Pour cela il faut `nexus_index_build` — une indexation par embeddings sur
**18 073 entrees**, dont le cout n'est pas mesure. C'est le prochain geste, et
il se chiffre avant de se faire.

---

## 44. LE COUT DE L'INDEXATION PAR EMBEDDINGS — chiffre avant d'etre engage

§43.5 laissait ouvert : « il faudrait une indexation par embeddings sur
18 073 entrees, dont le cout n'est pas mesure ». Il l'est.

### 44.1 Trois mesures, et les deux premieres etaient MAL POSEES

| mesure | resultat | ce qu'elle valait |
| --- | --- | --- |
| appels **en serie** | 2,83 s/entree → **16 h** | **fausse** : le pont ne procede pas ainsi |
| lot de 12 | 0,17 s/entree, gain **×13,9** | juste, mais pas le regime reel |
| **lot de 32** — le regime du pont | **0,328 s/entree** | **111 minutes** pour 20 304 entrees |

**La premiere extrapolation portait sur un scenario inexistant.** J'ai mesure
des appels en serie et extrapole sans verifier ce que le pont fait : il groupe
par lots de 32 depuis toujours (`NEXUS_EMBED_BATCH`, defaut 32). *L'instrument
repondait a la question voisine* — troisieme fois du jour.

### 44.2 Le cout en DISQUE, que je n'avais pas regarde du tout

Un vecteur `bge-m3` porte **1024 dimensions**. En JSON, cela pese ~15 Ko par
entree :

> **~312 Mo** pour 20 304 entrees, **sans compter le texte** conserve a cote.

L'index vit dans `.nexus/`, ignore par git : **rien ne serait publie**.

### 44.3 Et une alarme que j'ai failli rapporter a tort

`loadIndex()` fait `JSON.parse(readFileSync(...))` : j'allais annoncer que
chaque recherche relit 312 Mo. **Il y a un cache**, indexe sur `mtime` et
`size`. L'analyse a lieu **une fois par processus**, pas par recherche.

Ce qui reste vrai : **~312 Mo residents en memoire** pour la vie du serveur.
Sur cette machine, l'iGPU n'a pas de VRAM dediee et partage les memes 61,6 Go
que les poids des modeles (§107.0) — la depense est modeste mais reelle.

### 44.4 VERDICT : abordable, et NON ENGAGE

| | |
| --- | --- |
| temps | **111 minutes**, sans surveillance |
| disque | ~312 Mo, ignore par git |
| memoire | ~312 Mo residents par processus serveur |
| reversible | oui — l'index se reconstruit |

**C'est abordable. Ce n'est pas pour autant lance.** Deux raisons :

* deux heures de machine s'engagent, elles ne se prennent pas d'autorite ;
* l'index est PARTAGE. Y verser 20 304 entrees de livres change ce que
  `nexus_search` rend **pour tous les projets** qui l'emploient — c'est un
  choix de perimetre, pas une optimisation.

Le geste, si vous le voulez :

```
python scripts/nexus_mcp_probe.py index_build references/livres/code bge-m3-local
```

Et le corpus de **code** est le meilleur candidat pour commencer : 2 231
entrees — **12 minutes** — dont 1 277 sur les agents, et ses identifiants sont
deja consultables sans embeddings.

---

## 45. DEUX SIGNALEMENTS VOISINS — dont un qui vaut ICI, mesure

### 45.1 CORRIGE — mon affirmation etait FAUSSE, et la vraie trouvaille est ailleurs

**Ce que j'ai ecrit ici et qui est faux** : « le pont calcule la troncature et
ne la dit pas ». J'avais vu un texte coupe en plein mot et conclu.

**Mesure a la source, qui me dementit :**

```
gpt-oss-120b-cloud     finish_reason='stop'   completion=326 jetons
glm-4.7-flash-local    finish_reason='stop'   completion=1544 jetons
```

Aucune troncature. `nexus_ask` appelle bien `mentionsReponse(result)` et
insere `${coupe}` dans sa banniere : **il n'a rien annonce parce qu'il n'y
avait rien a annoncer**. Le « coupe en plein mot » etait la troncature
d'affichage **de mon propre script de test**, a 200 signes.

*Deduire d'une apparence au lieu de mesurer a la source* — l'erreur que ce
role existe pour empecher, commise dans le tour meme ou je la nommais. Et
c'est la deuxieme fois du jour qu'un artefact de MA mesure passe pour un
defaut du code.

### 45.1.1 OUVERT — la vraie trouvaille : `max_tokens` est IGNORE

Les deux appels ci-dessus portaient **`max_tokens: 12`**. Ils ont rendu **326**
et **1544** jetons de completion.

Le plafond de sortie n'est donc pas applique — ni sur le plan cloud, ni sur le
plan local. Un appelant qui borne sa sortie **n'obtient aucune borne**.

Consequence, et elle porte loin : `nexus_summarize`, `nexus_context` et
`nexus_batch` bornent leur sortie par ce parametre. Si le moteur l'ignore, ces
budgets ne tiennent pas — et la MAP-REDUCE de §110, dont tout le principe est
de tenir dans des fenetres bornees, repose sur une borne qui n'existe pas.

**CAUSE ETABLIE, et elle est chez nous.** La configuration epingle
`num_predict: 4096` dans les `litellm_params` — sur **70 declarations** :

```yaml
  - model_name: glm-4.7-flash-local
    litellm_params:
      model: ollama_chat/glm-4.7-flash
      num_ctx: 32768
      num_predict: 4096        # <-- ce plafond-ci gagne
```

LiteLLM applique ses `litellm_params` **par-dessus** la requete. Le
`max_tokens` de l'appelant est donc ecrase par la configuration,
silencieusement. Ce n'est pas le moteur qui ignore la borne : c'est le depot
qui en impose une autre sans le dire.

**Le remede n'est pas trivial — et c'est pourquoi il n'est pas pris dans ce
tour.**

| voie | ce qu'elle coute |
| --- | --- |
| retirer `num_predict` des 70 declarations | le plafond disparait pour tout appelant qui n'en fournit pas — or il protege d'une generation qui s'emballe, sur une machine ou cela se paie en minutes |
| garder l'epinglage et prendre le minimum des deux | LiteLLM ne compose pas ainsi : ses parametres gagnent, il n'y a pas de `min()` a activer |
| porter `num_predict` a une valeur haute | deplace le plafond sans rendre la main a l'appelant |

C'est un changement **R3** au sens du contrat §47 : il touche le routage et
modifie le comportement de **chaque** appel. Il se teste avant de se deployer.

**Ce qui est acquis malgre tout** : la cause n'est plus une hypothese. Le
prochain geste n'est plus « mesurer », il est « arbitrer entre trois voies
connues » — et la mesure qui tranchera est celle du cout d'une generation non
bornee sur cette machine.

### 45.2 OUVERT — le worktree isole, confirme par un incident voisin

La meme instance : « j'ai edite `src/trading/risk_policy.py` dans l'arbre vif.
Filet de peche, pas l'arbre. »

C'est la regle §0.4 de ce contrat, deja inscrite ouverte en §34.5 — « chaque
worker dans un worktree git isole », qu'aucun controle ne garde. Leur incident
en est la confirmation vivante : *une regle qu'aucun controle ne garde se
transgresse, y compris par qui la connait.*

### 45.3 Et une lecon de routage, qui n'est pas un defaut

Leur modele etait `llama3.2:3b` sur une tache d'ASSEMBLAGE. Un modele de trois
milliards de parametres, avec un budget de sortie court, n'est pas le bon
candidat pour cela — c'est un choix de profil (§109), pas une panne. Le
diagnostic « le harnais est sain, c'est le budget qui est trop court » est
juste, et la conclusion utile est en amont : *choisir le modele selon la
tache, explicitement.*

---

## 46. LA BRIDE LEVEE — et trois diagnostics faux avant le bon

L'operateur : « leve la bride, les instances voisines sont en debit reduit et
l'on a acces a plus de 80 IA connectees, c'est un comble ». La bride etait
reelle et elle etait **de nous**.

### 46.1 Ou elle etait, et pourquoi son motif ne valait qu'a moitie

```python
largeur = max(1, min(args.parallele, 8, len(taches)))
```

Le commentaire justifiait le plafond de 8 par la RAM : « plusieurs gros
modeles charges en meme temps sur une machine qui n'a qu'une reserve de RAM ».

**Ce motif ne vaut que pour le plan LOCAL.** Un modele `-cloud` tourne chez
ollama.com et ne consomme aucune RAM ici. Le plafond avait ete etendu au plan
ou son motif n'existe pas — encore le motif *« une lecon appliquee d'un cote
et pas a son jumeau »*.

### 46.2 La rampe, qui autorise l'ouverture

Appels de seize jetons, paliers separes de cinq secondes :

| connexions | OK | bascules | refus | p95 |
| --- | --- | --- | --- | --- |
| 4 | 4 | 0 | 0 | 6,3 s |
| 8 | 8 | 0 | 0 | 6,4 s |
| 12 | 12 | 0 | 0 | 4,6 s |
| 16 | 16 | 0 | 0 | 2,3 s |
| **20** | **20** | **0** | **0** | **2,6 s** |

Vingt connexions simultanees, zero refus, et **la latence qui baisse**. Le
plafond de 8 ne tient pas cote cloud. Il demeure cote local, ou la contrainte
est physique et non politique.

### 46.3 TROIS DIAGNOSTICS FAUX AVANT LE BON — et c'est le sujet

Durant le meme tour, dix-neuf taches lancees sur dix-neuf alias cloud
distincts : sept ont bascule vers un autre modele. J'ai avance trois causes,
et **les deux premieres sont refutees par la mesure suivante** :

| j'ai dit | ce qui l'a refute |
| --- | --- |
| « aucun echec cloud » (sur le lot 1 seul) | le lot 2 : sept bascules |
| « la contrainte est le nombre de connexions » | la rampe : 20 simultanees, zero refus |
| « nos propres delais expirent » | `DELAI` vaut **900 s** ; la plus longue a mis 525 s |

### 46.3.1 J'ai accuse l'instrument, et c'etait encore moi

J'ai ecrit ici, une heure durant, que « l'instrument a detruit la preuve ».
**Faux.** Le champ `bascule` la portait depuis le debut :

```
glm-5.3-cloud -> gpt-oss-120b-cloud apres : glm-5.3-cloud : timed out
kimi-k2.7-code-cloud -> gpt-oss-120b-cloud apres : ... : timed out
gpt-oss-20b-cloud -> gpt-oss-120b-cloud apres : ... : timed out
```

**Huit bascules, huit `timed out`.** Mon lecteur interrogeait un champ `refus`
qui n'existe pas, et concluait « aucun detail consigne ». Quatrieme fois du
jour qu'un artefact de MA mesure passe pour un defaut du code.

Donc mon DEUXIEME diagnostic — « nos propres delais expirent » — etait le bon,
et je l'avais refute a tort en citant `DELAI = 900`, qui n'est pas le delai
qui a mordu. Celui-ci est `request_timeout: 180`, cote passerelle.

### 46.3.2 Le defaut REEL de l'instrument, lui, existe : `duree` sous-declare

Ce qui rendait la chronologie incomprehensible — `switch` bascule « en 14,4 s »
alors que le delai est de 180 s — tient a ceci, verifie a la ligne 390 :

```python
duree = time.time() - depart      # duree de CET appel-ci
```

Sur une bascule, le resultat rendu est celui du candidat qui a **reussi**, et
il ne porte que **sa** duree. Les 180 s brulees par le candidat qui a expire
ne sont additionnees nulle part.

> *Une duree qui n'additionne pas les tentatives ecartees ne mesure pas le
> cout : elle mesure la fin de l'histoire.*

C'est ce defaut-la qu'il faut corriger, et non celui que j'avais invente.
Les champs `demande_initiale` et `motif_bascule` sont ajoutes quand meme : la
raison etait lisible, mais dans une chaine a decouper plutot que dans un champ.

### 46.3.3 Ce qui explique alors les huit bascules

Coherent avec toutes les mesures du jour, et rien n'y contredit :

| fait | mesure |
| --- | --- |
| 20 connexions LEGERES simultanees | 0 refus, p95 2,6 s |
| 9 alias dits morts, appeles seuls | 9 vivants, 2,8 a 6,0 s |
| 8 taches LOURDES sous ~16 simultanees | 8 `timed out` a 180 s |

Ce n'est donc ni le quota, ni le nombre de connexions, ni la nature des
alias : c'est la **duree de generation sous charge**, contre un
`request_timeout` de 180 s. Un appel de seize jetons ne l'atteint jamais ;
un appel qui lit un fichier de 30 Ko et redige un correctif l'atteint.

Ce qui suit de la, pour ouvrir vraiment les vannes : la largeur ne doit pas
se choisir par plan seul, mais par POIDS de la tache. Vingt taches legeres
passent ; huit taches lourdes ne passent pas.

### 46.4 Ce que la mesure a aussi rendu

Neuf alias cloud dits « morts » dans le lot, appeles **seuls** :

```
deepseek-v4-flash-0731-cloud   VIVANT  2.8s
nemotron-3-super-cloud         VIVANT  5.3s
glm-5.3-flash-cloud            VIVANT  3.8s
minimax-m2.7-cloud             VIVANT  3.4s
kimi-k2.6-cloud                VIVANT  6.0s
glm-5.1-cloud                  VIVANT  6.0s
gpt-oss-20b-cloud              VIVANT  3.1s
nemotron-3-nano-30b-cloud      VIVANT  3.2s
minimax-m3-cloud               VIVANT  3.4s
```

**9 sur 9.** Aucun n'est mort. Les dix-neuf alias cloud existent bel et bien.

---

## 47. `max_tokens` EST INERTE — et l'envoyer DETRUIT la borne qui marchait

§45.1.1 laissait ouvert : « le plafond de sortie n'est pas applique ». La
cause est etablie, et elle n'est pas celle que j'avais ecrite.

**Ce n'est pas une preseance, c'est un ECART DE NOM.** Mesure sur
`gpt-oss-120b-cloud`, meme question, meme temperature :

| corps envoye | jetons rendus | `finish_reason` |
| --- | --- | --- |
| `max_tokens: 12` | **523** | `stop` — ignore |
| `num_predict: 12` | **12** | `length` — **honore exactement** |
| **les deux a 12** | **523** | `stop` — max_tokens gagne, et il est inerte |

La troisieme ligne est la plus dure : **envoyer `max_tokens` a cote de
`num_predict` annule la borne qui fonctionnait.**

Le generateur epingle `num_predict: 4096` (local) et `8192` (cloud) dans les
`litellm_params`. Il porte, sur la *temperature*, un commentaire explicite :
« declaree et non imposee : un parametre envoye dans la requete l'emporte ».
Ce raisonnement n'a jamais ete reproduit pour `num_predict` — et il ne pouvait
pas l'etre, puisque l'appelant n'envoie pas ce nom-la.

**Consequence sur l'outil que j'emploie a chaque delegation** : le drapeau
`--max-tokens` de `nexus_agent.py` est **inerte** sur tout modele Ollama,
local comme cloud, depuis toujours. Une tache demandee a 2 400 jetons en a
rendu 10 126. Et `nexus_summarize`, `nexus_context`, `nexus_batch` ainsi que
la MAP-REDUCE de §110 bornent leur sortie par ce meme parametre.

Le remede ne coute rien et il est en cours : envoyer `num_predict` pour les
modeles servis par Ollama, `max_tokens` pour les autres.

---

## 48. LES 138 REPLIS LOCAUX — mesure voisine, confirmee, et mon compteur etait aveugle

L'instance voisine annonce sur NOTRE configuration : 2 chaines
`cloud -> cloud` la ou son brief en portait 37, et **138 chaines
`local -> local` visant toutes un poids DIFFERENT**, donc payant chacune une
eviction-rechargement.

**Ma premiere remesure a rendu 72 et j'ai failli les contredire.** Mon
compteur ne lisait que `router_settings.fallbacks` : la cle
`context_window_fallbacks`, au premier niveau du document, lui echappait —
**68 paires**. En l'incluant :

```
local -> local total      : 138
  vers poids DIFFERENT    : 138
  vers le MEME poids      :   0
```

**Leur mesure est confirmee au chiffre pres.** Soupconner son propre
instrument avant l'annonce d'autrui n'est pas une politesse : c'est ce qui a
evite de leur renvoyer un dementi faux.

Reste OUVERT : ces 138 replis descendent une echelle de tailles, et chaque
saut paie un chargement. Rien ne prefere aujourd'hui un modele deja resident.
Les pieces existent — `/api/ps` se lit — mais rien ne les emploie.

---

## 49. « ON NE VEUT AUCUNE BRIDE » — ce qui bridait vraiment, mesure par mesure

L'operateur, avec deux instances voisines deja lancees sur du lourd et du
massif : *« consulte un ou deux gros modeles cloud, on ne veut aucune
bride »*. Fait — et la consultation a trouve ce que je n'avais pas vu.

### 49.1 La bride qui comptait etait CACHEE, et elle mentait sur elle-meme

`qwen3.5-397b-cloud` et `kimi-k3-cloud` ont ete consultes sur la
configuration et sur `nexus_agent.py`. Le second a nomme une constante que je
n'avais pas ouverte :

```python
# Fils simultanes par plan. Ces deux nombres sont MESURES : au-dela de trois
# appels concurrents le cloud n'accelere plus [...]
PLAFOND_FILS = {"cloud": 3, "local": 2}
```

Elle gouverne le MAP-REDUCE — **tout le travail lourd distribue** — et son
commentaire invoque une mesure. **Ma rampe du jour la dement** : de 4 a 20
connexions, zero refus, zero 429, p95 de 6,3 s a 2,6 s. *Une mesure gelee ment
le lendemain*, et celle-ci mentait en s'annoncant comme mesure.

### 49.2 ET POURTANT LA LEVER N'A RIEN DONNE — essai alterne

La tentation etait de porter le chiffre a 16 et d'annoncer un gain. Essai
alterne, trois tours par valeur, meme corpus de 670 Ko, huit fenetres :

| fils cloud | mediane | min | max |
| --- | --- | --- | --- |
| 3 | **36 s** | 34 s | 39 s |
| 16 | **36 s** | 34 s | 37 s |

**Ecart des medianes : 0 s. Etendue du bruit : 5 s. INDISCERNABLE.**

Deux essais isoles avaient d'abord donne 30 contre 25 s, puis 33 contre 38 s
— deux directions opposees. Sans l'essai alterne j'aurais publie le premier.

La valeur passe quand meme a 16, **et pas pour un gain** : pour que le chiffre
cesse d'affirmer une mesure que rien ne soutient, et parce qu'il devient
reglable par `NEXUS_FILS_CLOUD` sans toucher au code. Le goulot du MAP est
ailleurs, et **il reste a trouver**.

### 49.3 Ce que la consultation a rendu, verifie cle par cle

Toutes les cles citees par `qwen3.5-397b` existent — `drop_params`,
`routing_strategy`, `health_check_interval: 900`, `RateLimitErrorRetries: 0`,
`num_retries`, `allowed_fails`, `cooldown_time`. **Aucune invention.** Et il a
ecrit « JE NE SAIS PAS » sur `max_concurrent_requests`, qui est en effet
ABSENTE de la configuration — une piste, pas une erreur.

Sa trouvaille la plus utile, verifiee : **30 modeles locaux a `num_ctx: 8192`**
pour des fichiers de 15 a 40 Ko. Verifie sur les quatre modeles qui avaient
echoue : ils portent 131 072, donc **ce n'etait pas la cause chez eux** — mais
la remarque tient pour le plan local.

### 49.4 Les quatre echecs cloud ne sont PAS une bride

`gpt-oss-20b-cloud` sur la meme tache lourde, **appele seul**, budget
identique : bascule quand meme. Ce n'est donc ni la concurrence, ni le delai,
ni le contexte. **C'est le modele.** Quatre alias sur dix-neuf ne tiennent pas
une tache d'audit lourde — question de pool (§76 : declare n'est pas eligible),
pas de plafond a lever.

### 49.5 L'etat des brides, apres ce tour

| bride | verdict |
| --- | --- |
| `request_timeout: 180` | **levee** a 900 s — c'etait un reglage a nous |
| `PLAFOND_FILS["cloud"] = 3` | **levee** a 16, reglable — sans gain mesure |
| `max_tokens` inerte | **corrige** : `num_predict` est honore |
| defaut `--max-tokens 1500` | **relve** a 4096, sinon regression |
| `PLAFOND_FILS["local"] = 2` | **TENUE** — contrainte physique, pas prudence |
| `num_ctx: 8192` sur 30 modeles locaux | **OUVERT**, non mesure |
| `max_concurrent_requests` | **ABSENTE** de la config — piste ouverte |

### 49.6 Et une batterie complete, en reel

383 reussis, 3 echecs, 1 ignore. Un des trois etait **de moi** : un second
cas de test encodait encore la croyance fausse sur le heredoc quote. Corrige,
avec son jumeau non quote ajoute. Restent deux echecs anterieurs :
`phi3-mini-local` injoignable, et le generateur idempotent en echec.

---

## 50. LE PLAN LOCAL N'EST PAS BRIDE PAR LA PHYSIQUE — j'avais herite, pas mesure

L'operateur : *« pourquoi cote local ne rien ouvrir alors que l'on pourrait le
faire ? »* Question juste, et elle m'a pris en defaut.

### 50.1 L'erreur, et c'est exactement celle que je venais de denoncer

J'ai refute, une heure plus tot, un commentaire qui s'annoncait « MESURE »
cote cloud. **Et j'ai accepte son jumeau local sans le verifier** :

```python
# ...et le plan local plafonne des le deuxieme.
PLAFOND_FILS = {..., "local": 2}
```

*Une lecon appliquee d'un cote et pas a son jumeau* — septieme occurrence
enregistree dans ce depot.

### 50.2 Ce que la machine dit, et qui dement la doctrine

```
OLLAMA_NUM_PARALLEL        2       <- un REGLAGE, pas une loi physique
OLLAMA_MAX_LOADED_MODELS   3
OLLAMA_KEEP_ALIVE          15m
memoire hote : 66,2 Go totale, 23,5 Go LIBRE
```

Trois faits en decoulent :

* **`PLAFOND_FILS["local"] = 2` ne mesure rien** : il RECOPIE
  `OLLAMA_NUM_PARALLEL = 2`. Le lever cote script seul ne servirait a rien,
  la file se formerait au moteur. Le vrai levier est la variable du moteur.
* **La doctrine de ce contrat est perimee sur DEUX variables.** §107.0 affirme
  `OLLAMA_KEEP_ALIVE` non defini, §107.1 affirme `OLLAMA_MAX_LOADED_MODELS`
  non defini. **Les deux sont definis.**
* Il y avait **23,5 Go libres**. La saturation invoquee n'existait pas.

### 50.3 La distinction que le plafond de 2 ECRASE

| cas | cout reel |
| --- | --- |
| N appels vers des modeles **DIFFERENTS** | eviction-rechargement, 20 Go qui se poussent |
| N appels vers le **MEME** modele resident | **aucun rechargement** |

Et un MAP-REDUCE est exactement le second cas. Le plafond de 2 traite les
deux de la meme facon.

### 50.4 Reste OUVERT, et pourquoi la mesure n'a pas ete faite

De combien monter n'est **pas** mesure. Le moteur local etait occupe par
`deepseek-coder:33b`, 21 Go, pendant toute la fenetre disponible ; deux
reveils ont expire a 300 s puis 422 s. Mesurer alors aurait rendu un chiffre
confondu — l'erreur evitee tout au long de ce tour.

**L'idee de l'operateur, a instruire** : autoriser plusieurs residents pour
que **plusieurs petits modeles forment un essaim**, en ne reservant la
prudence qu'aux gros par leur taille. La memoire libre la soutient ; il
manque la mesure.

Une instance voisine apporte un point de methode : `api/ps` liste les modeles
**CHARGES**, pas les requetes **ACTIVES**. Un modele resident ne travaille pas
forcement — attribuer une occupation a une charge qui n'existe plus fausserait
la mesure.

---

## 51. LE PONT MCP COUPAIT AVANT LA PASSERELLE

Rapporte par une instance voisine — deux `nexus_ask` echoues a 600 s sur une
classe de tache que la ligne de commande servait — puis verifie ici.

| etage | plafond |
| --- | --- |
| `nexus_agent.py` | `DELAI` 900 s |
| passerelle LiteLLM | `request_timeout` 900 s (releve ce jour) |
| **pont MCP** | `DEFAULT_TIMEOUT_MS` **600 s** |

Le pont coupait donc le premier, et rendait une erreur de delai **pour un
appel que la passerelle aurait servi**. Aligne a 900 s.

**Epreuve** : appel reel via le pont apres correction, 356 jetons rendus, plan
cloud annonce.

### 51.1 Reste OUVERT — la reprise sur troncature

Le voisin mesure, sur 78 taches : **onze bascules pour onze troncatures,
exactement un pour un**. La troncature est la cause UNIQUE des bascules. Et
son mode d'echec est traitre : un budget trop court ne rend pas plus court,
il rend **inexploitable**, coupe en plein JSON. A 2000 jetons, 3 sur 12
tronques ; a 4000, **0 sur 144**.

Le remede — rejouer UNE fois a budget double — est **delegue mais NON
APPLIQUE** : les deux rendus du banc proposaient de renommer la fonction
`chat`, trop invasif pour un pont ACTIF chez deux instances a cet instant.
Inscrit ouvert plutot qu'applique a la hate.

---

## 52. RECOLTE DES SUJETS OUVERTS — et trois qui etaient deja fermes

Demande de l'operateur : *« recolte tous les sujets ouverts a traiter »*.
Delegue au banc, qui a lu les **264 Ko** de ce document en quatre fenetres et
**115 790 jetons**, puis rendu le tableau ci-dessous, classe par degat.

### 52.1 L'ARBITRAGE D'ABORD — la source ment, pas le banc

Le banc a ete FIDELE. Ce sont trois entrees du cockpit qui etaient perimees,
et que les mesures de ce jour ferment :

| entree recoltee | ce que la mesure du 2026-08-31 dit |
| --- | --- |
| #19 « `OLLAMA_KEEP_ALIVE` non defini » | il vaut **15m**, releve directement |
| #6 « les modeles cloud echouent en serie (429) » | **zero 429** sur 144 taches, et zero sur ma propre rampe a 20 |
| #32 « la config porte toujours les 37 chaines » | **2** chaines `cloud -> cloud`, remesure et confirme avec l'instance voisine |

> **Le cockpit accumule et ne retire jamais.** Un sujet ferme qui reste
> inscrit ouvert coute deux fois : il occupe l'attention, et il decredibilise
> les sujets qui, eux, sont reels.

C'est un defaut de ce document, pas des mesures. Il n'a aucun mecanisme de
retrait, et cette recolte est la premiere chose qui le revele.

### 52.2 ET UN DEFAUT TROUVE EN PRODUISANT CETTE RECOLTE

Le tableau ci-dessous s'arrete en plein mot, a l'entree 34 — et le champ
`tronque` du resultat vaut **`None`**, pas `True`.

**Le chemin MAP-REDUCE perd le drapeau de troncature.** L'appel simple le
porte, la fusion en plusieurs paliers ne le remonte pas. Un appelant qui
demande un corpus de 264 Ko recoit donc un rendu coupe **sans le savoir**.

C'est exactement l'entree #10 de la recolte — *« `nexus_compare` perd le
drapeau `tronquee` que `chat()` calcule »* — observee ici sur un autre
chemin, en produisant la liste qui la mentionne. La famille est plus large
que l'entree ne le disait.

### 52.3 La recolte, telle que rendue

Les entrees 6, 19 et 32 sont **fermees** par 52.1 ; les autres restent
ouvertes. Un sujet ne se clot que lorsqu'un CONTROLE echoue si la regle est
enfreinte — jamais par un paragraphe.

| # | Sujet ouvert | Section | Ce qui le fermerait concrètement |
|---|---|---|---|
| 1 | Tâches de fond tuées (trois fois de suite, cause non identifiée) | Défauts constatés, non corrigés | Contrôle qui échoue si la récidive de tuerie de tâche survient |
| 2 | `nexus_index_build` expire (600 s) — embedding 8 Go au lieu de 46 Mo | Défauts constatés, non corrigés | Contrôle validant le temps d'exécution inférieur au timeout |
| 3 | `nexus_search` expire (600 s) — même cause probable | Défauts constatés, non corrigés | Contrôle validant le temps d'exécution inférieur au timeout |
| 4 | `releve-locale` expire dans le MCP (HTTP 408 après 180 s) | Défauts constatés, non corrigés | Contrôle validant la complétion de la requête avant timeout |
| 5 | Un amont qui **pend** attend 3 × 180 s avant tout repli | La sélection naturelle tournait sur une jambe | Contrôle vérifiant le délai de repli réduit et fonctionnel |
| 6 | Les modèles **cloud échouent en série** (429 Too Many Requests) | Sujets ouverts consolidés | Contrôle vérifiant la borne de concurrence cloud respectée |
| 7 | 9 appels Anthropic sur 9 échouent — le repli masque la cause | Sujets ouverts consolidés / Vérifications jamais faites | Contrôle avec repli désactivé validant la lecture de la cause réelle |
| 8 | Suite complète après tous les changements — trois lancements interrompus | Vérifications jamais faites | Contrôle d'exécution de la suite complète sans interruption |
| 9 | Une réponse vidée par le retrait du raisonnement est rendue **sans le dire** | Charge massive sur le pont MCP | Contrôle échouant si le signalement explicite disparaît dans les appelants |
| 10 | `nexus_compare` perd le drapeau `tronquee` que `chat()` calcule | Charge massive sur le pont MCP | Contrôle échouant si le drapeau `tronquee` est absent en sortie |
| 11 | Biais systématique du validateur (pas protégé du biais de format) | Défauts constatés, non corrigés | Contrôle vérifiant la protection contre le biais de format |
| 12 | La moitié du pool d'orchestration est **confirmée incapable d'orchestrer** (deepseek-coder-33b, phi3-mini) | La moitié du pool d'orchestration ne sait pas orchestrer | Contrôle mécanisé vérifiant l'exclusion effective des modèles incapables |
| 13 | Les épreuves promeuvent mais ne rétrogradent jamais | La moitié du pool d'orchestration ne sait pas orchestrer | Contrôle vérifiant l'application de la politique de rétrogradation |
| 14 | La politique de promotion elle-même — décision réservée à l'opérateur | Un 4/4 obtenu une fois n'est pas un 4/4 confirmé | Contrôle vérifiant l'application de la décision de l'opérateur |
| 15 | `nexus_essaim` : 3 échecs sur 6, palier jamais revérifié | Défauts constatés, non corrigés | Contrôle de revérification du palier de réussite |
| 16 | Le profil `reasoning` a répondu entièrement hors sujet — aucune épreuve de compréhension | Charge massive sur le pont MCP | Contrôle d'épreuve de compréhension par profil exécuté |
| 17 | `nexus_search` rend 8 extraits à score 0,205 sur une requête absurde | Charge massive sur le pont MCP | Contrôle vérifiant le seuil de score ou la mention explicite |
| 18 | Chaque worker dans un **worktree isolé** — c'est un répertoire, pas un worktree git | Règles du 30/08 encore OUVERTES / Sujets ouverts consolidés | Contrôle échouant si la règle de worktree git véritable est enfreinte |
| 19 | Réglages du moteur Ollama (`OLLAMA_KEEP_ALIVE` non défini) | Bloqué sur une décision qui ne m'appartient pas | Contrôle vérifiant la définition effective de la variable d'environnement |
| 20 | Taille du pool local — couplé au réglage ci-dessus, borné à 4 modèles | Bloqué sur une décision qui ne m'appartient pas | Contrôle vérifiant la taille du pool suite à la décision hôte |
| 21 | Préserver le contexte de l'orchestrateur — mesurable mais non mesuré par tour | Règles du 30/08 encore OUVERTES / Sujets ouverts consolidés | Contrôle de rituel comparant jetons facturés et délégués |
| 22 | Le pont MCP est **beaucoup plus lent** que LiteLLM en direct — mesuré, non expliqué | Le plafond mesuré | Contrôle d'instrumentation validant l'explication du surcoût |
| 23 | Débit mesuré sur 7 modèles sur 71 — le banc n'a jamais tourné en entier | Sujets ouverts consolidés | Contrôle d'exécution de `nexus_bench.py --debit` machine au repos |
| 24 | Coût binaire mesuré sur aucun modèle — jamais lancé | Sujets ouverts consolidés | Contrôle d'exécution de `nexus_bench.py --cout` |
| 25 | `epreuves.json` ne juge qu'un modèle sur 71 (maintenant 25/44, mais `stable` exige 2 mesures) | La sélection naturelle tournait sur une jambe / Un 4/4 obtenu une fois n'est pas un 4/4 confirmé | Contrôle validant deux mesures par modèle pour confirmer `stable` |
| 26 | Le détail des sept modèles déjà partiels — perdu, reviendra à la prochaine mesure | Combien ont échoué ne dit pas laquelle | Contrôle de conservation du détail lors de la prochaine mesure |
| 27 | Qualité de résumé — grandeur manquante pour trancher `DEFAULT_CHAT_MODEL` | Mesures incomplètes | Contrôle de mesure de similarité sémantique résumé↔source |
| 28 | Niveau de qualité — 21 modèles sur 36 restent à `tier 0` (jamais déclaré, jamais déduit) | Capacités déclarées, non exploitées | Contrôle de déclaration ou déduction du niveau pour tous les modèles |
| 29 | `qwen3-vl-32b` hors classement — écarté par verdict matériel ? Non vérifié | Défauts constatés, non corrigés | Contrôle de vérification du verdict matériel d'exclusion |
| 30 | `This model isn't mapped yet` sur les alias `ollama_chat/*` — effet réel à établir | Le plan cloud est tombé sous mes propres vagues | Contrôle établissant l'effet réel du mapping d'alias |
| 31 | `num_retries: 2` sur un 429 — politique à vérifier dans la doc LiteLLM | L'amplification des replis | Contrôle de vérification dans la documentation LiteLLM |
| 32 | `litellm_config.yaml` porte toujours les 37 chaînes — régénération à la main | L'amplification des replis | Contrôle vérifiant la régénération et le redémarrage effectués |
| 33 | `thinking` — déclarée par le moteur, lue nulle part | Capacités déclarées, non exploitées | Contrôle de lecture et exploitation effective de la capacité |
| 34 | `command-r`, `sqlcoder`, `codegemma:7b` — installés, déclarés, **jamais mesurés** | Modèles téléchargés, non intégrés | Contrôle de mesure effectuée et intégr

---

## 53. A2A — l'apport reel, et le premier pas que l'analyse propose a tort

Demande de l'operateur : *« passer au A2A »*. La matiere etait deja sur le
disque, et il fallait s'en servir plutot que d'en chercher d'autre :

```
references/livres/code/index.tsv   563 entrees du livre MCP + A2A
                                   8 symboles du PROTOCOLE lui-meme
```

Lues par `nexus_doc.py`, en seek sur l'index — pas en ouvrant les fichiers.
Le corpus reste gitignore : c'est un livre commercial, il ne sort pas.

### 53.1 La difference structurelle, telle que les deux sources la montrent

| | qui appelle qui | ce qui transporte |
| --- | --- | --- |
| **MCP** | orchestrateur -> outils, hierarchique et synchrone | arguments d'appel, resultats de fonction |
| **A2A** | agent <-> agent, pair a pair et asynchrone | messages de protocole, **etat de tache persistant** |

### 53.2 MON ARBITRAGE : le premier pas propose est LOCAL a la session

L'analyse propose, comme plus petit pas verifiable : ajouter un `task_id` a
`nexus_batch`, une `Map tachesActives` dans `server.js`, et un outil
`nexus_task_status` qui la lit.

**Cela ne marcherait pas ici.** Notre pont MCP est lance **par session** :
une Map dans son processus est locale a cette session. `nexus_task_status`
ne renseignerait donc que sur des taches que l'orchestrateur connait deja,
et resterait muet sur celles des autres — c'est-a-dire precisement le cas ou
A2A servirait.

L'analyse n'avait pas cette information : elle lisait `server.js`, qui ne dit
pas comment il est lance. *L'analyse est le signal, jamais la preuve.*

### 53.3 LE MANQUE REEL, prouve par un incident de ce jour

Le manque n'est pas le suivi de tache dans une session. C'est **l'identite et
le statut d'une affirmation entre sessions**.

Mesure vecue aujourd'hui : j'ai transmis a une instance voisine une
affirmation — « cote local, ne rien ouvrir, la borne est physique » — qu'elle
a **relayee**. Elle etait FAUSSE. J'ai du envoyer une correction, qui
**s'ajoute** au fil au lieu de **remplacer** l'affirmation d'origine. Rien,
dans ces messages, ne porte :

* une identite d'affirmation, pour qu'une correction designe ce qu'elle
  corrige ;
* un statut — avancee, confirmee, retiree — pour qu'un lecteur tardif sache
  laquelle des deux fait foi ;
* la mesure qui la fonde, pour qu'elle soit rejouable.

C'est exactement le role que joue `A2ATaskInfo` pour une tache, transpose a
une AFFIRMATION. Et c'est ce que le fil libre ne peut pas offrir.

### 53.4 Le risque, et il decide du perimetre

L'analyse le nomme justement : A2A etablit un **canal persistant** entre
agents. Aujourd'hui, chaque appel du pont est une decision explicite de
l'orchestrateur. Un canal automatise ferait transiter des donnees d'un plan
a l'autre **sans decision par message** — ce que §64 et §108 interdisent.

Donc : emprunter la FORME — identite, statut, mesure jointe — et **non** le
canal. C'est la regle du depot appliquee telle quelle : on emprunte une idee,
on ne se subordonne pas a une implementation.

### 53.5 Les pieges du code, releves avant tout emprunt

Delegue en parallele, et chaque trouvaille est nommee sur un symbole reel :

* `A2AManager` — **singleton** centralisant toute l'infrastructure : etat
  global, mecanisme non isolable ni testable.
* `SimpleCredentialService` — un seul identifiant par schema, **sans
  rotation ni isolation** : service de demonstration, dangereux en production.
* `A2AMessagePump` — si son demarrage ou son nettoyage echoue, **le contexte
  synchrone ne voit rien** : l'echec passe inapercu.
* `A2AExecutor` — pont synchrone vers asynchrone qui **suppose que le pair
  repond**, et fait pendre l'appelant sinon.

Les quatre sont a proscrire tels quels. Le troisieme et le quatrieme sont des
`fail-open` et un `pendage silencieux` — deux familles que ce depot a deja
payees.

### 53.6 L'analyse complete, telle que rendue

#### a2a_risque — ollama_chat/kimi-k3
- **A2AManager** (classe A2AManager) — piège (A) : singleton déclaré qui centralise l'initialisation et le nettoyage de toute l'infrastructure A2A, donc état global partagé rendant le mécanisme non isolable et intestable.
- **SimpleCredentialService** (classe SimpleCredentialService) — piège (B) : ne stocke qu'un seul credential par scheme, service de démonstration sans rotation ni isolation des secrets, dangereux à porter en production.
- **A2AMessagePump** (classe A2AMessagePump) — piège (C) : pompe qui fait tourner la communication async pour un contexte sync, donc si son démarrage, son arrêt ou son nettoyage échoue, le contexte synchrone ne voit rien et l'échec passe inaperçu.
- **A2AExecutor** (classe A2AExecutor) — piège (D) : pont sync-vers-async qui bloque l'appelant synchrone sur des opérations réseau asynchrones, donc suppose implicitement que le pair répond et le fait pendre sinon.

#### a2a_apport — ollama_chat/qwen3.5:397b
(A) **Différence STRUCTURELLE entre le modèle MCP et le modèle A2A :**

*   **MCP (`server.js`) :** Architecture **Orchestrateur → Outils**. Un agent central (orchestrateur) invoque des fonctions exposées (`nexus_ask`, `nexus_route`, etc.) via un protocole JSON-RPC (stdin/stdout). Ce qui est transporté : des **arguments d'appel** et des **résultats de fonction** (texte ou erreur). La relation est hiérarchique et synchrone (requête/réponse).
*   **A2A (`scratch_a2a.md`) :** Architecture **Agent ↔ Agent** (ou Client/Serveur pair). Des composants comme `A2AClient` et `A2AMessagePump` gèrent des échanges de **messages structurés** liés à un état persistant (`A2ATaskInfo`). Ce qui est transporté : des **messages de protocole** et des **métadonnées de tâche**. La relation est distribuée et asynchrone (cycle de vie de tâche).

---

(B) **Mécanismes que A2A apporte et que le pont MCP joint N'A PAS :**

| Nom exact (scratch_a2a.md) | À quoi il sert |
|---|---|
| `A2ATaskInfo` | Maintient l'état et le cycle de vie d'une tâche active (suivi de progression/statut). |
| `SimpleCredentialService` | Stocke et gère les identifiants/négociations d'identité par schéma (carte d'agent). |
| `A2AMessagePump` | Gère la file de messages asynchrone structurée entre agents (protocole formel). |
| `A2AManager` | Orchestre le cycle de vie des clients et de l'infrastructure A2A (gestion centrale). |
| `A2AExecutor` | Gère l'exécution des opérations et le pont entre contexte synchrone et asynchrone. |

---

(C) **Parmi ces mécanismes, lesquels résoudraient un problème RÉEL de cette plateforme telle qu'elle est ?**

| Mécanisme | Justification par ce que je vois dans `server.js` |
|---|---|
| `A2ATaskInfo` | **RÉSOUT UN PROBLÈME.** `server.js` expose des outils comme `nexus_batch`, mais la plateforme est décrite comme ayant « pas de cycle de vie de tache ». Ce mécanisme permettrait de suivre l'état d'un batch au-delà de la réponse JSON-RPC immédiate. |
| `SimpleCredentialService` | **RÉSOUT UN PROBLÈME.** `server.js` agit comme pont pour un orchestrateur mais la plateforme a « pas d'identite negociee » ni « carte d'agent ». Ce mécanisme permettrait d'identifier l'agent émetteur avant de traiter une demande. |
| `A2AMessagePump` | **RÉSOUT UN PROBLÈME.** `server.js` gère des appels d'outils, mais les sessions d'agents s'échangent des messages « en texte libre... sans protocole formel ». Ce mécanisme structurerait ces échanges machine-to-machine. |
| `A2AManager` | **N'APPORTE RIEN ICI.** `server.js` est un service unique (« pont MCP ») qui gère déjà son propre cycle de vie via le processus Node.js ; un manager d'infrastructure externe est redondant. |
| `A2AExecutor` | **N'APPORTE RIEN ICI.** `server.js` est nativement asynchrone (Node.js) et exécute les outils directement ; un pont d'exécution sync/async n'est pas nécessaire. |

---

(D) **Quel serait le PREMIER pas d'implementation, le plus petit qui apporte quelque chose de verifiable ?**

1.  **Étape 1 :** Dans `server.js`, modifier le `inputSchema` de l'outil `nexus_batch` pour ajouter un champ optionnel `task_id` (string).
2.  **Étape 2 :** Dans `server.js`, créer une Map globale `tachesActives` et y enregistrer le statut `EN_COURS` lors de la réception d'une requête `nexus_batch` contenant un `task_id`.
3.  **Étape 3 :** Dans `server.js`, ajouter un nouvel outil `nexus_task_status` qui lit la Map `tachesActives` et retourne le statut associé au `task_id` fourni.

**Fichier à toucher :** `server.js`

---

(E) **Quel est le principal RISQUE d'adopter A2A ici ?**

Le risque majeur est la violation de la règle stricte : **« aucune donnee ne doit franchir une frontiere de fournisseur sans decision explicite »**.

Dans `server.js`, chaque appel d'outil (`nexus_ask`, etc.) est une décision explicite de l'orchestrateur. A2A, via `A2AMessagePump` et `A2AClient`, risque d'établir un **canal de communication persistant** entre agents. Si ce canal est automatisé, des données pourraient transiter d'un fournisseur à un autre (ex: local vers cloud) via les messages A2A sans que l'orchestrateur ne prenne une décision explicite **pour chaque message**, contournant ainsi les garde-fous actuels du pont MCP.

---

## 54. LE MASSIF — 44 audits, 5 trouvailles, UNE qui tient

Lot bati depuis le depot lui-meme : un script par tache, **six familles de
defaut que CE depot a payees**, neuf modeles cloud distincts, trois fronts,
**24 appels simultanes**. 44 sur 44 abouties.

### 54.1 Le rendement brut, et ce qu'il dit

| | |
| --- | --- |
| taches abouties | **44 / 44** |
| rendus **non vides** | **5** |
| rendus vides | 11 |
| « AUCUN DEFAUT SUR » | 28 |
| bascules | 13 — dont **10 par troncature**, 3 par delai |

Cinq trouvailles sur quarante-quatre audits etroits. Les six familles que ce
depot a payees sont donc, pour l'essentiel, **deja purgees de ses propres
scripts** — ce qui est le resultat souhaite, et qu'il fallait mesurer plutot
que supposer.

### 54.2 L'ARBITRAGE : une sur quatre tient

La cinquieme etait une non-reponse — le modele reclamait le fichier qu'on lui
avait deja donne.

| trouvaille | verdict, verifie dans le code reel |
| --- | --- |
| `nexus_garde_shell` — « le refus sort en 0, donc ne bloque rien » | **REJETEE** |
| `nexus_relais` — « `total_jetons` calcule et jamais employe » | **REJETEE** — employe ligne 333 |
| `nexus_generate:215` — « code de sortie de `ollama show` ignore » | **REJETEE** — la ligne 215 est une docstring, l'emplacement est invente |
| `nexus_maj_modeles` — mesure sans date, constantes gelees | **CONFIRMEE** |

**La premiere merite d'etre expliquee, car elle instruit.** Le code est :

```python
def refuser(motif):
    sys.stdout.write(json.dumps({... "permissionDecision": "deny" ...}))
    sys.exit(0)
```

Un hook `PreToolUse` communique son refus **par ce JSON**, jamais par son
code de sortie. Sortir en 0 EST le mecanisme de blocage — et ce garde a
bloque son auteur trois fois dans la journee.

> *Une regle vraie sur un mecanisme est fausse sur son voisin.* La doctrine
> « un refus qui sort en 0 ne bloque rien » a ete payee sur un AUTRE
> mecanisme ; elle ne se transporte pas ici. C'est la meme erreur de
> generalisation que §112.3 corrige sur les modeles, commise cette fois par
> le banc, et arretee par la verification.

### 54.3 La seule confirmee, et elle vise la famille du jour

`scripts/nexus_maj_modeles.py` portait :

```python
MARGE_DISQUE_GO = 50
DELAI_PULL_S = 1800
```

et, plus loin, un commentaire affirmant *« Mesure apres correction : un
modele a jour est classe en 0,7 seconde »* — **sans dire quand**.

Corrige : les deux valeurs se lisent desormais depuis l'environnement
(`NEXUS_MARGE_DISQUE_GO`, `NEXUS_DELAI_PULL_S`), avec le motif ecrit a cote —
une marge de disque est une POLITIQUE qui depend de la machine, et un delai
de telechargement depend du debit reseau, qui n'est pas une propriete du
depot.

### 54.4 LES ONZE VIDES : le script diagnostiquait, et se taisait ensuite

Lu un enregistrement EN ENTIER plutot qu'agrege — apres deux lectures fausses
de suite :

```
erreur              plafond insuffisant : demande 4000 jetons, augmenter le plafond
plafond_insuffisant True
modele              glm-4.7-flash-local      <- dernier candidat essaye
lot demandait       nemotron-3-ultra-cloud   <- le vrai demande, PERDU
```

Deux defauts, tous deux des JUMEAUX oublies :

* le champ `demande_initiale` n'etait pose que sur le chemin de BASCULE,
  jamais sur celui de l'EPUISEMENT — d'ou un chiffre lu a l'envers deux fois ;
  desormais pose systematiquement ;
* le pont MCP a recu ce jour une reprise unique a budget double sur ce cas
  precis ; **le script ne l'avait pas eue**. Ajoutee, avec ses trois bornes :
  une seule reprise, plafond a 16384, et seulement si le nouveau budget est
  STRICTEMENT superieur.

**Et le premier jet de cette reprise etait un faux vert parfait** : le banc
avait declare `PLAFOND_REPRISE = 16384` et ne s'en servait NULLE PART. Une
constante sans sa mecanique — *produit, non consomme*. Attrapee par
l'arbitrage, pas par le compilateur.

---

## 55. UNE FONCTION MORTE, ET DEUX INSTRUMENTS CASSES DE MA MAIN

Point de depart : une tache de fond **tuee pour la quatrieme fois du jour** —
l'entree #1 de la recolte, celle classee la plus grave. La cause est hors du
depot : aucun script n'y tue de processus, les taches planifiees etaient au
repos, **42 Go etaient libres**, et *tous* les processus python sont tombes
ensemble. Je ne la trouverai pas d'ici.

**Alors plutot que de la reinscrire une quatrieme fois, rendre le travail
survivant.** Le chemin des LOTS possede `--sortie`, qui ecrit chaque tache
des qu'elle aboutit — precisement pour cela. Le chemin MAP ne l'avait jamais
eu : ses resultats s'accumulent en memoire seule, et une mort perd vingt
minutes de calcul local.

### 55.1 En cherchant ou poser ce journal, j'ai patche du code MORT

`_map_sur_plan` n'a **aucun appelant**, nulle part. C'est l'implementation
**supersedee** : la docstring de `_repartir_map`, qui la remplace, explique
pourquoi une file commune vaut mieux qu'une part assignee d'avance.

Le patch est annule, la fonction retiree.

### 55.2 L'ANGLE MORT QU'ELLE REVELE

`nexus_cablage.py` traque les **scripts** orphelins. Rien ne traquait les
**fonctions** orphelines. Une granularite entiere echappait au cliquet — et
c'est en tombant dedans que je l'ai vue.

### 55.3 TROIS INSTRUMENTS, DEUX FAUX, ET C'EST LE SUJET

| jet | regle | resultat |
| --- | --- | --- |
| 1er | ne compter que « nom( » | **13 candidats**, la plupart faux : manque les rappels, les cles de tri, les types d'argument |
| 2e | seuil « au plus une reference » | **46 candidats**, dont `_repartir_map` dont j'avais VERIFIE l'appel |
| 3e | seuil ZERO, references par `ast` | **UNE**, concordant exactement avec la recherche textuelle |

L'erreur du 2e jet, nommee : **une definition de fonction ne produit aucun
noeud `Name`**. Le seuil est donc zero reference, jamais une. J'avais suppose
le contraire sans le verifier.

> Deux instruments casses de ma main, sur le meme sujet, en quinze minutes.
> C'est exactement ce que l'operateur martele : *ce qu'on ecrit soi-meme, on
> le valide soi-meme, et l'erreur passe.*

### 55.4 LE CLIQUET, ET SES QUATRE MAILLONS

| maillon | etat |
| --- | --- |
| le script | `scripts/epreuve_orphelines.py` |
| **sa preuve** | contre-epreuve : une orpheline ajoutee -> **code 1**, les deux nommees ; retiree -> code 0. **Rejouee a travers le harnais.** |
| l'appelant | `nexus_test.py --only orphelines` |
| la porte | le harnais **a refuse** l'epreuve : muette a zero orpheline. Corrigee pour toujours dire son compte |

**Et un defaut attrape en comparant aux jumeaux.** Ma reference vivait dans
`.nexus/`, **ignore par git**, alors que `cablage_reference.json` et
`outillage_reference.json` vivent dans `rituels/`, **suivis**. Une reference
ignoree se remet a zero sur chaque machine : le cliquet lit comme une
protection sans en etre une. Deplacee.

**Le cliquet s'est RESSERRE de 1 a 0** en retirant la fonction morte. Toute
nouvelle orpheline echouera desormais — ce qui est la seule facon de fermer
un sujet dans ce depot.

### 55.5 FERME — le journal est pose dans le chemin vivant, et mesure

Pose dans `_ouvrier`, a l'interieur de `_repartir_map` : une ligne JSON par
fenetre, ecrite DES QU'ELLE TOMBE, sur le chemin de succes ET sur celui
d'erreur — un trou dans le journal se confondrait avec une fenetre jamais
traitee. Chemin lu dans `NEXUS_MAP_JOURNAL` : absent, le comportement est
strictement celui d'avant.

**Les trois epreuves, jouees :**

| epreuve | mesure |
| --- | --- |
| **forward** | 5 fenetres annoncees, **5 lignes journalisees**, cles `indice` et `resultat` presentes |
| **reverse** | sans `NEXUS_MAP_JOURNAL`, **aucun fichier ecrit** |
| **survie** | processus tue a 75 s : rendu final **0 octet**, journal **38 fenetres** |

La troisieme est celle qui compte. Avant, une mort perdait la totalite du
travail deja paye ; elle ne perd desormais que la fenetre en cours.

**Ce qui reste, et qui n'est pas fait** : le journal PRESERVE, il ne REJOUE
pas. Une relance repart de zero. La reprise depuis le journal demande une
identite de corpus — sans elle, on fusionnerait les fenetres d'un corpus dans
un autre.

### 55.6 ET LE GARDE M'A REBLOQUE — sur le JUMEAU du defaut corrige ce matin

En ecrivant ce commit, le garde shell a refuse la commande au titre du CAS B,
« accent grave non echappe entre guillemets doubles ». Or ces accents graves
etaient dans un heredoc a delimiteur QUOTE, ou le shell ne fait AUCUNE
substitution.

Mesure, faite avant d'affirmer quoi que ce soit :

```
heredoc QUOTE     ->  un texte avec `_repartir_map` entre accents graves
```

L'accent grave arrive LITTERAL. **C'est exactement l'angle mort que j'ai
corrige ce matin sur le CAS A, et que je n'ai pas porte a son jumeau le meme
jour, dans le meme fichier.**

Compte tenu ce jour : c'est la neuvieme fois qu'une lecon est appliquee d'un
cote et pas de l'autre. La classe merite son nom, et elle merite un controle.

### 55.7 CORRIGE — et le premier correctif faisait l'INVERSE

Le banc avait propose une expression reguliere multiligne. **Mesuree** sur la
commande de trois lignes, plutot que relue :

```
origine       'python - <<\'PY\'\nx = "voir `f`"\nPY'
apres regex   'python - <<\'PY\'\nx = "voir `f`"\n'
```

Elle **conservait le corps** et **supprimait le terminateur** — exactement
l'inverse du but. Le refus a tort subsistait, et le fichier compilait. Un
correctif qui compile n'est pas un correctif qui corrige.

Remplace par un parcours **ligne a ligne**, sans expression reguliere
multiligne : l'ouverture se repere sur une seule ligne, le corps est saute
jusqu'au delimiteur seul, et un heredoc a delimiteur NON quote reste examine
puisque le shell y substitue bien.

**Les epreuves**, quatre cas sur le detecteur :

| cas | attendu | obtenu |
| --- | --- | --- |
| heredoc QUOTE, grave dans le corps | passe | passe |
| heredoc NON quote, grave dans le corps | refuse | refuse |
| grave hors heredoc | refuse | refuse |
| grave entre guillemets simples | passe | passe |

**Contre-epreuve**, sur une copie du code d'avant : `detecte=True` avant,
`detecte=False` apres. Et la suite du garde par son harnais : **12 reussis,
0 echec**, le cas neuf compris.

### 55.8 CE QUI RESTE OUVERT — le controle de la classe elle-meme

Neuf fois en un jour, une lecon a ete appliquee d'un cote et pas de son
jumeau. Aucun controle ne garde cette classe. Ce qui la fermerait :

* un controle qui, pour deux fonctions **soeurs** d'un meme fichier — meme
  prefixe de nom, meme role — signale qu'une correction a touche l'une sans
  toucher l'autre depuis N commits ;
* ou, plus simple et plus sur : que toute correction de garde s'accompagne
  d'un cas d'epreuve sur **chacun** des cas declares, ce qui rend l'oubli
  visible au moment ou il se produit.

Le second est mecanisable et ne demande aucune heuristique. **Il est fait** —
sous une forme meilleure que celle envisagee, et c'est une mesure qui l'a
corrigee avant l'ecriture.

### 55.9 FERME — le controle de la classe, et le critere qu'une mesure a change

**Ce que j'allais ecrire** : un controle exigeant que l'epreuve NOMME le
detecteur qu'elle couvre.

**Ce que la mesure a dit** : `epreuve_garde_shell_ps.py` n'en nomme **aucun**.
Elle passe par le protocole du hook, en boite noire — ce qui est **meilleur**,
puisqu'elle eprouve toute la chaine, refus compris. Le controle envisage
aurait donc rougi sur la meilleure des epreuves.

**Le critere retenu, exact et sans heuristique** : pour chaque fonction du
garde nommee `detecter_cas_*`, verifier qu'elle est menee aux **deux issues**.

> Un detecteur qui ne peut pas rendre vrai ne refuse RIEN.
> Un detecteur qui ne peut pas rendre faux refuse TOUT.

Les deux ont deja ete payes ici. La decouverte est **dynamique** : un
detecteur ajoute demain fait echouer l'epreuve tant qu'il n'a pas ses deux
cas.

| maillon | etat |
| --- | --- |
| le script | `scripts/epreuve_couverture_gardes.py` |
| **sa preuve** | detecteur temporaire ajoute sans cas -> `[RATE] detecter_cas_zz : missing test cases`, **code 1** ; garde restaure -> code 0 |
| l'appelant | `nexus_test.py --only couverture` |
| la porte | 6 reussis, 0 echec par le harnais |

Ce qui n'est PAS couvert, et se dit : le controle vaut pour les detecteurs
d'un garde. La classe plus large — toute lecon non portee a son jumeau, quel
que soit le jumeau — reste sans mecanisme general, et il est douteux qu'elle
puisse en avoir un sans heuristique.


