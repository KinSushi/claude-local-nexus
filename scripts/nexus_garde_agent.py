# -*- coding: utf-8 -*-
"""
Garde economique sur la creation de sous-agents.

Pourquoi ce script existe
-------------------------
Un sous-agent Claude coute deux fois : son propre raisonnement, facture au
token, et ce qu'il delegue, gratuit. Seule la seconde moitie sert le but du
depot. Mesure faite le 29 aout 2026 : 475 000 tokens payants avaient servi a
piloter 126 000 tokens gratuits -- exactement l'inverse de ce que la
plateforme existe pour demontrer.

La cause n'etait pas l'oubli d'appeler le banc gratuit, mais la coquille
d'orchestration : un sous-agent lance sans `model` HERITE du modele du
parent, donc du plus cher, et rien ne le signale. Une regle qui repose sur la
vigilance se perd a la premiere session un peu chargee ; celle-ci est donc
appliquee par un hook `PreToolUse`, au moment meme de la depense.

Contrat du hook
---------------
Entree : un objet JSON sur stdin.
Sortie : code 2 et un message sur stderr pour bloquer, code 0 sinon.

Toute anomalie -- JSON illisible, champ absent, autre outil -- rend 0. Une
garde qui plante ne doit jamais empecher de travailler : elle cesse alors de
garantir quoi que ce soit, ce qui est moins grave que de bloquer le depot.
"""
from __future__ import annotations

import json
import os
import sys

# Seul modele autorise pour un sous-agent. La liste est volontairement d'un
# seul element : chaque ajout doit etre une decision, pas une derive.
MODELES_AUTORISES = {"haiku"}

# Un fork herite du contexte ET du modele du parent : l'argument `model` y est
# ignore par la plateforme. Le laisser passer en le croyant bride serait une
# garantie fausse, plus nuisible qu'une absence de garantie.
TYPES_INTERDITS = {"fork"}


def bloquer(*lignes: str) -> int:
    for ligne in lignes:
        print(ligne, file=sys.stderr)
    return 2


def main() -> int:
    try:
        charge = json.load(sys.stdin)
    except Exception:
        return 0

    if os.environ.get("NEXUS_AGENT_LIBRE") == "1":
        return 0
    if charge.get("tool_name") != "Agent":
        return 0

    entree = charge.get("tool_input")
    if not isinstance(entree, dict):
        return 0

    genre = entree.get("subagent_type")
    if genre in TYPES_INTERDITS:
        return bloquer(
            "Sous-agent refuse : subagent_type='%s' herite du modele du parent," % genre,
            "et l'argument model y est ignore. Le lancer reviendrait a payer le",
            "modele le plus cher en croyant l'avoir bride.",
            "",
            "Employer un agent ordinaire avec model='haiku', ou poser",
            "NEXUS_AGENT_LIBRE=1 si le contexte du parent est reellement requis.")

    modele = entree.get("model")
    if modele not in MODELES_AUTORISES:
        return bloquer(
            "Sous-agent refuse : model=%s." % ("absent" if modele is None else repr(modele)),
            "Un model absent fait HERITER celui du parent, donc le plus cher.",
            "Un sous-agent n'a pas a raisonner cher : son role est d'appeler le",
            "banc gratuit (scripts/nexus_agent.py) et de verifier.",
            "",
            "Correction : ajouter model=\"haiku\" a l'appel Agent.",
            "Derogation : poser NEXUS_AGENT_LIBRE=1 dans l'environnement.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
