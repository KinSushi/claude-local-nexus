# CHECKLIST — LIVRE VS CODE

> Mission permanente de l'operateur : *« audit complet de tout CODE VS LIVRE, non negociable »*.
> Une ligne par prescription du livre. Etat mesure, jamais suppose.
>
> **Source** : *Design Multi-Agent AI Systems Using MCP and A2A*, ch. 4 et 10 — chapitres lus par
> `seek`, **26 821 octets, aucun modele, aucun jeton**.

---

## 1. Les six garde-fous de coordination — ch. 10

| # | prescription du livre | etat | ou / preuve |
| --- | --- | --- | --- |
| 1 | **Timeout enforcement** — *fail gracefully rather than hanging* | 🟡 partiel | `verrou(attente_s=)` borne · mais `nexus_conformite` a ete TUE par un delai calibre sur un chiffre perime |
| 2 | **Circuit breakers** — *stop calling an agent that keeps failing* | 🟡 **PARTIEL** | **RETROGRADE le 2026-09-02 : le vert etait FAUX.** `nexus_agent:1023` importait `Disjoncteur`, nom qui N EXISTE PAS (la classe est `CircuitBreaker`) ; l `except Exception: pass` avalait l ImportError, donc le filtrage n avait JAMAIS eu lieu. Corrige et **prouve par effet** : les 5 candidats apparaissent desormais dans `nexus_disjoncteur.py --etat`, ce qui n etait pas le cas avant. Reste JAUNE car `record_failure` n est pas atteint quand TOUS les candidats echouent — mesure : journal a 694 octets avant ET apres un echec total |
| 3 | **Idempotency** — marquer les operations idempotentes | 🟡 **PARTIEL, et le vert reste interdit** | `nexus_appliquer.py:121-123` refuse un rejeu du meme patch — **prouve par execution le 2026-09-02** : 1er appel `APPLIQUE : 1 bloc(s)`, 2e appel `REFUS ... Occurrences trouvees : 0`, exit 1, **fichier inchange**. Mais c'est un EFFET DE BORD de la verification d'ancre unique, pas un marquage idempotent/non-idempotent concu. Le livre demande de **marquer** les operations ; rien ne les marque. `nexus_vitrine`, `nexus_sauvegarde` et `nexus_valide` n'ont aucune detection de doublon. Le tableau disait « absent » : c'etait mesurablement inexact |
| 4 | **State validation** — invariants verifies en tache de fond | 🟡 partiel | `nexus_conformite` · rien ne verifie les invariants de VERROU |
| 5 | **Dependency validation** au deploiement | 🔴 absent | — |
| 6 | **Coordination testing** — *deux agents sur la meme ressource* | 🟡 **PARTIEL, promu le 2026-09-02** | **1 cas sur 4 du livre** couvert et PROUVE PAR EFFET, re-verifie ici : `epreuve_verrou_banc.py` rend 3/3 (arme, LOCAL refuse code 75, CLOUD non bloque), cable sans condition dans `nexus_test.py:1405`. Les **trois autres cas du livre** — agent lent ou muet, donnees malformees, messages hors d'ordre — restent 🔴 : aucune epreuve trouvee. Le livre exige les quatre, donc le vert reste interdit |

## 2. Retry et disjoncteur — ch. 10, sept parametres

