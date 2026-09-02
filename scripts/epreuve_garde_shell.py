#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import subprocess
import json
import tempfile
import time

# Codes de retour réservés
CODE_OUTIL_INTROUVABLE = 127
CODE_ECHEC_TEST = 1

def run_garde(input_data, timeout=10):
    """Exécute nexus_garde_shell.py en sous-processus avec un timeout."""
    script_path = os.path.join("scripts", "nexus_garde_shell.py")
    if not os.path.exists(script_path):
        print(f"[ERREUR] Outil introuvable: {script_path}")
        sys.exit(CODE_OUTIL_INTROUVABLE)

    with tempfile.TemporaryDirectory() as tmpdir:
        env = os.environ.copy()
        env["TMPDIR"] = tmpdir

        proc = subprocess.Popen(
            [sys.executable, script_path],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=tmpdir,
            env=env
        )

        try:
            stdout, stderr = proc.communicate(input=input_data, timeout=timeout)
            return proc.returncode, stdout, stderr
        except subprocess.TimeoutExpired:
            proc.kill()
            return -1, "", "Timeout: l'outil n'a pas rendu la main dans les 10 secondes"

def verifier_nominal_bash():
    """Cas nominal: commande Bash valide (sans heredoc ni backtick)."""
    input_data = json.dumps({
        "tool_name": "Bash",
        "tool_input": {
            "command": "echo 'Commande valide sans heredoc ni backtick'"
        }
    })
    code, stdout, stderr = run_garde(input_data)
    if code != 0 or stdout.strip() != "":
        print("[ECHEC] NOMINAL_BASH: sortie inattendue ou code non nul")
        return False
    print("[OK  ] NOMINAL_BASH")
    return True

def verifier_refus_cas_a():
    """Cas inverse: heredoc Python avec antislash (doit refuser)."""
    input_data = json.dumps({
        "tool_name": "Bash",
        "tool_input": {
            "command": "python <<PYEOF\nimport re\npattern = re.compile(r\"[^\\\\]+\")\nPYEOF"
        }
    })
    code, stdout, stderr = run_garde(input_data)
    if code != 0:
        print("[ECHEC] REFUS_CAS_A: code non nul mais refus non JSON")
        return False

    try:
        response = json.loads(stdout)
        decision = response.get("hookSpecificOutput", {}).get("permissionDecision")
        if decision != "deny":
            print("[ECHEC] REFUS_CAS_A: permission non refusée")
            return False
    except json.JSONDecodeError:
        print("[ECHEC] REFUS_CAS_A: sortie non JSON valide")
        return False

    print("[OK  ] REFUS_CAS_A")
    return True

def verifier_refus_cas_b():
    """Cas inverse: backtick non échappé dans guillemets doubles (doit refuser)."""
    input_data = json.dumps({
        "tool_name": "Bash",
        "tool_input": {
            "command": 'echo "Commande avec `backtick` non échappé"'
        }
    })
    code, stdout, stderr = run_garde(input_data)
    if code != 0:
        print("[ECHEC] REFUS_CAS_B: code non nul mais refus non JSON")
        return False

    try:
        response = json.loads(stdout)
        decision = response.get("hookSpecificOutput", {}).get("permissionDecision")
        if decision != "deny":
            print("[ECHEC] REFUS_CAS_B: permission non refusée")
            return False
    except json.JSONDecodeError:
        print("[ECHEC] REFUS_CAS_B: sortie non JSON valide")
        return False

    print("[OK  ] REFUS_CAS_B")
    return True

def verifier_refus_cas_ps():
    """Cas inverse: here-string PowerShell avec fermeture indentée (doit refuser)."""
    input_data = json.dumps({
        "tool_name": "PowerShell",
        "tool_input": {
            "command": "@'\n  Contenu indente\n  '@  # Fermeture indentée"
        }
    })
    code, stdout, stderr = run_garde(input_data)
    if code != 0:
        print("[ECHEC] REFUS_CAS_PS: code non nul mais refus non JSON")
        return False

    try:
        response = json.loads(stdout)
        decision = response.get("hookSpecificOutput", {}).get("permissionDecision")
        if decision != "deny":
            print("[ECHEC] REFUS_CAS_PS: permission non refusée")
            return False
    except json.JSONDecodeError:
        print("[ECHEC] REFUS_CAS_PS: sortie non JSON valide")
        return False

    print("[OK  ] REFUS_CAS_PS")
    return True

def verifier_entree_malformee():
    """Entree malformee: JSON invalide (doit rendre la main sans planter)."""
    code, stdout, stderr = run_garde("JSON invalide")
    if code == -1:
        print("[ECHEC] ENTREE_MALFORMEE: timeout ou plantage")
        return False
    print("[OK  ] ENTREE_MALFORMEE")
    return True

def verifier_usage_manquant():
    """Invocation sans arguments requis: doit afficher usage et code non nul."""
    # Simule une entrée vide (pas de tool_name ni tool_input)
    input_data = json.dumps({})
    code, stdout, stderr = run_garde(input_data)
    if code == 0:
        print("[ECHEC] USAGE_MANQUANT: code nul malgré entrée incomplète")
        return False
    print("[OK  ] USAGE_MANQUANT")
    return True

def verifier_commande_legitime_powershell():
    """Commande PowerShell legitime (doit passer)."""
    input_data = json.dumps({
        "tool_name": "PowerShell",
        "tool_input": {
            "command": "@'\nContenu valide\n'@  # Fermeture en colonne zéro"
        }
    })
    code, stdout, stderr = run_garde(input_data)
    if code != 0 or stdout.strip() != "":
        print("[ECHEC] COMMANDE_LEGITIME_PS: refus ou sortie inattendue")
        return False
    print("[OK  ] COMMANDE_LEGITIME_PS")
    return True

def main():
    tests = [
        verifier_nominal_bash,
        verifier_refus_cas_a,
        verifier_refus_cas_b,
        verifier_refus_cas_ps,
        verifier_entree_malformee,
        verifier_usage_manquant,
        verifier_commande_legitime_powershell
    ]

    resultats = []
    for test in tests:
        try:
            resultats.append(test())
        except Exception as e:
            print(f"[ECHEC] {test.__name__}: exception non capturée - {str(e)}")
            resultats.append(False)

    if not all(resultats):
        sys.exit(CODE_ECHEC_TEST)

if __name__ == "__main__":
    main()
