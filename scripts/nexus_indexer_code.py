#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Indexeur de symboles Python pour le rayon references/livres/code.

L'outil parcourt un depot de code source, extrait chaque fonction, classe et
méthode Python par analyse syntaxique (ast.parse). Il ne fait JAMAIS d'import
des modules du livre : un module de livre peut avoir des dépendances absentes,
et importer exécuterait du code tiers.

Il produit deux fichiers au format mesure sur le rayon existant :
- index.tsv : 5 colonnes (id, offset_octets, longueur_octets, type, resume)
- symbols.jsonl : un objet JSON par ligne, 25 champs exacts

Appel :
    python scripts/nexus_indexer_code.py --source .nexus/livres_code/<depot> \
                                         --cible references/livres/code \
                                         [--simuler]
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any

# Repertoires et motifs ecartes : pas de sens a indexer.
EXCLUDED_DIR_NAMES: set[str] = {
    ".git", "__pycache__", ".venv", "venv", "env", ".env",
    ".pytest_cache", ".mypy_cache", ".tox", "node_modules",
    ".idea", ".vscode", "build", "dist",
}
EXCLUDED_DIR_SUFFIXES: tuple[str, ...] = (
    ".egg-info", ".dist-info",
)


def _is_excluded_dir(name: str) -> bool:
    """Vrai si le répertoire doit être ignoré."""
    if name in EXCLUDED_DIR_NAMES:
        return True
    return any(name.endswith(suffix) for suffix in EXCLUDED_DIR_SUFFIXES)


def _repo_root_from_script() -> Path:
    """Racine du dépôt courant, dérivée de __file__."""
    return Path(__file__).resolve().parent.parent


def _default_source() -> Path:
    """Source par défaut : répertoire des dépôts de livres de code."""
    return _repo_root_from_script() / ".nexus" / "livres_code"


def _default_cible() -> Path:
    """Cible par défaut : rayon references/livres/code."""
    return _repo_root_from_script() / "references" / "livres" / "code"


def _file_fingerprint(rel_path: str) -> str:
    """Empreinte stable de huit caractères hex, déduite du chemin relatif."""
    digest = hashlib.sha256(rel_path.encode("utf-8")).hexdigest()
    return digest[:8]


def _chemin_point(rel_path: str) -> str:
    """Chemin relatif sans extension, avec '/' remplacé par '.'."""
    stem = Path(rel_path).with_suffix("").as_posix()
    return stem.replace("/", ".")


def _unparse_decorator(decorator: ast.expr) -> str:
    """Nom lisible d'un décorateur."""
    try:
        text = ast.unparse(decorator).strip()
    except Exception:
        text = "<decorateur_non_lu>"
    return text


def _extract_docstring(node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef
                       ) -> tuple[str, str]:
    """Retourne (docstring_brut, docstring_etat)."""
    doc = ast.get_docstring(node)
    if doc is None:
        return "", "ABSENTE"
    return doc, "PRESENTE"


def _extract_decorators(node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef
                        ) -> list[str]:
    """Liste des décorateurs sous forme de chaînes."""
    return [_unparse_decorator(d) for d in node.decorator_list]


def _extract_bases(node: ast.ClassDef) -> list[str]:
    """Liste des classes de base."""
    try:
        return [ast.unparse(b).strip() for b in node.bases]
    except Exception:
        return []


def _extract_parameters(node: ast.FunctionDef | ast.AsyncFunctionDef
                        ) -> tuple[list[str], int, str, str]:
    """Retourne (noms, nombre, état, annotation_retour)."""
    args = node.args
    names: list[str] = []
    for group in (args.posonlyargs, args.args, args.kwonlyargs):
        for arg in group:
            names.append(arg.arg)
    if args.vararg and args.vararg.arg:
        names.append(args.vararg.arg)
    if args.kwarg and args.kwarg.arg:
        names.append(args.kwarg.arg)
    n = len(names)
    etat = "AUCUN" if n == 0 else "OK"
    retour = ""
    if node.returns is not None:
        try:
            retour = ast.unparse(node.returns).strip()
        except Exception:
            retour = ""
    return names, n, etat, retour


def _build_signature(node: ast.AST) -> tuple[str, str]:
    """Reconstruit la ligne de définition et son état."""
    try:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            names, _, _, retour = _extract_parameters(node)
            retour_part = f" -> {retour}" if retour else ""
            kind = "async def " if isinstance(node, ast.AsyncFunctionDef) else "def "
            sig = f"{kind}{node.name}({', '.join(names)}){retour_part}:"
            return sig, "OK"
        if isinstance(node, ast.ClassDef):
            bases = _extract_bases(node)
            base_part = f"({', '.join(bases)})" if bases else "()"
            sig = f"class {node.name}{base_part}:"
            return sig, "OK"
    except Exception:
        pass
    return "", "ERREUR"


