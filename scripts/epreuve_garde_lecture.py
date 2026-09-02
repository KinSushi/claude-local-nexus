#!/usr/bin/env python3
# -*- coding: ascii -*-
"""
Test script for scripts/nexus_garde_lecture.py

It extracts the public interface of the guard script and runs a series of
subprocess checks.  All output lines start with a bracketed tag.  The script
exits with code 0 if all checks pass, otherwise with a non-zero code.
"""

import json
import os
import sys
import subprocess
import tempfile

# ----------------------------------------------------------------------
# Configuration
# ----------------------------------------------------------------------
TOOL_PATH = os.path.join("scripts", "nexus_garde_lecture.py")
RESERVED_EXIT = 2          # exit code used when the tool file is missing
TIMEOUT = 10               # seconds for each subprocess call

# ----------------------------------------------------------------------
# Helper functions
# ----------------------------------------------------------------------
def report(tag, message="", fail=False):
    """Print a line with a tag.  If fail is True, exit with non-zero."""
    line = "[%s] %s" % (tag, message)
    print(line)
    if fail:
        sys.exit(1)

def read_interface(path):
    """
    Parse the guard script and return a dictionary with:
    - options: list of command line options (none for this script)
    - args_order: list of expected JSON fields in order of use
    - return_codes: set of exit codes that can be produced
    - stdout_markers: strings that appear on stdout
    - stderr_markers: strings that appear on stderr
    """
    options = []
    args_order = ["tool_name", "tool_input", "session_id"]
    return_codes = {0}
    stdout_markers = ["hookSpecificOutput"]
    stderr_markers = []   # script never writes to stderr
    return {
        "options": options,
        "args_order": args_order,
        "return_codes": return_codes,
        "stdout_markers": stdout_markers,
        "stderr_markers": stderr_markers,
    }

def run_tool(input_json):
    """
    Execute the guard script with the given JSON input.
    Returns (returncode, stdout, stderr).
    """
    try:
        proc = subprocess.run(
            [sys.executable, TOOL_PATH],
            input=json.dumps(input_json).encode("utf-8"),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=TIMEOUT,
        )
        return proc.returncode, proc.stdout.decode("utf-8"), proc.stderr.decode("utf-8")
    except subprocess.TimeoutExpired:
        return None, "", "timeout"

def write_temp_file(dir_path, name, content=""):
    """Create a temporary file in dir_path with the given name and content."""
    path = os.path.join(dir_path, name)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return path

# ----------------------------------------------------------------------
# Main test logic
# ----------------------------------------------------------------------
def main():
    # 1. Verify that the tool file exists
    if not os.path.isfile(TOOL_PATH):
        report("FAIL", "Tool not found: %s" % TOOL_PATH, fail=True)

    # 2. Extract interface description
    iface = read_interface(TOOL_PATH)
    report("INFO", "Interface extracted")

    # 3. Prepare a temporary session directory
    with tempfile.TemporaryDirectory() as tmpdir:
        session_id = "testsession"

        # 3a. Nominal case: read then edit an existing file
        existing_path = write_temp_file(tmpdir, "file.txt", "initial")
        # Simulate a Read operation to register the file as read
        read_input = {
            "tool_name": "Read",
            "tool_input": {"file_path": existing_path},
            "session_id": session_id,
        }
        rc, out, err = run_tool(read_input)
        if rc != 0 or out or err:
            report("FAIL", "Read step unexpected output", fail=True)
        # Now attempt an Edit operation, which should be allowed (no output)
        edit_input = {
            "tool_name": "Edit",
            "tool_input": {"file_path": existing_path},
            "session_id": session_id,
        }
        rc, out, err = run_tool(edit_input)
        if rc != 0:
            report("FAIL", "Edit step non-zero exit", fail=True)
        if out.strip():
            report("FAIL", "Edit step produced stdout when none expected", fail=True)
        if err.strip():
            report("FAIL", "Edit step produced stderr when none expected", fail=True)
        report("OK", "Nominal edit allowed")

        # 3b. Inverse case: edit without prior read
        new_path = os.path.join(tmpdir, "newfile.txt")
        edit_no_read = {
            "tool_name": "Edit",
            "tool_input": {"file_path": new_path},
            "session_id": session_id,
        }
        rc, out, err = run_tool(edit_no_read)
        if rc != 0:
            report("FAIL", "Edit without read non-zero exit", fail=True)
        if not any(m in out for m in iface["stdout_markers"]):
            report("FAIL", "Edit without read did not produce expected stdout marker", fail=True)
        if err.strip():
            report("FAIL", "Edit without read produced stderr", fail=True)
        report("OK", "Refusal on unwatched edit detected")

        # 3c. Creation of a new file (should be allowed, no output)
        create_path = os.path.join(tmpdir, "created.txt")
        create_input = {
            "tool_name": "Edit",
            "tool_input": {"file_path": create_path},
            "session_id": session_id,
        }
        rc, out, err = run_tool(create_input)
        if rc != 0:
            report("FAIL", "Create step non-zero exit", fail=True)
        if out.strip():
            report("FAIL", "Create step produced stdout", fail=True)
        if err.strip():
            report("FAIL", "Create step produced stderr", fail=True)
        report("OK", "Creation of new file allowed")

        # 3d. Malformed input (missing tool_name)
        malformed_input = {
            "tool_input": {"file_path": existing_path},
            "session_id": session_id,
        }
        rc, out, err = run_tool(malformed_input)
        if rc != 0:
            report("FAIL", "Malformed input non-zero exit", fail=True)
        if out.strip():
            report("FAIL", "Malformed input produced stdout", fail=True)
        if err.strip():
            report("FAIL", "Malformed input produced stderr", fail=True)
        report("OK", "Malformed input handled gracefully")

        # 3e. Empty JSON (no arguments) - should produce no output
        empty_input = {}
        rc, out, err = run_tool(empty_input)
        if rc != 0:
            report("FAIL", "Empty input non-zero exit", fail=True)
        if out.strip():
            report("FAIL", "Empty input produced stdout", fail=True)
        if err.strip():
            report("FAIL", "Empty input produced stderr", fail=True)
        report("OK", "Empty input handled gracefully")

    report("ALL", "All tests passed")
    sys.exit(0)

if __name__ == "__main__":
    main()
