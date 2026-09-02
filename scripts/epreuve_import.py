import os
import sys
import subprocess
import tempfile
import shutil

def run_tool(args):
    tool_path = "scripts/nexus_import.py"
    if not os.path.exists(tool_path):
        print("Outil introuvable: " + tool_path)
        sys.exit(127)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # On recrée la structure scripts/ pour que l'outil trouve ses cibles
        scripts_dir = os.path.join(tmpdir, "scripts")
        os.makedirs(scripts_dir)
        
        # Copie de l'outil lui-meme dans le dossier temporaire
        tool_dest = os.path.join(scripts_dir, "nexus_import.py")
        with open(tool_path, "rb") as src, open(tool_dest, "wb") as dst:
            shutil.copyfileobj(src, dst)
            
        # On lance l'outil depuis la racine du dossier temporaire
        try:
            proc = subprocess.run(
                [sys.executable, tool_dest] + args,
                cwd=tmpdir,
                capture_output=True,
                text=True,
                timeout=10,
                encoding="utf-8",
                errors="replace"
            )
            return proc.returncode, proc.stdout, proc.stderr
        except subprocess.TimeoutExpired:
            return -1, "", "L'outil n'a pas rendu la main"
        except Exception as e:
            return -2, "", "Erreur execution: " + str(e)

def create_module(tmpdir, name, content):
    path = os.path.join(tmpdir, "scripts", name + ".py")
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

def main():
    # On utilise un dossier temporaire pour isoler les modules de test
    with tempfile.TemporaryDirectory() as tmpdir:
        # Setup: on recrée la structure pour les tests
        scripts_dir = os.path.join(tmpdir, "scripts")
        os.makedirs(scripts_dir)
        tool_src = "scripts/nexus_import.py"
        tool_dest = os.path.join(scripts_dir, "nexus_import.py")
        with open(tool_src, "rb") as s, open(tool_dest, "wb") as d:
            shutil.copyfileobj(s, d)

        def test_run(name, args, expected_code, check_out=None, check_err=None):
            # On execute l'outil depuis tmpdir
            try:
                proc = subprocess.run(
                    [sys.executable, tool_dest] + args,
                    cwd=tmpdir,
                    capture_output=True,
                    text=True,
                    timeout=10,
                    encoding="utf-8",
                    errors="replace"
                )
                code, out, err = proc.returncode, proc.stdout, proc.stderr
            except subprocess.TimeoutExpired:
                print("[FAIL] " + name + " : L'outil n'a pas rendu la main")
                return False
            except Exception as e:
                print("[FAIL] " + name + " : Exception " + str(e))
                return False

            success = (code == expected_code)
            if check_out and check_out not in out:
                success = False
            if check_err and check_err not in err:
                success = False
            
            print(("[OK  ] " if success else "[FAIL] ") + name)
            return success

        # CAS 1: Nominal - Module sain
        create_module(tmpdir, "mod_sain", "x = 1")
        res1 = test_run("NOMINAL", ["--seul", "mod_sain"], 0, check_out="0 module(s) importes, 0 echec(s).")

        # CAS 2: Inverse - Module avec effet de bord (ecrit sur stdout)
        create_module(tmpdir, "mod_effet", "print('Hello')")
        res2 = test_run("INVERSE", ["--seul", "mod_effet"], 1, check_out="[EFFET ] mod_effet")

        # CAS 3: Malformee - Module qui plante a l'import
        create_module(tmpdir, "mod_crash", "raise RuntimeError('Crash')")
        res3 = test_run("MALFORMEE", ["--seul", "mod_crash"], 1, check_out="[ECHEC ] mod_crash")

        # CAS 4: Invocation sans arguments requis (cas ici: module inconnu)
        res4 = test_run("INCONNU", ["--seul", "inexistant"], 2, check_err="Module(s) inconnu(s)")

        if not all([res1, res2, res3, res4]):
            sys.exit(1)

if __name__ == "__main__":
    main()
