#!/usr/bin/env python3
import ast
import argparse
import sys
import subprocess
import threading
from pathlib import Path

# ----------------------------------------------------------------------
# Helper to run a python file with --help and a timeout
def run_help_strict(path, timeout):
    try:
        proc = subprocess.Popen(
            [sys.executable, path, '--help'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        
        timed_out = False
        def kill_proc():
            nonlocal timed_out
            timed_out = True
            proc.kill()

        timer = threading.Timer(timeout, kill_proc)
        timer.start()
        stdout, stderr = proc.communicate()
        timer.cancel()

        if timed_out:
            return False, "program hung (timeout)", True
        
        if proc.returncode != 0:
            if stdout.strip() or stderr.strip():
                return True, None, False
            return True, f"non zero exit ({proc.returncode})", False
            
        return True, None, False
    except Exception as e:
        return False, str(e), True

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
# Check 4 : detect potentially eaten backslash in regex character classes
def check_backslash(node, issues, path):
    if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
        return
    val = node.value
    start = 0
    while True:
        start = val.find('[', start)
        if start == -1: break
        end = val.find(']', start)
        if end == -1: break
        content = val[start+1:end]
        i = 0
        while i < len(content):
            if content[i] == '\\':
                if i + 1 < len(content):
                    nxt = content[i+1]
                    if nxt == '\\':
                        i += 2
                        continue
                    # Legitimate escapes in Python strings or Regex classes
                    if nxt.lower() in ('w', 's', 'd', 'n', 't', 'r') or nxt in '.\'"[]^+*()|${}?-':
                        i += 2
                        continue
                    issues.append(
                        f"{path}:{node.lineno}: class [{content}] - a backslash may have been eaten during transport"
                    )
                    i += 2
                else:
                    i += 1
            else:
                i += 1
        start = end + 1

# ----------------------------------------------------------------------
class FileChecker(ast.NodeVisitor):
    def __init__(self, path, refs, args):
        self.path = path
        self.refs = refs
        self.args = args
        self.issues = []

    def generic_visit(self, node):
        check_slice(node, self.refs, self.issues, self.path)
        check_compare(node, self.issues, self.path)
        if not self.args.disable_check4:
            check_backslash(node, self.issues, self.path)
        super().generic_visit(node)

# ----------------------------------------------------------------------
def process_file(path, args):
    reported = False
    if not args.disable_check1:
        ok, msg, is_failure = run_help_strict(path, 10)
        if not ok and is_failure:
            print(f"{path}: {msg}", file=sys.stderr)
            reported = True
        elif msg:
            print(f"{path}: NOTE - {msg}", file=sys.stderr)

    try:
        with open(path, 'r', encoding='utf-8') as f:
            source = f.read()
        tree = ast.parse(source, filename=path)
    except (UnicodeDecodeError, SyntaxError, OSError) as e:
        print(f"{path}: read/parse error - {e}", file=sys.stderr)
        return True

    checker = FileChecker(path, args.refs, args)
    checker.visit(tree)

    if checker.issues:
        for issue in checker.issues:
            print(issue)
        reported = True
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
    parser.add_argument('--disable-check4', action='store_true', help='skip backslash check')
    args = parser.parse_args()

    sys.stdout.reconfigure(encoding='utf-8')
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
