# État de la plateforme

> Généré par `python scripts/nexus_state.py` le 2026-08-30 12:19 Amér. du Sud - Pac..
> **Ne pas éditer à la main** : ce fichier décrit ce qui a été mesuré,
> pas ce que l'on croit installé. Le régénérer vaut mieux que le corriger.

## Dépôt

| | |
|---|---|
| Branche | `main` |
| Commit | `e2a8e19` |
| Arbre de travail | modifie |
| Version de routage | `r19be7650d1` |

## Services

```
litellm-db	db	Up 22 hours (healthy)
litellm-proxy	litellm	Up 2 hours
litellm-redis	redis	Up 22 hours (healthy)
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

Verdict : **INVALIDE**

```
- fallbacks : 'claude-haiku-4-5' (text) retombe sur 'gemma4-31b-local' (vision) — modalite incompatible
- fallbacks : 'deepseek-coder-6.7b-local' (text) retombe sur 'qwen3-vl-8b-local' (vision) — modalite incompatible
- fallbacks : 'qwen2.5-coder-7b-local' (text) retombe sur 'qwen3-vl-8b-local' (vision) — modalite incompatible
- fallbacks : 'qwen2.5-coder-7b-local' (text) retombe sur 'qwen3.6-27b-local' (vision) — modalite incompatible
- fallbacks : 'qwen3-vl-8b-local' (vision) retombe sur 'qwen3-14b-local' (text) — modalite incompatible
- fallbacks : 'qwen3.6-27b-local' (vision) retombe sur 'qwen3-14b-local' (text) — modalite incompatible
- fallbacks : 'qwen3.6-27b-local' (vision) retombe sur 'qwen3-8b-local' (text) — modalite incompatible
- fallbacks : 'gemma4-31b-local' (vision) retombe sur 'llama3.2-3b-local' (text) — modalite incompatible
- fallbacks : 'gemma4-12b-local' (vision) retombe sur 'llama3.2-3b-local' (text) — modalite incompatible
- fallbacks : 'gemma4-12b-local' (vision) retombe sur 'phi3-mini-local' (text) — modalite incompatible
- fallbacks : 'phi3-mini-local' (text) retombe sur 'bge-m3-local' (embedding) — modalite incompatible
- fallbacks : 'ultime-recourse-local' (text) retombe sur 'bge-m3-local' (embedding) — modalite incompatible
- fallbacks : 'bge-m3-local' (embedding) retombe sur 'granite3.3-8b-local' (text) — modalite incompatible
- fallbacks : 'bge-m3-local' (embedding) retombe sur 'gemma4-26b-local' (vision) — modalite incompatible
- fallbacks : 'granite3.3-8b-local' (text) retombe sur 'gemma4-26b-local' (vision) — modalite incompatible
- fallbacks : 'granite3.3-8b-local' (text) retombe sur 'gemma4-local' (vision) — modalite incompatible
- fallbacks : 'gemma4-26b-local' (vision) retombe sur 'gpt-oss-20b-local' (text) — modalite incompatible
- fallbacks : 'gemma4-local' (vision) retombe sur 'gpt-oss-20b-local' (text) — modalite incompatible
- fallbacks : 'gemma4-local' (vision) retombe sur 'llama3.1-8b-local' (text) — modalite incompatible
- fallbacks : 'gemma4-31b-cloud' (text) retombe sur 'gemma4-31b-local' (vision) — modalite incompatible
- fallbacks : 'adaptive-router-local' (text) retombe sur 'gemma4-31b-local' (vision) — modalite incompatible
- context_window_fallbacks : 'gemma4-31b-local' (vision) retombe sur 'deepseek-coder-6.7b-local' (text) — modalite incompatible
- context_window_fallbacks : 'gemma4-31b-local' (vision) retombe sur 'llama3.1-8b-local' (text) — modalite incompatible
- context_window_fallbacks : 'gemma4-12b-local' (vision) retombe sur 'deepseek-coder-6.7b-local' (text) — modalite incompatible
- context_window_fallbacks : 'gemma4-12b-local' (vision) retombe sur 'llama3.1-8b-local' (text) — modalite incompatible
- context_window_fallbacks : 'bge-m3-local' (embedding) retombe sur 'deepseek-coder-6.7b-local' (text) — modalite incompatible
- context_window_fallbacks : 'bge-m3-local' (embedding) retombe sur 'llama3.1-8b-local' (text) — modalite incompatible
- context_window_fallbacks : 'gemma4-26b-local' (vision) retombe sur 'deepseek-coder-6.7b-local' (text) — modalite incompatible
- context_window_fallbacks : 'gemma4-26b-local' (vision) retombe sur 'llama3.1-8b-local' (text) — modalite incompatible
- context_window_fallbacks : 'gemma4-local' (vision) retombe sur 'deepseek-coder-6.7b-local' (text) — modalite incompatible
- context_window_fallbacks : 'gemma4-local' (vision) retombe sur 'llama3.1-8b-local' (text) — modalite incompatible
- context_window_fallbacks : 'qwen3-vl-8b-local' (vision) retombe sur 'glm-4.7-flash-local' (text) — modalite incompatible
- context_window_fallbacks : 'qwen3-vl-8b-local' (vision) retombe sur 'granite3.3-8b-local' (text) — modalite incompatible
- context_window_fallbacks : 'qwen3.6-27b-local' (vision) retombe sur 'deepseek-coder-6.7b-local' (text) — modalite incompatible
- context_window_fallbacks : 'qwen3.6-27b-local' (vision) retombe sur 'llama3.1-8b-local' (text) — modalite incompatible
```

## Empreintes SHA-256

| Fichier | Empreinte |
|---|---|
| `docker-compose.yml` | `d60af63eaaa60b59c9e0e01857a67509` |
| `litellm_config.yaml` | `858ed7bb9da8ea1357800687535e439d` |
| `model_list.txt` | `310b5f8a5f8367a09771645407e19985` |
| `cloud_models.txt` | `f33e74e16defb33966e90cb56522004c` |
| `.mcp.json` | `2622bc6acf81e92285537bda8468c839` |
| `Set-ClaudeModel.ps1` | `9e2a59fe81edff69aa860e95e3015223` |
| `tools/nexus-mcp/server.js` | `e722e5839bfb652f072d91801bfc094d` |
| `scripts/nexus_generate.py` | `61b116ed0ddee0ae004f39c8f3b80bb7` |
| `scripts/nexus_validate.py` | `13d985178ff1a6e02c61c76c37c1b9f7` |
| `scripts/nexus_capability.py` | `d12b9c73d1ed8a18a4352c73efb11966` |
| `scripts/nexus_test.py` | `e9baaa6c9992692829397dc869facdd8` |
| `scripts/Update-NexusModels.ps1` | `dc4dc63208ecbb38d62936d2d7a2a2d0` |

## Traque mecanique

```
26 fichier(s) analyse(s)
  classe 1  handler muet sur un try qui agit       11
  classe 2  decision prise sur un nom              21
  classe 3  defaut de modele non mesure            5
  classe 4  valeur neutre rendue par un except     3
  classe 5  refus rendu en sortie 0                0
  classe 6  refus rendu en retour 0                0
```

Heuristiques : chaque constat est une piste a verifier
dans le code reel, jamais un verdict. Detail par
`python scripts/nexus_traque.py`.

---

Sujets ouverts : voir [CHECKLIST_COCKPIT.MD](CHECKLIST_COCKPIT.MD).
Historique : voir [PROGRESS.md](PROGRESS.md).
