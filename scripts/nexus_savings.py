# -*- coding: utf-8 -*-
"""
Mesure ce que la delegation fait réellement economiser.

Ce que ce rapport mesure, et ce qu'il ne mesure pas
---------------------------------------------------
Il compte le travail qui a transité par la passerelle : chaque requête, son
plan d'exécution, ses tokens, son coût réel. Il en deduit ce que le même
volume aurait coute sur Claude, et donc l'économie obtenue.

Il ne voit **pas** le trafic de l'abonnement claude.ai : celui-ci ne passe
pas par la passerelle, par construction. Le chiffre produit est donc
« volume détourne de l'abonnement », pas « pourcentage d'abonnement
restant ». Pretendre le contraire serait mesurer ce qu'on ne voit pas.

Le cout contrefactuel s'appuie sur les tarifs declares dans
litellm_config.yaml pour les modèles Anthropic — la même source que celle
qu'utilise le routeur, pour que les deux chiffres restent comparables.

Usage :
    python scripts/nexus_savings.py [--jours 7] [--json]
"""
from __future__ import annotations

import argparse
import collections
import datetime
import io
import json
import os
import re
import sys
import urllib.error
import urllib.request

# La sortie est souvent redirigee : journaux, STATE.md, sousprocessus.
# Sans cette ligne, Python ecrit dans la page de codes locale de Windows
# et les accents se degradent des que la sortie est capturee -- le
# resultat finissait commite dans rituels/STATE.md, donc visible sur
# GitHub. PYTHONUTF8 est deja pose pour LiteLLM dans le compose ;
# il manquait ici.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

try:
    import yaml
except ImportError:
    print("ERREUR: PyYAML requis", file=sys.stderr)
    sys.exit(1)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG = os.path.join(ROOT, "litellm_config.yaml")
BASE_URL = os.environ.get("NEXUS_LITELLM_URL", "http://127.0.0.1:4000")

# Modèle de référence du contrefactuel : celui qu'on aurait
# vraisemblablement employé sans delegation.
REFERENCE = "claude-sonnet-5"


def _clean_env_value(value: str) -> str:
    """Supprime les guillemets, les commentaires et le prefixe export."""
    # Retire le prefixe export si present
    value = re.sub(r"^\s*export\s+", "", value)
    # Supprime tout ce qui suit un # (commentaire)
    value = value.split("#", 1)[0].strip()
    # Enleve les guillemets simples ou doubles autour de la valeur
    if (value.startswith('"') and value.endswith('"')) or (
        value.startswith("'") and value.endswith("'")
    ):
        value = value[1:-1]
    return value.strip()


