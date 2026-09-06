# MANIFESTE DE QUARANTAINE

Genere le 2026-09-06T14:17:58Z par `outillage/nexus_quarantaine.py`.

| champ | valeur |
| --- | --- |
| racine | `C:\local-llm-docker` |
| arbre principal (source des originaux) | `C:/local-llm-docker` |
| dossier des worktrees | `C:\local-llm-docker\.claude\worktrees` |
| dossier de quarantaine | `C:\local-llm-docker\rituels\QUARANTAINE` |
| simulation | non |

## Comptes par population

- **SANS PREUVE** : 99 fichier(s) dans 30 worktree(s)
- **PREUVE PARTIELLE** : 58 fichier(s) dans 15 worktree(s)
- **PREUVE COMPLETE** : 0 fichier(s) dans 0 worktree(s)

## Audit

Pour auditer chaque fichier liste ci-dessous, suivre le gabarit `rituels/GABARIT_QUARANTAINE.md` (une ligne du tableau = un « Fichier » du gabarit). La colonne « original » dit si `_ORIGINAL/<chemin>` existe sous ce worktree en quarantaine : sans lui, aucun diff n'est possible et l'audit ne peut pas avoir lieu. « FICHIER NEUF » signifie qu'aucun original n'a ete trouve dans l'arbre principal -- attendu pour un fichier cree par l'agent, a verifier sinon. Les trois sections qui suivent separent les fichiers SANS aucun fichier de preuve, de ceux dont la preuve est PARTIELLE (fichier trouve, rubriques non toutes remplies) et de ceux dont la preuve est COMPLETE (huit rubriques remplies). Le critere porte sur la PRESENCE d'une reponse par rubrique, jamais sur son contenu, et aucune couleur n'est calculee ici : seule celle ECRITE PAR L'AUTEUR est rapportee, ou son absence (contrat §0.7.1).

## Resume

- worktrees examines : 45
- worktrees en erreur : 0
- fichiers au total : 157

## SANS PREUVE

### agent-a03ce1f4953606cae

- branche : `worktree-agent-a03ce1f4953606cae`
- tete : `196e761`
- retard sur main (commits non repris) : 116
- commits de l'agent au-dela de la base commune : 0
- fichier de preuve : AUCUN

| fichier | etat | octets | original |
| --- | --- | --- | --- |
| `outillage/competences/relire-code.txt` | non_commite ( M) | 1078 | oui (1078 octets) |
| `scripts/mesure_rendu_vide.py` | non_commite ( M) | 7932 | oui (7932 octets) |
| `outillage/nexus_doc.py` | non_commite ( M) | 40700 | oui (40700 octets) |

### agent-a0b07e433b871704d

- branche : `worktree-agent-a0b07e433b871704d`
- tete : `a149320`
- retard sur main (commits non repris) : 105
- commits de l'agent au-dela de la base commune : 0
- fichier de preuve : AUCUN

| fichier | etat | octets | original |
| --- | --- | --- | --- |
| `epreuves/epreuve_charge_derive.py` | non_commite (??) | 5256 | NON -- FICHIER NEUF |
| `epreuves/epreuve_reglages_moteur.py` | non_commite (??) | 4320 | NON -- FICHIER NEUF |
| `outillage/nexus_charge.py` | non_commite ( M) | 14270 | oui (8094 octets) |
| `scripts/nexus_reglages_moteur.py` | non_commite (??) | 20086 | NON -- FICHIER NEUF |
| `outillage/nexus_test.py` | non_commite ( M) | 172074 | oui (175825 octets) |

### agent-a0b2638a810ecfdd4

- branche : `worktree-agent-a0b2638a810ecfdd4`
- tete : `323aff4`
- retard sur main (commits non repris) : 115
- commits de l'agent au-dela de la base commune : 0
- fichier de preuve : AUCUN

| fichier | etat | octets | original |
| --- | --- | --- | --- |
| `outillage/nexus_doc.py` | non_commite ( M) | 40700 | oui (40700 octets) |

### agent-a13026bc69d52eaf0

- branche : `worktree-agent-a13026bc69d52eaf0`
- tete : `27bf53f`
- retard sur main (commits non repris) : 127
- commits de l'agent au-dela de la base commune : 0
- fichier de preuve : AUCUN

| fichier | etat | octets | original |
| --- | --- | --- | --- |
| `README.md` | non_commite ( M) | 15264 | oui (15567 octets) |
| `UTILISER_NEXUS.md` | non_commite ( M) | 3859 | oui (4079 octets) |
| `outillage/nexus_doc.py` | non_commite ( M) | 40700 | oui (40700 octets) |

### agent-a1b41eff010c12245

