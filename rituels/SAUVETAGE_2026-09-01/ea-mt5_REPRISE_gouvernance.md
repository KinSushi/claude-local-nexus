# SAUVETAGE — `ea-mt5` — le contenu de `REPRISE_2026-09-01.md`

> **Pourquoi ce fichier est le plus important du repertoire.**
> `workspace/_GOVERNANCE/REPRISE_2026-09-01.md` portait les ordres de
> l'operateur en verbatim et la LOI 1 durcie. C'est le fichier lu au demarrage
> de chaque session de ce depot. Il a ete ecrit le matin du 2026-09-01, jamais
> commite, et le volume est mort a 11:35. **Il n'existait nulle part.**
>
> Il a ete transmis au dernier appel, quelques minutes avant l'arret complet de
> la machine, parce que la question posee etait *« reste-t-il quoi que ce soit
> qui ne soit ni sur origin ni dans le sauvetage ? »* et que la reponse etait
> oui.
>
> **Provenance, declaree par son auteur :** verbatim des messages de
> l'operateur dans sa session, recopies depuis son contexte. **Ce sont les mots
> de l'operateur, pas une interpretation.**

---

## A. Les ordres de l'operateur, 2026-09-01, mot pour mot

### Sur la source

> « la seule source de verite c'est BARON PDF qui est l'ultime source de verite
> **et aussi un track record VIVANT** »
>
> « le livre de BARON PDF c'est du texte **mais aussi des images** »
>
> « on a des outils locaux pour du pdf » · « sers toi en »
>
> « debrouilles toi pour avoir **UNE seule derivee de source fiable**,
> ingestion digestion parsee **BARON DOCTORAT du tres haut de gamme. UNE SEULE
> SOURCE pas 15.** »
>
> « ce qui n'est pas fiable => **quarantaine avec message explicite NON
> FIABLE** »

### Sur la methode

> « tu delegues la grosse charge »
>
> « tu preserves tes tokens et ton contexte »
>
> « tu as le format, la forme, **les templates** »
>
> « **0 excuses** » · « pas de bavardages inutiles. Au travail »
>
> « tu as 4H pour tout livrer. tu as acces a **80+ IA**, alors tu as 0
> excuses »
>
> « signale toutes anomalie au responsable et charge du projet nexus »
>
> « tant que **code premium audite partout non execute** alors il y aura
> toujours des **instabilites et des erreurs silencieuses** »
>
> « **CONCERTEZ VOUS 3 VOISINES ENSEMBLES. VOUS VOUS PARLEZ.** »
>
> « arme un moniteur plutot que de sonder a la main » · « **pas de
> babysitting** »
>
> « si tu peux en faire un **outil mecanise**, c'est encore mieux, et le
> partager avec les autres c'est PARFAIT »
>
> « tu es en charge de veiller a ce que les **outils anti-derive** soient en
> place avec les autres instances **toi inclus** »

### Sur le fond du projet, dit plus tot, et qui commande tout

> « les **figures chartistes SONT le systeme de trading** »
>
> « Baron est un livre mais aussi un **track record**, il est le **PLANCHER pas
> le plafond** »
>
> « si le code lui meme ne donne pas les memes resultats que Baron lui meme
> **alors c'est qu'il y a des erreurs dans le code** »
>
> « donnees synthetiques tolerees pour la validation, mais **le vrai verdict
> c'est la data reelle** »
>
> « tester du M15 sur D1, quelle idee aussi… »

---

## B. La LOI 1 durcie — verbatim, et c'est ce qui regit tout le reste

> « attention **tu ne peux pas valider ton propre travail**, le meilleur atout
> c'est que tu orchestres, tu delegues et tu audites. **MAIS tu ne corriges
> pas, sinon tu tombes dans le piege d'auto-validation.** rajoute cela en dur
> partout la LOI 1. **c'est fondamental et cela evite les erreurs a
> repetition.** »

### La regle operatoire, telle qu'inscrite

| je fais | je ne fais **PAS** |
| --- | --- |
| **ORCHESTRER** — mesurer la premisse, rediger la consigne | ecrire le code |
| **DELEGUER** — au plan le moins cher qui repond | rediger ce qu'un modele peut rediger |
| **AUDITER** — verifier, RE-MESURER, faire le joint | **CORRIGER**, meme une ligne, meme evidente |
| **TRANCHER** | valider ce que j'ai produit |

