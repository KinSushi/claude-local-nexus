#!/usr/bin/env python3
import json
import os
import pathlib
import subprocess
import sys
import tempfile


def main():
    # Chemin vers le script a tester
    script_path = pathlib.Path(__file__).resolve().parents[1] / "scripts" / "nexus_agent.py"

    # Cree un fichier lot JSON temporaire contenant un tableau vide
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as tf:
        tf.write('[]')
        lot_path = tf.name

    try:
        # Execute le script avec les options demandees
        proc = subprocess.run(
            [sys.executable, str(script_path), '--json', '--lot', lot_path],
            capture_output=True,
            text=True,
        )
        stdout = proc.stdout.strip()

        # Verifie que la sortie est vide ou bien un JSON valide
        ok = True
        if stdout:
            try:
                json.loads(stdout)
            except Exception:
                ok = False

        if ok:
            print("[OK]")
            sys.exit(0)
        else:
            print("[RATE]")
            sys.exit(1)
    finally:
        # Nettoyage du fichier temporaire
        os.unlink(lot_path)

if __name__ == "__main__":
    main()