def master_key() -> str:
    """Retourne la clé maître LITELLM_MASTER_KEY.

    La clé peut être fournie via la variable d'environnement ou le fichier
    .env à la racine du projet. Si aucune clé n'est trouvée, une exception
    explicite est levée.
    """
    if os.environ.get("LITELLM_MASTER_KEY"):
        return os.environ["LITELLM_MASTER_KEY"]
    env_path = os.path.join(ROOT, ".env")
    if not os.path.isfile(env_path):
        raise RuntimeError("LITELLM_MASTER_KEY introuvable")
    with io.open(env_path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            match = re.match(r"^\s*LITELLM_MASTER_KEY\s*=\s*(.*)$", line)
            if match:
                raw = match.group(1).strip()
                if raw:
                    return _clean_env_value(raw)
    raise RuntimeError("LITELLM_MASTER_KEY introuvable")


def _safe_int(value) -> int:
    """Convertit en int, renvoie 0 si la conversion échoue, en loggant le problème."""
    try:
        return int(value)
    except Exception as exc:  # pragma: no cover
        print(f"AVERTISSEMENT: conversion int impossible ({exc})", file=sys.stderr)
        return 0


def _safe_float(value) -> float:
    """Convertit en float, renvoie 0.0 si la conversion échoue, en loggant le problème."""
    try:
        return float(value)
    except Exception as exc:  # pragma: no cover
        print(f"AVERTISSEMENT: conversion float impossible ({exc})", file=sys.stderr)
        return 0.0


def load_domains() -> tuple[dict[str, str], dict[str, tuple[float, float]]] | None:
    """
    Domaine et tarif de chaque alias, lus dans la configuration.

    Retourne ``None`` lorsqu'une erreur de lecture ou de format empêche
    l'extraction fiable des données. Les erreurs de schema sont signalees
    de façon precise afin d'éviter de masquer un bug réel.
    """
    try:
        with io.open(CONFIG, encoding="utf-8") as fh:
            config = yaml.safe_load(fh)
    except yaml.YAMLError as exc:
        print("Configuration illisible (%s) : %s" % (CONFIG, exc), file=sys.stderr)
        return None
    except Exception as exc:
        print("Erreur lors de la lecture de la configuration (%s) : %s"
              % (CONFIG, exc), file=sys.stderr)
        return None

    if not isinstance(config, dict):
        print("Configuration illisible (%s) : document vide ou non conforme"
              % CONFIG, file=sys.stderr)
        return None

    domains: dict[str, str] = {}
    prices: dict[str, tuple[float, float]] = {}

    for model in config.get("model_list") or []:
        # Protection contre les entrees malformées
        alias = model.get("model_name")
        if not isinstance(alias, str):
            continue
        params = model.get("litellm_params") or {}
        raw = str(params.get("model", ""))

        if raw.startswith("auto_router/"):
            continue

        # Determination du domaine en se basant sur l'URL d'API, pas sur le nom du modèle.
        api_base = str(params.get("api_base") or "")
        if "anthropic.com" in api_base:
            domains[alias] = "anthropic"
        elif "ollama.com" in api_base:
            domains[alias] = "cloud"
        elif raw.startswith("anthropic/"):
            # Repli de nom, et seulement pour Anthropic : un modele Anthropic
            # n'a souvent aucun api_base, LiteLLM employant le sien par defaut.
            # L'absence d'adresse n'y est donc pas un silence suspect.
            domains[alias] = "anthropic"
        else:
            # Un api_base pointant vers cette machine EST la preuve du local :
            # ce n'est pas un repli, et il n'y a rien a signaler.
            #
            # Mesure du 2026-08-30 : l'avertissement se declenchait 40 fois
            # par execution, une par modele local, c'est-a-dire sur le cas
            # parfaitement normal. Un avertissement qui crie sur la normale
            # n'avertit plus -- il noie le seul cas qui meritait d'etre vu,
            # celui d'un modele dont on ne sait pas ou il s'execute.
            #
            # Le classement, lui, ne change pas : ces modeles etaient deja
            # comptes locaux, et le sont toujours. Seul le bruit disparait.
            local_prouve = any(marque in str(params.get("api_base") or "")
                               for marque in ("host.docker.internal",
                                              "localhost", "127.0.0.1"))
            if local_prouve:
                domains[alias] = "local"
                continue

            # Classification par defaut : on signale le fallback pour eviter
            # les faux positifs d'economie.
            # stderr, et non stdout : --json ecrit sa mesure sur stdout, et un
            # avertissement place devant la rendait illisible au parseur. Le
            # controle « part deleguee » de nexus_conformite.py tombait ainsi
            # en IGNORE a chaque passage -- la mesure du produit central etait
            # aveugle, alors que la valeur, elle, etait calculee correctement.
            print("AVERTISSEMENT: le modele %s n'est pas reconnu, classifie comme local" % alias,
                  file=sys.stderr)
            domains[alias] = "local"

        # Extraction des tarifs ; on ignore les modèles dont le tarif est
        # invalide afin de ne pas interrompre le traitement complet.
        if params.get("input_cost_per_token"):
            try:
                price = (float(params["input_cost_per_token"]),
                         float(params.get("output_cost_per_token") or 0.0))
                prices[alias] = price
                prices[raw] = price
            except Exception as exc:  # pragma: no cover
                # Tarif invalide : on le consigne mais on poursuit.
                print("Tarif invalide pour le modele %s, ignore. (%s)" % (alias, exc),
                      file=sys.stderr)

    return domains, prices


def _validate_base_url(url: str) -> str:
    """Valide que l'URL possède un scheme http ou https."""
    if not url.startswith(("http://", "https://")):
        raise RuntimeError("BASE_URL invalide : doit commencer par http:// ou https://")
    return url.rstrip("/")


def fetch_logs(days: int) -> list[dict]:
    """
    Journal des requêtes, filtre côté client.

    Le filtre par dates de l'API s'est revele peu fiable ; on récupère donc
    une fenêtre large et on tranche sur ``startTime``, qui est present dans
    chaque enregistrement.
    """
    key = master_key()
    base = _validate_base_url(BASE_URL)
    request = urllib.request.Request(f"{base}/spend/logs?limit=5000")
    request.add_header("Authorization", "Bearer " + key)

    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise RuntimeError("Erreur HTTP %s lors de la recuperation des logs"
                           % exc.code) from exc
    except urllib.error.URLError as exc:
        raise RuntimeError("Erreur reseau lors de la recuperation des logs: %s"
                           % exc.reason) from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError("Reponse JSON invalide : %s" % exc) from exc

    entries = payload if isinstance(payload, list) else payload.get("data", [])

    # Avertir si le nombre d'entrees atteint la limite connue.
    if len(entries) >= 5000:
        print("AVERTISSEMENT: le serveur a pu tronquer les logs a 5000 entrees",
              file=sys.stderr)

    limite = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=days)
    retenus = []
    for entry in entries:
        tags = [str(t) for t in (entry.get("request_tags") or [])]
        if any("health-check" in t for t in tags):
            continue
        stamp = str(entry.get("startTime") or entry.get("created_at") or "")
        try:
            # Convertit en datetime UTC, en ignorant le suffixe Z et les fractions.
            iso = stamp.replace("Z", "")
            if "." in iso:
                iso = iso.split(".", 1)[0]
            moment = datetime.datetime.fromisoformat(iso)
            if moment.tzinfo is None:
                moment = moment.replace(tzinfo=datetime.timezone.utc)
            else:
                moment = moment.astimezone(datetime.timezone.utc)
        except Exception as exc:  # pragma: no cover
            # Horodatage illisible : on loggue le problème avant d'ignorer l'entree.
            print(f"AVERTISSEMENT: horodatage invalide ({exc})", file=sys.stderr)
            continue
        if moment >= limite:
            retenus.append(entry)
    return retenus


