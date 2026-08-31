# -*- coding: cp1252 -*-
"""
Garde economique sur la creation de sous-agents et workflows.

Pourquoi ce script existe
-------------------------
Le depot a mesure le 31/08/2026 : 460 sous-agents lances par Workflow en une nuit,
32,1 millions de tokens factures. Le contrat cite 475 000 tokens comme "inverse
du but". Le garde doit donc bloquer toute utilisation non justifiee de modeles
factures, que ce soit via l'outil Agent ou via Workflow.

Ce que la garde protege
-----------------------
* Refus des modeles factures (haiku, sonnet, opus, fable) lorsqu'aucune
  justification n'est fournie.
* Refus du subagent_type='fork' qui herite du modele du parent.
* Analyse des scripts JavaScript de Workflow pour detecter les modeles
  factures.

Ce que la garde ne protege pas
------------------------------
* Les outils autres que Agent ou Workflow.
* Les scripts ne contenant aucune reference a un modele.
* Les cas ou la justification est presente.

Justification acceptee
----------------------
1. Variable d'environnement NEXUS_AGENT_LIBRE=1
2. Presence du texte litteral NEXUS_JUSTIFIE_PAYANT suivi d'un motif sur la
   meme ligne (dans le prompt ou le script).

Le refus est rendu via le protocole des hooks : un JSON sur stdout contenant
hookSpecificOutput.permissionDecision = "deny" et
hookSpecificOutput.permissionDecisionReason = "<message>".
"""

from __future__ import annotations

import json
import os
import re
import sys
from typing import Any, Dict, List, Tuple

# Modeles factures connus. Leur presence doit etre justifiee.
MODELES_FACTURES = {"haiku", "sonnet", "opus", "fable"}

# Types interdits pour Agent.
TYPES_INTERDITS = {"fork"}

# Message d'aide rappelant le banc gratuit.
MESSAGE_BANC_GRATUIT = (
    "Le banc gratuit est disponible via scripts/nexus_agent.py ou les outils "
    "MCP nexus_ask et nexus_summarize, sans cout."
)

def _justification_present(charge: Dict[str, Any], script: str | None = None) -> Tuple[bool, str]:
    """
    Retourne (True, motif) si une justification est detectee.
    La justification peut provenir de :
    * la variable d'environnement NEXUS_AGENT_LIBRE=1
    * la presence du texte NEXUS_JUSTIFIE_PAYANT suivi d'un motif sur la meme ligne
      (dans le script ou dans n'importe quelle chaine du charge).
    """
    if os.environ.get("NEXUS_AGENT_LIBRE") == "1":
        return True, ""

    pattern = re.compile(r"NEXUS_JUSTIFIE_PAYANT\s+(.+)")
    # Recherche dans le script, le cas de Workflow
    if script:
        for line in script.splitlines():
            m = pattern.search(line)
            if m:
                return True, m.group(1).strip()
    # Recherche dans toutes les chaines du charge (prompt, etc.)
    def _search_in_obj(obj: Any) -> Tuple[bool, str]:
        if isinstance(obj, str):
            m = pattern.search(obj)
            if m:
                return True, m.group(1).strip()
        elif isinstance(obj, dict):
            for v in obj.values():
                found, motif = _search_in_obj(v)
                if found:
                    return True, motif
        elif isinstance(obj, list):
            for v in obj:
                found, motif = _search_in_obj(v)
                if found:
                    return True, motif
        return False, ""
    return _search_in_obj(charge)