def _implementation(node: ast.AST, source: str) -> str:
    """Code source exact du symbole."""
    segment = ast.get_source_segment(source, node)
    if segment is None:
        return ""
    return segment


def _internal_symbols(cls_node: ast.ClassDef) -> list[str]:
    """Noms des symboles définis directement dans une classe."""
    found: list[str] = []
    for item in cls_node.body:
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            found.append(item.name)
    return found


def _make_resume(nom_qualifie: str, docstring_etat: str) -> str:
    """Résumé lisible, tronqué à 100 caractères comme le rayon existant."""
    full = f"{nom_qualifie} · ({docstring_etat.lower().replace('_', ' ')})"
    return full[:100]


def _build_symbol(
    node: ast.AST,
    source: str,
    rel_path: str,
    depot: str,
    class_stack: list[str],
) -> dict[str, Any]:
    """Construit un objet symbole avec les 25 champs requis."""
    chemin_point = _chemin_point(rel_path)
    impl = _implementation(node, source)
    octets = len(impl.encode("utf-8"))
    caracteres = len(impl)

    if isinstance(node, ast.ClassDef):
        sym_type = "class"
        nom_court = node.name
        arbre = "."
        nom_qualifie = f"{depot}.{chemin_point}.{nom_court}"
        docstring_brut, docstring_etat = _extract_docstring(node)
        signature, signature_etat = _build_signature(node)
        decorateurs = _extract_decorators(node)
        bases = _extract_bases(node)
        symboles_internes = _internal_symbols(node)
        parametres: list[str] = []
        n_parametres = 0
        parametres_etat = "AUCUN"
        retour_annotation = ""
    else:
        sym_type = "method" if class_stack else "function"
        nom_court = node.name
        arbre = class_stack[-1] if class_stack else "."
        if class_stack:
            nom_qualifie = f"{depot}.{chemin_point}.{class_stack[-1]}.{nom_court}"
        else:
            nom_qualifie = f"{depot}.{chemin_point}.{nom_court}"
        docstring_brut, docstring_etat = _extract_docstring(node)
        signature, signature_etat = _build_signature(node)
        decorateurs = _extract_decorators(node)
        bases = []
        symboles_internes = []
        parametres, n_parametres, parametres_etat, retour_annotation = (
            _extract_parameters(node)
        )

    empreinte = _file_fingerprint(rel_path)
    sym_id = f"code.{empreinte}.{depot}.{chemin_point}.{nom_court}"
    resume = _make_resume(nom_qualifie, docstring_etat)

    return {
        "id": sym_id,
        "resume": resume,
        "type": sym_type,
        "nom_court": nom_court,
        "nom_qualifie": nom_qualifie,
        "arbre": arbre,
        "chemin": f"{depot}/{rel_path}",
        "chemin_point": chemin_point,
        "ligne_debut": node.lineno,
        "ligne_fin": node.end_lineno or node.lineno,
        "decorateurs": decorateurs,
        "bases": bases,
        "symboles_internes": symboles_internes,
        "n_symboles_internes": len(symboles_internes),
        "signature": signature,
        "signature_etat": signature_etat,
        "docstring_brut": docstring_brut,
        "docstring_etat": docstring_etat,
        "parametres": parametres,
        "n_parametres": n_parametres,
        "parametres_etat": parametres_etat,
        "retour_annotation": retour_annotation,
        "implementation": impl,
        "caracteres": caracteres,
        "octets": octets,
    }


class _SymbolVisitor(ast.NodeVisitor):
    """Visiteur AST collectant fonctions, classes et méthodes."""

    def __init__(self, source: str, rel_path: str, depot: str) -> None:
        self.source = source
        self.rel_path = rel_path
        self.depot = depot
        self.symbols: list[dict[str, Any]] = []
        self.class_stack: list[str] = []

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.symbols.append(
            _build_symbol(node, self.source, self.rel_path, self.depot,
                          self.class_stack)
        )
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self.symbols.append(
            _build_symbol(node, self.source, self.rel_path, self.depot,
                          self.class_stack)
        )
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.symbols.append(
            _build_symbol(node, self.source, self.rel_path, self.depot,
                          self.class_stack)
        )
        self.class_stack.append(node.name)
        self.generic_visit(node)
        self.class_stack.pop()


