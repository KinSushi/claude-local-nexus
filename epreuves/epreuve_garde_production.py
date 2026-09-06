import os
import sys
import json
import subprocess

TOOL_PATH = "scripts/nexus_garde_production.py"

def run_tool(payload=None, env=None, args=None):
    current_env = os.environ.copy()
    if env:
        current_env.update(env)

    cmd = [sys.executable, TOOL_PATH]
    if args:
        cmd.extend(args)

    input_data = json.dumps(payload).encode("utf-8") if payload else None

    try:
        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=current_env
        )
        stdout, stderr = proc.communicate(input=input_data, timeout=10)
        return proc.returncode, stdout.decode("utf-8", "ignore"), stderr.decode("utf-8", "ignore")
    except subprocess.TimeoutExpired:
        proc.kill()
        return -1, "", "TIMEOUT"

def main():
    if not os.path.exists(TOOL_PATH):
        print("Outil introuvable : " + TOOL_PATH)
        sys.exit(127)

    cases = [
        ("UN", {"tool_name": "Write", "tool_input": {"file_path": "repo/main.py"}}, None, None, "deny"),
        ("DEUX", {"tool_name": "Write", "tool_input": {"file_path": "repo/doc.md"}}, None, None, "allow"),
        ("TROIS", {"tool_name": "Write", "tool_input": {"file_path": "tmp/main.py"}}, None, None, "allow"),
        ("QUATRE", {"tool_name": "Bash", "tool_input": {}}, None, None, "allow"),
        ("CINQ", {"tool_name": "Write", "tool_input": {"file_path": "repo/main.py"}}, {"NEXUS_PRODUCTION_LIBRE": "1"}, None, "allow"),
    ]

    for name, payload, env, args, expected in cases:
        rc, out, err = run_tool(payload, env, args)
        if expected == "deny":
            try:
                res = json.loads(out)
                inner = res.get("hookSpecificOutput", {})
                ok = (inner.get("hookEventName") == "PreToolUse" and
                      inner.get("permissionDecision") == "deny")
            except (json.JSONDecodeError, AttributeError, TypeError):
                ok = False
        else:
            ok = (not out)

        print(f"[{'OK' if ok else 'RATE'}] {name}")
        if not ok:
            sys.exit(1)

    # CAS REND_LA_MAIN: verifier que l'outil rend la main avant le delai
    rc, out, err = run_tool(payload=None, args=["--help"])
    ok_six = (rc != -1)  # rc == -1 indique un timeout
    if not ok_six:
        print("outil n'a pas rendu la main")
    print(f"[{'OK' if ok_six else 'RATE'}] REND_LA_MAIN")
    if not ok_six:
        sys.exit(1)

    sys.exit(0)

if __name__ == "__main__":
    main()
