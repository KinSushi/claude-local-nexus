# -*- coding: utf-8 -*-
"""
Mesure ce que la délégation fait réellement économiser.

Ce que ce rapport mesure, et ce qu'il ne mesure pas
---------------------------------------------------
Il compte le travail qui a transité par la passerelle : chaque requête, son
plan d'exécution, ses tokens, son coût réel. Il en déduit ce que le même
volume aurait coûté sur Claude, et donc l'économie obtenue.

Il ne voit **pas** le trafic de l'abonnement claude.ai : celui-ci ne passe
pas par la passerelle, par construction. Le chiffre produit est donc
« volume détourné de l'abonnement », et non « pourcentage de l'abonnement
restant ». Prétendre le contraire serait mesurer ce qu'on ne voit pas.

Le coût contrefactuel s'appuie sur les tarifs déclarés dans
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
import urllib.request

# La sortie est souvent redirigee : journaux, STATE.md, sous-processus.
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
    print("ERREUR: PyYAML est requis")
    sys.exit(1)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG = os.path.join(ROOT, "litellm_config.yaml")
BASE_URL = os.environ.get("NEXUS_LITELLM_URL", "http://127.0.0.1:4000")

# Modèle de référence du contrefactuel : celui qu'on aurait
# vraisemblablement employé sans délégation.
REFERENCE = "claude-sonnet-5"


def master_key() -> str:
    if os.environ.get("LITELLM_MASTER_KEY"):
        return os.environ["LITELLM_MASTER_KEY"]
    with io.open(os.path.join(ROOT, ".env"), encoding="utf-8",
                 errors="replace") as fh:
        for line in fh:
            match = re.match(r"^\s*LITELLM_MASTER_KEY\s*=\s*(.*)$", line)
            if match and match.group(1).strip():
                return match.group(1).strip()
    raise RuntimeError("LITELLM_MASTER_KEY introuvable")


def load_domains() -> tuple[dict[str, str], dict[str, tuple[float, float]]] | None:
    """
    Domaine et tarif de chaque alias, lus dans la configuration.

    Rend `None` — jamais un couple vide — quand la configuration est
    illisible, pour deux raisons distinctes. Sans garde, un
    `litellm_config.yaml` corrompu remontait une trace `yaml` nue : le
    rapport de délégation mourait sur une pile d'appels au lieu de dire
    quel fichier relire. Et un repli sur des dictionnaires vides serait
    pire que la trace, car il produirait un rapport d'apparence normale :
    chaque requête tomberait dans « inconnu », le contrefactuel Claude
    vaudrait zéro, et le chiffre d'économie serait faux sans que rien ne
    le signale. Sa jumelle `declares_sans_poids`, dans nexus_pull_host.py,
    garde déjà la même lecture de la même façon.
    """
    try:
        with io.open(CONFIG, encoding="utf-8") as fh:
            config = yaml.safe_load(fh)
    except Exception as exc:
        # La cause n'est connue qu'ici : l'appelant ne verrait qu'un `None`
        # et ne pourrait pas nommer le fichier ni la ligne fautive.
        print("Configuration illisible (%s) : %s" % (CONFIG, exc))
        return None
    # Un fichier tronqué s'analyse sans erreur et rend `None` : la garde
    # ci-dessus le laisserait passer, et c'est `config.get` qui lèverait la
    # trace nue qu'on vient précisément de supprimer.
    if not isinstance(config, dict):
        print("Configuration illisible (%s) : document vide ou non conforme"
              % CONFIG)
        return None
    domains: dict[str, str] = {}
    prices: dict[str, tuple[float, float]] = {}
    for model in config.get("model_list") or []:
        alias = model["model_name"]
        params = model.get("litellm_params") or {}
        raw = str(params.get("model", ""))
        if raw.startswith("auto_router/"):
            continue
        if raw.startswith("anthropic/"):
            domains[alias] = "anthropic"
        elif "ollama.com" in str(params.get("api_base", "")):
            domains[alias] = "cloud"
        else:
            domains[alias] = "local"
        # Les tarifs sont indexés sur les deux formes : l'alias et le nom
        # amont, car les journaux emploient tantôt l'un tantôt l'autre.
        if params.get("input_cost_per_token"):
            price = (float(params["input_cost_per_token"]),
                     float(params.get("output_cost_per_token") or 0.0))
            prices[alias] = price
            prices[raw] = price
    return domains, prices


def fetch_logs(days: int) -> list[dict]:
    """
    Journal des requêtes, filtré côté client.

    Le filtre par dates de l'API s'est révélé peu fiable ; on récupère donc
    une fenêtre large et on tranche sur `startTime`, qui est présent dans
    chaque enregistrement.
    """
    key = master_key()
    request = urllib.request.Request("%s/spend/logs?limit=5000" % BASE_URL)
    request.add_header("Authorization", "Bearer " + key)
    with urllib.request.urlopen(request, timeout=90) as response:
        payload = json.loads(response.read().decode("utf-8"))
    entries = payload if isinstance(payload, list) else payload.get("data", [])

    limite = datetime.datetime.now() - datetime.timedelta(days=days)
    retenus = []
    for entry in entries:
        # Le trafic de sonde est ecarte, et ce n'est pas un detail : sur une
        # journee ordinaire il represente 93 % des requetes. L'inclure
        # produirait un taux de delegation flatteur mesurant la plateforme
        # en train de s'observer elle-meme.
        tags = [str(t) for t in (entry.get("request_tags") or [])]
        if any("health-check" in t for t in tags):
            continue
        stamp = str(entry.get("startTime") or entry.get("created_at") or "")
        try:
            moment = datetime.datetime.fromisoformat(
                stamp.replace("Z", "").split(".")[0])
        except Exception:
            retenus.append(entry)  # horodatage illisible : on ne l'écarte pas
            continue
        if moment >= limite:
            retenus.append(entry)
    return retenus


def domain_of(entry: dict, domains: dict[str, str]) -> str:
    """
    Plan d'exécution d'une requête.

    `api_base` prime sur le nom : il dit où la requête est réellement
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
    if "claude" in alias:
        return "anthropic"
    return "inconnu"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--jours", type=int, default=7)
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
        lambda: {"requetes": 0, "entree": 0, "sortie": 0, "cout": 0.0})
    par_modele = collections.Counter()

    for entry in logs:
        plan = domain_of(entry, domains)
        stats = par_plan[plan]
        stats["requetes"] += 1
        stats["entree"] += int(entry.get("prompt_tokens") or 0)
        stats["sortie"] += int(entry.get("completion_tokens") or 0)
        stats["cout"] += float(entry.get("spend") or 0.0)
        par_modele[entry.get("model_group") or entry.get("model") or "?"] += 1

    # Sans tarif de référence configuré, il n'y a pas de contrefactuel à
    # calculer. La version précédente substituait un tarif écrit en dur :
    # le rapport annonçait alors une économie en dollars construite sur un
    # prix inventé, sans le dire. Un chiffre faux présenté comme mesuré est
    # pire qu'une case vide — il se cite, se compare et se propage.
    # Les tokens, eux, restent comptés : ils ne dépendent d'aucun tarif.
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
            # Un `null` sans explication serait lu comme « zéro économie ».
            # Le motif accompagne donc la case vide.
            "economie_indisponible":
                None if chiffrable else
                "tarif de reference '%s' absent de litellm_config.yaml" % REFERENCE,
        }, indent=2, ensure_ascii=False))
        return 0

    print("=" * 70)
    print(" Delegation et economie — %d dernier(s) jour(s)" % args.jours)
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

    if chiffrable:
        print("\n  Contrefactuel — ce que le volume delegue aurait coute sur %s :" % REFERENCE)
        print("    cout evite    : %.4f $" % cout_contrefactuel)
        print("    cout reel     : %.4f $" % cout_delegue_reel)
        print("    economie      : %.4f $" % (cout_contrefactuel - cout_delegue_reel))
    else:
        print("\n  Contrefactuel indisponible : le tarif de '%s' n'est pas" % REFERENCE)
        print("  declare dans litellm_config.yaml. Le volume delegue ci-dessus")
        print("  reste exact ; seule sa conversion en dollars manque.")
    if cout_anthropic:
        print("    depense API   : %.4f $ (Anthropic, hors abonnement)" % cout_anthropic)

    print("\n  Modeles les plus sollicites :")
    for alias, count in par_modele.most_common(6):
        print("    %-32s %d" % (alias, count))

    print("\n" + "-" * 70)
    print("""
  Ce que ce chiffre dit, et ce qu'il ne dit pas.

  Il mesure le volume detourne de l'abonnement, pas le pourcentage
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
