# Claude-Local-Nexus

Plateforme locale d'orchestration IA – Dockerisée, souveraine, reproductible.

## Architecture
- **LiteLLM Proxy** : http://localhost:4000
- **Ollama** : http://localhost:11434 (interne Docker)
- **PostgreSQL**, **Redis**, **Langfuse** pour logs/cache/tracing.

## Modèles disponibles
- **Routeur global** : `adaptive-router` (choisit automatiquement)
- **Modèle cloud gratuit** : `gpt-oss-20b-cloud`
- **Modèles locaux** : `qwen3-coder-30b-local`, `gemma4-31b-local`, `qwen2.5-coder-32b-local`, etc.
- **Anthropic** (si clé valide) : `claude-sonnet-5`, `claude-opus-5`.

## Commandes utiles
```powershell
docker compose ps
docker compose up -d
docker compose down
docker logs litellm-proxy -f
docker exec ollama-server ollama list
.\update_local_models.ps1
.\update_cloud_models.ps1