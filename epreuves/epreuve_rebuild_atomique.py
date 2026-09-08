#!/usr/bin/env python3
"""
Test statique garantissant que le processus de construction de l'index
reste atomique.

Pourquoi ?
Le script ``nexus_livres_semantique.py`` construit l'index par lots.
Sans écriture atomique (promotion via ``os.replace``) un build concurrent
peut laisser l'index partiellement tronqué, ce qui rend la recherche
impossible.  Cette épreuve détecte les régressions suivantes :

* suppression du fichier temporaire ``TMP_FILE`` ;
* suppression de la promotion atomique ``os.replace(TMP_FILE, OUTPUT_FILE)`` ;
* réintroduction d'un truncate en place via ``open(OUTPUT_FILE, "w"…)`` ;
* écriture directe dans le fichier final au lieu du temporaire.

Si l'une de ces conditions manque, le test « RATE » échoue et le
processus de build doit être considéré comme non fiable.
"""

import os
import sys

def _read_source(path: str) -> str | None:
    """Retourne le contenu du fichier ou None en cas d'erreur."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return None

def _check_conditions(source: str) -> list[str]:
    """Vérifie les 4 exigences et renvoie la liste des messages manquants."""
    missing = []

    # a. définition de TMP_FILE
    if "TMP_FILE =" not in source:
        missing.append("définition de TMP_FILE")

    # b. promotion atomique
    if "os.replace(TMP_FILE, OUTPUT_FILE)" not in source:
        missing.append("promotion atomique via os.replace")

    # c. pas de truncate en place
    if 'open(OUTPUT_FILE, "w"' in source:
        missing.append('absence de truncate en place (open(OUTPUT_FILE, "w"))')

    # d. écriture dans le temporaire
    if 'open(TMP_FILE, "a"' not in source:
        missing.append("écriture en mode ajout sur TMP_FILE")

    return missing

def main() -> None:
    # 1. localisation du script cible
    racine = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    cible = os.path.join(racine, "scripts", "nexus_livres_semantique.py")

    # 2. lecture du source
    source = _read_source(cible)
    if source is None:
        sys.stdout.write("[RATE] rebuild atomique : source introuvable ou illisible\n")
        sys.exit(1)

    # 3. vérifications
    manquants = _check_conditions(source)

    # 4. sortie
    if not manquants:
        sys.stdout.write("[OK  ] rebuild atomique : toutes les vérifications passent\n")
        sys.exit(0)
    else:
        detail = ", ".join(manquants)
        sys.stdout.write(f"[RATE] rebuild atomique : {detail}\n")
        sys.exit(1)

if __name__ == "__main__":
    main()