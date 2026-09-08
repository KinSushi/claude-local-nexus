#!/usr/bin/env python3

"""
nexus_indexer_resumes.py

Indexe les résumés de sections présents sous
<racine>/references/livres_texte/*/*__PRE_MACHE/resumes_sections.tsv.
Produit deux fichiers atomiques :
    - symbols.jsonl   (une ligne JSON par résumé de section)
    - index.tsv       (méta‑données pour chaque ligne JSON)

Fonctionnement
-------------
1. Parcourt tous les répertoires
   <racine>/references/livres_texte/*/*__PRE_MACHE/resumes_sections.tsv
2. Pour chaque ligne valide du TSV (≥ 5 colonnes) :
       - construit un UID unique :  "resume.<slug(livre)>#<section_id>"
         (suffixe .2, .3… en cas de collision)
       - crée l’objet JSON attendu par Nexus
       - écrit la ligne JSON dans symbols.jsonl (UTF‑8)
       - mémorise offset et longueur en octets pour index.tsv
3. Écrit index.tsv avec les colonnes :
       id  offset_octets  longueur_octets  type  resume
4. Toutes les écritures sont atomiques (fichiers temporaires → os.replace).

Robustesse : fichiers illisibles, en‑tête manquante ou lignes < 5 colonnes sont comptés
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


def _read_tsv(path: Path) -> tuple[list[list[str]], int]:
    """
    Lit un TSV en mode texte, renvoie la liste des lignes (listes de champs)
    et le nombre de lignes ignorées (mal formées ou < 5 colonnes).
    """
    rows: list[list[str]] = []
    skipped = 0
    try:
        with path.open(newline='', encoding='utf-8') as f:
            reader = csv.reader(f, delimiter='\t')
            header = next(reader, None)
            if header is None or len(header) < 5:
                # en‑tête absente ou insuffisante → tout le fichier est sauté
                return [], 0
            for fields in reader:
                if len(fields) < 5:
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


def _write_atomic_text(target: Path, lines: list[str]) -> None:
    """Écrit une liste de lignes texte (sans \\n) de façon atomique."""
    tmp = target.with_suffix('.tmp')
    with tmp.open('w', encoding='utf-8', newline='\n') as f:
        for line in lines:
            f.write(line + '\n')
    os.replace(tmp, target)


# --------------------------------------------------------------------------- #
# Core indexing logic
# --------------------------------------------------------------------------- #

def index_resumes(root: Path) -> tuple[int, int, int, int]:
    """
    Parcourt les résumés sous *root*/references/livres_texte,
    crée symbols.jsonl et index.tsv dans *root*/references/livres_texte_resumes.

    Retourne (nb_fichiers, nb_resumes, nb_lignes_sautées, nb_fichiers_sautés).
    """
    src_base = root / 'references' / 'livres_texte'
    dst_base = root / 'references' / 'livres_texte_resumes'
    dst_base.mkdir(parents=True, exist_ok=True)

    symbols_path = dst_base / 'symbols.jsonl'
    index_path = dst_base / 'index.tsv'

    index_lines: list[str] = []
    symbols_bytes = bytearray()

    uid_counts: dict[str, int] = {}

    nb_files = 0
    nb_resumes = 0
    nb_skipped_lines = 0
    nb_skipped_files = 0

    pattern = '**/*__PRE_MACHE/resumes_sections.tsv'
    for tsv_path in src_base.glob(pattern):
        nb_files += 1

        rows, skipped = _read_tsv(tsv_path)
        nb_skipped_lines += skipped

        if not rows:
            nb_skipped_files += 1
            continue

        # extraction du livre et de la matière
        pre_dir = tsv_path.parent                     # <Livre>__PRE_MACHE
        book_dir_name = pre_dir.name
        book_name = book_dir_name.removesuffix('__PRE_MACHE')
        matiere = pre_dir.parent.name                 # <Matiere>

        slug_book = _slugify(book_name)

        for fields in rows:
            section_id, titre_section, resume_mecanique, verbatim, nb_phrases = fields[:5]

            # UID avec gestion de collision
            base_uid = f'resume.{slug_book}#{section_id}'
            uid = base_uid
            count = uid_counts.get(base_uid, 0)
            while uid in uid_counts:
                count += 1
                uid = f'{base_uid}.{count}'
            uid_counts[base_uid] = count

            texte = f"{titre_section} :: {resume_mecanique} :: {verbatim}"

            obj = {
                "id": uid,
                "resume": titre_section,
                "livre": book_name,
                "matiere": matiere,
                "type": "resume_section",
                "section_id": section_id,
                "texte": texte
            }

            json_line = json.dumps(obj, ensure_ascii=False)
            encoded = json_line.encode('utf-8')
            offset = len(symbols_bytes)
            length = len(encoded)

            symbols_bytes.extend(encoded + b'\n')
            index_line = f'{uid}\t{offset}\t{length}\tresume_section\t{titre_section}'
            index_lines.append(index_line)

            nb_resumes += 1

    # Écriture atomique des deux fichiers
    _write_atomic(symbols_path, bytes(symbols_bytes))
    header = 'id\toffset_octets\tlongueur_octets\ttype\tresume'
    _write_atomic_text(index_path, [header] + index_lines)

    # Bilan
    print(
        f'Bilan : {nb_files} fichiers traités, {nb_resumes} résumés indexés, '
        f'{nb_skipped_lines} lignes sautées, {nb_skipped_files} fichiers sans résumés.'
    )
    return nb_files, nb_resumes, nb_skipped_lines, nb_skipped_files


# --------------------------------------------------------------------------- #
# Self‑test (option --epreuve)
# --------------------------------------------------------------------------- #

def _run_epreuve(root: Path) -> int:
    """
    Exécute les trois volets de l’épreuve décrits dans la spécification.
    Retourne 0 si tout passe, sinon un code d’erreur >0.
    """
    src_base = root / 'references' / 'livres_texte'
    dst_base = root / 'references' / 'livres_texte_resumes'

    # ------------------------------------------------------------------- #
    # 1️⃣ FORWARD : corpus minimal avec deux résumés valides
    # ------------------------------------------------------------------- #
    matiere = 'philosophie'
    livre = 'LivreTest'
    pre_dir = src_base / matiere / f'{livre}__PRE_MACHE'
    pre_dir.mkdir(parents=True, exist_ok=True)

    tsv_path = pre_dir / 'resumes_sections.tsv'
    header = ['section_id', 'titre_section', 'resume_mecanique', 'verbatim', 'nb_phrases_utilisees']
    rows = [
        ['S1', 'Introduction', 'Bref aperçu', 'Ceci est le texte.', '3'],
        ['S2', 'Conclusion', 'Synthèse', 'Fin du texte.', '2']
    ]
    with tsv_path.open('w', encoding='utf-8', newline='\n') as f:
        writer = csv.writer(f, delimiter='\t')
        writer.writerow(header)
        writer.writerows(rows)

    try:
        index_resumes(root)
    except Exception as e:
        print(f'Erreur FORWARD : {e}', file=sys.stderr)
        return 1

    symbols_path = dst_base / 'symbols.jsonl'
    index_path = dst_base / 'index.tsv'
    if not symbols_path.is_file() or not index_path.is_file():
        print('Fichiers manquants après FORWARD', file=sys.stderr)
        return 2

    # Vérification du contenu de index.tsv
    with index_path.open('r', encoding='utf-8') as f:
        reader = csv.reader(f, delimiter='\t')
        index_rows = list(reader)

    if not index_rows or index_rows[0] != ['id', 'offset_octets', 'longueur_octets', 'type', 'resume']:
        print('En‑tête incorrecte dans index.tsv (FORWARD)', file=sys.stderr)
        return 3

    if len(index_rows) != 3:  # 1 header + 2 résumés
        print('Nombre de lignes inattendu dans index.tsv (FORWARD)', file=sys.stderr)
        return 4

    # Mapping titre_section -> verbatim from fixture
    attendu_verbatim = {r[1]: r[3] for r in rows}

    # Vérification round‑trip
    with symbols_path.open('rb') as f_sym:
        for line in index_rows[1:]:
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
            if obj.get('texte') is None or attendu_verbatim.get(obj.get('resume', ''), '\x00') not in obj['texte']:
                # on vérifie que le champ 'verbatim' de la ligne d'origine apparaît
                print(f'Champ texte ne contient pas le verbatim d’origine pour {uid} (FORWARD)', file=sys.stderr)
                return 7

    # ------------------------------------------------------------------- #
    # 2️⃣ REVERSE : fichiers mal formés ou vides
    # ------------------------------------------------------------------- #
    # a) fichier avec seulement l’en‑tête
    livre_vide = 'LivreVide'
    pre_dir_vide = src_base / matiere / f'{livre_vide}__PRE_MACHE'
    pre_dir_vide.mkdir(parents=True, exist_ok=True)
    (pre_dir_vide / 'resumes_sections.tsv').write_text('section_id\ttitre_section\tresume_mecanique\tverbatim\tnb_phrases_utilisees\n', encoding='utf-8')

    # b) fichier avec ligne <5 colonnes
    livre_mal = 'LivreMalForme'
    pre_dir_mal = src_base / matiere / f'{livre_mal}__PRE_MACHE'
    pre_dir_mal.mkdir(parents=True, exist_ok=True)
    bad_tsv = pre_dir_mal / 'resumes_sections.tsv'
    with bad_tsv.open('w', encoding='utf-8', newline='\n') as f:
        writer = csv.writer(f, delimiter='\t')
        writer.writerow(header)
        writer.writerow(['S3', 'Titre incomplet'])  # seulement 2 colonnes

    try:
        index_resumes(root)
    except Exception as e:
        print(f'Erreur REVERSE : {e}', file=sys.stderr)
        return 8

    if not symbols_path.is_file() or not index_path.is_file():
        print('Fichiers manquants après REVERSE', file=sys.stderr)
        return 9

    # ------------------------------------------------------------------- #
    # 3️⃣ ANTI‑ECRASEMENT : s’assurer de ne pas toucher au répertoire d’entrée
    # ------------------------------------------------------------------- #
    sentinel_dir = src_base
    sentinel_dir.mkdir(parents=True, exist_ok=True)
    sentinel_path = sentinel_dir / 'index.tsv'
    sentinel_content = 'sentinel\t0\t0\ttype\tresume\n'
    sentinel_path.write_text(sentinel_content, encoding='utf-8')

    try:
        index_resumes(root)
    except Exception as e:
        print(f'Erreur ANTI‑ECRASEMENT : {e}', file=sys.stderr)
        return 10

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
        description='Indexe les résumés de sections pour Claude‑Local‑Nexus.'
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
        index_resumes(args.racine)


if __name__ == '__main__':
    main()
