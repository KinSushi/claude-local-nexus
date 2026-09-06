# Produit par gpt-oss-120b-cloud (Ollama Cloud -- les donnees sortent)
import argparse
import csv
import importlib.metadata
import logging
import os
import sys
import sysconfig
import time
from pathlib import Path

# Import de l'extracteur fourni
try:
    import extraire_api_par_ast as extractor
except Exception as e:
    sys.stderr.write(f"Erreur d'importation de l'extracteur : {e}\\n")
    sys.exit(2)

# ----------------------------------------------------------------------
# Configuration du logger (texte simple, ASCII)
# ----------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stdout,
)

# ----------------------------------------------------------------------
# Découverte de la racine du dépôt (marqueur CLAUDE.md)
# ----------------------------------------------------------------------
def find_repo_root(start: Path) -> Path:
    current = start.resolve()
    while True:
        if (current / "CLAUDE.md").is_file():
            return current
        if current.parent == current:
            # Racine du système atteinte sans trouver le marqueur
            return start.anchor  # fallback, will be used as is
        current = current.parent

REPO_ROOT = find_repo_root(Path.cwd())

# ----------------------------------------------------------------------
# Chargement unique et chronométré de packages_distributions()
# ----------------------------------------------------------------------
def load_pkg_dist_map():
    start = time.perf_counter()
    try:
        mapping = importlib.metadata.packages_distributions()
    except Exception:
        mapping = {}
    duration = time.perf_counter() - start
    logging.info(f"packages_distributions chargé en {duration:.2f}s, {len(mapping)} modules trouvés")
    return mapping, duration

PKG_DIST_MAP, PKG_DIST_DURATION = load_pkg_dist_map()

# ----------------------------------------------------------------------
# Construction de la liste des cibles
# ----------------------------------------------------------------------
def enumerate_targets(only_stdlib: bool, only_third: bool):
    targets = []

    # 1. Bibliothèque standard
    stdlib_modules = {
        name for name in sys.stdlib_module_names if not name.startswith("_")
    }

    # 2. Modules tiers (clés du mapping)
    third_modules = set(PKG_DIST_MAP.keys())

    # Filtrage exclusif
    if only_stdlib:
        selected = stdlib_modules
    elif only_third:
        selected = third_modules
    else:
        selected = stdlib_modules.union(third_modules)

    for name in sorted(selected):
        nature = "stdlib" if name in stdlib_modules else "tierce"
        targets.append((name, nature))
    return targets

# ----------------------------------------------------------------------
# Fonction utilitaire : compter les symboles retournés
# ----------------------------------------------------------------------
def count_symbols(symbols):
    funcs = classes = methods = 0
    for _, typ, _, _ in symbols:
        if typ in ("function", "async function"):
            funcs += 1
        elif typ == "class":
            classes += 1
        elif typ in ("method", "async function"):  # async method also typ 'method' in extracteur
            methods += 1
    return funcs, classes, methods

