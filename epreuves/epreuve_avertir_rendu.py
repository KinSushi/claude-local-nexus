# -*- coding: utf-8 -*-
"""Le rendu doit DIRE ce qui a diverge, pas seulement l'afficher.

Deux defauts d'usage signales par la session ea-mt5-python-rentable-e1 le
2026-09-01, tous deux verifies dans le code avant correction.

1. Les lignes « demande » et « servi » posaient deux faits cote a cote sans
   jamais dire qu'ils differaient. La passerelle peut replier en interne sans
   que le champ `bascule` soit pose : le voisin a vu deux alias distincts,
   `deepseek-v4-pro-0813-cloud` et `qwen3.5-397b-cloud`, servis tous deux par
   `ollama_chat/gpt-oss:120b`. Trois lots sur quatre ont tourne sur le meme
   modele sans qu'il le sache -- pour un audit croise, cela annule l'objet
   meme de la frappe.

2. Le champ `tronque` n'etait JAMAIS affiche. Il l'a decouvert parce qu'un
   fichier Python rendu ne compilait pas.

Et un FAUX POSITIF, trouve en essayant le remede plutot qu'en le relisant :
derriere un routeur adaptatif la divergence est le fonctionnement NORMAL.
Un avertissement qui crie a chaque appel de routeur est desarme par son
lecteur, et il masque alors le vrai cas.
"""
import contextlib
import importlib.util
import io
import os
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _rendre(resultat):
    """Capture ce que rendre() imprime pour un resultat donne."""
    chemin = os.path.join(RACINE, "scripts", "nexus_agent.py")
    spec = importlib.util.spec_from_file_location("nexus_agent_rendu", chemin)
    module = importlib.util.module_from_spec(spec)
    sys.modules["nexus_agent_rendu"] = module
    spec.loader.exec_module(module)
    tampon = io.StringIO()
    with contextlib.redirect_stdout(tampon):
        module.rendre(dict(resultat))
    return tampon.getvalue()


BASE = {"nom": "t", "texte": "peu importe", "tokens": 100, "duree": 1.0,
        "cout": "0", "plan": "cloud", "adresse": "https://ollama.com"}


def _dire(ok, nom, detail):
    print("%s %s : %s" % ("[OK  ]" if ok else "[RATE]", nom, detail))
    return ok


def main():
    code = 0

    # 1 : le cas du voisin. Un alias qui NOMME une famille, servi par une
    # autre. C'est celui qu'il faut voir, et qu'il n'a pas vu.
    sortie = _rendre(dict(BASE, modele="deepseek-v4-pro-0813-cloud",
                          servi_par="ollama_chat/gpt-oss:120b"))
    if not _dire("famille servie differente" in sortie,
                 "la famille divergente est annoncee",
                 "\n".join([l for l in sortie.splitlines() if "[" in l]) or f"{len(sortie.splitlines())} lignes"):
        code = 1

    # 2 : le faux positif. Derriere un routeur, la divergence est le principe.
    sortie = _rendre(dict(BASE, modele="adaptive-router-cloud",
                          servi_par="ollama_chat/qwen3.5:397b"))
    if not _dire("servi" in sortie and "famille servie differente" not in sortie,
                 "un routeur adaptatif n'avertit pas",
                 "silencieux" if "famille" not in sortie else "CRIE A TORT"):
        code = 1

    # 3 : concordance. L'alias porte la famille reellement servie.
    sortie = _rendre(dict(BASE, modele="gpt-oss-120b-cloud",
                          servi_par="ollama_chat/gpt-oss:120b"))
    if not _dire("servi" in sortie and "famille servie differente" not in sortie,
                 "une famille concordante n'avertit pas",
                 "silencieux" if "famille" not in sortie else "CRIE A TORT"):
        code = 1

    # 4 : la troncature doit se voir a l'ecran, pas seulement dans le JSON.
    sortie = _rendre(dict(BASE, modele="gpt-oss-120b-cloud",
                          servi_par="ollama_chat/gpt-oss:120b",
                          tronque=True, tokens_sortie=1400))
    if not _dire("TRONQUE" in sortie, "la troncature est annoncee a l'ecran",
                 "\n".join([l for l in sortie.splitlines() if "[" in l]) or f"{len(sortie.splitlines())} lignes"):
        code = 1

    return code


if __name__ == "__main__":
    sys.exit(main())
