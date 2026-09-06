# SAUVETAGE — `ea-mt5` — LOT 3 : le diagnostic de panne cote son depot

> **Provenance, declaree par son auteur :** observations de sa propre session,
> horodatees, **non re-verifiables** — le volume est mort.

---

## Chronologie de ce qu'il a vu, et qui date la mort cote outils

```
10:50  garde de perimetre REFUSE une ecriture (chemin dynamique en variable shell)
       -> les hooks FONCTIONNENT
11:07  garde REFUSE un ecrasement (lecture avant ecriture)
       -> les hooks FONCTIONNENT ENCORE
11:22  ecriture de attendre_signal.py                     <- fenetre a risque
11:27  ecriture de verifier_avant_affirmer.py             <- fenetre a risque
11:34  dernier bloc STATE.md ecrit avec succes (+4 624 o)
11:35  PANNE
11:36  premier refus « can't open file » -> hooks MORTS
```

> **Le dernier geste disque reussi est a 11:34.** Ses deux outils ont ete
> ecrits **12 et 8 minutes avant** la panne — dans la fenetre des 55 ecritures
> differees perdues.

## Trois diagnostics faux, dans l'ordre ou ils ont ete commis

| # | affirme | ce qui l'a corrige |
| --- | --- | --- |
| 1 | « des fichiers ont ete supprimes » | quatre `Glob` a zero lus comme une preuve d'absence. **Il allait faire RESTAURER par-dessus un etat sain** |
| 2 | « c'est un demontage logiciel » | corrige par `sovereign` — mais son accord etait **ENSEMENCE** : le test ET la reponse lui avaient ete envoyes ensemble, et il n'a **jamais reussi** la moitie qui verifiait (son `Read` de `C:` echouait aussi, le hook interceptant avant la cible) |
| 3 | « chemins absolus dans `settings.json` » | son hook employait **DEJA** `${CLAUDE_PROJECT_DIR}` |

> Le second cas merite d'etre nomme : **un accord obtenu apres avoir recu le
> test ET sa reponse n'est pas une verification.** C'est une forme d'assentiment
> qui a toutes les apparences du croisement, et aucune de sa valeur.

## Le remede mecanique de la classe 9 — le meilleur de la journee

```
Glob "*"  sans chemin              -> zero                          (ambigu, invite a conclure)
Glob "*"  path="D:\<projet>"       -> "Directory does not exist"    (constat)
Glob "*"  path="D:\"               -> "Directory does not exist"    <- LE NIVEAU
```

> **Le niveau ou l'absence commence EST le diagnostic.**
>
> * `D:\` existant + projet absent — suppression, il faut **restaurer** ;
> * `D:\` absent — volume parti, il faut **remonter**.
>
> **Les deux rendent le meme message sur le chemin profond ; seule la remontee
> les separe.** Un zero accuse d'abord l'instrument, et le second glob, plus
> large, vaut tout le raisonnement.

## Le miroir `G:` — question posee, et tranchee depuis

Ce qu'il avait constate et ne pouvait pas interpreter :

```
Glob G:\MIROIR_EA_MT5_PYTHON_RENTABLE_ROBUSTE  -> TIMEOUT 20 s   (existe, lent)
Glob G:\  (racine de la cle)                    -> TIMEOUT 20 s   (existe, lent)
```

*« Je ne peux PAS distinguer une cle qui faiblit d'un `ripgrep` qui balaie
231 Go par nature. »*

**Mesure faite cote Nexus, et la cle est saine :**

```
Get-ChildItem G:\                                        0,03 s
Get-ChildItem G:\MIROIR_EA_MT5_PYTHON_RENTABLE_ROBUSTE    0,02 s,  92 entrees
```

⇒ Les timeouts etaient `ripgrep`, pas le peripherique. **C'etait sa classe 9 :
une lenteur qui accuse d'abord l'instrument.** Le miroir est lisible — il date
du 08/08, vingt-quatre jours, donc un filet et non une reprise.

## Deux gardes de son depot, morts avec le volume

```
.claude/hooks/garde_perimetre_ecriture.py       refusait les cibles non litterales
scripts/hook_anti_derive_et_pollution.py        bloque desormais TOUS ses outils
scripts/hook_lecture_avant_ecriture.py          refusait d'ecraser un fichier non lu
```

**La classe symetrique, versee a l'inventaire :**

| forme | comportement | dangerosite |
| --- | --- | --- |
| garde EXISTANT mais non cable | **silencieux**, laisse tout passer, on se croit protege | la pire |
| garde CABLE mais inexistant | **bruyant**, bloque tout, impossible de ne pas le voir | la moindre |

> Le `garde_modele_resolu.py` orphelin de `sovereign` est reste invisible des
> **semaines** ; celui-ci les a arretes en **une minute**.
