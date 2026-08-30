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
# Le répertoire racine du dépôt (celui contenant ce script) est utilisé
# pour toutes les opérations de découverte et pour le journal d’état.
BASE_DIR = Path(__file__).resolve().parent.parent

ETAT_FICHIER = BASE_DIR / ".nexus" / "ruche-etat.json"
MAX_ESSAIMS = 4
TAILLE_LOT_DEFAUT = 6
ESSAIMS_DEFAUT = 2
LIGNES_MIN = 30
EXCLUSIONS_DIR = {"__pycache__", ".nexus"}
SECRET_MOTS = {"secret", "passwd", "password", "token", "key"}

# Chemin absolu du script d'essaim, résolu depuis le répertoire contenant ce fichier.
# On utilise os.path.abspath(__file__) pour obtenir le chemin réel du script,
# puis os.path.dirname pour en extraire le répertoire. Cette méthode ne dépend
# d'aucun répertoire de travail courant et évite le problème du doublement
# « scripts/scripts » qui survenait avec un chemin relatif.
ESSAIM_SCRIPT = Path(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "nexus_essaim.py")
)

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
    racine = BASE_DIR
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


def lancer_essaim(lot: list[Path], simuler: bool, plan: str, essaims: int) -> dict:
    """
    Lancer un essaim (sous‑processus) sur le lot fourni.
    Retourne un dict {str(cible): {"verdict": "ok"|"echec", "cause": str}}.
    """
    resultats = {}
    if simuler:
        # Message sans accents, comme requis.
        print(f"Simuler essaim sur {len(lot)} cible(s).")
        for p in lot:
            resultats[str(p)] = {"verdict": "ok", "cause": ""}
        return resultats

    # Verifier que le script d'essaim existe avant de le lancer.
    if not ESSAIM_SCRIPT.is_file():
        msg = f"Script essaim introuvable: {ESSAIM_SCRIPT}"
        print(msg)
        for p in lot:
            resultats[str(p)] = {"verdict": "echec", "cause": msg}
        return resultats

    # --------------------------------------------------------------
    # Construction de la ligne de commande.
    # --------------------------------------------------------------
    # COMMENTAIRE : seules les options reconnues par nexus_essaim.py
    # sont transmises.  L'option --essaims appartient à la ruche et
    # provoquerait "unrecognized arguments" dans l'essaim, ce qui
    # ferait échouer tout le lot.  De même, l'option correcte pour le
    # plan est --plans (pluriel).  En filtrant ainsi, on évite que
    # l'ajout futur d'options à la ruche ne casse l'essaim.
    cmd = [
        sys.executable,
        str(ESSAIM_SCRIPT),
        "--cibles"
    ] + [str(p) for p in lot] + [
        "--plans", plan
    ]

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
        sortie_err = proc.stderr.strip()
        sortie_out = proc.stdout.strip()
    except FileNotFoundError as e:
        code = 1
        sortie_err = str(e)
        sortie_out = ""
    except CalledProcessError as e:
        code = e.returncode
        sortie_err = e.stderr.strip() if e.stderr else str(e)
        sortie_out = e.stdout.strip() if e.stdout else ""

    # Tentative d’interpréter une sortie détaillée (JSON) fournie par l’essaim.
    # Si le parsing échoue, on retombe sur le verdict global basé sur le code retour.
    if sortie_out:
        try:
            details = json.loads(sortie_out)
            if isinstance(details, dict):
                for cible_str, info in details.items():
                    verdict = info.get("verdict", "echec")
                    cause = info.get("cause", "")
                    resultats[cible_str] = {"verdict": verdict, "cause": cause}
                return resultats
        except Exception:
            # Le format n’est pas celui attendu ; on ignore et on utilise le fallback.
            pass

    statut = "ok" if code == 0 else "echec"
    cause = "" if statut == "ok" else sortie_err or "code de retour non nul"
    for p in lot:
        resultats[str(p)] = {"verdict": statut, "cause": cause}
    return resultats


