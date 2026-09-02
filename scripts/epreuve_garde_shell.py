import os, sys, json, subprocess, pathlib, time

def _tool_path():
    return os.path.join(os.path.dirname(__file__), "scripts", "nexus_garde_shell.py")

def _ensure_tool():
    p = _tool_path()
    if not os.path.isfile(p):
        print("[FAIL] Tool not found at", p)
        sys.exit(3)
    return p

def _run(payload):
    exe = sys.executable
    tool = _ensure_tool()
    try:
        res = subprocess.run([exe, tool],
                             input=payload.encode("utf-8"),
                             stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE,
                             timeout=10)
    except subprocess.TimeoutExpired:
        print("[FAIL] Tool timeout")
        sys.exit(1)
    return res

def _denied(out):
    try:
        data = json.loads(out)
        return data.get("hookSpecificOutput", {}).get("permissionDecision") == "deny"
    except Exception:
        return False

def _test_nominal():
    cmd = "echo hello"
    payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": cmd}})
    r = _run(payload)
    if r.returncode != 0:
        print("[FAIL] Nominal non-zero exit", r.returncode)
        sys.exit(1)
    if _denied(r.stdout.decode()):
        print("[FAIL] Nominal denied")
        sys.exit(1)
    print("[OK] Nominal accepted")

def _test_case_a():
    back = chr(92)                     # backslash character
    nl = chr(10)                        # newline
    cmd = "cat <<PYEOF" + nl + "print('test" + back + "n')" + nl + "PYEOF"
    payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": cmd}})
    r = _run(payload)
    if not _denied(r.stdout.decode()):
        print("[FAIL] Case A not denied")
        sys.exit(1)
    print("[OK] Case A denied")

def _test_case_b():
    cmd = 'echo "run `ls`"'
    payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": cmd}})
    r = _run(payload)
    if not _denied(r.stdout.decode()):
        print("[FAIL] Case B not denied")
        sys.exit(1)
    print("[OK] Case B denied")

def _test_invalid_tool():
    payload = json.dumps({"tool_name": "Unknown", "tool_input": {"command": "echo hi"}})
    r = _run(payload)
    if r.stdout:
        print("[FAIL] Invalid tool produced output")
        sys.exit(1)
    print("[OK] Invalid tool ignored")

def main():
    _test_nominal()
    _test_case_a()
    _test_case_b()
    _test_invalid_tool()
    print("[ALL TESTS PASSED]")

if __name__ == "__main__":
    main()
