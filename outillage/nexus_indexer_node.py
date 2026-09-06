#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys

import argparse
import json
import os
import re
import html
from collections import Counter

# Constants from specification
LIB_NAME = "node"
CONTAINER_KEYS = {
    "modules", "classes", "methods", "classMethods",
    "globals", "miscs", "properties"
}
SYMBOL_TYPES = {"method", "class", "classMethod", "module", "global"}

def clean_html(text: str) -> str:
    """Remove HTML tags and decode common entities."""
    no_tags = re.sub(r'<[^>]+>', '', text or '')
    return html.unescape(no_tags)

def clean_signature(text: str) -> str:
    """Remove back‑ticks from a signature."""
    return (text or '').replace('`', '')

def is_valid_name(name: str) -> bool:
    """Return True if the identifier segment respects the naming rules."""
    return bool(name) and ' ' not in name and len(name) <= 60 and not name.endswith('.') and '(' not in name and ')' not in name

def first_sentence(text: str) -> str:
    """Return the first sentence, limited to 200 characters."""
    txt = (text or '').strip()
    match = re.search(r'\.(\s|$)', txt)
    sentence = txt[:match.end()].strip() if match else txt
    return sentence[:200]

def normalize_field(text: str) -> str:
    """Replace newlines, carriage returns, tabs with a space, collapse spaces, strip."""
    if not isinstance(text, str):
        return text
    cleaned = re.sub(r'[\r\n\t]+', ' ', text)
    cleaned = re.sub(r'\s+', ' ', cleaned)
    return cleaned.strip()

def walk(node, ancestors, symbols, counters):
    """Recursive traversal building symbols."""
    if isinstance(node, dict):
        # Determine qualified name for children
        current_name = node.get("name")
        new_ancestors = ancestors
        if current_name:
            new_ancestors = ancestors + [current_name]

        # Symbol detection
        if ("name" in node) and (("signatures" in node) or (node.get("type") in SYMBOL_TYPES)):
            qual_id = ".".join(ancestors + [node["name"]])
            # Validate the name and each segment of the qualified identifier
            if not is_valid_name(node["name"]) or not all(is_valid_name(seg) for seg in qual_id.split('.')):
                # Rejet : entrée de prose
                counters["rejected_prose"] += 1
            else:
                symbol = {
                    "id": qual_id,
                    "nom_court": node["name"],
                    "type": node.get("type", ""),
                    "lib": LIB_NAME,
                    "lib_version": args.version,
                    "signature": clean_signature(node.get("textRaw", "")),
                    "docstring_brut": clean_html(node.get("desc", "")),
                    "resume": first_sentence(clean_html(node.get("desc", "")))
                }
                symbols.append(symbol)

        # Recurse into container keys
        for key in CONTAINER_KEYS:
            if key in node and isinstance(node[key], list):
                for child in node[key]:
                    walk(child, new_ancestors, symbols, counters)

    elif isinstance(node, list):
        for item in node:
            walk(item, ancestors, symbols, counters)

def main():
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    parser = argparse.ArgumentParser(description="Node.js documentation indexer for nexus_doc")
    parser.add_argument("--source", required=True, help="Path to all.json")
    parser.add_argument("--cible", required=True, help="Output directory")
    parser.add_argument("--version", required=True, help="Node.js version string (e.g. v22.23.2)")
    global args
    args = parser.parse_args()

    # Verify source existence
    if not os.path.isfile(args.source):
        sys.exit(3)

    # Prepare output paths
    symbols_path = os.path.join(args.cible, "symbols.jsonl")
    index_path = os.path.join(args.cible, "index.tsv")

    # Do not overwrite existing files
    for p in (symbols_path, index_path):
        if os.path.exists(p):
            print(f"Erreur : le fichier cible « {p} » existe déjà.", file=sys.stderr)
            sys.exit(1)

    # Load source JSON
    try:
        with open(args.source, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"Erreur de lecture du source : {e}", file=sys.stderr)
        sys.exit(1)

    # Collect symbols
    symbols = []
    counters = {"rejected_prose": 0}
    walk(data, [], symbols, counters)

    # Generate alias entries
    alias_added = 0
    alias_collisions = 0
    existing_ids = {sym["id"] for sym in symbols}
    for sym in list(symbols):  # copy to avoid modifying during iteration
        parts = sym["id"].split('.')
        if len(parts) >= 3:
            alias_id = f"{parts[0]}.{parts[-1]}"
            if alias_id in existing_ids:
                alias_collisions += 1
                continue
            alias_entry = sym.copy()
            alias_entry["id"] = alias_id
            symbols.append(alias_entry)
            existing_ids.add(alias_id)
            alias_added += 1

    if not symbols:
        # No symbols written → exit code 1 per spec
        sys.exit(1)

    # Write symbols.jsonl and build index entries
    index_entries = []
    offset = 0
    try:
        with open(symbols_path, "wb") as sym_f:
            for sym in symbols:
                line = json.dumps(sym, ensure_ascii=False) + "\n"
                encoded = line.encode("utf-8")
                length = len(encoded)
                sym_f.write(encoded)
                norm_id = normalize_field(sym["id"])
                norm_type = normalize_field(sym["type"])
                norm_resume = normalize_field(sym["resume"])
                index_entries.append((norm_id, offset, length, norm_type, norm_resume))
                offset += length
    except Exception as e:
        print(f"Erreur d'écriture du fichier symbols.jsonl : {e}", file=sys.stderr)
        sys.exit(1)

    # Write index.tsv
    try:
        with open(index_path, "w", encoding="utf-8", newline="") as idx_f:
            idx_f.write("id\toffset_octets\tlongueur_octets\ttype\tresume\n")
            for entry in index_entries:
                idx_f.write("\t".join(str(v) for v in entry) + "\n")
    except Exception as e:
        print(f"Erreur d'écriture du fichier index.tsv : {e}", file=sys.stderr)
        sys.exit(1)

    # Statistics
    total = len(symbols)
    per_type = Counter(sym["type"] for sym in symbols)
    size_sym = os.path.getsize(symbols_path)
    size_idx = os.path.getsize(index_path)

    print(f"Nombre total de symboles : {total}")
    for t, c in per_type.items():
        print(f"  {t} : {c}")
    print(f"Taille de symbols.jsonl : {size_sym} octets")
    print(f"Taille de index.tsv     : {size_idx} octets")
    print(f"Entrées rejetées pour prose : {counters['rejected_prose']}")
    print(f"Alias ajoutés : {alias_added}")

    sys.exit(0)


if __name__ == "__main__":
    main()
