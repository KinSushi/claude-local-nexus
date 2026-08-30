#!/usr/bin/env python3
"""
Module nexus_bench
Ce script mesure la latence des modeles locaux exposes par la passerelle Nexus.
Il genere un releve (latences.json) que le generateur lira pour decide quels
modeles entrer dans les pools de routage.
"""

import os
import sys
import json
import time
import argparse
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

# ----- fonctions utilitaires -------------------------------------------------
def charger_env(racine: Path) -> dict:
    """Lire le fichier .env a la racine et retourner un dictionnaire."""
    env_path = racine / ".env"
    env = {}
    if env_path.is_file():
        with env_path.open(encoding="utf-8") as f:
            for ligne in f:
                ligne = ligne.strip()
                if not ligne or ligne.startswith("#"):
                    continue
                if "=" in ligne:
                    cle, val = ligne.split("=", 1)
                    env[cle.strip()] = val.strip()
    return env

# Clef de la passerelle, posee une fois pour toutes les requetes.
#
# La lire sans la transmettre donnait un 401, rapporte comme « impossible de
# joindre la passerelle » : le message envoyait chercher une panne reseau la
# ou l'appel etait simplement refuse.
CLEF = {"valeur": ""}


def _entetes() -> dict:
    entetes = {"Content-Type": "application/json"}
    if CLEF["valeur"]:
        entetes["Authorization"] = "Bearer " + CLEF["valeur"]
    return entetes


def appel_get(url: str, timeout: float) -> dict:
    """Effectuer un GET et retourner le JSON decode."""
    req = urllib.request.Request(url, method="GET", headers=_entetes())
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = resp.read()
        return json.loads(data.decode("utf-8"))

def appel_post(url: str, payload: dict, timeout: float) -> dict:
    """Effectuer un POST avec le payload JSON et retourner le JSON decode."""
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST", headers=_entetes())
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = resp.read()
        return json.loads(body.decode("utf-8"))

def est_embedding(nom: str) -> bool:
    """Detecter les modeles d'embedding par leur nom."""
    nom_lower = nom.lower()
    return any(tok in nom_lower for tok in ("embed", "minilm", "bge"))

def mesurer_latence(gateway: str, alias: str, timeout: float) -> tuple:
    """
    Mesurer la latence du modele alias.
    Retourne (latence_ms, ok, motif)
    """
    if est_embedding(alias):
        return (None, False, "non applicable")
    url = f"{gateway.rstrip('/')}/v1/chat/completions"
    payload = {
        "model": alias,
        "messages": [{"role": "user", "content": "Repond par le seul mot: PRET"}],
        "max_tokens": 16,
    }
    start = time.monotonic()
    try:
        appel_post(url, payload, timeout)
        elapsed = time.monotonic() - start
        return (int(elapsed * 1000), True, "")
    except urllib.error.URLError as e:
        # timeout ou autre erreur de connexion
        elapsed = time.monotonic() - start
        if isinstance(e.reason, TimeoutError) or isinstance(e.reason, socket.timeout):
            return (int(timeout * 1000), False, "timeout")
        return (int(elapsed * 1000), False, str(e.reason))
    except Exception as e:
        elapsed = time.monotonic() - start
        return (int(elapsed * 1000), False, str(e))

def ecrire_json(racine: Path, mesures: dict):
    """Ecrire le fichier latences.json avec encodage UTF-8 explicite."""
    sortie_dir = racine / ".nexus"
    sortie_dir.mkdir(parents=True, exist_ok=True)
    sortie_path = sortie_dir / "latences.json"
    with sortie_path.open("w", encoding="utf-8") as f:
        json.dump(mesures, f, ensure_ascii=False, indent=2)

def afficher_tableau(resultats: dict):
    """Afficher un tableau simple alias, secondes, verdict."""
    entete = f"{'Alias':30} {'Secondes':>10} {'Verdict':>20}"
    print(entete)
    print("-" * len(entete))
    for alias, info in resultats.items():
        lat = info.get("latence_ms")
        sec = f"{lat/1000:.3f}" if lat is not None else "N/A"
        # Trois verdicts et non deux : un embedding ne repond pas a un
        # endpoint de conversation, ce n'est pas un echec de sa part. Le
        # confondre avec une panne le ferait ecarter des pools pour une
        # raison fausse.
        if info.get("motif") == "non applicable":
            verdict = "N/A (embedding)"
        elif info["ok"]:
            verdict = "OK"
        else:
            verdict = f"FAIL ({info['motif']})"
        print(f"{alias:30} {sec:>10} {verdict:>20}")

# ----- corps principal -------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Mesure de latence des modeles locaux")
    parser.add_argument("--timeout", type=float, help="Timeout en secondes (defaut 90)")
    parser.add_argument("--json", action="store_true", help="Afficher le JSON de sortie")
    parser.add_argument("--modele", action="append", help="Alias du modele a tester (repetable)")
    args = parser.parse_args()

    # determiner la racine (parent du repertoire du script)
    script_path = Path(__file__).resolve()
    racine = script_path.parent.parent

    # charger .env
    env = charger_env(racine)
    CLEF["valeur"] = os.getenv("LITELLM_MASTER_KEY", env.get("LITELLM_MASTER_KEY", ""))
    gateway = os.getenv("NEXUS_GATEWAY", env.get("NEXUS_GATEWAY", "http://localhost:4000"))
    timeout_defaut = float(os.getenv("NEXUS_BENCH_TIMEOUT", env.get("NEXUS_BENCH_TIMEOUT", "90")))
    timeout = args.timeout if args.timeout is not None else timeout_defaut

    # recuperer la liste des modeles
    try:
        info = appel_get(f"{gateway.rstrip('/')}/model/info", timeout)
    except urllib.error.HTTPError as exc:
        # Distinguer le refus de l'injoignable : le premier se corrige dans
        # .env, le second en demarrant la pile. Les confondre envoie
        # chercher au mauvais endroit -- c'est arrive.
        sys.stderr.write("Passerelle joignable mais refus HTTP %s : verifier "
                         "LITELLM_MASTER_KEY dans .env\n" % exc.code)
        sys.exit(1)
    except Exception as exc:
        sys.stderr.write("Passerelle injoignable sur %s : %s\n" % (gateway, exc))
        sys.exit(1)

    modeles = [m["model_name"] for m in info.get("data", []) if m.get("model_name", "").endswith("-local")]
    if not modeles:
        sys.stderr.write("Aucun modele local trouve.\n")
        sys.exit(1)

    # filtrer selon --modele si fourni
    if args.modele:
        modeles = [m for m in modeles if m in args.modele]
        if not modeles:
            sys.stderr.write("Aucun des modeles demandes n'est disponible.\n")
            sys.exit(1)

    resultats = {}
    for alias in modeles:
        lat_ms, ok, motif = mesurer_latence(gateway, alias, timeout)
        resultats[alias] = {
            "latence_ms": lat_ms,
            "ok": ok,
            "motif": motif,
        }

    # ecrire le fichier json
    mesures = {
        "mesure_le": datetime.now(timezone.utc).isoformat(),
        "modeles": resultats,
    }
    ecrire_json(racine, mesures)

    # affichage
    afficher_tableau(resultats)
    if args.json:
        print(json.dumps(mesures, ensure_ascii=False, indent=2))

    sys.exit(0)

if __name__ == "__main__":
    main()
