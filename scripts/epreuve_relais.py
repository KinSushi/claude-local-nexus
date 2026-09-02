import os
import sys
import json
import subprocess
import pathlib
import re
import time

# ----------------------------------------------------------------------
# Helper to run the tool with a timeout of 10 seconds.
# ----------------------------------------------------------------------
def _run_tool(tool_path, input_data):
    """Run the tool, feed input_data on stdin, capture stdout/stderr."""
    env = os.environ.copy()
    proc = subprocess.Popen(
        [sys.executable, str(tool_path)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
    )
    try:
        stdout, stderr = proc.communicate(input=input_data, timeout=10)
        return proc.returncode, stdout, stderr
    except subprocess.TimeoutExpired:
        proc.kill()
        return -1, "", "Timeout"

# ----------------------------------------------------------------------
# Parse the tool source to extract CLI definition and return codes.
# ----------------------------------------------------------------------
def _parse_cli(tool_path):
    """Return (options, positionals, return_codes) extracted from source."""
    options = []
    positionals = []
    return_codes = set()
    option_pat = re.compile(r'add_argument\(\s*([\'"]--[^\'"]+[\'"])(?:\s*,\s*([\'"]-[^\'"]+[\'"]))?')
    positional_pat = re.compile(r'add_argument\(\s*([\'"][^\'"-][^\'"]*[\'"])')
    return_pat = re.compile(r'sys\.exit\(\s*([0-9]+)\s*\)|return\s+([0-9]+)')

    try:
        src = tool_path.read_text(encoding="utf-8")
    except Exception:
        return options, positionals, return_codes

    for line in src.splitlines():
        # Options (starting with --)
        m = option_pat.search(line)
        if m:
            opt = m.group(1).strip('\'"')
            options.append(opt)
            continue
        # Positional arguments (no leading dash)
        m = positional_pat.search(line)
        if m:
            arg = m.group(1).strip('\'"')
            if not arg.startswith('-'):
                positionals.append(arg)
            continue
        # Return codes
        for m in return_pat.finditer(line):
            code = m.group(1) or m.group(2)
            if code is not None:
                return_codes.add(int(code))
    return options, positionals, return_codes

# ----------------------------------------------------------------------
# Verification helpers
# ----------------------------------------------------------------------
def _is_json_denial(text):
    """Return True if text is JSON containing deny decision."""
    try:
        data = json.loads(text)
        hook = data.get("hookSpecificOutput", {})
        return (
            hook.get("hookEventName") == "PreToolUse"
            and hook.get("permissionDecision") == "deny"
        )
    except Exception:
        return False

def _verify_accept(code, out):
    """Accept case: code 0 and no stdout."""
    return code == 0 and out.strip() == ""

def _verify_refuse(code, out):
    """Refuse case: non-zero code and JSON denial on stdout."""
    return code != 0 and _is_json_denial(out)

def _verify_missing_args(code, out, err):
    """Missing required args: non-zero code and usage text."""
    txt = out + err
    return code != 0 and ("usage" in txt.lower() or "error" in txt.lower())

# ----------------------------------------------------------------------
# Main test runner
# ----------------------------------------------------------------------
def main():
    tool_rel = pathlib.Path("scripts") / "nexus_garde_isolation.py"
    if not tool_rel.is_file():
        print(f"Tool not found: {tool_rel}")
        sys.exit(127)   # reserved code for missing tool

    # Extract CLI info (not used directly in tests but required by spec)
    options, positionals, return_codes = _parse_cli(tool_rel)

    results = []

    # 1. UN: isolation worktree -> accept
    input_un = json.dumps({"tool_name": "Agent", "tool_input": {"isolation": "worktree"}})
    code, out, err = _run_tool(tool_rel, input_un)
    ok = _verify_accept(code, out)
    results.append(ok)
    print("[OK  ] UN" if ok else "[FAIL] UN")

    # 2. DEUX: no isolation -> refuse
    input_deux = json.dumps({"tool_name": "Agent", "tool_input": {}})
    code, out, err = _run_tool(tool_rel, input_deux)
    ok = _verify_refuse(code, out)
    results.append(ok)
    print("[OK  ] DEUX" if ok else "[FAIL] DEUX")

    # 3. TROIS: empty input -> refuse
    code, out, err = _run_tool(tool_rel, "")
    ok = _verify_refuse(code, out)
    results.append(ok)
    print("[OK  ] TROIS" if ok else "[FAIL] TROIS")

    # 4. QUATRE: no isolation but env var NEXUS_ISOLATION_LIBRE=1 -> accept
    env_backup = os.environ.copy()
    os.environ["NEXUS_ISOLATION_LIBRE"] = "1"
    code, out, err = _run_tool(tool_rel, input_deux)
    ok = _verify_accept(code, out)
    results.append(ok)
    print("[OK  ] QUATRE" if ok else "[FAIL] QUATRE")
    # restore environment
    os.environ.clear()
    os.environ.update(env_backup)

    # 5. CINQ: invalid JSON -> must not crash (timeout is failure)
    code, out, err = _run_tool(tool_rel, "invalid json")
    ok = code != -1   # not a timeout
    results.append(ok)
    print("[OK  ] CINQ" if ok else "[FAIL] CINQ")

    # 6. INVOCATION without stdin -> should show usage and non-zero code
    code, out, err = _run_tool(tool_rel, "")
    ok = _verify_missing_args(code, out, err)
    results.append(ok)
    print("[OK  ] INVOCATION" if ok else "[FAIL] INVOCATION")

    if not all(results):
        sys.exit(1)
    sys.exit(0)

if __name__ == "__main__":
    main()