- branche : `worktree-agent-a1b41eff010c12245`
- tete : `5701a60`
- retard sur main (commits non repris) : 113
- commits de l'agent au-dela de la base commune : 0
- fichier de preuve : AUCUN

| fichier | etat | octets | original |
| --- | --- | --- | --- |
| `docs/architecture/Drift-detection.txt` | non_commite ( M) | 1392 | oui (1392 octets) |

### agent-a268d2e8fe1dc957c

- branche : `worktree-agent-a268d2e8fe1dc957c`
- tete : `a149320`
- retard sur main (commits non repris) : 105
- commits de l'agent au-dela de la base commune : 0
- fichier de preuve : AUCUN

| fichier | etat | octets | original |
| --- | --- | --- | --- |
| `outillage/competences/arbitrer.txt` | non_commite ( M) | 2862 | oui (2862 octets) |
| `docs/architecture/Agent-Contracts.txt` | non_commite ( M) | 3231 | oui (3231 octets) |
| `docs/architecture/Architecture_documentaire.md` | non_commite ( M) | 3266 | oui (3266 octets) |
| `docs/architecture/Conformance-Tests.txt` | non_commite ( M) | 3928 | oui (3928 octets) |
| `docs/architecture/Policy-as-code.txt` | non_commite ( M) | 2148 | oui (2148 octets) |
| `docs/architecture/Routing-unit-tests.txt` | non_commite ( M) | 2355 | oui (2355 octets) |
| `docs/architecture/Secrets-Gateway.txt` | non_commite ( M) | 2582 | oui (2582 octets) |
| `docs/architecture/budget-aware-execution.txt` | non_commite ( M) | 2884 | oui (2884 octets) |

### agent-a2b921b2e5443e3f3

- branche : `worktree-agent-a2b921b2e5443e3f3`
- tete : `6b2285b`
- retard sur main (commits non repris) : 104
- commits de l'agent au-dela de la base commune : 0
- fichier de preuve : AUCUN

| fichier | etat | octets | original |
| --- | --- | --- | --- |
| `tools/nexus-mcp/epreuve_protocole.js` | non_commite ( M) | 6701 | oui (6701 octets) |

### agent-a3a373ce61c0f6d6f

- branche : `worktree-agent-a3a373ce61c0f6d6f`
- tete : `27bf53f`
- retard sur main (commits non repris) : 127
- commits de l'agent au-dela de la base commune : 0
- fichier de preuve : AUCUN

| fichier | etat | octets | original |
| --- | --- | --- | --- |
| `outillage/nexus_doc.py` | non_commite ( M) | 40700 | oui (40700 octets) |

### agent-a50cbf7c79394206d

- branche : `worktree-agent-a50cbf7c79394206d`
- tete : `a149320`
- retard sur main (commits non repris) : 105
- commits de l'agent au-dela de la base commune : 0
- fichier de preuve : AUCUN

| fichier | etat | octets | original |
| --- | --- | --- | --- |
| `rituels/BOUSSOLE.csv` | non_commite ( M) | 400763 | oui (13663046 octets) |
| `rituels/CHECKLIST_COCKPIT.MD` | non_commite ( M) | 952614 | oui (1066903 octets) |
| `rituels/CHECKLIST_LIVRE_VS_CODE.md` | non_commite ( M) | 33312 | oui (33312 octets) |
| `rituels/CHECKLIST_PROGRESS.md` | non_commite ( M) | 1509 | oui (1509 octets) |
| `rituels/GABARIT_QUARANTAINE.md` | non_commite (??) | 5846 | oui (5846 octets) |
| `rituels/INVENTAIRE_OUTILS.md` | non_commite ( M) | 6416 | oui (6416 octets) |
| `rituels/LECONS_PARTAGEES.md` | non_commite ( M) | 60078 | oui (60078 octets) |
| `rituels/SURVIE_SANS_ABONNEMENT.md` | non_commite ( M) | 11855 | oui (11855 octets) |
| `rituels/VAGUES_REPARATION.md` | non_commite (??) | 94466 | oui (205112 octets) |
| `rituels/cablage_reference.json` | non_commite ( M) | 593 | oui (791 octets) |
| `rituels/orphelines_reference.json` | non_commite ( M) | 19 | oui (19 octets) |
| `rituels/outillage_reference.json` | non_commite ( M) | 578 | oui (578 octets) |

### agent-a5415ae7306cee00e

- branche : `worktree-agent-a5415ae7306cee00e`
- tete : `a149320`
- retard sur main (commits non repris) : 105
- commits de l'agent au-dela de la base commune : 0
- fichier de preuve : AUCUN

| fichier | etat | octets | original |
| --- | --- | --- | --- |
| `rituels/DOSSIER_MANDAT_AGENT.md` | non_commite (??) | 14167 | NON -- FICHIER NEUF |

### agent-a54e8dae802fa4a1b

