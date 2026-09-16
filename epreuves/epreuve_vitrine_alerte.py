import os, sys, tempfile, importlib.util
from pathlib import Path

# --- Environnement de test ----------------------------------------------------
os.environ["NEXUS_GATEWAY"] = "http://127.0.0.1:9"
_TEMP_DIR = tempfile.TemporaryDirectory()
os.environ["NEXUS_ETAT_DISJONCTEUR"] = _TEMP_DIR.name

# --- Chargement du module à tester -------------------------------------------
_module_path = Path(__file__).resolve().parents[1] / "scripts" / "nexus_conformite.py"
_spec = importlib.util.spec_from_file_location("nexus_conformite", _module_path)
module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(module)

# --- Infrastructure de l'épreuve --------------------------------------------
total_cases = 0
failed_cases = 0


def run_case(nom, fonction):
    global total_cases, failed_cases
    total_cases += 1
    try:
        resultat = fonction()
        print(f"[OK  ] {nom} : {resultat!r}")
    except Exception as e:
        failed_cases += 1
        print(f"[RATE] {nom} : {type(e).__name__}: {e}")


# --- Cas de test -------------------------------------------------------------

def C0():
    if not hasattr(module, "etat_journal_vitrine"):
        raise AssertionError("fonction etat_journal_vitrine absente du module")
    return "presente"


def F1():
    texte = "\n".join(
        [
            "=== passage 1 ===",
            "=== passage 2 ===",
            "VERDICT : vitrine publiee",
            "=== passage 3 ===",
        ]
    )
    return module.etat_journal_vitrine(texte)


def F2():
    texte = "\n".join(
        [
            "=== passage unique ===",
            "VERDICT : vitrine publiee",
        ]
    )
    return module.etat_journal_vitrine(texte)


def R1():
    texte = "\n".join(
        [
            "=== p1 ===",
            "=== p2 ===",
            "=== p3 ===",
            "=== p4 ===",
        ]
    )
    return module.etat_journal_vitrine(texte)


def R2():
    vide = module.etat_journal_vitrine("")
    nul = module.etat_journal_vitrine(None)
    return (vide, nul)


def R3():
    texte = "\n".join(
        [
            "   === p1 ===   ",
            "VERDICT : vitrine publiee   ",
            "   === p2 ===",
            " VERDICT : publication REFUSEE. Rien n est parti. ",
        ]
    )
    return module.etat_journal_vitrine(texte)


def L1():
    # Vérifier l'existence de ROOT
    if not hasattr(module, "ROOT"):
        raise AssertionError("module.ROOT manquant")
    # Mesurer le nombre d'entrées dans le répertoire temporaire avant/après appel
    avant = set(os.listdir(_TEMP_DIR.name))
    # Appel de la fonction (pure)
    module.etat_journal_vitrine("")
    apres = set(os.listdir(_TEMP_DIR.name))
    return len(apres - avant)


# --- Exécution des cas -------------------------------------------------------
run_case("C0", C0)
run_case("F1", F1)
run_case("F2", F2)
run_case("R1", R1)
run_case("R2", R2)
run_case("R3", R3)
run_case("L1", L1)

print(f"{total_cases} cas, {failed_cases} RATE")
sys.exit(1 if failed_cases > 0 else 0)
