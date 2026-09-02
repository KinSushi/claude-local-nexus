"""nexus_livres_semantique.py

This script indexes book fragments and enables semantic search.
It never sends data outside the local machine. Two JSON schemas are
supported for the fragment text: the key "texte", then "text", then
"implementation". The script provides two sub‑commands:

* build : walk through sub‑directories under "references/books",
  read fragments according to "index.tsv", embed them with the
  Ollama embedding API and write a JSONL file incrementally.

* search : embed a query, read the previously created JSONL file
  line by line, compute cosine similarity and display the N best
  matches.

Only the Python standard library, urllib and json are used.
"""

import os
import sys
import csv
import json
import math
import argparse
import urllib.request
import urllib.error
import heapq

API_URL_DEFAULT = "http://127.0.0.1:11434/api/embed"
MODEL_DEFAULT = "nomic-embed-text"
BATCH_SIZE = 32
OUTPUT_DIR = "nexus"
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "fragments_embeddings.jsonl")


def embed_texts(texts, model, api_url):
    """Send a batch of texts to the Ollama embed API.

    Returns a list of vectors (list of floats) or raises an exception.
    """
    payload = json.dumps({"model": model, "input": texts}).encode("utf-8")
    req = urllib.request.Request(
        api_url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req) as resp:
        data = json.load(resp)
    return data.get("embeddings", [])


def read_fragment(path, offset, length):
    """Read a fragment from a jsonl file using binary seek."""
    with open(path, "rb") as f:
        f.seek(offset)
        raw = f.read(length)
    obj = json.loads(raw.decode("utf-8"))
    for key in ("texte", "text", "implementation"):
        if key in obj:
            return obj[key]
    return ""


def build_index(args):
    if not os.path.isdir(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR, exist_ok=True)

    total_indexed = 0
    failures = 0
    batch = []
    batch_meta = []

    # Determine repository root and data directory
    _repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    _data_root = os.path.join(_repo_root, "references", "livres")
    for root, dirs, files in os.walk(_data_root):
        if "index.tsv" not in files or "symbols.jsonl" not in files:
            continue
        index_path = os.path.join(root, "index.tsv")
        symbols_path = os.path.join(root, "symbols.jsonl")
        rayon = os.path.relpath(root, _data_root)

        with open(index_path, newline="", encoding="utf-8") as idx_file:
            reader = csv.reader(idx_file, delimiter="\t")
            for row in reader:
                if len(row) < 5:
                    continue
                ident, offset_str, length_str, typ, resume = row[:5]
                try:
                    offset = int(offset_str)
                    length = int(length_str)
                except ValueError:
                    continue

                fragment_text = read_fragment(symbols_path, offset, length)
                embed_input = resume + "\n" + fragment_text[:2000]

                meta = {
                    "id": ident,
                    "rayon": rayon,
                    "resume": resume,
                    "path": symbols_path,
                    "offset": offset,
                    "length": length,
                    "model": args.model,
                }

                batch.append(embed_input)
                batch_meta.append(meta)

                if len(batch) == BATCH_SIZE:
                    try:
                        vectors = embed_texts(batch, args.model, args.api_url)
                        write_batch(vectors, batch_meta)
                        total_indexed += len(vectors)
                    except Exception as e:
                        failures += len(batch)
                        sys.stderr.write(f"Batch error: {e}\n")
                    batch.clear()
                    batch_meta.clear()

                if args.max_fragments and total_indexed + len(batch) >= args.max_fragments:
                    break
            if args.max_fragments and total_indexed >= args.max_fragments:
                break

    # Process remaining batch
    if batch:
        try:
            vectors = embed_texts(batch, args.model, args.api_url)
            write_batch(vectors, batch_meta)
            total_indexed += len(vectors)
        except Exception as e:
            failures += len(batch)
            sys.stderr.write(f"Final batch error: {e}\n")

    sys.stderr.write(f"Indexed {total_indexed} fragments, failures: {failures}\n")
    sys.exit(1 if total_indexed == 0 else 0)


def write_batch(vectors, metas):
    """Append a batch of results to the output JSONL file."""
    with open(OUTPUT_FILE, "a", encoding="utf-8") as out_f:
        for vec, meta in zip(vectors, metas):
            record = meta.copy()
            record["vector"] = vec
            out_f.write(json.dumps(record, ensure_ascii=False) + "\n")


def cosine_similarity(v1, v2):
    dot = sum(a * b for a, b in zip(v1, v2))
    norm1 = math.sqrt(sum(a * a for a in v1))
    norm2 = math.sqrt(sum(b * b for b in v2))
    if norm1 == 0 or norm2 == 0:
        return 0.0
    return dot / (norm1 * norm2)


def search_index(args):
    if not os.path.isfile(OUTPUT_FILE):
        sys.stderr.write("Embedding file does not exist. Run build first.\n")
        sys.exit(1)

    # Verify model consistency
    with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
        first_line = f.readline()
        if not first_line:
            sys.stderr.write("Embedding file is empty.\n")
            sys.exit(1)
        first_record = json.loads(first_line)
        stored_model = first_record.get("model")
        if stored_model != args.model:
            sys.stderr.write(
                f"Model mismatch: index built with '{stored_model}', requested '{args.model}'.\n"
            )
            sys.exit(1)

    # Embed query
    try:
        query_vec = embed_texts([args.query], args.model, args.api_url)[0]
    except Exception as e:
        sys.stderr.write(f"Failed to embed query: {e}\n")
        sys.exit(1)

    top_n = args.top
    heap = []  # min-heap of (score, record)

    processed = 0
    with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
        for line in f:
            if args.max_fragments and processed >= args.max_fragments:
                break
            record = json.loads(line)
            vec = record.get("vector")
            if not isinstance(vec, list):
                continue
            score = cosine_similarity(query_vec, vec)
            if len(heap) < top_n:
                heapq.heappush(heap, (score, record))
            else:
                heapq.heappushpop(heap, (score, record))
            processed += 1

    results = sorted(heap, key=lambda x: x[0], reverse=True)
    for score, rec in results:
        print(f"Score: {score:.4f}")
        print(f"Resume: {rec.get('resume')}")
        print(f"Path: {rec.get('path')} (offset {rec.get('offset')}, length {rec.get('length')})")
        print("-" * 40)


def main():
    parser = argparse.ArgumentParser(prog="nexus_livres_semantique")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Build subcommand
    build_parser = subparsers.add_parser("build", help="Build the embedding index")
    build_parser.add_argument(
        "--model", default=MODEL_DEFAULT, help="Embedding model name"
    )
    build_parser.add_argument(
        "--api-url", default=API_URL_DEFAULT, help="Embedding API endpoint"
    )
    build_parser.add_argument(
        "--max-fragments", type=int, help="Limit number of fragments to process"
    )
    build_parser.set_defaults(func=build_index)

    # Search subcommand
    search_parser = subparsers.add_parser("search", help="Search the embedding index")
    search_parser.add_argument("query", help="Query string")
    search_parser.add_argument(
        "--model", default=MODEL_DEFAULT, help="Embedding model name"
    )
    search_parser.add_argument(
        "--api-url", default=API_URL_DEFAULT, help="Embedding API endpoint"
    )
    search_parser.add_argument(
        "-n", "--top", type=int, default=5, help="Number of top results to display"
    )
    search_parser.add_argument(
        "--max-fragments", type=int, help="Limit number of fragments to read"
    )
    search_parser.set_defaults(func=search_index)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()