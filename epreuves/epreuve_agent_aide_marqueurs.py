import os
import sys
import importlib.util
import tempfile
from pathlib import Path

# Configuration d'environnement avant tout import du module testé
os.environ["NEXUS_GATEWAY"] = "http://127.0.0.1:9"
_temp_dir = tempfile.TemporaryDirectory()
os.environ["NEXUS_ETAT_DISJONCTEUR"] = _temp_dir.name

# Chargement du module cible
module_path = Path(__file__).resolve().parents[1] / "scripts" / "nexus_agent.py"
spec = importlib.util.spec_from_file_location("nexus_agent", module_path)
module = importlib.util.module_from_spec(spec)
assert spec is not None and spec.loader is not None, "Impossible de créer le spec du module"
spec.loader.exec_module(module)

# Compteurs et fonction d'exécution de cas
total_cases = 0
failed_cases = 0


def run_case(name, func):
    global total_cases, failed_cases
    total_cases += 1
    try:
        result = func()
        print(f"[OK  ] {name} : {result!r}")
    except Exception as e:
        failed_cases += 1
        print(f"[RATE] {name} : {type(e).__name__}: {e}")


# ---------- Cas de test ----------
def C0():
    """Longueur de la docstring."""
    assert module.__doc__ is not None and module.__doc__.strip() != "", "Docstring manquante ou vide"
    return len(module.__doc__)


def F1():
    """Présence des trois marqueurs de correction."""
    doc = module.__doc__
    cnt_avant = doc.count("<<<AVANT>>>")
    cnt_apres = doc.count("<<<APRES>>>")
    cnt_fin = doc.count("<<<FIN>>>")
    assert cnt_avant > 0, "Marqueur <<<AVANT>>> absent"
    assert cnt_apres > 0, "Marqueur <<<APRES>>> absent"
    assert cnt_fin > 0, "Marqueur <<<FIN>>> absent"
    return (cnt_avant, cnt_apres, cnt_fin)


def F2():
    """Présence du marqueur <<<CREER>>>."""
    doc = module.__doc__
    cnt = doc.count("<<<CREER>>>")
    assert cnt > 0, "Marqueur <<<CREER>>> absent"
    return cnt


def F3():
    """Présence des deux outils de pose."""
    doc = module.__doc__
    has_appliquer = "nexus_appliquer" in doc
    has_creer = "nexus_creer" in doc
    assert has_appliquer, "nexus_appliquer absent"
    assert has_creer, "nexus_creer absent"
    return (has_appliquer, has_creer)


def R1():
    """Le mot DEMANDES doit apparaître."""
    doc = module.__doc__
    assert "DEMANDES" in doc, "Mot DEMANDES absent"
    return True


def R2():
    """Vérifie la présence de --materialiser et du mot pose."""
    doc = module.__doc__
    has_materialiser = "--materialiser" in doc
    has_pose = "pose" in doc
    assert has_materialiser, "--materialiser absent"
    assert has_pose, "Mot 'pose' absent"
    return (has_materialiser, has_pose)


# ---------- Exécution ----------
run_case("C0", C0)
run_case("F1", F1)
run_case("F2", F2)
run_case("F3", F3)
run_case("R1", R1)
run_case("R2", R2)

print(f"{total_cases} cas, {failed_cases} RATE")
sys.exit(1 if failed_cases > 0 else 0)
