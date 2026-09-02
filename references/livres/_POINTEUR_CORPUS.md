# POINTEUR DE CORPUS — `references/livres`

**24 ouvrages techniques découpés en fragments indexés, lisibles par positionnement direct.**

## Fiabilité — ✅ **TEXTE VERBATIM**

Chaque fragment porte le texte tel qu'il figure dans l'ouvrage, avec son livre, son document
source et son titre de section. Aucune reformulation, aucun résumé généré.

> **À consulter AVANT de concevoir un mécanisme — jamais après.** Mesure du 2026-09-02 : une
> nuit entière passée à réinventer des gardes de coordination pendant qu'un chapitre intitulé
> *« Building coordination guardrails »* attendait à **2 914 octets** de distance.

## Ce qu'il contient

- **20 304 fragments** · 3 rayons · 24 ouvrages
- par rayon : `epub` × 11 377 · `packt` × 6 698 · `code` × 2 232
- **2 590 fragments sur les agents IA**, répartis sur 7 ouvrages

| fragments | ouvrage |
| --- | --- |
| 543 | 30 Agents Every AI Engineer Must Build |
| 446 | Design Multi-Agent AI Systems Using MCP and A2A |
| 361 | Context Engineering for Multi-Agent Systems |
| 346 | Agentic Coding with Claude Code |
| 344 | Agentic AI for Offensive Cybersecurity |
| 280 | Building Agentic AI Systems |
| 270 | Architecting AI Software Systems |

Les 17 autres — trading algorithmique, C++, cybersécurité offensive, mathématiques du ML,
apprentissage par renforcement — sont listés dans `rituels/CORPUS_LIVRES.md`.

## Provenance

Ingérés depuis des ouvrages au format EPUB, découpés par section, et indexés avec leur décalage
en octets. Le rayon `code` porte le **code source** des ouvrages, indexé par symbole.

## Comment s'en servir

**La règle**, et elle est plus forte que « lire l'index » :

> **Avant de concevoir un mécanisme, chercher dans l'index le chapitre qui porte SON NOM.**
> Pas « des idées sur le sujet » — le chapitre qui traite exactement de la chose qu'on
> s'apprête à inventer.

**TROUVER** — recherche lexicale sur la colonne `resume` :

```bash
grep -ihE "guardrail|timeout|permission" references/livres/*/index.tsv | cut -f5
```

**LIRE** — positionnement direct, jamais de chargement complet :

```python
with open(rayon / "symbols.jsonl", "rb") as f:
    f.seek(offset)                       # colonne 1 de index.tsv
    texte = json.loads(f.read(longueur).decode("utf-8"))["texte"]   # colonne 2
```

**Coût mesuré : 2 914 octets sur 26 161 265** — 0,011 % du corpus pour un chapitre entier.

**Le rayon `code`** porte des symboles : `python scripts/nexus_doc.py <symbole>`.

## Entrées de premier niveau

`references/livres/epub/` · `references/livres/packt/` · `references/livres/code/`

Chaque rayon porte `index.tsv` (`id · offset_octets · longueur_octets · type · resume`) et
`symbols.jsonl`. Les rayons se **découvrent** — aucun nom n'est gravé dans les outils.

---

## ⚠ Ce que ce corpus NE couvre PAS

*Section absente du pointeur des bibliothèques Python, et c'est son défaut mesuré : un pointeur
qui énumère ce qu'il contient sans déclarer ce qu'il omet transforme une liste en promesse.*

- **Aucune recherche sémantique utilisable.** Un index d'embeddings des 20 304 résumés a été
  construit (modèle local, 108 s, coût nul) : **ses résultats sont mauvais** — il rend des
  tables des matières sur une requête en langage naturel. Cause de conception : *un titre ne
  contient pas les mots de la question*. L'index sur les **textes** n'est pas fonctionnel.
- **Le rayon `code` seul est atteignable par `nexus_doc`**, parce qu'il porte des symboles.
  `epub` et `packt` ne sont atteignables que par `grep` sur les résumés puis `seek`.
- **DEUX SCHÉMAS DE FRAGMENT COEXISTENT, et un lecteur naïf en lit 2 232 comme vides.**
  `epub` et `packt` portent leur contenu dans `texte` ; **`code` le porte dans
  `implementation`**. Mesuré le 2026-09-02 : un tirage lisant le seul champ `texte` rend
  **80/120 = 66,7 %** et conclut « rayon `code` illisible » — faux. En lisant les deux champs :
  **180/180 = 100 %**. ⇒ Le lecteur doit essayer `texte` **puis** `implementation`.
- **Aucune vérification que les fragments couvrent l'intégralité des ouvrages.** Le découpage
  par section peut avoir omis des passages, et rien ici ne le mesure. Le nombre de fragments
  n'est pas une preuve de complétude.
- **Aucune numérotation stable pour citation.** Un modèle à qui l'on fournit un fragment ne
  transcrit pas son identifiant long : il le paraphrase. Mesure d'une session voisine :
  **0 ligne sur 30** portait l'identifiant réel malgré une consigne explicite. Pour faire citer
  un fragment, le **numéroter** à l'assemblage et résoudre soi-même.
- **Les ouvrages ne sont pas datés dans l'index.** Un livre sur un outil qui évolue vite décrit
  un état passé, et rien ici ne dit lequel.

## État mesuré le 2026-09-02

| mesure | valeur | par quoi |
| --- | --- | --- |
| fragments indexés | 20 304 | somme des `index.tsv`, en-têtes déduits |
| lecture d'un chapitre | 2 914 octets sur 26 161 265 | `seek` + `read`, mesuré |
| recherche lexicale | fonctionnelle | `grep` sur `resume` |
| recherche sémantique | **non utilisable** | index construit, résultats mauvais |
| **fragments UTILISABLES** | **180/180 = 100 %** | tirage aléatoire, `seek`, les DEUX schémas |
| lus avec le seul champ `texte` | 80/120 = 66,7 % | **la mesure qui conclut à tort** |
| rappel automatique | ✅ actif | hook de reprise, nombre dérivé à chaque session |

**LA TÉTRADE, convention reçue de la session EA MT5 le 2026-09-02** — elle vaut pour tout
corpus, et elle a mordu ici au premier essai :

    DOCUMENTÉ  /  INDEXÉ  /  LISIBLE (1ᵉʳ niveau)  /  UTILISABLE (le champ réellement appelé)

> **`import arch` réussit, `arch.univariate.GARCH` échoue.** Chez eux, deux bibliothèques sur
> dix-sept se sont effondrées au chargement profond. Chez moi, le même angle mort a fait passer
> un rayon entier pour illisible. **Une mesure de premier niveau répond à la question voisine**
> — et un document faux et FRAIS est pire qu'un document vieux.

> **Un chiffre figé ment le lendemain.** Tous les nombres de ce document se recomptent par
> parcours des `index.tsv` ; aucun n'est gravé dans un outil.
