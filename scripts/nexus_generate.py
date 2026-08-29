# -*- coding: utf-8 -*-
"""
Générateur de configuration Claude-Local-Nexus.

Ne réécrit que les zones délimitées par les marqueurs :
    # >>> AUTOGEN:<NOM> ... # <<< AUTOGEN:<NOM>

Tout le reste de litellm_config.yaml est main-maintenu : les blocs des
modèles locaux, leurs fenêtres de contexte et leurs profils de capacité
relèvent d'un jugement humain et ne sont jamais touchés ici.

Ce qui est généré l'est à partir de deux sources de vérité vivantes :
    - le catalogue Ollama Cloud (https://ollama.com/api/tags) ;
    - la liste des modèles réellement déclarés dans la configuration.

Les graphes de fallback sont dérivés, jamais écrits à la main. Ils sont
donc acycliques par construction (chaîne strictement descendante) et ne
franchissent jamais une frontière de modalité ni de fournisseur (§17, §65, §66).

Usage :
    python scripts/nexus_generate.py [--dry-run] [--no-validate]

La validation des droits est active par defaut.
"""
from __future__ import annotations

import argparse
import datetime
import io
import json
import os
import re
import subprocess
import sys
import urllib.request

try:
    import yaml
except ImportError:
    print("ERREUR: PyYAML est requis (pip install pyyaml)")
    sys.exit(1)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nexus_capability as capability  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG = os.path.join(ROOT, "litellm_config.yaml")
CLOUD_LIST = os.path.join(ROOT, "cloud_models.txt")
TAGS_URL = "https://ollama.com/api/tags"

# Adresse du moteur d'inférence local, vue depuis le conteneur LiteLLM.
#   http://ollama:11434                 Ollama dans Docker
#   http://host.docker.internal:11434   Ollama sur l'hôte
# Sortir Ollama de Docker n'est pas cosmétique : dans le conteneur, le
# moteur est plafonné par la mémoire allouée à la VM WSL2 — sur cette
# machine, la moitié de la RAM lui est inaccessible.
OLLAMA_ENDPOINT = os.environ.get("NEXUS_OLLAMA_ENDPOINT", "http://ollama:11434")

# Classement de capacité du catalogue cloud. Plus le rang est bas, plus le
# modèle est considéré capable. Un modèle inconnu tombe en fin de chaîne
# plutôt que d'être ignoré : le script reste tolérant aux nouveautés.
CLOUD_RANKS = [
    (r"^qwen3\.5:397b", 10),
    (r"^deepseek-v4-pro", 20),
    (r"^kimi-k3", 30),
    (r"^glm-5\.3$", 40),
    (r"^mistral-large-3", 50),
    (r"^minimax-m3", 60),
    (r"^nemotron-3-ultra", 70),
    (r"^kimi-k2\.7-code", 80),
    (r"^glm-5\.2$", 90),
    (r"^deepseek-v4-flash", 100),
    (r"^gpt-oss:120b", 110),
    (r"^nemotron-3-super", 120),
    (r"^glm-5\.3-flash", 130),
    (r"^minimax-m2\.7", 140),
    (r"^kimi-k2\.6", 150),
    (r"^glm-5\.1$", 160),
    (r"^gpt-oss:20b", 170),
    (r"^nemotron-3-nano", 180),
    (r"^gemma4", 190),
]

# Codes qui prouvent une absence de droit. Tout le reste (429, 5xx,
# timeout, coupure reseau) est traite comme passager.
ENTITLEMENT_CODES = {401, 402, 403, 404}

CODE_HINT = re.compile(r"cod(er|e)|devstral|qwen|codestral")
VISION_HINT = re.compile(r"vision|llava")
EMBED_HINT = re.compile(r"embed|minilm")


def cloud_rank(name: str) -> int:
    for pattern, rank in CLOUD_RANKS:
        if re.search(pattern, name):
            return rank
    return 900


def cloud_alias(base: str) -> str:
    """Seuls les ':' deviennent '-' : les points restent lisibles."""
    return base.replace(":", "-") + "-cloud"


def quality_tier(rank: int) -> int:
    if rank <= 60:
        return 3
    if rank <= 140:
        return 2
    return 1


