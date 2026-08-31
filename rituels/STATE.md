# État de la plateforme

> Généré par `python scripts/nexus_state.py` le 2026-08-31 03:19 Amér. du Sud - Pac..
> **Ne pas éditer à la main** : ce fichier décrit ce qui a été mesuré,
> pas ce que l'on croit installé. Le régénérer vaut mieux que le corriger.

## Dépôt

| | |
|---|---|
| Branche | `main` |
| Commit | `6bd502e` |
| Arbre de travail | propre |
| Version de routage | `r19be7650d1` |

## Services

```
litellm-db	db	Up 37 hours (healthy)
litellm-proxy	litellm	Up 4 hours
litellm-redis	redis	Up 37 hours (healthy)
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
| Disque libre | 341.0 Go |

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
| `litellm_config.yaml` | `f31e7e7f63c69bee65c62b6aa27213b616f74601c6f4caa1efa79c6698b3d196` |
| `model_list.txt` | `310b5f8a5f8367a09771645407e199854f44f0c1ff6571c5ac7fdb0e7a6ceace` |
| `cloud_models.txt` | `7565ac0a0376fafa2b126349c10e6916c7ca891a2986acc8119dbbc0c6882659` |
| `.mcp.json` | `2622bc6acf81e92285537bda8468c839ab6c5efd85876ec63b2ebe2fb101e7c5` |
| `Set-ClaudeModel.ps1` | `9e2a59fe81edff69aa860e95e30152239b48128cbd68a4ef887acec3c21bd79f` |
| `tools/nexus-mcp/server.js` | `2df945e54f8470df9143a8449a95525f5f9ace9b5183042626feb87d390d7c2c` |
| `scripts/nexus_generate.py` | `d9aef51096bd1ec4741f635069353377840dc60d0abe2dcba8f6ef452d0be6a9` |
| `scripts/nexus_validate.py` | `13d985178ff1a6e02c61c76c37c1b9f79d24bd59c14a067c86087b28961ab4d1` |
| `scripts/nexus_capability.py` | `d12b9c73d1ed8a18a4352c73efb11966eb6b3dacbb4a7e63d7fd3cf0fb7da643` |
| `scripts/nexus_test.py` | `8fa3b5e5da5a030a30e3c322f81486d87a4d5643347317b800c940c374b4f42c` |
| `scripts/Update-NexusModels.ps1` | `dc4dc63208ecbb38d62936d2d7a2a2d08ce1f7f38a711e29b4cc6b2fba58043b` |

## Traque mecanique

```
38 fichier(s) analyse(s)
  classe 1  handler muet sur un try qui agit       27
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
