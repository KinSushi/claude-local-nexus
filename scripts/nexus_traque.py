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
#
# Reduits apres examen des 21 constats du premier passage : la plupart
# etaient legitimes, et les signaler noyait les vrais.
#
# ECARTES, parce que ce ne sont pas des devinettes :
#   « anthropic/ »        prefixe de provider LiteLLM, un FAIT de la
#                         configuration et non une supposition sur un nom
#   « -local », « -cloud » nos propres alias, dont controle_frontiere_alias
#                         garantit qu'ils ne mentent pas sur l'api_base
#   « claude- »           prefixe employe pour EXCLURE, jamais pour deduire
#
# CONSERVES, parce qu'ils devinent une CAPACITE que le moteur declare :
#   « embed », « vision », « coder », « llava », « minilm »
#
# Les trois premiers ont produit de vrais defauts le 2026-08-30 : deux
# modeles de vision classes texte, six generalistes pris pour des
# specialistes du code, un embedding non reconnu.
NOMS = ("embed", "vision", "coder", "llava", "minilm")

NEUTRES = (0, 0.0, "", False)
# ajout des mots clefs du motif A
# LES MARQUEURS STRUCTURES, distincts des mots. Un refus rendu en JSON ne
# porte aucun mot francais : il porte une CLE. Ces cles-la sont assez rares
# pour etre cherchees dans une fonction entiere sans noyer le signal.
MARQUEURS_REFUS = re.compile(
    r"permissionDecision|[\"']deny[\"']|[\"']blocked[\"']|"
    r"[\"']refused[\"']|[\"']reject(ed)?[\"']", re.I)

ECHEC = re.compile(r"refus|impossible|echec|erreur|deny|permissionDecision|blocked|refused|reject", re.I)


def _texte(noeud):
    """Chaines litterales d'un appel, pour y chercher un aveu d'echec."""
    return " ".join(a.value for a in getattr(noeud, "args", [])
                    if isinstance(a, ast.Constant) and isinstance(a.value, str))


