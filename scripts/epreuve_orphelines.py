# -*- coding: utf-8 -*-
import ast
import json
import sys
from pathlib import Path

def find_repo_root(start: Path) -> Path:
    p = start.resolve()
    while p != p.parent:
        if (p / "scripts").is_dir():
            return p
        p = p.parent
    return start.resolve().parent

def collect_references(tree: ast.AST) -> set:
    refs = set()
    class RefVisitor(ast.NodeVisitor):
        def visit_Name(self, node: ast.Name):
            refs.add(node.id)
            self.generic_visit(node)

        def visit_Attribute(self, node: ast.Attribute):
            # collect attribute name (attr) and also the value if it's a Name
            refs.add(node.attr)
            self.generic_visit(node)

    RefVisitor().visit(tree)
    return refs

def is_module_level(func: ast.FunctionDef, parent_map: dict) -> bool:
    return isinstance(parent_map.get(func), ast.Module)

def build_parent_map(tree: ast.AST) -> dict:
    parent_map = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parent_map[child] = node
    return parent_map

def main():
    repo_root = find_repo_root(Path(__file__).parent)
    scripts_dir = repo_root / "scripts"
    if not scripts_dir.is_dir():
        scripts_dir = repo_root

    all_refs = set()
    module_funcs = []

    for py_path in scripts_dir.rglob("*.py"):
        try:
            source = py_path.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(py_path))
        except Exception:
            continue  # ignore files that cannot be parsed

        all_refs.update(collect_references(tree))

        parent_map = build_parent_map(tree)
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.FunctionDef):
                name = node.name
                if name.startswith("_") and not name.startswith("__") and is_module_level(node, parent_map):
                    module_funcs.append((name, py_path))

    orphan_funcs = [(name, path) for name, path in module_funcs if name not in all_refs]

    # Load or create reference
    # Une reference de cliquet doit etre SUIVIE, sinon elle se remet a zero ailleurs et le cliquet ne retient rien.
    rituels_dir = repo_root / "rituels"
    ref_file = rituels_dir / "orphelines_reference.json"
    if not ref_file.is_file():
        rituels_dir.mkdir(parents=True, exist_ok=True)
        ref_data = {"compte": len(orphan_funcs)}
        ref_file.write_text(json.dumps(ref_data, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[OK  ] reference_created : compte initial {len(orphan_funcs)}")
        sys.exit(0)

    try:
        ref_data = json.loads(ref_file.read_text(encoding="utf-8"))
        ref_count = int(ref_data.get("compte", 0))
    except Exception:
        ref_count = 0

    current_count = len(orphan_funcs)

    if current_count > ref_count:
        # Failure: list all orphan functions as RATE
        for name, path in orphan_funcs:
            print(f"[RATE] {name} : orpheline dans {path.relative_to(repo_root)}")
        sys.exit(1)
    else:
        # Success: possibly update reference if count decreased
        print(f"[OK  ] cliquet : {current_count} orpheline(s), reference {ref_count}")
        if current_count < ref_count:
            ref_data["compte"] = current_count
            ref_file.write_text(json.dumps(ref_data, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"[OK  ] reference_updated : nouveau compte {current_count}")
        for name, path in orphan_funcs:
            print(f"[OK  ] {name} : orpheline dans {path.relative_to(repo_root)}")
        sys.exit(0)

if __name__ == "__main__":
    main()