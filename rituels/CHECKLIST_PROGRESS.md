# Checklist Progress
Generated: 2026-09-02 13:04:30

## 1. Depot
| Metric | Value |
|---|---|
| Commits non pushes | 154 |
| Etat de l'arbre | modifie |
| Date du dernier commit | 2026-09-02 12:48:12 -0500 |

## 2. Rituels
| Script | Regressions annoncees |
|---|---|
| nexus_cablage.py | 6 |
| nexus_outillage.py | 83 |

## 3. Outils
| Description | Value |
|---|---|
| Scripts nexus dans scripts/ | 73 |
| Occurrences name:"nexus_" dans server.js | 15 |

## 4. Checklist VS Code
| Couleur | Nombre |
|---|---|
| Vert | 11 |
| Jaune | 9 |
| Rouge | 10 |

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
- Regressions de cablage : 6
- Regressions d outillage : 83
- Prescriptions rouges : 10
  - Idempotency
  - Dependency validation
  - Coordination testing
  - Tool compatibility checks
  - Tool shadowing
  - Graceful degradation EN TIERS
  - TTL sur les donnees echangees
  - Timeout-aware retry with backoff
  - `record_failure` n est pas atteint quand TOUS les candidats echouent
  - 12 639 PDF a portee, jamais ingeres
- Commits non pousses : 154
