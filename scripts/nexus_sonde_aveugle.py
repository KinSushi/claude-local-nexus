#!/usr/bin/env python3
import ast
import os
import sys
from pathlib import Path

class NexusSondeAveugle(ast.NodeVisitor):
    def __init__(self, path):
        self.path = path
        self.found = False
        self.keywords = {
            'injoignable', 'indisponible', 'absent', 'echec', 'failed',
            'unavailable', 'unreachable', 'missing', 'error', 'offline'
        }

    def visit_Try(self, node):
        for handler in node.handlers:
            if self._is_broad_exception(handler):
                for stmt in handler.body:
                    if isinstance(stmt, ast.Assign):
                        self._check_assignment(handler, stmt)
        self.generic_visit(node)

    def _is_broad_exception(self, handler):
        if handler.type is None:
            return True
        if isinstance(handler.type, ast.Name):
            return handler.type.id in ('Exception', 'BaseException')
        return False

    def _check_assignment(self, handler, stmt):
        for target in stmt.targets:
            if not isinstance(target, ast.Name):
                continue
            
            var_name = target.id
            val_node = stmt.value
            val_str = ast.unparse(val_node) if hasattr(ast, 'unparse') else "<?>"
            
            # Critère 1: Nom évoquant l'indisponibilité
            if any(k in var_name.lower() for k in self.keywords):
                self._report(handler, var_name, val_str)
                continue

            # Critère 2: Valeur chaîne littérale évoquant l'indisponibilité
            if isinstance(val_node, ast.Constant) and isinstance(val_node.value, str):
                if any(k in val_node.value.lower() for k in self.keywords):
                    self._report(handler, var_name, val_str)
                    continue

            # Critère 3: Booléen True affecté à cible avec négation/échec
            if isinstance(val_node, ast.Constant) and val_node.value is True:
                if any(k in var_name.lower() for k in self.keywords) or 'not' in var_name.lower():
                    self._report(handler, var_name, val_str)
                    continue
            
            # Cas général: Simple affectation dans bloc except large
            # (L'énoncé demande "une affectation OU BIEN...", donc l'affectation seule suffit)
            self._report(handler, var_name, val_str)

    def _report(self, handler, var_name, value_str):
        line = handler.lineno
        print(f"{self.path}:{line}: Variable '{var_name}' = {value_str} "
              f"dans un bloc except large - distinction perdue entre "
              f"'ressource injoignable' et 'ressource vide'")
        self.found = True

def scan_file(path):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            tree = ast.parse(f.read(), filename=path)
        visitor = NexusSondeAveugle(path)
        visitor.visit(tree)
        return visitor.found
    except (UnicodeDecodeError, SyntaxError, OSError) as e:
        print(f"{path}: Erreur de lecture/syntaxe - {e}", file=sys.stderr)
        return False

def scan_path(path):
    found = False
    if os.path.isdir(path):
        for root, _, files in os.walk(path):
            for file in files:
                if file.endswith('.py'):
                    if scan_file(os.path.join(root, file)):
                        found = True
    elif path.endswith('.py'):
        if scan_file(path):
            found = True
    return found

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(f"Usage: {Path(__file__).name} <chemin>...", file=sys.stderr)
        sys.exit(2)

    global_found = False
    for path in sys.argv[1:]:
        if scan_path(path):
            global_found = True
    sys.exit(1 if global_found else 0)
