#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test suite for scripts/nexus_garde_lecture.py

The suite checks:
* existence of the tool
* behaviour on a normal read then edit (allowed)
* behaviour on edit without prior read (denied)
* handling of malformed JSON (no crash)
* handling of missing required fields (no crash)
* that a write to a new file is allowed and recorded
All subprocesses are limited to ten seconds.
"""

import os
import sys
import json
import subprocess
import tempfile

# ----------------------------------------------------------------------
# Helper to run the tool in an isolated temporary directory
# ----------------------------------------------------------------------
def run_tool(stdin_data):
    """
    Execute nexus_garde_lecture.py with the given stdin_data.
    Returns (returncode, stdout, stderr).
    """
    tool_path = os.path.join("scripts", "nexus_garde_lecture.py")
    if not os.path.isfile(tool_path):
        # Tool not found - report special code 127 as per specification
        return 127, "", "Tool not found"

    # Use a temporary directory as the current working directory
    with tempfile.TemporaryDirectory() as tmpdir:
        proc = subprocess.Popen(
            [sys.executable, tool_path],
            cwd=tmpdir,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        try:
            out, err = proc.communicate(input=stdin_data, timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            return -1, "", "Timeout"
        return proc.returncode, out, err

# ----------------------------------------------------------------------
# Verification helpers
# ----------------------------------------------------------------------
def expect_no_output(code, out, err):
    return code == 0 and out.strip() == "" and err.strip() == ""

def expect_deny_json(code, out):
    if code != 0:
        return False
    try:
        data = json.loads(out)
        hook = data.get("hookSpecificOutput", {})
        return (
            hook.get("hookEventName") == "PreToolUse"
            and hook.get("permissionDecision") == "deny"
        )
    except Exception:
        return False

def print_result(name, ok):
    marker = "[OK  ]" if ok else "[FAIL]"
    print(f"{marker} {name}")

# ----------------------------------------------------------------------
# Test cases
# ----------------------------------------------------------------------
def main():
    all_ok = True

    # CASE1: nominal read then edit (allowed)
    with tempfile.TemporaryDirectory() as td:
        test_file = os.path.join(td, "test.txt")
        # create the file so that it exists
        with open(test_file, "w", encoding="utf-8") as f:
            f.write("data")
        # first call: Read (records the file)
        read_input = json.dumps({
            "tool_name": "Read",
            "tool_input": {"file_path": test_file}
        })
        rc, out, err = run_tool(read_input)
        ok = expect_no_output(rc, out, err)
        print_result("CASE1-READ", ok)
        all_ok = all_ok and ok

        # second call: Edit (should be allowed, no output)
        edit_input = json.dumps({
            "tool_name": "Edit",
            "tool_input": {"file_path": test_file}
        })
        rc, out, err = run_tool(edit_input)
        ok = expect_no_output(rc, out, err)
        print_result("CASE1-EDIT", ok)
        all_ok = all_ok and ok

    # CASE2: edit without prior read (should deny)
    with tempfile.TemporaryDirectory() as td:
        test_file = os.path.join(td, "new.txt")
        # create the file but do not read it first
        with open(test_file, "w", encoding="utf-8") as f:
            f.write("content")
        edit_input = json.dumps({
            "tool_name": "Edit",
            "tool_input": {"file_path": test_file}
        })
        rc, out, err = run_tool(edit_input)
        ok = expect_deny_json(rc, out)
        print_result("CASE2", ok)
        all_ok = all_ok and ok

    # CASE3: malformed JSON (should not crash, no output)
    rc, out, err = run_tool("this is not json")
    ok = expect_no_output(rc, out, err)
    print_result("CASE3", ok)
    all_ok = all_ok and ok

    # CASE4: missing required fields (no file_path) (should not crash)
    missing_input = json.dumps({
        "tool_name": "Edit",
        "tool_input": {}
    })
    rc, out, err = run_tool(missing_input)
    ok = expect_no_output(rc, out, err)
    print_result("CASE4", ok)
    all_ok = all_ok and ok

    # CASE5: write to a new file (allowed, no output) and second edit allowed
    with tempfile.TemporaryDirectory() as td:
        new_file = os.path.join(td, "brandnew.txt")
        # first edit on non-existent file (allowed)
        edit_input = json.dumps({
            "tool_name": "Edit",
            "tool_input": {"file_path": new_file}
        })
        rc, out, err = run_tool(edit_input)
        ok1 = expect_no_output(rc, out, err)
        # second edit on the same file (now recorded) should also be allowed
        rc, out, err = run_tool(edit_input)
        ok2 = expect_no_output(rc, out, err)
        ok = ok1 and ok2
        print_result("CASE5", ok)
        all_ok = all_ok and ok

    # Exit with non-zero if any test failed
    sys.exit(0 if all_ok else 1)

if __name__ == "__main__":
    main()