- branche : `worktree-agent-a54e8dae802fa4a1b`
- tete : `27bf53f`
- retard sur main (commits non repris) : 127
- commits de l'agent au-dela de la base commune : 0
- fichier de preuve : AUCUN

| fichier | etat | octets | original |
| --- | --- | --- | --- |
| `Set-ClaudeModel.ps1` | non_commite ( M) | 12771 | oui (12771 octets) |
| `scripts/Initialize-Nexus.ps1` | non_commite ( M) | 10598 | oui (10598 octets) |
| `outillage/nexus_doc.py` | non_commite ( M) | 40700 | oui (40700 octets) |
| `scripts/restore.ps1` | non_commite ( M) | 7779 | oui (7779 octets) |
| `scripts/stop.ps1` | non_commite ( M) | 4119 | oui (4119 octets) |

### agent-a66668e1a379333b5

- branche : `worktree-agent-a66668e1a379333b5`
- tete : `a2a3aa0`
- retard sur main (commits non repris) : 111
- commits de l'agent au-dela de la base commune : 0
- fichier de preuve : AUCUN

| fichier | etat | octets | original |
| --- | --- | --- | --- |
| `outillage/nexus_doc.py` | non_commite ( M) | 40700 | oui (40700 octets) |

### agent-a676d0352359b0253

- branche : `worktree-agent-a676d0352359b0253`
- tete : `6b2285b`
- retard sur main (commits non repris) : 104
- commits de l'agent au-dela de la base commune : 0
- fichier de preuve : AUCUN

(aucun fichier commite ou non commite au-dela de la base de fusion)

### agent-a7a78c2da71438fd9

- branche : `worktree-agent-a7a78c2da71438fd9`
- tete : `5701a60`
- retard sur main (commits non repris) : 113
- commits de l'agent au-dela de la base commune : 0
- fichier de preuve : AUCUN

| fichier | etat | octets | original |
| --- | --- | --- | --- |
| `docs/architecture/Router-versioning.txt` | non_commite ( M) | 1463 | oui (1463 octets) |
| `docs/architecture/model-registry.yaml` | non_commite ( M) | 3565 | oui (4187 octets) |

### agent-a803b8dbb3c35914b

- branche : `worktree-agent-a803b8dbb3c35914b`
- tete : `a149320`
- retard sur main (commits non repris) : 105
- commits de l'agent au-dela de la base commune : 0
- fichier de preuve : AUCUN

| fichier | etat | octets | original |
| --- | --- | --- | --- |
| `docs/architecture/Adaptive-Inference-Controller.md` | non_commite ( M) | 11862 | oui (11862 octets) |
| `docs/architecture/Agent-loops.txt` | non_commite ( M) | 4543 | oui (4543 octets) |
| `docs/architecture/Confidence-uncertainty.txt` | non_commite ( M) | 2287 | oui (2287 octets) |
| `docs/architecture/Cost-budget.txt` | non_commite ( M) | 2012 | oui (2012 octets) |
| `docs/architecture/Reproductible-execution.txt` | non_commite ( M) | 3716 | oui (3716 octets) |
| `docs/architecture/Scientific-quantitative-evaluation-layer.txt` | non_commite ( M) | 2962 | oui (2962 octets) |
| `docs/architecture/agent-planner.txt` | non_commite ( M) | 3879 | oui (3879 octets) |
| `docs/architecture/tool-registry.txt` | non_commite ( M) | 4362 | oui (4362 octets) |

### agent-a8a7d862bd3f37091

- branche : `worktree-agent-a8a7d862bd3f37091`
- tete : `323aff4`
- retard sur main (commits non repris) : 115
- commits de l'agent au-dela de la base commune : 0
- fichier de preuve : AUCUN

| fichier | etat | octets | original |
| --- | --- | --- | --- |
| `outillage/nexus_doc.py` | non_commite ( M) | 40700 | oui (40700 octets) |

### agent-a8ddf6cc4a6aec704

- branche : `worktree-agent-a8ddf6cc4a6aec704`
- tete : `fa47fa7`
- retard sur main (commits non repris) : 114
- commits de l'agent au-dela de la base commune : 0
- fichier de preuve : AUCUN

| fichier | etat | octets | original |
| --- | --- | --- | --- |
| `.scratch_patch/` | non_commite (??) | ? [ERREUR COPIE: absent du worktree (supprime depuis ?)] | NON -- FICHIER NEUF |
| `outillage/nexus_doc.py` | non_commite ( M) | 40700 | oui (40700 octets) |
| `outillage/nexus_generate.py` | non_commite ( M) | 77230 | oui (80018 octets) |

### agent-a95744881ae0492ff

- branche : `worktree-agent-a95744881ae0492ff`
- tete : `a149320`
- retard sur main (commits non repris) : 105
- commits de l'agent au-dela de la base commune : 0
- fichier de preuve : AUCUN

