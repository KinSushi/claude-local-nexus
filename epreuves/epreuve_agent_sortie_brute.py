#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import subprocess
import tempfile
from pathlib import Path

def _run_agent(script_path: Path, jsonl: Path, nom: str, sortie: Path, brute_ajout: bool, env: dict):
    cmd = [
        sys.executable,
        str(script_path),
        "--depuis-jsonl", str(jsonl),
        "--nom", nom,
        "--sortie-brute", str(sortie),
    ]
    if brute_ajout:
        cmd.append("--brute-ajout")
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        timeout=120,
    )

def _file_info(path: Path):
    if not path.is_file():
        return 0, []
    size = path.stat().st_size
    with path.open(encoding="utf-8") as f:
        lines = [ln.rstrip("\n") for ln in f if ln.rstrip("\n")]
    return size, lines

def _check_option_present(script_path: Path):
    try:
        content = script_path.read_text(encoding="utf-8")
        return "--brute-ajout" in content
    except Exception:
        return False

def main():
    root = Path(__file__).resolve().parents[1]
    script = root / "scripts" / "nexus_agent.py"

    total = 0
    failures = 0

    # C0 – vérification de la présence de l'option
    total += 1
    if _check_option_present(script):
        print("[OK  ] C0 : option --brute-ajout presente dans le source")
    else:
        print("[RATE] C0 : option absente du source")
        failures += 1

    env = os.environ.copy()
    env["NEXUS_GATEWAY"] = "http://127.0.0.1:9"
    # le fichier d'état sera créé dans le répertoire temporaire
    with tempfile.TemporaryDirectory() as td:
        tmpdir = Path(td)
        env["NEXUS_ETAT_DISJONCTEUR"] = str(tmpdir / "etat.txt")

        jsonl = tmpdir / "data.jsonl"
        jsonl.write_text('{"nom": "t1", "texte": "print(\'un\')\\n"}\n', encoding="utf-8")

        sortie = tmpdir / "out.txt"

        # F1 – première écriture
        total += 1
        try:
            res = _run_agent(script, jsonl, "t1", sortie, False, env)
            size, lines = _file_info(sortie)
            ok = res.returncode == 0 and size > 0 and len(lines) == 1 and lines[0] == "print('un')"
            print("[%s] F1 : code=%s, %d ligne(s), %d octets" % ("OK  " if ok else "RATE", res.returncode, len(lines), size))
            if not ok:
                failures += 1
        except Exception as exc:
            print("[RATE] F1 : %s %s" % (type(exc).__name__, exc))
            failures += 1

        # R1 – refus sans --brute-ajout
        total += 1
        try:
            before_size, _ = _file_info(sortie)
            res = _run_agent(script, jsonl, "t1", sortie, False, env)
            after_size, _ = _file_info(sortie)
            ok = (res.returncode == 3 and "refus" in (res.stderr or "").lower()
                  and str(sortie) in (res.stderr or "") and before_size == after_size)
            premiere = (res.stderr or "").strip().splitlines()[0][:90] if (res.stderr or "").strip() else "stderr vide"
            print("[%s] R1 : code=%s, %d -> %d octets, %s" % ("OK  " if ok else "RATE", res.returncode, before_size, after_size, premiere))
            if not ok:
                failures += 1
        except Exception as exc:
            print("[RATE] R1 : %s %s" % (type(exc).__name__, exc))
            failures += 1

        # F2 – ajout avec --brute-ajout
        total += 1
        try:
            res = _run_agent(script, jsonl, "t1", sortie, True, env)
            size, lines = _file_info(sortie)
            ok = res.returncode == 0 and len(lines) == 2
            print("[%s] F2 : code=%s, %d ligne(s) apres ajout assume" % ("OK  " if ok else "RATE", res.returncode, len(lines)))
            if not ok:
                failures += 1
        except Exception as exc:
            print("[RATE] F2 : %s %s" % (type(exc).__name__, exc))
            failures += 1

        # R2 – fichier vide autorise l'écriture
        total += 1
        try:
            empty_path = tmpdir / "vide.txt"
            empty_path.touch()
            res = _run_agent(script, jsonl, "t1", empty_path, False, env)
            size, lines = _file_info(empty_path)
            ok = res.returncode == 0 and len(lines) == 1
            print("[%s] R2 : code=%s, %d ligne(s) sur fichier vide" % ("OK  " if ok else "RATE", res.returncode, len(lines)))
            if not ok:
                failures += 1
        except Exception as exc:
            print("[RATE] R2 : %s %s" % (type(exc).__name__, exc))
            failures += 1

    print(f"{total} cas, {failures} RATE")
    sys.exit(1 if failures else 0)

if __name__ == "__main__":
    main()
