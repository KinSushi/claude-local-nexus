# -*- coding: utf-8 -*-
"""Épreuve fonctionnelle pour la fonction ``texteDegenere`` du fichier
``tools/nexus-mcp/server.js``.

L’épreuve :

* lit le fichier ``server.js`` à partir de la racine du dépôt,
* extrait le texte source de la fonction ``texteDegenere`` (du mot‑clé
  ``function texteDegenere(`` jusqu’à l’accolade fermante qui équilibre la
  première accolade ouvrante),
* construit un petit script JavaScript contenant uniquement cette fonction
  et les appels de test,
* l’exécute avec ``node -e``,
* vérifie que chaque appel renvoie la valeur attendue,
* s’assure que le script transmis à ``node`` ne contient aucun ``require(``
  (fuite : aucune dépendance serveur ne doit être chargée).

Le protocole de sortie suit le format attendu par le lanceur de la suite :
une ligne par cas, commençant exactement par ``[OK  ]`` ou ``[RATE]``.
Le code de sortie du processus est 0 si tous les cas sont OK, 1 sinon.

Aucun effet de bord n’est produit : aucune connexion réseau, aucun port
ouvert, aucun ``require`` du module serveur.

"""

import pathlib
import sys
import json
import shutil
import subprocess
import re

def _print_result(name: str, condition: bool, detail: str = "") -> bool:
    """Affiche le résultat d’un cas de test et renvoie le booléen."""
    if condition:
        print(f"[OK  ] {name} : {detail}")
    else:
        print(f"[RATE] {name} : {detail}")
    return condition

def _find_texte_degenere(root: pathlib.Path) -> str | None:
    """Retourne le texte source complet de ``function texteDegenere`` ou ``None``."""
    server_js = root / "tools" / "nexus-mcp" / "server.js"
    if not server_js.is_file():
        return None

    content = server_js.read_text(encoding="utf-8")

    # Recherche du début de la fonction
    match = re.search(r"\bfunction\s+texteDegenere\s*\(", content)
    if not match:
        return None

    start = match.start()
    # Position de la première accolade ouvrante après le signature
    brace_open = content.find("{", match.end())
    if brace_open == -1:
        return None

    # Parcours pour trouver l’accolade fermante équilibrante
    depth = 0
    pos = brace_open
    while pos < len(content):
        if content[pos] == "{":
            depth += 1
        elif content[pos] == "}":
            depth -= 1
            if depth == 0:
                # Inclure l’accolade fermante
                return content[start:pos + 1]
        pos += 1
    return None  # déséquilibre d’accolades

def _build_node_script(func_src: str) -> str:
    """Construit le script JavaScript à passer à ``node -e``."""
    # Génération des cas de test
    forward_str = ("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$") * 12  # 40 car × 12 = 480
    reverse_str = "".join(chr((i % 94) + 33) for i in range(600))  # 600 caractères différents
    threshold_str = "a" * 150  # 150 caractères répétitifs

    cases = [
        ("forward_long_repeat", json.dumps(forward_str), True),
        ("reverse_long_varied", json.dumps(reverse_str), False),
        ("threshold_150_repeat", json.dumps(threshold_str), False),
        ("empty_string", json.dumps(""), False),
        ("null_input", "null", False),
    ]

    lines = [func_src, "\n"]
    for name, arg_js, expected in cases:
        lines.append(
            f"let __res = texteDegenere({arg_js});"
            f"console.log(JSON.stringify({{name: '{name}', result: !!__res, expected: {str(expected).lower()}}}));"
        )
    return "\n".join(lines)

def main() -> int:
    ok = True
    repo_root = pathlib.Path(__file__).resolve().parents[1]

    # 1️⃣ Vérification de la présence de ``node``
    if shutil.which("node") is None:
        ok &= _print_result("node introuvable", False, "exécutable ``node`` non trouvé")
        return 1

    # 2️⃣ Extraction de la fonction
    func_src = _find_texte_degenere(repo_root)
    if func_src is None:
        ok &= _print_result("texteDegenere absente", False, "fonction non trouvée dans server.js")
        return 1

    # 3️⃣ Construction du script à exécuter
    node_script = _build_node_script(func_src)

    # 4️⃣ Vérification de la fuite (aucun ``require(`` dans le script)
    if "require(" in node_script:
        ok &= _print_result("fuite require détectée", False, "le script contient un require")
        return 1

    # 5️⃣ Exécution via ``node -e``
    try:
        proc = subprocess.run(
            ["node", "-e", node_script],
            capture_output=True,
            text=True,
            check=False,
        )
    except Exception as exc:  # pragma: no cover – improbable en environnement normal
        ok &= _print_result("execution node échouée", False, str(exc))
        return 1

    if proc.returncode != 0:
        ok &= _print_result("node retour non‑zéro", False, f"code={proc.returncode}")
        return 1

    # 6️⃣ Analyse des résultats
    for line in proc.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            data = json.loads(line)
            name = data.get("name")
            result = bool(data.get("result"))
            expected = bool(data.get("expected"))
            detail = f"obtenu={result}"
            ok &= _print_result(name, result == expected, detail)
        except Exception as exc:  # pragma: no cover
            ok &= _print_result("parsing json échoué", False, str(exc))
            ok = False

    return 0 if ok else 1

if __name__ == "__main__":
    sys.exit(main())
