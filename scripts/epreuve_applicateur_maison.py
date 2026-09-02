"""epreuve_applicateur_maison.py

Cette epreuve protege le depot contre les scripts maison qui
appliquent des patches sans passer par l'outil officiel
scripts/nexus_appliquer.py. Elle detecte les fichiers .py du
repertoire scripts qui contiennent a la fois le marqueur de
patch <<<AVANT>>> et un appel d'ecriture sur disque (write_text ou
write). Les fichiers exclus de la verification sont :
- nexus_appliquer.py (outil officiel)
- ce fichier lui-meme
- tout fichier dont le nom commence par "epreuve"

Ce script ne regarde que les fichiers du repertoire scripts du
depot. Il ne detecte pas les scripts hors du depot. Aucun code
n'est execute a l'import.

"""

import sys
import os
from pathlib import Path
import tempfile

MARKER = "<<<AVANT>>>"
WRITE_KEYWORDS = ("write_text(", ".write(")


def is_faulty(file_path: Path) -> bool:
    """Return True if file contains both the marker and a write call."""
    try:
        content = file_path.read_text(encoding="utf-8")
    except Exception:
        return False
    has_marker = MARKER in content
    has_write = any(kw in content for kw in WRITE_KEYWORDS)
    return has_marker and has_write


def collect_faulty_scripts(base_dir: Path) -> list[Path]:
    """Collect faulty script files in base_dir, applying exemptions."""
    faulty = []
    for py_file in base_dir.rglob("*.py"):
        name = py_file.name
        # Exemptions
        if name == "nexus_appliquer.py":
            continue  # official tool
        if name == "epreuve_applicateur_maison.py":
            continue  # this test file
        if name.startswith("epreuve"):
            continue  # other test files
        if is_faulty(py_file):
            faulty.append(py_file)
    return faulty


def run_self_test(base_dir: Path) -> bool:
    """Create temporary test files to verify detection logic."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)

        # File with both marker and write -> should be detected
        file_both = tmp_path / "test_both.py"
        file_both.write_text(f"{MARKER}\nPath('out.txt').write_text('data')\n")

        # File with only marker -> should NOT be detected
        file_marker_only = tmp_path / "test_marker.py"
        file_marker_only.write_text(f"{MARKER}\nprint('no write')\n")

        # Run detection on the temporary directory
        detected = collect_faulty_scripts(tmp_path)

        # Check expectations
        if file_both not in detected:
            print("Echec du test: fichier contenant le marqueur et l'ecriture n'a pas ete detecte.")
            return False
        if file_marker_only in detected:
            print("Echec du test: fichier ne contenant qu'un seul signe a ete detecte comme fautif.")
            return False
    return True


def main() -> None:
    repo_root = Path(__file__).resolve().parent
    if not run_self_test(repo_root):
        sys.exit(1)

    faulty_files = collect_faulty_scripts(repo_root)

    if faulty_files:
        for f in faulty_files:
            rel = f.relative_to(repo_root)
            print(f"Fichier fautif: {rel}")
        print("Verdict: fichiers fautifs trouves.")
        sys.exit(1)
    else:
        print("Verdict: aucun fichier fautif.")
        sys.exit(0)


if __name__ == "__main__":
    main()