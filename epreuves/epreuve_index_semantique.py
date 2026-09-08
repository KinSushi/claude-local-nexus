# -*- coding: utf-8 -*-
"""Épreuve : vérifie que l'index sémantique n'est pas sur‑dupliqué.

L'index se trouve dans « .racine/.nexus/fragments_embeddings.jsonl ».  
Il doit contenir au plus le nombre total de fragments provenant des
quatre sources :
    references/livres/epub
    references/livres/packt
    references/livres/code
    references/livres_texte

Chaque source possède un fichier « index.tsv » (en‑tête + N lignes).  
Le test calcule :

    TOTAL_SOURCE = Σ (lignes‑1) sur les fichiers existants
    LIGNES_INDEX = nombre de lignes non vides de l'index

Si l'index est absent → OK.  
Sinon, si LIGNES_INDEX ≤ TOTAL_SOURCE × 1.05 → OK.  
Sinon → RATE (suspicion de duplication due à un append au lieu d'un truncate).

Le script ne dépend que de la bibliothèque standard (Python 3.8+).
"""

import os
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INDEX_PATH = os.path.join(RACINE, ".nexus", "fragments_embeddings.jsonl")
# Chemins EXACTS des 4 index.tsv sources (mesures sur le disque, pas devines).
SOURCE_INDEX = [
    os.path.join(RACINE, "references", "livres", "epub", "index.tsv"),
    os.path.join(RACINE, "references", "livres", "packt", "index.tsv"),
    os.path.join(RACINE, "references", "livres", "code", "index.tsv"),
    os.path.join(RACINE, "references", "livres_texte", "index.tsv"),
]

def _dire(ok: bool, nom: str, detail: str) -> bool:
    """Affiche le résultat d'un test."""
    print("%s %s : %s" % ("[OK  ]" if ok else "[RATE]", nom, detail))
    return ok

def _lignes_fichier(path: str) -> int:
    """Retourne le nombre de lignes (y compris l'en‑tête) d'un fichier texte."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return sum(1 for _ in f)
    except Exception:
        return 0  # fichier manquant ou illisible → compté comme 0

def _compte_lignes_index(path: str) -> int:
    """Compte les lignes non vides de l'index JSONL."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return sum(1 for line in f if line.strip())
    except Exception:
        return 0

def main() -> int:
    code = 0

    # 1. Calcul du nombre total de fragments sources
    total_source = 0
    for index_tsv in SOURCE_INDEX:
        lignes = _lignes_fichier(index_tsv)
        if lignes > 0:
            total_source += max(0, lignes - 1)  # on enleve l'en-tete
    # Si aucune source n'est trouvée, total_source reste 0 (test passera trivially)

    # 2. Cas où l'index est absent
    if not os.path.isfile(INDEX_PATH):
        _dire(True, "index absent (machine-locale)", "rien a verifier")
        return 0

    # 3. Comptage des lignes de l'index (non vides)
    lignes_index = _compte_lignes_index(INDEX_PATH)

    # 4. Vérification du seuil
    seuil = total_source * 1.05
    if lignes_index <= seuil:
        _dire(True, "lignes %d <= source %d (pas de sur-duplication)" % (lignes_index, total_source),
              "OK")
    else:
        _dire(False,
              "SUR-DUPLICATION : %d lignes > source %d (build a appende au lieu de tronquer ?)" % (
                  lignes_index, total_source),
              "ERREUR")
        code = 1

    return code

if __name__ == "__main__":
    sys.exit(main())
