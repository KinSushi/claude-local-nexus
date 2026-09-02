import subprocess
import sys
import os
import json
import tempfile
import shutil

def run_tool(args, cwd, env=None):
    cmd = [sys.executable, "scripts/nexus_posterior.py"] + args
    try:
        proc = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=10,
            env=env
        )
        return proc.returncode, proc.stdout, proc.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "L'outil n'a pas rendu la main"
    except Exception as e:
        return -1, "", f"Erreur execution: {str(e)}"

def test():
    tool_path = "scripts/nexus_posterior.py"
    if not os.path.isfile(tool_path):
        print(f"[FAIL] Fichier introuvable: {tool_path}")
        sys.exit(127)

    tmp_dir = tempfile.mkdtemp()
    try:
        # Setup: create a dummy .nexus structure in tmp_dir
        nexus_dir = os.path.join(tmp_dir, ".nexus", "temperature")
        os.makedirs(nexus_dir)
        obs_file = os.path.join(nexus_dir, "observations.jsonl")
        
        # Data: 6 obs for llama (measured), 3 for mistral (insufficient), 1 malformed
        data = [
            {"model": "llama", "temperature": 0.1, "debit_jps": 10.0, "duree_ms": 100, "tronquee": False, "repli": "0"},
            {"model": "llama", "temperature": 0.1, "debit_jps": 12.0, "duree_ms": 110, "tronquee": False, "repli": "0"},
            {"model": "llama", "temperature": 0.1, "debit_jps": 11.0, "duree_ms": 105, "tronquee": True, "repli": "0"},
            {"model": "llama", "temperature": 0.1, "debit_jps": 10.5, "duree_ms": 102, "tronquee": False, "repli": "1"},
            {"model": "llama", "temperature": 0.1, "debit_jps": 11.5, "duree_ms": 108, "tronquee": False, "repli": "0"},
            {"model": "llama", "temperature": 0.1, "debit_jps": 11.0, "duree_ms": 105, "tronquee": False, "repli": "0"},
            {"model": "mistral", "temperature": 0.2, "debit_jps": 5.0, "duree_ms": 200, "tronquee": False, "repli": "0"},
            {"model": "mistral", "temperature": 0.2, "debit_jps": 6.0, "duree_ms": 210, "tronquee": False, "repli": "0"},
            {"model": "mistral", "temperature": 0.2, "debit_jps": 5.5, "duree_ms": 205, "tronquee": False, "repli": "0"},
            "INVALID JSON LINE",
            {"model": "mistral", "temperature": 0.2} # Missing fields
        ]
        with open(obs_file, "w", encoding="utf-8") as f:
            for line in data:
                if isinstance(line, dict):
                    f.write(json.dumps(line) + "\n")
                else:
                    f.write(line + "\n")

        # Case 1: Nominal (Text)
        rc, out, err = run_tool([], tmp_dir)
        if rc == 0 and "llama" in out and "mistral" in out and "mesuree" in out and "insuffisante" in out:
            print("[OK] Nominal text")
        else:
            print(f"[FAIL] Nominal text: rc={rc}, out={out[:50]}")
            sys.exit(1)

        # Case 2: JSON output
        rc, out, err = run_tool(["--json"], tmp_dir)
        try:
            res = json.loads(out)
            if rc == 0 and res["total"] == 9 and res["lignes_ignorees"] == 2:
                print("[OK] JSON output")
            else:
                print(f"[FAIL] JSON content: {res}")
                sys.exit(1)
        except Exception as e:
            print(f"[FAIL] JSON parse: {e}")
            sys.exit(1)

        # Case 3: Filter by model
        rc, out, err = run_tool(["--modele", "llama"], tmp_dir)
        if rc == 0 and "llama" in out and "mistral" not in out:
            print("[OK] Model filter")
        else:
            print(f"[FAIL] Model filter: {out[:50]}")
            sys.exit(1)

        # Case 4: Empty file (No observations)
        empty_dir = tempfile.mkdtemp()
        os.makedirs(os.path.join(empty_dir, ".nexus", "temperature"))
        rc, out, err = run_tool([], empty_dir)
        if rc == 0 and "Aucune observation" in out:
            print("[OK] Empty store")
        else:
            print(f"[FAIL] Empty store: {out[:50]}")
            sys.exit(1)

        # Case 5: No arguments (Usage/Help)
        # Note: The tool doesn't have a 'required' arg, so it runs. 
        # But if we pass an unknown arg, it should return non-zero.
        rc, out, err = run_tool(["--unknown"], tmp_dir)
        if rc != 0 and "unrecognized arguments" in err:
            print("[OK] Invalid argument")
        else:
            print(f"[FAIL] Invalid argument: rc={rc}, err={err[:50]}")
            sys.exit(1)

    finally:
        shutil.rmtree(tmp_dir)

if __name__ == "__main__":
    test()
    print("[ALL TESTS PASSED]")
    sys.exit(0)
