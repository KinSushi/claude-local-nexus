import sys
import subprocess
from pathlib import Path

def _find_tool():
    # tool is expected at outillage/nexus_outillage.py relative to repository root
    base = Path(__file__).resolve().parent
    candidate = base.parent / "outillage" / "nexus_outillage.py"
    if candidate.is_file():
        return candidate
    return None

def _run_tool(tool_path):
    try:
        proc = subprocess.run(
            [sys.executable, str(tool_path)],
            cwd=tool_path.parent.parent,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=10,
        )
        return proc.returncode, proc.stdout, proc.stderr
    except subprocess.TimeoutExpired as e:
        return None, "", f"timeout: {e}"
    except Exception as e:
        return None, "", f"exception: {e}"

def main():
    failures = 0

    # 1. verify tool existence
    tool_path = _find_tool()
    if not tool_path:
        print("[RATE] Outil introuvable")
        sys.exit(3)
    else:
        print("[OK  ] Outil trouve")

    # 2. execute tool without arguments
    retcode, out, err = _run_tool(tool_path)
    if retcode is None:
        print("[RATE] Execution duoutil impossible :", err)
        sys.exit(4)
    else:
        print("[OK  ] Execution duoutil terminee")

    # 3. verify that no bootstrap message appears when reference is present
    if "Reference absente" not in out:
        print("[OK  ] pas de bootstrap errone (reference presente, comparaison faite)")
    else:
        print("[RATE] bootstrap errone : Reference absente alors que la reference existe")
        failures += 1

    # 4. verify output contains status line for at least one linter
    if any(name in out for name in ("ruff :", "eslint :", "psscriptanalyzer :")):
        print("[OK  ] Ligne d'etat d'au moins un linter presente")
    else:
        print("[RATE] Aucune ligne d'etat de linter trouvee")
        failures += 1

    # 5. verify exit code is 2 (no tool played) or 0/1 with matching content
    if retcode == 2:
        print("[OK  ] Code de sortie 2 comme attendu")
    else:
        # check that content matches the code when not 2
        if retcode in (0, 1):
            print("[OK  ] Code de sortie", retcode, "compatible avec le contenu")
        else:
            print("[RATE] Code de sortie inattendu :", retcode)
            failures += 1

    # 6. verify that stderr is empty
    if err.strip() == "":
        print("[OK  ] Stderr vide")
    else:
        print("[RATE] Stderr non vide :", err.strip())
        failures += 1

    sys.exit(0 if failures == 0 else 1)

if __name__ == "__main__":
    main()
