# VAGUES DE RÉPARATION — liste complète, mesurée

> Établie le 2026-09-02, révisée le même soir après relecture : **la première version omettait
> plus de la moitié des trouvailles**. Elle listait ce qui restait à faire et oubliait ce qui
> avait été mesuré.
>
> **Chaque chiffre de ce document a été mesuré**, aucun n'est repris d'une note antérieure :
> cinq compteurs du dépôt ont été trouvés périmés le même soir.
>
> Ce fichier n'est **pas généré**. `rituels/CHECKLIST_PROGRESS.md` l'est, par
> `scripts/nexus_checklist_progres.py` — l'éditer à la main serait écrasé au passage suivant.

---

## 0. Le périmètre, et ce qui en est exclu

Consigne de l'opérateur : *« il faut tout faire réparer les fichiers concernant ceux qui sont
le projet lui même »*, *« les outils des autres dépôts bricolés pour le MCP sont rejetés »*,
*« seul compte notre projet FOCUS »*.

Ligne de partage appliquée, celle du contrat §0.5 : un outil qui pose une question **sur ce
dépôt** en fait partie ; un outil portable qui servirait à n'importe quel projet n'en fait pas
partie.

| | mesuré |
| --- | --- |
| scripts Python au total | 143 |
| **dans le périmètre — le projet lui-même** | **46** |
| hors périmètre — outils portables | 97 |
| scripts PowerShell | 17 |
| fichiers JavaScript | 8, dont `server.js` à 3 592 lignes |
| fichiers suivis par git | 279, **tous présents sur le disque** |

La liste des 46 est figée dans `.nexus/fichiers_projet_46.txt`.

**Le dépôt n'est pas détruit** — vérifié : `git fsck` ne rend que des blobs orphelins,
aucune suppression, 279/279 fichiers présents, historique intact, 12 commits non poussés.

---

## 1. Cinq compteurs du dépôt sont périmés

À corriger dans les documents qui les portent, car ils orientent les décisions.

| affirmation | où | réel, mesuré |
| --- | --- | --- |
| « chemins absolus en dur : **0** » | contrat §0.5 | **5**, dans 2 fichiers |
| « **26 fichiers** prescrivent `gpt-oss-120b-cloud` » | `PROGRESS.md:302`, cockpit `:10043` | **31 fichiers**, 114 occurrences |
| « prescriptions rouges : **15** » | `CHECKLIST_PROGRESS.md` §4 | **17** dans `CHECKLIST_LIVRE_VS_CODE.md` |
| « `OLLAMA_MAX_LOADED_MODELS` non défini, le moteur en garde **un** » | contrat §107.1 | **3**, et `NUM_PARALLEL=2` |
| « `OLLAMA_KEEP_ALIVE` non défini, défaut **5 minutes** » | contrat §107.0 | **15m** |

Les deux derniers invalident la conclusion du §107.1 sur la largeur du pool : elle a été
dérivée sous un réglage qui n'existe plus.

Quatre chiffres nus nommés par le cockpit §70.5 comme cibles de la règle de provenance :
`PLAFOND_FILS`, `allowed_fails` et `cooldown_time` **n'existent plus** dans le code vivant ;
seul `NEXUS_CHARGE_SEUIL_MIN` subsiste, dans `epreuve_charge.py:51`.

---

## 2. VAGUE 1 — en cours, cinq agents Fable 5 en worktrees isolés

| # | périmètre | état |
| --- | --- | --- |
| 1 | `epreuve_cles_only.py` orpheline | **RENDU** — câblée `nexus_test.py:1420`, 2 contre-épreuves + régression |
| 2 | `nexus_epreuve_vide.py` appelé sans argument | **RENDU** — épreuve neuve, 3 contre-épreuves par mutation |
| 3 | repli automatique à un seul candidat | **RENDU** — 2 défauts coopérants, forward/reverse/fuite |
| 4 | les dix contrôles confrontés aux docs et livres | **RENDU** — 8 fichiers corrigés, 4 faux verts retirés |
| 5 | couper les liaisons aux dépôts voisins | **RENDU** — 5 chemins coupés, contrôle bloquant neuf |

**Cinq agents sur cinq refusent de se valider eux-mêmes.** Aucun ne s'attribue le VERT
définitif ; tous citent le §0.7.1 et renvoient le troisième temps.

### 2.4 Agent 3 — ma prémisse était FAUSSE, et il le prouve

J'avais écrit dans sa consigne : *« le candidat qui aurait réussi, `gpt-oss-120b-cloud`, a fait
la MÊME tâche en 6 secondes »*. **Faux.**

`gpt-oss-120b-cloud` n'a pas été tenté **à raison** : le filtre de souveraineté
`nexus_agent.py:1057-1069` exclut le cloud pour une demande locale. Ma prémisse aurait conduit
à « réparer » le repli en ouvrant une sortie de données — exactement ce que le §108 interdit.
**L'agent a refusé ma piste et l'a nommée.**

Et ma citation était périmée : `REPLIS_GRATUITS` porte **quatre** entrées depuis le commit
`1c96440`, non deux. Les candidats légitimement jamais tentés étaient `qwen3-coder-30b-local`
et `llama3.2-3b-local`.

**La cause réelle, deux défauts coopérants** :
- `nexus_agent.py:1123` — `break` à la première troncature, posé délibérément par `3e5b01a`
  dont le message **nomme le trou** : *« si la reprise échoue à son tour, plus aucun repli
  n'est tenté »* ;
- `nexus_disjoncteur.py:176-185` — « réponse vide tronquée » classée **PERMANENTE**, donc le
  modèle tronqué est banni avant même sa reprise. Journal réel : `20:00:18 gemma4-12b-local
  permanent open`, `20:07:03 glm-4.7-flash-local permanent open`.

Argument du livre, cité : un disjoncteur surveille un **taux** (« 50 % over 10 requests »), pas
un incident. *« Le classement plafond insuffisant → permanent n'est dans aucun des deux
livres : c'est une propriété de l'APPEL, pas de la cible. »*

**Preuve forward sur la passerelle réelle** : 79 s, `PRET`, servi par `qwen3-coder:30b`,
`x-litellm-model-api-base = http://host.docker.internal:11434` — **plan local, aucune fuite**.

### 2.5 Agent 3 — le moteur Ollama est cassé depuis 16 h 08

**[E]** `app.log` porte une boucle « ollama exited » depuis **16:08:15** — 17 543 lignes. Un
`ollama.exe serve` lancé à la main à 16:07:52 tient le port, et l'application échoue au bind
chaque seconde. Depuis ~21:08 une génération d'un seul jeton sur `llama3.2:1b` expire à 25 s,
machine au repos.

**Cela remet en cause une partie des mesures de la soirée** sur les modèles locaux : ce qui a
été attribué à `gemma4-12b` ou `glm-4.7-flash` peut relever de l'état du moteur.

### 2.6 Agent 4 — quatre contrôles qui ne pouvaient pas rougir

| contrôle | ce qu'il faisait | mesure |
| --- | --- | --- |
| `controle_mcp_a_jour` | notait `ok=True` **quoi qu'il arrive** | un rappel présenté comme une vérification |
| `boussole` de `nexus_rituel` | régénérait `PROGRESS.MD` sous un autre nom | la boussole datait de 07:21, le code de 15:57 — périmée, déclarée OK |
| `arbres recoltes` | « aucun arbre en attente » | **29 worktrees existent** ; le critère ne connaissait que la convention interne, pas celle du harnais |
| `orphelin` de `nexus_cablage` | catégorie **inatteignable** | `BOUSSOLE.md` liste chaque fichier par construction, et la référence du cliquet se comptait elle-même comme appelant |

**Et une fuite de périmètre chiffrée** : `PSScriptAnalyzer` descendait dans les **29
worktrees** depuis la racine — 229 violations ≈ 13 × 17,6. Prouvé par sonde : ajouter un
fichier fautif était annoncé comme **« amélioration 229 → 14 »**. *« Le cliquet ne refusait
plus rien sous 229. »*

`nexus_checklist_progres.py` classé **ROUGE** : il lisait la **dette totale** (85) au lieu du
verdict du cliquet (1), et il n'a **aucun appelant** — la tâche planifiée a été supprimée par
`f364f40`.

