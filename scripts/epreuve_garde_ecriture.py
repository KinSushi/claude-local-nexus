# -*- coding: utf-8 -*-
import os
import sys
import json
import tempfile
import subprocess
import shutil

GARDE_PATH = os.path.join(os.path.dirname(__file__), "scripts", "nexus_garde_ecriture.py")
PROTECTED_PATHS = ["/protected/file.txt", "/var/nexus/hook.json"]

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
    passed = (
        (expected_outcome == "REFUSE" and returncode != 0) or
        (expected_outcome == "PASS" and returncode == 0)
    )
    if expected_outcome == "REFUSE":
        passed = passed and (expected_reason in (stdout + stderr))

    status = "OK  " if passed else "RATE"
    print(f"  [{status}] {name}")
    if not passed:
        print(f"      Sortie: {stdout.strip()}")
        print(f"      Erreur: {stderr.strip()}")
        print(f"      Code: {returncode}")
    return passed

def main():
    with tempfile.TemporaryDirectory() as tmpdir:
        os.chdir(tmpdir)
        protected_file = os.path.join(tmpdir, "protected", "file.txt")
        os.makedirs(os.path.dirname(protected_file), exist_ok=True)
        with open(protected_file, "w") as f:
            f.write("dummy")

        global PROTECTED_PATHS
        PROTECTED_PATHS = [protected_file]

        cases = [
            ("UN: Refus écriture protégée", {
                "tool_name": "bash",
                "command_line": f"echo test > {protected_file}"
            }, "REFUSE", "chemin protégé"),
            ("DEUX: Écriture non protégée", {
                "tool_name": "bash",
                "command_line": "echo test > /tmp/safe.txt"
            }, "PASS"),
            ("TROIS: Lecture seule", {
                "tool_name": "bash",
                "command_line": "cat /etc/passwd"
            }, "PASS"),
            ("QUATRE: Heredoc (indéterminé)", {
                "tool_name": "bash",
                "command_line": "cat << EOF"
            }, "PASS"),
            ("CINQ: JSON invalide", "invalid json", "PASS"),
            ("CINQ: Entrée vide", "", "PASS"),
            ("CINQ: Outil non jugé", {
                "tool_name": "unknown_tool",
                "command_line": "echo test > /tmp/safe.txt"
            }, "PASS"),
        ]

        failures = 0
        for name, input_json, *rest in cases:
            expected_outcome = rest[0]
            expected_reason = rest[1] if len(rest) > 1 else None
            if not test_case(name, json.dumps(input_json) if isinstance(input_json, dict) else input_json, expected_outcome, expected_reason):
                failures += 1

        print("")
        if failures:
            print(f"Échec: {failures} cas")
            sys.exit(1)
        print("Tous les cas passés")

if __name__ == "__main__":
    main()
