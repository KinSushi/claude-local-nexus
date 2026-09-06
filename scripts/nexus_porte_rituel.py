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

Options :
* ``--epreuve`` : lit un verdict JSON depuis l'entree standard et affiche la
  decision qui serait prise, sans toucher au compteur. Mode de diagnostic.
* ``--verdict CHEMIN`` : lit le verdict JSON depuis le fichier CHEMIN au lieu
  de lancer ``nexus_rituel.py``. Le comportement est identique au mode normal
  (compteur, borne, echappatoire, JSON de decision, code de sortie). Si le
  fichier est absent, vide, illisible, contient un JSON invalide ou est trop
  ancien, la porte laisse passer sans bloquer et sans planter (fail-open). Le
  compteur n'est pas remis a zero dans ce cas : on n'a rien constate sur le rituel.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import List, Tuple

# ---------------------------------------------------------------------------
# Constante : âge maximal du fichier de verdict (en secondes)
# Une passe du rituel prend environ 21 s sur cette machine. On ajoute une
# marge de 24 s pour couvrir les ralentissements éventuels (charge CPU,
# I/O, etc.). Ainsi, tout verdict plus vieux que 45 s est considéré périmé.
# On préfère laisser passer (fail‑open) plutôt que de bloquer à tort,
# car une garde qui bloque à tort désarme le dépôt.
VERDICT_MAX_AGE = 45

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

def _read_verdict_file(path: str) -> dict | None:
    """
    Lit un verdict JSON depuis un fichier. Retourne le dict ou ``None`` si le
    fichier est absent, vide, illisible, contient un JSON invalide ou est trop
    ancien.

    Note sur le fichier perime : un fichier au format valide mais trop ancien
    peut provoquer un blocage errone si son contenu ne correspond plus a l'etat
    actuel du depot. Pour s'en premunir, on verifie l'age du fichier. Si
    l'horodatage est illisible, on laisse passer (fail-open).
    """
    try:
        verdict_path = Path(path)
        if not verdict_path.exists():
            return None

        # Verification de l'age du fichier
        file_mtime = verdict_path.stat().st_mtime
        if time.time() - file_mtime > VERDICT_MAX_AGE:
            return None

        content = verdict_path.read_text(encoding="utf-8")
        if not content.strip():
            return None
        return json.loads(content)
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
    return json.dumps(
        {"decision": "allow", "reason": "Aucun blocage requis"} if not block
        else {"decision": "block", "reason": _actionable_message(detail, remaining=2)},
        ensure_ascii=True,
    )

def main(argv: List[str] | None = None) -> int:
    """Point d'entree du hook."""
    if argv is None:
        argv = sys.argv[1:]

    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--epreuve", action="store_true")
    parser.add_argument("--verdict", type=str, default=None)
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

    verdict = _read_verdict_file(args.verdict) if args.verdict else _run_rituel(root)

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
