#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import argparse
import os
import json
import re
import time

# SEUIL_CORPS est le nombre minimal de caractères qu'un chapitre doit contenir pour qu'un titre candidat soit retenu, ce qui élimine les étiquettes de schémas rendues par pdftotext.
SEUIL_CORPS = 1500

def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument('--source', required=True, help='racine des .txt')
    p.add_argument('--cible', required=True, help='racine de sortie')
    p.add_argument('--calibre', type=int, default=3000, help='taille visee d un fragment en caracteres')
    p.add_argument('--minutes', type=int, default=0, help='arret apres M minutes')
    return p.parse_args()

def load_index(index_path):
    processed = set()
    if not os.path.isfile(index_path):
        return processed
    with open(index_path, 'r', encoding='utf-8') as f:
        for line in f:
            parts = line.rstrip('\n').split('\t')
            if len(parts) >= 2:
                processed.add(parts[1])  # livre
    return processed

def is_title(lines, i):
    """
    Détecte un titre de chapitre de façon stricte.
    Retourne True si la ligne i de `lines` correspond à un titre.
    """
    line = lines[i]
    stripped = line.strip()
    if not stripped:
        return False

    # rejet de lignes trop courtes
    if len(stripped) < 4:
        return False

    # rejet de ponctuation terminale non souhaitée
    if stripped.endswith(',') or stripped.endswith(':'):
        return False

    # rejet d'adresses e‑mail ou d'URL
    low = stripped.lower()
    if '@' in low or low.startswith('http://') or low.startswith('https://'):
        return False

    # rejet de numéros de page isolés
    if stripped.isdigit():
        return False

    # rejet de légendes de figures / tables
    if stripped.startswith(('Figure ', 'Fig.', 'Fig ', 'Table ', 'Table.', 'Table')):
        return False

    # 1. numérotation explicite « 1. … »
    if re.match(r'^\d+\.\s', stripped):
        return True

    # 2. mots-clés « Chapter/Chapitre/Section » suivis d’un nombre
    if re.match(r'^(Chapter|Chapitre|Section)\s+\d+', stripped, re.IGNORECASE):
        return True

    # 3. ligne entièrement en majuscules d’au moins 10 caractères
    if stripped.isupper() and len(stripped) >= 10:
        return True

    # 4. ligne courte isolée entre deux lignes vides
    prev_blank = (i == 0) or not lines[i - 1].strip()
    next_blank = (i + 1 == len(lines)) or not lines[i + 1].strip()
    return prev_blank and next_blank and len(stripped) <= 30

def split_chapters(text):
    lines = text.splitlines()
    # Pass 1 – collect candidate title line indices
    candidate_idxs = [i for i in range(len(lines)) if is_title(lines, i)]

    # Pass 2 – filter candidates according to body length
    kept_idxs = []
    for pos, idx in enumerate(candidate_idxs):
        # end of the current segment (exclusive)
        next_idx = candidate_idxs[pos + 1] if pos + 1 < len(candidate_idxs) else len(lines)
        # texte entre le titre actuel et le prochain titre (excluant le prochain titre)
        body = "\n".join(lines[idx + 1:next_idx])
        body_len = len(body)
        if pos == len(candidate_idxs) - 1:
            # dernier candidat : on le garde seulement si le texte restant est suffisant
            if body_len >= SEUIL_CORPS:
                kept_idxs.append(idx)
        else:
            if body_len >= SEUIL_CORPS:
                kept_idxs.append(idx)

    # Aucun titre valide trouvé → tout le texte devient un seul chapitre sans titre
    if not kept_idxs:
        return [('', text.strip())]

    # Pass 3 – construire les chapitres à partir des indices retenus
    chapters = []
    for pos, idx in enumerate(kept_idxs):
        start = idx
        end = kept_idxs[pos + 1] if pos + 1 < len(kept_idxs) else len(lines)
        chap_lines = lines[start:end]
        title = chap_lines[0].strip()
        chap_text = "\n".join(chap_lines).strip()
        chapters.append((title, chap_text))

    return chapters

