#!/usr/bin/env python3
"""
nexus_ruche.py – coordinateur qui découvre les cibles du dépôt et lance
plusieurs essaims concurrents jusqu’à ce que le dépôt soit couvert.

Pourquoi ?  La version précédente ne traitait qu’une cible à la fois et
requérait de les nommer manuellement.  Cette ruche automatise la découverte,
la priorisation, le découpage en lots et la relance en cas d’échec, tout en
respectant les limites de ressources de l’hôte.

Le script ne dépend que de la bibliothèque standard.
"""

import argparse
import concurrent.futures
import json
import os
import sys
import time
from pathlib import Path
from subprocess import run, CalledProcessError

# --------------------------------------------------------------------------- #
# Constantes
# --------------------------------------------------------------------------- #
ETAT_FICHIER = Path(".nexus/ruche-etat.json")
MAX_ESSAIMS = 4
TAILLE_LOT_DEFAUT = 6
ESSAIMS_DEFAUT = 2
LIGNES_MIN = 30
EXCLUSIONS_DIR = {"__pycache__", ".nexus"}
SECRET_MOTS = {"secret", "passwd", "password", "token", "key"}

# --------------------------------------------------------------------------- #
# Fonctions utilitaires
# --------------------------------------------------------------------------- #
def ecrire_etat_atomique(etat: dict) -> None:
    """Écrire le journal d’état de façon atomique pour éviter les corruptions."""
    ETAT_FICHIER.parent.mkdir(parents=True, exist_ok=True)
    tmp = ETAT_FICHIER.with_suffix(".tmp")
    tmp.write_text(json.dumps(etat, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, ETAT_FICHIER)


def charger_etat() -> dict:
    """Charger le journal d’état s’il existe, sinon retourner un dict vide."""
    if ETAT_FICHIER.is_file():
        try:
            return json.loads(ETAT_FICHIER.read_text(encoding="utf-8"))
        except Exception:
            # Corruption éventuelle : repartir de zéro.
            return {}
    return {}


def est_secret(nom: str) -> bool:
    """Détecter si le nom évoque un secret (ex. contient 'secret', 'token', …)."""
    lower = nom.lower()
    return any(mot in lower for mot in SECRET_MOTS)


def fichier_valide(p: Path) -> bool:
    """Vérifier qu’un fichier doit être traité : extension, taille, secret, etc."""
    if not p.is_file():
        return False
    if p.parent.name in EXCLUSIONS_DIR:
        return False
    if est_secret(p.name):
        return False
    try:
        lignes = sum(1 for _ in p.open(encoding="utf-8", errors="ignore"))
        if lignes < LIGNES_MIN:
            return False
    except Exception:
        return False
    return True


def decouvrir_cibles() -> list[Path]:
    """Lister les cibles auditables du dépôt selon les règles de découverte."""
    racine = Path(".")
    cibles = set()

    # scripts/*.py et scripts/*.ps1
    cibles.update(racine.glob("scripts/*.py"))
    cibles.update(racine.glob("scripts/*.ps1"))

    # *.ps1 à la racine
    cibles.update(racine.glob("*.ps1"))

    # tools/nexus-mcp/*.js
    cibles.update(racine.glob("tools/nexus-mcp/*.js"))

    # Filtrer
    valides = [p for p in cibles if fichier_valide(p)]
    return valides


def prioriser(cibles: list[Path]) -> list[Path]:
    """Trier les cibles du plus gros et le plus récemment modifié au plus petit."""
    def cle(p: Path):
        try:
            stat = p.stat()
            taille = stat.st_size
            mtime = stat.st_mtime
        except Exception:
            taille = 0
            mtime = 0
        # On veut décroissant sur taille puis mtime
        return (-taille, -mtime)

    return sorted(cibles, key=cle)


def decouper_lots(cibles: list[Path], taille_lot: int) -> list[list[Path]]:
    """Diviser la liste ordonnée en lots de taille donnée."""
    return [cibles[i:i + taille_lot] for i in range(0, len(cibles), taille_lot)]


def lancer_essaim(lot: list[Path], simuler: bool) -> dict:
    """
    Lancer un essaim (sous‑processus) sur le lot fourni.
    Retourne un dict {str(cible): "ok"|"echec"}.
    """
    resultats = {}
    if simuler:
        print(f"Simuler essaim sur {len(lot)} cible(s).")
        for p in lot:
            resultats[str(p)] = "ok"
        return resultats

    cmd = [sys.executable, "scripts/nexus_essaim.py"] + [str(p) for p in lot]
    try:
        proc = run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        code = proc.returncode
    except CalledProcessError as e:
        code = e.returncode

    statut = "ok" if code == 0 else "echec"
    for p in lot:
        resultats[str(p)] = statut
    return resultats


def traiter_lots(
    lots: list[list[Path]],
    essaims: int,
    simuler: bool,
    etat: dict,
) -> dict:
    """
    Exécuter les lots en parallèle, au maximum `essaims` processus simultanés.
    Met à jour le dictionnaire d’état et le renvoie.
    """
    # Limiter la concurrence
    if essaims > MAX_ESSAIMS:
        print(f"Limite atteinte : le nombre d'essaims est plafonne a {MAX_ESSAIMS}.")
        essaims = MAX_ESSAIMS

    with concurrent.futures.ThreadPoolExecutor(max_workers=essaims) as pool:
        futures = []
        for lot in lots:
            # Ignorer les cibles déjà traitées avec succès
            lot_a_traiter = [p for p in lot if etat.get(str(p), {}).get("verdict") != "ok"]
            if not lot_a_traiter:
                continue
            futures.append(pool.submit(lancer_essaim, lot_a_traiter, simuler))

        for fut in concurrent.futures.as_completed(futures):
            res = fut.result()
            for cible, verdict in res.items():
                etat[cible] = {"verdict": verdict, "timestamp": time.time()}
                ecrire_etat_atomique(etat)  # écriture atomique après chaque mise à jour
    return etat


def rapport_final(etat: dict) -> None:
    """Afficher le résumé des traitements."""
    total = len(etat)
    ok = sum(1 for v in etat.values() if v["verdict"] == "ok")
    echec = sum(1 for v in etat.values() if v["verdict"] == "echec")
    ignore = sum(1 for v in etat.values() if v["verdict"] == "ignore")
    # Jetons gratuits consommés – on ne suit pas ce compteur, on indique N/A.
    print("\n--- Rapport ---")
    print(f"Cibles traitees : {total}")
    print(f"Abouties       : {ok}")
    print(f"Echecs         : {echec}")
    print(f"Ignorees       : {ignore}")
    print("Jetons gratuits consommes : N/A")
    if echec:
        print("\nCibles en echec (a corriger) :")
        for cible, info in etat.items():
            if info["verdict"] == "echec":
                print(f"- {cible}")


# --------------------------------------------------------------------------- #
# Point d’entrée
# --------------------------------------------------------------------------- #
def main() -> int:
    parser = argparse.ArgumentParser(
        description="Coordinateur de lancement d'essaims pour le dépôt Nexus."
    )
    parser.add_argument("--essaims", type=int, default=ESSAIMS_DEFAUT,
                        help="Nombre d'essaims concurrents (max 4).")
    parser.add_argument("--taille-lot", type=int, default=TAILLE_LOT_DEFAUT,
                        help="Taille d'un lot de cibles.")
    parser.add_argument("--plans", choices=["cloud", "local", "deux"],
                        default="local", help="Plan d'exécution (non utilisé).")
    parser.add_argument("--tout-refaire", action="store_true",
                        help="Ignorer le journal et tout retraiter.")
    parser.add_argument("--simuler", action="store_true",
                        help="Ne pas lancer de sous‑processus, simuler les résultats.")
    args = parser.parse_args()

    # Charger ou réinitialiser le journal d’état
    if args.tout_refaire:
        etat = {}
    else:
        etat = charger_etat()

    # Découverte et priorisation
    cibles = decouvrir_cibles()
    cibles = prioriser(cibles)

    # Découpage en lots
    lots = decouper_lots(cibles, args.taille_lot)

    # Traitement
    etat = traiter_lots(lots, args.essaims, args.simuler, etat)

    # Rapport
    rapport_final(etat)

    # Code de sortie
    return 0 if all(v["verdict"] == "ok" for v in etat.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
