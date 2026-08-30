#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Traque mecanique des classes de defauts rencontrees dans ce depot.

Ce script existe parce que la vigilance ne passe pas l'echelle. Chacune des
six classes ci-dessous a ete rencontree REELLEMENT, plusieurs fois, et
souvent recommise apres avoir ete corrigee ailleurs :

  1  handler muet sur un try qui AGIT      la cause de l'echec est perdue
  2  decision prise sur un NOM              un nom est une convention
  3  defaut de modele non mesure            un defaut sans mesure est un pari
  4  except rendant une valeur neutre       zero n'est pas une mesure
  5  refus rendu en code de sortie 0        un echec deguise en succes
  6  print d'echec suivi d'un retour 0      idem, dans une fonction

Rapport, jamais porte : le code de sortie est toujours 0. Un outil qui
bloque sur des heuristiques finit desactive, et c'est la pire des issues.

Ecrit par le banc gratuit sur consigne, puis reduit : sa classe « clef lue
jamais ecrite » produisait des centaines de faux positifs sur des clefs
d'API legitimes, et a ete retiree plutot que gardee bruyante.
"""
from __future__ import annotations

import argparse
import ast
import collections
import os
import re
import sys

ACTIONS = {"write", "write_text", "writelines", "dump", "makedirs", "mkdir",
           "copy", "copy2", "move", "remove", "unlink", "rename", "replace",
           "rmtree", "run", "check_call", "Popen", "urlopen"}

# Fragments de NOM sur lesquels on a deja decide a tort.
NOMS = ("-local", "-cloud", "anthropic", "claude", "embed", "vision", "coder")

NEUTRES = (0, 0.0, "", False)
ECHEC = re.compile(r"refus|impossible|echec|erreur", re.I)


def _texte(noeud):
    """Chaines litterales d'un appel, pour y chercher un aveu d'echec."""
    return " ".join(a.value for a in getattr(noeud, "args", [])
                    if isinstance(a, ast.Constant) and isinstance(a.value, str))


def analyser(chemin):
    constats = []
    try:
        source = open(chemin, encoding="utf-8", errors="replace").read()
        arbre = ast.parse(source, filename=chemin)
    except Exception as exc:
        return [(0, 0, "illisible : %s" % str(exc)[:60])]

    for n in ast.walk(arbre):
        for enfant in ast.iter_child_nodes(n):
            enfant.parent = n

    for n in ast.walk(arbre):
        # --- 1 : handler muet sur un try qui agit -----------------------
        if isinstance(n, ast.Try):
            agit = {c.func.attr for c in ast.walk(ast.Module(body=n.body,
                                                             type_ignores=[]))
                    if isinstance(c, ast.Call)
                    and isinstance(c.func, ast.Attribute)} & ACTIONS
            for h in n.handlers:
                parle = any(isinstance(x, ast.Call) for x in ast.walk(h))
                if agit and not parle:
                    constats.append((h.lineno, 1,
                                     "try appelant %s, handler muet"
                                     % ", ".join(sorted(agit))))
                # --- 4 : valeur neutre rendue par un except -------------
                for s in h.body:
                    if isinstance(s, ast.Return) and isinstance(s.value, ast.Constant)                             and s.value.value in NEUTRES and agit:
                        constats.append((s.lineno, 4,
                                         "rend %r au lieu de dire l'echec"
                                         % s.value.value))

        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute):
            litteral = (n.args[0].value.lower()
                        if n.args and isinstance(n.args[0], ast.Constant)
                        and isinstance(n.args[0].value, str) else "")
            # --- 2 : decision sur un nom -------------------------------
            if n.func.attr in ("startswith", "endswith", "search", "compile", "match")                     and any(f in litteral for f in NOMS):
                constats.append((n.lineno, 2,
                                 "decide sur le nom : %r" % litteral[:40]))
            # --- 3 : defaut de modele non mesure -----------------------
            if n.func.attr == "add_argument":
                for kw in n.keywords:
                    if kw.arg == "default" and isinstance(kw.value, ast.Constant)                             and isinstance(kw.value.value, str)                             and kw.value.value.endswith(("-local", "-cloud")):
                        constats.append((n.lineno, 3,
                                         "defaut %r : mesure ?" % kw.value.value))

    # --- 5 et 6 : un refus rendu en succes -----------------------------
    for n in ast.walk(arbre):
        corps = getattr(n, "body", None)
        if not isinstance(corps, list):
            continue
        for i in range(len(corps) - 1):
            cur, suiv = corps[i], corps[i + 1]
            if not (isinstance(cur, ast.Expr) and isinstance(cur.value, ast.Call)
                    and getattr(cur.value.func, "id", "") == "print"
                    and ECHEC.search(_texte(cur.value))):
                continue
            if isinstance(suiv, ast.Expr) and isinstance(suiv.value, ast.Call)                     and getattr(suiv.value.func, "attr", "") == "exit"                     and suiv.value.args                     and isinstance(suiv.value.args[0], ast.Constant)                     and suiv.value.args[0].value == 0:
                constats.append((suiv.lineno, 5, "refus annonce, sortie 0"))
            if isinstance(suiv, ast.Return) and isinstance(suiv.value, ast.Constant)                     and suiv.value.value == 0:
                constats.append((suiv.lineno, 6, "refus annonce, retour 0"))
    return constats


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--racine", default="scripts")
    p.add_argument("--classe", type=int, choices=range(1, 7))
    p.add_argument("--muet", action="store_true",
                   help="N'afficher que les totaux.")
    a = p.parse_args()

    fichiers = [os.path.join(r, f) for r, _, fs in os.walk(a.racine)
                for f in fs if f.endswith(".py")]
    total = collections.Counter()
    lignes = []
    for f in sorted(fichiers):
        for ligne, classe, motif in analyser(f):
            if classe and (not a.classe or classe == a.classe):
                lignes.append("%s:%d  classe %d  %s" % (f, ligne, classe, motif))
            if classe:
                total[classe] += 1
    if not a.muet:
        for l in lignes:
            print(l)
        print()
    intitules = {1: "handler muet sur un try qui agit",
                 2: "decision prise sur un nom",
                 3: "defaut de modele non mesure",
                 4: "valeur neutre rendue par un except",
                 5: "refus rendu en sortie 0",
                 6: "refus rendu en retour 0"}
    print("%d fichier(s) analyse(s)" % len(fichiers))
    for c in range(1, 7):
        print("  classe %d  %-38s %d" % (c, intitules[c], total.get(c, 0)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
