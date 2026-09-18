# -*- coding: utf-8 -*-
"""
Clé de vérification des appels Invoke-WebRequest sans -UseBasicParsing.

Le script se place dans epreuves/ ; la racine du dépôt est le répertoire
parent de ce répertoire. Cette information est calculée à partir de __file__.
"""

import contextlib
import os
import sys
import argparse
import uuid

# Ajout du répertoire outillage à sys.path
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUTILAGE_DIR = os.path.join(ROOT_DIR, "outillage")
if OUTILAGE_DIR not in sys.path:
    sys.path.insert(0, OUTILAGE_DIR)

# Import forcé de l'outil d'encodage UTF‑8
try:
    from console_tools import forcer_utf8
    forcer_utf8()
except ImportError as exc:
    sys.stderr.write("ImportError lors du chargement de console_tools : %s\n" % exc)

# Constante des chemins tolérés (vide au départ)
TOLERES = set()

def _read_ps1_files():
    """Génère les chemins des fichiers .ps1 sous scripts/ et outillage/."""
    for sub in ("scripts", "outillage"):
        base = os.path.join(ROOT_DIR, sub)
        for dirpath, _, filenames in os.walk(base):
            for name in filenames:
                if name.lower().endswith(".ps1"):
                    yield os.path.join(dirpath, name)

def _assemble_commands(lines):
    """
    Assemble les lignes en commandes complètes en tenant compte du caractère
    de continuation PowerShell (`). Retourne une liste de tuples
    (numero_debut, commande).
    """
    commands = []
    i = 0
    while i < len(lines):
        line = lines[i]
        # Ignorer les lignes de commentaire
        if line.lstrip().startswith("#"):
            i += 1
            continue
        start = i + 1  # numéro de ligne 1‑based
        cmd_parts = [line.rstrip("\n")]
        while cmd_parts[-1].rstrip().endswith("`"):
            # Retirer le backtick de continuation
            cmd_parts[-1] = cmd_parts[-1].rstrip()[:-1]
            i += 1
            if i >= len(lines):
                break
            cmd_parts.append(lines[i].rstrip("\n"))
        commands.append((start, "".join(cmd_parts)))
        i += 1
    return commands

def _is_faulty(command):
    """
    Retourne True si la commande contient Invoke-WebRequest sans le paramètre
    -UseBasicParsing (insensible à la casse). Les commentaires sont déjà exclus.
    """
    if "Invoke-WebRequest" not in command:
        return False
    # Recherche du paramètre, insensible à la casse
    return "-UseBasicParsing".lower() not in command.lower()

def _analyse_fichier(path):
    """Analyse un fichier .ps1 et renvoie la liste des numéros de ligne fautifs."""
    fautifs = []
    try:
        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except Exception as exc:
        sys.stderr.write("Impossible de lire %s : %s\n" % (path, exc))
        return fautifs
    for num, cmd in _assemble_commands(lines):
        if _is_faulty(cmd):
            fautifs.append(num)
    return fautifs

def _contre_epreuve():
    """Vérifie le mécanisme sur un fichier temporaire."""
    tmp_path = os.path.join(ROOT_DIR, "epreuves", f"tmp_test_{uuid.uuid4().hex}.ps1")
    try:
        # Étape 1 : sans -UseBasicParsing (devrait être fautif)
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write("Invoke-WebRequest http://example.com\n")
        fautif1 = any(_is_faulty(cmd) for _, cmd in _assemble_commands(
            open(tmp_path, "r", encoding="utf-8").readlines()))
        print("Etape 1 : attendu FAUTIF, obtenu %s" % ("FAUTIF" if fautif1 else "OK"))

        # Étape 2 : avec -UseBasicParsing (ne doit plus être fautif)
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write("Invoke-WebRequest -UseBasicParsing http://example.com\n")
        fautif2 = any(_is_faulty(cmd) for _, cmd in _assemble_commands(
            open(tmp_path, "r", encoding="utf-8").readlines()))
        print("Etape 2 : attendu OK, obtenu %s" % ("OK" if not fautif2 else "FAUTIF"))

        conclusion = "CONCLUSION : OK" if (fautif1 and not fautif2) else "CONCLUSION : ECHEC"
        print(conclusion)
        return 0 if (fautif1 and not fautif2) else 1
    finally:
        with contextlib.suppress(OSError):
            os.remove(tmp_path)

def main():
    parser = argparse.ArgumentParser(description="Détecte les appels Invoke-WebRequest sans -UseBasicParsing.")
    parser.add_argument("--contre-epreuve", action="store_true",
                        help="Exécute le test de contre‑épreuve.")
    args = parser.parse_args()

    if args.contre_epreuve:
        code = _contre_epreuve()
        sys.exit(code)

    total_fautifs = 0
    for fichier in _read_ps1_files():
        lignes_fautives = _analyse_fichier(fichier)
        if lignes_fautives:
            total_fautifs += len(lignes_fautives)
            for num in lignes_fautives:
                print("%s : ligne %d" % (fichier, num))

    # Gestion des chemins tolérés qui ne sont plus fautifs
    chemins_non_fautifs = [c for c in TOLERES if c not in TOLERES]
    if chemins_non_fautifs:
        for c in chemins_non_fautifs:
            print("Chemin toléré devenu correct, retirer de TOLERES : %s" % c)
        total_fautifs += len(chemins_non_fautifs)

    print("Nombre total de fautifs : %d" % total_fautifs)
    sys.exit(1 if total_fautifs else 0)

if __name__ == "__main__":
    main()
