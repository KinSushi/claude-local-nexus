# -*- coding: utf-8 -*-
"""
Sonde du serveur MCP nexus-local : exerce les outils de bout en bout.

Sert à vérifier le montage C (réduction de contexte en local) sur des
fichiers réels : indexation, puis recherche hybride, puis synthèse.

Usage :
    python scripts/nexus_mcp_probe.py index <racine>
    python scripts/nexus_mcp_probe.py search "<question>"
    python scripts/nexus_mcp_probe.py summarize <fichier> [<fichier> ...]
    python scripts/nexus_mcp_probe.py ask "<prompt>" [<modele>]
    python scripts/nexus_mcp_probe.py route "<prompt>" [local|cloud|all]
    python scripts/nexus_mcp_probe.py context "<instruction>" <modele> <fenetre> <fichier...>
    python scripts/nexus_mcp_probe.py vision <image> ["<question>"] [<modele>]
    python scripts/nexus_mcp_probe.py models
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
    messages = "\n".join([
        json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                    "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                               "clientInfo": {"name": "probe", "version": "1"}}}),
        json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/call",
                    "params": {"name": name, "arguments": arguments}}),
    ]) + "\n"
    result = subprocess.run(["node", SERVER], input=messages,
                            capture_output=True, text=True,
                            encoding="utf-8", errors="replace", timeout=timeout)
    for line in result.stdout.splitlines():
        if not line.strip().startswith("{"):
            continue
        message = json.loads(line)
        if message.get("id") == 2:
            payload = message.get("result", {})
            flag = " [ERREUR]" if payload.get("isError") else ""
            return flag + "\n" + payload.get("content", [{}])[0].get("text", "")
    return "aucune reponse\n" + result.stderr[-800:]


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    action = sys.argv[1]
    if action == "index":
        root = sys.argv[2] if len(sys.argv) > 2 else "."
        print(call_tool("nexus_index_build", {"root": root}))
    elif action == "search":
        print(call_tool("nexus_search", {"query": sys.argv[2],
                                         "k": int(sys.argv[3]) if len(sys.argv) > 3 else 5}))
    elif action == "summarize":
        print(call_tool("nexus_summarize", {"paths": sys.argv[2:]}))
    elif action == "context":
        # context <instruction> <modele> <fenetre> <fichier...>
        args = {"instruction": sys.argv[2], "model": sys.argv[3],
                "context_tokens": int(sys.argv[4]), "paths": sys.argv[5:]}
        print(call_tool("nexus_context", args))
    elif action == "vision":
        args = {"path": sys.argv[2]}
        if len(sys.argv) > 3:
            args["prompt"] = sys.argv[3]
        if len(sys.argv) > 4:
            args["model"] = sys.argv[4]
        print(call_tool("nexus_vision", args))
    elif action == "models":
        print(call_tool("nexus_models", {}))
    elif action == "ask":
        args = {"prompt": sys.argv[2]}
        if len(sys.argv) > 3:
            args["model"] = sys.argv[3]
        print(call_tool("nexus_ask", args))
    elif action == "route":
        args = {"prompt": sys.argv[2]}
        if len(sys.argv) > 3:
            args["plane"] = sys.argv[3]
        print(call_tool("nexus_route", args))
    else:
        print(__doc__)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
