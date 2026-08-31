# État de la plateforme

> Généré par `python scripts/nexus_state.py` le 2026-08-31 05:16 Amér. du Sud - Pac..
> **Ne pas éditer à la main** : ce fichier décrit ce qui a été mesuré,
> pas ce que l'on croit installé. Le régénérer vaut mieux que le corriger.

## Dépôt

| | |
|---|---|
| Branche | `main` |
| Commit | `7ef85e7` |
| Arbre de travail | modifie |
| Version de routage | `r19be7650d1` |

## Services

```
litellm-db	db	Up 39 hours (healthy)
litellm-proxy	litellm	Up 6 hours
litellm-redis	redis	Up 39 hours (healthy)
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
| Disque libre | 337.9 Go |

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
| `litellm_config.yaml` | `5c96414b214c94ad9e0b7e5f59cc78549b1d48e5d89c61304e9d09232f9e29b8` |
| `model_list.txt` | `310b5f8a5f8367a09771645407e199854f44f0c1ff6571c5ac7fdb0e7a6ceace` |
| `cloud_models.txt` | `4cacc5ffa16f30eb984272ea6425abec8dc449d4c93eab567da61969ea083155` |
| `.mcp.json` | `2622bc6acf81e92285537bda8468c839ab6c5efd85876ec63b2ebe2fb101e7c5` |
| `Set-ClaudeModel.ps1` | `9e2a59fe81edff69aa860e95e30152239b48128cbd68a4ef887acec3c21bd79f` |
| `tools/nexus-mcp/server.js` | `aec5dc3c373a0ac6cf17ec847017bdb2fac21e039fea49f74fe2772903391796` |
| `scripts/nexus_generate.py` | `d9aef51096bd1ec4741f635069353377840dc60d0abe2dcba8f6ef452d0be6a9` |
| `scripts/nexus_validate.py` | `13d985178ff1a6e02c61c76c37c1b9f79d24bd59c14a067c86087b28961ab4d1` |
| `scripts/nexus_capability.py` | `d12b9c73d1ed8a18a4352c73efb11966eb6b3dacbb4a7e63d7fd3cf0fb7da643` |
| `scripts/nexus_test.py` | `d52d14e32356233ec6707ed644b1facba5f2d3e05f9706141a0f2a1e07ce319f` |
| `scripts/Update-NexusModels.ps1` | `dc4dc63208ecbb38d62936d2d7a2a2d08ce1f7f38a711e29b4cc6b2fba58043b` |

## Traque mecanique

```
44 fichier(s) analyse(s)
  classe 1  handler muet sur un try qui agit       29
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
