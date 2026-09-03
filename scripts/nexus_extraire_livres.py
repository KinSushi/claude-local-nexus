"""nexus_extraire_livres.py – Extraction de texte depuis une bibliothèque de livres."""

import argparse
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import time
import zipfile
import contextlib


def _extract_txt(src: str, dst: str) -> int:
    with open(src, "rb") as fsrc, open(dst, "wb") as fdst:
        shutil.copyfileobj(fsrc, fdst)
    return os.path.getsize(dst)


def _extract_pdf(src: str, dst: str) -> int:
    result = subprocess.run(
        ["pdftotext", "-q", src, dst],
        timeout=600,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"pdftotext failed: {result.stderr.strip()}")
    return os.path.getsize(dst)


def _extract_epub(src: str, dst: str) -> int:
    with zipfile.ZipFile(src, "r") as z:
        names = [n for n in z.namelist() if n.lower().endswith((".xhtml", ".html"))]
        names.sort()
        parts = []
        for n in names:
            with z.open(n) as f:
                data = f.read().decode("utf-8", errors="ignore")
                parts.append(data)
        raw = "\n".join(parts)
        clean = re.sub(r"<[^>]+>", "", raw)
    with open(dst, "w", encoding="utf-8") as f:
        f.write(clean)
    return os.path.getsize(dst)


def _process_file(src_path: pathlib.Path, dst_path: pathlib.Path) -> int:
    ext = src_path.suffix.lower()
    if ext == ".txt":
        return _extract_txt(str(src_path), str(dst_path))
    if ext == ".pdf":
        return _extract_pdf(str(src_path), str(dst_path))
    return _extract_epub(str(src_path), str(dst_path))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, help="Racine de la bibliothèque")
    parser.add_argument("--cible", required=True, help="Racine de sortie")
    parser.add_argument("--limite", type=int, default=None, help="Arrêter après N livres neufs")
    parser.add_argument("--minutes", type=int, default=None, help="Arrêter après M minutes")
    args = parser.parse_args()

    source = pathlib.Path(args.source).resolve()
    cible = pathlib.Path(args.cible).resolve()

    if not source.is_dir() or shutil.which("pdftotext") is None:
        return 3

    stats = {
        "livres_vus": 0,
        "neufs": 0,
        "deja_faits": 0,
        "rates": 0,
        "octets_texte": 0,
        "secondes": 0.0,
        "echecs": [],
    }

    start = time.time()
    stop_by_limit = False

    for root, _, files in os.walk(source):
        for fname in files:
            if not fname.lower().endswith((".pdf", ".epub", ".txt")):
                continue

            src_path = pathlib.Path(root) / fname
            rel_path = src_path.relative_to(source).with_suffix(".txt")
            dst_path = cible / rel_path

            stats["livres_vus"] += 1

            if dst_path.is_file() and dst_path.stat().st_size > 0:
                stats["deja_faits"] += 1
                continue

            dst_path.parent.mkdir(parents=True, exist_ok=True)

            try:
                size = _process_file(src_path, dst_path)
                stats["neufs"] += 1
                stats["octets_texte"] += size
            except Exception as exc:
                if dst_path.is_file():
                    with contextlib.suppress(Exception):
                        dst_path.unlink()
                stats["rates"] += 1
                stats["echecs"].append(
                    {"livre": str(src_path), "motif": str(exc)}
                )

            elapsed = time.time() - start
            stats["secondes"] = elapsed

            if args.limite is not None and stats["neufs"] >= args.limite:
                stop_by_limit = True
                break
            if args.minutes is not None and elapsed >= args.minutes * 60:
                stop_by_limit = True
                break
        if stop_by_limit:
            break

    json_path = cible / "_extraction.json"
    with open(json_path, "w", encoding="utf-8") as jf:
        json.dump(stats, jf, ensure_ascii=False, indent=2)

    résumé = (
        f"Livres vus : {stats['livres_vus']}, "
        f"nouveaux : {stats['neufs']}, "
        f"déjà faits : {stats['deja_faits']}, "
        f"échecs : {stats['rates']}, "
        f"octets texte : {stats['octets_texte']}, "
        f"temps : {int(stats['secondes'])} s"
    )
    print(résumé)

    if stats["neufs"] > 0 or stats["deja_faits"] > 0:
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
