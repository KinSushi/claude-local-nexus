import os, sys, tempfile, importlib.util
from pathlib import Path

# Configuration d'environnement pour éviter tout appel réel
os.environ["NEXUS_GATEWAY"] = "http://127.0.0.1:9"
_NEXUS_ETAT_DISJONCTEUR_DIR = tempfile.TemporaryDirectory()
os.environ["NEXUS_ETAT_DISJONCTEUR"] = _NEXUS_ETAT_DISJONCTEUR_DIR.name

# Chargement du module à tester
_spec = importlib.util.spec_from_file_location(
    "nexus_vitrine",
    Path(__file__).resolve().parents[1] / "outillage" / "nexus_vitrine.py",
)
nexus_vitrine = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(nexus_vitrine)

# Utilitaire de création d'une fausse racine contenant scripts/nexus_charge.py
def fabriquer_racine(dossier: Path, corps: str) -> Path:
    scripts_dir = dossier / "scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)
    (scripts_dir / "nexus_charge.py").write_text(corps, encoding="utf-8")
    return dossier

# Compteurs et exécuteur de cas
total_cases = 0
failed_cases = 0

def run_case(nom, fonction):
    global total_cases, failed_cases
    total_cases += 1
    try:
        resultat = fonction()
        print(f"[OK  ] {nom} : {resultat!r}")
    except AssertionError as e:
        failed_cases += 1
        print(f"[RATE] {nom} : {type(e).__name__}: {e}")
    except Exception as e:
        failed_cases += 1
        print(f"[RATE] {nom} : {type(e).__name__}: {e}")

# ----------------------------------------------------------------------
# Cas de test
# ----------------------------------------------------------------------
def C0():
    # Vérifier la présence de la fonction et du seuil
    assert hasattr(nexus_vitrine, "machine_libre"), "machine_libre manquant"
    assert hasattr(nexus_vitrine, "SEUIL_ENGAGEMENT_PCT"), "SEUIL_ENGAGEMENT_PCT manquant"
    assert nexus_vitrine.SEUIL_ENGAGEMENT_PCT == 90.0, f"Seuil attendu 90.0, trouvé {nexus_vitrine.SEUIL_ENGAGEMENT_PCT}"
    return nexus_vitrine.SEUIL_ENGAGEMENT_PCT

def F1():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        code = (
            "import json, sys\n"
            "print(json.dumps({\"engagement_pct\": 50.0}))\n"
            "sys.exit(0)\n"
        )
        fabriquer_racine(root, code)
        statut, msg = nexus_vitrine.machine_libre(root)
        assert statut == nexus_vitrine.OK, f"Statut attendu OK, obtenu {statut}"
        return (statut, msg)

def F2():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        code = (
            "import json, sys\n"
            "print(json.dumps({\"engagement_pct\": 95.0}))\n"
            "sys.exit(0)\n"
        )
        fabriquer_racine(root, code)
        statut, msg = nexus_vitrine.machine_libre(root)
        assert statut == nexus_vitrine.BLOQUE, f"Statut attendu BLOQUE, obtenu {statut}"
        assert "95" in msg, f"Message attendu contenant '95', obtenu {msg}"
        return (statut, msg)

def F3():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        code = (
            "import json, sys\n"
            "print(json.dumps({\"engagement_pct\": 50.0}))\n"
            "sys.exit(1)\n"
        )
        fabriquer_racine(root, code)
        statut, msg = nexus_vitrine.machine_libre(root)
        assert statut == nexus_vitrine.OK, f"Statut attendu OK malgré code 1, obtenu {statut}"
        return (statut, msg)

def R1():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)  # Aucun script/nexus_charge.py
        statut, msg = nexus_vitrine.machine_libre(root)
        assert statut == nexus_vitrine.OK, f"Statut attendu OK, obtenu {statut}"
        assert "absent" in msg.lower(), f"Message attendu contenant 'absent', obtenu {msg}"
        return (statut, msg)

def R2():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        code = (
            "import sys\n"
            "print('not a json')\n"
            "sys.exit(0)\n"
        )
        fabriquer_racine(root, code)
        statut, msg = nexus_vitrine.machine_libre(root)
        assert statut == nexus_vitrine.OK, f"Statut attendu OK, obtenu {statut}"
        assert "non mesurable" in msg.lower(), f"Message attendu contenant 'non mesurable', obtenu {msg}"
        return (statut, msg)

def R3():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        code = (
            "import json, sys\n"
            "print(json.dumps({\"autre_champ\": 123}))\n"
            "sys.exit(0)\n"
        )
        fabriquer_racine(root, code)
        statut, msg = nexus_vitrine.machine_libre(root)
        assert statut == nexus_vitrine.OK, f"Statut attendu OK, obtenu {statut}"
        assert "non mesurable" in msg.lower(), f"Message attendu contenant 'non mesurable', obtenu {msg}"
        return (statut, msg)

def L1():
    val = os.getenv("NEXUS_GATEWAY")
    assert val == "http://127.0.0.1:9", f"NEXUS_GATEWAY attendu 'http://127.0.0.1:9', obtenu {val}"
    return val

# ----------------------------------------------------------------------
# Exécution des cas
# ----------------------------------------------------------------------
run_case("C0", C0)
run_case("F1", F1)
run_case("F2", F2)
run_case("F3", F3)
run_case("R1", R1)
run_case("R2", R2)
run_case("R3", R3)
run_case("L1", L1)

print(f"{total_cases} cas, {failed_cases} RATE")
sys.exit(1 if failed_cases > 0 else 0)
