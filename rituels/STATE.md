# État de la plateforme

> Généré par `python scripts/nexus_state.py` le 2026-09-06 15:31 Amér. du Sud - Pac..
> **Ne pas éditer à la main** : ce fichier décrit ce qui a été mesuré,
> pas ce que l'on croit installé. Le régénérer vaut mieux que le corriger.

## Dépôt

| | |
|---|---|
| Branche | `main` |
| Commit | `8fcf745` |
| Arbre de travail | modifie |
| Version de routage | `r4501352c7d` |

## Services

```
litellm-db	db	Up 26 hours (healthy)
litellm-proxy	litellm	Up 7 hours (healthy)
litellm-redis	redis	Up 26 hours (healthy)
```

## Moteur d'inférence

| | |
|---|---|
| Implantation | `host` |
| Mémoire d'inférence | 66.2 Go |
| RAM machine | 66.2 Go |
| Budget pool | 39.7 Go |
| Budget maximal | 56.2 Go |
| CPU | 12 cœurs / 24 threads |
| GPU | AMD Radeon(TM) 890M Graphics (2.1 Go) |
| Offload GPU | non |
| Stockage modèles | `C:\Users\dibac\.ollama\models` |
| Disque libre | 261.5 Go |

## Inventaire exposé — 83 modèles



| Plan | Nombre | Facturation |
|---|---|---|
| Local | 56 | aucune, rien ne quitte la machine |
| Ollama Cloud | 19 | abonnement Ollama |
| Anthropic | 0 | crédits API, distincts de l'abonnement claude.ai |
| Routeurs | 4 | selon le plan retenu |
| Autres | 4 | non classés |

## Intégrité de la configuration

Verdict : **valide**

## Empreintes SHA-256

| Fichier | Empreinte |
|---|---|
| `docker-compose.yml` | `f1c6cae6dd67286a9f88c62e8d692ca19c2111da897851c56371588c6cd198fa` |
| `litellm_config.yaml` | `003f2b4bf04c0d4305ae41511be0f09adfd069f683e1e2190f4d81a5928dd07d` |
| `model_list.txt` | `15c95c6f625eeeaa1ac7840039315396caf4e9cd4a8f5e16602929cb94931e2b` |
| `cloud_models.txt` | `8126b079ecf7807f2519b57a3d5cd342614232713aca2248af97989df0f4b655` |
| `.mcp.json` | `2622bc6acf81e92285537bda8468c839ab6c5efd85876ec63b2ebe2fb101e7c5` |
| `Set-ClaudeModel.ps1` | `cd68d2299da2ed40a8f239ae11037cd243d9d64be4824c3cce3543ddc8244c1d` |
| `tools/nexus-mcp/server.js` | `d8474627f5a282fbe821099bc4d0d372eb97f40cb34457116089167eeac48703` |
| `scripts/nexus_generate.py` | `f29c16a2361518a3f920dddcd69dc2d96574860d6784245515ba404f2de5fd40` |
| `scripts/nexus_validate.py` | `8b0241724b3fbe8d44ccc84463e28b6e2dc9eafec340155d67d65ddecad51271` |
| `scripts/nexus_capability.py` | `5914bd87ce48ec4341715179051d36acd98a805302e416615bd043e1d842eb7c` |
| `scripts/nexus_test.py` | `509ab93db0d1d99731ca9d1c482844744f428ef3151e85948b96580f4ed248c8` |
| `scripts/Update-NexusModels.ps1` | `1fedad75868f29c99749fb9eb1825d1e7f181ba683f9be000ad65af37ce6f8f4` |

## Traque mecanique

```
82 fichier(s) analyse(s)
  classe 1  handler muet sur un try qui agit       61
  classe 2  decision prise sur un nom              5
  classe 3  defaut de modele non mesure            5
  classe 4  valeur neutre rendue par un except     7
  classe 5  refus rendu en sortie 0                0
  classe 6  refus rendu en retour 0                0
```

Heuristiques : chaque constat est une piste a verifier
dans le code reel, jamais un verdict. Detail par
`python scripts/nexus_traque.py`.

---

Sujets ouverts : voir [CHECKLIST_COCKPIT.MD](CHECKLIST_COCKPIT.MD).
Historique : voir [PROGRESS.md](PROGRESS.md).