| prescription | etat | preuve |
| --- | --- | --- |
| **classer transitoire vs permanent** | 🟢 **MECANISE** | `echec_transitoire()` dans `nexus_disjoncteur` — patron `_is_retryable` du livre · 9 cas eprouves · un echec PERMANENT ouvre le circuit IMMEDIATEMENT |
| **backoff exponentiel** 100→200→400→800 ms | 🟢 **CABLE** | `_retry_delay()` appele dans `nexus_agent` entre deux tentatives · valeurs eprouvees 0.1/0.2/0.4/0.8/1.6, plafond 30 s · **aucun delai avant le premier candidat**, verifie : 1 reussie, 0 tronquee |
| **jitter** contre le *thundering herd* | 🟢 **CABLE** | tirage uniforme prouve — deux appels identiques rendent 1.5052 et 1.0678 · meme fonction, desormais appelee |
| **plafond d'essais** (5) | 🟡 **CONSTANTE DECLAREE, NON EMPLOYEE** | `MAX_RETRIES = 5` — la valeur du livre, mais **aucun code ne la lit** |
| **journal du POURQUOI de chaque echec** | 🟡 **ECRIT ET EPROUVE, NOURRI A MOITIE** | `_journal()` ecrit `.nexus/circuit_journal.jsonl` : horodatage, cible, motif, classe, compteur, etat. **Preuve de fonctionnement** : `epreuve_journal_disjoncteur.py` rend 3/3 classes, exit 0. **Preuve de DETECTION** : rejouee sur la version d avant correctif, elle rend exit 1 en nommant `cible-permanente`. **Cablee** : `nexus_test.py:1370`. Le defaut trouve par la mesure et non par la lecture : le chemin PERMANENT sortait par `return` avant le journal, la classe la plus importante etait perdue en silence. **Reste JAUNE** : aucun appelant ne l alimente quand tous les candidats echouent |
| **seuil du disjoncteur** (50 % sur 10) | 🟢 pose | seuil 3 echecs consecutifs |
| **etats OPEN / HALF-OPEN / CLOSED** | 🟢 pose | prouve sur 6 cas + persistance entre processus |

## 3. Les cinq garde-fous d'outils — ch. 10

| prescription | etat | preuve |
| --- | --- | --- |
| **Schema validation** — rejeter avant execution | 🟢 | `epreuve_applicateur_maison` · `nexus_appliquer` (ancre unique + syntaxe) |
| **Dry-run modes** pour tout geste destructeur | 🟡 | `nexus_vitrine --simulation` · `nexus_appliquer` n'en a pas |
| **Confirmation prompts** | 🟡 **externe** | c'est le harnais qui refuse, pas mes outils |
| **Tool compatibility checks** — sortie de A vers entree de B | 🔴 absent | **a casse** : `suivis()` rend des chemins que `contenus()` OUVRE |
| **Rate limiting / circuit breakers** | 🟢 pose | voir §2 |
| **Tool shadowing** — journaliser SANS executer | 🔴 **TOUJOURS ROUGE** | `nexus_ombre.py` pose et **NON FONCTIONNEL** : l'extraction des blocs echoue, et il rend **0 sur un echec**. Il n'ecrit rien — cible verifiee INTACTE par hash — mais un outil qui ne fait rien correctement n'est pas un outil. **TROIS tentatives echouees** — deux patchs et une commande a neuf. L'outil traite les MARQUEURS comme des ancres et rend 0 sur REFUSE. **QUATRE tentatives** — deux patchs, une commande a neuf, un Haiku en worktree isole. Le rendu Haiku etait DEGENERE (une chaine repetee), **et l'isolation a tenu** : arbre principal PROPRE, fichier inchange, worktree jete. Acquis : aucune ecriture, cibles INTACTES par hash. **Arret decide.** |

## 4. Modes de defaillance — ch. 10

| prescription | etat | preuve |
| --- | --- | --- |
| **Graceful degradation EN TIERS** | 🔴 absent | vitrine binaire : publication ou refus total |
| **Feature flags / kill switches** | 🟡 pose ce jour | `NEXUS_GENERATION_GELEE` · `NEXUS_PRODUCTION_LIBRE` · `NEXUS_AGENT_LIBRE` |
| **Checkpointing en stockage DURABLE** | 🟢 | commit par tour · `nexus_sauvegarde` en tache planifiee |
| **TTL sur les donnees echangees** | 🔴 absent | **4 chiffres perimes mesures en un jour** |
| **Timeout-aware retry with backoff** | 🔴 absent | — |

## 5. Anti-patrons d'outils — ch. 10, et je les ai COMMIS

| anti-patron | mes occurrences du jour |
| --- | --- |
| **Zombie parameters** — hallucination par analogie | **3x** : `--fichier --patch`, `--chaines`, `controle_script` |
| **Assumed state** — supposer sans verifier | `ruff` dans le PATH · `.nexus` sous `scripts/` · corpus indexable |
| **Ignored errors** | **20x** avertissements CRLF · **3x** `F821 Undefined name` lu comme du style |
| **Premature optimization** | — |

