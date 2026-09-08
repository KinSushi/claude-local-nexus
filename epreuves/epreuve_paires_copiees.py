#!/usr/bin/env python3
"""Test d'intégrité des modules dupliqués.

Cette épreuve échoue dès qu'une paire de fichiers copiés
`scripts/<name>.py` ↔ `outillage/<name>.py` diverge (par ex. un correctif
appliqué d'un seul côté). La comparaison normalise les fins de ligne
car le dépôt impose `eol=lf` via `.gitattributes`.

Le script :

1. Détermine la racine du projet à partir du répertoire du fichier.
2. Recherche les répertoires ``scripts`` et ``outillage``.
3. Pour chaque fichier ``*.py`` présent **dans les deux** répertoires,
   compare le contenu après normalisation des fins de ligne
   (lecture binaire, remplacement de ``b'\r\n'`` et ``b'\r'`` par ``b'\n'``).
4. Signale les paires divergentes ou indique que toutes les paires sont
   identiques.
5. Si l'un des répertoires est absent, le test réussit avec le message
   « rien à comparer ».

Sortie :

* Aucun problème : ``[OK  ] paires copiees : N paires identiques``
* Divergence   : ``[RATE] paires copiees : divergent -> f1.py, f2.py, ...``

Le script se termine avec le code de sortie 0 en cas de succès,
ou 1 en cas de divergence.

Only the Python standard library is used.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import List


def _root_dir() -> Path:
    """Return the project root (two levels up from this file)."""
    return Path(__file__).resolve().parents[1]


def _normalize(content: bytes) -> bytes:
    """Normalize line endings to LF (``b'\n'``)."""
    # Replace Windows CRLF then stray CR.
    return content.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def _list_py_files(directory: Path) -> List[Path]:
    """Return a list of ``*.py`` files directly inside *directory*."""
    if not directory.is_dir():
        return []
    return [p for p in directory.iterdir() if p.suffix == ".py" and p.is_file()]


def _compare_files(file_a: Path, file_b: Path) -> bool:
    """Return ``True`` if the normalized contents of the two files are equal."""
    try:
        content_a = _normalize(file_a.read_bytes())
        content_b = _normalize(file_b.read_bytes())
    except OSError as exc:
        print(f"[RATE] erreur de lecture : {exc}", file=sys.stderr)
        return False
    return content_a == content_b


def main() -> None:
    root = _root_dir()
    scripts_dir = root / "scripts"
    outillage_dir = root / "outillage"

    # If one of the directories is missing, nothing to compare.
    if not scripts_dir.is_dir() or not outillage_dir.is_dir():
        print("[OK  ] rien a comparer")
        sys.exit(0)

    scripts_files = {p.name: p for p in _list_py_files(scripts_dir)}
    outillage_files = {p.name: p for p in _list_py_files(outillage_dir)}

    common_names = sorted(set(scripts_files) & set(outillage_files))

    divergent: List[str] = []
    for name in common_names:
        if not _compare_files(scripts_files[name], outillage_files[name]):
            divergent.append(name)

    total_pairs = len(common_names)

    if divergent:
        print("[RATE] paires copiees : divergent -> " + ", ".join(divergent))
        sys.exit(1)
    else:
        print(f"[OK  ] paires copiees : {total_pairs} paires identiques")
        sys.exit(0)


if __name__ == "__main__":
    main()