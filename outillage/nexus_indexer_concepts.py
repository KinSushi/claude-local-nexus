#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
nexus_indexer_concepts.py

Indexe les concepts présents sous <racine>/references/livres_texte/*/*__PRE_MACHE/concepts.tsv.
Produit deux fichiers atomiques :
    - symbols.jsonl   (une ligne JSON par concept)
    - index.tsv       (méta‑données pour chaque ligne JSON)

Fonctionnement
-------------
1. Parcourt tous les répertoires
   <racine>/references/livres_texte/*/*__PRE_MACHE/concepts.tsv
2. Pour chaque ligne valide du TSV :
       - construit un UID unique :  "concept.<slug(livre)>#<slug(concept)>" (suffixe .2,.3… en cas de collision)
       - crée l’objet JSON attendu par Nexus
       - écrit la ligne JSON dans symbols.jsonl (UTF‑8)
       - mémorise offset et longueur en octets pour index.tsv
3. Écrit index.tsv avec les colonnes :
       id  offset_octets  longueur_octets  type  resume
4. Toutes les écritures sont atomiques (fichiers temporaires → os.replace).

Robustesse : fichiers illisibles, en‑tête manquante ou lignes < 4 colonnes sont comptés
et ignorés, jamais d’exception.

Option « --epreuve » exécute trois tests autonomes dans un répertoire temporaire
et renvoie 0 si tout passe, sinon un code d’erreur >0.
"""

import argparse
import csv
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

_SLUG_MAX_LEN = 50  # longueur maximale du slug (troncature)


def _slugify(text: str) -> str:
    """Retourne un slug stable, court et sûr à partir d'un texte."""
    text = text.lower()
    text = re.sub(r'[^a-z0-9]+', '_', text)
    text = text.strip('_')
    if not text:
        text = 'unknown'
    return text[:_SLUG_MAX_LEN]


def _read_tsv(path: Path) -> Tuple[List[List[str]], int]:
    """
    Lit un TSV en mode texte, renvoie la liste des lignes (listes de champs)
    et le nombre de lignes ignorées (mal formées ou < 4 colonnes).
    """
    rows: List[List[str]] = []
    skipped = 0
    try:
        with path.open(newline='', encoding='utf-8') as f:
            reader = csv.reader(f, delimiter='\t')
            header = next(reader, None)
            if header is None or len(header) < 4:
                # en‑tête absente ou insuffisante → tout le fichier est sauté
                return [], 0
            for fields in reader:
                if len(fields) < 4:
                    skipped += 1
                    continue
                rows.append(fields)
    except Exception:
        # fichier illisible → considéré comme entièrement sauté
        return [], 0
    return rows, skipped


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
# Core indexing logic
# --------------------------------------------------------------------------- #

