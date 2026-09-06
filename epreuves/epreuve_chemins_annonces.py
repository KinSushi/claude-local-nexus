"""Module epreuve_chemins_annonces.
Protects against false absolute script paths announced by guard scripts.
It scans guard scripts in the scripts directory, feeds them a generic JSON
payload, parses their JSON output and checks any .py paths found in the
reason text.
Absolute paths that do not exist cause a failure, relative paths cause a
warning. The script reports one line per guard and a total count.
It also contains a self‑test for the path extraction function.
"""

import os
import sys
import json
import re
import subprocess

def extract_script_paths(text):
    """Return a list of non‑whitespace substrings ending with .py."""
    pattern = re.compile(r'\S+?\.py')
    return pattern.findall(text)

def _run_guard(guard_path, payload):
    """Run a guard script with the given JSON payload.
    Return (stdout_text, error) where error is None on success."""
    try:
        proc = subprocess.Popen(
            [sys.executable, guard_path],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        out, err = proc.communicate(input=payload, timeout=60)
        return out.strip(), None
    except subprocess.TimeoutExpired:
        proc.kill()
        return "", "timeout"
    except Exception as e:
        return "", str(e)

def main():
    # Determine repository root (parent of this script's directory)
    script_dir = os.path.abspath(os.path.join(os.path.dirname(__file__)))
    repo_root = os.path.abspath(os.path.join(script_dir, ".."))
    # Find guard scripts
    guard_files = [
        f for f in os.listdir(script_dir)
        if f.startswith("nexus_garde") and f.endswith(".py")
    ]

    # Prepare generic payload
    payload_dict = {
        "hook_event_name": "PreToolUse",
        "tool_name": "Write",
        "tool_input": {
            "file_path": __file__,
            "content": ""
        }
    }
    payload_json = json.dumps(payload_dict)

    total_fail = 0

    for guard in guard_files:
        guard_path = os.path.join(script_dir, guard)
        out_text, err = _run_guard(guard_path, payload_json)

        if err:
            verdict = f"{guard}: Erreur execution ({err})"
            print(verdict)
            total_fail += 1
            continue

        # Try to parse JSON output
        try:
            out_json = json.loads(out_text)
        except json.JSONDecodeError:
            # No JSON => no judgement
            print(f"{guard}: Aucun jugement")
            continue

        if not (isinstance(out_json, dict) and
                "hookSpecificOutput" in out_json and
                isinstance(out_json["hookSpecificOutput"], dict) and
                "permissionDecisionReason" in out_json["hookSpecificOutput"]):
            print(f"{guard}: Aucun jugement")
            continue

        reason = out_json["hookSpecificOutput"]["permissionDecisionReason"]
        paths = extract_script_paths(reason)

        guard_failed = False
        for p in paths:
            # Normalize path separators
            norm_path = os.path.normpath(p)
            if os.path.isabs(norm_path):
                if not os.path.exists(norm_path):
                    print(f"{guard}: Echec - {p}")
                    guard_failed = True
                    total_fail += 1
                else:
                    # absolute and exists -> ok, no message needed
                    pass
            else:
                print(f"{guard}: Avertissement - {p}")

        if not guard_failed and not paths:
            # No paths found, but JSON was valid
            print(f"{guard}: OK")

    print(f"Total: {total_fail} echec(s)")
    sys.exit(0 if total_fail == 0 else 1)

if __name__ == "__main__":
    # Self‑test for extract_script_paths
    test_with_path = "Error at /home/user/script.py line 10"
    test_without_path = "No path here"

    if not extract_script_paths(test_with_path):
        print("Controle muet echoue: path not detected")
        sys.exit(1)
    if extract_script_paths(test_without_path):
        print("Controle muet echoue: false positive")
        sys.exit(1)

    main()