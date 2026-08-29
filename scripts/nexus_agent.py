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
# ----------------------------------------------------------------------
def racine_travail() -> str:
    """
    Retourne la racine de travail selon l'ordre de priorité suivant :
    1. Variable d'environnement NEXUS_WORK_ROOT (réglage explicite).
    2. Variable d'environnement CLAUDE_PROJECT_DIR (fourni par l'hôte).
    3. Répertoire courant (os.getcwd()).
    Aucun chemin en dur n'est utilisé afin que le banc reste utilisable
    depuis n'importe quel projet.
    """
    for var in ("NEXUS_WORK_ROOT", "CLAUDE_PROJECT_DIR"):
        val = os.getenv(var)
        if val:
            return val
    return os.getcwd()

# Un modèle local non chargé met 60 à 120 s à répondre au premier appel, et
# davantage pour les gros poids. Un délai court ne protège de rien : il
# transforme un chargement normal en échec, et pousse à réessayer, donc à
# recharger. Mieux vaut attendre.
DELAI = int(os.environ.get("NEXUS_AGENT_TIMEOUT", "900"))

# Temperature par defaut. 0.2 et non le defaut des modeles, souvent 0.7 a
# 0.8 : le travail dominant ici est de la relecture de code, de l'extraction
# et des sorties au format strict, ou une temperature haute produit de la
# vraisemblance plutot que de l'exactitude. Mesure du jour ou elle a ete
# posee : trois echecs consecutifs du banc sur des taches a sortie stricte
# -- une reponse vide apres 19 000 jetons, une reponse tronquee dont le code
# etait reecrit de memoire, et une boucle de repetition de 589 secondes.
TEMPERATURE_DEFAUT = float(os.environ.get("NEXUS_TEMPERATURE", "0.2"))

# Ordre de repli entre plans GRATUITS uniquement. Aucun alias Claude n'y
# figure et aucun ne doit y figurer : retomber sur le paye reviendrait a
# facturer au jeton ce qui devait etre gratuit, sans que personne l'ait
# decide.
REPLIS_GRATUITS = ["gpt-oss-120b-cloud", "glm-4.7-flash-local"]

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


def sous_racine(chemin: str, racine: str) -> bool:
    """
    Le fichier est-il sous la racine spécifiée ?

    Utilise `os.path.commonpath` pour éviter les faux positifs (ex.
    C:\\local-llm-docker-prive). En cas de lecteurs différents sous Windows,
    `commonpath` lève `ValueError` qui est interprété comme un refus.
    """
    try:
        return os.path.commonpath([os.path.realpath(chemin), os.path.realpath(racine)]) == \
            os.path.realpath(racine)
    except ValueError:
        return False

# Compatibilité : l'ancienne fonction conserve le même comportement avec ROOT.
def dans_depot(chemin: str) -> bool:
    """Alias conservé pour compatibilité interne."""
    return sous_racine(chemin, ROOT)


def charger_fichiers(chemins: list[str], racine: str | None = None) -> tuple[str, list[str]]:
    """Assemble le corpus et rend aussi la liste de ce qui a été refusé.

    Le paramètre `racine` désigne la racine de travail. S'il n'est pas fourni,
    il est déterminé par `racine_travail()`. Les chemins relatifs sont résolus
    depuis cette racine.
    """
    if racine is None:
        racine = racine_travail()
    morceaux, refus = [], []
    for brut in chemins:
        complet = brut if os.path.isabs(brut) else os.path.join(racine, brut)
        if not sous_racine(complet, racine):
            refus.append("%s (hors de la racine de travail %s)" % (brut, racine))
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


def appeler(modele: str, messages: list[dict], max_tokens: int, cle: str,
            temperature: float | None = None) -> dict:
    """
    Un appel à la passerelle, avec la preuve du plan réellement servi.

    `no-cache` est posé volontairement : une réponse de cache mesurerait la
    latence de Redis, pas celle du modèle, et ferait croire à un travail
    accompli qui ne l'a pas été.

    La température était jusqu'ici laissée au défaut du modèle. Voir
    `TEMPERATURE_DEFAUT` : ce défaut, trop haut pour les tâches d'ici,
    faisait passer le banc pour incapable alors qu'il était mal réglé.
    """
    corps_requete = {
        "model": modele,
        "messages": messages,
        "max_tokens": max_tokens,
        "cache": {"no-cache": True},
    }
    if temperature is not None:
        corps_requete["temperature"] = temperature
    charge = json.dumps(corps_requete).encode("utf-8")
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


