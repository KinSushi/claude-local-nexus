#!/usr/bin/env python3
"""outillage/nexus_paires.py

Outils de vérification et de synchronisation des fichiers dupliqués
entre les répertoires ``scripts`` et ``outillage`` d’un dépôt.

Fonctions principales :

* ``paires(racine)`` – renvoie la liste triée des noms ``*.py`` présents
  dans les deux répertoires.
* ``normaliser(octets)`` – convertit les fins de ligne CRLF et CR en LF.
* ``divergentes(racine)`` – renvoie les noms dont le contenu normalisé diffère.
* ``lignes_propres(copie, source, seuil=12)`` – lignes « propres » de la copie
  (strip, longueur ≥ *seuil*) absentes de la source.
* ``synchroniser(racine, nom, forcer=False)`` – copie atomique du fichier source
  vers la copie si aucune ligne propre n’est détectée ou si ``forcer`` est
  vrai.
* ``main(argv=None)`` – interface en ligne de commande.

Aucun effet de bord n’est produit à l’import du module.
"""

from __future__ import annotations

import argparse
import contextlib
import os
import sys
import tempfile
from pathlib import Path
from typing import List, Tuple

# --------------------------------------------------------------------------- #
# Constante racine du projet (deux niveaux au‑dessus de ce fichier)
RACINE: Path = Path(__file__).resolve().parent.parent
# --------------------------------------------------------------------------- #


def paires(racine: Path) -> List[str]:
    """Retourne la liste triée des noms ``*.py`` présents à la fois dans
    ``racine/scripts`` et ``racine/outillage`` (fichiers directs uniquement)."""
    scripts_dir = racine / "scripts"
    outillage_dir = racine / "outillage"

    if not scripts_dir.is_dir() or not outillage_dir.is_dir():
        return []

    scripts = {p.name for p in scripts_dir.iterdir() if p.is_file() and p.suffix == ".py"}
    outillage = {p.name for p in outillage_dir.iterdir() if p.is_file() and p.suffix == ".py"}

    return sorted(scripts & outillage)


def normaliser(octets: bytes) -> bytes:
    """Normalise les fins de ligne : CRLF → LF puis CR → LF."""
    return octets.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def _contenu_normalise(fichier: Path) -> bytes | None:
    """Lit *fichier* en binaire et renvoie son contenu normalisé.
    Retourne ``None`` en cas d’erreur de lecture."""
    try:
        return normaliser(fichier.read_bytes())
    except OSError:
        return None


def divergentes(racine: Path) -> List[str]:
    """Renvoie la liste des noms de paires dont le contenu normalisé diffère."""
    result: List[str] = []
    for nom in paires(racine):
        src = racine / "scripts" / nom
        dst = racine / "outillage" / nom
        src_c = _contenu_normalise(src)
        dst_c = _contenu_normalise(dst)
        if src_c is None or dst_c is None or src_c != dst_c:
            result.append(nom)
    return result


def lignes_propres(copie: List[str], source: List[str], seuil: int = 12) -> List[str]:
    """Renvoie les lignes de *copie* (strip, longueur ≥ *seuil*) qui n’apparaissent
    pas, après strip, dans *source*.

    Les lignes retournées sont les versions stripées.
    """
    source_set = {ln.strip() for ln in source}
    propres: List[str] = []
    for ln in copie:
        stripped = ln.strip()
        if len(stripped) >= seuil and stripped not in source_set:
            propres.append(stripped)
    return propres


