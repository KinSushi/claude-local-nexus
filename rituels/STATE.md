# État de la plateforme

> Généré par `python scripts/nexus_state.py` le 2026-08-30 11:20 Amér. du Sud - Pac..
> **Ne pas éditer à la main** : ce fichier décrit ce qui a été mesuré,
> pas ce que l'on croit installé. Le régénérer vaut mieux que le corriger.

## Dépôt

| | |
|---|---|
| Branche | `main` |
| Commit | `c4d6da5` |
| Arbre de travail | propre |
| Version de routage | `rdb210b95d0` |

## Services

```
litellm-db	db	Up 21 hours (healthy)
litellm-proxy	litellm	Up About an hour
litellm-redis	redis	Up 21 hours (healthy)
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
| Disque libre | 350.6 Go |

## Inventaire exposé — 67 modèles



| Plan | Nombre | Facturation |
|---|---|---|
| Local | 40 | aucune, rien ne quitte la machine |
| Ollama Cloud | 19 | abonnement Ollama |
| Anthropic | 0 | crédits API, distincts de l'abonnement claude.ai |
| Routeurs | 4 | selon le plan retenu |
| Autres | 4 | non classés |

## Intégrité de la configuration

Verdict : **valide**

## Empreintes SHA-256

| Fichier | Empreinte |
|---|---|
| `docker-compose.yml` | `d60af63eaaa60b59c9e0e01857a67509` |
| `litellm_config.yaml` | `401b405ea3a74323924a74717dc4b723` |
| `model_list.txt` | `310b5f8a5f8367a09771645407e19985` |
| `cloud_models.txt` | `15f445162e1ffb18c6ae3262f1437892` |
| `.mcp.json` | `2622bc6acf81e92285537bda8468c839` |
| `Set-ClaudeModel.ps1` | `9e2a59fe81edff69aa860e95e3015223` |
| `tools/nexus-mcp/server.js` | `b8f2ccefaa00d963b03db3ea90776764` |
| `scripts/nexus_generate.py` | `971b85a75f423e9c7fb7754096699194` |
| `scripts/nexus_validate.py` | `6223858008b01929344d3cb53430d70f` |
| `scripts/nexus_capability.py` | `d12b9c73d1ed8a18a4352c73efb11966` |
| `scripts/nexus_test.py` | `e9baaa6c9992692829397dc869facdd8` |
| `scripts/Update-NexusModels.ps1` | `f1471ac00eeaa15c056ca4d66d3a9495` |

---

Sujets ouverts : voir [CHECKLIST_COCKPIT.MD](CHECKLIST_COCKPIT.MD).
Historique : voir [PROGRESS.md](PROGRESS.md).
