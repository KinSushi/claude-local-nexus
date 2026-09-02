import os
import sys
import subprocess
import tempfile
import textwrap

# ----------------------------------------------------------------------
# Helper functions (ASCII only, no non-ASCII punctuation)
# ----------------------------------------------------------------------
def run_tool(args, cwd):
    """Run the tool in a subprocess, return (rc, out)."""
    proc = subprocess.run(
        [sys.executable, tool_path] + args,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        encoding="utf-8",
        errors="replace",
        timeout=10,
    )
    return proc.returncode, proc.stdout

def report(case, ok, msg=""):
    """Print a line for the test harness."""
    if ok:
        print(f"[{case}]")
    else:
        print(f"[{case}] {msg}")

# ----------------------------------------------------------------------
# 1. Verify that the tool file exists
# ----------------------------------------------------------------------
if len(sys.argv) < 2:
    sys.stderr.write("Missing path to tool\n")
    sys.exit(3)  # reserved code for missing argument

tool_path = sys.argv[1]

if not os.path.isfile(tool_path):
    sys.stderr.write(f"Tool not found: {tool_path}\n")
    sys.exit(3)

# ----------------------------------------------------------------------
# 2. Prepare a temporary directory that mimics the repository layout
# ----------------------------------------------------------------------
with tempfile.TemporaryDirectory() as tmpdir:
    # Copy the tool into the temporary directory
    tool_name = os.path.basename(tool_path)
    tmp_tool = os.path.join(tmpdir, tool_name)
    with open(tool_path, "r", encoding="utf-8") as src, open(tmp_tool, "w", encoding="utf-8") as dst:
        dst.write(src.read())

    # Create a dummy target script (will be ignored by the tool because it
    # expects a nexus_agent module that is not present)
    dummy_target = os.path.join(tmpdir, "dummy_target.py")
    with open(dummy_target, "w", encoding="utf-8") as f:
        f.write("# dummy script\n")

    # ------------------------------------------------------------------
    # Sub-test A : invocation without arguments (should show usage)
    # ------------------------------------------------------------------
    rc, out = run_tool([], tmpdir)
    ok = rc != 0 and "usage:" in out.lower()
    report("A", ok, f"expected usage message, rc={rc}")

    # ------------------------------------------------------------------
    # Sub-test B : nominal case - no targets (tool returns code 2)
    # ------------------------------------------------------------------
    rc, out = run_tool([], tmpdir)
    ok = rc == 2 and "no targets to process." in out.lower()
    report("B", ok, f"expected no-target message, rc={rc}")

    # ------------------------------------------------------------------
    # Sub-test C : provide a non-existent file via --file (should fail)
    # ------------------------------------------------------------------
    rc, out = run_tool(["--file", "nonexistent.txt"], tmpdir)
    # The tool will raise FileNotFoundError; we only check that it does not
    # return 0 and that the traceback appears in the output.
    ok = rc != 0 and "filenotfounderror" in out.lower()
    report("C", ok, f"expected file-not-found error, rc={rc}")

    # ------------------------------------------------------------------
    # Sub-test D : malformed entry in file list (empty line)
    # ------------------------------------------------------------------
    list_path = os.path.join(tmpdir, "list.txt")
    with open(list_path, "w", encoding="utf-8") as f:
        f.write("\n")  # empty line only
    rc, out = run_tool(["--file", list_path], tmpdir)
    ok = rc == 2 and "no targets to process." in out.lower()
    report("D", ok, f"expected graceful handling of empty list, rc={rc}")

    # ------------------------------------------------------------------
    # Sub-test E : invoke with a valid file list containing the dummy target
    # ------------------------------------------------------------------
    with open(list_path, "w", encoding="utf-8") as f:
        f.write(dummy_target + "\n")
    rc, out = run_tool(["--file", list_path, "--max-cibles", "0"], tmpdir)
    # With --max-cibles 0 the tool should process nothing and exit with code 2
    ok = rc == 2 and "no targets to process." in out.lower()
    report("E", ok, f"expected early exit with max-cibles=0, rc={rc}")

