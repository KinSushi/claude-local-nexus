# INVENTAIRE DES PERTES — ce qui n'est ni sur `origin` ni sur `G:`

> **A quoi sert ce fichier.** L'operateur demande de ne rien perdre des deux
> disques. Un effort de recuperation se calibre sur ce qui manque, pas sur ce
> qui a disparu — la majorite de ce qui a disparu existe ailleurs. Voici la
> liste, demandee a chaque session et rendue par elle, avec ses incertitudes
> declarees.

---

## Ce que la mesure a etabli sur le materiel

**Les deux projets etaient sur LE MEME volume `D:`.**

```
D:\SAS\sovereign-ai-system\v1.104\sovereign-ai-system
D:\EA MT5 PYTHON RENTABLE ROBUSTE
```

Le second volume perdu est le miroir de `sovereign`, pas un second disque de
travail.

**`D:` n'etait pas un peripherique `USBSTOR`.** Le registre
(`HKLM\SYSTEM\MountedDevices`) lui donne une signature GPT et aucune entree
`USBSTOR`, alors que `E:`, `F:` et `G:` en ont une. Il s'enumerait donc en
**SCSI**, ce que font les boitiers **UASP** — et c'est coherent avec
`UASPStor` comme pilote qui l'a reinitialise.

**Quatre boitiers UAS sont connus de cette machine**, identifies par leur
identifiant de fabricant :

| VID | fabricant | disque fantome correspondant |
| --- | --- | --- |
| `0781` | SanDisk | `SanDisk 3.2 Gen 1 SCSI Disk Device` |
| `0B05` | ASUSTek | `ROG ESD-S1C SCSI Disk Device` |
| `0BC2` | Seagate | `Seagate Portable SCSI Disk Device` |
| `174C` | **ASMedia** | pont NVMe/SATA vers USB, generique — probablement `PHIXERO BIZ-F18` |

> **Piste, et non conclusion.** Les ponts ASMedia en mode UAS sont un candidat
> documente pour ce mode de defaillance sur controleurs AMD. Si `D:` etait le
> boitier a pont ASMedia, cela expliquerait la reproductibilite de la
> signature. **Le logiciel ne peut pas dire lequel des quatre etait `D:`** —
> l'operateur, lui, le sait en regardant.

Aucune des deux sessions ne connaissait le modele, la capacite ni le type de
boitier, et **les deux ont refuse de deviner** — `ea-mt5` explicitement : *« je
ne vais pas nommer un modele de disque par elimination sur une liste que vous
m'avez fournie »*, apres trois diagnostics faux dans la journee.

---

## `sovereign-ai-system` — perte probablement NULLE

```
racine            D:\SAS\sovereign-ai-system\v1.104\sovereign-ai-system
taille de l'arbre 35 823 558 502 octets (~33,4 Gio), hors _REFERENCE_PYTHON_LIBS
contenu           96 277 fichiers / 7 444 repertoires
dont suivis       33 343         -> SUR origin
dont worktrees    43 782         -> copies jetables, 0 modification verifiee ce matin
```

| categorie | verdict |
| --- | --- |
| les 33 343 fichiers suivis, `_REFERENCE_PYTHON_LIBS` comprise | **sauf** — sur `origin` |
| 43 782 fichiers de worktrees d'agents | **jetable** — un worktree est une copie par construction |
| `.venv`, `.mypy_cache`, `.pytest_cache`, `__pycache__` | **reconstructible** |
| ancre de boussole canonique, `~/.sas/evidence/`, 129 lignes | **hors du disque mort**, survit |
| memoires de session, sous le profil utilisateur | **hors du disque mort**, survit |

**La seule reserve, et elle est nommee comme telle :** environ 19 000 fichiers
non suivis, hors worktrees et hors caches — corpus de reference,
`_QUARANTINE` (1 790 fichiers), `_LIVRAISONS_EN_ATTENTE`, artefacts de `.sas/`.
Son contrat situe les sources des corpus sur un autre volume en lecture seule,
donc une re-ingestion serait possible — **mais il ne peut plus le verifier**.

> **Si un effort de recuperation doit etre calibre, `_QUARANTINE` est le seul
> repertoire pour lequel il le demanderait** : son contrat dit « rien n'est
> jamais detruit », et il contient par definition ce qu'on a voulu garder sans
> le suivre.

Et ce qu'il ne demande PAS : la restauration de l'arbre de travail. *« Le
distant est prouve sain et sans transaction en vol ; l'arbre local a perdu 55
ecritures differees. Un clone vaut mieux qu'une recuperation, meme reussie. »*

---

## `EA MT5 PYTHON RENTABLE ROBUSTE` — trois categories par valeur decroissante

### (a) IRREMPLACABLE — ne se refait qu'en refaisant les calculs, et les donnees sont dessus

