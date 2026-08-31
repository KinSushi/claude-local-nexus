#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import subprocess
import sys
import time
import shutil

# Constantes
MARGE_DISQUE_GO = 50
DELAI_PULL_S = 1800

def execute_command(cmd, encoding='utf-8'):
    """Execute une commande et retourne stdout, stderr, code de sortie."""
    try:
        # `text=False` ET `encoding=` se contredisent : le premier demande des
        # octets, le second du texte. Le `.decode()` qui suivait s'appliquait
        # alors a une chaine, levait AttributeError, et l'except generique
        # rendait un code non nul -- rapporte a l'ecran comme « Ollama
        # introuvable » alors qu'Ollama repondait parfaitement. Un diagnostic
        # faux ne d'un defaut interne envoie chercher au mauvais endroit.
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            encoding=encoding,
            errors='replace'
        )
        return result.stdout, result.stderr, result.returncode
    except Exception as e:
        return '', str(e), 1

def get_disk_space():
    """Retourne l'espace libre en Go ou None si impossible."""
    try:
        total, used, free = shutil.disk_usage(os.path.abspath('.'))
        return free // (1024**3)
    except Exception:
        # PIEGE A : os.statvfs n'existe pas sous Windows
        return None

def parse_size(size_str):
    """Convertit une taille comme '6.7 GB' ou '725 MB' en Go."""
    size_str = size_str.strip()
    if size_str.endswith('GB'):
        return float(size_str[:-2])  # Extrait le nombre avant 'GB'
    if size_str.endswith('MB'):
        return float(size_str[:-2]) / 1024.0  # Convertit MB en Go
    # PIEGE B : Ne pas confondre colonne taille avec ID
    return 0.0

def main():
    import argparse
    parser = argparse.ArgumentParser(description='Mise a jour des modeles Ollama deja installes.')
    parser.add_argument('--appliquer', action='store_true', help='Appliquer les mises a jour.')
    parser.add_argument('--limite', type=int, default=None, help='Nombre limite de modeles a traiter.')
    args = parser.parse_args()

    # Verifier si ollama est disponible
    stdout, stderr, code = execute_command('ollama --version')
    if code != 0:
        print("ERREUR : Ollama introuvable.")
        sys.exit(2)

    # Recuperer la liste des modeles
    stdout, stderr, code = execute_command('ollama list')
    if code != 0:
        print(f"ERREUR : Impossible de recuperer la liste des modeles. {stderr}")
        sys.exit(2)

    lines = stdout.strip().split('\n')
    if len(lines) < 2:
        print("AUCUN MODELE TROUVE.")
        sys.exit(2)

    # Ignorer l'en-tete
    model_lines = lines[1:]

    models_to_update = []
    total_size = 0.0

    for line in model_lines:
        parts = line.split()
        if len(parts) < 4:
            continue
        name = parts[0]
        # LA TAILLE TIENT EN DEUX CHAMPS, pas un. `ollama list` ecrit
        # « 6.7 GB » : decoupe sur les espaces, le nombre est en parts[2] et
        # l'unite en parts[3]. Ne prendre que parts[2] donnait « 6.7 » sans
        # unite, que parse_size rendait a ZERO -- d'ou un total de 0,00 Go
        # affiche pour cinquante modeles, et une garde disque qui comparait
        # ce zero a son seuil.
        size_str = parts[2] + ' ' + parts[3]
        # Ignorer les modeles marques comme ':cloud'
        if name.endswith(':cloud'):
            continue
        size_go = parse_size(size_str)
        total_size += size_go
        models_to_update.append((name, size_go))

    # LA LIMITE BORNE LA LISTE, ET NON LA SEULE BOUCLE D'APPLICATION.
    #
    # Elle n'etait appliquee qu'a la mise a jour : la simulation
    # affichait CINQUANTE modeles la ou l'application n'en aurait traite
    # que quatre. Une simulation qui ne montre pas ce qui sera fait ne
    # simule rien -- et c'est precisement le geste cense proteger de la
    # surprise.
    if args.limite:
        models_to_update = models_to_update[:args.limite]

    if not models_to_update:
        print("AUCUN MODELE A METTRE A JOUR.")
        sys.exit(2)

    # Afficher les modeles et le total
    print("Modeles a mettre a jour :")
    for name, size in models_to_update:
        print(f"  {name} ({size:.2f} Go)")
    # LE TOTAL PORTE SUR CE QUI EST LISTE, ET NON SUR TOUT LE PARC.
    # Il etait accumule avant l application de --limite : la simulation
    # annoncait 430 Go pour quatre modeles affiches. Une simulation dont le
    # chiffre ne correspond pas a sa liste ne simule rien.
    print(f"Taille totale : {sum(t for _n, t in models_to_update):.2f} Go")

    # Garde disque
    free_space = get_disk_space()
    if free_space is None or free_space < MARGE_DISQUE_GO:
        msg = f"ESPACE DISQUE INSUFFISANT : {free_space} Go (minimum requis : {MARGE_DISQUE_GO} Go)"
        if free_space is None:
            msg = "IMPOSSIBLE DE DETERMINER L'ESPACE LIBRE."
        print(msg)
        sys.exit(2)

    print(f"Espace libre : {free_space} Go")

    if not args.appliquer:
        print("SIMULATION SEULEMENT. AUCUNE MISE A JOUR EFFECTUEE.")
        sys.exit(0)

    # Mode application
    updated = 0
    up_to_date = 0
    failed = 0

    for name, _taille in models_to_update:

        print(f"Traitement de : {name}")
        stdout, stderr, code = execute_command(f'ollama pull {name}')
        output = stdout + stderr

        # Analyser la sortie pour determiner l'etat
        if 'already up to date' in output.lower():
            up_to_date += 1
        elif 'pulling' in output.lower() and 'done' in output.lower():
            updated += 1
        else:
            failed += 1

        # Delai entre chaque pull
        print(f"Attente de {DELAI_PULL_S} secondes...")
        time.sleep(DELAI_PULL_S)

    print("\nRapport final :")
    print(f"  Deja a jour : {up_to_date}")
    print(f"  Mises a jour : {updated}")
    print(f"  Echecs       : {failed}")

    if failed > 0:
        sys.exit(1)
    elif updated > 0 or up_to_date > 0:
        sys.exit(0)
    else:
        sys.exit(2)

if __name__ == '__main__':
    main()
