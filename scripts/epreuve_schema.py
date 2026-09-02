# -*- coding: utf-8 -*-
"""L'outil tient-il sa promesse centrale : JAMAIS une valeur, toujours les cles ?

MESURE QUI JUSTIFIE CE BANC, tiree de la genese de l'outil : trois rendus
fautifs de suite ont ete mesures avant que le contrat de donnees soit etabli,
et c'est pour ne plus jamais faire sortir les valeurs que nexus_schema.py
existe. Un outil qui rendrait la structure MAIS laisserait passer une valeur
serait pire qu'un outil absent : il donnerait confiance a tort.

Le cas qui compte le plus est donc NEGATIF : des valeurs RECONNAISSABLES --
une chaine tres particuliere, un entier a sept chiffres, un flottant a
plusieurs decimales, une valeur imbriquee et une dans un tableau -- sont
plantees dans un JSON, et la sortie est passee au crible, en mode texte comme
en mode --json. Aucune ne doit y figurer, ni dans stdout ni dans stderr.

Les noms de cles, eux, DOIVENT apparaitre : c'est ce que l'outil promet de
rendre. Sans ce controle positif, un outil qui ne rendrait rien paraitrait
parfait -- les anti-controles portent la moitie du banc, comme chez le garde.

Tout se deroule dans un repertoire temporaire ; rien n'est ecrit ailleurs.
"""
import os
import sys
import json
import subprocess
import tempfile

REPERTOIRE = os.path.dirname(os.path.abspath(__file__))
OUTIL = os.path.join(REPERTOIRE, "nexus_schema.py")

# Valeurs reconnaissables : aucune ne peut figurer par hasard dans une sortie
# qui ne contiendrait que structure, types et cardinalites.
DONNEES = {
    "identifiant": "KUMQUAT-ZQL-7781-SECRET",
    "compte": 7654321,
    "mesure": 3.141592653589793,
    "enveloppe": {"interieur": "NID-SECRET-4402"},
    "journal": ["CELLULE-SECRET-6603", 7654321],
}
MARQUEURS = ["KUMQUAT-ZQL-7781-SECRET", "7654321", "3.141592653589793",
             "NID-SECRET-4402", "CELLULE-SECRET-6603"]
CLES = ["identifiant", "compte", "mesure", "enveloppe", "interieur", "journal"]

echecs = 0


def verifier(nom, condition, detail):
    global echecs
    print("  [%s] %s : %s" % ("OK  " if condition else "RATE", nom, detail))
    if not condition:
        echecs += 1


def lancer(*arguments):
    proc = subprocess.run([sys.executable, OUTIL] + list(arguments),
                          capture_output=True, text=True, timeout=60)
    return proc.returncode, proc.stdout, proc.stderr


def main():
    global echecs
    echecs = 0
    with tempfile.TemporaryDirectory(prefix="epreuve_schema_") as temp:

        # --- Le cas qui compte le plus : aucune valeur ne doit fuiter -------
        chemin_json = os.path.join(temp, "contrat.json")
        with open(chemin_json, "w", encoding="utf-8") as f:
            json.dump(DONNEES, f)
        for mode in ([], ["--json"]):
            etiquette = mode[0] if mode else "texte"
            code, sortie, err = lancer(*(mode + [chemin_json]))
            verifier("JSON valide : code 0 (%s)" % etiquette, code == 0,
                     "code=%d err=%s" % (code, err.strip()[:50]))
            for marqueur in MARQUEURS:
                verifier("absent %s (%s)" % (marqueur[:20], etiquette),
                         marqueur not in sortie and marqueur not in err,
                         "la valeur ne figure ni dans stdout ni dans stderr")
            for cle in CLES:
                verifier("cle %s (%s)" % (cle, etiquette), cle in sortie,
                         "le nom de cle est rendu")
            verifier("structure affichee (%s)" % etiquette,
                     "racine" in sortie or "squelette" in sortie,
                     "arborescence et types, pas de valeurs")

        # --- Texte brut : format non reconnu, jamais decrit comme CSV -------
        chemin_txt = os.path.join(temp, "brut.txt")
        with open(chemin_txt, "w", encoding="utf-8") as f:
            f.write("ceci est du texte brut, sans structure de donnees\n")
        code, sortie, err = lancer(chemin_txt)
        verifier("texte brut : code non nul", code != 0, "code=%d" % code)
        verifier("texte brut : format non reconnu",
                 "format non reconnu" in sortie + err, sortie.strip()[:60])
        verifier("texte brut : pas decrit comme CSV",
                 "(CSV" not in sortie and "colonnes" not in sortie,
                 "aucune description tabulaire")

        # --- Fichier inexistant : echec propre, jamais un traceback ---------
        code, sortie, err = lancer(os.path.join(temp, "inexistant.json"))
        verifier("inexistant : code non nul", code != 0, "code=%d" % code)
        verifier("inexistant : message d'erreur",
                 "ERREUR" in sortie or "Error" in sortie + err,
                 sortie.strip()[:60])
        verifier("inexistant : pas de traceback",
                 "Traceback" not in sortie + err, "echec nomme, proprement")

    print("")
    if echecs:
        print("epreuve ratee : %d cas" % echecs)
        sys.exit(1)
    print("epreuve tenue")
    sys.exit(0)


if __name__ == "__main__":
    main()
