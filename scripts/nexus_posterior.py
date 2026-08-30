#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Agrège les observations en posterior, par couple (modèle, température).

Ce script **mesure et ne décide pas**. Il produit le posterior que le
contrôleur adaptatif lira plus tard ; mélanger les deux rendrait impossible
de savoir si un changement vient du modèle ou de la politique — c'est
exactement la mise en garde du point 9 de
`docs/architecture/Adaptive-Inference-Controller.md`, et elle a déjà été
payée trois fois dans ce dépôt.

Écrit par le banc gratuit sur consigne, intégré après correction d'un défaut
qui aurait ruiné l'agrégation : il convertissait la température en `int`,
or elles valent 0,0 / 0,1 / 0,2 / 0,4. `int(0.4)` vaut zéro, donc tous les
couples se seraient effondrés sur une seule température et le posterior
aurait comparé des choses différentes sous le même nom.

Usage :
    python scripts/nexus_posterior.py
    python scripts/nexus_posterior.py --json
    python scripts/nexus_posterior.py --modele llama3.2-3b-local
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import statistics
import sys

# En deçà, un couple n'a pas assez d'observations pour décider quoi que ce
# soit. Il est rendu quand même — le cacher donnerait à croire qu'il n'existe
# pas — mais marqué « insuffisante », et le contrôleur devra le refuser.
MIN_OBS = 5

DEFAUT = os.path.join(".nexus", "temperature", "observations.jsonl")


def charger(chemin: str) -> tuple[dict, int]:
    """
    Observations groupées par (modèle, température), et lignes ignorées.

    Ne lève jamais : une ligne JSON invalide est comptée et sautée. Un
    fichier absent rend un agrégat vide — c'est le cas normal d'une machine
    qui n'a encore rien observé.
    """
    groupes: dict = collections.defaultdict(list)
    ignorees = 0
    if not os.path.isfile(chemin):
        return groupes, ignorees
    with open(chemin, encoding="utf-8", errors="replace") as fh:
        for ligne in fh:
            ligne = ligne.strip()
            if not ligne:
                continue
            try:
                obs = json.loads(ligne)
                modele = obs.get("model")
                temp = obs.get("temperature")
                if modele is None or temp is None:
                    raise ValueError("champs manquants")
                # float et non int : les températures valent 0,1 / 0,2 / 0,4,
                # et un int les écraserait toutes sur zéro.
                groupes[(str(modele), float(temp))].append(obs)
            except Exception:
                ignorees += 1
    return groupes, ignorees


def agreger(observations: list) -> dict:
    """
    Statistiques d'un couple. Médianes, jamais moyennes.

    Un seul appel lent fausse une moyenne sur quelques points ; la médiane
    y résiste. C'est la même raison qui a fait choisir la médiane dans
    `mesurer_binaire`.
    """
    n = len(observations)
    # Les débits nuls sont ÉCARTÉS, non comptés comme zéro : une génération
    # sans sortie ne dit rien du débit, et la compter tirerait la médiane
    # vers le bas en donnant à croire que le modèle est lent.
    debits = [o["debit_jps"] for o in observations
              if o.get("debit_jps")]
    durees = [o["duree_ms"] for o in observations if o.get("duree_ms") is not None]
    tronquees = sum(1 for o in observations if o.get("tronquee") is True)
    replis = sum(1 for o in observations if str(o.get("repli", "0")) != "0")
    return {
        "n": n,
        # None et non 0.0 quand rien n'a été mesuré : zéro est une valeur,
        # l'absence de mesure n'en est pas une.
        "debit_median": round(statistics.median(debits), 2) if debits else None,
        "duree_median": int(statistics.median(durees)) if durees else None,
        "taux_tronque": round(tronquees / n, 3) if n else None,
        "taux_repli": round(replis / n, 3) if n else None,
        "confiance": "mesuree" if n >= MIN_OBS else "insuffisante",
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--observations", default=DEFAUT)
    p.add_argument("--json", action="store_true")
    p.add_argument("--modele", action="append", default=[])
    a = p.parse_args()

    groupes, ignorees = charger(a.observations)
    if a.modele:
        voulus = set(a.modele)
        groupes = {k: v for k, v in groupes.items() if k[0] in voulus}

    lignes = []
    total = 0
    for (modele, temp), obs in sorted(groupes.items()):
        stats = agreger(obs)
        total += stats["n"]
        lignes.append(dict(model=modele, temperature=temp, **stats))

    if a.json:
        print(json.dumps({"agregats": lignes, "total": total,
                          "lignes_ignorees": ignorees},
                         ensure_ascii=False, indent=2))
        return 0

    if not lignes:
        print("Aucune observation. Le magasin se remplit a chaque appel du")
        print("serveur MCP : %s" % a.observations)
        return 0

    print("%-26s %5s %5s %10s %10s %8s %8s  %s"
          % ("modele", "T", "n", "debit j/s", "duree ms", "tronq", "repli",
             "confiance"))
    print("-" * 96)
    for l in lignes:
        print("%-26s %5s %5d %10s %10s %8s %8s  %s"
              % (l["model"], l["temperature"], l["n"],
                 l["debit_median"] if l["debit_median"] is not None else "-",
                 l["duree_median"] if l["duree_median"] is not None else "-",
                 l["taux_tronque"], l["taux_repli"], l["confiance"]))
    print("-" * 96)
    print("%d observation(s) sur %d couple(s), %d ligne(s) ignoree(s)"
          % (total, len(lignes), ignorees))
    mesurees = sum(1 for l in lignes if l["confiance"] == "mesuree")
    print("%d couple(s) au-dela de %d observations : les seuls sur lesquels"
          % (mesurees, MIN_OBS))
    print("un controleur pourrait decider.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