def cut_menu(chap_text, calibre):
    if not chap_text:
        return []
    length = len(chap_text)
    if length <= calibre:
        return [chap_text]
    fragments = []
    start = 0
    min_size = max(1, calibre // 4)
    while start < length:
        end = min(start + calibre, length)
        min_cut = min(start + min_size, length)
        cut = -1
        # 1. recherche de la fin de phrase
        for i in range(end - 1, min_cut - 1, -1):
            if chap_text[i] in '.!?':
                cut = i + 1
                break
        # 2. sinon recherche de fin de ligne
        if cut == -1:
            for i in range(end - 1, min_cut - 1, -1):
                if chap_text[i] == '\n':
                    cut = i + 1
                    break
        # 3. sinon position brute
        if cut == -1:
            cut = end
        # 4. éviter de couper un mot
        while cut < length and not chap_text[cut].isspace():
            cut += 1
        fragment = chap_text[start:cut].strip()
        if fragment:
            fragments.append(fragment)
        # sortir si on a atteint la fin du texte
        if cut >= length:
            break
        # 5. calcul du prochain départ avec recouvrement ≤200
        next_start = cut - 200
        if next_start <= start:
            next_start = start + 1
        start = next_start
    return fragments

def main():
    args = parse_args()
    src = args.source
    dst = args.cible
    calibre = args.calibre
    minutes = args.minutes

    if not os.path.isdir(src):
        sys.exit(3)

    os.makedirs(dst, exist_ok=True)
    symbols_path = os.path.join(dst, 'symbols.jsonl')
    index_path = os.path.join(dst, 'index.tsv')
    decoupage_path = os.path.join(dst, '_decoupage.json')

    processed_books = load_index(index_path)

    start_time = time.time()
    time_limit = minutes * 60 if minutes > 0 else None

    total_books = 0
    frag_chap = 0
    frag_menu = 0
    total_bytes = 0

    with open(symbols_path, 'ab') as sym_file,          open(index_path, 'a', encoding='utf-8') as idx_file:
        for root, _, files in os.walk(src):
            for fname in files:
                if not fname.lower().endswith('.txt'):
                    continue
                book_name = os.path.splitext(fname)[0]
                if book_name in processed_books:
                    continue

                if time_limit and (time.time() - start_time) > time_limit:
                    break

                total_books += 1
                fpath = os.path.join(root, fname)
                with open(fpath, 'r', encoding='utf-8', errors='replace') as f:
                    content = f.read()

                chapters = split_chapters(content)
                for chap_idx, (chap_title, chap_text) in enumerate(chapters):
                    # chapitre fragment
                    frag_id = f"{book_name}_chap_{chap_idx}"
                    record = {
                        "id": frag_id,
                        "livre": book_name,
                        "chapitre": chap_title,
                        "niveau": "chapitre",
                        "rang": chap_idx,
                        "caracteres": len(chap_text),
                        "texte": chap_text
                    }
                    line = json.dumps(record, ensure_ascii=False) + "\n"
                    offset = sym_file.tell()
                    sym_file.write(line.encode('utf-8'))
                    idx_file.write(f"{frag_id}\t{book_name}\tchapitre\t{offset}\t{len(line.encode('utf-8'))}\n")
                    total_bytes += len(line.encode('utf-8'))
                    frag_chap += 1

                    # menu fragments
                    menu_frags = cut_menu(chap_text, calibre)
                    for men_idx, men_text in enumerate(menu_frags):
                        frag_id = f"{book_name}_menu_{chap_idx}_{men_idx}"
                        record = {
                            "id": frag_id,
                            "livre": book_name,
                            "chapitre": chap_title,
                            "niveau": "menu",
                            "rang": men_idx,
                            "caracteres": len(men_text),
                            "texte": men_text
                        }
                        line = json.dumps(record, ensure_ascii=False) + "\n"
                        offset = sym_file.tell()
                        sym_file.write(line.encode('utf-8'))
                        idx_file.write(f"{frag_id}\t{book_name}\tmenu\t{offset}\t{len(line.encode('utf-8'))}\n")
                        total_bytes += len(line.encode('utf-8'))
                        frag_menu += 1

    elapsed = time.time() - start_time
    summary = {
        "livres_traites": total_books,
        "fragments_chapitre": frag_chap,
        "fragments_menu": frag_menu,
        "octets": total_bytes,
        "secondes": elapsed
    }
    with open(decoupage_path, 'w', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print(f"Traitement terminé : {summary}")

    sys.exit(0 if total_books > 0 else 1)

if __name__ == '__main__':
    main()