## 6. Securite des outils — ch. 4

| prescription | etat |
| --- | --- |
| **Mediated fine-grained access** — outils etroits plutot qu'un `kubectl` | 🟢 46 outils cibles, pas un shell generique |
| **Human-in-the-loop** sur les gestes a fort enjeu | 🟢 externe : `rm` refuse, publication confirmee |
| **Full trust, full access** — a eviter | 🟢 evite |

---

## Ce que cette checklist NE couvre PAS

⛔ **Deux fichiers du coeur restent hors audit** : `nexus_test.py` (3 610 lignes) et
`tools/nexus-mcp/server.js` (3 556 lignes, **le serveur MCP**). Ils depassent le calibre d'un
appel unique. **Ecartes en le DISANT.**

⚠️ **Une prescription ABSENTE n'est pas toujours un defaut** : l'appariement chapitre-fichier est
de moi. Un chapitre hors sujet produit un ABSENTE juste et inutile.

⚠️ **14 fichiers audites sur 71.** Le ratio mesure — **~1 prescription tenue sur 7** — porte sur
ces 14 seulement.

---

## 7. Ce que le CLIQUET DE CABLAGE ne sait pas voir — defaut connu, non corrige

**Mesure du 2026-09-02, repetee trois fois dans la journee** : `nexus_cablage.py` declare
orphelin tout script qu'aucun **FICHIER SUIVI PAR GIT** n'invoque.

    nexus_sauvegarde.py        tache planifiee NexusSauvegarde, resultat 0   -> declare ORPHELIN
    nexus_checklist_progres.py tache planifiee NexusProgress,   Ready        -> declare ORPHELIN

⇒ **Ces deux scripts ont un appelant REEL, qui tourne sans session — et c'est precisement pour
cela qu'il est invisible au cliquet.** Une tache planifiee Windows n'est pas un fichier du depot.

★ **Un controle aveugle a une classe entiere d'appelants produit de FAUX orphelins, et de faux
orphelins font desarmer le controle.** C'est le risque reel : a force de voir des orphelins qui
n'en sont pas, on cesse de lire la liste.

**CAUSE, lue dans le code** : `suivis()` rend des CHEMINS, `contenus()` les OUVRE et filtre sur
l'extension. **Y injecter une ligne de commande de tache planifiee ne peut pas marcher** — j'ai
essaye, le patch a ete pose sans effet, et je l'ai RETIRE plutot que de laisser du code mort.

**REMEDE JUSTE, nomme et NON FAIT** : `contenus()` doit accepter un couple nom-texte plutot qu'un
chemin, pour qu'une source d'appelant non-fichier soit representable. **C'est une refonte, pas un
patch** — et le dire vaut mieux que le bricoler.

---

## 8. VS Code — etat des sources, mesure le 2026-09-02

**Consigne : consulter les livres et la documentation VS Code AVANT de conclure, et distinguer
documente / constate / non verifie / inconnu.** Mesure faite, resultats bruts :

| question | verdict | mesure |
| --- | --- | --- |
| corpus VS Code sous `references/` | **INCONNU** | 9 corpus presents, **aucun** ne porte VS Code |
| VS Code dans les 24 livres | **INCONNU** | recherche semantique -> « Microsoft Visual Studio » (IDE C++) et « Selecting the workspace folder », **rien sur VS Code** |
| ce depot est-il un projet VS Code | **CONSTATE : non** | ni `.vscode/`, ni `*.code-workspace` |

⇒ **Aucune affirmation sur VS Code — architecture, extensions, agents, workspaces, modeles — ne
peut etre faite depuis ce depot.** Les sources n'y sont pas. **L'absence d'information n'est pas
une validation**, et elle n'est pas non plus une infirmation : c'est INCONNU.

**Ce qui EST constate**, sans interpretation : le travail de ce depot est livre par commits git,
donc lisible depuis n'importe quel editeur. **Aucune integration VS Code n'existe et aucune n'a
ete demandee de facon verifiable.**


---

## 9. Ce que ce tour a mesure et laisse OUVERT — 2026-09-02

