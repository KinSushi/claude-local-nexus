import os
import sys
import hashlib
import importlib.util
import tempfile
from pathlib import Path

# ----------------------------------------------------------------------
# Pré‑configuration de l’environnement
# ----------------------------------------------------------------------
os.environ["NEXUS_GATEWAY"] = "http://127.0.0.1:9"
temp_dir = tempfile.TemporaryDirectory()
os.environ["NEXUS_ETAT_DISJONCTEUR"] = temp_dir.name

# ----------------------------------------------------------------------
# Chargement du module à tester
# ----------------------------------------------------------------------
racine = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "_epreuve_materialiser", racine / "scripts" / "nexus_agent.py"
)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)

# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------
def sha256_trunc(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()[:16]

def run_case(name, func):
    global total_cases, failed_cases
    total_cases += 1
    try:
        observed = func()
        print(f"[OK  ] {name} : {observed!r}")
    except Exception as e:
        failed_cases += 1
        print(f"[RATE] {name} : {type(e).__name__}: {e}")

# ----------------------------------------------------------------------
# Cas de test
# ----------------------------------------------------------------------
total_cases = 0
failed_cases = 0

# C0 – présence de la fonction
def case_C0():
    if not hasattr(module, "materialiser_rendu"):
        raise AssertionError("fonction absente")
    return "présente"

# F1 – écriture simple
def case_F1():
    with tempfile.TemporaryDirectory() as d:
        dossier = Path(d)
        result = module.materialiser_rendu(dossier, "t1", "print('un')\n", set())
        if not isinstance(result, tuple) or len(result) != 2:
            raise AssertionError("retour inattendu")
        chemin, empreinte = result
        if chemin is None or empreinte is None:
            raise AssertionError("échec d’écriture")
        chemin = Path(chemin)
        if not chemin.is_file():
            raise AssertionError("fichier non créé")
        contenu = chemin.read_bytes()
        if contenu != b"print('un')\n":
            raise AssertionError("contenu incorrect")
        attendu = sha256_trunc(contenu)
        if empreinte != attendu:
            raise AssertionError(f"empreinte {empreinte} ≠ {attendu}")
        return (chemin, empreinte)

# F2 – suppression des balises markdown
def case_F2():
    with tempfile.TemporaryDirectory() as d:
        dossier = Path(d)
        texte = "```python\nprint('deux')\n```"
        result = module.materialiser_rendu(dossier, "t2", texte, set())
        chemin, _ = result
        chemin = Path(chemin)
        if not chemin.is_file():
            raise AssertionError("fichier non créé")
        contenu = chemin.read_text(encoding="utf-8")
        if "```" in contenu or contenu.lstrip().startswith("python"):
            raise AssertionError("balises non retirées")
        if "print('deux')" not in contenu:
            raise AssertionError("corps manquant")
        return contenu

# F3 – fins de ligne LF uniquement
def case_F3():
    with tempfile.TemporaryDirectory() as d:
        dossier = Path(d)
        texte = "a\nb\n"
        result = module.materialiser_rendu(dossier, "t3", texte, set())
        chemin, _ = result
        chemin = Path(chemin)
        data = chemin.read_bytes()
        if b"\r\n" in data:
            raise AssertionError("présence de CRLF")
        return data

# R1 – doublon détecté
def case_R1():
    with tempfile.TemporaryDirectory() as d:
        dossier = Path(d) / "nouveau_dossier"
        result = module.materialiser_rendu(dossier, "t1", "x", {"t1"})
        if result != (None, "doublon"):
            raise AssertionError(f"résultat inattendu {result}")
        if dossier.exists():
            raise AssertionError("dossier créé malgré doublon")
        return result

# R2 – erreur d’écriture (dossier est un fichier)
def case_R2():
    with tempfile.NamedTemporaryFile(delete=False) as f:
        f_path = Path(f.name)
    try:
        result = module.materialiser_rendu(f_path, "tX", "y", set())
        if not (isinstance(result, tuple) and result[0] is None and isinstance(result[1], str) and result[1]):
            raise AssertionError(f"résultat inattendu {result}")
        return result
    finally:
        f_path.unlink(missing_ok=True)

# R3 – mise à jour de l’ensemble passé
def case_R3():
    with tempfile.TemporaryDirectory() as d:
        dossier = Path(d)
        vus = set()
        module.materialiser_rendu(dossier, "t4", "z", vus)
        if "t4" not in vus:
            raise AssertionError("nom absent de l’ensemble")
        return vus

# L1 – vérification de la passerelle
def case_L1():
    if getattr(module, "PASSERELLE", None) != "http://127.0.0.1:9":
        raise AssertionError("PASSERELLE incorrecte")
    return module.PASSERELLE

# ----------------------------------------------------------------------
# Exécution des cas
# ----------------------------------------------------------------------
run_case("C0", case_C0)
run_case("F1", case_F1)
run_case("F2", case_F2)
run_case("F3", case_F3)
run_case("R1", case_R1)
run_case("R2", case_R2)
run_case("R3", case_R3)
run_case("L1", case_L1)

# ----------------------------------------------------------------------
# Résumé
# ----------------------------------------------------------------------
print(f"{total_cases} cas, {failed_cases} RATE")
sys.exit(1 if failed_cases > 0 else 0)
