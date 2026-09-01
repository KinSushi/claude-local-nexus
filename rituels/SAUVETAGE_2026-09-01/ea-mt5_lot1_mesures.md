# SAUVETAGE — `ea-mt5` — LOT 1 : les mesures

> **Pourquoi ce fichier existe.** Le 2026-09-01 a 11:35:16, une reinitialisation
> de la liaison USB-SCSI (`UASPStor` 129) a emporte le volume `D:` et son
> miroir. Deux sessions Claude Code se sont retrouvees sans disque, sans shell
> et sans droit d'ecriture. Elles ne pouvaient plus rien persister, et leur
> contexte de session ne survit pas a un redemarrage.
>
> Cette session, sur un autre volume, pouvait encore ecrire et pousser. Ce
> fichier est le vidage de contexte de `ea-mt5`, recopie **verbatim**, sans
> reformulation ni resume — resumer, ici, ce serait perdre.
>
> **Provenance, declaree par son auteur et conservee telle quelle :** ces
> chiffres viennent de son CONTEXTE DE SESSION, ou ils avaient ete produits par
> execution reelle et affiches en sortie de commande. Ils ne sont **PAS relus
> d'un disque**. Ce sont des **mesures rapportees, non rejouables en l'etat** —
> le volume qui portait les instruments et les donnees est mort. **A rejouer
> avant tout usage decisionnel.**

---

## 1. Test d'acceptation contre Baron

Methode : pour chaque figure, comparer le taux d'atteinte de l'objectif mesure
sur 1 011 symboles D1 (`outcome == "TP"`) a la statistique publiee par Baron,
extraite de `BARON_SOURCE_2026-07-18/L3_doctoral/`.

```
figure                Baron   mesure   ecart    verdict
double_bottom          68 %   68,7 %   +0,7     REPRODUIT
triple_top             50 %   52,8 %   +2,8     REPRODUIT
rising_wedge           63 %   59,8 %   -3,2     REPRODUIT
triple_bottom          73 %   69,7 %   -3,3     REPRODUIT
head_shoulders         63 %   52,9 %  -10,1     a instruire
inv_head_shoulders     83 %   67,9 %  -15,1     ECART
double_top             40 %   59,6 %  +19,6     ECART (mieux que Baron)
falling_wedge          88 %   63,4 %  -24,6     ECART
rounding_top           70 %    0,0 %  -70       BUG
```

**Le point de methode qui a tout decide :** Baron publie DEUX taux — le taux de
SORTIE dans le bon sens (98 %, 97 %, 66 %) et le taux d'ATTEINTE DE L'OBJECTIF.
**Seul le second se compare a la mesure.** Les confondre produisait des ecarts
de 30 points sans signification.

## 2. Le stop : une non-conformite qui a gouverne deux lots geles

Baron enonce le stop explicitement et de facon repetee (p118, p120, p121,
p188 : « sous la ligne du cou », « sous le niveau de support le plus recent »).
Le defaut en production est l'AUTRE mode, `pattern_extreme`, documente dans le
code comme un **accident historique** — il a gouverne **deux lots geles sans
jamais avoir ete decide**.

Mesure appariee (memes candidats, seul le stop change), 1 011 symboles D1,
0 echec :

```
figure               mode        n      taux_TP   esperance_R
double_bottom        extreme     923    68,69     +0,1466
double_bottom        NECKLINE   1093    34,13     +0,4048
triple_bottom        extreme    3190    69,66     +0,1905
triple_bottom        NECKLINE   3961    26,79     +0,2600
inv_head_shoulders   extreme     999    67,87     +0,1448
inv_head_shoulders   NECKLINE   1200    28,58     +0,2465
```

**Le taux de reussite CHUTE de moitie et l'esperance MONTE.** Le stop plus
serre stoppe plus souvent mais reduit le risque unitaire ; le nombre de trades
AUGMENTE (923 vers 1 093) car des configurations rejetees pour R:R insuffisant
redeviennent eligibles.

> **Un taux de reussite n'est pas une performance.** Lu seul, il aurait fait
> rejeter le mode qui gagne.

Validation (bootstrap 10 000, graine 20260901 ; permutation 10 000 ; Holm sur
3 tests, seuil 0,0167) :

```
figure               diff      IC 95 % de la diff      p_brut   p_Holm   verdict
double_bottom       +0,2583   [+0,1143 ; +0,4076]     0,0011   0,0033   SIGNIFICATIF
triple_bottom       +0,0695   [-0,0106 ; +0,1518]     0,1295   0,2590   non
inv_head_shoulders  +0,1017   [-0,0376 ; +0,2417]     0,1833   0,2590   non
```

**UNE SEULE figure passe.** Sans la correction de multiplicite on aurait annonce
« x1,4 a x2,8 sur trois figures ».

## 3. Le net, apres couts

`cost_r_points(spread_points, swap_points=0, risk_points, ...)` APPELE, jamais
reimplemente. Spread depuis `_ALL_SYMBOLS_COSTS.csv` — 947 des 1 011 symboles
ont un cout. **SWAP NON APPLIQUE** : aucune colonne `swap_mode` dans la source,
et la fonction leve plutot que de deviner. **Le net est donc une BORNE
SUPERIEURE.**

