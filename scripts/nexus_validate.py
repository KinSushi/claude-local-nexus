# -*- coding: utf-8 -*-
"""
Validation d'intégrité de la configuration Claude-Local-Nexus.

Vérifie que la configuration LiteLLM est cohérente AVANT tout redémarrage :
aucune référence pendante, aucun cycle de fallback, aucune incompatibilité
de modalité, aucun secret manquant.

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

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG = os.path.join(ROOT, "litellm_config.yaml")

errors: list[str] = []
warnings: list[str] = []

VISION = re.compile(r"vision|llava")
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

    # --- 3. Graphe de fallback ------------------------------------------
    router_settings = cfg.get("router_settings") or {}
    graph: dict[str, list[str]] = {}

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

    for label, entries in (
        ("fallbacks", router_settings.get("fallbacks")),
        ("context_window_fallbacks", cfg.get("context_window_fallbacks")),
    ):
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
                src_kind, dst_kind = classify(source), classify(target)
                if src_kind != dst_kind and src_kind in ("embedding", "vision"):
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
            if label == "fallbacks":
                graph.setdefault(source, []).extend(t for t in targets if t in known)

    # --- 4. Cycles dans le graphe de fallback ---------------------------
    WHITE, GREY, BLACK = 0, 1, 2
    color: dict[str, int] = {}

    def visit(node: str, path: list[str]) -> None:
        color[node] = GREY
        for nxt in graph.get(node, []):
            state = color.get(nxt, WHITE)
            if state == GREY:
                cycle = path[path.index(nxt):] if nxt in path else [nxt]
                errors.append("cycle de fallback : %s" % " -> ".join(cycle + [nxt]))
            elif state == WHITE:
                visit(nxt, path + [nxt])
        color[node] = BLACK

    for node in list(graph):
        if color.get(node, WHITE) == WHITE:
            visit(node, [node])

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
    try:
        raw = subprocess.run(
            ["docker", "exec", "ollama-server", "ollama", "list"],
            capture_output=True, text=True, timeout=60,
        )
        installed = {line.split()[0] for line in raw.stdout.splitlines()[1:] if line.strip()}
    except Exception as exc:  # Ollama indisponible : non bloquant
        installed = set()
        warnings.append("inventaire Ollama illisible (%s)" % exc)

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
            if canonical(base) not in canonical_refs:
                warnings.append("installé mais non exposé : %s" % base)

    # --- 7. Garde-fou materiel ------------------------------------------
    # La machine est mesuree, pas supposee. Un modele plus lourd que la
    # memoire du moteur ne rate pas franchement : il pagine, et la reponse
    # n'arrive jamais utilement. Le laisser selectionnable automatiquement
    # revient a tirer au sort une reponse qui ne viendra pas (§26).
    profile = capability.build_profile()
    sizes = capability.installed_models()

    # Tout ce qui peut etre choisi SANS decision humaine : candidats de
    # routeur et cibles de fallback.
    selectable: set[str] = set()
    for candidates in routers.values():
        selectable.update(candidates)
    for entry in (router_settings.get("fallbacks") or []):
        for targets in entry.values():
            selectable.update(targets or [])

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
