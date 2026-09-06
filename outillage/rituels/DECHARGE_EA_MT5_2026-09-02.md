# Decharge de contexte — EA MT5, 2026-09-02

> **Consignee ici parce que son auteur ne peut plus rien ecrire.** Le volume
> `D:` a disparu ; ses deux hooks y vivent et echouent avant chaque commande,
> `echo test` compris. Il lui reste `Read`, `Glob`, `Grep` et les messages.
> Ordre de l'operateur : *« decharge ton contexte, fais-toi aider de Nexus »*.
>
> Ce fichier est un RELAIS FIDELE, pas une synthese : rien n'y est reformule,
> rien n'y est juge. Ce qui est mesure est marque comme tel, ce qui ne l'est
> pas aussi. Voir [LECONS_PARTAGEES §27](LECONS_PARTAGEES.md) pour le meme
> incident vu depuis SAS.

## 0. La contre-epreuve qu'il a faite avant de repondre

    Glob C:\Users\dibac\.claude\projects\...\memory\   ->  32 fichiers
    Glob D:\                                            ->  0

**L'outil marche, l'absence est reelle.** Il le note lui-meme : il avait
d'abord conclu sur des `Glob` vides **sans temoin positif** — sa propre regle
du differentiel, non appliquee a lui-meme.

## 1. Ce qui est perdu si le volume ne revient pas

**5 outils, 802 lignes, mesures `??` NON SUIVIS PAR GIT une heure avant la
panne** : `ecart_doc_bibliotheques`, `qualite_doc_bibliotheques`,
`regenerer_toute_la_doc`, `chercher_paquets_sur_disque`,
`extraire_fragment_doc`.

**Contre-mesure du meme tour** : `junction_bases`, `sauvegarde_miroir`,
`triage_worktrees` — **3/3 SUIVIS**.

> Ce n'etait pas un oubli isole, c'etait un MOTIF : aucun de ses outils
> n'existait pour le depot.

Il avait ecrit deux tours avant la panne : *« une compaction, un git clean, un
changement de machine, et 802 lignes disparaissent sans trace »*. **C'est
arrive, par une voie qu'il n'avait pas listee.**

## 2. Mesures du jour, toutes verifiees par execution

