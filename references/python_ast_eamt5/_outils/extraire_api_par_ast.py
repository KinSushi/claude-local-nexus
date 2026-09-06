# Produit par gpt-oss-120b-cloud (Ollama Cloud -- les donnees sortent)
import sys
import os
import argparse
import sysconfig
import importlib.metadata
import ast
import datetime
import traceback

# Cache lazily built packages -> distributions mapping
_pkg_dist_map = None

def _load_packages_distributions():
    global _pkg_dist_map
    if _pkg_dist_map is None:
        try:
            _pkg_dist_map = importlib.metadata.packages_distributions()
        except Exception:
            _pkg_dist_map = {}
    return _pkg_dist_map

def read_version(lib_name: str):
    """
    Retourne (version, source) où source décrit la voie qui a fourni la version.
    - Voie 1 : version directe du module (source = 'nom de distribution direct')
    - Voie 2 : version d'une distribution qui fournit le module (source = 'distribution <dist> fournissant le module <lib_name>')
    - Aucun succès : (None, None)
    """
    # Voie 1
    try:
        ver = importlib.metadata.version(lib_name)
        return ver, 'nom de distribution direct'
    except importlib.metadata.PackageNotFoundError:
        pass

    # Voie 2
    pkg_map = _load_packages_distributions()
    dists = pkg_map.get(lib_name)
    if dists:
        for dist_name in dists:
            try:
                ver = importlib.metadata.version(dist_name)
                src = f'distribution {dist_name} fournissant le module {lib_name}'
                return ver, src
            except importlib.metadata.PackageNotFoundError:
                continue

    # Aucun résultat
    return None, None

def build_signature(args_node: ast.arguments) -> str:
    parts = []
    # Positional-only args
    posonly = args_node.posonlyargs
    regular = args_node.args
    defaults = list(args_node.defaults)
    # Align defaults to the right
    total_pos = len(posonly) + len(regular)
    defaults = [None] * (total_pos - len(defaults)) + defaults
    # Posonly
    for i, arg in enumerate(posonly):
        s = arg.arg
        if arg.annotation:
            s += ': ' + ast.unparse(arg.annotation)
        default = defaults[i]
        if default is not None:
            s += ' = ' + ast.unparse(default)
        parts.append(s)
    if posonly:
        parts.append('/')  # separator after posonly
    # Regular args
    for i, arg in enumerate(regular, start=len(posonly)):
        s = arg.arg
        if arg.annotation:
            s += ': ' + ast.unparse(arg.annotation)
        default = defaults[i]
        if default is not None:
            s += ' = ' + ast.unparse(default)
        parts.append(s)
    # Vararg
    if args_node.vararg:
        s = '*' + args_node.vararg.arg
        if args_node.vararg.annotation:
            s += ': ' + ast.unparse(args_node.vararg.annotation)
        parts.append(s)
    elif args_node.kwonlyargs:
        parts.append('*')
    # Kwonly args
    for kwarg, default in zip(args_node.kwonlyargs, args_node.kw_defaults):
        s = kwarg.arg
        if kwarg.annotation:
            s += ': ' + ast.unparse(kwarg.annotation)
        if default is not None:
            s += ' = ' + ast.unparse(default)
        parts.append(s)
    # Kwarg
    if args_node.kwarg:
        s = '**' + args_node.kwarg.arg
        if args_node.kwarg.annotation:
            s += ': ' + ast.unparse(args_node.kwarg.annotation)
        parts.append(s)
    return ', '.join(parts)

