#!/usr/bin/env python3
"""
Contrôle de défaut d'import local non‑déclaré.

Ce script parcourt récursivement des fichiers *.py et signale les cas où
un nom est importé uniquement à l'intérieur d'une fonction puis utilisé
ailleurs (hors de la portée de cet import).  Un tel import local n’est pas
en soi un problème ; il devient une erreur d’exécution seulement lorsqu’on
tente d’utiliser le nom en dehors de la fonction qui l’a importé.  Le
contrôle évite les faux‑positifs en respectant les règles suivantes :

a. le nom est défini au niveau du module (import, assignation, def, class) ;
b. le nom est un builtin ;
c. l’usage se trouve dans le sous‑arbre de la fonction qui l’a importé
   (fonctions imbriquées comprises) ;
d. l’usage se trouve dans une autre fonction qui importe elle‑même le même
   nom ;
e. dans la fonction qui utilise le nom, celui‑ci est un paramètre ou une
   cible d’affectation, de boucle, de with, d’except ou de compréhension.

Seuls les usages qui échappent à toutes ces règles sont signalés.
"""

import ast
import argparse
import builtins
import os
import sys

def _extract_target_names(node):
    """Retourne la liste des identifiants liés par un nœud cible."""
    if isinstance(node, ast.Name):
        return [node.id]
    if isinstance(node, (ast.Tuple, ast.List)):
        names = []
        for elt in node.elts:
            names.extend(_extract_target_names(elt))
        return names
    return []  # Attribute, Subscript, etc. ne créent pas de liaison de nom


class Analyzer(ast.NodeVisitor):
    def __init__(self, filename):
        self.filename = filename
        self.module_defs = set()          # noms définis au niveau module
        self.func_parent = {}            # fonction -> fonction parent (ou None)
        self.func_name = {}               # fonction -> son nom
        self.func_imports = {}            # fonction -> {nom: ligne_import}
        self.func_locals = {}             # fonction -> ensemble de noms locaux (paramètres, cibles)
        self.usage = []                   # (nom, ligne, fonction_ou_None)

        self._func_stack = []             # pile des fonctions en cours de visite

    # ------------------------------------------------------------------ #
    # Helpers pour la pile de fonctions
    # ------------------------------------------------------------------ #
    def _enter_function(self, node):
        parent = self._func_stack[-1] if self._func_stack else None
        self.func_parent[node] = parent
        self.func_name[node] = getattr(node, 'name', '<lambda>')
        self.func_imports[node] = {}
        self.func_locals[node] = set()
        self._func_stack.append(node)

        # paramètres
        args = node.args
        for arg in getattr(args, 'posonlyargs', []):
            self.func_locals[node].add(arg.arg)
        for arg in args.args:
            self.func_locals[node].add(arg.arg)
        if args.vararg:
            self.func_locals[node].add(args.vararg.arg)
        for arg in args.kwonlyargs:
            self.func_locals[node].add(arg.arg)
        if args.kwarg:
            self.func_locals[node].add(args.kwarg.arg)

    def _exit_function(self):
        self._func_stack.pop()

    # ------------------------------------------------------------------ #
    # Visite des nœuds
    # ------------------------------------------------------------------ #
    def visit_Module(self, node):
        # définitions de niveau module (imports, assignations, fonctions, classes)
        for stmt in node.body:
            if isinstance(stmt, (ast.Import, ast.ImportFrom)):
                for alias in stmt.names:
                    name = alias.asname or alias.name.split('.')[0]
                    self.module_defs.add(name)
            elif isinstance(stmt, (ast.Assign, ast.AnnAssign)):
                targets = stmt.targets if isinstance(stmt, ast.Assign) else [stmt.target]
                for tgt in targets:
                    self.module_defs.update(_extract_target_names(tgt))
            elif isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                self.module_defs.add(stmt.name)
        self.generic_visit(node)

    def visit_FunctionDef(self, node):
        self._enter_function(node)
        self.generic_visit(node)
        self._exit_function()

    def visit_AsyncFunctionDef(self, node):
        self._enter_function(node)
        self.generic_visit(node)
        self._exit_function()

    def visit_Import(self, node):
        if self._func_stack:
            func = self._func_stack[-1]
            for alias in node.names:
                name = alias.asname or alias.name.split('.')[0]
                func_imports = self.func_imports[func]
                if name not in func_imports:
                    func_imports[name] = node.lineno
        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        if self._func_stack:
            func = self._func_stack[-1]
            for alias in node.names:
                if alias.name == '*':
                    continue
                name = alias.asname or alias.name
                func_imports = self.func_imports[func]
                if name not in func_imports:
                    func_imports[name] = node.lineno
        self.generic_visit(node)

    def visit_Assign(self, node):
        current = self._func_stack[-1] if self._func_stack else None
        if current:
            for tgt in node.targets:
                self.func_locals[current].update(_extract_target_names(tgt))
        self.generic_visit(node)

    def visit_AnnAssign(self, node):
        current = self._func_stack[-1] if self._func_stack else None
        if current:
            self.func_locals[current].update(_extract_target_names(node.target))
        self.generic_visit(node)

    def visit_AugAssign(self, node):
        current = self._func_stack[-1] if self._func_stack else None
        if current:
            self.func_locals[current].update(_extract_target_names(node.target))
        self.generic_visit(node)

    def visit_For(self, node):
        current = self._func_stack[-1] if self._func_stack else None
        if current:
            self.func_locals[current].update(_extract_target_names(node.target))
        self.generic_visit(node)

    def visit_AsyncFor(self, node):
        self.visit_For(node)

    def visit_With(self, node):
        current = self._func_stack[-1] if self._func_stack else None
        if current:
            for item in node.items:
                if item.optional_vars:
                    self.func_locals[current].update(_extract_target_names(item.optional_vars))
        self.generic_visit(node)

    def visit_AsyncWith(self, node):
        self.visit_With(node)

    def visit_ExceptHandler(self, node):
        current = self._func_stack[-1] if self._func_stack else None
        if current and node.name:
            self.func_locals[current].add(node.name)
        self.generic_visit(node)

    def visit_Name(self, node):
        if isinstance(node.ctx, ast.Load):
            func = self._func_stack[-1] if self._func_stack else None
            self.usage.append((node.id, node.lineno, func))
        self.generic_visit(node)


