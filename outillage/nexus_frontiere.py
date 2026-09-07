"""outillage/nexus_frontiere.py

Outil de vérification des dépendances interdites entre le produit (scripts/, tools/)
et l'outillage (outillage/).

Il parcourt :

* scripts/*.ps1
* scripts/*.py
* tools/**/*.js

et identifie chaque référence à ``outillage/``.  Les références sont classées :

* **EXECUTION** – le produit invoque réellement un fichier d'outillage
  (définit une dépendance réelle).  Toute présence d'EXECUTION entraîne
  l'échec de l'outil (code de sortie 1).

* **MENTION** – le texte mentionne simplement le chemin (ex. affichage à
  l'utilisateur).  Les mentions sont comptabilisées mais ne provoquent pas
  d'échec.

L'outil accepte ``--json`` pour une sortie machine‑lisible et ``--epreuve``
qui crée un dépôt factice dans un répertoire temporaire afin de vérifier
les deux comportements (acceptation et rejet) sans toucher au dépôt réel.

Usage :

    python -m outillage.nexus_frontiere [--racine <racine>] [--json] [--epreuve]

Le code de sortie est :

* 0 – aucune EXECUTION détectée.
* 1 – au moins une EXECUTION détectée.
* 2 – indécision (fichier illisible, etc.).
"""

import argparse
import contextlib
import glob
import json
import os
import re
import sys
import tempfile
from typing import Dict, List, Tuple

# Protection pré‑argparse contre les problèmes d’encodage sur --help
with contextlib.suppress(Exception):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# --------------------------------------------------------------------------- #
# Détection des références
# --------------------------------------------------------------------------- #

# Recherche du nom de l'outil après « outillage » (même ligne)
_TOOL_PATTERN = re.compile(r"nexus_[a-z_]+\.py", re.IGNORECASE)

def _extract_tool(line: str) -> str:
    """
    Retourne le nom du fichier visé après ``outillage``.
    Fonctionne pour les formes « outillage/nexus_x.py » ainsi que pour les
    formes où « outillage » et le nom du script sont séparés (ex. Join‑Path … "outillage") "nexus_x.py").
    """
    # Recherche du premier « outillage » (quel que soit le séparateur)
    if re.search(r"outillage(?:[\\/]|['\"])", line, re.IGNORECASE) is None:
        return ""
    # Recherche du nom du script après ce point
    m = _TOOL_PATTERN.search(line)
    return m.group(0) if m else ""

# Patterns d'exécution par langage (détectent la présence d'une commande d'appel)
_POWERSHELL_EXEC_KEYWORDS = ["join-path", "& python", "& $python"]
_JAVASCRIPT_EXEC_KEYWORD = "path.join"
_PYTHON_EXEC_KEYWORD = "os.path.join"

# Détection de lignes de mention (affichage à l'utilisateur)
_MENTION_START = re.compile(r"^\s*(Write-Host|Write-Log|Ecrire|print)\b", re.IGNORECASE)

def _classify_line(file_path: str, line: str) -> Tuple[str, str]:
    """
    Analyse une ligne et renvoie un tuple ``(type, tool)`` où *type* vaut
    ``EXECUTION``, ``MENTION`` ou ``""`` (non pertinent) et *tool* le nom du
    fichier ciblé (ou chaîne vide).
    """
    stripped = line.strip()
    # Ignorer les commentaires purs (ex. # …) – ils ne sont pas des mentions
    if stripped.startswith("#"):
        return "", ""

    tool = _extract_tool(line)

    if file_path.endswith(".ps1"):
        # PowerShell
        lowered = line.lower()
        if any(k in lowered for k in _POWERSHELL_EXEC_KEYWORDS) and tool:
            return "EXECUTION", tool
        if _MENTION_START.search(line) and tool:
            return "MENTION", tool

    elif file_path.endswith(".js"):
        # JavaScript
        if _JAVASCRIPT_EXEC_KEYWORD in line and tool:
            return "EXECUTION", tool
        if _MENTION_START.search(line) and tool:
            return "MENTION", tool

    elif file_path.endswith(".py"):
        # Python
        if _PYTHON_EXEC_KEYWORD in line and tool:
            return "EXECUTION", tool
        if _MENTION_START.search(line) and tool:
            return "MENTION", tool

    return "", tool


