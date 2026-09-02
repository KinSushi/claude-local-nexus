import os
import sys
import subprocess
import tempfile
import shutil

def run_tool(exe, args, cwd):
    try:
        proc = subprocess.run(
            [sys.executable, exe] + args,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=10
        )
        return proc.returncode, proc.stdout, proc.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "L'outil n'a pas rendu la main"
    except Exception as e:
        return -1, "", str(e)

def main():
    # Analyse du premier fichier : nexus_progres.py
    # Options : Aucune
    # Arguments : Aucun
    # Codes retour : 0 (succes), 1 (erreur ecriture)
    # Sortie : Rien sur stdout, ecrit PROGRESS.MD a la racine
    
    tool_rel_path = os.path.join("scripts", "nexus_progres.py")
    tool_abs_path = os.path.abspath(tool_rel_path)
    
    if not os.path.exists(tool_abs_path):
        print(f"[FAIL] Fichier introuvable : {tool_abs_path}")
        sys.exit(127)

    # L'outil utilise os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    # pour trouver la racine. On simule donc l'arborescence.
    with tempfile.TemporaryDirectory() as tmp_root:
        scripts_dir = os.path.join(tmp_root, "scripts")
        os.makedirs(scripts_dir)
        
        # Copie de l'outil dans le repertoire temporaire pour eviter d'ecrire dans le depot
        tool_tmp_path = os.path.join(scripts_dir, "nexus_progres.py")
        shutil.copy2(tool_abs_path, tool_tmp_path)
        
        # Cas 1 : Nominal
        # On cree un faux depot git pour eviter les messages d'erreur git
        subprocess.run(["git", "init"], cwd=tmp_root, capture_output=True)
        
        rc, out, err = run_tool(tool_tmp_path, [], tmp_root)
        
        progress_file = os.path.join(tmp_root, "PROGRESS.MD")
        if os.path.exists(progress_file):
            with open(progress_file, "r", encoding="utf-8") as f:
                content = f.read()
            if "# PROGRESS.MD" in content and rc == 0:
                print("[OK] Cas nominal : PROGRESS.MD genere avec contenu valide")
            else:
                print(f"[FAIL] Cas nominal : Contenu invalide ou RC={rc}")
                sys.exit(1)
        else:
            print("[FAIL] Cas nominal : PROGRESS.MD non cree")
            sys.exit(1)

        # Cas 2 : Invocation sans arguments (comportement attendu : nominal car pas d'options)
        rc, out, err = run_tool(tool_tmp_path, [], tmp_root)
        if rc == 0:
            print("[OK] Invocation sans arguments : Succes")
        else:
            print(f"[FAIL] Invocation sans arguments : RC={rc}")
            sys.exit(1)

        # Cas 3 : Entree malformee (arguments inattendus)
        # L'outil n'utilise pas sys.argv, donc il ignore les arguments
        rc, out, err = run_tool(tool_tmp_path, ["--unknown", "val"], tmp_root)
        if rc == 0:
            print("[OK] Entree malformee : Ignore sans plantage")
        else:
            print(f"[FAIL] Entree malformee : Plantage RC={rc}")
            sys.exit(1)

        # Cas 4 : Refus d'ecriture (Lecture seule)
        # On tente de rendre la racine non ecrivable
        try:
            os.chmod(tmp_root, 0o555)
            rc, out, err = run_tool(tool_tmp_path, [], tmp_root)
            # L'outil doit retourner 1 en cas d'exception lors de l'ecriture
            if rc == 1:
                print("[OK] Cas inverse : Refus d'ecriture gere (RC=1)")
            else:
                print(f"[FAIL] Cas inverse : RC attendu 1, recu {rc}")
                sys.exit(1)
        except Exception as e:
            print(f"[INFO] Impossible de tester le refus d'ecriture : {e}")
        finally:
            os.chmod(tmp_root, 0o755)

    print("[ALL TESTS PASSED]")
    sys.exit(0)

if __name__ == "__main__":
    main()
