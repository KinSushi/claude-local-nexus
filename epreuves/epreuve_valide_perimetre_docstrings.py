import os
import sys
import importlib.util
import tempfile
from pathlib import Path

# ----------------------------------------------------------------------
# 1. Configuration de l'environnement avant le chargement du module testé
# ----------------------------------------------------------------------
os.environ["NEXUS_GATEWAY"] = "http://127.0.0.1:9"

# Utilisation d'un TemporaryDirectory (pas NamedTemporaryFile) conformément à la consigne
_TEMP_DIR = tempfile.TemporaryDirectory()
os.environ["NEXUS_ETAT_DISJONCTEUR"] = _TEMP_DIR.name

# ----------------------------------------------------------------------
# 2. Chargement dynamique du module `scripts/nexus_valide.py`
# ----------------------------------------------------------------------
_ROOT = Path(__file__).resolve().parents[1]          # répertoire racine du dépôt
_MODULE_PATH = _ROOT / "scripts" / "nexus_valide.py"

_spec = importlib.util.spec_from_file_location("nexus_valide", str(_MODULE_PATH))
if _spec is None or _spec.loader is None:
    raise ImportError(f"Impossible de charger le module depuis {_MODULE_PATH}")
nexus_valide = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(nexus_valide)

# ----------------------------------------------------------------------
# 3. Infrastructure de comptage et d'affichage des cas de test
# ----------------------------------------------------------------------
total_cases = 0
failed_cases = 0


def run_case(name: str, func):
    """Exécute un cas de test et affiche le résultat."""
    global total_cases, failed_cases
    total_cases += 1
    try:
        result = func()
        print(f"[OK  ] {name} : {result!r}")
    except Exception as exc:  # noqa: BLE001
        failed_cases += 1
        exc_type = type(exc).__name__
        print(f"[RATE] {name} : {exc_type}: {exc}")
        # Propagation éventuelle pour le débogage (facultatif)
        # raise


# ----------------------------------------------------------------------
# 4. Cas de test
# ----------------------------------------------------------------------


def case_C0():
    """C0 – Vérifie que la fonction `extract_changed_functions` est bien présente."""
    assert hasattr(nexus_valide, "extract_changed_functions"), "Fonction manquante"
    return "presente"


def case_F1():
    """F1 – Diff contenant uniquement une modification de docstring ; le nom ne doit pas être retourné."""
    diff = """diff --git a/file.py b/file.py
--- a/file.py
+++ b/file.py
@@ -10,3 +10,3 @@ def calculer_total(a, b):
-    \"\"\"Calcul le total\"\"\"
+    \"\"\"Calcul le total mis à jour\"\"\"
"""
    res = nexus_valide.extract_changed_functions(diff)
    assert "calculer_total" not in res, "Nom indésirable présent"
    return res


def case_F2():
    """F2 – Diff contenant une modification de code ; le nom doit être retourné."""
    diff = """diff --git a/file.py b/file.py
--- a/file.py
+++ b/file.py
@@ -10,3 +10,3 @@ def calculer_total(a, b):
-    return a + b
+    return a + b + 1
"""
    res = nexus_valide.extract_changed_functions(diff)
    assert "calculer_total" in res, "Nom attendu absent"
    return res


def case_F3():
    """F3 – Ajout d'une nouvelle fonction ; le nom doit être détecté même si le reste est documentaire."""
    diff = """diff --git a/file.py b/file.py
--- a/file.py
+++ b/file.py
@@ -0,0 +1,5 @@
+def nouvelle_fonction(x):
+    \"\"\"Nouvelle fonction\"\"\"
+    return x * 2
"""
    res = nexus_valide.extract_changed_functions(diff)
    assert "nouvelle_fonction" in res, "Nom de la fonction ajoutée non détecté"
    return res


def case_F4():
    """F4 – Modification de la signature d'une fonction ; le nom doit être détecté."""
    diff = """diff --git a/file.py b/file.py
--- a/file.py
+++ b/file.py
@@ -5,2 +5,2 @@
-def f(a):
-    pass
+def f(a, b):
+    pass
"""
    res = nexus_valide.extract_changed_functions(diff)
    assert "f" in res, "Nom de la fonction dont la signature change n'est pas détecté"
    return res


def case_R1():
    """R1 – Modification d'un commentaire uniquement ; le nom ne doit pas être détecté."""
    diff = """diff --git a/file.py b/file.py
--- a/file.py
+++ b/file.py
@@ -10,3 +10,3 @@ def ma_fonction():
-    # ancien commentaire
+    # nouveau commentaire
"""
    res = nexus_valide.extract_changed_functions(diff)
    assert "ma_fonction" not in res, "Nom indésirable présent pour un changement de commentaire"
    return res


def case_R2():
    """R2 – Diff vide et diff sans en‑tête de hunk ; les deux doivent retourner une liste vide."""
    empty_diff = ""
    no_hunk_diff = "random text without any hunk header"
    res1 = nexus_valide.extract_changed_functions(empty_diff)
    res2 = nexus_valide.extract_changed_functions(no_hunk_diff)
    assert isinstance(res1, list) and not res1, "Diff vide doit retourner []"
    assert isinstance(res2, list) and not res2, "Diff sans hunk doit retourner []"
    return (res1, res2)


def case_L1():
    """L1 – Vérifie que la variable d'environnement NEXUS_GATEWAY a bien la valeur attendue."""
    val = os.getenv("NEXUS_GATEWAY")
    assert val == "http://127.0.0.1:9", f"NEXUS_GATEWAY vaut {val!r} au lieu de 'http://127.0.0.1:9'"
    return val


# ----------------------------------------------------------------------
# 5. Exécution des cas
# ----------------------------------------------------------------------
run_case("C0", case_C0)
run_case("F1", case_F1)
run_case("F2", case_F2)
run_case("F3", case_F3)
run_case("F4", case_F4)
run_case("R1", case_R1)
run_case("R2", case_R2)
run_case("L1", case_L1)

# ----------------------------------------------------------------------
# 6. Résumé et sortie
# ----------------------------------------------------------------------
print(f"{total_cases} cas, {failed_cases} RATE")
sys.exit(1 if failed_cases > 0 else 0)