def analyse_file(path):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            source = f.read()
    except (OSError, IOError) as exc:
        sys.stderr.write("Erreur de lecture %s : %s\n" % (path, exc))
        return []

    try:
        tree = ast.parse(source, filename=path)
    except SyntaxError as exc:
        sys.stderr.write("Erreur de syntaxe %s : %s\n" % (path, exc))
        return []

    analyzer = Analyzer(path)
    analyzer.visit(tree)

    builtin_names = set(dir(builtins))
    defects = []

    # pré‑calcul : fonctions qui importent chaque nom
    name_to_funcs = {}
    for func, imports in analyzer.func_imports.items():
        for name, line in imports.items():
            name_to_funcs.setdefault(name, []).append((func, line))

    # fonction auxiliaire : vérifier si un nom est importé dans un ancêtre
    def imported_in_ancestors(func, name):
        cur = func
        while cur is not None:
            if name in analyzer.func_imports.get(cur, {}):
                return True
            cur = analyzer.func_parent.get(cur)
        return False

    for name, lineno, func in analyzer.usage:
        if name in builtin_names or name in analyzer.module_defs:
            continue

        # cas où le nom est localement lié dans la fonction courante
        if func is not None and name in analyzer.func_locals.get(func, set()):
            continue

        if func is None:
            # usage au niveau module
            if name in name_to_funcs:
                import_func, import_line = name_to_funcs[name][0]
                defects.append((path, lineno, name,
                                 analyzer.func_name[import_func],
                                 import_line))
        else:
            if imported_in_ancestors(func, name):
                continue
            if name in name_to_funcs:
                import_func, import_line = name_to_funcs[name][0]
                defects.append((path, lineno, name,
                                 analyzer.func_name[import_func],
                                 import_line))

    return defects


def iter_py_files(root, explicit_files):
    if explicit_files:
        for p in explicit_files:
            if os.path.isfile(p) and p.endswith('.py'):
                yield p
    else:
        for dirpath, _, filenames in os.walk(root):
            for fn in filenames:
                if fn.endswith('.py'):
                    yield os.path.join(dirpath, fn)


def main():
    parser = argparse.ArgumentParser(description="Détecte les imports locaux utilisés hors de leur fonction.")
    parser.add_argument('--racine', default=os.path.dirname(os.path.abspath(__file__)),
                        help='répertoire racine à parcourir (défaut : répertoire du script)')
    parser.add_argument('files', nargs='*', help='fichiers à analyser (privilégie la racine sinon)')
    args = parser.parse_args()

    # reconfigure stdout si possible
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')

    all_defects = []
    for py_file in iter_py_files(args.racine, args.files):
        defects = analyse_file(py_file)
        all_defects.extend(defects)

    for path, line, name, func_name, import_line in all_defects:
        sys.stdout.write("%s:%d: nom '%s' importe seulement dans '%s' (ligne d'import : %d)\n" %
                         (path, line, name, func_name, import_line))

    if not all_defects:
        sys.stdout.write("OK\n")
        sys.exit(0)
    else:
        sys.stdout.write("DEFAUTS: %d\n" % len(all_defects))
        sys.exit(1)


if __name__ == '__main__':
    main()
