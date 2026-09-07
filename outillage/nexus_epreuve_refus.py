#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""outillage/nexus_epreuve_refus.py

Épreuve autonome qui vérifie que la fonction `_ecrire_refus_sortie` de
`nexus_agent` conserve son comportement vis‑à‑vis du paramètre `--sortie`.

Aucun effet de bord n’est produit à l’import du module.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any, List

# --------------------------------------------------------------------------- #
# 1.  Préparation du sys.path
# --------------------------------------------------------------------------- #
_ROOT = os.path.abspath(os.path.dirname(__file__))
_SCRIPTS = os.path.join(_ROOT, "scripts")

for _p in (_ROOT, _SCRIPTS):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# --------------------------------------------------------------------------- #
# 2.  Import de la fonction cible
# --------------------------------------------------------------------------- #
_ECRIRE_REFUS_SORTIE = None  # type: ignore[var-annotated]

try:
    from nexus_agent import _ecrire_refus_sortie as _ECRIRE_REFUS_SORTIE  # noqa: F401
except Exception as exc:  # ImportError, AttributeError, etc.
    _IMPORT_ERROR = exc
else:
    _IMPORT_ERROR = None

# --------------------------------------------------------------------------- #
# 3.  Fonctions utilitaires
# --------------------------------------------------------------------------- #
def _read_jsonl(path: Path) -> List[dict]:
    """Lit un fichier JSON‑Lines et renvoie la liste des objets décodés."""
    lines = []
    with path.open("r", encoding="utf-8") as fh:
        for raw in fh:
            raw = raw.strip()
            if raw:
                try:
                    lines.append(json.loads(raw))
                except json.JSONDecodeError as e:
                    raise ValueError(f"Ligne non JSON valide dans {path}: {e}") from e
    return lines


def _check_forward(tmp_dir: Path) -> bool:
    """Exécute le volet FORWARD de l’épreuve."""
    sortie_path = tmp_dir / "r.jsonl"
    try:
        _ECRIRE_REFUS_SORTIE(str(sortie_path), [{"nom": "a"}, {"nom": "b"}], "cause X")
    except Exception as e:
        sys.stderr.write(f"[FORWARD] Erreur lors de l’appel de _ecrire_refus_sortie : {e}\n")
        return False

    # Lecture et validation du fichier produit
    try:
        records = _read_jsonl(sortie_path)
    except Exception as e:
        sys.stderr.write(f"[FORWARD] Impossible de lire le fichier produit : {e}\n")
        return False

    if len(records) != 2:
        sys.stderr.write(f"[FORWARD] Nombre de lignes attendu : 2, trouvé : {len(records)}\n")
        return False

    for idx, rec in enumerate(records, start=1):
        if rec.get("refus") != "cause X":
            sys.stderr.write(f"[FORWARD] Ligne {idx} : champ 'refus' incorrect ({rec.get('refus')})\n")
            return False
        if rec.get("texte") != "":
            sys.stderr.write(f"[FORWARD] Ligne {idx} : champ 'texte' doit être vide\n")
            return False
        if "nom" not in rec:
            sys.stderr.write(f"[FORWARD] Ligne {idx} : champ 'nom' absent\n")
            return False
    return True


def _check_reverse(tmp_dir: Path) -> bool:
    """Exécute le volet REVERSE de l’épreuve."""
    # Aucun fichier ne doit être créé ; on mémorise la liste initiale.
    before = set(p.name for p in tmp_dir.iterdir())

    try:
        _ECRIRE_REFUS_SORTIE(None, [{"nom": "z"}], "y")
    except Exception as e:
        sys.stderr.write(f"[REVERSE] Exception inattendue : {e}\n")
        return False

    after = set(p.name for p in tmp_dir.iterdir())
    new_files = after - before
    if new_files:
        sys.stderr.write(f"[REVERSE] Des fichiers inattendus ont été créés : {new_files}\n")
        return False
    return True


def run_epreuve() -> int:
    """Orchestre l’ensemble de l’épreuve et renvoie le code de sortie."""
    if _IMPORT_ERROR is not None:
        sys.stderr.write(
            f"Import de _ecrire_refus_sortie impossible : {_IMPORT_ERROR}\n"
        )
        return 1

    exit_code = 0
    with tempfile.TemporaryDirectory() as td:
        tmp_path = Path(td)

        # FORWARD
        if _check_forward(tmp_path):
            sys.stdout.write("[FORWARD] OK\n")
        else:
            sys.stdout.write("[FORWARD] ÉCHEC\n")
            exit_code = 1

        # REVERSE
        if _check_reverse(tmp_path):
            sys.stdout.write("[REVERSE] OK\n")
        else:
            sys.stdout.write("[REVERSE] ÉCHEC\n")
            exit_code = 1

    return exit_code


# --------------------------------------------------------------------------- #
# 4.  Entrée script
# --------------------------------------------------------------------------- #
def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Épreuve de régression pour _ecrire_refus_sortie",
        add_help=False,
    )
    parser.add_argument(
        "--epreuve",
        action="store_true",
        help="exécuter l’épreuve de régression et retourner le code d’état",
    )
    # Un petit -h manuel pour les cas où aucun argument n’est fourni
    parser.add_argument(
        "-h",
        "--help",
        action="help",
        help="afficher cette aide et quitter",
    )
    return parser


def main() -> None:
    parser = _build_parser()
    args, unknown = parser.parse_known_args()

    if not args.epreuve:
        # Aucun argument pertinent : afficher l’aide courte et quitter avec succès.
        parser.print_help(sys.stdout)
        sys.exit(0)

    # Exécution de l’épreuve
    code = run_epreuve()
    sys.exit(code)


if __name__ == "__main__":
    main()