| fichier | etat | octets | original |
| --- | --- | --- | --- |
| `AUDIT_TIERS.md` | non_commite (??) | 23177 | NON -- FICHIER NEUF |

### agent-a96910bce09e87b38

- branche : `worktree-agent-a96910bce09e87b38`
- tete : `29f3d78`
- retard sur main (commits non repris) : 105
- commits de l'agent au-dela de la base commune : 1
- fichier de preuve : AUCUN

| fichier | etat | octets | original |
| --- | --- | --- | --- |
| `outillage/nexus_quarantaine.py` | commite (A) | 24980 | oui (43895 octets) |

### agent-a9fe6d8711708973c

- branche : `worktree-agent-a9fe6d8711708973c`
- tete : `abf6406`
- retard sur main (commits non repris) : 284
- commits de l'agent au-dela de la base commune : 0
- fichier de preuve : AUCUN

| fichier | etat | octets | original |
| --- | --- | --- | --- |
| `outillage/nexus_doc.py` | non_commite ( M) | 40700 | oui (40700 octets) |
| `scripts/nexus_garde_production.py` | non_commite ( M) | 4459 | oui (4564 octets) |

### agent-aaafb81b13e76c172

- branche : `worktree-agent-aaafb81b13e76c172`
- tete : `5701a60`
- retard sur main (commits non repris) : 113
- commits de l'agent au-dela de la base commune : 0
- fichier de preuve : AUCUN

| fichier | etat | octets | original |
| --- | --- | --- | --- |
| `docs/MANUEL.md` | non_commite ( M) | 19672 | oui (19310 octets) |
| `docs/architecture/README.md` | non_commite ( M) | 6724 | oui (6724 octets) |
| `docs/pont-local-abonnement.md` | non_commite ( M) | 16770 | oui (16770 octets) |
| `docs/set-claude-model.md` | non_commite ( M) | 3026 | oui (3026 octets) |

### agent-ab941411343b29376

- branche : `worktree-agent-ab941411343b29376`
- tete : `c271935`
- retard sur main (commits non repris) : 129
- commits de l'agent au-dela de la base commune : 0
- fichier de preuve : AUCUN

| fichier | etat | octets | original |
| --- | --- | --- | --- |
| `outillage/nexus_doc.py` | non_commite ( M) | 40700 | oui (40700 octets) |

### agent-abbea6f5f883f4469

- branche : `worktree-agent-abbea6f5f883f4469`
- tete : `27bf53f`
- retard sur main (commits non repris) : 127
- commits de l'agent au-dela de la base commune : 0
- fichier de preuve : AUCUN

| fichier | etat | octets | original |
| --- | --- | --- | --- |
| `scripts/nexus_agent.py` | non_commite ( M) | 73315 | oui (74721 octets) |
| `outillage/nexus_appliquer.py` | non_commite ( M) | 10320 | oui (10903 octets) |
| `scripts/nexus_disjoncteur.py` | non_commite ( M) | 9839 | oui (11129 octets) |
| `outillage/nexus_doc.py` | non_commite ( M) | 40700 | oui (40700 octets) |
| `outillage/nexus_essaim.py` | non_commite ( M) | 30884 | oui (30884 octets) |
| `tmp/` | non_commite (??) | ? [ERREUR COPIE: absent du worktree (supprime depuis ?)] | NON -- FICHIER NEUF |

### agent-abfe13fb0c58da618

- branche : `worktree-agent-abfe13fb0c58da618`
- tete : `a149320`
- retard sur main (commits non repris) : 105
- commits de l'agent au-dela de la base commune : 0
- fichier de preuve : AUCUN

| fichier | etat | octets | original |
| --- | --- | --- | --- |
| `AUDIT_TIERS_FILET.md` | non_commite (??) | 24341 | NON -- FICHIER NEUF |

### agent-acb34a9bbc8199d49

- branche : `worktree-agent-acb34a9bbc8199d49`
- tete : `323aff4`
- retard sur main (commits non repris) : 115
- commits de l'agent au-dela de la base commune : 0
- fichier de preuve : AUCUN

| fichier | etat | octets | original |
| --- | --- | --- | --- |
| `outillage/nexus_doc.py` | non_commite ( M) | 40700 | oui (40700 octets) |

### agent-acef566b4e8c5392f

- branche : `worktree-agent-acef566b4e8c5392f`
- tete : `6b2285b`
- retard sur main (commits non repris) : 104
- commits de l'agent au-dela de la base commune : 0
- fichier de preuve : AUCUN

(aucun fichier commite ou non commite au-dela de la base de fusion)

### agent-ad2d06940ef00ceb7

