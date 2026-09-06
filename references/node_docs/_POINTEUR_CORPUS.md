# POINTEUR DE CORPUS — `references/node_docs`

**L'API Node.js v22.23.2 indexée par symbole, lisible par positionnement direct.**

## Pourquoi ce document existe

La matière ne part plus sur GitHub. Mesure du 2026-09-06 : ce rayon pesait **11,08 Mo sur les
20,3 Mo** qu'un clone recevait — **54,6 %**, plus que tout le reste du dépôt réuni, pour un
produit qui pèse 1,46 Mo. Même règle que `references/livres/` et `references/python_libs_docs/` :
la matière reste sur disque et hors historique, seul ce pointeur est suivi.

Le rayon y relève à **double titre** : c'est un corpus, et `all.json` est la *source de
régénération* de `scripts/nexus_indexer_node.py --source`. `.gitignore` pose déjà la règle pour
ce qui se régénère.

## Fiabilité — ✅ **DOCUMENTATION OFFICIELLE, VERBATIM**

Chaque entrée porte la description telle qu'elle figure dans la documentation Node officielle,
avec sa signature et son type. Aucune reformulation.

## Ce qu'il contient

- **4 598 symboles**, Node **v22.23.2**

| symboles | type |
| --- | --- |
| 2 321 | `method` |
| 1 865 | `module` |
| 367 | `class` |
| 44 | `classMethod` |
| 1 | `global` |

Sur disque, trois fichiers :

| poids | fichier | rôle |
| --- | --- | --- |
| 7,24 Mo | `node/22.23.2/all.json` | **source brute**, jamais lue à la consultation |
| 3,84 Mo | `node/22.23.2/symbols.jsonl` | les fragments, lus par `seek` |
| 0,62 Mo | `node/22.23.2/index.tsv` | l'index, 5 colonnes |

## Comment s'en servir

Le rayon se **découvre** — son nom n'est gravé nulle part. `scripts/nexus_livres.py` parcourt
`references/` et retient tout répertoire portant un `index.tsv` (ligne 125), puis lit par
`symbols.jsonl` (ligne 146). Il apparaît dans les résultats sous le nom `22.23.2`.

**TROUVER** :

```bash
python scripts/nexus_livres.py "timeout socket"
# -> Rayon: 22.23.2 | ID: http.http.Server.setTimeout | Resume: Sets the timeout value...
```

**LIRE** — positionnement direct, jamais de chargement complet :

```python
with open(rayon / "symbols.jsonl", "rb") as f:
    f.seek(offset)                    # colonne 2 de index.tsv
    d = json.loads(f.read(longueur).decode("utf-8"))   # colonne 3
```

**Coût mesuré : 115 127 octets pour 120 fragments — 2,86 % du fichier.**

**RÉGÉNÉRER**, si la version de Node change :

```bash
python scripts/nexus_indexer_node.py --source <chemin vers all.json>
```

---

## ⚠ Ce que ce corpus NE couvre PAS

### **UN TROISIÈME SCHÉMA DE FRAGMENT — et un lecteur naïf lit les 4 598 comme VIDES**

Le pointeur de `references/livres` documente deux schémas : `texte` pour `epub` et `packt`,
`implementation` pour `code`. **Ce rayon n'emploie ni l'un ni l'autre.**

Ses champs, mesurés sur un tirage de 120 fragments :

```
docstring_brut · id · lib · lib_version · nom_court · resume · signature · type
```

| lecture | rendu |
| --- | --- |
| avec le seul champ `texte` | **0 / 120 = 0,0 %** |
| en essayant tous les champs porteurs | **116 / 120 = 96,7 %** |

Là où la même erreur avait fait passer le rayon `code` pour lisible à 66,7 %, elle rend ici
**zéro**. Un lecteur qui n'essaie que `texte` conclut que le rayon entier est vide — et il aura
tort de bout en bout. ⇒ **Lire `resume`, puis `docstring_brut`.**

- **3,3 % des fragments (4 sur 120) ne rendent aucun texte**, tous champs essayés. La cause n'est
  pas diagnostiquée, et le nombre n'est pas nul : ne pas annoncer 100 %.
- **Une seule version de Node**, `v22.23.2`. Rien ici ne dit si elle correspond au runtime
  installé, et une API Node change entre versions majeures.
- **Aucune couverture du code source de Node**, seulement son API documentée. Pas d'exemples
  d'usage au-delà de ce que la documentation officielle en donne.
- **`all.json` n'est jamais lu à la consultation.** Il ne sert qu'à régénérer les deux autres
  fichiers. Un clone qui ne le récupère pas peut consulter le rayon, mais pas le reconstruire.
- **Aucune recherche sémantique.** Comme pour `references/livres`, seule la recherche lexicale
  sur la colonne `resume` fonctionne.
- **Non versionné à partir du 2026-09-06.** Un clone ne reçoit plus la matière. Ce document dit
  quoi régénérer et avec quoi ; il ne remplace pas le corpus.

## État mesuré le 2026-09-06

| mesure | valeur | par quoi |
| --- | --- | --- |
| symboles indexés | 4 598 | lignes de `index.tsv`, en-tête déduit |
| poids sorti de l'historique | 11,08 Mo | `os.path.getsize` sur les trois fichiers |
| part d'un clone que cela représentait | 54,6 % | sur 20,3 Mo suivis |
| lecture de 120 fragments | 115 127 octets, 2,86 % | `seek` + `read` |
| **fragments UTILISABLES** | **116/120 = 96,7 %** | tirage aléatoire, tous champs |
| lus avec le seul champ `texte` | **0/120 = 0,0 %** | **la mesure qui conclut à tort** |
| découverte par les outils | par parcours | `os.walk` sur `index.tsv`, aucun nom gravé |

> **Un chiffre figé ment le lendemain.** Tous les nombres ci-dessus se recomptent depuis
> `index.tsv` et `symbols.jsonl` ; aucun n'est gravé dans un outil.
