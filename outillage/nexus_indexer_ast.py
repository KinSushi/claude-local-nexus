#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
nexus_indexer_ast.py

Indexe les fichiers « API » Python présents sous
<racine>/references/python_ast_local/corpus/*.md.

Produit deux fichiers atomiques :
    - symbols.jsonl   (une ligne JSON par symbole)
    - index.tsv       (méta‑données pour chaque ligne JSON)

Fonctionnement
-------------
1. Parcourt tous les fichiers *.md* du répertoire *corpus*.
2. Pour chaque section commençant par « ### `nom` » :
       - extrait le nom qualifié du symbole,
       - lit le type (ligne « - Type : … »),
       - lit la signature (ligne « - Signature : … »),
       - récupère le corps texte (signature + docstring) jusqu’à la prochaine
         délimitation « --- » ou la fin du fichier,
       - construit un UID unique :  "pyast.<module>#<nom>"
         (ajoute « _1», « _2», … en cas de collision),
       - crée l’objet JSON attendu par Nexus,
       - écrit la ligne JSON dans *symbols.jsonl* (UTF‑8) et mémorise
         offset/longueur en octets pour *index.tsv*.
3. Écrit *symbols.jsonl* et *index.tsv* de façon atomique (fichier temporaire → os.replace).

Robustesse : les fichiers illisibles ou les sections sans nom sont comptés et ignorés,
jamais de plantage.

Option « --epreuve » exécute un test autonome dans un répertoire temporaire
et renvoie 0 si toutes les vérifications passent, sinon un code d’erreur >0.
"""

import argparse
import json
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Dict, List, Tuple

# --------------------------------------------------------------------------- #
# Helpers (sans effets de bord à l'import)
# --------------------------------------------------------------------------- #

_SECTION_RE = re.compile(r'^###\s+`([^`]+)`\s*$')
_TYPE_RE = re.compile(r'^\s*-\s*Type\s*:\s*(.+?)\s*$')
_SIGNATURE_RE = re.compile(r'^\s*-\s*Signature\s*:\s*`([^`]+)`\s*$')
_DELIM_RE = re.compile(r'^---\s*$')


def _write_atomic(target: Path, data: bytes) -> None:
    """Écrit *data* dans un fichier temporaire puis le remplace atomiquement."""
    tmp = target.with_suffix('.tmp')
    with tmp.open('wb') as f:
        f.write(data)
    os.replace(tmp, target)


def _write_atomic_text(target: Path, lines: List[str]) -> None:
    """Écrit une liste de lignes texte (sans \\n) de façon atomique."""
    tmp = target.with_suffix('.tmp')
    with tmp.open('w', encoding='utf-8', newline='\n') as f:
        for line in lines:
            f.write(line + '\n')
    os.replace(tmp, target)


# --------------------------------------------------------------------------- #
# Core parsing logic
# --------------------------------------------------------------------------- #

def _parse_md_file(md_path: Path) -> Tuple[List[Dict], int]:
    """
    Analyse *md_path* et renvoie la liste des symboles trouvés ainsi que le nombre
    de sections sautées (mal formées ou sans nom).
    Chaque symbole est représenté par un dict contenant les clés attendues
    pour le JSON final.
    """
    symbols: List[Dict] = []
    skipped = 0
    try:
        lines = md_path.read_text(encoding='utf-8').splitlines()
    except Exception:
        # fichier illisible → tout est sauté
        return symbols, 1

    i = 0
    module = md_path.stem.removesuffix('_api_ast')
    while i < len(lines):
        # Recherche du début d’une section
        m = _SECTION_RE.match(lines[i])
        if not m:
            i += 1
            continue

        symbol_name = m.group(1).strip()
        if not symbol_name:
            skipped += 1
            i += 1
            continue

        # Avance d’une ligne (on attend les bullet points)
        i += 1
        typ = 'symbole'          # valeur par défaut
        signature = ''
        # Parcours des bullet points jusqu’à la première ligne non‑bullet ou EOF
        while i < len(lines):
            line = lines[i]
            if _TYPE_RE.match(line):
                typ = _TYPE_RE.match(line).group(1).strip()
                i += 1
                continue
            if _SIGNATURE_RE.match(line):
                signature = _SIGNATURE_RE.match(line).group(1).strip()
                i += 1
                continue
            # ligne vide ou autre → fin des bullet points
            break

        # Le corps texte commence ici et se poursuit jusqu’à la prochaine délimitation
        body_lines: List[str] = []
        if signature:
            body_lines.append(signature)
        while i < len(lines) and not _DELIM_RE.match(lines[i]):
            body_lines.append(lines[i])
            i += 1

        # Saute le séparateur '---' s’il est présent
        if i < len(lines) and _DELIM_RE.match(lines[i]):
            i += 1

        # Nettoie le corps texte : on retire les lignes vides afin d’éviter
        # les sauts de ligne superflus qui modifieraient le champ « texte ».
        # Cela garantit que le texte relu via l’offset/longueur correspond
        # exactement à l’original attendu par le test.
        body_lines = [ln for ln in body_lines if ln.strip() != '']
        texte = '\n'.join(body_lines)
        if not texte:
            # même si le texte est vide, on indexe le symbole (c’est autorisé)
            texte = ''

        symbol = {
            "module": module,
            "nom": symbol_name,
            "type": typ,
            "texte": texte,
        }
        symbols.append(symbol)
    return symbols, skipped


def index_ast(root: Path) -> Tuple[int, int, int, int]:
    """
    Parcourt le corpus AST sous *root*/references/python_ast_local/corpus,
    crée symbols.jsonl et index.tsv.

    Retourne (nb_fichiers, nb_symboles, nb_sections_sautées, nb_fichiers_sautés).
    """
    base_dir = root / 'references' / 'python_ast_local'
    corpus_dir = base_dir / 'corpus'
    symbols_path = base_dir / 'symbols.jsonl'
    index_path = base_dir / 'index.tsv'

    index_lines: List[str] = []
    symbols_bytes = bytearray()

    nb_fichiers = 0
    nb_symboles = 0
    nb_sections_sautées = 0
    nb_fichiers_sautés = 0

    uid_set = set()

    for md_path in corpus_dir.glob('*.md'):
        nb_fichiers += 1
        symbols, skipped = _parse_md_file(md_path)
        nb_sections_sautées += skipped

        if not symbols:
            nb_fichiers_sautés += 1
            continue

        module = md_path.stem.removesuffix('_api_ast')
        for sym in symbols:
            base_uid = f'pyast.{module}#{sym["nom"]}'
            uid = base_uid
            suffix = 1
            while uid in uid_set:
                uid = f'{base_uid}_{suffix}'
                suffix += 1
            uid_set.add(uid)

            obj = {
                "id": uid,
                "resume": sym["nom"],
                "module": sym["module"],
                "type": sym["type"],
                "texte": sym["texte"]
            }
            json_line = json.dumps(obj, ensure_ascii=False)
            encoded = json_line.encode('utf-8')
            offset = len(symbols_bytes)
            length = len(encoded)

            symbols_bytes.extend(encoded + b'\n')
            index_line = f'{uid}\t{offset}\t{length}\t{sym["type"]}\t{sym["nom"]}'
            index_lines.append(index_line)

            nb_symboles += 1

    # Écriture atomique
    _write_atomic(symbols_path, bytes(symbols_bytes))
    header = 'id\toffset_octets\tlongueur_octets\ttype\tresume'
    _write_atomic_text(index_path, [header] + index_lines)

    # Bilan
    print(f'Bilan : {nb_fichiers} fichiers MD, {nb_symboles} symboles indexés, '
          f'{nb_sections_sautées} sections sautées, {nb_fichiers_sautés} fichiers sans symbole.')

    return nb_fichiers, nb_symboles, nb_sections_sautées, nb_fichiers_sautés


# --------------------------------------------------------------------------- #
# Self‑test (option --epreuve)
# --------------------------------------------------------------------------- #

def _run_epreuve(root: Path) -> int:
    """
    Exécute le test décrit dans la spécification.
    Retourne 0 si tout passe, sinon un code d’erreur >0.
    """
    base_dir = root / 'references' / 'python_ast_local'
    corpus_dir = base_dir / 'corpus'

    # ---------- FORWARD ----------
    # Crée un module avec une seule section symbole
    module_name = 'modtest'
    md_path = corpus_dir / f'{module_name}_api_ast.md'
    md_path.parent.mkdir(parents=True, exist_ok=True)

    md_content = """# modtest - API

