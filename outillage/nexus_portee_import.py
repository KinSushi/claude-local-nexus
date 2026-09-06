#!/usr/bin/env python3
"""
Detecte deux types de defauts :

1. import local utilise hors de sa fonction (deja implemente)
2. utilisation d'un module standard comme base d'attribut sans aucun import
   ni definition locale.

Le second controle ne s'active que si sys.stdlib_module_names existe.
En presence d'un import *, le fichier est ignore avec un message sur stderr.
"""

import ast
import argparse
import builtins
import os
import sys

# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _extract_target_names(node):
    """Retourne la liste des identifiants liés par un noeud cible."""
    if isinstance(node, ast.Name):
        return [node.id]
    if isinstance(node, (ast.Tuple, ast.List)):
        names = []
        for elt in node.elts:
            names.extend(_extract_target_names(elt))
        return names
    return []  # Attribute, Subscript, etc. ne créent pas de liaison de nom


# --------------------------------------------------------------------------- #
# Analyseur AST
# --------------------------------------------------------------------------- #
class Analyzer(ast.NodeVisitor):
    def __init__(self, filename):
        self.filename = filename

        # definitions au niveau du module
        self.module_defs = set()          # imports, assignations, fonctions, classes, globals, nonlocals
        self.module_imports = set()        # noms importes au niveau module

        # informations sur les fonctions
        self.func_parent = {}              # fonction -> fonction parent (ou None)
        self.func_name = {}               # fonction -> son nom
        self.func_imports = {}            # fonction -> {nom: ligne_import}
        self.func_locals = {}              # fonction -> ensemble de noms locaux (params, cibles, comprehensions)

        # usages
        self.usage = []                   # (nom, ligne, fonction_ou_None)
        self.attr_usage = []              # (nom_base, ligne)

        # pile de fonctions en cours de visite
        self._func_stack = []

        # presence d'un import *
        self._has_star_import = False

    # ------------------------------------------------------------------ #
    # Gestion de la pile de fonctions
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
    # Visite des noeuds
    # ------------------------------------------------------------------ #
    def visit_Module(self, node):
        for stmt in node.body:
            if isinstance(stmt, (ast.Import, ast.ImportFrom)):
                for alias in stmt.names:
                    if isinstance(stmt, ast.ImportFrom) and alias.name == '*':
                        self._has_star_import = True
                        continue
                    name = alias.asname or (alias.name.split('.')[0] if isinstance(stmt, ast.Import) else alias.name)
                    self.module_defs.add(name)
                    self.module_imports.add(name)
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
                self.func_imports[func].setdefault(name, node.lineno)
        else:
            for alias in node.names:
                name = alias.asname or alias.name.split('.')[0]
                self.module_defs.add(name)
                self.module_imports.add(name)
        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        if node.module == '__future__':
            # ignore future imports
            self.generic_visit(node)
            return
        if node.names and any(alias.name == '*' for alias in node.names):
            self._has_star_import = True
            # on ne poursuit pas le traitement de ce import *
        if self._func_stack:
            func = self._func_stack[-1]
            for alias in node.names:
                if alias.name == '*':
                    continue
                name = alias.asname or alias.name
                self.func_imports[func].setdefault(name, node.lineno)
        else:
            for alias in node.names:
                if alias.name == '*':
                    continue
                name = alias.asname or alias.name
                self.module_defs.add(name)
                self.module_imports.add(name)
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

    def visit_Global(self, node):
        for name in node.names:
            self.module_defs.add(name)

    def visit_Nonlocal(self, node):
        for name in node.names:
            self.module_defs.add(name)

    # Comprehensions : on collecte les cibles de chaque generator
    def _handle_comprehension(self, generators):
        current = self._func_stack[-1] if self._func_stack else None
        for gen in generators:
            if current:
                self.func_locals[current].update(_extract_target_names(gen.target))
            else:
                self.module_defs.update(_extract_target_names(gen.target))

    def visit_ListComp(self, node):
        self._handle_comprehension(node.generators)
        self.generic_visit(node)

    def visit_SetComp(self, node):
        self._handle_comprehension(node.generators)
        self.generic_visit(node)

    def visit_DictComp(self, node):
        self._handle_comprehension(node.generators)
        self.generic_visit(node)

    def visit_GeneratorExp(self, node):
        self._handle_comprehension(node.generators)
        self.generic_visit(node)

    def visit_Name(self, node):
        if isinstance(node.ctx, ast.Load):
            func = self._func_stack[-1] if self._func_stack else None
            self.usage.append((node.id, node.lineno, func))
        self.generic_visit(node)

    def visit_Attribute(self, node):
        # on ne s'interesse qu'aux lectures de la forme NOM.xxx
        if isinstance(node.value, ast.Name) and isinstance(node.ctx, ast.Load):
            self.attr_usage.append((node.value.id, node.lineno))
        self.generic_visit(node)


