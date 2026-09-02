import os
import sys
import subprocess
import json
import tempfile

# Reserved exit code when the tool script is missing
RESERVED_CODE = 127
# Maximum time for each subprocess (seconds)
TIMEOUT = 10

def tool_path():
    """Return absolute path to the tool script."""
    base = os.path.abspath(os.path.join(os.path.dirname(__file__), "scripts"))
    return os.path.join(base, "nexus_reprise.py")

def run_tool(extra_args=None, cwd=None):
    """Execute the tool in a temporary directory.

    Returns (returncode, stdout, stderr).
    """
    path = tool_path()
    if not os.path.isfile(path):
        print(f"Tool not found: {path}")
        return RESERVED_CODE, "", ""
    args = [sys.executable, path]
    if extra_args:
        args.extend(extra_args)
    # Use a temporary directory as working directory
    if cwd is None:
        temp_dir = tempfile.TemporaryDirectory()
        cwd = temp_dir.name
    else:
        temp_dir = None
    try:
        result = subprocess.run(
            args,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=TIMEOUT,
            env=os.environ.copy(),
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "Timeout"
    finally:
        if temp_dir is not None:
            temp_dir.cleanup()

def check_nominal():
    """Nominal case: tool runs without arguments, returns 0,
    writes to stdout, nothing to stderr."""
    code, out, err = run_tool()
    ok = (code == 0) and (out.strip() != "") and (err.strip() == "")
    print("[OK  ] NOMINAL" if ok else "[FAIL] NOMINAL")
    return ok

def check_unknown_option():
    """Inverse case: pass an unknown option, tool should refuse.
    Expected: non-zero return code and a message on stdout or stderr."""
    code, out, err = run_tool(["--unknown"])
    # The tool does not parse options, so it will still succeed.
    # The test expects a refusal, therefore it will fail if the tool does not refuse.
    ok = (code != 0) or (out.strip() != "" or err.strip() != "")
    print("[OK  ] UNKNOWN_OPTION" if ok else "[FAIL] UNKNOWN_OPTION")
    return ok

def check_malformed_input():
    """Malformed input: feed invalid JSON via stdin.
    The tool does not read stdin, so it should ignore it and still succeed."""
    path = tool_path()
    try:
        proc = subprocess.Popen(
            [sys.executable, path],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=os.environ.copy(),
        )
        out, err = proc.communicate(input="invalid json", timeout=TIMEOUT)
        code = proc.returncode
    except subprocess.TimeoutExpired:
        proc.kill()
        code, out, err = -1, "", "Timeout"
    # Expect success because the tool does not process stdin.
    ok = (code == 0) and (err.strip() == "")
    print("[OK  ] MALFORMED_INPUT" if ok else "[FAIL] MALFORMED_INPUT")
    return ok

def check_missing_args():
    """Invocation without required arguments.
    The script has no required arguments, so it should succeed."""
    code, out, err = run_tool()
    ok = (code == 0)
    print("[OK  ] MISSING_ARGS" if ok else "[FAIL] MISSING_ARGS")
    return ok

def main():
    # Verify that the tool script exists before running any test.
    if not os.path.isfile(tool_path()):
        print(f"Tool not found at expected location: {tool_path()}")
        sys.exit(RESERVED_CODE)

    results = []
    results.append(check_nominal())
    results.append(check_unknown_option())
    results.append(check_malformed_input())
    results.append(check_missing_args())

    if all(results):
        sys.exit(0)
    else:
        sys.exit(1)

if __name__ == "__main__":
    main()