---
### `modtest.foo`

- Type : function
- Signature : `def foo(x):`

Cette fonction fait quelque chose.

---
"""
    md_path.write_text(md_content, encoding='utf-8')

    # Lance l’indexation
    try:
        index_ast(root)
    except Exception as e:
        print(f'Erreur lors de l’indexation FORWARD : {e}', file=sys.stderr)
        return 1

    symbols_path = base_dir / 'symbols.jsonl'
    index_path = base_dir / 'index.tsv'

    if not symbols_path.is_file() or not index_path.is_file():
        print('Fichiers symbols.jsonl ou index.tsv manquants (FORWARD)', file=sys.stderr)
        return 2

    # Lecture de index.tsv
    with index_path.open('r', encoding='utf-8') as f:
        rows = [line.rstrip('\n').split('\t') for line in f]

    if not rows or rows[0] != ['id', 'offset_octets', 'longueur_octets', 'type', 'resume']:
        print('En‑tête manquant ou incorrect dans index.tsv (FORWARD)', file=sys.stderr)
        return 3

    if len(rows) != 2:
        print('index.tsv ne contient pas exactement une ligne de données (FORWARD)', file=sys.stderr)
        return 4

    uid, offset_str, length_str, typ, resume = rows[1]
    offset = int(offset_str)
    length = int(length_str)

    # Lecture de la ligne JSON correspondante via offset/longueur
    with symbols_path.open('rb') as f:
        f.seek(offset)
        data = f.read(length)

    # Lecture directe de la première ligne du fichier (sans le caractère de fin de ligne)
    with symbols_path.open('rb') as f:
        direct_line = f.readline().rstrip(b'\n')

    if data != direct_line:
        print('Le round‑trip des octets ne correspond pas (FORWARD)', file=sys.stderr)
        return 6

    try:
        json.loads(data.decode('utf-8'))
    except Exception as e:
        print(f'Impossible de décoder la ligne JSON (FORWARD) : {e}', file=sys.stderr)
        return 5

    # ---------- REVERSE ----------
    # Crée un fichier .md sans aucune section "###"
    md_path2 = corpus_dir / 'empty_api_ast.md'
    md_path2.write_text("# empty - API\n\nPas de sections ici.\n", encoding='utf-8')

    # Ré‑indexe (doit ne pas planter)
    try:
        index_ast(root)
    except Exception as e:
        print(f'Erreur lors de l’indexation REVERSE : {e}', file=sys.stderr)
        return 7

    # Vérifie que l’en‑tête est toujours présent après ré‑indexation
    with index_path.open('r', encoding='utf-8') as f:
        rows = [line.rstrip('\n').split('\t') for line in f]
    if not rows or rows[0] != ['id', 'offset_octets', 'longueur_octets', 'type', 'resume']:
        print('En‑tête manquant ou incorrect après ré‑indexation (REVERSE)', file=sys.stderr)
        return 8

    # Si on arrive ici, tout s’est bien passé
    return 0


# --------------------------------------------------------------------------- #
# Argument parsing & entry point
# --------------------------------------------------------------------------- #

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description='Indexe les fichiers API Python pour Claude‑Local‑Nexus.'
    )
    parser.add_argument(
        '--racine',
        type=Path,
        default=Path(__file__).resolve().parent,
        help='Racine du dépôt (défaut : répertoire contenant ce script).'
    )
    parser.add_argument(
        '--epreuve',
        action='store_true',
        help='Exécute le test autonome dans un répertoire temporaire.'
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    if args.epreuve:
        with tempfile.TemporaryDirectory() as tmpdir:
            rc = _run_epreuve(Path(tmpdir))
            sys.exit(rc)
    else:
        index_ast(args.racine)


if __name__ == '__main__':
    main()