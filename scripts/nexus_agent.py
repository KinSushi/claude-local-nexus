# -*- coding: utf-8 -*-
"""
Lanceur d'agents gratuits.

Pourquoi ce script existe
-------------------------
Déléguer une analyse à un sous-agent Claude consomme l'abonnement : c'est
le contraire du but poursuivi. Ce script fait exécuter le même travail par
les modèles servis par la passerelle — locaux ou Ollama Cloud — dont le
coût est nul. L'orchestrateur ne dépense alors que ce qu'il faut pour
formuler la tâche et lire la réponse.

Ce qu'il apporte par rapport à un `curl` à la main :

  - plusieurs tâches partent en parallèle sur des modèles différents, ce
    qui est le seul moyen d'amortir les 60 à 120 s de chargement à froid
    d'un modèle local ;
  - le plan réellement servi est PROUVÉ par l'en-tête de réponse plutôt
    que déduit du nom demandé — un routeur peut basculer, un alias peut
    pointer ailleurs, et une réponse « locale » venue du cloud n'est pas
    une économie mais une fuite ;
  - les fichiers joints subissent les mêmes interdictions que dans le
    serveur MCP : rien hors du dépôt, aucun fichier susceptible de porter
    un secret ;
  - le coût facturé est rapporté, donc vérifiable au lieu d'être supposé.

Usage
-----
    # une tâche, un modèle
    python scripts/nexus_agent.py --tache "Relis et signale les defauts" \
        --fichiers scripts/nexus_validate.py --modele qwen3-coder-30b-local

    # plusieurs tâches en parallèle, décrites dans un JSON
    python scripts/nexus_agent.py --lot taches.json

    # lister les modèles gratuits disponibles
    python scripts/nexus_agent.py --modeles

Format du lot (liste d'objets) :

    [
      {"nom": "validateur", "modele": "qwen3-coder-30b-local",
       "tache": "...", "fichiers": ["scripts/nexus_validate.py"]},
      {"nom": "generateur", "modele": "qwen3-14b-local",
       "tache": "...", "fichiers": ["scripts/nexus_generate.py"]}
    ]
"""
from __future__ import annotations

import argparse
import concurrent.futures
import io
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PASSERELLE = os.environ.get("NEXUS_GATEWAY", "http://localhost:4000")

# Un modèle local non chargé met 60 à 120 s à répondre au premier appel, et
# davantage pour les gros poids. Un délai court ne protège de rien : il
# transforme un chargement normal en échec, et pousse à réessayer, donc à
# recharger. Mieux vaut attendre.
DELAI = int(os.environ.get("NEXUS_AGENT_TIMEOUT", "900"))

# Mêmes règles que le serveur MCP : ce qui ne doit pas remonter vers un
# modèle ne doit pas davantage remonter parce que le canal a changé.
FICHIERS_SECRETS = {
    ".env", ".env.local", ".env.production", ".npmrc", ".netrc",
    "credentials", "credentials.json", "id_rsa", "id_ed25519",
}
MOTIFS_SECRETS = re.compile(
    r"(^\.env($|\.)|\.pem$|\.key$|\.pfx$|\.p12$|_rsa$|_ed25519$|"
    r"secrets?\.(ya?ml|json|toml)$)",
    re.IGNORECASE,
)


def cle_maitre() -> str:
    """
    Clé de la passerelle, lue dans l'environnement puis dans .env.

    La valeur n'est jamais journalisée ni renvoyée : elle ne sert qu'à
    remplir un en-tête. Les guillemets et le commentaire de fin de ligne
    sont retirés parce que .env les tolère et que la clé, elle, non.
    """
    valeur = os.environ.get("LITELLM_MASTER_KEY")
    if not valeur:
        chemin = os.path.join(ROOT, ".env")
        if os.path.exists(chemin):
            for ligne in io.open(chemin, encoding="utf-8", errors="replace"):
                if ligne.startswith("LITELLM_MASTER_KEY="):
                    valeur = ligne.split("=", 1)[1]
                    break
    if not valeur:
        raise SystemExit(
            "LITELLM_MASTER_KEY introuvable (ni dans l'environnement, ni dans .env)."
        )
    valeur = valeur.strip()
    if " #" in valeur:
        valeur = valeur.split(" #", 1)[0].strip()
    return valeur.strip("\"'").strip()


def est_secret(chemin: str) -> bool:
    base = os.path.basename(chemin)
    return base.lower() in FICHIERS_SECRETS or bool(MOTIFS_SECRETS.search(base))


def dans_depot(chemin: str) -> bool:
    """
    Le fichier est-il sous la racine du dépôt ?

    `os.path.commonpath` plutôt qu'une comparaison de préfixe : un chemin
    voisin nommé `C:\\local-llm-docker-prive` commence par la racine sans
    être dedans, et aurait donc été accepté par un `startswith`.
    """
    try:
        return os.path.commonpath([os.path.realpath(chemin), os.path.realpath(ROOT)]) == \
            os.path.realpath(ROOT)
    except ValueError:
        # Lecteurs différents sous Windows : commonpath lève plutôt que de
        # rendre un résultat trompeur. C'est donc un refus.
        return False