| fait | etat | preuve |
| --- | --- | --- |
| ~~**`record_failure` n est pas atteint quand TOUS les candidats echouent**~~ **FERME** | 🟢 **PROUVE PAR EFFET** | journal **1120 -> 1586 octets** apres un echec total, et `modele-qui-n-existe-pas` passe a `etat=open`, `fail_count=3`. **Non-regression verifiee dans le meme geste** : les 4 replis gratuits restent `closed`, `fail_count=0` — le correctif n a banni aucun modele reel |
| **12 639 PDF a portee, jamais ingeres** | 🔴 **OUVERT** | comptes ce jour sous `D:\SAS\reference` (dont le benchmark GAIA). La doc PyMuPDF est deja sur disque (8 Ko, `open`/`get_text`/`get_pixmap`/`get_toc`) : le moyen existe, l ingestion n a jamais eu lieu |
| **`recovery_timeout` passe de 0 a 300 s par defaut** | 🟡 **A SURVEILLER** | le code d avant passait `delai=0` ; le correctif n a pas repris le parametre, donc le defaut du module (300 s) s applique. Sans consequence tant que rien n ouvre le circuit — mais deviendra visible des que la rouge ci-dessus sera fermee |

**Ce que ce tour confirme sur la METHODE, et qui vaut au-dela du disjoncteur :**

Le format de rendu est une garde. Deux passes ont ete refusees au banc, la
seconde parce que **deux ancres sur quatre etaient FABRIQUEES** — 0 occurrence
reelle. La troisieme est passee sans que le modele change : seul le FORMAT a
change. L orchestrateur a fourni les ancres, verifiees uniques dans le fichier
reel, et le banc n a plus rendu que le remplacement. **L invention d ancre
devient alors impossible, non pas decouragee.**


## 10. ANOMALIE OUVERTE, mesuree et NON EXPLIQUEE — 2026-09-02

| fait | etat |
| --- | --- |
| **le repli automatique n essaie qu UN SEUL candidat** | 🔴 **OUVERT** |

Mesure, par le fichier de sortie et non par l affichage :

```
python scripts/nexus_agent.py --modele modele-qui-n-existe-pas --sortie echec.jsonl
  -> candidats en echec : 1
  -> "tous les replis gratuits ont echoue : modele-qui-n-existe-pas : HTTP 400 ..."
```

`REPLIS_GRATUITS` porte quatre modeles ; `candidats` en compte donc cinq ; la
boucle fait `continue` apres chaque echec et le seul `break` concerne la
troncature. **Un seul essai a pourtant eu lieu.** Plus troublant : au moment de
cette mesure `modele-qui-n-existe-pas` etait deja `open`, donc le filtrage du
disjoncteur aurait du l ECARTER — et c est lui, et lui seul, qui figure dans
les echecs.

**Aucune hypothese n est retenue ici.** Le chemin de retour (ligne 1175) et la
boucle (ligne 1062) appartiennent bien a la meme fonction `executer` : la
boucle a donc tourne. Pourquoi elle n a tourne qu une fois n est PAS etabli, et
ecrire une cause plausible serait exactement la faute que ce depot mesure
depuis deux jours.

### La faute que j ai commise en le cherchant, et qui vaut d etre gravee

Premiere mesure : `grep -o "ECHEC : [^|]*"`. Le message concatene les echecs
avec ` | `, **que ma propre classe de caracteres excluait**. J ai donc lu « un
seul echec » sur une sortie qui en portait peut-etre plusieurs, et j ai failli
declarer une anomalie de MESSAGE la ou il n y en avait pas.

> **L instrument etait exact — `grep -o` fait exactement ce qu on lui demande —
> et la conclusion etait fausse.** La classe du depot, commise par
> l orchestrateur lui-meme, dans le geste ou il traquait la meme classe chez un
> autre.

C est la relecture par le fichier `--sortie` qui a tranche, et elle a confirme
le chiffre : **1**. L anomalie est reelle. Le premier instrument qui l avait
« montree » ne prouvait rien.


## 11. Audit LIVRE VS CODE delegue — trois prescriptions, 2026-09-02

