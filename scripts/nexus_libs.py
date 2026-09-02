#!/usr/bin/env python3
"""
nexus_libs - Outil de comparaison d'ensembles de bibliotheques Python.

Usage:
    python nexus_libs.py --doc-dir <chemin_doc> --config <fichier_json>

Le fichier JSON doit contenir:
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

# Reconfiguration du flux de sortie pour eviter les erreurs d'encodage console
sys.stdout = open(sys.stdout.fileno(), mode='w', encoding='utf-8', errors='replace')

def _load_config(path):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return data.get("name_map", {}), data.get("deep_modules", {})

def _list_doc_modules(doc_dir, name_map):
    """Retourne l'ensemble des noms de modules documentes."""
    modules = set()
    for entry in os.listdir(doc_dir):
        full = os.path.join(doc_dir, entry)
        if not os.path.isdir(full):
            continue
        module_name = name_map.get(entry, entry)
        modules.add(module_name)
    return modules

def _test_import(module_name):
    """Essaye d'importer le module de premier niveau."""
    try:
        importlib.import_module(module_name)
        return True
    except Exception:
        return False

def _test_deep_import(deep_path):
    """Essaye d'importer le sous-module indique."""
    try:
        importlib.import_module(deep_path)
        return True
    except Exception:
        return False

def main():
    parser = argparse.ArgumentParser(prog="nexus_libs")
    parser.add_argument("--doc-dir", required=True,
                        help="Repertoire contenant les dossiers de documentation.")
    parser.add_argument("--config", required=True,
                        help="Fichier JSON de configuration (name_map, deep_modules).")
    args = parser.parse_args()

    print(f"Interpreteur : {sys.executable}")

    name_map, deep_modules = _load_config(args.config)
    documented = _list_doc_modules(args.doc_dir, name_map)
    importable = {m for m in documented if _test_import(m)}

    broken_deep = set()
    not_measured_deep = set()

    for mod in importable:
        deep_path = deep_modules.get(mod)
        if deep_path:
            if _test_deep_import(deep_path):
                pass # Utilisable
            else:
                broken_deep.add(mod)
        else:
            not_measured_deep.add(mod)

    doc_absentes = sorted(documented - importable)
    broken_deep_sorted = sorted(broken_deep)
    not_measured_sorted = sorted(not_measured_deep)

    if doc_absentes:
        print("\nDocumentees mais absentes :")
        for name in doc_absentes:
            print(f"  - {name}")

    if broken_deep_sorted:
        print("\nImportables mais non utilisables en profondeur :")
        for name in broken_deep_sorted:
            print(f"  - {name}")

    if not_measured_sorted:
        print("\nNon mesurees en profondeur :")
        for name in not_measured_sorted:
            print(f"  - {name}")

    # Code de retour: documentees absentes OU reellement cassees en profondeur
    sys.exit(1 if (doc_absentes or broken_deep_sorted) else 0)

if __name__ == "__main__":
    main()