def charger_fichiers(chemins: list[str]) -> tuple[str, list[str]]:
    """Assemble le corpus et rend aussi la liste de ce qui a été refusé."""
    morceaux, refus = [], []
    for brut in chemins:
        complet = brut if os.path.isabs(brut) else os.path.join(ROOT, brut)
        if not dans_depot(complet):
            refus.append("%s (hors du depot)" % brut)
            continue
        if est_secret(complet):
            refus.append("%s (susceptible de contenir un secret)" % brut)
            continue
        if not os.path.exists(complet):
            refus.append("%s (introuvable)" % brut)
            continue
        try:
            contenu = io.open(complet, encoding="utf-8", errors="replace").read()
        except Exception as exc:
            refus.append("%s (illisible : %s)" % (brut, exc))
            continue
        morceaux.append("--- %s ---\n%s" % (brut, contenu))
    return "\n\n".join(morceaux), refus


def appeler(modele: str, messages: list[dict], max_tokens: int, cle: str) -> dict:
    """
    Un appel à la passerelle, avec la preuve du plan réellement servi.

    `no-cache` est posé volontairement : une réponse de cache mesurerait la
    latence de Redis, pas celle du modèle, et ferait croire à un travail
    accompli qui ne l'a pas été.
    """
    charge = json.dumps({
        "model": modele,
        "messages": messages,
        "max_tokens": max_tokens,
        "cache": {"no-cache": True},
    }).encode("utf-8")
    requete = urllib.request.Request(
        PASSERELLE + "/v1/chat/completions",
        data=charge,
        headers={
            "Authorization": "Bearer " + cle,
            "Content-Type": "application/json",
        },
        method="POST",
    )
    depart = time.time()
    with urllib.request.urlopen(requete, timeout=DELAI) as reponse:
        corps = json.loads(reponse.read().decode("utf-8"))
        entetes = {k.lower(): v for k, v in reponse.getheaders()}
    duree = time.time() - depart
    choix = (corps.get("choices") or [{}])[0]
    return {
        "texte": choix.get("message", {}).get("content", ""),
        # Distinguer une réponse coupée d'une réponse fautive. Sans cette
        # information, un plafond `max_tokens` trop bas se présentait comme
        # une défaillance du modèle : la première tâche réelle a ainsi
        # rendu une analyse juste dans un JSON tronqué, rapportée comme
        # « réponse inexploitable ». Le défaut était dans l'appelant.
        "tronque": choix.get("finish_reason") == "length",
        "tokens": (corps.get("usage") or {}).get("total_tokens", 0),
        # Le nom demandé peut être un routeur ; seuls ces en-têtes disent ce
        # qui a réellement répondu, et par quelle adresse.
        "servi_par": entetes.get("x-litellm-model-name", "?"),
        "adresse": entetes.get("x-litellm-model-api-base", "?"),
        "cout": entetes.get("x-litellm-response-cost", "0"),
        "duree": duree,
    }


def plan_de(adresse: str) -> str:
    """Plan d'exécution déduit de l'adresse réellement servie."""
    if not adresse or adresse == "?":
        return "inconnu"
    if "ollama.com" in adresse:
        return "cloud"
    if "anthropic" in adresse:
        return "anthropic"
    if "11434" in adresse or "11435" in adresse or "ollama" in adresse:
        return "local"
    return "inconnu"


def executer(tache: dict, cle: str) -> dict:
    nom = tache.get("nom") or tache.get("modele") or "tache"
    modele = tache.get("modele") or "qwen3-coder-30b-local"
    consigne = tache.get("tache") or ""
    if not consigne:
        return {"nom": nom, "erreur": "champ 'tache' vide"}
    corpus, refus = charger_fichiers(tache.get("fichiers") or [])
    systeme = tache.get("systeme") or (
        "Tu es un relecteur technique rigoureux. Tu reponds en francais, de "
        "maniere concise et factuelle. Tu ne pretends jamais avoir verifie ce "
        "que tu n'as pas lu, et tu dis explicitement quand tu n'es pas sur."
    )
    contenu = consigne if not corpus else "%s\n\n%s" % (consigne, corpus)
    try:
        resultat = appeler(
            modele,
            [{"role": "system", "content": systeme},
             {"role": "user", "content": contenu}],
            int(tache.get("max_tokens") or 1500),
            cle,
        )
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:300]
        return {"nom": nom, "modele": modele, "erreur": "HTTP %s : %s" % (exc.code, detail)}
    except Exception as exc:
        return {"nom": nom, "modele": modele, "erreur": str(exc)}
    resultat.update({"nom": nom, "modele": modele, "refus": refus,
                     "plan": plan_de(resultat["adresse"])})
    return resultat


def rendre(resultat: dict) -> None:
    print("=" * 72)
    print("  %s" % resultat["nom"])
    if resultat.get("erreur"):
        print("  ECHEC : %s" % resultat["erreur"])
        print("=" * 72)
        return
    print("  demande : %s" % resultat["modele"])
    print("  servi   : %s  [%s]  %s" %
          (resultat["servi_par"], resultat["plan"], resultat["adresse"]))
    print("  %d tokens, %.0f s, cout %s" %
          (resultat["tokens"], resultat["duree"], resultat["cout"]))
    for r in resultat.get("refus") or []:
        print("  [refuse] %s" % r)
    print("-" * 72)
    print(resultat["texte"].strip())
    print("=" * 72)
    print()


