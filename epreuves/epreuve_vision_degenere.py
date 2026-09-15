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
        ("prefixe_puis_boucle", json.dumps("La prose française, avec ses nuances et ses subtilités, offre un terrain fertile pour l'analyse des répétitions textuelles. En effet, un texte dégénéré se caractérise souvent par des motifs répétitifs qui, lorsqu'ils dépassent un certain seuil, trahissent une absence de variété sémantique ou syntaxique. Ce phénomène peut être observé dans divers contextes, allant des discours politiques aux textes publicitaires, en passant par les contenus générés automatiquement. L'étude de ces répétitions permet non seulement de détecter des anomalies, mais aussi de comprendre les mécanismes sous-jacents à la production de textes. Cependant, il est crucial de distinguer les répétitions intentionnelles, qui peuvent servir un but stylistique ou rhétorique, des répétitions involontaires, souvent symptomatiques d'une dégénérescence textuelle. Dans cette optique, l'analyse doit prendre en compte la longueur des motifs, leur fréquence, ainsi que leur distribution au sein du texte." + "1. " * 80), True),
        ("prose_variee_longue", json.dumps("L'histoire des civilisations est marquée par des périodes de transformation profonde, où les structures sociales, politiques et culturelles évoluent sous l'effet de forces internes et externes. Ces mutations, souvent lentes et imperceptibles à l'échelle d'une génération, finissent par redéfinir les contours d'une société. Par exemple, la Renaissance en Europe a vu émerger une nouvelle vision de l'homme et du monde, fondée sur la redécouverte des textes antiques et l'essor des sciences. De même, la révolution industrielle a bouleversé les modes de production et les rapports sociaux, entraînant des changements radicaux dans les villes et les campagnes. Ces transitions ne sont jamais linéaires : elles sont jalonnées de résistances, de conflits et d'adaptations qui en complexifient la compréhension. Ainsi, étudier ces périodes de transition permet de saisir la dynamique des sociétés humaines, tout en soulignant l'importance des contextes historiques et géographiques dans leur évolution. Les outils d'analyse contemporains, qu'ils soient quantitatifs ou qualitatifs, offrent des perspectives nouvelles pour appréhender ces phénomènes, mais ils doivent être utilisés avec rigueur pour éviter les généralisations hâtives ou les interprétations anachroniques."), False),
        ("fin_huit_tirets", json.dumps("Lorem ipsum dolor sit amet, consectetur adipiscing elit. Lorem ipsum dolor sit amet, consectetur adipiscing elit. Lorem ipsum dolor sit amet, consectetur adipiscing elit. Lorem ipsum dolor sit amet, consectetur adipiscing elit. Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do eiusmod tempor.--------"), False),
        ("motif_51_repete", json.dumps("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxy" * 10), False),
        ("motif_3_couvre_240", json.dumps("Lorem ipsum dolor sit amet, consectetur adipiscing elit. Lorem ipsum dolor sit amet, consectetur adipiscing elit. Lorem ipsum dolor sit amet, consectetur adipiscing elit. Lorem ipsum dolor sit amet, consectetur adipiscing elit. Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do eiusmod tempor." + "ab " * 80), True),
        ("empty_string", json.dumps(""), False),
        ("null_input", "null", False),
    ]

    lines = [func_src, "\n"]
    for name, arg_js, expected in cases:
        lines.append(
            f"{{"
            f"let __res = texteDegenere({arg_js});"
            f"console.log(JSON.stringify({{name: '{name}', result: !!__res, expected: {str(expected).lower()}}}));"
            f"}}"
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
        stderr_normalized = " ".join(proc.stderr[:300].split())
        ok &= _print_result("node retour non‑zéro", False, f"code={proc.returncode} stderr={stderr_normalized}")
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
