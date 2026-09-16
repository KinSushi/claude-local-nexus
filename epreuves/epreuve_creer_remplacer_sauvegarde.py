import os
import sys
import subprocess
import tempfile
import json
from pathlib import Path

# Configuration d'environnement avant tout import supplémentaire
os.environ["NEXUS_GATEWAY"] = "http://127.0.0.1:9"
_NEXUS_ETAT_DISJONCTEUR_DIR = tempfile.TemporaryDirectory()
os.environ["NEXUS_ETAT_DISJONCTEUR"] = _NEXUS_ETAT_DISJONCTEUR_DIR.name

# Variables globales de comptage
total_cases = 0
failed_cases = 0

def _run_case(name: str, func):
    global total_cases, failed_cases
    total_cases += 1
    try:
        result = func()
        print(f"[OK  ] {name} : {result!r}")
    except Exception as e:
        failed_cases += 1
        print(f"[RATE] {name} : {type(e).__name__}: {e}")

def _script_path() -> Path:
    return Path(__file__).resolve().parents[1] / "scripts" / "nexus_creer.py"

def _racine() -> Path:
    return Path(__file__).resolve().parents[1]

def _dossier_travail() -> Path:
    """Un dossier temporaire SOUS la racine du depot.

    Mesure du 2026-09-16 : nexus_creer refuse tout chemin hors du depot
    (« REFUS : chemin refuse ... hors racine du depot detectee »), et c'est
    la bonne garde. L'epreuve travaille donc sous .nexus/, ignore par git.
    """
    parent = _racine() / ".nexus" / "epreuve_sauvegarde"
    parent.mkdir(parents=True, exist_ok=True)
    return Path(tempfile.mkdtemp(dir=str(parent)))

def _execute(script: Path, args: list):
    cmd = [sys.executable, str(script)] + args
    r = subprocess.run(cmd, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    if r.returncode != 0:
        motif = (r.stdout or "") + (r.stderr or "")
        raise AssertionError("nexus_creer a refuse (code %d) : %s"
                             % (r.returncode, motif.strip().splitlines()[0] if motif.strip() else "aucun motif"))

def _prepare_jsonl(dir_path: Path, nom: str, texte: str) -> Path:
    """Ecrit le lot rendu attendu par nexus_creer.

    Mesure du 2026-09-16 : le champ texte doit porter le contenu ENCADRE par
    les marqueurs, chacun seul sur sa ligne. Le contenu nu est refuse, et ce
    refus est juste.
    """
    jsonl_path = dir_path / "input.jsonl"
    encadre = "<<<CREER>>>\n" + texte.rstrip("\n") + "\n<<<FIN>>>"
    with jsonl_path.open("w", encoding="utf-8") as f:
        json.dump({"nom": nom, "texte": encadre}, f)
        f.write("\n")
    return jsonl_path

# ----------------------------------------------------------------------
# Cas C0
def case_C0():
    script = _script_path()
    assert script.is_file(), "scripts/nexus_creer.py n'existe pas"
    return script.stat().st_size

# ----------------------------------------------------------------------
# Cas F1
def case_F1():
    work_dir = _dossier_travail()

    cible = work_dir / "cible.txt"
    cible.write_text("ancien\n", encoding="utf-8")

    jsonl = _prepare_jsonl(work_dir, "test", "neuf\n")
    script = _script_path()
    _execute(script, ["--remplacer", str(jsonl), "test", str(cible)])

    new_content = cible.read_text(encoding="utf-8")
    backup = Path(str(cible) + ".avant-remplacement")
    backup_exists = backup.is_file()

    assert new_content == "neuf\n", "Le contenu de la cible n'est pas mis à jour"
    assert backup_exists, "Le fichier de sauvegarde n'existe pas"

    return (new_content, backup_exists)

# ----------------------------------------------------------------------
# Cas F2
def case_F2():
    work_dir = _dossier_travail()

    cible = work_dir / "cible.txt"
    cible.write_text("ancien\n", encoding="utf-8")

    jsonl = _prepare_jsonl(work_dir, "test", "neuf\n")
    script = _script_path()
    _execute(script, ["--remplacer", str(jsonl), "test", str(cible)])

    backup = Path(str(cible) + ".avant-remplacement")
    assert backup.is_file(), "La sauvegarde n'a pas été créée"

    backup_content = backup.read_text(encoding="utf-8")
    assert backup_content == "ancien\n", "Le contenu de la sauvegarde n'est pas l'ancien texte"

    return backup_content

# ----------------------------------------------------------------------
# Cas F3
def case_F3():
    work_dir = _dossier_travail()

    cible = work_dir / "cible.txt"
    cible.write_text("ancien\n", encoding="utf-8")

    jsonl = _prepare_jsonl(work_dir, "test", "neuf\n")
    script = _script_path()
    _execute(script, ["--remplacer", str(jsonl), "test", str(cible)])

    backups = list(work_dir.glob("*.avant-remplacement"))
    count = len(backups)
    assert count == 1, f"Nombre de sauvegardes attendu 1, trouvé {count}"
    return count

# ----------------------------------------------------------------------
# Cas R1
def case_R1():
    work_dir = _dossier_travail()

    cible = work_dir / "cible_absente.txt"  # aucune création préalable

    jsonl = _prepare_jsonl(work_dir, "test", "neuf\n")
    script = _script_path()
    # appel sans l'option --remplacer
    _execute(script, [str(jsonl), "test", str(cible)])

    backups = list(work_dir.glob("*.avant-remplacement"))
    count = len(backups)
    assert count == 0, f"Aucun fichier de sauvegarde ne doit être créé, trouvé {count}"
    return count

# ----------------------------------------------------------------------
# Cas L1
def case_L1():
    val = os.getenv("NEXUS_GATEWAY")
    assert val == "http://127.0.0.1:9", f"NEXUS_GATEWAY vaut {val!r} au lieu de 'http://127.0.0.1:9'"
    return val

# ----------------------------------------------------------------------
if __name__ == "__main__":
    _run_case("C0", case_C0)
    _run_case("F1", case_F1)
    _run_case("F2", case_F2)
    _run_case("F3", case_F3)
    _run_case("R1", case_R1)
    _run_case("L1", case_L1)

    print(f"{total_cases} cas, {failed_cases} RATE")
    sys.exit(1 if failed_cases > 0 else 0)
