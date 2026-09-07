# Plan — Achever l'isolation, puis frapper en masse sur le cloud

## Contexte

Deux choses sont vraies en même temps, et le plan les traite dans cet ordre.

**Un.** Le rangement du projet est fait aux trois quarts — `scripts/` est passé
de 166 à 29 fichiers, `outillage/` porte les 127 fichiers d'orchestration, un
clone reçoit 8,57 Mo au lieu de 20,26 — **mais il a cassé le produit**, et
précisément parce que l'outillage y était mêlé : les scripts de la passerelle
appelaient mes outils comme des voisins de répertoire.

**Deux.** Le disque porte **968 Mo de corpus** dont **271 Mo, soit 2 801
fichiers, sont invisibles à tous les outils de recherche** — jamais indexés,
donc jamais consultés. La connaissance est là et personne ne peut l'atteindre.

---

# PARTIE A — ACHEVER L'ISOLATION

## A.0 L'état des dégâts, mesuré

| classe | ampleur | visible à `git grep` ? |
| --- | --- | --- |
| chemins **assemblés** PowerShell | 13, dont le démarrage et la porte d'intégrité | **non** |
| `"scripts"` **gravé en dur** | **92 occurrences, 50 fichiers** | oui |
| contrôles devenus **aveugles** | 3 mécanismes qui rendent **VERT** | non |

Le troisième est le pire. `controle_hooks_cables` annonce *« 5 hooks pointent
sur un script présent »* alors que le settings en déclare **8** : sa regex ne
matche que `scripts/`. **Vert sur une vue partielle.**

## A.1 Vague 1 — RÉPARER (le produit est à terre)

Six tâches, parallélisme 6, cloud. Chacune rend des patchs ancrés.

| # | cible | ancres |
| --- | --- | --- |
| 1 | 13 chemins PowerShell assemblés | `Test-NexusConfig.ps1:71` · `Update-NexusModels.ps1:121,148,169,198,272,298` · `start.ps1:201,282` · `nexus.ps1:91,247,251,267` |
| 2 | `controle_hooks_cables` aveugle | `nexus_conformite.py:588` (regex) et `:593` (join) |
| 3 | `controle_gardes_accordes` | `nexus_conformite.py:167` |
| 4 | périmètre des 3 linters | `nexus_outillage.py:243` (ruff) et `:471` (PSScriptAnalyzer) |
| 5 | 4 chemins gravés restants | `nexus_conformite.py:743,1376,1432,2019` |
| 6 | `model_list.txt` cherché à côté | `update_local_models.ps1` — défaut **antérieur**, commit séparé |

**Contre-épreuves exigées** : le hook doit compter **8**, pas 5. Le linter doit
passer de 21 à ~99 violations — `outillage/` en cache **68**, `epreuves/` **8**.
C'est la fin d'une cécité, pas une régression : `--rebaseline` avec la raison
écrite, jamais l'inverse.

## A.2 Vague 2 — MÉCANISER

Trois outils, chacun avec sa contre-épreuve **et son appelant**. Sans appelant,
un script n'est pas un mécanisme : c'est un fichier.

**`outillage/nexus_chemins.py`** — tout chemin nommé existe-t-il ? Cinq sources :
fichiers suivis, settings du dépôt, settings **global** (barres obliques *et*
antislashs doublés JSON), planificateur Windows (chemins tantôt absolus tantôt
**relatifs** après `Set-Location`), périmètre des linters. Dégrade, ne plante
jamais. Appelant : `nexus_rituel.py:498`.

> Il aurait attrapé **quatre des cinq pannes du jour** : 3 tâches planifiées
> muettes, le verrouillage de session par un hook, les chemins morts de la
> consigne permanente, la cécité du linter.

**`outillage/nexus_racine.py`** — remonter jusqu'à **deux marqueurs** parmi
`scripts/`, `outillage/`, `docker-compose.yml`, `.git`. Un seul ne suffit pas :
plusieurs répertoires `scripts` existent à des profondeurs différentes.
Remplace les **29** `dirname(dirname(__file__))` d'`epreuves/`.