def _collect_from_file(
    file_path: Path,
    depot_root: Path,
    depot_name: str,
) -> tuple[list[dict[str, Any]], bool]:
    """Indexe un fichier .py. Retourne (symboles, illisible)."""
    rel_path = file_path.relative_to(depot_root).as_posix()
    try:
        source_bytes = file_path.read_bytes()
    except Exception:
        return [], True

    try:
        source = source_bytes.decode("utf-8")
    except UnicodeDecodeError:
        try:
            source = source_bytes.decode("utf-8", errors="replace")
        except Exception:
            return [], True

    try:
        tree = ast.parse(source, filename=str(file_path))
    except SyntaxError:
        return [], True
    except Exception:
        return [], True

    visitor = _SymbolVisitor(source, rel_path, depot_name)
    visitor.visit(tree)
    return visitor.symbols, False


def _neutralise_magics(lines: list[str]) -> list[str]:
    """
    Transforme les lignes commençant (après espaces) par '!' ou '%' en commentaires.
    Coût : la magie disparait de l'implémentation extraite, donc un lecteur qui
    reconstruirait le carnet depuis le fragment n'obtiendrait pas un carnet
    exécutable. Le choix est assumé : l'index sert à CHERCHER du code, pas à le
    rejouer.
    """
    out: list[str] = []
    for line in lines:
        stripped = line.lstrip()
        if stripped.startswith("!") or stripped.startswith("%"):
            prefix = line[: len(line) - len(stripped)]
            new_line = f"{prefix}# {stripped}"
        else:
            new_line = line
        # Garantir un retour à la ligne pour chaque ligne afin d'éviter la fusion
        if not new_line.endswith("\n"):
            new_line += "\n"
        out.append(new_line)
    return out


def _collect_from_notebook(
    nb_path: Path,
    depot_root: Path,
    depot_name: str,
) -> tuple[list[dict[str, Any]], bool]:
    """Indexe un fichier .ipynb. Retourne (symboles, illisible)."""
    rel_path = nb_path.relative_to(depot_root).as_posix()
    try:
        raw = nb_path.read_bytes()
    except Exception:
        return [], True

    try:
        content = json.loads(raw.decode("utf-8"))
    except Exception:
        return [], True

    if not isinstance(content, dict) or "cells" not in content:
        return [], True

    # Concatène les sources des cellules de code.
    lines: list[str] = []
    for cell in content.get("cells", []):
        if cell.get("cell_type") != "code":
            continue
        src = cell.get("source", [])
        if isinstance(src, list):
            # S’assurer que chaque ligne se termine par un retour à la ligne.
            for l in src:
                if not l.endswith("\n"):
                    l = l + "\n"
                lines.append(l)
        elif isinstance(src, str):
            # splitlines(keepends=True) conserve déjà les retours à la ligne.
            lines.extend(src.splitlines(keepends=True))

    # Neutralise les magies.
    lines = _neutralise_magics(lines)

    source = "".join(lines)

    try:
        tree = ast.parse(source, filename=str(nb_path))
    except SyntaxError:
        return [], True
    except Exception:
        return [], True

    visitor = _SymbolVisitor(source, rel_path, depot_name)
    visitor.visit(tree)
    return visitor.symbols, False


def _find_depots(source_dir: Path) -> list[tuple[Path, str]]:
    """Liste les dépôts à indexer sous source_dir."""
    if not source_dir.is_dir():
        return []

    has_git = (source_dir / ".git").exists()
    has_py = any(p.suffix == ".py" for p in source_dir.iterdir())
    if has_git or has_py:
        return [(source_dir, source_dir.name)]

    depots: list[tuple[Path, str]] = []
    for child in sorted(source_dir.iterdir()):
        if child.is_dir() and not _is_excluded_dir(child.name):
            depots.append((child, child.name))
    return depots


def _collect_depot(depot_root: Path, depot_name: str
                   ) -> tuple[list[dict[str, Any]], list[str], int]:
    """Parcourt un dépôt et extrait ses symboles."""
    symbols: list[dict[str, Any]] = []
    unreadable: list[str] = []
    files_read = 0

    for root, dirs, files in os.walk(depot_root):
        dirs[:] = [d for d in dirs if not _is_excluded_dir(d)]

        for name in files:
            if name.endswith(".py"):
                file_path = Path(root) / name
                files_read += 1
                syms, bad = _collect_from_file(file_path, depot_root, depot_name)
                if bad:
                    rel = file_path.relative_to(depot_root).as_posix()
                    unreadable.append(f"{depot_name}/{rel}")
                else:
                    symbols.extend(syms)
            elif name.endswith(".ipynb"):
                nb_path = Path(root) / name
                files_read += 1
                syms, bad = _collect_from_notebook(nb_path, depot_root, depot_name)
                if bad:
                    rel = nb_path.relative_to(depot_root).as_posix()
                    unreadable.append(f"{depot_name}/{rel}")
                else:
                    symbols.extend(syms)

    return symbols, unreadable, files_read


