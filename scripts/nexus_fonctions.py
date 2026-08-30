#!/usr/bin/env python3
"""
Remplace des fonctions entières dans un fichier Python en se basant sur les
bornes fournies par l'AST.  Le script évite les tronquages de gros fichiers
en ne demandant au modèle que les parties réellement modifiées.
"""

import ast
import argparse
import sys
import os
import tempfile

# ---------------------------------------------------------------------------

def charger_fichier(chemin):
    """Lit le fichier en UTF‑8 et renvoie la liste de ses lignes."""
    with open(chemin, "r", encoding="utf-8") as f:
        return f.readlines()


def analyser_ast(lignes):
    """
    Analyse le module et renvoie un dictionnaire :
        nom_fonction -> (debut, fin)
    où debut et fin sont des indices de ligne 1‑based incluant les décorateurs.
    Les méthodes de classe sont référencées sous la forme Classe.methode.
    """
    source = "".join(lignes)
    arbre = ast.parse(source)
    fonctions = {}

    for node in arbre.body:
        # fonctions top‑level
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            debut = _ligne_debut(node)
            fonctions[node.name] = (debut, node.end_lineno)
        # classes : on ne retient que les méthodes si le nom demandé les cible
        elif isinstance(node, ast.ClassDef):
            for sub in node.body:
                if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    nom_complet = f"{node.name}.{sub.name}"
                    debut = _ligne_debut(sub)
                    fonctions[nom_complet] = (debut, sub.end_lineno)
    return fonctions


def _ligne_debut(node):
    """Retourne la première ligne du décorateur le plus haut ou du def."""
    if node.decorator_list:
        return min(d.lineno for d in node.decorator_list)
    return node.lineno


def parser_blocs(chemin):
    """
    Lit le fichier de remplacements et renvoie une liste de tuples
    (nom_fonction, code_lignes).  Lève ValueError si un bloc est mal formé.
    """
    lignes = charger_fichier(chemin)
    blocs = []
    i = 0
    while i < len(lignes):
        ligne = lignes[i].strip()
        if ligne.startswith("@@FONCTION") and ligne.endswith("@@"):
            nom = ligne[len("@@FONCTION"): -len("@@")].strip()
            i += 1
            code = []
            while i < len(lignes) and lignes[i].strip() != "@@FIN@@":
                code.append(lignes[i])
                i += 1
            if i == len(lignes):
                raise ValueError(f"Bloc {nom} non terminee")
            # on saute la ligne @@FIN@@
            i += 1
            blocs.append((nom, code))
        else:
            i += 1
    return blocs


