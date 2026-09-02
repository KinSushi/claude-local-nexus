import subprocess
import sys
import os
import tempfile
import json

def run_tool(args):
    tool_path = os.path.join("scripts", "nexus_preload.py")
    cmd = [sys.executable, tool_path] + args
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=10,
            cwd=os.getcwd()
        )
        return proc.returncode, proc.stdout, proc.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "L'outil n'a pas rendu la main"
    except Exception as e:
        return -1, "", str(e)

def main():
    tool_path = os.path.join("scripts", "nexus_preload.py")
    if not os.path.exists(tool_path):
        print(f"[FAIL] Fichier introuvable: {tool_path}")
        sys.exit(127)

    with tempfile.TemporaryDirectory() as tmpdir:
        os.chdir(tmpdir)
        
        # CAS 1: Invocation sans arguments (Usage + Code non nul)
        # Note: argparse sort normalement en code 2 pour manque d'args
        rc, out, err = run_tool([])
        if rc != 0 and "usage" in err.lower():
            print("[OK] Invocation sans arguments")
        else:
            print(f"[FAIL] Sans arguments: rc={rc}, err={err}")
            sys.exit(1)

        # CAS 2: Modèle distant (Refus explicite)
        # L'outil doit refuser les alias finissant par -cloud
        rc, out, err = run_tool(["model-cloud"])
        if rc == 0 and "erreur" in out and "Modèle distant" in out:
            print("[OK] Refus modèle distant")
        else:
            print(f"[FAIL] Modèle distant: rc={rc}, out={out}")
            sys.exit(1)

        # CAS 3: Entrée malformée / Passerelle inaccessible (Nominal erreur)
        # On teste un alias local alors que rien n'écoute sur le port 4000
        rc, out, err = run_tool(["model-local"])
        if rc == 0 and "erreur" in out and "Passerelle inaccessible" in out:
            print("[OK] Gestion passerelle inaccessible")
        else:
            print(f"[FAIL] Passerelle inaccessible: rc={rc}, out={out}")
            sys.exit(1)

        # CAS 4: Sortie JSON
        rc, out, err = run_tool(["model-local", "--json"])
        try:
            data = json.loads(out)
            if isinstance(data, list) and len(data) > 0 and "etat" in data[0]:
                print("[OK] Sortie JSON valide")
            else:
                raise ValueError("Structure JSON incorrecte")
        except Exception as e:
            print(f"[FAIL] Sortie JSON: {e}")
            sys.exit(1)

        # CAS 5: Plusieurs alias
        rc, out, err = run_tool(["m1", "m2"])
        if rc == 0 and out.count(":") >= 2:
            print("[OK] Multiples alias")
        else:
            print(f"[FAIL] Multiples alias: rc={rc}, out={out}")
            sys.exit(1)

    print("[ALL TESTS PASSED]")
    sys.exit(0)

if __name__ == "__main__":
    main()