Conduit par un agent en **worktree isole**, puis **audite ici contre le reel**
(LOI 1, temps 3 : ni le diagnostic ni le correctif ne sont de l'orchestrateur).

**Les trois citations ont ete verifiees dans le corpus, verbatim, avant tout
verdict** — un modele peut fabriquer une citation, et deux l'ont fait sur ce
depot aujourd'hui meme :

| prescription | citation retrouvee dans `references/livres/` |
| --- | --- |
| Idempotency | *« Idempotency requirements ensure agents can safely retry operations. Mark which operations are idempotent and which aren't. »* |
| TTL | *« Consider stamping data passed between agents with a TTL so stale data is refreshed »* |
| Degradation en tiers | *« Tier 2 might disable analytics or logging to reduce load. Tier 3 could switch to simpler, faster models... »* |

Source commune : *Design Multi-Agent AI Systems Using MCP and A2A*, sections
« Building coordination guardrails », « Timeout and latency issues »,
« Graceful degradation strategies ». Trouvees dans **deux** corpus independants
(`epub/` et `packt/`).

### Ce que l'audit a change, et ce qu'il a REFUSE de changer

| ligne | avant | apres | pourquoi |
| --- | --- | --- | --- |
| **Idempotency** | 🔴 | 🟡 | une protection existe et est **prouvee par execution** — mais accidentelle, locale a 1 outil sur ~46, et sans marquage |
| **TTL** | 🔴 | 🔴 **CONFIRMEE** | `git grep -ci "ttl" -- scripts tools` rend **0**, contre-verifie ici. Le seul mecanisme de fraicheur (`controle_config_active`) porte sur un fichier de CONFIGURATION et **ne bloque jamais**, par conception ecrite |
| **Degradation en tiers** | 🔴 | 🔴 **CONFIRMEE** | `nexus_vitrine.py` est **binaire** : un seul `BLOQUE` arrete tout. `NEXUS_GENERATION_GELEE` et `NEXUS_PRODUCTION_LIBRE` sont des 0/1, pas des paliers. Aucun etat observable « je tourne en Tier 2 » |

### La nuance que l'agent a refuse de transformer en promotion

La chaine de repli de `nexus_agent.py` **est** une degradation progressive de
capacite. Elle n'est pourtant **ni declaree comme palier, ni observable comme
etat, ni couplee a une reduction de fonctionnalites** comme le livre le
prescrit. L'agent l'a nomme et a **maintenu le ROUGE**.

> C'est exactement la mecanique demandee : une ressemblance n'est pas une
> satisfaction, et un mecanisme qui produit le bon effet **par accident** ne
> ferme pas une prescription qui demande une INTENTION declaree.

### Ce que l'agent declare n'avoir PAS verifie — recopie sans adoucissement

* le rejeu reel de `nexus_valide.py`, `nexus_sauvegarde.py`, `nexus_batch`,
  `nexus_ruche`, `nexus_essaim` : cherches par grep, **jamais executes** ;
* la mesure « 4 chiffres perimes en un jour » citee par le tableau pour TTL :
  **preuve heritee, non reproduite** ce tour ;
* `nexus_vitrine.py` **n'a pas ete execute** (effet de publication possible) :
  le verdict binaire repose sur lecture de code.


## 12. LA PRESCRIPTION QUE J AVAIS MAL DECRITE — et l audit faux qu elle a produit

Un agent isole a conclu que « **Tool shadowing** » n existe **nulle part** dans
le corpus, apres avoir cherche dans les deux rayons (18 075 fragments), et en a
deduit que les garde-fous du livre sont « exactement cinq, pas six ».

**Verification ici, LOI 1 temps 3 — sa conclusion est FAUSSE.** La prescription
existe, verbatim :

> *« **Tool shadowing**: Implement shadow tools that log calls without executing
> them. Use these during development to verify agents are calling tools
> correctly before allowing real operations. This is especially valuable for
> destructive operations such as deletions or deployments. »*

### La faute est la MIENNE, et elle vaut plus que la trouvaille

Dans la consigne que je lui ai ecrite, j ai decrit Tool shadowing comme
« **deux outils exposant le meme nom** ». C est faux. Je l ai ecrit **de
memoire**, sans ouvrir le livre — alors que le tableau, ligne 43, portait deja
la bonne definition depuis le debut : « journaliser SANS executer ».

L agent a donc cherche une collision de noms, ne l a evidemment pas trouvee, et
a conclu correctement **a partir d une premisse fausse**.

> **Une consigne fausse produit un audit faux, et l audit a l air rigoureux.**
> Le rapport citait ses sources, comptait ses fragments, listait ce qu il n
> avait pas pu verifier — tout etait juste sauf la question posee.

C est la classe du depot deplacee d un cran : non plus un instrument qui repond
a la question voisine, mais **un operateur qui pose la question voisine a un
instrument exact**.

### Ce que cela change pour `nexus_ombre.py`

Rien sur la couleur — la ligne **reste 🔴**, quatre tentatives, arret
decide. Mais l outil visait la **bonne** prescription : un outil-ombre qui
journalise sans ecrire, pour les operations **destructrices**. Le nom etait
juste, la definition du tableau etait juste ; seule ma consigne ne l etait pas.

**Et le livre dit pour quoi il sert en priorite** — *« especially valuable for
destructive operations such as deletions or deployments »* — ce que ni le
tableau ni les quatre tentatives n avaient retenu.

## 13. UN FAUX VERT DANS LA SUITE D EPREUVES — 2026-09-02

| fait | etat |
| --- | --- |
| **`nexus_epreuve_vide.py` est appele SANS ARGUMENT** | 🔴 **OUVERT** |

`nexus_test.py:1383` fait `jouer_epreuve_python("nexus_epreuve_vide.py", "rendu vide")`.
Mesure directe :

```
python scripts/nexus_epreuve_vide.py
Usage: nexus_epreuve_vide.py <path>...
```

**Aucun cas n est rendu.** L epreuve du « rendu vide » — celle-la meme qui
existe pour attraper les rendus vides — est appelee d une facon qui la rend
muette. Elle figure dans la suite, elle ne prouve rien.

> Trouve par un agent isole qui a **execute** le script au lieu de lire son
> appel. Aucune lecture ne l aurait montre : la ligne d appel est correcte en
> syntaxe et fausse en effet.

---

## 14. LE FAUX VERT INTER-DEPOTS — 2026-09-02

| fait | etat |
| --- | --- |
| **l empreinte annoncee du socle n etait pas celle que git portait** | 🟢 **REPARE, prouve** |

Le commit `fa49224` affirmait *« CONCORDANCE PROUVEE sur les trois depots —
empreinte cef66586 »*. Mesure par trois instruments, dont un qui n applique
aucun filtre :

```
git cat-file blob (aucun filtre)  ->  34828bedf08e14ad ,   0 CR
git show          (filtres)       ->  34828bedf08e14ad
fichier sur disque                ->  cef66586c7fbebfb , 216 CR
```

**L empreinte annoncee decrivait le fichier LOCAL, jamais le blob.** Un depot
tiers qui clone recevait `34828bed`. La concordance ne survivait pas au
clone — et elle portait sur le mecanisme meme cense prouver que les trois
depots partagent un socle identique.

**Cause** : `.gitattributes` declare bien `-text` et l attribut est ACTIF
(`git check-attr` rend `text: unset`). Mais il a ete pose **apres** que le
fichier ait ete commis normalise, et **un attribut n agit jamais
retroactivement sur un blob deja ecrit**.

**Remede** : `git add --renormalize`. Le fichier sur disque ne bouge pas d un
octet ; seul le blob s aligne. Verifie avant commit puis apres : `cef66586`,
216 CR. 216 insertions, 216 suppressions, aucune modification de contenu.

> **Un hash annonce dans un commit n est pas une preuve : c est une
> affirmation.** Celui-ci a survecu parce que personne n avait compare
> l annonce au blob — seulement au fichier qu on avait sous la main.

## 15. UN DEFAUT DE MON PROPRE DISPOSITIF DE DELEGATION

| fait | etat |
| --- | --- |
| **les worktrees d agents naissent en retard, et se resynchronisent sur le MAUVAIS point** | 🔴 **OUVERT** |

Un agent a diagnostique, repare et prouve un defaut de `nexus_garde_production.py`
— declaration `OUTILS_JUGES` manquante, controle a `ALERTE` puis a `OK`, quatre
epreuves rejouees vertes. Travail impeccable.

**Le defaut n existait plus.** Mesure dans l arbre principal au moment de
l integration : `OUTILS_JUGES` present, controle deja `OK`.

**Cause, et elle est de l orchestrateur** : sa consigne disait
`git fetch && git merge --ff-only origin/main`. Or `origin/main` est **157
commits en arriere** — rien n est pousse. L agent a donc lu « Already up to
date » et travaille sur du code d avant-hier, en toute bonne foi.

> **Un agent qui se resynchronise sur une reference perimee auditera du code
> perime, et son rapport sera exact sur un etat qui n existe plus.**

Les cinq consignes suivantes portaient `git merge --ff-only main` — la branche
LOCALE — et n ont pas eu le probleme. La correction est connue ; ce qui reste
ouvert, c est qu **aucun controle ne refuse une consigne qui pointe vers
`origin`** quand `origin` est en retard.

**Et la vraie racine est ailleurs** : ces 157 commits non pousses sont eux-memes
la cause. Deux sessions voisines l ont dit le meme jour, apres avoir perdu leur
volume : *« ce qui sauve le travail, ce sont les poussees regulieres »*.

---

## 16. CABLAGE DES EPREUVES — deux dettes DECLAREES, aucune maquillee

Mecanique appliquee : ROUGE = non satisfait, et **aucune promotion sans
preuve**. Ce qui suit est mesure, pas suppose.

| epreuve | etat REEL mesure | verdict |
| --- | --- | --- |
| `epreuve_journal_disjoncteur.py` | **cablee mais IMBRIQUEE** sous `if args.only in (None, "import")`. Elle se joue en passe complete — `args.only` vaut `None` — mais **`--only` ne peut pas l atteindre seule** : elle n a pas de cle propre | 🟡 **PARTIEL** |
| `epreuve_cles_only.py` | **ORPHELINE**. Ecrite, verte, contre-epreuve prouvee — et **personne ne l appelle**. Le cliquet la signale : `orphelin scripts/epreuve_cles_only.py` | 🔴 **NON CABLEE** |

### Ce que j ai commis, et qui est la faute la plus interessante du tour

**J ai ecrit une epreuve et je ne l ai pas cablee — le jour meme ou j inscrivais
que « l appelant est le lien le plus souvent manquant ».** Le cliquet l a
attrape en une passe. C est exactement ce que le contrat 0.2.1 prevoit : la
regle ecrite n a pas protege son auteur, le CONTROLE si.

Et en revenant en arriere, j ai decouvert que **mon cablage du matin etait deja
mal pose** : `epreuve_journal_disjoncteur` avait ete inseree SANS son propre
`if`, donc imbriquee. Elle tournait, elle passait, et elle etait mal branchee.
Personne ne l aurait vu : elle rend vert en passe complete.

### QUATRE tentatives de reparation, quatre echecs, et ce qu ils prouvent

| passe | rendu du banc | ce qui a arrete |
| --- | --- | --- |
| 1 | bloc **imbrique a 12 espaces** au lieu de 8 | rien — applique, puis retire par moi |
| 2 | ancre alteree | `REFUS : occurrences trouvees : 0` |
| 3 | rendu **VIDE** apres 76 s | le banc lui-meme, en echec |
| 4 | patch syntaxiquement invalide | `[!] Le patch produirait un fichier SYNTAXIQUEMENT INVALIDE` |

**Trois gardes sur quatre ont mordu.** Seule la premiere passe est entree — et
c est la plus instructive : le fichier restait **syntaxiquement valide** et
faisait **autre chose que ce qui etait demande**. C est exactement le troisieme
mode de defaillance du livre, cite verbatim :

> *« Semantic mismatches: These are subtle but critical failure modes where a
> tool executes successfully but produces a result that does not align with the
> user's intent. »*
> — *30 Agents Every AI Engineer Must Build*, ch. 7, « Common failure modes »

Aucune garde ne l a vue, parce qu aucune ne juge l INTENTION. `py_compile`
passe, `ruff` passe, l applicateur passe. **Seule une relecture du resultat
l attrape** — et c est la raison d etre du temps 3 du contrat 0.7.1.

**Arret decide apres quatre passes**, comme pour `nexus_ombre.py`. Les deux
lignes restent a leur couleur reelle. Un cablage force au chausse-pied vaudrait
moins qu une dette ecrite.

### 16.1 UN FAUX VERT QUE J AI CREE EN DOCUMENTANT LA DETTE

Mesure, dans l ordre, sans rien omettre :

```
1. cliquet avant inscription   ->  orphelin  scripts/epreuve_cles_only.py
2. j inscris la dette dans CHECKLIST_LIVRE_VS_CODE.md
3. cliquet apres inscription   ->  preuve_seule  (categorie MOINS grave)
4. rebaseline                  ->  « 0 orphelin(s) »
5. cliquet                     ->  « Cablage : aucune regression. »   exit 0
```

**L epreuve n est toujours appelee par PERSONNE.** Seule sa MENTION dans un
fichier Markdown a change sa categorie.

C est le defaut deja connu de cet instrument, reinscrit ici parce qu il vient
de mordre : *« the wiring check counted a mention in a comment as a call »*.
Il ne distingue pas **etre cite** de **etre appele**, et une documentation
honnete de la dette suffit a la faire disparaitre du tableau.

> **Ecrire qu un defaut existe l a fait disparaitre de l instrument qui le
> mesurait.** Le cliquet dit maintenant « aucune regression » sur un depot ou
> l epreuve reste orpheline.

**Consequence tenue** : la ligne du tableau reste **🔴 NON CABLEE**. Le cliquet
est vert, la realite ne l est pas, et c est la realite qui compte. La reference
a ete figee parce que 164 commits attendaient d etre pousses et que deux
sessions voisines ont perdu leur volume le meme jour — mais elle est figee avec
cet aveu, pas a sa place.

**Ce qui manque, et qui n est PAS ecrit ce tour** : un controle qui distingue
une citation d un appel. Tant qu il n existe pas, ce paragraphe ne ferme rien
(contrat 0.2.1).

---

## 17. INVENTAIRE AVANT L AUDIT FINAL — 2026-09-02

Consigne de l operateur : *« avant FABLE 5, assure-toi qu il ne manque aucun
fichier a faire reparer »*. Inventaire mecanique, pas declaratif.

| ensemble | compte |
| --- | --- |
| fichiers suivis par git | 278 |
| dont **le PROJET** (hors `nexus_*`, `epreuve_*`, `rituels/`, `references/`, `.claude/`) | **93** |
| couverts par un agent de reparation | **44** |
| **jamais vus par personne** | **49** |

Les 49 se repartissent ainsi, et deux lots ont ete depeches pour les couvrir :

* **2 scripts Python du projet** — `console_tools.py`, `mesure_rendu_vide.py` —
  du CODE jamais audite ;
* **3 `competences/*.txt`**, charges dynamiquement par `nexus_agent.py` comme
  consigne systeme : une consigne qui se contredit est un defaut reel ;
* **44 documents** sous `docs/`, dont ~36 `docs/architecture/*.txt`.

### Deux ecarts trouves par la confrontation checklist vs depot

La regle « verifie que ce que tu affirmes correspond a ce que tu as fait » a
ete appliquee au tableau de bord lui-meme. Deux ecarts, tous deux dans
l INSTRUMENT :

| declare | reel | cause |
| --- | --- | --- |
| arbre « propre » | **modifie** | le generateur mesure l arbre AVANT de s ecrire : il ne peut jamais voir son propre effet |
| cablage « inconnu » | **0 regression** | le rituel qui REUSSIT ecrit « aucune regression » — sans chiffre. Le motif `(\d+)` ne trouvait rien et lisait un SUCCES comme une IGNORANCE |

Le second est repare et verifie : le tableau affiche desormais **0**.
Le premier est **OUVERT** : un tableau de bord qui se salit lui-meme en se
generant ne peut pas rendre compte de sa propre modification.

> **Un « inconnu » affiche a la place d un succes est un defaut grave** : il se
> lit comme une mesure impossible alors que la mesure a reussi et vaut zero.
> C est la meme famille que le « vide lu comme une panne », vue a l envers.