**Contrôle d'identité des paires copiées** — six modules existent en double sur
consigne « ce qui pourrait casser ⇒ copie ». Rien n'échoue si l'une dérive. Les
deux cliquets existants comptent une **quantité** attachée à un **périmètre** —
ils se sont trompés trois fois aujourd'hui pour cette raison.

## A.3 Vague 3 — ACHEVER

- **92 occurrences gravées** → `nexus_racine.chemin(...)`, par lots de 15.
- **Préambule `sys.path` des 7 gardes** → libère 4 modules, `scripts/` tombe de
  29 à **25**.
- **Découper `scripts/nexus.ps1`** : il expose cinq commandes du produit
  (`start stop status check mcp`) et quatre d'orchestration (`ask valide
  appliquer sujets`). **C'est lui qui empêche `outillage/` d'être détachable.**

---

# PARTIE B — L'INVENTAIRE DU DISQUE

Mesuré pour la première fois, exhaustivement.

## B.1 Ce qui est indexé et atteignable — 391 Mo

| rayon | fragments | poids |
| --- | --- | --- |
| `livres` (`code` 11 898 · `epub` 11 377 · `packt` 6 698) | **29 973** | 79 Mo |
| `node_docs` (Node 22.23.2) | 4 599 | 12 Mo |
| `python_libs_docs` | 3 069 | 136 Mo |
| `python_libs_docs_eamt5` | 3 069 | 149 Mo |
| `shell_docs` (PowerShell 7.5 · bash 5.3) | 369 | 12 Mo |
| `lecons` | 307 | 2 Mo |
| `securite_confinement` | 29 | 1 Mo |

`references/livres/code` **indexe bien** `CODE_LIVRES` : les 305 Mo de dépôts
GitHub des sept ouvrages sont atteignables par leurs 11 898 symboles.

## B.2 Ce qui est INVISIBLE — 271 Mo, 2 801 fichiers

| corpus | fichiers | poids | contenu |
| --- | --- | --- | --- |
| `livres_texte` | 614 | **114 Mo** | **102 livres techniques français, DÉJÀ PRÉ-MÂCHÉS** |
| `CODE_ENZO` | 1 824 | **82 Mo** | 5 dépôts quant/trading : `ai-trader`, `crucible-quant`, `backtest-overfitting-lab`, `quant-intelligence-platform`, `OS_Pipeline_MT5_forge` |
| `python_ast_local` | 363 | **75 Mo** | **234 211 symboles** d'API de bibliothèques |

Aucun `index.tsv` → `nexus_livres.py`, qui retient les répertoires portant un
index, ne les voit pas. **Ils existent, ils sont payés, ils ne servent à rien.**

### `livres_texte` n'est pas du texte brut — il est pré-mâché

Chacun des 102 livres porte un répertoire `__PRE_MACHE/` à cinq fichiers.
Totaux **mesurés**, en-têtes déduits :

| fichier | contenu | total |
| --- | --- | --- |
| `unites_atomiques.tsv` | id, type, titre, pages, `char_debut`, `char_fin`, **`texte_verbatim`** | **29 300** |
| `concepts.tsv` | concept, occurrences, renvois vers unités | **26 995** |
| `structure.tsv` | sections, niveaux, pages, confiance | 4 974 |
| `resumes_sections.tsv` | `resume_mecanique` **et `verbatim`** | 3 914 |

Matières : algorithmique fondamentale, apprentissage statistique, calcul
scientifique, deep learning, finance quantitative, mathématiques fondamentales.

**Trois conséquences, et elles renversent la Partie C.**

1. **Le travail n'est pas un découpage, c'est une conversion.** Le plan
   proposait `nexus_decouper_livres.py` ; le corpus est déjà découpé.
2. **Les 29 300 unités verbatim doublent le corpus consultable** — le dépôt en
   indexe aujourd'hui 29 973, toutes rayons confondus.
3. **Les 26 995 concepts n'ont aucun équivalent.** La recherche du dépôt est
   lexicale sur `resume`, c'est-à-dire sur des **titres de section**. C'est
   très probablement pourquoi mes cinq recherches (`quality gate`, `Goodhart`,
   `false green`, `refactoring`, `path`) ont toutes rendu zéro : je cherchais
   dans des titres, pas dans des concepts. **La faiblesse serait alors le
   schéma d'index du dépôt, pas le corpus.**

**Le verbatim est ce qui compte.** Une conversion qui ne garderait que
`resume_mecanique` perdrait le texte des ouvrages et reproduirait exactement le
défaut que ce corpus existe pour éviter — le pointeur du dépôt porte d'ailleurs
la mention « TEXTE VERBATIM » comme critère de fiabilité.

**Un quatrième schéma serait de trop.** Trois coexistent déjà — `texte` pour
`epub`/`packt`, `implementation` pour `code`, `resume` + `docstring_brut` pour
`node_docs` — et chacun a déjà fait lire des fragments comme vides. La roadmap
doit dire si les schémas s'unifient **avant** toute nouvelle indexation.

## B.3 Deux défauts du pointeur de corpus

`references/livres/_POINTEUR_CORPUS.md` annonce **2 232** fragments pour le
rayon `code` qui en porte **11 898**, et **20 304** au total contre **29 973**
mesurés. Un pointeur qui sous-déclare son contenu d'un facteur cinq décourage
de s'en servir.

## B.4 Mes cinq recherches ont échoué — et l'erreur était MIENNE

J'avais écrit que le corpus « ne couvre pas ce problème » après cinq requêtes
infructueuses (`quality gate`, `Goodhart`, `false green`, `refactoring`,
`path`). **C'est réfuté, et par la mesure.**

| mode | ce qu'il interroge | mesuré dans |
| --- | --- | --- |
| lexical | `row["resume"]` | `nexus_livres.py` |
| sémantique | embeddings construits sur `resume` | `nexus_livres_semantique.py` |

**Les deux cherchent dans les TITRES DE SECTION. Aucun ne cherche dans le
texte.** Épreuve de la recherche sémantique, jamais lancée jusqu'ici :

```
requête : comment eviter qu une metrique de qualite devienne fausse
          quand le perimetre change

