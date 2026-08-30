#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Lire avant d'écrire. Refusé sinon.

Hook `PreToolUse` sur Edit / Write / NotebookEdit. Il refuse d'écrire dans un
fichier EXISTANT qui n'a pas été lu pendant cette session : écrire sur un
contenu supposé écrase ce qu'on n'a pas vu, et le travail perdu ne se
distingue pas d'un travail jamais fait.

Repris du dépôt SAS (`hook_lecture_avant_ecriture.py`), où il a mordu le jour
même où nous l'inscrivions « à reprendre » — il a arrêté une écriture sur un
fichier de test non lu.

CE QU'IL NE VOIT PAS, et il faut le dire pour ne pas s'en croire protégé :
il ne voit **que** les outils qui passent par ce hook. Ce qu'un script lancé
par le shell écrit, ce qu'un éditeur externe modifie, ce qu'un autre
processus touche — rien de tout cela ne lui parvient. Le garde borne un
chemin d'écriture, pas tous.

Squelette produit par le banc (`gpt-oss-120b-cloud`, 2613 jetons, coût nul),
intégré après arbitrage de trois défauts :

* `.nexus/lectures` était RELATIF au répertoire courant. Un hook peut être
  lancé de n'importe où : la mémoire des lectures serait allée ailleurs, et
  le garde aurait refusé des écritures légitimes en ayant oublié les lectures
  correspondantes. C'est la troisième fois aujourd'hui qu'une racine relative
  passe pour absolue dans ce dépôt ;
* accents dans le motif IMPRIMÉ, alors que ce motif s'affiche à l'opérateur
  et casse sous cp1252 ;
* `portee()` était une fonction vide, avec un `pass` et un docstring — de la
  documentation déguisée en code, que rien n'appelle et que rien ne vérifie.
  La limite est ici, dans le docstring du module, là où elle se lit.
"""
import json
import os
import re
import sys

# Racine ABSOLUE. `CLAUDE_PROJECT_DIR` quand le hook est lance par Claude
# Code ; sinon, deduite de la position de ce fichier -- jamais du repertoire
# courant, qui n'est pas celui du projet des qu'un outil change de dossier.
ROOT = os.environ.get("CLAUDE_PROJECT_DIR") or os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))

ECRITURES = ("Edit", "Write", "NotebookEdit")


def normaliser(chemin: str) -> str:
    """
    Forme canonique d'un chemin.

    `normcase` autant qu'`abspath` : sous Windows, « C:/a/B.py » et
    « c:\\a\\b.py » designent le meme fichier, et les traiter comme deux
    refuserait une ecriture pourtant legitime -- le garde punirait alors
    quelqu'un qui a bel et bien lu.
    """
    return os.path.normcase(os.path.abspath(str(chemin)))


def memoire(session: str) -> str:
    """
    Fichier de memoire de cette session.

    L'identifiant est filtre avant de servir de nom de fichier : un
    identifiant contenant « .. » ou un separateur ecrirait ailleurs sur le
    disque. On ne garde que ce qui ne peut designer aucun autre repertoire.
    """
    propre = re.sub(r"[^A-Za-z0-9_-]", "", str(session or ""))
    return os.path.join(ROOT, ".nexus", "lectures",
                        (propre or "sans-session") + ".json")


def lus(chemin_memoire: str) -> set:
    try:
        with open(chemin_memoire, encoding="utf-8") as fh:
            return set(json.load(fh).get("lus") or [])
    except Exception:
        # Memoire absente ou illisible : on repart de rien. Le garde refusera
        # peut-etre une ecriture de trop, jamais une de moins -- et il suffit
        # de lire le fichier pour passer.
        return set()


def retenir(chemin_memoire: str, connus: set) -> None:
    try:
        os.makedirs(os.path.dirname(chemin_memoire), exist_ok=True)
        with open(chemin_memoire, "w", encoding="utf-8") as fh:
            json.dump({"lus": sorted(connus)}, fh, ensure_ascii=False)
    except Exception:
        # Un echec d'ecriture ne doit JAMAIS empecher d'autoriser : le pire
        # que l'on risque est d'oublier une lecture, pas de perdre un fichier.
        pass


def refuser(chemin_affiche: str) -> None:
    """
    Le nom montre est celui du chemin D'ORIGINE, jamais la forme canonique.

    `normaliser` applique `normcase`, qui met tout en minuscules sous
    Windows : le motif annoncait « readme.md » pour un fichier nomme
    « README.md ». La forme canonique sert a COMPARER, pas a AFFICHER, et un
    message qui renomme le fichier qu'il designe fait douter de ce qu'il dit.
    """
    motif = ("REFUS -- LIRE AVANT D'ECRIRE. Le fichier %s existe et n'a pas "
             "ete lu dans cette session : ecrire dessus ecraserait un contenu "
             "suppose. Le lire d'abord (outil Read), puis ecrire."
             % os.path.basename(chemin_affiche))
    try:
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": motif,
        }}, ensure_ascii=False))
    except Exception:
        pass


def main() -> None:
    try:
        brut = sys.stdin.read()
    except Exception:
        return
    if not brut or not brut.strip():
        return
    try:
        charge = json.loads(brut)
    except Exception:
        return
    if not isinstance(charge, dict):
        return

    outil = charge.get("tool_name") or ""
    entree = charge.get("tool_input")
    entree = entree if isinstance(entree, dict) else {}
    chemin = entree.get("file_path") or entree.get("notebook_path") or ""
    if not isinstance(chemin, str) or not chemin.strip():
        return

    try:
        cible = normaliser(chemin)
        fichier_memoire = memoire(charge.get("session_id"))
    except Exception:
        # Sans chemin canonique, aucune decision prudente n'est possible :
        # autoriser plutot que refuser sur une base incertaine.
        return

    if outil == "Read":
        connus = lus(fichier_memoire)
        connus.add(cible)
        retenir(fichier_memoire, connus)
        return

    if outil not in ECRITURES:
        return

    try:
        existe = os.path.exists(cible)
    except Exception:
        return
    if not existe:
        # Creer un fichier neuf n'ecrase rien : il n'y a rien a avoir lu.
        return
    if cible in lus(fichier_memoire):
        return
    refuser(chemin)


if __name__ == "__main__":
    try:
        main()
    except BaseException:
        # Rempart final. La contrainte est absolue : ce garde n'echoue jamais,
        # et une anomalie AUTORISE en silence. Un garde qui plante empeche de
        # travailler, ce qui est pire que le defaut qu'il surveille.
        pass
    sys.exit(0)