def plans_par_alias(cle: str) -> dict[str, str]:
    """
    Plan d'exécution de chaque alias, lu dans le catalogue de la passerelle.

    L'en-tête `x-litellm-model-api-base` est la preuve la plus directe,
    mais il n'est renvoyé que par `/v1/chat/completions` : `/v1/messages`,
    l'API que Claude Code emploie, ne le pose pas. Déduire le plan de son
    absence donnerait « inconnu » pour tout le chemin de relève — et
    conclurait donc que la relève n'est pas locale, alors qu'elle l'est.

    Le catalogue dit la même chose de façon déterministe : c'est lui qui
    décrit où chaque alias enverra ses requêtes.
    """
    requete = urllib.request.Request(
        PASSERELLE + "/v1/model/info", headers={"Authorization": "Bearer " + cle})
    try:
        with urllib.request.urlopen(requete, timeout=30) as reponse:
            donnees = json.loads(reponse.read().decode("utf-8")).get("data", [])
    except Exception:
        return {}
    plans: dict[str, str] = {}
    for entree in donnees:
        nom = entree.get("model_name")
        if not nom:
            continue
        params = entree.get("litellm_params") or {}
        cible = str(params.get("model", ""))
        base = str(params.get("api_base", ""))
        if cible.startswith("anthropic/"):
            plans[nom] = "anthropic"
        elif "ollama.com" in base:
            plans[nom] = "cloud"
        elif cible.startswith("ollama"):
            plans[nom] = "local"
        else:
            plans[nom] = "inconnu"
    return plans


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
    racine_tache = tache.get("racine")
    corpus, refus = charger_fichiers(tache.get("fichiers") or [], racine=racine_tache)
    systeme = tache.get("systeme") or (
        "Tu es un relecteur technique rigoureux. Tu reponds en francais, de "
        "maniere concise et factuelle. Tu ne pretends jamais avoir verifie ce "
        "que tu n'as pas lu, et tu dis explicitement quand tu n'es pas sur."
    )
    contenu = consigne if not corpus else "%s\n\n%s" % (consigne, corpus)
    messages = [{"role": "system", "content": systeme},
                {"role": "user", "content": contenu}]
    plafond = int(tache.get("max_tokens") or 1500)
    temperature = tache.get("temperature", TEMPERATURE_DEFAUT)

    # Les plans gratuits s'enchainent SEULS. Un quota epuise, un refus ou
    # une reponse vide obligeaient quelqu'un a s'en apercevoir et a relancer
    # a la main sur un autre modele -- et ce quelqu'un etait le plan payant.
    # Une bascule est SUBIE, jamais choisie : elle ne coute que de la
    # capacite, n'elargit pas l'exposition des donnees, et n'atteint jamais
    # un alias facture au jeton.
    essais, echecs = [], []
    for candidat in [modele] + REPLIS_GRATUITS:
        if candidat in essais or candidat.startswith("claude-"):
            continue
        essais.append(candidat)
        try:
            resultat = appeler(candidat, messages, plafond, cle, temperature)
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")[:300]
            # Certains modeles refusent tout parametre d'echantillonnage non
            # defaut. Reessayer sans, plutot que de perdre le candidat.
            if temperature is not None and "temperature" in detail.lower():
                try:
                    resultat = appeler(candidat, messages, plafond, cle, None)
                except Exception as second:
                    echecs.append("%s : %s" % (candidat, second))
                    continue
            else:
                echecs.append("%s : HTTP %s : %s" % (candidat, exc.code, detail))
                continue
        except Exception as exc:
            echecs.append("%s : %s" % (candidat, exc))
            continue
        # Une reponse vide n'est pas une reponse : la compter comme telle
        # ferait conclure a un travail accompli qui ne l'a pas ete.
        if not (resultat.get("texte") or "").strip():
            echecs.append("%s : reponse vide (%d jetons consommes)"
                          % (candidat, resultat.get("tokens", 0)))
            continue
        resultat.update({"nom": nom, "modele": candidat, "refus": refus,
                         "plan": plan_de(resultat["adresse"])})
        # Une reponse servie par un autre modele que celui demande, sans le
        # dire, est un mensonge sur la mesure.
        if candidat != modele:
            resultat["bascule"] = "%s -> %s apres : %s" % (
                modele, candidat, " | ".join(echecs))
        return resultat

    return {"nom": nom, "modele": modele,
            "erreur": "tous les replis gratuits ont echoue : " + " | ".join(echecs)}


def rendre(resultat: dict) -> None:
    print("=" * 72)
    print("  %s" % resultat["nom"])
    if resultat.get("erreur"):
        print("  ECHEC : %s" % resultat["erreur"])
        print("=" * 72)
        return
    if resultat.get("bascule"):
        # Une bascule tue est une mesure faussee : le lecteur croirait le
        # modele demande capable de ce qu'un autre a produit.
        print("  BASCULE : %s" % resultat["bascule"])
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
    parseur.add_argument("--temperature", type=float, default=None,
                         help="Defaut %.1f. Ne monter au-dessus de 0.5 que "
                              "pour une redaction libre." % TEMPERATURE_DEFAUT)
    parseur.add_argument("--racine", help="Racine de travail explicite (remplace le calcul par défaut).")
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
                   "max_tokens": args.max_tokens,
                   "temperature": (args.temperature if args.temperature is not None
                                   else TEMPERATURE_DEFAUT),
                   "racine": args.racine}]
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
