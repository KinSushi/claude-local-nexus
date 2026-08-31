# État de la plateforme

> Généré par `python scripts/nexus_state.py` le 2026-08-31 11:45 Amér. du Sud - Pac..
> **Ne pas éditer à la main** : ce fichier décrit ce qui a été mesuré,
> pas ce que l'on croit installé. Le régénérer vaut mieux que le corriger.

## Dépôt

| | |
|---|---|
| Branche | `main` |
| Commit | `bafa8f9` |
| Arbre de travail | modifie |
| Version de routage | `r19be7650d1` |

## Services

```
litellm-db	db	Up 46 hours (healthy)
litellm-proxy	litellm	Up 12 hours
litellm-redis	redis	Up 46 hours (healthy)
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
| Disque libre | 333.5 Go |

## Inventaire exposé — 80 modèles



| Plan | Nombre | Facturation |
|---|---|---|
| Local | 53 | aucune, rien ne quitte la machine |
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
| `litellm_config.yaml` | `b04522a0be29ba8deddbf255a6b31172f93ff2e8dd7078464616c0cb7f53db4b` |
| `model_list.txt` | `310b5f8a5f8367a09771645407e199854f44f0c1ff6571c5ac7fdb0e7a6ceace` |
| `cloud_models.txt` | `17684bcb15b3a210bd2c660511bc68327c41e3d17b0bafe18c91192eff31ae6e` |
| `.mcp.json` | `2622bc6acf81e92285537bda8468c839ab6c5efd85876ec63b2ebe2fb101e7c5` |
| `Set-ClaudeModel.ps1` | `c9e49eec98c0e482634eb3faefc4a5b6b577ad02ec40acb71817d357e9e19d64` |
| `tools/nexus-mcp/server.js` | `40d90759e2621f0d9c4e65e5ab5a1568fcab4c0a0e59272cd3fbdcd7ac193e9b` |
| `scripts/nexus_generate.py` | `7bdb7c9b0626e3392c5b12fb5a4985ca246440aa036132b3a79a7d0131047d9b` |
| `scripts/nexus_validate.py` | `f861fb7f5d50240ba56a41233fb22c5b24426cb5d9d91cdc881f31f90dd64613` |
| `scripts/nexus_capability.py` | `2dd9e691834d26ff9139bc2e21155094ef4762f27479df1bfa34646f2ae151a3` |
| `scripts/nexus_test.py` | `13bb5d5f3dea9dbf57667b377350e72cf8a1806ac6b9399dca1869536b2a0bff` |
| `scripts/Update-NexusModels.ps1` | `dc4dc63208ecbb38d62936d2d7a2a2d08ce1f7f38a711e29b4cc6b2fba58043b` |

## Traque mecanique

```
50 fichier(s) analyse(s)
  classe 1  handler muet sur un try qui agit       38
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
