# État de la plateforme

> Généré par `python scripts/nexus_state.py` le 2026-08-31 21:29 Amér. du Sud - Pac..
> **Ne pas éditer à la main** : ce fichier décrit ce qui a été mesuré,
> pas ce que l'on croit installé. Le régénérer vaut mieux que le corriger.

## Dépôt

| | |
|---|---|
| Branche | `main` |
| Commit | `e5862eb` |
| Arbre de travail | propre |
| Version de routage | `r19be7650d1` |

## Services

```
litellm-db	db	Up 2 days (healthy)
litellm-proxy	litellm	Up 2 hours
litellm-redis	redis	Up 2 days (healthy)
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
| Disque libre | 329.0 Go |

## Inventaire exposé — 81 modèles



| Plan | Nombre | Facturation |
|---|---|---|
| Local | 54 | aucune, rien ne quitte la machine |
| Ollama Cloud | 19 | abonnement Ollama |
| Anthropic | 0 | crédits API, distincts de l'abonnement claude.ai |
| Routeurs | 4 | selon le plan retenu |
| Autres | 4 | non classés |

## Intégrité de la configuration

Verdict : **valide**

## Empreintes SHA-256

| Fichier | Empreinte |
|---|---|
| `docker-compose.yml` | `d60af63eaaa60b59c9e0e01857a675092a96fc184c8dc51777362ea383dca2ef` |
| `litellm_config.yaml` | `0de981bbf44cb8086422741b642426ad3cc7a9fec1001a743c47019e1c873c19` |
| `model_list.txt` | `310b5f8a5f8367a09771645407e199854f44f0c1ff6571c5ac7fdb0e7a6ceace` |
| `cloud_models.txt` | `17684bcb15b3a210bd2c660511bc68327c41e3d17b0bafe18c91192eff31ae6e` |
| `.mcp.json` | `2622bc6acf81e92285537bda8468c839ab6c5efd85876ec63b2ebe2fb101e7c5` |
| `Set-ClaudeModel.ps1` | `c9e49eec98c0e482634eb3faefc4a5b6b577ad02ec40acb71817d357e9e19d64` |
| `tools/nexus-mcp/server.js` | `616a6b42c9d80739d4c77d00c9faebf9a1d1b7aef6fc93244ca4f640fc0e0db6` |
| `scripts/nexus_generate.py` | `7bdb7c9b0626e3392c5b12fb5a4985ca246440aa036132b3a79a7d0131047d9b` |
| `scripts/nexus_validate.py` | `f861fb7f5d50240ba56a41233fb22c5b24426cb5d9d91cdc881f31f90dd64613` |
| `scripts/nexus_capability.py` | `2dd9e691834d26ff9139bc2e21155094ef4762f27479df1bfa34646f2ae151a3` |
| `scripts/nexus_test.py` | `fbfc4df9a00e26335ff18205607444087b3c7de4d0c3a9a42173531438c30e1c` |
| `scripts/Update-NexusModels.ps1` | `1fedad75868f29c99749fb9eb1825d1e7f181ba683f9be000ad65af37ce6f8f4` |

## Traque mecanique

```
63 fichier(s) analyse(s)
  classe 1  handler muet sur un try qui agit       39
  classe 2  decision prise sur un nom              5
  classe 3  defaut de modele non mesure            5
  classe 4  valeur neutre rendue par un except     5
  classe 5  refus rendu en sortie 0                0
  classe 6  refus rendu en retour 0                0
```

Heuristiques : chaque constat est une piste a verifier
dans le code reel, jamais un verdict. Detail par
`python scripts/nexus_traque.py`.

---

Sujets ouverts : voir [CHECKLIST_COCKPIT.MD](CHECKLIST_COCKPIT.MD).
Historique : voir [PROGRESS.md](PROGRESS.md).
