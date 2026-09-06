#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import pathlib
import subprocess
import sys
import tempfile

def verifier_fichier_outil():
    script_dir = pathlib.Path(__file__).resolve().parent
    outil_path = script_dir / "nexus_relais.py"
    if not outil_path.is_file():
        print(f"[ERREUR] Fichier de l'outil introuvable : {outil_path}")
        sys.exit(3)
    return outil_path

def lancer_processus(cmd, input_text=None):
    try:
        result = subprocess.run(
            cmd,
            input=input_text,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            encoding="utf-8",
            errors="replace",
            timeout=10
        )
        return result.returncode, result.stdout
    except subprocess.TimeoutExpired:
        return -1, "[ERREUR] Délai de 10 secondes dépassé"

def cas_nominal(outil_path):
    with tempfile.TemporaryDirectory() as tmpdir:
        cible_path = pathlib.Path(tmpdir) / "test_cible.py"
        cible_path.write_text("#!/usr/bin/env python3\nprint('Test')\n", encoding="utf-8")

        cmd = [sys.executable, str(outil_path), "--file", str(cible_path)]
        code, output = lancer_processus(cmd)

        if code == 0 and "Debut traitement de" in output and "Fin traitement de" in output:
            print("[OK] Cas nominal")
            return True
        print(f"[ECHEC] Cas nominal - Code: {code}\n{output}")
        return False

def cas_inverse(outil_path):
    cmd = [sys.executable, str(outil_path), "--plans", "cloud"]
    code, output = lancer_processus(cmd)

    if code != 0 and "No targets to process" in output:
        print("[OK] Cas inverse (pas de cibles)")
        return True
    print(f"[ECHEC] Cas inverse - Code: {code}\n{output}")
    return False

def cas_malforme(outil_path):
    with tempfile.TemporaryDirectory() as tmpdir:
        cible_path = pathlib.Path(tmpdir) / "malforme.py"
        cible_path.write_text("print('Test sans shebang'", encoding="utf-8")

        cmd = [sys.executable, str(outil_path), "--file", str(cible_path)]
        code, output = lancer_processus(cmd)

        if code == 0 or "Debut traitement de" in output:
            print("[OK] Cas malformé (traité sans plantage)")
            return True
        print(f"[ECHEC] Cas malformé - Code: {code}\n{output}")
        return False

def cas_usage(outil_path):
    cmd = [sys.executable, str(outil_path)]
    code, output = lancer_processus(cmd)

    if code != 0 and "usage: nexus_relais.py" in output:
        print("[OK] Cas usage (affichage de l'aide)")
        return True
    print(f"[ECHEC] Cas usage - Code: {code}\n{output}")
    return False

def main():
    outil_path = verifier_fichier_outil()
    resultats = []

    resultats.append(cas_nominal(outil_path))
    resultats.append(cas_inverse(outil_path))
    resultats.append(cas_malforme(outil_path))
    resultats.append(cas_usage(outil_path))

    if not all(resultats):
        sys.exit(1)

if __name__ == "__main__":
    main()
