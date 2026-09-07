#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
nexus_chemins.py

Outil portable et professionnel pour détecter les références mortes à des
scripts « nexus » dans un dépôt contenant les répertoires `scripts/` et
`outillage/`.  Fonctionne avec la bibliothèque standard uniquement (Python 3.8).

Fonctionnalités principales :
* Recherche de références du type `scripts/nexus_*.py` ou `outillage\nexus_*.py`
  dans les fichiers *.py, *.ps1, *.md (exclusion des chemins contenant « QUARANTAINE »).
* Détection des chemins morts et proposition d’une correction lorsqu’un fichier
  du même nom existe dans l’autre répertoire.
* Option `--corriger` qui réécrit les références mortes sur place.
* Mode `--epreuve` qui crée un dépôt factice dans un répertoire temporaire et
  vérifie les trois scénarios requis (FORWARD, REVERSE, CORRECTION).

Aucun effet de bord à l’import : tout le code s’exécute uniquement depuis
`if __name__ == "__main__":`.
"""

import argparse
import pathlib
import re
import sys
import tempfile
from typing import List, Tuple, Optional, Dict

# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def find_repo_root(start: pathlib.Path, forced: Optional[pathlib.Path] = None) -> Optional[pathlib.Path]:
    """
    Recherche le répertoire racine du dépôt contenant à la fois `scripts/` et
    `outillage/`.  Si `forced` est fourni, il est retourné directement (après
    validation minimale).
    """
    if forced:
        if (forced / "scripts").is_dir() and (forced / "outillage").is_dir():
            return forced.resolve()
        return None

    cur = start.resolve()
    while cur != cur.parent:
        scripts_dir = cur / "scripts"
        outillage_dir = cur / "outillage"
        if scripts_dir.is_dir() and outillage_dir.is_dir():
            return cur
        cur = cur.parent
    return None


def iter_source_files(root: pathlib.Path) -> List[pathlib.Path]:
    """
    Retourne la liste des fichiers à analyser sous `scripts/` et `outillage/`,
    en excluant tout chemin contenant la chaîne « QUARANTAINE ».
    """
    # Chemin absolu du script lui‑même, afin de l’exclure du scan
    self_path = pathlib.Path(__file__).resolve()
    patterns = ["*.py", "*.ps1", "*.md"]
    files: List[pathlib.Path] = []
    for sub in ("scripts", "outillage"):
        base = root / sub
        for pat in patterns:
            for p in base.rglob(pat):
                if "QUARANTAINE" in str(p):
                    continue
                # Exclure le fichier de l’outil lui‑même
                if p.resolve() == self_path:
                    continue
                files.append(p)
    return files


_REF_REGEX = re.compile(
    r"""(?P<prefix>scripts|outillage)          # répertoire source
        (?P<sep>[\\/])                         # séparateur slash ou antislash
        nexus_(?P<name>[A-Za-z0-9_]+)\.py      # nom du script
    """,
    re.VERBOSE,
)


def analyse_file(file_path: pathlib.Path, repo_root: pathlib.Path) -> List[Dict]:
    """
    Analyse un fichier et renvoie la liste des références mortes détectées.
    Chaque dictionnaire contient :
        - line: numéro de ligne (1‑based)
        - dead_path: chemin tel qu’il apparaît dans le code (string)
        - suggestion: chemin de remplacement éventuel (string ou None)
        - match_span: tuple(start, end) de la correspondance dans le texte
    """
    results: List[Dict] = []
    try:
        text = file_path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return results  # on ignore les fichiers illisibles

    for m in _REF_REGEX.finditer(text):
        # Utilisation d’indices de groupe pour éviter les incompatibilités de noms
        prefix = m.group(1)          # groupe 1 : scripts|outillage
        sep = m.group(2)             # groupe 2 : séparateur / ou \
        name = m.group(3)            # groupe 3 : nom du script
        dead_rel = f"{prefix}{sep}nexus_{name}.py"
        target_dir = repo_root / prefix
        target_path = target_dir / f"nexus_{name}.py"

        if target_path.is_file():
            continue  # référence valide

        # référence morte : chercher dans l’autre répertoire
        other_prefix = "outillage" if prefix == "scripts" else "scripts"
        other_path = repo_root / other_prefix / f"nexus_{name}.py"
        suggestion = None
        if other_path.is_file():
            suggestion = f"{other_prefix}{sep}nexus_{name}.py"

        # déterminer le numéro de ligne
        line_no = text.count("\n", 0, m.start()) + 1

        results.append({
            "line": line_no,
            "dead_path": dead_rel,
            "suggestion": suggestion,
            "match_span": m.span(),
        })
    return results


def replace_dead_references(
    file_path: pathlib.Path,
    dead_refs: List[Dict],
) -> Tuple[bool, List[Tuple[int, str, str]]]:
    """
    Réécrit le fichier en remplaçant les références mortes pour lesquelles une
    suggestion unique existe.  Retourne (modifié, changements) où `changements`
    est une liste de tuples (line, ancien, nouveau).
    """
    try:
        original = file_path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return False, []

    # On travaille sur une copie mutable du texte
    new_text = original
    offset = 0
    changements: List[Tuple[int, str, str]] = []

    for ref in dead_refs:
        if not ref["suggestion"]:
            continue
        start, end = ref["match_span"]
        start += offset
        end += offset
        ancien = new_text[start:end]
        nouveau = ref["suggestion"]
        new_text = new_text[:start] + nouveau + new_text[end:]
        offset += len(nouveau) - (end - start)
        changements.append((ref["line"], ancien, nouveau))

    if changements:
        file_path.write_text(new_text, encoding="utf-8")
        return True, changements
    return False, []


def report_dead_refs(dead_refs_by_file: Dict[pathlib.Path, List[Dict]]) -> int:
    """
    Affiche les références mortes, séparées en deux catégories :
      • « REFERENCES MORTES CORRIGEABLES (deplacements) » : références mortes
        pour lesquelles une suggestion existe (c’est‑à‑dire qu’un fichier du même
        nom se trouve dans l’autre répertoire).  Ces références sont bloquantes.
      • « SANS CANDIDAT (a verifier a la main, non bloquant) » : références mortes
        sans aucune suggestion possible.
    Retourne le code de sortie : 1 s’il existe au moins une référence
    CORRIGEABLE, 0 sinon.
    """
    corrigeables: List[Tuple[pathlib.Path, Dict]] = []
    sans_candidat: List[Tuple[pathlib.Path, Dict]] = []

    # Classer chaque référence
    for file_path, refs in dead_refs_by_file.items():
        for ref in refs:
            if ref["suggestion"]:
                corrigeables.append((file_path, ref))
            else:
                sans_candidat.append((file_path, ref))

    # Affichage des corrigeables
    if corrigeables:
        print("REFERENCES MORTES CORRIGEABLES (deplacements) :")
        for file_path, ref in corrigeables:
            line = ref["line"]
            dead = ref["dead_path"]
            sugg = ref["suggestion"]
            print(f"{file_path}:{line}  {dead}  -> {sugg}")

    # Affichage des références sans candidat
    if sans_candidat:
        print("SANS CANDIDAT (a verifier a la main, non bloquant) :")
        for file_path, ref in sans_candidat:
            line = ref["line"]
            dead = ref["dead_path"]
            print(f"{file_path}:{line}  {dead}")

    # Code de sortie : non‑nul uniquement s’il y a au moins une corrigeable
    return 1 if corrigeables else 0


# --------------------------------------------------------------------------- #
# Core logic
# --------------------------------------------------------------------------- #

def process_repository(root: pathlib.Path, corriger: bool) -> int:
    """
    Parcourt le dépôt, détecte les références mortes, les affiche et, si
    `corriger` est True, les répare sur place.
    Retourne le code de sortie approprié.
    """
    files = iter_source_files(root)
    dead_by_file: Dict[pathlib.Path, List[Dict]] = {}

    for f in files:
        refs = analyse_file(f, root)
        if refs:
            dead_by_file[f] = refs

    exit_code = report_dead_refs(dead_by_file)

    if corriger and dead_by_file:
        for f, refs in dead_by_file.items():
            changed, changements = replace_dead_references(f, refs)
            if changed:
                for line, old, new in changements:
                    print(f"Modifié {f}:{line}  {old} -> {new}")

    return exit_code


# --------------------------------------------------------------------------- #
# Test mode (--epreuve)
# --------------------------------------------------------------------------- #

def _create_file(path: pathlib.Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _run_detection(root: pathlib.Path) -> Tuple[int, Dict[pathlib.Path, List[Dict]]]:
    files = iter_source_files(root)
    dead_by_file: Dict[pathlib.Path, List[Dict]] = {}
    for f in files:
        refs = analyse_file(f, root)
        if refs:
            dead_by_file[f] = refs
    code = 0 if not dead_by_file else 1
    return code, dead_by_file


def _run_correction(root: pathlib.Path) -> None:
    files = iter_source_files(root)
    for f in files:
        refs = analyse_file(f, root)
        if refs:
            replace_dead_references(f, refs)


def epreuve_mode() -> int:
    """
    Exécute les trois scénarios de test dans un dépôt temporaire.
    Retourne 0 si tout passe, 1 sinon.
    """
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = pathlib.Path(tmpdir)

            # ── Structure de base ────────────────────────────────────────
            scripts_dir = repo / "scripts"
            outillage_dir = repo / "outillage"

            # Fichiers valides (présents dans les deux répertoires, sauf le fichier cible du scénario REVERSE)
            for name in [
                "nexus_conformite.py",
                "nexus_rituel.py",
                "nexus_valide.py",
            ]:
                _create_file(scripts_dir / name, f"# {name} dans scripts\n")
                if name != "nexus_conformite.py":
                    _create_file(outillage_dir / name, f"# {name} dans outillage\n")

            # ── Scénario FORWARD (référence valide) ───────────────────────
            forward_file = scripts_dir / "forward.py"
            _create_file(
                forward_file,
                "path = 'scripts/nexus_conformite.py'\n"
            )
            code_fwd, dead_fwd = _run_detection(repo)
            if code_fwd != 0 or dead_fwd:
                print("Échec du scénario FORWARD")
                return 1

            # ── Scénario REVERSE (référence morte) ────────────────────────
            reverse_file = scripts_dir / "reverse.py"
            _create_file(
                reverse_file,
                "path = 'outillage/nexus_conformite.py'\n"
            )
            code_rev, dead_rev = _run_detection(repo)
            if code_rev == 0 or not dead_rev:
                print("Échec du scénario REVERSE (détection manquante)")
                return 1

            # Vérifier que la suggestion pointe vers le bon fichier
            expected_suggestion = "scripts/nexus_conformite.py"
            found = False
            for refs in dead_rev.values():
                for r in refs:
                    if r["suggestion"] == expected_suggestion:
                        found = True
            if not found:
                print("Échec du scénario REVERSE (suggestion incorrecte)")
                return 1

            # ── Scénario CORRECTION ───────────────────────────────────────
            _run_correction(repo)
            code_corr, dead_corr = _run_detection(repo)
            if code_corr != 0 or dead_corr:
                print("Échec du scénario CORRECTION (références restantes)")
                return 1

        # Tous les scénarios ont réussi
        return 0
    except Exception:
        import traceback
        traceback.print_exc()
        return 1


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Détecte et corrige les références mortes aux scripts nexus."
    )
    parser.add_argument(
        "--racine",
        type=pathlib.Path,
        help="Chemin explicite vers la racine du dépôt (contient scripts/ et outillage/).",
    )
    parser.add_argument(
        "--corriger",
        action="store_true",
        help="Réécrit les références mortes avec la suggestion unique lorsqu’elle existe.",
    )
    parser.add_argument(
        "--epreuve",
        action="store_true",
        help="Exécute les tests d’épreuve en mode autonome.",
    )

    args = parser.parse_args()

    if args.epreuve:
        sys.exit(epreuve_mode())

    # Détermination de la racine du dépôt
    start_path = pathlib.Path(__file__).parent
    repo_root = find_repo_root(start_path, forced=args.racine)

    if repo_root is None:
        print("Racine du dépôt introuvable (absence conjointe de scripts/ et outillage/).")
        sys.exit(0)

    exit_code = process_repository(repo_root, corriger=args.corriger)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()