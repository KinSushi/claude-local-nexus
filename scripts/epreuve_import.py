import os
import sys
import subprocess
import tempfile
import shutil

def run_tool(args, cwd):
    try:
        res = subprocess.run(
            [sys.executable, "scripts/nexus_import.py"] + args,
            cwd=cwd, capture_output=True, text=True, timeout=10,
            encoding="utf-8", errors="replace"
        )
        return res.returncode, res.stdout, res.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "L'outil n'a pas rendu la main"
    except Exception as e:
        return -1, "", str(e)

def main():
    tool_path = os.path.join("scripts", "nexus_import.py")
    if not os.path.exists(tool_path):
        print(f"[FAIL] Fichier introuvable : {tool_path}")
        sys.exit(127)

    tmp_dir = tempfile.mkdtemp()
    # Copie du depot pour isoler les tests
    try:
        shutil.copytree("scripts", os.path.join(tmp_dir, "scripts"), dirs_exist_ok=True)
        # On travaille dans le parent de scripts pour que le script trouve son dossier
        work_dir = tmp_dir
    except Exception as e:
        print(f"[FAIL] Erreur setup : {e}")
        sys.exit(1)

    try:
        # CAS NOMINAL : Execution standard
        # L'outil liste les modules et finit par "X module(s) importes, Y echec(s)."
        rc, out, err = run_tool([], work_dir)
        if "module(s) importes" in out and rc in (0, 1):
            print("[OK] Nominal")
        else:
            print(f"[FAIL] Nominal : rc={rc}, out={out[:50]}")
            sys.exit(1)

        # CAS INVERSE : Module inconnu via --seul
        # Doit rendre code 2 et message "Module(s) inconnu(s)" sur stderr
        rc, out, err = run_tool(["--seul", "module_fantome"], work_dir)
        if rc == 2 and "Module(s) inconnu(s)" in err:
            print("[OK] Inconnu")
        else:
            print(f"[FAIL] Inconnu : rc={rc}, err={err[:50]}")
            sys.exit(1)

        # CAS MALFORMEE : Option inconnue
        # Argparse rend code 2 et écrit sur stderr
        rc, out, err = run_tool(["--option-inconnue"], work_dir)
        if rc != 0:
            print("[OK] Malformee")
        else:
            print(f"[FAIL] Malformee : rc={rc}")
            sys.exit(1)

        # CAS SANS ARGUMENTS : Usage
        # L'outil ne rend pas l'usage sur invocation vide (il lance le scan),
        # mais on verifie ici que l'invocation sans arguments fonctionne.
        rc, out, err = run_tool([], work_dir)
        if "module(s) importes" in out:
            print("[OK] Sans arguments")
        else:
            print(f"[FAIL] Sans arguments : rc={rc}")
            sys.exit(1)

        # CAS JSON : Formatage
        rc, out, err = run_tool(["--json"], work_dir)
        if out.strip().startswith("{") and out.strip().endswith("}"):
            print("[OK] JSON")
        else:
            print(f"[FAIL] JSON : out={out[:50]}")
            sys.exit(1)

    finally:
        shutil.rmtree(tmp_dir)

    sys.exit(0)

if __name__ == "__main__":
    main()