- branche : `worktree-agent-ad2d06940ef00ceb7`
- tete : `6b2285b`
- retard sur main (commits non repris) : 104
- commits de l'agent au-dela de la base commune : 0
- fichier de preuve : AUCUN

| fichier | etat | octets | original |
| --- | --- | --- | --- |
| `Start-Claude.ps1` | non_commite ( M) | 7924 | oui (7924 octets) |
| `scripts/Register-NexusDemarrage.ps1` | non_commite ( M) | 6096 | oui (6096 octets) |

### agent-ad3f0e991a26eb4ce

- branche : `worktree-agent-ad3f0e991a26eb4ce`
- tete : `27bf53f`
- retard sur main (commits non repris) : 127
- commits de l'agent au-dela de la base commune : 0
- fichier de preuve : AUCUN

| fichier | etat | octets | original |
| --- | --- | --- | --- |
| `docker-compose.yml` | non_commite ( M) | 5979 | oui (6402 octets) |
| `requirements.txt` | non_commite ( M) | 14 | oui (15 octets) |
| `outillage/nexus_doc.py` | non_commite ( M) | 40700 | oui (40700 octets) |

### agent-ade9a13af3736b1a3

- branche : `worktree-agent-ade9a13af3736b1a3`
- tete : `5701a60`
- retard sur main (commits non repris) : 113
- commits de l'agent au-dela de la base commune : 0
- fichier de preuve : AUCUN

| fichier | etat | octets | original |
| --- | --- | --- | --- |
| `docs/architecture/Escalation-policy.txt` | non_commite ( M) | 1270 | oui (1270 octets) |
| `docs/architecture/Event-log.txt` | non_commite ( M) | 1608 | oui (1608 octets) |
| `docs/architecture/Final-target-architecture.txt` | non_commite ( M) | 7362 | oui (7362 octets) |
| `docs/architecture/Latency-budget.txt` | non_commite ( M) | 924 | oui (924 octets) |
| `docs/architecture/MCP-external-tool-layer.txt` | non_commite ( M) | 1552 | oui (1552 octets) |
| `docs/architecture/MCP-ne-doit-pas-bypasser-la-policy.txt` | non_commite ( M) | 871 | oui (871 octets) |
| `docs/architecture/Mission-P0.txt` | non_commite ( M) | 21506 | oui (21506 octets) |
| `docs/architecture/Model-lifecycle-automation.txt` | non_commite ( M) | 1220 | oui (1220 octets) |
| `docs/architecture/Multi-agent-orchestration.txt` | non_commite ( M) | 2121 | oui (2121 octets) |
| `docs/architecture/execution-policy.yaml.txt` | non_commite ( M) | 1367 | oui (1367 octets) |
| `docs/architecture/execution-profiles.txt` | non_commite ( M) | 1455 | oui (1455 octets) |
| `docs/architecture/missions/INGEST-001-platform-integration.md` | non_commite ( M) | 10933 | oui (10933 octets) |
| `docs/architecture/model-registry.yaml` | non_commite ( M) | 2455 | oui (4187 octets) |

### agent-aec47b54a536e6499

- branche : `worktree-agent-aec47b54a536e6499`
- tete : `a149320`
- retard sur main (commits non repris) : 105
- commits de l'agent au-dela de la base commune : 0
- fichier de preuve : AUCUN

| fichier | etat | octets | original |
| --- | --- | --- | --- |
| `docs/architecture/Agent-Trace-Schema.txt` | non_commite ( M) | 2138 | oui (2138 octets) |
| `docs/architecture/Bayesian-routing-evolution-future.txt` | non_commite ( M) | 1676 | oui (1676 octets) |
| `docs/architecture/Context-cache.txt` | non_commite ( M) | 1434 | oui (1434 octets) |
| `docs/architecture/Prompt-registry.txt` | non_commite ( M) | 1451 | oui (1451 octets) |
| `docs/architecture/SKILLS.txt` | non_commite ( M) | 3553 | oui (3553 octets) |
| `docs/architecture/Verification-Agent.txt` | non_commite ( M) | 1871 | oui (1871 octets) |
| `docs/architecture/provider-registry.txt` | non_commite ( M) | 3004 | oui (3004 octets) |
| `scripts/console_tools.py` | non_commite ( M) | 4039 | oui (4039 octets) |

## PREUVE PARTIELLE

### agent-a084add637786a142

- branche : `worktree-agent-a084add637786a142`
- tete : `a149320`
- retard sur main (commits non repris) : 105
- commits de l'agent au-dela de la base commune : 0
- fichier de preuve : `QUARANTAINE.md`
- rubriques remplies : 7/8
- trois epreuves -- test : remplie, reverse : remplie, forward : remplie
- couleur proposee par l'auteur : JAUNE
- audit du tiers (rubrique 8) : VIDE

