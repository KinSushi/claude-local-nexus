# -*- coding: utf-8 -*-
"""
Validation d'intégrité de la configuration Claude-Local-Nexus.

Vérifie que la configuration LiteLLM est cohérente AVANT tout redémarrage :
aucune référence pendante, aucun cycle de fallback, aucune incompatibilité
de modalité, aucun secret manquant.

Usage :
    python scripts/nexus_validate.py [--config <fichier>]

Codes de sortie :
    0  configuration valide (des avertissements restent possibles)
    1  au moins une erreur bloquante
"""
from __future__ import annotations

import io
import os
import re
import subprocess
import sys

try:
    import yaml
except ImportError:
    print("ERREUR: PyYAML est requis (pip install pyyaml)")
    sys.exit(1)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nexus_capability as capability  # noqa: E402

# La sortie est souvent redirigee : journaux, STATE.md, sous-processus.
# Sans cette ligne, Python ecrit dans la page de codes locale de Windows
# et les accents se degradent des que la sortie est capturee -- le
# resultat finissait commite dans rituels/STATE.md, donc visible sur
# GitHub. PYTHONUTF8 est deja pose pour LiteLLM dans le compose ;
# il manquait ici.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Le fichier a juger peut etre un candidat, pas encore en place : c'est ce
# qui permet de valider AVANT de remplacer une configuration qui tourne.
CONFIG = os.path.join(ROOT, "litellm_config.yaml")
for _i, _a in enumerate(sys.argv):
    if _a == "--config" and _i + 1 < len(sys.argv):
        CONFIG = sys.argv[_i + 1]

errors: list[str] = []
warnings: list[str] = []

# `-vl` couvre les Qwen-VL, que `vision|llava` laissait passer : ils
# étaient classés « texte », et un repli les faisant tomber sur un modèle
# aveugle n'aurait déclenché aucune erreur.
VISION = re.compile(r"vision|llava|-vl[-:]|-vl$")
EMBED = re.compile(r"embed|minilm")


def classify(alias: str) -> str:
    """Modalité déduite de l'alias, pour vérifier la compatibilité des fallbacks."""
    if EMBED.search(alias):
        return "embedding"
    if VISION.search(alias):
        return "vision"
    return "text"


