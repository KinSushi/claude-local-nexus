import os
import sys
import subprocess
import json
import tempfile
import shutil

def run_tool(input_data):
    tool_path = "scripts/nexus_garde_isolation.py"
    if not os.path.exists(tool_path):
        print(f"Outil introuvable: {tool_path}")
        sys.exit(127)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        proc = subprocess.Popen(
            [sys.executable, tool_path],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=tmpdir
        )
        stdout, stderr = proc.communicate(input=input_data)
        return proc.returncode, stdout, stderr

def test_case(name, payload, expected_code, check_msg=False):
    input_str = json.dumps(payload) if payload is not None else ""
    code, out, err = run_tool(input_str)
    
    success = (code == expected_code)
    if check_msg and success and code != 0:
        if "hookSpecificOutput" not in out:
            success = False
            
    marker = "[OK  ]" if success else "[RATE]"
    print(f"{marker} {name} : attendu={expected_code} obtenu={code}")
    return success

def main():
    cases = [
        ("NOMINAL: Agent avec isolation", 
         {"tool_name": "Agent", "tool_input": {"isolation": "worktree"}}, 0),
        
        ("INVERSE: Agent sans isolation", 
         {"tool_name": "Agent", "tool_input": {"isolation": "none"}}, 2, True),
        
        ("MALFORMEE: JSON invalide", 
         "not a json", 2, True),
        
        ("USAGE: Invocation vide", 
         None, 2, True),
        
        ("GARDE: Outil hors perimetre", 
         {"tool_name": "Bash", "tool_input": {}}, 0),
    ]
    
    # Special handling for "not a json" string vs dict
    results = []
    for name, payload, code, *extra in cases:
        check_msg = extra[0] if extra else False
        if isinstance(payload, str) and payload == "not a json":
            res = test_case(name, payload, code, check_msg)
        elif payload is None:
            res = test_case(name, None, code, check_msg)
        else:
            res = test_case(name, payload, code, check_msg)
        results.append(res)

    if not all(results):
        sys.exit(1)
    sys.exit(0)

if __name__ == "__main__":
    main()
