# -*- coding: utf-8 -*-
"""Appliquer un patch rendu par le banc, apres verification.

L'orchestrateur ne retape pas : il verifie que chaque bloc AVANT est REEL
et UNIQUE dans le fichier cible, applique tous les blocs, et laisse
l'epreuve juger. Un bloc absent ou multiple provoque un REFUS total.
"""
import io
import json
import re
import sys

def main():
    if len(sys.argv) < 4:
        print("Usage: python nexus_appliquer.py <fichier_jsonl> <nom_tache> <fichier_cible>")
        return 2

    jsonl_path, nom_tache, cible_path = sys.argv[1], sys.argv[2], sys.argv[3]

    # Lecture du JSONL
    texte = None
    with io.open(jsonl_path, encoding="utf-8") as fh:
        for ligne in fh:
            ligne = ligne.strip()
            if not ligne:
                continue
            d = json.loads(ligne)
            if d.get("nom") == nom_tache:
                texte = d.get("texte") or ""
                break

    if texte is None:
        print("REFUS : aucune tache nommee %s dans %s" % (nom_tache, jsonl_path))
        return 1

    if "AUCUN DEFAUT" in texte.upper():
        print("Le banc declare AUCUN DEFAUT SUR -- rien a appliquer.")
        return 2

    # Extraction de tous les blocs AVANT/APRES/FIN
    pattern = re.compile(
        r'^<<<AVANT>>>[ \t]*\r?$(.*?)^<<<APRES>>>[ \t]*\r?$(.*?)^<<<FIN>>>[ \t]*\r?$',
        re.MULTILINE | re.DOTALL
    )
    blocs = []
    for m in pattern.finditer(texte):
        avant = m.group(1).strip("\r\n")
        apres = m.group(2).strip("\r\n")
        blocs.append((avant, apres))

    if not blocs:
        print("REFUS : le rendu ne porte pas les triplets de marqueurs.")
        print(texte[:400])
        return 1

    # Lecture du fichier cible
    with io.open(cible_path, encoding="utf-8") as f:
        src = f.read()

    # Verification de chaque bloc AVANT
    for idx, (avant, _) in enumerate(blocs, start=1):
        occ = src.count(avant)
        if occ != 1:
            print("REFUS : le bloc %d doit etre unique et reel. Occurrences trouvees : %d" % (idx, occ))
            print("--- ce que le banc a cru trouver ---")
            print(avant[:400])
            return 1

    # Application de tous les remplacements
    nouveau_src = src
    for avant, apres in blocs:
        nouveau_src = nouveau_src.replace(avant, apres)

    # Ecriture du fichier cible
    with io.open(cible_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(nouveau_src)

    print("APPLIQUE : %d bloc(s) dans %s" % (len(blocs), cible_path))
    return 0

if __name__ == "__main__":
    sys.exit(main())