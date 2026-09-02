#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import sys
import json
import tempfile
import subprocess
from pathlib import Path

def verifier_fichier_existe(chemin):
    if not os.path.exists(chemin):
        print(f"[ERREUR] Fichier introuvable : {chemin}")
        sys.exit(2)

def lancer_garde(entree, timeout=10):
    cmd = [sys.executable, str(Path("scripts/nexus_garde_shell.py"))]
    try:
        proc = subprocess.run(
            cmd,
            input=json.dumps(entree).encode("utf-8"),
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=tempfile.gettempdir()
        )
        return proc.returncode, proc.stdout, proc.stderr
    except subprocess.TimeoutExpired:
        return None, "", f"[ERREUR] Timeout après {timeout} secondes"

def verifier_sortie(refus, code, stdout, attendu, cas):
    if refus:
        if code != 0:
            print(f"[ECHEC] {cas} : code de retour {code} (attendu 0)")
            return False
        if attendu not in stdout:
            print(f"[ECHEC] {cas} : motif de refus absent")
            return False
        print(f"[OK] {cas}")
        return True
    else:
        if code != 0:
            print(f"[ECHEC] {cas} : code non nul {code}")
            return False
        if stdout.strip():
            print(f"[ECHEC] {cas} : sortie inattendue")
            return False
        print(f"[OK] {cas}")
        return True

def main():
    chemin_garde = Path("scripts/nexus_garde_shell.py")
    verifier_fichier_existe(chemin_garde)

    cas = [
        {
            "nom": "Chemin nominal Bash - heredoc Python sans antislash",
            "entree": {
                "tool_name": "Bash",
                "tool_input": {"command": "python3 <<PY\nprint('Hello')\nPY"}
            },
            "refus": False,
            "attendu": ""
        },
        {
            "nom": "Cas A - heredoc Python avec antislash",
            "entree": {
                "tool_name": "Bash",
                "tool_input": {"command": "python3 <<PY\nre.compile(r\"[^\\\\\"]+\")\nPY"}
            },
            "refus": True,
            "attendu": "CAS A -- heredoc Python portant un antislash"
        },
        {
            "nom": "Cas B - accent grave non échappé entre doubles quotes",
            "entree": {
                "tool_name": "Bash",
                "tool_input": {"command": 'echo "Code avec `rm -rf` dangereux"'}
            },
            "refus": True,
            "attendu": "CAS B -- accent grave non echappe entre guillemets doubles"
        },
        {
            "nom": "Cas inverse - heredoc quoted (protégé)",
            "entree": {
                "tool_name": "Bash",
                "tool_input": {"command": "python3 <<'PY'\nre.compile(r\"[^\\\\\"]+\")\nPY"}
            },
            "refus": False,
            "attendu": ""
        },
        {
            "nom": "Cas inverse - accent grave échappé",
            "entree": {
                "tool_name": "Bash",
                "tool_input": {"command": 'echo "Code avec \\`safe\\`"'}
            },
            "refus": False,
            "attendu": ""
        },
        {
            "nom": "Cas inverse - outil non jugé (Python)",
            "entree": {
                "tool_name": "Python",
                "tool_input": {"command": "python3 <<PY\nre.compile(r\"[^\\\\\"]+\")\nPY"}
            },
            "refus": False,
            "attendu": ""
        },
        {
            "nom": "Cas PowerShell - here-string correcte",
            "entree": {
                "tool_name": "PowerShell",
                "tool_input": {"command": "@'\nWrite-Output \"Hello\"\n'@"}
            },
            "refus": False,
            "attendu": ""
        },
        {
            "nom": "Cas PS - here-string avec fermeture indentée",
            "entree": {
                "tool_name": "PowerShell",
                "tool_input": {"command": "@'\nWrite-Output \"Hello\"\n  '@"}
            },
            "refus": True,
            "attendu": "CAS PS -- here-string dont le delimiteur de FERMETURE est indente"
        },
        {
            "nom": "Commande sans arguments (usage)",
            "entree": {
                "tool_name": "Bash",
                "tool_input": {}
            },
            "refus": False,
            "attendu": ""
        },
        {
            "nom": "Commande legitime (laisser passer)",
            "entree": {
                "tool_name": "Bash",
                "tool_input": {"command": "echo 'Commande normale'"}
            },
            "refus": False,
            "attendu": ""
        }
    ]

    echecs = 0
    for c in cas:
        code, stdout, stderr = lancer_garde(c["entree"])
        if code is None:
            print(f"[ECHEC] {c['nom']} : {stderr}")
            echecs += 1
            continue
        if not verifier_sortie(c["refus"], code, stdout, c["attendu"], c["nom"]):
            echecs += 1

    if echecs > 0:
        sys.exit(1)
    print("[TOUS LES TESTS PASSES]")

if __name__ == "__main__":
    main()
