import subprocess
import sys
import os
import tempfile
import json
import shutil

def run(exe, args, cwd):
    try:
        res = subprocess.run(
            [sys.executable, exe] + args,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=10
        )
        return res.returncode, res.stdout, res.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "L'outil n'a pas rendu la main"
    except Exception as e:
        return -2, "", f"Erreur execution: {str(e)}"

def test():
    tool = "scripts/nexus_posterior.py"
    if not os.path.exists(tool):
        print(f"Outil introuvable: {tool}")
        sys.exit(127)

    tmp = tempfile.mkdtemp()
    try:
        # Setup: fichier d'observations
        obs_path = os.path.join(tmp, "obs.jsonl")
        # 6 obs pour llama (mesuree), 2 pour mistral (insuffisante), 1 malformee
        data = [
            {"model": "llama", "temperature": 0.1, "debit_jps": 10.0, "duree_ms": 100, "tronquee": False, "repli": "0"},
            {"model": "llama", "temperature": 0.1, "debit_jps": 12.0, "duree_ms": 110, "tronquee": False, "repli": "0"},
            {"model": "llama", "temperature": 0.1, "debit_jps": 11.0, "duree_ms": 105, "tronquee": False, "repli": "0"},
            {"model": "llama", "temperature": 0.1, "debit_jps": 10.0, "duree_ms": 100, "tronquee": False, "repli": "0"},
            {"model": "llama", "temperature": 0.1, "debit_jps": 11.0, "duree_ms": 105, "tronquee": False, "repli": "0"},
            {"model": "llama", "temperature": 0.1, "debit_jps": 11.0, "duree_ms": 105, "tronquee": False, "repli": "0"},
            {"model": "mistral", "temperature": 0.2, "debit_jps": 5.0, "duree_ms": 200, "tronquee": True, "repli": "1"},
            {"model": "mistral", "temperature": 0.2, "debit_jps": 6.0, "duree_ms": 210, "tronquee": False, "repli": "0"},
            "LIGNE_CORROMPUE",
            {"model": "mistral", "temperature": 0.2} # Manque debit/duree -> doit etre ignoree ou traitée sans crash
        ]
        with open(obs_path, "w", encoding="utf-8") as f:
            for line in data:
                if isinstance(line, dict):
                    f.write(json.dumps(line) + "\n")
                else:
                    f.write(line + "\n")

        # Cas 1: Nominal JSON
        rc, out, err = run(tool, ["--observations", obs_path, "--json"], tmp)
        res = json.loads(out)
        if rc == 0 and res["total"] == 8 and res["lignes_ignorees"] >= 1:
            print("[NOMINAL] OK")
        else:
            print(f"[NOMINAL] FAIL: rc={rc}, out={out}")
            sys.exit(1)

        # Cas 2: Filtre modele
        rc, out, err = run(tool, ["--observations", obs_path, "--modele", "llama", "--json"], tmp)
        res = json.loads(out)
        if rc == 0 and len(res["agregats"]) == 1 and res["agregats"][0]["model"] == "llama":
            print("[FILTRE] OK")
        else:
            print(f"[FILTRE] FAIL: rc={rc}, out={out}")
            sys.exit(1)

        # Cas 3: Fichier absent (doit rendre 0 et message specifique)
        rc, out, err = run(tool, ["--observations", "absent.jsonl"], tmp)
        if rc == 0 and "Aucune observation" in out:
            print("[ABSENT] OK")
        else:
            print(f"[ABSENT] FAIL: rc={rc}, out={out}")
            sys.exit(1)

        # Cas 4: Invocation sans arguments (nominal par defaut)
        rc, out, err = run(tool, [], tmp)
        if rc == 0:
            print("[DEFAUT] OK")
        else:
            print(f"[DEFAUT] FAIL: rc={rc}, err={err}")
            sys.exit(1)

    finally:
        shutil.rmtree(tmp)

if __name__ == "__main__":
    test()
