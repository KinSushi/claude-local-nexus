import os
import sys
import subprocess
import tempfile
import shutil

def run_tool(tool_path, args, cwd):
    try:
        res = subprocess.run(
            [sys.executable, tool_path] + args,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=10
        )
        return res.returncode, res.stdout, res.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "L'outil n'a pas rendu la main"
    except Exception as e:
        return -2, "", str(e)

def main():
    tool_rel_path = os.path.join("scripts", "nexus_progres.py")
    if not os.path.exists(tool_rel_path):
        print(f"Outil introuvable : {tool_rel_path}")
        sys.exit(127)

    tmp_dir = tempfile.mkdtemp()
    try:
        # Structure minimale requise par l'outil
        os.makedirs(os.path.join(tmp_dir, "scripts"))
        os.makedirs(os.path.join(tmp_dir, "rituels"))
        
        tool_dst = os.path.join(tmp_dir, "scripts", "nexus_progres.py")
        shutil.copy(tool_rel_path, tool_dst)

        # L'outil ne permet pas de designer un fichier de sortie.
        # Il ecrit PROGRESS.MD a la racine derivee de __file__.
        # L'execution dans tmp_dir isole donc l'ecriture.

        # CAS 1: NOMINAL
        # L'outil n'a pas d'options en ligne de commande.
        rc, out, err = run_tool(tool_dst, [], tmp_dir)
        prog_file = os.path.join(tmp_dir, "PROGRESS.MD")
        success_1 = (rc == 0 and os.path.exists(prog_file))
        print(f"[{'OK' if success_1 else 'RATE'}] Nominal : rc={rc}")
        if not success_1: sys.exit(1)

        # CAS 2: INVERSE (Refus ecriture)
        # On retire les droits d'ecriture sur le dossier racine du tmp
        os.chmod(tmp_dir, 0o555)
        rc, out, err = run_tool(tool_dst, [], tmp_dir)
        # L'outil doit rendre 1 via son bloc try/except final
        print(f"[{'OK' if rc == 1 else 'RATE'}] Refus ecriture : rc={rc}")
        os.chmod(tmp_dir, 0o755)
        if rc != 1: sys.exit(1)

        # CAS 3: ENTREE MALFORMEE
        # L'outil ignore sys.argv, il ne doit pas planter
        rc, out, err = run_tool(tool_dst, ["--unknown", "val"], tmp_dir)
        print(f"[{'OK' if rc == 0 else 'RATE'}] Entree malformee : rc={rc}")
        if rc != 0: sys.exit(1)

        # CAS 4: INVOCATION SANS ARGUMENTS REQUIS
        # L'outil n'a aucun argument requis. L'absence est le mode nominal.
        rc, out, err = run_tool(tool_dst, [], tmp_dir)
        print(f"[{'OK' if rc == 0 else 'RATE'}] Invocation vide : rc={rc}")
        if rc != 0: sys.exit(1)

    finally:
        shutil.rmtree(tmp_dir)

if __name__ == "__main__":
    main()
