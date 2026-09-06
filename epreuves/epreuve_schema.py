import os
import sys
import subprocess
import tempfile

def run_tool(args, timeout=10):
    proc = subprocess.Popen(
        [sys.executable] + args,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    try:
        out, err = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        out, err = proc.communicate()
        return proc.returncode, out, err + "\nTimeout expired"
    return proc.returncode, out, err

def main():
    tool_path = os.path.abspath(os.path.join("scripts", "nexus_schema.py"))
    if not os.path.isfile(tool_path):
        print(f"[MISSING] Tool not found at {tool_path}")
        sys.exit(3)

    # Case 1: nominal success
    with tempfile.TemporaryDirectory() as td:
        json_file = os.path.join(td, "data.json")
        with open(json_file, "w", encoding="utf-8") as f:
            f.write('{"a": 1}')
        rc, out, err = run_tool([tool_path, json_file])
        if rc == 0 and json_file in out and "JSON" in out:
            print("[NOMINAL] OK")
        else:
            print(f"[NOMINAL] FAIL {rc}")

    # Case 2: tool must refuse (non-existent file)
    missing_file = os.path.join(td, "does_not_exist.json")
    rc, out, err = run_tool([tool_path, missing_file])
    if rc == 2 and "Aucun fichier n'a pu etre decrit." in err:
        print("[REFUSE] OK")
    else:
        print(f"[REFUSE] FAIL {rc}")

    # Case 3: mixed valid and malformed input
    with tempfile.TemporaryDirectory() as td2:
        good = os.path.join(td2, "good.json")
        bad = os.path.join(td2, "bad.json")
        with open(good, "w", encoding="utf-8") as f:
            f.write('{"b": true}')
        with open(bad, "w", encoding="utf-8") as f:
            f.write('not json')
        rc, out, err = run_tool([tool_path, good, bad])
        if rc == 1 and good in out and bad in out and "ERREUR" in out:
            print("[MIXED] OK")
        else:
            print(f"[MIXED] FAIL {rc}")

    # Case 4: invocation without arguments
    rc, out, err = run_tool([tool_path])
    if rc != 0 and ("usage:" in err or "usage:" in out):
        print("[NOARGS] OK")
    else:
        print(f"[NOARGS] FAIL {rc}")

if __name__ == "__main__":
    main()
