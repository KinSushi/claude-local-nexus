# LISTE COMPLÈTE DU LOT — établie avant l'envoi

Tout ce qui est ouvert, mesuré cette nuit, et délégable au banc gratuit.
Un fichier cible par tâche : deux patchs sur le même fichier entrent en collision.

## Ressources jointes à CHAQUE tâche

| ressource | ce qu'elle empêche |
| --- | --- |
| le fichier cible réel | inventer des ancres — 6 sur 7 fabriquées la dernière fois |
| `CODE_PREMIUM.md` | un nombre nu, sans la commande qui l'a produit |
| `LIVRES_PLANCHER.md` | s'arrêter au livre, ou l'ignorer |
| `CONTRAT_EPREUVES_ET_LOI1.md` | oublier la contre-épreuve, la LOI 1, le cycle à trois temps |
| `LIVRES_<thème>.md` | inventer un patron au lieu d'adapter un patron lu |

## Les tâches

| # | cible | défaut mesuré | § | thème |
| --- | --- | --- | --- | --- |
| 1 | `nexus_rituel.py` | 4 verdicts aveugles : boussole, arbres, part déléguée, rédaction | 36-40 | VERIF |
| 2 | `nexus_loi1.py` | `--base HEAD~1` : le cliquet oublie à chaque commit (853 lignes invisibles) | 37 | VERIF |
| 3 | `nexus_appliquer.py` | bannière sur `if stdout:` ; et `<<<FICHIER>>>` jamais lu | 29.1-29.2 | VERIF |
| 4 | `nexus_redaction.py` | compare 976 appels à 56 commits — volume contre traçabilité | 39 | VERIF |
| 5 | **fichier neuf** `epreuve_controles_rituel.py` | aucune contre-épreuve n'existe pour les 12 contrôles | 38-41 | VERIF |
| 6 | `nexus_agent.py` | plan `inconnu` ré-ajouté APRÈS le filtre du disjoncteur | 34.5 | RESILIENCE |
| 7 | `nexus_disjoncteur.py` | écriture non atomique de `circuit_state.json` | 34.1 | RESILIENCE |
| 8 | `nexus_decouper_livres.py` | effet de bord à l'import (`sys.stdout` réenveloppé) | 29 | — |
| 9 | `nexus_extraire_livres.py` | idem | 29 | — |
| 10 | `nexus_indexer_node.py` | idem | 29 | — |
| 11 | *arbitrage* `nexus_garde_production.py` | contournable par `echo >` ; le remède n'est pas « bloquer Bash » | 35 | GARDES |
| 12 | *arbitrage* `nexus_cablage.py` | outil manuel contre mécanisme : 5 scripts `preuve_seule` | 33 | ORCHESTR |

## Ce qui N'EST PAS dans le lot, et pourquoi

* **La troncature qui bannit un modèle sain** et **`ecartes` inopérant** — un agent
  les a déjà corrigés et prouvés en vol ; sa rebase est en cours. Les redonner au
  banc dupliquerait un travail fait.
* **Le `CLAUDE.md` vide à la racine** — décision de l'opérateur, pas un défaut de code.
* **Le câblage des trois outils de corpus** — dépend de l'arbitrage n° 12.

## Contraintes communes, toutes mesurées dans ce dépôt

1. `max_tokens` ≥ 6000 — en dessous, le rendu revient **vide**, pas tronqué.
2. Marqueurs `<<<AVANT>>>` / `<<<APRES>>>` / `<<<FIN>>>`, seuls sur leur ligne.
   Le banc **perd le marqueur de pied** sur les rendus longs : le redemander en tête et en pied.
3. Un bloc `APRES` jamais vide — l'applicateur refuse une suppression pure non demandée.
4. Chaque bloc `AVANT` unique dans le fichier — l'applicateur vérifie et refuse sinon.
5. Jamais le fichier entier, sauf pour la tâche 5 qui crée un fichier neuf.
6. Aucun chiffre nu : la commande qui l'a produit, et sa sortie.