# ----------------------------------------------------------------------
# Traitement d'une cible individuelle
# ----------------------------------------------------------------------
def process_target(name, nature, output_dir, redo, limit_reached):
    # Gestion de la limite d'essai
    if limit_reached[0]:
        return None  # signaler que le traitement doit s'arrêter

    out_path = Path(output_dir) / f"{name}_api_ast.md"

    # Saut si déjà présent et non vide
    if out_path.is_file() and out_path.stat().st_size > 0 and not redo:
        logging.info(f"SAUT {name} (déjà traité)")
        return {
            "nom": name,
            "nature": nature,
            "version": "INCONNUE",
            "nb_symbols": 0,
            "nb_fonctions": 0,
            "nb_classes": 0,
            "nb_methodes": 0,
            "duree": 0.0,
            "statut": "SAUTE_DEJA_FAIT",
        }

    # Choix du site‑packages : stdlib ou purelib
    if nature == "stdlib":
        site_packages = sysconfig.get_paths()["stdlib"]
    else:
        site_packages = sysconfig.get_paths()["purelib"]

    start = time.perf_counter()
    try:
        success, symbols, _, version = extractor.process_library(name, site_packages, str(output_dir))
        duration = time.perf_counter() - start
    except SystemExit as se:
        # L'extracteur utilise sys.exit(2) pour "introuvable"
        duration = time.perf_counter() - start
        if se.code == 2:
            logging.warning(f"INTROUVABLE {name}")
            return {
                "nom": name,
                "nature": nature,
                "version": "INCONNUE",
                "nb_symbols": 0,
                "nb_fonctions": 0,
                "nb_classes": 0,
                "nb_methodes": 0,
                "duree": duration,
                "statut": "INTROUVABLE",
            }
        else:
            logging.error(f"ECHEC {name} (SystemExit code={se.code})")
            return {
                "nom": name,
                "nature": nature,
                "version": "INCONNUE",
                "nb_symbols": 0,
                "nb_fonctions": 0,
                "nb_classes": 0,
                "nb_methodes": 0,
                "duree": duration,
                "statut": f"ECHEC (SystemExit {se.code})",
            }
    except Exception as exc:
        duration = time.perf_counter() - start
        logging.error(f"ECHEC {name} : {exc}")
        return {
            "nom": name,
            "nature": nature,
            "version": "INCONNUE",
            "nb_symbols": 0,
            "nb_fonctions": 0,
            "nb_classes": 0,
            "nb_methodes": 0,
            "duree": duration,
            "statut": f"ECHEC ({type(exc).__name__})",
        }

    # Comptage
    nb_fonctions, nb_classes, nb_methodes = count_symbols(symbols)
    nb_symbols = len(symbols)

    statut = "EXTRAIT" if success else "ECHEC (aucun symbole)"
    logging.info(f"{statut} {name} : {nb_symbols} symboles, {duration:.2f}s")
    return {
        "nom": name,
        "nature": nature,
        "version": version,
        "nb_symbols": nb_symbols,
        "nb_fonctions": nb_fonctions,
        "nb_classes": nb_classes,
        "nb_methodes": nb_methodes,
        "duree": duration,
        "statut": statut,
    }

# ----------------------------------------------------------------------
# Fonction principale
# ----------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Couverture totale de la documentation Python.")
    parser.add_argument("--sortie", required=True, help="Dossier où écrire les fichiers markdown.")
    parser.add_argument("--rapport", required=True, help="Fichier CSV récapitulatif.")
    parser.add_argument("--refaire", action="store_true", help="Forcer le retraitement même si le fichier existe.")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--seulement-stdlib", action="store_true", help="Ne traiter que la bibliothèque standard.")
    group.add_argument("--seulement-tierces", action="store_true", help="Ne traiter que les paquets tiers.")
    parser.add_argument("--limite", type=int, default=None, help="Nombre maximal de cibles à traiter (pour test).")
    args = parser.parse_args()

    os.makedirs(args.sortie, exist_ok=True)

    # Construction de la liste des cibles
    targets = enumerate_targets(args.seulement_stdlib, args.seulement_tierces)

    # Application de la limite éventuelle
    limite = args.limite
    if limite is not None:
        targets = targets[:limite]

    rows = []
    any_failure = False
    limit_reached = [False]  # mutable flag pour arrêter la boucle lorsqu'on atteint la limite dynamique

    for idx, (name, nature) in enumerate(targets, 1):
        if limite is not None and idx > limite:
            limit_reached[0] = True
            break

        result = process_target(name, nature, args.sortie, args.refaire, limit_reached)
        if result is None:
            break  # limite atteinte
        rows.append(result)

        if result["statut"].startswith("ECHEC"):
            any_failure = True

    # Écriture du CSV
    fieldnames = [
        "nom",
        "nature",
        "version",
        "nb_symbols",
        "nb_fonctions",
        "nb_classes",
        "nb_methodes",
        "duree",
        "statut",
    ]
    with open(args.rapport, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)

    # Retour du code d'exécution
    if any_failure:
        sys.exit(2)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()

