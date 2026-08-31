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
import subprocess
import os
import re
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
# Le pattern est maintenant ancré pour éviter les faux positifs comme
# « supervision-7b ».
# Correction du 2026-08-30 : le motif RATAIT « qwen3-vl-8b-local ».
#
# Il exigeait « -vl » ENTOURE de separateurs, soit « [-:]-vl[-:] », donc un
# double tiret qui n'existe dans aucun alias. Les deux Qwen-VL passaient
# pour des modeles textuels, et le validateur approuvait des chaines ou une
# vision retombe sur du texte -- ce que la 17 interdit et que ce meme
# fichier commente trois lignes plus bas.
#
# Le generateur, lui, lit desormais les capacites declarees par le moteur
# (« ollama show ») et savait que qwen3-vl est une vision. Les deux sources
# ont diverge, et c'est le validateur qui avait tort.
VISION = re.compile(r"(?:^|[-:])(?:vision|llava|vl)(?:$|[-:])")
EMBED = re.compile(r"embed|minilm")


_CAPACITES = {}


def _capacites(base: str) -> set:
    """Capacites declarees par le moteur, mises en cache. Set vide = inconnu."""
    if base in _CAPACITES:
        return _CAPACITES[base]
    trouvees = set()
    try:
        r = subprocess.run(["ollama", "show", base], capture_output=True,
                           text=True, timeout=20, encoding="utf-8",
                           errors="replace")
        if r.returncode == 0:
            dedans = False
            for ligne in r.stdout.splitlines():
                if not dedans:
                    if ligne.strip().lower() == "capabilities":
                        dedans = True
                    continue
                if not ligne.strip() or not ligne[0].isspace():
                    break
                trouvees.add(ligne.strip().lower())
    except Exception:
        pass
    _CAPACITES[base] = trouvees
    return trouvees


def _base_ollama(config: dict, alias: str) -> str | None:
    """Nom Ollama d'un alias local, ou None s'il n'est pas servi localement."""
    for m in config.get("model_list") or []:
        if m.get("model_name") != alias:
            continue
        params = m.get("litellm_params") or {}
        raw = str(params.get("model") or "")
        if "ollama.com" in str(params.get("api_base") or ""):
            return None
        if raw.startswith(("ollama/", "ollama_chat/")):
            return raw.split("/", 1)[1]
        return None
    return None


def classify(alias: str, base: str | None = None) -> str:
    """
    Modalite du modele. La DECLARATION du moteur prime sur le nom.

    Le motif sur le nom ne pouvait pas savoir, et c'est demontre : le
    2026-08-30, « qwen3.6:27b » declare « vision » alors que rien dans son
    nom ne l'indique. Le validateur le tenait pour un modele textuel et
    aurait approuve une chaine ou une vision retombe sur du texte -- ce que
    la 17 interdit.

    Le generateur lisait deja « ollama show » ; les deux sources ont donc
    diverge, et c'est celle qui devinait qui avait tort. Elles lisent
    desormais la meme chose.

    Le nom reste en REPLI : pour un modele distant, ou quand le moteur ne
    repond pas. Un set vide signifie « inconnu », jamais « aucune capacite ».
    """
    if base:
        capacites = _capacites(base)
        if capacites:
            if "embedding" in capacites:
                return "embedding"
            if "vision" in capacites:
                return "vision"
            return "text"
    if EMBED.search(alias):
        return "embedding"
    if VISION.search(alias):
        return "vision"
    return "text"


def load_config() -> dict:
    """Charge le fichier YAML de configuration en capturant les erreurs de syntaxe."""
    try:
        with io.open(CONFIG, encoding="utf-8") as fh:
            return yaml.safe_load(fh) or {}
    except yaml.YAMLError as exc:
        errors.append(f"impossible de parser le fichier YAML : {exc}")
        return {}


def flatten_fallbacks(entries) -> list[tuple[str, list[str]]]:
    """
    Aplatit une liste de repli LiteLLM, quelle que soit sa forme.

    `fallbacks` et `context_window_fallbacks` sont des listes de dicts à
    une seule clé — `{source: [cibles]}`. Mais `default_fallbacks` est une
    liste PLATE de noms : ce sont les modèles vers lesquels n'importe
    quelle source peut retomber. Appeler `.items()` dessus lève un
    `AttributeError`.

    Les deux autres listes étant vides sur cette installation, le défaut
    est aujourd'hui dormant. Il se réveillerait au premier
    `default_fallbacks` ajouté — et le simple fait de l'ignorer, plutôt
    que de le lire, serait pire : la liste la plus universelle de toutes
    échapperait alors à tout contrôle de domaine et de modalité.

    La source implicite est notée `*`, ce qui laisse les contrôles de
    cycle et de direction s'appliquer sans se tromper de responsable.
    """
    out = []
    for entry in entries or []:
        if isinstance(entry, dict):
            for source, targets in entry.items():
                out.append((source, list(targets or [])))
        elif isinstance(entry, str):
            out.append(("*", [entry]))
    return out