def index_concepts(root: Path) -> Tuple[int, int, int, int]:
    """
    Parcourt les concepts sous *root*/references/livres_texte,
    crée symbols.jsonl et index.tsv dans *root*/references/livres_texte_concepts.

    Retourne (nb_fichiers, nb_concepts, nb_lignes_sautées, nb_fichiers_sautés).
    """
    src_base = root / 'references' / 'livres_texte'
    dst_base = root / 'references' / 'livres_texte_concepts'
    dst_base.mkdir(parents=True, exist_ok=True)

    symbols_path = dst_base / 'symbols.jsonl'
    index_path = dst_base / 'index.tsv'

    index_lines: List[str] = []
    symbols_bytes = bytearray()

    uid_counts: Dict[str, int] = {}

    nb_files = 0
    nb_concepts = 0
    nb_skipped_lines = 0
    nb_skipped_files = 0

    pattern = '**/*__PRE_MACHE/concepts.tsv'
    for tsv_path in src_base.glob(pattern):
        nb_files += 1

        rows, skipped = _read_tsv(tsv_path)
        nb_skipped_lines += skipped

        if not rows:
            # soit fichier illisible, soit en‑tête manquante, soit aucune ligne valide
            nb_skipped_files += 1
            continue

        # extraction du livre et de la matière
        pre_dir = tsv_path.parent                     # <Livre>__PRE_MACHE
        book_dir_name = pre_dir.name
        book_name = book_dir_name.removesuffix('__PRE_MACHE')
        matiere = pre_dir.parent.name                 # <Matiere>

        slug_book = _slugify(book_name)

        for fields in rows:
            concept, nb_occ_str, unit_ids, types = fields[:4]

            # nettoyage des champs
            nb_occ = int(nb_occ_str) if nb_occ_str.isdigit() else 0
            unit_ids_clean = unit_ids.strip()
            types_clean = types.strip()
            concept_clean = concept.strip()

            # UID avec gestion de collision
            base_uid = f'concept.{slug_book}#{_slugify(concept_clean)}'
            uid = base_uid
            count = uid_counts.get(base_uid, 0)
            while uid in uid_counts:
                count += 1
                uid = f'{base_uid}.{count}'
            uid_counts[base_uid] = count

            # construction du champ texte
            texte = (
                f"{concept_clean} | type: {types_clean} | occurrences: {nb_occ}"
                f" | unites: {unit_ids_clean}"
            )

            obj = {
                "id": uid,
                "resume": concept_clean,
                "livre": book_name,
                "matiere": matiere,
                "type": types_clean,
                "occurrences": nb_occ,
                "unit_ids": unit_ids_clean,
                "texte": texte
            }

            json_line = json.dumps(obj, ensure_ascii=False)
            encoded = json_line.encode('utf-8')
            offset = len(symbols_bytes)
            length = len(encoded)

            symbols_bytes.extend(encoded + b'\n')
            index_line = f'{uid}\t{offset}\t{length}\t{types_clean}\t{concept_clean}'
            index_lines.append(index_line)

            nb_concepts += 1

    # Écriture atomique des deux fichiers
    _write_atomic(symbols_path, bytes(symbols_bytes))
    header = 'id\toffset_octets\tlongueur_octets\ttype\tresume'
    _write_atomic_text(index_path, [header] + index_lines)

    # Bilan
    print(
        f'Bilan : {nb_files} fichiers traités, {nb_concepts} concepts indexés, '
        f'{nb_skipped_lines} lignes sautées, {nb_skipped_files} fichiers sans concept.'
    )
    return nb_files, nb_concepts, nb_skipped_lines, nb_skipped_files


# --------------------------------------------------------------------------- #
# Self‑test (option --epreuve)
# --------------------------------------------------------------------------- #

