#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import os
import subprocess
import sys
import tempfile

# --------------------------------------------------------------------------- #
# Configuration du garde
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GARDE = os.path.join(ROOT, "scripts", "nexus_garde_lecture.py")
SESSION_ID = "test_session_20260907"

if not os.path.isfile(GARDE):
    print(f"[ERREUR] Garde introuvable : {GARDE}", file=sys.stderr)
    sys.exit(3)


def _lancer_garde(tool_name: str, file_path: str) -> bool:
    """
    Lance le garde en sous‑processus avec l’entrée JSON attendue.
    Retourne True si la sortie contient `"permissionDecision": "deny"`.
    """
    payload = {
        "session_id": SESSION_ID,
        "tool_name": tool_name,
        "tool_input": {"file_path": file_path},
    }

    try:
        result = subprocess.run(
            [sys.executable, GARDE],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            timeout=10,
        )
    except subprocess.TimeoutExpired:
        print("[TIMEOUT] Le garde n’a pas répondu à temps.", file=sys.stderr)
        return False

    # Le garde renvoie toujours code 0 ; on ne s’en préoccupe pas.
    # On recherche simplement la présence du champ deny.
    return '"permissionDecision": "deny"' in result.stdout


def envoyer(tool_name: str, file_path: str) -> bool:
    """
    Interface publique : renvoie True si le garde a refusé (deny présent).
    """
    return _lancer_garde(tool_name, file_path)


def _nettoyer_memoire():
    """Supprime le fichier de mémoire de session créé par le garde."""
    memoire_path = os.path.join(
        ROOT, ".nexus", "lectures", f"{SESSION_ID}.json"
    )
    try:
        if os.path.isfile(memoire_path):
            os.unlink(memoire_path)
    except Exception:
        pass  # on ne veut pas interrompre le test à cause d’une erreur de nettoyage


def main() -> int:
    # ------------------------------------------------------------------- #
    # 1. FORWARD : Edit d’un fichier jamais lu → doit être refusé
    tmp_fwd = tempfile.NamedTemporaryFile(delete=False)
    tmp_fwd_path = tmp_fwd.name
    tmp_fwd.close()

    try:
        deny_forward = envoyer("Write", tmp_fwd_path)
        if not deny_forward:
            print("[RATE] forward : le garde n’a pas refusé l’écriture d’un fichier inconnu.")
            return 1
        print("[OK  ] forward : garde refuse bien l ecriture d un fichier inconnu")
    finally:
        if os.path.isfile(tmp_fwd_path):
            os.unlink(tmp_fwd_path)

    # ------------------------------------------------------------------- #
    # 2. REVERSE : Read puis Edit du même fichier → ne doit pas être refusé
    tmp_rev = tempfile.NamedTemporaryFile(delete=False)
    tmp_rev_path = tmp_rev.name
    tmp_rev.close()

    try:
        # Lecture préalable
        _ = envoyer("Read", tmp_rev_path)  # le résultat n’est pas important ici

        # Tentative d’écriture après lecture
        deny_reverse = envoyer("Write", tmp_rev_path)
        if deny_reverse:
            print("[RATE] reverse : le garde a refusé l’écriture après lecture.")
            return 1
        print("[OK  ] reverse : garde autorise l ecriture apres lecture")
    finally:
        if os.path.isfile(tmp_rev_path):
            os.unlink(tmp_rev_path)

    # ------------------------------------------------------------------- #
    # Nettoyage de la mémoire du garde
    _nettoyer_memoire()
    return 0


if __name__ == "__main__":
    sys.exit(main())
