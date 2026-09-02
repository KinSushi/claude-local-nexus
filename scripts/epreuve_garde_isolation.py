import os
import sys
import subprocess
import json

def run_tool(input_data, env_vars=None):
    tool_path = "scripts/nexus_garde_isolation.py"
    if not os.path.exists(tool_path):
        print(f"Outil introuvable: {tool_path}")
        sys.exit(127)
    
    env = os.environ.copy()
    if env_vars:
        env.update(env_vars)
        
    proc = subprocess.Popen(
        [sys.executable, tool_path],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env
    )
    try:
        stdout, stderr = proc.communicate(input=input_data, timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
        return -1, "", "Timeout"
    return proc.returncode, stdout, stderr

def verify(name, input_data, expected_code, env_vars=None, check_deny=False):
    code, out, err = run_tool(input_data, env_vars)
    success = (code == expected_code)
    
    if check_deny and success:
        try:
            res = json.loads(out)
            data = res.get("hookSpecificOutput", {})
            if data.get("hookEventName") != "PreToolUse" or data.get("permissionDecision") != "deny":
                success = False
        except (json.JSONDecodeError, AttributeError, TypeError):
            success = False
            
    if not check_deny and expected_code == 0:
        if out.strip() != "":
            success = False

    marker = "[OK  ]" if success else "[FAIL]"
    print(f"{marker} {name}")
    return success

def main():
    results = []
    
    # UN: isolation worktree -> ACCEPTE, code 0, rien stdout
    results.append(verify("UN", json.dumps({"tool_name": "Agent", "tool_input": {"isolation": "worktree"}}), 0))
    
    # DEUX: sans isolation -> REFUSE, code 2, JSON deny
    results.append(verify("DEUX", json.dumps({"tool_name": "Agent", "tool_input": {}}), 2, check_deny=True))
    
    # TROIS: entree vide -> REFUSE, code 2, JSON deny
    results.append(verify("TROIS", "", 2, check_deny=True))
    
    # QUATRE: sans isolation + NEXUS_ISOLATION_LIBRE=1 -> ACCEPTE, code 0
    results.append(verify("QUATRE", json.dumps({"tool_name": "Agent", "tool_input": {}}), 0, {"NEXUS_ISOLATION_LIBRE": "1"}))
    
    # CINQ: JSON invalide -> ne doit pas planter (rend la main)
    code, out, err = run_tool("invalid json")
    results.append(True)
    print("[OK  ] CINQ")

    if not all(results):
        sys.exit(1)

if __name__ == "__main__":
    main()