def _charge_de_refus(appel, portee) -> bool:
    """La chose IMPRIMEE porte-t-elle un marqueur de refus structure ?

    CE QUI ETAIT FAUX, deux fois de suite, et la seconde etait de mon fait.

    D'abord le motif ne regardait que le TEXTE de la ligne du print. Or le
    defaut qui a coute 32 millions de jetons factures ce jour imprimait une
    charge construite trois lignes plus haut :
        payload = {"hookSpecificOutput": {"permissionDecision": "deny", ...}}
        print(json.dumps(payload, ensure_ascii=False))
        return 0
    Aucun mot de refus sur la ligne du print. La traque tournait toutes les
    dix minutes et ne voyait rien.

    Elargi ensuite a la FONCTION englobante, il a signale
    nexus_worktree.py:378 -- un chemin de SUCCES, dans une fonction qui
    contient par ailleurs un refus. Une fonction porte les deux, et confondre
    ses chemins accuse du code correct. Un detecteur qui crie sur du juste
    finit desarme, et emporte ses vraies detections avec lui.

    On suit donc la VARIABLE reellement imprimee, et rien d'autre : les noms
    cites dans l'appel, puis les affectations de ces noms dans la meme portee.
    """
    noms = {x.id for x in ast.walk(appel) if isinstance(x, ast.Name)}
    if not noms:
        return False
    if portee is None:
        return False
    for st in ast.walk(portee):
        if not isinstance(st, (ast.Assign, ast.AnnAssign)):
            continue
        cibles = st.targets if isinstance(st, ast.Assign) else [st.target]
        if not any(isinstance(c, ast.Name) and c.id in noms for c in cibles):
            continue
        if st.value is not None and MARQUEURS_REFUS.search(ast.dump(st.value)):
            return True
    return False


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
                    if (isinstance(s, ast.Return) and isinstance(s.value, ast.Constant)
                            and s.value.value in NEUTRES and agit):
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
                    if (kw.arg == "default" and isinstance(kw.value, ast.Constant)
                            and isinstance(kw.value.value, str)
                            and kw.value.value.endswith(("-local", "-cloud"))):
                        constats.append((n.lineno, 3,
                                         "defaut %r : mesure ?" % kw.value.value))

    # --- 5 et 6 : un refus rendu en succes -----------------------------
    for n in ast.walk(arbre):
        corps = getattr(n, "body", None)
        if not isinstance(corps, list):
            continue
        portee = n if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) else None
        for i in range(len(corps) - 1):
            cur, suiv = corps[i], corps[i + 1]
            if not (isinstance(cur, ast.Expr) and isinstance(cur.value, ast.Call)
                    and getattr(cur.value.func, "id", "") == "print"):
                continue
            # UN REFUS PEUT ETRE ECRIT EN DONNEES, PAS EN MOTS.
            #
            # Le motif ne regardait que le texte de l'appel a print. Or le
            # defaut qui a coute 32 millions de jetons factures ce jour
            # imprimait une charge STRUCTUREE construite trois lignes plus
            # haut :
            #     payload = {"hookSpecificOutput":
            #                {"permissionDecision": "deny", ...}}
            #     print(json.dumps(payload, ensure_ascii=False))
            #     return 0
            # Sur la ligne du print, aucun mot de refus. La traque tournait
            # toutes les dix minutes et n'a rien vu.
            #
            # On elargit donc a la FONCTION englobante -- mais uniquement
            # pour les marqueurs STRUCTURES. Les mots francais (« erreur »,
            # « echec ») restent bornes a la ligne du print : etendus a la
            # fonction entiere ils allumeraient la moitie du depot, et un
            # detecteur qui crie partout finit desarme.
            if not (ECHEC.search(_texte(cur.value))
                    or _charge_de_refus(cur.value, portee)):
                continue
            # print suivi de sys.exit(0)  -> classe 5
            if (isinstance(suiv, ast.Expr) and isinstance(suiv.value, ast.Call)
                    and getattr(suiv.value.func, "attr", "") == "exit"
                    and suiv.value.args
                    and isinstance(suiv.value.args[0], ast.Constant)
                    and suiv.value.args[0].value == 0):
                constats.append((suiv.lineno, 5, "refus annonce, sortie 0"))
            # print suivi de return 0 -> classe 6
            if (isinstance(suiv, ast.Return) and isinstance(suiv.value, ast.Constant)
                    and suiv.value.value == 0):
                constats.append((suiv.lineno, 6, "refus annonce, retour 0"))

    # --- B : except convertissant un echec en succes -----------------
    for n in ast.walk(arbre):
        if not isinstance(n, ast.Try):
            continue
        # recherche d'un sys.exit(X) dans le try dont X n'est pas la constante 0
        bad_exit_in_try = False
        for stmt in n.body:
            if (isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call)):
                func = stmt.value.func
                if (isinstance(func, ast.Attribute)
                        and getattr(func.value, "id", "") == "sys"
                        and func.attr == "exit"):
                    if stmt.value.args:
                        arg = stmt.value.args[0]
                        if not (isinstance(arg, ast.Constant) and arg.value == 0):
                            bad_exit_in_try = True
        if not bad_exit_in_try:
            continue
        # UN `except SystemExit: raise` DESAMORCE LE REMPART.
        #
        # Faux positif mesure le 2026-08-31 sur nexus_garde_edition.py : ce
        # garde attrape SystemExit et le RELANCE avant son except
        # BaseException, si bien que le refus traverse. Le motif le signalait
        # tout de meme. Un detecteur qui accuse du code correct se fait
        # desarmer, et emporte avec lui les vraies detections.
        #
        # Note pour l'histoire : cet idiome etait DEJA present dans ce garde
        # quand nexus_garde_agent.py avalait ses propres refus. Le depot
        # tenait la bonne forme a un endroit et pas a l'autre -- une raison
        # de plus de mecaniser plutot que de se fier a la memoire.
        def _relance_systemexit(handler):
            cible = handler.type
            attrape = (isinstance(cible, ast.Name) and cible.id == "SystemExit")
            if isinstance(cible, ast.Tuple):
                attrape = any(isinstance(e, ast.Name) and e.id == "SystemExit"
                              for e in cible.elts)
            if not attrape:
                return False
            return any(isinstance(x, ast.Raise) and x.exc is None
                       for x in ast.walk(ast.Module(body=handler.body,
                                                    type_ignores=[])))

        if any(_relance_systemexit(h) for h in n.handlers):
            continue
        for h in n.handlers:
            # except BaseException ou except sans type
            if (h.type is None) or (isinstance(h.type, ast.Name) and h.type.id == "BaseException"):
                for s in h.body:
                    # return 0
                    if (isinstance(s, ast.Return) and isinstance(s.value, ast.Constant)
                            and s.value.value == 0):
                        constats.append((s.lineno, 5,
                                         "except convertit echec en retour 0"))
                    # sys.exit(0)
                    if (isinstance(s, ast.Expr) and isinstance(s.value, ast.Call)):
                        func = s.value.func
                        if (isinstance(func, ast.Attribute)
                                and getattr(func.value, "id", "") == "sys"
                                and func.attr == "exit"
                                and s.value.args
                                and isinstance(s.value.args[0], ast.Constant)
                                and s.value.args[0].value == 0):
                            constats.append((s.lineno, 5,
                                             "except convertit echec en sortie 0"))
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
