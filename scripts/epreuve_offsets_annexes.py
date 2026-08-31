# -*- coding: utf-8 -*-
"""Les offsets d'un corpus annexe sont-ils VERIFIES, et la verification mord-elle ?

DEUX DEFAUTS TROUVES LE 2026-08-31, en absorbant un corpus produit par une
instance voisine -- donc par un producteur INDEPENDANT, dont rien ne
garantissait qu'il suive la meme convention d'offsets.

  1. `verifier_offsets_annexe` etait DEFINIE et appelee nulle part. Le message
     « offsets relus par seek : 201 verifies » vient de `construire_index`,
     qui indexe la documentation PYTHON : il ne dit rien des annexes. J'avais
     moi-meme cite ce nombre comme preuve que mon corpus ingere etait verifie
     -- une inference, faite parce que j'ingerais 201 entrees au moment ou je
     lisais 201. C'est « l'instrument qui repond a la question voisine ».

  2. Une fois la verification cablee, elle NE MORDAIT PAS. Les 28 offsets du
     corpus voisin tous decales de 7 octets : construction verte, code 0,
     aucun mot. 60 tirages repartis sur une liste A PLAT de 3769 entrees ne
     touchent jamais un corpus de 28.

Le remede n'a pas ete d'agrandir l'echantillon -- a 1,6 % de couverture il
aurait fallu le multiplier par soixante pour ESPERER -- mais de le repartir
PAR CORPUS. Un corpus est produit par un outil unique : si cet outil se
trompe, il se trompe sur TOUTES ses entrees. Repartir par corpus rend donc
structurellement impossible qu'un corpus entier echappe.

CE QUE LE DEFAUT AURAIT COUTE. Un corpus dont les offsets sont decales est
parfaitement lisible : chaque consultation rend simplement le contenu d'une
AUTRE entree. L'index annonce un sujet, le seek en rend un autre, et rien ne
le signale.
"""
import io
import json
import os
import shutil
import subprocess
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Un nom improbable, sous references/ pour etre decouvert, et retire ensuite.
CORPUS = os.path.join(RACINE, "references", "_epreuve_offsets_jetable")

echecs = 0


def verifier(nom, condition, detail):
    global echecs
    print("  [%s] %s : %s" % ("OK  " if condition else "RATE", nom, detail))
    if not condition:
        echecs += 1


def batir(decalage=0):
    """
    Ecrit un corpus minimal, avec un decalage optionnel sur les offsets.

    Les entrees portent des accents : sur un corpus sans accent, un offset en
    caracteres et un offset en octets coincident, et l'epreuve serait verte a
    tort.
    """
    os.makedirs(CORPUS, exist_ok=True)
    entrees = [
        {"id": "jetable.premiere", "resume": "premiere entree accentuee",
         "titre": "Premiere entree accentuee", "texte": "donnees, integrite",
         "type": "doc"},
        {"id": "jetable.deuxieme", "resume": "deuxieme entree accentuee",
         "titre": "Deuxieme entree accentuee", "texte": "cle privee, reseau",
         "type": "doc"},
        {"id": "jetable.troisieme", "resume": "troisieme entree accentuee",
         "titre": "Troisieme entree accentuee", "texte": "acces, perimetre",
         "type": "doc"},
    ]
    lignes_idx = ["id\toffset_octets\tlongueur_octets\ttype\tresume"]
    offset = 0
    with io.open(os.path.join(CORPUS, "symbols.jsonl"), "w",
                 encoding="utf-8", newline="\n") as fh:
        for e in entrees:
            ligne = json.dumps(e, ensure_ascii=False) + "\n"
            octets = len(ligne.encode("utf-8"))
            lignes_idx.append("%s\t%d\t%d\tdoc\t%s"
                              % (e["id"], offset + decalage, octets, e["resume"]))
            fh.write(ligne)
            offset += octets
    io.open(os.path.join(CORPUS, "index.tsv"), "w",
            encoding="utf-8", newline="\n").write("\n".join(lignes_idx) + "\n")


def construire():
    r = subprocess.run([sys.executable, os.path.join(RACINE, "scripts", "nexus_doc.py"),
                        "--construire"], cwd=RACINE, capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def main():
    global echecs
    echecs = 0
    try:
        # --- FORWARD : un corpus sain passe, et la ligne le DIT -----------
        batir(decalage=0)
        code, sortie = construire()
        ligne = [x for x in sortie.splitlines() if x.startswith("annexes")]
        verifier("un corpus sain passe", code == 0 and bool(ligne),
                 ligne[0] if ligne else sortie[-70:])
        verifier("le compte des corpus est dit",
                 bool(ligne) and "corpus" in ligne[0],
                 "sinon on ignore combien de corpus ont ete regardes")

        # --- REVERSE : le decalage est VU, et le code de sortie le porte --
        #
        # C'est le cas decisif. La premiere version de cette verification
        # passait ici en vert, et c'est ce qui l'a fait reecrire.
        batir(decalage=7)
        code, sortie = construire()
        dit = [x for x in sortie.splitlines() if "DISCORDANT" in x]
        verifier("un offset decale est VU", bool(dit),
                 dit[0][:88] if dit else "aucune discordance signalee")
        verifier("le code de sortie porte la discordance", code != 0,
                 "code = %d ; un avertissement sans code finit par ne plus etre lu"
                 % code)

        # --- FUITE : la construction de l'index Python n'est pas empechee -
        #
        # Un corpus annexe fautif ne doit pas priver le depot de sa
        # documentation Python. Le refuser en bloc serait un garde trop large.
        verifier("l'index Python est construit malgre tout",
                 "index écrit" in sortie, "un corpus annexe fautif ne bloque pas")
    finally:
        shutil.rmtree(CORPUS, ignore_errors=True)
        # L'index reste coherent pour la suite : on le reconstruit sans le
        # corpus jetable. Laisser un index qui reference un corpus disparu
        # ferait echouer la prochaine consultation pour une raison sans
        # rapport.
        construire()

    print("")
    if echecs:
        print("epreuve ratee : %d cas" % echecs)
        sys.exit(1)
    print("epreuve tenue")
    sys.exit(0)


if __name__ == "__main__":
    main()
