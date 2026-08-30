# -*- coding: utf-8 -*-
"""
Suite de tests Claude-Local-Nexus — modèles réels, chemins réels.

Trois familles de tests, volontairement distinctes :

  FORWARD  le chemin nominal produit-il le bon résultat ?
           (exécution locale, cloud, embeddings, routeurs, outils, vision)

  REVERSE  le système échoue-t-il correctement ?
           Un test qui ne vérifie que le succès ne prouve rien sur la
           robustesse : on injecte donc de vraies pannes (modèle
           inexistant, clé invalide, référence pendante, cycle,
           fallback de modalité) et l'on vérifie que la plateforme
           les refuse au lieu de les absorber silencieusement.

  POLICY   les frontières de coût et de confidentialité tiennent-elles ?
           Un routeur « local » ne doit jamais répondre depuis le cloud.

Usage :
    python scripts/nexus_test.py [--include-slow] [--only forward|reverse|policy|code|releve]
"""
from __future__ import annotations

import argparse
import base64
import copy
import io
import json
import os
import re
import subprocess
import sys
import random
import time
import urllib.error
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

PASSED: list[str] = []
FAILED: list[tuple[str, str]] = []
SKIPPED: list[tuple[str, str]] = []


# ----------------------------------------------------------------------
# Utilitaires
# ----------------------------------------------------------------------
def master_key() -> str:
    """Clé maîtresse, ou chaîne vide si les secrets ne sont pas configurés."""
    if os.environ.get("LITELLM_MASTER_KEY"):
        return os.environ["LITELLM_MASTER_KEY"]
    env_file = os.path.join(ROOT, ".env")
    if not os.path.exists(env_file):
        return ""
    with io.open(env_file, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            match = re.match(r"^\s*LITELLM_MASTER_KEY\s*=\s*(.*)$", line)
            if match and match.group(1).strip():
                # Guillemets et commentaire de fin de ligne retires : sinon
                # la valeur part telle quelle dans l'en-tete Authorization
                # et produit un 401 que rien n'explique.
                valeur = match.group(1).strip()
                if valeur[:1] in "\"'" and valeur[-1:] == valeur[:1]:
                    valeur = valeur[1:-1]
                return valeur.split("#")[0].strip()
    return ""


KEY = master_key()

# Un clone frais n'a pas de .env, et ce n'est pas une panne : c'est une
# etape d'installation. Faire echouer la suite dans ce cas ferait conclure
# au lecteur que « les tests de l'auteur ne passent pas », alors que rien
# n'est casse. Les verifications qui dependent des secrets sont donc
# ignorees, avec leur motif.
SECRETS_ABSENTS = not KEY


def call(path: str, payload=None, key: str | None = None, timeout: int = 300,
         with_headers: bool = False):
    """
    Retourne (status, corps décodé), ou (status, corps, en-têtes).

    Les en-têtes comptent : derrière un routeur adaptatif, le champ "model"
    du corps ne renvoie que le nom du routeur. Seul l'en-tête
    x-litellm-model-group révèle l'alias réellement servi.
    """
    url = BASE_URL + path
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(url, data=data, method="POST" if data else "GET")
    request.add_header("Authorization", "Bearer %s" % (KEY if key is None else key))
    if data:
        request.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = json.loads(response.read().decode("utf-8"))
            if with_headers:
                return response.status, body, dict(response.headers)
            return response.status, body
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", "replace")
        try:
            body = json.loads(raw)
        except Exception:
            body = {"raw": raw}
        return (exc.code, body, dict(exc.headers)) if with_headers else (exc.code, body)
    except Exception as exc:
        return (0, {"error": str(exc)}, {}) if with_headers else (0, {"error": str(exc)})


def ask(model: str, prompt: str, max_tokens: int = 64, timeout: int = 300,
        key: str | None = None, with_headers: bool = False,
        no_cache: bool = True, **extra):
    """
    `key` part dans l'en-tete Authorization ; `extra` dans le corps.

    Le cache est desactive par defaut : un test qui mesure 0,0 s n'a pas
    exerce le modele, il a relu Redis. Un test vert sur du cache ne prouve
    rien sur la plateforme.
    """
    payload = {"model": model, "messages": [{"role": "user", "content": prompt}],
               "max_tokens": max_tokens}
    if no_cache:
        payload["cache"] = {"no-cache": True}
    payload.update(extra)
    return call("/v1/chat/completions", payload, key=key, timeout=timeout,
                with_headers=with_headers)


def resolved_model(headers: dict, body: dict) -> str:
    """
    Alias reellement choisi, routeur traverse.

    x-litellm-adaptive-router-model est le seul en-tete qui designe le
    modele retenu par un routeur adaptatif : le corps et model-group ne
    renvoient que le nom du routeur lui-meme.
    """
    lowered = {k.lower(): v for k, v in headers.items()}
    for name in ("x-litellm-adaptive-router-model", "x-litellm-model-group"):
        if lowered.get(name):
            return lowered[name]
    return body.get("model", "")


def served_model(headers: dict) -> str:
    """Modele amont ayant reellement produit la reponse (fallback compris)."""
    lowered = {k.lower(): v for k, v in headers.items()}
    return lowered.get("x-litellm-model-name", "")


def served_endpoint(headers: dict) -> str:
    """
    Adresse reellement contactee.

    C'est la preuve directe de non-fuite : peu importe quel alias a ete
    choisi, ce qui compte est de savoir si la requete a quitte la machine.
    """
    lowered = {k.lower(): v for k, v in headers.items()}
    return lowered.get("x-litellm-model-api-base", "")


def check(name: str, condition: bool, detail: str = "") -> bool:
    if condition:
        PASSED.append(name)
        print("  [PASS] %-52s %s" % (name, detail))
    else:
        FAILED.append((name, detail))
        print("  [FAIL] %-52s %s" % (name, detail))
    return condition


def skip(name: str, reason: str) -> None:
    SKIPPED.append((name, reason))
    print("  [SKIP] %-52s %s" % (name, reason))


def load_config() -> dict:
    with io.open(CONFIG, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def exposed_models() -> list[str]:
    status, body = call("/v1/models", timeout=30)
    if status != 200:
        return []
    return sorted(d["id"] for d in body.get("data", []))


def recover_swapped_config() -> None:
    """
    Répare une permutation laissée par une exécution interrompue.

    run_validator_on déplace momentanément la vraie configuration vers
    `.testswap`. Si le processus meurt dans cette fenêtre, le dépôt se
    retrouve sans `litellm_config.yaml`. On restaure donc avant tout.
    """
    swapped = CONFIG + ".testswap"
    if not os.path.exists(swapped):
        return
    if os.path.exists(CONFIG):
        # La configuration est revenue : le fichier de secours est un reste.
        os.remove(swapped)
        print("  [i] reste d'une execution interrompue supprime")
    else:
        os.replace(swapped, CONFIG)
        print("  [i] configuration restauree apres une execution interrompue")


def run_validator_on(config: dict) -> tuple[int, str]:
    """Écrit une configuration temporaire et lui applique le validateur."""
    recover_swapped_config()
    temp = os.path.join(ROOT, "backups", "_test_config.yaml")
    os.makedirs(os.path.dirname(temp), exist_ok=True)
    with io.open(temp, "w", encoding="utf-8", newline="\n") as fh:
        yaml.safe_dump(config, fh, allow_unicode=True, sort_keys=False)
    original = CONFIG
    backup = original + ".testswap"
    os.replace(original, backup)
    try:
        os.replace(temp, original)
        result = subprocess.run(
            [sys.executable, os.path.join(ROOT, "scripts", "nexus_validate.py")],
            capture_output=True, text=True, timeout=180,
        )
        return result.returncode, result.stdout + result.stderr
    finally:
        if os.path.exists(original):
            os.remove(original)
        os.replace(backup, original)


# ----------------------------------------------------------------------
# FORWARD — le chemin nominal
# ----------------------------------------------------------------------
def test_forward(models: list[str], include_slow: bool) -> None:
    print("\n--- FORWARD : le chemin nominal produit-il le bon resultat ? ---")

    status, body = call("/health/liveliness", timeout=20)
    check("proxy joignable", status == 200)

    check("inventaire non vide", len(models) > 0, "%d modeles" % len(models))

    # Jeton aleatoire a restituer. Le hasard interdit le cache et prouve
    # donc une inference reelle, mais la tache reste a la portee de
    # n'importe quel modele.
    #
    # L'arithmetique, essayee d'abord, melangeait deux questions : la
    # plateforme achemine-t-elle correctement, et le modele sait-il
    # compter. phi3-mini a repondu 244 pour 344 — resultat exact sur la
    # seconde question, mais qui faisait echouer un test cense porter sur
    # la premiere. Juger la qualite d'un modele est le role de
    # nexus_compare, pas celui d'un test d'acheminement.
    def echo_task():
        token = "NX%04d" % random.randint(1000, 9999)
        # La consigne doit etre inequivoque pour un petit modele. Une
        # premiere version disait « recopie ce code » : phi3-mini y a lu
        # une demande d'ecrire du Python et a repondu par un extrait de
        # code. Un test d'acheminement ne doit pas echouer sur une
        # ambiguite de formulation.
        return ("Repete ce mot et rien d'autre : %s" % token), token

    for model in ["phi3-mini-local", "llama3.2-3b-local", "gemma4-12b-local"]:
        if model not in models:
            skip("acheminement local : %s" % model, "non expose")
            continue
        prompt, expected = echo_task()
        start = time.time()
        status, body = ask(model, prompt)
        if status != 200:
            check("acheminement local : %s" % model, False, "HTTP %s" % status)
            continue
        text = body["choices"][0]["message"]["content"]
        check("acheminement local : %s" % model, expected in text,
              "%.1fs — %s restitue" % (time.time() - start, expected)
              if expected in text
              else "%.1fs — attendu %s, recu %r" % (time.time() - start, expected,
                                                    text.strip()[:40]))

    cloud = [m for m in models if m.endswith("-cloud") and not m.startswith("adaptive")]
    if cloud:
        target = cloud[0]
        prompt, expected = echo_task()
        start = time.time()
        status, body = ask(target, prompt, timeout=600)
        text = body["choices"][0]["message"]["content"] if status == 200 else ""
        check("acheminement cloud : %s" % target,
              status == 200 and expected in text,
              "%.1fs — %s restitue" % (time.time() - start, expected)
              if expected in text
              else "%.1fs — attendu %s, recu %r" % (time.time() - start, expected,
                                                    text.strip()[:40]))
    else:
        skip("acheminement cloud", "aucun modele cloud expose")

    # Embeddings : deux phrases proches doivent être plus proches entre elles
    # qu'une phrase sans rapport. C'est ce qui rend la recherche utilisable.
    # On teste le modele que le pont utilise reellement. nomic-embed-text a
    # ete ecarte apres mesure : sur des paires francaises il classe la phrase
    # sans rapport au-dessus de la paraphrase, ce qui rendrait la recherche
    # trompeuse plutot que simplement mediocre.
    embed_model = os.environ.get("NEXUS_EMBED_MODEL", "qwen3-embedding-8b-local")
    nonce = "ref%d" % random.randint(10000, 99999)
    status, body = call("/v1/embeddings", {
        "model": embed_model,
        "cache": {"no-cache": True},
        "input": ["%s le chat dort sur le canape" % nonce,
                  "%s un felin se repose sur le sofa" % nonce,
                  "%s compilation du noyau linux en mode verbeux" % nonce],
    }, timeout=900)
    if status != 200:
        check("embeddings coherents : %s" % embed_model, False, "HTTP %s" % status)
    else:
        vectors = [d["embedding"] for d in body["data"]]

        def cosine(a, b):
            dot = sum(x * y for x, y in zip(a, b))
            na = sum(x * x for x in a) ** 0.5
            nb = sum(y * y for y in b) ** 0.5
            return dot / (na * nb) if na and nb else 0

        close = cosine(vectors[0], vectors[1])
        far = cosine(vectors[0], vectors[2])
        # Une marge est exigee : une separation infime ne survivrait pas au
        # bruit d'un vrai corpus.
        check("embeddings coherents : %s" % embed_model, close > far + 0.05,
              "proche=%.3f vs eloigne=%.3f (marge %.3f)" % (close, far, close - far))

    # Appel d'outils : c'est la capacité qui justifie ollama_chat/ plutot
    # que ollama/. On vérifie qu'un modèle local renvoie bien un tool_call.
    tool_model = next((m for m in ["llama3.2-3b-local", "qwen2.5-coder-14b-local"]
                       if m in models), None)
    if not tool_model:
        skip("appel d'outil local", "aucun modele candidat")
    else:
        status, body = ask(
            tool_model,
            "Quelle est la meteo a Lyon ? Utilise l'outil.",
            max_tokens=256,
            tools=[{
                "type": "function",
                "function": {
                    "name": "get_weather",
                    "description": "Donne la meteo d'une ville",
                    "parameters": {
                        "type": "object",
                        "properties": {"city": {"type": "string"}},
                        "required": ["city"],
                    },
                },
            }],
        )
        calls = (body.get("choices", [{}])[0].get("message", {}) or {}).get("tool_calls") \
            if status == 200 else None
        # Un tool_call vers la mauvaise fonction, ou sans la ville demandee,
        # n'est pas un appel reussi : il serait inexploitable. Verifier la
        # seule presence d'un tool_call laisserait passer les deux cas.
        bonne_fonction = bool(calls) and calls[0]["function"]["name"] == "get_weather"
        arguments = calls[0]["function"].get("arguments", "") if calls else ""
        if isinstance(arguments, dict):
            arguments = json.dumps(arguments)
        bonne_ville = "lyon" in str(arguments).lower()
        check("appel d'outil local : %s" % tool_model,
              bonne_fonction and bonne_ville,
              "%s(%s)" % (calls[0]["function"]["name"], str(arguments)[:48])
              if calls else "aucun tool_call")

    # Vision : un modèle multimodal doit lire une vraie image.
    banner = os.path.join(ROOT, "images", "banner.png")
    vision_model = next((m for m in ["llava-7b-local", "llama3.2-vision-11b-local"]
                         if m in models), None)
    if not include_slow:
        skip("vision sur image reelle", "lent sur CPU (--include-slow)")
    elif not vision_model or not os.path.exists(banner):
        skip("vision sur image reelle", "modele ou image absent")
    else:
        with open(banner, "rb") as fh:
            encoded = base64.b64encode(fh.read()).decode("ascii")
        status, body = call("/v1/chat/completions", {
            "model": vision_model,
            "messages": [{"role": "user", "content": [
                {"type": "text", "text": "Decris cette image en une phrase."},
                {"type": "image_url",
                 "image_url": {"url": "data:image/png;base64," + encoded}},
            ]}],
            "max_tokens": 120,
        }, timeout=900)
        text = body["choices"][0]["message"]["content"] if status == 200 else ""
        check("vision sur image reelle : %s" % vision_model,
              status == 200 and len(text.strip()) > 20, text.strip()[:60])

    # Routeurs : ils doivent répondre ET révéler le modèle réellement retenu.
    for router in ["adaptive-router-local", "adaptive-router-cloud", "adaptive-router"]:
        if router not in models:
            skip("routeur repond : %s" % router, "non expose")
            continue
        # Un 200 avec un corps vide passerait un test qui ne verifie que le
        # code : on exige donc que la reponse restitue le jeton demande.
        prompt, expected = echo_task()
        status, body, headers = ask(router, prompt, timeout=900, with_headers=True)
        selected = resolved_model(headers, body) if status == 200 else ""
        text = (body.get("choices") or [{}])[0].get("message", {}).get("content", "")             if status == 200 else ""
        check("routeur repond : %s" % router,
              status == 200 and expected in text,
              "-> %s" % (selected or "HTTP %s" % status))


# ----------------------------------------------------------------------
# REVERSE — le système échoue-t-il correctement ?
# ----------------------------------------------------------------------
def test_reverse(models: list[str]) -> None:
    print("\n--- REVERSE : le systeme echoue-t-il correctement ? ---")

    # Un modèle inexistant doit être refusé franchement, pas absorbé.
    status, body = ask("modele-qui-nexiste-pas-local", "test", timeout=60)
    check("modele inexistant refuse", status in (400, 404),
          "HTTP %s" % status)

    # Une clé invalide ne doit jamais passer.
    status, body = ask("phi3-mini-local", "test", key="clef-invalide-xyz", timeout=60)
    check("clef invalide rejetee", status in (401, 403), "HTTP %s" % status)

    # Le validateur doit attraper une référence pendante.
    config = load_config()
    broken = copy.deepcopy(config)
    broken.setdefault("router_settings", {}).setdefault("fallbacks", []).insert(
        0, {"phi3-mini-local": ["modele-fantome-local"]})
    code, output = run_validator_on(broken)
    check("reference pendante detectee", code == 1 and "modele-fantome-local" in output,
          "code %s" % code)

    # Le validateur doit attraper un cycle.
    broken = copy.deepcopy(config)
    broken.setdefault("router_settings", {}).setdefault("fallbacks", []).insert(
        0, {"phi3-mini-local": ["llama3.2-3b-local"]})
    broken["router_settings"]["fallbacks"].insert(
        0, {"llama3.2-3b-local": ["phi3-mini-local"]})
    code, output = run_validator_on(broken)
    check("cycle de fallback detecte", code == 1 and "cycle" in output.lower(),
          "code %s" % code)

    # Le validateur doit refuser un fallback qui change de modalité :
    # une image envoyee a un modele textuel ne produit pas une erreur
    # franche, elle produit une reponse fausse.
    broken = copy.deepcopy(config)
    broken.setdefault("router_settings", {}).setdefault("fallbacks", []).insert(
        0, {"llava-7b-local": ["phi3-mini-local"]})
    code, output = run_validator_on(broken)
    check("fallback de modalite refuse",
          code == 1 and "incompatible" in output.lower(),
          "code %s" % code)

    # Un cycle place ailleurs que dans `fallbacks` doit etre vu aussi.
    broken = copy.deepcopy(config)
    broken.setdefault("context_window_fallbacks", []).insert(
        0, {"phi3-mini-local": ["llama3.2-3b-local"]})
    broken["context_window_fallbacks"].insert(
        0, {"llama3.2-3b-local": ["phi3-mini-local"]})
    code, output = run_validator_on(broken)
    check("cycle hors de fallbacks detecte aussi",
          code == 1 and "context_window_fallbacks" in output,
          "code %s" % code)

    # Le pool d'un routeur doit respecter le domaine annonce par son nom :
    # c'est la promesse sur laquelle repose toute la politique locale.
    broken = copy.deepcopy(config)
    for model in broken["model_list"]:
        params = model.get("litellm_params") or {}
        if model["model_name"] == "adaptive-router-local":
            params["adaptive_router_config"]["available_models"].append(
                "gpt-oss-120b-cloud")
            break
    code, output = run_validator_on(broken)
    check("modele cloud refuse dans le pool local",
          code == 1 and "hors des domaines" in output, "code %s" % code)

    # Un modele que la machine ne peut pas executer ne doit pas etre le
    # default_model d'un routeur -- c'est le chemin le plus servi quand le
    # routeur ne tranche pas.
    broken = copy.deepcopy(config)
    broken["model_list"].append({
        "model_name": "modele-trop-lourd-local",
        "litellm_params": {"model": "ollama_chat/llama4:scout",
                           "api_base": "http://ollama:11434"},
        "model_info": {"max_input_tokens": 8192},
    })
    for model in broken["model_list"]:
        params = model.get("litellm_params") or {}
        if model["model_name"] == "adaptive-router-local":
            params["adaptive_router_default_model"] = "modele-trop-lourd-local"
            break
    code, output = run_validator_on(broken)
    check("modele hors budget refuse comme default_model",
          code == 1 and "modele-trop-lourd-local" in output, "code %s" % code)

    # Le validateur doit refuser un pool de routeur vide.
    broken = copy.deepcopy(config)
    for model in broken["model_list"]:
        params = model.get("litellm_params") or {}
        if str(params.get("model", "")).startswith("auto_router/"):
            params["adaptive_router_config"]["available_models"] = []
            break
    code, output = run_validator_on(broken)
    check("pool de routeur vide refuse", code == 1 and "vide" in output.lower(),
          "code %s" % code)

    # Un modèle inexistant ne doit pas être « rattrapé » par un fallback :
    # échouer franchement vaut mieux que répondre depuis un autre modèle,
    # car l'appelant croirait avoir obtenu ce qu'il a demandé.
    status, body = ask("phi3-mini-local-inexistant", "Dis: pret", timeout=90)
    served = body.get("model") if status == 200 else None
    check("chemin interdit non rattrape par un fallback", served is None,
          "servi par %s" % served if served else "aucune reponse servie")

    # Une requête d'embedding ne doit jamais être servie par un modèle de
    # chat : la réponse aurait la mauvaise forme sans erreur explicite.
    status, body = call("/v1/embeddings",
                        {"model": "phi3-mini-local", "input": "test"}, timeout=120)
    served_ok = status == 200 and body.get("data") and "embedding" in body["data"][0]
    check("embedding refuse sur un modele de chat", not served_ok,
          "HTTP %s" % status)

    # FUITE TRANSITIVE : un fallback a deux sauts peut sortir du domaine
    # la ou un controle a un saut ne voit rien. On calcule donc la
    # fermeture transitive du graphe et l'on verifie qu'aucun modele local
    # n'atteint, meme indirectement, le cloud ou Anthropic.
    config = load_config()
    domains = domains_of(config)
    graph: dict[str, list[str]] = {}
    for entry in (config.get("router_settings") or {}).get("fallbacks") or []:
        for source, targets in entry.items():
            graph.setdefault(source, []).extend(targets or [])

    # Les candidats d'un routeur sont des aretes au meme titre que ses
    # replis : c'est par eux qu'il choisit. Les omettre laissait passer un
    # modele cloud glisse dans le pool de adaptive-router-local -- le test
    # concluait alors « fermeture transitive propre » sur une fuite reelle.
    for model in config.get("model_list") or []:
        params = model.get("litellm_params") or {}
        if str(params.get("model", "")).startswith("auto_router/"):
            pool = (params.get("adaptive_router_config") or {}).get("available_models") or []
            graph.setdefault(model["model_name"], []).extend(pool)

    def reachable(start: str) -> set[str]:
        seen: set[str] = set()
        stack = list(graph.get(start, []))
        while stack:
            node = stack.pop()
            if node in seen:
                continue
            seen.add(node)
            stack.extend(graph.get(node, []))
        return seen

    leaks = []
    for alias, domain in domains.items():
        if domain != "local":
            continue
        for target in reachable(alias):
            target_domain = domains.get(target)
            if target_domain and target_domain != "local":
                leaks.append("%s ~> %s (%s)" % (alias, target, target_domain))
    check("aucune fuite transitive depuis le pool local", not leaks,
          "; ".join(leaks[:3]) if leaks else "fermeture transitive propre")

    # Un fichier de secrets ne doit ni etre resume ni entrer dans l'index :
    # les extraits remontent vers l'orchestrateur et quittent la machine.
    server = os.path.join(ROOT, "tools", "nexus-mcp", "server.js")
    messages = "\n".join([
        json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                    "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                               "clientInfo": {"name": "test", "version": "1"}}}),
        json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/call",
                    "params": {"name": "nexus_summarize",
                               "arguments": {"paths": [".env"]}}}),
    ]) + "\n"
    try:
        result = subprocess.run(["node", server], input=messages,
                                capture_output=True, text=True, timeout=180)
        replies = {r.get("id"): r for r in
                   (json.loads(l) for l in result.stdout.splitlines()
                    if l.strip().startswith("{"))}
        text = replies.get(2, {}).get("result", {}).get("content", [{}])[0].get("text", "")
        # Ni le contenu du fichier ni une cle ne doivent apparaitre.
        refused = "refuse" in text.lower()
        no_secret = not re.search(r"(sk-ant-|MASTER_KEY\s*=\s*\S|PASSWORD\s*=\s*\S)", text)
        check("fichier de secrets ni resume ni indexe", refused and no_secret,
              "refus=%s, aucun secret=%s" % (refused, no_secret))
    except Exception as exc:
        check("fichier de secrets ni resume ni indexe", False, str(exc))

    # Une image envoyee a un modele TEXTUEL ne doit pas produire une reponse
    # d'apparence plausible : c'est le pire des echecs, puisqu'il ne se voit
    # pas. Verifier la longueur de la reponse d'un modele de vision ne dit
    # rien la-dessus ; seul ce test le prouve.
    banner = os.path.join(ROOT, "images", "banner.png")
    if not os.path.exists(banner):
        skip("image refusee par un modele textuel", "aucune image de test")
    else:
        with open(banner, "rb") as fh:
            encoded = base64.b64encode(fh.read()).decode("ascii")
        status, body = call("/v1/chat/completions", {
            "model": "phi3-mini-local",
            "cache": {"no-cache": True},
            "messages": [{"role": "user", "content": [
                {"type": "text", "text": "Que montre cette image ?"},
                {"type": "image_url",
                 "image_url": {"url": "data:image/png;base64," + encoded}},
            ]}],
            "max_tokens": 80,
        }, timeout=300)
        texte = ""
        if status == 200:
            texte = (body.get("choices") or [{}])[0].get("message", {}).get("content", "")
        # Acceptable : un refus franc, ou une reponse qui reconnait ne pas
        # voir l'image. Inacceptable : une description assuree.
        avoue = re.search(r"ne (peux|puis)|pas d'image|aucune image|incapab|"
                          r"cannot|unable|no image|as an ai", texte, re.I)
        check("image refusee par un modele textuel",
              status != 200 or not texte.strip() or bool(avoue),
              "HTTP %s — %r" % (status, texte.strip()[:60]))

    # Le serveur MCP doit signaler un outil inconnu sans se terminer.
    server = os.path.join(ROOT, "tools", "nexus-mcp", "server.js")
    messages = "\n".join([
        json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                    "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                               "clientInfo": {"name": "test", "version": "1"}}}),
        json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/call",
                    "params": {"name": "outil_inexistant", "arguments": {}}}),
        json.dumps({"jsonrpc": "2.0", "id": 3, "method": "tools/list"}),
    ]) + "\n"
    try:
        result = subprocess.run(["node", server], input=messages,
                                capture_output=True, text=True, timeout=120)
        replies = [json.loads(l) for l in result.stdout.splitlines() if l.strip().startswith("{")]
        unknown = next((r for r in replies if r.get("id") == 2), None)
        survived = any(r.get("id") == 3 for r in replies)
        # La specification MCP reserve `-32602` aux erreurs de PROTOCOLE --
        # outil inconnu, argument absent ou du mauvais type -- et laisse
        # `isError` aux echecs d'EXECUTION d'un outil qui existe. Le
        # serveur rendait autrefois `isError`, ce qui faisait passer une
        # faute d'appelant pour un incident d'execution : l'appelant ne
        # pouvait pas distinguer "cet outil n'existe pas" de "cet outil a
        # echoue", et reessayait donc indefiniment.
        code = (unknown or {}).get("error", {}).get("code")
        check("MCP : outil inconnu rend -32602 sans crash",
              bool(unknown) and code == -32602 and survived,
              "code=%s, survit=%s" % (code if unknown else "?", survived))
    except Exception as exc:
        check("MCP : outil inconnu signale sans crash", False, str(exc))


