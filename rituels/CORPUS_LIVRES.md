# Le corpus de livres — inventaire, et comment y entrer

> **À lire AVANT de concevoir un mécanisme**, pas après. Mesure du 2026-09-02 : une nuit
> entière passée à réinventer des gardes pendant qu'un chapitre intitulé *« Adding production
> guardrails »* attendait à **2 914 octets** de distance.
>
> Chaque chiffre de ce document a été mesuré sur le disque, jamais estimé.

---

## 1. La règle, et pourquoi la première version ne suffisait pas

**« L'index se lit avant »** était trop faible : on peut lire un index et y chercher la mauvaise
chose. J'ai cherché `orchestrator` et trouvé une classe de `sktime` — la réponse était correcte,
ma question était la voisine.

> **Avant de concevoir un mécanisme, chercher dans l'index le chapitre qui porte SON NOM.**
> Pas « des idées sur le sujet » — le chapitre qui traite exactement de la chose qu'on
> s'apprête à inventer.

Trois mots auraient suffi cette nuit-là : `guardrails`, `timeout`, `permission`.

---

## 2. Ce que contient le corpus

**24 livres · 20 304 fragments indexés · 3 rayons**

| rayon | fragments | contenu |
| --- | --- | --- |
| `references/livres/epub/` | 11 377 | chapitres entiers |
| `references/livres/packt/` | 6 698 | chapitres techniques |
| `references/livres/code/` | 2 232 | **le code source des livres**, indexé par symbole |

### Les sept livres sur les agents — 2 590 fragments

| fragments | titre |
| --- | --- |
| 543 | **30 Agents Every AI Engineer Must Build** |
| 446 | **Design Multi-Agent AI Systems Using MCP and A2A** |
| 361 | Context Engineering for Multi-Agent Systems |
| 346 | Agentic Coding with Claude Code |
| 344 | Agentic AI for Offensive Cybersecurity |
| 280 | Building Agentic AI Systems |
| 270 | Architecting AI Software Systems |

### Les dix-sept autres

`Machine Learning for Algorithmic Trading` (1 072) · `Modern C++ Programming Cookbook` (773) ·
`Python Automation Cookbook` (635) · `50 Algorithms Every Programmer Should Know` (588) ·
`Deep Learning with C++` (517) · `Adversarial AI — Attacks, Mitigations and Defense
Strategies` (486) · `Deep Reinforcement Learning Hands-On` (470) · `Python for Algorithmic
Trading Cookbook` (465) · `Beginning C++ Game Programming` (435) · `Artificial Intelligence for
Cybersecurity` (400) · `Mathematics of Machine Learning` (397) · `Python Machine Learning By
Example` (380) · `Artificial Intelligence with Python` (345) · `Generative AI with
LangChain` (331) · `Graph Machine Learning` (294) · `MATLAB for Machine Learning` (264) ·
`Bayesian Analysis with Python` (215)

---

## 3. Comment y entrer — trois gestes, aucun modèle

### Geste 1 — TROUVER par titre

```powershell
python -c "import pathlib; [print(l.split(chr(9))[4]) for l in pathlib.Path('references/livres/epub/index.tsv').read_text(encoding='utf-8',errors='replace').splitlines()[1:] if 'guardrail' in l.lower()]"
```

Ou plus simplement :

```bash
grep -ihE "guardrail|timeout|permission" references/livres/*/index.tsv | cut -f5
```

### Geste 2 — LIRE par positionnement direct

Chaque ligne de `index.tsv` porte `id · offset_octets · longueur_octets · type · resume`.
Le fragment se lit dans `symbols.jsonl` du **même répertoire** :

```python
with open(rayon / "symbols.jsonl", "rb") as f:
    f.seek(offset)
    fragment = json.loads(f.read(longueur).decode("utf-8"))
    texte = fragment["texte"]
```

**Coût mesuré : 2 914 octets sur 26 161 265** — soit 0,011 % du corpus pour un chapitre entier.
Ne jamais charger `symbols.jsonl` en entier.

### Geste 3 — le code source, par `nexus_doc`

Le rayon `code/` porte des **symboles**, donc il est déjà atteignable :

```powershell
python scripts/nexus_doc.py run_self_improvement_loop
```

---

## 4. Ce que le corpus a déjà rendu

**« Building coordination guardrails »** — *Design Multi-Agent AI Systems Using MCP and A2A*,
2 914 octets. Ses six prescriptions, et ce que nous faisions à la place :

| le chapitre | notre pratique avant lecture |
| --- | --- |
| **Timeout enforcement** — *fail gracefully rather than hanging indefinitely* | 900 s d'attente muette, deux rendus perdus |
| **Circuit breakers** — *stop calling it rather than generating more failures* | fait **à la main** |
| **Dependency validation** au déploiement | absent |
| **Idempotency** déclarée par opération | absent |
| **State validation** par invariants en tâche de fond | présent par accident |

Et ses quatre questions de **Coordination testing**, qui décrivaient notre nuit :
*agent lent ou muet · données malformées · messages désordonnés · deux agents sur la même
ressource*.

---

## 5. Les bibliothèques Python — 63 paquets, un autre outil

Ce corpus-là est distinct, et il a son propre accès :

```powershell
python scripts/nexus_doc.py subprocess.run      # 166 507 symboles, ~280 jetons par consultation
python scripts/nexus_doc.py --paquets           # la liste des 63
```

`MetaTrader5 · arch · catboost · duckdb · hmmlearn · hypothesis · lifelines · lightgbm ·
matplotlib · numba · numpy · onnx · optuna · pandas · polars · pyarrow · pydantic · pytest ·
scikit-learn · scipy · shap · sktime · statsmodels · stumpy · torch · tsfresh · xgboost` — et
36 autres.

> **L'index lit l'entrée par `seek`, jamais le fichier.** Consulter coûte moins cher que relire
> trois lignes de code, et ne peut pas halluciner une signature.

---

## 6. L'ordre, et il a été payé

    1. `ls` du rayon          l'inventaire MONTRE
    2. l'index                il dit ce qui existe
    3. un fragment ENTIER     la structure s'y révèle
    4. les embeddings         ils CHERCHENT — en dernier

> **Un essaim d'embeddings répond aux questions qu'on lui pose ; il ne dit jamais ce qu'on n'a
> pas pensé à demander. L'inventaire brut, lui, le dit.**

**Mesure contre les embeddings, faite ici** : un index sémantique des 20 304 **résumés**
(`all-minilm` local, 108 s, coût nul) rend des **tables des matières** sur une requête en
langage naturel. La cause est de conception : *un titre ne contient pas les mots de la
question*. Le `grep` sur les résumés puis le `seek` ont suffi à tout ce qui a servi cette nuit.
