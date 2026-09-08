import sys
from pathlib import Path

# ----------------------------------------------------------------------
# Configuration
# ----------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent
VITRINE_PATH = ROOT / "outillage" / "nexus_vitrine.py"

# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------
def print_result(ok: bool, name: str, detail: str) -> None:
    """Print a result line respecting the contract."""
    prefix = "[OK  ]" if ok else "[RATE]"
    print(f"{prefix} {name} : {detail}")

def load_source(path: Path) -> str | None:
    """Return the file content as a string, or None if the file does not exist."""
    if not path.is_file():
        return None
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return None

def find_cable_line(source: str) -> str | None:
    """Return the first line that contains 'nexus_test.py', or None."""
    for line in source.splitlines():
        if "nexus_test.py" in line:
            return line
    return None

def cable_in_controles(source: str) -> bool:
    """
    Return True if the word 'cable' appears inside the dictionary
    CONTROLES = { … } (i.e. between the opening line and the matching
    closing line that contains only '}').
    """
    lines = source.splitlines()
    start_idx = None
    for i, line in enumerate(lines):
        if "CONTROLES = {" in line:
            start_idx = i
            break
    if start_idx is None:
        return False

    # Search for the closing brace at the same indentation level
    for j in range(start_idx + 1, len(lines)):
        if lines[j].strip() == "}":
            block = lines[start_idx + 1 : j]  # exclude opening and closing lines
            return any("nexus_test.py" in l for l in block)
    return False

# ----------------------------------------------------------------------
# Main logic
# ----------------------------------------------------------------------
def main() -> int:
    source = load_source(VITRINE_PATH)
    if source is None:
        print_result(
            False,
            "vitrine",
            f"introuvable {VITRINE_PATH}",
        )
        return 1

    # 1. cable : presence of 'nexus_test.py'
    has_cable = "nexus_test.py" in source
    if has_cable:
        print_result(True, "cable", "trouvé")
    else:
        print_result(
            False,
            "cable",
            "la porte de publication ne joue plus la suite",
        )

    # 2. dans les controles : 'cable' must be inside CONTROLES dict
    in_controles = cable_in_controles(source)
    if in_controles:
        print_result(True, "dans les controles", "présent dans CONTROLES")
    else:
        print_result(
            False,
            "dans les controles",
            "absent du dictionnaire CONTROLES",
        )

    # 3. avertit sans bloquer : line with nexus_test.py must contain AVERTISSENT
    cable_line = find_cable_line(source)
    if cable_line is not None and "AVERTISSENT" in cable_line:
        print_result(True, "avertit sans bloquer", "type AVERTISSENT")
    else:
        detail = (
            "ligne manquante ou type BLOQUENT"
            if cable_line is not None
            else "ligne nexus_test.py introuvable"
        )
        print_result(False, "avertit sans bloquer", detail)

    # Determine exit code
    all_ok = has_cable and in_controles and (cable_line is not None and "AVERTISSENT" in cable_line)
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())