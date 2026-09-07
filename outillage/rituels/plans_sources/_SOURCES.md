# Plans sources -- point de retour avant fusion

Ces fichiers sont deposes ici VERBATIM, avant toute fusion,
pour que la fusion soit un commit distinct et annulable.

Consigne de l'operateur : un seul plan a la fin, mais la
fusion doit etre reversible.

| fichier | octets | lignes | sha256 (16) | origine |
| --- | ---: | ---: | --- | --- |
| `PLAN_A_isolation_et_frappes_cloud.md` | 13785 | 292 | `011f2a85b814dde0` | plan de mode PLAN du 2026-09-05, hors git, ecrit avant l'audit Fable |
| `PLAN_B_unifie_corpus_ouvert.md` | 9828 | 223 | `9545ac7dbb527041` | plan du 2026-09-06, hors git, ecrit apres l'ouverture du corpus |
| `../PLAN_MAITRE_2026-09-01.md` | 19044 | 288 | `f04b9636c0d9c29a` | deja suivi ; porte des faits perimes, dont le port 11435 |

## Comment revenir en arriere

La fusion sera un commit SEPARE de celui-ci.

    git log --oneline -- outillage/rituels/
    git revert <le commit de fusion>

Le present commit reste alors en place, et les trois sources
sont retrouvees telles qu'elles etaient avant la fusion.
