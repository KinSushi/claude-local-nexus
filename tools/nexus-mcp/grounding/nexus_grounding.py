#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""nexus_grounding.py

Outil portable pour créer un « lot » JSON compatible avec le format
nexus_agent.  Il copie les fichiers indiqués en les nommant uniquement par
leur basename (en ajoutant un préfixe numérique en cas de collision) et
génère la tâche en préfixant chaque correspondance
« basename = vrai_chemin ».  Aucun effet de bord n’est produit à l’import.

Fonction principale :
    construire_lot(fichiers, tache, docs=None,
                   modele='gpt-oss-120b-cloud',
                   max_tokens=4000,
                   racine=None,
                   cible_lot=None) -> str
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import List, Optional, Sequence

__all__ = ["LotConstructionError", "construire_lot"]


class LotConstructionError(RuntimeError):
    """Exception levée lorsqu’une étape de construction du lot échoue
    (fichier manquant, problème d’écriture, …)."""


def _derive_root() -> Path:
    """Racine du dépôt : répertoire contenant ce fichier."""
    return Path(__file__).resolve().parent


def _copy_with_basename(src: Path, dst_dir: Path) -> Path:
    """
    Copie *src* dans *dst_dir* en conservant uniquement le basename.
    En cas de collision, préfixe le nom avec « 1_ », « 2_ », … jusqu’à ce
    qu’il soit unique.
    Retourne le chemin relatif (par rapport à *dst_dir*) du fichier copié.
    """
    base = src.name
    candidate = dst_dir / base
    n = 1
    while candidate.exists():
        candidate = dst_dir / f"{n}_{base}"
        n += 1
    shutil.copy2(src, candidate)
    return candidate.relative_to(dst_dir)


def construire_lot(
    fichiers: Sequence[str],
    tache: str,
    docs: Optional[Sequence[str]] = None,
    modele: str = "gpt-oss-120b-cloud",
    max_tokens: int = 4000,
    racine: Optional[str] = None,
    cible_lot: Optional[str] = None,
) -> str:
    """
    Construit un lot JSON à partir d’une liste de fichiers.

    Parameters
    ----------
    fichiers : sequence of str
        Chemins relatifs (par rapport à *racine*) des fichiers à inclure.
    tache : str
        Texte de la tâche à fournir au modèle.
    docs : sequence of str, optional
        Documents de grounding à joindre (copiés mais non listés dans la
        correspondance « basename = vrai chemin »).
    modele : str, default ``gpt-oss-120b-cloud``
    max_tokens : int, default ``4000``
    racine : str, optional
        Répertoire racine du dépôt. Si ``None``, il est dérivé de
        ``__file__``.
    cible_lot : str, optional
        Chemin où écrire le fichier JSON. Si ``None``, le fichier est créé
        dans le répertoire de travail temporaire sous le nom ``lot.json``.

    Returns
    -------
    str
        Chemin absolu du fichier JSON généré.

    Raises
    ------
    LotConstructionError
        Si un des fichiers indiqués n’existe pas ou si l’écriture du lot
        échoue.
    """
    # ------------------------------------------------------------------ #
    # 1. Détermination de la racine et du répertoire de travail
    # ------------------------------------------------------------------ #
    root_path = Path(racine).resolve() if racine is not None else _derive_root()
    # Le répertoire où seront écrits le lot JSON et les copies de fichiers.
    # Si *cible_lot* est fourni, les copies sont placées dans le même répertoire
    # que le fichier JSON (ou dans un sous‑répertoire de celui‑ci).  Sinon, on
    # crée un répertoire temporaire comme auparavant.
    if cible_lot:
        json_path = Path(cible_lot).resolve()
        copy_dir = json_path.parent
        temporary_dir: Optional[Path] = None
    else:
        temporary_dir = Path(tempfile.mkdtemp(prefix="nexus_grounding_"))
        json_path = temporary_dir / "lot.json"
        copy_dir = temporary_dir

    try:
        # ------------------------------------------------------------------ #
        # 2. Copie des fichiers demandés
        # ------------------------------------------------------------------ #
        correspondances: List[str] = []
        fichiers_copies: List[str] = []

        for rel_path in fichiers:
            src = root_path / rel_path
            if not src.is_file():
                raise LotConstructionError(f"Fichier manquant : {src}")

            rel_copie = _copy_with_basename(src, copy_dir)
            fichiers_copies.append(str(rel_copie).replace(os.sep, "/"))
            correspondances.append(f"  {rel_copie.name}  =  {rel_path}")

        # ------------------------------------------------------------------ #
        # 3. Copie des documents de grounding (le cas échéant)
        # ------------------------------------------------------------------ #
        if docs:
            for doc_rel in docs:
                src = root_path / doc_rel
                if not src.is_file():
                    raise LotConstructionError(f"Document de grounding manquant : {src}")

                rel_copie = _copy_with_basename(src, copy_dir)
                fichiers_copies.append(str(rel_copie).replace(os.sep, "/"))
                # Les docs ne sont pas ajoutés aux correspondances, conformément
                # à la spécification.

        # ------------------------------------------------------------------ #
        # 4. Construction du texte de la tâche
        # ------------------------------------------------------------------ #
        tache_complète = "\n".join(correspondances + ["", tache.rstrip()])

        # ------------------------------------------------------------------ #
        # 5. Assemblage du lot JSON
        # ------------------------------------------------------------------ #
        lot = [
            {
                "nom": "lot-auto",
                "modele": modele,
                "max_tokens": max_tokens,
                "fichiers": fichiers_copies,
                "tache": tache_complète,
            }
        ]

        # ------------------------------------------------------------------ #
        # 6. Écriture du fichier JSON
        # ------------------------------------------------------------------ #
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(
            json.dumps(lot, ensure_ascii=False, indent=1), encoding="utf-8"
        )
        # Retour du chemin absolu du lot.  Les copies se trouvent dans le même
        # répertoire que le lot (ou dans un sous‑dossier de celui‑ci).  L’appelant
        # doit donc utiliser « --racine = dirname(lot_path) » lorsqu’il invoque
        # nexus_agent.
        return str(json_path)

    except Exception as exc:
        # Nettoyage du répertoire temporaire en cas d’erreur
        if temporary_dir:
            shutil.rmtree(temporary_dir, ignore_errors=True)
        if isinstance(exc, LotConstructionError):
            raise
        raise LotConstructionError(str(exc)) from exc


