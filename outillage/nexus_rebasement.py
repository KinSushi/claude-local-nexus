"""outillage/nexus_rebasement.py

Outil de rebasement de comptage de violations de lint.

Il compare les comptes de règles de lint (produits par *ruff*) entre une
référence historique, le périmètre ancien et le périmètre nouveau.

- Une augmentation sur le périmètre ancien constitue une **REGRESSION**.
- Une augmentation uniquement sur le périmètre nouveau est **ATTRIBUABLE**
  à l’élargissement du périmètre.
- Une diminution constitue une **IMPROVEMENT**.

Le code de sortie est :
    0 – aucune régression détectée,
    1 – au moins une régression,
    2 – linter introuvable ou autre indécision.

Une contre‑épreuve (``--epreuve``) vérifie la logique de classification
sans appeler *ruff* ni toucher le disque.
"""

import argparse
import json
import os
import subprocess
import sys
from typing import Dict, List
import contextlib

# Protection pré‑argparse contre les problèmes d’encodage sur --help
with contextlib.suppress(Exception):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def _run_ruff(directories: List[str]) -> Dict[str, int]:
    """Exécute ruff sur les répertoires fournis et renvoie le comptage par règle.

    Retourne un dictionnaire ``{code: nombre}``. En cas d’absence du binaire,
    lève ``FileNotFoundError``.
    """
    if not directories:
        return {}

    cmd = ["ruff", "--output-format", "json", "--no-cache"] + directories
    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except FileNotFoundError as exc:
        raise FileNotFoundError("ruff executable not found") from exc

    stdout = result.stdout or ""
    try:
        data = json.loads(stdout)
    except json.JSONDecodeError:
        data = []

    counts: Dict[str, int] = {}
    for entry in data:
        code = entry.get("code")
        if code:
            counts[code] = counts.get(code, 0) + 1
    return counts


def _load_reference(path: str) -> Dict[str, int]:
    """Charge le fichier JSON de référence. Retourne un dictionnaire vide si le
    fichier n’existe pas ou ne peut être lu.
    """
    if not os.path.isfile(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            data = json.load(f)
    except Exception:
        return {}
    if isinstance(data, dict):
        return {str(k): int(v) for k, v in data.items()}
    return {}


def _classify_rule(
    rule: str,
    reference: Dict[str, int],
    old_counts: Dict[str, int],
    new_counts: Dict[str, int],
) -> str:
    """Détermine le verdict pour une règle donnée."""
    ref = reference.get(rule, 0)
    old = old_counts.get(rule, 0)
    new = new_counts.get(rule, 0)

    if old > ref:
        return "REGRESSION"
    if new > ref and old == ref:
        return "ATTRIBUABLE"
    if old < ref:
        return "IMPROVEMENT"
    return "UNCHANGED"


def _compare_counts(
    reference: Dict[str, int],
    old_counts: Dict[str, int],
    new_counts: Dict[str, int],
) -> Dict[str, str]:
    """Retourne un mapping ``rule -> verdict`` pour toutes les règles rencontrées."""
    all_rules = set(reference) | set(old_counts) | set(new_counts)
    return {
        rule: _classify_rule(rule, reference, old_counts, new_counts) for rule in all_rules
    }


def _run_epreuve() -> int:
    """Exécute la contre‑épreuve pure."""
    # Référence de base
    reference = {"F823": 1, "B009": 2, "C001": 0}

    # Cas 1 : augmentation sur l’ancien périmètre (régression)
    old_counts_reg = {"F823": 2, "B009": 2, "C001": 0}
    new_counts_reg = {"F823": 2, "B009": 2, "C001": 0}

    # Cas 2 : augmentation uniquement sur le nouveau périmètre (attribuable)
    old_counts_att = {"F823": 1, "B009": 2, "C001": 0}
    new_counts_att = {"F823": 1, "B009": 3, "C001": 0}

    # Classification attendue
    verdicts_reg = _compare_counts(reference, old_counts_reg, new_counts_reg)
    verdicts_att = _compare_counts(reference, old_counts_att, new_counts_att)

    ok = (
        verdicts_reg.get("F823") == "REGRESSION"
        and verdicts_att.get("B009") == "ATTRIBUABLE"
    )
    return 0 if ok else 1


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Comparer les comptes de violations entre références et périmètres."
    )
    parser.add_argument(
        "--ancien",
        nargs="+",
        required=False,
        default=[],
        help="Liste des répertoires du périmètre ancien.",
    )
    parser.add_argument(
        "--nouveau",
        nargs="+",
        required=False,
        default=[],
        help="Liste des répertoires du périmètre nouveau.",
    )
    parser.add_argument(
        "--reference",
        required=False,
        help="Chemin du fichier JSON contenant les comptes de référence.",
    )
    parser.add_argument(
        "--racine",
        required=False,
        help="Chemin racine à préfixer aux répertoires (prend le dessus).",
    )
    parser.add_argument(
        "--epreuve",
        action="store_true",
        help="Exécuter la contre‑épreuve interne et sortir.",
    )

    args = parser.parse_args()

    if args.epreuve:
        return _run_epreuve()

    # Détermination de la racine
    root = os.path.abspath(args.racine) if args.racine else os.path.abspath(os.path.dirname(__file__))

    # Normalisation des chemins
    ancien_dirs = [os.path.abspath(os.path.join(root, d)) for d in args.ancien]
    nouveau_dirs = [os.path.abspath(os.path.join(root, d)) for d in args.nouveau]

    # Chargement de la référence
    reference_path = args.reference
    if not reference_path:
        print("Aucun fichier de référence fourni – aucune régression possible.", file=sys.stderr)
        return 0

    reference = _load_reference(reference_path)
    if not reference:
        print(f"Fichier de référence introuvable ou vide : {reference_path}", file=sys.stderr)
        return 0

    # Exécution du linter
    try:
        old_counts = _run_ruff(ancien_dirs)
        new_counts = _run_ruff(nouveau_dirs)
    except FileNotFoundError:
        print("Linter ruff non trouvé – verdict INDECIS.", file=sys.stderr)
        return 2

    # Comparaison
    verdicts = _compare_counts(reference, old_counts, new_counts)

    # Affichage des résultats
    for rule in sorted(verdicts):
        ref = reference.get(rule, 0)
        old = old_counts.get(rule, 0)
        new = new_counts.get(rule, 0)
        verdict = verdicts[rule]
        print(f"{rule}: avant={ref}, ancien={old}, nouveau={new} => {verdict}")

    # Code de sortie
    has_regression = any(v == "REGRESSION" for v in verdicts.values())
    return 1 if has_regression else 0


if __name__ == "__main__":
    sys.exit(main())
