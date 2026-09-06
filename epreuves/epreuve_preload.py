import subprocess
import os
import sys

def run_test(args):
    tool = os.path.join("scripts", "nexus_preload.py")
    cmd = [sys.executable, tool] + args
    try:
        res = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=10
        )
        return res.returncode, res.stdout, res.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "Timeout after 10s"
    except Exception as e:
        return -2, "", str(e)

def main():
    tool_path = os.path.join("scripts", "nexus_preload.py")
    if not os.path.exists(tool_path):
        print(f"Tool missing: {tool_path}")
        sys.exit(99)

    results = []
    
    # CAS NOMINAL: Modèle local (simule erreur passerelle car pas de serveur)
    # On verifie que l'outil tente l'appel et rend un message specifique
    rc, out, err = run_test(["my-model-local"])
    if rc == 0 and "my-model-local: erreur" in out and "Passerelle inaccessible" in out:
        results.append("[NOMINAL] OK")
    else:
        results.append(f"[NOMINAL] FAIL: rc={rc} out={out[:50]}")

    # CAS INVERSE: Modèle cloud doit etre refuse sans appel reseau
    rc, out, err = run_test(["my-model-cloud"])
    if rc == 0 and "Modèle distant (pas de poids locaux à précharger)" in out:
        results.append("[INVERSE] OK")
    else:
        results.append(f"[INVERSE] FAIL: rc={rc} out={out[:50]}")

    # CAS MALFORME: Entree vide ou bizarre (ici on teste un alias vide via shell)
    # L'outil accepte n'importe quelle chaine comme alias
    rc, out, err = run_test([""])
    if rc == 0 and ": erreur" in out:
        results.append("[MALFORME] OK")
    else:
        results.append(f"[MALFORME] FAIL: rc={rc} out={out[:50]}")

    # CAS USAGE: Aucun argument
    rc, out, err = run_test([])
    if rc != 0 and ("usage:" in err.lower() or "the following arguments are required" in err.lower()):
        results.append("[USAGE] OK")
    else:
        results.append(f"[USAGE] FAIL: rc={rc} err={err[:50]}")

    for r in results:
        print(r)

    if any("FAIL" in r for r in results):
        sys.exit(1)
    sys.exit(0)

if __name__ == "__main__":
    main()