def _run_epreuve(root: Path) -> int:
    """
    Exécute les trois volets de l’épreuve décrits dans la spécification.
    Retourne 0 si tout passe, sinon un code d’erreur >0.
    """
    src_base = root / 'references' / 'livres_texte'
    dst_base = root / 'references' / 'livres_texte_concepts'

    # ------------------------------------------------------------------- #
    # 1️⃣ FORWARD : corpus minimal avec deux concepts valides
    # ------------------------------------------------------------------- #
    matiere = 'physique'
    livre = 'LivreTest'
    pre_dir = src_base / matiere / f'{livre}__PRE_MACHE'
    pre_dir.mkdir(parents=True, exist_ok=True)

    tsv_path = pre_dir / 'concepts.tsv'
    header = ['concept', 'nb_occurrences', 'unit_ids', 'types']
    concepts = [
        ['Théorème de Pythagore', '3', 'U001,U002', 'theoreme'],
        ['Loi de Newton', '5', 'U010', 'loi']
    ]
    with tsv_path.open('w', encoding='utf-8', newline='\n') as f:
        writer = csv.writer(f, delimiter='\t')
        writer.writerow(header)
        for row in concepts:
            writer.writerow(row)

    try:
        index_concepts(root)
    except Exception as e:
        print(f'Erreur FORWARD : {e}', file=sys.stderr)
        return 1

    # Vérifications existence
    symbols_path = dst_base / 'symbols.jsonl'
    index_path = dst_base / 'index.tsv'
    if not symbols_path.is_file() or not index_path.is_file():
        print('Fichiers manquants après FORWARD', file=sys.stderr)
        return 2

    # Lecture index.tsv
    with index_path.open('r', encoding='utf-8') as f:
        reader = csv.reader(f, delimiter='\t')
        rows = list(reader)

    if not rows or rows[0] != ['id', 'offset_octets', 'longueur_octets', 'type', 'resume']:
        print('En‑tête incorrecte dans index.tsv (FORWARD)', file=sys.stderr)
        return 3

    if len(rows) != 3:  # 1 header + 2 concepts
        print('Nombre de lignes inattendu dans index.tsv (FORWARD)', file=sys.stderr)
        return 4

    # Vérification round‑trip pour chaque concept
    with symbols_path.open('rb') as f_sym:
        for line in rows[1:]:
            uid, off_str, len_str, typ, resume = line
            offset = int(off_str)
            length = int(len_str)
            f_sym.seek(offset)
            data = f_sym.read(length)
            try:
                obj = json.loads(data.decode('utf-8'))
            except Exception as e:
                print(f'JSON invalide pour {uid} (FORWARD) : {e}', file=sys.stderr)
                return 5
            if obj.get('resume') != resume or obj.get('type') != typ:
                print(f'Incohérence métadonnées pour {uid} (FORWARD)', file=sys.stderr)
                return 6
            if obj.get('texte') is None or resume not in obj['texte']:
                print(f'Champ texte ne contient pas le concept original pour {uid} (FORWARD)', file=sys.stderr)
                return 7

    # ------------------------------------------------------------------- #
    # 2️⃣ REVERSE : fichiers mal formés ou vides
    # ------------------------------------------------------------------- #
    # a) concepts.tsv sans données (seulement l’en‑tête)
    livre_vide = 'LivreVide'
    pre_dir_vide = src_base / matiere / f'{livre_vide}__PRE_MACHE'
    pre_dir_vide.mkdir(parents=True, exist_ok=True)
    (pre_dir_vide / 'concepts.tsv').write_text('concept\tnb_occurrences\tunit_ids\ttypes\n', encoding='utf-8')

    # b) concepts.tsv avec ligne <4 colonnes
    livre_mal = 'LivreMalForme'
    pre_dir_mal = src_base / matiere / f'{livre_mal}__PRE_MACHE'
    pre_dir_mal.mkdir(parents=True, exist_ok=True)
    bad_tsv = pre_dir_mal / 'concepts.tsv'
    with bad_tsv.open('w', encoding='utf-8', newline='\n') as f:
        writer = csv.writer(f, delimiter='\t')
        writer.writerow(header)
        writer.writerow(['Concept incomplet', '2'])  # seulement 2 colonnes

    try:
        index_concepts(root)
    except Exception as e:
        print(f'Erreur REVERSE : {e}', file=sys.stderr)
        return 8

    # Vérifier que les fichiers de sortie existent toujours et restent valides
    if not symbols_path.is_file() or not index_path.is_file():
        print('Fichiers manquants après REVERSE', file=sys.stderr)
        return 9

    # ------------------------------------------------------------------- #
    # 3️⃣ ANTI‑ECRASEMENT : s’assurer de ne pas toucher au répertoire d’entrée
    # ------------------------------------------------------------------- #
    # Crée le répertoire d’entrée (s’il n’existait pas) et un fichier sentinel
    sentinel_dir = src_base
    sentinel_dir.mkdir(parents=True, exist_ok=True)
    sentinel_path = sentinel_dir / 'index.tsv'
    sentinel_content = 'sentinel\t0\t0\ttype\tresume\n'
    sentinel_path.write_text(sentinel_content, encoding='utf-8')

    # Lance l’indexation
    try:
        index_concepts(root)
    except Exception as e:
        print(f'Erreur ANTI‑ECRASEMENT : {e}', file=sys.stderr)
        return 10

    # Vérifie que le sentinel n’a pas été modifié
    if sentinel_path.read_text(encoding='utf-8') != sentinel_content:
        print('Le fichier sentinel a été écrasé (ANTI‑ECRASEMENT)', file=sys.stderr)
        return 11

    # Tous les volets passent
    return 0


# --------------------------------------------------------------------------- #
# Argument parsing & entry point
# --------------------------------------------------------------------------- #

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description='Indexe les concepts pour Claude‑Local‑Nexus.'
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
        index_concepts(args.racine)


if __name__ == '__main__':
    main()
