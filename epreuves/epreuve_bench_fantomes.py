#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Epreuve de validation de outillage.nexus_bench.archiver_fantomes.
"""

import json
import sys
import pathlib
import tempfile

CURRENT_DIR = pathlib.Path(__file__).resolve().parent
OUTILLAGE_DIR = CURRENT_DIR.parent / "outillage"
if str(OUTILLAGE_DIR) not in sys.path:
    sys.path.insert(0, str(OUTILLAGE_DIR))

from nexus_bench import archiver_fantomes  # noqa: E402


def _load_archive(chemin: pathlib.Path) -> dict:
    if chemin.is_file():
        with chemin.open("r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def _test_forward(tmp_dir: pathlib.Path) -> bool:
    releves = {
        "alpha": {"val": 1},
        "beta": {"val": 2},
        "gamma": {"val": 3},
    }
    alias_exposes = {"alpha", "beta"}
    chemin_archive = tmp_dir / "archive_forward.json"
    moved = archiver_fantomes(releves, alias_exposes, chemin_archive)
    ok = True
    ok &= (moved == 1)
    ok &= (set(releves.keys()) == {"alpha", "beta"})
    archive_content = _load_archive(chemin_archive)
    ok &= ("gamma" in archive_content)
    ok &= ("gamma" in archive_content and "archive_le" in archive_content["gamma"])
    detail = f"moved={moved}, remaining={len(releves)}"
    print(("[OK  ] " if ok else "[RATE] ") + "forward : " + detail)
    return ok


def _test_fusion(tmp_dir: pathlib.Path) -> bool:
    chemin_archive = tmp_dir / "archive_fusion.json"
    preexisting = {"ancien": {"data": 42}}
    with chemin_archive.open("w", encoding="utf-8") as f:
        json.dump(preexisting, f)
    releves = {"nouveau": {"info": "test"}}
    alias_exposes = set()
    moved = archiver_fantomes(releves, alias_exposes, chemin_archive)
    ok = True
    ok &= (moved == 1)
    ok &= (len(releves) == 0)
    archive_content = _load_archive(chemin_archive)
    ok &= ("ancien" in archive_content)
    ok &= ("nouveau" in archive_content)
    ok &= ("nouveau" in archive_content and "archive_le" in archive_content["nouveau"])
    detail = f"moved={moved}, archive_keys={list(archive_content.keys())}"
    print(("[OK  ] " if ok else "[RATE] ") + "fusion : " + detail)
    return ok


def _test_neutre(tmp_dir: pathlib.Path) -> bool:
    releves = {"x": {"v": 0}, "y": {"v": 1}}
    alias_exposes = {"x", "y"}
    chemin_archive = tmp_dir / "archive_neutre.json"
    moved = archiver_fantomes(releves, alias_exposes, chemin_archive)
    ok = True
    ok &= (moved == 0)
    ok &= (set(releves.keys()) == {"x", "y"})
    ok &= (not chemin_archive.is_file())
    detail = f"moved={moved}, archive_exists={chemin_archive.is_file()}"
    print(("[OK  ] " if ok else "[RATE] ") + "neutre : " + detail)
    return ok


def main() -> None:
    results = []
    with tempfile.TemporaryDirectory() as td:
        tmp_path = pathlib.Path(td)
        results.append(_test_forward(tmp_path))
        results.append(_test_fusion(tmp_path))
        results.append(_test_neutre(tmp_path))
    sys.exit(0 if all(results) else 1)


if __name__ == "__main__":
    main()
