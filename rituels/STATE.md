# État de la plateforme

> Généré par `python scripts/nexus_state.py` le 2026-08-30 20:09 Amér. du Sud - Pac..
> **Ne pas éditer à la main** : ce fichier décrit ce qui a été mesuré,
> pas ce que l'on croit installé. Le régénérer vaut mieux que le corriger.

## Dépôt

| | |
|---|---|
| Branche | `main` |
| Commit | `dbc2ebe` |
| Arbre de travail | modifie |
| Version de routage | `r19be7650d1` |

## Services

```
litellm-db	db	Up 30 hours (healthy)
litellm-proxy	litellm	Up 7 hours
litellm-redis	redis	Up 30 hours (healthy)
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
| Disque libre | 346.7 Go |

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
| `docker-compose.yml` | `d60af63eaaa60b59c9e0e01857a67509` |
| `litellm_config.yaml` | `92a860365e08bc93dcb833f81306cf64` |
| `model_list.txt` | `310b5f8a5f8367a09771645407e19985` |
| `cloud_models.txt` | `c3dd69a2673b53559124fd20e9e93c84` |
| `.mcp.json` | `2622bc6acf81e92285537bda8468c839` |
| `Set-ClaudeModel.ps1` | `9e2a59fe81edff69aa860e95e3015223` |
| `tools/nexus-mcp/server.js` | `8a94ecd4ef9a1a24adbae936895c91a7` |
| `scripts/nexus_generate.py` | `bbb16e11531b9e90e2f3c8889950a9bc` |
| `scripts/nexus_validate.py` | `13d985178ff1a6e02c61c76c37c1b9f7` |
| `scripts/nexus_capability.py` | `d12b9c73d1ed8a18a4352c73efb11966` |
| `scripts/nexus_test.py` | `b6e559a15ae5caa4e81d07156f8c602b` |
| `scripts/Update-NexusModels.ps1` | `dc4dc63208ecbb38d62936d2d7a2a2d0` |

## Traque mecanique

```
38 fichier(s) analyse(s)
  classe 1  handler muet sur un try qui agit       26
  classe 2  decision prise sur un nom              5
  classe 3  defaut de modele non mesure            5
  classe 4  valeur neutre rendue par un except     4
  classe 5  refus rendu en sortie 0                0
  classe 6  refus rendu en retour 0                0
```

Heuristiques : chaque constat est une piste a verifier
dans le code reel, jamais un verdict. Detail par
`python scripts/nexus_traque.py`.

---

Sujets ouverts : voir [CHECKLIST_COCKPIT.MD](CHECKLIST_COCKPIT.MD).
Historique : voir [PROGRESS.md](PROGRESS.md).
