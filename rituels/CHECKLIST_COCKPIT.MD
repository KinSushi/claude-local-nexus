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
| Les modèles **cloud** échouent en série (« Remote end closed connection », 2,0 s) | `--plan local` rend zéro échec : le défaut est côté cloud, pas côté banc | diagnostiquer quota ou réseau, machine au repos |
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
