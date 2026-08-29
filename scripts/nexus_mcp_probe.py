# -*- coding: utf-8 -*-
"""
Sonde du serveur MCP nexus-local : exerce les outils de bout en bout.

Cette sonde doit rester robuste même lorsque l'environnement est défectueux.
Elle attrape les erreurs liées à l'exécution du serveur Node et renvoie un
code de sortie explicite afin que les scripts d'automatisation puissent
distinguuer :

* « le pont a répondu une erreur »  → le serveur a renvoyé un payload
  avec isError = true.
* « le pont n'a pas répondu »       → le serveur n'a pas pu être lancé
  (exécutable absent, délai expiré, autre exception).

Le code minimise les changements : il ne touche que la fonction
`call_tool` et la logique de retour de `main`.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SERVER = os.path.join(ROOT, "tools", "nexus-mcp", "server.js")

# La console Windows reste en cp1252 : une reponse de modele contient
# souvent des caracteres qu'elle ne sait pas encoder (espace fine, tirets
# longs, symboles). Sans cela, une reponse correcte se perdrait sur une
# exception d'affichage.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def call_tool(name: str, arguments: dict, timeout: int = 3600) -> str:
    """
    Appelle le serveur Node via le protocole JSON‑RPC.

    En cas d'échec du sous‑processus, la fonction renvoie un message
    diagnostique sans accents, préfixé par ``ERROR:`` et contenant le chemin
    du serveur. Les trois cas distincts sont :

    * executable introuvable (FileNotFoundError)
    * délai d'attente dépassé (subprocess.TimeoutExpired)
    * toute autre exception inattendue

    Le format de la réponse serveur (payload) est conservé : si le serveur
    indique une erreur, le texte retourné commence par `` [ERREUR]``.
    """
    messages = "\n".join([
        json.dumps({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "probe", "version": "1"},
            },
        }),
        json.dumps({
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        }),
    ]) + "\n"

    try:
        result = subprocess.run(
            ["node", SERVER],
            input=messages,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
    except FileNotFoundError:
        # node n'est pas dans le PATH
        return f"ERROR: node executable not found (SERVER={SERVER})"
    except subprocess.TimeoutExpired:
        # le serveur n'a pas répondu à temps
        return f"ERROR: timeout expired after {timeout}s (SERVER={SERVER})"
    except Exception as e:  # pragma: no cover
        # toute autre erreur inattendue
        return f"ERROR: unexpected error {e} (SERVER={SERVER})"

    # Analyse de la sortie du serveur
    for line in result.stdout.splitlines():
        if not line.strip().startswith("{"):
            continue
        message = json.loads(line)
        if message.get("id") == 2:
            payload = message.get("result", {})
            flag = " [ERREUR]" if payload.get("isError") else ""
            # Le texte retourné peut être vide ou ne contenir que des espaces.
            # Une réponse vide signifie qu'aucune mesure n'a pu être obtenue ;
            # la considérer comme un succès masquerait un problème de collecte
            # de données et ferait croire à l'appelant que le pont fonctionne.
            # On renvoie donc un message explicite sans accents afin que
            # _probe_success le traite comme une erreur.
            content = payload.get("content", [{}])[0].get("text", "")
            if not flag and not content.strip():
                return "NO CONTENT: nothing could be measured"
            return flag + "\n" + content
    # Aucun message JSON valide reçu
    return "aucune reponse\n" + result.stderr[-800:]


def _probe_success(output: str) -> bool:
    """
    Détermine si la sonde a réussi.

    - Un préfixe ``ERROR:`` indique un problème d'environnement.
    - Le texte ``aucune reponse`` indique que le serveur n'a pas renvoyé de
      réponse exploitable.
    - La présence du flag `` [ERREUR]`` indique que le serveur a renvoyé une
      erreur de logique.

    Dans tous les cas ci‑dessus, la fonction renvoie ``False``.
    """
    # Une sortie vide ou faite d'espaces n'est pas une reponse : c'est une
    # absence de mesure. La compter comme un succes ferait conclure a un pont
    # fonctionnel alors que rien n'a ete mesure -- exactement le defaut que
    # cet outil de diagnostic existe pour aider a trouver ailleurs.
    if not output or not output.strip():
        return False
    # `call_tool` produit ce temoin quand le serveur repond sans contenu.
    # Sans cette ligne, les deux fonctions du meme fichier ne s'accordaient
    # pas, et le temoin passait pour une reponse valide.
    if output.startswith("NO CONTENT:"):
        return False
    if output.startswith("ERROR:"):
        return False
    if output.startswith("aucune reponse"):
        return False
    if " [ERREUR]" in output:
        return False
    return True


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 1

    action = sys.argv[1]
    exit_code = 1  # défaut : échec

    if action == "index":
        root = sys.argv[2] if len(sys.argv) > 2 else "."
        out = call_tool("nexus_index_build", {"root": root})
        print(out)
        exit_code = 0 if _probe_success(out) else 1
    elif action == "search":
        out = call_tool(
            "nexus_search",
            {
                "query": sys.argv[2],
                "k": int(sys.argv[3]) if len(sys.argv) > 3 else 5,
            },
        )
        print(out)
        exit_code = 0 if _probe_success(out) else 1
    elif action == "summarize":
        out = call_tool("nexus_summarize", {"paths": sys.argv[2:]})
        print(out)
        exit_code = 0 if _probe_success(out) else 1
    elif action == "context":
        # context <instruction> <modele> <fenetre> <fichier...>
        args = {
            "instruction": sys.argv[2],
            "model": sys.argv[3],
            "context_tokens": int(sys.argv[4]),
            "paths": sys.argv[5:],
        }
        out = call_tool("nexus_context", args)
        print(out)
        exit_code = 0 if _probe_success(out) else 1
    elif action == "vision":
        args = {"path": sys.argv[2]}
        if len(sys.argv) > 3:
            args["prompt"] = sys.argv[3]
        if len(sys.argv) > 4:
            args["model"] = sys.argv[4]
        out = call_tool("nexus_vision", args)
        print(out)
        exit_code = 0 if _probe_success(out) else 1
    elif action == "models":
        out = call_tool("nexus_models", {})
        print(out)
        exit_code = 0 if _probe_success(out) else 1
    elif action == "ask":
        args = {"prompt": sys.argv[2]}
        if len(sys.argv) > 3:
            args["model"] = sys.argv[3]
        out = call_tool("nexus_ask", args)
        print(out)
        exit_code = 0 if _probe_success(out) else 1
    elif action == "route":
        args = {"prompt": sys.argv[2]}
        if len(sys.argv) > 3:
            args["plane"] = sys.argv[3]
        out = call_tool("nexus_route", args)
        print(out)
        exit_code = 0 if _probe_success(out) else 1
    else:
        print(__doc__)
        return 1

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
