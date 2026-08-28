# Claude-Local-Nexus

![Banner](https://raw.githubusercontent.com/KinSushi/Claude-Local-Nexus/main/images/banner.png)

> Plateforme locale d'orchestration IA – Dockerisée, souveraine, reproductible.

Architecture complète de proxy IA pour modèles locaux (Ollama), cloud (Anthropic, Ollama Cloud) et routeurs adaptatifs, avec PostgreSQL, Redis, Langfuse Cloud pour le tracing, et Claude Code comme client possible.

## Pourquoi ce projet ?

- **Souveraineté** : les modèles locaux ne quittent pas votre machine.
- **Flexibilité** : basculez entre modèles locaux et cloud selon la charge et le coût.
- **Reproductibilité** : une seule commande pour reconstruire l'infrastructure.
- **Observabilité** : traces complètes via Langfuse Cloud.
- **Automatisation** : scripts de synchronisation pour rester à jour.

## Configuration de la machine

- **OS** : Windows 11 (ou 10) 64-bit
- **CPU** : AMD Ryzen AI 9 HX 370 (24 threads, jusqu'à 5,1 GHz)
- **RAM** : 62 Go
- **GPU** : AMD Radeon 890M (iGPU intégrée) – utilisée uniquement par Ollama en mode CPU pour éviter les problèmes de pilotes Vulkan ; la mise à jour des pilotes AMD peut réactiver le GPU si souhaité
- **Stockage** : SSD NVMe recommandé pour les volumes Docker (modèles volumineux)
- **Docker Desktop** : dernière version stable
- **PowerShell** : 7.x recommandé pour les scripts et commandes

## Services inclus

| Service   | Image                                | Description                             |
|-----------|--------------------------------------|-----------------------------------------|
| `db`      | `postgres:16`                        | Base de données LiteLLM (logs, budgets) |
| `redis`   | `redis:7-alpine`                     | Cache sémantique pour LiteLLM           |
| `ollama`  | `ollama/ollama:latest`               | Serveur Ollama local (CPU)              |
| `litellm` | `ghcr.io/berriai/litellm:main-latest`| Proxy LiteLLM avec routeurs adaptatifs  |

## Prérequis

- Docker Desktop installé et fonctionnel
- Accès à un terminal PowerShell (ou bash)
- Clés API :
  - Anthropic (optionnel)
  - Ollama Cloud (pour les modèles cloud gratuits, ex: `gpt-oss:20b`)
  - Langfuse Cloud (pour le tracing)

## Fichiers importants

- `docker-compose.yml` : définition des services et volumes
- `litellm_config.yaml` : configuration des modèles, routeurs, cache, callbacks
- `model_list.txt` : liste des modèles **locaux** à télécharger dans Ollama
- `cloud_models.txt` : liste des modèles **cloud** (Ollama Cloud) utilisables avec votre clé ; actuellement `gpt-oss:20b:cloud`
- `.env.example` : modèle de fichier d'environnement (à copier en `.env` et personnaliser)
- `.gitignore` : pour exclure `.env` et les sauvegardes du versionnement
- `update_cloud_models.ps1` : script pour synchroniser automatiquement les modèles cloud avec l'API officielle
- `update_local_models.ps1` : script pour télécharger automatiquement les modèles locaux listés dans `model_list.txt`
- `backup.ps1` : script de sauvegarde (fichiers de configuration, et volumes Docker avec l'option `-IncludeVolumes`)
- `start.ps1`, `stop.ps1`, `restore.ps1` : scripts utilitaires pour la gestion de la stack

## Installation / Reconstruction sur une nouvelle machine

1. **Cloner le dépôt** :

   ```powershell
   git clone https://github.com/KinSushi/Claude-Local-Nexus.git
   cd Claude-Local-Nexus
   ```

2. **Créer le fichier `.env`** :

   ```powershell
   Copy-Item .env.example .env
   ```

   Puis éditez `.env` et renseignez vos vraies clés API.

3. **Démarrer la stack** :

   ```powershell
   docker compose up -d
   ```

4. **Télécharger les modèles locaux** :

   ```powershell
   .\update_local_models.ps1
   ```

5. **Synchroniser les modèles cloud** :

   ```powershell
   .\update_cloud_models.ps1
   ```

   Ce script interroge l'API officielle, filtre les modèles cloud accessibles avec votre clé, met à jour `cloud_models.txt` et la section `OLLAMA CLOUD` de `litellm_config.yaml`.

6. **Vérifier l'état** :

   ```powershell
   docker compose ps
   ```

7. **Tester le healthcheck** :

   ```powershell
   curl.exe --max-time 30 -H "Authorization: Bearer $($env:LITELLM_MASTER_KEY)" http://localhost:4000/health
   ```

## Configuration des clés API

Le fichier `.env` doit contenir :

```ini
LITELLM_MASTER_KEY=ma-cle-tres-secrete-2025
ANTHROPIC_API_KEY=sk-ant-...
OLLAMA_CLOUD_API_KEY=...
REDIS_PASSWORD=
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_HOST=https://cloud.langfuse.com
```

- **Anthropic** : depuis [console.anthropic.com](https://console.anthropic.com/)
- **Ollama Cloud** : depuis [ollama.com](https://ollama.com/) → Settings → API Keys
- **Langfuse** : depuis [cloud.langfuse.com](https://cloud.langfuse.com/) → projet → Settings → API Keys

## Mise à jour des modèles cloud

Les modèles cloud évoluent régulièrement. Pour maintenir votre configuration à jour :

```powershell
cd C:\local-llm-docker
.\update_cloud_models.ps1
```

Ce script :
- Interroge l'API officielle `https://ollama.com/api/tags`.
- Vérifie les modèles listés dans `cloud_models.txt`.
- Met à jour automatiquement `cloud_models.txt`.
- Régénère la section `OLLAMA CLOUD` de `litellm_config.yaml` avec `api_base: https://ollama.com`.

Vous pouvez l'exécuter manuellement ou le planifier (tâche Windows) pour une synchronisation régulière.

## Mise à jour des modèles locaux

Les modèles locaux sont listés dans `model_list.txt`. Pour télécharger automatiquement ceux qui manquent dans le conteneur Ollama, utilisez le script **`update_local_models.ps1`** :

```powershell
cd C:\local-llm-docker
.\update_local_models.ps1           # Télécharge uniquement les modèles absents
.\update_local_models.ps1 -Force    # Force le retéléchargement de tous les modèles
```

Ce script vérifie l'état du conteneur, ignore les commentaires/lignes vides, et fournit un récapitulatif clair.

## Sauvegarde et restauration

### Sauvegarde automatisée

Pour sauvegarder les fichiers de configuration uniquement :

```powershell
.\backup.ps1
```

Pour sauvegarder également les volumes Docker (données PostgreSQL, modèles Ollama, cache Redis) :

```powershell
.\backup.ps1 -IncludeVolumes
```

Les sauvegardes sont horodatées et placées dans `C:\backups`.

### Restauration des volumes

```powershell
# Créer les volumes vides
docker volume create local-llm-docker_pgdata
docker volume create local-llm-docker_ollama_data
docker volume create local-llm-docker_redis_data

# Restaurer
docker run --rm -v local-llm-docker_pgdata:/volume -v C:\backups:/backup alpine sh -c "cd /volume && tar xzf /backup/pgdata.tar.gz"
docker run --rm -v local-llm-docker_ollama_data:/volume -v C:\backups:/backup alpine sh -c "cd /volume && tar xzf /backup/ollama_data.tar.gz"
docker run --rm -v local-llm-docker_redis_data:/volume -v C:\backups:/backup alpine sh -c "cd /volume && tar xzf /backup/redis_data.tar.gz"
```

## Tester l'API

> **Note** : les modèles cloud utilisent désormais `api_base: https://ollama.com` et sont appelés directement avec la clé `OLLAMA_CLOUD_API_KEY`. Ils ne passent plus par le conteneur Ollama local.

### Chat avec un modèle local (ex: `ultime-recourse-local`)

```powershell
$headers = @{ "Authorization" = "Bearer $($env:LITELLM_MASTER_KEY)" }
$bodyJson = @{ model = "ultime-recourse-local"; messages = @(@{ role = "user"; content = "Bonjour" }) } | ConvertTo-Json -Depth 5
$bodyBytes = [System.Text.Encoding]::UTF8.GetBytes($bodyJson)
Invoke-RestMethod -Uri "http://localhost:4000/v1/chat/completions" -Method Post -Headers $headers -ContentType "application/json; charset=utf-8" -Body $bodyBytes
```

### Chat avec le modèle cloud gratuit (ex: `gpt-oss-20b-cloud`)

```powershell
$bodyJson = @{ model = "gpt-oss-20b-cloud"; messages = @(@{ role = "user"; content = "Bonjour" }) } | ConvertTo-Json -Depth 5
$bodyBytes = [System.Text.Encoding]::UTF8.GetBytes($bodyJson)
Invoke-RestMethod -Uri "http://localhost:4000/v1/chat/completions" -Method Post -Headers $headers -ContentType "application/json; charset=utf-8" -Body $bodyBytes
```

### Utiliser Claude Code

Claude Code peut être connecté à votre proxy LiteLLM pour bénéficier des modèles locaux et cloud sans dépendre uniquement de l'API Anthropic.

#### Configuration

Dans votre terminal PowerShell, avant de lancer `claude`, définissez les variables d'environnement :

```powershell
$env:ANTHROPIC_BASE_URL = "http://localhost:4000"
$env:ANTHROPIC_AUTH_TOKEN = $env:LITELLM_MASTER_KEY   # ou la clé maîtresse directement
```

#### Lancer Claude Code

```powershell
claude
```

Toutes les requêtes seront envoyées à votre proxy LiteLLM, qui utilisera le routeur adaptatif (`adaptive-router`) pour choisir le meilleur modèle parmi les modèles locaux et cloud disponibles.

#### Utiliser un modèle spécifique

Vous pouvez forcer l'utilisation d'un modèle précis avec l'option `--model` :

- Modèle local léger :  
  ```powershell
  claude --model "ultime-recourse-local"
  ```
- Modèle cloud gratuit :  
  ```powershell
  claude --model "gpt-oss-20b-cloud"
  ```
- Modèle Anthropic (si clé API disponible) :  
  ```powershell
  claude --model "claude-sonnet-5"
  ```

#### Vérifier que ça passe par LiteLLM

Ouvrez un second terminal et consultez les logs :

```powershell
docker logs litellm-proxy -f
```

Vous verrez les requêtes de Claude Code arriver sur le proxy.

## Commandes utiles

```powershell
docker compose up -d                 # Démarrer tous les services
docker compose down                  # Arrêter et supprimer les conteneurs (garde les volumes)
docker compose down -v               # Arrêter et supprimer conteneurs + volumes (données perdues)
docker compose logs -f litellm       # Suivre les logs de LiteLLM
docker exec -it ollama-server /bin/sh # Shell dans le conteneur Ollama
```

## Dépannage

- **Port occupé** : changez le port hôte dans `docker-compose.yml`.
- **Conteneur ne démarre pas** : `docker logs <service>`.
- **Erreur 401** : vérifiez l'en-tête `Authorization: Bearer ...`.
- **Modèle local en erreur** : vérifiez `docker exec ollama-server ollama list`, sinon `ollama pull`.
- **Modèle cloud 401** : vérifiez `OLLAMA_CLOUD_API_KEY` ou `ANTHROPIC_API_KEY`.
- **Langfuse ne remonte pas** : vérifiez `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_HOST`.

---

## Licence

Ce projet est destiné à un usage personnel. Adaptez selon vos besoins.

**Auteur** : KinSushi – Enzo – Sovralys LLC