# ----------------------------------------------------------------------
# Découverte du catalogue cloud
# ----------------------------------------------------------------------
def discover_cloud() -> list[str]:
    with urllib.request.urlopen(TAGS_URL, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))
    names = sorted({m["name"] for m in payload.get("models", [])})
    if not names:
        raise RuntimeError("catalogue cloud vide")
    return sorted(names, key=lambda n: (cloud_rank(n), n))


def local_alias(base: str) -> str:
    """
    Alias d'un modèle Ollama installé.

    Le tag ':latest' est retiré car il n'apporte rien au nom logique, puis
    les ':' deviennent '-'. La règle reproduit exactement les alias déjà
    écrits à la main (qwen3-coder:30b -> qwen3-coder-30b-local), ce qui
    permet de reconnaître un modèle déjà déclaré et de ne pas le doubler.
    """
    if base.endswith(":latest"):
        base = base[: -len(":latest")]
    return base.replace(":", "-") + "-local"


def discover_local() -> list[str]:
    """Inventaire réel du conteneur Ollama. Vide si Ollama est injoignable."""
    try:
        result = subprocess.run(
            ["docker", "exec", "ollama-server", "ollama", "list"],
            capture_output=True, text=True, timeout=60,
        )
    except Exception as exc:
        print("  [!] inventaire local illisible (%s)" % exc)
        return []
    if result.returncode != 0:
        print("  [!] ollama list a echoue")
        return []
    names = []
    for line in result.stdout.splitlines()[1:]:
        if line.strip():
            names.append(line.split()[0])
    return sorted(set(names))


def local_context(base: str) -> int:
    """
    Fenêtre attribuée aux modèles exposés automatiquement.

    Volontairement conservatrice : sur un hôte CPU, le contexte se paie en
    RAM et en latence, et la capacité annoncée d'un modèle ne rend pas son
    allocation raisonnable (§26). Un modèle qui mérite mieux se promeut en
    le déclarant à la main.
    """
    if EMBED_HINT.search(base):
        return 8192
    match = re.search(r"(\d+(?:\.\d+)?)b", base.lower())
    if match and float(match.group(1)) <= 9:
        return 16384
    return 8192


def render_local_extra(installed: list[str], declared: set[str],
                       profile: dict | None = None,
                       sizes: dict[str, float] | None = None) -> list[str]:
    """
    Expose les modèles Ollama non déclarés à la main.

    Le profil matériel tranche : un modèle que la machine ne peut pas
    exécuter n'est pas déclaré du tout — l'exposer reviendrait à offrir
    une porte qui ne mène nulle part.
    """
    out: list[str] = []
    sizes = sizes or {}
    extra = [b for b in installed if local_alias(b) not in declared]
    rendered = []
    for base in extra:
        if profile:
            state, reason = capability.verdict(sizes.get(base, 0.0), profile)
            if state == capability.REJECT:
                print("  [rejet] %s : %s" % (base, reason))
                continue
        else:
            state, reason = capability.ACCEPT, ""
        rendered.append((base, state, reason))

    for i, (base, state, reason) in enumerate(rendered):
        alias = local_alias(base)
        ctx = local_context(base)
        is_embed = bool(EMBED_HINT.search(base))
        note = "expose automatiquement"
        if state == capability.DEGRADED:
            note = "expose automatiquement — hors pool : " + reason
        out += [
            "  - model_name: %s" % alias,
            "    litellm_params:",
            "      model: ollama%s/%s" % ("" if is_embed else "_chat", base),
            "      api_base: %s" % OLLAMA_ENDPOINT,
            "      litellm_health_check: true",
        ]
        if not is_embed:
            out += ["      num_ctx: %d" % ctx, "      num_predict: 4096"]
        out += [
            "    model_info:",
            "      max_input_tokens: %d" % ctx,
            '      description: "%s (%s)"' % (base, note),
            # Deux marques distinctes, et il faut les deux :
            #   nexus_generated : d'ou vient le bloc (evite de le redeclarer)
            #   nexus_pool      : s'il est eligible au routage automatique
            # Les confondre ferait redeclarer tout modele ecarte des pools
            # a la main, donc un alias en double.
            "      nexus_generated: true",
            "      nexus_pool: false",
        ]
        if i < len(rendered) - 1:
            out.append("")
    return out