def _refuse(reason: str) -> int:
    """
    Emet le JSON de refus sur stdout et retourne le code de sortie.
    Aucun accent n'est utilise.
    """
    payload = {
        "hookSpecificOutput": {
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }
    print(json.dumps(payload, ensure_ascii=False))
    # UN REFUS SORT EN 2, JAMAIS EN 0.
    #
    # Le protocole des hooks de ce depot fait du code 2 le refus ; le JSON
    # porte le MOTIF, pas la decision. Le premier jet de ce garde rendait 0
    # apres avoir imprime « deny » : il affichait un refus qui ne bloquait
    # rien -- une fausse garantie, pire que pas de garde du tout.
    #
    # L'erreur venait de mon epreuve, qui avait encode « un garde ne doit
    # jamais planter » en « un garde sort toujours 0 ». PLANTER et REFUSER
    # sont deux choses distinctes : la premiere se rattrape en 0 (le rempart
    # BaseException plus bas), la seconde DOIT etre non nulle. La porte de
    # conformite l'a vu en EXERCANT le garde, la ou une relecture du code ne
    # l'aurait pas vu.
    return 2

def _handle_agent(charge: Dict[str, Any]) -> int:
    """
    Controle specifique a l'outil Agent.
    """
    entree = charge.get("tool_input")
    if not isinstance(entree, dict):
        return 0

    # Refus du type interdits (fork)
    sub_type = entree.get("subagent_type")
    if isinstance(sub_type, str) and sub_type in TYPES_INTERDITS:
        reason = (
            f"Sous-agent refuse : subagent_type='{sub_type}' herite du modele du parent, "
            f"et l'argument model y est ignore. {MESSAGE_BANC_GRATUIT} "
            "Pour autoriser, fournir justification."
        )
        return _refuse(reason)

    # Presence du champ model
    modele = entree.get("model")
    if modele is None:
        reason = (
            "Sous-agent refuse : aucun modele choisi. "
            f"{MESSAGE_BANC_GRATUIT} "
            "Pour autoriser, fournir justification."
        )
        return _refuse(reason)

    # Le modele doit etre une chaine
    if not isinstance(modele, str):
        reason = (
            f"Sous-agent refuse : modele de type {type(modele).__name__} invalide. "
            f"{MESSAGE_BANC_GRATUIT} "
            "Pour autoriser, fournir justification."
        )
        return _refuse(reason)

    # Controle du modele facture
    if modele in MODELES_FACTURES:
        justified, motif = _justification_present(charge)
        if not justified:
            reason = (
                f"Sous-agent refuse : modele facture '{modele}'. "
                f"{MESSAGE_BANC_GRATUIT} "
                "Pour autoriser, definir NEXUS_AGENT_LIBRE=1 ou ajouter "
                "NEXUS_JUSTIFIE_PAYANT <motif> dans le prompt."
            )
            return _refuse(reason)
        # Si justification presente, on peut inclure le motif dans le log (pas obligatoire)
    return 0

def _handle_workflow(charge: Dict[str, Any]) -> int:
    """
    Controle specifique a l'outil Workflow.
    Analyse le champ script du tool_input.
    """
    entree = charge.get("tool_input")
    if not isinstance(entree, dict):
        return 0

    script = entree.get("script")
    if not isinstance(script, str):
        return 0  # Aucun script a analyser -> laisser passer

    # Recherche des model: <nom> dans le script
    pattern = re.compile(r"model\s*:\s*['\"]?(\w+)['\"]?")
    matches = pattern.findall(script)

    # Filtrer les modeles factures
    factures = [m for m in matches if m in MODELES_FACTURES]

    if not factures:
        return 0  # Aucun modele facture trouve -> laisser passer

    justified, motif = _justification_present(charge, script)
    if justified:
        return 0  # Justification presente, on autorise

    # Refus : construire le message avec le nombre d'occurrences et les noms
    nb = len(factures)
    uniques = sorted(set(factures))
    modele_liste = ", ".join(uniques)
    reason = (
        f"Workflow refuse : {nb} occurrence(s) de modele(s) facture(s) [{modele_liste}] detectees. "
        f"{MESSAGE_BANC_GRATUIT} "
        "Pour autoriser, definir NEXUS_AGENT_LIBRE=1 ou ajouter "
        "NEXUS_JUSTIFIE_PAYANT <motif> dans le script."
    )
    return _refuse(reason)

# Les outils que ce garde JUGE -- voir OUTILS_JUGES dans
# nexus_garde_shell.py pour le motif.
OUTILS_JUGES = ("Agent", "Workflow")


def main() -> int:
    """
    Point d'entree du garde.
    Toute anomalie de forme (JSON illisible, champs manquants, etc.) rend 0.
    Le garde ne doit jamais planter.
    """
    try:
        charge = json.load(sys.stdin)
    except Exception:
        return 0

    if not isinstance(charge, dict):
        return 0

    # Si la justification globale est fournie via l'environnement, on laisse passer.
    if os.environ.get("NEXUS_AGENT_LIBRE") == "1":
        return 0

    tool_name = charge.get("tool_name")
    if tool_name == "Agent":
        return _handle_agent(charge)
    if tool_name == "Workflow":
        return _handle_workflow(charge)

    # Tout autre outil : aucune decision, on rend 0.
    return 0

if __name__ == "__main__":
    # LE REMPART NE DOIT PAS AVALER LE REFUS.
    #
    # `sys.exit(2)` leve SystemExit, qui EST une BaseException. Un
    # `except BaseException` place autour rattrapait donc le refus lui-meme
    # et le rendait en 0 : le garde imprimait « deny », sortait 0, et
    # n'empechait rien. Mesure : trois refus sur trois traversaient.
    #
    # C'est le meme defaut qu'un cran plus bas -- « ne jamais planter »
    # ecrasant « refuser » -- et il ne se voit qu'en EXERCANT le garde, car
    # les deux lignes sont justes prises separement.
    #
    # On calcule donc le code AVANT de sortir, et on ne rattrape que ce qui
    # arrive pendant le calcul. La sortie elle-meme est hors du try.
    try:
        code = main()
    except BaseException:
        # Un garde qui plante ne doit jamais arreter le travail qu'il protege.
        code = 0
    sys.exit(code)
