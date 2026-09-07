#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
nexus_indexer_texte.py

Indexe les livres texte présents sous <racine>/references/livres_texte.
Produit deux fichiers atomiques :
    - symbols.jsonl   (une ligne JSON par unité)
    - index.tsv       (méta‑données pour chaque ligne JSON)

Fonctionnement
-------------
1. Parcourt tous les répertoires
   <racine>/references/livres_texte/*/*__PRE_MACHE/unites_atomiques.tsv
2. Pour chaque ligne valide du TSV :
       - construit un UID unique :  "livtexte.<slug>#<id_source>"
       - crée l’objet JSON attendu par Nexus
       - écrit la ligne JSON dans symbols.jsonl (UTF‑8)
       - mémorise offset et longueur en octets pour index.tsv
3. Écrit index.tsv avec les colonnes :
       id  offset_octets  longueur_octets  type  resume
4. Toutes les écritures sont atomiques (fichiers temporaires → os.replace).

Idempotence : chaque exécution regénère complètement les deux fichiers.
Robustesse : les livres ou lignes mal formées sont simplement comptés et ignorés.

Option « --epreuve » exécute un test autonome dans un répertoire temporaire
et renvoie 0 si toutes les vérifications passent, sinon un code d’erreur >0.
"""

import argparse
import csv
import json
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import List, Tuple

# --------------------------------------------------------------------------- #
# Helpers (sans effets de bord à l'import)
# --------------------------------------------------------------------------- #

def _slugify(text: str) -> str:
    """Retourne un slug stable et court à partir d'un texte."""
    text = text.lower()
    text = re.sub(r'[^a-z0-9]+', '_', text)
    text = text.strip('_')
    return text or 'unknown'


def _read_tsv(path: Path) -> Tuple[List[List[str]], int]:
    """
    Lit un TSV en mode texte, renvoie la liste des lignes (listes de champs)
    et le nombre de lignes ignorées (mal formées).
    """
    rows = []
    skipped = 0
    with path.open(newline='', encoding='utf-8') as f:
        reader = csv.reader(f, delimiter='\t')
        next(reader, None)  # on ignore l'en‑tête
        for fields in reader:
            if len(fields) < 10:
                skipped += 1
                continue
            rows.append(fields)
    return rows, skipped


def _write_atomic(target: Path, data: bytes) -> None:
    """Écrit *data* dans un fichier temporaire puis le remplace atomiquement."""
    tmp = target.with_suffix('.tmp')
    with tmp.open('wb') as f:
        f.write(data)
    os.replace(tmp, target)


def _write_atomic_text(target: Path, lines: List[str]) -> None:
    """Écrit une liste de lignes texte (sans \n) de façon atomique."""
    tmp = target.with_suffix('.tmp')
    with tmp.open('w', encoding='utf-8', newline='\n') as f:
        for line in lines:
            f.write(line + '\n')
    os.replace(tmp, target)


# --------------------------------------------------------------------------- #
# Core indexing logic
# --------------------------------------------------------------------------- #

def index_texte(root: Path) -> Tuple[int, int, int, int]:
    """
    Parcourt les livres texte sous *root*/*references/livres_texte*,
    crée symbols.jsonl et index.tsv.

    Retourne (nb_livres, nb_unites, nb_lignes_sautées, nb_livres_sautés).
    """
    base_dir = root / 'references' / 'livres_texte'
    symbols_path = base_dir / 'symbols.jsonl'
    index_path = base_dir / 'index.tsv'

    # Accumulate data
    index_lines: List[str] = []
    symbols_bytes = bytearray()
    nb_livres = 0
    nb_unites = 0
    nb_lignes_sautées = 0
    nb_livres_sautés = 0

    # Recherche des fichiers unites_atomiques.tsv
    pattern = '**/*__PRE_MACHE/unites_atomiques.tsv'
    for tsv_path in base_dir.glob(pattern):
        # Dérivation du nom du livre et du slug
        pre_mache_dir = tsv_path.parent
        book_dir = pre_mache_dir.parent
        book_name = book_dir.name
        slug = _slugify(book_name)

        rows, skipped = _read_tsv(tsv_path)
        nb_lignes_sautées += skipped

        if not rows:
            # Aucunité valide → on compte le livre comme sauté
            nb_livres_sautés += 1
            continue

        nb_livres += 1
        for fields in rows:
            (uid_src, typ, _, _, titre, _, _, _, _, texte_verbatim) = fields[:10]

            uid = f'livtexte.{slug}#{uid_src}'
            obj = {
                "id": uid,
                "resume": titre,
                "livre": book_name,
                "type": typ,
                "texte": texte_verbatim
            }
            json_line = json.dumps(obj, ensure_ascii=False)
            encoded = json_line.encode('utf-8')
            offset = len(symbols_bytes)
            length = len(encoded)

            # Ajout à symbols.jsonl
            symbols_bytes.extend(encoded + b'\n')

            # Ajout à index.tsv
            index_line = f'{uid}\t{offset}\t{length}\t{typ}\t{titre}'
            index_lines.append(index_line)

            nb_unites += 1

    # Écriture atomique des deux fichiers
    _write_atomic(symbols_path, bytes(symbols_bytes))
    # Ajout de l’en‑tête obligatoire à index.tsv
    header_line = 'id\toffset_octets\tlongueur_octets\ttype\tresume'
    _write_atomic_text(index_path, [header_line] + index_lines)

    # Bilan
    print(f'Bilan : {nb_livres} livres traités, {nb_unites} unités indexées, '
          f'{nb_lignes_sautées} lignes sautées, {nb_livres_sautés} livres sans unité.')

    return nb_livres, nb_unites, nb_lignes_sautées, nb_livres_sautés


# --------------------------------------------------------------------------- #
# Self‑test (option --epreuve)
# --------------------------------------------------------------------------- #

def _run_epreuve(root: Path) -> int:
    """
    Exécute le test décrit dans la spécification.
    Retourne 0 si tout passe, sinon un code d’erreur >0.
    """
    base_dir = root / 'references' / 'livres_texte'

    # ---------- FORWARD ----------
    # Crée un livre avec une seule unité
    matiere = 'physique'
    titre = 'LivreTest'
    pre_dir = base_dir / matiere / f'{titre}__PRE_MACHE'
    pre_dir.mkdir(parents=True, exist_ok=True)

    tsv_path = pre_dir / 'unites_atomiques.tsv'
    header = ['id', 'type', 'mot_cle_source', 'numero', 'titre',
              'page_pdf_debut', 'page_pdf_fin', 'char_debut',
              'char_fin', 'texte_verbatim']
    unit_id = 'U1'
    unit_type = 'definition'
    unit_titre = 'Définition test'
    unit_texte = 'Ceci est le texte de l’unité.'
    with tsv_path.open('w', encoding='utf-8', newline='\n') as f:
        writer = csv.writer(f, delimiter='\t')
        writer.writerow(header)
        writer.writerow([unit_id, unit_type, '', '', unit_titre,
                         '', '', '', '', unit_texte])

    # Lance l’indexation
    try:
        index_texte(root)
    except Exception as e:
        print(f'Erreur lors de l’indexation FORWARD : {e}', file=sys.stderr)
        return 1

    # Vérifie l’existence des fichiers
    symbols_path = base_dir / 'symbols.jsonl'
    index_path = base_dir / 'index.tsv'
    if not symbols_path.is_file() or not index_path.is_file():
        print('Fichiers symbols.jsonl ou index.tsv manquants (FORWARD)', file=sys.stderr)
        return 2

    # Lecture de index.tsv
    with index_path.open('r', encoding='utf-8') as f:
        reader = csv.reader(f, delimiter='\t')
        rows = list(reader)

    # Vérifie la présence de l’en‑tête
    if not rows or rows[0] != ['id', 'offset_octets', 'longueur_octets', 'type', 'resume']:
        print('En‑tête manquant ou incorrect dans index.tsv (FORWARD)', file=sys.stderr)
        return 3

    if len(rows) != 2:
        print('index.tsv ne contient pas exactement une ligne de données (FORWARD)', file=sys.stderr)
        return 4

    uid, offset_str, length_str, typ, resume = rows[1]
    offset = int(offset_str)
    length = int(length_str)

    # Lecture de la ligne JSON correspondante
    with symbols_path.open('rb') as f:
        f.seek(offset)
        data = f.read(length)
    try:
        obj = json.loads(data.decode('utf-8'))
    except Exception as e:
        print(f'Impossible de décoder la ligne JSON (FORWARD) : {e}', file=sys.stderr)
        return 4

    if obj.get('texte') != unit_texte:
        print('Le champ texte ne correspond pas à l’original (FORWARD)', file=sys.stderr)
        return 5

    # ---------- REVERSE ----------
    # Crée un livre sans unites_atomiques.tsv
    titre2 = 'LivreSansUnites'
    pre_dir2 = base_dir / matiere / f'{titre2}__PRE_MACHE'
    pre_dir2.mkdir(parents=True, exist_ok=True)  # pas de TSV

    # Ré‑indexe (doit ne pas planter)
    try:
        index_texte(root)
    except Exception as e:
        print(f'Erreur lors de l’indexation REVERSE : {e}', file=sys.stderr)
        return 6

    # Vérifie que l’en‑tête est toujours présent après ré‑indexation
    index_path = base_dir / 'index.tsv'
    with index_path.open('r', encoding='utf-8') as f:
        reader = csv.reader(f, delimiter='\t')
        rows = list(reader)
    if not rows or rows[0] != ['id', 'offset_octets', 'longueur_octets', 'type', 'resume']:
        print('En‑tête manquant ou incorrect après ré‑indexation (REVERSE)', file=sys.stderr)
        return 7

    # Si on arrive ici, tout s’est bien passé
    return 0


# --------------------------------------------------------------------------- #
# Argument parsing & entry point
# --------------------------------------------------------------------------- #

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description='Indexe les livres texte pour Claude‑Local‑Nexus.'
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
        index_texte(args.racine)


if __name__ == '__main__':
    main()