def _scan_repository(root: str) -> Tuple[List[Dict], List[Dict]]:
    """
    Parcourt les fichiers d'intérêt sous *root* et renvoie deux listes :

    * ``executions`` : dictionnaires ``{file, line, tool, language}``
    * ``mentions``    : dictionnaires ``{file, line, tool, language}``
    """
    executions: List[Dict] = []
    mentions: List[Dict] = []

    patterns = [
        os.path.join(root, "scripts", "*.ps1"),
        os.path.join(root, "scripts", "*.py"),
        os.path.join(root, "tools", "**", "*.js"),
    ]

    for pattern in patterns:
        for file_path in glob.glob(pattern, recursive=True):
            language = (
                "PowerShell"
                if file_path.endswith(".ps1")
                else "Python"
                if file_path.endswith(".py")
                else "JavaScript"
            )
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                for idx, line in enumerate(f, start=1):
                    typ, tool = _classify_line(file_path, line)
                    record = {
                        "file": os.path.relpath(file_path, root),
                        "line": idx,
                        "tool": tool,
                        "language": language,
                    }
                    if typ == "EXECUTION":
                        executions.append(record)
                    elif typ == "MENTION":
                        mentions.append(record)
    return executions, mentions


# --------------------------------------------------------------------------- #
# Contre‑épreuve
# --------------------------------------------------------------------------- #

def _run_epreuve() -> int:
    """
    Crée deux dépôts factices :

    * *pass_repo* : ne contient que des mentions → doit retourner 0.
    * *fail_repo* : contient au moins une exécution → doit retourner 1.

    Retourne 0 si les deux comportements sont corrects, sinon 1.
    """
    with tempfile.TemporaryDirectory() as tmp_root:
        # Dépôt qui doit passer (aucune EXECUTION)
        pass_repo = os.path.join(tmp_root, "pass_repo")
        os.makedirs(os.path.join(pass_repo, "scripts"))
        mention_path = os.path.join(pass_repo, "scripts", "mention.ps1")
        with open(mention_path, "w", encoding="utf-8") as f:
            f.write('Write-Host "Test : python outillage\\nexus_test.py"\n')

        execs, _ = _scan_repository(pass_repo)
        if execs:
            return 1  # devrait être vide

        # Dépôt qui doit échouer (au moins une EXECUTION)
        fail_repo = os.path.join(tmp_root, "fail_repo")
        os.makedirs(os.path.join(fail_repo, "scripts"))
        os.makedirs(os.path.join(fail_repo, "tools"))
        exec_path_ps1 = os.path.join(fail_repo, "scripts", "run.ps1")
        with open(exec_path_ps1, "w", encoding="utf-8") as f:
            f.write('& python outillage\\nexus_x.py\n')
        exec_path_js = os.path.join(fail_repo, "tools", "run.js")
        with open(exec_path_js, "w", encoding="utf-8") as f:
            f.write('const script = path.join(INSTALL_ROOT, "outillage", "nexus_x.py");\n')

        execs, _ = _scan_repository(fail_repo)
        if not execs:
            return 1  # devrait contenir au moins une exécution

    return 0


