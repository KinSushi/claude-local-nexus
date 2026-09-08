import sys
import subprocess
import tempfile
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent

def _run_tool(rendu: Path, nom: str, cible: Path, extra_args=None):
    if extra_args is None:
        extra_args = []
    cmd = [sys.executable, str(RACINE / 'outillage' / 'nexus_ancres.py'), str(rendu), nom, str(cible)] + extra_args
    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=120,
            encoding='utf-8',
            errors='replace',
            check=False,
        )
    except Exception as e:
        return None, None, 1, str(e)
    return result.stdout, result.stderr, result.returncode, None

def _case_forward():
    _name = "FORWARD"
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        cible = td_path / "cible.txt"
        rendu = td_path / "rendu.jsonl"

        # cible: line indented with 4 spaces
        cible.write_text("    some text\n", encoding='utf-8')

        # rendu: same line indented with 8 spaces, stored as JSONL
        rendu_line = {"line": "        some text"}
        rendu.write_text(f"{rendu_line}\n", encoding='utf-8')

        out, err, rc, exc = _run_tool(rendu, "anchor", cible)
        if exc is not None:
            return False, f"exception {exc}"
        if rc != 0:
            return False, f"return code {rc}"
        if "reparation indentation" not in out:
            return False, "missing 'reparation indentation' in output"
        if "1" not in out:
            return False, "missing indication of 1 repair in output"
        return True, "reparation detected"

def _case_reverse():
    _name = "REVERSE"
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        cible = td_path / "cible.txt"
        rendu = td_path / "rendu.jsonl"

        # cible: same line appears twice
        cible.write_text("duplicate line\nduplicate line\n", encoding='utf-8')

        # rendu: JSONL with the line
        rendu_line = {"line": "duplicate line"}
        rendu.write_text(f"{rendu_line}\n", encoding='utf-8')

        out, err, rc, exc = _run_tool(rendu, "anchor", cible)
        if exc is not None:
            return False, f"exception {exc}"
        if rc == 0:
            return False, "expected non‑zero return code"
        if "AMBIGU" not in out.upper():
            return False, "missing 'AMBIGU' in output"
        return True, "ambiguity correctly detected"

def _case_fuite():
    _name = "FUITE"
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        cible = td_path / "cible.txt"
        rendu = td_path / "rendu.jsonl"

        # reparable content similar to case 1
        cible.write_text("    some text\n", encoding='utf-8')
        rendu_line = {"line": "        some text"}
        rendu.write_text(f"{rendu_line}\n", encoding='utf-8')

        before = rendu.read_bytes()

        # run without '--ecrire' flag
        out, err, rc, exc = _run_tool(rendu, "anchor", cible, extra_args=[])
        if exc is not None:
            return False, f"exception {exc}"
        after = rendu.read_bytes()
        if before != after:
            return False, "file modified despite missing '--ecrire'"
        return True, "file unchanged as expected"

def main():
    cases = [
        ("FORWARD", _case_forward),
        ("REVERSE", _case_reverse),
        ("FUITE", _case_fuite),
    ]
    all_ok = True
    for nom, func in cases:
        try:
            ok, detail = func()
        except Exception as e:
            ok, detail = False, f"exception {e}"
        if ok:
            print(f"[OK  ] {nom} : {detail}")
        else:
            print(f"[RATE] {nom} : {detail}")
            all_ok = False
    sys.exit(0 if all_ok else 1)

if __name__ == "__main__":
    main()