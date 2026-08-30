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

Ce que la garde protege, et ce qu'elle ne protege pas
-----------------------------------------------------
Elle ne refuse pas la puissance. Une premiere version n'autorisait que le
modele le moins cher, et cette rigidite a coute plus qu'elle n'economisait :
des validations bacles ont produit deux faux negatifs et un rapport aux
mesures inventees, donc du travail a refaire. Econome ne veut pas dire bas de
gamme.

Ce qu'elle refuse, c'est la depense NON DECIDEE. Le defaut constate n'a jamais
ete « quelqu'un a choisi un modele puissant » ; il etait « personne n'a
choisi », et le sous-agent heritait alors du modele du parent -- le plus cher
-- sans que rien ne le signale.

L'ordre des ressorts, que le message de refus rappelle
------------------------------------------------------
Le plan payant est l'ULTIME ressort. Avant de lancer un sous-agent Claude, la
question est d'abord : le banc gratuit peut-il faire ce travail directement,
par `scripts/nexus_agent.py` ? Un sous-agent ne se justifie que lorsqu'il faut
une boucle d'outils, du jugement, ou une validation independante -- et il
choisit alors son modele selon la tache, explicitement.

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

# Modeles connus. Y figurer ne vaut pas recommandation : c'est la preuve
# qu'un choix a ete pose. Une faute de frappe ne doit pas passer pour une
# decision, d'ou le refus de tout nom absent de cet ensemble.
MODELES_CONNUS = {"haiku", "sonnet", "opus", "fable"}

# Un fork herite du contexte ET du modele du parent : l'argument `model` y est
# ignore par la plateforme. Le laisser passer en le croyant bride serait une
# garantie fausse, plus nuisible qu'une absence de garantie.
TYPES_INTERDITS = {"fork"}

# Rappele a chaque refus. Le reflexe a installer n'est pas « prendre le moins
# cher » mais « le payant est l'ultime ressort ».
RAPPEL = (
    "",
    "Avant tout sous-agent : le banc gratuit peut-il faire ce travail seul ?",
    "",
    "  VALIDER un correctif ne demande AUCUN agent :",
    "      python scripts/nexus_valide.py --base main",
    "  batterie mecanique, recherche de regressions, jugement par le banc",
    "  gratuit, verdict et code de sortie. Cout facture : zero.",
    "",
    "    python scripts/nexus_agent.py --tache \"...\" --fichiers f1 f2 \\",
    "        --modele gpt-oss-120b-cloud --max-tokens 2000",
    "Un sous-agent ne se justifie que s'il faut une boucle d'outils, du",
    "jugement, ou une validation independante. Le payant est l'ultime ressort.",
    "",
    "Choisir alors selon la tache, explicitement :",
    "    haiku   coquille d'orchestration, taches mecaniques, verification",
    "    sonnet  jugement, arbitrage, audit exigeant",
    "    opus    seulement la ou sonnet a reellement echoue",
    "",
    "Derogation : poser NEXUS_AGENT_LIBRE=1 dans l'environnement.",
)


def bloquer(*lignes: str) -> int:
    for ligne in tuple(lignes) + RAPPEL:
        print(ligne, file=sys.stderr)
    return 2


def main() -> int:
    try:
        charge = json.load(sys.stdin)
    except Exception:
        # JSON illisible → aucune décision, on rend 0
        return 0

    # La charge doit être un dictionnaire ; sinon on ne peut pas interpréter les champs.
    if not isinstance(charge, dict):
        return 0

    if os.environ.get("NEXUS_AGENT_LIBRE") == "1":
        return 0
    if charge.get("tool_name") != "Agent":
        return 0

    entree = charge.get("tool_input")
    if not isinstance(entree, dict):
        return 0

    genre = entree.get("subagent_type")
    # Si le type n'est pas une chaîne, on ne peut pas le comparer correctement → aucune décision.
    if not isinstance(genre, str):
        return 0
    if genre in TYPES_INTERDITS:
        return bloquer(
            "Sous-agent refuse : subagent_type='%s' herite du modele du parent," % genre,
            "et l'argument model y est ignore. L'annoncer bride serait une",
            "garantie fausse, plus nuisible qu'aucune garantie.")

    modele = entree.get("model")
    # Le champ model doit être présent ; son absence indique une dépense non décidée.
    if modele is None:
        return bloquer(
            "Sous-agent refuse : aucun modele choisi.",
            "Un model absent fait HERITER celui du parent, donc le plus cher,",
            "et rien ne le signale. C'est la depense non decidee, pas la",
            "depense elevee, que cette garde refuse.")
    # Le champ model doit être une chaîne pour pouvoir le valider.
    if not isinstance(modele, str):
        return 0
    if modele not in MODELES_CONNUS:
        return bloquer(
            "Sous-agent refuse : model=%r inconnu." % modele,
            "Valeurs connues : %s." % ", ".join(sorted(MODELES_CONNUS)),
            "Une faute de frappe ne doit pas passer pour un choix.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
