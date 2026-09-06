# QUARANTAINE — ou est le contenu, et pourquoi il n'est pas ici

Les **copies** des worktrees d'agents ont ete deplacees **deux fois**.

**Aujourd'hui**, elles sont hors de l'arbre du projet, dans le repertoire
frere decrit par `rituels/_POINTEUR_HORS_PROJET.md` :

```
<repertoire du depot>-hors-projet/.nexus__quarantaine/
    5246 fichiers, 2624,3 Mo
```

**Auparavant**, elles etaient sous `.nexus/quarantaine/`, et ce pointeur
l'annoncait encore apres leur sortie. **Il pointait donc dans le vide.**

> **Ce que cet incident enseigne, et il est de la meme main que le
> deplacement.** Un pointeur suivi par git est un ENGAGEMENT : celui qui
> deplace la matiere doit mettre a jour tout pointeur qui la designe, dans le
> meme geste. Sinon la convention se retourne — un pointeur faux est pire
> qu'un pointeur absent, parce qu'on le croit.
>
> Aucun controle ne garde cela aujourd'hui. Le manque est nomme, pas comble.

## Pourquoi

Elles etaient dans `rituels/`, le dossier des rituels DU PROJET. Mesure avant
le deplacement :

```
fichiers du projet dans rituels/   41,  29,2 Mo
copies de quarantaine              290, 22,5 Mo   -> 88 % du dossier
```

Le dossier qui porte les rituels du projet portait surtout autre chose. Le
sain et le mis-en-quarantaine se melangeaient dans le meme espace, ce qui est
exactement ce qu'une quarantaine doit empecher.

## Ce qui reste ici, et pourquoi

Les quatre documents d'INDEX, qui portent la **mesure** et non le contenu :

| fichier | ce qu'il porte |
| --- | --- |
| `MANIFESTE.md` / `.json` | 287 fichiers isoles, leur provenance, leur classification |
| `MESURE_BASE_FUSION.json` | 18 entrees commitees, mesurees contre la base de fusion |
| `MESURE_NON_COMMITE.json` | 154 entrees non commitees, mesurees contre leur propre HEAD |
| `RECONCILIATION.md` | le dossier de reconciliation, commande exacte par fichier |

Meme regle que `references/livres/_POINTEUR_CORPUS.md` : ce qui se **regenere**
n'est pas versionne, ce qui porte la **mesure** l'est.

Les copies se refont en une commande tant que les worktrees existent :

```
python scripts/nexus_quarantaine.py
```

Verifie avant le deplacement : **45 worktrees sur 45 presents**.
