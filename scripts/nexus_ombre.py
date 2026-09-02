#!/usr/bin/env python3
"""Shadow tool for nexus_appliquer.

Implements the prescription from the book: this script logs what would happen
if the official patch applicator were run, but never writes to the target
file. It reads a JSONL file describing replacement blocks, analyses the
effects on the target file and reports a verdict.

The script does not modify any file. Return code 0 means APPLICABLE,
non‑zero means REFUSE.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import List, Tuple


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Shadow wrapper for nexus_appliquer."
    )
    parser.add_argument("jsonl", type=Path, help="Path to JSONL file with blocks")
    parser.add_argument("task", help="Task name (unused, kept for compatibility)")
    parser.add_argument("target", type=Path, help="Path to target file")
    parser.add_argument(
        "--root",
        type=Path,
        default=None,
        help="Root directory (default: directory of this script)",
    )
    return parser.parse_args()


def load_blocks(jsonl_path: Path) -> List[dict]:
    blocks = []
    with jsonl_path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                blocks.append(json.loads(line))
            except json.JSONDecodeError as e:
                print(f"Error parsing JSONL line: {e}", file=sys.stderr)
                sys.exit(2)
    return blocks


def count_anchor(lines: List[str], anchor: str) -> int:
    return sum(1 for l in lines if l.rstrip("\n") == anchor)


def apply_block(
    lines: List[str], anchor: str, replacement: str
) -> Tuple[List[str], List[int]]:
    """Return new lines and list of modified line numbers (1‑based)."""
    new_lines = lines[:]
    modified = []
    for idx, line in enumerate(lines):
        if line.rstrip("\n") == anchor:
            new_lines[idx] = replacement + ("\n" if line.endswith("\n") else "")
            modified.append(idx + 1)
            break
    return new_lines, modified


def syntax_valid(py_content: str) -> bool:
    try:
        compile(py_content, "<shadow>", "exec")
        return True
    except SyntaxError:
        return False


def main() -> None:
    args = parse_args()
    root = args.root or Path(__file__).resolve().parent
    jsonl_path = args.jsonl
    target_path = args.target

    if not jsonl_path.is_file():
        print(f"JSONL file not found: {jsonl_path}", file=sys.stderr)
        sys.exit(2)
    if not target_path.is_file():
        print(f"Target file not found: {target_path}", file=sys.stderr)
        sys.exit(2)

    blocks = load_blocks(jsonl_path)

    try:
        target_text = target_path.read_text(encoding="utf-8")
    except Exception as e:
        print(f"Failed to read target file: {e}", file=sys.stderr)
        sys.exit(2)

    lines = target_text.splitlines(keepends=True)
    all_ok = True
    reasons = []

    for i, block in enumerate(blocks, start=1):
        anchor = block.get("anchor")
        replacement = block.get("replacement")
        if anchor is None or replacement is None:
            print(f"Block {i} missing 'anchor' or 'replacement'", file=sys.stderr)
            sys.exit(2)

        occ = count_anchor(lines, anchor)
        print(f"Block {i}: anchor occurrences = {occ}")

        if occ != 1:
            all_ok = False
            reasons.append(f"Block {i}: anchor not unique ({occ} occurrences)")
            continue

        new_lines, modified = apply_block(lines, anchor, replacement)
        added = len(new_lines) - len(lines)
        removed = -added if added < 0 else 0
        added = added if added > 0 else 0

        print(
            f"Block {i}: lines added = {added}, lines removed = {removed}, modified lines = {modified}"
        )

        lines = new_lines

    # Final syntax check if target is a .py file
    if target_path.suffix == ".py":
        final_content = "".join(lines)
        if syntax_valid(final_content):
            print("Final syntax check: valid")
        else:
            all_ok = False
            reasons.append("Final syntax invalid after applying blocks")
            print("Final syntax check: invalid")

    verdict = "APPLICABLE" if all_ok else "REFUSE"
    print(f"VERDICT: {verdict}")
    if not all_ok:
        for r in reasons:
            print(f"Reason: {r}", file=sys.stderr)
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()