> **Corriger, c'est PRODUIRE. Produire, c'est devoir etre AUDITE.**

### La forme insidieuse, mesuree le jour meme ou la regle a ete posee

Un protocole a ete audite par deux modeles de familles distinctes. Ils ont
rendu cinq findings fondes. **Les cinq corrections ont ensuite ete ecrites par
l'orchestrateur lui-meme.** Le texte final etait de sa main, relu par personne
— et il pouvait dire « j'ai fait auditer ».

> **C'est PIRE que l'auto-validation directe : l'audit rend la faute
> INVISIBLE.** Sa trace couvre la version *avant* correction ; le livrable n'a
> jamais ete vu par un tiers.

### La chaine correcte

```
produire (banc)  ->  AUDITER (moi + famille distincte)  ->  CORRIGER (banc, JAMAIS moi)
                 ->  AUDITER LA CORRECTION              ->  trancher (moi)
```

> **Le correctif est un livrable comme un autre : il se delegue et il
> s'audite.**

### La seule exception, etroite et declaree

Le transport **mecanique**, sans jugement, verifiable par un tiers :
decapsuler un bloc markdown, renommer, compter, extraire un JSON. **JAMAIS une
ligne de logique, JAMAIS un seuil, JAMAIS un texte de gouvernance.** Et
toujours ANNONCE.

### Le test avant de toucher quoi que ce soit

> ***« Si je me trompe ici, QUI le verra ? »***
>
> Si la reponse est **personne**, c'est qu'on est en train de CORRIGER.
> **Deleguer.**

---

## C. Les trois arbitrages non tranches — ils bloquent l'edge

Du registre `workspace/tools/provenance_parametres.py`, qui classe 49
parametres. Trois sont marques `NON_TRANCHE`, `ARBITRAGE ENZO`.

### `stop_mode`

> « Baron donne le stop explicitement et de facon REPETEE (p118, p120, p121,
> p188 : "sous la ligne du cou", "sous le niveau de support le plus recent")
> => un modele conclut EXOGENE a cout 0 ; la spec derivee du depot pose que
> tout choix de `stop_mode` est un ESSAI. Le defaut en production est l'AUTRE
> mode, documente dans le code comme un ACCIDENT HISTORIQUE. »

**Il a gouverne DEUX LOTS GELES sans jamais avoir ete decide.**

⇒ **TRANCHE** par la regle de l'operateur elle-meme : si Baron est la seule
source de verite et qu'il enonce le stop, appliquer autre chose est **une
erreur du code**. Se conformer ne consomme **aucun essai**.

### `atr_mult`

> « Baron SOURCE le tampon (p121 "un peu au-dela") mais REFUSE le nombre (p121
> "les chiffres automatiques du type 3 % ou 5 % ne peuvent en aucun cas
> s'adapter") => valeur fidele = 0 selon un modele ; SELECTIONNE selon les
> autres. Sortie propre possible : stop en CLOTURE (p132) rend le tampon
> inutile — mais c'est un changement de LOGIQUE, pas un reglage. »

⇒ **RESTE OUVERT.** *Une source qui refuse de chiffrer ne tranche pas a la
place de l'operateur.*

### `min_spacing_bars`

> « cette valeur, calibree en D1, a tourne sur des barres M15 dans le seul run
> gele du projet — 150 minutes au lieu de deux semaines »

⇒ **RESTE OUVERT.** Le filtre est peut-etre **a l'envers**.

---

## D. Ce qui reste, en une ligne chacun

```
rounding_top         mesure 0,0 % contre 70 % chez Baron  ->  BUG CERTAIN, non instruit
residu +7 a +8 pts   sur 3 figures apres retrait du stop  ->  INEXPLIQUE
v_reversal           AUCUNE statistique publiee par Baron ->  non confrontable, jamais
spread actions       _SPREAD_MEASURED_FROM_TICKS ne couvre AUCUNE action -> jamais verifie
```

**Et un defaut connu, non corrige par application de la LOI 1** — il n'ecrit
pas le correctif de ce qu'il audite :

> le mode `--gardes` de `verifier_avant_affirmer.py` **n'est pas borne en
> temps** et se fige sur un `rglob`. `--cherche` avait ete borne, `--gardes`
> non. **Corriger la moitie d'un couplage ne le supprime pas, ca le deplace.**
