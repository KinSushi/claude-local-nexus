# État de la plateforme

> Généré par `python scripts/nexus_state.py` le 2026-08-29 14:27.
> **Ne pas éditer à la main** : ce fichier décrit ce qui a été mesuré,
> pas ce que l'on croit installé. Le régénérer vaut mieux que le corriger.

## Dépôt

| | |
|---|---|
| Branche | `main` |
| Commit | `7555762` |
| Arbre de travail | propre |
| Version de routage | `rbe9e348efb` |

## Services

```
litellm-db	db	Up 12 minutes (healthy)
litellm-proxy	litellm	Up 12 minutes
litellm-redis	redis	Up 12 minutes (healthy)
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
| Disque libre | 576.7 Go |

## Inventaire exposé — 44 modèles



| Plan | Nombre | Facturation |
|---|---|---|
| Local | 30 | aucune, rien ne quitte la machine |
| Ollama Cloud | 6 | abonnement Ollama |
| Anthropic | 4 | crédits API, distincts de l'abonnement claude.ai |
| Routeurs | 4 | selon le plan retenu |

## Intégrité de la configuration

Verdict : **INVALIDE**

```
- modèle deepseek-coder-33b-local : 'deepseek-coder:33b' déclaré mais absent d'Ollama
- modèle codestral-local : 'codestral' déclaré mais absent d'Ollama
- modèle qwen2.5-32b-local : 'qwen2.5:32b' déclaré mais absent d'Ollama
- modèle llava-34b-local : 'llava:34b' déclaré mais absent d'Ollama
```

## Empreintes SHA-256

| Fichier | Empreinte |
|---|---|
| `docker-compose.yml` | `d60af63eaaa60b59c9e0e01857a67509` |
| `litellm_config.yaml` | `96c602b7fce82bf74cbdae75300cbfa8` |
| `model_list.txt` | `7ad5bf3484b009187e8d130b4fc33289` |
| `cloud_models.txt` | `28d73b327162ed4a55736b7753ddecc3` |
| `.mcp.json` | `3d8aee915dd1ab43456d15ba17cb7685` |
| `Set-ClaudeModel.ps1` | `e22aede9ce5d33311e8a95c3ee7ee8cf` |
| `tools/nexus-mcp/server.js` | `83ea15431cd8bef72106a78641139355` |
| `scripts/nexus_generate.py` | `313b11a242f4cdc705d07863a55a2558` |
| `scripts/nexus_validate.py` | `a6a3a10ad0e2b2430342252c30a49185` |
| `scripts/nexus_capability.py` | `aa1349a15c746e1914b6fa5cb8794478` |
| `scripts/nexus_test.py` | `ea2c0d41181ed56be68fef447be262a2` |
| `scripts/Update-NexusModels.ps1` | `d48fc00a503f02db5ff9746cdc2e1535` |

---

Sujets ouverts : voir [CHECKLIST_COCKPIT.MD](CHECKLIST_COCKPIT.MD).
Historique : voir [PROGRESS.md](PROGRESS.md).
