#!/usr/bin/env python3
import os
import sys
import json
import argparse
from pathlib import Path

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("query", nargs="*", help="Mots a chercher")
    parser.add_argument("-l", "--limit", type=int, default=10, help="Limite resultats")
    parser.add_argument("-r", "--read", help="ID du fragment a lire")
    args = parser.parse_args()

    ref_dir = Path(Path(__file__).parent).parent.joinpath("references")
    if not ref_dir.exists() or not ref_dir.is_dir():
        print(f"Aucun corpus trouve dans {ref_dir}")
        sys.exit(2)

    found_any_corpus = False
    matches = []
    
    for root, _, files in os.walk(ref_dir):
        if "index.tsv" in files:
            found_any_corpus = True
            idx_path = Path(root).joinpath("index.tsv")
            try:
                with open(idx_path, "r", encoding="utf-8") as f:
                    next(f)
                    for line in f:
                        cols = line.strip().split("\t")
                        if len(cols) < 5: continue
                        uid, offset, length, dtype, summary = cols
                        if all(q.lower() in summary.lower() for q in args.query):
                            matches.append((Path(root).name, uid, summary, offset, length))
            except Exception as e:
                print(f"Fichier illisible {idx_path}: {e}", file=sys.stderr)

    if not found_any_corpus:
        print(f"Aucun corpus n a ete trouve sous le repertoire des references {ref_dir}", file=sys.stderr)
        sys.exit(1)
    if args.read:
        for root, _, files in os.walk(ref_dir):
            if "symbols.jsonl" in files:
                sym_path = Path(root).joinpath("symbols.jsonl")
                try:
                    with open(sym_path, "rb") as f:
                        f.seek(0, 2)
                        f_size = f.tell()
                        # Recherche de l'ID dans l'index du rayon
                        idx_path = Path(root).joinpath("index.tsv")
                        with open(idx_path, "r", encoding="utf-8") as idx:
                            next(idx)
                            for line in idx:
                                cols = line.strip().split("\t")
                                if cols[0] == args.read:
                                    off, length = int(cols[1]), int(cols[2])
                                    f.seek(off)
                                    data = json.loads(f.read(length).decode("utf-8"))
                                    print(f"Cout: {length} / {f_size} octets")
                                    print(data.get("texte", ""))
                                    return 0
                except Exception as e:
                    print(f"Erreur lecture fragment {args.read}: {e}", file=sys.stderr)
        return 1

    if not matches:
        return 1

    for m in matches[:args.limit]:
        print(f"Rayon: {m[0]} | ID: {m[1]} | Resume: {m[2]}")
    
    return 0

if __name__ == "__main__":
    # Utilisation de chr(92) pour eviter le backslash litteral
    sep = chr(92)
    sys.exit(main())
