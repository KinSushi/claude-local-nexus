import os
import sys
import subprocess
import tempfile
import shutil
from pathlib import Path

def run_tool(args, cwd):
    cmd = [sys.executable, "scripts/nexus_outillage.py"] + args
    return subprocess.run(
        cmd, cwd=str(cwd), capture_output=True, text=True, encoding="utf-8"
    )

def main():
    tool_path = Path("scripts/nexus_outillage.py")
    if not tool_path.exists():
        print(f"Outil introuvable : {tool_path}")
        sys.exit(42)

    tmp_dir = Path(tempfile.mkdtemp())
    try:
        # Simulation de la structure du depot
        (tmp_dir / "scripts").mkdir()
        (tmp_dir / "tools").mkdir()
        (tmp_dir / "rituels").mkdir()
        shutil.copy(tool_path, tmp_dir / "scripts/nexus_outillage.py")
        
        # On simule l'absence des binaires pour tester les etats 'absent'
        # car l'outil cherche dans .nexus/outillage
        
        results = []

        # CAS 1: Nominal (sans options, outils absents = code 2 selon spec)
        # Note: L'outil rend 2 si aucun outil n'a joue.
        res1 = run_tool([], tmp_dir)
        results.append(["NOMINAL", res1.returncode == 2])

        # CAS 2: Inverse (Refus attendu)
        # On teste --installer qui doit echouer car uv/npm ne sont pas dans le venv tmp
        res2 = run_tool(["--installer"], tmp_dir)
        # Doit refuser (code non nul) et nommer le probleme (Ruff/Eslint NON installe)
        ok2 = (res2.returncode != 0) and ("NON installe" in res2.stdout)
        results.append(["INVERSE", ok2])

        # CAS 3: Entree malformee (Option inconnue)
        # argparse doit gerer et rendre non nul sans planter (crash)
        res3 = run_tool(["--option-inexistante"], tmp_dir)
        ok3 = (res3.returncode != 0)
        results.append(["MALFORME", ok3])

        # CAS 4: Arguments requis / Usage
        # L'outil n'a pas d'arguments positionnels requis, mais on teste 
        # l'invocation vide vs options. L'usage est affiche si args invalides.
        res4 = run_tool(["--json"], tmp_dir) 
        # --json attend un FICHIER. Sans argument, argparse affiche l'usage et rend non nul.
        ok4 = (res4.returncode != 0) and ("the following arguments are required" in res4.stderr or "usage" in res4.stderr.lower())
        results.append(["USAGE", ok4])

        for name, ok in results:
            print(f"[{'OK' if ok else 'FAIL'}] {name}")

        if any(not ok for _, ok in results):
            sys.exit(1)

    finally:
        shutil.rmtree(tmp_dir)

if __name__ == "__main__":
    main()
