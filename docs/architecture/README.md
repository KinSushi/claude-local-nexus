# Notes d'architecture

Ces documents sont la **matière première du projet** : ce qu'on veut
construire, et pourquoi. Ils décrivent une cible, pas l'état déployé.

La distinction est volontaire. L'état réellement en place est mesuré et
généré — voir [`rituels/STATE.md`](../../rituels/STATE.md) — tandis que ces
notes servent de réserve d'idées où puiser à mesure que la plateforme mûrit.
Plusieurs y ont déjà été puisées : les profils d'exécution, le versionnement
du routeur, la détection de dérive et les tests de conformité sont
aujourd'hui implémentés.

> Ce qui reste ici n'est donc **pas** une dette, mais un plan.
> Ce qui en a été retenu figure dans [`CHECKLIST_COCKPIT.MD`](../../rituels/CHECKLIST_COCKPIT.MD).

---

## Agents et orchestration

| Note | Objet |
|---|---|
| [`Agent-loops.txt`](Agent-loops.txt) | Cycle PLAN → ACT → OBSERVE → VERIFY, avec les états REPLAN, RECOVER et ESCALATE |
| [`agent-planner.txt`](agent-planner.txt) | Un planificateur qui produit un plan d'exécution : tâches, modèles, outils, validations |
| [`Multi-agent-orchestration.txt`](Multi-agent-orchestration.txt) | Orchestrateur reliant des agents spécialisés à un vérificateur puis à un finaliseur |
| [`Verification-Agent.txt`](Verification-Agent.txt) | Une phase de vérification dédiée : syntaxe, tests, sécurité, sortie des outils |
| [`Self-critique-contrôlée.txt`](Self-critique-contrôlée.txt) | Générer puis vérifier, sans multiplier les confirmations redondantes |
| [`Agent-Contracts.txt`](Agent-Contracts.txt) | Contrat par agent : outils permis et interdits, modèles préférés, schéma de sortie, budget |
| [`Agent-Trace-Schema.txt`](Agent-Trace-Schema.txt) | Schéma de trace stable, pour que deux exécutions restent comparables |
| [`budget-aware-execution.txt`](budget-aware-execution.txt) | Une exécution qui connaît son budget avant de le dépenser |

## Routage et politique

| Note | Objet | État |
|---|---|---|
| [`execution-profiles.txt`](execution-profiles.txt) | Profils par classe de tâche plutôt que par modèle | **implémenté** |
| [`Router-versioning.txt`](Router-versioning.txt) | Une version de politique de routage, reportée dans les traces | **implémenté** |
| [`execution-policy.yaml.txt`](execution-policy.yaml.txt) | Moteur de règles : routage, confidentialité, repli, autonomie |
| [`Policy-as-code.txt`](Policy-as-code.txt) | Traduire une politique en prose en règles de refus exécutables |
| [`provider-registry.txt`](provider-registry.txt) | Registre des fournisseurs : zone de confiance, capacités, niveau de confidentialité |
| [`tool-registry.txt`](tool-registry.txt) | Registre d'outils avec classe de risque et approbation requise |
| [`Escalation-policy.txt`](Escalation-policy.txt) | Sous un seuil de confiance : rejouer, changer de modèle, ou demander un humain |
| [`model-registry.yaml`](model-registry.yaml) | Registre de modèles et de leurs capacités déclarées |
| [`Bayesian-routing-evolution-future.txt`](Bayesian-routing-evolution-future.txt) | Piste d'évolution : un routage qui apprend de ses résultats |

## Observabilité et évaluation

| Note | Objet | État |
|---|---|---|
| [`Conformance-Tests.txt`](Conformance-Tests.txt) | Tests validant les politiques : L3 jamais vers le cloud, vision jamais vers du texte | **implémenté** |
| [`Drift-detection.txt`](Drift-detection.txt) | Comparer registre, LiteLLM, Ollama et Docker, puis signaler l'écart | **implémenté** |
| [`Routing-unit-tests.txt`](Routing-unit-tests.txt) | Tests unitaires de classification de tâche et de capacité requise |
| [`Event-log.txt`](Event-log.txt) | Événements structurés à chaque étape d'exécution |
| [`Confidence-uncertainty.txt`](Confidence-uncertainty.txt) | Distinguer la confiance du modèle de celle du système |
| [`Reproductible-execution.txt`](Reproductible-execution.txt) | Les métadonnées sans lesquelles une exécution ne peut pas être refaite |
| [`Scientific-quantitative-evaluation-layer.txt`](Scientific-quantitative-evaluation-layer.txt) | Quantifier la réussite d'un routeur plutôt que de l'apprécier |

## Budgets et cache

| Note | Objet |
|---|---|
| [`Cost-budget.txt`](Cost-budget.txt) | Plafonds de dépense par requête, par session et par jour |
| [`Latency-budget.txt`](Latency-budget.txt) | Cible et limite dure de latence, par profil |
| [`Cache-policy-avancée.txt`](Cache-policy-avancée.txt) | Trois catégories : cacheable, conditionnel, jamais |
| [`Context-cache.txt`](Context-cache.txt) | Distinguer cache de réponse, sémantique, de contexte, d'embedding et de résultat d'outil |

## Sécurité

| Note | Objet |
|---|---|
| [`Secrets-Gateway.txt`](Secrets-Gateway.txt) | Un point de passage unique pour les secrets |
| [`MCP-ne-doit-pas-bypasser-la-policy.txt`](MCP-ne-doit-pas-bypasser-la-policy.txt) | Un outil externe passe par le moteur de politique, jamais à côté |

## Intégration

| Note | Objet |
|---|---|
| [`MCP-external-tool-layer.txt`](MCP-external-tool-layer.txt) | Une passerelle d'outils centralisant permissions, audit et limitation de débit |
| [`Model-lifecycle-automation.txt`](Model-lifecycle-automation.txt) | Du modèle découvert au modèle retiré, avec une porte à chaque étape |
| [`Prompt-registry.txt`](Prompt-registry.txt) | Prompts versionnés, avec la liste des modèles compatibles |
| [`SKILLS.txt`](SKILLS.txt) | Compétences et ressources mobilisables par les agents |

## Vision d'ensemble

| Note | Objet |
|---|---|
| [`Final-target-architecture.txt`](Final-target-architecture.txt) | L'architecture cible complète, composants et plan par phases |
| [`Architecture_documentaire.md`](Architecture_documentaire.md) | L'organisation documentaire du projet |
| [`missions/`](missions/) | Missions d'ingestion et de migration |
| [`policies/`](policies/) | Emplacement prévu pour les politiques exécutables |
