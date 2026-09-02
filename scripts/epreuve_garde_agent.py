import os
import sys
import json
import subprocess
from json import JSONDecodeError

TOOL_PATH = "scripts/nexus_garde_agent.py"

def run_tool(input_str):
    try:
        proc = subprocess.Popen(
            [sys.executable, TOOL_PATH],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        stdout, stderr = proc.communicate(input=input_str, timeout=10)
        return proc.returncode, stdout, stderr
    except subprocess.TimeoutExpired:
        proc.kill()
        return -1, "", "Timeout"

def check_refusal(output):
    try:
        data = json.loads(output)
        inner = data.get("hookSpecificOutput", {})
        return inner.get("permissionDecision") == "deny"
    except (JSONDecodeError, TypeError, AttributeError):
        return False

def main():
    if not os.path.exists(TOOL_PATH):
        print(f"Outil introuvable : {TOOL_PATH}")
        sys.exit(127)

    tests = [
        {
            "id": "UN",
            "input": json.dumps({
                "tool_input": {"subagent_type": "general-purpose", "model": "haiku"},
                "tool_name": "Agent"
            }),
            "expected_code": 2,
            "check_out": lambda o: check_refusal(o) and ("NEXUS_AGENT_LIBRE" in o or "NEXUS_JUSTIFIE_PAYANT" in o)
        },
        {
            "id": "DEUX",
            "input": json.dumps({
                "tool_input": {"subagent_type": "general-purpose"},
                "tool_name": "Agent"
            }),
            "expected_code": 2,
            "check_out": lambda o: check_refusal(o)
        },
        {
            "id": "TROIS",
            "input": json.dumps({
                "tool_input": {"subagent_type": "fork"},
                "tool_name": "Agent"
            }),
            "expected_code": 2,
            "check_out": lambda o: check_refusal(o)
        },
        {
            "id": "QUATRE",
            "input": "",
            "expected_code": 0,
            "check_out": lambda o: True
        },
        {
            "id": "CINQ",
            "input": "not a json",
            "expected_code": 0,
            "check_out": lambda o: True
        }
    ]

    failed = False
    for t in tests:
        code, out, err = run_tool(t["input"])
        success = (code == t["expected_code"]) and t["check_out"](out)
        print(f"[{'OK' if success else 'FAIL'}] {t['id']}")
        if not success:
            failed = True

    sys.exit(1 if failed else 0)

if __name__ == "__main__":
    main()