def synchroniser(racine: Path, nom: str, forcer: bool = False) -> Tuple[bool, List[str]]:
    """Synchronise le fichier ``scripts/<nom>.py`` vers ``outillage/<nom>.py``.

    * Si aucune ligne propre n’est détectée ou si ``forcer`` est vrai,
      la copie est réalisée de façon atomique (tempfile + ``os.replace``) et
      la fonction renvoie ``(True, [])`` (ou les lignes propres si ``forcer``).
    * Sinon, aucune modification n’est faite et la fonction renvoie
      ``(False, lignes_propres)``.
    """
    fichier = nom if nom.endswith(".py") else f"{nom}.py"  # accepte le nom avec ou sans extension, divergentes() rend les noms avec
    src_path = racine / "scripts" / fichier
    dst_path = racine / "outillage" / fichier

    # Lecture du source (bytes) – on suppose qu’il existe.
    try:
        src_bytes = src_path.read_bytes()
    except OSError as exc:
        print(f"[RATE] impossible de lire la source {src_path} : {exc}", file=sys.stderr)
        return False, []

    # Lecture de la copie (texte) pour détecter les lignes propres.
    if dst_path.is_file():
        try:
            dst_text = dst_path.read_text(encoding="utf-8", errors="replace")
            dst_lines = dst_text.splitlines()
        except OSError as exc:
            print(f"[RATE] impossible de lire la copie {dst_path} : {exc}", file=sys.stderr)
            dst_lines = []
    else:
        dst_lines = []

    src_text = src_bytes.decode("utf-8", errors="replace")
    src_lines = src_text.splitlines()

    propres = lignes_propres(dst_lines, src_lines)

    # Décision de copie
    if forcer or not propres:
        # Copie atomique
        out_dir = dst_path.parent
        fd, tmp_path = tempfile.mkstemp(prefix=nom + "_", suffix=".py", dir=out_dir)
        try:
            with os.fdopen(fd, "wb") as tmp_file:
                tmp_file.write(src_bytes)
            os.replace(tmp_path, dst_path)
        finally:
            # Nettoyage en cas d’échec
            if os.path.exists(tmp_path):
                with contextlib.suppress(OSError):
                    os.unlink(tmp_path)
        return True, (propres if forcer else [])
    return False, propres


def _afficher_lignes_propres(nom: str, lignes: List[str]) -> None:
    """Affiche les lignes propres (troncature à 150 caractères)."""
    nb = len(lignes)
    print(f"REFUS {nom} : {nb} ligne(s) propres a outillage/")
    for ln in lignes:
        affichage = (ln[:150] + "…") if len(ln) > 150 else ln
        print(affichage)


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Vérifie et synchronise les paires de fichiers dupliqués."
    )
    parser.add_argument(
        "--racine",
        type=Path,
        default=RACINE,
        help="Chemin racine du projet (défaut : %(default)s).",
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--verifier",
        action="store_true",
        help="Vérifie l’intégrité des paires et affiche le résultat.",
    )
    group.add_argument(
        "--synchroniser",
        nargs="*",
        metavar="NOM",
        help="Synchronise les paires indiquées (ou toutes les divergentes si aucun nom).",
    )
    parser.add_argument(
        "--forcer",
        action="store_true",
        help="Force l’écrasement même en présence de lignes propres.",
    )

    args = parser.parse_args(argv)

    racine: Path = args.racine

    # Aucun mode sélectionné → usage
    if not (args.verifier or args.synchroniser is not None):
        parser.print_help()
        return 2

    if args.verifier:
        diverg = divergentes(racine)
        total = len(paires(racine))
        if diverg:
            print("[RATE] paires copiees : divergent -> " + ", ".join(diverg))
            return 1
        print(f"[OK  ] paires copiees : {total} paires identiques")
        return 0

    # Mode synchronisation
    noms: List[str]
    if args.synchroniser is None:
        # Ne devrait jamais arriver (mutually exclusive), mais on protège.
        parser.print_help()
        return 2
    # Sans nom : toutes les paires divergentes.
    noms = divergentes(racine) if len(args.synchroniser) == 0 else args.synchroniser

    refus = False
    for nom in noms:
        ok, lignes = synchroniser(racine, nom, forcer=args.forcer)
        if ok:
            if args.forcer and lignes:
                # Affichage des lignes propres avant écrasement
                print(f"FORCE {nom} : {len(lignes)} ligne(s) propres a outillage/")
                for ln in lignes:
                    affichage = (ln[:150] + "…") if len(ln) > 150 else ln
                    print(affichage)
        else:
            refus = True
            _afficher_lignes_propres(nom, lignes)

    return 1 if refus else 0


if __name__ == "__main__":
    sys.exit(main())
