# Ce qui a ete SORTI de l'arbre du projet

> **Ne pas editer a la main** : les chiffres sont derives des manifestes
> JSON deposes dans le repertoire d'isolation, et une valeur gravee a la
> main ment des le lendemain.
>
> **Generateur** : aujourd'hui un script de session, hors du depot. C'est
> un manque, et il est nomme : tant que ce pointeur n'est pas regenere par
> un script de `scripts/` appele par un rituel, il vieillira en silence.
> Le controle `nexus_separation.py` est commande pour cela.

Consigne de l'operateur, 2026-09-06 : *« les fichiers qui contaminent doit
etre isole ; separes du projet. le projet lui meme a son propre arbre
propre »*, puis *« dans l'arbre propre du projet tu te mets des pointeurs et
marqueurs, ainsi tu sais ce qui est sain »*.

## L'arbre propre, mesure le 2026-09-06 13:32

```
suivi par git (ce qu'un clone recoit)     307 fichiers      20.3 Mo
present dans le dossier                 21949 fichiers    2811.5 Mo
SORTI vers hors-projet                   5729 fichiers    3734.5 Mo
```

## Ou c'est parti

Un repertoire **FRERE** du depot, hors de son arbre :

```
<repertoire du depot>-hors-projet
```

Le chemin n'est pas grave ici : ce fichier est SUIVI par git et partirait
dans le depot avec le chemin d'une seule machine. Sur cette machine, la
racine du depot est celle qui contient ce fichier ; le repertoire
d'isolation porte le meme nom, suffixe de `-hors-projet`.

**Deplace, jamais supprime.** Chaque manifeste JSON porte, pour chaque
entree, son `origine` et sa `destination` : revenir en arriere consiste a
deplacer l'une vers l'autre.

## Ce qui est sorti, par poids

| origine | fichiers | poids |
| --- | ---: | ---: |
| `.nexus/quarantaine` | 5246 | 2624.3 Mo |
| `backups` | 85 | 580.7 Mo |
| `.nexus/livres_kos` | 3 | 452.4 Mo |
| `.nexus/rayon_code_sauvegarde-20260906-082035` | 2 | 41.9 Mo |
| `.nexus/corpus_gardes.md` | 1 | 8.9 Mo |
| `.nexus/node_verif` | 2 | 4.5 Mo |
| `.nexus/node_v2` | 2 | 4.5 Mo |
| `.nexus/bishop.txt` | 1 | 3.6 Mo |
| `.nexus/essai_rayon` | 2 | 1.4 Mo |
| `.nexus/corpus_gardes_dense.md` | 1 | 1.2 Mo |
| `.nexus/t10` | 3 | 1.0 Mo |
| `.nexus/t6` | 3 | 0.9 Mo |
| `.nexus/t7` | 3 | 0.9 Mo |
| `.nexus/t8` | 3 | 0.9 Mo |
| `scripts/.nexus` | 40 | 0.9 Mo |
| `.nexus/tcb_pearson.txt` | 1 | 0.8 Mo |
| `.claude/worktrees/.nexus-arbres` | 12 | 0.8 Mo |
| `.nexus/bishop_gardes.md` | 1 | 0.6 Mo |
| *(et 63 entree(s) de moins de 1 Mo)* | 381 | 10.08 Mo |

## Ce qui est RESTE, et pourquoi

Rien n'est sorti sans que la question *« qui lit ce chemin ? »* ait recu une
reponse mesuree. Sont **restes** parce que le code les lit reellement :

| garde | lu par |
| --- | --- |
| `.nexus/livres_code` | `nexus_conformite.py:1654`, `nexus_indexer_code.py`, `nexus_test.py` |
| `.nexus/fragments_embeddings.jsonl` | l'index semantique, verifie fonctionnel |
| `.nexus/index_doc_libs.tsv`, `index_livres.*` | `nexus_conformite.py`, `nexus_test.py` |
| `.nexus/verbatim`, `outillage`, `sauvegardes` | epreuves et controles |
| `references/` | les corpus, deja regis par leurs propres pointeurs |

Un contre-exemple mesure, qui dit pourquoi la verification etait
necessaire : `.nexus/quarantaine` semblait *lu* par `nexus_quarantaine.py`.
Verification : ce script vise `<racine>/rituels/QUARANTAINE`, pas
`.nexus/quarantaine`. Le mot matchait le **nom du script**, rien d'autre.

## Manifestes

- `MANIFESTE-20260906-112415.json`
- `MANIFESTE-20260906-113155.json`
- `MANIFESTE-20260906-114022.json`
- `MANIFESTE-20260906-115256.json`
- `MANIFESTE-20260906-115747.json`
- `MANIFESTE-20260906-130324.json`
- `MANIFESTE-20260906-133229.json`
