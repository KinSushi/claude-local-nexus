#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
nexus_pull_garde.py

Garde‑fou autour de ``ollama pull``.  Il interroge le registre Ollama pour
connaître le poids d’un modèle, puis utilise le module
``nexus_capability`` (exposé sous le nom ``capability``) pour décider
s’il est possible de le télécharger.

Fonctions publiques :
    - taille_distante(modele_tag) → float|None
    - decision(size_gb, profile) → (etat, autorise, motif)
    - garder(modele_tag, faire_pull=False, profile=None) → str

Exécution directe :
    python nexus_pull_garde.py <nom:tag> [--pull] [--epreuve]

Codes de sortie :
    0 : AUTORISE
    1 : INDETERMINE
    2 : REFUSE
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
import subprocess
from typing import Tuple, Optional

# Import du module existant sans le modifier.
import nexus_capability as capability

# ----------------------------------------------------------------------
# Constantes
# ----------------------------------------------------------------------
_ACCEPTED = "AUTORISE"
_REFUSED = "REFUSE"
_UNKNOWN = "INDETERMINE"

# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------
def _root_dir() -> str:
    """Répertoire racine dérivé de ce fichier (sans effets de bord)."""
    return os.path.abspath(os.path.dirname(__file__))


# ----------------------------------------------------------------------
# API publique
# ----------------------------------------------------------------------
def taille_distante(modele_tag: str) -> Optional[float]:
    """
    Retourne le poids (en Go décimaux) du modèle indiqué par ``modele_tag``
    (format ``nom:tag``) en interrogeant le registre Ollama.

    En cas d’échec réseau, d’erreur HTTP ou de format inattendu, renvoie
    ``None``.  Aucun exception n’est propagée.
    """
    try:
        if ':' not in modele_tag:
            return None
        nom, tag = modele_tag.split(':', 1)
        url = f"https://registry.ollama.ai/v2/library/{nom}/manifests/{tag}"
        req = urllib.request.Request(url)
        req.add_header(
            "Accept",
            "application/vnd.docker.distribution.manifest.v2+json",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status != 200:
                return None
            data = json.load(resp)
    except (urllib.error.URLError, urllib.error.HTTPError, ValueError, json.JSONDecodeError):
        return None
    except Exception:
        return None

    try:
        total_bytes = 0
        # ``layers`` est une liste de dicts contenant ``size`` en octets.
        for layer in data.get("layers", []):
            total_bytes += int(layer.get("size", 0))
        # ``config`` possède également un champ ``size``.
        config = data.get("config", {})
        total_bytes += int(config.get("size", 0))
        return total_bytes / 1e9  # conversion décimale Go
    except Exception:
        return None


def decision(
    size_gb: Optional[float], profile: dict
) -> Tuple[str, Optional[bool], str]:
    """
    Décide du statut d’un téléchargement à partir du poids et du profil.

    Retourne un tuple ``(etat, autorise, motif)`` où :

    * ``etat``   ∈ {AUTORISE, REFUSE, INDETERMINE}
    * ``autorise`` est ``True``/``False``/``None`` correspondant à la
      réponse de ``capability.can_download``.
    * ``motif``  chaîne explicative provenant de ``can_download`` ou d’une
      règle interne.
    """
    if size_gb is None:
        return (_UNKNOWN, None, "poids inconnu – décision indéterminée")
    ok, motif = capability.can_download(size_gb, profile)
    if ok is True:
        return (_ACCEPTED, True, motif)
    if ok is False:
        return (_REFUSED, False, motif)
    # ok is None
    return (_UNKNOWN, None, motif)


def garder(modele_tag: str, faire_pull: bool = False, profile: Optional[dict] = None) -> str:
    """
    Applique la garde‑fou avant d’éventuellement lancer ``ollama pull``.

    * ``profile`` : si ``None`` le profil est construit via
      ``capability.build_profile()``.
    * ``faire_pull`` : si ``True`` et que la décision est AUTORISE,
      le modèle est téléchargé avec ``subprocess.run``.
    * Retourne l’état (AUTORISE, REFUSE ou INDETERMINE) sous forme de chaîne.
    """
    if profile is None:
        profile = capability.build_profile()
    size = taille_distante(modele_tag)
    etat, autorise, motif = decision(size, profile)

    print(f"{modele_tag} : {etat} ({motif})")

    if faire_pull and etat == _ACCEPTED:
        # Exécution du pull – aucune exception n’est levée, on ignore le
        # code retour du sous‑processus (le garde‑fou a déjà validé).
        subprocess.run(["ollama", "pull", modele_tag], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    return etat


# ----------------------------------------------------------------------
# Tests autonomes (--epreuve)
# ----------------------------------------------------------------------
def _profil_test() -> dict:
    """
    Construit un profil minimal suffisant pour les tests de décision.
    Les valeurs sont choisies de façon à ce que :

    * 1 Go soit autorisé,
    * 500 Go soit refusé (dépassant le runnable_budget_gb),
    * le disque soit largement suffisant.
    """
    return {
        "disque_mesure": True,
        "free_disk_gb": 1000.0,          # disque largement disponible
        "runnable_budget_gb": 100.0,    # seuil au‑delà duquel on refuse
        "pool_budget_gb": 200.0,        # non utilisé dans les tests
        "inference_memory_gb": 200.0,    # non utilisé dans les tests
    }


def _epreuve() -> int:
    """
    Exécute les trois scénarios décrits dans la spécification.
    Retourne 0 si tous passent, sinon 1.
    """
    profile = _profil_test()

    # 1. Forward – petite taille autorisée
    etat, ok, _ = decision(1.0, profile)
    if not (etat == _ACCEPTED and ok is True):
        return 1

    # 2. Reverse – taille énorme refusée
    etat, ok, _ = decision(500.0, profile)
    if not (etat == _REFUSED and ok is False):
        return 1

    # 3. Indéterminé – taille inconnue
    etat, ok, _ = decision(None, profile)
    if not (etat == _UNKNOWN and ok is None):
        return 1

    return 0


# ----------------------------------------------------------------------
# Interface en ligne de commande
# ----------------------------------------------------------------------
def _cli() -> int:
    parser = argparse.ArgumentParser(
        description="Garde‑fou avant ``ollama pull``."
    )
    parser.add_argument(
        "modele_tag",
        nargs="?",
        help="Modèle à télécharger, sous la forme nom:tag",
    )
    parser.add_argument(
        "--pull",
        action="store_true",
        help="Effectuer le pull si la décision est AUTORISE",
    )
    parser.add_argument(
        "--epreuve",
        action="store_true",
        help="Lancer les tests autonomes de la fonction decision()",
    )
    args = parser.parse_args()

    if args.epreuve:
        return _epreuve()

    if not args.modele_tag:
        parser.error("le paramètre <modele:tag> est requis")

    etat = garder(args.modele_tag, faire_pull=args.pull)

    # Mapping des codes de sortie demandés.
    if etat == _ACCEPTED:
        return 0
    if etat == _UNKNOWN:
        return 1
    return 2


if __name__ == "__main__":
    sys.exit(_cli())