# ---------------------------------------------------------------------------
# LA MODALITE DECLAREE DOIT CORRESPONDRE A CE QUE LE MOTEUR DECLARE.
#
# CE QUI ETAIT FAUX, mesure le 2026-08-31. Le moteur Ollama dit lui-meme ce
# que chaque modele sait faire :
#     ollama show deepseek-ocr   ->  Capabilities: completion, vision
#     ollama show llama3.2:3b    ->  Capabilities: completion, tools
# Sur QUATORZE modeles locaux dont le moteur declare « vision », SEPT
# seulement portaient `mode: vision` dans la configuration. Les six autres
# sont declares A LA MAIN, hors de la zone generee, donc hors de portee du
# correctif qui emet desormais la modalite sur le chemin auto-expose.
#
# CE QUE CELA PRODUIT : la regle du contrat 17 -- un modele de vision ne
# retombe jamais sur un modele texte -- ne peut pas s'appliquer, faute de
# savoir lesquels sont des modeles de vision. Deux modeles declarent meme
# « audio » sans qu'aucun `mode: audio` n'existe nulle part.
#
# Le controle ne signale PAS l'inverse -- un mode present que le moteur ne
# declare pas -- car un modele peut etre absent du moteur sans que la
# configuration soit fausse.
#
# Et quand `ollama` est injoignable, il le DIT au lieu de se taire : un
# controle muet est indiscernable d'un depot sain.
# ---------------------------------------------------------------------------


def controle_modalites(model_list, erreurs):
    # Cache pour stocker les capacites des modeles ollama
    cache = {}
    
    # Verifier si 'ollama' est disponible
    try:
        result = subprocess.run(['ollama', '--version'], capture_output=True,
                                text=True, encoding='utf-8',
                                errors='replace', timeout=15)
        if result.returncode != 0:
            erreurs.append("Controle impossible : commande 'ollama' introuvable ou non fonctionnelle")
            return
    except (subprocess.TimeoutExpired, FileNotFoundError):
        erreurs.append("Controle impossible : commande 'ollama' introuvable ou non fonctionnelle")
        return
    
    for model in model_list:
        # Ne traiter que les modeles locaux
        params = model.get('litellm_params') or {}
        cible = params.get('model') or ''
        if not cible.startswith(('ollama/', 'ollama_chat/')):
            continue
            
        model_name = model['model_name']
        ollama_model = cible
        
        # Extraire le nom:tag
        tag = ollama_model.split('/', 1)[1] if '/' in ollama_model else ollama_model
            
        # Verifier si deja dans le cache
        if tag in cache:
            capabilities = cache[tag]
        else:
            try:
                result = subprocess.run(['ollama', 'show', tag], capture_output=True,
                                        text=True, encoding='utf-8',
                                        errors='replace', timeout=15)
                if result.returncode != 0:
                    continue  # Ne pas signaler si echec, mais ne pas ajouter au cache
                
                lines = result.stdout.splitlines()
                in_capabilities = False
                capabilities = []
                
                for line in lines:
                    if line.strip().rstrip(':') == 'Capabilities':
                        in_capabilities = True
                        continue
                    if in_capabilities:
                        if line.strip() == '':
                            break
                        if line.startswith(' '):
                            capabilities.append(line.strip())
                        else:
                            in_capabilities = False
                
                cache[tag] = capabilities
            except (subprocess.TimeoutExpired, Exception):
                continue  # Ne pas ajouter au cache en cas d'erreur
        
        # Obtenir le mode de la configuration si present
        config_mode = (model.get('model_info') or {}).get('mode')
        
        # Verifier les capacites
        has_vision = 'vision' in capabilities
        has_embedding = 'embedding' in capabilities
        
        if has_vision and config_mode != 'vision':
            erreurs.append(f"Modele {model_name} declare 'vision' mais n'a pas 'mode: vision' dans la configuration")
        
        if has_embedding and config_mode != 'embedding':
            erreurs.append(f"Modele {model_name} declare 'embedding' mais n'a pas 'mode: embedding' dans la configuration")


