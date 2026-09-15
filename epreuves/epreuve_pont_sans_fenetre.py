#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Épreuve « pont sans fenêtre ».
Analyse statique d’un fichier JavaScript (par défaut : tools/nexus-mcp/server.js)
pour vérifier que chaque appel à :
    spawn, spawnSync, execFile, execFileSync, fork
respecte les exigences suivantes :

* l’option `windowsHide: true` doit être présente,
* l’option `detached: true` **ne doit pas** être présente,
* le mot `inherit` ne doit pas apparaître dans les options.

Un appel est considéré en défaut si :
(a) il ne contient pas `windowsHide: true`,
(b) il contient `detached: true`,
(c) il contient le mot `inherit`.

Le script produit une ligne `[OK  ]` ou `[RATE]` pour chaque appel,
avec le numéro de ligne où l’appel commence et une description du défaut.
S’il n’y a aucun appel, un `[RATE]` est émis.

Avant l’analyse du fichier fourni, le même contrôle est appliqué à quatre
fragments de code (auto‑contrôle).  Tout écart produit un `[RATE] auto‑controle`.

Le script se termine avec le code 0 si aucune ligne `[RATE]` n’a été émise,
sinon avec le code 1.

Usage :
    python epreuves/epreuve_pont_sans_fenetre.py [--fichier CHEMIN]