0.5313  Machine Learning for Algorithmic Trading · Testing the gradients
0.5280  Choosing the right response
0.5263  Mathematics of Machine Learning · 16.1.4 Directional derivatives
```

Hors sujet, scores bas. L'index d'embeddings existe pourtant —
`.nexus/fragments_embeddings.jsonl`, **215 Mo**, 20 366 vecteurs, modèle
`nomic-embed-text`, construit le 2026-09-02.

**Trois défauts, tous mesurés :**

1. il embarque `resume`, donc des **titres**, jamais le texte ;
2. sa couverture est **partielle**, comptée par le champ `rayon` :

| rayon | indexé | réel | couverture |
| --- | --- | --- | --- |
| `epub` | 11 377 | 11 377 | 100 % |
| `packt` | 6 698 | 6 698 | 100 % |
| `code` | **2 291** | **11 898** | **19,3 %** |

**9 607 fragments de code source sont absents de l'index sémantique.**

3. son `build` exige `index.tsv` + `symbols.jsonl`, donc il ignore les trois
   corpus invisibles.

**Ce que cela corrige sur le pointeur périmé.** Le pointeur annonce 2 232
fragments pour le rayon `code` : ce chiffre était **juste** au 2026-09-02. Le
rayon a quintuplé depuis, et ni le pointeur ni l'index n'ont suivi. Ce n'est
donc pas un pointeur qui ment, c'est un chiffre qui n'est pas **dérivé** — et
le remède n'est pas de le corriger à la main.

**Ce que cela réordonne.** La priorité n'est peut-être pas d'indexer les
271 Mo invisibles, mais de faire porter la recherche sur le **texte** des
29 973 fragments déjà indexés : le corpus deviendrait utile avant même d'être
agrandi. Et les 26 995 concepts de `livres_texte` prennent une autre valeur —
ils sont la seule voie d'accès **par le contenu** qui existe sur ce disque.

Coût non mesuré : reconstruire les embeddings sur `texte_verbatim` demande un
passage complet du modèle local. Je ne l'ai pas chiffré.

---

# PARTIE C — LES FRAPPES CLOUD

## C.1 Pourquoi le cloud, et pourquoi maintenant

Le local a rendu **zéro** sur les trois dernières commissions : v34 a tourné
18 min pour un plafond de 900 s, v35 a été arrêtée, v36 tourne encore. Six à
huit processus des trois sessions se disputent le même iGPU.

Le cloud rend en **5 à 9 s**, sans contention, avec zéro rendu vide sur plus de
quarante appels mesurés. **Toute la Partie A tient en trois vagues de quelques
minutes** si le plan cloud répond.

## C.2 L'indexation des 271 Mo invisibles

Un indexeur par nature de corpus, chacun produisant `index.tsv` +
`symbols.jsonl` au format du dépôt :

| corpus | indexeur | réutilise |
| --- | --- | --- |
| `python_ast_local` | par AST | `references/python_ast_eamt5/_outils/extraire_api_par_ast.py` |
| `CODE_ENZO` | par AST | `outillage/nexus_indexer_code.py` |
| `livres_texte` | par section | `outillage/nexus_decouper_livres.py` |

**Aucun ne s'écrit à neuf** : les trois outils existent. C'est leur **appel** qui
manque, pas leur code.

## C.3 Discipline

- **Un seul lot en vol.** Mesure du jour : trois lots empilés ont saturé
  l'iGPU, un a tourné 18 min sans rien rendre, et cela a retardé la réparation
  du produit que j'avais cassé.
- **Cloud pour le volume**, local seulement s'il est muet.
- **LOI 1** : chaque patch produit par le banc, appliqué après vérification que
  l'ancre est unique et réelle, puis **audité par un tiers qui n'a écrit ni le
  diagnostic ni le correctif**.
- **Commit par cause.** Le 14ᵉ chemin mort est antérieur au rangement : il ne va
  pas dans le même commit.

---

# Ce qui reste à l'arbitrage de l'opérateur

Aucune vague ne peut les trancher.

1. **`~/.claude/settings.json`** épingle 7 gardes dans `scripts/` par chemin
   absolu. Ce fichier sert **les autres projets**. Tant qu'il les épingle,
   `scripts/` ne descend pas sous 25 et `outillage/` ne se détache pas.
2. **`.nexus/`** — 2 842 Mo dans le dossier, 103 références dans 36 fichiers, et
   le contrat le nomme comme magasin machine-local.
3. **`python_libs_docs`** versionné ou non — la réponse vaut aussi pour
   `node_docs`, aujourd'hui traités en sens inverse.

# Vérification de bout en bout

Dans cet ordre, chacune passant avant la suivante :

1. `pwsh -File scripts/Test-NexusConfig.ps1` → **code 0** (aujourd'hui : 1)
2. `pwsh -File scripts/start.ps1` → la pile monte
3. `python outillage/nexus_chemins.py` → 0 mort, 0 répertoire non couvert
4. `python outillage/nexus_chemins.py --epreuve` → détecte un témoin mort
5. `python outillage/nexus_racine.py --epreuve` → racine juste depuis profondeur 3
6. échantillon de 30 épreuves → **23 / 7**, mêmes échecs qu'avant le chantier
7. `python outillage/nexus_cablage.py` → 0
8. `python outillage/nexus_rituel.py` → 0
9. `python outillage/nexus_conformite.py` → `hooks cables` compte **8**
10. `python outillage/nexus_livres.py` sur un terme du corpus français → rend un
    fragment de `livres_texte`

**Aucun `py_compile` ne compte comme preuve.** Mesuré aujourd'hui : 68 fichiers
compilaient à 0 pendant que 28 imports étaient cassés, et PowerShell n'a pas de
compilation du tout.
