import subprocess
import os
import json
import tempfile
import shutil
import sys

def run(args, input_str=None):
    try:
        res = subprocess.run(
            [sys.executable, "scripts/nexus_posterior.py"] + args,
            input=input_str,
            capture_output=True,
            text=True,
            timeout=10
        )
        return res.returncode, res.stdout, res.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "Timeout"
    except Exception as e:
        return -2, "", str(e)

def main():
    tool = "scripts/nexus_posterior.py"
    if not os.path.isfile(tool):
        print(f"Outil absent : {tool}")
        sys.exit(42)

    tmpdir = tempfile.mkdtemp()
    results = []
    
    try:
        # CAS NOMINAL
        obs_path = os.path.join(tmpdir, "obs.jsonl")
        with open(obs_path, "w", encoding="utf-8") as f:
            # 6 obs pour passer MIN_OBS=5
            for i in range(6):
                f.write(json.dumps({"model": "m1", "temperature": 0.1, "debit_jps": 10.0 + i, "duree_ms": 100 + i, "tronquee": False, "repli": "0"}) + "\n")
        
        rc, out, err = run(["--observations", obs_path, "--json"])
        if rc == 0 and '"confiance": "mesuree"' in out and '"model": "m1"' in out:
            results.append("[NOMINAL] OK")
        else:
            results.append(f"[NOMINAL] FAIL: rc={rc} out={out[:50]}")

        # CAS INVERSE (Insuffisant)
        obs_path_low = os.path.join(tmpdir, "low.jsonl")
        with open(obs_path_low, "w", encoding="utf-8") as f:
            f.write(json.dumps({"model": "m2", "temperature": 0.2, "debit_jps": 5.0, "duree_ms": 200}) + "\n")
        
        rc, out, err = run(["--observations", obs_path_low, "--json"])
        if rc == 0 and '"confiance": "insuffisante"' in out:
            results.append("[INVERSE] OK")
        else:
            results.append(f"[INVERSE] FAIL: rc={rc} out={out[:50]}")

        # ENTREE MALFORMEE
        obs_path_bad = os.path.join(tmpdir, "bad.jsonl")
        with open(obs_path_bad, "w", encoding="utf-8") as f:
            f.write("NOT JSON\n")
            f.write(json.dumps({"model": "m3", "temperature": 0.3, "debit_jps": 1.0, "duree_ms": 10}) + "\n")
        
        rc, out, err = run(["--observations", obs_path_bad, "--json"])
        if rc == 0 and '"lignes_ignorees": 1' in out:
            results.append("[MALFORMEE] OK")
        else:
            results.append(f"[MALFORMEE] FAIL: rc={rc} out={out[:50]}")

        # USAGE (Arguments manquants / invalides)
        # L'outil n'a pas d'arguments requis, mais on teste un argument inconnu
        rc, out, err = run(["--unknown-arg"])
        if rc != 0 and "usage:" in err.lower():
            results.append("[USAGE] OK")
        else:
            results.append(f"[USAGE] FAIL: rc={rc} err={err[:50]}")

    finally:
        shutil.rmtree(tmpdir)

    for r in results:
        print(r)

    if any("FAIL" in r for r in results):
        sys.exit(1)
    sys.exit(0)

if __name__ == "__main__":
    main()
