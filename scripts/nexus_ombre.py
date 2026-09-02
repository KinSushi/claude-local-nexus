"""nexus_ombre.py
Implements the shadow tool described in the book. The script logs the actions that would be
performed on a target file but never writes to it. It extracts blocks delimited by
<<<AVANT>>>, <<<APRES>>> and <<<FIN>>> from a JSONL rendering file and simulates their
replacement in the target file. The script returns exit code 0 only when the simulated
operation is applicable, otherwise 1.
"""

import argparse
import json
import re
import sys
from pathlib import Path

def build_marker(word: str) -> str:
    less = '<' * 3
    greater = '>' * 3
    return f"{less}{word}{greater}"

def parse_arguments():
    parser = argparse.ArgumentParser(description="Shadow tool that logs replacements without writing.")
    parser.add_argument("jsonl_file", type=Path, help="Path to the JSONL file containing renderings")
    parser.add_argument("task_name", help="Name of the task to locate in the JSONL")
    parser.add_argument("target_file", type=Path, help="Path to the target file to analyse")
    parser.add_argument("--root", help="Optional root directory (unused)", default=None)
    return parser.parse_args()

def load_task_text(jsonl_path: Path, task_name: str) -> str:
    try:
        with jsonl_path.open(encoding="utf-8") as f:
            for line in f:
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if obj.get("nom") == task_name:
                    return obj.get("texte", "")
    except OSError:
        pass
    return ""

def extract_blocks(text: str):
    markers = ["AVANT", "APRES", "FIN"]
    marker_regex = {}
    for m in markers:
        marker_regex[m] = re.compile(rf"(?m)^\s*{re.escape(build_marker(m))}\s*$")
    lines = text.splitlines()
    blocks = {}
    current = None
    buffer = []
    for line in lines:
        stripped = line.strip()
        matched = None
        for m in markers:
            if stripped == build_marker(m):
                matched = m
                break
        if matched:
            if current:
                blocks[current] = buffer
            current = matched
            buffer = []
        else:
            if current:
                buffer.append(line)
    if current:
        blocks[current] = buffer
    # Ensure all three markers are present
    if any(m not in blocks for m in markers):
        return {}
    return blocks

def count_anchor_occurrences(target_lines, anchor):
    return sum(1 for line in target_lines if line.strip() == anchor)

def simulate_replacement(target_lines, blocks):
    new_lines = []
    markers = ["AVANT", "APRES", "FIN"]
    i = 0
    while i < len(target_lines):
        line = target_lines[i]
        stripped = line.strip()
        replaced = False
        for m in markers:
            anchor = build_marker(m)
            if stripped == anchor:
                new_lines.extend(blocks[m])
                replaced = True
                break
        if not replaced:
            new_lines.append(line)
        i += 1
    return new_lines

def main():
    args = parse_arguments()
    task_text = load_task_text(args.jsonl_file, args.task_name)
    if not task_text:
        print("Task not found or empty rendering.")
        sys.exit(1)

    blocks = extract_blocks(task_text)
    if not blocks:
        print("No blocks extracted.")
        sys.exit(1)

    try:
        target_content = args.target_file.read_text(encoding="utf-8")
    except OSError:
        print("Cannot read target file.")
        sys.exit(1)

    target_lines = target_content.splitlines()
    markers = ["AVANT", "APRES", "FIN"]
    occurrences = {}
    for m in markers:
        anchor = build_marker(m)
        occ = count_anchor_occurrences(target_lines, anchor)
        occurrences[m] = occ

    all_single = all(occ == 1 for occ in occurrences.values())
    if not all_single:
        for m in markers:
            if occurrences[m] != 1:
                print(f"REFUSE: anchor {build_marker(m)} occurs {occurrences[m]} times.")
        sys.exit(1)

    new_lines = simulate_replacement(target_lines, blocks)
    added_lines = sum(len(blocks[m]) for m in markers)
    removed_lines = sum(occurrences[m] for m in markers)

    for m in markers:
        print(f"{build_marker(m)}: occurrences={occurrences[m]}, lines_added={len(blocks[m])}, lines_removed={occurrences[m]}")

    result_text = "\n".join(new_lines)
    if args.target_file.suffix == ".py":
        try:
            compile(result_text, "<string>", "exec")
        except SyntaxError as e:
            print(f"REFUSE: resulting python code is syntactically invalid: {e}")
            sys.exit(1)

    print("APPLICABLE")
    sys.exit(0)

if __name__ == "__main__":
    main()