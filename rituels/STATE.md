# État de la plateforme

> Généré par `python scripts/nexus_state.py` le 2026-08-29 12:00.
> **Ne pas éditer à la main** : ce fichier décrit ce qui a été mesuré,
> pas ce que l'on croit installé. Le régénérer vaut mieux que le corriger.

## Dépôt

| | |
|---|---|
| Branche | `main` |
| Commit | `c2ef132` |
| Arbre de travail | modifié |
| Version de routage | `rbe9e348efb` |

## Services

```
litellm-db	db	Up 22 hours (healthy)
litellm-proxy	litellm	Up 17 minutes
litellm-redis	redis	Up 22 hours (healthy)
ollama-server	ollama	Up 22 hours (healthy)
```

## Moteur d'inférence

| | |
|---|---|
| Implantation | `docker+host` |
| Mémoire d'inférence | 32.4 Go |
| RAM machine | 61.6 Go |
| Budget pool | 19.4 Go |
| Budget maximal | 27.5 Go |
| CPU | 12 cœurs / 24 threads |
| GPU | AMD Radeon(TM) 890M Graphics (2.0 Go) |
| Offload GPU | non |
| Stockage modèles | `C:\` |
| Disque libre | 101.2 Go |

> 29 Go des 62 Go de la machine restent hors d'atteinte de
> l'inférence tant que le moteur tourne dans Docker.

## Inventaire exposé — 54 modèles

| Plan | Nombre | Facturation |
|---|---|---|
| Local | 40 | aucune, rien ne quitte la machine |
| Ollama Cloud | 6 | abonnement Ollama |
| Anthropic | 4 | crédits API, distincts de l'abonnement claude.ai |
| Routeurs | 4 | selon le plan retenu |

## Intégrité de la configuration

Verdict : **valide**

```
- non exposé à dessein : llama3.2-vision:90b — 54 Go de poids pour 32 Go de memoire d'inference
- non exposé à dessein : llama3.3:70b — 42 Go de poids pour 32 Go de memoire d'inference
- non exposé à dessein : llama4:scout — 67 Go de poids pour 32 Go de memoire d'inference
- moteur dans Docker : 29 Go des 62 Go de la machine sont hors d'atteinte de l'inference
```

## Empreintes SHA-256

| Fichier | Empreinte |
|---|---|
| `docker-compose.yml` | `d60af63eaaa60b59c9e0e01857a67509` |
| `litellm_config.yaml` | `83cfc30789cc46d868a92a9e184990f4` |
| `model_list.txt` | `7ad5bf3484b009187e8d130b4fc33289` |
| `cloud_models.txt` | `e29b58052f38e9ee5adf9e09482f1ced` |
| `.mcp.json` | `3d8aee915dd1ab43456d15ba17cb7685` |
| `Set-ClaudeModel.ps1` | `e22aede9ce5d33311e8a95c3ee7ee8cf` |
| `tools/nexus-mcp/server.js` | `f9e4937a55a4577544ed8f1e1cb19e50` |
| `scripts/nexus_generate.py` | `896c91105886be358aace27fae4e3986` |
| `scripts/nexus_validate.py` | `cd2a9c9f5a90d410d75f290de3ebbec6` |
| `scripts/nexus_capability.py` | `9f1fb5052abb98d31dae9ce6d06ca4e8` |
| `scripts/nexus_test.py` | `24d2ed49be58e3410b34be904144e00c` |
| `scripts/Update-NexusModels.ps1` | `4bc2d37e81a479fa59621b597221266e` |

---

Sujets ouverts : voir [CHECKLIST_COCKPIT.MD](CHECKLIST_COCKPIT.MD).
Historique : voir [PROGRESS.md](PROGRESS.md).
