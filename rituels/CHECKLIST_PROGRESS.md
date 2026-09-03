# Checklist Progress
Generated: 2026-09-02 16:01:09

## 1. Depot
| Metric | Value |
|---|---|
| Commits non pushes | 11 |
| Etat de l'arbre | modifie |
| Date du dernier commit | 2026-09-02 15:57:13 -0500 |

## 2. Rituels
| Script | Regressions annoncees |
|---|---|
| nexus_cablage.py | 1 |
| nexus_outillage.py | 85 |

## 3. Outils
| Description | Value |
|---|---|
| Scripts nexus dans scripts/ | 74 |
| Occurrences name:"nexus_" dans server.js | 15 |

## 4. Checklist VS Code
| Couleur | Nombre |
|---|---|
| Vert | 13 |
| Jaune | 11 |
| Rouge | 15 |

## 5. Sauvegardes
| Metric | Value |
|---|---|
| Nombre de fichiers .bundle | 0 |
| Date du plus recent | inconnu |

## 6. Corpus
| Metric | Value |
|---|---|
| Lignes dans fragments_embeddings.jsonl | 20366 |

## CE QUI RESTE OUVERT
- Regressions de cablage : 1
- Regressions d outillage : 85
- Prescriptions rouges : 15
  - Dependency validation
  - Coordination testing
  - Tool compatibility checks
  - Tool shadowing
  - Graceful degradation EN TIERS
  - TTL sur les donnees echangees
  - Timeout-aware retry with backoff
  - 12 639 PDF a portee, jamais ingeres
  - le repli automatique n essaie qu UN SEUL candidat
  - Idempotency
  - TTL
  - Degradation en tiers
  - reste 🔴
  - `nexus_epreuve_vide.py` est appele SANS ARGUMENT
  - les worktrees d agents naissent en retard, et se resynchronisent sur le MAUVAIS point
  - ORPHELINE
  - Consequence tenue
- Commits non pousses : 11

---

## 12. NexusProgress SUPPRIMEE — elle ne produisait rien, mesure a l appui

Signalee par l operateur : *« il y a une tache windows que tu avais posee pour
te rappeller les rituels, elle s avere inefficace et ne sert a rien »*.
Verifiee avant de conclure, puis retiree sur son ordre.

### La preuve, en trois mesures

```
NexusProgress a tourne a 15:57:25, LastTaskResult 3221225786
CHECKLIST_PROGRESS.md portait encore  Generated: 15:48:09
   -> soit ma generation MANUELLE precedente, pas la sienne
lance a la main : exit 0, fichier regenere a 15:59:21
```

**Le script fonctionne ; la tache ne produit rien.** `3221225786` vaut
`0xC000013A`, `STATUS_CONTROL_C_EXIT` : le processus est tue avant d ecrire.

### La cause, et ce n est pas un timeout

```
ExecutionTimeLimit : PT10M          duree reelle du script : 13,7 s
Execute : C:\Users\dibac\AppData\Local\Microsoft\WindowsApps\python.exe
```

**C est le stub du Microsoft Store**, pas l interpreteur reel. Ce stub ouvre le
Store quand Python n est pas installe par ce canal, et se fait tuer — d ou le
code d interruption. La tache pointait vers un lanceur, jamais vers Python.

**`Claude-Local-Nexus - Mise a jour` porte le MEME code** (`3221225786`, ce
jour a 04:00). Meme symptome, cause non verifiee — inscrite ici, pas supposee.

### Ce que l incident apprend

> **Une tache planifiee qui echoue silencieusement est pire qu une tache
> absente** : elle donne le sentiment qu un mecanisme tourne. Celle-ci s est
> declaree « Ready » et a rendu un code d erreur a chaque passage, pendant que
> le tableau de bord n etait tenu a jour que par des generations manuelles.

Le geste juste n etait pas de la reparer mais de la RETIRER : le tableau se
regenere en 13,7 s a la demande, et un rappel qui ment sur son propre etat ne
rappelle rien. **Supprimee, absence verifiee.**

Taches restantes, avec leur dernier code : `NexusSauvegarde` 0 · `NexusTraque`
0 · `NexusVitrine` 0 · `Demarrage` **1** · `Mise a jour` **3221225786**. Les
deux dernieres sont a examiner — inscrites, non traitees ce tour.