| fichier | etat | octets | original |
| --- | --- | --- | --- |
| `QUARANTAINE.md` | non_commite (??) | 10266 | NON -- FICHIER NEUF |
| `rituels/GABARIT_QUARANTAINE.md` | non_commite (??) | 5846 | oui (5846 octets) |
| `outillage/nexus_quarantaine.py` | non_commite (??) | 43895 | oui (43895 octets) |

### agent-a0bb278a9ee2836a5

- branche : `worktree-agent-a0bb278a9ee2836a5`
- tete : `ea8be64`
- retard sur main (commits non repris) : 93
- commits de l'agent au-dela de la base commune : 2
- fichier de preuve : `QUARANTAINE.md`
- rubriques remplies : 5/8
- trois epreuves -- test : VIDE, reverse : VIDE, forward : VIDE
- couleur proposee par l'auteur : JAUNE
- audit du tiers (rubrique 8) : VIDE

| fichier | etat | octets | original |
| --- | --- | --- | --- |
| `QUARANTAINE.md` | non_commite (??) | 21624 | NON -- FICHIER NEUF |
| `rituels/outillage_reference.json` | commite (M) | 526 | oui (578 octets) |
| `epreuves/epreuve_orphelines.py` | commite (M) | 4643 | oui (3677 octets) |
| `epreuves/epreuve_progres.py` | commite (M) | 9119 | oui (5602 octets) |
| `outillage/nexus_cablage.py` | commite (M) | 20787 | oui (19757 octets) |
| `outillage/nexus_checklist_progres.py` | commite (M) | 10989 | oui (9381 octets) |
| `outillage/nexus_conformite.py` | commite (M) | 89835 | oui (92142 octets) |
| `outillage/nexus_outillage.py` | commite (M) | 34519 | oui (32787 octets) |
| `outillage/nexus_progres.py` | commite (M) | 8636 | oui (7798 octets) |
| `outillage/nexus_rituel.py` | commite (M) | 21784 | oui (21397 octets) |

### agent-a11923e06ae11d5df

- branche : `worktree-agent-a11923e06ae11d5df`
- tete : `a149320`
- retard sur main (commits non repris) : 105
- commits de l'agent au-dela de la base commune : 0
- fichier de preuve : `QUARANTAINE.md`
- rubriques remplies : 6/8
- trois epreuves -- test : remplie, reverse : remplie, forward : VIDE
- couleur proposee par l'auteur : VERT
- audit du tiers (rubrique 8) : VIDE

| fichier | etat | octets | original |
| --- | --- | --- | --- |
| `QUARANTAINE.md` | non_commite (??) | 31630 | NON -- FICHIER NEUF |
| `scripts/nexus_agent.py` | non_commite ( M) | 74399 | oui (74721 octets) |
| `scripts/nexus_disjoncteur.py` | non_commite ( M) | 10567 | oui (11129 octets) |

### agent-a1f14f9783bcb3e7f

- branche : `worktree-agent-a1f14f9783bcb3e7f`
- tete : `a149320`
- retard sur main (commits non repris) : 105
- commits de l'agent au-dela de la base commune : 0
- fichier de preuve : `QUARANTAINE.md`
- rubriques remplies : 3/8
- trois epreuves -- test : VIDE, reverse : VIDE, forward : VIDE
- couleur proposee par l'auteur : VERT
- audit du tiers (rubrique 8) : VIDE

| fichier | etat | octets | original |
| --- | --- | --- | --- |
| `QUARANTAINE.md` | non_commite (??) | 14784 | NON -- FICHIER NEUF |
| `epreuves/epreuve_armer_garde.py` | non_commite ( M) | 3403 | oui (3063 octets) |
| `epreuves/epreuve_garde_ecriture.py` | non_commite ( M) | 5423 | oui (3159 octets) |
| `epreuves/epreuve_garde_lecture.py` | non_commite ( M) | 7300 | oui (6260 octets) |
| `epreuves/epreuve_garde_shell.py` | non_commite ( M) | 2454 | oui (2539 octets) |

### agent-a3666d882218a276d

- branche : `worktree-agent-a3666d882218a276d`
- tete : `a149320`
- retard sur main (commits non repris) : 105
- commits de l'agent au-dela de la base commune : 0
- fichier de preuve : `QUARANTAINE.md`
- rubriques remplies : 7/8
- trois epreuves -- test : VIDE, reverse : VIDE, forward : VIDE
- couleur proposee par l'auteur : VERT
- audit du tiers (rubrique 8) : VIDE

