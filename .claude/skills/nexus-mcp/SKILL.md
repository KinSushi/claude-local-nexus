---
name: nexus-mcp
description: "Employer cette competence lorsqu'une session s'apprete a deleguer du travail, a chercher dans le depot, a poser un patch, a mesurer la machine ou a choisir un modele."
---

## Outils exposes par le pont MCP Nexus

| Outil | Fonction | Parametres |
|---|---|---|
| nexus_ask | Deleguer une tache a un modele expose par la passerelle. | prompt: string, paths: string[], system: string, model: string, profile: string, max_tokens: integer |
| nexus_route | Confier la tache au routeur adaptatif de LiteLLM. | prompt: string, system: string, plane: string, max_tokens: integer |
| nexus_context | Traiter un corpus plus grand que toute fenetre contextuelle. | paths: string[], text: string, instruction: string, model: string, context_tokens: integer |
| nexus_vision | Analyser une image en local sans l'envoyer hors machine. | path: string, prompt: string, model: string, max_tokens: integer, raisonnement: boolean |
| nexus_summarize | Resumer des fichiers du depot via un modele local. | paths: string[], instruction: string, model: string, context_tokens: number, fusionner: boolean |
| nexus_index_build | Construire l'index d'embeddings du depot en local. | root: string, model: string |
| nexus_search | Rechercher hybride dans l'index local du depot. | query: string, k: integer, model: string |
| nexus_batch | Executer plusieurs taches independantes, eventuellement en parallele. | tasks: object[] (prompt: string, model: string, system: string, max_tokens: integer), model: string |
| nexus_compare | Comparer plusieurs modeles sur la meme demande. | prompt: string, models: string[], system: string, max_tokens: integer |
| nexus_profile | Connaitre les limites reelles de la machine hote. | aucun |
| nexus_savings | Mesurer le volume delegue et ce qu'il aurait coute sur Claude. | jours: integer |
| nexus_charge | Rapporter qui occupe la machine et la memoire disponible. | aucun |
| nexus_apply | Appliquer un patch ancre rendu par un modele. | texte: string, cible: string, nom: string |
| nexus_livres | Chercher dans les 24 livres techniques par sens, en local. | question: string |
| nexus_verrou | Constater l'etat des verrous de machine partages entre projets. | aucun |
| nexus_models | Lister les modeles disponibles dans la passerelle. | aucun |

## Regles tirees des erreurs deja payees

- Les noms de parametres ne se devinent pas : il faut employer ceux du tableau ci-dessus, avec la casse exacte.
- Quatre outils ne declarent aucun parametre : nexus_profile, nexus_charge, nexus_verrou et nexus_models. Tout argument passe a l'un d'eux est ignore en silence.
- Un patch rendu par un modele s'ancre avec des marqueurs a trois chevrons de chaque cote, encadrant les blocs AVANT, APRES et FIN. Le texte du bloc AVANT doit figurer exactement une seule fois dans le fichier vise.

## Ce que le pont ne fait pas

- Il ne cree pas de fichier sous un nom propre. La creation de fichier est obtenue via nexus_apply, quand le texte du patch porte les marqueurs de creation.
- Il ne remplace pas les outils de fichier natifs de Claude Code.

En cas de desaccord, la source faisant foi est outillage/rituels/README_MCP.md, genere depuis le serveur.
