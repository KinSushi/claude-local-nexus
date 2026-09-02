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


    # === CINQ CORRECTIFS GRAVES, issus d'une CONFRONTATION avec l'extracteur
    # === d'une equipe voisine : 26 commandes croisees, puis leurs 19 cas.
    #
    # Aucun de ces cas n'a servi a construire notre fonction : ce sont des
    # forward-tests au sens propre. Ils ont revele cinq defauts, dont deux que
    # notre propre banc ne pouvait pas voir -- il avait ete ecrit par l'auteur
    # de la fonction.
    #
    # DEUX TENTATIVES LARGES ont casse 13 cas sur 16, chacune, et ont ete
    # RETIREES. Trois tentatives ETROITES, un defaut a la fois, ont reussi
    # sans une seule regression. La forme de la delegation etait le defaut,
    # pas le delegue.

    # Correctif 1 : verbes PowerShell manquants. L'outil ne reconnaissait pas Set-Content, Add-Content et Out-File.
    att("Set-Content f.txt 'x'", ['f.txt'], False, "PS Set-Content simple")
    att("Set-Content -Path src/x.py -Value z", ['src/x.py'], False, "PS Set-Content avec -Path")
    att("set-content autre.txt 'y'", ['autre.txt'], False, "PS Set-Content case insensitive")
    att("Add-Content -Path journal.log -Value x", ['journal.log'], False, "PS Add-Content")
    att("Out-File -FilePath f.txt", ['f.txt'], False, "PS Out-File")

    # Correctif 2 : sed accepte plusieurs fichiers.
    # L'ancien code ne prenait que le dernier argument, ce qui faisait perdre les fichiers precedents.
    att("sed -i -e s/x/y/ a.py b.py", ['a.py', 'b.py'], False, "sed multiple fichiers avec -i")

    # Correctif 3 : sed sans -i ne doit pas produire de chemins.
    # L'ancienne version pouvait signaler une lecture inutile.
    att("sed 's/a/b/' f.py", [], False, "sed sans -i, aucune cible")
    att("sed -n '1,5p' f.py", [], False, "sed -n sans -i, aucune cible")

    # Correctif 4 : citation non fermee.
    # L'outil renvoyait un chemin faux ou ne detectait pas l'indetermine.
    att('echo x > "non ferme', [], True, "citation non fermee")
    # Anti-controle : deux guillemets pairs, chemin correct.
    att('echo "a | b" > f.txt', ['f.txt'], False, "citation fermee correcte")

    # Correctif 5 : apostrophe orpheline collee a la cible.
    # L'ancien extracteur ajoutait la quote au chemin ou ne renvoyait rien.
    att("bash -c 'echo x > f.txt'", ['f.txt'], False, "bash -c avec apostrophe")
    att("eval 'echo x > f.txt'", ['f.txt'], False, "eval avec apostrophe")

    # --- Quatre motifs reels manquants au banc initial ----------------------
    # Issus de sessions reelles, ils n'avaient jamais ete couverts : aucun ne
    # ressemble aux cas ecrits a la main ci-dessus.
    att("cat err 2>&1 | grep motif", [], False,
        "CAS A : 2>&1 n'ecrit aucun fichier ; le tube non plus")
    att('grep "x < y" fichier.py', [], False,
        "CAS B : chevron dans une chaine citee, pas une redirection")
    att("cat << 'fin'", [], True,
        "CAS C : heredoc, cible indeterminee")
    att("echo x > doit_passer.txt", ["doit_passer.txt"], False,
        "CAS D : anti-controle, redirection simple inchangee")
    print("")
    if echecs:
        print("epreuve ratee : %d cas" % echecs)
        sys.exit(1)
    print("epreuve tenue")
    sys.exit(0)


if __name__ == "__main__":
    main()
