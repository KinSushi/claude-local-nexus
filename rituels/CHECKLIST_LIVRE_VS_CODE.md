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
| 2 | **Circuit breakers** — *stop calling an agent that keeps failing* | 🟢 **POSE** | `nexus_disjoncteur.py`, seuil 3, etat DURABLE, cable dans `nexus_agent` |
| 3 | **Idempotency** — marquer les operations idempotentes | 🔴 absent | aucune relance n'est marquee |
| 4 | **State validation** — invariants verifies en tache de fond | 🟡 partiel | `nexus_conformite` · rien ne verifie les invariants de VERROU |
| 5 | **Dependency validation** au deploiement | 🔴 absent | — |
| 6 | **Coordination testing** — *deux agents sur la meme ressource* | 🔴 absent | **c'est l'incident `banc`, vecu trois fois** |

## 2. Retry et disjoncteur — ch. 10, sept parametres

| prescription | etat | preuve |
| --- | --- | --- |
| **classer transitoire vs permanent** | 🟢 **MECANISE** | `echec_transitoire()` dans `nexus_disjoncteur` — patron `_is_retryable` du livre · 9 cas eprouves · un echec PERMANENT ouvre le circuit IMMEDIATEMENT |
| **backoff exponentiel** 100→200→400→800 ms | 🔴 absent | — |
| **jitter** contre le *thundering herd* | 🔴 absent | — |
| **plafond d'essais** (5) | 🟡 partiel | regle empirique « six renvois », non imposee |
| **journal du POURQUOI de chaque echec** | 🔴 absent | c'est ce qui empechait de CLASSER |
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
| **Tool shadowing** — journaliser SANS executer | 🔴 absent | **mes 6 applicateurs maison ECRIVAIENT** au lieu de journaliser |

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

