import os
import sys
import subprocess
import tempfile

TOOL_PATH = "scripts/nexus_fonctions.py"
TIMEOUT = 10

def run_tool(args, stdin_data=None, env_vars=None):
    """Execute the tool with given args and optional stdin."""
    if not os.path.exists(TOOL_PATH):
        print(f"Tool not found: {TOOL_PATH}")
        return 127, "", ""
    env = os.environ.copy()
    if env_vars:
        env.update(env_vars)
    cmd = [sys.executable, TOOL_PATH] + args
    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env
    )
    try:
        out, err = proc.communicate(input=stdin_data, timeout=TIMEOUT)
    except subprocess.TimeoutExpired:
        proc.kill()
        return -1, "", "Timeout"
    return proc.returncode, out, err

def verify(name, args, expected_code, check_msg=None, stdin_data=None):
    """Run a single test and print a line with a bracketed prefix."""
    code, out, err = run_tool(args, stdin_data)
    success = (code == expected_code)
    if check_msg and success and check_msg not in out and check_msg not in err:
        success = False
    marker = "[OK]" if success else "[FAIL]"
    print(f"{marker} {name}")
    return success

def write_file(path, content):
    """Write content (list of lines) to a file."""
    with open(path, "w", encoding="utf-8") as f:
        f.writelines(content)

def main():
    results = []

    # Case 1: nominal operation, should return 0
    with tempfile.TemporaryDirectory() as tmpdir:
        target = os.path.join(tmpdir, "target.py")
        blocks = os.path.join(tmpdir, "blocks.txt")
        # simple target file with one function
        write_file(target, [
            "def hello():\n",
            "    print('old')\n",
            "\n",
            "if __name__ == '__main__':\n",
            "    hello()\n"
        ])
        # block that replaces hello
        write_file(blocks, [
            "@@FONCTION hello@@\n",
            "def hello():\n",
            "    print('new')\n",
            "@@FIN@@\n"
        ])
        args = ["--cible", target, "--blocs", blocks, "--simuler"]
        results.append(verify("CASE1_NOMINAL", args, 0))

    # Case 2: missing required argument --cible, should fail with non-zero code
    args = ["--blocs", "dummy.txt"]
    results.append(verify("CASE2_MISSING_CIBLE", args, 2, check_msg="error"))

    # Case 3: target file with syntax error, tool should return non-zero
    with tempfile.TemporaryDirectory() as tmpdir:
        target = os.path.join(tmpdir, "bad.py")
        blocks = os.path.join(tmpdir, "blocks.txt")
        write_file(target, [
            "def broken(\n",   # syntax error
            "    pass\n"
        ])
        write_file(blocks, [
            "@@FONCTION broken@@\n",
            "def broken():\n",
            "    pass\n",
            "@@FIN@@\n"
        ])
        args = ["--cible", target, "--blocs", blocks]
        results.append(verify("CASE3_SYNTAX_ERROR", args, 1, check_msg="Erreur"))

    # Case 4: invoke tool with no arguments, should show usage and non-zero code
    results.append(verify("CASE4_NO_ARGS", [], 2, check_msg="usage"))

    # Case 5: tool file missing, should return reserved code 127
    original_path = TOOL_PATH
    try:
        # rename temporarily if it exists
        if os.path.exists(original_path):
            missing_path = original_path + ".bak"
            os.rename(original_path, missing_path)
        results.append(verify("CASE5_TOOL_MISSING", [], 127))
    finally:
        # restore
        if os.path.exists(missing_path):
            os.rename(missing_path, original_path)

    if not all(results):
        sys.exit(1)

if __name__ == "__main__":
    main()