def read_env(name: str) -> str | None:
    if os.environ.get(name):
        return os.environ[name]
    env_file = os.path.join(ROOT, ".env")
    if not os.path.exists(env_file):
        return None
    with io.open(env_file, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            match = re.match(r"^\s*%s\s*=\s*(.*)$" % re.escape(name), line)
            if match and match.group(1).strip():
                return match.group(1).strip()
    return None


def validate_cloud(names: list[str]) -> tuple[list[str], dict[str, str]]:
    """
    Ne conserve que les modèles réellement exécutables par CE compte.

    Le catalogue publié n'est pas le catalogue autorisé : un modèle hors
    du palier souscrit répond 402. Publier un tel modèle dans le pool
    reviendrait à router vers un échec garanti.

    Le verdict n'est jamais figé : la validation est rejouée à chaque
    mise à jour, donc le pool s'élargit de lui-même dès qu'un palier
    supérieur est souscrit, sans aucune retouche de configuration.

    Distinction essentielle : un échec n'est pas l'autre.

        402/401/403/404  droit manquant       -> le modèle est écarté
        429/5xx/timeout  condition passagère  -> le modèle est CONSERVÉ

    Un quota momentanément épuisé ou un démarrage à froid ne prouve rien
    sur les droits du compte. Retirer un modèle du pool pour cette raison
    l'amputerait jusqu'à la mise à jour suivante, sur la foi d'un incident
    déjà terminé.

    Retourne (modèles retenus, {modèle: motif d'exclusion}).
    """
    key = read_env("OLLAMA_CLOUD_API_KEY")
    if not key:
        raise RuntimeError("OLLAMA_CLOUD_API_KEY absente : validation impossible")

    accepted: list[str] = []
    rejected: dict[str, str] = {}
    for name in names:
        body = json.dumps({
            "model": name,
            "messages": [{"role": "user", "content": "ping"}],
            "stream": False,
            "options": {"num_predict": 1},
        }).encode("utf-8")
        request = urllib.request.Request(
            "https://ollama.com/api/chat",
            data=body,
            headers={"Authorization": "Bearer %s" % key,
                     "Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                if response.status == 200:
                    accepted.append(name)
                    print("  [OK]    %s" % name)
                else:
                    rejected[name] = "HTTP %s" % response.status
                    print("  [ecart] %s : HTTP %s" % (name, response.status))
        except Exception as exc:
            code = getattr(exc, "code", None)
            if code in ENTITLEMENT_CODES:
                reason = {
                    402: "402 palier non souscrit",
                    401: "401 cle invalide",
                    403: "403 acces refuse",
                    404: "404 modele absent",
                }[code]
                rejected[name] = reason
                print("  [ecart] %s : %s" % (name, reason))
            else:
                # Incident passager : on conserve le modèle plutôt que
                # d'amputer le pool sur la foi d'un echec deja termine.
                accepted.append(name)
                print("  [garde] %s : %s (echec passager, modele conserve)"
                      % (name, code or exc))
    return accepted, rejected


# ----------------------------------------------------------------------
# Classification des modèles déjà déclarés
# ----------------------------------------------------------------------
class Entry:
    __slots__ = ("alias", "domain", "modality", "family", "tier", "ctx", "order")

    def __init__(self, alias, domain, modality, family, tier, ctx, order):
        self.alias = alias
        self.domain = domain
        self.modality = modality
        self.family = family
        self.tier = tier
        self.ctx = ctx
        self.order = order


def classify(config: dict, profile: dict | None = None,
             sizes: dict[str, float] | None = None) -> list[Entry]:
    """
    Modèles éligibles à la construction des chaînes de routage.

    Trois exclusions, dans cet ordre : les routeurs eux-mêmes, ce qui a été
    écarté des pools à la main, et ce que la machine ne peut pas exécuter
    avec une marge suffisante. La dernière est mesurée, pas déclarée : un
    modèle trop lourd rendrait la chaîne de fallback inopérante là où elle
    devrait précisément sauver la requête.
    """
    sizes = sizes or {}
    entries: list[Entry] = []
    for order, model in enumerate(config.get("model_list") or []):
        alias = model["model_name"]
        params = model.get("litellm_params") or {}
        info = model.get("model_info") or {}
        prefs = info.get("adaptive_router_preferences") or {}
        raw = str(params.get("model", ""))
        api_base = str(params.get("api_base", ""))

        if raw.startswith("auto_router/"):
            continue
        # Exposé automatiquement : adressable, mais hors pool et hors
        # chaînes de fallback tant qu'il n'a pas été évalué (§76).
        if info.get("nexus_pool") is False:
            continue
        if profile and raw.startswith(("ollama/", "ollama_chat/")) \
                and "ollama.com" not in api_base:
            base = raw.split("/", 1)[1]
            size = sizes.get(base) or sizes.get(base + ":latest") or 0.0
            state, reason = capability.verdict(size, profile)
            if state != capability.ACCEPT:
                print("  [hors chaine] %s : %s" % (alias, reason))
                continue
        if raw.startswith("anthropic/"):
            domain = "anthropic"
        elif "ollama.com" in api_base:
            domain = "cloud"
        else:
            domain = "local"

        if EMBED_HINT.search(alias):
            modality = "embedding"
        elif VISION_HINT.search(alias):
            modality = "vision"
        else:
            modality = "text"

        # La spécialisation coding/general ne discrimine que le pool local :
        # les modèles Anthropic et cloud sont généralistes, les séparer
        # isolerait des modèles seuls dans leur chaîne.
        strengths = prefs.get("strengths") or []
        if modality != "text":
            family = modality
        elif domain == "local":
            family = "coding" if ("code_generation" in strengths or CODE_HINT.search(alias)) else "general"
        else:
            family = "text"

        entries.append(Entry(
            alias=alias,
            domain=domain,
            modality=modality,
            family=family,
            tier=int(prefs.get("quality_tier") or 0),
            ctx=int(info.get("max_input_tokens") or 0),
            order=order,
        ))
    return entries


def group_of(entry: Entry) -> tuple[str, str]:
    """Un fallback ne franchit jamais ces deux frontières."""
    return (entry.domain, entry.family)


def ranked(entries: list[Entry], domain: str) -> dict[tuple[str, str], list[Entry]]:
    """Chaînes ordonnées du plus capable au moins capable, par groupe."""
    groups: dict[tuple[str, str], list[Entry]] = {}
    for entry in entries:
        if entry.domain != domain:
            continue
        groups.setdefault(group_of(entry), []).append(entry)
    for chain in groups.values():
        chain.sort(key=lambda e: (-e.tier, e.order))
    return groups


def ranked_by_modality(entries: list[Entry], domain: str) -> dict[tuple[str, str], list[Entry]]:
    """
    Regroupement plus large, réservé aux fallbacks de contexte.

    Un dépassement de fenêtre n'est pas un problème de spécialité : il faut
    une fenêtre plus grande, dans le même domaine et la même modalité. Garder
    ici la séparation coding/general priverait les modèles généralistes de
    toute issue, alors qu'un seul modèle local dépasse 8K.
    """
    groups: dict[tuple[str, str], list[Entry]] = {}
    for entry in entries:
        if entry.domain != domain:
            continue
        groups.setdefault((entry.domain, entry.modality), []).append(entry)
    for chain in groups.values():
        chain.sort(key=lambda e: (-e.tier, e.order))
    return groups


# ----------------------------------------------------------------------
# Rendu des blocs
# ----------------------------------------------------------------------
def render_chain(groups: dict, indent: int, width: int = 2,
                 terminal: list[str] | None = None) -> list[str]:
    """
    Chaîne descendante : chacun retombe sur les suivants, jamais sur un
    précédent — l'acyclicité est donc structurelle.

    `terminal` prolonge la chaîne au-delà de son plan, et n'est légitime
    que dans un seul sens.

    Règle de direction, asymétrique et volontairement stricte :

        cloud     -> local      autorisé   (le repli protège davantage)
        anthropic -> local      autorisé   (idem, et évite l'interruption)
        local     -> cloud      INTERDIT   (les données sortiraient)
        local     -> anthropic  INTERDIT   (idem, et la facturation change)

    Un repli est une dégradation subie, pas une décision : il ne doit
    jamais élargir l'exposition des données ni engager une dépense que
    personne n'a demandée. L'inverse — se replier vers le local quand un
    quota s'épuise — ne fait perdre que de la capacité.
    """
    pad = " " * indent
    out: list[str] = []
    for _, chain in sorted(groups.items()):
        for i, entry in enumerate(chain):
            targets = [e.alias for e in chain[i + 1:i + 1 + width]]
            if terminal and len(targets) < width:
                for extra in terminal:
                    if extra not in targets and extra != entry.alias:
                        targets.append(extra)
                    if len(targets) >= width + 1:
                        break
            if not targets:
                continue
            out.append("%s- %s:" % (pad, entry.alias))
            for target in targets:
                out.append("%s    - %s" % (pad, target))
            out.append("")
    return out


def render_ctx_chain(groups: dict, indent: int) -> list[str]:
    """Contexte : on ne remonte que vers une fenêtre strictement plus large."""
    pad = " " * indent
    out: list[str] = []
    for _, chain in sorted(groups.items()):
        for entry in chain:
            larger = sorted(
                (e for e in chain if e.ctx > entry.ctx),
                key=lambda e: e.ctx,
            )[:2]
            if not larger:
                continue
            out.append("%s- %s:" % (pad, entry.alias))
            for target in larger:
                out.append("%s    - %s" % (pad, target.alias))
            out.append("")
    return out


def render_cloud_models(cloud: list[str]) -> list[str]:
    out: list[str] = []
    for i, base in enumerate(cloud):
        rank = cloud_rank(base)
        out += [
            "  - model_name: %s" % cloud_alias(base),
            "    litellm_params:",
            "      model: ollama_chat/%s" % base,
            "      api_base: https://ollama.com",
            "      api_key: os.environ/OLLAMA_CLOUD_API_KEY",
            "      num_ctx: 131072",
            "      num_predict: 8192",
            "    model_info:",
            "      max_input_tokens: 131072",
            '      description: "%s (Ollama Cloud)"' % base,
            "      adaptive_router_preferences:",
            "        quality_tier: %d" % quality_tier(rank),
            "        strengths:",
            "          - general",
            "          - analytical_reasoning",
        ]
        if CODE_HINT.search(base):
            out += ["          - code_generation", "          - code_understanding"]
        if i < len(cloud) - 1:
            out.append("")
    return out


def render_router_fallbacks(entries: list[Entry], cloud: list[str]) -> list[str]:
    """
    Repli de chaque routeur.

    Les routeurs externes s'achèvent sur le routeur local : un quota
    Ollama épuisé ou des crédits Anthropic consommés doivent dégrader la
    capacité, pas interrompre le service. L'inverse n'existe pas — le
    routeur local ne sort jamais.
    """
    def top(domain: str, count: int = 2) -> list[str]:
        pool = [e for e in entries if e.domain == domain and e.modality == "text"]
        pool.sort(key=lambda e: (-e.tier, e.order))
        return [e.alias for e in pool[:count]]

    cloud_top = [cloud_alias(b) for b in cloud[:2]]
    out: list[str] = []
    for router, targets in (
        ("adaptive-router-local", top("local")),
        # Quota Ollama epuise : on retombe en local plutot que d'echouer.
        ("adaptive-router-cloud", cloud_top + ["adaptive-router-local"]),
        # Abonnement ou credits Anthropic epuises : meme principe.
        ("adaptive-router-anthropic", top("anthropic") + ["adaptive-router-local"]),
        # Le routeur global ne monte jamais vers Anthropic de lui-meme :
        # engager une depense n'est pas une degradation, c'est une decision.
        ("adaptive-router", ["adaptive-router-local", "adaptive-router-cloud"]),
    ):
        if not targets:
            continue
        out.append("    - %s:" % router)
        for target in targets:
            out.append("        - %s" % target)
        out.append("")
    return out


# ----------------------------------------------------------------------
# Remplacement par marqueurs
# ----------------------------------------------------------------------
def aliases_inside(lines: list[str], marker: str) -> set[str]:
    """
    Alias declares a l'interieur d'une zone AUTOGEN.

    Discriminant fiable de l'origine d'un bloc : sa POSITION, et non une
    marque posee dans son contenu. Une marque de contenu depend de la
    version qui l'a ecrite, donc echoue exactement lors des migrations
    ou l'on en a le plus besoin.
    """
    inside = False
    found: set[str] = set()
    open_re = re.compile(r"^\s*# >>> AUTOGEN:%s(\s|$)" % re.escape(marker))
    close_re = re.compile(r"^\s*# <<< AUTOGEN:%s\s*$" % re.escape(marker))
    for line in lines:
        if open_re.match(line):
            inside = True
            continue
        if close_re.match(line):
            inside = False
            continue
        if inside:
            match = re.match(r"^\s*- model_name:\s*(\S+)\s*$", line)
            if match:
                found.add(match.group(1))
    return found


def set_block(lines: list[str], marker: str, content: list[str]) -> list[str]:
    start = end = -1
    open_re = re.compile(r"^\s*# >>> AUTOGEN:%s(\s|$)" % re.escape(marker))
    close_re = re.compile(r"^\s*# <<< AUTOGEN:%s\s*$" % re.escape(marker))
    for i, line in enumerate(lines):
        if start < 0 and open_re.match(line):
            start = i
        elif start >= 0 and close_re.match(line):
            end = i
            break
    if start < 0:
        raise RuntimeError("marqueur AUTOGEN:%s introuvable" % marker)
    if end < 0:
        raise RuntimeError("marqueur AUTOGEN:%s jamais fermé" % marker)
    return lines[:start + 1] + content + lines[end:]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true",
                        help="affiche ce qui serait généré sans rien écrire")
    # La validation est le comportement par defaut : generer sans elle
    # remplit le pool de modeles que le compte ne peut pas executer, ce
    # qui produit des echecs garantis au routage.
    parser.add_argument("--no-validate", dest="validate", action="store_false",
                        default=True,
                        help="ne pas tester les droits reels (deconseille : le "
                             "pool peut alors contenir des modeles inutilisables)")
    args = parser.parse_args()

    print("=== Découverte du catalogue Ollama Cloud ===")
    cloud = discover_cloud()
    print("  %d modèle(s) publiés" % len(cloud))

    published = list(cloud)
    rejected: dict[str, str] = {}
    if args.validate:
        print("\n=== Validation par requête réelle ===")
        cloud, rejected = validate_cloud(cloud)
        if not cloud:
            print("\nAucun modèle cloud utilisable : configuration inchangée.")
            return 1
        print("  %d modèle(s) retenus sur %d" % (len(cloud), len(published)))
        gated = [n for n, r in rejected.items() if r.startswith("402")]
        if gated:
            print("  %d modèle(s) attendent un palier supérieur ; ils entreront"
                  % len(gated))
            print("  automatiquement dans le pool à la prochaine mise à jour"
                  " après souscription.")

    with io.open(CONFIG, encoding="utf-8") as fh:
        raw = fh.read()
    config = yaml.safe_load(raw)

    # Garde-fou materiel : mesure avant toute decision de routage.
    profile = capability.build_profile()
    sizes = capability.installed_models()
    print("  Moteur %s — %.0f Go de memoire d'inference, budget pool %.0f Go"
          % (profile["ollama"]["mode"], profile["inference_memory_gb"],
             profile["pool_budget_gb"]))

    entries = classify(config, profile, sizes)

    # Les entrées cloud déjà déclarées sont remplacées par la découverte :
    # on les retire avant de dériver les chaînes.
    entries = [e for e in entries if e.domain != "cloud"]

    anthropic_groups = ranked(entries, "anthropic")
    local_groups = ranked(entries, "local")

    cloud_chain = [
        Entry(cloud_alias(b), "cloud", "text", "text",
              quality_tier(cloud_rank(b)), 131072, i)
        for i, b in enumerate(cloud)
    ]
    cloud_groups: dict[tuple[str, str], list[Entry]] = {}
    for entry in cloud_chain:
        cloud_groups.setdefault(group_of(entry), []).append(entry)
    for chain in cloud_groups.values():
        chain.sort(key=lambda e: e.order)

    # Exposition automatique de l'inventaire Ollama. La liste est relue à
    # chaque exécution : un modèle téléchargé après coup apparaît de
    # lui-même, sans plafond ni liste à tenir à jour.
    installed = discover_local()
    raw_lines = raw.replace("\r\n", "\n").split("\n")
    generated_aliases = aliases_inside(raw_lines, "LOCAL_MODELS_EXTRA")
    declared_aliases = {m["model_name"] for m in (config.get("model_list") or [])
                        if m["model_name"] not in generated_aliases}

    local_extra = (render_local_extra(installed, declared_aliases, profile, sizes)
                   if installed else [])
    if installed:
        exposed_extra = len([b for b in installed if local_alias(b) not in declared_aliases])
        print("  %d modele(s) installes, %d exposes automatiquement"
              % (len(installed), exposed_extra))

    # Terminal de repli : les meilleurs modeles locaux. Toute chaine
    # externe s'y acheve, pour qu'un quota epuise degrade la capacite
    # sans interrompre le service.
    local_text = [e for e in entries if e.domain == "local" and e.modality == "text"]
    local_text.sort(key=lambda e: (-e.tier, e.order))
    terminal_local = [e.alias for e in local_text[:2]]

    blocks = {
        "LOCAL_MODELS_EXTRA": local_extra,
        "CLOUD_MODELS": render_cloud_models(cloud),
        "CLOUD_POOL_CLOUD": ["          - %s" % cloud_alias(b) for b in cloud],
        "CLOUD_POOL_GLOBAL": ["          - %s" % cloud_alias(b) for b in cloud],
        # Les chaines externes s'achevent en local ; la chaine locale,
        # elle, ne sort jamais.
        "ANTHROPIC_FALLBACKS": render_chain(anthropic_groups, 4,
                                            terminal=terminal_local),
        "LOCAL_FALLBACKS": render_chain(local_groups, 4),
        "CLOUD_FALLBACKS": render_chain(cloud_groups, 4,
                                        terminal=terminal_local),
        "ROUTER_FALLBACKS": render_router_fallbacks(entries, cloud),
        "ANTHROPIC_CTX_FALLBACKS": render_ctx_chain(
            ranked_by_modality(entries, "anthropic"), 2),
        "LOCAL_CTX_FALLBACKS": render_ctx_chain(
            ranked_by_modality(entries, "local"), 2),
        "CLOUD_CTX_FALLBACKS": [],
    }

    if args.dry_run:
        print("\n=== [Simulation] blocs générés ===")
        for name, content in blocks.items():
            print("  %-26s %d ligne(s)" % (name, len(content)))
        print("\n  Routeur cloud par défaut : %s" % cloud_alias(cloud[0]))
        return 0

    lines = raw.replace("\r\n", "\n").split("\n")
    for name, content in blocks.items():
        lines = set_block(lines, name, content)

    # Version de la politique de routage : empreinte de ce qui decide
    # reellement du modele servi. Elle rend un resultat rattachable aux
    # regles qui l'ont produit (§88).
    signature = "|".join([
        "|".join(sorted(blocks["CLOUD_POOL_CLOUD"])),
        "|".join(sorted(blocks["CLOUD_POOL_GLOBAL"])),
        "|".join(blocks["ROUTER_FALLBACKS"]),
        "%.0f" % profile["pool_budget_gb"],
    ])
    router_version = "r%s" % __import__("hashlib").sha256(
        signature.encode("utf-8")).hexdigest()[:10]

    default_cloud = cloud_alias(cloud[0])
    for i, line in enumerate(lines):
        match = re.match(r"^(\s*adaptive_router_default_model:\s*)\S+-cloud\s*$", line)
        if match:
            lines[i] = match.group(1) + default_cloud
        if line.startswith("# NEXUS-ROUTER-VERSION:"):
            lines[i] = "# NEXUS-ROUTER-VERSION: %s" % router_version

    with io.open(CONFIG, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(lines).rstrip() + "\n")
    # cloud_models.txt documente le catalogue COMPLET : les modèles actifs
    # en clair, ceux qu'un palier supérieur débloquerait en commentaire.
    # Rien n'est à décommenter à la main — la prochaine validation les
    # réintègre d'elle-même.
    inventory = [
        "# Catalogue Ollama Cloud — généré le %s par scripts/nexus_generate.py"
        % datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "# Actifs : exécutables avec l'abonnement Ollama Cloud actuel.",
        "# Commentés : publiés mais non autorisés — ils redeviendront actifs",
        "# automatiquement dès qu'un palier supérieur sera souscrit.",
        "",
    ]
    inventory += list(cloud)
    if rejected:
        inventory.append("")
        for name in published:
            if name in rejected:
                inventory.append("# %-24s # %s" % (name, rejected[name]))
    with io.open(CLOUD_LIST, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(inventory) + "\n")

    print("\n=== Génération terminée ===")
    for name, content in blocks.items():
        print("  %-26s %d ligne(s)" % (name, len(content)))
    print("  Routeur cloud par défaut : %s" % default_cloud)
    print("  Version de routage       : %s" % router_version)
    return 0


if __name__ == "__main__":
    sys.exit(main())