# --------------------------------------------------------------------------- #
# Analyse d'un fichier
# --------------------------------------------------------------------------- #
def analyse_file(path):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            source = f.read()
    except (OSError, UnicodeDecodeError) as exc:
        # UnicodeDecodeError est un ValueError, JAMAIS un OSError : un fichier
        # non UTF-8 traversait donc ce filtre et faisait planter le detecteur
        # avec une trace. Or ce detecteur est appele par la porte de
        # conformite : un seul fichier mal encode dans scripts/ aurait bloque
        # le demarrage, ce qui est exactement le defaut que ce depot nomme
        # « un garde qui plante arrete le travail qu'il protegeait ».
        #
        # Trouve le 2026-08-30 par une vague d'audit deleguee, sur ce fichier
        # meme, quelques minutes apres sa livraison.
        sys.stderr.write("Fichier ignore, illisible en utf-8 : %s (%s)\n" % (path, exc))
        return [], False

    try:
        tree = ast.parse(source, filename=path)
    except SyntaxError as exc:
        sys.stderr.write(f"Erreur de syntaxe {path} : {exc}\n")
        return [], False

    analyzer = Analyzer(path)
    analyzer.visit(tree)

    # si un import * a ete rencontre, on abandonne le fichier
    if analyzer._has_star_import:
        sys.stderr.write(f"Star import detected in {path}, skipping file\n")
        return [], False

    # ------------------------------------------------- #
    # 1. Controle existant : import local mal utilise
    # ------------------------------------------------- #
    builtin_names = set(dir(builtins))
    defects_local = []

    # map nom -> [(func, ligne_import), ...]
    name_to_funcs = {}
    for func, imports in analyzer.func_imports.items():
        for name, line in imports.items():
            name_to_funcs.setdefault(name, []).append((func, line))

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
        if func is not None and name in analyzer.func_locals.get(func, set()):
            continue

        if func is None:
            if name in name_to_funcs:
                import_func, import_line = name_to_funcs[name][0]
                defects_local.append((path, lineno, name,
                                      analyzer.func_name[import_func],
                                      import_line))
        else:
            if imported_in_ancestors(func, name):
                continue
            if name in name_to_funcs:
                import_func, import_line = name_to_funcs[name][0]
                defects_local.append((path, lineno, name,
                                      analyzer.func_name[import_func],
                                      import_line))

    # ------------------------------------------------- #
    # 2. Nouveau controle : attribut base module standard non importe
    # ------------------------------------------------- #
    try:
        stdlib_names = set(sys.stdlib_module_names)
    except AttributeError:
        stdlib_names = set()   # on ne fait rien si l'attribut n'existe pas

    # ensemble de tous les noms liés quelque part dans le fichier
    all_bound = set(analyzer.module_defs)
    all_bound.update(analyzer.module_imports)
    for locals_set in analyzer.func_locals.values():
        all_bound.update(locals_set)
    for imports in analyzer.func_imports.values():
        all_bound.update(imports.keys())

    defects_attr = []
    for base_name, lineno in analyzer.attr_usage:
        if base_name in stdlib_names and base_name not in all_bound:
            defects_attr.append((path, lineno, base_name))

    return defects_local + defects_attr, True


# --------------------------------------------------------------------------- #
# Parcours des fichiers .py
# --------------------------------------------------------------------------- #
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


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main():
    parser = argparse.ArgumentParser(
        description="Detecte deux types de defauts d'import.")
    parser.add_argument('--racine', default=os.path.dirname(os.path.abspath(__file__)),
                        help='repertoire racine a parcourir')
    parser.add_argument('files', nargs='*', help='fichiers a analyser')
    args = parser.parse_args()

    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')

    all_defects = []
    for py_file in iter_py_files(args.racine, args.files):
        defects, ok = analyse_file(py_file)
        if ok:
            all_defects.extend(defects)

    for item in all_defects:
        if len(item) == 5:
            # defaut du premier type
            path, line, name, func_name, import_line = item
            sys.stdout.write(
                "%s:%s: nom '%s' importe seulement dans '%s' (ligne d'import : %s)\n"
                % (path, line, name, func_name, import_line))
        else:
            # defaut du second type
            path, line, name = item
            sys.stdout.write(
                "%s:%s: nom '%s' employe comme module sans etre importe nulle part\n"
                % (path, line, name))

    if not all_defects:
        sys.stdout.write("OK\n")
        sys.exit(0)
    else:
        sys.stdout.write(f"DEFAUTS: {len(all_defects)}\n")
        sys.exit(1)


if __name__ == '__main__':
    main()