| fichier | etat | octets | original |
| --- | --- | --- | --- |
| `QUARANTAINE.md` | non_commite (??) | 10791 | NON -- FICHIER NEUF |
| `outillage/nexus_test.py` | non_commite ( M) | 172446 | oui (175825 octets) |
| `tools/nexus-mcp/epreuve_perte_map.js` | non_commite (??) | 9611 | NON -- FICHIER NEUF |
| `tools/nexus-mcp/server.js` | non_commite ( M) | 156998 | oui (152490 octets) |

### agent-a415cd08dccd3fd97

- branche : `worktree-agent-a415cd08dccd3fd97`
- tete : `0da3a82`
- retard sur main (commits non repris) : 105
- commits de l'agent au-dela de la base commune : 5
- fichier de preuve : `QUARANTAINE.md`
- rubriques remplies : 6/8
- trois epreuves -- test : VIDE, reverse : remplie, forward : remplie
- couleur proposee par l'auteur : JAUNE
- audit du tiers (rubrique 8) : VIDE

| fichier | etat | octets | original |
| --- | --- | --- | --- |
| `QUARANTAINE.md` | commite (A) | 46522 | NON -- FICHIER NEUF |
| `fichier.txt` | non_commite (??) | 28765 | NON -- FICHIER NEUF |
| `outillage/nexus_filet.py` | commite (A) | 22581 | oui (22581 octets) |

### agent-a55bdfccf377cfffa

- branche : `worktree-agent-a55bdfccf377cfffa`
- tete : `a149320`
- retard sur main (commits non repris) : 105
- commits de l'agent au-dela de la base commune : 0
- fichier de preuve : `QUARANTAINE.md`
- rubriques remplies : 7/8
- trois epreuves -- test : VIDE, reverse : VIDE, forward : VIDE
- couleur proposee par l'auteur : (aucune)
- audit du tiers (rubrique 8) : VIDE

| fichier | etat | octets | original |
| --- | --- | --- | --- |
| `QUARANTAINE.md` | non_commite (??) | 16238 | NON -- FICHIER NEUF |
| `scripts/nexus_garde_ecriture.py` | non_commite ( M) | 11660 | oui (7011 octets) |

### agent-a697c9b31ea2b75e4

- branche : `worktree-agent-a697c9b31ea2b75e4`
- tete : `a149320`
- retard sur main (commits non repris) : 105
- commits de l'agent au-dela de la base commune : 0
- fichier de preuve : `QUARANTAINE.md`
- rubriques remplies : 7/8
- trois epreuves -- test : VIDE, reverse : VIDE, forward : VIDE
- couleur proposee par l'auteur : VERT
- audit du tiers (rubrique 8) : VIDE

| fichier | etat | octets | original |
| --- | --- | --- | --- |
| `QUARANTAINE.md` | non_commite (??) | 12176 | NON -- FICHIER NEUF |
| `rituels/cablage_reference.json` | non_commite ( M) | 554 | oui (791 octets) |
| `outillage/nexus_test.py` | non_commite ( M) | 171916 | oui (175825 octets) |

### agent-a6d8fb7354cc50b30

- branche : `worktree-agent-a6d8fb7354cc50b30`
- tete : `a149320`
- retard sur main (commits non repris) : 105
- commits de l'agent au-dela de la base commune : 0
- fichier de preuve : `QUARANTAINE.md`
- rubriques remplies : 7/8
- trois epreuves -- test : VIDE, reverse : VIDE, forward : VIDE
- couleur proposee par l'auteur : JAUNE
- audit du tiers (rubrique 8) : VIDE

| fichier | etat | octets | original |
| --- | --- | --- | --- |
| `QUARANTAINE.md` | non_commite (??) | 15763 | NON -- FICHIER NEUF |
| `outillage/nexus_conformite.py` | non_commite ( M) | 93278 | oui (92142 octets) |
| `outillage/nexus_socle.py` | non_commite ( M) | 5378 | oui (5683 octets) |
| `outillage/nexus_test.py` | non_commite ( M) | 173033 | oui (175825 octets) |

### agent-a925f543aaa6e4d34

- branche : `worktree-agent-a925f543aaa6e4d34`
- tete : `a149320`
- retard sur main (commits non repris) : 105
- commits de l'agent au-dela de la base commune : 0
- fichier de preuve : `QUARANTAINE.md`
- rubriques remplies : 6/8
- trois epreuves -- test : VIDE, reverse : VIDE, forward : VIDE
- couleur proposee par l'auteur : ROUGE
- audit du tiers (rubrique 8) : VIDE

| fichier | etat | octets | original |
| --- | --- | --- | --- |
| `QUARANTAINE.md` | non_commite (??) | 19183 | NON -- FICHIER NEUF |
| `epreuves/epreuve_repli_epuise.py` | non_commite ( A) | 9158 | NON -- FICHIER NEUF |
| `epreuves/epreuve_reprise_avant_repli.py` | non_commite ( M) | 6151 | oui (4159 octets) |
| `scripts/nexus_agent.py` | non_commite ( M) | 75964 | oui (74721 octets) |
| `outillage/nexus_test.py` | non_commite ( M) | 171885 | oui (175825 octets) |

