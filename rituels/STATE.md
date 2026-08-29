# État de la plateforme

> Généré par `python scripts/nexus_state.py` le 2026-08-29 11:12.
> **Ne pas éditer à la main** : ce fichier décrit ce qui a été mesuré,
> pas ce que l'on croit installé. Le régénérer vaut mieux que le corriger.

## Dépôt

| | |
|---|---|
| Branche | `main` |
| Commit | `718100e` |
| Arbre de travail | modifié |
| Version de routage | `rbe9e348efb` |

## Services

```
litellm-db	db	Up 22 hours (healthy)
litellm-proxy	litellm	Up 24 minutes
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
| Disque libre | 156.6 Go |

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
- install� mais non expos� : llama4:scout
- modele llama3.3-70b-local : 42 Go de poids pour 32 Go de memoire d'inference � declare mais inexecutable
- modele llama3.2-vision-90b-local : 54 Go de poids pour 32 Go de memoire d'inference � declare mais inexecutable
- moteur dans Docker : 29 Go des 62 Go de la machine sont hors d'atteinte de l'inference
```

## Empreintes SHA-256

| Fichier | Empreinte |
|---|---|
| `docker-compose.yml` | `cc1352d7cc8182db7f357a27f4c81208` |
| `litellm_config.yaml` | `6824305bbff60f2f4455c6bf73debb7d` |
| `model_list.txt` | `7ad5bf3484b009187e8d130b4fc33289` |
| `cloud_models.txt` | `2c1cfefd076d71ca16105df35a58d073` |
| `.mcp.json` | `3d8aee915dd1ab43456d15ba17cb7685` |
| `Set-ClaudeModel.ps1` | `4a0081170aa41da17b28a2e43fc57efc` |
| `tools/nexus-mcp/server.js` | `d23d0d108370bad272bf924823fc5f9a` |
| `scripts/nexus_generate.py` | `fa0302760b7d23700ca39ea668808ce1` |
| `scripts/nexus_validate.py` | `ab15e88b93f1a5a21571421fbf9bd9a0` |
| `scripts/nexus_capability.py` | `e469bf90814f06d15fdc22b396264c29` |
| `scripts/nexus_test.py` | `34d63912c310a1cbbb52e61f91c5414b` |
| `scripts/Update-NexusModels.ps1` | `4bc2d37e81a479fa59621b597221266e` |

---

Sujets ouverts : voir [CHECKLIST_COCKPIT.MD](CHECKLIST_COCKPIT.MD).
Historique : voir [PROGRESS.md](PROGRESS.md).