def extract_symbols_from_ast(tree: ast.Module, module_qual: str):
    symbols = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if not node.name.startswith('_'):
                qual = f"{module_qual}.{node.name}"
                doc = ast.get_docstring(node, clean=True)
                sig = f"({build_signature(node.args)})"
                typ = 'async function' if isinstance(node, ast.AsyncFunctionDef) else 'function'
                symbols.append((qual, typ, sig, doc))
        elif isinstance(node, ast.ClassDef):
            if not node.name.startswith('_'):
                class_qual = f"{module_qual}.{node.name}"
                doc = ast.get_docstring(node, clean=True)
                symbols.append((class_qual, 'class', '()', doc))
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        if not item.name.startswith('_'):
                            meth_qual = f"{class_qual}.{item.name}"
                            meth_doc = ast.get_docstring(item, clean=True)
                            meth_sig = f"({build_signature(item.args)})"
                            meth_type = 'async function' if isinstance(item, ast.AsyncFunctionDef) else 'method'
                            symbols.append((meth_qual, meth_type, meth_sig, meth_doc))
    return symbols

def locate_package(lib_name: str, site_packages: str):
    # Determine version and source via read_version
    version, source = read_version(lib_name)

    # Directories or simple modules in site-packages
    possible_dir = os.path.join(site_packages, lib_name)
    if os.path.isdir(possible_dir):
        return possible_dir, version, source
    possible_file = os.path.join(site_packages, f"{lib_name}.py")
    if os.path.isfile(possible_file):
        return possible_file, version, source

    # Use distribution metadata (handles cases like scikit-learn -> sklearn)
    try:
        dist = importlib.metadata.distribution(lib_name)
        # If version not already found via read_version, use distribution version
        if version is None:
            version = dist.version
            source = 'nom de distribution direct'
        # Try top_level.txt which lists top‑level modules/packages
        try:
            top = dist.read_text('top_level.txt')
        except Exception:
            top = None
        if top:
            for line in top.splitlines():
                name = line.strip()
                if not name:
                    continue
                pkg_dir = os.path.join(site_packages, name)
                if os.path.isdir(pkg_dir):
                    return pkg_dir, version, source
                pkg_file = os.path.join(site_packages, f"{name}.py")
                if os.path.isfile(pkg_file):
                    return pkg_file, version, source
        # Fallback: inspect files and keep only those whose first segment matches a module name
        if dist.files:
            for p in dist.files:
                parts = p.parts
                if not parts:
                    continue
                first = parts[0]
                pkg_dir = os.path.join(site_packages, first)
                if os.path.isdir(pkg_dir):
                    return pkg_dir, version, source
                pkg_file = os.path.join(site_packages, f"{first}.py")
                if os.path.isfile(pkg_file):
                    return pkg_file, version, source
    except importlib.metadata.PackageNotFoundError:
        pass
    # Package not found → fail closed
    sys.exit(2)

