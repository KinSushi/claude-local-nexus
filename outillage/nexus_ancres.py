#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import io
import json
import os
import re
import sys
import unicodedata
import tempfile

def charger_jsonl(path):
    try:
        with io.open(path, 'r', encoding='utf-8') as f:
            lignes = f.readlines()
    except Exception as e:
        sys.stderr.write(f"Erreur lors de la lecture du fichier JSONL '{path}': {e}\n")
        sys.exit(2)
    objets = []
    for i, ligne in enumerate(lignes):
        ligne = ligne.rstrip('\n')
        if not ligne.strip():
            continue
        try:
            obj = json.loads(ligne)
            objets.append((obj, ligne))
        except json.JSONDecodeError as e:
            sys.stderr.write(f"Ligne {i+1} du JSONL invalide: {e}\n")
            sys.exit(2)
    return objets

def ecrire_jsonl_atomique(path, objets):
    dir_name = os.path.dirname(os.path.abspath(path))
    fd, tmp_path = tempfile.mkstemp(dir=dir_name, text=True)
    try:
        with io.open(fd, 'w', encoding='utf-8') as tmp:
            for obj, _ in objets:
                json.dump(obj, tmp, ensure_ascii=False)
                tmp.write('\n')
        os.replace(tmp_path, path)
    except Exception as e:
        sys.stderr.write(f"Erreur lors de l'ecriture du JSONL '{path}': {e}\n")
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        sys.exit(2)

def normaliser_ascii(texte):
    nf = unicodedata.normalize('NFD', texte)
    return ''.join(c for c in nf if not unicodedata.combining(c))

def reparer_indentation(avant_lines, cible_lines):
    indentations = []
    for av in avant_lines:
        stripped = av.strip()
        if not stripped:
            indentations.append('')
            continue
        matches = [l for l in cible_lines if l.strip() == stripped]
        if len(matches) == 0:
            return None, 'INTROUVABLE'
        if len(matches) > 1:
            return None, 'AMBIGU'
        # indentation = leading whitespace of the match
        leading = re.match(r'\s*', matches[0]).group()
        indentations.append(leading)
    # toutes les lignes ont une indentation unique
    return indentations, None

def reparer_accents(avant_lines, cible_lines):
    reparations = []
    for av in avant_lines:
        norm_av = normaliser_ascii(av).strip()
        matches = [l for l in cible_lines if normaliser_ascii(l).strip() == norm_av]
        if len(matches) == 0:
            return None, 'INTROUVABLE'
        if len(matches) > 1:
            return None, 'AMBIGU'
        reparations.append(matches[0])
    return reparations, None

def traiter_bloc(bloc_idx, avant, apres, cible_lines):
    avant_lines = avant.splitlines()
    apres_lines = apres.splitlines()
    # intact se juge sur des lignes entieres consecutives, pas par sous-chaine
    cible_entieres = [l.rstrip(chr(10)) for l in cible_lines]
    n = len(avant_lines)
    if n and any(cible_entieres[i:i + n] == avant_lines for i in range(len(cible_entieres) - n + 1)):
        return 'intact', None, None, avant, apres

    # 1. indentation
    indentations, err = reparer_indentation(avant_lines, cible_lines)
    if err is None:
        # appliquer indentation aux lignes d'apres
        repares_apres = []
        for i, line in enumerate(apres_lines):
            # on utilise l'indentation de la ligne correspondante de avant si possible,
            # sinon on garde l'indentation originale du modele
            ind = indentations[i] if i < len(indentations) else ''
            repares_apres.append(ind + line.lstrip())
        nouveau_apres = '\n'.join(repares_apres)
        return 'reparation indentation', avant, nouveau_apres, avant, nouveau_apres

    # une ambiguite d'indentation est deja un verdict : ne pas la masquer par
    # une tentative sur les accents qui rendrait INTROUVABLE.
    if err == 'AMBIGU':
        return 'AMBIGU', None, None, avant, apres

    # 2. accents
    repares_avant, err2 = reparer_accents(avant_lines, cible_lines)
    if err2 is None:
        nouveau_avant = '\n'.join(repares_avant)
        # on ne touche pas a l'indentation d'apres ici
        return 'reparation accents', nouveau_avant, apres, nouveau_avant, apres

    # impossible
    statut = 'AMBIGU' if err2 == 'AMBIGU' else 'INTROUVABLE'
    return statut, None, None, avant, apres

