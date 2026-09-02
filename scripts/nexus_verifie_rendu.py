#!/usr/bin/env python3
import ast
import argparse
import sys
import subprocess
import threading
from pathlib import Path

# ----------------------------------------------------------------------
# Helper to run a python file with --help and a timeout
def run_help(path, timeout):
    try:
        proc = subprocess.Popen(
            [sys.executable, path, '--help'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        timer = threading.Timer(timeout, proc.kill)
        timer.start()
        stdout, stderr = proc.communicate()
        timer.cancel()
        if proc.returncode != 0:
            return False, f"non zero exit ({proc.returncode})"
        return True, None
    except Exception as e:
        return False, str(e)

# ----------------------------------------------------------------------
# Check 2 : constant slice start that does not match any reference length
def check_slice(node, refs, issues, path):
    if not isinstance(node, ast.Subscript):
        return
    if not isinstance(node.slice, ast.Slice):
        return
    lower = node.slice.lower
    if isinstance(lower, ast.Constant) and isinstance(lower.value, int):
        start = lower.value
        # find closest reference length
        distances = [(abs(start - len(r)), r) for r in refs]
        if not distances:
            return
        min_dist, closest = min(distances, key=lambda x: x[0])
        if min_dist <= 1 and start not in [len(r) for r in refs]:
            lineno = node.lineno
            issues.append(
                f"{path}:{lineno}: slice start {start} close to length {len(closest)} of reference '{closest}'"
            )

# ----------------------------------------------------------------------
# Check 3 : attribute vs variable name mismatch
IGNORED_PREFIXES = {'max', 'min', 'total', 'nb', 'n'}

def split_words(name):
    parts = name.lower().split('_')
    return [p for p in parts if p and p not in IGNORED_PREFIXES]

def check_compare(node, issues, path):
    if not isinstance(node, ast.Compare):
        return
    left = node.left
    right = node.comparators[0] if node.comparators else None
    if isinstance(left, ast.Attribute) and isinstance(right, ast.Name):
        attr_name = left.attr
        var_name = right.id
    elif isinstance(right, ast.Attribute) and isinstance(left, ast.Name):
        attr_name = right.attr
        var_name = left.id
    else:
        return
    attr_words = set(split_words(attr_name))
    var_words = set(split_words(var_name))
    if attr_words and var_words and not attr_words.intersection(var_words):
        lineno = node.lineno
        issues.append(
            f"{path}:{lineno}: attribute '{attr_name}' and variable '{var_name}' share no significant word"
        )

# ----------------------------------------------------------------------
# Visitor that runs all checks on a single file
class FileChecker(ast.NodeVisitor):
    def __init__(self, path, refs):
        self.path = path
        self.refs = refs
        self.issues = []

    def generic_visit(self, node):
        check_slice(node, self.refs, self.issues, self.path)
        check_compare(node, self.issues, self.path)
        super().generic_visit(node)

# ----------------------------------------------------------------------
def process_file(path, args):
    reported = False
    # Check 1 : execution with --help
    if not args.disable_check1:
        ok, msg = run_help(path, 10)
        if not ok:
            print(f"{path}: execution failed or hung ({msg})", file=sys.stderr)
            reported = True

    # Parse file
    try:
        with open(path, 'r', encoding='utf-8') as f:
            source = f.read()
        tree = ast.parse(source, filename=path)
    except (UnicodeDecodeError, SyntaxError, OSError) as e:
        print(f"{path}: read/parse error - {e}", file=sys.stderr)
        return True

    checker = FileChecker(path, args.refs)
    checker.visit(tree)

    if checker.issues:
        for issue in checker.issues:
            print(issue)
        reported = True
        # indicate possible false positives for checks 2 and 3
        print(f"{path}: note - some reports may be false positives", file=sys.stderr)

    return reported

def iter_paths(targets):
    for target in targets:
        p = Path(target)
        if p.is_dir():
            for py in p.rglob('*.py'):
                yield str(py)
        elif p.suffix == '.py':
            yield str(p)

def main():
    parser = argparse.ArgumentParser(description='Verify rendered python files')
    parser.add_argument('paths', nargs='+', help='files or directories')
    parser.add_argument('--refs', default='', help='comma separated reference strings for slice check')
    parser.add_argument('--disable-check1', action='store_true', help='skip execution check')
    args = parser.parse_args()

    # configure stdout to utf-8
    sys.stdout.reconfigure(encoding='utf-8')

    # prepare reference list
    args.refs = [s for s in args.refs.split(',') if s]

    any_issue = False
    for path in iter_paths(args.paths):
        try:
            if process_file(path, args):
                any_issue = True
        except Exception as e:
            print(f"TOOL ERROR on {path}: {type(e).__name__}: {e}", file=sys.stderr)
            any_issue = True

    sys.exit(1 if any_issue else 0)

if __name__ == '__main__':
    main()
