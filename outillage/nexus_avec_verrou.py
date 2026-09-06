# -*- coding: utf-8 -*-
"""Lanceur de commandes sous verrou machine.

Ce fichier existe car il n'existait aucun chemin legitime pour executer une commande
arbitraire en tenant le verrou machine. Une mesure comparant l'appel direct a l'appel
par la passerelle etait impossible sans contourner le verrou, ce qui a conduit a
des erreurs de mesure par des sessions voisines.

Employer ce script pour garantir l'exclusivite d'une ressource lors de mesures.
Exemple : python nexus_avec_verrou.py GPU --attente-s 60 -- ollama run llama3

LIMITE : Il protege uniquement ce qui passe par lui. Un appel direct a 'ollama run'
lance a la main dans un terminal echappe totalement a ce mecanisme.

Codes de sortie :
0-74, 76-255 : Code de sortie de la commande lancee.
75 : Contention (le verrou est tenu par un autre processus).
2 : Erreur d'usage (commande manquante).
"""
import os
import sys
import subprocess
import argparse

# Derivation de la racine pour portabilite
SCRIPTS = os.path.dirname(os.path.abspath(__file__))
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

from nexus_verrou_machine import verrou

def main():
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("classe", nargs="?", default=None)
    parser.add_argument("--attente-s", type=float, default=120.0)
    parser.add_argument("--projet", type=str, default=None)
    
    # On utilise parse_known_args pour gerer le double tiret manuellement
    args, remaining = parser.parse_known_args()

    if not args.classe:
        print("Usage: python nexus_avec_verrou.py <classe> [--attente-s N] [--projet P] -- <commande>", file=sys.stderr)
        return 2

    # Gestion du double tiret
    try:
        idx = sys.argv.index("--")
        cmd_args = sys.argv[idx + 1:]
    except ValueError:
        print("Erreur : Aucune commande fournie apres le double tiret '--'", file=sys.stderr)
        print("Usage: python nexus_avec_verrou.py <classe> [--attente-s N] [--projet P] -- <commande>", file=sys.stderr)
        return 2

    if not cmd_args:
        print("Erreur : La commande apres '--' est vide", file=sys.stderr)
        return 2

    # Deduction du projet depuis le repertoire courant
    if args.projet is None:
        cwd_name = os.path.basename(os.getcwd())
        args.projet = cwd_name if cwd_name else "?"

    # Acquisition du verrou
    with verrou(args.classe, projet=args.projet, attente_s=args.attente_s) as v:
        if not v:
            print(f"Contention : la classe {args.classe} est tenue par un autre processus", file=sys.stderr)
            return 75

        # Execution de la commande
        # shell=False pour eviter les injections et respecter la consigne "sans passer par un shell"
        try:
            process = subprocess.run(cmd_args)
            return process.returncode
        except FileNotFoundError:
            print(f"Erreur : La commande '{cmd_args[0]}' est introuvable", file=sys.stderr)
            return 127
        except Exception as e:
            print(f"Erreur lors de l'execution : {e}", file=sys.stderr)
            return 1

if __name__ == "__main__":
    sys.exit(main())