# ----------------------------------------------------------------------
# POLICY — les frontières tiennent-elles ?
# ----------------------------------------------------------------------
def domains_of(config: dict) -> dict[str, str]:
    """
    Domaine d'exécution de chaque alias : local, cloud ou anthropic.

    Les routeurs en reçoivent un aussi — le moins confidentiel de leur
    pool, car c'est ce qu'ils peuvent réellement exposer. Les exclure,
    comme c'était le cas, rendait muet tout contrôle portant sur eux :
    or c'est exactement là que la frontière locale est promise.
    """
    domains: dict[str, str] = {}
    routeurs: dict[str, list[str]] = {}
    for model in config.get("model_list") or []:
        alias = model["model_name"]
        params = model.get("litellm_params") or {}
        raw = str(params.get("model", ""))
        if raw.startswith("auto_router/"):
            routeurs[alias] = list(
                (params.get("adaptive_router_config") or {}).get("available_models") or [])
            continue
        if raw.startswith("anthropic/"):
            domains[alias] = "anthropic"
        elif "ollama.com" in str(params.get("api_base", "")):
            domains[alias] = "cloud"
        else:
            domains[alias] = "local"

    rang = {"local": 0, "cloud": 1, "anthropic": 2}
    for alias, pool in routeurs.items():
        presents = [domains[c] for c in pool if c in domains]
        if presents:
            domains[alias] = max(presents, key=lambda d: rang.get(d, 0))
    return domains


