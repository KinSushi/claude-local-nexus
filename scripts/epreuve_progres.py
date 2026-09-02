import os
import sys
import subprocess
import tempfile
import shutil

def run_tool(args):
    tool_path = os.path.join("scripts", "nexus_progres.py")
    if not os.path.exists(tool_path):
        print(f"Outil introuvable : {tool_path}")
        sys.exit(127)
    
    res = subprocess.run(
        [sys.executable, tool_path] + args,
        capture_output=True,
        text=True
    )
    return res.returncode, res.stdout, res.stderr

def main():
    # Setup environnement temporaire pour ne pas toucher au depot
    tmp_dir = tempfile.mkdtemp()
    try:
        # On simule la structure attendue par l'outil
        os.makedirs(os.path.join(tmp_dir, "scripts"))
        os.makedirs(os.path.join(tmp_dir, "rituels"))
        
        # Copie de l'outil dans le dossier temporaire pour l'execution
        tool_src = "scripts/nexus_progres.py"
        tool_dst = os.path.join(tmp_dir, "scripts", "nexus_progres.py")
        shutil.copy(tool_src, tool_dst)
        
        # On change le repertoire de travail pour le sous-processus
        # Note: l'outil utilise os.path.abspath(__file__) pour trouver la racine
        # On doit donc lancer le script depuis son emplacement dans tmp_dir
        
        def execute(args):
            # On simule l'appel depuis la racine du depot temporaire
            res = subprocess.run(
                [sys.executable, tool_dst] + args,
                cwd=tmp_dir,
                capture_output=True,
                text=True
            )
            return res.returncode, res.stdout, res.stderr

        # CAS 1: NOMINAL
        # L'outil n'a pas d'arguments requis selon son code, il lit le depot
        rc, out, err = execute([])
        print(f"[{'OK' if rc == 0 else 'RATE'}] Nominal : rc={rc}")
        if rc != 0: sys.exit(1)

        # CAS 2: INVERSE (Refus attendu)
        # L'outil ecrit PROGRESS.MD a la racine. On retire les droits d'ecriture
        # sur le dossier racine pour forcer un echec d'ecriture atomique.
        os.chmod(tmp_dir, 0o555)
        rc, out, err = execute([])
        # L'outil doit rendre 1 en cas d'exception lors de l'ecriture
        print(f"[{'OK' if rc != 0 else 'RATE'}] Refus ecriture : rc={rc}")
        os.chmod(tmp_dir, 0o755) # Restore
        if rc == 0: sys.exit(1)

        # CAS 3: ENTREE MALFORMEE
        # L'outil n'utilise pas sys.argv pour sa logique, mais on teste 
        # le passage d'arguments inconnus pour verifier la stabilite.
        rc, out, err = execute(["--option-inconnue", "valeur"])
        print(f"[{'OK' if rc == 0 else 'RATE'}] Entree malformee : rc={rc}")
        if rc != 0: sys.exit(1)

        # CAS 4: INVOCATION SANS ARGUMENTS REQUIS
        # L'outil n'a aucun argument requis dans son code (main() ne lit pas sys.argv).
        # Cependant, on verifie qu'il ne crash pas et ne rend pas d'usage errone.
        # Si on considerait que le script DOIT avoir des arguments, ce test changerait.
        # Ici, l'absence d'arguments est le mode nominal.
        rc, out, err = execute([])
        print(f"[{'OK' if rc == 0 else 'RATE'}] Invocation vide : rc={rc}")
        if rc != 0: sys.exit(1)

    finally:
        shutil.rmtree(tmp_dir)

if __name__ == "__main__":
    main()
