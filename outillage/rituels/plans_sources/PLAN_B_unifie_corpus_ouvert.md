# PLAN UNIFIÉ — isolation, corpus, anti-dérive

État au 2026-09-06. Chaque chiffre a été **mesuré ce tour**, jamais rappelé
de mémoire. Les sources livresques sont nommées ; ce qu'elles ne couvrent
pas est dit explicitement, parce qu'un corpus qui paraît couvrir est plus
dangereux qu'un corpus muet.

---

## 0. LA MESURE QUI CHANGE TOUT — le corpus était fermé, il est ouvert

Cinq recherches sur des sujets que les livres **traitent réellement**
rendaient zéro. Cause mesurée : la recherche interrogeait le champ
`resume`, c'est-à-dire des **titres de section**. Jamais le texte.

Contre-épreuve faite ce tour, même requête :

```
nexus_livres.py "quality gate"            ->  Verdict negatif: aucun resultat
nexus_livres.py --texte "quality gate"    ->  10 fragments reels
```

Le correctif `--texte` est **posé et prouvé**. 70 fragments, 235 Ko de
texte de livres, ont ensuite été récoltés et synthétisés par le banc.

**Conséquence sur tout ce qui suit** : le plan précédent affirmait que
« le corpus ne couvre pas ce problème ». C'était faux, et la faute était
d'instrument.

**Défaut résiduel, nommé** : le verdict négatif annonce encore chercher
« dans id, type ou resume » même avec `--texte`. Le message n'a pas suivi
le correctif. Un message qui décrit mal ce qu'il a fait envoie au mauvais
diagnostic — c'est ainsi que la cécité a duré.

---

## 1. LA CAUSE RACINE, ENFIN NOMMÉE — et elle invalide un diagnostic précédent

`scripts/nexus_agent.py:313` refuse tout fichier hors de la racine :

```python
if not sous_racine(complet, racine):
    refus.append("%s (hors de la racine de travail %s ; --racine pour en"
                 " designer une autre, ou copier le fichier sous la racine)")
```

Le scratchpad de l'orchestrateur est hors du dépôt. **Aucun extrait
n'est jamais arrivé au banc** : ni en v39, ni en v41, ni en v42.

| lot | avec la mauvaise racine | avec `--racine` |
| --- | --- | --- |
| v42, 5 tâches | 4 523 jetons, 5 refus honnêtes | **57 565 jetons**, 5 synthèses |

**Le diagnostic que j'avais posé était faux.** J'avais accusé les numéros
de ligne des extraits de rendre l'ancre impossible. Les sept
« AUCUN DEFAUT SUR » du lot v39 n'étaient pas de la prudence : c'était le
vide. La garde disait par où passer ; sa liste de refus n'a pas été lue.

**Ce que cela coûte, chiffré** : 7 tâches sur 12 perdues au lot v39, plus
1 sur 3 au lot v41, plus 5 sur 5 au lot v42 — **13 tâches** produites
dans le vide avant que la cause soit vue.

---

## 2. CE QUI EST POSÉ ET PROUVÉ CE TOUR

| correctif | preuve |
| --- | --- |
| `nexus_livres.py --texte` | contre-épreuve : 0 sans l'option, 10 avec |
| `nexus_traque.py` périmètre | `py_compile` OK, périmètre étendu |
| `nexus_cablage.py` périmètre | `py_compile` OK |
| `Initialize-Nexus.ps1` ×2 | 2 chemins morts réparés |

Six blocs sur huit, tous vérifiés **uniques** dans le fichier réel avant
écriture. Deux refusés : ancre absente, non posés.

---

## 3. CE QUI EST MESURÉ ET NON CORRIGÉ

| défaut | mesure exacte |
| --- | --- |
| `hooks cables` aveugle | annonce **5**, le settings en déclare **8**, rend **VERT** |
| `gardes accordes` | **ALERTE** : `nexus_garde_edition.py` cherché dans `scripts/` |
| périmètre ruff | `scripts` + `tools` seulement ; 194 fichiers Python jamais analysés |
| périmètre PSScriptAnalyzer | 2 `.ps1` d'`outillage/` jamais analysés |
| 6 skips silencieux | `nexus_test.py` : `:2342 :2427 :2962 :3005 :3059 :3493` |
| `nexus_agent.py` en double | `scripts/` et `outillage/`, **74 763 octets identiques**, rien ne le garde |
| étiquette injectée | `nexus_agent.py:971` insère l'avertissement **dans** le rendu |
| U+202F | `nexus_frontiere.py` plante sur console cp1252 — le **9ᵉ** cas du dépôt |

---

## 4. CE QUE LES LIVRES ÉTABLISSENT — et ce qu'ils ne disent pas

### 4.1 Le principe qui commande tout le reste

> **« Les quality-gates doivent être recalculés à chaque exécution ; un
> seuil fixé une fois devient invalide dès que les données ou le périmètre
> changent. »** — *Architecting AI Software Systems*

C'est exactement le défaut du dépôt, écrit dans un ouvrage. Un cliquet qui
compte une **quantité** attachée à un **périmètre** ne distingue pas
« corrigé » de « plus regardé ».

**Corollaire, du même corpus** : *« le contrôle ne porte que sur les
fichiers explicitement listés ou sur le diff fourni par la CI »* — donc le
périmètre se **dérive**, il ne se grave pas.

### 4.2 La frontière structurelle, que je n'avais pas envisagée

> Déclarer les paquets dans `pyproject.toml` / `setup.cfg` : les imports
> transversaux sont alors **bloqués par le gestionnaire de paquets**.
> — *Generative AI with LangChain*, *Python Automation Cookbook 3e*

Plus fort qu'un contrôle : une frontière que l'outillage fait respecter
au lieu de la vérifier après coup.

