# -*- coding: utf-8 -*-
"""Précharge les poids d'un modèle local pour éviter le coût de chargement à froid.

Un modèle local froid prend 180,3 s pour répondre, contre 2,90 s une fois chaud.
Le rapport de latence (60 à 700x) fausse toute mesure de débit réel.

Cet outil envoie une requête minimale à la passerelle pour forcer le chargement
des poids en mémoire, puis rend la main en rapportant temps et état.

Ce que l'outil NE FAIT PAS :
- Ne mesure pas le débit réel du modèle (seule la latence de chargement).
- Ne garantit pas que les poids restent en mémoire après l'appel.
- Ne remplace pas un appel réel (seule la passerelle peut confirmer l'état).
"""

import sys
import argparse
import time
import json
import urllib.request
import urllib.error

NEXUS_GATEWAY = "http://localhost:4000"

def preload_model(alias: str, timeout: float) -> dict:
    """Envoie une requête minimale pour charger les poids du modèle."""
    if alias.endswith("-cloud"):
        return {
            "alias": alias,
            "etat": "erreur",
            "message": "Modèle distant (pas de poids locaux à précharger)"
        }

    url = f"{NEXUS_GATEWAY}/v1/models/{alias}/preload"
    data = json.dumps({"prompt": " ", "max_tokens": 1}).encode("utf-8")
    headers = {"Content-Type": "application/json"}

    try:
        start = time.time()
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=timeout) as response:
            _ = response.read()  # Consomme la réponse pour éviter des fuites
        duree = time.time() - start
        return {
            "alias": alias,
            "etat": "succes",
            "duree_s": round(duree, 3),
            "message": "Poids chargés"
        }
    except urllib.error.URLError as e:
        return {
            "alias": alias,
            "etat": "erreur",
            "message": f"Passerelle inaccessible: {str(e)}"
        }
    except Exception as e:
        return {
            "alias": alias,
            "etat": "erreur",
            "message": f"Erreur inattendue: {str(e)}"
        }

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("alias", nargs="+", help="Alias du modèle à précharger")
    parser.add_argument("--timeout", type=float, default=300.0,
                        help="Timeout par alias en secondes (défaut: 300)")
    parser.add_argument("--json", action="store_true", help="Sortie en JSON")
    args = parser.parse_args()

    resultats = []
    for alias in args.alias:
        resultat = preload_model(alias, args.timeout)
        resultats.append(resultat)

    if args.json:
        print(json.dumps(resultats, ensure_ascii=False))
    else:
        for r in resultats:
            print(f"{r['alias']}: {r['etat']} ({r.get('duree_s', 'N/A')}s) - {r['message']}")

    return 0

if __name__ == "__main__":
    sys.exit(main())
