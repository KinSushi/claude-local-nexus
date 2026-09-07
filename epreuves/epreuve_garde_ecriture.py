# -*- coding: utf-8 -*-
import os
import sys
import json
import subprocess

# ----------------------------------------------------------------------
# Chemins de base
# ----------------------------------------------------------------------
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GARDE_PATH = os.path.join(ROOT, "scripts", "nexus_garde_ecriture.py")
SETTINGS_PATH = os.path.join(ROOT, ".claude", "settings.json")

def charger_chemin_protege():
    """
    Lit <racine>/.claude/settings.json et retourne le premier chemin
    d'une règle Edit(...) ou Write(...) qui ne contient pas de caractère
    générique (*). Si aucun chemin ne correspond, retourne None.
    """
    try:
        with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"SKIP: impossible de lire les paramètres ({e})")
        return None

    deny_rules = data.get("permissions", {}).get("deny", [])
    for rule in deny_rules:
        # On ne garde que les règles Edit(...) ou Write(...)
        if rule.startswith("Edit(") or rule.startswith("Write("):
            # extraire le contenu entre parenthèses
            start = rule.find("(") + 1
            end = rule.find(")", start)
            if start == 0 or end == -1:
                continue
            path = rule[start:end].strip()
            # ignorer les chemins contenant un glob
            if "*" in path:
                continue
            # convertir en chemin absolu si nécessaire
            if not os.path.isabs(path):
                path = os.path.join(ROOT, path)
            return os.path.normpath(path)
    return None

def run_garde(input_json):
    proc = subprocess.Popen(
        [sys.executable, GARDE_PATH],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    stdout, stderr = proc.communicate(input_json)
    return proc.returncode, stdout, stderr

def test_case(name, input_json, expected_outcome, expected_reason=None):
    returncode, stdout, stderr = run_garde(input_json)

    # Le garde indique un refus en écrivant dans stdout un JSON contenant
    # "permissionDecision": "deny". Le code de retour est toujours 0.
    deny_present = '"permissionDecision": "deny"' in stdout

    if expected_outcome == "REFUSE":
        passed = deny_present
        if expected_reason:
            passed = passed and (expected_reason.lower() in stdout.lower())
    else:  # PASS
        passed = not deny_present

    status = "OK  " if passed else "RATE"
    print(f"  [{status}] {name}")
    if not passed:
        print(f"      Sortie: {stdout.strip()}")
        print(f"      Erreur: {stderr.strip()}")
        print(f"      Code: {returncode}")
    return passed

def main():
    # Exécuter depuis la racine du dépôt
    os.chdir(ROOT)

    protected_path = charger_chemin_protege()
    if not protected_path:
        print("SKIP: aucun chemin protégé concret trouvé dans les règles deny")
        sys.exit(0)

    cases = [
        ("UN: Refus écriture protégée", {
            "tool_name": "Bash",
            "tool_input": {"command": f"echo test > {protected_path}"}
        }, "REFUSE", "REFUS"),
        ("DEUX: Écriture non protégée", {
            "tool_name": "Bash",
            "tool_input": {"command": "echo test > /tmp/safe.txt"}
        }, "PASS"),
        ("TROIS: Lecture seule", {
            "tool_name": "Bash",
            "tool_input": {"command": "cat /etc/passwd"}
        }, "PASS"),
        ("QUATRE: Heredoc (indéterminé)", {
            "tool_name": "Bash",
            "tool_input": {"command": "cat << EOF"}
        }, "PASS"),
        ("CINQ: JSON invalide", "invalid json", "PASS"),
        ("SIX: Entrée vide", "", "PASS"),
        ("SEPT: Outil non jugé", {
            "tool_name": "unknown_tool",
            "tool_input": {"command": "echo test > /tmp/safe.txt"}
        }, "PASS"),
    ]

    failures = 0
    for name, input_json, *rest in cases:
        expected_outcome = rest[0]
        expected_reason = rest[1] if len(rest) > 1 else None
        json_payload = json.dumps(input_json) if isinstance(input_json, dict) else input_json
        if not test_case(name, json_payload, expected_outcome, expected_reason):
            failures += 1

    print("")
    if failures:
        print(f"Échec: {failures} cas")
        sys.exit(1)
    print("Tous les cas passés")

if __name__ == "__main__":
    main()