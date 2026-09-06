#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Un fichier Python qui vient d'être écrit compile-t-il encore ?

Hook `PostToolUse`. Il dit, il ne bloque pas : l'écriture a déjà eu lieu, et
refuser après coup n'annulerait rien — cela ne ferait qu'ajouter du bruit à
une erreur déjà commise. Le signal immédiat, lui, vaut : une syntaxe cassée
découverte dix minutes plus tard a eu le temps d'être commise, publiée, et
d'entraîner une seconde correction par-dessus la première.

CE QU'IL NE FAIT PAS, ET POURQUOI
---------------------------------
Il n'écrit AUCUN fichier — la compilation va vers `os.devnull`. C'est
délibéré : la plateforme a déjà des automatismes qui écrivent, et deux
mécanismes qui touchent la même cible finissent par se marcher dessus.

* `NexusTraque` (PT10M) régénère le cockpit — ce garde n'y touche pas ;
* `NexusVitrine` (PT6H) commite et pousse — ce garde ne fait ni l'un ni
  l'autre ;
* `nexus_traque.py` fait une analyse AST de tout le dépôt, toutes les dix
  minutes. Ce garde ne la double pas : il répond à une autre question, à un
  autre moment. La traque dit « l'état du dépôt » ; lui dit « ce que tu
  viens d'écrire », tout de suite. Complémentaires, jamais concurrents.

Écrit par le banc local (`qwen3-coder-30b-local`, 835 jetons, coût nul),
intégré après correction d'un défaut qui violait sa contrainte principale :
`data.get("tool_response", {}).get("filePath")` lève `AttributeError` quand
`tool_response` vaut `null` — ce qui arrive — et le garde serait sorti en
erreur, avec une trace, exactement ce qu'il promettait de ne jamais faire.
Un garde qui plante empêche de travailler ; c'est pire que le défaut qu'il
surveille.
"""
import io
import json
import os
import sys


def chemin_ecrit(charge) -> str:
    """
    Chemin du fichier touché, ou chaîne vide.

    Chaque accès est garde separement : un champ peut etre absent, mais il
    peut aussi valoir `null`, et les deux cas ne se traitent pas pareil --
    `.get()` sur `None` leve, `.get()` sur un dictionnaire absent non.
    """
    if not isinstance(charge, dict):
        return ""
    for section, cle in (("tool_response", "filePath"),
                         ("tool_input", "file_path")):
        bloc = charge.get(section)
        if isinstance(bloc, dict):
            valeur = bloc.get(cle)
            if isinstance(valeur, str) and valeur.strip():
                return valeur
    return ""


# CE GARDE EST AGNOSTIQUE A L OUTIL : il se cale sur la presence d un
# champ `file_path` dans tool_input, jamais sur un nom d outil. `None` le
# dit explicitement, pour que le controle « gardes accordes » ne l exige
# pas -- et pour qu un futur lecteur ne prenne pas l absence de constante
# pour un oubli. Voir nexus_garde_shell.py pour le motif complet.
OUTILS_JUGES = None


def main() -> int:
    try:
        brut = sys.stdin.read()
    except Exception:
        return 0
    if not brut or not brut.strip():
        return 0
    try:
        charge = json.loads(brut)
    except Exception:
        return 0

    chemin = chemin_ecrit(charge)
    if not chemin or not chemin.lower().endswith(".py"):
        return 0
    if not os.path.isfile(chemin):
        return 0

    try:
        with io.open(chemin, encoding="utf-8", errors="replace") as fh:
            source = fh.read()
    except OSError:
        # Fichier illisible, droit refuse : rien a voir avec la syntaxe.
        return 0

    # compile() natif, et NON py_compile : le premier jet employait
    # `py_compile.compile(..., cfile=os.devnull)`, qui sous Windows leve
    # FileExistsError -- « nul is a non-regular file » -- et non
    # PyCompileError. Le garde tombait donc dans son except generique et
    # n'a JAMAIS rien detecte. Silencieux sur un fichier sain, silencieux
    # sur un fichier casse : rigoureusement aveugle, et indiscernable d'un
    # garde qui fonctionne tant qu'on ne l'eprouve pas.
    #
    # compile() n'ecrit aucun fichier, ce qui sert aussi la regle de
    # non-concurrence : ce hook ne pose rien sur le disque.
    try:
        compile(source, chemin, "exec")
    except SyntaxError as exc:
        message = ("Syntaxe invalide dans %s ligne %s : %s"
                   % (os.path.basename(chemin), exc.lineno or "?",
                      str(exc.msg)[:100]))
        try:
            print(json.dumps({"systemMessage": message}, ensure_ascii=False))
        except Exception:
            pass
    except Exception:
        # Un fichier qui n'est pas du Python valide pour une autre raison
        # (encodage exotique, valeur hors bornes) ne justifie pas d'alerter.
        return 0
    # Le silence est le cas NORMAL. Un garde qui parle a chaque ecriture finit
    # ignore, et le jour ou il a raison personne ne le lit.
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except BaseException:
        # Dernier rempart. La contrainte est absolue : ce script ne sort
        # jamais non nul, quoi qu'il arrive en amont.
        sys.exit(0)