def test_policy(models: list[str]) -> None:
    print("\n--- POLICY : les frontieres de cout et de confidentialite tiennent-elles ? ---")

    config = load_config()
    domains = domains_of(config)

    # Le routeur local ne doit répondre que depuis un modèle local :
    # une bascule silencieuse vers le cloud trahirait la promesse de
    # confidentialité sur laquelle repose tout le classement L2/L3.
    if "adaptive-router-local" in models:
        leaked, observed = [], []
        for _ in range(3):
            status, body, headers = ask("adaptive-router-local", "Dis simplement: pret",
                                        timeout=900, with_headers=True)
            if status != 200:
                continue
            endpoint = served_endpoint(headers)
            selected = resolved_model(headers, body)
            observed.append("%s @ %s" % (served_model(headers) or selected, endpoint))
            # Preuve directe : l'adresse contactee doit rester l'Ollama local.
            if endpoint and "ollama.com" in endpoint:
                leaked.append("sortie vers %s" % endpoint)
            # Quatre formes, et pas une liste ouverte : la garde doit rester
            # stricte, sinon elle ne garde plus rien. `host.docker.internal`
            # a ete ajoute apres la sortie du moteur hors de Docker -- LiteLLM
            # est encore en conteneur et atteint l'hote par ce nom. Sans lui,
            # ce test criait au loup a chaque execution, et une garde de
            # confidentialite qu'on ignore ne garde rien le jour ou elle a
            # raison.
            LOCALES = ("http://ollama:", "http://host.docker.internal:",
                       "http://127.0.0.1:", "http://localhost:")
            if endpoint and not endpoint.startswith(LOCALES):
                leaked.append("adresse inattendue %s" % endpoint)
            if selected and not selected.startswith("adaptive-router")                     and domains.get(selected, "local") != "local":
                leaked.append("modele %s" % selected)
        if not observed:
            skip("routeur local ne sort jamais de la machine",
                 "aucune reponse observee")
        else:
            check("routeur local ne sort jamais de la machine", not leaked,
                  "; ".join(sorted(set(observed))) if not leaked
                  else "; ".join(sorted(set(leaked))))
    else:
        skip("routeur local ne sort jamais de la machine", "routeur non expose")

    # Le routeur global ne doit jamais basculer vers Anthropic : franchir
    # cette frontiere change la facturation sans decision explicite.
    fallbacks = (config.get("router_settings") or {}).get("fallbacks") or []
    global_targets = []
    for entry in fallbacks:
        for source, targets in entry.items():
            if source == "adaptive-router":
                global_targets = targets
    check("routeur global ne bascule pas vers Anthropic",
          all("anthropic" not in t for t in global_targets),
          "cibles: %s" % ", ".join(global_targets))

    # Direction des replis. La règle est asymétrique à dessein : se replier
    # vers le local ne fait perdre que de la capacité, alors que sortir vers
    # le cloud ou Anthropic élargirait l'exposition des données et
    # engagerait une dépense que personne n'a demandée.
    #
    # On vérifie donc le SENS, et non l'absence de franchissement :
    # interdire tout franchissement priverait la plateforme de son repli
    # quand un quota s'épuise, ce qui transformerait une dégradation
    # acceptable en interruption de service.
    def domain_of(alias: str) -> str | None:
        if alias == "adaptive-router-local":
            return "local"
        if alias.startswith("adaptive-router"):
            return None  # le routeur global couvre plusieurs plans
        return domains.get(alias)

    wrong_way, toward_local = [], 0
    for entry in fallbacks:
        for source, targets in entry.items():
            src = domain_of(source)
            for target in targets:
                dst = domain_of(target)
                if not src or not dst or src == dst:
                    continue
                if dst == "local":
                    toward_local += 1
                else:
                    wrong_way.append("%s(%s) -> %s(%s)" % (source, src, target, dst))

    check("aucun repli ne reduit la confidentialite", not wrong_way,
          ("%d repli(s) vers le local, aucun vers l'exterieur" % toward_local)
          if not wrong_way else "; ".join(wrong_way[:3]))

    # Réciproque : sans repli vers le local, un quota épuisé interromprait
    # le service au lieu de le dégrader.
    check("un quota epuise degrade au lieu d'interrompre", toward_local > 0,
          "%d chemin(s) de repli vers le local" % toward_local)

    # Aucun secret ne doit être écrit en dur dans la configuration.
    with io.open(CONFIG, encoding="utf-8") as fh:
        raw_config = fh.read()
    leaked_secrets = re.findall(r"(sk-ant-[A-Za-z0-9_-]{8,}|api_key:\s*(?!os\.environ)\S+)",
                                raw_config)
    check("aucun secret en dur dans la configuration", not leaked_secrets,
          "%d occurrence(s)" % len(leaked_secrets))


