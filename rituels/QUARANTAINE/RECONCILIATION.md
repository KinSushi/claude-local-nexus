# DOSSIER DE RECONCILIATION

> Ce dossier REMPLACE une premiere version fautive. Elle comparait chaque
> fichier d'agent au `main` COURANT et annoncait donc « l'agent a retire N
> lignes » quand la verite etait « `main` a gagne N lignes depuis ».
> Consequence : un agent y etait accuse d'avoir detruit 87 179 lignes. Verifie
> contre sa base de fusion : **aucun changement** sur les trois fichiers.

La docstring de `nexus_quarantaine.py` nommait deja ce piege :

> *« un premier comptage naif donnait 32 a 34 fichiers modifies par agent.
> C'etait faux : ce diff inclut tout le RETARD DE BRANCHE. La bonne mesure
> passe par la base de fusion. »*

Elle avait ete lue avant l'erreur.

## L'etat reel, sur les deux mesures justes

| population | agents | entrees | lignes |
| --- | --- | --- | --- |
| travail **commite** (`git diff base..branche`) | 5 | 18 | +2797 / -280 |
| travail **non commite** (`git diff HEAD` dans le worktree) | 40 | 102 modifies + 52 neufs | +2994 / -474 |

**Suppressions massives : ZERO dans les deux mesures.** Aucun agent n'a
detruit quoi que ce soit contre sa propre base.

## Le geste : PRENDRE, jamais greffer

```
git checkout <branche> -- <fichier>          pour le commite
cp rituels/QUARANTAINE/<agent>/<fichier> .   pour le non commite
```

Une session voisine a paye l'autre choix : une greffe par cherry-pick a
supprime 28 456 fichiers dont 4 seulement etaient en conflit ; les 28 452
autres sont partis en silence.

## 1. Travail COMMITE, avec fiche de preuve

| fichier | agent | + | - | rubriques | epreuves | commande |
| --- | --- | --- | --- | --- | --- | --- |
| `QUARANTAINE.md` | `755c603728d190` | 456 | 0 | 7/8 | False/False/False | `git checkout worktree-agent-ae2755c603728d190 -- QUARANTAINE.md` |
| `scripts/nexus_agent.py` | `755c603728d190` | 24 | 19 | 7/8 | False/False/False | `git checkout worktree-agent-ae2755c603728d190 -- scripts/nexus_agent.py` |
| `scripts/nexus_disjoncteur.py` | `755c603728d190` | 22 | 3 | 7/8 | False/False/False | `git checkout worktree-agent-ae2755c603728d190 -- scripts/nexus_disjoncteur.py` |
| `QUARANTAINE.md` | `5cd08dccd3fd97` | 625 | 0 | 6/8 | False/True/True | `git checkout worktree-agent-a415cd08dccd3fd97 -- QUARANTAINE.md` |
| `scripts/nexus_filet.py` | `5cd08dccd3fd97` | 406 | 0 | 6/8 | False/True/True | `git checkout worktree-agent-a415cd08dccd3fd97 -- scripts/nexus_filet.py` |
| `rituels/CHECKLIST_LIVRE_VS_CODE.md` | `ae5bcacf5d3042` | 83 | 11 | 5/8 | False/False/False | `git checkout worktree-agent-a9bae5bcacf5d3042 -- rituels/CHECKLIST_LIVRE_VS_CODE.md` |
| `rituels/outillage_reference.json` | `b278a9ee2836a5` | 5 | 6 | 5/8 | False/False/False | `git checkout worktree-agent-a0bb278a9ee2836a5 -- rituels/outillage_reference.json` |
| `epreuves/epreuve_orphelines.py` | `b278a9ee2836a5` | 17 | 0 | 5/8 | False/False/False | `git checkout worktree-agent-a0bb278a9ee2836a5 -- epreuves/epreuve_orphelines.py` |
| `epreuves/epreuve_progres.py` | `b278a9ee2836a5` | 195 | 163 | 5/8 | False/False/False | `git checkout worktree-agent-a0bb278a9ee2836a5 -- epreuves/epreuve_progres.py` |
| `epreuves/epreuve_rendu_vide.py` | `ae5bcacf5d3042` | 152 | 0 | 5/8 | False/False/False | `git checkout worktree-agent-a9bae5bcacf5d3042 -- epreuves/epreuve_rendu_vide.py` |
| `scripts/nexus_cablage.py` | `b278a9ee2836a5` | 18 | 1 | 5/8 | False/False/False | `git checkout worktree-agent-a0bb278a9ee2836a5 -- scripts/nexus_cablage.py` |
| `scripts/nexus_checklist_progres.py` | `b278a9ee2836a5` | 43 | 17 | 5/8 | False/False/False | `git checkout worktree-agent-a0bb278a9ee2836a5 -- scripts/nexus_checklist_progres.py` |
| `scripts/nexus_conformite.py` | `b278a9ee2836a5` | 10 | 5 | 5/8 | False/False/False | `git checkout worktree-agent-a0bb278a9ee2836a5 -- scripts/nexus_conformite.py` |
| `scripts/nexus_outillage.py` | `b278a9ee2836a5` | 29 | 2 | 5/8 | False/False/False | `git checkout worktree-agent-a0bb278a9ee2836a5 -- scripts/nexus_outillage.py` |
| `scripts/nexus_progres.py` | `b278a9ee2836a5` | 42 | 39 | 5/8 | False/False/False | `git checkout worktree-agent-a0bb278a9ee2836a5 -- scripts/nexus_progres.py` |
| `scripts/nexus_rituel.py` | `b278a9ee2836a5` | 69 | 13 | 5/8 | False/False/False | `git checkout worktree-agent-a0bb278a9ee2836a5 -- scripts/nexus_rituel.py` |
| `scripts/nexus_test.py` | `ae5bcacf5d3042` | 6 | 1 | 5/8 | False/False/False | `git checkout worktree-agent-a9bae5bcacf5d3042 -- scripts/nexus_test.py` |