Trois épreuves passent au VERT après réparation : `epreuve_progres.py` (quatre causes
indépendantes de rouge permanent, réécrite en 212 lignes), `epreuve_orphelines.py` (faux
positif sur un import aliasé — `ast.alias.name` n'était pas visité), plus deux déjà saines.

### 2.1 Agent 2 — la checklist se trompait de CLASSE de défaut

`CHECKLIST_LIVRE_VS_CODE.md:293` dit « appelé sans argument », ce qui suggère un faux vert.
Mesuré, c'est l'inverse : **un rouge permanent**.

```
python scripts/nexus_test.py --only vide      (AVANT)
  [FAIL] rendu vide   aucun cas rendu par l'epreuve (code 2)
  Reussis : 0   Echecs : 1                    EXIT=1
```

La suite entière rendait 1 **quel que soit l'état du dépôt** — elle ne distinguait donc plus
rien. L'outil, lui, **refuse correctement** : exit 2, message nommant la voie (`<path>...`),
aucun effet de bord. **La faute est chez l'appelant**, `nexus_test.py:1389`, qui le lance sans
argument et n'attend que des `[OK  ]`/`[RATE]` qu'un outil ne parle pas. Le commit `c672862`
qui l'a posé dit lui-même que ces quatre-là « ne sont pas des épreuves mais des OUTILS ».

Correctif : `scripts/epreuve_rendu_vide.py`, 152 lignes, ruff propre, 5 cas sur fichiers
fabriqués en répertoire temporaire. Trois contre-épreuves par mutation de l'outil — rendu muet,
analyse aveugle, `SyntaxError` — les trois font échouer le lanceur ; restauration vérifiée par
empreinte identique avant/après.

**Trois frères sont câblés de la même façon fautive** par le même commit :
`nexus_test.py:1396` (`--only livres` → FAIL code 1), `:1398` (`--only index_livres` → FAIL
code 4), `:1400` (`sauvegarde`, non exécuté car créerait un bundle). Non corrigés.

### 2.2 Deux défauts d'infrastructure trouvés par les agents, hors de leur tâche

**Le plan cloud a disparu entre 20 h 45 et 20 h 57.** Une demande de `gpt-oss-120b-cloud` a été
**servie par `glm-4.7-flash [local]`** — repli autorisé par le §108, mais **toutes les mesures
de la soirée attribuant un échec à un modèle nommé sont potentiellement confondues**. À rejouer
avant d'en tirer une conclusion sur un modèle.

**Le scratchpad est PARTAGÉ entre agents**, malgré l'isolation des worktrees : l'agent 2 y a
trouvé une trentaine de fichiers d'un autre agent, et a dû préfixer les siens pour éviter la
collision. **L'isolation ne couvre pas cet espace.**

Autres relevés de l'agent 2, non corrigés :
- le cliquet compte une **épreuve** comme appelant de **production** — `nexus_cablage.py:284-287`
  n'écarte que « test » là où le filtre des imports (`:302-304`) écarte aussi « epreuve ». Faux
  gain que le mode verdict figerait dans la référence ; l'agent a délibérément évité de le figer ;
- `nexus_epreuve_vide.py:18` dérive le module cible **sans le préfixe `nexus_`** : 31 épreuves
  sur 63 signalées, verdict sur `scripts/` non fiable ;
- `nexus_livres.py` plante sur `references/securite_confinement/index.tsv` — 6 colonnes au lieu
  de 5 — et sort 1 **en silence** à zéro résultat ;
- aucune tâche planifiée Nexus n'existe (`Get-ScheduledTask` et `schtasks` : rien) ; les bundles
  de `NexusSauvegarde` s'arrêtent à 15:55 ;
- `ruff` est absent du venv des worktrees : `nexus_outillage --cliquet` y rend « ruff NON JOUÉ ».

**L'agent 2 a respecté la garde de production** : `Write` lui a été refusé, il a posé son
fichier par un script **déclaré**, et l'écrit dans son rapport — *« sans exploiter le trou Bash
de la garde »*.

### 2.3 Addendum agent 2 — deux défauts de mécanisme, plus lourds que sa tâche

**Le validateur de la LOI 1 ne peut pas tourner depuis un worktree d'agent.**
`nexus_valide.py --base HEAD~1` rend **exit 1 sans jamais juger le diff** : `run_conformite()`
(`nexus_valide.py:187-200`) lève dès que la conformité rend non nul, et les quatre contrôles
bloquants portent tous sur des fichiers **gitignorés que le worktree ne reçoit pas** —
`.env`, `.nexus/latences.json`, `.nexus/epreuves.json`, `.env` encore pour les secrets.

Aucun ne concerne le changement jugé. Ceux qui le concernent sont verts : 139 modules importés
sans échec, portée des imports correcte, encodage conforme.

**Le juge tiers est donc inutilisable depuis l'endroit même où le travail tiers se fait.**
C'est un défaut structurel du cycle à trois temps du §0.7.1. L'agent refuse d'y remédier en
lançant la copie de l'arbre principal, ce qui ferait juger — et écrire — dans l'arbre vivant.

**Un contrôle de validation ÉCRIT dans un fichier suivi par git.** `nexus_conformite` appelle
`nexus_cablage.py` en mode verdict, qui « resserre » `rituels/cablage_reference.json`
(`nexus_cablage.py:426-427`) : il en a retiré `scripts/nexus_epreuve_vide.py` de `preuve_seule`,
**figeant dans la référence le faux gain** décrit au §2.2 — celui où une épreuve compte comme
appelant d'un fichier de production. Détecté par `git diff`, restauré par `git checkout`.

Un contrôle censé vérifier a modifié l'état du dépôt, et ce qu'il a gravé était faux.

**Et l'agent corrige sa propre erreur de méthode** : *« mon premier `tail -30` avait coupé le
haut de la liste — instrument exact, lecture fausse, la classe du dépôt »*. C'est la faute
commise le même soir par l'orchestrateur, qui a détruit une ancre de patch et 663 secondes de
travail. **Deux acteurs, deux fois, le même outil.**

**Ce que l'agent 1 a réfuté** : `CHECKLIST_LIVRE_VS_CODE.md:387` affirme que le cliquet
signalait l'épreuve comme orpheline. Mesuré : **il ne la signalait pas** — il la classait
`PREUVE_SEULE`, figée par `rituels/cablage_reference.json:8`. Le défaut réel existait,
l'instrument ne le voyait pas.

**Défauts collatéraux qu'il signale et n'a pas corrigés** :
`nexus_progres.py:76` cherche `choices=[...]` quand `nexus_test.py:1265` écrit `choices=_choix`
— le compteur rend 0 par construction ; et le cliquet compte sa propre référence comme
appelant, ce qui rend la catégorie `orphelin` inatteignable pour tout script déjà figé.

**L'isolation tient** : une tentative de `git -C` de l'agent 1 vers l'arbre principal a été
**refusée par la garde**. L'arbre principal n'a jamais bougé pendant les cinq lancements.

**Réserve sur l'agent 1** : il a travaillé **sans** le corpus de livres, sans le standard de
code premium, sans le contexte architectural ni l'intégration Claude Code — rien de tout cela
ne lui avait été fourni. Envoyé depuis aux quatre autres.

**Le troisième temps manque pour tous.** L'agent 1 refuse lui-même le vert : *« Audit de la
correction, temps 3 du §0.7.1 : non fait, et il ne doit pas l'être par moi. »*

---

### 2.6.1 UN ZÉRO FAUX DANS `CHECKLIST_PROGRESS.MD` LUI-MÊME — vérifié deux fois

Trouvé par l'agent 4, **revérifié directement par l'orchestrateur** :

```
nexus_sauvegarde.py:117-118      ECRIT dans  .nexus/sauvegardes
nexus_checklist_progres.py:147   LIT depuis  root / "cache" / ".nexus"   <- n'existe pas
bundles reellement presents      5, le plus recent a 15:55
ce que la checklist affiche      | Nombre de fichiers .bundle | 0 |
```

**L'orchestrateur a affiché ce zéro à l'opérateur ce soir**, en régénérant la checklist, et l'a
présenté comme un état mesuré. C'est exactement la classe que le fichier lui-même dénonce à sa
ligne 278 : *« un zéro faux est pire qu'une valeur inconnue »*.

Remède d'une ligne, **non posé** — l'agent l'a trouvé après la demande de rendu.

### 2.7 Couleurs proposées par les agents, fichier par fichier — aucune n'est définitive

| fichier | couleur proposée | motif |
| --- | --- | --- |
| `epreuve_cles_only.py` | VERT proposé | câblée, 2 contre-épreuves, régression |
| `epreuve_rendu_vide.py` (neuf) | VERT proposé | 3 contre-épreuves par mutation |
| `nexus_agent.py` — repli | **JAUNE** | manifestation B prouvée, A non re-mesurée sur la passerelle |
| `nexus_conformite.py` | **JAUNE** | 30 contrôles ne peuvent tous recevoir leur contre-épreuve en un tour |
| `nexus_rituel.py` | **JAUNE** | geste 1 du §0.2 sans mécanisme, appelant fragile |
| `nexus_cablage.py` | **JAUNE** | citation ≠ appel reste ouvert en général |
| `nexus_outillage.py` | **JAUNE** | mécanisme vert, **sa propre preuve ROUGE** hors périmètre |
| `nexus_progres.py` | **JAUNE** | « sujets ouverts : 548 » reste une heuristique |
| `nexus_checklist_progres.py` | **ROUGE** | code réparé, **aucun appelant** — supprimé par `f364f40` |
| `epreuve_progres.py` | VERT proposé | réécrite, 7 cas |
| `epreuve_orphelines.py` | VERT proposé | faux positif retiré, sonde rougit |
| `epreuve_gardes_accordes.py` | VERT | contre-épreuve par mutation jouée |
| `epreuve_conformite_sources.py` | VERT | forward, reverse et fuite déjà présents |
| `nexus_socle.py` + `nexus_conformite.py` — chemins | **JAUNE par construction** | auteur = vérificateur |

**Aucun VERT n'est acquis.** Le §0.7.1 exige un tiers, et le §2.3 établit que ce tiers **ne
peut pas** être `nexus_valide.py` depuis un worktree.

### 2.8 Défauts préexistants découverts en réparant, non corrigés

| défaut | mesure |
| --- | --- |
| `epreuve_reprise_avant_repli.py` était **rouge sur HEAD** | et **bannissait deux modèles de production 300 s à chaque exécution** — corrigé par l'agent 3 |
| `epreuve_fuite_repli.py` cas 4 rouge sur HEAD | même pollution du disjoncteur — **non corrigé** |
| `nexus_appliquer.py` affiche deux verdicts contraires | « [!] Violations detectees : » suivi de « All checks passed! » |
| `nexus_filet.py` orphelin **et** RET505 ligne 91 | tient `cablage tenu`, `outillage tenu` et la porte de conformité en MANQUE sur `main` |
| `epreuve_outillage.py` **ne peut pas passer** | `timeout=10` là où les linters prennent 20-60 s, et attend un message qui n'existe qu'en `--cliquet` sans référence |
| le hook `Stop` **meurt en silence** sur un clone sans `.nexus` | la redirection échoue avant Python, `\|\| true` avale tout |
| `nexus_disjoncteur.py` classe un budget comme propriété **permanente de la cible** | corrigé côté appelant seulement |
| `--sortie-brute` ajoute un saut de ligne à un texte déjà terminé | fichier à double saut final |
| un alias inconnu à replis locaux **ne prend pas le verrou machine** | `nexus_agent.py:1466-1470` |
| `f364f40` a ajouté **54 lignes écrites à la main dans un fichier généré** | toute régénération de `CHECKLIST_PROGRESS.md` les efface ; l'agent 4 les a restaurées |

### 2.9 Ce que les agents ont mesuré sur le corpus, et qui invalide une partie de mon envoi

**Les worktrees ne reçoivent pas le corpus de livres.** L'agent 5 : *« `references/livres/` ne
contient qu'un pointeur, `index.tsv` introuvable dans le worktree »*. L'agent 4 a dû le
**copier** pour y accéder (§0.4).

Les sources que l'orchestrateur leur a envoyées — 20 304 fragments, `CORPUS_LIVRES.md` —
étaient donc **inaccessibles depuis leur worktree** sans copie préalable. Même classe que ce
que le cockpit §17.1 nomme déjà « les agents travaillaient sans les livres ».

**Et ce que le corpus a réellement rendu sur ces mécanismes** : l'agent 4 a compté
`grep -ic` sur les index — `ratchet` 0, `lint` 0, `dead code` 0, `orphan` 0, `checklist` 0,
`invariant` 0, `static analysis` 1, `guardrail` 6, `validation` 30. **Aucun chapitre ne porte
le nom de ces mécanismes** au-delà de « Building coordination guardrails », déjà exploité. Il a
donc conclu qu'il n'y avait rien à en tirer — et l'a dit plutôt que d'inventer une source.

---

## 3. VAGUE 2 — les 20 fichiers du projet portant des violations d'outillage

42 violations, jeu de règles du dépôt `--select E9,F,B,C4,SIM,RET`, binaire
`.nexus/outillage/ruff_venv/Scripts/ruff.exe`.

| violations | fichier | note |
| --- | --- | --- |
| 12 | `nexus_test.py` | le lanceur d'épreuves |
| 8 | `nexus_conformite.py` | **contrôle de démarrage** — le casser bloque la plateforme |
| 3 | `nexus_generate.py` | générateur de `litellm_config.yaml` |
| 2 | `nexus_boussole.py` | |
| 2 | `nexus_preserve.py` | |
| 1 chacun | `epreuve_commande_nexus`, `epreuve_offsets_annexes`, `nexus_appliquer`, `nexus_cablage`, `nexus_capability`, `nexus_checklist_progres`, `nexus_filet`, `nexus_garde_shell`, `nexus_livres_semantique`, `nexus_reprise`, `nexus_rituel`, `nexus_ruche`, `nexus_state`, `nexus_validate`, `nexus_valide` | dont 3 hooks et l'orchestrateur local |

Autres langages, non répartis par périmètre : **8 violations JavaScript** (`no-unused-vars`,
`require-atomic-updates`) et **399 PowerShell** sur 17 fichiers (`PSAvoidAssignmentToAutomaticVariable`,
`PSAvoidOverwritingBuiltInCmdlets`, `PSAvoidUsingEmptyCatchBlock`, `PSReviewUnusedParameter`,
`PSUseApprovedVerbs`).

**53 violations Python restantes sont hors périmètre** — outils portables, exclus par
l'opérateur. Ne pas les traiter.

**26 des 46 fichiers du projet ne portent aucune violation ruff.** Cela ne vaut pas
conformité : ruff ne juge ni la provenance des chiffres, ni les six maillons du §0.2.1, ni les
trois épreuves du §0.1.4.1.

---

## 4. VAGUE 3 — les 17 rouges de `CHECKLIST_LIVRE_VS_CODE.md`

| ligne | prescription | note |
| --- | --- | --- |
| 19 | **Dependency validation** au déploiement | absent |
| 20 | **Coordination testing** | 1 cas sur 4 du livre couvert ; 3 restent rouges |
| 41 | **Tool compatibility checks** | `suivis()` rend des chemins que `contenus()` ouvre |
| 43 | **Tool shadowing** — `nexus_ombre.py` | **4 tentatives échouées, arrêt décidé** — ne pas relancer sans instruction |
| 49 | **Graceful degradation en tiers** | vitrine binaire : publication ou refus total |
| 52 | **TTL sur les données échangées** | `git grep -ci "ttl"` rend **0** |
| 53 | **Timeout-aware retry with backoff** | absent |
| 140 | **12 639 PDF jamais ingérés** | sous `D:\SAS\reference` — hors périmètre depuis « FOCUS » |
| 157 | **repli à un seul candidat** | **pris — vague 1, agent 3** |
| 221 | **Idempotency** | protection accidentelle, 1 outil sur ~46, sans marquage |
| 222 | **TTL** | confirmée rouge |
| 223 | **Dégradation en tiers** | confirmée rouge |
| 293 | **`nexus_epreuve_vide.py` sans argument** | **pris — vague 1, agent 2** |
| 351 | worktrees d'agents nés en retard, resynchronisés au mauvais point | |
| 387 | `epreuve_cles_only.py` orpheline | **pris — vague 1, agent 1**, et l'affirmation était fausse |

**Ce document est une piste, jamais une preuve** — voir la réfutation de la ligne 387.

---

## 5. VAGUE 4 — les gardes, et leurs épreuves

### 5.1 Deux gardes écrites, éprouvées, jamais appelées

`nexus_garde_isolation.py` et `nexus_garde_ecriture.py` figurent dans les règles `deny` —
donc protégées contre leur propre édition, ce qui les fait *paraître* actives — mais **aucun
hook ne les exécute**. Candidat vérifié dans `.nexus/settings_candidat.json` : ancre unique,
JSON valide, 7 blocs `PreToolUse`. Non appliqué : `Edit(**/settings.json)` est une règle
vivante de l'ACL globale.

| garde | forward | reverse |
| --- | --- | --- |
| `nexus_garde_isolation.py` | passe, code 0 | **refuse**, code 2, nomme le remède |
| `nexus_garde_ecriture.py` | passe | **3 vecteurs sur 5** seulement |

### 5.2 `nexus_garde_ecriture.py` est à moitié aveugle

| vecteur d'écriture | verdict |
| --- | --- |
| `echo x > scripts/nexus_garde_agent.py` | REFUSE |
| `echo x \| tee scripts/nexus_garde_agent.py` | REFUSE |
| `Set-Content -Path scripts/nexus_garde_agent.py` | REFUSE |
| `echo x > .claude/settings.json` | **PASSE** |
| `python -c "open('.claude/settings.json','w').write(1)"` | **PASSE** |

Cause, ligne 48 : `chemin_config = os.path.join(ROOT, ".claude", "settings.json")` — elle ne
lit que l'ACL **du projet, 55 règles**, et ignore l'ACL **globale, 185 règles**. Elle applique
moins du quart de la politique en vigueur, et laisse passer le fichier qui déclare toutes les
gardes.

### 5.3 Cinq épreuves de gardes échouent — trois causes, aucune n'étant un défaut des gardes

| épreuve | cause |
| --- | --- |
| `epreuve_garde_shell.py` | chemin doublé : `scripts/scripts/nexus_garde_shell.py` |
| `epreuve_garde_ecriture.py` | `NamedTemporaryFile` encore ouvert → `WinError 32` |
| `epreuve_garde_lecture.py` | idem, `os.unlink` sur un handle ouvert |
| `epreuve_armer_garde.py` | vise `%USERPROFILE%/.claude/settings.json` sans poser `NEXUS_SETTINGS_PATH` → 4 `[RATE]` faux |
| `epreuve_garde_quote.py` | sort **1 par conception** — « contre-épreuve non jouée » : ne peut jamais passer au vert |

Remède documenté pour les deux `WinError 32`, ancré par `nexus_doc` : `delete_on_close=False`.

Conséquence : les gardes ne sont pas cassées, elles sont **non prouvées** — ce qui, au sens du
§0.1.4.1, revient au même.

### 5.4 L'ACL — 46 règles inertes sur 240

Prouvé par Claude Code lui-même, non par lecture :

```
Write(**/.env) is not matched by file permission checks — only Edit(path) rules are.
```

Version installée **2.1.258** ; le changement date de 2.1.210. 22 inertes côté projet, 24 côté
global. **Zéro trou réel** : les 46 chemins sont tous déjà couverts par une règle `Edit()`
vivante. Le niveau de protection tient ; l'expression porte 19 % de poids mort, signalé à
chaque démarrage.

Pour comparaison, le dépôt SAS : 0 règle `Read` en deny et aucune règle `Bash`. Ce dépôt en a
12 et 75 — il est en avance là où l'audit voisin se déclare le plus vulnérable.

### 5.5 Le contrôle qui aurait dû voir les gardes orphelines ne le peut pas

`controle_gardes_accordes` affiche `[ OK ] 5 garde(s) accordés`. Il y en a **sept**. Cause
structurelle, `nexus_conformite.py:137` : `for _event, blocs in hooks_by_event.items()` — il
part des **hooks déclarés**. Une garde sans hook n'apparaît dans aucune itération. Il répond à
« les gardes câblées sont-elles bien accordées ? » et jamais à « toutes les gardes sont-elles
câblées ? ».

---

## 6. VAGUE 5 — défauts d'outillage trouvés par l'usage

Aucun ne vient d'une lecture ; chacun a été rencontré en se servant de l'outil.

| # | défaut | preuve |
| --- | --- | --- |
| 1 | `nexus_appliquer.py` affiche `REFUS` **après avoir écrit** | patch appliqué lignes 56 et 69, verdict `REFUS : occurrences 0` |
| 2 | `nexus_appliquer.py` affiche `APPLIQUE` sur un patch qui **supprime une fonction** | `def cut_menu` disparue, syntaxe valide, corps orphelin, ruff ne signale qu'un import inutilisé |
| 3 | `nexus_garde_shell.py` prend `<<<AVANT>>>`, **marqueur de patch du dépôt**, pour un heredoc | refus sur une commande sans heredoc ; et la garde de production bloque ensuite l'écriture d'une sonde dans `.nexus/`, donc **deux gardes empêchent de diagnostiquer la troisième** |
| 4 | `start.ps1` rend **1** alors que la pile démarre saine | `nexus_conformite` conclut « Conforme, 3 avertissements », 3 conteneurs healthy 26 min plus tard. Même classe que le commit `218133b` |
| 5 | `nexus_doc.py` affirme « ancrage version installée : **OUI** » avec Python 3.13.2 | Python installé : **3.14.7**. Le chemin tiers, lui, n'affirme rien — comportement honnête |
| 6 | `nexus_doc.py` affiche `[type de corpus non reconnu : 'method']` | sur le corpus Node ; il rend tout le contenu, seul l'en-tête est faux |
| 7 | `nexus_context` expire à 900 s sur 312 k jetons et **ne rend rien** | pas même un partiel — toutes les fenêtres calculées sont perdues. `nexus_agent --sortie` a appris cette leçon, `nexus_context` non |
| 8 | `nexus_livres` échoue à 300 s sous contention | deux fois, pendant qu'un modèle de 20 Go occupait le moteur |
| 9 | Le verrou machine sérialise ce que le moteur sait paralléliser | son motif, `nexus_verrou_machine.py:91`, dit « la mémoire du moteur étant partagée » — vrai quand le moteur gardait 1 modèle, faux à 3 |
| 10 | `OLLAMA_CONTEXT_LENGTH` **non posé** | ni processus ni portée User ; contrat §13 et §54 exigent ≥ 64 k, modèles natifs à 262 144 |

---

## 7. VAGUE 6 — la souveraineté, exigence que l'opérateur place au-dessus

*« les données confidentielles RESTENT sur la machine. Si abonnement Claude Code OFF et Ollama
Cloud OFF, on doit pouvoir quand même tourner en local sans rien, avec un orchestrateur.
Permettre contexte 1M avec plusieurs LLM Ollama locaux, système auto distribué. »*

| | état mesuré |
| --- | --- |
| orchestrateur local | `nexus_ruche.py`, 22 702 octets, `--plans local --essaims N` |
| découpage MAP-REDUCE | `nexus_context`, §110 — **échoue à 900 s, ne rend rien** |
| modèles locaux | **52**, 441 Go, dont 11 sous 1,5 Go pour un essaim |
| modèles cloud | **3 seulement**, tous `glm-*:cloud` |
| contexte moteur | **non posé** |
| chiffrage du découpage | `SURVIE_SANS_ABONNEMENT.md` : 165 fenêtres, ~82 min pour 1 M jetons |

**Deux chemins d'appel se contredisent** sur le plan par défaut :

| chemin | défaut | plan |
| --- | --- | --- |
| `tools/nexus-mcp/server.js:106` | `glm-4.7-flash-local` | **local**, privé |
| `scripts/nexus_agent.py:221` | `gpt-oss-120b-cloud` en tête des replis | **cloud**, les données sortent |

Et **31 fichiers prescrivent le second en exemple**, dont le contrat lui-même trois fois. Le
chemin le plus documenté est celui qui sort les données. C'est le §0.6 pris en défaut par le
dépôt : *la voie la plus simple doit être la voie correcte*.

**L'écart à combler** : le mécanisme est écrit, le chiffrage existe, et la capacité **n'est pas
tenue aujourd'hui**. C'est le seul point où une promesse du contrat est contredite par une
mesure directe.

---

## 7.1 L'EXIGENCE PRÉCISÉE — Claude Code en interface, un modèle LOCAL en orchestrateur

Précisions de l'opérateur, dans l'ordre où elles sont venues :

> *« les données confidentielles RESTENT sur la machine »*
> *« si abonnement Claude Code OFF et Ollama Cloud OFF, on doit pouvoir quand même tourner en
> local sans rien, avec un orchestrateur »*
> *« il faut pouvoir tourner en **système auto distribué**, les modèles locaux se coordonnent,
> et il nous faut **un ou deux orchestrateurs qui peuvent remplacer OPUS** »*
> *« et je rajoute **interface = claude code** »*

### 7.1.1 Le fait qui rend l'architecture possible — mesuré, pas supposé

`rituels/SURVIE_SANS_ABONNEMENT.md` §2 :

```
POST http://localhost:11434/v1/messages   ->  HTTP 200 en 48.9 s
```

**Le moteur expose lui-même le protocole Anthropic.** Pas de passerelle, pas de clé, pas
d'abonnement. C'est ce qui permet de rediriger Claude Code vers le plan local :

```powershell
$env:ANTHROPIC_BASE_URL  = "http://localhost:11434"
$env:ANTHROPIC_AUTH_TOKEN = "local"
claude --model qwen3-coder:30b
```

**Piège mesuré, le plus coûteux** : le moteur ignore les alias LiteLLM.
`glm-4.7-flash-local` → **404** ; `glm-4.7-flash:latest` → **200**. Une fois la bascule posée,
il faut le nom Ollama avec son tag.

**Signe que la bascule a pris** : la bannière du client n'affiche plus `Claude Max`.

### 7.1.2 Les orchestrateurs candidats — MESURÉ ce soir sur les 44 modèles locaux

**29 modèles sur 44 déclarent `tools`.** Ceux qui portent en plus `thinking` — la capacité de
planifier avant d'agir, donc de remplacer un orchestrateur :

| modèle | poids | contexte natif | capacités |
| --- | --- | --- | --- |
| `qwen3-vl:32b` | 20,9 Go | **262 144** | vision, tools, **thinking** |
| `gemma4:31b` | 19,9 Go | **262 144** | vision, tools, **thinking** |
| `qwen3.6:27b` | 17,8 Go | **262 144** | vision, tools, **thinking** |
| `gemma4:26b` | 18,6 Go | **262 144** | vision, tools, **thinking** |
| `glm-4.7-flash` | 19,0 Go | 202 752 | tools, **thinking** |
| `gpt-oss:20b` | 13,8 Go | 131 072 | tools, **thinking** |
| `qwen3-coder:30b` | 18,6 Go | **262 144** | tools (sans thinking) |

**Pour l'essaim** : `llama3.2:1b` pèse **1,3 Go** et déclare pourtant **131 072 de contexte et
`tools`** ; `granite3.1-moe:1b` de même à 1,4 Go ; `llama3.2:3b` à 2,0 Go.

### 7.1.3 Ce que la mémoire permet, chiffré

Mesuré : **66,2 Go totale, 25,7 Go disponible** (un modèle de 19 Go étant résident).

| scénario | modèles | poids | verdict |
| --- | --- | --- | --- |
| 1 orchestrateur lourd + 4 ouvriers légers | 5 | 26,0 Go | **dépasse** la marge |
| 2 orchestrateurs + 3 ouvriers | 5 | 36,8 Go | **dépasse** largement |
| essaim léger seul, 10 ouvriers | 10 | **14,9 Go** | **tient** |

**Et le plafond du moteur bloque les trois** : `OLLAMA_MAX_LOADED_MODELS = 3`. Aucun essaim
n'est possible sans relever ce réglage — c'est le verrou n° 1, et il se lève par une variable
d'environnement.

### 7.1.3.1 CORRECTION — mon verdict était faux, et l'erreur était de me brider

Consigne de l'opérateur : *« il ne faut pas se brider soi-même, que tout soit **auto-évolutif**
et **adaptatif à l'hôte**. Si la machine peut auto-actualiser les modèles cloud et locaux et
tenir 2-3 modèles ou plusieurs, tant mieux. **Ne pas se figer uniquement sur ma machine
actuelle.** »*

Le tableau du §7.1.3 déclarait deux scénarios « dépasse ». **C'était faux.** Il chiffrait
contre la **mémoire libre à l'instant** — 25,7 Go, un modèle de 19 Go étant déjà résident —
au lieu du **budget dérivé de la machine** par `nexus_capability.py` :

```
CPU 12 coeurs / 24 threads · GPU Radeon 890M integre · RAM 66,2 Go
Budget pool     39,7 Go     <- DERIVE, non grave
Budget maximal  56,2 Go
52 modeles ACCEPTES au routage automatique
```

Recalculé sur la bonne base :

| scénario | modèles | poids | verdict |
| --- | --- | --- | --- |
| 1 orchestrateur + 4 ouvriers légers | 5 | 26,0 Go | **tient dans le pool** |
| 2 orchestrateurs + 3 ouvriers | 5 | 36,8 Go | **tient dans le pool** |
| 2 gros orchestrateurs + essaim | 4 | 40,3 Go | tient au budget maximal |
| essaim léger, 10 ouvriers | 10 | 14,9 Go | tient largement |
| **essaim maximal, 20 ouvriers** | **20** | **23,8 Go** | **tient largement** |

**Les cinq passent.** Vingt ouvriers légers occupent 23,8 Go sur un budget de 39,7.

**Ce n'est donc pas la machine qui bride : c'est `OLLAMA_MAX_LOADED_MODELS = 3`.**

### 7.1.3.2 LE PRINCIPE — dériver, y compris ce qui est aujourd'hui gravé

Le contrat porte déjà la règle, empruntée au dépôt voisin (§0) : *« tout dériver et ne rien
graver, puisqu'une mesure gelée ment le lendemain »*. `nexus_capability.py` l'applique — budget
et verdicts par modèle sortent de la machine.

**Mais trois valeurs restent gravées, et ce sont exactement celles qui bornent l'essaim :**

| valeur | état | ce qu'elle devrait être |
| --- | --- | --- |
| `OLLAMA_MAX_LOADED_MODELS` | **posé à 3, à la main** | dérivé de `budget_pool ÷ poids moyen des résidents` |
| `OLLAMA_CONTEXT_LENGTH` | **non posé** | dérivé du contexte natif des modèles retenus et de la RAM |
| `OLLAMA_NUM_PARALLEL` | posé à 2 | dérivé des cœurs et de la bande passante mesurée |

Aucune des trois ne vit dans le dépôt : elles sont dans l'environnement Windows. Le dépôt
mesure la machine et **n'agit pas** sur le moteur qu'il mesure.

**Ce que « auto-évolutif » impose, concrètement :**

1. **Dériver les trois réglages moteur** du profil matériel, au lieu de les subir. Un outil qui
   lit `nexus_capability` et pose les variables — avec la contre-épreuve qui prouve qu'il
   rougit si le réglage posé ne correspond plus à la machine.
2. **La fraîcheur des modèles** — l'opérateur la nomme. `Update-NexusModels.ps1` et la tâche
   planifiée de 04:00 existent déjà (§105.4) ; **mais aucune tâche Nexus n'est enregistrée sur
   cette machine** (0 sur 202, mesuré deux fois par deux agents). Le mécanisme est écrit, il ne
   tourne pas.
3. **Ne rien conclure de la machine actuelle.** Les chiffres de ce document — 39,7 Go, 52
   modèles, 20 ouvriers — décrivent **cette** machine ce soir. Sur un hôte à 128 Go ou avec un
   GPU dédié, `nexus_capability` rendrait d'autres budgets et l'essaim s'élargirait **sans
   qu'une ligne change**. C'est déjà vrai du pool ; ça ne l'est pas encore des trois réglages.

> **La règle à retenir** : un chiffre de ce document qui n'est pas dérivé d'une mesure de la
> machine est une dette, pas un fait. Les trois réglages moteur sont aujourd'hui la seule
> dette de cette nature dans la chaîne d'exécution.

### 7.1.3.3 LA MIGRATION GPU EST DÉJÀ TRAITÉE — vérifié, contre mon attente

Consigne : *« prévoir GPU dans le futur, actuellement j'ai iGPU partagé avec CPU »*.

Je m'attendais à un trou. Il n'y en a pas. **Trois mécanismes existent et se répondent :**

**1. La configuration ne grave pas le CPU** — `docker-compose.yml:57-58` :

```yaml
OLLAMA_LLM_LIBRARY: ${OLLAMA_LLM_LIBRARY:-cpu}
OLLAMA_VULKAN:      ${OLLAMA_VULKAN:-false}
# le passage a une carte graphique plus tard ne doit demander aucune reecriture
```

Des variables surchargeables, avec un défaut — pas des valeurs figées.

**2. `docker-compose.gpu.yml` existe** (941 octets), non chargé par défaut *« parce que
réserver un périphérique absent ferait échouer le démarrage »* — et il annonce le
comportement attendu :

> *« Le profil matériel s'adapte seul ensuite : avec une VRAM dédiée, le budget d'éligibilité
> au routage devient la VRAM et non la RAM système, et les fenêtres de contexte suivent.
> **Aucune autre modification requise.** »*

**3. Et le code tient cette promesse** — `nexus_capability.py:403-408` :

```python
discrete = bool(gpu["vram_gb"] >= 6 and not gpu["integrated"])
if discrete:
    fast_budget = gpu["vram_gb"] * POOL_FRACTION
    max_budget  = max(gpu["vram_gb"], usable) * RUNNABLE_FRACTION
```

Le budget bascule **seul** de la RAM vers la VRAM. La détection d'iGPU se fait par motif —
`radeon\d{3}m|iris|uhd|vega|integrated|graphics$` — avec sa justification mesurée dans le code :

> *« Un iGPU ne dispose pas d'une VRAM propre : la valeur annoncée est une réservation prélevée
> sur la mémoire système, pas un budget distinct. **Mesuré sur Radeon 890M, passer du CPU au GPU
> intégré ne gagne que 7 %**, parce que le goulot est la bande passante mémoire, que les deux
> partagent. »*

C'est un exemple du standard CODE PREMIUM appliqué : le seuil n'est pas nu, il porte sa mesure.

#### Deux réserves précises, et elles sont étroites

| réserve | portée |
| --- | --- |
| **NVIDIA seulement** | `docker-compose.gpu.yml` grave `driver: nvidia` et `OLLAMA_LLM_LIBRARY: cuda`. Un GPU **AMD dédié** (ROCm) ou **Intel Arc** n'est pas couvert — il faudrait un second fichier de surcharge, sur le même patron |
| **`vram_gb >= 6` est un chiffre nu** | ligne 403, sans provenance, contrairement au seuil des 7 % juste au-dessus. Une carte de 4 Go serait traitée comme intégrée |

#### Ce que la migration changera vraiment, et qu'il faudra re-mesurer

Le contrat §100 le dit déjà : *« ne pas simplement augmenter chaque modèle »*. Avec une VRAM
dédiée, **six mesures de ce document deviennent caduques** :

- le budget pool (39,7 Go dérivé de la RAM) ;
- les cinq scénarios d'essaim du §7.1.3.1 ;
- les débits du contrat §107.3 (20,22 tok/s pour un 30B) — mesurés sur bande passante partagée ;
- le seuil `SEUIL_POOL_MS` de démarrage ;
- la conclusion « le local n'a rien produit d'utilisable ce soir » (§11) ;
- et l'arbitrage sur le merging, qui devient praticable avec du calcul disponible.

**Aucune ne demande de réécriture** : elles se refont en relançant `nexus_capability.py` et
`nexus_bench.py`. C'est précisément ce que « adaptatif à l'hôte » signifie — et sur ce point,
le dépôt tient sa promesse.

### 7.1.3.4 SUJET OUVERT — comment tenir 45 modèles de 0,5 B sans saturer RAM et GPU

Consigne de l'opérateur : *« 10 qwen 0,5B est possible, c'est là où ce n'est pas très
adaptable. Un qwen 0.5B chaud rend en 1 s en local. »* puis *« rajoute au plan : trouver
comment cela est possible, 45 × 0.5B, sans pour autant taponner la RAM/GPU »*.

#### Le défaut du plafond actuel, chiffré

| base de calcul | poids moyen | plafond que la formule produit |
| --- | --- | --- |
| les 51 modèles installés | 8,64 Go | **4** |
| médiane | 6,14 Go | 6 |
| les 11 modèles < 1,6 Go | 0,87 Go | **45** |
| `qwen2.5:0.5b` / `qwen3:0.6b` | **0,46 Go** | **86** |

**Dix qwen 0,5 B occupent 4,6 Go, soit 12 % du budget de 39,7 Go.**

La recommandation de 4 vient d'une moyenne **écrasée par les gros** — `mixtral:8x7b` à 26 Go,
`qwen3-vl:32b` à 21 Go. Un plafond unique ne peut pas servir un orchestrateur de 20 Go et un
essaim de 0,46 Go : la formule décrit une machine, pas un usage.

#### LA TENSION QUI REND LE SUJET NON TRIVIAL — et c'est elle qu'il faut résoudre

Le poids des fichiers n'est PAS ce qui occupe la mémoire. `SURVIE_SANS_ABONNEMENT.md` porte
cette mesure :

> *« `llama3.2:3b` occupe déjà **16 Go en mémoire pour 2 Go de poids**. Le cache de contexte
> domine largement le modèle, et monter à 64 k ou 128 k multiplie ce coût. »*

Corroboré ce soir : `qwen2.5-coder:32b` pèse 19,9 Go sur disque et **21,8 Go résident**, à un
contexte de seulement **8 192**.

**Donc les deux recommandations du chantier « réglages moteur » se contredisent** :

    OLLAMA_CONTEXT_LENGTH = 65536   multiplie par 8 le cache de CHAQUE modele resident
    45 modeles legers residents     multiplie par 45 le nombre de caches

Les tenir ensemble est impossible sur 39,7 Go. **C'est le vrai sujet, et il n'est pas résolu.**

#### Ce qui est mesuré, et ce qui ne l'est pas

| | état |
| --- | --- |
| poids disque des petits modèles | **mesuré** — 0,46 Go |
| `MAX_LOADED_MODELS` est un COMPTE, jamais un poids | **mesuré** — 43,1 Go tenus à 3 modèles, au-dessus du budget |
| le cache de contexte domine le poids | **mesuré** — 16 Go pour 2 Go de poids |
| coût mémoire réel d'un 0,5 B à contexte réduit | **NON MESURÉ** |
| latence à chaud d'un 0,5 B | **NON MESURÉ** — deux tentatives expirées à 120 s, sous contention |
| débit agrégé de N petits modèles contre un gros | **NON MESURÉ** |

#### Les pistes à explorer, aucune vérifiée

1. **Contexte par modèle, pas global.** `OLLAMA_CONTEXT_LENGTH` est une variable unique du
   moteur. L'API `/api/generate` accepte `options.num_ctx` **par requête** — un essaim
   pourrait tourner à 2 048 pendant que l'orchestrateur travaille à 65 536. À vérifier :
   le moteur alloue-t-il le cache par modèle chargé, ou par requête ?
2. **`keep_alive` différencié.** Un ouvrier appelé une fois n'a pas besoin de rester résident
   quinze minutes. `keep_alive: "30s"` sur les ouvriers libérerait la mémoire entre les vagues.
3. **Rotation plutôt que résidence.** 45 modèles chargés *simultanément* n'est peut-être pas
   le bon objectif : 45 modèles *disponibles* avec 5 résidents en rotation donnerait le même
   parallélisme apparent si le rechargement d'un 0,46 Go est réellement rapide — ce qui reste
   à mesurer.
4. **Le plafond dérivé du profil d'usage**, non de la moyenne globale : `budget ÷ poids du plus
   lourd de l'essaim visé`, avec l'essaim déclaré et non deviné.

#### La mesure qui tranchera, et elle n'a pas encore abouti

Charger **un seul** `qwen2.5:0.5b` avec un budget généreux, puis mesurer trois appels à chaud
et relever sa taille résidente réelle par `ollama ps`. Deux tentatives ont expiré ce soir sous
contention d'un modèle de 21,8 Go. **Tant que ce chiffre manque, tout le reste est spéculation
— y compris le « 1 s à chaud ».**

### 7.1.4 L'architecture complète, et sa tension

```
Claude Code (interface)
   |  ANTHROPIC_BASE_URL -> 127.0.0.1:11434   [protocole Anthropic, mesure : 200]
   v
modele ORCHESTRATEUR local  (tools + thinking, 262k)
   |  appelle les outils MCP
   v
serveur nexus-local  (15 outils)
   |
   +-- nexus_ruche    -> essaim d'ouvriers legers, coordination
   +-- nexus_context  -> MAP-REDUCE, le contexte de 1M
   +-- nexus_ask / nexus_route / ...
```

**La tension, écrite dans le dépôt même** (`SURVIE_SANS_ABONNEMENT.md` §6) :

> *« Rediriger `ANTHROPIC_BASE_URL` vers le moteur donne **un modèle à 8 k, pas un essaim**. Le
> découpage vit dans les outils de ce dépôt, pas dans le protocole. »*

La distribution ne vient donc **pas** de la bascule : elle vient des outils MCP que
l'orchestrateur appelle. La bascule fournit l'interface ; `nexus_ruche` et `nexus_context`
fournissent l'essaim.

### 7.1.5 CE QUI N'EST PAS PROUVÉ — et le dépôt le dit lui-même

> *« Ce qui n'est PAS prouvé, et il faut le dire : le protocole répond ; **l'usage agentique
> complet du client — outils, sessions, fichiers — n'a pas été éprouvé de bout en bout**. »*

À quoi s'ajoutent trois obstacles mesurés ce soir :

| obstacle | mesure |
| --- | --- |
| `OLLAMA_MAX_LOADED_MODELS = 3` | interdit tout essaim de plus de trois |
| `OLLAMA_CONTEXT_LENGTH` non posé | les modèles déclarent 262 144, le moteur applique son défaut |
| `nexus_context` expire à 900 s sans rien rendre | le MAP-REDUCE qui donne le 1M ne tient pas sur 312 k jetons |

**Les trois se lèvent dans cet ordre** : le réglage moteur d'abord, la mesure ensuite, la
réparation du MAP-REDUCE en dernier — car sans les deux premiers, la mesure du troisième décrit
une machine bridée.

### 7.1.6 Le code de référence existe, et il est sur le disque

`OllamaProvider` (§13.2.11) parle au moteur **en direct**, avec appels d'outils, sans
passerelle. C'est la brique d'un orchestrateur local, écrite et lisible — seul le paquet
`ollama` manque (`ModuleNotFoundError`, mesuré).

---

## 8. VAGUE 7 — corpus, documentation, capacités absentes

### 8.1 Livrés et prouvés ce soir

| corpus | mesure |
| --- | --- |
| livres pré-mâchés, sur **D:** | 226 livres, 32 008 fragments chapitre + 87 969 menu, 419 Mo, seek **400/400** |
| calibre | médiane 2 820 car (~705 jetons), p99 3 002, **0 %** au-delà de 4 000 |
| extraction | 225 livres, 183,9 Mo de texte, 8 minutes, rendement pondéré 3,9 % |
| doc Node, sur **C:** | v22.23.2, 4 598 symboles, 795 fragments de prose rejetés, 1 840 alias, seek **300/300** |

**5 livres non extraits.** Cause trouvée : **4 chemins de sortie dépassent 260 caractères**
(263, 266, 269, 285) — la limite Windows. Le suffixe `_Qwen_Parse` ajoute 11 caractères et fait
basculer ces quatre-là. Remède : préfixe de chemin étendu `\\?\`. **Non corrigé.** Le
cinquième est réellement illisible.

### 8.2 La documentation des 60 bibliothèques Python

| | mesuré |
| --- | --- |
| bibliothèques documentées | 63, 110 Mo, 166 507 symboles |
| **réellement installées ici** | **5** — `numpy`, `polars`, `pydantic`, `torch`, `typer` |
| répartition | 52,5 % ML/stats, 41,3 % dev, 6,2 % quant |
| la plus volumineuse | `torch`, 30,6 Mo — **28 % du corpus** |
| second exemplaire | `python_libs_docs_eamt5`, 149 Mo |

Le corpus a été bâti pour le projet de trading voisin, pas pour celui-ci. Sa valeur qui
survit : **empêcher le banc d'inventer des signatures**, ce qui ne dépend pas de ce qui est
installé.

**Lacune** : zéro documentation Node/JavaScript avant ce soir, alors que `server.js` fait
3 592 lignes et que chaque appel d'outil y passe. Comblée.

### 8.3 Capacités absentes du parc de modèles

Vérifié contre la bibliothèque Ollama, avec deux témoins connus présents pour valider la sonde :

| capacité | verdict |
| --- | --- |
| **reranker** | **aucun modèle**, et **aucune route `/rerank`** sur le moteur — 404 sur les trois formes, témoin `/api/embed` à 400. Structurel, pas un oubli de téléchargement |
| modèle de garde | `llama-guard3` et `shieldgemma` **présents** dans la bibliothèque, non tirés |
| math | `mathstral` **présent**, `qwen2.5-math` absent |
| vérification factuelle | `bespoke-minicheck` **présent** — classe si une affirmation est étayée par une source |

Voie réelle pour le reranking : `torch 2.13.0+cpu` est **déjà installé** — un cross-encoder
hors d'Ollama est la voie courte.

### 8.4 Sur le merging de modèles

**Aucun des 55 modèles n'est fusionnable** : 44 blobs > 1 Go, magic `GGUF`, tous quantifiés.
Le merging exige du fp16 safetensors. 4 des 55 ne sont pas des LLM génératifs mais des
encodeurs. Les couples partageant architecture **et** taille se comptent sur une main.

---

## 9. VAGUE 8 — les 16 couches, cartographie rendue par le banc et arbitrée

Source : `D:/Bibliotheque_Ultime_KOS_IA/16_Couches_IA_et_architectures.pdf`, extrait en
quelques secondes.

**Couches 1 à 9 denses et réelles. Couches 10 à 16 vides, sauf 16.**

Le banc a classé la couche 16, Interopérabilité, « COUVERT : rien ». **Faux** : `.mcp.json`
déclare `nexus-local` avec quinze outils — c'est un registre de capacités sur un protocole
standard, exactement ce que la couche réclame. C'est la couche la mieux servie, classée vide.

Gestes rejetés à l'arbitrage, parce que le banc ne connaît pas la machine : Kubernetes local,
registre de modèles en Git avec les `.gguf`, quantification ONNX (mauvaise pile — Ollama est
GGUF/llama.cpp), Airflow, Unity ML-Agents, consensus Raft.

Geste retenu : **un `purpose.yaml` lisible par machine** — le §0 du contrat est déjà cette
chose, écrite en prose.

**Les six couches vides partagent un seul verrou** : chacune suppose un système capable de
juger ses propres sorties. `nexus_bench` mesure la latence et le débit, `nexus_savings` le
volume délégué, `nexus_conformite` la conformité structurelle. **La qualité : rien.** C'est
le même obstacle que pour le merging — la boucle de rétroaction n'a pas de capteur.

---

## 10. VAGUE 9 — isolation et sécurité de la session

Mesuré : Windows 11 **Professionnel** build 26200, hyperviseur **présent**, WSL2 Ubuntu
installé, Docker Desktop en service, **un seul compte actif**.

| mécanisme | isole | disponible |
| --- | --- | --- |
| `uv` / `venv` | les paquets Python, **rien d'autre** | `uv` déjà installé |
| compte Windows dédié + ACL NTFS | le profil, les clés, les documents | à créer |
| Docker | processus et FS ; tout volume monté perce | oui |
| WSL2 | noyau distinct ; `/mnt/c` monte tout C: par défaut | oui, à configurer |
| **Windows Sandbox** | VM jetable | **`WindowsSandbox.exe` ABSENT** — une case à cocher |
| Hyper-V, VM dédiée | tout | hyperviseur déjà là |

**`venv` et `uv` n'isolent rien au sens sécurité** — ils cloisonnent des dépendances, pas des
capacités. Le meilleur rapport isolation/friction est un **compte Windows dédié** : les ACL
NTFS rendent les clés *illisibles* et non « refusées par une règle ».

**Infrastructure, à ne pas supposer** : trois conteneurs — `litellm-db` (postgres:16),
`litellm-redis` (redis:7-alpine), `litellm-proxy` (épinglé par digest). **Le moteur Ollama
tourne sur l'HÔTE** : le service existe dans `docker-compose.yml:44` mais derrière
`profiles: ["embedded"]` et n'est pas démarré. Donc `docker exec ollama-server` échoue.

**Le serveur MCP survit à la panne de la passerelle** : quand Docker était arrêté,
`nexus_livres` répondait — index local via Ollama direct — pendant que tout ce qui passe par
le port 4000 rendait `socket hang up`.

---

## 11. Ce que le plan local n'a pas tenu, mesuré ce soir

| modèle | tâche | résultat |
| --- | --- | --- |
| `gemma4-12b-local` | un patch ancré d'une ligne | **tronqué à 6 933 jetons** pour un budget de 2 000 |
| `glm-4.7-flash-local` | la même | **4 000 jetons de sortie, `car_par_jeton 0.0`** — zéro caractère, 405 s |
| `qwen3-8b` et `mistral-7b` | tri mécanique, 12 lots | **rendu vide**, bascule automatique sur un 30B |
| `gpt-oss-120b-cloud` | la même tâche | **6 à 17 s**, douze fois de suite |

Sur les tâches à forme imposée, le plan local n'a rien produit d'utilisable ce soir. Ce n'est
pas une conclusion générale : c'est une mesure sur une classe de tâches.

**Et le banc fabrique quand on ne lui donne pas la documentation** : il a rendu les numéros de
ligne **19 et 84** là où les vrais étaient **20 et 179**. Vérifiés dans le code ; un agent qui
ne l'aurait pas fait aurait corrigé au mauvais endroit. C'est la justification mesurée de
*« la documentation et les livres empêchent d'halluciner »*.

---

## 12. Mes propres fautes, inscrites plutôt que tues

Elles font partie de l'état réel, et deux d'entre elles ont coûté du travail.

| # | faute | conséquence |
| --- | --- | --- |
| 1 | Annoncé **0 violation** sur mes trois scripts | faux — `ruff` lancé avec les règles par défaut au lieu des six familles du dépôt. Réel : **10** |
| 2 | Annoncé **2 fichiers manquants** dans `docs/architecture/` | faux — `git ls-files` échappe les non-ASCII en octal ; 279/279 présents |
| 3 | Empilé **4 lots** sur le banc contre la consigne | deux recherches sémantiques expirées à 300 s |
| 4 | Pipé la sortie du banc dans `tail -60` | a **détruit le marqueur `<<<AVANT>>>`**, patch inapplicable, 663 s perdues |
| 5 | Annoncé que `nexus_agent.py` n'avait pas de sortie fichier | faux — `--sortie` et `--sortie-brute` existent |
| 6 | Premier moniteur : branche « mort silencieuse » | **faux positif** — confondait « modèle non résident » et « processus mort » |
| 7 | Second moniteur : branche « rendu » | **faux positif** — le `.jsonl` reçoit une ligne aussi en cas d'échec |
| 8 | Consignes aux agents portant **mon diagnostic** | un auditeur à qui l'on donne la conclusion vérifie mon intention, pas les faits |
| 9 | Aucun agent n'a reçu docs, livres, code premium, architecture, Claude Code, Docker | corrigé depuis, par message à chacun |
| 10 | Donné une commande PowerShell pour une invite Bash | `Remove-Item: command not found` |
| 11 | Première version de ce fichier | **omettait plus de la moitié des trouvailles** |

---

## 13. VAGUE 10 — les livres qui peuvent mener le projet à son aboutissement

Recherche menée dans le corpus de **226 livres** indexé ce soir sur D: — 119 977 fragments,
recherche lexicale, échantillon 1 fragment sur 3, coût nul. Ce corpus n'avait jamais servi
avant cette recherche.

### 13.1 Verrou n° 1 — l'évaluation, et le livre qui le traite

**`AI Engineering`, Chip Huyen — VÉRIFIÉ par lecture de fragments, pas par densité.**

Citation exacte, chapitre 3 :

> *« Due to the importance and complexity of evaluation, this book has two chapters on it. This
> chapter covers different evaluation methods used to evaluate open-ended models, how these
> methods work, and their limitations. The next chapter focuses on how to use these methods to
> select models for your application and build an evaluation pipeline. »*

**Deux chapitres entiers** sur ce qui manque : juger une sortie ouverte, et **choisir un modèle
parmi plusieurs** — le dépôt en a 55 sans moyen de les départager.

Et il pose le piège de la LOI 1 avec ses objections :

> *« The rising star of subjective evaluation is AI as a judge... It's subjective because the
> score depends on what model and prompt the AI judge uses. While this approach is gaining rapid
> traction, it also invites intense opposition from those who believe that AI isn't trustworthy
> enough for this important task. »*

C'est le capteur absent du §9 : `nexus_bench` mesure la latence, `nexus_savings` le volume,
`nexus_conformite` la structure — **la qualité, rien**. Sans lui, les couches 10 à 16 sont
inatteignables, le merging est une marche aléatoire, et le choix parmi 55 modèles est arbitraire.

### 13.2 Verrou n° 2 — le contexte distribué

| livre | densité | état |
| --- | --- | --- |
| **`Context Engine Reference Guide`** (ISBN 9781806690053) | — | **NON VÉRIFIÉ**, mais sa première phrase est sur le sujet exact |
| `Designing Data-Intensive Applications` | 86 | NON VÉRIFIÉ |
| `Prompt Engineering for Generative AI` (Phoenix) | 89 | NON VÉRIFIÉ |
| `Generative AI with LangChain` | 61 | NON VÉRIFIÉ |
| `Design Multi-Agent AI Systems Using MCP and A2A` | 56 | déjà indexé sur C:, déjà cité par la checklist |
| `Context Engineering for Multi-Agent Systems` | 47 | déjà indexé sur C: |

Première phrase du `Context Engine Reference Guide`, relevée dans le corpus :

> *« The context engine is a sophisticated, multi-agent system designed to transform the
> interaction paradigm with LLMs. »*

C'est littéralement le système décrit par l'opérateur — plusieurs LLM locaux coordonnés pour
dépasser la fenêtre d'un seul.

`Designing Data-Intensive Applications` apporte ce qui manque à `nexus_ruche` pour devenir un
essaim plutôt qu'une boucle : partitionnement, tolérance aux pannes, cohérence.

### 13.2.1 `Context Engine Reference Guide` — VÉRIFIÉ, méthode utilisable, pile à rejeter

Extraits relevés dans le corpus :

- **un `planner()` explicite** : `resolve_dependencies()` remplace les références par l'état,
  `registry.get_handler()` récupère l'agent, l'état s'accumule (`state["STEP_1_OUTPUT"]`), et
  **chaque étape est tracée**. C'est ce qui manque à `nexus_ruche` : une boucle qui garde son
  état et sait le reprendre après interruption — exactement le défaut mesuré sur
  `nexus_context`, qui perd toutes ses fenêtres en expirant ;
- **recouvrement entre fragments** — 50 jetons chez lui, 200 caractères ici — *« pour maintenir
  le contexte sémantique à travers les frontières »* ;
- **enrichissement de métadonnées** décrit comme *« l'étape critique pour la vérifiabilité »* ;
- et une phrase qui rejoint la question des gardes :
  > *« l'architecture reconnaît explicitement les limites de l'automatisation. Elle intègre un
  > « méta-contrôleur » piloté par politique, reconnaissant que **les protections les plus
  > robustes impliquent souvent des règles organisationnelles extérieures au raisonnement de
  > l'IA**. »*

**RÉSERVE DISQUALIFIANTE POUR L'IMPLÉMENTATION** : le livre emploie **Pinecone**, base
vectorielle cloud, et **`text-embedding-3-small`** d'OpenAI. Son architecture entière fait
sortir les données. Prendre la méthode, rejeter la pile — le dépôt a `nomic-embed-text`,
`bge-m3` et `qwen3-embedding` en local.

### 13.2.2 `Designing Data-Intensive Applications` — VÉRIFIÉ, portée plus étroite qu'annoncé

Les fragments denses portent sur les **bases de données** : réplication, partitionnement,
cohérence de préfixe, élection de leader, shared-nothing. Les principes transfèrent —
coordination au niveau logiciel, idempotence, tolérance aux pannes — mais **ce n'est pas de la
distribution d'inférence**. Utile pour la méthode, pas comme recette. Priorité moindre que les
deux précédents.

### 13.2.3 Le local et la souveraineté — classement vérifié par extrait

| livre | densité | extrait relevé |
| --- | --- | --- |
| **`Design Multi-Agent AI Systems Using MCP and A2A`** | 49 | *« un sous-système extensible qui définit une interface générique de fournisseur LLM et fournit quelques implémentations (OpenAI et **Ollama** pour l'instant) »* |
| ISBN 9781837022014 | 48 | *« running local models for privacy and cost efficiency »* |
| ISBN 9781806116478 | 40 | *« scale from local development to enterprise production... on-premises infrastructure »* |
| `Generative AI with LangChain` | 39 | *« run both cloud-based and local models, balancing cost, privacy, and performance »* |
| `Hands-On ML with Scikit-Learn and PyTorch` | 35 | section sur **Ollama** en ligne de commande |

**Le premier est déjà indexé sur C:** et sert déjà de source à `CHECKLIST_LIVRE_VS_CODE.md` —
mais son chapitre 4, qui porte une **implémentation Ollama d'une interface de fournisseur
générique**, n'a jamais été exploité. C'est le chaînon le plus proche de l'exigence
« tourner en local sans rien ».

### 13.2.4 `Release it!` — le livre qui traite les défauts trouvés ce soir, VÉRIFIÉ

Trouvé en cherchant ce que le corpus dit du défaut que l'agent 3 venait de mesurer : un
disjoncteur qui ouvre le circuit sur **un seul** incident. Citation exacte :

> *« Timeouts have natural synergy with circuit breakers. **A circuit breaker can tabulate
> timeouts, tripping to the "off" state if too many occur.** The Timeouts and Fail Fast
> patterns both address latency problems. Timeouts protect your system from someone else's
> failure ; Fail Fast reports why you won't be able to process some transaction. »*

C'est mot pour mot le remède au défaut de `nexus_disjoncteur.py:176-185`, qui classe
« réponse vide tronquée » comme **permanente** sur une occurrence unique. Le livre prescrit de
**tabuler** et de comparer à un seuil.

Et sur la raison d'être du mécanisme :

> *« Preventing cascading failures is the very key to resilience. The most effective patterns to
> combat cascading failures are **Circuit Breaker and Timeouts**. »*
> *« le disjoncteur existe pour permettre à un sous-système d'échouer sans détruire le système
> entier ; et une fois le danger passé, le circuit [se referme]. »*

**Ce livre couvre trois lignes rouges de `CHECKLIST_LIVRE_VS_CODE.md` à lui seul** :
ligne 53 « Timeout-aware retry with backoff », le disjoncteur du §221-223, et la dégradation en
tiers de la ligne 49 — le *Fail Fast* qu'il oppose au *Timeout* est exactement la distinction
qui manque à `nexus_vitrine.py`, binaire aujourd'hui.

**Priorité relevée : c'est le livre le plus directement actionnable du corpus** pour les rouges
restants, devant les trois précédents qui traitent de méthode.

### 13.2.5 Deux autres, sur les défauts trouvés par les agents

Recherche menée sur les classes exactes de défauts que les agents ont découvertes.

| défaut trouvé ce soir | livre le plus dense | extrait vérifié |
| --- | --- | --- |
| un **contrôle qui écrit** (`cablage_reference.json` modifié par la validation) | `Fluent Python` (57), `Learning Python` (55) | *« Changing Class Attributes Can Have Side Effects »*, chapitres sur mutabilité et effets de bord |
| **isolation des épreuves** (scratchpad partagé, worktree sans corpus) | `Modern C++ Programming Cookbook` (65) | fixtures, setup/teardown — méthode transposable, langage étranger |
| **pipeline d'évaluation continue** | `Machine Learning Design Patterns` (19) | *« Continuous evaluation of this kind requires access to the raw prediction request... to determine whether the model, or any changes we've made, are working as they should »* |

`Machine Learning Design Patterns` complète `AI Engineering` : le premier donne le **motif
d'évaluation continue**, le second la **méthode de jugement d'une sortie ouverte**. Ensemble
ils couvrent le capteur manquant du §9.

### 13.2.6 Les rouges restants, et ce que le corpus a pour eux

Recherche menée sur les prescriptions rouges de `CHECKLIST_LIVRE_VS_CODE.md` non encore
appariées à une source.

| rouge | livre le plus dense | verdict |
| --- | --- | --- |
| ligne 49 **dégradation en tiers** | `Site Reliability Engineering` (14), `Release it!` (13) | **RETENU** — SRE : *« cheaper-to-compute results to the user... see Load Shedding and Graceful Degradation »* ; `Release it!` : le motif **Bulkhead**, *« splitting a single chain reaction into two »* |
| §221 **idempotence** | `Designing Data-Intensive Applications` (31) | **RETENU** — *« We discuss idempotence in more detail in Chapter 11 »*, dans le chapitre sur les appels distants |
| ligne 19 **dependency validation** | `Combinatorial Optimization` (61), `Causality` (58) | **REJETÉ** — faux positifs : `DAG` et `acyclic` y désignent des graphes mathématiques, pas des dépendances de déploiement |
| §222 **TTL** | `Paul Wilmott on Quantitative Finance` (187) | **REJETÉ** — faux positif massif : `ttl` matche à l'intérieur de mots, et le livre traite de finance stochastique |

**Deux rejets sur quatre.** Le second est instructif : chercher `ttl` comme sous-chaîne rend
187 occurrences dans un livre de mathématiques financières. Sans lecture d'extrait, la
recherche aurait désigné Wilmott comme source sur les durées de vie de cache.

`Site Reliability Engineering` entre au classement : c'est la seconde source sur la dégradation
en tiers, et elle traite en plus du *load shedding*, absent de la checklist.

### 13.2.7 Classement final, par utilité mesurée

| rang | livre | ce qu'il débloque | vérifié |
| --- | --- | --- | --- |
| **1** | `Release it!` | **3 rouges** — disjoncteur (tabuler, pas réagir), timeout, Bulkhead pour la dégradation | oui, 3 extraits |
| **2** | `AI Engineering`, Chip Huyen | le capteur de qualité absent — **2 chapitres** sur juger une sortie ouverte et choisir un modèle | oui, 3 extraits |
| **3** | `Design Multi-Agent AI Systems` ch. 4 | interface fournisseur **avec implémentation Ollama** — le « tourner en local sans rien » | oui, 1 extrait |
| **4** | `Site Reliability Engineering` | dégradation en tiers, load shedding | oui, 1 extrait |
| **5** | `Designing Data-Intensive Applications` | idempotence, shared-nothing — **bases de données, pas inférence** | oui, 3 extraits |
| **6** | `ML Design Patterns` | motif d'évaluation continue, complément du n° 2 | oui, 1 extrait |
| **7** | `Context Engine Reference Guide` | `planner()` avec état et reprise — **pile cloud à rejeter** | oui, 4 extraits |

### 13.2.8 `Prompt Engineering for Generative AI` — il traite l'échec le plus répété de la soirée

Le banc a manqué la forme imposée **sept fois** : marqueurs tronqués faute de budget,
`<<< BEFORE >>>` rendu en anglais au lieu du marqueur du dépôt, fichier rendu sans clôture
quand l'extracteur en cherchait une, fichier rendu avec clôture quand la consigne l'interdisait.
Chaque échec a coûté un aller-retour, et l'un d'eux 663 secondes.

Le livre nomme exactement ce défaut, vérifié par extrait :

> *« Common errors that you'll encounter when working with JSON involve invalid payloads, or
> **the JSON being wrapped within triple backticks** »*

Et il donne deux remèdes, dont **aucun n'est appliqué dans ce dépôt** :

1. **Relance automatique sur échec d'analyse** — *« broken JSON will result in a parsing error,
   which can act as a **trigger to retry the prompt** or investigate before continuing »*.
   Ici, chaque échec de forme a été relancé **à la main** par l'orchestrateur.
2. **Décodage contraint plutôt que consigne en prose** — *« specify JSON output in the model
   parameters where available (this is called **grammars** with Llama models) »*.

Le dépôt demande aujourd'hui un format de marqueurs `<<<AVANT>>> / <<<APRES>>> / <<<FIN>>>`
**par une phrase dans le prompt**. Un format imposé au décodage ne peut pas être manqué.

**À VÉRIFIER avant d'agir** : le moteur Ollama expose-t-il un paramètre de sortie contrainte,
et `nexus_agent.py` le transmet-il à travers LiteLLM ? Non vérifié ce soir — le moteur était en
panne (§2.5). Ne pas conclure sans mesure : c'est une capacité fournisseur, et le §103 du
contrat interdit de les inventer.

**Second candidat sur ce thème, non vérifié** : `Natural Language Processing with Transformers`
— *« knowledge distillation, quantization, and pruning »*, utile pour la ligne « faire tourner
de petits modèles locaux » plutôt que pour la forme.

### 13.2.9 Le poison du classement lexical : les sous-chaînes courtes

Trois recherches ont été détruites par des acronymes de trois lettres qui matchent **à
l'intérieur des mots** :

| terme cherché | livre en tête | occurrences | réalité |
| --- | --- | --- | --- |
| `ttl` | `Paul Wilmott on Quantitative Finance` | 187 | finance stochastique |
| `pii` | `Handbook of regression methods` | **999** | régression linéaire |
| `slm` | `Handbook of Survival Analysis` | 30 | analyse de survie |
| `model selection` | idem, et `Hidden Markov Models` | 24-30 | sélection **statistique** par AIC/BIC, sens étranger |
| `grammar` | `Speech and Language Processing` | 92 | grammaires **linguistiques** |
| `DAG`, `acyclic` | `Combinatorial Optimization`, `Causality` | 58-61 | graphes mathématiques |

**Six faux positifs sur une seule passe.** Sans lecture d'extrait, la recherche aurait désigné
un manuel de régression comme source sur la confidentialité des données.

**Règle qui en découle, à inscrire dans `CORPUS_LIVRES.md`** : ne jamais classer un livre sur un
terme de moins de quatre caractères, ni sur un terme dont le sens change de domaine
(`grammar`, `model selection`, `validation`, `regression`). La vérification par extrait n'est
pas un supplément de rigueur : c'est la seule chose qui distingue un résultat d'un artefact.

### 13.2.10 CARTE COMPLÈTE — 26 thèmes cherchés, corpus de 226 livres épuisé

Quatre passes lexicales sur les 119 977 fragments, échantillon 1 sur 2 ou 1 sur 3.
**Un livre n'entre ici que si un extrait a été lu.** Densité seule = rejeté.

#### Ce que le corpus couvre, par problème du dépôt

| problème | livre | extrait vérifié |
| --- | --- | --- |
| **disjoncteur qui ouvre sur un incident** | `Release it!` | *« a circuit breaker can **tabulate** timeouts, tripping if **too many** occur »* |
| **capteur de qualité absent** | `AI Engineering` | *« this book has **two chapters** on evaluation... build an evaluation pipeline »* |
| **choisir parmi 55 modèles** | `AI Engineering` | même chapitre 4 |
| **fusion de modèles** | `AI Engineering` | section **« Model Merging and Multi-Task Finetuning », p. 347** — réponse directe à la question posée |
| **reranker absent** | `Hands-On Large Language Models` (Alammar) | *« giving the model two texts — le modèle est alors un **crossencoder**. Un exemple est le **reranking**, chapitre 8 »* |
| **tourner en local sans rien** | `Design Multi-Agent AI` ch. 4 | *« interface générique de fournisseur LLM... implémentations OpenAI et **Ollama** »* |
| **dégradation en tiers** | `Site Reliability Engineering` | *« cheaper-to-compute results... Load Shedding and Graceful Degradation »* |
| | `Release it!` | motif **Bulkhead** |
| **idempotence** | `Designing Data-Intensive Applications` | *« We discuss idempotence in more detail in Chapter 11 »* |
| **messages hors d'ordre** | idem, **96 occurrences** | horloges logiques, numéros de séquence |
| **agent lent ou muet** | ISBN 9781806029570 | *« safety net patterns, such as **Watchdog Timeout** and **Agent Calls Human** »* |
| **données malformées** | `30 Agents Every AI Engineer` | *« transient failures warrant **automatic retry with backoff**, permanent failures... routed to a **deadletter queue** »* |
| **humain dans la boucle** | ISBN 9781806116478 | *« audit logs of all agent actions... **human-in-the-loop approval** for sensitive operations »* |
| **injection de prompt** | `Adversarial AI` — **138** | chapitre 14 entier : injection directe, override, style injection |
| **mémoire d'agent** | ISBN 9781806109012 | *« context window where relevant history is **summarized** and stored in working memory, less relevant archived in **long-term vector** [store] »* |
| **découpage** | ISBN 9781803246970 | *« chunks de **256-512 jetons avec 64 de recouvrement** »* — chiffres concrets |
| **garde de sortie** | `Context Engineering for Multi-Agent Systems` — **102** | ch. 8 « Moderation, Latency, and Policy-Driven AI » ; protocole **pre-flight / post-flight** |
| **forme imposée non respectée** | `Prompt Engineering for Generative AI` | relance sur erreur d'analyse ; **grammaires** = décodage contraint |
| **quantification, petits modèles** | `Deep Learning with C++` | *« Distillation, Pruning, Quantization, Range selection »* |

#### Ce sur quoi le corpus est MUET, dit plutôt que comblé

| thème cherché | résultat |
| --- | --- |
| `ratchet`, `lint`, `dead code`, `orphan`, `checklist`, `invariant` | **0 occurrence** dans les index C: — mesuré par l'agent 4 |
| **tool shadowing** — journaliser sans exécuter | rien : les hits sur `shadow` renvoient aux **modèles de substitution adverses**, sens étranger |
| **validation de dépendances au déploiement** | rien : `DAG` et `acyclic` renvoient aux graphes mathématiques |
| **TTL, fraîcheur de cache** | rien : `ttl` matche à l'intérieur des mots |
| **test de systèmes multi-agents** | quasi rien — 7 et 3 occurrences, hors sujet |

**Cinq thèmes sur vingt-six sont sans source.** Ce sont exactement ceux où le dépôt devra
inventer plutôt qu'emprunter — et le savoir vaut mieux que de chercher indéfiniment.

#### Les six ISBN identifiés par leur contenu

Le corpus ne les nomme que par leur numéro ; les titres ont dû être extraits du texte.

| ISBN | sujet établi par extrait |
| --- | --- |
| 9781806029570 | architecture d'agents — orchestrateur, handoffs, watchdog, human-in-the-loop |
| 9781806109012 | agents autonomes — mémoire de travail et vectorielle |
| 9781806690053 | `Context Engine Reference Guide` — moteur de contexte multi-agents |
| 9781806116478 | histoire de l'IA + sécurité des agents, journaux d'audit |
| 9781835087985 | défense de l'IA contre les attaques adverses |
| 9781837022014 | LangChain — recherche hybride, modèles locaux |
| 9781803246970 | ML pour le trading systématique — mais **les chiffres de découpage** sont bons |

### 13.2.11 LE CODE SOURCE DES LIVRES — la ressource la plus actionnable, jamais touchée

`references/livres/code/symbols.jsonl` — **2 231 symboles**, chacun avec sa signature, sa
docstring, ses paramètres **et son implémentation complète**. Sur C:, indexé, gratuit.
**Jamais consulté avant ce soir.** C'est du code qui tourne, pas de la prose à traduire.

#### Ce qu'il contient pour les problèmes du dépôt

| problème | symboles trouvés |
| --- | --- |
| disjoncteur | **5** dont `class CircuitBreaker`, `_is_retryable`, `RetryableAPIError` |
| orchestration | **39** dont `def planner(...)`, `MAKDOWorkflowTest`, `KubernetesFailureSimulator` |
| mémoire d'agent | **43** dont `agent_summarizer`, `MockLLMProvider`, `create_mock_agent` |
| évaluation | **61** |
| découpage | **25** dont `preprocess_documents(docs, chunk_size=500, ...)` |
| **reranking** | **0** — cohérent avec le manque mesuré au §8.3 |

#### `CircuitBreaker` — le remède exact au défaut de `nexus_disjoncteur.py`

`30-Agents-Every-AI-Engineer-Must-Build/chapter04/agent_utils.py`, lignes 284-397 :

```python
failure_threshold: int = 3      # echecs CONSECUTIFS avant ouverture
recovery_timeout: float = 5.0   # open -> half_open
etats : closed / open / half_open
```

> *« **closed** : Normal operation. Failures are **counted**. **open** : All calls blocked;
> fallback returned. **half_open** : A single **probe** call is permitted. Success resets the
> breaker to closed; failure reopens it. »*

`nexus_disjoncteur.py:176-185` ouvre **immédiatement** sur un seul motif non transitoire, et n'a
**pas d'état half_open** : rien ne referme le circuit par une sonde. L'agent 3 l'a mesuré, le
livre le prescrit, et **le code existe déjà sur le disque**.

**Et il porte sa propre provenance** — exactement ce que le cockpit §70.5 exige et que le dépôt
n'applique pas :

```
Author: Imran Ahmad
Ref: Section 4.3, Table 4.1, pp. 14-15
failure_threshold : int — Consecutive failures before opening (book default: 3, p. 14)
```

Chaque valeur cite sa source dans la docstring. C'est le standard CODE PREMIUM **implémenté**,
et il vient d'un livre, pas d'un gabarit voisin rejeté.

#### `planner()` — 31 lignes, le remède au défaut de `nexus_ruche.py`

`Context-Engineering-for-Multi-Agent-Systems/commons/engine/engine_k15.py`, lignes 49-79 :

```python
def planner(goal, capabilities, client, generation_model):
    """Analyzes the goal and generates a structured Execution Plan.
       Verified Signature: 4 parameters."""
```

Deux choses qu'il fait et que le dépôt ne fait pas :

1. **`json_mode=True`** passé à `call_llm_robust` — le **décodage contraint** identifié au
   §13.2.8. Le livre ne demande pas la forme en prose, il l'impose au décodage. Le dépôt a
   manqué sa forme sept fois ce soir en la demandant par une phrase.
2. **Chaînage de contexte par jetons** : `"$$STEP_N_OUTPUT$$"` — la sortie d'une étape se
   réfère explicitement, et `resolve_dependencies()` la substitue. C'est l'état repris que
   `nexus_context` perd quand il expire.

**Autres symboles voisins à lire** : `call_llm_robust` (l'appel robuste lui-même),
`agent_summarizer`, `preprocess_documents(docs, chunk_size=500, chunk_overlap=...)`.

#### `OllamaProvider` — le chemin « tourner en local sans rien », en code qui tourne

`Design-Multi-Agent-AI-Systems-Using-MCP-and-A2A/ch08/ai-six/py/backend/llm_providers/ollama_provider.py`
lignes 8-113, **3 939 caractères**, `bases: ['LLMProvider']`, six méthodes :

```
__init__  _tool2dict  _tool_call2dict  _fix_tool_call_arguments  send  models
```

Il implémente une interface abstraite `LLMProvider(ABC)` — dont il existe aussi
`OpenAIProvider` et `MockLLMProvider` dans le même dépôt. **Il parle à Ollama en direct**, avec
les appels d'outils au format function-calling, sans passerelle ni conteneur.

C'est **exactement** l'exigence de l'opérateur : *« si abonnement Claude Code OFF et Ollama
Cloud OFF, on doit pouvoir quand même tourner en local sans rien »*. Ici, « sans rien » veut
dire sans LiteLLM, sans Docker, sans réseau — le moteur de l'hôte et rien d'autre.

Détail qui prouve que ce code a tourné : `_fix_tool_call_arguments` corrige un travers réel du
protocole — Ollama rend parfois `arguments` en chaîne là où un dictionnaire est attendu. On
n'écrit pas ce correctif sans l'avoir rencontré.

**Et un `MockLLMProvider` accompagne les deux** : de quoi éprouver l'orchestration sans appeler
un modèle, ce que le dépôt ne sait pas faire aujourd'hui.

#### Les autres symboles directement utilisables

| symbole | fichier | ce qu'il apporte |
| --- | --- | --- |
| `call_llm_robust(system_prompt, user_prompt, client, generation_model, json_mode)` | `Context-Engineering/commons/engine/helpers.py` | l'appel robuste **avec `json_mode`** — 3 implémentations |
| `resolve_dependencies(input_params, state)` | idem, `engine_k15.py` | la substitution `$$STEP_N_OUTPUT$$` — **10 implémentations** |
| `AgentRegistry` | `Context-Engineering/commons/ch6/registry.py` | registre d'agents, ce que `nexus_ruche` n'a pas |
| `get_embedding(text, client, embedding_model)` | `Context-Engineering/commons/helpers.py` | embeddings, à rebrancher sur `nomic-embed-text` local |
| `preprocess_documents(docs, chunk_size=500, chunk_overlap=...)` | `generative_ai_with_langchain/chapter9/ray/build_index.py` | découpage paramétré |
| `MockVectorStore`, `MockVectorDB`, `MockEmbeddingModel` | `30-Agents/chapter14/mock_llm.py` | éprouver un RAG **sans appeler un modèle** |

#### Ce que cela change au classement

Le code des livres passe **devant la prose** pour trois des sept problèmes principaux :
disjoncteur, planificateur, découpage. Pour ceux-là, il n'y a plus à concevoir — il y a à
**adapter un code lu**, ce qui est un travail d'une autre nature et d'un autre coût.

**Réserve** : ce code vient de dépôts d'éditeurs et n'a pas été éprouvé ici. Il se lit comme
une source, pas comme une dépendance — et le §0 impose la copie, jamais l'emprunt en place.

### 13.2.12 LE CODE DU LIVRE SUR CLAUDE CODE — et ce qu'il révèle en creux

`references/CODE_LIVRES/PacktPublishing__Agentic-Coding-with-Claude-Code`, 2,0 Mo, 122 fichiers,
huit chapitres. **Jamais consulté.**

#### Sur les hooks, ce dépôt est EN AVANCE sur le livre

Le `settings.json` du livre (`Chapter03/hooks-notification/.claude/settings.json`) en entier :

```json
{"hooks":{"Stop":[{"matcher":"","hooks":[{"type":"command",
  "command":"uv run /Users/edenmarco/GithubProjects/claude-code-crash-course/play_sound.py"}]}]}}
```

**Un seul hook, qui joue un son, avec un chemin absolu vers la machine de l'auteur.** Le livre
qui enseigne les hooks commet le défaut que les agents ont corrigé ce soir (§0.5, cinq chemins
coupés). Ce dépôt en déclare **sept gardes sur quatre événements**.

Conclusion pour l'audit livre-contre-code : sur ce point, **le code n'a rien à apprendre du
livre**. C'est un résultat, pas un échec de recherche.

#### En revanche : QUATRE ÉVÉNEMENTS DE HOOK NON EMPLOYÉS

Son catalogue `hookhub/src/data/hooks.json` recense 18 projets externes. L'entrée
`claude-code-hooks-mastery` (disler, 1 900 étoiles) nomme ses types :

```
PRE_TOOL_USE  POST_TOOL_USE  USER_PROMPT_SUBMIT  NOTIFICATION
STOP  SUBAGENT_START  SUBAGENT_STOP  SUBAGENT_STREAM
```

Employés ici : `SessionStart`, `PreToolUse`, `PostToolUse`, `Stop` (projet) ; `PreToolUse`
(global). **`SessionStart` ne figure pas dans leur liste** — leur inventaire est donc incomplet
ou d'une autre version. **Piste à vérifier contre la documentation officielle, pas une
spécification.**

**L'écart qui compte : `SubagentStart` et `SubagentStop` ne sont pas employés.** Ce soir, cinq
agents ont tourné dans cinq worktrees isolés, et **rien n'était accroché à leur départ ni à
leur fin**. Or le §0 du contrat liste « la récolte automatique des worktrees d'agents » comme
**encore ouverte** — et un hook `SubagentStop` est précisément le mécanisme qui la ferait.

De même, `UserPromptSubmit` porterait automatiquement l'injection de sources que
l'orchestrateur a faite **à la main** ce soir, après l'avoir oubliée pour quatre agents sur
cinq (§12, faute n° 9).

#### Cinq définitions d'agents, contre une ici

`Chapter02/hookhub2/.claude/agents/` : `prd-writer`, `python-backend-dev`,
`react-typescript-specialist`, `system-architect`, `ui-designer`. Ce dépôt n'a que
`nexus-delegue.md`.

Et des `CLAUDE.md` **hiérarchiques** — `memory/frontend/CLAUD.MD`, `memory/spec/CLAUDE.md` —
là où ce dépôt n'en a qu'un par racine. À évaluer : un contrat de 2 500 lignes chargé
intégralement à chaque session contre des contrats locaux chargés selon le répertoire.

#### Prérequis mesuré pour `OllamaProvider`

```
python -c "import ollama"   ->   ModuleNotFoundError
```

Le paquet `ollama` **n'est pas installé** — cohérent avec la mesure du §8.2 (5 bibliothèques
sur 60). C'est le seul obstacle matériel à l'emploi de cette implémentation.

### 13.3 Le piège du classement par densité, mesuré

Les livres de **trading sortent en tête** sur le thème « évaluation » — 145 et 142 occurrences,
devant `AI Engineering` à 123 — parce que le backtesting emploie exactement le même
vocabulaire : *held-out*, *benchmark*, *test set*, *significance*, *confidence interval*.

**Sans vérification par lecture, la recherche aurait recommandé un livre de finance
quantitative pour évaluer des LLM.** C'est la démonstration que la densité lexicale n'est pas
la pertinence.

### 13.4 Ce que cette recherche révèle sur le corpus lui-même

Le corpus de D: **n'a aucun index sémantique** — seulement l'index lexical par `seek` construit
ce soir. Celui de C: en a un (`nomic-embed-text`, 20 304 fragments). La recherche sur 226
livres est donc bornée aux mots exacts, avec les faux positifs que cela implique.

Six livres du corpus ne portent qu'un **ISBN** comme nom de fichier ; leur titre a dû être
extrait du texte. Un index sémantique demanderait d'abord de résoudre ces identités.

---

## 13.5 L'ÉTAT FINAL ATTENDU — le cadre, tel qu'il ressort des consignes et des mesures

### 13.5.1 Ce que la plateforme doit être

| exigence | source | état mesuré |
| --- | --- | --- |
| **les données confidentielles ne quittent pas la machine** | opérateur, « le plus important » | filtre de souveraineté `nexus_agent.py:1057-1069` **vérifié actif** par l'agent 3 |
| **tourner avec abonnement OFF et cloud OFF** | opérateur | le moteur expose `/v1/messages`, **mesuré HTTP 200** ; usage agentique complet **non prouvé** |
| **interface = Claude Code** | opérateur | bascule par deux variables, mesurée ; bannière `Claude Max` = témoin |
| **un ou deux orchestrateurs LOCAUX remplaçant Opus** | opérateur | **7 modèles** portent `tools` + `thinking`, jusqu'à 262 144 de contexte |
| **système auto-distribué, modèles qui se coordonnent** | opérateur | `nexus_ruche` existe ; **20 ouvriers tiennent en 23,8 Go** sur 39,7 de budget |
| **contexte 1M** | opérateur | `nexus_context` **échoue à 900 s sans rien rendre** — seule promesse du contrat contredite par une mesure |
| **auto-évolutif, adaptatif à l'hôte** | opérateur | pool et verdicts **dérivés** ; **trois réglages moteur restent gravés** |
| **GPU futur** | opérateur | **déjà traité** — bascule RAM→VRAM automatique, réserve NVIDIA seulement |

### 13.5.1.1 SURVEILLANCE ET ADAPTATIVITÉ — ce qui manque, mesuré

Consignes : *« je rajouterais aussi un clock CPU GPU pour adaptatif »*, *« surveillance CPU GPU
RAM DISQUE »*, *« ADAPTATIF »*.

#### Ce qui est surveillé aujourd'hui

`scripts/nexus_charge.py` — sortie réelle mesurée :

```
RAM Libre: 23.41 Go / Modeles residents: 20.45 Go / Disponible pour inference: 43.86 Go / Totale: 61.62 Go
machine AU REPOS (modeles residents: 20.45 Go)
```

| ressource | surveillée ? |
| --- | --- |
| **RAM** | oui — libre, résidents, disponible pour l'inférence, totale |
| **CPU** | oui, mais **par processus**, en minutes de temps accumulé |
| **GPU** | **non** |
| **disque** | **non** — `nexus_capability` le lit une fois, rien ne le surveille |
| **horloges CPU/GPU** | **non** — `cpu_cores()` ne lit que le nombre de cœurs |

#### LE DÉFAUT D'ADAPTATIVITÉ, dans le code

```python
cpu_seuil_min = float(os.environ.get("NEXUS_CHARGE_SEUIL_MIN", 2))
ram_seuil_go  = float(os.environ.get("NEXUS_CHARGE_RAM_MIN", 30))
```

**30 Go de RAM libre exigés, en valeur ABSOLUE.** Sur cette machine de 61,6 Go c'est la moitié ;
sur un hôte de 16 Go, la condition ne peut jamais être satisfaite et **la plateforme se
déclarerait occupée en permanence**. Le seuil devrait être une **fraction du budget dérivé**,
pas un nombre.

Même défaut pour `SEUIL_MIN = 2` minutes de CPU : deux minutes de temps accumulé n'ont pas le
même sens sur 4 cœurs à 2 GHz et sur 24 threads à 5 GHz.

C'est la dette exacte que l'opérateur désigne : **la machine actuelle gravée dans un défaut**.

#### Les horloges : obtenables, mais TRAITRESSES — deux pièges mesurés

```
Win32_Processor.MaxClockSpeed      2000 MHz    <- frequence de BASE
   or le Ryzen AI 9 HX 370 monte a ~5,1 GHz en boost : l'ecart est d'un facteur 2,5
Win32_VideoController.CurrentRefreshRate   60  <- taux de RAFRAICHISSEMENT DE L'ECRAN,
   PAS l'horloge du GPU. Une implementation naive enregistrerait 60 comme horloge GPU.
Win32_Processor.LoadPercentage     (vide)      <- n'a rien rendu sur cette machine
```

**Trois valeurs disponibles, trois pièges.** Aucune ne doit être employée telle quelle :
`MaxClockSpeed` sous-estime d'un facteur 2,5 ; `CurrentRefreshRate` mesure autre chose ;
`LoadPercentage` est vide. Une horloge lue sans contre-épreuve est pire qu'une horloge absente.

#### Ce qu'un profil vraiment adaptatif devrait dériver

| grandeur | source honnête | pourquoi pas l'évidente |
| --- | --- | --- |
| **capacité de calcul** | un micro-banc réel — quelques centaines de jetons chronométrés | l'horloge annoncée ment (base contre boost) |
| **seuil RAM libre** | **fraction** du budget de `nexus_capability`, non 30 Go | un absolu exclut les petites machines |
| **seuil CPU** | fraction des cœurs × durée, non 2 minutes | 2 min n'ont pas le même sens selon la machine |
| **charge GPU** | `nvidia-smi` si NVIDIA ; **rien de fiable pour un iGPU AMD** | à dire plutôt qu'à inventer |
| **disque** | libre **et** débit d'écriture mesuré | un disque plein arrête l'ingestion silencieusement |
| **`OLLAMA_MAX_LOADED_MODELS`** | `budget_pool ÷ poids moyen des résidents` | aujourd'hui posé à 3 à la main |

> **La règle** : ce qui est annoncé par le système se vérifie ; ce qui ne se vérifie pas se
> mesure ; ce qui ne se mesure pas se déclare **INCONNU**. Les trois horloges ci-dessus tombent
> dans la première catégorie et **aucune ne survit à la vérification**.

### 13.5.2 Les trois verrous, dans l'ordre où ils se lèvent

**1. `OLLAMA_MAX_LOADED_MODELS = 3`** — interdit tout essaim. Se lève par une variable, et
devrait être **dérivé** de `budget_pool ÷ poids moyen`, non posé à la main.

**2. `OLLAMA_CONTEXT_LENGTH` non posé** — les modèles déclarent 262 144, le moteur applique son
défaut. Le contrat §13 et §54 exigent ≥ 64 k pour un client agentique.

**3. `nexus_context` perd tout en expirant** — le seul vrai travail des trois. Le remède est
lisible sur le disque : `resolve_dependencies(input_params, state)` et le chaînage
`$$STEP_N_OUTPUT$$`, dix implémentations dans `references/livres/code/`.

### 13.5.3 Les livres, par ce qu'ils débloquent

| livre | débloque | vérifié |
| --- | --- | --- |
| **`Release it!`** | disjoncteur qui **tabule** au lieu de réagir, timeout, Bulkhead — **3 rouges** | 3 extraits |
| **`AI Engineering`** (Huyen) | le capteur de qualité — **2 chapitres** ; et **« Model Merging », p. 347** | 3 extraits |
| **`Design Multi-Agent AI Systems`** ch. 4 et 8 | `LLMProvider(ABC)` + **`OllamaProvider` en code qui tourne** | code lu, 3 939 car. |
| **`Context Engineering for Multi-Agent Systems`** | `planner()`, `resolve_dependencies()`, `AgentRegistry`, **`json_mode=True`** | code lu |
| **`Site Reliability Engineering`** | dégradation en tiers, load shedding | 1 extrait |
| **`30 Agents Every AI Engineer`** | `CircuitBreaker` complet, deadletter, trois mémoires | code lu, l. 284-397 |
| **`Prompt Engineering for Generative AI`** | décodage contraint — l'échec répété **7 fois** ce soir | 3 extraits |
| **`ML Design Patterns`** | évaluation continue | 1 extrait |
| `Designing Data-Intensive Applications` | idempotence, ordre des messages — **bases de données** | 3 extraits |
| `Context Engine Reference Guide` | méthode du moteur de contexte — **pile cloud à rejeter** | 4 extraits |

**Et cinq thèmes sur vingt-six sont sans source** : tool shadowing, validation de dépendances,
TTL, test multi-agents, et les mécanismes propres au dépôt (`ratchet`, `orphan`, `checklist` —
**0 occurrence**). Ce sont ceux où il faudra inventer, et le savoir vaut mieux que de chercher.

### 13.5.4 La ressource décisive, et elle était sur le disque

`references/livres/code/symbols.jsonl` — **2 231 symboles avec leur implémentation complète**,
jamais consultés avant ce soir. Pour trois des sept problèmes principaux — disjoncteur,
planificateur, fournisseur Ollama — **il n'y a plus à concevoir, il y a à adapter un code lu**.

Seul obstacle matériel mesuré : `import ollama` → `ModuleNotFoundError`.

### 13.5.5 Ce qui interdit de déclarer quoi que ce soit terminé

- **Aucun VERT n'est acquis.** Cinq agents sur cinq refusent de se valider eux-mêmes.
- **Le troisième temps est structurellement bloqué** : `nexus_valide.py` ne peut pas tourner
  dans un worktree, faute de `.env` et `.nexus/` gitignorés.
- **Rien n'est fusionné.** Cinq worktrees attendent.
- **Le moteur était cassé depuis 16 h 08** — une partie des mesures de la soirée sur les
  modèles locaux est à rejouer.
- **Un zéro faux a été affiché à l'opérateur** par l'orchestrateur, et corrigé après coup.

---

## 13.6 REPÊCHAGE — les mesures du début de session, re-vérifiées et non recopiées

Les constats des §1 à §6 datent de quatre heures. Cinq agents ont travaillé depuis. **Les
reporter de mémoire serait exactement la faute que ce document dénonce ailleurs.** Ils ont donc
été rejoués, un par un.

| # | constat d'origine | re-mesuré | verdict |
| --- | --- | --- | --- |
| 1 | deux gardes sans hook | `nexus_garde_ecriture.py`, `nexus_garde_isolation.py` | **inchangé** |
| 2 | 46 règles `deny` inertes sur 240 | 46 | **inchangé** |
| 3 | `nexus_garde_ecriture.py` ne lit que l'ACL projet | ligne 48 : `os.path.join(ROOT, ".claude", "settings.json")` | **inchangé** |
| 4 | `nexus_doc` affirme un ancrage faux | annonce `python 3.13.2` — installé : **3.14.7** | **inchangé** |
| 5 | cinq épreuves de gardes en échec | exits `3, 1, 1, 1, 1` | **inchangé** |
| 6 | zéro faux sur les bundles | 5 réels, checklist affiche **0** | **inchangé** |
| 7 | `start.ps1` rend 1 sur succès | **non rejoué** — 2 min de conformité | **NON VÉRIFIÉ ce tour** |
| 8 | arbre principal intact | 7 écarts, HEAD `f364f40` | **inchangé** |

### La raison pour laquelle rien n'a bougé, et elle est structurante

**Aucune correction des cinq agents n'est dans l'arbre principal.** Elles vivent dans cinq
worktrees non fusionnés :

```
HEAD f364f40  —  identique au debut de session
7 ecarts : CHECKLIST_PROGRESS.md regenere, CLAUDE.md, references/node_docs/,
           trois scripts neufs, VAGUES_REPARATION.md
```

Les huit défauts re-mesurés sont donc **toujours actifs en production**. Ce qui a été réparé
l'a été ailleurs, et attend un arbitrage.

### Ce que ce repêchage établit comme méthode

Sept constats sur huit ont survécu à la re-mesure — mais **c'est le fait de les avoir rejoués
qui le prouve**, non leur âge ni la confiance qu'on leur accorde. Le huitième est classé
**NON VÉRIFIÉ** faute d'avoir été rejoué, plutôt que reconduit par défaut.

> Un constat vieux de quatre heures dans un dépôt où cinq agents travaillent n'est pas un fait :
> c'est une hypothèse dont la date est connue. La re-mesure coûte quelques secondes ; la
> reconduction tacite coûte une conclusion fausse.

---

## 13.7 QUARANTAINE — exigence de l'opérateur, et pourquoi la mesure la justifie

> *« on doit avoir les fichiers corrigés en quarantaine/isolement »*
> *« + ceux que l'on doit produire qui iront rejoindre le même dossier »*

### 13.7.1 L'état réel du travail des cinq agents — mesuré

| agent | travail | état |
| --- | --- | --- |
| `a697c9b3` | `cablage_reference.json`, `nexus_test.py` | **NON COMMITÉ** |
| `a9bae5bc` | 3 fichiers | commités (`be40d1f`) |
| `a925f543` | `epreuve_reprise_avant_repli.py`, `nexus_agent.py`, `nexus_test.py` | **NON COMMITÉ** |
| `a0bb278a` | 9 fichiers | commités (`23829cb`, `ea8be64`) |
| `a6d8fb73` | `nexus_conformite.py`, `nexus_socle.py`, `nexus_test.py` | **NON COMMITÉ** |

**Trois agents sur cinq ont laissé leur travail non commité** — huit fichiers qui n'existent
que dans l'arbre de travail d'un worktree. Ils survivent tant que le worktree n'est pas nettoyé,
et disparaissent avec lui.

**Précision qui corrige un chiffre** : un premier comptage donnait 32 à 34 fichiers modifiés par
agent. C'était faux — le `diff` contre `main` incluait le **retard de branche** de 12 commits.
Seul `a0bb278a` s'était avancé en `--ff-only`, d'où ses 9 propres. Les changements réels sont
de 2 à 9 fichiers, non de 32.

### 13.7.2 Ce que la quarantaine résout, et que le worktree ne résout pas

| | worktree | quarantaine |
| --- | --- | --- |
| isolation pendant le travail | **oui**, prouvée ce soir | — |
| survie après la fin de l'agent | **non** — lié au cycle de vie de l'agent | **oui** |
| inspection sans git | non — il faut connaître la branche | **oui**, un dossier |
| accueil des fichiers **à produire** | non prévu | **oui**, même dossier |
| trace de provenance | dans le rapport de l'agent, volatil | **avec le fichier** |

Le worktree est une **isolation d'exécution**. La quarantaine est une **isolation de
livraison**. Les deux sont nécessaires et ne se remplacent pas : ce soir, l'isolation
d'exécution a tenu, et la livraison n'existe pas.

### 13.7.3 Le dépôt a le nom, pas le mécanisme

```
rituels/_QUARANTAINE_BRICOLAGE/
    _temoin_bricolage.py      88 octets
```

Un fichier témoin, et **aucun script ne lit ce dossier**. Le nom existe depuis ce matin ; le
mécanisme, non.

Prior art de l'opérateur, dans `references/CODE_ENZO/OS_Pipeline_MT5_forge` :
`QUARANTINE_MANIFEST.yaml`, `cloud_darwin_quarantine_replay_v32.py`, son test, et un rapport
canari. **À lire comme source, pas à importer** — et c'est du code de l'opérateur, non des deux
dépôts voisins rejetés.

### 13.7.4 Ce que la quarantaine doit porter, pour que le temps 3 soit possible

Un fichier en quarantaine sans sa provenance est inauditable. Chaque entrée doit porter :

| élément | pourquoi |
| --- | --- |
| le fichier corrigé ou produit | l'artefact |
| **l'original** qu'il remplace | sans lui, pas de diff, pas de contre-épreuve |
| l'agent auteur, et son worktree | le temps 3 exige que le juge **ne soit pas l'auteur** |
| les trois épreuves et leur sortie | test, reverse-test, **forward-test** |
| la couleur **proposée**, jamais acquise | cinq agents sur cinq refusent le vert |
| ce que l'auteur a **classé NON VÉRIFIÉ** | ce qu'il n'a pas pu prouver |

### 13.7.5 La porte de sortie, et elle est bloquée

Un fichier ne quitte la quarantaine que par le **temps 3** du §0.7.1 : un tiers qui n'a écrit ni
le diagnostic ni le correctif vérifie que ce qui a été posé fait ce qu'il annonce.

**Cette porte est structurellement fermée aujourd'hui** : `nexus_valide.py` ne peut pas tourner
dans un worktree — il échoue sur `.env` et `.nexus/`, gitignorés donc absents (§2.3). Le juge
mécanique ne peut pas juger là où le travail se fait.

**Conséquence à énoncer clairement** : construire la quarantaine sans réparer sa porte de sortie
produirait un dossier qui se remplit et ne se vide jamais. Les deux vont ensemble.

---

## 13.8 ACCIDENT À INVESTIGUER — un worktree supprimé SOUS un agent au travail

Consigne de l'opérateur : *« défaut à investiguer, cela est un accident et on n'en veut pas.
Rajoute aux plans à interroger. »*

### 13.8.0 CORRECTION DE CETTE SECTION — l'incident n'est pas ce qui était écrit

Écrite d'abord comme *« un worktree supprimé sous un agent au travail »*. Les rendus suivants
des deux agents concernés établissent **deux anomalies distinctes**, et la première seule n'est
pas la bonne lecture.

**Anomalie 1 — répertoire de travail déclaré ≠ répertoire réel.** L'agent pair rapporte :

> *« j'ai opéré dans le worktree `agent-af1346a4d9a403253` — un chemin DIFFÉRENT de celui
> déclaré dans mon propre bloc d'environnement de départ (`agent-a3666d882218a276d`). Je ne
> l'ai remarqué qu'après la destruction-puis-recréation de mon worktree en cours de tâche,
> quand le garde Bash a explicitement nommé `agent-a3666d882218a276d` comme mon worktree
> assigné. »*

Vérifié : `agent-a3666d882218a276d` **existe** (répertoire et entrée git) ;
`agent-af1346a4d9a403253` est **absent des deux**.

**Anomalie 2 — la suppression sans trace**, décrite au §13.8.1, qui reste vraie telle que
mesurée.

L'agent parent les sépare explicitement : *« c'est une anomalie d'infrastructure DISTINCTE de
l'incident "worktree supprimé sans trace au reflog" ; ni l'une ni l'autre ne sont diagnosticables
d'ici »*.

**Ce que la correction change** : le worktree effacé n'était peut-être pas celui de l'agent —
c'en était un qu'il employait sans qu'il lui soit assigné. Sa suppression pourrait alors être un
nettoyage NORMAL, et le vrai défaut serait qu'un agent ait pu travailler ailleurs que dans son
arbre sans que rien ne l'arrête avant la fin.

**Ce que la correction NE change pas** : trois agents sur cinq laissent leur travail non
commité, et la collecte de quarantaine reste à rendre périodique. Les deux lectures aboutissent
à la même précaution.

**Classé NON DIAGNOSTIQUÉ.** Les questions du §13.8.4 restent posées, et il faut y ajouter :
*qu'est-ce qui assigne un worktree à un agent, et qu'est-ce qui vérifie qu'il y travaille ?*

### 13.8.1 Le fait, rapporté puis vérifié

L'agent `af1346a4d9a403253`, qui travaillait sur la reprise de `nexus_context`, écrit dans son
rendu : *« mon worktree a été supprimé sous moi en cours de tâche (aucune perte : le travail
vivait dans le scratchpad) »*.

Vérifié après coup :

```
repertoire .claude/worktrees/agent-af1346a4d9a403253   ABSENT
entree git worktree list                               ABSENTE
branche worktree-agent-af1346a4d9a403253               ABSENTE
git worktree prune --dry-run                           rien a elaguer
reflog                                                 aucune trace
```

**La suppression est TOTALE et COHÉRENTE** : répertoire, entrée git et branche, les trois
effacés ensemble. Ce n'est pas un nettoyage partiel ni une corruption — c'est un geste délibéré
de quelque chose. 38 branches pour 38 répertoires : l'état est sain, il manque juste un agent.

### 13.8.2 Pourquoi c'est grave, et pas seulement gênant

Le travail de cet agent a survécu **par accident** : il écrivait dans le scratchpad partagé,
qui n'est pas dans le worktree. S'il avait travaillé proprement — tout dans son worktree, comme
l'isolation le prescrit — **il aurait tout perdu**.

Et la mesure de la soirée rend le risque général : **trois agents sur cinq laissent leur travail
NON COMMITÉ** (§13.7.1). Huit fichiers, à cet instant, n'existent que dans des arbres de travail.

### 13.8.3 L'hypothèse à interroger, et elle est testable

Le harnais documente que les worktrees sont *« auto-nettoyés s'ils sont inchangés »*.

**Hypothèse** : le critère de « inchangé » serait l'absence de COMMIT, non l'absence de
modification. Un agent qui travaille sans commiter présenterait alors un worktree *« propre »*
au nettoyeur, et serait effacé avec tout son travail.

Si elle est vraie, elle explique l'accident **et** en promet d'autres : les trois agents non
commités de ce soir sont exactement dans ce cas.

### 13.8.4 Les questions à poser, dans l'ordre

1. **Qu'est-ce qui supprime ?** Le harnais à la fin d'un agent, une tâche planifiée, un autre
   agent, ou `git worktree prune` appelé par un outil du dépôt ? `grep -rn "worktree.*prune\|
   rmtree.*worktree"` sur `scripts/` et `tools/` est le premier geste.
2. **Sur quel critère ?** Absence de commit, absence de diff, âge, ou fin de l'agent ?
3. **La suppression attend-elle la fin de l'agent ?** Ici non — l'agent travaillait encore.
4. **Est-ce reproductible ?** Créer un worktree jetable, y écrire sans commiter, déclencher le
   nettoyage, observer. C'est la seule preuve qui vaille.
5. **Quelle protection ?** Un commit automatique en fin de tâche, un refus de nettoyer un arbre
   modifié, ou la quarantaine du §13.7 qui copie hors du worktree — les trois sont
   complémentaires, aucune n'est en place.

### 13.8.5 Ce que cela impose au collecteur de quarantaine

`nexus_quarantaine.py` (§13.7, rendu ce soir) collecte les fichiers **depuis les worktrees**.
Si un worktree peut disparaître pendant qu'un agent travaille, **la collecte doit être
périodique et non finale** : collecter à la fin, c'est collecter ce qui a survécu.

C'est un changement de conception, pas un réglage — et il n'est pas fait.

---

## 13.9 MESURES DE FIN DE VAGUE — à ne pas perdre

### 13.9.1 Routage, mesuré sur vérité terrain obtenue sans modèle

Tâche : lister les 18 fonctions de `nexus_disjoncteur.py`. Vérité comptée par l'AST.

| plan | durée | rappel | servi par |
| --- | --- | --- | --- |
| `llama3.2:1b` | 22 s | **0 %** | texte dégénéré |
| `llama3.2:3b` | 20 s | **0 %** | boucle de répétition |
| `qwen3:8b` | 127 s | **0 %** | **replié sur `glm-4.7-flash`** |
| `qwen3-coder:30b` | 36 s | 44 % | 8 fonctions sur 18 |
| `gpt-oss-120b-cloud` | **4 s** | **100 %** | les 18 |

**Défaut de conception révélé** : l'enregistrement du rendu conserve le modèle qui a **servi**
et **perd celui qui était demandé**. Toute mesure par modèle est donc fausse par construction.

### 13.9.2 L'essaim de 0,5 B — résolu, mesuré

```
qwen2.5:0.5b   poids 0,46 Go   cache a 32 768 : 0,41 Go   resident 0,87 Go
latence : froid 213 s (sous contention)   chaud 0,08 / 0,10 / 0,11 s

45 modeles -> 39,1 Go   dans le budget de 39,7
64 modeles -> 55,7 Go   au budget maximal de 56,2
```

**45 est le plafond exact du budget de pool.** Le cache double le modèle, il ne le multiplie pas
par huit — ma crainte inscrite au §7.1.3.4 était surestimée : à 65 536 le coût serait 1,28 Go
par modèle, soit **31 modèles au lieu de 45**, un tiers d'essaim et non sa totalité.

**Le seul obstacle réel est le chargement** : 213 s pour 0,46 Go sous contention.

**Et la quantification est le levier ignoré** : `smollm2:360m` pèse 0,73 Go en F16 quand
`qwen2.5:0.5b` pèse 0,40 Go en Q4_K_M — un modèle de 361 M plus gros qu'un de 494 M.
`llama3.2:1b` et `granite3.1-moe:1b` sont en Q8_0. Requantifier ce qui est installé rapporte
plus que télécharger plus petit. `smollm2:135m` existe au catalogue jusqu'en q2.

### 13.9.3 Failles des gardes et du hook — tableau consolidé

| mécanisme | faille | preuve |
| --- | --- | --- |
| `nexus_garde_isolation` | n'empêche pas un agent de travailler dans un worktree non assigné | nommé après coup, pas avant |
| garde d'isolation Bash | **contrôle de texte**, pas bac à sable | `git -C` refusé en direct, non intercepté depuis un sous-processus |
| `nexus_garde_ecriture` | 14 règles inter-volumes lèvent une exception avalée | zéro protection shell sur `.ssh` |
| ACL — 46 sur 240 | inertes depuis Claude Code 2.1.210 | `claude --debug` |
| ACL — 59 règles à motif | lues, non applicables | comparateur à égalité exacte ou `*` final |
| `controle_gardes_accordes` | aveugle à une garde non câblée | itère sur les hooks déclarés |
| hook `SessionStart` | **18 sujets affichés sur 631** | `nexus_reprise.py:258` |
| scratchpad | partagé entre worktrees isolés | ~30 fichiers d'autrui trouvés |

### 13.9.4 `nexus_context` — cycle à quatre parties, et ce qui reste ouvert

| | rôle |
| --- | --- |
| agent A | a produit le correctif |
| agent B | l'a appliqué et vérifié |
| agent C | a audité, et **a trouvé un défaut que ni A ni B n'avaient vu** |
| agent A | a produit le correctif complémentaire, **sans l'appliquer ni le juger** |

Défaut trouvé par C : quand **toutes** les fenêtres rendent `RIEN`, le fichier de points de
contrôle survit à un appel entièrement réussi. Prouvé par exécution.

**RESTE OUVERT** : le correctif complémentaire est écrit, vérifié quatre fois par son auteur,
**non appliqué et non audité**. Couleur proposée pour l'ensemble : **ORANGE**.

---

## 14. Ce qui n'est pas fait, et n'est pas promis

- **Aucun commit.** L'arbre porte 6 écarts : `CHECKLIST_PROGRESS.md` régénéré, `CLAUDE.md` non
  suivi, `references/node_docs/`, et trois scripts neufs.
- Les **10 violations** des trois scripts neufs ne sont pas corrigées.
- Les **4 livres à chemin trop long** ne sont pas récupérés.
- Le candidat `.nexus/settings_candidat.json` n'est pas appliqué.
- Aucun audit final global, **aucun troisième temps** sur la vague 1.
- « 40 fichiers » et « 98 outils » évoqués par l'opérateur : **aucune trace** dans `rituels/`,
  `docs/`, les contrats ni les worktrees. Classés **NON VÉRIFIÉ**. Le seul décompte voisin est
  `rituels/STATE.md:73` — 140 fichiers analysés, six classes de défauts.
- Le template `CODE_PREMIUM` des dépôts voisins a été **localisé mais non importé** :
  l'opérateur les rejette, et la copie a d'ailleurs été refusée par l'ACL. Seules les trois
  idées du cockpit §70.5 sont retenues — provenance, présence ≠ contenu, cliquet ≠ portail.

---

## 22. LE TROISIÈME TEMPS EST BLOQUÉ PAR LA MÉCANIQUE — cause mesurée

Mesuré le 2026-09-02, dans le worktree `agent-a9bae5bcacf5d3042`, sans pipe
(le premier essai lisait le code de sortie de `head`, jamais celui de Python) :

```
python scripts/nexus_valide.py --base HEAD~1
code de sortie : 1
=> NON CONFORME : 4 controle(s) bloquant(s).
```

Les quatre bloquants, et **aucun ne concerne le code réparé** :

| contrôle | motif | pourquoi en worktree |
| --- | --- | --- |
| configuration valide | 23 variables non définies | `.env` gitignoré, absent |
| relevé `latences.json` | « a existé puis disparu » | `.nexus/` gitignoré, absent |
| relevé `epreuves.json` | idem | idem |
| secrets présents | `.env` absent | idem |

### La cause exacte, lue dans le code réel

`scripts/nexus_conformite.py:791-803`. Le contrôle est bien raisonné : il
n'assimile pas l'absence à une panne. Il cherche un **témoin** pour distinguer
« jamais mesuré » de « mesuré puis effacé » :

```python
temoin = "nexus_pool: true" in f.read()   # dans litellm_config.yaml
if temoin:
    noter(..., BLOQUANT, "le relevé a existe puis disparu")
else:
    ignorer(..., "jamais mesure sur cette machine")
```

**Le témoin est suivi par git, la preuve ne l'est pas.** `litellm_config.yaml`
voyage dans chaque worktree avec son `nexus_pool: true` ; `.nexus/` ne voyage
jamais. Le témoin s'allume donc toujours, et la conclusion « a existé puis
disparu » est fausse partout où le raisonnement est juste sur l'arbre principal.

Ce n'est pas la classe « vide lu comme une panne » : c'est **un témoin et sa
preuve séparés par le `.gitignore`**.

### Ce que cela coûte, et pourquoi c'est bloquant

Dix agents ont rendu dix fiches. **Aucun n'a pu obtenir de verdict tiers**, et
les dix rubriques 8 sont vides — vérifié : ce qui s'y trouve n'est que le
gabarit à remplir, pas un auto-audit. La règle a tenu ; c'est l'outil qui
manque.

Tant que ce blocage tient, aucun fichier de quarantaine ne peut passer au VERT,
et la question de l'opérateur — *ne pas confondre un fichier produit SAIN
contre un contaminé* — reste sans instrument.

### Statut

**OUVERT.** Diagnostic posé par l'orchestrateur, correctif NON écrit ici
(LOI 1). À déléguer, avec sa contre-épreuve : le correctif doit rendre un
verdict en worktree ET continuer de bloquer sur l'arbre principal quand un
relevé a réellement disparu.

---

## 23. LE BANC TOURNE DÉGRADÉ EN CE MOMENT — mesuré, pas déduit

Trouvé le 2026-09-03 en **se servant** de la plateforme, pas en l'auditant.

### La chaîne, du compteur fabriqué à la substitution muette

**1. Le compteur est inventé.** `.nexus/circuit_journal.jsonl` relu : 25 lignes
`classe=permanent`, **toutes à `echecs: 3`**, sur 7 cibles distinctes. Un seul
appel réel par ligne. Le compteur est posé à la valeur du seuil, jamais compté.

**2. L'état vivant, `.nexus/circuit_state.json` :**

```
gpt-oss-120b-cloud     etat=open       echecs=3
glm-4.7-flash-local    etat=half_open  echecs=3
qwen3-8b-local         etat=open       echecs=3
gemma4-12b-local       etat=open       echecs=3
```

**3. Le prédicat réellement employé à l'appel** (`scripts/nexus_agent.py:1026`) :

```python
_c = [c for c in candidats if _dj.is_available(c)]
if _c:
    candidats = _c        # <- le modele demande disparait de la liste
```

Interrogé directement :

```
gpt-oss-120b-cloud   is_available = False
glm-4.7-flash-local  is_available = False
qwen3-coder-30b-local is_available = True
```

**4. L'effet, mesuré par un appel réel** — le forward-test, par un chemin
indépendant de l'état lu :

```
$ python scripts/nexus_agent.py --tache "..." --modele gpt-oss-120b-cloud --max-tokens 300
  demande : qwen3-coder-30b-local
  servi   : ollama_chat/qwen3-coder:30b  [local]
```

### Ce que la mesure ajoute au défaut déjà connu

Le défaut consigné était : *le résultat garde le modèle SERVANT et perd le
modèle DEMANDÉ*. La mesure montre pire — **le champ `demande` lui-même
enregistre le modèle retenu après filtrage**, pas celui que l'appelant a
demandé. Il ne reste donc, nulle part, aucune trace de l'intention.

Conséquences, dans cet ordre :

* toute mesure PAR MODÈLE faite via ce chemin est fausse par construction ;
* la substitution est un **repli silencieux**, que l'opérateur a explicitement
  rejeté ;
* les deux chevaux de trait du banc — le cloud `gpt-oss-120b-cloud` et le local
  `glm-4.7-flash-local`, défaut du serveur MCP — sont coupés **en ce moment**.

### La nuance qui empêche de crier au blocage

`if _c:` conserve la liste complète quand le filtre la vide. Un circuit
entièrement ouvert ne bloque donc rien : il dégrade. C'est pourquoi le défaut a
pu vivre sans jamais se voir — rien n'échoue, tout répond, et ce n'est pas ce
qui a été demandé.

### Pollution par les épreuves — piste, NON PROUVÉE

Trois cibles de l'état sont des leurres d'épreuve
(`modele-qui-n-existe-pas`, `modele-inexistant-cloud`, `cible-permanente`).
Un agent a rapporté qu'une épreuve bannissait deux modèles de production 300 s
par exécution, et l'a corrigé en worktree. **Le lien entre cette épreuve et
l'état ouvert d'aujourd'hui n'est PAS établi** : il reste à prouver.

### Statut

**OUVERT.** Diagnostic et mesures par l'orchestrateur ; correctif NON écrit ici
(LOI 1). Trois exigences pour le correctif :

1. compter les échecs réels au lieu de poser le seuil ;
2. conserver le modèle DEMANDÉ dans le résultat, distinct du modèle servi ;
3. **dire** qu'une substitution a eu lieu — un repli est subi, il n'est jamais muet.

Et une épreuve ne doit jamais écrire dans l'état de production.

---

## 24. LES LIVRES SONT LE PLANCHER, JAMAIS LE PLAFOND

Énoncé par l'opérateur le 2026-09-03 : *« ce qui est contenu dans les livres
c'est le plancher pas le plafond. »*

### Ce que la règle corrige

Le corpus a été introduit pour une raison exacte : **les livres empêchent
d'halluciner**. Un mécanisme conçu de mémoire invente ses seuils, ses états et
ses garanties ; un mécanisme confronté au chapitre qui porte son nom hérite de
décennies de cas limites déjà payés par d'autres.

Mais cette qualité se retourne en défaut dès qu'on s'y arrête. Une consigne
envoyée le jour même à un agent disait : *« pour ce sujet précis, il n'y a pas
à inventer, il y a à adapter un code lu »*. C'est exactement l'erreur — le
livre y devenait la borne supérieure du travail.

### La règle, dans les deux sens

| le livre est | le livre n'est pas |
| --- | --- |
| le **minimum** exigible : ne pas le lire, c'est concevoir de mémoire | la limite de ce qui peut être conçu |
| l'état de l'art **publié**, donc déjà daté | l'état de l'art de cette machine |
| écrit pour un cas **général** | écrit pour un moteur Ollama sur iGPU partagé, en 2026 |
| une preuve que le problème est **connu** | une preuve que la solution publiée est la meilleure ici |

### Ce que cela impose concrètement

1. **Lire le chapitre d'abord** — la règle antérieure ne bouge pas. On ne
   conçoit pas un disjoncteur sans avoir lu celui de `Release it!`.
2. **Puis mesurer ce que le livre ne pouvait pas savoir.** Le livre ignore
   qu'ici le repli `local → cloud` fait sortir des données ; qu'un modèle de
   0,46 Go met 213 s à charger sous contention ; que le témoin d'un relevé et
   le relevé lui-même sont séparés par un `.gitignore`.
3. **Dépasser, et dire en quoi.** Un correctif qui va au-delà du livre doit
   nommer ce qu'il ajoute et sur quelle mesure il l'appuie — sinon c'est de
   l'invention, et le corpus existait précisément pour l'empêcher.

### La tension à tenir, et elle est réelle

Le corpus interdit d'inventer ; cette règle exige d'aller plus loin que lui.
Les deux tiennent ensemble par une seule discipline : **on ne dépasse le livre
que sur une mesure, jamais sur une intuition.** Ce qui n'est ni dans le livre
ni dans une mesure se classe `NON VÉRIFIÉ`, et ne s'écrit pas.

---

## 25. LE COLLECTEUR DE QUARANTAINE A RENDU UN FAUX VERT — troisième temps appliqué

Le 2026-09-03. Premier emploi réel du troisième temps du §0.7.1 sur cette
vague : l'orchestrateur, n'ayant écrit ni le diagnostic ni le correctif, audite
la correction. **Elle est fausse.**

### Ce que le collecteur annonce

Manifeste produit sur la flotte réelle — 41 worktrees, 145 fichiers :

| population | worktrees | fichiers |
| --- | --- | --- |
| SANS PREUVE | 30 | 100 |
| PREUVE PARTIELLE | 9 | 39 |
| **PREUVE COMPLÈTE** | **2** | **6** |

Les deux « complètes » portent `audit du tiers (rubrique 8) : rempli`.

### Ce que dit le disque

Lu mot pour mot, hors de l'outil :

```
agent-a6d8fb73 :  | auditeur | |        <- toutes cellules vides
                  « rien n'a ete inscrit ici par l'auteur »
agent-a95a4421 :  (laisse vide)
```

**Les deux sont vides.** L'une le déclare en toutes lettres, et l'outil la lit
comme remplie.

### La contradiction interne, dans la même sortie

```
- rubriques remplies : 8/8
- trois epreuves -- test : VIDE, reverse : VIDE, forward : VIDE
- audit du tiers (rubrique 8) : rempli
```

Une fiche dont les trois épreuves sont VIDE ne peut pas être 8/8. Deux
détections se contredisent dans le même bloc.

### Pourquoi c'est la faute la plus grave possible ICI

L'outil existe pour une seule raison : **ne pas confondre un fichier produit
SAIN avec un contaminé**. Il vient de promouvoir en « preuve complète » les deux
seules fiches dont l'audit tiers est vide. Un faux vert est pire qu'une absence
de contrôle : il se lit comme une garantie.

### Cause probable — NON PROUVÉE, laissée au diagnostic délégué

`_slot_vide` paraît n'avoir été éprouvé que contre la forme `[ ]` employée par
la fiche de son propre auteur. Les dix fiches réelles expriment le vide en
prose (`(laisse vide)`) et en tableau markdown à cellules vides — jamais avec
ce marqueur. Une détection fondée sur la LONGUEUR d'un texte compte le mot
« vide » comme du contenu.

### Ce que le même agent a néanmoins bien fait

Son forward-test a trouvé un défaut réel que ses deux premières épreuves
laissaient passer : les dix fiches emploient `## N.` là où le gabarit écrit
`### N.`, si bien qu'un fichier de 21 Ko se lisait « presque vide » (0–1 sur 8).
Corrigé, les scores passent à 3–8 sur 8. **C'est exactement ce que le
forward-test est censé faire** — les deux premières épreuves valident
l'instrument, seule la troisième valide le résultat.

Il a aussi classé trois points `NON VÉRIFIÉ` au lieu de les combler en silence,
dont la détection des trois épreuves, qui lit `{false, false, false}` sur les
dix fiches réelles.

### Statut

**RENVOYÉ à son auteur** avec les deux formes réelles à intégrer en
contre-épreuve. Elles doivent être ROUGES sur le code actuel. Correctif NON
écrit par l'orchestrateur (LOI 1).

---

## 26. AUDIT DES DEUX CORRECTIONS — le troisième temps, exercé

Le 2026-09-03. Orchestrateur auditant deux correctifs dont il n'a écrit ni le
diagnostic ni le code.

### 26.1 Collecteur de quarantaine — le faux vert est CORRIGÉ

Renvoyé la veille pour faux vert (§25). L'auteur a **reproduit la trouvaille
avant de la croire**, puis nommé deux causes distinctes : aucun parcours des
tableaux markdown, et un repli jugeant le texte brut par sa LONGUEUR — si bien
que `(laisse vide)`, treize caractères, passait le seuil.

Vérifié par moi, sur les fichiers réels, cache bytecode supprimé :

```
agent-a95a4421 : rubriques 7/8, audit_tiers_rempli = False -> PREUVE_PARTIELLE
agent-a6d8fb73 : rubriques 7/8, audit_tiers_rempli = False -> PREUVE_PARTIELLE
```

`PREUVE_COMPLETE` tombe de 2 (faux) à **0**. Et `PREUVE_COMPLETE` ne peut plus
coexister avec des épreuves vides : la contradiction est rendue structurellement
impossible, pas seulement évitée.

**Mon propre instrument s'est trompé, et il faut le dire.** Ma contre-épreuve
donnait `(laisse vide) -> True`, ce qui accusait le correctif. J'avais inclus le
TITRE de la rubrique dans le texte passé à la fonction ; ses mots comptaient
comme réponse. Sur le corps seul — ce que le code reçoit réellement — le
résultat est `False`. **L'accusation venait de mon extrait, pas du code.**
Vérifié avant d'être publiée.

### 26.2 Verdict tiers en worktree — la cause était plus profonde que la mienne

Ma cause : le témoin (`nexus_pool: true`, suivi par git) et la preuve
(`.nexus/`, gitignorée) séparés par le `.gitignore`.

La sienne, trouvée sans voir la mienne : **`ROOT` se dérive de `__file__`**, donc
s'ancre sur la copie qui s'exécute — le worktree. L'état de la plateforme est
cherché là où il ne peut jamais être. Ma cause en est un symptôme : le témoin
voyage avec git, l'état non.

Correctif : `racine_plateforme()` résout la racine réelle par
`git rev-parse --git-common-dir`, partagé par tous les worktrees d'un dépôt.

**Ce que j'ai vérifié moi-même :**

| point | résultat |
| --- | --- |
| invariance sur l'arbre principal | racine résolue == `ROOT`, **identique** |
| une valeur de secret peut-elle sortir ? | non — seuls des NOMS de variables manquantes et un décompte |
| le verdict est-il obtenu ? | **code 0** : « Aucune régression détectée » |

**Ce que l'auteur n'a PAS nommé, et que l'audit ajoute :** un processus lancé
depuis un worktree ouvre désormais le **`.env` réel de la plateforme**. C'est
nécessaire — un contrôle qui ne lit pas la plateforme ne peut rien en dire —
mais c'est un élargissement délibéré de ce qu'un worktree touche, et il doit
être déclaré plutôt que subi. Aucune valeur n'en sort ; le fait qu'il soit lu
reste vrai.

### 26.3 Le verdict obtenu n'est PAS attribuable — trouvaille de l'audit

La sortie annonce `gpt-oss-120b-cloud`. Or ce modèle est mesuré coupé le même
jour : `is_available = False`, circuit ouvert sur un compteur fabriqué (§23).
Le jugement a donc été rendu par un modèle **substitué en silence**, et les
quatre lignes de sortie ne disent pas lequel.

> Un verdict dont on ignore l'auteur est une preuve faible — et la LOI 1 porte
> précisément sur QUI a jugé.

Le déblocage du troisième temps et la réparation du disjoncteur sont donc
**couplés** : le premier ne vaut pleinement qu'une fois le second posé.

### 26.4 Réserve sur MON indépendance — et elle est réelle

J'avais produit ma propre cause du défaut §26.2 avant de le déléguer. Je ne suis
donc pas un tiers pur sur ce sujet : j'en suis co-diagnosticien. Le §0.7.1 vise
exactement ce piège — la délégation qui donne l'apparence de l'indépendance.

Mon audit ci-dessus reste utile (il a mesuré, et il a trouvé deux points que
l'auteur n'avait pas nommés), mais **il ne clôt pas le troisième temps**. Une
couleur ne sera attribuée que par un tiers n'ayant ni diagnostiqué, ni corrigé,
ni — comme moi — proposé une cause concurrente.

Couleurs PROPOSÉES, jamais attribuées : §26.1 **JAUNE** (correctif prouvé, liste
d'idiomes finie par nature) — §26.2 **JAUNE** (mécanisme prouvé, mais lecture du
`.env` réel non déclarée et verdict non attribuable).

---

## 27. AUDIT DU CORRECTIF DISJONCTEUR — prouvé contre la passerelle vivante

Le 2026-09-03. L'auteur a déclaré n'avoir jamais appelé la passerelle réelle :
ses preuves sont par bouchon. C'est exactement ce que l'audit pouvait faire et
lui non. État réel **copié** dans le worktree (jamais l'original, §0.4), circuit
forcé ouvert dans cet état isolé, puis appel réel :

```
BASCULE : gpt-oss-120b-cloud -> qwen3-coder-30b-local apres :
          gpt-oss-120b-cloud : circuit open (echecs=4) | glm-4.7-flash-local : circuit open (echecs=4)
demande : gpt-oss-120b-cloud
servi   : ollama_chat/qwen3-coder:30b  [local]  http://host.docker.internal:11434
```

Les trois défauts sont réparés, et prouvés par un seul appel :

| défaut | preuve vivante |
| --- | --- |
| compteur fabriqué | **`echecs=4`** — impossible avant, le code figeait à 3 |
| modèle demandé perdu | `demande : gpt-oss-120b-cloud`, le modèle réellement demandé |
| substitution muette | la ligne `BASCULE` nomme les écartés ET la raison |

Souveraineté : la bascule va `cloud -> local`, jamais l'inverse. Conforme au
§108, et vérifié sur l'`api_base` réellement contacté.

### 27.1 Rectification de MA propre formulation au §23

J'ai écrit « le banc tourne dégradé EN CE MOMENT ». Mesuré une heure plus tard,
après chargement du même état : `gpt-oss-120b-cloud is_available = True`. Le
refroidissement s'était écoulé.

**La coupure est donc TRANSITOIRE, pas permanente** — elle se rejoue à chaque
déclenchement du compteur fabriqué. L'énoncé était vrai à l'instant de la
mesure et faux comme description d'un état durable. C'est la faute classique
d'une mesure figée présentée comme une propriété.

### 27.2 Défaut voisin, PRÉEXISTANT, ni introduit ni corrigé

Trouvé par le forward-test, pas par lecture. `nexus_agent.py:1135` : à la
troncature, l'échec est empilé dans `echecs` — et plus bas **chaque entrée de
`echecs` est rejouée dans `_dj.record_failure()`**. Une troncature bannit donc
le modèle.

Or le code imprime, à la ligne suivante :

> `troncature ... : reprise du plafond plutot que repli, un autre modele ne changerait rien`

**Il déclare le modèle hors de cause, puis lui facture un échec.** Une
troncature est un défaut de BUDGET, jamais du modèle.

Mesure vivante : `glm-4.7-flash-local` est passé de `half_open echecs=3` à
`circuit open (echecs=4)` après une troncature, pendant mon épreuve.

L'auteur connaissait ce rejeu — son commentaire explique qu'il garde `ecartes`
séparé de `echecs` pour ne pas faire échouer deux fois une cible jamais
appelée. Il ne l'a simplement pas étendu à la troncature.

### 27.3 Ce que l'auteur a classé NON VÉRIFIÉ, et qui reste vrai

* écriture concurrente sur `circuit_state.json` — pas d'écriture atomique
  (`io.open` + `json.dump`, sans `temp` + `os.replace`) ; défaut préexistant,
  non éprouvé ;
* preuve de non-fuite établie **par bouchon**, pas par refus réseau observé —
  mon appel réel la complète pour le sens `cloud -> local` ;
* deux de MES chiffres non reproduits par lui, dont les « 25 lignes » — parce
  que je lui avais fourni un extrait **coupé à 13 lignes**. Faute de dossier de
  ma part, pas de la sienne.

### 27.4 Couleur PROPOSÉE

**VERT sur les trois défauts visés**, prouvés contre la passerelle vivante.
**JAUNE sur l'entrée** tant que le §27.2 reste ouvert : le mécanisme réparé
reste alimenté par une source d'échecs illégitime.

Comme au §26.4, cette couleur est **proposée**. J'avais produit une analyse
partielle du même chemin au §23 : mon indépendance n'est pas entière.

---

## 28. LE TROISIÈME TEMPS A RENDU — trois JAUNE, trois FUSIONNABLE

Le 2026-09-03. Audit par un tiers n'ayant écrit **aucun** des trois
diagnostics, **aucun** des trois correctifs, **aucune** des épreuves — et à qui
les affirmations de l'orchestrateur ont été données comme *à vérifier*, jamais
comme acquises.

Consigne tenue : **rejouer, jamais croire.**

| correctif | couleur ATTRIBUÉE | verdict |
| --- | --- | --- |
| A — `racine_plateforme()` | **JAUNE** | FUSIONNABLE |
| B — disjoncteur | **JAUNE** | FUSIONNABLE |
| C — collecteur de quarantaine | **JAUNE** | FUSIONNABLE |

Aucun ROUGE. Aucun VERT pur. Aucune régression trouvée.

### Ce que le tiers a confirmé de mes affirmations

* **A** : le worktree lit bien le `.env` réel (`contenu = f.read()` sur le vrai
  fichier) — mais **aucune VALEUR ne quitte la portée** ; seuls des décomptes
  et des noms atteignent `noter()`. Descendu de VERT à JAUNE parce que cet
  élargissement de privilège n'est pas déclaré dans les effets de bord de la
  fiche.
* **B** : la troncature est bien enregistrée comme échec **permanent** et
  bannit un modèle sain, en contradiction avec le commentaire du code
  lui-même. Préexistant.
* **C** : sur la flotte vivante — **42 worktrees aujourd'hui**, elle grandit —
  `audit_tiers_rempli = False` sur les deux fiches citées, et
  `PREUVE_COMPLETE = 0`.

### Ce que le tiers a trouvé SEUL, et qui m'avait échappé

Sur **B** : quand **tous** les candidats sont déjà coupés, la comptabilité
`ecartes` ne s'engage jamais — le garde-fou `if _c:` conserve la liste
complète — et les candidats sont réessayés **pour de bon**. Pas de fuite de
souveraineté (le filtre de rang de plan tient), pas de message vide, mais cela
contredit la raison d'être même du correctif dans ce cas limite.

C'est exactement ce que le temps 3 existe pour trouver : un cas que ni l'auteur
ni le premier auditeur n'avait éprouvé.

### 28.1 Intégration sur l'arbre principal

Vérifié AVANT de toucher quoi que ce soit — les worktrees sont sur `a149320`,
**12 commits en retard** sur `main`. Copier depuis cette base pouvait écraser
douze commits.

```
commits touchant ces 5 fichiers depuis a149320 : 0, 0, 0, 0, 0
empreintes blob a149320 vs HEAD                : IDENTIQUE x5
```

Les trois lots touchent des fichiers **strictement disjoints**, entre eux et
avec le travail en cours sur `main`. Aucun conflit possible, et rien à perdre.

Intégré : `nexus_disjoncteur.py`, `nexus_agent.py`, `nexus_capability.py`,
`nexus_conformite.py`, `nexus_validate.py`, plus deux fichiers neufs —
`nexus_quarantaine.py` (995 lignes, jamais présent sur `main`) et
`rituels/GABARIT_QUARANTAINE.md`.

### 28.2 Ce qui reste OUVERT après cette vague

1. **La troncature bannit un modèle sain** — préexistant, confirmé deux fois.
2. **`ecartes` inopérant quand tout est coupé** — trouvé par le tiers.
3. **Écriture non atomique** de `circuit_state.json` — corruptible par accès
   concurrent ; préexistant, non éprouvé.
4. **Le `.env` réel lu depuis un worktree** — nécessaire, mais à déclarer.
5. **Sept autres fiches de quarantaine** attendent encore leur rubrique 8.

---

## 29. TROIS DÉFAUTS D'OUTILLAGE TROUVÉS EN S'EN SERVANT

Le 2026-09-03, en faisant corriger dix violations ruff par le banc gratuit.
Aucun de ces trois n'aurait été trouvé par une relecture : ils ne se voient
qu'en conduisant l'outil.

### 29.1 `nexus_appliquer.py` ne lit pas le marqueur `<<<FICHIER>>>`

Le mot n'apparaît **nulle part** dans le script. Il applique tous les blocs au
seul fichier passé en argument, donc un patch multi-fichiers vise à côté.

Il **échoue proprement** — la vérification d'unicité l'a rattrapé :
`REFUS : le bloc 6 doit etre unique et reel. Occurrences trouvees : 0`.
Défaut d'ergonomie, jamais de correction.

Conséquence pratique : un patch se demande **un fichier à la fois**. Ce n'est
pas un contournement, c'est le contrat réel de l'outil.

### 29.2 `nexus_appliquer.py:229` annonce un faux positif

```python
if stdout:
    print("[!] Violations detectees :\n%s" % stdout)
```

Ruff écrit `All checks passed!` sur `stdout` **même quand il ne trouve rien**.
Observé mot pour mot :

```
APPLIQUE : 2 bloc(s) dans scripts/nexus_extraire_livres.py
[!] Violations detectees :
All checks passed!
```

Le contrôle porte sur la **présence** d'une sortie au lieu de son **sens** —
la classe la plus fréquente de ce dépôt. Et le coût réel n'est pas le faux
positif : c'est que celui qui voit la bannière sur un cas propre apprend à
l'ignorer, et manquera la vraie.

### 29.3 Le banc perd le marqueur de PIED sur les rendus longs

`8 <<<AVANT>>>, 8 <<<APRES>>>, ZERO <<<FIN>>>`. Déjà consigné en mémoire,
reconfirmé. Un rendu long se demande découpé.

### 29.4 Résultat mesuré du lot

| fichier | avant | après |
| --- | --- | --- |
| `nexus_extraire_livres.py` | 1 | **0** |
| `nexus_indexer_node.py` | 2 | **0** |
| `nexus_decouper_livres.py` | 7 | **7** — OUVERT |

Les sept restantes tiennent dans un seul fichier, et une seule n'est pas
cosmétique : `SIM115`, deux `open()` sans gestionnaire de contexte qu'une
exception pendant `os.walk` laisserait ouverts.

### 29.5 DEUX ERREURS DE MESURE DE MA PART

**J'ai lu deux fois un résultat derrière un `tail` qui tronquait**, et accusé
le cache de ruff de mentir. Les deux passes donnaient le même nombre ; c'est ma
commande qui coupait la première ligne. La mémoire du dépôt porte exactement
cet avertissement — *« jamais derrière un tail »* — et je l'ai enfreint deux
fois dans la même heure.

**Et l'origine de la coupure du banc, c'était moi.** Le journal :

```
cible: gpt-oss-120b-cloud   classe: permanent  motif: reponse vide tronquee (demande 20 jetons)
cible: glm-4.7-flash-local  classe: permanent  motif: reponse vide tronquee (demande 40 jetons)
```

Mes propres appels d'épreuve à `--max-tokens 20` ont banni les deux chevaux de
trait en « panne permanente ». Un défaut de **budget** classé comme panne du
**modèle** — c'est-à-dire précisément le §27.2, dont je détenais la preuve
depuis le début de la vague sans l'avoir lue.

---

## 30. ÉTAT À LA FIN DE LA VAGUE — ce qui est clos, ce qui ne l'est pas

### Clos, avec preuve

| | preuve |
| --- | --- |
| trois correctifs audités par un TIERS | 3 JAUNE, 3 FUSIONNABLE, aucune régression |
| intégrés sur `main` | conformité code 0, 143 modules, relevés 71 et 44 |
| substitution silencieuse du banc | `BASCULE` nomme les écartés et leur raison |
| compteur d'échecs fabriqué | `echecs=4` — impossible sous l'ancien code |
| modèle demandé perdu | `demande : gpt-oss-120b-cloud`, contre la passerelle réelle |
| verdict tiers en worktree | code 0 là où quatre bloquants refusaient |
| faux vert du collecteur | `PREUVE_COMPLETE` de 2 (faux) à 0 sur 42 worktrees |
| 7 violations ruff | 7 → 0, empreinte différentielle IDENTIQUE |
| corpus de livres | 226 livres, 119 977 fragments, seek 50/50 |

### Le rituel de fin de tour dit encore trois manques — et il a raison

**1. `CLAUDE.md` à la racine, non commité.** Fichier de **0 octet**, antérieur à
cette session. Sans effet : le contrat chargé est `.claude/CLAUDE.md`. Laissé
en l'état — ce n'est pas mon fichier et l'opérateur est absent. À trancher en
une seconde à son retour.

**2. Câblage : `nexus_decouper_livres.py` est `preuve_seule`.** Seul un document
le référence ; aucun appelant en production. **Celui-là est le mien.** Le
§0.2.1 est explicite : *un script que personne n'appelle n'est pas un
mécanisme, c'est un fichier.* Les trois outils de corpus demandent un vrai
point d'entrée — une commande de rafraîchissement du corpus — et non un
raccourci posé à la hâte.

**3. Outillage : `RET505 0 -> 1` et les alertes PowerShell.** Le `RET505` est
dans `scripts/nexus_filet.py:91`, fichier jamais touché cette nuit et qui porte
**aussi** l'orphelin de câblage. Ni diagnostiqué ni corrigé ici : il revient à
un tiers.

### Ce qui reste ouvert au-delà du rituel

* une **troncature** bannit un modèle sain — confirmé deux fois, préexistant ;
* `ecartes` inopérant quand **tous** les candidats sont coupés — trouvé par le
  tiers ;
* **écriture non atomique** de `circuit_state.json` ;
* le **`.env` réel** lu depuis un worktree, à déclarer ;
* **sept fiches** de quarantaine attendent encore leur rubrique 8 ;
* `nexus_appliquer.py` : la fausse bannière, et `<<<FICHIER>>>` jamais lu ;
* les scripts de corpus ont un **effet de bord à l'import** (§0.5).

### La leçon de la nuit, et elle est mesurée

Sur les défauts trouvés cette nuit, **aucun ne venait d'une relecture**. Tous
sont venus de l'usage : un appel réel contre la passerelle, un patch qu'on
essaie de poser, une contre-épreuve qu'on construit mal. Et trois gardes ont
arrêté **mes** fautes avant qu'elles n'écrivent — dont une spécification qui
aurait produit un fichier syntaxiquement invalide.

Le corollaire tient en une phrase : **une garde qui refuse proprement vaut plus
qu'un audit qui lit bien.**

---

## 31. L'OUTIL DE RÉCOLTE EXISTAIT, ET SON ORPHELINAGE L'A RENDU INVISIBLE

Trouvé le 2026-09-03, en cherchant pourquoi le cliquet de câblage restait rouge.

### Ce que `scripts/nexus_filet.py` fait

Il récolte le travail des agents depuis leurs worktrees et l'applique à l'arbre
principal. Ses garde-fous sont écrits après un incident réel :

* **dry-run par défaut** ; l'application exige `--appliquer` ;
* **refus de tout diff supprimant un fichier suivi**, sauf `--avec-suppressions`
  — *« un agent a supprimé `docker-compose.yml` dans son worktree ; un
  `git apply` aveugle aurait emporté le fichier du dépôt réel »* ;
* `git apply --check` **avant** toute écriture ;
* il n'affiche que des comptes et des noms, **jamais le contenu d'un diff**.

### Le coût exact de son orphelinage

**Cette nuit, j'ai fait son travail à la main.** J'ai copié des fichiers depuis
trois worktrees, sans aucun de ces garde-fous, parce que je ne savais pas qu'il
existait. Il n'était appelé par rien, donc rien ne me l'a montré.

C'est la démonstration littérale du §0.2.1 : *un script que personne n'appelle
n'est pas un mécanisme, c'est un fichier.* Le contrat §0 liste d'ailleurs « la
récolte automatique des worktrees » comme encore ouverte — alors que l'outil
était là.

### Le défaut, mesuré en s'en servant

```
$ python scripts/nexus_filet.py
code de sortie : 1
UnicodeDecodeError: 'charmap' codec can't decode byte 0x9d in position 2142
UnicodeDecodeError: 'charmap' codec can't decode byte 0x90 in position 7297
```

Deux fils de lecture meurent : la sortie de `git diff` est lue avec le `cp1252`
par défaut de Windows, dans un dépôt **écrit en français**. L'outil rend malgré
tout son tableau — et **on ignore ce qu'il a perdu en route**. Un outil de
récolte qui perd une entrée en silence est le pire défaut possible pour ce
qu'il fait.

### Ce que le dry-run révèle de la flotte — 43 worktrees

| état | nombre |
| --- | --- |
| vide (aucun diff sur fichier suivi) | 17 |
| conflit (base trop ancienne) | 20 |
| déjà appliqué | 4 |
| **récoltable proprement** | **3** |

Les trois récoltables : `a697c9b3` (30 lignes), `a6d8fb73` (405),
`a9bae5bc` (19).

**Ils ne sont PAS récoltés.** Aucun n'a de rubrique 8 remplie, et la discipline
tenue toute la nuit ne se relâche pas parce qu'un outil affiche « ok ».

Les 20 conflits sont un fait structurel, pas vingt défauts : les worktrees ont
été créés sur `a149320`, **12 commits en retard**, et leurs patches ne
s'appliquent plus. Le filet vérifie et refuse — ce qui est exactement son
travail.

Il confirme aussi mon intégration de cette nuit :
`agent-a11923e0 : 94 lignes - deja applique`.

### Statut

**DÉLÉGUÉ.** Diagnostic et correctif confiés à un tiers, avec deux exigences :
que la lecture ne meure plus, et que toute perte se **dise** — message nommant
le worktree, et code de sortie qui la reflète. Le `RET505:91` et la question du
câblage sont dans le même mandat, la décision restant à l'orchestrateur.

### 31.1 Le filet ignore le travail COMMITÉ — et l'incitation en est inversée

Mesuré le 2026-09-03, en croisant son tableau avec l'état git réel.

`scripts/nexus_filet.py:41` :

```python
cmd = ['git', '-C', str(wt), 'diff', '--', '.'] + excl_args
```

Le diff des modifications **non indexées**, rien d'autre. Ni l'index
(`--cached`), ni les commits (`main..HEAD`).

| | |
| --- | --- |
| worktrees dits « vide » par le filet | 15 |
| parmi eux, portant du travail COMMITÉ | **2** |
| `agent-a0bb278a` | 2 commits propres, 25 fichiers |
| `agent-a96910bc` | 1 commit propre, 46 fichiers |
| **total invisible** | **3 commits, 71 fichiers** |

**Deux raisons pour lesquelles c'est grave, et la seconde est la pire :**

1. **Le silence.** Le filet affiche `vide` — mot pour mot ce qu'il affiche pour
   un worktree réellement sans travail. Rien ne distingue les deux cas.
2. **L'incitation est inversée.** Un agent qui **commite** son travail — le
   comportement discipliné, celui que le cockpit reproche justement aux autres
   de ne pas avoir — devient invisible à la récolte. **L'outil récompense le
   plus négligent.**

### 31.2 Une mesure que j'ai failli publier fausse

Mon premier comptage donnait « 4 worktrees, 14 commits, 44 fichiers ». Il
mesurait contre `a149320` au lieu de `main` : les commits de `main` y entraient
aussi, puisque `a149320` est douze commits en arrière.

Contre `main`, qui isole le travail propre à chaque worktree : **2 worktrees,
3 commits, 71 fichiers.** Deux des quatre ne portaient aucun travail propre.

Corrigé avant publication, et inscrit ici plutôt qu'effacé : **le choix de la
base change le résultat d'un facteur trois.**

Transmis à l'agent en vol comme une affirmation à rejouer, jamais comme un
acquis, avec les commandes exactes et le piège de la base nommé.

### 31.3 J'AI TRANSMIS UNE COMMANDE FAUSSE, ET ELLE A ÉTÉ REPRISE

Le 2026-09-03, trouvé en auditant la correction du filet.

Pour un `log`, deux points signifient « les commits propres à HEAD ». Pour un
`diff`, **deux points signifient tout autre chose** : la différence entre les
deux commits, dans les deux sens — donc y compris les fichiers où c'est `main`
qui a avancé.

```
git log  --oneline   main..HEAD     <- juste
git diff --name-only main..HEAD     <- FAUX pour « qu'a contribue ce worktree »
git diff --name-only main...HEAD    <- juste : part de la base commune
```

Mesure des deux formes, côte à côte :

| worktree | commits | `diff ..` | `diff ...` |
| --- | --- | --- | --- |
| `a084add6` | 0 | 46 | **0** |
| `a0b2638a` | 0 | 75 | **0** |
| `a0bb278a` | 2 | 25 | **9** |
| `a3a373ce` | 0 | 90 | **0** |
| `a96910bc` | 1 | 46 | **1** |

Les worktrees à zéro commit ne contribuent **rien** : les 46, 75 et 90 étaient
entièrement la dérive de `main`, douze commits en avance sur ces bases.

**Mon chiffre publié au §31.1 — « 3 commits, 71 fichiers » — vaut en réalité
3 commits, 10 fichiers.** Facteur sept.

Et il n'est pas resté chez moi : je l'ai transmis à l'agent avec la commande,
il l'a inscrit **dans la docstring de sa correction**. Une docstring qui porte
une mesure fausse est pire qu'une sans mesure : elle sera recopiée.

> **Le chiffre d'un donneur d'ordre se rejoue comme le reste.** C'est
> exactement ce que je demandais aux agents de faire avec mes affirmations, et
> celui-ci a eu tort de me croire.

### 31.4 Ce qui est PROUVÉ réparé, et ce qui ne l'est pas

Piloté par import contre la flotte réelle, cache bytecode neutralisé :

```
worktrees vus         : 43
diffs lus sans mourir : 43        (avant : 2 fils morts)
erreurs de decodage   : 0
```

**L'encodage est réparé.** L'agent a en outre nommé deux worktrees perdus que
je n'avais pas vus — `a13026bc` (52 lignes) et `aec47b54` (311 lignes) — et
trouvé par sa propre reverse-test un **troisième défaut** : le refus de
suppression rendait **code 0**. Un refus affiché qui ne bloquait rien, motif
que le §0.1.4.1 nomme explicitement.

**Non vérifié par moi** : ce troisième défaut, faute de pouvoir lancer l'outil
depuis un worktree.

### 31.5 L'outil est intestable depuis un worktree — trouvaille de l'audit

```python
RACINE = Path(__file__).resolve().parent.parent
```

Aucune surcharge. Lancé depuis le worktree de son auteur, il affiche
`Total worktrees: 0` et se tait — un zéro qui ressemble à un succès. J'ai dû
importer le module et appeler ses fonctions avec la racine réelle pour
l'éprouver.

Le §0.5 est explicite : *une racine de travail explicite (`--racine`)
l'emporte ; l'appelant décide où il travaille, pas l'outil.* C'est le même
défaut que celui déjà corrigé dans `nexus_conformite.py` cette nuit — la racine
dérivée de `__file__` sans échappatoire.

### 31.6 AUDIT DE LA CORRECTION DU FILET — ce qui est prouvé, et par qui

Rejoué le 2026-09-03 par l'orchestrateur, contre la flotte réelle, avec la
`--racine` explicite que l'auteur a ajoutée après l'audit.

| exigence | résultat |
| --- | --- |
| plus aucun fil de lecture ne meurt | **43 worktrees, 43 diffs lus, 0 mort** (avant : 2) |
| les worktrees perdus réapparaissent | `a13026bc` (52 lignes) revient au tableau |
| comptes des commits non récoltés | `a0bb278a` → **9** fichiers (25 avant), `a96910bc` → **1** (46 avant) |
| les faux positifs disparaissent | `a084add6`, `a0b2638a`, `a3a373ce` redeviennent de simples `vide` |
| l'outil dit sa propre provenance | la sortie porte « 9 fichier(s) touchés, `main...HEAD` » |

**Reverse-test, fabriqué et lancé par l'audit** — un dépôt jetable dont le diff
non indexé supprime un fichier suivi :

```
CODE DE SORTIE : 1
agent-atest…: 7 lignes - refuse suppression [fichier_suivi.txt]
              (repasser avec --avec-suppressions pour autoriser)
empreinte de la racine AVANT : 400c1dd5414c551a
empreinte de la racine APRES : 400c1dd5414c551a
```

Les trois exigences du §0.1.4.1 sont tenues : **code non nul**, **message
nommant la voie**, **aucun effet de bord**.

**Contre-épreuve sur le code d'AVANT, lue dans le fichier réel :**

```python
sys.exit(1 if conflits > 0 else 0)                    # ligne 181
print(f'{name}: {lignes} lignes - refuse suppression [{suppr_str}]')   # ligne 139
```

`refuses` était compté (l. 137), affiché (l. 175), et **n'entrait pas dans le
code de sortie**. Un lancement dont le seul effet était de refuser une
suppression rendait **0**. Et le message ne nommait aucune voie de passage.
Deux des trois exigences manquaient — motif que le §0.1.4.1 nomme mot pour
mot : *un refus qui affichait `deny` et sortait 0 ne bloquait rien.*

### 31.7 Ce que l'auteur a écrit en rubrique 6, et qui vaut doctrine

> *« matching a source proves fidelity of copying, not validity of method »*

Il avait vérifié que ses chiffres correspondaient à mon brief. Ils
correspondaient — parce que nous employions la **même commande fausse**.
Concorder avec sa source prouve la fidélité de la copie, jamais la validité de
la méthode.

### 31.8 Où en est mon indépendance sur cette pièce

| défaut | l'ai-je diagnostiqué ? | puis-je l'auditer ? |
| --- | --- | --- |
| encodage `cp1252` | non — j'ai donné le symptôme seul | **oui** |
| refus rendant code 0 | non — trouvé par sa reverse-test | **oui** |
| travail commité invisible | **oui, et avec une commande fausse** | non |

Les deux premiers sont audités proprement. Le troisième ne l'est pas : j'en
suis le diagnosticien, et de surcroît la source de l'erreur. Il faut un tiers.

**Rien n'est intégré.** La rubrique 8 reste vide, et huit fiches attendent
désormais le même tiers.

### 31.9 LE FILET PROPOSAIT DE REBASER LE CLIQUET EN SILENCE

Trouvé le 2026-09-03 en se servant du filet réparé pour préparer une récolte —
donc par l'usage, encore, et non par lecture.

Le dry-run annonce deux worktrees « ok » :

```
agent-a9bae5bcacf5d3042: 19 lignes - ok
agent-a697c9b31ea2b75e4: 30 lignes - ok
```

Ce que ces diffs contiennent réellement :

| worktree | contenu du diff |
| --- | --- |
| `a9bae5bc` | `rituels/cablage_reference.json` **et rien d'autre** — horodatage porté à `2026-09-03T04:57:26`, `nexus_epreuve_vide.py` retiré de `preuve_seule` |
| `a697c9b3` | le même fichier (horodaté `01:41:37`) **plus** 2 vraies lignes dans `scripts/nexus_test.py` |

`rituels/cablage_reference.json` est **la ligne de base du cliquet de câblage**.
Elle est réécrite en effet de bord par toute passe de validation lancée dans un
worktree : les horodatages sont ceux de cette nuit, pas ceux d'un travail
d'agent.

**Appliquer ces diffs rebaserait le cliquet en silence** — précisément le geste
que `nexus_cablage.py` exige d'assumer explicitement (*« si la dégradation est
voulue, l'assumer explicitement par `--rebaseline` »*), accompli ici par
accident, sous couvert de récolte.

Et pour `a9bae5bc`, **l'artefact est tout ce qui est récoltable**. L'outil dit
« ok, 19 lignes » pour une opération dont le seul effet serait d'aveugler un
contrôle. Son vrai correctif est dans son commit — que `commits_non_vus`
signale désormais.

**Le remède est dans le code de l'outil lui-même** : `--exclure` a déjà pour
défaut `scripts/nexus_doc.py`, et sa docstring dit pourquoi — *« des copies
posées par l'orchestrateur et non du travail d'agent »*.
`rituels/cablage_reference.json` est rigoureusement la même catégorie : un
fichier **généré**.

Deux exigences transmises, la seconde étant la même que pour les trois autres
défauts : un fichier généré ne doit pas entrer dans une récolte par défaut, et
un diff **vide après exclusion** ne doit pas être annoncé « ok » — dire qu'il
ne restait qu'un artefact est une information, « ok » est un mensonge.

Contre-épreuve exigée sur ces deux worktrees réels, dont le cas difficile :
`a697c9b3` doit **rester récoltable pour ses 2 lignes de `nexus_test.py`**. Une
exclusion trop large qui ferait disparaître du vrai travail serait pire que le
défaut.

### 31.10 Conséquence pour la vague : la liste des récoltables était fausse

Le §31 annonçait « 3 récoltables proprement ». Après examen du contenu :

| worktree | verdict réel |
| --- | --- |
| `a6d8fb73` | 405 lignes de vrai travail |
| `a697c9b3` | **2 lignes** de vrai travail, le reste est artefact |
| `a9bae5bc` | **rien** — artefact seul ; son travail est dans un commit |

« Récoltable » ne veut pas dire « porteur de travail ». C'est une leçon sur
l'outil autant que sur la vague : il mesure l'applicabilité d'un patch, jamais
sa valeur.

### 31.11 Le quatrième correctif, vérifié — et un cinquième cas trouvé par l'auteur

Rejoué par l'audit, avec `--racine`, contre la flotte réelle :

```
a50cbf7c : vide (1 fichier genere ecarte : rituels/CHECKLIST_PROGRESS.md)
a697c9b3 : 13 lignes - ok
a9bae5bc : vide en modifications non indexees (1 fichier genere ecarte),
           MAIS 1 commit(s) non recoltes (3 fichiers, main...HEAD)
```

**Le cas difficile passe.** Vérifié par un chemin indépendant — un `git diff`
avec les mêmes exclusions en `:(exclude)`, sans employer le code de l'outil —
les 13 lignes de `a697c9b3` sont exactement ses deux vraies lignes :

```python
+    if args.only in (None, "cles"):
+        jouer_epreuve_python("epreuve_cles_only.py", "cles atteignables par --only")
```

Une exclusion trop large aurait fait disparaître ce travail. Elle ne l'a pas
fait.

**Cinquième cas, trouvé par l'auteur et non par moi** : `a50cbf7c`, que le
filet annonçait `50 lignes - deja applique`, est à 100 % un
`rituels/CHECKLIST_PROGRESS.md` — un rapport dont l'en-tête porte littéralement
`Generated:` — avec zéro commit d'avance. **Un worktree vide présenté comme du
travail intégré.**

Il a cherché les autres fichiers générés sur les 43 worktrees plutôt que de
supposer, en a confirmé deux de plus par lecture de leur script écrivain
(`outillage_reference.json`, `orphelines_reference.json`), et a **refusé
d'exclure** `PROGRESS.md` et `BOUSSOLE.md` faute d'avoir pu confirmer leur
chemin d'écriture. Exclure par ressemblance aurait été une supposition ; il l'a
classé ouvert.

### 31.12 CINQ DÉFAUTS SUR UN FICHIER, AUCUN TROUVÉ PAR LES ÉPREUVES DE SON AUTEUR

Le constat est de l'auteur lui-même, inscrit dans sa propre rubrique 5 : les
défauts trouvés sur ce fichier viennent tous de l'audit externe et de l'usage
réel, **jamais de ses trois épreuves**.

| # | défaut | trouvé par |
| --- | --- | --- |
| 1 | encodage `cp1252`, deux fils morts | l'usage (orchestrateur), symptôme seul |
| 2 | travail commité invisible | l'audit (orchestrateur) |
| 3 | refus rendant code 0 | **sa propre reverse-test** |
| 4 | rebasement silencieux du cliquet | l'audit (orchestrateur) |
| 5 | worktree vide annoncé « déjà appliqué » | l'auteur, en cherchant sur la flotte |

Trois sur cinq sont venus de l'extérieur. Deux de lui — dont un par sa
reverse-test, qui est exactement ce à quoi elle sert.

**Ce que cela dit des épreuves, et ce que cela n'en dit pas.** Ses trois
épreuves n'étaient pas inutiles : elles ont prouvé que ce qui était réparé
l'était, et la reverse-test a trouvé le défaut 3 toute seule. Mais une épreuve
valide **ce que son auteur a pensé à éprouver** ; elle ne découvre pas ce qu'il
n'a pas imaginé. C'est l'usage qui le fait — et c'est la raison d'être du
troisième temps.

Il l'écrit lui-même comme une réserve **contre son propre VERT**, ce qui est la
bonne façon de s'en servir.
