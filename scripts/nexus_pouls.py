import os
import time
import json
import argparse
import sys


def est_vivant(pouls, maintenant_ts, seuil_s):
    try:
        if pouls is None:
            return False
        ts = pouls.get("timestamp")
        if not isinstance(ts, (int, float)):
            return False
        delta = maintenant_ts - float(ts)
        return delta < float(seuil_s)
    except Exception:
        return False


def lire(chemin):
    try:
        chemin = os.fspath(chemin)
        with open(chemin, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def battre(chemin, modele="inconnu"):
    try:
        chemin = os.fspath(chemin)
        dossier = os.path.dirname(chemin)
        if dossier:
            os.makedirs(dossier, exist_ok=True)
        data = {
            "timestamp": time.time(),
            "modele": modele,
            "pid": os.getpid()
        }
        tmp_path = chemin + ".provisoire"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, separators=(",", ":"))
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, chemin)
        return True
    except Exception:
        return False


def _chemin_defaut():
    base = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
    return os.path.join(base, ".nexus", "pouls_claude.json")


def _main():
    parser = argparse.ArgumentParser(description="Heartbeat utility for Claude")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--battre", action="store_true", help="beat the heartbeat")
    group.add_argument("--etat", action="store_true", help="show alive/dead state")
    parser.add_argument("--modele", default="inconnu", help="model name for heartbeat")
    parser.add_argument("--seuil", type=float, default=900.0,
                        help="freshness threshold in seconds (default 900)")
    args = parser.parse_args()

    if args.battre:
        if battre(_chemin_defaut(), args.modele):
            print("pouls bat")
            sys.exit(0)
        else:
            print("echec du bat")
            sys.exit(1)

    if args.etat:
        pouls = lire(_chemin_defaut())
        vivant = est_vivant(pouls, time.time(), args.seuil)
        print("VIVANT" if vivant else "MORT")
        sys.exit(0 if vivant else 1)

    parser.print_help()
    sys.exit(0)


if __name__ == "__main__":
    _main()