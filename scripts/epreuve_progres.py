# -*- coding: utf-8 -*-
import os
import sys
import subprocess
import tempfile

def verifier_fichier_source():
    script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "nexus_progres.py")
    if not os.path.exists(script_path):
        print(f"[ERREUR] Fichier source introuvable: {script_path}")
        return False
    return script_path

def lancer_script(script_path, temp_dir):
    progress_path = os.path.join(temp_dir, "PROGRES.MD")
    cmd = [sys.executable, script_path]
    try:
        result = subprocess.run(
            cmd,
            cwd=os.path.dirname(script_path),
            timeout=10,
            capture_output=True,
            text=True
        )
        return result.returncode, result.stdout, result.stderr, progress_path
    except subprocess.TimeoutExpired:
        return -1, "", "Timeout", progress_path

def verifier_contenu(progress_path):
    if not os.path.exists(progress_path):
        return False, "Fichier PROGRES.MD non genere"

    with open(progress_path, 'r', encoding='utf-8') as f:
        content = f.read()

    required_sections = [
        "# PROGRESS.MD",
        "*GENERE AUTOMATIQUEMENT*",
        "## ETAT DU DEPOT",
        "## MECANISMES",
        "## SUJETS OUVERTS",
        "## TACHES PLANIFIEES",
        "## CE QUI N'EST PAS MECANISE"
    ]

    for section in required_sections:
        if section not in content:
            return False, f"Section manquante: {section}"

    if "GENERE AUTOMATIQUEMENT le" not in content:
        return False, "Horodatage manquant"

    return True, "Contenu valide"

def cas_nominal():
    script_path = verifier_fichier_source()
    if not script_path:
        return 1

    with tempfile.TemporaryDirectory() as temp_dir:
        code, stdout, stderr, progress_path = lancer_script(script_path, temp_dir)
        if code != 0:
            print(f"[ECHEC_NOMINAL] Code retour: {code}, stderr: {stderr}")
            return 1

        ok, msg = verifier_contenu(progress_path)
        if not ok:
            print(f"[ECHEC_NOMINAL] {msg}")
            return 1

        print("[OK_NOMINAL] Generation reussie")
        return 0

def cas_refus_sans_depot():
    script_path = verifier_fichier_source()
    if not script_path:
        return 1

    with tempfile.TemporaryDirectory() as temp_dir:
        os.chdir(temp_dir)
        code, stdout, stderr, progress_path = lancer_script(script_path, temp_dir)
        if code == 0:
            print("[ECHEC_REFUS] Le script a reussi sans depot git")
            return 1

        if "Git non disponible" not in stderr and "Git non disponible" not in stdout:
            print("[ECHEC_REFUS] Message d'erreur inattendu")
            return 1

        print("[OK_REFUS] Refus correct sans depot git")
        return 0

def cas_entree_malformee():
    script_path = verifier_fichier_source()
    if not script_path:
        return 1

    with tempfile.TemporaryDirectory() as temp_dir:
        checklist_path = os.path.join(temp_dir, "rituels", "CHECKLIST_COCKPIT.MD")
        os.makedirs(os.path.dirname(checklist_path), exist_ok=True)
        with open(checklist_path, 'w', encoding='utf-8') as f:
            f.write("Contenu malformé sans sections")

        code, stdout, stderr, progress_path = lancer_script(script_path, temp_dir)
        if code != 0:
            print(f"[ECHEC_MALFORME] Code retour: {code}, stderr: {stderr}")
            return 1

        with open(progress_path, 'r', encoding='utf-8') as f:
            content = f.read()
            if "CHECKLIST_COCKPIT.MD introuvable" in content:
                print("[ECHEC_MALFORME] Fichier non detecte malgre sa presence")
                return 1

        print("[OK_MALFORME] Gestion correcte de l'entree malformee")
        return 0

def cas_usage():
    script_path = verifier_fichier_source()
    if not script_path:
        return 1

    cmd = [sys.executable, script_path, "--help"]
    try:
        result = subprocess.run(
            cmd,
            timeout=10,
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            print("[ECHEC_USAGE] Le script accepte --help")
            return 1
    except subprocess.TimeoutExpired:
        print("[ECHEC_USAGE] Timeout")
        return 1

    cmd = [sys.executable, script_path]
    try:
        result = subprocess.run(
            cmd,
            timeout=10,
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            print("[OK_USAGE] Refus correct sans arguments")
            return 0
        else:
            print("[ECHEC_USAGE] Le script a reussi sans arguments")
            return 1
    except subprocess.TimeoutExpired:
        print("[ECHEC_USAGE] Timeout")
        return 1

def main():
    cas = [
        ("NOMINAL", cas_nominal),
        ("REFUS_SANS_DEPOT", cas_refus_sans_depot),
        ("ENTREE_MALFORMEE", cas_entree_malformee),
        ("USAGE", cas_usage)
    ]

    codes = []
    for name, func in cas:
        try:
            code = func()
            codes.append(code)
            if code != 0:
                print(f"[ECHEC_GLOBAL] Cas {name} a echoue")
                return 1
        except Exception as e:
            print(f"[ECHEC_GLOBAL] Exception dans {name}: {str(e)}")
            return 1

    print("[SUCCES_GLOBAL] Tous les cas passes")
    return 0

if __name__ == "__main__":
    sys.exit(main())