```
STATE.md, 6 blocs posterieurs a 4b8d30c4, +23 000 octets
  acceptation Baron (9 figures) · stop conforme (mesure appariee, 1011 symboles)
  net apres couts · concentration · sequence et drawdown · addendum spread

SORTIE_*.txt          les sorties BRUTES de chaque run, que les 6 blocs hachent
  SORTIE_acceptation_baron · _sans_stop · _stop_neckline · _validation_neckline
  _net_double_bottom · _hors_echantillon · _quartiles · _quartiles_v2
  _concentration · _sequence
```

> **Les CHIFFRES sont saufs** — ils sont dans
> [`ea-mt5_lot1_mesures.md`](ea-mt5_lot1_mesures.md). **Ce qui est perdu, ce
> sont les sorties brutes et leurs SHA-256** : sans elles, ces mesures passent
> du statut de **preuve rejouable** a celui de **resultat rapporte**. C'est
> precisement la distinction que ces trois depots placent au-dessus de tout.

### (b) RECONSTRUCTIBLE, environ deux heures — la logique est dans les lots 2 et 3

```
workspace/tools/attendre_signal.py             7 modes, triangule, 6 jambes vertes
workspace/tools/verifier_avant_affirmer.py     5 modes, triangule
workspace/_SCRATCH/descripteurs_2026-09-01/    ~12 instruments de mesure
  balayage_D1_actions · agreger_v3 · test_acceptation_baron (423 lignes)
  extraire_stats_doctoral · mesurer_sans_stop · mesurer_stop_neckline
  valider_stop_neckline · mesurer_net_double_bottom · valider_hors_echantillon
  valider_quartiles · mesurer_duree_trades · mesurer_concentration · mesurer_sequence
  + les 8 scripts de bloc STATE

BARON_STATS_DOCTORAL_2026-09-01.txt   398 citations
                                      SE REFAIT EN UNE COMMANDE depuis L3_doctoral,
                                      qui est sur origin — cout modele NUL
```

### (c) GOUVERNANCE — ecrite ce matin, jamais commitee

```
workspace/_GOVERNANCE/REPRISE_2026-09-01.md    +5 230 octets
  les ORDRES DE L'OPERATEUR du jour, VERBATIM, et la LOI 1 DURCIE
_QUARANTAINE_NON_FIABLE_2026-09-01/            3 derivees fautives + _NON_FIABLE.md
CONSIGNE_attendre_signal.md                    la specification des 7 modes
```

> **`REPRISE_2026-09-01.md` est le plus grave des trois.** Il porte les ordres
> de l'operateur en verbatim et la LOI 1 durcie, **c'est le fichier lu au
> demarrage de chaque session**, et **il n'est nulle part ailleurs.**

---

## Ce que cet inventaire commande, et qui n'etait pas evident

**Une recuperation ciblee suffit.** Il ne s'agit pas de restaurer 33 Gio ni
96 277 fichiers : il s'agit de retrouver **quelques dizaines de fichiers**,
tous dans deux arborescences connues :

```
D:\EA MT5 PYTHON RENTABLE ROBUSTE\STATE.md
D:\EA MT5 PYTHON RENTABLE ROBUSTE\SORTIE_*.txt
D:\EA MT5 PYTHON RENTABLE ROBUSTE\workspace\_GOVERNANCE\REPRISE_2026-09-01.md
D:\EA MT5 PYTHON RENTABLE ROBUSTE\workspace\tools\*.py
D:\EA MT5 PYTHON RENTABLE ROBUSTE\workspace\_SCRATCH\descripteurs_2026-09-01\
D:\SAS\...\_QUARANTINE\                       (la reserve de sovereign)
```

⇒ **Cela change l'ordre des gestes** : si le volume revient ne serait-ce qu'une
minute, ces chemins-la passent en premier, et rien d'autre. Une copie
integrale de 33 Gio sur un lien qui a lache deux fois est un pari ; une copie
de quelques megaoctets n'en est pas un.

## Le point qui protege ce qui reste

> **NTFS rejoue son journal au MONTAGE, et rejouer est une ECRITURE.**

`ea-mt5` a reconnu que sa propre consigne — « copier avant de reparer » —
etait insuffisante d'un cran : *« copier avant de reparer repond a "ai-je
sauvegarde avant l'operation risquee ?", jamais a "l'acces lui-meme est-il une
operation risquee ?"* — la question voisine, sur le geste cense nous
proteger.*

**La sequence qui remplace la sienne partout :**

```
1  diskpart -> select disk N -> attributes disk set readonly
     AVANT que Windows ne monte le volume
2  monter en lecture seule
3  COPIER les chemins listes ci-dessus, dans cet ordre
4  seulement ensuite, envisager quoi que ce soit d'autre
```