def appliquer_remplacements(lignes_cible, fonctions, blocs):
    """
    Retourne les nouvelles lignes ainsi que deux listes :
        - fonctions remplacées
        - fonctions ajoutées
    """
    import ast

    nouvelles = lignes_cible[:]
    remplacements = []
    ajouts = []

    # ------------------------------------------------------------
    # 1. Préparer les remplacements et les ajouts
    # ------------------------------------------------------------
    ops = []
    for nom, code in blocs:
        if nom in fonctions:
            debut, fin = fonctions[nom]
            ops.append((debut, fin, code, nom))   # (début, fin, nouveau code, nom)
        else:
            ajouts.append((nom, code))            # fonctions qui n'existent pas encore

    # ------------------------------------------------------------
    # 2. Appliquer les remplacements (du plus grand début au plus petit)
    # ------------------------------------------------------------
    ops.sort(key=lambda x: x[0], reverse=True)
    for debut, fin, code, nom in ops:
        # les indices AST sont 1‑based, la liste Python 0‑based
        nouvelles[debut - 1: fin] = code
        remplacements.append(nom)

    # ------------------------------------------------------------
    # 3. Insérer les fonctions nouvelles
    # ------------------------------------------------------------
    if ajouts:
        # 3.1 Localiser le bloc `if __name__ == "__main__"` via l'AST
        source = "".join(lignes_cible)
        try:
            tree = ast.parse(source)
        except SyntaxError:
            # si le fichier ne se parse pas, on se rabat sur l'ajout en fin de fichier
            tree = None

        insertion_index = None
        if tree is not None:
            for node in tree.body:
                if isinstance(node, ast.If):
                    # test doit être: __name__ == "__main__"
                    test = node.test
                    if (isinstance(test, ast.Compare) and
                        isinstance(test.left, ast.Name) and
                        test.left.id == "__name__" and
                        len(test.ops) == 1 and isinstance(test.ops[0], ast.Eq) and
                        len(test.comparators) == 1):
                        comp = test.comparators[0]
                        # ast.Constant (py≥3.8) ou ast.Str (py<3.8)
                        if (isinstance(comp, ast.Constant) and comp.value == "__main__") or \
                           (isinstance(comp, ast.Str) and comp.s == "__main__"):
                            insertion_index = node.lineno - 1   # 0‑based
                            break

        # 3.2 Construire la séquence à insérer
        a_inserer = ["\n", "\n"]                     # deux lignes vides AVANT les ajouts
        for _, code in ajouts:
            a_inserer.extend(code)

        # 3.3 Effectuer l'insertion
        if insertion_index is not None:
            # insertion juste avant le bloc `if __name__ == "__main__"`
            nouvelles[insertion_index:insertion_index] = a_inserer
        else:
            # aucun bloc __main__ trouvé → on ajoute en fin de module
            nouvelles.append("\n")
            nouvelles.append("\n")
            for _, code in ajouts:
                nouvelles.extend(code)

    # ------------------------------------------------------------
    # NOTE : pourquoi insérer avant le bloc `if __name__ == "__main__"` ?
    # ------------------------------------------------------------
    # Si une fonction est ajoutée *après* ce bloc, elle n'existe pas encore
    # lorsque `main()` (appelé dans le bloc) s'exécute. Cela provoque
    # `NameError: name '<fonction>' is not defined`. Le problème n'est pas
    # détectable par la vérification syntaxique, car la syntaxe reste valide.
    # En insérant les nouvelles fonctions avant le bloc, elles sont déjà
    # définies au moment où `main()` démarre, évitant ainsi l'erreur.
    # ------------------------------------------------------------

    return nouvelles, remplacements, [n for n, _ in ajouts]


def verifier_syntaxe(lignes):
    """Lève SyntaxError si le code ne se parse pas."""
    source = "".join(lignes)
    ast.parse(source)


def ecrire_atomique(chemin, lignes):
    """Écrit de façon atomique en remplaçant le fichier cible."""
    dir_name = os.path.dirname(os.path.abspath(chemin))
    fd, tmp_path = tempfile.mkstemp(dir=dir_name, text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as tmp:
            tmp.writelines(lignes)
        os.replace(tmp_path, chemin)
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def rapport(remplacees, ajoutees, demandes):
    """Affiche un petit rapport sans accents."""
    print("Fonctions remplacees :", ", ".join(remplacees) if remplacees else "aucune")
    print("Fonctions ajoutees   :", ", ".join(ajoutees) if ajoutees else "aucune")
    introuvables = [n for n in demandes if n not in remplacees and n not in ajoutees]
    print("Fonctions introuvables:", ", ".join(introuvables) if introuvables else "aucune")


def main():
    parser = argparse.ArgumentParser(description="Remplace des fonctions dans un fichier Python.")
    parser.add_argument("--cible", required=True, help="Fichier Python à modifier")
    parser.add_argument("--blocs", required=True, help="Fichier contenant les blocs de remplacement")
    parser.add_argument("--simuler", action="store_true", help="N'effectue aucune ecriture")
    args = parser.parse_args()

    try:
        lignes_cible = charger_fichier(args.cible)
        fonctions = analyser_ast(lignes_cible)
        blocs = parser_blocs(args.blocs)
    except (OSError, ValueError, SyntaxError) as e:
        print(f"Erreur de lecture ou de parsing : {e}")
        return 1

    nouvelles, remplacees, ajoutees = appliquer_remplacements(lignes_cible, fonctions, blocs)

    try:
        verifier_syntaxe(nouvelles)
    except SyntaxError as e:
        print(f"Resultat invalide, aucune modification appliquee : {e}")
        return 1

    rapport(remplacees, ajoutees, [n for n, _ in blocs])

    if not args.simuler:
        try:
            ecrire_atomique(args.cible, nouvelles)
        except OSError as e:
            print(f"Echec d'ecriture : {e}")
            return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