def _load_existing(cible_dir: Path
                 ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Charge l'index et les symboles existants sans les modifier."""
    index_path = cible_dir / "index.tsv"
    symbols_path = cible_dir / "symbols.jsonl"

    existing_index: list[dict[str, Any]] = []
    existing_symbols: list[dict[str, Any]] = []

    if not symbols_path.exists():
        return existing_index, existing_symbols

    try:
        with symbols_path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                existing_symbols.append(json.loads(line))
    except Exception:
        existing_symbols = []

    if index_path.exists():
        try:
            with index_path.open("r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    parts = line.split("\t")
                    if len(parts) >= 5:
                        existing_index.append({
                            "id": parts[0],
                            "offset_octets": int(parts[1]),
                            "longueur_octets": int(parts[2]),
                            "type": parts[3],
                            "resume": parts[4],
                        })
        except Exception:
            existing_index = []

    return existing_index, existing_symbols


def _depot_from_chemin(chemin: str) -> str:
    """Extrait le nom du dépôt du champ 'chemin' (depot/rel/path)."""
    return chemin.split("/")[0] if "/" in chemin else chemin


def _merge_and_write(
    cible_dir: Path,
    new_symbols: list[dict[str, Any]],
    depots_indexed: set[str],
    simulate: bool,
) -> int:
    """Fusionne sans détruire les autres dépôts, réécrit les fichiers."""
    _, existing_symbols = _load_existing(cible_dir)

    kept = [
        s for s in existing_symbols
        if _depot_from_chemin(s.get("chemin", "")) not in depots_indexed
    ]

    final_symbols = kept + new_symbols

    if simulate:
        return len(final_symbols)

    cible_dir.mkdir(parents=True, exist_ok=True)
    symbols_path = cible_dir / "symbols.jsonl"
    index_path = cible_dir / "index.tsv"

    index_rows: list[tuple[str, int, int, str, str]] = []
    with symbols_path.open("wb") as sym_fh:
        offset = 0
        for sym in final_symbols:
            line = json.dumps(sym, ensure_ascii=False, sort_keys=False)
            payload = (line + "\n").encode("utf-8")
            length = len(payload)
            index_rows.append((
                sym["id"],
                offset,
                length,
                sym["type"],
                sym["resume"],
            ))
            sym_fh.write(payload)
            offset += length

    with index_path.open("w", encoding="utf-8") as idx_fh:
        idx_fh.write("id\toffset_octets\tlongueur_octets\ttype\tresume\n")
        for row in index_rows:
            idx_fh.write("\t".join(str(c) for c in row) + "\n")

    return len(final_symbols)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse les arguments en ligne de commande."""
    parser = argparse.ArgumentParser(
        description="Indexe des symboles Python pour le rayon livres/code.",
    )
    parser.add_argument(
        "--source",
        type=Path,
        default=_default_source(),
        help="Racine du dépôt (ou répertoire de dépôts) à indexer.",
    )
    parser.add_argument(
        "--cible",
        type=Path,
        default=_default_cible(),
        help="Répertoire cible du rayon (index.tsv + symbols.jsonl).",
    )
    parser.add_argument(
        "--simuler",
        action="store_true",
        help="Calcule sans écrire les fichiers.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Point d'entrée principal."""
    args = _parse_args(argv)

    source_dir = args.source.resolve()
    cible_dir = args.cible.resolve()

    if not source_dir.is_dir():
        print(f"ERREUR: source introuvable: {source_dir}", file=sys.stderr)
        return 2

    depots = _find_depots(source_dir)
    if not depots:
        print("AUCUN DEPOT TROUVE dans la source.", file=sys.stderr)
        return 1

    all_symbols: list[dict[str, Any]] = []
    all_unreadable: list[str] = []
    total_files = 0
    depots_indexed: set[str] = set()

    for depot_root, depot_name in depots:
        syms, bad, n_files = _collect_depot(depot_root, depot_name)
        all_symbols.extend(syms)
        all_unreadable.extend(bad)
        total_files += n_files
        depots_indexed.add(depot_name)

    total_entries = _merge_and_write(
        cible_dir, all_symbols, depots_indexed, args.simuler
    )

    mode = "SIMULATION" if args.simuler else "ECRITURE"
    print(f"[{mode}] Fichiers lus : {total_files}")
    print(f"[{mode}] Symboles extraits : {len(all_symbols)}")
    print(f"[{mode}] Fichiers illisibles : {len(all_unreadable)}")
    for name in all_unreadable:
        print(f"  - {name}")
    print(f"[{mode}] Total entrées du rayon : {total_entries}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
