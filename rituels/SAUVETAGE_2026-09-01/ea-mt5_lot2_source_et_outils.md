# SAUVETAGE — `ea-mt5` — LOT 2 : la source, les deux outils, et le correctif qui a aggrave

> **Provenance, declaree par son auteur :** reconstitue depuis son CONTEXTE DE
> SESSION, **non relu d'un disque**. Le volume qui portait ces fichiers est
> mort. A rejouer avant tout usage.

---

## A. La source Baron — elle EXISTAIT, et elle a ete recartographiee pour rien

```
workspace/BARON_SOURCE_2026-07-18/
    L1_pages     531        L2_chapters   43     L3_figure_index.json
    L1_images   1156        L3_doctoral   45     L4_ingestion   2
    L1_renders   518

PDF socle : 518 pages
  SHA-256  3a4136e1788157d4c5c0fb425b9948094a38084513102697ba0f093ea4a84ae2

fulltext canonique : 770 335 octets, 12 161 lignes
  SHA-256  760655f5891e644c833405b1afd1e5bb4e141f1a0557dae8ebd3abfdf68ef5d9
  present en TROIS exemplaires au hash IDENTIQUE
```

**Structure d'un `L3_doctoral/chXX_*.doctoral.json`** — c'est cela qui compte,
et non les 398 lignes extraites :

```
figure_id                      ex. "triple_bottom"
chapitre                       "ch08_chapitre_8_le_triple_bottom"
source.pdf_sha256_socle        3a4136e1...     <- ancre sur le PDF, PAS sur un derive
source.plage_pages_pdf         "160-171"
source.regle                   "0 invention, 100% fidele au texte de Baron"
dimensions{}                   geometrie, contexte, psychologie, profils, volume,
                               indicateurs, exemples
  chaque dimension -> citations[] { texte (verbatim), page }
```

> **L'extraction se refait en une commande, a cout modele NUL** : parcourir les
> 43 JSON, filtrer les citations contenant un pourcentage, « fois sur » ou une
> duree chiffree, sortir `figure|page|dimension|texte`. **Ne pas deleguer** :
> `figure_id` et `page` sont deja dans le JSON, il n'y a aucun jugement a
> rendre.

### Les statistiques cles, verbatim — celles qui ont servi au test d'acceptation

```
triple_bottom  p160  « TRIPLE BOTTOM - 66 % de sortie haussiere - Pullback tres frequent : 70 % »
               p161  « taux d'echec faible de l'ordre de 4 % »
               p161  « haussiere dans 66 % des cas avec un gain moyen de l'ordre de 38 %,
                       le delai d'atteinte de l'ultime plus haut etant de 7 mois et demi »
               p162  « Cet objectif minimal est valide dans 73 % des cas »
double_bottom  p143  « retournements haussiers dans 70 % des cas. Dans 30 % des cas,
                       il s'agit d'une figure de continuation »
               p143  « pullback [...] observe dans 68 % des cas et dure en moyenne 11 jours »
               p144  « objectif minimal est valide dans 68 % des cas. Le gain moyen a la
                       cassure est de l'ordre de 40 % »
inv_head_sh.   p260  « 98 % de sortie haussiere - 85 % de retournement - 15 % continuation »
               p262  « Cet objectif est valide dans 83 % des cas »
double_top     p198  « objectif minimal valide dans 40 % des cas, ce qui est peu pertinent »
triple_top     p214  « objectif minimal valide dans 50 % des cas »
rounding_top   p224  « objectif est atteint dans pres de 70 % »
head_shoulders p242  « objectif est valide dans 63 % »
falling_wedge  p355  « objectif minimal est atteint dans 88 % des cas pour la sortie haussiere »
```

> **PIEGE A CONSIGNER.** Les ancres `fulltext:NNNN` des docstrings de detecteurs
> **ne pointent vers rien de verifiable** : trois fichiers `fulltext` ont
> coexiste avec des numerotations differentes, et un audit du 26/07 avait deja
> mesure **45 citations invalidees** dans deux detecteurs. **L'ancre canonique
> est la PAGE DU PDF, jamais un numero de ligne d'un derive.**

## B. `attendre_signal.py` — sept modes

Sa terminaison EST la notification. Les predicats sont **SANS ETAT** : ils
mesurent une fois, rendent vrai ou faux, ne dorment ni ne bouclent, ne
modifient rien. Tout etat appartient a la boucle.

```
--verrou <classe>          lance verrou_machine.py --etat, lit "LIBRE|TENU <classe>"
                           classe ABSENTE de la sortie -> EXCEPTION, jamais "occupe"
--fichier <chemin>         existence + taille NON NULLE + STABLE + FRAICHE
    --depuis <ISO|chemin>  mtime strictement posterieur
    --efface-avant         supprime UNE FOIS au demarrage, AVANT la boucle
    sans l'une des deux -> REFUS de demarrer, code 3
--commande <cmd> --attendu <code>        returncode, JAMAIS $? apres un tube
--processus-absent <motif>               aucun processus vivant portant ce motif
--processus-fige <motif> [--releves N]   delta CPU ET delta E/S nuls sur N releves
--modele-resident <alias> / --modele-decharge <alias>   via 127.0.0.1:11434/api/ps

communes : --intervalle 20 · --timeout 3600 · --silencieux
codes    : 0 atteint · 2 timeout · 3 usage invalide OU 5 sondes en echec
```

