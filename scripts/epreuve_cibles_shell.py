# -*- coding: utf-8 -*-
"""Le garde voit-il les ecritures du SHELL, et seulement elles ?

MESURE QUI JUSTIFIE CE CODE, 2026-08-31 :

    Write sur un fichier non lu   -> REFUSE   (le garde fonctionnait)
    sed -i par Bash               -> PASSE
    echo > par Bash               -> PASSE
    Set-Content par PowerShell    -> PASSE

Trois sur trois, et 79,5 % des invocations de la session passent par le shell
(1416 Bash contre 353 Write). Le garde couvrait donc environ un cinquieme des
chemins.

POURQUOI CE BANC EXISTE AVANT LE CORRECTIF. Une session voisine a tente le
refus direct le meme jour : sa greffe a atteint son effet mais a refuse
`ls > /dev/null` et bloque une restauration depuis sauvegarde. Elle a du etre
retiree de la production. *Un garde trop large se fait desarmer, et c'est pire
que le trou.*

Chaque cas ci-dessous vient d'un incident reel, ici ou chez elle. Les
anti-controles -- ce qui NE DOIT PAS etre vu -- portent la moitie du banc :
sans eux, une extraction qui rendrait tout paraitrait parfaite.

Le premier jet du banc gratuit a echoue 9 fois sur 17. Deux defauts de plus
ont ete trouves en corrigeant, tous deux MASQUES par un rempart :

  * un decalage d'un cran dans la numerotation des groupes, qui ne se voyait
    que dans le cas guillemets doubles -- le `or` court-circuitant, l'index
    invalide n'etait atteint que la, et son erreur etait avalee par le
    `except` global qui rend « indetermine » ;
  * deux constantes de module laissees dehors par l'extraction, meme effet.

Dans les deux cas, un filet de securite transformait un bug en valeur
parfaitement plausible.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from nexus_garde_lecture import cibles_ecrites  # noqa: E402

echecs = 0


def verifier(nom, condition, detail):
    global echecs
    print("  [%s] %s : %s" % ("OK  " if condition else "RATE", nom, detail))
    if not condition:
        echecs += 1


def att(commande, chemins_attendus, indet_attendu, note):
    ch, ind = cibles_ecrites(commande)
    ok = (sorted(ch) == sorted(chemins_attendus)) and (ind == indet_attendu)
    verifier(commande[:44], ok, "%s (%s)" % (note, ch if ch else "indet=%s" % ind))


def main():
    global echecs
    echecs = 0

    # --- Ce qui DOIT etre vu ------------------------------------------------
    att("echo x > rapport.txt", ["rapport.txt"], False, "redirection simple")
    att("echo x >> rapport.txt", ["rapport.txt"], False, "ajout")
    att("sed -i 's/a/b/' scripts/bench.py", ["scripts/bench.py"], False,
        "sed en place : le fichier est le DERNIER argument, pas l'expression")
    att("sed -i.bak 's/a/b/' f.py", ["f.py"], False, "suffixe attache")
    att("cat a | tee sortie.log", ["sortie.log"], False, "tee apres un tube")
    att("cp source.txt dest.txt", ["dest.txt"], False, "seule la destination")
    att("git status && echo x > f.txt", ["f.txt"], False,
        "second segment : un prefixe inoffensif ne doit pas masquer la suite")

    # --- Ce qui NE DOIT PAS etre vu : les anti-controles --------------------
    #
    # Chacun a coute quelque chose. Le premier a fait retirer de la production
    # la greffe d'une session voisine, le jour meme.
    att("ls > /dev/null", [], False, "destination inoffensive")
    att("ls -la /mnt/dd", [], False, "dd DANS un chemin, pas en commande")
    att("python - < entree.txt", [], False, "chevron gauche : une LECTURE")
    att("grep -n motif fichier.py", [], False, "aucune ecriture")

    # --- Indetermine : ne rien deviner, mais LE DIRE ------------------------
    #
    # « Une mesure impossible n'est pas une mesure a zero » : un garde qui
    # confond « rien trouve » et « pas pu chercher » autorise precisement ce
    # qu'il ne sait pas voir.
    att("echo x > $CIBLE", [], True, "variable")
    att("echo x > $(mktemp)", [], True, "substitution")
    att("echo x > *.log", [], True, "glob")

    # --- Les deux cas qui ont coute cher ------------------------------------
    att('echo x > "mon dossier/f.txt"', ["mon dossier/f.txt"], False,
        "espaces dans un chemin cite : une racine voisine en contient")
    att('echo "a | b" > f.txt', ["f.txt"], False,
        "le tube est DANS les guillemets : ne pas y decouper")

    print("")
    if echecs:
        print("epreuve ratee : %d cas" % echecs)
        sys.exit(1)
    print("epreuve tenue")
    sys.exit(0)


if __name__ == "__main__":
    main()
