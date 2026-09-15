#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""nexus_lot_controle.py — contrôle des arrêts de lots cloud.

Ce module permet de demander, consulter et effacer des arrêts pour des lots identifiés
par un `lot_id` au format `<pid>-<epoch>`. Les opérations sont atomiques et persistantes
dans un dossier dédié (`<RACINE_VERROUS>/arrets`).

Fonctions principales :
- `dossier_arrets()` : chemin du dossier de stockage.
- `demander_arret(lot_id, motif, dossier=None)` : demande un arrêt.
- `arret_demande(lot_id, dossier=None)` : consulte un arrêt.
- `effacer_arret(lot_id, dossier=None)` : efface un arrêt.
- `sonder_cloud(appel, delai_s, horloge=time.monotonic)` : sonde une ressource cloud.
- `attendre_cloud_sain(appel, delai_s, pas_s, attente_max_s, annoncer=None,
  dormir=time.sleep, horloge=time.monotonic)` : attend qu'une ressource cloud soit saine,
  en annonçant chaque tentative, y compris la réussite.

CLI :
- `arreter <lot_id> [--motif]` : demande un arrêt.
- `effacer <lot_id>` : efface un arrêt.
- `etat` : affiche l'état des arrêts.
"""

import os
import re
import json
import time
import sys
from datetime import datetime
from typing import Dict, Any, Optional, Callable
from contextlib import suppress

with suppress(Exception):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Constante pour valider le format du lot_id
LOT_ID = re.compile(r"^\d+-\d+$")

def dossier_arrets() -> str:
    """Retourne le chemin du dossier de stockage des arrêts.

    Le dossier est `<RACINE_VERROUS>/arrets`, où `RACINE_VERROUS` est importé de
    `nexus_verrou_machine` si disponible, ou dérivé depuis `__file__` sinon.
    """
    try:
        from nexus_verrou_machine import RACINE_VERROUS
    except ImportError:
        # Dérivation depuis __file__ (même logique que dans verrou_machine.py)
        RACINE_VERROUS = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            '.nexus', 'verrous'
        )
    return os.path.join(RACINE_VERROUS, 'arrets')

def demander_arret(lot_id: str, motif: str, dossier: Optional[str] = None) -> str:
    """Demande un arrêt pour le lot `lot_id` avec un motif.

    Args:
        lot_id: Identifiant du lot au format `<pid>-<epoch>`.
        motif: Raison de l'arrêt (chaîne non vide).
        dossier: Chemin du dossier de stockage (par défaut : `dossier_arrets()`).

    Returns:
        Chemin absolu du fichier JSON créé.

    Raises:
        ValueError: Si `lot_id` est invalide ou `motif` est vide.
    """
    if not LOT_ID.fullmatch(lot_id):
        raise ValueError(f"lot_id invalide : doit être au format <pid>-<epoch>, reçu '{lot_id}'")
    if not motif:
        raise ValueError("motif ne peut pas être vide")

    dossier = dossier or dossier_arrets()
    os.makedirs(dossier, exist_ok=True)
    chemin = os.path.join(dossier, f"{lot_id}.json")

    # Écriture atomique
    tmp_chemin = f"{chemin}.tmp"
    fiche = {
        "lot_id": lot_id,
        "motif": motif,
        "demande_par_pid": os.getpid(),
        "depuis": datetime.now().isoformat(timespec='seconds')
    }
    with open(tmp_chemin, 'w', encoding='utf-8') as f:
        json.dump(fiche, f, ensure_ascii=False)
    os.replace(tmp_chemin, chemin)
    return chemin

def arret_demande(lot_id: str, dossier: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Consulte l'arrêt demandé pour `lot_id`.

    Args:
        lot_id: Identifiant du lot.
        dossier: Chemin du dossier de stockage (par défaut : `dossier_arrets()`).

    Returns:
        Dictionnaire des métadonnées de l'arrêt si trouvé, `None` sinon.
        Ne lève jamais d'exception.
    """
    if not LOT_ID.fullmatch(lot_id):
        return None

    dossier = dossier or dossier_arrets()
    chemin = os.path.join(dossier, f"{lot_id}.json")
    try:
        with open(chemin, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None

def effacer_arret(lot_id: str, dossier: Optional[str] = None) -> bool:
    """Efface l'arrêt demandé pour `lot_id`.

    Args:
        lot_id: Identifiant du lot.
        dossier: Chemin du dossier de stockage (par défaut : `dossier_arrets()`).

    Returns:
        `True` si l'arrêt a été effacé, `False` s'il n'existait pas.
    """
    if not LOT_ID.fullmatch(lot_id):
        return False

    dossier = dossier or dossier_arrets()
    chemin = os.path.join(dossier, f"{lot_id}.json")
    try:
        os.remove(chemin)
        return True
    except FileNotFoundError:
        return False

def sonder_cloud(
    appel: Callable[[], Dict[str, Any]],
    delai_s: float,
    horloge: Callable[[], float] = time.monotonic
) -> Dict[str, Any]:
    """Sonde une ressource cloud via `appel` avec un délai maximal.

    Args:
        appel: Fonction sans argument retournant un dictionnaire avec les clés
               `ok`, `duree_s`, et `erreur`.
        delai_s: Délai maximal en secondes pour l'appel.
        horloge: Fonction retournant le temps courant (par défaut : `time.monotonic`).

    Returns:
        Dictionnaire avec les clés :
        - `ok` (bool) : `True` si l'appel a réussi et respecté le délai.
        - `duree_s` (float) : Durée de l'appel.
        - `erreur` (str) : Message d'erreur si `ok` est `False`.
        Ne lève jamais d'exception.
    """
    debut = horloge()
    try:
        resultat = appel()
        duree = horloge() - debut
        if duree > delai_s:
            return {
                "ok": False,
                "duree_s": duree,
                "erreur": f"délai dépassé ({duree:.3f}s > {delai_s:.3f}s)"
            }
        return {
            "ok": resultat.get("ok", False),
            "duree_s": duree,
            "erreur": resultat.get("erreur", "")
        }
    except Exception as e:
        duree = horloge() - debut
        return {
            "ok": False,
            "duree_s": duree,
            "erreur": str(e)
        }

def attendre_cloud_sain(
    appel: Callable[[], Dict[str, Any]],
    delai_s: float,
    pas_s: float,
    attente_max_s: float,
    annoncer: Optional[Callable[[str], None]] = None,
    dormir: Callable[[float], None] = time.sleep,
    horloge: Callable[[], float] = time.monotonic
) -> Dict[str, Any]:
    """Attend qu'une ressource cloud soit saine via des appels répétés.

    Annonce chaque tentative, y compris la réussite.

    Args:
        appel: Fonction sans argument retournant un dictionnaire avec les clés
               `ok`, `duree_s`, et `erreur`.
        delai_s: Délai maximal en secondes pour chaque appel.
        pas_s: Intervalle entre les tentatives.
        attente_max_s: Temps maximal total d'attente.
        annoncer: Fonction pour annoncer les tentatives (par défaut : aucune).
        dormir: Fonction pour attendre (par défaut : `time.sleep`).
        horloge: Fonction retournant le temps courant (par défaut : `time.monotonic`).

    Returns:
        Dictionnaire avec les clés :
        - `ok` (bool) : `True` si une tentative a réussi.
        - `tentatives` (int) : Nombre de tentatives.
        - `duree_totale_s` (float) : Durée totale d'attente.
        - `derniere` (dict) : Résultat de la dernière tentative.
        Ne lève jamais d'exception.
    """
    debut = horloge()
    tentatives = 0
    derniere = {}

    while True:
        tentatives += 1
        derniere = sonder_cloud(appel, delai_s, horloge)

        # Annonce de la tentative, succès ou échec
        if annoncer is not None:
            if derniere["ok"]:
                annoncer(f"Tentative {tentatives} : reussie (durée {derniere['duree_s']:.3f}s)")
            else:
                annoncer(f"Tentative {tentatives} : {derniere['erreur']} (durée {derniere['duree_s']:.3f}s)")

        if derniere["ok"]:
            break

        duree_totale = horloge() - debut
        if duree_totale >= attente_max_s:
            break
        dormir(pas_s)

    return {
        "ok": derniere["ok"],
        "tentatives": tentatives,
        "duree_totale_s": horloge() - debut,
        "derniere": derniere
    }

def main() -> None:
    """Point d'entrée CLI."""
    import argparse
    import sys

    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--arreter', metavar='LOT_ID',
                       help='Demande un arrêt pour le lot.')
    group.add_argument('--effacer', metavar='LOT_ID',
                       help='Efface un arrêt pour le lot.')
    group.add_argument('--etat', action='store_true',
                       help='Affiche l’état des arrêts.')
    parser.add_argument('--motif', default='demande manuelle',
                        help='Motif de l’arrêt (défaut « demande manuelle »).')

    args = parser.parse_args()

    # Validation du lot_id lorsqu’il est fourni
    if args.arreter:
        if not LOT_ID.fullmatch(args.arreter):
            print("Erreur : lot_id invalide, doit être au format <pid>-<epoch>", file=sys.stderr)
            sys.exit(2)
        try:
            demander_arret(args.arreter, args.motif)
            print(f"Arrêt demandé pour le lot {args.arreter}.")
        except ValueError as e:
            print(f"Erreur : {e}", file=sys.stderr)
            sys.exit(2)

    elif args.effacer:
        if not LOT_ID.fullmatch(args.effacer):
            print("Erreur : lot_id invalide, doit être au format <pid>-<epoch>", file=sys.stderr)
            sys.exit(2)
        if effacer_arret(args.effacer):
            print(f"Arrêt effacé pour le lot {args.effacer}.")
        else:
            print(f"Aucun arrêt trouvé pour le lot {args.effacer}.", file=sys.stderr)

    elif args.etat:
        dossier = dossier_arrets()
        fichiers = []
        with suppress(FileNotFoundError):
            fichiers = os.listdir(dossier)
        if not fichiers:
            print("Aucun arrêt en cours.")
        else:
            print(f"Arrêts en cours ({len(fichiers)}):")
            for fichier in fichiers:
                if fichier.endswith('.json'):
                    lot_id = fichier[:-5]
                    fiche = arret_demande(lot_id)
                    if fiche:
                        print(f"- {lot_id} : {fiche['motif']} (demandé par PID {fiche['demande_par_pid']} à {fiche['depuis']})")

if __name__ == '__main__':
    main()
