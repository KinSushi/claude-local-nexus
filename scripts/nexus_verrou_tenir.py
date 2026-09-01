#!/usr/bin/env python3
"""nexus_verrou_tenir.py

Script autonome qui tient un verrou machine pour le compte d'un processus externe.
Il utilise le gestionnaire de contexte `verrou` fourni par le module
`nexus_verrou_machine` situé dans le même répertoire que ce script.

Usage :
    nexus_verrou_tenir.py <classe> [--projet NOM] [--attente-s N]

Comportement :
    1. Ajoute le répertoire du script en tête de sys.path pour pouvoir importer
       `nexus_verrou_machine` même si le répertoire de travail diffère.
    2. Acquiert le verrou via `verrou(classe, projet=..., attente_s=...)`.
    3. Si le verrou n'est pas obtenu, écrit sur stderr une ligne commençant par
       "[!]" suivie du nom de la classe et quitte avec le code 75.
    4. Sinon, écrit exactement "PRIS\\n" sur stdout, vide le tampon (flush) et
       attend la fermeture du flux d'entrée standard.
    5. Les interruptions clavier (KeyboardInterrupt) et les erreurs de pipe
       cassé (BrokenPipeError) sont traitées comme une fin de flux normale.
    6. Quitte avec le code 0 en fin normale.
"""

import os
import sys
import argparse

# 1. Ajouter le répertoire du script au début de sys.path
script_dir = os.path.abspath(os.path.dirname(__file__))
if script_dir not in sys.path:
    sys.path.insert(0, script_dir)

# Import du gestionnaire de contexte `verrou`
try:
    from nexus_verrou_machine import verrou
except ImportError as e:
    sys.stderr.write(f"[!] impossible d'importer verrou : {e}\n")
    sys.exit(1)


def parse_arguments():
    """Analyse les arguments de la ligne de commande."""
    parser = argparse.ArgumentParser(
        description="Tenir un verrou machine pour un processus externe."
    )
    parser.add_argument("classe", help="Nom de la classe du verrou")
    parser.add_argument(
        "--projet",
        default="?",
        help="Nom du projet (défaut : '?')",
    )
    parser.add_argument(
        "--attente-s",
        type=float,
        default=0.0,
        help="Temps d'attente en secondes (défaut : 0.0)",
    )
    return parser.parse_args()


def main():
    args = parse_arguments()

    # 2. Entrer le gestionnaire de contexte
    try:
        with verrou(
            args.classe, projet=args.projet, attente_s=args.attente_s, bavard=False
        ) as v:
            # Le canal du protocole ne porte que le protocole.
            # Mesure: l'appelant recoit « verrou machine [banc] OBTENU (ep) » au lieu de PRIS.
            # 3. Verifier si le verrou a été obtenu
            if not v:
                sys.stderr.write(f"[!] {args.classe}\n")
                sys.exit(75)

            # 4. Verrou obtenu : informer l'appelant
            try:
                sys.stdout.write("PRIS\n")
                sys.stdout.flush()
            except BrokenPipeError:
                # Le lecteur a fermé le pipe avant que nous puissions écrire.
                # Considéré comme fin normale.
                return

            # 5. Bloquer en lisant stdin jusqu'à la fermeture du flux
            try:
                # Lecture et rejet de tout le contenu sans le traiter.
                for _ in sys.stdin:
                    pass
            except KeyboardInterrupt:
                # Interruption clavier : traiter comme fin de flux normale.
                pass
            except BrokenPipeError:
                # Le pipe d'entrée a été fermé de façon inattendue.
                pass

    except KeyboardInterrupt:
        # Interruption pendant l'acquisition du verrou : traiter comme fin normale.
        pass
    except BrokenPipeError:
        # Même traitement que ci‑dessus.
        pass

    # 6. Sortie normale
    sys.exit(0)


if __name__ == "__main__":
    main()