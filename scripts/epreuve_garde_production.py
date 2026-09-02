import os
import sys
import json
import subprocess
import tempfile
import shutil

TOOL_PATH = "scripts/nexus_garde_production.py"

def run_tool(payload, env=None):
    """Lance l'outil en sous-processus avec sys.executable."""
    input_data = json.dumps(payload).encode("utf-8")
    current_env = os.environ.copy()
    if env:
        current_env.update(env)
    
    proc = subprocess.Popen(
        [sys.executable, TOOL_PATH],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=current_env
    )
    stdout, stderr = proc.communicate(input=input_data)
    return proc.returncode, stdout.decode("utf-8", "ignore"), stderr.decode("utf-8", "ignore")

def main():
    if not os.path.exists(TOOL_PATH):
        print(f"Outil introuvable : {TOOL_PATH}")
        sys.exit(127)

    # On travaille dans un repertoire temporaire pour ne pas toucher au depot
    tmp_dir = tempfile.mkdtemp()
    try:
        # CAS 1: NOMINAL - Fichier non-code ou chemin temporaire (doit passer)
        # Le garde laisse passer silencieusement (stdout vide) et rend 0.
        payload1 = {"tool_name": "Write", "tool_input": {"file_path": "doc.md"}}
        rc, out, err = run_tool(payload1)
        print(f"[{'OK' if rc == 0 and not out else 'RATE'}] NOMINAL: Fichier Markdown")
        if rc != 0 or out: sys.exit(1)

        # CAS 2: INVERSE - Fichier code en production (doit refuser)
        # Doit rendre 0 (car le script capture l'erreur dans le JSON) mais 
        # le JSON doit contenir "deny" et la raison.
        payload2 = {"tool_name": "Write", "tool_input": {"file_path": "src/main.py"}}
        rc, out, err = run_tool(payload2)
        try:
            res = json.loads(out)
            decision = res["hookSpecificOutput"]["permissionDecision"]
            reason = res["hookSpecificOutput"]["permissionDecisionReason"]
            ok2 = (decision == "deny" and "fichier code source en production" in reason)
        except:
            ok2 = False
        print(f"[{'OK' if ok2 else 'RATE'}] INVERSE: Blocage code production")
        if not ok2: sys.exit(1)

        # CAS 3: MALFORMEE - JSON invalide (doit etre classee sans planter)
        # Le script rend 0 et écrit sur stderr.
        proc_mal = subprocess.Popen(
            [sys.executable, TOOL_PATH],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        rc, out, err = proc_mal.communicate(input=b"invalid json")
        print(f"[{'OK' if rc == 0 else 'RATE'}] MALFORMEE: JSON invalide")
        if rc != 0: sys.exit(1)

        # CAS 4: ARGUMENTS REQUIS - Invocation sans stdin (usage/erreur)
        # Le script attend un JSON sur stdin. S'il n'y a rien, json.load echoue.
        # Selon le code, il rend 0 et écrit "Anomalie: JSON illisible" sur stderr.
        proc_empty = subprocess.Popen(
            [sys.executable, TOOL_PATH],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        rc, out, err = proc_empty.communicate(input=b"")
        print(f"[{'OK' if rc == 0 else 'RATE'}] INVOKE: Entree vide")
        if rc != 0: sys.exit(1)

        # CAS 5: GARDE - Verifier qu'elle laisse passer via variable d'environnement
        payload5 = {"tool_name": "Write", "tool_input": {"file_path": "src/main.py"}}
        rc, out, err = run_tool(payload5, env={"NEXUS_PRODUCTION_LIBRE": "1"})
        print(f"[{'OK' if rc == 0 and not out else 'RATE'}] GARDE: Bypass via ENV")
        if rc != 0 or out: sys.exit(1)

    finally:
        shutil.rmtree(tmp_dir)

    sys.exit(0)

if __name__ == "__main__":
    main()
