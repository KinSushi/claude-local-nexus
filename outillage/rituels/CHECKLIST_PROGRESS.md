# Checklist Progress
Generated: 2026-09-06 12:47:06

## 1. Depot
| Metric | Value |
|---|---|
| Commits non pushes | 33 |
| Etat de l'arbre | propre (hors ce tableau) |
| Date du dernier commit | 2026-09-06 12:46:53 -0500 |

## 2. Rituels
| Script | Regressions annoncees |
|---|---|
| nexus_cablage.py | 0 |
| nexus_outillage.py | 0 |

## 3. Outils
| Description | Value |
|---|---|
| Scripts nexus dans scripts/ | 80 |
| Occurrences name:"nexus_" dans server.js | 15 |

## 4. Checklist LIVRE VS CODE
| Couleur | Nombre |
|---|---|
| Vert | 14 |
| Jaune | 12 |
| Rouge | 16 |

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
- Prescriptions rouges : 16
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
  - `nexus_index_livres.py`, `nexus_livres.py`, `nexus_sauvegarde.py` sont cables de la meme facon (`nexus_test.py:1396,1398,1400`, meme commit `c672862`)
  - le cliquet compte une EPREUVE comme appelant de PRODUCTION
  - les worktrees d agents naissent en retard, et se resynchronisent sur le MAUVAIS point
  - ORPHELINE
  - Consequence tenue
- Commits non pousses : 33