```
mode        n      esp_brute   esp_NETTE   IC_nette              cout_moyen_R
extreme     923    +0,1466     +0,1298     [+0,0792 ; +0,1806]   0,0167
neckline   1093    +0,4048     +0,3387     [+0,2013 ; +0,4772]   0,0661

diff_nette  +0,2089   IC [+0,0659 ; +0,3576]   p = 0,0087
exclusions : symbole_absent=64  spread_nul=0  risque_nul=0
```

Le mode gagnant paie **4x plus cher** — stop serre, donc `risk_points` plus
petit, donc cout en R plus grand — **et gagne quand meme**.

## 4. Concentration — le resultat le plus important

```
n=1093   esperance +0,338695   perdants 65,97 %   plus gros trade = 1,12 % du gain
somme totale +370,19 R         somme des R positifs +1136,83

retrait  1 % (11 trades)  : +0,245654  IC [+0,1220 ; +0,3729]  exclut zero
retrait  5 % (55 trades)  : +0,003229  IC [-0,1041 ; +0,1150]  CONTIENT ZERO
retrait 10 % (109)        : -0,244541  NEGATIF
retrait 25 % (273)        : -0,829832  NEGATIF
```

**Retirer 55 trades sur 1 093 annule l'edge**, soit moins 99 %. **Mais le plus
gros trade unique ne pese que 1,12 %** : ce n'est pas un coup de chance isole,
c'est une **queue etroite d'une cinquantaine de trades**.

Durees, 300 symboles, 341 trades :

```
tenue <= 20 barres : n=258  R = -0,0714     > 20 : n=83  R = +2,4289
tenue <= 40        : n=305  R = +0,1075     > 40 : n=36  R = +4,1771
tenue <= 60        : n=320  R = +0,2926     > 60 : n=21  R = +4,2639
tenue <= 80        : n=328  R = +0,4016     > 80 : n=13  R = +3,9578
emprise (formation+tenue) : mediane 39 barres, p90 82, 5,6 % depassent 105
```

## 5. Sequence — drawdown, trades tries chronologiquement tous symboles confondus

```
n=1093  esperance +0,3387  somme +370,19 R
drawdown maximal    59,39 R
serie perdante max  17 trades consecutifs, -18,15 R
recuperation        JAMAIS RECUPERE
periode du DD       2025-12-18  ->  2026-07-16   (SEPT MOIS)
serie perdante      2026-01-13  ->  2026-01-28
ratio esp/DD        0,0057  -> environ 175 trades pour effacer le seul DD maximal
```

**Le creux du DD maximal EST le dernier trade des donnees.** Sommet a environ
+429,6 R le 18/12/2025, puis sept mois de baisse.

> Cela TRANCHE la stabilite : le test par moities donnait +0,4018 pour la
> premiere contre +0,1165 pour la seconde, IC contenant zero, et trois lectures
> restaient ouvertes. **Un artefact d'echantillonnage ne produit pas sept mois
> sans nouveau sommet avec le creux au dernier point. La degradation est
> reelle.**

## 6. Deux tests invalides, consignes plutot qu'effaces

**(a) Quartiles, seuil 480 barres.** A elimine **975 symboles sur 1 011** —
mediane reelle des series : **420 barres**. A rendu 4 tranches de 7 a 20
trades, des chiffres spectaculaires de +1,64 a -0,98, et **4 IC excluant
zero** : une fausse significativite parfaitement presentable. Rien ne la
signalait sauf le compte `trop courts : 975`.

> Seuil fixe sans mesurer la distribution, et seuil de mesurabilite a 182
> trades omis. C'est la classe 2 de l'inventaire anti-derive, et la plus
> dangereuse : les autres produisent une erreur VISIBLE, celle-ci un resultat
> PRESENTABLE.

**(b) Quartiles, seuil corrige a 400 :**

```
q1 | 214 | -0,0777 | [-0,3112,+0,1700] | contient zero
q2 | 189 | +0,1600 | [-0,1285,+0,4646] | contient zero
q3 | 260 | +0,1775 | [-0,0569,+0,4227] | contient zero
q4 | 287 | -0,1561 | [-0,3409,+0,0411] | contient zero
MONOTONE DECROISSANTE : NON  (profil erratique)
```

## 7. Le verdict, et il n'est pas un feu vert

> `double_bottom` avec le stop conforme a Baron est **la figure la plus fidele
> a sa source** — +0,7 point, le meilleur des neuf — et **la seule** dont la
> mise en conformite produise un gain significatif ET net. **Mais son esperance
> repose sur 5 % des trades, elle n'est pas stable dans le temps, et la courbe
> est en drawdown non recupere depuis decembre 2025.**

**Defendable** : appliquer le stop conforme PAR CONFORMITE A LA SOURCE. Baron
l'enonce, le code appliquait autre chose par accident jamais decide.

**Non defendable** : engager du capital sur la foi de +0,3387 R.

**Reserves cumulables, toutes declarees :**

* swap non applique ;
* spread actions jamais verifie sur ticks — `_SPREAD_MEASURED_FROM_TICKS`
  couvre 35 symboles fx, crypto et indices, **aucune action** ; mediane du
  ratio p95 sur broker = **1,8**, et non « 12 a 19 » comme relaye d'abord,
  19 etant le MAXIMUM et non la mediane ;
* aucune validation hors echantillon stricte ;
* biais de survie, symboles radies absents ;
* rien n'est applique en production.
