#!/usr/bin/env python3
"""
scripts/mesure_rendu_vide.py

Mesure du phénomène de réponses vides lorsqu’on demande un grand nombre de
jetons (défaut 2200). Pour chaque alias fourni, deux appels sont effectués
vers la passerelle LLM locale et les métriques suivantes sont relevées :

- nombre de caractères rendus
- nombre de jetons de sortie rapportés (completion_tokens)
- durée de l’appel (ms)
- code HTTP (ou None en cas d’erreur de transport)

Un tableau lisible est affiché. Le script renvoie le code de sortie 1 si au
moins un modèle rend une réponse vide lors du **deuxième** appel,
sinon 0.

La clé d’accès à la passerelle est lue dans le fichier .env à la racine du
dépôt, variable LITELLM_MASTER_KEY.
"""

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

# ---------------------------------------------------------------------------

def charger_env(racine: Path) -> dict:
    """Lire le fichier .env à la racine et retourner un dictionnaire."""
    env_path = racine / ".env"
    env = {}
    if env_path.is_file():
        with env_path.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    k, v = line.split("=", 1)
                    env[k.strip()] = v.strip()
    return env

# ---------------------------------------------------------------------------

CLEF = {"valeur": ""}

def _entetes() -> dict:
    hdr = {"Content-Type": "application/json"}
    if CLEF["valeur"]:
        hdr["Authorization"] = "Bearer " + CLEF["valeur"]
    return hdr

def appel_post(url: str, payload: dict, timeout: float):
    """Effectuer un POST JSON et retourner le corps décodé (dict)."""
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST", headers=_entetes())
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = resp.read()
        return json.loads(body.decode("utf-8")), resp.getcode()

def mesurer(alias: str, max_tokens: int, timeout: float):
    """
    Effectuer un appel unique et retourner un dict contenant :

    {
        "chars": int | None,
        "tokens": int | None,
        "duration_ms": int,
        "http_code": int | None,
        "error": str | None
    }
    """
    url = "http://localhost:4000/v1/chat/completions"
    payload = {
        "model": alias,
        "messages": [
            {
                "role": "user",
                "content": (
                    "Ecris un texte long d'au moins 3000 mots en français, "
                    "décrivant en détail le fonctionnement d'une passerelle de "
                    "modèles de langage, son utilité, ses contraintes et les "
                    "meilleures pratiques d'utilisation."
                )
            }
        ],
        "max_tokens": max_tokens,
        "temperature": 0.7,
        "cache": {"no-cache": True, "no-store": True}
    }

    start = time.monotonic()
    try:
        response, code = appel_post(url, payload, timeout)
        duration = int((time.monotonic() - start) * 1000)

        # Extraction du texte rendu
        try:
            texte = response["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, TypeError):
            texte = ""

        # Nombre de caractères
        chars = len(texte)

        # Nombre de jetons de sortie rapportés
        usage = response.get("usage", {})
        tokens = usage.get("completion_tokens")

        return {
            "chars": chars,
            "tokens": tokens,
            "duration_ms": duration,
            "http_code": code,
            "error": None
        }

    except urllib.error.HTTPError as exc:
        duration = int((time.monotonic() - start) * 1000)
        return {
            "chars": None,
            "tokens": None,
            "duration_ms": duration,
            "http_code": exc.code,
            "error": f"HTTPError: {exc.reason}"
        }
    except urllib.error.URLError as exc:
        duration = int((time.monotonic() - start) * 1000)
        return {
            "chars": None,
            "tokens": None,
            "duration_ms": duration,
            "http_code": None,
            "error": f"URLError: {exc.reason}"
        }
    except Exception as exc:
        duration = int((time.monotonic() - start) * 1000)
        return {
            "chars": None,
            "tokens": None,
            "duration_ms": duration,
            "http_code": None,
            "error": f"Exception: {str(exc)}"
        }

# ---------------------------------------------------------------------------

def afficher_tableau(resultats: dict):
    """Affiche un tableau récapitulatif des mesures."""
    entete = (
        f"{'Alias':30} "
        f"{'P1 chars':>10} {'P1 tok':>7} {'P1 ms':>7} "
        f"{'P2 chars':>10} {'P2 tok':>7} {'P2 ms':>7} {'HTTP':>6}"
    )
    print(entete)
    print("-" * len(entete))
    for alias, data in resultats.items():
        p1 = data["pass1"]
        p2 = data["pass2"]
        http_code = p2["http_code"] if p2["http_code"] is not None else p1["http_code"]
        ligne = (
            f"{alias:30} "
            f"{p1['chars'] if p1['chars'] is not None else '-':>10} "
            f"{p1['tokens'] if p1['tokens'] is not None else '-':>7} "
            f"{p1['duration_ms']:>7} "
            f"{p2['chars'] if p2['chars'] is not None else '-':>10} "
            f"{p2['tokens'] if p2['tokens'] is not None else '-':>7} "
            f"{p2['duration_ms']:>7} "
            f"{http_code if http_code is not None else '-':>6}"
        )
        print(ligne)

# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Mesure du rendu vide sur de longues requêtes."
    )
    parser.add_argument(
        "aliases",
        nargs="+",
        help="Alias(s) du modèle à tester."
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=2200,
        help="Nombre maximal de jetons demandés (défaut 2200)."
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=120.0,
        help="Timeout en secondes pour chaque appel (défaut 120)."
    )
    args = parser.parse_args()

    # Déterminer la racine du dépôt (parent du répertoire du script)
    script_path = Path(__file__).resolve()
    racine = script_path.parent.parent

    # Charger .env et récupérer la clé
    env = charger_env(racine)
    CLEF["valeur"] = os.getenv("LITELLM_MASTER_KEY", env.get("LITELLM_MASTER_KEY", ""))

    resultats = {}

    for alias in args.aliases:
        pass1 = mesurer(alias, args.max_tokens, args.timeout)
        pass2 = mesurer(alias, args.max_tokens, args.timeout)
        resultats[alias] = {"pass1": pass1, "pass2": pass2}

    afficher_tableau(resultats)

    # Déterminer le code de sortie
    vide_second_pass = any(
        (data["pass2"]["chars"] == 0) for data in resultats.values()
        if data["pass2"]["error"] is None
    )
    sys.exit(1 if vide_second_pass else 0)

if __name__ == "__main__":
    main()
