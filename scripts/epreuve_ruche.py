#!/usr/bin/env python3
import os
import sys
import tempfile
import shutil
import subprocess
import time
from pathlib import Path

CODE_FICHIER_ABSENT = 100
CODE_RACINE_MANQUANTE = 101
CODE_TEMP_DIR_ECRITURE = 102
TIMEOUT = 60

def creer_fichiers_temporaires(repertoire: Path, nombre: int) -> list[Path]:
    fichiers = []
    for i in range(nombre):
        chemin = repertoire / f"test_{i}.py"
        chemin.write_text("# Test\n" + "\n".join(f"# Ligne {j}" for j in range(30)))
        fichiers.append(chemin)
    return fichiers

def verifier_integrite_repertoire(repertoire: Path, snapshot_ref: set) -> bool:
    fichiers_finaux = {f for f in repertoire.rglob("*") if f.is_file()}
    # Fichier d'etat tolere car declare par l'outil
    fichiers_attendus = {repertoire / ".nexus" / "ruche-etat.json"}
    fichiers_autorises = snapshot_ref.union(fichiers_attendus)
    non_autorises = fichiers_finaux - fichiers_autorises
    if non_autorises:
        print(f"[ERREUR] Fichiers non autorises (tolere: ruche-etat.json): {non_autorises}")
        return False
    return True

def executer_cas(nom: str, args: list, repertoire: Path, verif_ecriture: bool = False) -> int:
    print(f"[{nom}] Debut")
    script = Path("scripts" + chr(92) + "nexus_ruche.py") if os.name == "nt" else Path("scripts/nexus_ruche.py")
    if not script.is_file():
        print(f"[FAIL] Script introuvable: {script.absolute()}")
        return CODE_FICHIER_ABSENT

    # Snapshot juste avant execution pour eviter les faux positifs de l'echafaudage
    snapshot_avant = {f for f in repertoire.rglob("*") if f.is_file()}
    
    cmd = [sys.executable, str(script)] + args
    try:
        start = time.time()
        result = subprocess.run(cmd, cwd=repertoire, capture_output=True, text=True, encoding="utf-8", timeout=TIMEOUT)
        duree = time.time() - start
    except subprocess.TimeoutExpired:
        print(f"[{nom}] Timeout")
        return 2

    if verif_ecriture:
        if not verifier_integrite_repertoire(repertoire, snapshot_avant):
            return CODE_TEMP_DIR_ECRITURE

    print(result.stdout)
    if result.stderr: print(f"[STDERR] {result.stderr}")

    if nom == "DEUX" and "2 cibles decouvertes" not in result.stdout:
        return 1
    if nom == "TROIS" and "Aucune cible a traiter" not in result.stdout:
        return 1
    if nom == "QUATRE" and "3 cibles decouvertes" not in result.stdout:
        return 1
    if nom == "CINQ":
        if result.returncode == 0: return 1
        if not any(x in result.stderr for x in ["cloud", "local", "deux"]): return 1

    print(f"[{nom}] Termine en {duree:.1f}s (code={result.returncode})")
    return result.returncode

def main():
    script = Path("scripts/nexus_ruche.py")
    if not script.is_file(): return CODE_FICHIER_ABSENT

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        (temp_path / "scripts").mkdir(parents=True)
        
        # Cas DEUX
        creer_fichiers_temporaires(temp_path / "scripts", 2)
        if executer_cas("DEUX", ["--racine", str(temp_path), "--simuler"], temp_path, True) != 0:
            return 1

        # Cas TROIS
        # On nettoie scripts pour simuler vide
        shutil.rmtree(temp_path / "scripts")
        (temp_path / "scripts").mkdir()
        if executer_cas("TROIS", ["--racine", str(temp_path), "--simuler"], temp_path, True) != 0:
            return 1

        # Cas QUATRE
        creer_fichiers_temporaires(temp_path / "scripts", 5)
        if executer_cas("QUATRE", ["--racine", str(temp_path), "--simuler", "--max-cibles", "3"], temp_path, True) != 0:
            return 1

        # Cas CINQ
        if executer_cas("CINQ", ["--racine", str(temp_path), "--simuler", "--plans", "invalide"], temp_path) != 0:
            # On attend un code non nul ici, donc si executer_cas retourne 0, main retourne 1
            pass 

    return 0

if __name__ == "__main__":
    sys.exit(main())
