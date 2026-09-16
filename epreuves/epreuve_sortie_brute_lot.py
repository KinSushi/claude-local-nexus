import os, sys, tempfile, importlib.util
from pathlib import Path

# --- Préparer l'environnement avant l'import du module ---
os.environ["NEXUS_GATEWAY"] = "http://127.0.0.1:9"
# dossier temporaire pour NEXUS_ETAT_DISJONCTEUR : garde en vie par la variable
_state_tmp = tempfile.TemporaryDirectory()
os.environ["NEXUS_ETAT_DISJONCTEUR"] = _state_tmp.name

# --- Charger le module nexus_agent ---
script_path = Path(__file__).resolve().parents[1] / "scripts" / "nexus_agent.py"
spec = importlib.util.spec_from_file_location("nexus_agent", script_path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

# --- Compteurs et fonction d'exécution des cas ---
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

# --- Cas C0 : présence de la fonction ---
def case_C0():
    assert hasattr(module, "ouvrir_sortie_brute"), "fonction manquante"
    return "presente"
run_case("C0", case_C0)

# --- Cas F1 : chemin inexistant, ajout=False ---
def case_F1():
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "fichier.txt"
        flux, renomme = module.ouvrir_sortie_brute(str(p), False)
        assert flux is not None, "flux est None"
        assert renomme is None, "renomme devrait être None"
        flux.write("un\n")
        flux.close()
        data = p.read_bytes()
        assert data == b"un\n", f"contenu inattendu {data}"
        assert b"\r\n" not in data, "présence de CRLF"
        return data
run_case("F1", case_F1)

# --- Cas F2 : fichier existant, ajout=False (renommage) ---
def case_F2():
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "fichier.txt"
        p.write_text("ancien\n", encoding="utf-8")
        flux, renomme = module.ouvrir_sortie_brute(str(p), False)
        assert renomme is not None, "renomme devrait être non None"
        renamed_path = Path(renomme)
        assert renamed_path.is_file(), "fichier renommé introuvable"
        assert renamed_path.read_text(encoding="utf-8") == "ancien\n", "contenu du renommé incorrect"
        assert p.stat().st_size == 0, "fichier original devrait être vide"
        flux.write("neuf\n")
        flux.close()
        assert p.read_text(encoding="utf-8") == "neuf\n", "contenu final incorrect"
        return renamed_path.name
run_case("F2", case_F2)

# --- Cas F3 : fichier existant, ajout=True (append) ---
def case_F3():
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "fichier.txt"
        p.write_text("ancien\n", encoding="utf-8")
        flux, renomme = module.ouvrir_sortie_brute(str(p), True)
        assert renomme is None, "renomme devrait être None en mode ajout"
        # aucun fichier supplémentaire ne doit exister
        files = list(Path(td).iterdir())
        assert len(files) == 1 and files[0] == p, "fichier supplémentaire créé"
        flux.write("suite\n")
        flux.close()
        contenu = p.read_text(encoding="utf-8")
        assert contenu == "ancien\nsuite\n", f"contenu inattendu {contenu!r}"
        return contenu
run_case("F3", case_F3)

# --- Cas R1 : fichier vide, ajout=False ---
def case_R1():
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "vide.txt"
        p.touch()
        flux, renomme = module.ouvrir_sortie_brute(str(p), False)
        assert renomme is None, "renomme doit être None pour fichier vide"
        flux.close()
        return renomme
run_case("R1", case_R1)

# --- Cas R2 : parent est un fichier, pas un dossier ---
def case_R2():
    with tempfile.TemporaryDirectory() as td:
        parent_file = Path(td) / "parent.txt"
        parent_file.write_text("je suis un fichier", encoding="utf-8")
        child_path = parent_file / "enfant.txt"  # parent_file est un fichier
        flux, motif = module.ouvrir_sortie_brute(str(child_path), False)
        assert flux is None, "flux doit être None en cas d'erreur"
        assert isinstance(motif, str) and motif, "motif doit être une chaîne non vide"
        return (flux, motif)
run_case("R2", case_R2)

# --- Cas L1 : vérification de la passerelle ---
def case_L1():
    passerelle = getattr(module, "PASSERELLE", None)
    assert passerelle == "http://127.0.0.1:9", f"passerelle non isolee : {passerelle!r}"
    return passerelle
run_case("L1", case_L1)

# --- Résumé et sortie ---
print(f"{total_cases} cas, {failed_cases} RATE")
sys.exit(1 if failed_cases > 0 else 0)
