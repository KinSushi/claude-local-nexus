"""nexus_garde_production.py
Ce garde pretooluse refuse l'ecriture directe de code source en production.
Il protege le depot contre la production et la validation simultane du
code par l'orchestrateur. Il ne bloque pas les autres types de fichiers
(Markdown, donnees, etc.) et ne s'applique qu'aux outils Edit, Write et
NotebookEdit.

Si le chemin fourni a une extension code (.py, .js, .mjs, .cjs, .ts,
.ps1), n'est pas situe dans un repertoire temporaire et que la variable
d'environnement NEXUS_PRODUCTION_LIBRE n'est pas a '1', le garde renvoie
un refus avec la raison et la voie de contournement declaree.

Tout autre cas, ainsi que toute anomalie de forme, laisse passer
silencieusement (aucun JSON sur stdout). Les anomalies sont signalees
sur stderr afin de ne pas etre confondues avec une approbation.
"""

import sys
import os
import json

TEMP_SUBSTRINGS = ("scratchpad", "temp", "tmp", "AppData")
CODE_EXTENSIONS = {".py", ".js", ".mjs", ".cjs", ".ts", ".ps1"}
TARGET_TOOLS = {"Edit", "Write", "NotebookEdit"}


def _is_temp_path(path: str) -> bool:
    """Retourne True si le chemin contient un des substrings temporaires."""
    lower = path.lower()
    return any(sub in lower for sub in TEMP_SUBSTRINGS)


def refuse(chemin: str) -> bool:
    """
    Determine si le garde doit refuser le fichier.
    Retourne True si toutes les conditions de refus sont remplies.
    """
    if not chemin:
        return False
    ext = os.path.splitext(chemin)[1].lower()
    if ext not in CODE_EXTENSIONS:
        return False
    if _is_temp_path(chemin):
        return False
    if os.environ.get("NEXUS_PRODUCTION_LIBRE") == "1":
        return False
    return True


def _handle_tool(charge: dict) -> int:
    """Traite l'appel pour les outils cible."""
    tool_input = charge.get("tool_input", {})
    if not isinstance(tool_input, dict):
        sys.stderr.write("Anomalie: tool_input absent ou non dict\n")
        return 0

    chemin = tool_input.get("file_path") or tool_input.get("notebook_path")
    if not isinstance(chemin, str):
        sys.stderr.write("Anomalie: chemin absent ou non string\n")
        return 0

    if refuse(chemin):
        raison = (
            f"Le chemin '{chemin}' est refuse car il s'agit d'un fichier code source en production. "
            "Regle: tu ne produis pas, tu orchestres et tu audites.\n"
            "Faire produire le patch avec scripts/nexus_agent.py --tache <tache> --fichiers <fichiers>\n"
            "Appliquer le patch avec scripts/nexus_appliquer.py\n"
            "Si la production directe est vraiment voulue, definir NEXUS_PRODUCTION_LIBRE=1 avant l'appel."
        )
        sortie = {
            "hookSpecificOutput": {
                "permissionDecision": "deny",
                "permissionDecisionReason": raison,
            }
        }
        print(json.dumps(sortie, ensure_ascii=False))
        return 0

    # Aucun refus, laisser passer silencieusement.
    return 0


def main() -> int:
    """
    Point d'entree du garde.
    Toute anomalie de forme (JSON illisible, champs manquants, etc.) rend 0.
    Le garde ne doit jamais planter.
    """
    try:
        charge = json.load(sys.stdin)
    except Exception:
        sys.stderr.write("Anomalie: JSON illisible sur stdin\n")
        return 0

    if not isinstance(charge, dict):
        sys.stderr.write("Anomalie: charge JSON n'est pas un dict\n")
        return 0

    # Si la justification globale est fournie via l'environnement, on laisse passer.
    if os.environ.get("NEXUS_PRODUCTION_LIBRE") == "1":
        return 0

    tool_name = charge.get("tool_name")
    if tool_name in TARGET_TOOLS:
        return _handle_tool(charge)

    # Tout autre outil : aucune decision, on rend 0.
    return 0


if __name__ == "__main__":
    sys.exit(main())