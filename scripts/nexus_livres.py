#!/usr/bin/env python3
import os
import sys
import json
import argparse
import datetime
from pathlib import Path

# 6164 entrées perdues sur trois index à six colonnes
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

def _iter_index(idx_path):
    """Yield rows of index.tsv as dicts keyed by column name."""
    try:
        with open(idx_path, "r", encoding="utf-8") as f:
            header = f.readline()
            if not header:
                print(f"Fichier illisible {idx_path}: entete manquante", file=sys.stderr)
                return
            cols = header.rstrip("\n").split("\t")
            colpos = {name: i for i, name in enumerate(cols)}
            required = ["id", "offset_octets", "longueur_octets", "type", "resume"]
            missing = [c for c in required if c not in colpos]
            if missing:
                print(f"Fichier illisible {idx_path}: colonne(s) manquante(s) {', '.join(missing)}",
                      file=sys.stderr)
                return
            for line in f:
                parts = line.rstrip("\n").split("\t")
                if len(parts) < len(cols):
                    continue
                yield {
                    "id": parts[colpos["id"]],
                    "offset_octets": parts[colpos["offset_octets"]],
                    "longueur_octets": parts[colpos["longueur_octets"]],
                    "type": parts[colpos["type"]],
                    "resume": parts[colpos["resume"]],
                }
    except Exception as e:
        print(f"Fichier illisible {idx_path}: {e}", file=sys.stderr)

def _log_consultation(mode, query_or_id, count, bytes_read=0):
    """Trace a consultation in .nexus/consultations.jsonl (JSON lines).
    POURQUOI: un chapitre attendait pendant qu'on concevait de memoire;
    sans trace, aucun controle ne sait si le corpus a ete consulte.
    L'ecriture ne doit jamais faire echouer l'outil."""
    try:
        log_dir = Path(__file__).resolve().parent.parent / ".nexus"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / "consultations.jsonl"
        entry = {
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "mode": mode,
            "query": query_or_id if mode == "recherche" else None,
            "id": query_or_id if mode == "lecture" else None,
            "count": count,
            "bytes": bytes_read,
        }
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception:
        pass

def _format_fragment(data):
    """Return (rendering, known_keys_found) for a fragment."""
    if "texte" in data:
        return data["texte"], ["texte"]
    code_cles = ("signature", "docstring_brut", "implementation")
    found = [c for c in code_cles if c in data]
    if not found:
        return None, []
    parts = [data.get(c, "") for c in found]
    affiche = "\n\n".join(p for p in parts if p)
    if not affiche:
        return None, found
    return affiche, found


def _score_entry(row, query):
    """Return (keep, score) for a row against query terms."""
    if not query:
        return True, 1
    resume = row["resume"].lower()
    ident = row["id"].lower()
    kind = row["type"].lower()
    score = 0
    for term in query:
        t = term.lower()
        hits = resume.count(t) + ident.count(t) + kind.count(t)
        if hits == 0:
            return False, 0
        score += hits
    return True, score


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("query", nargs="*", help="Mots a chercher")
    parser.add_argument("-l", "--limit", type=int, default=10,
                        help="Limite resultats")
    parser.add_argument("-r", "--read", help="ID du fragment a lire")
    args = parser.parse_args()

    ref_dir = Path(Path(__file__).parent).parent.joinpath("references")
    if not ref_dir.exists() or not ref_dir.is_dir():
        print(f"Aucun corpus trouve dans {ref_dir}")
        sys.exit(1)

    found_any_corpus = False
    matches = []

    for root, _, files in os.walk(ref_dir):
        if "index.tsv" in files:
            found_any_corpus = True
            idx_path = Path(root).joinpath("index.tsv")
            for row in _iter_index(idx_path):
                if not row:
                    continue
                keep, score = _score_entry(row, args.query)
                if keep:
                    matches.append((Path(root).name, row["id"], row["resume"],
                                    row["offset_octets"], row["longueur_octets"],
                                    score))

    if not found_any_corpus:
        print(f"Aucun corpus n a ete trouve sous le repertoire des references {ref_dir}",
              file=sys.stderr)
        sys.exit(1)

    if args.read:
        bytes_read = 0
        for root, _, files in os.walk(ref_dir):
            if "symbols.jsonl" in files:
                sym_path = Path(root).joinpath("symbols.jsonl")
                try:
                    with open(sym_path, "rb") as f:
                        f.seek(0, 2)
                        f_size = f.tell()
                        idx_path = Path(root).joinpath("index.tsv")
                        for row in _iter_index(idx_path):
                            if not row:
                                continue
                            if row["id"] == args.read:
                                off = int(row["offset_octets"])
                                length = int(row["longueur_octets"])
                                f.seek(off)
                                data = json.loads(f.read(length).decode("utf-8"))
                                affiche, connues = _format_fragment(data)
                                if not connues:
                                    cles = sorted(data.keys())
                                    print(f"Fragment {args.read}: cles inconnues {cles}",
                                          file=sys.stderr)
                                    _log_consultation("lecture", args.read, 0, 0)
                                    return 3
                                if affiche is None:
                                    cles = sorted(data.keys())
                                    print(f"Fragment {args.read}: cles connues vides {cles}",
                                          file=sys.stderr)
                                    _log_consultation("lecture", args.read, 0, 0)
                                    return 3
                                print(f"Cout: {length} / {f_size} octets")
                                print(affiche)
                                bytes_read = length
                                _log_consultation("lecture", args.read, 1, bytes_read)
                                return 0
                except Exception as e:
                    print(f"Erreur lecture fragment {args.read}: {e}", file=sys.stderr)
        _log_consultation("lecture", args.read, 0, 0)
        return 1

    _log_consultation("recherche", args.query, len(matches))

    matches.sort(key=lambda m: m[5], reverse=True)

    if not matches:
        print("Verdict negatif: aucun resultat. Les termes de la requete "
              "n'ont ete trouves dans id, type ou resume.", file=sys.stderr)
        return 2

    for m in matches[:args.limit]:
        print(f"Rayon: {m[0]} | ID: {m[1]} | Resume: {m[2]}")
    return 0

if __name__ == "__main__":
    # Utilisation de chr(92) pour eviter le backslash litteral
    sep = chr(92)
    sys.exit(main())
