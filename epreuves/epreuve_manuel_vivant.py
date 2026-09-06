# -*- coding: utf-8 -*-
"""Garantit que la dette documentaire des scripts ne croisse pas.

Le besoin derive d'un constat : les commentaires techniques s'evaporent
ou deviennent obsolètes, transformant le dépôt en une boîte noire.
L'objectif est d'imposer un 'manuel vivant' où chaque fichier explique
POURQUOI il existe, QUAND l'employer, COMMENT, et quelles DECISIONS
ont été prises, plutôt qu'une simple description de fonctions.

Ce cliquet ne bloque pas l'existence de fichiers non conformes (dette),
mais interdit l'ajout de nouveaux fichiers sans documentation.

Le contrôle vérifie :
  1. Présence d'un docstring de module avant tout code.
  2. Longueur minimale de 8 lignes (un résumé n'est pas un manuel).
  3. Présence d'une mesure (chiffre + unité) ou d'une date (2026-).
  4. Présence d'une décision ou limite (mots-clés : 'plutôt que', 'refuse', etc.).

L'état est stocké dans .nexus/manuel_vivant.json.
"""
import os
import re
import json
import sys
import argparse

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--liste", action="store_true")
    args = parser.parse_args()

    racine = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    scripts_dir = os.path.join(racine, "scripts")
    ref_path = os.path.join(racine, ".nexus", "manuel_vivant.json")

    # Identification des fichiers cibles
    fichiers = []
    for root, _, files in os.walk(scripts_dir):
        for f in files:
            if (f.startswith("nexus_") or f.startswith("epreuve_")) and f.endswith(".py"):
                fichiers.append(os.path.join(root, f))

    non_conformes = []
    for chemin in fichiers:
        with open(chemin, "r", encoding="utf-8") as fh:
            contenu = fh.read()

        # 1. Docstring de module (doit être au début, après éventuel encoding)
        # On nettoie le début pour ignorer le # -*- coding...
        clean_start = re.sub(r"^\s*#.*?\n", "", contenu)
        match_doc = re.match(r"^\s*([\"']{3}.*?[\"']{3})", clean_start, re.DOTALL)
        
        if not match_doc:
            non_conformes.append((chemin, "Pas de docstring de module"))
            continue
        
        doc = match_doc.group(1)
        
        # 2. Longueur (8 lignes min)
        if len(doc.splitlines()) < 8:
            non_conformes.append((chemin, "Trop court (< 8 lignes)"))
            continue
            
        # 3. Mesure ou Date
        # Chiffre suivi d'unité (ex: 10 Go, 5ms) ou date 2026- ou mots clés
        motif_mesure = r"(\d+\s*(Go|Mo|ko|ms|s|min|h|%|coeur))|(\d{4}-)|(mesure|mesuree|releve|constate)"
        if not re.search(motif_mesure, doc, re.I):
            non_conformes.append((chemin, "Pas de mesure ou date"))
            continue
            
        # 4. Limite ou Décision
        motif_decision = r"(limite|ne voit pas|ne couvre pas|refuse|rejete|plutot que|au lieu de|pourquoi)"
        if not re.search(motif_decision, doc, re.I):
            non_conformes.append((chemin, "Pas de décision ou limite"))
            continue

    compte_actuel = len(non_conformes)

    # Gestion du cliquet
    if not os.path.exists(os.path.dirname(ref_path)):
        os.makedirs(os.path.dirname(ref_path))

    if not os.path.exists(ref_path):
        with open(ref_path, "w", encoding="utf-8") as fh:
            json.dump({"ref": compte_actuel}, fh)
        print(f"Première pose du cliquet : référence fixée à {compte_actuel}")
        ref_val = compte_actuel
    else:
        with open(ref_path, "r", encoding="utf-8") as fh:
            ref_val = json.load(fh).get("ref", 0)

    if args.liste:
        for f, err in non_conformes:
            print(f"{f} : {err}")
        return 0

    print(f"Non conformes : {compte_actuel} (Réf : {ref_val})")
    
    if compte_actuel > ref_val:
        print(f"[RATE] dette documentaire : {compte_actuel} non conformes, reference {ref_val} — la dette a AUGMENTE")
    else:
        print(f"[OK  ] dette documentaire : {compte_actuel} non conformes, reference {ref_val}")
    print(f"[OK  ] cliquet arme : reference {ref_val}")

    if compte_actuel > ref_val:
        print("\nERREUR : La dette documentaire a augmenté !")
        for f, err in non_conformes[:10]:
            print(f"  - {os.path.relpath(f, racine)} : {err}")
        if compte_actuel > 10:
            print(f"  ... et {compte_actuel - 10} autres.")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())