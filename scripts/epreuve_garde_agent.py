import os
import sys
import json
import subprocess
import tempfile
import shutil

TOOL_PATH = "scripts/nexus_garde_agent.py"

def run_tool(input_data, env=None):
    """Lance l'outil en sous-processus et capture la sortie."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # On ne copie pas l'outil dans le tmpdir pour garder le chemin relatif
        # mais on execute dans le tmpdir pour isoler l'environnement.
        process = subprocess.Popen(
            [sys.executable, TOOL_PATH],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env if env is not None else os.environ.copy(),
            cwd=tmpdir
        )
        stdout, stderr = process.communicate(input=json.dumps(input_data))
        return process.returncode, stdout, stderr

def main():
    if not os.path.exists(TOOL_PATH):
        print(f"Outil introuvable : {TOOL_PATH}")
        sys.exit(127)

    tests = [
        {
            "name": "NOMINAL",
            "input": {"tool_name": "Agent", "tool_input": {"model": "gpt-4o-mini"}},
            "expected_code": 0,
            "desc": "Modele gratuit autorisé"
        },
        {
            "name": "REFUS_PAYANT",
            "input": {"tool_name": "Agent", "tool_input": {"model": "sonnet"}},
            "expected_code": 2,
            "desc": "Refus modele facture sans justification"
        },
        {
            "name": "MALFORMEE",
            "input": "ceci n'est pas un json",
            "expected_code": 0,
            "desc": "Entree malformee ne fait pas planter l'outil"
        },
        {
            "name": "ARG_MANQUANTS",
            "input": {}, 
            "expected_code": 0, # Le code source rend 0 si tool_name absent
            "desc": "Invocation sans arguments requis"
        },
        {
            "name": "PASSE_JUSTIFIE",
            "input": {
                "tool_name": "Agent", 
                "tool_input": {"model": "opus"},
                "prompt": "NEXUS_JUSTIFIE_PAYANT besoin de raisonnement"
            },
            "expected_code": 0,
            "desc": "Garde laisse passer avec justification"
        },
        {
            "name": "REFUS_FORK",
            "input": {"tool_name": "Agent", "tool_input": {"subagent_type": "fork"}},
            "expected_code": 2,
            "desc": "Refus type fork"
        }
    ]

    # Cas special pour l'invocation sans arguments (test de l'usage)
    # Le script actuel ne prend pas d'args sys.argv, il lit stdin.
    # On teste donc un JSON vide ou invalide.

    failures = 0
    for t in tests:
        # Gestion du cas malformee (on envoie une string au lieu d'un dict)
        input_val = t["input"]
        if isinstance(input_val, str):
            # On simule l'envoi brut
            process = subprocess.Popen(
                [sys.executable, TOOL_PATH],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, cwd=tempfile.mkdtemp()
            )
            code, out, err = process.communicate(input=input_val)
        else:
            code, out, err = run_tool(input_val)

        success = (code == t["expected_code"])
        
        # Pour les refus, on verifie que le message nomme le probleme
        if t["expected_code"] != 0 and success:
            if "refuse" not in out.lower() and "refuse" not in err.lower():
                success = False

        print(f"[{'OK' if success else 'FAIL'}] {t['name']} : {t['desc']}")
        if not success:
            failures += 1

    if failures > 0:
        sys.exit(1)
    sys.exit(0)

if __name__ == "__main__":
    main()
