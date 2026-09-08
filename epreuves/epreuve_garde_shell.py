#!/usr/bin/env python3
"""
Épreuve autonome du garde shell.

Cette script exécute quatre scénarios :
1. « nominal » :  `echo hello` – le garde doit **autoriser** (pas de *deny*).
2. « heredoc_backslash » : heredoc contenant un antislash – le garde doit **refuser** (*deny*).
3. « accent_grave » : accent grave entre guillemets doubles – le garde doit **refuser** (*deny*).
4. « invalid_tool » : outil inconnu – le garde doit **ignorer** (aucune sortie).

Le garde est recherché à la racine du dépôt :
    RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    GARDÉ = os.path.join(RACINE, "scripts", "nexus_garde_shell.py")

Les résultats sont imprimés au format attendu par la suite :
    "[OK  ] <nom> : <detail>"
    "[RATE] <nom> : <detail>"
Deux espaces suivent « OK ». Le script ne s’arrête pas au premier échec ; il
termine avec le code 0 si tous les tests passent, sinon 1.
"""

import json
import os
import subprocess
import sys
from typing import Optional

# --------------------------------------------------------------------------- #
# Chemins
# --------------------------------------------------------------------------- #
RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GARDÉ = os.path.join(RACINE, "scripts", "nexus_garde_shell.py")


def _ensure_tool() -> Optional[str]:
    """Vérifie la présence du garde. Retourne son chemin ou None."""
    if not os.path.isfile(GARDÉ):
        print(f"[RATE] garde present : introuvable a {GARDÉ}")
        return None
    return GARDÉ


def _run(payload: str) -> subprocess.CompletedProcess:
    """Exécute le garde avec le payload JSON fourni."""
    tool_path = _ensure_tool()
    if tool_path is None:
        # Le garde est absent ; on laisse le caller gérer la sortie.
        raise FileNotFoundError
    try:
        return subprocess.run(
            [sys.executable, tool_path],
            input=payload.encode("utf-8"),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=10,
        )
    except subprocess.TimeoutExpired:
        # Timeout : on considère cela comme un refus.
        return subprocess.CompletedProcess(
            args=[],
            returncode=1,
            stdout=b"",
            stderr=b"Timeout",
        )


def _denied(stdout: str) -> bool:
    """Détecte un refus du garde dans le JSON retourné."""
    try:
        data = json.loads(stdout)
        return (
            data.get("hookSpecificOutput", {})
            .get("permissionDecision")
            == "deny"
        )
    except Exception:
        return False


# --------------------------------------------------------------------------- #
# Tests
# --------------------------------------------------------------------------- #
def _test_nominal() -> bool:
    """Test (a) : commande simple autorisée."""
    cmd = "echo hello"
    payload = json.dumps(
        {"tool_name": "Bash", "tool_input": {"command": cmd}}
    )
    result = _run(payload)
    if result.returncode != 0:
        print("[RATE] nominal : non‑zero exit code")
        return False
    if _denied(result.stdout.decode()):
        print("[RATE] nominal : refus inattendu")
        return False
    print("[OK  ] nominal : accepté")
    return True


def _test_heredoc_backslash() -> bool:
    """Test (b) : heredoc contenant un antislash, doit être refusé."""
    back = "\\"          # antislash
    nl = "\n"
    cmd = f"cat <<PYEOF{nl}print('test{back}n'){nl}PYEOF"
    payload = json.dumps(
        {"tool_name": "Bash", "tool_input": {"command": cmd}}
    )
    result = _run(payload)
    if not _denied(result.stdout.decode()):
        print("[RATE] heredoc_backslash : pas de refus")
        return False
    print("[OK  ] heredoc_backslash : refusé")
    return True


def _test_accent_grave() -> bool:
    """Test (c) : accent grave entre guillemets doubles, doit être refusé."""
    cmd = 'echo "run `ls`"'
    payload = json.dumps(
        {"tool_name": "Bash", "tool_input": {"command": cmd}}
    )
    result = _run(payload)
    if not _denied(result.stdout.decode()):
        print("[RATE] accent_grave : pas de refus")
        return False
    print("[OK  ] accent_grave : refusé")
    return True


def _test_invalid_tool() -> bool:
    """Test (d) : outil inconnu, le garde doit rester muet."""
    payload = json.dumps(
        {"tool_name": "Unknown", "tool_input": {"command": "echo hi"}}
    )
    result = _run(payload)
    if result.stdout:
        print("[RATE] invalid_tool : sortie inattendue")
        return False
    print("[OK  ] invalid_tool : ignoré")
    return True


# --------------------------------------------------------------------------- #
# Entrée principale
# --------------------------------------------------------------------------- #
def main() -> None:
    if _ensure_tool() is None:
        sys.exit(1)

    all_ok = True
    all_ok &= _test_nominal()
    all_ok &= _test_heredoc_backslash()
    all_ok &= _test_accent_grave()
    all_ok &= _test_invalid_tool()

    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()