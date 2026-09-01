# -*- coding: utf-8 -*-
"""`--max-tokens` doit atteindre les taches d'un lot.

Defaut signale par la session sovereign-ai-system-8e le 2026-09-01, puis
verifie dans le code. La branche `--lot` propageait `args.temperature` sur
chaque tache et ne propageait PAS `args.max_tokens` : deux options voisines,
l'une active et l'autre inerte, sans que rien ne le dise.

Le voisin a lance deux vagues avec `--max-tokens 6000` puis `8000`. Les deux
ont tourne au defaut de 1500 jetons. Et 1500 est SOUS le besoin de
raisonnement mesure de ces modeles -- environ 1300 jetons avant la premiere
ligne de sortie -- donc la troncature etait structurelle, precisement pour
l'utilisateur qui avait pris soin de s'en premunir.

Ce que l'epreuve verifie, en construisant l'espace de noms de l'analyseur
plutot qu'en lancant un appel reseau :

  1. une tache de lot SANS `max_tokens` recoit celui de la ligne de commande ;
  2. la propagation ne depend PAS de `--temperature` -- premier remede propose
     par le banc, refuse : il imbriquait le nouveau test dans celui de la
     temperature, ce qui recreait le meme piege ;
  3. sans `--max-tokens`, le budget declare dans le JSON est PRESERVE ;
  4. la branche `--tache` retrouve bien 4096 quand l'option est absente, le
     defaut ayant ete retire de l'analyseur.
"""
import importlib.util
import io
import os
import re
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCE = os.path.join(RACINE, "scripts", "nexus_agent.py")


def _dire(ok, nom, detail):
    print("%s %s : %s" % ("[OK  ]" if ok else "[RATE]", nom, detail))
    return ok


def _propager(taches, max_tokens, temperature):
    """Rejoue la resolution des budgets telle que le module l'ecrit.

    On lit le code plutot que de le reimplementer : une epreuve qui recopie
    la logique qu'elle teste ne teste que sa propre copie.
    """
    spec = importlib.util.spec_from_file_location("nexus_agent_budget", SOURCE)
    module = importlib.util.module_from_spec(spec)
    sys.modules["nexus_agent_budget"] = module
    spec.loader.exec_module(module)

    class Args:
        def __getattr__(self, name):
            # Cette forme evite de rouvrir l'epreuve a chaque option nouvelle,
            # une option non posee vaut None donc n'est pas propagee,
            # ce qui est exactement le comportement voulu.
            return None

    args = Args()
    args.max_tokens = max_tokens
    args.temperature = temperature

    with io.open(SOURCE, encoding="utf-8") as fh:
        source = fh.read()
    # Le bloc de propagation, extrait du fichier et rejoue tel quel.
    bloc = re.search(
        r"\n(        # Si la temp.*?)\n    elif args\.tache:", source, re.S)
    if not bloc:
        raise AssertionError("bloc de propagation introuvable dans le source")
    code = "\n".join(l[8:] if l.startswith("        ") else l
                     for l in bloc.group(1).splitlines())
    exec(compile(code, "<propagation>", "exec"),
         {"args": args, "taches": taches})
    return taches


def main():
    code = 0

    # 1 et 2 : le budget descend, et sans dependre de la temperature.
    taches = _propager([{"nom": "a", "tache": "x"}], 8000, None)
    if not _dire(taches[0].get("max_tokens") == 8000,
                 "le budget atteint une tache de lot",
                 "max_tokens = %r (attendu 8000)" % taches[0].get("max_tokens")):
        code = 1

    # 3 : un JSON explicite reste maitre quand l'option est absente.
    taches = _propager([{"nom": "a", "tache": "x", "max_tokens": 2600}], None, None)
    if not _dire(taches[0].get("max_tokens") == 2600,
                 "le JSON reste maitre sans l'option",
                 "max_tokens = %r (attendu 2600)" % taches[0].get("max_tokens")):
        code = 1

    # 4 : l'analyseur ne porte plus de defaut, il doit etre retabli ailleurs.
    with io.open(SOURCE, encoding="utf-8") as fh:
        source = fh.read()
    sans_defaut = re.search(
        r'add_argument\("--max-tokens", type=int, default=None', source)
    retabli = "(args.max_tokens or 4096)" in source
    if not _dire(bool(sans_defaut) and retabli,
                 "le defaut 4096 est retabli hors de l'analyseur",
                 "default=None : %s, repli 4096 : %s" % (bool(sans_defaut), retabli)):
        code = 1

    return code


if __name__ == "__main__":
    sys.exit(main())
