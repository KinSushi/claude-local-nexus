# UTILISER_NEXUS.md

## 1. À QUOI ÇA SERT
Un banc de modèles gratuits — locaux et cloud — que votre session Claude Code appelle comme des outils ; le volume part au banc, votre abonnement ne paie que l'arbitrage.

## 2. LE PREMIER APPEL QUI MARCHE
Les outils MCP sont déjà intégrés à votre session. **Appelez-les directement par leur nom, et NON via le shell.** L'utilisation du shell pour ces fonctions est l'erreur principale rencontrée par les utilisateurs.

Outils disponibles :
`nexus_ask`, `nexus_batch`, `nexus_compare`, `nexus_context`, `nexus_index_build`, `nexus_models`, `nexus_profile`, `nexus_route`, `nexus_savings`, `nexus_search`, `nexus_summarize`, `nexus_vision`.

**Exemple :**
❌ Mauvais : `shell_execute("python C:/local-llm-docker/scripts/nexus_search.py --query 'gestion des verrous'")`
✅ Bon : `nexus_search(query="Où se trouve la gestion des verrous dans le dépôt ?")` $\rightarrow$ `nexus_ask(question="Comment fonctionne ce verrou ?")`

## 3. LA CARTE

| Besoin | Outil | Usage |
| :--- | :--- | :--- |
| Localiser un élément dans le dépôt | `nexus_search` | **Priorité :** a trouvé en 30s deux fichiers via rapprochement sémantique là où des heures de grep ont échoué. |
| Analyser un corpus plus large que la fenêtre | `nexus_context` | Injection de contexte étendu. |
| Réduire l'information avant de raisonner | `nexus_summarize` | Synthèse de documents. |
| Poser une question | `nexus_ask` | Question directe. **Ne prend PAS de fichiers** (conception volontaire : passez par search, context ou summarize). |
| Comparer plusieurs modèles sur une question | `nexus_compare` | Analyse comparative. |
| Traiter un lot de requêtes | `nexus_batch` | Exécution en série. |

## 4. LA RÈGLE DE PLAN
Le plan local ne s'emploie jamais pour la vitesse, seulement quand les données ne doivent pas sortir.
*Mesure : le rendu est identique au caractère près entre les deux plans, seule la durée change.*

## 5. LES PIÈGES

> **Le tube et le dollar**
> L'usage de `$?` après un tube rend le code du dernier maillon.
> *Mesure : 3 sessions ont commis cette erreur en une heure.*

> **Budget et Raisonnement**
> Un modèle à raisonnement étendu avec un budget trop serré rend une réponse VIDE.
> *Mesure : 1400 jetons consommés pour zéro caractère produit.*

> **Le silence de Python**
> Un run long sans l'option `-u` de python est indiscernable d'un run gelé.
> *Mesure : 3,0 secondes contre 0,0 pour l'affichage de la première ligne.*

## 6. LA MACHINE EST PARTAGÉE
Plusieurs projets cohabitent. Un verrou nommé protège le plan local.
L'outil `nexus_charge` indique l'état de la machine :
- `0` : repos
- `1` : chargée
- `2` : mesure impossible

**Règle d'or :** Un rapport entre grandeurs du même appel survit à une variable non contrôlée, une durée absolue non.

## 7. LES SCRIPTS
Pour les cas non couverts par le MCP, utilisez les scripts via leur **chemin absolu** depuis n'importe quel répertoire. Aucun script ne contient de chemin en dur.

Les quatre scripts les plus utiles pour un projet tiers :
- `C:/local-llm-docker/scripts/nexus_agent.py --tache "analyse" --fichiers "src/" --modele gemma4-31b-cloud --racine "C:/projet"`
- `C:/local-llm-docker/scripts/nexus_charge.py --json`
- `C:/local-llm-docker/scripts/nexus_verrou_machine.py --etat`
- `C:/local-llm-docker/scripts/nexus_appliquer.py resultats.jsonl "tache_01" cible.txt`

Le code de sortie doit être lu SANS tube (voir le piège de la section 5).

## 8. CE QUE CE GUIDE NE DIT PAS
- La configuration initiale du serveur MCP.
- La gestion des clés API pour les modèles cloud.
- Le détail technique de l'indexation sémantique.
- La maintenance du verrou machine en cas de crash système.