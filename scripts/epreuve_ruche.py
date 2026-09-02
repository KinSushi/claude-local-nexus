#!/usr/bin/env python3
import sys
import tempfile
import subprocess
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
NEXUS_RUCHE = SCRIPT_DIR / "nexus_ruche.py"
TIMEOUT = 10

def verifier_script_existe():
    if not NEXUS_RUCHE.is_file():
        print(f"[ERREUR] Script introuvable: {NEXUS_RUCHE}")
        return False
    return True

def lancer_ruche(args, input_text=None):
    cmd = [sys.executable, str(NEXUS_RUCHE)] + args
    try:
        proc = subprocess.run(
            cmd,
            input=input_text,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=TIMEOUT,
            check=False
        )
        return proc.returncode, proc.stdout, proc.stderr
    except subprocess.TimeoutExpired:
        return -1, "", f"Timeout apres {TIMEOUT}s"

def cas_nominal():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        test_file = tmp_path / "test.py"
        test_file.write_text("# Test\n" * 30, encoding="utf-8")

        code, out, err = lancer_ruche([
            "--racine", str(tmp_path),
            "--simuler",
            "--plans", "local"
        ])

        if code != 0:
            print(f"[NOMINAL] Echec code={code} err={err}")
            return False
        if "Simuler essaim sur 1 cible(s)" not in out:
            print(f"[NOMINAL] Sortie inattendue: {out}")
            return False
    print("[NOMINAL] OK")
    return True

def cas_inverse():
    code, out, err = lancer_ruche(["--racine", "/inexistant"])
    if code == 0:
        print("[INVERSE] Devrait echouer")
        return False
    if "Aucune cible a traiter" not in out:
        print(f"[INVERSE] Message inattendu: {out}")
        return False
    print("[INVERSE] OK")
    return True

def cas_malforme():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        test_file = tmp_path / "test.py"
        test_file.write_text("trop court", encoding="utf-8")

        code, out, err = lancer_ruche([
            "--racine", str(tmp_path),
            "--simuler"
        ])

        if code != 0:
            print(f"[MALFORME] Devrait reussir code={code}")
            return False
        if "0 cibles decouvertes" not in out:
            print(f"[MALFORME] Sortie inattendue: {out}")
            return False
    print("[MALFORME] OK")
    return True

def cas_usage():
    code, out, err = lancer_ruche([])
    if code == 0:
        print("[USAGE] Devrait echouer")
        return False
    if "usage:" not in err.lower():
        print(f"[USAGE] Message d'usage manquant: {err}")
        return False
    print("[USAGE] OK")
    return True

def main():
    if not verifier_script_existe():
        return 2

    cas = [
        ("NOMINAL", cas_nominal),
        ("INVERSE", cas_inverse),
        ("MALFORME", cas_malforme),
        ("USAGE", cas_usage)
    ]

    codes = []
    for nom, func in cas:
        try:
            if not func():
                codes.append(1)
            else:
                codes.append(0)
        except Exception as e:
            print(f"[{nom}] Exception: {str(e)}")
            codes.append(1)

    if any(codes):
        return 1
    return 0

if __name__ == "__main__":
    sys.exit(main())
