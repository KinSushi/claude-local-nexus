# Boussole

> Index du dépôt, généré par `python scripts/nexus_boussole.py` le 2026-08-29 11:12.
> Localiser sans chercher, vérifier sans commande jetable.
> `.env` en est volontairement absent : ni indexé, ni empreinté.

| Rôle | Fichier | Objet | Taille | Modifié | SHA-256 |
|---|---|---|---|---|---|
| Contrat | `.claude/CLAUDE.md` | Contrat d'exploitation de la plateforme | 62 Ko | 2026-08-29 | `eefdcf5c79d53511` |
| Contrat | `AGENTS.md` | Contrat d'agent universel | 3 Ko | 2026-08-28 | `e258b3cc90de2a14` |
| Infrastructure | `docker-compose.yml` | Définition des services et volumes | 3 Ko | 2026-08-29 | `cc1352d7cc8182db` |
| Configuration | `.env.example` | Modèle de fichier d'environnement | 1 Ko | 2026-08-29 | `759f762282fd007a` |
| Configuration | `litellm_config.yaml` | Modèles, routeurs, fallbacks — mi-généré, mi-manuel | 35 Ko | 2026-08-29 | `6824305bbff60f2f` |
| Inventaire | `cloud_models.txt` | Catalogue Ollama Cloud, généré, droits annotés | 551 o | 2026-08-29 | `2c1cfefd076d71ca` |
| Inventaire | `model_list.txt` | Modèles locaux à télécharger | 583 o | 2026-08-27 | `7ad5bf3484b00918` |
| Pont | `.mcp.json` | Déclaration du serveur MCP pour Claude Code | 311 o | 2026-08-29 | `3d8aee915dd1ab43` |
| Pont | `Set-ClaudeModel.ps1` | Choix explicite du mode d'exécution de Claude Code | 9 Ko | 2026-08-29 | `4a0081170aa41da1` |
| Pont | `tools/nexus-mcp/server.js` | Serveur MCP : les modèles comme outils | 51 Ko | 2026-08-29 | `d23d0d108370bad2` |
| Génération | `scripts/Update-NexusModels.ps1` | Orchestrateur de mise à jour | 7 Ko | 2026-08-29 | `4bc2d37e81a479fa` |
| Génération | `scripts/nexus_generate.py` | Régénère les zones AUTOGEN | 31 Ko | 2026-08-29 | `fa0302760b7d2370` |
| Vérification | `scripts/Test-NexusConfig.ps1` | Enveloppe du validateur | 1 Ko | 2026-08-29 | `ffb1d223bd5b23d5` |
| Vérification | `scripts/Test-NexusSmoke.ps1` | Smoke test runtime | 5 Ko | 2026-08-29 | `8d78c4db6071a802` |
| Vérification | `scripts/nexus_capability.py` | Profil matériel et verdict par modèle | 14 Ko | 2026-08-29 | `e469bf90814f06d1` |
| Vérification | `scripts/nexus_mcp_probe.py` | Sonde les outils du pont MCP | 4 Ko | 2026-08-29 | `848a574aea6a4f49` |
| Vérification | `scripts/nexus_test.py` | Suite forward / reverse / policy / code | 45 Ko | 2026-08-29 | `34d63912c310a1cb` |
| Vérification | `scripts/nexus_validate.py` | Intégrité — bloque tout redémarrage douteux | 13 Ko | 2026-08-29 | `ab15e88b93f1a5a2` |
| Migration | `scripts/nexus_migration_plan.py` | Plan de sortie des modèles hors de Docker | 8 Ko | 2026-08-29 | `99fb781c2e2f8e4b` |
| Migration | `scripts/nexus_switch_engine.py` | Bascule le moteur Docker ↔ hôte | 7 Ko | 2026-08-29 | `5d3aeb489c54f9a5` |
| Automatisation | `scripts/Register-NexusAutoUpdate.ps1` | Tâche planifiée quotidienne | 5 Ko | 2026-08-29 | `de88739da6a7970a` |
| Exploitation | `scripts/backup.ps1` | Sauvegarde configuration et volumes | 3 Ko | 2026-08-29 | `11433411efb9cf79` |
| Exploitation | `scripts/restore.ps1` | Restauration | 2 Ko | 2026-08-27 | `c28037d99bfe2eab` |
| Exploitation | `scripts/start.ps1` | Démarrage de la pile | 2 Ko | 2026-08-27 | `04cbd12224ec63e5` |
| Exploitation | `scripts/stop.ps1` | Arrêt de la pile | 929 o | 2026-08-27 | `c9a0c2e767975eb5` |
| Rituel | `rituels/BOUSSOLE.md` | Cet index | 10 Ko | 2026-08-29 | `a1b8caec2ade3f7c` |
| Rituel | `rituels/CHECKLIST_COCKPIT.MD` | Sujets ouverts | 14 Ko | 2026-08-29 | `8366a41b25f80861` |
| Rituel | `rituels/PROGRESS.md` | Historique des décisions et des erreurs | 7 Ko | 2026-08-29 | `62fdc016bd80f901` |
| Rituel | `rituels/RESUME.ps1` | Reprise de session | 3 Ko | 2026-08-29 | `7714dfe8b4c7c548` |
| Rituel | `rituels/STATE.md` | État mesuré — généré, ne pas éditer | 3 Ko | 2026-08-29 | `b04694d22c5dac8a` |
| Rituel | `scripts/nexus_boussole.py` | Régénère cette boussole | 8 Ko | 2026-08-29 | `20b7f3ea523995e3` |
| Rituel | `scripts/nexus_state.py` | Régénère STATE.md par mesure | 8 Ko | 2026-08-29 | `eff262d1bdcab333` |
| Documentation | `README.md` | Vue d'ensemble et installation | 13 Ko | 2026-08-29 | `93acc3010a982c7e` |
| Documentation | `docs/pont-local-abonnement.md` | Associer modèles locaux et abonnement | 15 Ko | 2026-08-29 | `55063ec33846b031` |
| Architecture | `.gitignore` | — | 153 o | 2026-08-29 | `e535aa660e5d2af8` |
| Architecture | `Agent-Contracts.txt` | Note d'architecture | 617 o | 2026-08-28 | `44a7e50923e522fd` |
| Architecture | `Agent-Trace-Schema.txt` | Note d'architecture | 395 o | 2026-08-28 | `cd92e5a2c6047458` |
| Architecture | `Agent-loops.txt` | Note d'architecture | 1 Ko | 2026-08-28 | `a626486bce89938f` |
| Architecture | `Architecture_documentaire.md` | — | 1 Ko | 2026-08-28 | `bf30d80a4d8a67e9` |
| Architecture | `Bayesian routing-évolution future.txt` | Note d'architecture | 665 o | 2026-08-28 | `6e04cd1f0483c864` |
| Architecture | `Cache-policy-avancée.txt` | Note d'architecture | 446 o | 2026-08-28 | `cbedaf12ff4b3053` |
| Architecture | `Confidence-uncertainty.txt` | Note d'architecture | 294 o | 2026-08-28 | `ad8d08631fdbd807` |
| Architecture | `Conformance-Tests.txt` | Note d'architecture | 529 o | 2026-08-28 | `2573719ab4ee8fcb` |
| Architecture | `Context-cache.txt` | Note d'architecture | 169 o | 2026-08-28 | `5c56aa801824dbc6` |
| Architecture | `Cost-budget.txt` | Note d'architecture | 356 o | 2026-08-28 | `58aa3bfae529b102` |
| Architecture | `Drift-detection.txt` | Note d'architecture | 369 o | 2026-08-28 | `f6a370279e81393e` |
| Architecture | `Escalation-policy.txt` | Note d'architecture | 212 o | 2026-08-28 | `806f7173fbb9112e` |
| Architecture | `Event-log.txt` | Note d'architecture | 578 o | 2026-08-28 | `2aadcf3964497d83` |
| Architecture | `Final-target-architecture.txt` | Note d'architecture | 6 Ko | 2026-08-28 | `eb6ec36a7a8d4ee2` |
| Architecture | `Latency-budget.txt` | Note d'architecture | 190 o | 2026-08-28 | `f75fafbdd76ecb0e` |
| Architecture | `MCP-external-tool-layer.txt` | Note d'architecture | 515 o | 2026-08-28 | `5f7219a3f58eaf9b` |
| Architecture | `MCP-ne-doit-pas-bypasser-la-policy.txt` | Note d'architecture | 249 o | 2026-08-28 | `18b5c3df75d9a7d7` |
| Architecture | `Mission-P0.txt` | Note d'architecture | 22 Ko | 2026-08-28 | `391c0394b7712238` |
| Architecture | `Model-lifecycle-automation.txt` | Note d'architecture | 243 o | 2026-08-28 | `96caae627bda0116` |
| Architecture | `Multi-agent-orchestration.txt` | Note d'architecture | 974 o | 2026-08-28 | `c75d80063f115ce4` |
| Architecture | `Policy-as-code.txt` | Note d'architecture | 329 o | 2026-08-28 | `e1bfd525e738057c` |
| Architecture | `Prompt-registry.txt` | Note d'architecture | 329 o | 2026-08-28 | `306b5c96dcf1b63f` |
| Architecture | `README_Set-ClaudeModel.ps1.md` | — | 3 Ko | 2026-08-29 | `43c15596721de2c3` |
| Architecture | `Reproductible-execution.txt` | Note d'architecture | 349 o | 2026-08-28 | `83527ed316590ac0` |
| Architecture | `Router-versioning.txt` | Note d'architecture | 294 o | 2026-08-28 | `47a980e9d0ca5f9f` |
| Architecture | `Routing-unit-tests.txt` | Note d'architecture | 512 o | 2026-08-28 | `f0af939d3d90d215` |
| Architecture | `SKILLS.txt` | Note d'architecture | 2 Ko | 2026-08-28 | `d06d7d87828f6b17` |
| Architecture | `Scientific-quantitative-evaluation-layer.txt` | Note d'architecture | 372 o | 2026-08-28 | `db4adee680ca3f04` |
| Architecture | `Secrets-Gateway.txt` | Note d'architecture | 396 o | 2026-08-28 | `49ae4c63ae8930f3` |
| Architecture | `Self-critique-contrôlée.txt` | Note d'architecture | 455 o | 2026-08-28 | `6f791cd036ba0a11` |
| Architecture | `Start-Claude.ps1` | — | 6 Ko | 2026-08-29 | `48d9c212d56e26a2` |
| Architecture | `Verification-Agent.txt` | Note d'architecture | 457 o | 2026-08-28 | `1f2b1e54a026bc7c` |
| Architecture | `agent-planner.txt` | Note d'architecture | 660 o | 2026-08-28 | `2f71f4d304a9ef18` |
| Architecture | `budget-aware-execution.txt` | Note d'architecture | 174 o | 2026-08-28 | `96ba3ba260f488c9` |
| Architecture | `execution-policy.yaml.txt` | Note d'architecture | 648 o | 2026-08-28 | `12b546689ff532ee` |
| Architecture | `execution-profiles.txt` | Note d'architecture | 1000 o | 2026-08-28 | `80920407dbb14313` |
| Architecture | `missions/INGEST-001-platform-integration.md` | — | 11 Ko | 2026-08-28 | `c3ee98341a74c6c2` |
| Architecture | `model-registry.yaml` | — | 2 Ko | 2026-08-28 | `6db49ebeea993873` |
| Architecture | `policies/execution-policy.yaml` | — | 0 o | 2026-08-28 | `e3b0c44298fc1c14` |
| Architecture | `provider-registry.txt` | Note d'architecture | 820 o | 2026-08-28 | `3e34f998a514ce88` |
| Architecture | `rituels/BOUSSOLE.csv` | — | 8 Ko | 2026-08-29 | `0044e4d155c9ec19` |
| Architecture | `rituels/README.md` | — | 425 o | 2026-08-28 | `2a8987268987f831` |
| Architecture | `scripts/Initialize-Nexus.ps1` | — | 7 Ko | 2026-08-29 | `2ad5c08de5db3923` |
| Architecture | `scripts/nexus_preserve.py` | — | 14 Ko | 2026-08-29 | `fdc484a0d862a348` |
| Architecture | `scripts/nexus_savings.py` | — | 10 Ko | 2026-08-29 | `f26e15f4000f218a` |
| Architecture | `tool-registry.txt` | Note d'architecture | 451 o | 2026-08-28 | `54767d583d48cf93` |
| Obsolète | `scripts/update_cloud_models.ps1` | Remplacé — neutralisé par garde-fou | 6 Ko | 2026-08-29 | `41078ab50423d589` |
| Obsolète | `scripts/update_local_models.ps1` | Remplacé — neutralisé par garde-fou | 4 Ko | 2026-08-29 | `ee795cabf6f53ae6` |

## Répartition

| Rôle | Fichiers |
|---|---|
| Contrat | 2 |
| Infrastructure | 1 |
| Configuration | 2 |
| Inventaire | 2 |
| Pont | 3 |
| Génération | 2 |
| Vérification | 6 |
| Migration | 2 |
| Automatisation | 1 |
| Exploitation | 4 |
| Rituel | 7 |
| Documentation | 2 |
| Architecture | 47 |
| Obsolète | 2 |

---

État mesuré : [STATE.md](STATE.md) · Sujets ouverts : [CHECKLIST_COCKPIT.MD](CHECKLIST_COCKPIT.MD) · Historique : [PROGRESS.md](PROGRESS.md)