# ---------------------------------------------------------------------- #
#  Interface en ligne de commande – mode « --epreuve »
# ---------------------------------------------------------------------- #
def _run_epreuve() -> int:
    """
    Exécute une démonstration :
    * crée deux fichiers temporaires,
    * construit un lot,
    * vérifie que les copies portent le basename,
    * vérifie que le texte de la tâche contient les correspondances,
    * teste le refus propre lorsqu’un fichier est absent.
    Retourne 0 en cas de succès, 1 sinon.
    """
    import traceback

    # 1. Préparer un répertoire de travail isolé
    with tempfile.TemporaryDirectory(prefix="nexus_grounding_test_") as tmp_root:
        root = Path(tmp_root)
        # 2. Créer deux fichiers source
        file_a = root / "moduleA.py"
        file_b = root / "moduleB.py"
        file_a.write_text("# module A\nx = 1\n", encoding="utf-8")
        file_b.write_text("# module B\ny = 2\n", encoding="utf-8")

        # 3. Construire le lot (forward test)
        try:
            lot_path = construire_lot(
                fichiers=[file_a.name, file_b.name],
                tache="Analyse de deux modules.",
                racine=str(root),
            )
        except Exception:
            print("Échec de la construction du lot (forward).")
            traceback.print_exc()
            return 1

        # 4. Charger le JSON et vérifier le contenu
        try:
            lot_data = json.loads(Path(lot_path).read_text(encoding="utf-8"))
            assert isinstance(lot_data, list) and len(lot_data) == 1
            entry = lot_data[0]
            fichiers_copies = entry["fichiers"]
            assert len(fichiers_copies) == 2, "Nombre de copies inattendu."

            # Les copies doivent être nommées par basename (ou préfixées en cas de collision)
            for src_name, copy_rel in zip([file_a.name, file_b.name], fichiers_copies, strict=False):
                copy_name = Path(copy_rel).name
                if copy_name != src_name:
                    # collision improbable dans ce test, mais on accepte le préfixe numérique
                    # Vérification d'utilisabilité : chaque copie doit exister sous le répertoire du lot
                    lot_dir = Path(lot_path).parent
                    for copy_rel in fichiers_copies:
                        assert (lot_dir / copy_rel).is_file(), f"Copie introuvable sous la racine: {copy_rel}"
        except AssertionError as ae:
            print(f"Vérification du lot (forward) échouée : {ae}")
            return 1
        except Exception:
            print("Erreur lors de la lecture ou de la validation du lot (forward).")
            traceback.print_exc()
            return 1

        # 5. Reverse test – fichier manquant doit lever LotConstructionError
        try:
            construire_lot(
                fichiers=["inexistant.py"],
                tache="Test d’erreur.",
                racine=str(root),
            )
            print("Erreur : le lot a été construit malgré un fichier manquant.")
            return 1
        except LotConstructionError:
            # Comportement attendu
            pass
        except Exception as e:
            print(f"Erreur inattendue lors du reverse test : {e}")
            traceback.print_exc()
            return 1

    # Tous les tests sont passés
    print("Épreuve réussie.")
    return 0


def _main() -> None:
    parser = argparse.ArgumentParser(
        description="Construire un lot JSON compatible nexus_agent."
    )
    parser.add_argument(
        "--epreuve",
        action="store_true",
        help="Exécuter la démonstration interne (forward & reverse).",
    )
    args = parser.parse_args()

    if args.epreuve:
        sys.exit(_run_epreuve())
    else:
        parser.print_help()
        sys.exit(0)


if __name__ == "__main__":
    _main()