"""

import argparse
import pathlib
import re
import sys

# ----------------------------------------------------------------------
# Fonctions utilitaires
# ----------------------------------------------------------------------


def _replace_with_spaces(text: str, start: int, end: int) -> None:
    """Remplace le segment text[start:end] par des espaces (conserve la longueur)."""
    length = end - start
    return " " * length


def clean_js(source: str) -> str:
    """
    Retourne une version du code JavaScript où les commentaires et les littéraux
    (', ", `) sont remplacés par des espaces afin de préserver les positions
    (et donc les numéros de ligne).
    """
    i = 0
    n = len(source)
    out = []
    while i < n:
        ch = source[i]
        # Commentaire ligne //
        if ch == "/" and i + 1 < n and source[i + 1] == "/":
            # jusqu’à la fin de ligne
            end = source.find("\n", i + 2)
            if end == -1:
                end = n
            out.append(_replace_with_spaces(source, i, end))
            i = end
            continue
        # Commentaire bloc /* … */
        if ch == "/" and i + 1 < n and source[i + 1] == "*":
            end = source.find("*/", i + 2)
            if end == -1:
                end = n
            else:
                end += 2
            out.append(_replace_with_spaces(source, i, end))
            i = end
            continue
        # Littéral simple, double ou back‑tick
        if ch in ("'", '"', "`"):
            quote = ch
            j = i + 1
            escaped = False
            while j < n:
                c = source[j]
                if escaped:
                    escaped = False
                elif c == "\\":
                    escaped = True
                elif c == quote:
                    break
                elif quote == "`" and c == "$" and j + 1 < n and source[j + 1] == "{":
                    # saut du ${ … } dans les template literals
                    j += 2
                    brace_depth = 1
                    while j < n and brace_depth:
                        if source[j] == "\\":
                            j += 2
                            continue
                        if source[j] == "{":
                            brace_depth += 1
                        elif source[j] == "}":
                            brace_depth -= 1
                        j += 1
                    continue
                j += 1
            # j pointe sur le guillemet de fermeture ou n‑1 si non trouvé
            end = j + 1 if j < n else n
            out.append(_replace_with_spaces(source, i, end))
            i = end
            continue
        # Caractère normal
        out.append(ch)
        i += 1
    return "".join(out)


def find_calls(cleaned: str, original: str):
    """
    Recherche les appels aux fonctions ciblées dans le texte nettoyé.
    Retourne un générateur de tuples (lineno, call_text).
    """
    pattern = re.compile(r"\b(spawn|spawnSync|execFile|execFileSync|fork)\s*\(", re.MULTILINE)
    for m in pattern.finditer(cleaned):
        start = m.start()
        # calcul du numéro de ligne dans le fichier original
        lineno = original[:start].count("\n") + 1

        # extraction du texte complet de l’appel (jusqu’à la parenthèse fermante appariée)
        depth = 0
        i = start
        n = len(cleaned)
        while i < n:
            if cleaned[i] == "(":
                depth += 1
            elif cleaned[i] == ")":
                depth -= 1
                if depth == 0:
                    i += 1
                    break
            i += 1
        call_text = original[start:i]  # on garde le texte original (avec espaces, commentaires, etc.)
        yield lineno, call_text


def analyse_call(call_text: str):
    """
    Analyse le texte d’un appel et renvoie (is_ok, raisons).
    is_ok : bool – True si aucune des conditions de défaut n’est remplie.
    raisons : list de chaînes décrivant les défauts détectés.
    """
    reasons = []
    # Normalisation (supprimer espaces)
    txt = call_text

    # Recherche de windowsHide:true
    has_windows_hide = re.search(r"windowsHide\s*:\s*true", txt) is not None
    # Recherche de detached:true
    has_detached = re.search(r"detached\s*:\s*true", txt) is not None
    # Recherche du mot inherit (en dehors d’une chaîne – déjà éliminé)
    has_inherit = re.search(r"\binherit\b", txt) is not None

    if not has_windows_hide:
        reasons.append("absence de windowsHide:true")
    if has_detached:
        reasons.append("detached:true présent")
    if has_inherit:
        reasons.append("mot inherit présent")

    is_ok = not reasons
    return is_ok, reasons


def auto_control():
    """
    Exécute le même contrôle sur les quatre fragments décrits dans l’énoncé.
    Retourne True si le résultat correspond aux attentes, False sinon.
    """
    fragments = [
        # 1. sans windowsHide → défaut
        ("spawn('cmd', [], {});", True),
        # 2. avec detached:true → défaut
        ("spawn('cmd', [], { detached: true });", True),
        # 3. avec inherit → défaut
        ("spawn('cmd', [], { stdio: 'inherit' });", True),
        # 4. correct → aucun défaut
        ("spawn('cmd', [], { windowsHide: true, stdio: 'ignore' });", False),
    ]

    ok = True
    for code, expect_defect in fragments:
        cleaned = clean_js(code)
        calls = list(find_calls(cleaned, code))
        if len(calls) != 1:
            ok = False
            break
        _, call_txt = calls[0]
        is_ok, _ = analyse_call(call_txt)
        defect = not is_ok
        if defect != expect_defect:
            ok = False
            break
    return ok


def main():
    parser = argparse.ArgumentParser(description="Épreuve pont sans fenêtre")
    parser.add_argument(
        "--fichier",
        help="Chemin du fichier server.js à analyser",
        default=None,
    )
    args = parser.parse_args()

    # Détermination du chemin du fichier à analyser
    if args.fichier:
        target_path = pathlib.Path(args.fichier).resolve()
    else:
        # chemin par défaut relatif à la racine du dépôt (deux niveaux au-dessus de ce script)
        repo_root = pathlib.Path(__file__).resolve().parents[1]
        target_path = repo_root / "tools" / "nexus-mcp" / "server.js"

    if not target_path.is_file():
        print(f"[RATE] fichier introuvable : {target_path}", file=sys.stderr)
        sys.exit(1)

    # Lecture du fichier
    try:
        source = target_path.read_text(encoding="utf-8")
    except Exception as exc:
        print(f"[RATE] lecture du fichier échouée : {exc}", file=sys.stderr)
        sys.exit(1)

    # Auto‑contrôle
    if not auto_control():
        print("[RATE] auto-controle")
        sys.exit(1)

    # Nettoyage du code
    cleaned = clean_js(source)

    # Recherche des appels
    any_call = False
    any_rate = False
    for lineno, call_txt in find_calls(cleaned, source):
        any_call = True
        is_ok, reasons = analyse_call(call_txt)
        if is_ok:
            print(f"[OK  ] ligne {lineno} : OK")
        else:
            any_rate = True
            detail = "; ".join(reasons)
            print(f"[RATE] ligne {lineno} : {detail}")

    if not any_call:
        any_rate = True
        print("[RATE] aucun appel trouvé")

    sys.exit(0 if not any_rate else 1)


if __name__ == "__main__":
    main()
