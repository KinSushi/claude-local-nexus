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
| 3 | **Idempotency** — marquer les operations idempotentes | 🔴 absent | aucune relance n'est marquee |
| 4 | **State validation** — invariants verifies en tache de fond | 🟡 partiel | `nexus_conformite` · rien ne verifie les invariants de VERROU |
| 5 | **Dependency validation** au deploiement | 🔴 absent | — |
| 6 | **Coordination testing** — *deux agents sur la meme ressource* | 🔴 absent | **c'est l'incident `banc`, vecu trois fois** |

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