def domain_of(entry: dict, domains: dict[str, str]) -> str:
    """
    Determine le plan d'execution d'une requete.

    ``api_base`` prime sur le nom : il indique ou la requete est réellement
    partie, ce qu'aucun alias ne garantit.
    """
    api_base = str(entry.get("api_base") or "")
    if "ollama.com" in api_base:
        return "cloud"
    if "ollama" in api_base or "11434" in api_base:
        return "local"
    if "anthropic.com" in api_base:
        return "anthropic"

    for field in ("model_group", "model"):
        alias = entry.get(field)
        if alias and alias in domains:
            return domains[alias]

    alias = str(entry.get("model", ""))
    if alias.startswith("ollama"):
        return "cloud" if ":cloud" in alias else "local"
    # Le test sur le nom du modele (ex: "claude") est supprime, on se fie a api_base.
    return "inconnu"


def _positive_int(value: str) -> int:
    """Convertit en int et verifie qu'il est >= 1."""
    ivalue = int(value)
    if ivalue < 1:
        raise argparse.ArgumentTypeError("Le nombre de jours doit etre >= 1")
    return ivalue


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--jours", type=_positive_int, default=7,
                        help="Nombre de jours a analyser (minimum 1)")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    charge = load_domains()
    if charge is None:
        print("Sans les domaines ni les tarifs, aucun plan ne peut etre")
        print("attribue : le rapport s'arrete plutot que d'annoncer une")
        print("economie nulle sur une configuration qu'il n'a pas su lire.")
        return 1
    domains, prices = charge

    try:
        logs = fetch_logs(args.jours)
    except Exception as exc:
        print("Journaux de depense illisibles : %s" % exc)
        return 1

    if not logs:
        print("Aucune requete enregistree sur %d jour(s)." % args.jours)
        print("La mesure suppose un usage reel : deleguer d'abord, mesurer ensuite.")
        return 0

    par_plan = collections.defaultdict(
        lambda: {"requetes": 0, "entree": 0, "sortie": 0, "cout": 0.0,
                 "sans_sortie": 0})
    par_modele = collections.Counter()

    for entry in logs:
        plan = domain_of(entry, domains)
        stats = par_plan[plan]
        stats["requetes"] += 1
        # Un appel qui n'a rien produit n'a pas traite de volume.
        #
        # Mesure du 2026-08-30 : neuf appels a claude-fable-5, 65 403 jetons
        # d'entree, ZERO de sortie, cout nul. Ils ont echoue avant de
        # generer. Leur entree pese pourtant au denominateur de la part
        # deleguee, et representait exactement les 0,6 % manquants.
        #
        # Le chiffre n'est PAS corrige pour autant, et c'est delibere : les
        # retrancher flatterait la mesure, exactement comme le faisait jadis
        # l'inclusion du trafic de sante (111). Ils sont comptes comme avant,
        # et signales a cote -- au lecteur de savoir ce que le chiffre
        # recouvre, plutot qu'a l'outil de choisir pour lui.
        # Un embedding n'a PAS de completion_tokens : c'est sa nature, pas
        # un echec. Les compter ici donnait 213 « echecs » locaux sur 1034,
        # soit un indicateur qui aurait fait chercher une panne inexistante
        # -- le defaut meme que cet indicateur est cense reveler ailleurs.
        modele = str(entry.get("model_group") or entry.get("model") or "")
        bas = modele.lower()
        est_embedding = ("embed" in bas or "minilm" in bas or "bge-" in bas)

        # Un modele qui n'est pas declare n'est pas en panne : c'est une
        # epreuve de refus. La suite REVERSE appelle exprès
        # « modele-qui-nexiste-pas » et « phi3-mini-local-inexistant » pour
        # verifier que la passerelle les rejette ; leur echec EST le
        # resultat attendu.
        #
        # Deuxieme fois que ce meme piege se presente : apres les
        # embeddings, dont l'absence de sortie est la nature. Un indicateur
        # d'echec doit connaitre les echecs qui n'en sont pas, sans quoi il
        # envoie chercher des pannes inexistantes.
        est_declare = modele in domains
        if est_declare and not est_embedding and not _safe_int(
                entry.get("completion_tokens")):
            stats["sans_sortie"] += 1
        stats["entree"] += _safe_int(entry.get("prompt_tokens"))
        stats["sortie"] += _safe_int(entry.get("completion_tokens"))
        stats["cout"] += _safe_float(entry.get("spend"))
        par_modele[entry.get("model_group") or entry.get("model") or "?"] += 1

    reference = prices.get(REFERENCE)
    chiffrable = reference is not None
    delegue = {k: v for k, v in par_plan.items() if k in ("local", "cloud")}
    tokens_delegues_entree = sum(v["entree"] for v in delegue.values())
    tokens_delegues_sortie = sum(v["sortie"] for v in delegue.values())
    cout_delegue_reel = sum(v["cout"] for v in delegue.values())
    cout_contrefactuel = (
        (tokens_delegues_entree * reference[0]
         + tokens_delegues_sortie * reference[1]) if chiffrable else None)
    cout_anthropic = par_plan.get("anthropic", {}).get("cout", 0.0)

    total_tokens = sum(v["entree"] + v["sortie"] for v in par_plan.values())
    tokens_delegues = tokens_delegues_entree + tokens_delegues_sortie
    part_deleguee = (tokens_delegues / total_tokens * 100) if total_tokens else 0.0

    if args.json:
        print(json.dumps({
            "jours": args.jours,
            "par_plan": {k: dict(v) for k, v in par_plan.items()},
            "tokens_delegues": tokens_delegues,
            "part_deleguee_pct": round(part_deleguee, 1),
            "cout_delegue_reel": round(cout_delegue_reel, 4),
            "cout_contrefactuel":
                round(cout_contrefactuel, 4) if chiffrable else None,
            "economie":
                round(cout_contrefactuel - cout_delegue_reel, 4) if chiffrable else None,
            "economie_indisponible":
                None if chiffrable else
                "tarif de reference '%s' absent de litellm_config.yaml" % REFERENCE,
        }, indent=2, ensure_ascii=False))
        return 0

    print("=" * 70)
    print(" Delegation et economie - %d dernier(s) jour(s)" % args.jours)
    print("=" * 70)
    print("  %d requetes passees par la passerelle" % len(logs))

    print("\n  %-12s %8s %12s %12s %12s" % ("Plan", "Requetes", "Entree", "Sortie", "Cout reel"))
    print("  " + "-" * 60)
    for plan in ("local", "cloud", "anthropic", "inconnu"):
        if plan not in par_plan:
            continue
        v = par_plan[plan]
        print("  %-12s %8d %12d %12d %12s"
              % (plan, v["requetes"], v["entree"], v["sortie"],
                 ("%.4f $" % v["cout"]) if v["cout"] else "0"))

    print("\n  Part deleguee : %.1f %% des tokens (%d sur %d)"
          % (part_deleguee, tokens_delegues, total_tokens))

    # Les appels qui n'ont rien produit, dits a cote du chiffre et non
    # retranches.
    #
    # Mesure du 2026-08-30 : neuf appels a claude-fable-5, 65 403 jetons
    # d'entree, ZERO de sortie, cout nul -- des echecs avant generation.
    # Leur entree pese pourtant au denominateur, et representait exactement
    # les 0,6 % manquants.
    #
    # Le chiffre n'est PAS corrige, et c'est delibere : les retrancher
    # flatterait la mesure, exactement comme le faisait jadis l'inclusion
    # du trafic de sante (111). Au lecteur de savoir ce que le chiffre
    # recouvre, plutot qu'a l'outil de choisir pour lui.
    muets = [(plan, v) for plan, v in sorted(par_plan.items())
             if v.get("sans_sortie")]
    if muets:
        print(chr(10) + "  Dont appels sans aucune sortie (echecs avant generation) :")
        for plan, v in muets:
            taux = (v["sans_sortie"] / v["requetes"] * 100) if v["requetes"] else 0.0
            print("    %-10s %d requete(s) (%.1f%%) sur %d" % (plan, v["sans_sortie"],
                                                               taux, v["requetes"]))
        print("    Leur entree reste au denominateur : la retrancher")
        print("    flatterait la mesure au lieu de la corriger.")
        print("    Un appel sans sortie a consommé son entrée et son temps sans rien rendre ;")
        print("    la cause la plus fréquente mesurée est un budget de sortie trop serré.")

    if chiffrable:
        print("\n  Contrefactuel - ce que le volume delegue aurait coute sur %s :" % REFERENCE)
        print("    cout evite    : %.4f $" % cout_contrefactuel)
        print("    cout reel     : %.4f $" % cout_delegue_reel)
        print("    economie      : %.4f $" % (cout_contrefactuel - cout_delegue_reel))
    else:
        print("\n  Contrefactuel indisponible : le tarif de '%s' n'est pas" % REFERENCE)
        print("  declare dans litellm_config.yaml. Le volume delegue ci-dessus")
        print("  reste exact ; seule sa conversion en dollars manque.")
    if cout_anthropic:
        print("    depense API   : %.4f $ (Anthropic, hors abonnement)" % cout_anthropic)

    # Note : le cout reel des delegations locales ne prend pas en compte le
    # cout d'infrastructure (GPU, electricite, maintenance). Le chiffre
    # indique uniquement le montant facture par le fournisseur.
    print("\n  Modeles les plus sollicites :")
    for alias, count in par_modele.most_common(6):
        print("    %-32s %d" % (alias, count))

    print("\n" + "-" * 70)
    print("""
  Ce que ce chiffre dit, et ce qu'il ne dit pas.

  Il mesure le volume détourne de l'abonnement, pas le pourcentage
  d'abonnement restant : le trafic de claude.ai ne passe pas par la
  passerelle et reste donc invisible ici. Il n'y a pas de seuil a
  atteindre — la part deleguee est une grandeur a maximiser, et elle ne
  progresse qu'en confiant reellement le volume aux outils du pont
  plutot qu'en lisant les fichiers directement.

  Les trois leviers, par ordre de rendement :
    nexus_search      repondre sans charger les fichiers entiers
    nexus_context     traiter un corpus entier hors de l'abonnement
    nexus_summarize   distiller avant de raisonner
""")
    return 0


if __name__ == "__main__":
    sys.exit(main())