### Ce que chaque mode NE repond PAS — c'est la partie qui vaut

| mode | il repond a | il ne repond **jamais** a |
| --- | --- | --- |
| `--processus-absent` | le processus a-t-il disparu ? | **la ressource est-elle rendue ?** |
| `--processus-fige` | aucune progression observee | « bloque » |
| `--fichier` | stabilite = un INDICE | l'ecriture est-elle finie ? |
| `api/ps` injoignable | **echec de mesure** | « liste vide » |

**Mesure derriere la premiere ligne :** deux sessions ont annonce « GPU rendu »
apres avoir tue leur processus ; le modele est reste **25 s en `Stopping` avec
ses 20 Go**. *Arreter un processus ne libere pas les poids.*

**Mesure derriere la deuxieme :** les DEUX deltas sont necessaires, aucun n'est
suffisant. Un test d'acceptation consommait **0,6 s de CPU en six minutes** sous
contention disque, et il etait **sain** — le seul critere CPU l'aurait declare
fige.

**Et une regle absolue :** *un timeout ne rend JAMAIS 0.*

## C. Les deux defauts, et le correctif qui a AGGRAVE

Reverse-test : `--processus-fige "motif_qui_nexiste_pas_2026"` doit rendre **3**
— rien a observer.

```
essai 1        code 2 apres 32 s, AUCUN message d'echec
               cause : la ligne de commande de l'OUTIL contient le motif qu'il
               cherche. Il se voyait lui-meme progresser -> "pas fige", indefiniment.

correctif 1    exclure os.getpid()

essai 2        code 0, SIGNAL          <- PIRE QUE L'ECHEC INITIAL
               cause : le motif figure AUSSI dans la ligne de commande du
               PowerShell que l'outil lance. Ce maillon est stable par nature,
               donc lu comme "fige".

correctif 2    ecarter la CHAINE ENTIERE par signature :
               ("attendre_signal", "Get-CimInstance", "Win32_Process")

essai 3        ECHEC-SONDE apres 11 s, code 3, les 5 echecs comptes    <- correct
```

> **Deux lecons, et la seconde est la plus chere.**
>
> 1. **Un moniteur qui se compte dans sa propre mesure ne mesure jamais rien
>    d'autre que lui.** Exclure son PID **ne suffit pas** : toute la chaine
>    d'invocation porte le motif.
> 2. **Le premier correctif a transforme un TIMEOUT — visible — en SIGNAL, un
>    faux vert.** Il allait dans la bonne direction et il a **aggrave** le
>    defaut. **Seul le rejeu l'a montre.** Rejouer les tests apres chaque
>    correction n'est pas une formalite : c'est ce qui separe un correctif
>    d'une degradation deguisee.

**Defaut connu et NON corrige, par application de la LOI 1** — il n'ecrit pas le
correctif de ce qu'il audite : le mode `--gardes` de l'autre outil n'est **pas
borne en temps** et s'est fige sur un `rglob`. `--cherche` a ete borne,
`--gardes` non. *Corriger la moitie d'un couplage ne le supprime pas, il le
deplace.*

## D. `verifier_avant_affirmer.py` — cinq modes

```
--existe <chemin...>                            avant de dire « existe / n'existe pas »
--cherche <motif> [--dans <dossier>]            avant de dire « ca n'existe pas dans le depot »
--citation <fichier> <texte>                    avant de citer une valeur ou une phrase
--distribution <csv> <colonne> --seuils N...    AVANT DE FIXER UN SEUIL
--gardes <dossier> --appelants ...              quels gardes ne sont CABLES nulle part

codes : 0 confirme · 1 infirme · 3 usage invalide OU MESURE IMPOSSIBLE
```

`--cherche` **borne son balayage en temps** et, s'il n'a pas fini, dit MESURE
IMPOSSIBLE et rend 3 — **jamais « absent »**. Une recherche interrompue qui
rendrait ABSENT transformerait *« je n'ai pas fini de chercher »* en *« cela
n'existe pas »*.

`--distribution` **rejoue sa propre faute et l'attrape** : sur le fichier de
spreads, `mediane 1,8 / max 19`, un seuil a 19 ne garde que **1 sur 17** —
ALERTE.

**Six jambes vertes chacun :** `--verrou` deja libre -> SIGNAL 0 ·
`--processus-absent` motif inexistant -> SIGNAL 0 · `--fichier` sans fraicheur
-> REFUS 3 · timeout -> 2 · `--processus-fige` sans processus -> ECHEC-SONDE 3 ·
**FORWARD** : fichier cree apres 6 s par une route independante, detecte a 9 s.

## E. Point de reprise

```
distant       origin, HEAD 4b8d30c4, branche freeze/first-edge-triple-bottom-m15-2026-07-28
etat local    perdu. Repartir du distant, PLUS SUR : Ntfs 140 rend tout etat local
              suspect, le distant n'a jamais eu de transaction en vol.
verifier      le COMPTE de fichiers materialises, pas le code de retour.
              git -c core.longpaths=true, atteste 18 829 / 18 829.
```

**Les quatre premiers pas apres le clone :**

1. recreer les deux outils depuis ce lot ;
2. re-extraire les 398 citations depuis `L3_doctoral` — une commande, cout nul ;
3. **REJOUER les mesures du lot 1** avant tout usage ;
4. seulement alors, reprendre le chemin critique.