def load_config() -> dict:
    with io.open(CONFIG, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def flatten_fallbacks(entries) -> list[tuple[str, list[str]]]:
    """Les fallbacks LiteLLM sont une liste de dicts à une seule clé."""
    out = []
    for entry in entries or []:
        for source, targets in entry.items():
            out.append((source, list(targets or [])))
    return out


def main() -> int:
    cfg = load_config()

    # --- 1. Alias déclarés, doublons -------------------------------------
    model_list = cfg.get("model_list") or []
    declared: list[str] = [m["model_name"] for m in model_list]
    seen: set[str] = set()
    for alias in declared:
        if alias in seen:
            errors.append("alias dupliqué dans model_list : %s" % alias)
        seen.add(alias)
    known = set(declared)

    # --- 2. Références des routeurs adaptatifs ---------------------------
    #
    # Domaines qu'un routeur a le droit de contenir. L'intention est portée
    # par son nom : `adaptive-router-local` promet du local, et c'est
    # précisément la promesse qu'il faut vérifier.
    #
    # Ce contrôle manquait, et son absence était démontrable : un modèle
    # cloud glissé dans le pool de `adaptive-router-local` passait la
    # validation sans un mot, parce que les routeurs étaient exclus du
    # calcul des domaines. Le trou se trouvait exactement là où la
    # frontière est annoncée.
    ROUTER_DOMAINS = {
        "adaptive-router-local": {"local"},
        "adaptive-router-cloud": {"cloud"},
        "adaptive-router-anthropic": {"anthropic"},
        # Le routeur global couvre local et cloud, jamais Anthropic :
        # engager une dépense n'est pas une décision de routage.
        "adaptive-router": {"local", "cloud"},
    }

    routers: dict[str, list[str]] = {}
    for m in model_list:
        params = m.get("litellm_params") or {}
        if not str(params.get("model", "")).startswith("auto_router/"):
            continue
        alias = m["model_name"]
        rcfg = params.get("adaptive_router_config") or {}
        candidates = list(rcfg.get("available_models") or [])
        routers[alias] = candidates
        if not candidates:
            errors.append("routeur %s : pool available_models vide" % alias)
        for cand in candidates:
            if cand not in known:
                errors.append("routeur %s : candidat inexistant '%s'" % (alias, cand))
        default = params.get("adaptive_router_default_model")
        if default and default not in known:
            errors.append("routeur %s : default_model inexistant '%s'" % (alias, default))
        elif default and default not in candidates:
            warnings.append("routeur %s : default_model '%s' hors du pool" % (alias, default))

    # Le contrôle de domaine du pool a besoin de `domains`, calculé plus
    # bas : il est donc appliqué juste après, section 2 bis.

    # --- 3. Graphe de fallback ------------------------------------------
    router_settings = cfg.get("router_settings") or {}
    graphes: dict[str, dict[str, list[str]]] = {}

    # Domaine d'exécution de chaque alias, pour juger la direction des replis.
    domains: dict[str, str] = {}
    for m in model_list:
        params = m.get("litellm_params") or {}
        raw_model = str(params.get("model", ""))
        if raw_model.startswith("auto_router/"):
            continue
        if raw_model.startswith("anthropic/"):
            domains[m["model_name"]] = "anthropic"
        elif "ollama.com" in str(params.get("api_base", "")):
            domains[m["model_name"]] = "cloud"
        else:
            domains[m["model_name"]] = "local"

    # --- 2 bis. Le pool d'un routeur respecte-t-il sa promesse ? --------
    for alias, candidates in routers.items():
        autorises = ROUTER_DOMAINS.get(alias)
        if not autorises:
            warnings.append("routeur %s : nom inconnu, domaine non verifiable" % alias)
            continue
        for cand in candidates:
            domaine = domains.get(cand)
            if domaine and domaine not in autorises:
                errors.append(
                    "routeur %s : le pool contient '%s' (%s), hors des domaines "
                    "annonces par son nom (%s)"
                    % (alias, cand, domaine, ", ".join(sorted(autorises))))
        # Un routeur porte le domaine le moins confidentiel de son pool :
        # c'est ce qu'il peut réellement exposer, et donc ce qu'il faut
        # opposer aux contrôles de direction de repli.
        rang = {"local": 0, "cloud": 1, "anthropic": 2}
        presents = [domains[c] for c in candidates if c in domains]
        if presents:
            domains[alias] = max(presents, key=lambda d: rang.get(d, 0))

    # LiteLLM connait plusieurs listes de repli. N'en inspecter que deux
    # laissait passer des alias pendants ET une fuite local -> cloud dans
    # les autres, sans un mot.
    listes_de_repli = (
        ("fallbacks", router_settings.get("fallbacks")),
        ("context_window_fallbacks", cfg.get("context_window_fallbacks")),
        ("default_fallbacks", router_settings.get("default_fallbacks")),
        ("content_policy_fallbacks", router_settings.get("content_policy_fallbacks")),
        ("context_window_fallbacks (router)", router_settings.get("context_window_fallbacks")),
    )
    for label, entries in listes_de_repli:
        for source, targets in flatten_fallbacks(entries):
            if source not in known:
                errors.append("%s : source inexistante '%s'" % (label, source))
            if not targets:
                warnings.append("%s : '%s' n'a aucune cible" % (label, source))
            for target in targets:
                if target not in known:
                    errors.append("%s : '%s' retombe sur '%s' qui n'existe pas"
                                  % (label, source, target))
                    continue
                # Modalité : un embedding ne retombe que sur un embedding,
                # une vision que sur une vision (§17).
                # La regle est symetrique : un embedding ne retombe pas sur
                # un modele de chat, et un modele de chat ne retombe pas sur
                # un embedding. Restreindre le controle au sens descendant
                # laissait passer gemma4-12b-local -> all-minilm-local.
                src_kind, dst_kind = classify(source), classify(target)
                if src_kind != dst_kind:
                    errors.append("%s : '%s' (%s) retombe sur '%s' (%s) — modalité incompatible"
                                  % (label, source, src_kind, target, dst_kind))

                # Direction du repli. La règle est asymétrique à dessein :
                # se replier vers le local ne fait perdre que de la
                # capacité, tandis que sortir vers le cloud ou Anthropic
                # élargirait l'exposition des données et engagerait une
                # dépense que personne n'a demandée. Un repli est subi,
                # jamais choisi : il ne doit pas décider à notre place.
                src_domain = domains.get(source)
                dst_domain = domains.get(target)
                if src_domain and dst_domain and src_domain != dst_domain \
                        and dst_domain != "local":
                    errors.append(
                        "%s : '%s' (%s) retombe sur '%s' (%s) — un repli ne "
                        "peut aller que vers plus de confidentialité"
                        % (label, source, src_domain, target, dst_domain))
            # Un graphe PAR LISTE, et non un graphe unique.
            #
            # `fallbacks` descend en capacite, `context_window_fallbacks`
            # remonte vers une fenetre plus large : les fusionner fabrique
            # des cycles qui n'en sont pas, puisque LiteLLM n'emprunte
            # jamais les deux types d'arcs dans la meme defaillance. Mais
            # les ignorer laissait passer un vrai cycle place ailleurs que
            # dans `fallbacks`.
            graphes.setdefault(label, {}).setdefault(source, []).extend(
                t for t in targets if t in known)

    # --- 4. Cycles, liste par liste -------------------------------------
    WHITE, GREY, BLACK = 0, 1, 2

    for label, graph in graphes.items():
        color: dict[str, int] = {}

        def visit(node: str, path: list[str]) -> None:
            color[node] = GREY
            for nxt in graph.get(node, []):
                state = color.get(nxt, WHITE)
                if state == GREY:
                    cycle = path[path.index(nxt):] if nxt in path else [nxt]
                    errors.append("cycle dans %s : %s"
                                  % (label, " -> ".join(cycle + [nxt])))
                elif state == WHITE:
                    visit(nxt, path + [nxt])
            color[node] = BLACK

        for node in list(graph):
            if color.get(node, WHITE) == WHITE:
                visit(node, [node])

    # Le graphe des replis proprement dits sert aussi a la fermeture
    # transitive de la section suivante.
    graph = graphes.get("fallbacks", {})

    # --- 5. Variables d'environnement référencées -----------------------
    env_present: set[str] = set(os.environ)
    env_file = os.path.join(ROOT, ".env")
    if os.path.exists(env_file):
        with io.open(env_file, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                match = re.match(r"^\s*([A-Z0-9_]+)\s*=\s*(.*)$", line)
                if match and match.group(2).strip():
                    env_present.add(match.group(1))
    for m in model_list:
        for value in (m.get("litellm_params") or {}).values():
            if isinstance(value, str) and value.startswith("os.environ/"):
                name = value.split("/", 1)[1]
                if name not in env_present:
                    errors.append("modèle %s : variable %s non définie"
                                  % (m["model_name"], name))

    # --- 6. Inventaire Ollama vs configuration --------------------------
    # Le profil sert des la section 6, pour distinguer un modele oublie
    # d'un modele deliberement ecarte.
    profile_materiel = capability.build_profile()
    # Un seul inventaire, celui du moteur qui sert réellement. Le
    # validateur en relançait un second, `docker exec ollama-server` écrit
    # en dur : après la sortie du moteur hors de Docker, il a continué de
    # décrire un conteneur supprimé, échoué, et — parce qu'un inventaire
    # vide entrait dans le même `if installed:` qu'un inventaire réussi —
    # s'est tu. Toute la section 6 a disparu sans un mot, au moment précis
    # où huit alias venaient de perdre leurs poids. Un inventaire illisible
    # n'est pas un inventaire vide : il doit s'entendre.
    tailles_installees = capability.installed_models()
    if tailles_installees is None:
        errors.append(
            "inventaire du moteur illisible : impossible de verifier qu'un "
            "modele declare existe reellement. Verifiez que le moteur Ollama "
            "designe par la configuration repond."
        )
        installed: set[str] = set()
    else:
        installed = set(tailles_installees)
        if not installed:
            warnings.append("le moteur ne sert aucun modele local")

    if installed:
        referenced_local: set[str] = set()
        for m in model_list:
            model = str((m.get("litellm_params") or {}).get("model", ""))
            base = model.split("/", 1)[1] if "/" in model else ""
            if model.startswith(("ollama/", "ollama_chat/")) and "ollama.com" not in str(
                (m.get("litellm_params") or {}).get("api_base", "")
            ):
                referenced_local.add(base)
                if base not in installed and base + ":latest" not in installed:
                    errors.append("modèle %s : '%s' déclaré mais absent d'Ollama"
                                  % (m["model_name"], base))
        # ':latest' n'est qu'un tag implicite : 'codestral:latest' installé et
        # 'codestral' référencé désignent le même modèle. Comparer les deux
        # formes brutes produirait un avertissement pour chaque modèle sans
        # tag explicite.
        def canonical(name: str) -> str:
            return name[: -len(":latest")] if name.endswith(":latest") else name

        canonical_refs = {canonical(b) for b in referenced_local}
        for base in sorted(installed):
            if canonical(base) in canonical_refs:
                continue
            # Distinguer « oublié » de « refusé ». Reprocher à un modèle de
            # ne pas être exposé alors que le garde-fou vient de l'écarter
            # produisait un avertissement inextinguible : l'opérateur ne
            # pouvait ni le corriger, ni le faire taire.
            taille = tailles_installees.get(base, 0.0)
            etat, motif = capability.verdict(taille, profile_materiel)
            if etat == capability.REJECT:
                warnings.append("non exposé à dessein : %s — %s" % (base, motif))
            else:
                warnings.append("installé mais non exposé : %s" % base)

    # --- 7. Garde-fou materiel ------------------------------------------
    # La machine est mesuree, pas supposee. Un modele plus lourd que la
    # memoire du moteur ne rate pas franchement : il pagine, et la reponse
    # n'arrive jamais utilement. Le laisser selectionnable automatiquement
    # revient a tirer au sort une reponse qui ne viendra pas (§26).
    profile = profile_materiel
    sizes = capability.installed_models()
    if sizes is None:
        errors.append("inventaire des modeles illisible : verdict materiel impossible")
        sizes = {}

    # Tout ce qui peut etre choisi SANS decision humaine : candidats de
    # routeur et cibles de fallback.
    selectable: set[str] = set()
    for candidates in routers.values():
        selectable.update(candidates)
    # Toutes les listes de repli, et pas seulement `fallbacks` : un modèle
    # inexécutable restait accepté comme cible de `context_window_fallbacks`.
    for _, entries in listes_de_repli:
        for entry in (entries or []):
            for targets in entry.values():
                selectable.update(targets or [])
    # Le `default_model` est le chemin le plus servi quand le routeur ne
    # tranche pas : il doit subir le même budget que les candidats du pool.
    for m in model_list:
        defaut = (m.get("litellm_params") or {}).get("adaptive_router_default_model")
        if defaut:
            selectable.add(defaut)

    for m in model_list:
        alias = m["model_name"]
        params = m.get("litellm_params") or {}
        raw_model = str(params.get("model", ""))
        if "ollama.com" in str(params.get("api_base", "")):
            continue  # execute chez le fournisseur, pas ici
        if not raw_model.startswith(("ollama/", "ollama_chat/")):
            continue
        base = raw_model.split("/", 1)[1]
        size = sizes.get(base) or sizes.get(base + ":latest") or 0.0
        state, reason = capability.verdict(size, profile)
        if state == capability.REJECT:
            message = "modele %s : %s" % (alias, reason)
            if alias in selectable:
                errors.append(message + " — selectionnable automatiquement")
            else:
                warnings.append(message + " — declare mais inexecutable")
        elif state == capability.DEGRADED and alias in selectable:
            errors.append("modele %s : %s — a retirer des pools" % (alias, reason))

    if profile["ollama"]["mode"].startswith("docker"):
        perdu = profile["host_ram_gb"] - profile["inference_memory_gb"]
        if perdu > 4:
            warnings.append(
                "moteur dans Docker : %.0f Go des %.0f Go de la machine sont "
                "hors d'atteinte de l'inference"
                % (perdu, profile["host_ram_gb"]))

    # --- 8. Politique de cache ------------------------------------------
    cache_params = (cfg.get("litellm_settings") or {}).get("cache_params") or {}
    if cache_params.get("type") == "redis-semantic":
        warnings.append(
            "cache sémantique actif : risque de réponse erronée sur les appels "
            "d'outils et les étapes d'agent (§27)"
        )

    # --- Rapport ---------------------------------------------------------
    print("=" * 60)
    print(" Validation de la configuration Claude-Local-Nexus")
    print("=" * 60)
    print("  Modèles déclarés  : %d" % len(declared))
    print("  Routeurs          : %d" % len(routers))
    print("  Arcs de fallback  : %d" % sum(len(v) for v in graph.values()))

    if warnings:
        print("\n  AVERTISSEMENTS (%d)" % len(warnings))
        for w in warnings:
            print("    - %s" % w)

    if errors:
        print("\n  ERREURS (%d)" % len(errors))
        for e in errors:
            print("    - %s" % e)
        print("\n  => Configuration INVALIDE : ne pas redémarrer LiteLLM.")
        return 1

    print("\n  => Configuration valide.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
