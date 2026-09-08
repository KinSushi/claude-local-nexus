import sys
import subprocess
from pathlib import Path

def _run_tool() -> int:
    # Determine project root and tool path
    root = Path(__file__).resolve().parent.parent
    tool_path = root / "outillage" / "nexus_socle.py"

    # Verify tool existence
    if not tool_path.is_file():
        print(f"[RATE] socle : outil introuvable {tool_path}")
        return 1

    try:
        # Execute the tool
        result = subprocess.run(
            [sys.executable, str(tool_path)],
            cwd=root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=300,
        )
    except subprocess.TimeoutExpired:
        print("[RATE] socle : pas de reponse en 300 s")
        return 1
    except Exception as e:
        # Unexpected error while launching the tool
        print(f"[RATE] socle : erreur d'exécution ({e})")
        return 1

    # Relay relevant lines and detect presence
    has_output = False
    for line in result.stdout.splitlines():
        if line.startswith("[OK  ]") or line.startswith("[RATE]"):
            print(line)
            has_output = True

    if not has_output:
        print("[RATE] socle : aucun cas rendu")
        return 1

    return result.returncode


if __name__ == "__main__":
    sys.exit(_run_tool())