| sujet | mesure |
| --- | --- |
| **`llvmlite` debloque** | `Interrupted, 1 error` -> **3 844 collectes, 0 erreur** -> 13 failed / 3 828 passed. **Cause NON isolee** : une reinstallation a tire une chaine. Il a l'EFFET, pas le MECANISME |
| **P0 corrige** | `LogisticRegression(l1_ratio=1, ...)` **sans `penalty`** => penalite effective **L2**. Mesure : **0/8 coefficient nul contre 7/8**. La selection de stabilite ne selectionnait rien. Correctif : **une ligne**, `penalty="l1"` |
| **L4 — 14 echecs, DEUX causes, aucune du code applicatif** | **9** postulent `l1_ratio=1 == penalty='l1'`, **faux sous sklearn 1.7.2** ; **4** viennent d'un scelle de hash perime par un commit **ADDITIF prouve par AST** (19 communes, **0 modifiee**) |
| ⛔ **voie « monter sklearn a 1.8 » FERMEE** | `hdbscan 0.8.44` est la derniere version publiee et importe `_fill_or_add_to_diagonal` de `sklearn.utils._array_api`, **API privee retiree en 1.8**. Sa declaration `scikit-learn>=1.6` **n'a pas de borne superieure et ne protege de rien** |
| **L1 tranche** | les deux hypotheses etaient vraies A MOITIE : degradation **commune** (12 figures se degradent, 4 s'ameliorent) **PLUS** sur-usure propre a `double_bottom` : **-0,634 contre une mediane de -0,312**, trades **18 -> 13**, taux **77,8 % -> 46,2 %**. Pas de la saturation : **moins de trades ET moins bons** |
| **L2 tranche** | critere = **collisions numeriques**, pas nombre de regles. Tete : `rounding_bottom`, `double_bottom`, `triple_bottom` (0 collision). Risque max : `triangle_descendant` et `elargissement_sym_creux` (**21 %**) |
| **doc** | 22 -> **49 fiches a jour** · perimees 6 -> 2 · non-verbatim 3 -> 1 · `MANQUE_DOC` **3 -> 0**. `scipy` **901/910**, `statsmodels` 96/97, `sklearn` **92 %** reexports ecartes. Calibre 0,5B : ~31 000 fragments a ~6 Ko, 94 % sous 8 Ko |
| **BARON / gaps** | six types, chiffres portant sur le **COMBLEMENT** : commun 90 % combles 1re semaine · rupture volumes **2 a 2,5x** · continuation **90 % non comble** · terminaison **60 % haussiers / 70 % baissiers** · confirmation « constamment combles » |
| ★ **l'ile** | **combinaison de DEUX gaps de sens opposes** => **causalement implementable** (le second gap est un EVENEMENT), contrairement a runaway-vs-exhaustion qui exige le futur |
| **`figure_island_reversal`** | porte `find_island_reversal_candidates` et **AUCUN simulateur** : 20 tests valident le detecteur, **zero trade produit**. Troisieme cas apres `v_reversal` (**1 536 trades jamais mesures**) et `diamond` |

## 3. Lecons neuves — dans aucun de nos trois depots avant ce jour

### 3.1 QUATRE modes d'erreur, quatre remedes, et le dernier n'en a aucun

    CAS A               contredit le texte fourni  -> ANCRAGE   -> changer de modele
    CAS B               comble un vide             -> FORMAT    -> fermer la branche
    ABSTENTION FAUSSE   nie un present             -> nommer OU regarder
    NON-REPONSE FORMELLE  rend le gabarit          -> CAPACITE  -> AUCUN remede de consigne

### 3.2 Le format ferme le cas B quand le modele PEUT s'abstenir ; sinon il le DEPLACE

Mesure : cloud **5/7 -> 7/7** ; 0,5B **inchange a 2 inventions**, et **en pire**
(`index=dates`, absent de l'extrait) — **la branche offerte, nommee, declaree
attendue**.

### 3.3 Un renvoi porte DEUX listes, et la seconde doit etre COMPTABLE

Nommer les elements a preserver ne suffit pas : **un test garde son nom, sa
docstring et son `pytest.raises` en perdant deux tiers de ses assertions**
(v1 15 -> v2 **5**). Seul `>= 15 assert` l'a attrape.

### 3.4 ★ Et les invariants comptables ne suffisent pas non plus

Un patch a tenu **6/6 invariants** et est reste **inapplicable** : ancres
recopiees **sans l'indentation** du fichier.

> **Le seul controle qui vaut est l'APPLICATION elle-meme.**

Quatre tours, quatre causes differentes : tronque · help mensonger + tirets
U+2011 · ancres desindentees · applique.

### 3.5 Un audit produit des FAUX NEGATIFS aussi

Son compteur cherchait `**LA LIMITE DU PYTHON PUR**` et rendait 10 — **il
allait se retrograder A TORT de 17 a 10**, les groupes 1 et 2 employant un
autre format. **La severite n'est pas la rigueur.**

### 3.6 Un outil destructif se prouve par ses REFUS

Patron trouve dans son propre depot, `junction_bases.py` : `--execute`
(DRY-RUN par defaut) · preconditions avec ABANDON · idempotence declaree ·
`_rollback(stage)` **qui dit quand il n'y arrive pas** · **sonde ecrite et
verifiee de l'autre cote** avant de declarer le succes. **6/7.**
Son `regenerer_toute_la_doc` en tenait **0** — il n'a pu poser que le dry-run
avant la panne.

## 4. Decisions de l'operateur en attente chez lui — a ne pas perdre

| # | decision |
| --- | --- |
| **D1** | re-pin du scelle `AUDITED_MODULES_HASHES.md` (additivite prouvee) |
| **D2** | les 9 tests d'equivalence -> `xfail(strict=True)` (seule voie, sklearn ferme) |
| **D3** | brancher `figure_island_reversal` sur `simulate_generic` (**change la population tradee**) |
| **D4** | sweep pre-enregistre a nomenclature morte, 6 figures |
| **D5** | sort de `produire_au_banc.py` |
| **D6** | cabler ses outils dans `rituel_complet.GARDES` |

## 5. Ce qu'il me renvoie, et que je note contre moi

> ⚠️ *« Et ta mesure "152 commits non pousses" est le vrai sujet de ton cote :
> le mien vient de demontrer ce que ca coute. Pousse avant de continuer quoi
> que ce soit. »*

Etat au moment ou ce fichier est ecrit : **152 commits non pousses**, et la
vitrine **REFUSE** de publier pour 4 manques au rituel. Le refus est correct ;
la dette est reelle. Elle est traitee dans le meme tour.
