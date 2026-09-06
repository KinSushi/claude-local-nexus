# -*- coding: utf-8 -*-
"""
Porte de rituel (hook STOP)

Cette porte bloque la cloture d'un tour lorsque le controle « travail commite »
est en statut « MANQUE ». Tous les autres controles manquants ne provoquent
qu'un avertissement.

Pourquoi ce refus est-il si strict ?
Le controle « travail commite » est le seul qui peut etre satisfait
immediatement par la session courante : il suffit de pousser les changements
en attente. Sans ce commit, le tour se termine avec du travail non sauvegarde,
ce qui est inacceptable.

Comment desarmer la porte ?
* Exporter la variable d'environnement ``NEXUS_AGENT_LIBRE=1`` : la porte ne
  bloque jamais.
* Commiter les fichiers indiques dans le detail du controle ; la commande
  exacte est affichee dans le message de refus.
* Apres deux refus consecutifs, le troisieme passage est autorise avec un
  avertissement et le compteur est remis a zero.

Le compteur de refus consecutifs est stocke dans ``.nexus/rituel_counter.txt``
a la racine du depot (chemin relatif, jamais absolu). Il est reinitialise
des qu'un tour passe.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, List, Tuple

# ---------------------------------------------------------------------------

def _repo_root() -> Path:
    """Racine du depot, derivee de ce fichier (un niveau au-dessus)."""
    return Path(__file__).resolve().parent.parent

def _counter_path(root: Path) -> Path:
    """Chemin du fichier compteur, sous .nexus/."""
    return root / ".nexus" / "rituel_counter.txt"

def _read_counter(path: Path) -> int:
    """Lit le compteur, 0 si le fichier n'existe pas ou est invalide."""
    try:
        return int(path.read_text(encoding="utf-8").strip())
    except Exception:
        return 0

def _write_counter(path: Path, count: int) -> None:
    """Ecrit le compteur, cree le repertoire parent si besoin."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(str(count), encoding="utf-8")

def _run_rituel(root: Path) -> dict | None:
    """
    Execute ``scripts/nexus_rituel.py --json`` depuis la racine du depot.
    Retourne le JSON decode ou ``None`` en cas d'erreur (fail-open).
    """
    cmd = [
        sys.executable,
        str(root / "scripts" / "nexus_rituel.py"),
        "--json",
    ]
    try:
        result = subprocess.run(
            cmd,
            cwd=root,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=180,
            check=False,
        )
        if result.returncode not in (0, 1):
            # Le rituel renvoie 0 (pas de manque) ou 1 (manque)
            return None
        return json.loads(result.stdout.decode("utf-8"))
    except Exception:
        return None

def _should_block(verdict: dict) -> Tuple[bool, str]:
    """
    Analyse le verdict du rituel.
    Retourne (True, detail) si le controle « travail commite » est en MANQUE,
    sinon (False, "").
    """
    controles = verdict.get("controles", [])
    for ctrl in controles:
        if ctrl.get("nom") == "travail commite" and ctrl.get("statut") == "MANQUE":
            detail = ctrl.get("detail", "")
            return True, detail
    return False, ""

def _actionable_message(detail: str, remaining: int) -> str:
    """
    Construit le message de refus avec les informations demandees.
    """
    cmd = "git add -A && git commit -m 'Commit avant cloture du tour'"
    return (
        f"Fichiers non commites: {detail}. "
        f"Commande: {cmd}. "
        f"Refus restants avant autorisation: {remaining}. "
        f"Escalade: definir NEXUS_AGENT_LIBRE=1."
    )

def _process(
    root: Path, counter_path: Path, verdict_json: dict | None
) -> Tuple[bool, str]:
    """
    Determine la decision finale.
    Retourne (do_block, message_json_string).
    """
    # Cas d'echappatoire global
    if os.environ.get("NEXUS_AGENT_LIBRE") == "1":
        return False, ""

    # Si le rituel n'a pas pu etre execute, on laisse passer (fail-open)
    if verdict_json is None:
        return False, ""

    block, detail = _should_block(verdict_json)
    if not block:
        # Aucun blocage requis - remise a zero du compteur
        _write_counter(counter_path, 0)
        return False, ""

    # Gestion du compteur de refus consecutifs
    count = _read_counter(counter_path)
    if count >= 2:
        # Troisieme passage : avertissement, remise a zero
        _write_counter(counter_path, 0)
        system_msg = {
            "systemMessage": (
                "Troisieme refus consecutif - le tour est autorise. "
                "Le compteur a ete reinitialise."
            )
        }
        return False, json.dumps(system_msg, ensure_ascii=True)
    else:
        # Refus reel
        new_count = count + 1
        _write_counter(counter_path, new_count)
        remaining = 2 - count
        reason = _actionable_message(detail, remaining)
        block_msg = {"decision": "block", "reason": reason}
        return True, json.dumps(block_msg, ensure_ascii=True)

def _epreuve_mode(input_data: str) -> str:
    """
    Mode --epreuve : lit le verdict JSON depuis stdin et renvoie la decision
    qui aurait ete prise (sans toucher au compteur).
    """
    try:
        verdict = json.loads(input_data)
    except Exception:
        return ""  # fail-open, aucune sortie
    block, detail = _should_block(verdict)
    if not block:
        return json.dumps({"decision": "allow", "reason": "Aucun blocage requis"})
    reason = _actionable_message(detail, remaining=2)  # valeur indicative
    return json.dumps({"decision": "block", "reason": reason}, ensure_ascii=True)

def main(argv: List[str] | None = None) -> int:
    """Point d'entree du hook."""
    if argv is None:
        argv = sys.argv[1:]

    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--epreuve", action="store_true")
    args, _ = parser.parse_known_args(argv)

    root = _repo_root()
    counter_path = _counter_path(root)

    if args.epreuve:
        # Lecture du verdict depuis stdin
        input_json = sys.stdin.read()
        out = _epreuve_mode(input_json)
        if out:
            print(out)
        return 0

    verdict = _run_rituel(root)
    block, out_json = _process(root, counter_path, verdict)

    if out_json:
        print(out_json)
    # Retour du code d'exit : 0 (pas de blocage) ou 1 (blocage)
    return 1 if block else 0

if __name__ == "__main__":
    # Le rempart final ne doit pas ecraser un refus deja decide.
    # Accepte car : le JSON de refus est imprime AVANT l'exception, donc la
    # decision est deja transmise via stdout. Le fail-ouvert ne s'applique
    # qu'aux exceptions survenues AVANT la decision (rituel plante, etc.)
    try:
        exit_code = main()
    except BaseException:
        exit_code = 0
    sys.exit(exit_code)