def lister_modeles(cle: str) -> int:
    """
    Modèles exposés, séparés par plan.

    Un modèle Anthropic n'est pas gratuit ; les mélanger dans une même
    liste inviterait à en choisir un par inadvertance, ce qui est
    exactement ce que ce script cherche à éviter.
    """
    requete = urllib.request.Request(
        PASSERELLE + "/v1/model/info",
        headers={"Authorization": "Bearer " + cle},
    )
    try:
        with urllib.request.urlopen(requete, timeout=30) as reponse:
            donnees = json.loads(reponse.read().decode("utf-8")).get("data", [])
    except Exception as exc:
        print("Passerelle injoignable sur %s (%s)" % (PASSERELLE, exc))
        return 1
    plans: dict[str, list[str]] = {"local": [], "cloud": [], "anthropic": [], "inconnu": []}
    for entree in donnees:
        nom = entree.get("model_name", "?")
        params = entree.get("litellm_params") or {}
        cible = str(params.get("model", ""))
        base = str(params.get("api_base", ""))
        if cible.startswith("anthropic/"):
            plans["anthropic"].append(nom)
        elif "ollama.com" in base:
            plans["cloud"].append(nom)
        elif cible.startswith("ollama"):
            plans["local"].append(nom)
        else:
            plans["inconnu"].append(nom)
    for plan in ("local", "cloud", "anthropic", "inconnu"):
        noms = sorted(plans[plan])
        if not noms:
            continue
        cout = "gratuit" if plan in ("local", "cloud") else "FACTURE"
        print("\n  %s (%d, %s)" % (plan.upper(), len(noms), cout))
        for nom in noms:
            print("    %s" % nom)
    print()
    return 0


def main() -> int:
    parseur = argparse.ArgumentParser(description=__doc__)
    parseur.add_argument("--tache", help="Consigne adressee au modele.")
    parseur.add_argument("--fichiers", nargs="*", default=[],
                         help="Fichiers du depot a joindre.")
    parseur.add_argument("--modele", default="qwen3-coder-30b-local")
    parseur.add_argument("--systeme", help="Consigne systeme optionnelle.")
    parseur.add_argument("--max-tokens", type=int, default=1500)
    parseur.add_argument("--lot", help="Fichier JSON decrivant plusieurs taches.")
    parseur.add_argument("--parallele", type=int, default=3,
                         help="Taches simultanees (defaut 3).")
    parseur.add_argument("--modeles", action="store_true",
                         help="Lister les modeles exposes par plan.")
    parseur.add_argument("--json", action="store_true",
                         help="Sortie machine au lieu du rapport lisible.")
    args = parseur.parse_args()

    cle = cle_maitre()

    if args.modeles:
        return lister_modeles(cle)

    if args.lot:
        taches = json.loads(io.open(args.lot, encoding="utf-8").read())
        if not isinstance(taches, list):
            print("Le lot doit etre une liste d'objets.")
            return 1
    elif args.tache:
        taches = [{"nom": args.modele, "modele": args.modele, "tache": args.tache,
                   "fichiers": args.fichiers, "systeme": args.systeme,
                   "max_tokens": args.max_tokens}]
    else:
        parseur.print_help()
        return 1

    # Le parallélisme est plafonné : au-delà, plusieurs gros modèles sont
    # chargés en même temps sur une machine qui n'a qu'une réserve de RAM,
    # et l'ensemble ralentit au lieu d'accélérer.
    largeur = max(1, min(args.parallele, len(taches)))
    depart = time.time()
    resultats: list[dict] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=largeur) as pool:
        futurs = {pool.submit(executer, t, cle): t for t in taches}
        for futur in concurrent.futures.as_completed(futurs):
            resultats.append(futur.result())

    if args.json:
        print(json.dumps(resultats, ensure_ascii=False, indent=2))
        return 0

    ordre = {t.get("nom") or t.get("modele"): i for i, t in enumerate(taches)}
    for resultat in sorted(resultats, key=lambda r: ordre.get(r["nom"], 99)):
        rendre(resultat)

    echecs = [r for r in resultats if r.get("erreur")]
    factures = [r for r in resultats if r.get("plan") == "anthropic"]
    total = sum(r.get("tokens", 0) for r in resultats)
    print("  %d tache(s), %d token(s), %.0f s au total, %d echec(s)"
          % (len(resultats), total, time.time() - depart, len(echecs)))
    if factures:
        # Signalé, jamais tu : une tâche partie chez Anthropic sans qu'on
        # l'ait voulu est précisément la dépense que ce script évite.
        print("  [!] %d tache(s) servies par Anthropic, donc FACTUREES : %s"
              % (len(factures), ", ".join(r["nom"] for r in factures)))
    return 1 if echecs else 0


if __name__ == "__main__":
    sys.exit(main())