# ----------------------------------------------------------------------
# CODE — le code de la plateforme lui-meme
# ----------------------------------------------------------------------
def test_releve() -> None:
    """
    Le local prend-il réellement le relais si l'abonnement s'arrête ?

    C'est la promesse centrale de la plateforme, et la seule qu'aucun autre
    test ne couvre : les familles forward et policy vérifient que les
    modèles répondent et que les frontières tiennent, jamais qu'un modèle
    local sait *orchestrer* — demander un outil, exploiter le résultat,
    enchaîner. Un modèle qui répond n'orchestre pas, et la différence ne se
    découvre qu'au moment où l'on aurait eu besoin de la relève.

    Les quatre épreuves vivent dans nexus_releve.py, qui sert aussi de
    commande autonome. Les dupliquer ici les ferait diverger.
    """
    print("\n--- RELEVE : le local peut-il remplacer l'orchestrateur ? ---")
    sys.path.insert(0, os.path.join(ROOT, "scripts"))
    try:
        import nexus_agent as agent
        import nexus_releve as releve
    except Exception as exc:
        check("module de releve importable", False, str(exc))
        return

    try:
        cle = agent.cle_maitre()
    except SystemExit as exc:
        SKIPPED.append(("releve", "cle absente : %s" % exc))
        print("  [SKIP] releve  (LITELLM_MASTER_KEY absente)")
        return

    rapport = releve.juger(releve.RELEVE, cle)
    for e in rapport["epreuves"]:
        check("releve : %s" % e["epreuve"], e["ok"], str(e.get("detail", ""))[:160])
    # Servie par le cloud ou par Anthropic, la releve ne releve de rien :
    # elle depend precisement de ce dont on cherche a s'affranchir.
    check("releve servie en local", rapport["plan"] == "local",
          "plan reel : %s" % rapport["plan"])


