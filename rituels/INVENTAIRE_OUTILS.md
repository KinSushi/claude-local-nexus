# INVENTAIRE DES OUTILS NEXUS

> Un outil non decouvrable n'existe pas, meme s'il est parfait.
> Genere par lecture des docstrings et du serveur MCP.

## Les 14 outils exposes en MCP — appelables par TOUT agent

`nexus_ask` · `nexus_batch` · `nexus_charge` · `nexus_compare` · `nexus_context` · `nexus_index_build` · `nexus_models` · `nexus_profile` · `nexus_route` · `nexus_savings` · `nexus_search` · `nexus_summarize` · `nexus_verrou` · `nexus_vision`

## Les scripts du depot

**MCP** = ce script est lance par le serveur MCP, donc atteignable par un agent tiers.

| script | MCP | ce qu'il fait |
| --- | --- | --- |
| `nexus_agent` | non | Lanceur d'agents gratuits. |
| `nexus_appliquer` | non | Appliquer un patch rendu par le banc, apres verification. |
| `nexus_armer_garde` | non | (sans docstring) |
| `nexus_armer_hook` | non | (sans docstring) |
| `nexus_avec_verrou` | non | Lanceur de commandes sous verrou machine. |
| `nexus_bench` | non | Module nexus_bench |
| `nexus_boussole` | non | Génère la boussole : index navigable du dépôt, avec empreintes. |
| `nexus_cablage` | non | Qui appelle réellement chaque script ? Et le nombre d'orphelins baisse-t-il ? |
| `nexus_capability` | oui | Profil matériel de la machine et verdict automatique par modèle. |
| `nexus_charge` | oui | Verifie si la machine est assez libre pour qu'une mesure de latence LOCALE soit interpretabl |
| `nexus_conformite` | non | Porte de conformité : tout est-il en ordre avant de (re)démarrer ? |
| `nexus_corpus` | non | (sans docstring) |
| `nexus_disjoncteur` | non | module |
| `nexus_doc` | non | doc_lib.py — consulter la doc Python officielle parsée SANS jamais la charger. |
| `nexus_epreuve_vide` | non | (sans docstring) |
| `nexus_essaim` | non | (sans docstring) |
| `nexus_fonctions` | non | Remplace des fonctions entières dans un fichier Python en se basant sur les |
| `nexus_garde_agent` | non | Garde economique sur la creation de sous-agents et workflows. |
| `nexus_garde_ecriture` | non | Garde d'écriture pour le shell : refuse d'écrire dans un chemin protégé. |
| `nexus_garde_edition` | non | Un fichier Python qui vient d'être écrit compile-t-il encore ? |
| `nexus_garde_isolation` | non | garde PreToolUse. |
| `nexus_garde_lecture` | non | Lire avant d'écrire. Refusé sinon. |
| `nexus_garde_production` | non | (sans docstring) |
| `nexus_garde_shell` | non | Un heredoc shell mange les échappements du code Python qu'il porte. |
| `nexus_generate` | non | Générateur de configuration Claude-Local-Nexus. |
| `nexus_import` | non | Chaque script s'importe-t-il, et son import fait-il quelque chose ? |
| `nexus_index_livres` | non | (sans docstring) |
| `nexus_ingerer` | non | Ingerer une documentation pour qu'un PETIT modele puisse la consulter. |
| `nexus_libs` | non | Outil de comparaison d'ensembles de bibliotheques Python. |
| `nexus_livres` | non | (sans docstring) |
| `nexus_livres_semantique` | non | (sans docstring) |
| `nexus_loi1` | non | (sans docstring) |
| `nexus_maj_modeles` | non | (sans docstring) |
| `nexus_mcp_probe` | non | Sonde du serveur MCP nexus-local : exerce les outils de bout en bout. |
| `nexus_migration_plan` | non | Plan de sortie des modeles hors de Docker. |
| `nexus_outillage` | non | DEFAUT ORIGINALE : chaque fonction _run_* renvoyait une LISTE de violations. |
| `nexus_patch` | non | (sans docstring) |
| `nexus_portee_import` | non | Detecte deux types de defauts : |
| `nexus_poser_socle` | non | (sans docstring) |
| `nexus_posterior` | non | Agrège les observations en posterior, par couple (modèle, température). |
| `nexus_preload` | non | Précharge les poids d'un modèle local pour éviter le coût de chargement à froid. |
| `nexus_preserve` | non | Sépare ce qui se retélécharge de ce qui ne se retélécharge pas. |
| `nexus_progres` | non | Genere le fichier PROGRESS.MD a la racine du depot. |
| `nexus_pull_host` | non | Télécharge sur l'hôte les modèles retenus par le plan de migration. |
| `nexus_redaction` | non | Ce script contrôle que chaque modification de code source (.py, .ps1, .js) est |
| `nexus_relais` | non | Orchestrateur de relais pour le dépôt Nexus. |
| `nexus_releve` | non | Le local prend‑il réellement le relais ? |
| `nexus_reprise` | non | Ce qu'une session fraîche doit savoir, imprimé AU DÉMARRAGE. |
| `nexus_rituel` | non | Rituel de fin de tour, exécuté plutôt que lu. |
| `nexus_ruche` | non | – coordinateur qui découvre les cibles du dépôt et lance |
| `nexus_sauvegarde` | non | Local git repository backup script. |
| `nexus_savings` | oui | Mesure ce que la delegation fait réellement economiser. |
| `nexus_schema` | non | Rend le SQUELETTE de fichiers de donnees (JSON, JSONL, CSV) sans en exposer aucune valeur. |
| `nexus_secours` | non | diagnostic de secours pour le moteur d'inference local. |
| `nexus_socle` | non | (sans docstring) |
| `nexus_sonde_aveugle` | non | (sans docstring) |
| `nexus_state` | non | Génère rituels/STATE.md à partir de l'état réellement mesuré. |
| `nexus_stats_jsonl` | non | Croise des motifs regex avec un champ booleen, PAR GROUPE, sur un journal JSONL. |
| `nexus_sujets` | non | (sans docstring) |
| `nexus_switch_engine` | non | Bascule le moteur d'inférence local entre Docker et l'hôte. |
| `nexus_test` | non | Suite de tests Claude-Local-Nexus — modèles réels, chemins réels. |
| `nexus_test_outillage` | non | Suite de tests ALLER / RETOUR pour l'outillage qui porte desormais tout le |
| `nexus_traque` | non | Traque mecanique des classes de defauts rencontrees dans ce depot. |
| `nexus_validate` | non | Validation d'intégrité de la configuration Claude-Local-Nexus. |
| `nexus_valide` | non | Script de validation automatisée du dépôt. |
| `nexus_verbatim` | non | Conserver VERBATIM ce que chaque agent a produit. |
| `nexus_verifie_rendu` | non | (sans docstring) |
| `nexus_verrou_machine` | oui | verrou_machine.py — exclusion mutuelle entre PROJETS, sur la MEME SESSION Windows. |
| `nexus_verrou_tenir` | non | (sans docstring) |
| `nexus_vitrine` | non | Sauvegarde vitrine : ne publie que si l'état est sain. |
| `nexus_worktree` | non | Agent local en arbre de travail isolé. |

**71 scripts · 4 atteignables par le MCP · 14 outils MCP au total**