## 2. Travail NON COMMITE, fichiers de code, par ampleur

Ces fichiers n'existent QUE dans l'arbre de travail de leur worktree et dans
la copie de quarantaine. Retirer un worktree les detruirait.

| fichier | agent | etat | + | - | rubriques |
| --- | --- | --- | --- | --- | --- |
| `epreuves/epreuve_repli_epuise.py` | `5f543aaa6e4d34` | MODIFIE | 197 | 0 | 6/8 |
| `tools/nexus-mcp/server.js` | `66d882218a276d` | MODIFIE | 149 | 43 | 7/8 |
| `scripts/nexus_conformite.py` | `8fb7354cc50b30` | MODIFIE | 124 | 45 | 7/8 |
| `scripts/nexus_disjoncteur.py` | `a4421aa8062ff1` | MODIFIE | 138 | 15 | 7/8 |
| `scripts/nexus_charge.py` | `07e433b871704d` | MODIFIE | 122 | 4 | 0/8 |
| `scripts/nexus_socle.py` | `8fb7354cc50b30` | MODIFIE | 47 | 72 | 7/8 |
| `scripts/nexus_garde_ecriture.py` | `bdfccf377cfffa` | MODIFIE | 102 | 10 | 7/8 |
| `scripts/nexus_valide.py` | `d763084f29adf5` | MODIFIE | 103 | 7 | 7/8 |
| `scripts/nexus_agent.py` | `5f543aaa6e4d34` | MODIFIE | 62 | 18 | 6/8 |
| `epreuves/epreuve_garde_ecriture.py` | `14f9783bcb3e7f` | MODIFIE | 58 | 16 | 3/8 |
| `epreuves/epreuve_reprise_avant_repli.py` | `5f543aaa6e4d34` | MODIFIE | 46 | 14 | 6/8 |
| `epreuves/epreuve_garde_lecture.py` | `14f9783bcb3e7f` | MODIFIE | 34 | 17 | 3/8 |
| `scripts/stop.ps1` | `e8dae802fa4a1b` | MODIFIE | 29 | 15 | 0/8 |
| `scripts/nexus_capability.py` | `13c9acd701d299` | MODIFIE | 43 | 0 | 6/8 |
| `scripts/nexus_appliquer.py` | `ea6f5f883f4469` | MODIFIE | 37 | 5 | 0/8 |
| `epreuves/epreuve_armer_garde.py` | `14f9783bcb3e7f` | MODIFIE | 20 | 12 | 3/8 |
| `scripts/nexus_generate.py` | `df6cc4a6aec704` | MODIFIE | 26 | 6 | 0/8 |
| `scripts/nexus_agent.py` | `923e06ae11d5df` | MODIFIE | 23 | 7 | 6/8 |
| `scripts/restore.ps1` | `e8dae802fa4a1b` | MODIFIE | 14 | 15 | 0/8 |
| `scripts/nexus_doc.py` | `e6d8711708973c` | MODIFIE | 22 | 2 | 0/8 |
| `scripts/nexus_agent.py` | `ea6f5f883f4469` | MODIFIE | 20 | 4 | 0/8 |
| `scripts/nexus_test.py` | `8fb7354cc50b30` | MODIFIE | 23 | 0 | 7/8 |
| `scripts/mesure_rendu_vide.py` | `ce1f4953606cae` | MODIFIE | 17 | 4 | 0/8 |
| `epreuves/epreuve_garde_shell.py` | `14f9783bcb3e7f` | MODIFIE | 10 | 10 | 3/8 |
| `scripts/console_tools.py` | `47b54a536e6499` | MODIFIE | 20 | 0 | 0/8 |
| `scripts/nexus_essaim.py` | `ea6f5f883f4469` | MODIFIE | 17 | 1 | 0/8 |
| `scripts/Initialize-Nexus.ps1` | `e8dae802fa4a1b` | MODIFIE | 8 | 9 | 0/8 |
| `scripts/nexus_disjoncteur.py` | `ea6f5f883f4469` | MODIFIE | 12 | 1 | 0/8 |
| `scripts/nexus_doc.py` | `ce1f4953606cae` | MODIFIE | 10 | 2 | 0/8 |
| `scripts/nexus_doc.py` | `2638a810ecfdd4` | MODIFIE | 10 | 2 | 0/8 |

## 3. Ce que ce dossier ne dit pas

- il **compte des lignes**, il ne juge aucun changement sur le fond ;
- une fiche de preuve PRESENTE ne veut pas dire REMPLIE : la colonne
  rubriques donne le compte, et le critere porte sur la presence d'une
  reponse, jamais sur son contenu ;
- **aucun** des 157 fichiers ne porte les huit rubriques ;
- aucun worktree n'a ete detruit, et aucun ne doit l'etre avant que la
  ligne correspondante de ce dossier soit traitee.
