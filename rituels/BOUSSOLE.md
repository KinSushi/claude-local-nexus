# Boussole

> Index du dépôt, généré par `python scripts/nexus_boussole.py` le 2026-08-29 12:10.
> Localiser sans chercher, vérifier sans commande jetable.
> `.env` en est volontairement absent : ni indexé, ni empreinté.

| Rôle | Fichier | Objet | Taille | Modifié | SHA-256 |
|---|---|---|---|---|---|
| Contrat | `.claude/CLAUDE.md` | Contrat d'exploitation de la plateforme | 62 Ko | 2026-08-29 | `eefdcf5c79d53511` |
| Contrat | `AGENTS.md` | Contrat d'agent universel | 3 Ko | 2026-08-28 | `e258b3cc90de2a14` |
| Infrastructure | `docker-compose.yml` | Définition des services et volumes | 4 Ko | 2026-08-29 | `d60af63eaaa60b59` |
| Configuration | `.env.example` | Modèle de fichier d'environnement | 3 Ko | 2026-08-29 | `f70ad0c51a6d67ab` |
| Configuration | `litellm_config.yaml` | Modèles, routeurs, fallbacks — mi-généré, mi-manuel | 35 Ko | 2026-08-29 | `83cfc30789cc46d8` |
| Inventaire | `cloud_models.txt` | Catalogue Ollama Cloud, généré, droits annotés | 551 o | 2026-08-29 | `058c58ca406ff748` |
| Inventaire | `model_list.txt` | Modèles locaux à télécharger | 583 o | 2026-08-27 | `7ad5bf3484b00918` |
| Pont | `.mcp.json` | Déclaration du serveur MCP pour Claude Code | 311 o | 2026-08-29 | `3d8aee915dd1ab43` |
| Pont | `Set-ClaudeModel.ps1` | Choix explicite du mode d'exécution de Claude Code | 10 Ko | 2026-08-29 | `e22aede9ce5d3331` |
| Pont | `tools/nexus-mcp/server.js` | Serveur MCP : les modèles comme outils | 62 Ko | 2026-08-29 | `3f041a0567cad3ec` |
| Génération | `scripts/Update-NexusModels.ps1` | Orchestrateur de mise à jour | 7 Ko | 2026-08-29 | `4bc2d37e81a479fa` |
| Génération | `scripts/nexus_generate.py` | Régénère les zones AUTOGEN | 33 Ko | 2026-08-29 | `896c91105886be35` |
| Vérification | `scripts/Test-NexusConfig.ps1` | Enveloppe du validateur | 1 Ko | 2026-08-29 | `ffb1d223bd5b23d5` |
| Vérification | `scripts/Test-NexusSmoke.ps1` | Smoke test runtime | 5 Ko | 2026-08-29 | `8d78c4db6071a802` |
| Vérification | `scripts/nexus_capability.py` | Profil matériel et verdict par modèle | 18 Ko | 2026-08-29 | `9f1fb5052abb98d3` |
| Vérification | `scripts/nexus_mcp_probe.py` | Sonde les outils du pont MCP | 4 Ko | 2026-08-29 | `848a574aea6a4f49` |
| Vérification | `scripts/nexus_test.py` | Suite forward / reverse / policy / code | 48 Ko | 2026-08-29 | `24d2ed49be58e341` |
| Vérification | `scripts/nexus_validate.py` | Intégrité — bloque tout redémarrage douteux | 16 Ko | 2026-08-29 | `cd2a9c9f5a90d410` |
| Migration | `scripts/nexus_migration_plan.py` | Plan de sortie des modèles hors de Docker | 9 Ko | 2026-08-29 | `cde341e659bd1a23` |
| Migration | `scripts/nexus_switch_engine.py` | Bascule le moteur Docker ↔ hôte | 7 Ko | 2026-08-29 | `626b4224c6990eb3` |
| Automatisation | `scripts/Register-NexusAutoUpdate.ps1` | Tâche planifiée quotidienne | 5 Ko | 2026-08-29 | `de88739da6a7970a` |
| Exploitation | `scripts/backup.ps1` | Sauvegarde configuration et volumes | 4 Ko | 2026-08-29 | `fe3343b015ad4e70` |
| Exploitation | `scripts/restore.ps1` | Restauration | 2 Ko | 2026-08-27 | `c28037d99bfe2eab` |
| Exploitation | `scripts/start.ps1` | Démarrage de la pile | 2 Ko | 2026-08-27 | `04cbd12224ec63e5` |
| Exploitation | `scripts/stop.ps1` | Arrêt de la pile | 929 o | 2026-08-27 | `c9a0c2e767975eb5` |
| Rituel | `rituels/BOUSSOLE.md` | Cet index | 24 Ko | 2026-08-29 | `c5973dcb667bf3cf` |
| Rituel | `rituels/CHECKLIST_COCKPIT.MD` | Sujets ouverts | 14 Ko | 2026-08-29 | `013b5b576bee7efa` |
| Rituel | `rituels/PROGRESS.md` | Historique des décisions et des erreurs | 9 Ko | 2026-08-29 | `12e90e1e05c99d5c` |
| Rituel | `rituels/RESUME.ps1` | Reprise de session | 3 Ko | 2026-08-29 | `7714dfe8b4c7c548` |
| Rituel | `rituels/STATE.md` | État mesuré — généré, ne pas éditer | 3 Ko | 2026-08-29 | `17b9752787e0494a` |
| Rituel | `scripts/nexus_boussole.py` | Régénère cette boussole | 8 Ko | 2026-08-29 | `24acb7c304f608f5` |
| Rituel | `scripts/nexus_state.py` | Régénère STATE.md par mesure | 8 Ko | 2026-08-29 | `6c9ef6d86143d6fe` |
| Documentation | `README.md` | Vue d'ensemble et installation | 11 Ko | 2026-08-29 | `1d896517383e8a2e` |
| Documentation | `docs/pont-local-abonnement.md` | Associer modèles locaux et abonnement | 15 Ko | 2026-08-29 | `c99bdaf7c7ad0b78` |
| Architecture | `.claude/worktrees/agent-a653df9057bc132d9/.claude/CLAUDE.md` | — | 62 Ko | 2026-08-29 | `eefdcf5c79d53511` |
| Architecture | `.claude/worktrees/agent-a653df9057bc132d9/.env.example` | — | 2 Ko | 2026-08-29 | `c18e773b896c3408` |
| Architecture | `.claude/worktrees/agent-a653df9057bc132d9/.git` | — | 67 o | 2026-08-29 | `efe9bca285aed023` |
| Architecture | `.claude/worktrees/agent-a653df9057bc132d9/.gitattributes` | — | 1 Ko | 2026-08-29 | `b6b90b72d26b36e7` |
| Architecture | `.claude/worktrees/agent-a653df9057bc132d9/.gitignore` | — | 153 o | 2026-08-29 | `e535aa660e5d2af8` |
| Architecture | `.claude/worktrees/agent-a653df9057bc132d9/.mcp.json` | — | 311 o | 2026-08-29 | `3d8aee915dd1ab43` |
| Architecture | `.claude/worktrees/agent-a653df9057bc132d9/AGENTS.md` | — | 3 Ko | 2026-08-29 | `e21cd2bae8539810` |
| Architecture | `.claude/worktrees/agent-a653df9057bc132d9/LICENSE` | — | 34 Ko | 2026-08-29 | `0d96a4ff68ad6d4b` |
| Architecture | `.claude/worktrees/agent-a653df9057bc132d9/README.md` | — | 11 Ko | 2026-08-29 | `5636d3b99b61d76b` |
| Architecture | `.claude/worktrees/agent-a653df9057bc132d9/Set-ClaudeModel.ps1` | — | 9 Ko | 2026-08-29 | `4a0081170aa41da1` |
| Architecture | `.claude/worktrees/agent-a653df9057bc132d9/Start-Claude.ps1` | — | 6 Ko | 2026-08-29 | `48d9c212d56e26a2` |
| Architecture | `.claude/worktrees/agent-a653df9057bc132d9/cloud_models.txt` | Note d'architecture | 551 o | 2026-08-29 | `c410c5b7d084ea58` |
| Architecture | `.claude/worktrees/agent-a653df9057bc132d9/docker-compose.yml` | — | 3 Ko | 2026-08-29 | `cc1352d7cc8182db` |
| Architecture | `.claude/worktrees/agent-a653df9057bc132d9/docs/architecture/Agent-Contracts.txt` | Note d'architecture | 585 o | 2026-08-29 | `b875ea87d451437e` |
| Architecture | `.claude/worktrees/agent-a653df9057bc132d9/docs/architecture/Agent-Trace-Schema.txt` | Note d'architecture | 368 o | 2026-08-29 | `60dfa91be8c51587` |
| Architecture | `.claude/worktrees/agent-a653df9057bc132d9/docs/architecture/Agent-loops.txt` | Note d'architecture | 1 Ko | 2026-08-29 | `d34e49715af5ea16` |
| Architecture | `.claude/worktrees/agent-a653df9057bc132d9/docs/architecture/Architecture_documentaire.md` | — | 1 Ko | 2026-08-29 | `dbafe79f6b13d520` |
| Architecture | `.claude/worktrees/agent-a653df9057bc132d9/docs/architecture/Bayesian-routing-evolution-future.txt` | Note d'architecture | 618 o | 2026-08-29 | `24d3d9a50abec226` |
| Architecture | `.claude/worktrees/agent-a653df9057bc132d9/docs/architecture/Cache-policy-avancée.txt` | Note d'architecture | 425 o | 2026-08-29 | `206024bed62b61e8` |
| Architecture | `.claude/worktrees/agent-a653df9057bc132d9/docs/architecture/Confidence-uncertainty.txt` | Note d'architecture | 279 o | 2026-08-29 | `ff0c0a41673128cc` |
| Architecture | `.claude/worktrees/agent-a653df9057bc132d9/docs/architecture/Conformance-Tests.txt` | Note d'architecture | 512 o | 2026-08-29 | `4a02efab17780b0b` |
| Architecture | `.claude/worktrees/agent-a653df9057bc132d9/docs/architecture/Context-cache.txt` | Note d'architecture | 159 o | 2026-08-29 | `c93d7fdfcd0b9416` |
| Architecture | `.claude/worktrees/agent-a653df9057bc132d9/docs/architecture/Cost-budget.txt` | Note d'architecture | 345 o | 2026-08-29 | `54fd737f827ea6ea` |
| Architecture | `.claude/worktrees/agent-a653df9057bc132d9/docs/architecture/Drift-detection.txt` | Note d'architecture | 342 o | 2026-08-29 | `1f7ae47c7210cfab` |
| Architecture | `.claude/worktrees/agent-a653df9057bc132d9/docs/architecture/Escalation-policy.txt` | Note d'architecture | 191 o | 2026-08-29 | `87dcc4310f8ece9e` |
| Architecture | `.claude/worktrees/agent-a653df9057bc132d9/docs/architecture/Event-log.txt` | Note d'architecture | 548 o | 2026-08-29 | `68646bac4773800d` |
| Architecture | `.claude/worktrees/agent-a653df9057bc132d9/docs/architecture/Final-target-architecture.txt` | Note d'architecture | 6 Ko | 2026-08-29 | `1446371c35602e75` |
| Architecture | `.claude/worktrees/agent-a653df9057bc132d9/docs/architecture/Latency-budget.txt` | Note d'architecture | 182 o | 2026-08-29 | `ff1be5b25771226a` |
| Architecture | `.claude/worktrees/agent-a653df9057bc132d9/docs/architecture/MCP-external-tool-layer.txt` | Note d'architecture | 483 o | 2026-08-29 | `59b701e6199307e2` |
| Architecture | `.claude/worktrees/agent-a653df9057bc132d9/docs/architecture/MCP-ne-doit-pas-bypasser-la-policy.txt` | Note d'architecture | 233 o | 2026-08-29 | `e38a1c1a96579b45` |
| Architecture | `.claude/worktrees/agent-a653df9057bc132d9/docs/architecture/Mission-P0.txt` | Note d'architecture | 21 Ko | 2026-08-29 | `8d10f595e46e354e` |
| Architecture | `.claude/worktrees/agent-a653df9057bc132d9/docs/architecture/Model-lifecycle-automation.txt` | Note d'architecture | 221 o | 2026-08-29 | `b72cc394c5e1eef5` |
| Architecture | `.claude/worktrees/agent-a653df9057bc132d9/docs/architecture/Multi-agent-orchestration.txt` | Note d'architecture | 943 o | 2026-08-29 | `187f0bc261b6d7b9` |
| Architecture | `.claude/worktrees/agent-a653df9057bc132d9/docs/architecture/Policy-as-code.txt` | Note d'architecture | 309 o | 2026-08-29 | `cc77a6e330d719a1` |
| Architecture | `.claude/worktrees/agent-a653df9057bc132d9/docs/architecture/Prompt-registry.txt` | Note d'architecture | 311 o | 2026-08-29 | `a9ded1ba472626e0` |
| Architecture | `.claude/worktrees/agent-a653df9057bc132d9/docs/architecture/README.md` | — | 6 Ko | 2026-08-29 | `a40c5bd466a8691f` |
| Architecture | `.claude/worktrees/agent-a653df9057bc132d9/docs/architecture/Reproductible-execution.txt` | Note d'architecture | 327 o | 2026-08-29 | `2cfbe21e85bfd8a7` |
| Architecture | `.claude/worktrees/agent-a653df9057bc132d9/docs/architecture/Router-versioning.txt` | Note d'architecture | 279 o | 2026-08-29 | `22ebe5fbf5a64f9c` |
| Architecture | `.claude/worktrees/agent-a653df9057bc132d9/docs/architecture/Routing-unit-tests.txt` | Note d'architecture | 476 o | 2026-08-29 | `8eaf35ef024778b9` |
| Architecture | `.claude/worktrees/agent-a653df9057bc132d9/docs/architecture/SKILLS.txt` | Note d'architecture | 2 Ko | 2026-08-29 | `58e8945d605c42e7` |
| Architecture | `.claude/worktrees/agent-a653df9057bc132d9/docs/architecture/Scientific-quantitative-evaluation-layer.txt` | Note d'architecture | 360 o | 2026-08-29 | `421a4a5360279315` |
| Architecture | `.claude/worktrees/agent-a653df9057bc132d9/docs/architecture/Secrets-Gateway.txt` | Note d'architecture | 378 o | 2026-08-29 | `d982298b4ec244e7` |
| Architecture | `.claude/worktrees/agent-a653df9057bc132d9/docs/architecture/Self-critique-contrôlée.txt` | Note d'architecture | 430 o | 2026-08-29 | `1b39c21a48488342` |
| Architecture | `.claude/worktrees/agent-a653df9057bc132d9/docs/architecture/Verification-Agent.txt` | Note d'architecture | 426 o | 2026-08-29 | `59aacf9aaa00a011` |
| Architecture | `.claude/worktrees/agent-a653df9057bc132d9/docs/architecture/agent-planner.txt` | Note d'architecture | 611 o | 2026-08-29 | `bd0b24926219de2f` |
| Architecture | `.claude/worktrees/agent-a653df9057bc132d9/docs/architecture/budget-aware-execution.txt` | Note d'architecture | 159 o | 2026-08-29 | `18584c952b55daf3` |
| Architecture | `.claude/worktrees/agent-a653df9057bc132d9/docs/architecture/execution-policy.yaml.txt` | Note d'architecture | 600 o | 2026-08-29 | `82c0e986d0d0ece7` |
| Architecture | `.claude/worktrees/agent-a653df9057bc132d9/docs/architecture/execution-profiles.txt` | Note d'architecture | 925 o | 2026-08-29 | `a21349561f810a99` |
| Architecture | `.claude/worktrees/agent-a653df9057bc132d9/docs/architecture/missions/INGEST-001-platform-integration.md` | — | 10 Ko | 2026-08-29 | `d88ef12b405cbc01` |
| Architecture | `.claude/worktrees/agent-a653df9057bc132d9/docs/architecture/model-registry.yaml` | — | 2 Ko | 2026-08-29 | `7a10ad2d1364a1f2` |
| Architecture | `.claude/worktrees/agent-a653df9057bc132d9/docs/architecture/policies/execution-policy.yaml` | — | 0 o | 2026-08-29 | `e3b0c44298fc1c14` |
| Architecture | `.claude/worktrees/agent-a653df9057bc132d9/docs/architecture/provider-registry.txt` | Note d'architecture | 757 o | 2026-08-29 | `ffe40ce4ae1ea45a` |
| Architecture | `.claude/worktrees/agent-a653df9057bc132d9/docs/architecture/tool-registry.txt` | Note d'architecture | 421 o | 2026-08-29 | `90ac2dd86d2ec601` |
| Architecture | `.claude/worktrees/agent-a653df9057bc132d9/docs/pont-local-abonnement.md` | — | 15 Ko | 2026-08-29 | `55063ec33846b031` |
| Architecture | `.claude/worktrees/agent-a653df9057bc132d9/docs/set-claude-model.md` | — | 3 Ko | 2026-08-29 | `43c15596721de2c3` |
| Architecture | `.claude/worktrees/agent-a653df9057bc132d9/litellm_config.yaml` | — | 35 Ko | 2026-08-29 | `6824305bbff60f2f` |
| Architecture | `.claude/worktrees/agent-a653df9057bc132d9/model_list.txt` | Note d'architecture | 545 o | 2026-08-29 | `940659862db4f87c` |
| Architecture | `.claude/worktrees/agent-a653df9057bc132d9/rituels/BOUSSOLE.csv` | — | 7 Ko | 2026-08-29 | `1659e5e93800fb29` |
| Architecture | `.claude/worktrees/agent-a653df9057bc132d9/rituels/BOUSSOLE.md` | — | 10 Ko | 2026-08-29 | `639e85609993bfa0` |
| Architecture | `.claude/worktrees/agent-a653df9057bc132d9/rituels/CHECKLIST_COCKPIT.MD` | — | 14 Ko | 2026-08-29 | `8366a41b25f80861` |
| Architecture | `.claude/worktrees/agent-a653df9057bc132d9/rituels/PROGRESS.md` | — | 7 Ko | 2026-08-29 | `62fdc016bd80f901` |
| Architecture | `.claude/worktrees/agent-a653df9057bc132d9/rituels/README.md` | — | 421 o | 2026-08-29 | `614056d5f2a7977d` |
| Architecture | `.claude/worktrees/agent-a653df9057bc132d9/rituels/RESUME.ps1` | — | 3 Ko | 2026-08-29 | `7714dfe8b4c7c548` |
| Architecture | `.claude/worktrees/agent-a653df9057bc132d9/rituels/STATE.md` | — | 3 Ko | 2026-08-29 | `b04694d22c5dac8a` |
| Architecture | `.claude/worktrees/agent-a653df9057bc132d9/scripts/Initialize-Nexus.ps1` | — | 7 Ko | 2026-08-29 | `2ad5c08de5db3923` |
| Architecture | `.claude/worktrees/agent-a653df9057bc132d9/scripts/Register-NexusAutoUpdate.ps1` | — | 5 Ko | 2026-08-29 | `de88739da6a7970a` |
| Architecture | `.claude/worktrees/agent-a653df9057bc132d9/scripts/Test-NexusConfig.ps1` | — | 1 Ko | 2026-08-29 | `ffb1d223bd5b23d5` |
| Architecture | `.claude/worktrees/agent-a653df9057bc132d9/scripts/Test-NexusSmoke.ps1` | — | 5 Ko | 2026-08-29 | `8d78c4db6071a802` |
| Architecture | `.claude/worktrees/agent-a653df9057bc132d9/scripts/Update-NexusModels.ps1` | — | 7 Ko | 2026-08-29 | `4bc2d37e81a479fa` |
| Architecture | `.claude/worktrees/agent-a653df9057bc132d9/scripts/backup.ps1` | — | 3 Ko | 2026-08-29 | `3e5897a314ee325e` |
| Architecture | `.claude/worktrees/agent-a653df9057bc132d9/scripts/nexus_boussole.py` | — | 8 Ko | 2026-08-29 | `20b7f3ea523995e3` |
| Architecture | `.claude/worktrees/agent-a653df9057bc132d9/scripts/nexus_capability.py` | — | 14 Ko | 2026-08-29 | `e469bf90814f06d1` |
| Architecture | `.claude/worktrees/agent-a653df9057bc132d9/scripts/nexus_generate.py` | — | 31 Ko | 2026-08-29 | `fa0302760b7d2370` |
| Architecture | `.claude/worktrees/agent-a653df9057bc132d9/scripts/nexus_mcp_probe.py` | — | 4 Ko | 2026-08-29 | `848a574aea6a4f49` |
| Architecture | `.claude/worktrees/agent-a653df9057bc132d9/scripts/nexus_migration_plan.py` | — | 8 Ko | 2026-08-29 | `99fb781c2e2f8e4b` |
| Architecture | `.claude/worktrees/agent-a653df9057bc132d9/scripts/nexus_preserve.py` | — | 14 Ko | 2026-08-29 | `fdc484a0d862a348` |
| Architecture | `.claude/worktrees/agent-a653df9057bc132d9/scripts/nexus_savings.py` | — | 10 Ko | 2026-08-29 | `f26e15f4000f218a` |
| Architecture | `.claude/worktrees/agent-a653df9057bc132d9/scripts/nexus_state.py` | — | 8 Ko | 2026-08-29 | `eff262d1bdcab333` |
| Architecture | `.claude/worktrees/agent-a653df9057bc132d9/scripts/nexus_switch_engine.py` | — | 7 Ko | 2026-08-29 | `5d3aeb489c54f9a5` |
| Architecture | `.claude/worktrees/agent-a653df9057bc132d9/scripts/nexus_test.py` | — | 45 Ko | 2026-08-29 | `34d63912c310a1cb` |
| Architecture | `.claude/worktrees/agent-a653df9057bc132d9/scripts/nexus_validate.py` | — | 13 Ko | 2026-08-29 | `ab15e88b93f1a5a2` |
| Architecture | `.claude/worktrees/agent-a653df9057bc132d9/scripts/restore.ps1` | — | 2 Ko | 2026-08-29 | `ad1c750a63ffa82d` |
| Architecture | `.claude/worktrees/agent-a653df9057bc132d9/scripts/start.ps1` | — | 2 Ko | 2026-08-29 | `3d9c527bc12bae4a` |
| Architecture | `.claude/worktrees/agent-a653df9057bc132d9/scripts/stop.ps1` | — | 909 o | 2026-08-29 | `9e79210f41911f95` |
| Architecture | `.claude/worktrees/agent-a653df9057bc132d9/scripts/update_cloud_models.ps1` | — | 6 Ko | 2026-08-29 | `41078ab50423d589` |
| Architecture | `.claude/worktrees/agent-a653df9057bc132d9/scripts/update_local_models.ps1` | — | 4 Ko | 2026-08-29 | `ee795cabf6f53ae6` |
| Architecture | `.claude/worktrees/agent-a653df9057bc132d9/tools/nexus-mcp/server.js` | — | 51 Ko | 2026-08-29 | `d23d0d108370bad2` |
| Architecture | `.gitattributes` | — | 1 Ko | 2026-08-29 | `b6b90b72d26b36e7` |
| Architecture | `.github/workflows/verification.yml` | — | 4 Ko | 2026-08-29 | `db4a9bf85a4f0b60` |
| Architecture | `.gitignore` | — | 268 o | 2026-08-29 | `923e51415fe6fed7` |
| Architecture | `LICENSE` | — | 34 Ko | 2026-08-29 | `0d96a4ff68ad6d4b` |
| Architecture | `Start-Claude.ps1` | — | 6 Ko | 2026-08-29 | `48d9c212d56e26a2` |
| Architecture | `docker-compose.gpu.yml` | — | 941 o | 2026-08-29 | `d8cb0679e22c2e51` |
| Architecture | `docs/architecture/Agent-Contracts.txt` | Note d'architecture | 617 o | 2026-08-28 | `44a7e50923e522fd` |
| Architecture | `docs/architecture/Agent-Trace-Schema.txt` | Note d'architecture | 395 o | 2026-08-28 | `cd92e5a2c6047458` |
| Architecture | `docs/architecture/Agent-loops.txt` | Note d'architecture | 1 Ko | 2026-08-28 | `a626486bce89938f` |
| Architecture | `docs/architecture/Architecture_documentaire.md` | — | 1 Ko | 2026-08-28 | `bf30d80a4d8a67e9` |
| Architecture | `docs/architecture/Bayesian-routing-evolution-future.txt` | Note d'architecture | 665 o | 2026-08-28 | `6e04cd1f0483c864` |
| Architecture | `docs/architecture/Cache-policy-avancée.txt` | Note d'architecture | 446 o | 2026-08-28 | `cbedaf12ff4b3053` |
| Architecture | `docs/architecture/Confidence-uncertainty.txt` | Note d'architecture | 294 o | 2026-08-28 | `ad8d08631fdbd807` |
| Architecture | `docs/architecture/Conformance-Tests.txt` | Note d'architecture | 529 o | 2026-08-28 | `2573719ab4ee8fcb` |
| Architecture | `docs/architecture/Context-cache.txt` | Note d'architecture | 169 o | 2026-08-28 | `5c56aa801824dbc6` |
| Architecture | `docs/architecture/Cost-budget.txt` | Note d'architecture | 356 o | 2026-08-28 | `58aa3bfae529b102` |
| Architecture | `docs/architecture/Drift-detection.txt` | Note d'architecture | 369 o | 2026-08-28 | `f6a370279e81393e` |
| Architecture | `docs/architecture/Escalation-policy.txt` | Note d'architecture | 212 o | 2026-08-28 | `806f7173fbb9112e` |
| Architecture | `docs/architecture/Event-log.txt` | Note d'architecture | 578 o | 2026-08-28 | `2aadcf3964497d83` |
| Architecture | `docs/architecture/Final-target-architecture.txt` | Note d'architecture | 6 Ko | 2026-08-28 | `eb6ec36a7a8d4ee2` |
| Architecture | `docs/architecture/Latency-budget.txt` | Note d'architecture | 190 o | 2026-08-28 | `f75fafbdd76ecb0e` |
| Architecture | `docs/architecture/MCP-external-tool-layer.txt` | Note d'architecture | 515 o | 2026-08-28 | `5f7219a3f58eaf9b` |
| Architecture | `docs/architecture/MCP-ne-doit-pas-bypasser-la-policy.txt` | Note d'architecture | 249 o | 2026-08-28 | `18b5c3df75d9a7d7` |
| Architecture | `docs/architecture/Mission-P0.txt` | Note d'architecture | 22 Ko | 2026-08-28 | `391c0394b7712238` |
| Architecture | `docs/architecture/Model-lifecycle-automation.txt` | Note d'architecture | 243 o | 2026-08-28 | `96caae627bda0116` |
| Architecture | `docs/architecture/Multi-agent-orchestration.txt` | Note d'architecture | 974 o | 2026-08-28 | `c75d80063f115ce4` |
| Architecture | `docs/architecture/Policy-as-code.txt` | Note d'architecture | 329 o | 2026-08-28 | `e1bfd525e738057c` |
| Architecture | `docs/architecture/Prompt-registry.txt` | Note d'architecture | 329 o | 2026-08-28 | `306b5c96dcf1b63f` |
| Architecture | `docs/architecture/README.md` | — | 6 Ko | 2026-08-29 | `ccb68aed4113a6b4` |
| Architecture | `docs/architecture/Reproductible-execution.txt` | Note d'architecture | 349 o | 2026-08-28 | `83527ed316590ac0` |
| Architecture | `docs/architecture/Router-versioning.txt` | Note d'architecture | 294 o | 2026-08-28 | `47a980e9d0ca5f9f` |
| Architecture | `docs/architecture/Routing-unit-tests.txt` | Note d'architecture | 512 o | 2026-08-28 | `f0af939d3d90d215` |
| Architecture | `docs/architecture/SKILLS.txt` | Note d'architecture | 2 Ko | 2026-08-29 | `58e8945d605c42e7` |
| Architecture | `docs/architecture/Scientific-quantitative-evaluation-layer.txt` | Note d'architecture | 372 o | 2026-08-28 | `db4adee680ca3f04` |
| Architecture | `docs/architecture/Secrets-Gateway.txt` | Note d'architecture | 396 o | 2026-08-28 | `49ae4c63ae8930f3` |
| Architecture | `docs/architecture/Self-critique-contrôlée.txt` | Note d'architecture | 455 o | 2026-08-28 | `6f791cd036ba0a11` |
| Architecture | `docs/architecture/Verification-Agent.txt` | Note d'architecture | 457 o | 2026-08-28 | `1f2b1e54a026bc7c` |
| Architecture | `docs/architecture/agent-planner.txt` | Note d'architecture | 660 o | 2026-08-28 | `2f71f4d304a9ef18` |
| Architecture | `docs/architecture/budget-aware-execution.txt` | Note d'architecture | 174 o | 2026-08-28 | `96ba3ba260f488c9` |
| Architecture | `docs/architecture/execution-policy.yaml.txt` | Note d'architecture | 648 o | 2026-08-28 | `12b546689ff532ee` |
| Architecture | `docs/architecture/execution-profiles.txt` | Note d'architecture | 1000 o | 2026-08-28 | `80920407dbb14313` |
| Architecture | `docs/architecture/missions/INGEST-001-platform-integration.md` | — | 11 Ko | 2026-08-28 | `c3ee98341a74c6c2` |
| Architecture | `docs/architecture/model-registry.yaml` | — | 2 Ko | 2026-08-28 | `6db49ebeea993873` |
| Architecture | `docs/architecture/provider-registry.txt` | Note d'architecture | 820 o | 2026-08-28 | `3e34f998a514ce88` |
| Architecture | `docs/architecture/tool-registry.txt` | Note d'architecture | 451 o | 2026-08-28 | `54767d583d48cf93` |
| Architecture | `docs/set-claude-model.md` | — | 3 Ko | 2026-08-29 | `43c15596721de2c3` |
| Architecture | `model_list.host.txt` | Note d'architecture | 471 o | 2026-08-29 | `9dbc42c010b604af` |
| Architecture | `requirements.txt` | Note d'architecture | 12 o | 2026-08-29 | `71749243f84428fe` |
| Architecture | `rituels/BOUSSOLE.csv` | — | 20 Ko | 2026-08-29 | `11549d97b0d53fdc` |
| Architecture | `rituels/README.md` | — | 2 Ko | 2026-08-29 | `dac6503c1883887f` |
| Architecture | `rituels/RESTE-A-FAIRE.md` | — | 12 Ko | 2026-08-29 | `bc4c948befe40a94` |
| Architecture | `scripts/Initialize-Nexus.ps1` | — | 7 Ko | 2026-08-29 | `2ad5c08de5db3923` |
| Architecture | `scripts/nexus_preserve.py` | — | 15 Ko | 2026-08-29 | `bd3127c5de5f2093` |
| Architecture | `scripts/nexus_pull_host.py` | — | 6 Ko | 2026-08-29 | `867271d991c9bffa` |
| Architecture | `scripts/nexus_savings.py` | — | 10 Ko | 2026-08-29 | `ea65fac5a8d1231b` |
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
| Architecture | 142 |
| Obsolète | 2 |

---

État mesuré : [STATE.md](STATE.md) · Sujets ouverts : [CHECKLIST_COCKPIT.MD](CHECKLIST_COCKPIT.MD) · Historique : [PROGRESS.md](PROGRESS.md)