### agent-a95a4421aa8062ff1

- branche : `worktree-agent-a95a4421aa8062ff1`
- tete : `a149320`
- retard sur main (commits non repris) : 105
- commits de l'agent au-dela de la base commune : 0
- fichier de preuve : `QUARANTAINE.md`
- rubriques remplies : 7/8
- trois epreuves -- test : VIDE, reverse : VIDE, forward : VIDE
- couleur proposee par l'auteur : JAUNE
- audit du tiers (rubrique 8) : VIDE

| fichier | etat | octets | original |
| --- | --- | --- | --- |
| `QUARANTAINE.md` | non_commite (??) | 10345 | NON -- FICHIER NEUF |
| `scripts/nexus_disjoncteur.py` | non_commite ( M) | 16857 | oui (11129 octets) |

### agent-a9bae5bcacf5d3042

- branche : `worktree-agent-a9bae5bcacf5d3042`
- tete : `be40d1f`
- retard sur main (commits non repris) : 105
- commits de l'agent au-dela de la base commune : 1
- fichier de preuve : `QUARANTAINE.md`
- rubriques remplies : 5/8
- trois epreuves -- test : VIDE, reverse : VIDE, forward : VIDE
- couleur proposee par l'auteur : VERT
- audit du tiers (rubrique 8) : VIDE

| fichier | etat | octets | original |
| --- | --- | --- | --- |
| `QUARANTAINE.md` | non_commite (??) | 15392 | NON -- FICHIER NEUF |
| `rituels/CHECKLIST_LIVRE_VS_CODE.md` | commite (M) | 38308 | oui (33312 octets) |
| `rituels/cablage_reference.json` | non_commite ( M) | 553 | oui (791 octets) |
| `epreuves/epreuve_rendu_vide.py` | commite (A) | 6108 | NON -- FICHIER NEUF |
| `outillage/nexus_test.py` | commite (M) | 172187 | oui (175825 octets) |

### agent-acbd763084f29adf5

- branche : `worktree-agent-acbd763084f29adf5`
- tete : `a149320`
- retard sur main (commits non repris) : 105
- commits de l'agent au-dela de la base commune : 0
- fichier de preuve : `QUARANTAINE.md`
- rubriques remplies : 7/8
- trois epreuves -- test : VIDE, reverse : VIDE, forward : VIDE
- couleur proposee par l'auteur : VERT
- audit du tiers (rubrique 8) : VIDE

| fichier | etat | octets | original |
| --- | --- | --- | --- |
| `QUARANTAINE.md` | non_commite (??) | 6962 | NON -- FICHIER NEUF |
| `scripts/nexus_valide.py` | non_commite ( M) | 37884 | oui (33502 octets) |

### agent-ae2755c603728d190

- branche : `worktree-agent-ae2755c603728d190`
- tete : `32c9175`
- retard sur main (commits non repris) : 66
- commits de l'agent au-dela de la base commune : 2
- fichier de preuve : `QUARANTAINE.md`
- rubriques remplies : 7/8
- trois epreuves -- test : VIDE, reverse : VIDE, forward : VIDE
- couleur proposee par l'auteur : VERT
- audit du tiers (rubrique 8) : VIDE

| fichier | etat | octets | original |
| --- | --- | --- | --- |
| `QUARANTAINE.md` | commite (A) | 21255 | NON -- FICHIER NEUF |
| `scripts/nexus_agent.py` | commite (M) | 74556 | oui (74721 octets) |
| `scripts/nexus_disjoncteur.py` | commite (M) | 11130 | oui (11129 octets) |

### agent-afe13c9acd701d299

- branche : `worktree-agent-afe13c9acd701d299`
- tete : `a149320`
- retard sur main (commits non repris) : 105
- commits de l'agent au-dela de la base commune : 0
- fichier de preuve : `QUARANTAINE.md`
- rubriques remplies : 6/8
- trois epreuves -- test : remplie, reverse : remplie, forward : remplie
- couleur proposee par l'auteur : VERT
- audit du tiers (rubrique 8) : VIDE

| fichier | etat | octets | original |
| --- | --- | --- | --- |
| `QUARANTAINE.md` | non_commite (??) | 26297 | NON -- FICHIER NEUF |
| `scripts/nexus_capability.py` | non_commite ( M) | 30590 | oui (30590 octets) |
| `outillage/nexus_conformite.py` | non_commite ( M) | 89957 | oui (92142 octets) |
| `outillage/nexus_validate.py` | non_commite ( M) | 34170 | oui (34209 octets) |

## PREUVE COMPLETE

(aucun worktree dans cette population)