def main():
    parser = argparse.ArgumentParser(description='Repare les ancres des patches.')
    parser.add_argument('jsonl', help='Fichier JSONL contenant les rendus')
    parser.add_argument('nom_tache', help='Nom de la tache a reparer')
    parser.add_argument('cible', help='Fichier cible')
    parser.add_argument('--ecrire', action='store_true', help='Ecrire les corrections dans le JSONL')
    args = parser.parse_args()

    # charger cible
    try:
        with io.open(args.cible, 'r', encoding='utf-8') as f:
            cible_lines = f.readlines()
    except Exception as e:
        sys.stderr.write(f"Erreur lors de la lecture du fichier cible '{args.cible}': {e}\n")
        sys.exit(2)

    # charger jsonl
    objets = charger_jsonl(args.jsonl)

    # trouver l'entree
    idx_entry = None
    for i, (obj, _) in enumerate(objets):
        if obj.get('nom') == args.nom_tache:
            idx_entry = i
            break
    if idx_entry is None:
        sys.stderr.write(f"Tache '{args.nom_tache}' non trouvee dans le JSONL.\n")
        sys.exit(2)

    entry_obj, _ = objets[idx_entry]
    texte = entry_obj.get('texte', '')
    pattern = re.compile(r'<<<AVANT>>>(.*?)<<<APRES>>>(.*?)<<<FIN>>>', re.DOTALL)
    blocs = list(pattern.finditer(texte))

    if not blocs:
        sys.stderr.write("Aucun bloc trouve dans le champ 'texte'.\n")
        sys.exit(2)

    nb_intact = nb_indent = nb_accents = nb_ambig = nb_introuv = 0
    nouvelles_blocs = []
    for n, match in enumerate(blocs, start=1):
        avant = match.group(1)
        apres = match.group(2)
        statut, avant_corr, apres_corr, _, _ = traiter_bloc(n, avant, apres, cible_lines)
        if statut == 'intact':
            nb_intact += 1
        elif statut == 'reparation indentation':
            nb_indent += 1
        elif statut == 'reparation accents':
            nb_accents += 1
        elif statut == 'AMBIGU':
            nb_ambig += 1
        else:  # INTROUVABLE
            nb_introuv += 1
        print(f"bloc {n} : {statut}")
        # reconstruit le bloc avec corrections éventuelles
        nouveau_bloc = f'<<<AVANT>>>{avant_corr if avant_corr is not None else avant}<<<APRES>>>{apres_corr if apres_corr is not None else apres}<<<FIN>>>'
        nouvelles_blocs.append((match.start(), match.end(), nouveau_bloc))

    # reconstruire le texte si ecriture demandee
    if args.ecrire:
        texte_modif = texte
        # on remplace en partant de la fin pour ne pas perturber les indices
        for debut, fin, nouveau in sorted(nouvelles_blocs, key=lambda x: x[0], reverse=True):
            texte_modif = texte_modif[:debut] + nouveau + texte_modif[fin:]
        entry_obj['texte'] = texte_modif
        ecrire_jsonl_atomique(args.jsonl, objets)
        print("Fichier JSONL mis a jour.")

    total_impossible = nb_ambig + nb_introuv
    print(f"{nb_indent + nb_accents} repares, {nb_intact} intacts, {total_impossible} impossibles")
    sys.exit(0 if total_impossible == 0 else 1)

if __name__ == '__main__':
    main()