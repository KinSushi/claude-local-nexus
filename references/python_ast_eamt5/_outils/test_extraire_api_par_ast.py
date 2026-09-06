# Produit par gpt-oss-120b-cloud (Ollama Cloud -- les donnees sortent)
import subprocess
import sys
import os
import sysconfig
import pathlib
import ast
import importlib.util

def _run_script(lib, site_packages, output_dir):
    """Execute extraire_api_par_ast.py pour une bibliothèque donnée et renvoie CompletedProcess."""
    script_path = pathlib.Path(__file__).resolve().with_name("extraire_api_par_ast.py")
    assert script_path.is_file(), f"script introuvable : {script_path}"
    args = [
        sys.executable,
        str(script_path),
        "--lib",
        lib,
        "--site-packages",
        str(site_packages),
        "--sortie",
        str(output_dir),
    ]
    return subprocess.run(args, capture_output=True, text=True)

def _read_markdown(lib, output_dir):
    md_path = pathlib.Path(output_dir) / f"{lib}_api_ast.md"
    return md_path.read_text(encoding="utf-8")

def test_public_private_symbols(tmp_path):
    """TEST – vérifie que seules les entités publiques sont documentées et que le compteur est cohérent."""
    pkg_name = "dummy_pkg"
    pkg_dir = tmp_path / pkg_name
    pkg_dir.mkdir()
    (pkg_dir / "__init__.py").write_text("", encoding="utf-8")
    mod_path = pkg_dir / "mod.py"
    mod_path.write_text(
        '''
def public_func(a: int, b=2, *args, **kwargs):
    """Fonction publique."""
    pass

def _private_func():
    pass

class PublicClass:
    """Classe publique."""
    def public_method(self, x):
        """Methode publique."""
        pass

    def _private_method(self):
        pass
''',
        encoding="utf-8",
    )
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    result = _run_script(pkg_name, tmp_path, out_dir)
    assert result.returncode == 0, f"Le script a échoué avec code {result.returncode}"
    md = _read_markdown(pkg_name, out_dir)

    assert "dummy_pkg.mod.public_func" in md, "La fonction publique doit être documentée"
    assert "dummy_pkg.mod.PublicClass" in md, "La classe publique dummy_pkg.mod.PublicClass doit être documentée"
    assert "dummy_pkg.mod.PublicClass.public_method" in md, "La méthode publique dummy_pkg.mod.PublicClass.public_method doit être documentée"

    assert "dummy_pkg.mod._private_func" not in md, "La fonction privée ne doit pas être documentée"
    assert "dummy_pkg.PublicClass._private_method" not in md, "La méthode privée ne doit pas être documentée"

    import re
    symbol_lines = re.findall(r"^### `", md, flags=re.MULTILINE)
    count_titles = len(symbol_lines)
    match = re.search(r"Symboles documentes dans ce fichier : (\d+)", md)
    assert match, "Ligne de comptage des symboles introuvable"
    count_declared = int(match.group(1))
    assert count_titles == count_declared, (
        f"Le nombre de titres ({count_titles}) doit correspondre au compteur déclaré ({count_declared})"
    )

def test_nonexistent_library(tmp_path):
    """REVERSE‑TEST (a) – la bibliothèque demandée n’existe pas doit renvoyer le code 2."""
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    result = _run_script("paquet_qui_nexiste_pas_12345", tmp_path, out_dir)
    assert result.returncode == 2, f"Code de sortie attendu 2, obtenu {result.returncode}"

def test_package_without_public_symbols(tmp_path):
    """REVERSE‑TEST (b) – un paquet présent mais sans symbole public doit renvoyer le code 2."""
    pkg_name = "empty_pkg"
    pkg_dir = tmp_path / pkg_name
    pkg_dir.mkdir()
    (pkg_dir / "__init__.py").write_text(
        '''
def _private():
    pass

class _Hidden:
    pass
''',
        encoding="utf-8",
    )
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    result = _run_script(pkg_name, tmp_path, out_dir)
    assert result.returncode == 2, f"Code de sortie attendu 2, obtenu {result.returncode}"

def test_mixed_package_with_syntax_error(tmp_path):
    """REVERSE‑TEST (c) – un paquet contenant un fichier syntaxiquement erroné doit le répertorier."""
    pkg_name = "mixed_pkg"
    pkg_dir = tmp_path / pkg_name
    pkg_dir.mkdir()
    (pkg_dir / "__init__.py").write_text("", encoding="utf-8")
    (pkg_dir / "good.py").write_text(
        '''
def good_func():
    """Bonne fonction."""
    pass
''',
        encoding="utf-8",
    )
    (pkg_dir / "bad.py").write_text(
        '''
def oops(: 
    pass
''',
        encoding="utf-8",
    )
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    result = _run_script(pkg_name, tmp_path, out_dir)
    assert result.returncode == 0, f"Le script devrait réussir (code 0), obtenu {result.returncode}"
    md = _read_markdown(pkg_name, out_dir)

    assert "mixed_pkg.good.good_func" in md, "Le fichier correct doit être présent dans le markdown"
    assert "Fichiers avec erreurs" in md, "Section des fichiers avec erreurs manquante"
    assert "SyntaxError" in md, "Le type d’erreur SyntaxError doit être listé"
    bad_path = str(pkg_dir / "bad.py")
    assert bad_path in md, f"Le chemin du fichier syntaxiquement erroné ({bad_path}) doit être présent"

def test_forward_real_library_signature(tmp_path):
    """FORWARD‑TEST – compare la signature d’une fonction publique réelle avec celle générée."""
    lib_name = "sktime"
    site_packages = sysconfig.get_paths()["purelib"]
    spec = importlib.util.find_spec(lib_name)
    assert spec and spec.submodule_search_locations, f"Impossible de localiser le package {lib_name}"
    pkg_root = pathlib.Path(spec.submodule_search_locations[0])
    target_file = None
    target_func = None
    for py_file in pkg_root.rglob("*.py"):
        source = py_file.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(py_file))
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and not node.name.startswith("_"):
                target_file = py_file
                target_func = node
                break
        if target_file:
            break
    assert target_file and target_func, "Aucune fonction publique trouvée dans sktime"

    expected_name = target_func.name
    pos_args = len(target_func.args.posonlyargs) + len(target_func.args.args)

    out_dir = tmp_path / "out"
    out_dir.mkdir()
    result = _run_script(lib_name, site_packages, out_dir)
    assert result.returncode == 0, f"Le script a échoué avec code {result.returncode}"
    md = _read_markdown(lib_name, out_dir)

    rel_path = target_file.relative_to(pkg_root).with_suffix("")
    module_qual = f"{lib_name}." + ".".join(rel_path.parts)
    full_qual = f"{module_qual}.{expected_name}"
    assert full_qual in md, f"Le symbole {full_qual} doit être présent dans le markdown"

    import re
    pattern = re.compile(rf"### `{re.escape(full_qual)}`\s+?- Type : .+?\s+?- Signature : `([^`]*)`", re.DOTALL)
    match = pattern.search(md)
    assert match, f"Signature du symbole {full_qual} introuvable"
    signature = match.group(1).strip()

    sig_args_part = signature.split(")")[0].lstrip("(")
    if sig_args_part.strip() == "":
        counted = 0
    else:
        parts = [p.strip() for p in sig_args_part.split(",")]
        counted = sum(1 for p in parts if not p.startswith("*"))
    assert counted == pos_args, (
        f"Nombre d'arguments positionnels attendu {pos_args}, trouvé {counted} dans la signature '{signature}'"
    )

