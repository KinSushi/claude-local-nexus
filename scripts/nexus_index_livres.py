#!/usr/bin/env python3
import argparse
import datetime
import json
import os
import struct
import sys
import time
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

def find_index_files(root_path):
    """Find all index.tsv files under root_path."""
    index_files = []
    for dirpath, _, filenames in os.walk(root_path):
        for name in filenames:
            if name == 'index.tsv':
                index_files.append(Path(dirpath) / name)
    return index_files

def read_index_file(path):
    """Read index.tsv and return list of entries.
    Each entry is a tuple (rayon, ident, resume, offset, length)."""
    entries = []
    try:
        with path.open('r', encoding='utf-8') as f:
            lines = f.read().splitlines()
        if not lines:
            return entries
        for line in lines[1:]:
            parts = line.split('\t')
            if len(parts) < 5:
                continue
            ident = parts[0]
            resume = parts[4]
            offset = None
            length = None
            if len(parts) > 1 and parts[1].isdigit():
                offset = int(parts[1])
            if len(parts) > 2 and parts[2].isdigit():
                length = int(parts[2])
            rayon = str(path.parent.relative_to(REPO_ROOT))
            entries.append((rayon, ident, resume, offset, length, path.parent))
    except Exception as e:
        print(f"Error reading {path}: {e}", file=sys.stderr)
    return entries

def batch_iter(iterable, size):
    batch = []
    for item in iterable:
        batch.append(item)
        if len(batch) == size:
            yield batch
            batch = []
    if batch:
        yield batch

def embed_texts(texts, model):
    """Call local inference engine and return list of embeddings."""
    url = 'http://127.0.0.1:11434/api/embed'
    payload = json.dumps({'model': model, 'input': texts}).encode('utf-8')
    req = urllib.request.Request(url, data=payload, method='POST')
    req.add_header('Content-Type', 'application/json')
    try:
        with urllib.request.urlopen(req) as resp:
            data = json.load(resp)
        return data.get('embeddings', [])
    except Exception as e:
        print(f"Embedding request failed: {e}", file=sys.stderr)
        return None

def write_binary(file_path, vectors):
    """Write list of vectors to binary file as 32-bit floats."""
    with open(file_path, 'wb') as bf:
        for vec in vectors:
            bf.write(struct.pack('f' * len(vec), *vec))

def read_fragment_text(fragment_dir, offset, length):
    """Read a fragment from fragment file, decode JSON and return the 'texte' field."""
    fragment_path = fragment_dir / 'symbols.jsonl'
    try:
        with fragment_path.open('rb') as f:
            f.seek(offset)
            raw = f.read(length)
        return json.loads(raw.decode('utf-8')).get('texte')
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as e:
        print(f"Error reading {fragment_path}: {type(e).__name__}: {e}", file=sys.stderr)
        raise
    except Exception:
        return None

def main():
    parser = argparse.ArgumentParser(description='Build semantic index of book summaries')
    parser.add_argument('--root', default=str(REPO_ROOT), help='Root directory of repository')
    parser.add_argument('--corpus', default='references/livres', help='Subpath of corpus')
    parser.add_argument('--model', default='all-minilm:latest', help='Embedding model')
    parser.add_argument('--out', default='index_output', help='Output base path (without extension)')
    parser.add_argument('--delay', type=float, default=0.0, help='Delay in seconds between batches')
    parser.add_argument('--limit', type=int, default=None, help='Maximum number of entries to process')
    parser.add_argument('--index-text', action='store_true', help='Index full text instead of resume')
    parser.add_argument('--maxlen', type=int, default=2000, help='Maximum characters per fragment')
    args = parser.parse_args()

    corpus_path = Path(args.root) / args.corpus
    if not corpus_path.is_dir():
        print(f"Corpus directory not found: {corpus_path}", file=sys.stderr)
        sys.exit(4)

    index_files = find_index_files(corpus_path)
    if not index_files:
        print(f"No index.tsv files found under {corpus_path}", file=sys.stderr)
        sys.exit(4)

    all_entries = []
    for idx_file in index_files:
        entries = read_index_file(idx_file)
        if entries:
            all_entries.extend(entries)

    if not all_entries:
        print(f"No readable entries found in corpus {corpus_path}", file=sys.stderr)
        sys.exit(4)

    if args.limit is not None:
        all_entries = all_entries[:args.limit]

    total = len(all_entries)
    processed = 0
    missing = 0
    unreadable = 0
    vectors = []
    metadata = []

    start_time = time.time()
    batch_size = 32

    for batch in batch_iter(all_entries, batch_size):
        texts = []
        meta_batch = []
        for entry in batch:
            rayon, ident, resume, offset, length, frag_dir = entry
            if args.index_text:
                if offset is None or length is None:
                    unreadable += 1
                    continue
                txt = read_fragment_text(frag_dir, offset, length)
                if txt is None:
                    unreadable += 1
                    continue
                txt = txt[:args.maxlen]
                texts.append(txt)
                meta_batch.append((rayon, ident, None, txt))
            else:
                texts.append(resume)
                meta_batch.append((rayon, ident, resume, None))
        if not texts:
            processed += len(batch)
            continue
        emb = embed_texts(texts, args.model)
        if emb is None or len(emb) != len(texts):
            missing += len(texts)
            print(f"Batch starting at {processed} failed, skipping", file=sys.stderr)
        else:
            vectors.extend(emb)
            for (rayon, ident, resume, txt) in meta_batch:
                entry_meta = {'rayon': rayon, 'id': ident}
                if args.index_text:
                    entry_meta['texte'] = txt
                else:
                    entry_meta['resume'] = resume
                metadata.append(entry_meta)
        processed += len(batch)
        elapsed = time.time() - start_time
        remaining = total - processed
        eta = (elapsed / processed * remaining) if processed else 0
        print(f"Processed {processed}/{total} in {elapsed:.1f}s, ETA {eta:.1f}s", flush=True)
        if args.delay > 0:
            time.sleep(args.delay)

    binary_path = f"{args.out}.bin"
    json_path = f"{args.out}.json"
    write_binary(binary_path, vectors)

    dim = len(vectors[0]) if vectors else 0
    output_json = {
        'model': args.model,
        'dimension': dim,
        'entries': len(vectors),
        'corpus_path': str(corpus_path),
        'date': datetime.datetime.utcnow().isoformat() + 'Z',
        'index_type': 'texte' if args.index_text else 'resume',
        'metadata': metadata
    }
    with open(json_path, 'w', encoding='utf-8') as jf:
        json.dump(output_json, jf, ensure_ascii=False, indent=2)

    if unreadable:
        print(f"Unreadable fragments: {unreadable}", file=sys.stderr)
    if missing:
        print(f"Index incomplete: {missing} embeddings missing", file=sys.stderr)
        sys.exit(3)
    else:
        sys.exit(0)

if __name__ == '__main__':
    main()
