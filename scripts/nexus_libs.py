#!/usr/bin/env python3
"""
nexus_libs – Outil de comparaison d’ensembles de bibliothèques Python.

Usage :
    python nexus_libs.py --doc-dir <chemin_doc> --config <fichier_json>

Le fichier JSON doit contenir :
{
    "name_map":   {"doc_folder": "module.name", ...},   # optionnel
    "deep_modules": {"module.name": "submodule.path", ...}
}
"""

import sys
import os
import argparse
import json
import importlib
import traceback

def _root_path():
    """Chemin absolu du répertoire contenant ce script."""
    return os.path.abspath(os.path.dirname(__file__))

def _load_config(path):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    name_map = data.get("name_map", {})
    deep_modules = data.get("deep_modules", {})
    return name_map, deep_modules

def _list_doc_modules(doc_dir, name_map):
    """Retourne l’ensemble des noms de modules documentés."""
    modules = set()
    for entry in os.listdir(doc_dir):
        full = os.path.join(doc_dir, entry)
        if not os.path.isdir(full):
            continue
        module_name = name_map.get(entry, entry)
        modules.add(module_name)
    return modules

def _test_import(module_name):
    """Essaye d’importer le module de premier niveau."""
    try:
        importlib.import_module(module_name)
        return True
    except Exception:
        return False

def _test_deep_import(deep_path):
    """Essaye d’importer le sous‑module indiqué."""
    try:
        importlib.import_module(deep_path)
        return True
    except Exception:
        return False

def main():
    parser = argparse.ArgumentParser(prog="nexus_libs")
    parser.add_argument("--doc-dir", required=True,
                        help="Répertoire contenant les dossiers de documentation.")
    parser.add_argument("--config", required=True,
                        help="Fichier JSON de configuration (name_map, deep_modules).")
    args = parser.parse_args()

    # Affichage de l’interpréteur réellement utilisé
    print(f"Interpréteur : {sys.executable}")

    # Chargement de la configuration
    name_map, deep_modules = _load_config(args.config)

    # Ensemble 1 – Documentées
    documented = _list_doc_modules(args.doc_dir, name_map)

    # Ensemble 2 – Importables
    importable = {m for m in documented if _test_import(m)}

    # Ensemble 3 – Utilisables (import profond)
    usable = set()
    for mod in importable:
        deep_path = deep_modules.get(mod)
        if deep_path and _test_deep_import(deep_path):
            usable.add(mod)

    # Différences demandées
    doc_absentes = sorted(documented - importable)
    importables_cassees = sorted(importable - usable)

    if doc_absentes:
        print("\nDocumentées mais absentes :")
        for name in doc_absentes:
            print(f"  - {name}")

    if importables_cassees:
        print("\nImportables mais non utilisables en profondeur :")
        for name in importables_cassees:
            print(f"  - {name}")

    # Code de retour
    sys.exit(1 if doc_absentes else 0)

if __name__ == "__main__":
    main()
