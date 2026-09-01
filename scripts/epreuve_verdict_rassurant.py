# -*- coding: utf-8 -*-
import contextlib
import importlib.util
import io
import os
import sys


def _load_module():
    # Resolve repository root from this file's location
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    module_path = os.path.join(repo_root, "scripts", "nexus_valide.py")
    if not os.path.isfile(module_path):
        raise FileNotFoundError(f"Impossible de trouver le module à {module_path}")
    spec = importlib.util.spec_from_file_location("nexus_valide", module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Impossible de charger le module depuis {module_path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

def _fake_free_plan_judgment(diff_text, callers, modele=None):
    # Retourne : aucune regression, une bascule de plan, texte avec avertissement
    return (
        False,                     # regression flag
        "plan-fake",               # bascule de plan
        "[!] AVERTISSEMENT : test de validation sans regression\n"
    )

def _run_test():
    try:
        mod = _load_module()
    except Exception as e:
        print(f"[RATE] chargement du module : {e}")
        sys.exit(1)

    # Sauvegarde des fonctions originales
    originals = {
        "free_plan_judgment": getattr(mod, "free_plan_judgment", None),
        "get_modified_files_uncommitted": getattr(mod, "get_modified_files_uncommitted", None),
        "get_modified_files_from_base": getattr(mod, "get_modified_files_from_base", None),
        "get_diff_uncommitted": getattr(mod, "get_diff_uncommitted", None),
        "get_diff_from_base": getattr(mod, "get_diff_from_base", None),
        "mechanical_battery": getattr(mod, "mechanical_battery", None),
        "find_callers": getattr(mod, "find_callers", None),
    }

    # Patch des fonctions pour éviter les dépendances externes
    dummy_diff = (
        "diff --git a/file.py b/file.py\n"
        "--- a/file.py\n"
        "+++ b/file.py\n"
        "@@ -1,1 +1,1 @@\n"
        "-def foo():\n"
        "+def foo():\n"
    )
    try:
        mod.free_plan_judgment = _fake_free_plan_judgment
        mod.get_modified_files_uncommitted = lambda: []
        mod.get_modified_files_from_base = lambda base: []
        mod.get_diff_uncommitted = lambda: dummy_diff
        mod.get_diff_from_base = lambda base: dummy_diff
        mod.mechanical_battery = lambda modified: None
        mod.find_callers = lambda funcs: {}

        # Capture stdout
        captured = io.StringIO()
        original_argv = sys.argv[:]
        sys.argv = [original_argv[0], "--base", "HEAD"]
        with contextlib.redirect_stdout(captured):
            try:
                ret_code = mod.main()
            except SystemExit as se:
                ret_code = se.code
            except Exception as e:
                raise RuntimeError(f"Erreur lors de l'exécution de main : {e}") from e
        output = captured.getvalue()
    finally:
        # Restauration des fonctions originales
        for name, func in originals.items():
            setattr(mod, name, func)
        sys.argv = original_argv

    # Vérifications
    cases = [
        ("absence de regression",
         "Aucune regression detectee" in output,
         "Aucune regression détectée",                     # libellé succès
         "Phrase d'absence de regression introuvable"),  # libellé échec
        ("ligne d'avertissement",
         any(line.lstrip().startswith("[!]") for line in output.splitlines()),
         "Avertissement présent",                         # libellé succès
         "Avertissement '[!]' manquant"),                # libellé échec
        ("bascule de plan",
         "bascule de plan" in output.lower(),
         "Bascule de plan détectée",                     # libellé succès
         "Mention de la bascule de plan absente"),       # libellé échec
    ]

    all_ok = True
    for name, ok, success_msg, failure_msg in cases:
        if ok:
            print(f"[OK  ] {name} : {success_msg}")
        else:
            print(f"[RATE] {name} : {failure_msg}")
            all_ok = False

    sys.exit(0 if all_ok else 1)

if __name__ == "__main__":
    _run_test()