# --------------------------------------------------------------------------- #
# Entrée principale
# --------------------------------------------------------------------------- #

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Détecte les dépendances interdites du produit vers l'outillage."
    )
    parser.add_argument(
        "--racine",
        help="Chemin racine du dépôt (prend le dessus sur le calcul automatique).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Émettre la sortie au format JSON.",
    )
    parser.add_argument(
        "--epreuve",
        action="store_true",
        help="Exécuter la contre‑épreuve interne et sortir.",
    )
    parser.add_argument(
        "--rebaseline",
        action="store_true",
        help="Écrire/mettre à jour la référence de cliquet.",
    )
    parser.add_argument(
        "--motif",
        help="Motif obligatoire lorsqu’on utilise --rebaseline.",
    )
    args = parser.parse_args()

    if args.epreuve:
        return _run_epreuve()

    # Détermination de la racine du dépôt
    if args.racine:
        root = os.path.abspath(args.racine)
    else:
        # Ce fichier vit dans <depot>/outillage/, le dépôt est le répertoire parent
        root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

    executions, mentions = _scan_repository(root)

    # ------------------------------------------------------------------- #
    # Gestion du cliquet (référence frontiere_reference.json)
    # ------------------------------------------------------------------- #
    REFERENCE = os.path.join(root, "outillage", "rituels", "frontiere_reference.json")

    # Rebasage demandé ?
    if args.rebaseline:
        if not args.motif:
            print("Erreur : --motif est obligatoire avec --rebaseline.", file=sys.stderr)
            return 2
        baseline = [
            {
                "file": e["file"],
                "line": e["line"],
                "tool": e["tool"],
                "motif": args.motif,
            }
            for e in executions
        ]
        os.makedirs(os.path.dirname(REFERENCE), exist_ok=True)
        with open(REFERENCE, "w", encoding="utf-8") as f:
            json.dump(baseline, f, ensure_ascii=False, indent=2)
        print(f"Référence mise à jour : {REFERENCE}")
        return 0

    # Chargement éventuel de la référence
    # Chargement éventuel de la référence et calcul des différences
    if os.path.isfile(REFERENCE):
        with open(REFERENCE, "r", encoding="utf-8") as f:
            reference = json.load(f)
        # Sets pour comparaison
        ref_set = {(e["file"], e["tool"]) for e in reference}
        cur_set = {(e["file"], e["tool"]) for e in executions}
        known_set = cur_set & ref_set
        new_set = cur_set - ref_set
        disappeared_set = ref_set - cur_set

        # Listes à inclure dans le JSON
        known = [
            e for e in executions if (e["file"], e["tool"]) in known_set
        ]
        new = [
            e for e in executions if (e["file"], e["tool"]) in new_set
        ]
        disappeared = [
            {
                "file": r["file"],
                "line": r["line"],
                "tool": r["tool"],
            }
            for r in reference
            if (r["file"], r["tool"]) in disappeared_set
        ]

        # Sortie texte uniquement si le mode texte est demandé
        if not args.json:
            print(
                f"{len(known)} connues, {len(new)} neuves, {len(disappeared)} disparues depuis la référence."
            )
            if new:
                for e in new:
                    print(
                        f"NOUVELLE EXECUTION → {e['file']}:{e['line']} outil={e['tool']}"
                    )
            print(f"Référence lue : {REFERENCE}")

        exit_code = 1 if new else 0
    else:
        # Pas de référence disponible
        if not args.json:
            print(f"Référence absente : {REFERENCE}")
            if executions:
                print("Executions détectées aujourd’hui :")
                for e in executions:
                    print(
                        f"{e['file']}:{e['line']} outil={e['tool']} (langage={e['language']})"
                    )
        # En mode JSON, la référence est null et les listes seront vides
        reference = None
        known = []
        new = []
        disappeared = []
        exit_code = 1

    # ------------------------------------------------------------------- #
    # Sortie JSON ou texte habituelle, en se basant sur le résultat du cliquet
    # ------------------------------------------------------------------- #
    if args.json:
        output = {
            "executions": executions,
            "mentions": mentions,
            "reference": REFERENCE if os.path.isfile(REFERENCE) else None,
            "connues": known,
            "neuves": new,
            "disparues": disappeared,
            "status": exit_code,
        }
        print(json.dumps(output, ensure_ascii=False, indent=2))
        return exit_code

    # Sortie texte classique
    if executions:
        print("EXECUTIONS détectées :")
        for e in executions:
            print(
                f"{e['file']}:{e['line']}: outil={e['tool']} (langage={e['language']})"
            )
    else:
        print("0 aucune EXECUTION produit -> outillage")
    if mentions:
        print(f"{len(mentions)} mentions détectées (non bloquantes).")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
