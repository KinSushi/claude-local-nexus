#!/usr/bin/env python3
import ast
import os
import sys
from pathlib import Path

class NexusEpreuveVide(ast.NodeVisitor):
    def __init__(self, path):
        self.path = path
        self.has_subprocess = False
        self.has_target_import = False
        self.has_assert = False
        self.has_cond_compare = False
        # derive target module name from file name
        name = os.path.basename(path)
        base = name[:-3] if name.lower().endswith('.py') else name
        if base.startswith('epreuve_'):
            self.target_module = base[len('epreuve_'):]
        else:
            self.target_module = base

    def visit_Call(self, node):
        # look for subprocess.xxx(...)
        if isinstance(node.func, ast.Attribute):
            if isinstance(node.func.value, ast.Name):
                if node.func.value.id == 'subprocess':
                    self.has_subprocess = True
        self.generic_visit(node)

    def visit_Import(self, node):
        for alias in node.names:
            if alias.name == self.target_module:
                self.has_target_import = True
        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        if node.module == self.target_module:
            self.has_target_import = True
        self.generic_visit(node)

    def visit_Assert(self, node):
        self.has_assert = True
        self.generic_visit(node)

    def visit_If(self, node):
        if isinstance(node.test, ast.Compare):
            self.has_cond_compare = True
        self.generic_visit(node)

def analyze_file(path):
    signals = []
    try:
        with open(path, 'r', encoding='utf-8') as f:
            source = f.read()
        tree = ast.parse(source, filename=path)
    except (UnicodeDecodeError, SyntaxError, OSError) as e:
        msg = f"{path}: unreadable or syntax error - {e}"
        print(msg, file=sys.stderr)
        signals.append(msg)
        return signals

    visitor = NexusEpreuveVide(path)
    visitor.visit(tree)

    if not (visitor.has_subprocess or visitor.has_target_import):
        signals.append(f"{path}: does not launch anything nor test anything")
    if not (visitor.has_assert or visitor.has_cond_compare):
        signals.append(f"{path}: cannot fail (no assert nor conditional compare)")
    return signals

def scan_path(entry):
    any_signal = False
    if os.path.isdir(entry):
        for root, _, files in os.walk(entry):
            for file in files:
                if file.startswith('epreuve') and file.endswith('.py'):
                    full = os.path.join(root, file)
                    sigs = analyze_file(full)
                    for s in sigs:
                        print(s)
                    if sigs:
                        any_signal = True
    else:
        if os.path.basename(entry).startswith('epreuve') and entry.endswith('.py'):
            sigs = analyze_file(entry)
            for s in sigs:
                print(s)
            if sigs:
                any_signal = True
    return any_signal

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(f"Usage: {Path(__file__).name} <path>...", file=sys.stderr)
        sys.exit(2)

    overall_signal = False
    for arg in sys.argv[1:]:
        if scan_path(arg):
            overall_signal = True

    # This is a SIGNAL, not a blocking guard
    if overall_signal:
        print("Ceci est un SIGNAL, pas une garde bloquee.")
        sys.exit(1)
    else:
        sys.exit(0)
