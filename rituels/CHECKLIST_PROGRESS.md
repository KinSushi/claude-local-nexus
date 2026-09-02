# Checklist Progress
Generated: 2026-09-02 15:31:49

## 1. Depot
| Metric | Value |
|---|---|
| Commits non pushes | 0 |
| Etat de l'arbre | modifie |
| Date du dernier commit | 2026-09-02 15:19:12 -0500 |

## 2. Rituels
| Script | Regressions annoncees |
|---|---|
| nexus_cablage.py | 0 |
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

---

## 7. LA VAGUE — etat mesure, pas declare (2026-09-02)

| ensemble | compte | verifie par |
| --- | --- | --- |
| fichiers suivis par git | 278 | `git ls-files` |
| **le PROJET** (hors outils `nexus_*`, `epreuve_*`, `rituels/`, `references/`, `.claude/`) | **93** | filtrage mecanique |
| perimetre « jamais vu par personne » a l inventaire | **47** | recoupement |
| **deja repares ET commites** | **21** | `git log --name-only 196e761..HEAD` |
| **confies aux 3 agents en vol** | **26** | lots disjoints de 9, 9 et 8 |
| somme | **47** | aucun fichier hors couverture |

### Le compte a ete corrige par la mesure, pas par l estime

Premiere reponse produite : « 0 reellement touches ». **Fausse** — mon
`git log --since=2026-09-02` ne rendait rien avec cette date. Remesure avec un
**temoin positif** (« la plage touche 32 fichiers au total ») : 21 faits, 26
restants. Sans le temoin, le zero se serait lu comme une mesure.

## 8. LE FILET — outil pose, et il ne fait PAS encore ce qu il annonce

`scripts/nexus_filet.py` : recupere en une passe le travail de tous les
worktrees d agents, VERBATIM, sans rien modifier. Dry-run par defaut,
`--appliquer` exige, refus de tout diff portant une SUPPRESSION sauf
`--avec-suppressions`.

Ce garde-fou existe pour une raison mesuree : **un agent a supprime
`docker-compose.yml` dans son worktree**, et un `git apply` aveugle aurait
emporte le fichier du depot reel — la suppression figurant comme un `D`
ordinaire, indiscernable d une modification voulue.

**Etat REEL de l outil, apres quatre passes de correction :**

```
Total worktrees: 20   Vides: 10   Refuses (suppressions): 0
Echecs check: 9       Deja appliques: 0   Conflits: 0   Appliques: 0
```

**Il compte encore mal.** Les compteurs `deja_appliques` et `conflits` restent
a zero alors que neuf patchs echouent au `--check` : la distinction demandee —
un patch DEJA APPLIQUE n est pas un conflit — a bien ete ecrite dans
`appliquer()`, mais le chemin qui la renseigne n est pas celui qu emprunte la
boucle. **JAUNE, jamais vert** : l outil tourne, son verdict n est pas fiable.

Quatre defauts corriges en route, chacun par delegation : `subprocess.stdout`
a `None`, un depaquetage a deux valeurs pour un retour a trois, deux compteurs
jamais initialises, et l affichage brut des erreurs de git.

> **Un outil de recuperation qui confond « deja fait » et « en conflit » ne
> repond pas a la question posee** — laquelle etait exactement : reste-t-il
> des manques dans ce qui a ete envoye en reparation ?