def traiter_lots(
    lots: list[list[Path]],
    essaims: int,
    simuler: bool,
    etat: dict,
    plan: str,
) -> tuple[dict, int]:
    """
    Exécuter les lots en parallèle, au maximum `essaims` processus simultanés.
    Met à jour le dictionnaire d’état et renvoie le dictionnaire ainsi que le
    nombre de cibles réellement traitées durant cet appel.
    """
    # Limiter la concurrence
    if essaims > MAX_ESSAIMS:
        # Message sans accents.
        print(f"Limite atteinte : le nombre d'essaims est plafonne a {MAX_ESSAIMS}.")
        essaims = MAX_ESSAIMS

    traitees = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=essaims) as pool:
        futures = []
        for lot in lots:
            # Ignorer les cibles déjà traitées avec succes.
            lot_a_traiter = [p for p in lot if etat.get(str(p), {}).get("verdict") != "ok"]
            if not lot_a_traiter:
                continue
            futures.append(pool.submit(lancer_essaim, lot_a_traiter, simuler, plan, essaims))

        for fut in concurrent.futures.as_completed(futures):
            res = fut.result()
            for cible, info in res.items():
                verdict = info["verdict"]
                cause = info.get("cause", "")
                # En mode simulation, on ne persiste pas les résultats.
                if not simuler:
                    etat[cible] = {
                        "verdict": verdict,
                        "timestamp": time.time(),
                        "processed": True,
                        "cause": cause,
                    }
                    ecrire_etat_atomique(etat)  # écriture atomique après chaque mise à jour
                else:
                    # On compte les cibles simulées pour le rapport mais on ne les enregistre pas.
                    traitees += 1
                if not simuler:
                    traitees += 1
    return etat, traitees


def rapport_final(etat: dict, total_cibles: int, traitees: int, start_time: float) -> None:
    """Afficher le résumé des traitements."""
    # Cibles réellement traitees durant cette execution.
    traitees_durant = traitees
    # Cibles sautees parce qu'elles etaient deja abouties.
    sautees = total_cibles - traitees_durant

    ok = sum(1 for v in etat.values() if v["verdict"] == "ok")
    echec = sum(1 for v in etat.values() if v["verdict"] == "echec")
    ignore = sum(1 for v in etat.values() if v["verdict"] == "ignore")

    print("\n--- Rapport ---")
    print(f"Cibles traitees cette execution : {traitees_durant}")
    print(f"Cibles sautees (deja abouties) : {sautees}")
    print(f"Total cibles connues           : {total_cibles}")
    print(f"Abouties                       : {ok}")
    print(f"Echecs                         : {echec}")
    print(f"Ignorees                       : {ignore}")
    # Le compteur de jetons gratuits n'est pas mesure ici.
    print("Jetons gratuits consommes : non mesure")
    if echec:
        print("\nCibles en echec (a corriger) :")
        for cible, info in etat.items():
            if info["verdict"] == "echec":
                cause = info.get("cause", "")
                print(f"- {cible} : {cause}")


# --------------------------------------------------------------------------- #
# Point d’entrée
# --------------------------------------------------------------------------- #
def main() -> int:
    parser = argparse.ArgumentParser(
        description="Coordinateur de lancement d'essaims pour le depot Nexus."
    )
    parser.add_argument("--essaims", type=int, default=ESSAIMS_DEFAUT,
                        help="Nombre d'essaims concurrents (max 4).")
    parser.add_argument("--taille-lot", type=int, default=TAILLE_LOT_DEFAUT,
                        help="Taille d'un lot de cibles.")
    parser.add_argument("--plans", choices=["cloud", "local", "deux"],
                        default="local", help="Plan d'execution (non utilise).")
    parser.add_argument("--tout-refaire", action="store_true",
                        help="Ignorer le journal et tout retraiter.")
    parser.add_argument("--simuler", action="store_true",
                        help="Ne pas lancer de sousprocessus, simuler les resultats.")
    args = parser.parse_args()

    # Charger ou reinitialiser le journal d'etat
    if args.tout_refaire:
        etat = {}
    else:
        etat = charger_etat()

    # Decouverte et priorisation
    cibles = decouvrir_cibles()
    cibles = prioriser(cibles)

    total_cibles = len(cibles)

    # Nettoyer le journal des cibles qui n'existent plus.
    cibles_str = {str(p) for p in cibles}
    etat = {k: v for k, v in etat.items() if k in cibles_str}

    # Decoupage en lots
    lots = decouper_lots(cibles, args.taille_lot)

    # Marquer le temps de debut pour le rapport
    start_time = time.time()

    # Traitement
    etat, traitees = traiter_lots(lots, args.essaims, args.simuler, etat, args.plans)

    # Rapport
    rapport_final(etat, total_cibles, traitees, start_time)

    # Code de sortie
    return 0 if all(v["verdict"] == "ok" for v in etat.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