def test_code() -> None:
    print("\n--- CODE : les scripts de la plateforme se tiennent-ils ? ---")

    sys.path.insert(0, os.path.join(ROOT, "scripts"))
    import nexus_generate as gen
    import nexus_capability as capability

    # Nommage : c'est la regle qui evite de declarer deux fois le meme
    # modele sous deux alias differents.
    cases = [
        ("qwen3-coder:30b", "qwen3-coder-30b-local"),
        ("codestral:latest", "codestral-local"),
        ("phi3:mini", "phi3-mini-local"),
        ("llama3.2-vision:11b", "llama3.2-vision-11b-local"),
        ("qwen2.5:32b", "qwen2.5-32b-local"),
    ]
    wrong = [(base, gen.local_alias(base), want)
             for base, want in cases if gen.local_alias(base) != want]
    check("alias local conforme aux declarations manuelles", not wrong,
          str(wrong[:2]) if wrong else "%d cas" % len(cases))

    cloud_cases = [
        ("gpt-oss:20b", "gpt-oss-20b-cloud"),
        ("glm-5.2", "glm-5.2-cloud"),
        ("mistral-large-3:675b", "mistral-large-3-675b-cloud"),
        ("kimi-k2.7-code", "kimi-k2.7-code-cloud"),
    ]
    wrong = [(base, gen.cloud_alias(base), want)
             for base, want in cloud_cases if gen.cloud_alias(base) != want]
    check("alias cloud conserve les points", not wrong,
          str(wrong[:2]) if wrong else "%d cas" % len(cloud_cases))

    # Un marqueur absent ou non ferme doit lever, jamais ecrire a l'aveugle.
    for label, lines in (
        ("absent", ["a", "b"]),
        ("non ferme", ["  # >>> AUTOGEN:X", "  contenu"]),
    ):
        try:
            gen.set_block(lines, "X", ["nouveau"])
            check("marqueur %s : refus d'ecrire" % label, False, "aucune erreur levee")
        except RuntimeError:
            check("marqueur %s : refus d'ecrire" % label, True)

    # set_block doit remplacer le contenu sans toucher aux bornes.
    sample = ["avant", "  # >>> AUTOGEN:X", "  vieux", "  # <<< AUTOGEN:X", "apres"]
    result = gen.set_block(sample, "X", ["  neuf"])
    check("set_block remplace sans deborder",
          result == ["avant", "  # >>> AUTOGEN:X", "  neuf", "  # <<< AUTOGEN:X", "apres"],
          " | ".join(result))

    # IDEMPOTENCE : c'est le test qui manquait historiquement. L'ancien
    # generateur reinjectait une ligne de commentaire a chaque execution
    # et avait fini par en accumuler sept. Deux executions successives
    # doivent produire un fichier strictement identique.
    with io.open(CONFIG, encoding="utf-8") as fh:
        snapshot = fh.read()
    try:
        # --no-validate : le test porte sur le mecanisme de reecriture, pas
        # sur les droits du compte. Valider ici rendrait le resultat
        # dependant d'un quota qui peut varier entre les deux executions.
        generate = [sys.executable,
                    os.path.join(ROOT, "scripts", "nexus_generate.py"),
                    "--no-validate"]
        first = subprocess.run(generate, capture_output=True, text=True, timeout=300)
        with io.open(CONFIG, encoding="utf-8") as fh:
            after_first = fh.read()
        second = subprocess.run(generate, capture_output=True, text=True, timeout=300)
        with io.open(CONFIG, encoding="utf-8") as fh:
            after_second = fh.read()
        if first.returncode != 0 or second.returncode != 0:
            check("generateur idempotent", False, "generation en echec")
        else:
            check("generateur idempotent", after_first == after_second,
                  "%d octets identiques" % len(after_second)
                  if after_first == after_second
                  else "ecart de %d octets" % abs(len(after_first) - len(after_second)))
    finally:
        # On restaure l'etat d'origine : un test ne doit rien laisser derriere lui.
        with io.open(CONFIG, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(snapshot)

    # Le validateur doit accepter la configuration reellement deployee.
    result = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "nexus_validate.py")],
                            capture_output=True, text=True, timeout=180)
    if not SECRETS_ABSENTS:
        check("configuration deployee valide", result.returncode == 0,
              "code %s" % result.returncode)

    # Regression : les modeles de chat doivent utiliser ollama_chat/
    # (l'endpoint generate laisse fuir les marqueurs de role et ne gere
    # pas l'appel d'outils), les embeddings rester sur ollama/.
    config = load_config()
    wrong_prefix = []
    for model in config.get("model_list") or []:
        alias = model["model_name"]
        raw = str((model.get("litellm_params") or {}).get("model", ""))
        is_embed = bool(re.search(r"embed|minilm", alias))
        if raw.startswith("ollama/") and not is_embed:
            wrong_prefix.append(alias)
        if raw.startswith("ollama_chat/") and is_embed:
            wrong_prefix.append(alias + " (embedding sur chat)")
    check("prefixe de provider correct partout", not wrong_prefix,
          ", ".join(wrong_prefix[:3]) if wrong_prefix else "chat=ollama_chat, embed=ollama")

    # Conformite MCP : version de protocole et methode inconnue.
    server = os.path.join(ROOT, "tools", "nexus-mcp", "server.js")
    messages = "\n".join([
        json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                    "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                               "clientInfo": {"name": "test", "version": "1"}}}),
        json.dumps({"jsonrpc": "2.0", "id": 2, "method": "methode/inconnue"}),
        json.dumps({"jsonrpc": "2.0", "id": 3, "method": "tools/list"}),
    ]) + "\n"
    try:
        result = subprocess.run(["node", server], input=messages,
                                capture_output=True, text=True, timeout=60)
        replies = {r.get("id"): r for r in
                   (json.loads(l) for l in result.stdout.splitlines()
                    if l.strip().startswith("{"))}
        init = replies.get(1, {}).get("result", {})
        check("MCP : handshake conforme",
              init.get("protocolVersion") == "2025-06-18"
              and "tools" in init.get("capabilities", {}),
              init.get("protocolVersion", "?"))
        check("MCP : methode inconnue -> -32601",
              replies.get(2, {}).get("error", {}).get("code") == -32601,
              str(replies.get(2, {}).get("error", {}).get("code")))
        tools = replies.get(3, {}).get("result", {}).get("tools", [])
        malformed = [t.get("name") for t in tools
                     if not t.get("name") or not t.get("description")
                     or (t.get("inputSchema") or {}).get("type") != "object"]
        check("MCP : schemas d'outils bien formes", tools and not malformed,
              "%d outils" % len(tools) if not malformed else str(malformed))
    except Exception as exc:
        check("MCP : conformite du protocole", False, str(exc))

    # Garde-fou materiel : les seuils doivent classer, pas tout accepter.
    profile = capability.build_profile()
    check("profil materiel mesurable",
          profile["inference_memory_gb"] > 0 and profile["cpu_cores"] > 0,
          "%.0f Go, %d coeurs, moteur %s"
          % (profile["inference_memory_gb"], profile["cpu_cores"],
             profile["ollama"]["mode"]))

    memory = profile["inference_memory_gb"]
    verdicts = [
        (memory * 0.10, capability.ACCEPT),
        (memory * 0.70, capability.DEGRADED),
        (memory * 2.00, capability.REJECT),
    ]
    wrong = [(size, expected, capability.verdict(size, profile)[0])
             for size, expected in verdicts
             if capability.verdict(size, profile)[0] != expected]
    check("verdicts materiels coherents", not wrong,
          str(wrong) if wrong else "ACCEPT / DEGRADED / REJECT distingues")

    # Un modele plus lourd que le disque libre ne doit pas etre telecharge.
    #
    # `free_disk_gb` vaut None quand la mesure a echoue. La multiplier levait,
    # et `not ok` sur l'etat indetermine (None) aurait fait PASSER le test sur
    # une mesure absente -- soit exactement la confusion que ce test existe
    # pour interdire ailleurs.
    if not profile.get("disque_mesure"):
        skip("telechargement refuse hors budget disque",
             "capacite disque non mesuree")
    else:
        ok, reason = capability.can_download(profile["free_disk_gb"] * 3, profile)
        check("telechargement refuse hors budget disque", ok is False, reason[:60])

    # Chaque script Python de la plateforme doit s'importer sans effet de bord.
    py_modules = ["nexus_capability", "nexus_generate", "nexus_switch_engine",
                  "nexus_migration_plan", "nexus_state", "nexus_boussole",
                  "nexus_preserve", "nexus_savings"]
    broken_imports = []
    for name in py_modules:
        result = subprocess.run(
            [sys.executable, "-c",
             "import sys; sys.path.insert(0, r'%s'); import %s"
             % (os.path.join(ROOT, "scripts"), name)],
            capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            broken_imports.append(name)
    check("modules Python importables sans effet de bord", not broken_imports,
          ", ".join(broken_imports) if broken_imports
          else "%d modules" % len(py_modules))

    if SECRETS_ABSENTS:
        skip("pile minimale valide sans Ollama", ".env absent")
        skip("profil 'embedded' rallume Ollama", ".env absent")
        skip("configuration deployee valide", ".env absent")
    # La pile minimale doit rester demarrable sans Ollama : c'est la cible
    # de la migration, et une cible qui ne se valide pas n'en est pas une.
    env_sans_profil = dict(os.environ)
    env_sans_profil["COMPOSE_PROFILES"] = ""
    minimal = subprocess.run(["docker", "compose", "config", "--services"],
                             cwd=ROOT, capture_output=True, text=True,
                             env=env_sans_profil, timeout=180)
    services_min = set(minimal.stdout.split()) if minimal.returncode == 0 else set()
    if not SECRETS_ABSENTS:
        check("pile minimale valide sans Ollama",
              services_min == {"db", "redis", "litellm"},
              ", ".join(sorted(services_min)) or "compose en echec")

    # Et le profil doit rester capable de le rallumer, sans quoi la
    # bascule ne serait pas reversible.
    env_avec_profil = dict(os.environ)
    env_avec_profil["COMPOSE_PROFILES"] = "embedded"
    complet = subprocess.run(["docker", "compose", "config", "--services"],
                             cwd=ROOT, capture_output=True, text=True,
                             env=env_avec_profil, timeout=180)
    services_all = set(complet.stdout.split()) if complet.returncode == 0 else set()
    if not SECRETS_ABSENTS:
        check("profil 'embedded' rallume Ollama", "ollama" in services_all,
              ", ".join(sorted(services_all)) or "compose en echec")

    # Aucun volume irremplacable ne doit etre absent de la sauvegarde, et
    # aucun volume retelechargeable ne doit y figurer : archiver 541 Go
    # pour 155 Go libres echouerait, et ne preserverait rien.
    with io.open(os.path.join(ROOT, "scripts", "backup.ps1"),
                 encoding="utf-8", errors="replace") as fh:
        backup_source = fh.read()
    sauvegarde_pg = "pgdata" in backup_source
    archive_ollama = re.search(r"^\s*@\{\s*Name\s*=\s*\"[^\"]*ollama",
                               backup_source, re.M)
    check("sauvegarde ciblee sur l'irremplacable",
          sauvegarde_pg and not archive_ollama,
          "pgdata sauvegarde=%s, ollama archive=%s"
          % (sauvegarde_pg, bool(archive_ollama)))

    # Les scripts PowerShell doivent au moins etre analysables — y compris
    # ceux de la racine, qui sont les points d'entree de l'utilisateur.
    ps_scripts = [f for f in os.listdir(os.path.join(ROOT, "scripts"))
                  if f.endswith(".ps1")]
    shell = "pwsh" if subprocess.run(["where", "pwsh"], capture_output=True).returncode == 0 \
        else "powershell"
    ps_paths = [os.path.join(ROOT, "scripts", n) for n in ps_scripts]
    ps_paths += [os.path.join(ROOT, n) for n in os.listdir(ROOT)
                 if n.endswith(".ps1")]
    rituels = os.path.join(ROOT, "rituels")
    if os.path.isdir(rituels):
        ps_paths += [os.path.join(rituels, n) for n in os.listdir(rituels)
                     if n.endswith(".ps1") and os.path.getsize(os.path.join(rituels, n))]

    broken = []
    for full in ps_paths:
        name = os.path.relpath(full, ROOT)
        path = full.replace("\\", "/")
        probe = (
            "$e=$null; [void][System.Management.Automation.Language.Parser]::"
            "ParseFile('%s',[ref]$null,[ref]$e); "
            "if($e -and $e.Count -gt 0){ exit 1 } else { exit 0 }" % path
        )
        result = subprocess.run([shell, "-NoProfile", "-Command", probe],
                                capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            broken.append(name)
    check("scripts PowerShell sans erreur de syntaxe", not broken,
          ", ".join(broken) if broken else "%d scripts" % len(ps_paths))


# ----------------------------------------------------------------------
def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--include-slow", action="store_true",
                        help="ajoute les tests lents (vision sur CPU)")
    parser.add_argument("--only", choices=["forward", "reverse", "policy", "code", "releve", "ruche"],
                        help="ne joue qu'une famille de tests")
    args = parser.parse_args()

    print("=" * 72)
    print(" Suite de tests Claude-Local-Nexus — %s" % BASE_URL)
    print("=" * 72)

    recover_swapped_config()
    models = exposed_models()

    if args.only in (None, "forward"):
        test_forward(models, args.include_slow)
    if args.only in (None, "reverse"):
        test_reverse(models)
    if args.only in (None, "policy"):
        test_policy(models)
    if args.only in (None, "code"):
        test_code()
    if args.only in (None, "ruche"):
        test_ruche()
    if args.only in (None, "releve"):
        test_releve()

    print("\n" + "=" * 72)
    print("  Reussis : %d    Echecs : %d    Ignores : %d"
          % (len(PASSED), len(FAILED), len(SKIPPED)))
    if FAILED:
        print("\n  Echecs :")
        for name, detail in FAILED:
            print("    - %s  (%s)" % (name, detail))
    print("=" * 72)
    return 1 if FAILED else 0




def test_ruche() -> None:
    """
    Un essaim en panne peut-il faire croire a la ruche qu'il a reussi ?

    Historique : la ruche a deja annonce 36 cibles "abouties", avec des
    horodatages identiques a la microseconde, sans avoir lance un seul
    essaim (corrige en 3abe81a). Ces epreuves simulent un essaim qui
    echoue, qui expire ou qui est introuvable -- sans jamais appeler un
    vrai modele -- afin qu'une regression future soit detectee ici, en
    quelques secondes, plutot que sur un vrai budget de temps et de jetons.
    """
    print("\n--- RUCHE : un essaim en panne produit-il vraiment un echec ? ---")
    sys.path.insert(0, os.path.join(ROOT, "scripts"))
    try:
        import nexus_ruche as ruche
    except Exception as exc:
        check("module ruche importable", False, str(exc))
        return

    import tempfile
    import textwrap
    from pathlib import Path

    def ecrire_faux_script(dossier: Path, nom: str, code: str) -> Path:
        chemin = dossier / nom
        chemin.write_text(textwrap.dedent(code), encoding="utf-8")
        return chemin

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        cible_a = tmp_path / "faux_a.py"
        cible_b = tmp_path / "faux_b.py"
        cible_a.write_text("# cible de test\n" * 31, encoding="utf-8")
        cible_b.write_text("# cible de test\n" * 31, encoding="utf-8")
        lot = [cible_a, cible_b]

        script_original = ruche.ESSAIM_SCRIPT
        etat_original = ruche.ETAT_FICHIER
        decouvrir_original = ruche.decouvrir_cibles
        argv_original = sys.argv
        timeout_original = os.environ.get("NEXUS_RUCHE_TIMEOUT")

        # Etat isole : sans ce remplacement, les cas qui appellent
        # ruche.main() ecriraient de vraies cibles temporaires dans le
        # journal reel du depot (.nexus/ruche-etat.json).
        ruche.ETAT_FICHIER = tmp_path / "etat-test.json"

        try:
            # RETOUR -- ECHEC : l'essaim se termine en erreur sans rien
            # ecrire. Aucune cible ne doit ressortir "ok".
            script = ecrire_faux_script(tmp_path, "essaim_echec.py", """
                import sys
                print("erreur simulee", file=sys.stderr)
                sys.exit(1)
            """)
            ruche.ESSAIM_SCRIPT = script
            resultats = ruche.lancer_essaim(lot, False, "cloud", 1)
            check("essaim en echec => echec pour toutes les cibles",
                  all(r["verdict"] == "echec" for r in resultats.values()),
                  str({Path(k).name: v["verdict"] for k, v in resultats.items()}))

            # RETOUR -- EXPIRE : l'essaim ne repond plus. Avant le
            # correctif, ce cas bloquait la ruche indefiniment (aucun
            # timeout sur le sous-processus). Le delai est plafonne tres
            # bas pour que le test reste rapide.
            script = ecrire_faux_script(tmp_path, "essaim_expire.py", """
                import time
                time.sleep(30)
            """)
            ruche.ESSAIM_SCRIPT = script
            os.environ["NEXUS_RUCHE_TIMEOUT"] = "2"
            depart = time.time()
            resultats = ruche.lancer_essaim(lot, False, "cloud", 1)
            duree = time.time() - depart
            check("essaim expire => echec sans blocage",
                  all(r["verdict"] == "echec" for r in resultats.values()) and duree < 20,
                  "%.1fs" % duree)
            os.environ.pop("NEXUS_RUCHE_TIMEOUT", None)

            # RETOUR -- NE LANCE RIEN : le script d'essaim est introuvable.
            ruche.ESSAIM_SCRIPT = tmp_path / "absent.py"
            resultats = ruche.lancer_essaim(lot, False, "cloud", 1)
            check("essaim introuvable => echec",
                  all(r["verdict"] == "echec" for r in resultats.values()),
                  str({Path(k).name: v["verdict"] for k, v in resultats.items()}))

            # ALLER -- un succes reel (code 0, CSV "ok") doit rester un succes.
            script_ok = ecrire_faux_script(tmp_path, "essaim_ok.py", """
                import argparse, sys, os
                p = argparse.ArgumentParser()
                p.add_argument("--cibles", nargs="+", required=True)
                p.add_argument("--plans", default="cloud")
                a = p.parse_args()
                for c in a.cibles:
                    print("%s,ok,0,5,modele-faux,%s" % (os.path.basename(c), a.plans))
                sys.exit(0)
            """)
            ruche.ESSAIM_SCRIPT = script_ok
            resultats = ruche.lancer_essaim(lot, False, "cloud", 1)
            check("essaim reussi => ok pour toutes les cibles",
                  all(r["verdict"] == "ok" for r in resultats.values()),
                  str({Path(k).name: v["verdict"] for k, v in resultats.items()}))

            # ALLER/RETOUR -- ECHEC PARTIEL : une cible en echec ne doit
            # plus noyer les cibles reellement corrigees du meme lot. Avant
            # le correctif, ce CSV etait relu comme du JSON (toujours en
            # echec) et la ruche retombait sur le seul code de retour du
            # sous-processus : un echec sur deux faisait echec du lot
            # entier, et les cibles deja corrigees repassaient inutilement
            # au banc gratuit a l'execution suivante.
            script_mixte = ecrire_faux_script(tmp_path, "essaim_mixte.py", """
                import argparse, sys, os
                p = argparse.ArgumentParser()
                p.add_argument("--cibles", nargs="+", required=True)
                p.add_argument("--plans", default="cloud")
                a = p.parse_args()
                noms = [os.path.basename(c) for c in a.cibles]
                for i, nom in enumerate(noms):
                    print("%s,%s,1,10,modele-faux,%s" % (nom, "echec" if i == 0 else "ok", a.plans))
                sys.exit(1)
            """)
            ruche.ESSAIM_SCRIPT = script_mixte
            resultats = ruche.lancer_essaim(lot, False, "cloud", 1)
            verdict_a = resultats.get(str(cible_a), {}).get("verdict")
            verdict_b = resultats.get(str(cible_b), {}).get("verdict")
            check("echec partiel : verdict distinct par cible",
                  verdict_a == "echec" and verdict_b == "ok",
                  "faux_a=%s, faux_b=%s" % (verdict_a, verdict_b))

            # RETOUR, niveau ruche entiere -- aucune cible decouverte ne
            # doit jamais rendre un succes. all() sur un dictionnaire vide
            # vaut True en Python : c'etait le piege exact.
            ruche.decouvrir_cibles = lambda: []
            sys.argv = ["nexus_ruche.py"]
            code = ruche.main()
            check("aucune cible decouverte => code de sortie en echec",
                  code == 1, "code %s" % code)

            # ALLER, niveau ruche entiere -- le meme garde-fou ne doit pas
            # se declencher a tort quand des cibles existent reellement.
            ruche.decouvrir_cibles = lambda: [cible_a]
            ruche.ESSAIM_SCRIPT = script_ok
            sys.argv = ["nexus_ruche.py", "--essaims", "1", "--taille-lot", "1",
                        "--tout-refaire"]
            code = ruche.main()
            check("cible reelle traitee avec succes => code de sortie ok",
                  code == 0, "code %s" % code)

            # ALLER, --max-cibles -- sans plafond, une execution couvre tout
            # le depot decouvert quel que soit --essaims/--taille-lot ; avec
            # lui, un essai reel a petit perimetre redevient possible.
            # Verifie en sous-processus reel : --simuler garantit un cout et
            # un trafic reseau nuls.
            script_ruche = os.path.join(ROOT, "scripts", "nexus_ruche.py")
            result = subprocess.run(
                [sys.executable, script_ruche, "--max-cibles", "2",
                 "--taille-lot", "2", "--essaims", "1", "--simuler",
                 "--tout-refaire"],
                capture_output=True, text=True, timeout=60)
            check("--max-cibles borne le volume traite",
                  "Cibles traitees cette execution : 2" in result.stdout,
                  (result.stdout.strip().splitlines() or ["aucune sortie"])[-1])
        finally:
            ruche.ESSAIM_SCRIPT = script_original
            ruche.ETAT_FICHIER = etat_original
            ruche.decouvrir_cibles = decouvrir_original
            sys.argv = argv_original
            if timeout_original is None:
                os.environ.pop("NEXUS_RUCHE_TIMEOUT", None)
            else:
                os.environ["NEXUS_RUCHE_TIMEOUT"] = timeout_original
if __name__ == "__main__":
    sys.exit(main())