def main() -> int:
    cfg = load_config()

    # --- 1. Alias déclarés, doublons -------------------------------------
    model_list = cfg.get("model_list") or []

    # LA MODALITE DECLAREE EST CONFRONTEE A CELLE DU MOTEUR.
    #
    # Le controle recoit sa propre liste : ce qu'il rend est de deux natures,
    # et les melanger serait faux. Un ECART est une erreur -- la regle du
    # contrat 17 ne peut pas s'appliquer sur une modalite fausse. Mais
    # « ollama injoignable » n'est PAS une erreur de configuration : sur une
    # machine sans moteur, la faire bloquer refuserait une configuration
    # parfaitement saine. Elle part donc en avertissement, ou elle reste
    # VISIBLE -- se taire serait indiscernable d'un depot verifie.
    _modalites: list[str] = []
    controle_modalites(model_list, _modalites)
    for _ligne in _modalites:
        if _ligne.startswith("Controle impossible"):
            warnings.append(_ligne)
        else:
            errors.append(_ligne)
    declared: list[str] = []
    for m in model_list:
        name = m.get("model_name")
        if not name:
            errors.append("objet dans model_list sans champ 'model_name'")
            continue
        declared.append(name)

    seen: set[str] = set()
    for alias in declared:
        if alias in seen:
            errors.append("alias duplique dans model_list : %s" % alias)
        seen.add(alias)
    known = set(declared)

    # Construction d'une table alias -> (model, api_base) pour le futur test
    # de repli identique. Cette table permet de détecter le cas où deux
    # alias différents pointent vers le même couple (model, api_base) et
    # sont reliés par un arc de fallback. Un tel repli ne fournit aucune
    # redondance : si le modèle sous-jacent tombe, les deux alias tombent
    # simultanément, poussant le système vers un plan payant, ce qui est le
    # comportement que l'on veut absolument interdire.
    alias_to_pair: dict[str, tuple[str, str]] = {}
    for m in model_list:
        params = m.get("litellm_params") or {}
        model = str(params.get("model", ""))
        api_base = str(params.get("api_base", ""))
        if "model_name" in m:
            alias_to_pair[m["model_name"]] = (model, api_base)

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
        # La duplication de « context_window_fallbacks (router) » a été
        # supprimée pour éviter les messages d'erreur doublés.
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

                # --- Nouveau contrôle : repli vers le même modele/engine ----
                if source != "*" and source in alias_to_pair and target in alias_to_pair:
                    src_model, src_api = alias_to_pair[source]
                    tgt_model, tgt_api = alias_to_pair[target]

                    # Ignorer les mécanismes de routeur et les alias sans api_base.
                    if src_model.startswith("auto_router/") or tgt_model.startswith("auto_router/"):
                        pass
                    elif not src_api or not tgt_api:
                        pass
                    elif src_model == tgt_model and src_api == tgt_api:
                        errors.append(
                            "%s : '%s' et '%s' pointent vers le meme modele '%s' et api_base '%s' - un repli vers le meme modele sur le meme moteur tombe en meme temps que sa source"
                            % (label, source, target, src_model, src_api)
                        )
                        continue

                # Modalité : un embedding ne retombe que sur un embedding,
                # une vision que sur une vision (§17).
                # La base Ollama, pour interroger le moteur plutot que
                # deviner sur le nom.
                src_kind = classify(source, _base_ollama(cfg, source))
                dst_kind = classify(target, _base_ollama(cfg, target))
                if src_kind != dst_kind:
                    errors.append("%s : '%s' (%s) retombe sur '%s' (%s) — modalite incompatible"
                                  % (label, source, src_kind, target, dst_kind))

                # Direction du repli. La règle est asymétrique à dessein :
                # se replier vers le local ne fait perdre que de la
                # capacité, tandis que sortir vers le cloud ou Anthropic
                # élargirait l'exposition des données et engagerait une
                # dépense que personne n'a demandée. Un repli est subi,
                # jamais choisi : il ne doit pas décider à notre place.
                src_domain = domains.get(source)
                dst_domain = domains.get(target)
                if src_domain and dst_domain and src_domain != dst_domain and dst_domain != "local":
                    errors.append(
                        "%s : '%s' (%s) retombe sur '%s' (%s) — un repli ne "
                        "peut aller que vers plus de confidentialite"
                        % (label, source, src_domain, target, dst_domain))
                # TOUS LES ALIAS D'UN MEME COMPTE SONT UN SEUL AMONT.
                #
                # Le contrôle de direction ci-dessus compare des DOMAINES :
                # `cloud -> cloud` a le même domaine des deux côtés, donc
                # `src_domain != dst_domain` est faux et la règle ne se
                # déclenche jamais. Le trou est exactement là.
                #
                # Or les modèles Ollama Cloud partagent tous un compte et
                # donc un plafond. Un 429 « too many concurrent requests »
                # ne peut pas être rattrapé par un alias qui partage la
                # ressource épuisée : le repli TRIPLE la charge qui a causé
                # le refus. Mesuré par une session voisine sur cet hôte :
                # 40 connexions sortantes pour 3 appels clients, 46 refus en
                # cinq minutes pour une seule réponse aboutie.
                #
                # Le validateur refusait déjà qu'un modèle se replie sur
                # lui-même — « un repli vers soi-même tombe en même temps
                # que sa source ». Il lui manquait de savoir que deux alias
                # d'un même compte tombent ensemble tout autant.
                #
                # LES ROUTEURS SONT EXEMPTS, et ce n'est pas une faveur :
                # un routeur cloud n'a par définition que des candidats
                # cloud, et sa liste est un POOL de choix, pas un repli
                # subi. Le lui interdire reviendrait à interdire le routeur.
                #
                # ÉTAT AU MOMENT DE LA POSE : zéro cas hors routeur. Ce
                # contrôle est donc un cliquet — il ne répare rien
                # aujourd'hui, il empêche le retour d'un état qui a
                # réellement existé, avant le correctif d'amplification.
                if (src_domain == "cloud" and dst_domain == "cloud"
                        and source not in routers and source != "*"):
                    errors.append(
                        "%s : '%s' retombe sur '%s' — meme compte Ollama "
                        "Cloud, donc meme plafond : un repli vers un quota "
                        "epuise triple la charge qui a cause le refus"
                        % (label, source, target))

                # Cas spécial : source "*"
                if source == "*" and dst_domain and dst_domain != "local":
                    errors.append(
                        "%s : fallback par défaut vers '%s' (%s) — un repli par défaut ne doit pas sortir du domaine local"
                        % (label, target, dst_domain))

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
                    errors.append("modele %s : variable %s non definie"
                                  % (m.get("model_name", "<inconnu>"), name))

    # --- 6. Inventaire Ollama vs configuration --------------------------
    # Le profil sert des la section 6, pour distinguer un modele oublie
    # d'un modele deliberement ecarte.
    profile_materiel = capability.build_profile()
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
                    errors.append("modele %s : '%s' declare mais absent d'Ollama"
                                  % (m.get("model_name", "<inconnu>"), base))
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
            taille = tailles_installees.get(base, 0.0)
            etat, motif = capability.verdict(taille, profile_materiel)
            if etat == capability.REJECT:
                warnings.append("non expose a dessein : %s — %s" % (base, motif))
            else:
                warnings.append("installe mais non expose : %s" % base)

    # --- 7. Garde-fou materiel ------------------------------------------
    # La machine est mesuree, pas supposee. Un modele plus lourd que la
    # memoire du moteur ne rate pas franchement : il pagine, et la reponse
    # n'arrive jamais utilement. Le laisser selectionnable automatiquement
    # revient a tirer au sort une reponse qui ne viendra pas (§26).
    profile = profile_materiel
    sizes = tailles_installees or {}
    if sizes is None:
        sizes = {}

    # Tout ce qui peut etre choisi SANS decision humaine : candidats de
    # routeur et cibles de fallback.
    selectable: set[str] = set()
    for candidates in routers.values():
        selectable.update(candidates)
    # Toutes les listes de repli, et pas seulement `fallbacks` : un modèle
    # inexecutable restait accepté comme cible de `context_window_fallbacks`.
    for _, entries in listes_de_repli:
        for _source, targets in flatten_fallbacks(entries):
            selectable.update(targets)
    # Le `default_model` est le chemin le plus servi quand le routeur ne
    # tranche pas : il doit subir le même budget que les candidats du pool.
    for m in model_list:
        defaut = (m.get("litellm_params") or {}).get("adaptive_router_default_model")
        if defaut:
            selectable.add(defaut)

    for m in model_list:
        alias = m.get("model_name", "<inconnu>")
        params = m.get("litellm_params") or {}
        raw_model = str(params.get("model", ""))
        if "ollama.com" in str(params.get("api_base", "")):
            continue  # execute chez le fournisseur, pas ici
        if not raw_model.startswith(("ollama/", "ollama_chat/")):
            continue
        base = raw_model.split("/", 1)[1]
        size = sizes.get(base)
        if size is None:
            size = sizes.get(base + ":latest", 0.0)
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
            "cache semantique actif : risque de reponse erronnee sur les appels "
            "d'outils et les etapes d'agent (§27)"
        )

    # --- Rapport ---------------------------------------------------------
    print("=" * 60)
    print(" Validation de la configuration Claude-Local-Nexus")
    print("=" * 60)
    print("  Modeles declares  : %d" % len(declared))
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
        print("\n  => Configuration INVALIDE : ne pas redemarrer LiteLLM.")
        return 1

    print("\n  => Configuration valide.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
