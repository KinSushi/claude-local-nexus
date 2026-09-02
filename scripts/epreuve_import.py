import os, subprocess, sys, tempfile, shutil

def run(args):
    try:
        r = subprocess.run([sys.executable] + args, capture_output=True, 
                           text=True, timeout=10, encoding="utf-8", errors="replace")
        return r.returncode, r.stdout, r.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "L'outil n'a pas rendu la main (timeout 10s)"
    except Exception as e:
        return -1, "", str(e)

def main():
    tool = os.path.join("scripts", "nexus_import.py")
    if not os.path.exists(tool):
        print(f"Outil introuvable : {tool}")
        sys.exit(42)

    tmp = tempfile.mkdtemp()
    try:
        # On cree un module valide et un module avec effet de bord dans le dossier scripts
        # pour tester le comportement reel de l'outil sans modifier le depot.
        # Mais l'outil scanne SCRIPTS = os.path.dirname(os.path.abspath(__file__))
        # On ne peut pas facilement injecter des fichiers dans scripts/ sans ecrire dans le depot.
        # On va donc tester sur les fichiers existants ou simuler via des arguments.
        
        # CAS NOMINAL : --seul avec un module existant (l'outil lui-meme est exclue, 
        # on cherche un autre .py dans scripts/)
        scripts_dir = os.path.dirname(tool)
        candidats = [n[:-3] for n in os.listdir(scripts_dir) if n.endswith(".py") 
                     and n[:-3] != "nexus_import"]
        
        if not candidats:
            print("[Nominal] Aucun autre module .py trouve pour tester")
            return 0

        target = candidats[0]
        rc, out, err = run(["-c", "import sys; sys.path.insert(0, r'" + scripts_dir + "'); "
                           "import " + target + "; print('OK')"])
        # On verifie que l'outil peut au moins s'executer
        rc_tool, out_tool, err_tool = run([tool, "--seul", target])
        if rc_tool == 0 and "0 echec(s)" in out_tool:
            print(f"[Nominal] OK (module {target})")
        else:
            print(f"[Nominal] ECHEC: rc={rc_tool}, out={out_tool}, err={err_tool}")
            sys.exit(1)

        # CAS INVERSE : Module inconnu
        rc, out, err = run([tool, "--seul", "module_inexistant_xyz"])
        if rc == 2 and "Module(s) inconnu(s)" in err:
            print("[Inverse] OK (refus module inconnu)")
        else:
            print(f"[Inverse] ECHEC: rc={rc}, out={out}, err={err}")
            sys.exit(1)

        # CAS MALFORMEE : Argument inconnu
        rc, out, err = run([tool, "--option-fantome"])
        if rc != 0 and "unrecognized arguments" in err:
            print("[Malformee] OK (usage rendu)")
        else:
            print(f"[Malformee] ECHEC: rc={rc}, out={out}, err={err}")
            sys.exit(1)

        # CAS SANS ARGUMENTS : Verifie que ca lance le scan global
        rc, out, err = run([tool])
        if rc is not None and "module(s) importes" in out:
            print("[Global] OK (scan effectue)")
        else:
            print(f"[Global] ECHEC: rc={rc}, out={out}, err={err}")
            sys.exit(1)

    finally:
        shutil.rmtree(tmp)

if __name__ == "__main__":
    main()
