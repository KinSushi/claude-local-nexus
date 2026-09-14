#!/usr/bin/env python3
"""
Epreuve pure des fonctions creer_copie_detachee et retirer_copie de
scripts/nexus_valide.py, sans invoquer le validateur complet.
"""

import contextlib
import os
import shutil
import stat
import subprocess
import sys
import tempfile

# Ajouter le repertoire scripts au path
repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
scripts_path = os.path.join(repo_root, "scripts")
sys.path.insert(0, scripts_path)

import nexus_valide


def run_git(args, cwd):
    return subprocess.run(
        ["git"] + args,
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

def init_repo(path, commit=True):
    os.makedirs(path, exist_ok=True)
    result = run_git(["init", "-q"], cwd=path)
    if result.returncode != 0:
        raise RuntimeError("git init failed")
    run_git(["config", "user.email", "test@example.com"], cwd=path)
    run_git(["config", "user.name", "Test User"], cwd=path)
    if commit:
        file_path = os.path.join(path, "file.txt")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write("original")
        run_git(["add", "file.txt"], cwd=path)
        run_git(["commit", "-q", "-m", "init"], cwd=path)

def onerror(func, path, exc_info):
    with contextlib.suppress(Exception):
        os.chmod(path, stat.S_IWRITE)
    func(path)

def forward_test():
    depot = tempfile.mkdtemp()
    try:
        init_repo(depot, commit=True)
        # Cree la copie detachee
        copie = nexus_valide.creer_copie_detachee(depot)
        # Verifie que le fichier existe et contient le contenu d'origine
        orig = os.path.join(depot, "file.txt")
        copy_file = os.path.join(copie, "file.txt")
        if not os.path.isfile(copy_file):
            return False, "Le fichier n'existe pas dans la copie"
        with open(orig, "r", encoding="utf-8") as f:
            orig_content = f.read()
        with open(copy_file, "r", encoding="utf-8") as f:
            copy_content = f.read()
        if orig_content != copy_content:
            return False, "Le contenu de la copie differe du depot d'origine"
        # Modifie le fichier dans le depot vivant (sans commit)
        with open(orig, "w", encoding="utf-8") as f:
            f.write("modifie")
        # La copie doit garder l'ancien contenu
        with open(copy_file, "r", encoding="utf-8") as f:
            if f.read() != orig_content:
                return False, "La copie a ete modifiee apres le changement du depot"
        # Nettoyage
        nexus_valide.retirer_copie(depot, copie)
        if os.path.isdir(copie):
            return False, "Le repertoire de copie n'a pas ete supprime"
        return True, ""
    finally:
        shutil.rmtree(depot, onerror=onerror)

def reverse_test():
    depot = tempfile.mkdtemp()
    try:
        init_repo(depot, commit=False)  # depot sans commit
        try:
            nexus_valide.creer_copie_detachee(depot)
            return False, "La fonction n'a pas leve d'exception sur depot sans commit"
        except RuntimeError:
            pass  # attendu
        # Le repertoire .nexus/valide_wt doit etre absent ou vide
        wt_dir = os.path.join(depot, ".nexus", "valide_wt")
        if os.path.isdir(wt_dir) and os.listdir(wt_dir):
            return False, ".nexus/valide_wt present alors qu'il ne doit pas exister"
        return True, ""
    finally:
        shutil.rmtree(depot, onerror=onerror)

def main():
    ok_fwd, msg_fwd = forward_test()
    ok_rev, msg_rev = reverse_test()
    exit_code = 0
    if ok_fwd:
        print("[OK] forward")
    else:
        print(f"[RATE] forward : {msg_fwd}")
        exit_code = 1
    if ok_rev:
        print("[OK] reverse")
    else:
        print(f"[RATE] reverse : {msg_rev}")
        exit_code = 1
    sys.exit(exit_code)

if __name__ == "__main__":
    main()