### 4.3 L'ordre de remboursement de la dette

> Prioriser par impact et complexité. — *Architecting AI Software Systems*

Appliqué ici : **98 littéraux `"scripts"`** d'abord (densité forte, risque
faible), **point d'entrée mixte** ensuite (complexité haute, il bloque le
détachement), **paires copiées** en dernier (impact faible).

### 4.4 CE QUE LE CORPUS NE COUVRE PAS — dit par le banc lui-même

- aucune méthode de détection automatisée des **dépendances croisées** ;
- aucune de repérer qu'un test **s'est exécuté en silence** ;
- aucun critère pour dire **quand une réécriture coûte plus** que la dette ;
- aucune gestion des **chemins multiplateformes** PowerShell / JavaScript ;
- **la séparation producteur/auditeur — votre LOI 1 — n'est PAS couverte.**

Ce dernier point est le plus utile : la règle qui gouverne ce dépôt ne
vient d'aucun livre du corpus. Elle est à vous, et rien ne la valide de
l'extérieur. Les livres sont le plancher (§0.8) ; ici il n'y a pas même de
plancher, et ce qui suit doit donc s'appuyer sur la **mesure** seule.

---

## 5. LE PLAN, PAR ORDRE — chaque étape rend un CONTRÔLE, pas un paragraphe

### Vague 1 — RENDRE LES CONTRÔLES VOYANTS *(la cécité masque tout le reste)*

| # | cible | contre-épreuve exigée |
| --- | --- | --- |
| 1 | `nexus_conformite.py:589,593` regex des hooks | doit compter **8**, pas 5 |
| 2 | `nexus_conformite.py:167` repli `outillage/` | l'ALERTE actuelle disparaît |
| 3 | `nexus_outillage.py:243,471` périmètres | 21 → ~99 violations, `--rebaseline` **motivé** |
| 4 | `nexus_test.py` 6 skips | un fichier absent doit **échouer**, jamais sauter |

La hausse de 21 à 99 n'est **pas** une régression : c'est la fin d'une
cécité. Le rebasement se fait avec sa raison écrite, jamais l'inverse.

### Vague 2 — LA FRONTIÈRE, STRUCTURELLE PUIS GARDÉE

| # | livrable |
| --- | --- |
| 5 | `pyproject.toml` déclarant les paquets — frontière **structurelle** (§4.2) |
| 6 | `nexus_frontiere.py` corrigé de U+202F, contre-épreuve à 0 |
| 7 | `frontiere_tenue()` et `plan_tenu()` **définies** dans `nexus_rituel.py` |
| 8 | quatre ambigus **déclarés**, jamais tranchés en silence |

Les quatre ambigus : `console_tools.py`, `mesure_rendu_vide.py`,
`nexus_disjoncteur.py`, `nexus_verbatim.py`. L'outil les affiche à chaque
passage sans échouer : la question reste posée au lieu de s'oublier.

### Vague 3 — LA PLATEFORME, RÉPARÉE PAR SON PROPRE USAGE

| # | défaut trouvé **en s'en servant** |
| --- | --- |
| 9 | `nexus_agent.py:971` n'injecte plus dans la charge utile |
| 10 | sa preuve exige le nom du fichier **dans** l'appel d'écriture |
| 11 | le verdict négatif de `nexus_livres.py` dit **ce qu'il a vraiment cherché** |
| 12 | un refus de pièce jointe doit être **visible**, pas noyé |

Le 12 est le plus important : treize tâches ont travaillé dans le vide
parce qu'un refus existait et ne se voyait pas.

### Vague 4 — LA DETTE, DANS L'ORDRE DU LIVRE

| # | dette | pourquoi ce rang |
| --- | --- | --- |
| 13 | 98 littéraux `"scripts"` | densité forte, risque faible |
| 14 | découpage de `nexus.ps1` | 5 produit / 6 orchestration ; il **bloque** le détachement |
| 15 | 6 paires copiées | contrôle d'**identité**, pas de quantité |

---

## 6. CE QUI RESTE À VOTRE ARBITRAGE — aucune vague ne peut le trancher

1. **`~/.claude/settings.json`** épingle 5 gardes par chemin absolu et sert
   les **autres projets**. Tant qu'il les épingle, `scripts/` ne descend pas.
2. **`.nexus/`** — magasin machine-local, 103 références dans 36 fichiers.
3. **`python_libs_docs`** versionné ou non ; la réponse vaut pour `node_docs`.
4. **Smart App Control** bloque `libcurl-4.dll` : **84 commits ne partent
   pas**. La DLL est présente (898 732 octets, 4 exemplaires) ; c'est une
   politique système, hors du dépôt.

---

## 7. VÉRIFICATION DE BOUT EN BOUT — dans cet ordre

```
1  pwsh -File scripts/Test-NexusConfig.ps1        -> 0
2  python outillage/nexus_frontiere.py            -> 0
3  python outillage/nexus_frontiere.py --epreuve  -> 0  (elle DÉTECTE)
4  python outillage/nexus_plan.py --epreuve       -> 0  (déjà mesuré à 0)
5  python outillage/nexus_conformite.py           -> hooks = 8
6  python outillage/nexus_cablage.py              -> 0
7  python outillage/nexus_rituel.py               -> 0
8  python outillage/nexus_livres.py --texte "..." -> rend du texte
```

**Aucun `py_compile` ne compte comme preuve.** Mesuré ici : 68 fichiers
compilaient à 0 pendant que 28 imports étaient cassés, et PowerShell n'a
aucune compilation.

**Et aucune de ces vérifications ne clôt la LOI 1** : elles sont jouées par
celui qui a commandé les correctifs. Le troisième temps — auditer la
**correction** — revient à un tiers qui n'a écrit ni le diagnostic ni le
patch.
