# -*- coding: utf-8 -*-
"""Les options de ligne de commande doivent etre propagees aux taches d'un lot.

Defaut identifie comme une classe de regression : la branche `--lot` de
`scripts/nexus_agent.py` ne propage qu'une fraction des options disponibles.
L'utilisateur passe des arguments (ex: `--systeme`), croit qu'ils s'appliquent
au lot, mais ils sont silencieusement ignores car non recopies dans les
objets taches du JSON.

Trois options ont ete corrigees individuellement (temperature, max_tokens,
racine). Trois autres restent inertes (fichiers, systeme, competence).
L'epreuve derive la liste des options a verifier pour fermer la classe
de defaut et eviter toute nouvelle regression.
"""
import os
import re
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCE = os.path.join(RACINE, "scripts", "nexus_agent.py")


def _dire(ok, nom, detail):
    print("%s %s : %s" % ("[OK  ]" if ok else "[RATE]", nom, detail))
    return ok


def main():
    if not os.path.exists(SOURCE):
        print("Source introuvable : %s" % SOURCE)
        return 1

    with open(SOURCE, "r", encoding="utf-8") as fh:
        source = fh.read()

    # 1. Extraire les cles de tache lues par executer (tache.get("..."))
    # On ignore les cles commençant par '_'
    cles_tache = set()
    for match in re.finditer(r'tache\.get\([\'"]([^" ]+)[\'"]', source):
        # La regex ecartait a tort les cles contenant un souligne
        cle = match.group(1)
        if not cle.startswith('_'):
            cles_tache.add(cle)

    # 2. Extraire les options declarees par add_argument("--nom")
    options_cmd = set()
    for match in re.finditer(r'add_argument\("--([a-zA-Z0-9-]+)"', source):
        options_cmd.add(match.group(1).replace("-", "_"))

    # 3. Extraire la zone de la branche lot
    # Entre 'if args.lot:' et 'elif args.tache:'
    zone_lot_match = re.search(r'if args\.lot:(.*?)elif args\.tache:', source, re.S)
    if not zone_lot_match:
        print("Zone de branche lot introuvable dans le source")
        return 1
    zone_lot = zone_lot_match.group(1)

    # Intersection des cles de tache et des options CLI
    candidats = sorted(cles_tache.intersection(options_cmd))
    
    # Exceptions legitimes : declarees par le JSON du lot et non ecrasables globalement
    exceptions = {"tache", "modele", "nom"}
    
    examinees = [c for c in candidats if c not in exceptions]
    
    if not examinees:
        print("Aucune option a verifier trouvee (erreur de regex ?)")
        return 1

    code = 0
    for nom in examinees:
        # On verifie que 'args.nom' apparait dans la zone de propagation du lot
        propage = "args.%s" % nom in zone_lot
        if not _dire(propage, nom, "est propage dans la branche lot" if propage else "est INERTE"):
            code = 1

    print("\nNombre de noms examines : %d" % len(examinees))
    return code


if __name__ == "__main__":
    sys.exit(main())