import os
import sys
import subprocess
import tempfile
import shutil

def run_tool(cwd, args=[]):
    tool_path = os.path.join(cwd, "scripts", "nexus_progres.py")
    if not os.path.exists(tool_path):
        return None, f"Outil introuvable: {tool_path}"
    
    try:
        proc = subprocess.Popen(
            [sys.executable, tool_path] + args,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        stdout, stderr = proc.communicate(timeout=10)
        return (proc.returncode, stdout, stderr), None
    except subprocess.TimeoutExpired:
        proc.kill()
        return None, "L'outil n'a pas rendu la main"
    except Exception as e:
        return None, f"Erreur execution: {str(e)}"

def main():
    # L'outil ne permet pas de designer une racine ou une sortie differente.
    # Il utilise os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    # et ecrit PROGRESS.MD a la racine.
    # On cree donc un faux depot pour eviter d'ecrire dans le reel.
    
    base_tmp = tempfile.mkdtemp()
    try:
        # Structure minimale pour que l'outil fonctionne
        root = base_tmp
        scripts_dir = os.path.join(root, "scripts")
        os.makedirs(scripts_dir)
        
        # Copie de l'outil original vers le dossier temporaire
        # On suppose que le script est lance depuis la racine du depot reel
        real_tool = "scripts" + chr(92) + "nexus_progres.py" if os.name == 'nt' else "scripts/nexus_progres.py"
        if not os.path.exists(real_tool):
            print(f"Outil source introuvable: {real_tool}")
            sys.exit(127)
        shutil.copy(real_tool, os.path.join(scripts_dir, "nexus_progres.py"))
        
        # Simulation d'un depot git
        subprocess.run(["git", "init"], cwd=root, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=root, capture_output=True)
        subprocess.run(["git", "config", "user.name", "test"], cwd=root, capture_output=True)
        with open(os.path.join(root, "README.md"), "w") as f: f.write("test")
        subprocess.run(["git", "add", "."], cwd=root, capture_output=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=root, capture_output=True)

        cases = []
        
        # CAS 1: Nominal
        res, err = run_tool(root)
        if res and res[0] == 0 and os.path.exists(os.path.join(root, "PROGRESS.MD")):
            cases.append(True)
        else:
            cases.append(False)
        print(f"[{'OK  ' if cases[-1] else 'FAIL'}] NOMINAL")

        # CAS 2: Inverse (Echec ecriture)
        # On rend la racine en lecture seule pour forcer l'echec de l'ecriture atomique
        # Note: Sur Windows, os.chmod est limite, mais on tente de verrouiller le fichier
        prog_file = os.path.join(root, "PROGRESS.MD")
        with open(prog_file, "w") as f: f.write("lock")
        # On tente de simuler un echec en rendant le dossier non-ecrivable si possible
        # Sinon on verifie que l'outil rend 1 si l'ecriture echoue
        # Pour ce test, on simule un environnement dove l'outil ne peut pas ecrire
        # en changeant les permissions du dossier racine
        os.chmod(root, 0o555) 
        res, err = run_tool(root)
        # L'outil rend 1 en cas d'exception lors de l'ecriture
        cases.append(res is not None and res[0] == 1)
        print(f"[{'OK  ' if cases[-1] else 'FAIL'}] REFUS_ECRITURE")
        os.chmod(root, 0o755)

        # CAS 3: Entree malformee (Arguments inconnus)
        # L'outil n'utilise pas argparse, il ignore les arguments sys.argv[1:]
        # Il ne doit pas planter.
        res, err = run_tool(root, ["--unknown", "val"])
        cases.append(res is not None and res[0] == 0)
        print(f"[{'OK  ' if cases[-1] else 'FAIL'}] ARGUMENTS_INCONNUS")

        # CAS 4: Invocation sans arguments (Normal pour cet outil)
        # L'outil n'a pas d'arguments requis.
        res, err = run_tool(root)
        cases.append(res is not None and res[0] == 0)
        print(f"[{'OK  ' if cases[-1] else 'FAIL'}] SANS_ARGUMENTS")

        if not all(cases):
            sys.exit(1)

    finally:
        shutil.rmtree(base_tmp)

if __name__ == "__main__":
    main()