def process_library(lib_name: str, site_packages: str, output_dir: str):
    location, version, source = locate_package(lib_name, site_packages)
    error_files = {'SyntaxError': [], 'UnicodeDecodeError': [], 'OtherError': []}
    symbols = []
    if location is None:
        return False, symbols, error_files, version or 'INCONNUE'
    if os.path.isdir(location):
        root = location
        # os.walk now starts from the package directory (not site-packages root)
        for dirpath, _, filenames in os.walk(root):
            for fname in filenames:
                if not fname.endswith('.py'):
                    continue
                fpath = os.path.join(dirpath, fname)
                rel_path = os.path.relpath(fpath, root)
                module_path = rel_path[:-3].replace(os.sep, '.')
                if fname == '__init__.py':
                    module_qual = lib_name
                else:
                    module_qual = f"{lib_name}.{module_path}"
                try:
                    with open(fpath, 'r', encoding='utf-8') as f:
                        file_content = f.read()
                except UnicodeDecodeError:
                    error_files['UnicodeDecodeError'].append(fpath)
                    continue
                except Exception:
                    error_files['OtherError'].append(fpath)
                    continue
                try:
                    tree = ast.parse(file_content, filename=fpath)
                except SyntaxError:
                    error_files['SyntaxError'].append(fpath)
                    continue
                except Exception:
                    error_files['OtherError'].append(fpath)
                    continue
                symbols.extend(extract_symbols_from_ast(tree, module_qual))
    elif os.path.isfile(location) and location.endswith('.py'):
        fpath = location
        module_qual = lib_name
        try:
            with open(fpath, 'r', encoding='utf-8') as f:
                file_content = f.read()
        except UnicodeDecodeError:
            error_files['UnicodeDecodeError'].append(fpath)
        except Exception:
            error_files['OtherError'].append(fpath)
        else:
            try:
                tree = ast.parse(file_content, filename=fpath)
            except SyntaxError:
                error_files['SyntaxError'].append(fpath)
            except Exception:
                error_files['OtherError'].append(fpath)
            else:
                symbols.extend(extract_symbols_from_ast(tree, module_qual))
    else:
        return False, symbols, error_files, version or 'INCONNUE'

    # Write markdown
    out_path = os.path.join(output_dir, f"{lib_name}_api_ast.md")
    now = datetime.datetime.now().astimezone()
    interpreter_version = sys.version.splitlines()[0]
    interpreter_path = sys.executable
    with open(out_path, 'w', encoding='utf-8') as out:
        out.write(f"# {lib_name} - API publique installee (lecture AST, sans import)\n\n")
        if version is not None:
            out.write(f"- Version installee : {version} (source: {source})\n")
        else:
            out.write("- Version installee : INCONNUE (aucune distribution trouvee pour ce module ; le corpus produit n'est PAS ancre)\n")
        out.write(f"- Version de l'interpreteur ayant produit ce fichier : {interpreter_version}\n")
        out.write(f"- Chemin de cet interpreteur : {interpreter_path}\n")
        out.write(f"- Date de generation (ISO 8601) : {now.isoformat()}\n")
        out.write(f"- Symboles documentes dans ce fichier : {len(symbols)}\n")
        out.write("- Origine : lecture AST du CODE SOURCE installe dans site-packages, SANS import. Methode choisie parce que Smart App Control refuse de charger les binaires natifs non signes de cette bibliotheque ; le code source installe est la source officielle a la version exacte installee.\n")
        out.write("- LIMITE DECLAREE DE CETTE METHODE : l'AST ne voit QUE ce qui est ecrit dans les fichiers .py. Il ne voit PAS les symboles crees dynamiquement (setattr, metaclasses, generation a l'import), ni les fonctions et classes definies dans des extensions compilees (.pyd, .so). Un symbole absent de ce fichier n'est donc PAS une preuve qu'il n'existe pas dans la bibliotheque.\n\n")
        out.write("---\n")
        for qual, typ, sig, doc in sorted(symbols, key=lambda x: x[0]):
            out.write(f"### `{qual}`\n\n")
            out.write(f"- Type : {typ}\n")
            out.write(f"- Signature : `{sig}`\n\n")
            if doc:
                out.write(f"{doc}\n\n")
            else:
                out.write("(docstring absente)\n\n")
            out.write("---\n")
        # Errors section
        if any(error_files.values()):
            out.write("\n### Fichiers avec erreurs\n\n")
            for err_type, files in error_files.items():
                if files:
                    out.write(f"- {err_type} ({len(files)}):\n")
                    for fp in files:
                        out.write(f"  - {fp}\n")
    success = len(symbols) > 0
    return success, symbols, error_files, version or 'INCONNUE'

def main():
    parser = argparse.ArgumentParser(description="Extraction d'API via AST sans import.")
    parser.add_argument('--lib', action='append', required=True, help='Nom du paquet à documenter (peut être répété).')
    parser.add_argument('--site-packages', default=sysconfig.get_paths()['purelib'], help='Chemin du site-packages.')
    parser.add_argument('--sortie', required=True, help='Dossier où écrire les fichiers markdown.')
    args = parser.parse_args()
    os.makedirs(args.sortie, exist_ok=True)
    overall_success = True
    for lib in args.lib:
        success, _, _, _ = process_library(lib, args.site_packages, args.sortie)
        if not success:
            overall_success = False
    sys.exit(0 if overall_success else 2)

if __name__ == '__main__':
    main()

