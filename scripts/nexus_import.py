#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Chaque script s'importe-t-il, et son import fait-il quelque chose ?

POURQUOI
--------
Un module cassé ne se voit qu'à l'exécution du chemin qui l'emploie. Mesuré
ici le 2026-08-30 : `nexus_ruche.py` employait `nexus_agent.racine_travail()`
sans jamais importer le module. Toute exécution sans `--racine` levait
`NameError`, et personne ne l'avait vu — jusqu'à ce que la suite complète
soit jouée pour la première fois de la journée.

DEUX DÉFAUTS, ET LE SECOND EST LE PIRE
--------------------------------------
Un import qui **échoue** est un défaut certain. Un import qui **agit** est
plus grave : il transforme le simple fait de charger un module en action, si
bien qu'un outil qui inspecte le dépôt le modifie en l'inspectant.

Ce n'est pas théorique. Le premier jet de `nexus_verbatim.py` appelait
`os.makedirs()` au niveau du module : l'importer créait un répertoire, et un
échec de création faisait lever l'IMPORT — contredisant la promesse « ne lève
jamais » de la fonction qu'il portait.

On détecte donc les deux : un import qui échoue, et un import dont la sortie
n'est pas exactement `OK`.

UN SOUS-PROCESSUS PAR MODULE, jamais un seul pour tous : un module qui plante
masquerait les suivants, et un effet de bord polluerait les imports d'après.

Repris de `import_smoke.py` du dépôt SAS. Squelette produit par le banc
(`gpt-oss-120b-cloud`, 2454 jetons, coût nul), intégré après arbitrage de
quatre défauts :

* `sys.stdout.reconfigure()` au niveau du module, non gardé — sur un flux qui
  ne le supporte pas, l'outil mourait avant d'avoir rien vérifié ;
* `sys.path.append()` au lieu de `insert(0, …)` : un module homonyme situé
  ailleurs dans le chemin aurait été importé à la place du nôtre, et le
  verdict aurait porté sur un autre fichier ;
* aucune détection d'effet de bord, alors que c'est la moitié de l'objet ;
* `--seul` avec un nom inconnu rendait « 0 module, 0 échec » et le code 0 —
  un succès annoncé pour un test qui n'a pas eu lieu.

    python scripts/nexus_import.py
    python scripts/nexus_import.py --seul nexus_ruche --seul nexus_agent
    python scripts/nexus_import.py --json
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys

SCRIPTS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(SCRIPTS)


def code_dimport(module: str) -> str:
    """
    Le programme joué par le sous-processus.

    `insert(0, …)` et non `append` : le dossier des scripts doit primer sur
    tout le reste du chemin, sinon un homonyme installé ailleurs serait
    importé et le verdict porterait sur un autre fichier que le nôtre.
    """
    return ("import sys, importlib; "
            "sys.path.insert(0, r'" + SCRIPTS + "'); "
            "importlib.import_module('" + module + "'); "
            "print('OK')")


def importer(module: str) -> tuple:
    """Rend (statut, motif). Statut vaut OK, ECHEC ou EFFET."""
    try:
        r = subprocess.run([sys.executable, "-c", code_dimport(module)],
                           cwd=ROOT, capture_output=True, text=True,
                           timeout=60, encoding="utf-8", errors="replace")
    except subprocess.TimeoutExpired:
        # Un import qui ne rend pas la main FAIT quelque chose, et c'est
        # precisement ce qu'on interdit.
        return "ECHEC", "import bloque au-dela de 60 s"
    except Exception as exc:
        return "ECHEC", str(exc).splitlines()[0][:120]

    if r.returncode != 0:
        lignes = [l for l in (r.stderr or "").splitlines() if l.strip()]
        # La DERNIERE ligne de stderr porte le type de l'exception ; les
        # precedentes ne sont que la pile qui y mene.
        return "ECHEC", (lignes[-1].strip()[:120] if lignes
                         else "erreur sans message")

    sortie = (r.stdout or "").strip()
    if sortie != "OK":
        # Le module a imprime autre chose : son import ne se contente pas de
        # definir des noms.
        parasite = [l for l in sortie.splitlines() if l.strip() and l.strip() != "OK"]
        return "EFFET", ("l'import ecrit sur la sortie : %s"
                         % (parasite[0][:100] if parasite else sortie[:100]))
    return "OK", ""


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        # Un flux qui ne supporte pas la reconfiguration ne doit pas empecher
        # la verification : c'est l'affichage qui souffre, pas le verdict.
        pass

    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--json", action="store_true")
    p.add_argument("--seul", action="append", default=[])
    a = p.parse_args()

    moi = os.path.basename(os.path.abspath(__file__))[:-3]
    candidats = sorted(n[:-3] for n in os.listdir(SCRIPTS)
                       if n.endswith(".py") and n[:-3] != moi)

    if a.seul:
        cibles = [n for n in candidats if n in a.seul]
        inconnus = [n for n in a.seul if n not in candidats]
        if inconnus:
            # « 0 module, 0 echec, code 0 » pour un test qui n'a pas eu lieu
            # serait un succes annonce sur du vide.
            sys.stderr.write("Module(s) inconnu(s) : %s\n" % ", ".join(inconnus))
            return 2
    else:
        cibles = candidats

    resultats = []
    for module in cibles:
        statut, motif = importer(module)
        resultats.append({"module": module, "statut": statut, "motif": motif})

    fautifs = [r for r in resultats if r["statut"] != "OK"]

    if a.json:
        print(json.dumps({"modules": resultats, "total": len(cibles),
                          "echecs": len(fautifs)},
                         ensure_ascii=False, indent=2))
        return 1 if fautifs else 0

    # Seuls les fautifs sont imprimes : un outil qui aligne quarante lignes
    # vertes a chaque execution n'est plus lu, et le jour ou une ligne rouge
    # s'y glisse, personne ne la voit.
    for r in fautifs:
        print("  [%-6s] %-28s %s" % (r["statut"], r["module"], r["motif"]))
    print("%d module(s) importes, %d echec(s)." % (len(cibles), len(fautifs)))
    return 1 if fautifs else 0


if __name__ == "__main__":
    sys.exit(main())
