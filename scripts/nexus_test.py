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
        # CONFIG present ne veut PAS dire configuration saine.
        #
        # Si le processus meurt APRES l'echange, CONFIG contient la
        # configuration de TEST et .testswap la vraie. L'ancienne version
        # supprimait alors .testswap en croyant a un reste : elle detruisait
        # la vraie configuration et laissait la fausse en place.
        #
        # C'est arrive le 2026-08-30. Trois suites de tests ont ete tuees, et
        # « modele-trop-lourd-local » -- une cible de test referencant
        # llama4:scout, absent d'Ollama -- s'est retrouve declare ET designe
        # comme default_model du routeur local, puis commite.
        #
        # Le critere qui les distingue est net : yaml.safe_dump perd les
        # commentaires, donc une configuration de test n'a AUCUN marqueur
        # AUTOGEN. La vraie en a onze.
        try:
            with io.open(CONFIG, encoding="utf-8", errors="replace") as fh:
                actuelle_saine = "# >>> AUTOGEN:" in fh.read()
        except OSError:
            actuelle_saine = False
        if not actuelle_saine:
            os.replace(swapped, CONFIG)
            print("  [!] configuration de TEST trouvee en place : la vraie a "
                  "ete restauree depuis .testswap")
            return
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
    # chat : la réponse aurait la mauvaise forme sans erreur explicite (§17).
    #
    # Cette exigence avait été rétrogradée en sentinelle le 2026-08-30 :
    # phi3-mini-local rendait alors un vecteur de 1024 dimensions avec
    # HTTP 200, et la protection n'existait ni dans Ollama ni dans LiteLLM.
    # Déclarer `mode: chat` avait été essayé, puis retiré — sans effet.
    #
    # La sentinelle s'est déclenchée le jour même : la passerelle refuse
    # désormais, HTTP 400, « Unmapped LLM provider for this endpoint —
    # custom_llm_provider=ollama_chat ». Le refus est propre et pour la
    # bonne raison, et les replis déclarés sont tentés puis refusés de même.
    #
    # L'exigence est donc rétablie, comme la sentinelle le prescrivait
    # elle-même. C'est le cycle complet d'une sentinelle : elle constate une
    # limite, elle alerte quand la limite tombe, elle disparaît.
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
        # Une image envoyée à un modèle TEXTUEL ne doit pas produire une
        # réponse d'apparence plausible : c'est le pire des échecs, puisqu'il
        # ne se voit pas (§92).
        #
        # Cette exigence avait été rétrogradée en sentinelle le 2026-08-30 :
        # phi3-mini-local recevait l'image et répondait « Cette image est un
        # visuel de présentation (probablement une… » — une description
        # assurée de ce qu'il ne voit pas.
        #
        # La sentinelle s'est déclenchée le jour même, en même temps que
        # celle des embeddings : la passerelle refuse désormais, HTTP 400.
        # L'exigence est rétablie, comme la sentinelle le prescrivait.
        #
        # Reste acceptable, et le test le prévoit : un refus franc, ou une
        # réponse qui reconnaît ne pas voir l'image. Inacceptable : une
        # description assurée.
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


def test_routage_par_profil() -> None:
    """
    Les quatre profils resolvent-ils vers un modele reellement expose ?

    La table PROFILES vit cote JavaScript, dans le serveur MCP. Elle est LUE
    ici plutot que recopiee : une copie Python divergerait en silence le jour
    ou la table change, et le test cesserait de tester ce qu'il croit.

    resolveProfile parcourt spec.models dans l'ordre et rend le PREMIER
    expose. L'assertion porte donc sur cette propriete, et non sur un appel
    HTTP : il n'existe aucun endpoint de routage par profil.
    """
    print("\n--- ROUTAGE : les profils resolvent-ils vers un modele expose ? ---")

    racine = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    chemin = os.path.join(racine, "tools", "nexus-mcp", "server.js")
    try:
        with io.open(chemin, encoding="utf-8") as fh:
            source = fh.read()
    except Exception as exc:
        skip("routage : table des profils", "server.js illisible : %s" % exc)
        return

    # Le corps d'un profil contient lui-meme des accolades -- latency: { ... }
    # par exemple. Un motif en [^}] s'arrete a la premiere fermante et ne
    # trouve plus rien : c'est ce qui est arrive le jour ou latency a ete
    # ajoute. On autorise donc un niveau d'imbrication.
    motif = re.compile(
        r"(\w+)\s*:\s*\{(?:[^{}]|\{[^{}]*\})*?models\s*:\s*\[([^\]]*)\]",
        re.S)
    profils = {}
    for nom, liste in motif.findall(source):
        profils[nom] = [m.strip().strip("'\"") for m in liste.split(",") if m.strip()]

    attendus = {"coding", "reasoning", "rapide", "multimodal"}
    # Si l'extraction ne rend pas les quatre profils connus, c'est le motif
    # qui a vieilli, pas le routage. Le dire evite de chercher au mauvais
    # endroit.
    if set(profils) != attendus:
        skip("routage : table des profils",
             "extraction incoherente : %s" % sorted(profils))
        return
    check("routage : quatre profils extraits de server.js", True,
          ", ".join(sorted(profils)))

    status, corps = call("/v1/models")
    if status != 200 or not isinstance(corps, dict):
        skip("routage : inventaire", "GET /v1/models a rendu %s" % status)
        return
    exposes = {m.get("id") for m in corps.get("data", []) if m.get("id")}

    for profil in sorted(profils):
        candidats = profils[profil]
        presents = [m for m in candidats if m in exposes]
        if not presents:
            # Un profil sans modele disponible n'est pas un defaut de
            # routage : c'est un inventaire incomplet.
            skip("routage : profil %s" % profil,
                 "aucun candidat expose parmi %d" % len(candidats))
            continue
        retenu = presents[0]
        rang = candidats.index(retenu)
        # Tous ceux qui precedent le retenu doivent etre absents : sinon
        # resolveProfile en aurait choisi un autre.
        avant_absents = all(c not in exposes for c in candidats[:rang])
        check("routage : profil %s -> %s" % (profil, retenu), avant_absents,
              "rang %d sur %d candidats" % (rang + 1, len(candidats)))


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
        # « bge-m3 » est un embedding dont le nom ne dit ni « embed » ni
        # « minilm » : le motif le prenait pour un modele de chat et
        # signalait un faux prefixe. Meme angle mort que celui corrige dans
        # nexus_savings.py -- une famille d'embeddings se reconnait a son
        # nom propre, pas a un mot generique.
        is_embed = bool(re.search(r"embed|minilm|bge-", alias))
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
    parser.add_argument("--only", choices=["forward", "reverse", "policy", "routage", "code", "releve", "ruche", "vitrine", "isolation", "lecture",
                                 "shell", "portee", "semaphore", "mentions", "protocole",
                                 "terminal", "noms", "registre"],
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
    if args.only in (None, "routage"):
        test_routage_par_profil()
    if args.only in (None, "code"):
        test_code()
    if args.only in (None, "ruche"):
        test_ruche()
    if args.only in (None, "vitrine"):
        test_vitrine()
    if args.only in (None, "isolation"):
        test_isolation()
    if args.only in (None, "lecture"):
        test_garde_lecture()
    if args.only in (None, "shell"):
        test_garde_shell()
    if args.only in (None, "portee"):
        test_portee_import()
    if args.only in (None, "semaphore"):
        test_semaphore_local()
    if args.only in (None, "mentions"):
        test_mentions_reponse()
    if args.only in (None, "protocole"):
        test_protocole_refus()
    if args.only in (None, "terminal"):
        test_terminal_repli()
    if args.only in (None, "noms"):
        test_noms_js()
    if args.only in (None, "registre"):
        test_registre_epreuves()
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




def test_portee_import() -> None:
    """
    Le detecteur de portee voit-il, et se tait-il quand il le doit ?

    Un depot sain rend « OK ». Un motif casse rend « OK » aussi : le silence
    ne prouve donc rien, et il faut un cas positif FABRIQUE pour savoir que
    le detecteur detecte encore.

    Les cinq cas legitimes comptent autant que le cas dangereux. Le depot
    porte une trentaine d'imports locaux, tous justifies ; un detecteur qui
    les signalerait serait desactive le jour meme, et ne protegerait plus de
    rien.
    """
    import shutil
    import tempfile

    print("\n--- PORTEE DES IMPORTS : le detecteur detecte-t-il encore ? ---")

    outil = os.path.join(ROOT, "scripts", "nexus_portee_import.py")
    if not os.path.isfile(outil):
        skip("portee des imports", "nexus_portee_import.py introuvable")
        return

    dangereux = (
        "def prepare():\n"
        "    import subprocess\n"
        "    return subprocess.run(['true'])\n"
        "\n"
        "def autre_chemin():\n"
        "    return subprocess.TimeoutExpired\n"
    )

    legitimes = {
        "lie au niveau module": (
            "import json\n"
            "\n"
            "def charge():\n"
            "    import json\n"
            "    return json.loads('{}')\n"
            "\n"
            "def sauve():\n"
            "    return json.dumps({})\n"
        ),
        "builtin": (
            "def f():\n"
            "    import os\n"
            "    return os.getcwd()\n"
            "\n"
            "def g():\n"
            "    return len([1, 2])\n"
        ),
        "fonction imbriquee": (
            "def dehors():\n"
            "    import textwrap\n"
            "    def dedans():\n"
            "        return textwrap.dedent('  x')\n"
            "    return dedans()\n"
        ),
        "deux fonctions importent le meme nom": (
            "def une():\n"
            "    import yaml\n"
            "    return yaml.safe_load('a: 1')\n"
            "\n"
            "def deux():\n"
            "    import yaml\n"
            "    return yaml.safe_dump({})\n"
        ),
        "nom reaffecte chez l'employeur": (
            "def importe():\n"
            "    import shutil\n"
            "    return shutil.which('git')\n"
            "\n"
            "def emploie(shutil):\n"
            "    return shutil\n"
        ),
    }

    def jouer(source):
        dossier = tempfile.mkdtemp(prefix="epreuve_portee_")
        try:
            cible = os.path.join(dossier, "cas.py")
            with io.open(cible, "w", encoding="utf-8") as fh:
                fh.write(source)
            r = subprocess.run([sys.executable, outil, cible],
                               capture_output=True, text=True,
                               encoding="utf-8", errors="replace", timeout=120)
            return r.returncode, [l for l in r.stdout.splitlines() if l.strip()]
        finally:
            shutil.rmtree(dossier, ignore_errors=True)

    code, lignes = jouer(dangereux)
    check("cas dangereux signale",
          code == 1 and any("subprocess" in l for l in lignes),
          lignes[0] if lignes else "aucune sortie")

    for nom, source in legitimes.items():
        code, lignes = jouer(source)
        check("silence sur cas legitime : %s" % nom,
              code == 0 and lignes == ["OK"],
              "silence" if lignes == ["OK"] else "; ".join(lignes)[:70])

    # -- Seconde famille : un module employe sans etre importe NULLE PART.
    #
    # Trouve le 2026-08-30 par une vague d'audit, et invisible aux deux
    # controles existants : le module s'importe proprement, et le nom n'est
    # pas mal place -- il est absent. Dans nexus_bench.py, socket.timeout
    # etait employe aux lignes 127 et 195 sans aucun import de socket.
    #
    # L'effet etait grave : les deux usages sont dans un bloc
    # `except urllib.error.URLError`, et une exception levee dans un except
    # n'est pas rattrapee par les except FRERES du meme try. Le NameError
    # s'echappait donc de la fonction, et le banc de latence plantait sur la
    # condition meme qu'il mesure.
    absent = (
        "import urllib.error\n"
        "\n"
        "def mesurer():\n"
        "    try:\n"
        "        pass\n"
        "    except urllib.error.URLError as exc:\n"
        "        if isinstance(exc.reason, (TimeoutError, socket.timeout)):\n"
        "            return 'timeout'\n"
    )
    code, lignes = jouer(absent)
    check("module jamais importe : signale",
          code == 1 and any("socket" in l for l in lignes),
          lignes[0][:70] if lignes else "aucune sortie")

    # Les pieges qui ont fait rejeter un premier jet : il rendait 581 faux
    # positifs, prenant pour non liees les variables de comprehension et les
    # cibles de for, with et except. Le controle est volontairement ETROIT --
    # un nom de module standard, employe en attribut, lie nulle part -- et
    # c'est cette etroitesse qui le rend sur.
    muets = {
        "module bien importe":
            "import socket\n\ndef f():\n    return socket.timeout\n",
        "variables de comprehension":
            "def f(l):\n    return [n.strip() for n in l if n]\n",
        "nom de module en variable de boucle":
            "def f(c):\n    for io in c:\n        if io.strip():\n            return io\n",
        "cible de with et de except":
            ("def f(p):\n    with open(p) as json:\n        return json.read()\n"
             "\ndef g():\n    try:\n        pass\n"
             "    except ValueError as time:\n        return time.args\n"),
        "dunder de module":
            "import os\n\nRACINE = os.path.dirname(__file__)\n",
        "parametre nomme comme un module":
            "def f(re):\n    return re.sub('a', 'b', 'aa')\n",
    }
    for nom, source in muets.items():
        code, lignes = jouer(source)
        check("silence sur piege a faux positif : %s" % nom,
              code == 0 and lignes == ["OK"],
              "silence" if lignes == ["OK"] else "; ".join(lignes)[:70])

    # -- Un garde qui plante arrete le travail qu'il protegeait.
    #
    # `UnicodeDecodeError` est un ValueError, JAMAIS un OSError : un fichier
    # non utf-8 traversait le filtre de lecture et faisait tomber le
    # detecteur avec une trace. Or la porte de conformite l'appelle : un seul
    # fichier mal encode dans scripts/ aurait bloque le demarrage.
    #
    # Trouve le 2026-08-30 par une vague d'audit deleguee, sur un fichier
    # livre quelques minutes plus tot dans le meme tour.
    dossier = tempfile.mkdtemp(prefix="epreuve_portee_")
    try:
        cible = os.path.join(dossier, "mal_encode.py")
        with open(cible, "wb") as fh:
            fh.write(b"\xff\xfe\x00i\x00m\x00p\x00o\x00r\x00t\n")
        r = subprocess.run([sys.executable, outil, cible], capture_output=True,
                           text=True, encoding="utf-8", errors="replace", timeout=120)
        sortie = [l for l in r.stdout.splitlines() if l.strip()]
        check("fichier non utf-8 : le detecteur survit et continue",
              r.returncode == 0 and sortie == ["OK"] and "Traceback" not in (r.stderr or ""),
              "code=%s sortie=%s" % (r.returncode, "; ".join(sortie)[:40]))
    finally:
        shutil.rmtree(dossier, ignore_errors=True)


def test_semaphore_local() -> None:
    """
    Le plan local est-il encore borne, et le harnais le verrait-il sinon ?

    Mesure du 2026-08-30, 34 appels MCP dont une dizaine simultanes :
    plan local 8 reussites et 14 ECHECS, toutes des expirations a 600 s ;
    plan cloud 7 reussites et 0 echec. Ont expire un resume de README.md
    (15 Ko) et une extraction dite triviale : ce n'est pas la taille des
    taches qui a decide, c'est le nombre d'inferences concurrentes.

    `nexus_batch` etait deja sequentiel a dessein, mais seulement A
    L'INTERIEUR d'un appel. La regle existait en paragraphe, pas en
    mecanisme.

    L'epreuve joue sur le CODE REEL de server.js, extrait a la volee, et
    porte une CONTRE-EPREUVE : la variante fautive du premier jet -- jeton
    pris apres l'attente -- doit etre VUE. Sans elle, six cas verts ne
    prouveraient que la bonne humeur du harnais.
    """
    jouer_epreuve_node("epreuve_semaphore.js", "semaphore local",
                       "SEMAPHORE DU PLAN LOCAL : la borne tient-elle ?")


def jouer_epreuve_node(fichier: str, etiquette: str, titre: str) -> None:
    """
    Joue une epreuve Node du pont et reverse ses cas dans la suite.

    Ces epreuves lisent le CODE REEL de `server.js` et l'exercent : tester
    une copie ne prouverait que la copie. Elles portent chacune une
    CONTRE-EPREUVE, sans quoi une serie de cas verts ne prouverait que la
    bonne humeur du harnais.

    Un lanceur commun plutot qu'un par epreuve : la duplication est
    precisement ce que le pont vient de se voir reprocher, ou une meme regle
    vivait en deux copies et manquait aux deux autres appelants.
    """
    print("\n--- %s ---" % titre)

    epreuve = os.path.join(ROOT, "tools", "nexus-mcp", fichier)
    if not os.path.isfile(epreuve):
        skip(etiquette, "%s introuvable" % fichier)
        return
    try:
        r = subprocess.run(["node", epreuve], cwd=ROOT, capture_output=True,
                           text=True, encoding="utf-8", errors="replace",
                           timeout=300)
    except FileNotFoundError:
        skip(etiquette, "node introuvable")
        return
    except subprocess.TimeoutExpired:
        check(etiquette, False, "pas de reponse en 300 s")
        return

    vus = 0
    for ligne in (r.stdout or "").splitlines():
        ligne = ligne.strip()
        if not (ligne.startswith("[OK  ]") or ligne.startswith("[RATE]")):
            continue
        # rpartition, jamais split : deux cas s'appelaient tous deux
        # « limite 1 » dans le rapport, le libelle etant coupe a son PREMIER
        # deux-points au lieu du dernier.
        corps = ligne[6:].strip()
        nom, _, detail = corps.rpartition(" : ")
        if not nom:
            nom, detail = corps, ""
        check(nom, ligne.startswith("[OK  ]"), detail[:70])
        vus += 1
    # Une epreuve muette n'est pas une epreuve reussie : si elle n'a rien
    # imprime, c'est elle qui est cassee, et le silence se lirait comme un
    # succes.
    if not vus:
        check(etiquette, False, "aucun cas rendu par l'epreuve (code %s)" % r.returncode)


def test_mentions_reponse() -> None:
    """
    Un corps vide dit-il pourquoi il est vide ?

    `sansRaisonnement` rend la chaine vide quand un modele ouvre une balise
    de pensee sans la refermer -- choix juste, livrer le brouillon serait
    pire. Mais le vide etait rendu SANS explication alors que `chat()`
    detenait de quoi la donner. Mesure du 2026-08-30 : nexus_compare a
    affiche « ### glm-5.3-cloud » suivi de rien, a cote de « 50.4s 8234
    tokens », et l'appelant en a conclu « reponse tronquee ».

    L'epreuve rejoue ce cas-la, avec ses vrais chiffres, plutot qu'un cas
    invente pour la circonstance.
    """
    jouer_epreuve_node("epreuve_mentions.js", "mentions de reponse",
                       "MENTIONS DE REPONSE : un corps vide dit-il pourquoi ?")


def test_protocole_refus() -> None:
    """
    Un refus nomme-t-il le parametre ET l'issue ?

    Mesure du 2026-08-30, vague 2 sur le pont : sur 32 cas de protocole,
    DOUZE refus nommaient le parametre fautif sans jamais dire ce qu'il
    fallait fournir. Le critere est celui que ce depot s'applique a
    lui-meme : un garde qui refuse sans dire par ou passer se fait
    contourner, ou renoncer.

    L'epreuve porte aussi un defaut de CORRECTION, et non de seule
    ergonomie : `if (!args.prompt)` laissait passer une chaine d'espaces et
    un NOMBRE -- la negation d'un nombre non nul etant fausse. Le refus
    ecrit a la main etait moins clair ET moins juste que le helper que tous
    les autres outils employaient deja.
    """
    jouer_epreuve_node("epreuve_protocole.js", "refus du protocole",
                       "REFUS DU PROTOCOLE : nomment-ils l'issue ?")


def test_terminal_repli() -> None:
    """
    Chaque maillon d'une chaine externe porte-t-il SA PROPRE sortie locale ?

    Mesure du 2026-08-30. Le docstring de `render_chain` et le commentaire de
    son appelant affirmaient tous deux que « toute chaine externe s'acheve en
    local ». La configuration produite disait le contraire : 35 replis
    cloud -> cloud pour 3 cloud -> local. Le terminal n'etait greffe que s'il
    restait de la place, donc uniquement sur les deux derniers maillons.

    Ce que cela coutait : le mode de panne dominant du plan cloud est le 429,
    qui frappe le QUOTA DU COMPTE. Les successeurs cloud echouaient donc
    comme le premier, et chaque tentative ajoutait a la pression qui avait
    cause le 429. Mesure du meme soir : six taches simultanees, 36 refus et
    ZERO succes en six minutes, chacune se demultipliant en replis cloud.

    L'epreuve importe le code REEL de nexus_generate, et porte une
    contre-epreuve : l'ancienne regle laissait 4 maillons sur 6 sans issue.
    """
    import types

    print("\n--- TERMINAL DE REPLI : une issue locale a chaque maillon ? ---")

    try:
        import nexus_generate as gen
    except Exception as exc:
        skip("terminal de repli", str(exc).splitlines()[0][:60])
        return

    def faux(alias, modality="text"):
        e = types.SimpleNamespace()
        e.alias = alias
        e.modality = modality
        return e


    TERMINAL = ["glm-4.7-flash-local", "qwen3-coder-30b-local"]


    def cibles_de(lignes):
        """Rend {source: [cibles]} a partir du YAML produit."""
        res, courant = {}, None
        for l in lignes:
            s = l.strip()
            if s.endswith(":") and s.startswith("- "):
                courant = s[2:-1]
                res[courant] = []
            elif s.startswith("- ") and courant:
                res[courant].append(s[2:])
        return res


    # 1. Le cas qui a produit le defaut : une chaine cloud de six maillons.
    chaine = [faux("m%d-cloud" % i) for i in range(6)]
    rendu = cibles_de(gen.render_chain({"cloud": chaine}, 4, width=2, terminal=TERMINAL))
    sans_sortie = [s for s, c in rendu.items() if not any(t.endswith("-local") for t in c)]
    check("chaine cloud de six : chaque maillon a une sortie locale",
             not sans_sortie,
             "tous couverts" if not sans_sortie else "sans sortie : %s" % sans_sortie)

    trop_larges = {s: c for s, c in rendu.items() if len(c) > 2}
    check("la largeur demandee n'est jamais depassee", not trop_larges,
             "au plus 2 cibles" if not trop_larges else str(trop_larges))

    # 2. CONTRE-EPREUVE. L'ancienne regle -- greffer le terminal seulement s'il
    # restait de la place -- doit etre VUE par cette epreuve, sinon le cas 1 ne
    # prouve rien.
    def ancienne(chain, width, terminal):
        res = {}
        for i, entry in enumerate(chain):
            targets = [e.alias for e in chain[i + 1:i + 1 + width]]
            if terminal and len(targets) < width:
                for extra in terminal:
                    if extra not in targets and extra != entry.alias:
                        targets.append(extra)
                    if len(targets) >= width:
                        break
            if targets:
                res[entry.alias] = targets
        return res

    avant = ancienne(chaine, 2, TERMINAL)
    sans_avant = [s for s, c in avant.items() if not any(t.endswith("-local") for t in c)]
    check("contre-epreuve : l'ancienne regle est bien VUE",
             len(sans_avant) > 0,
             "l'ancienne laissait %d maillon(s) sans sortie locale" % len(sans_avant))

    # 3. La chaine LOCALE ne sort jamais : c'est une interdiction de
    # souverainete, pas une preference.
    locale = [faux("l%d-local" % i) for i in range(4)]
    rendu_local = cibles_de(gen.render_chain({"local": locale}, 4, width=2, terminal=None))
    fuites = [s for s, c in rendu_local.items()
              if any(t.endswith("-cloud") or t.startswith("claude-") for t in c)]
    check("la chaine locale ne sort jamais du plan", not fuites,
             "aucune fuite" if not fuites else str(fuites))

    # 4. Le controle de modalite tient : greffer un terminal TEXTUEL sur une
    # chaine de vision enverrait une image a un modele aveugle, qui ne rend pas
    # une erreur mais une reponse fausse.
    vision = [faux("v%d-cloud" % i, modality="vision") for i in range(3)]
    rendu_v = cibles_de(gen.render_chain({"vision": vision}, 4, width=2, terminal=TERMINAL))
    greffes = [s for s, c in rendu_v.items() if any(t in TERMINAL for t in c)]
    check("aucun terminal textuel greffe sur une chaine de vision", not greffes,
             "modalite preservee" if not greffes else str(greffes))

    # 5. width = 1 : mieux vaut une sortie locale que rien.
    rendu_1 = cibles_de(gen.render_chain({"cloud": chaine}, 4, width=1, terminal=TERMINAL))
    sans_1 = [s for s, c in rendu_1.items() if not any(t.endswith("-local") for t in c)]
    check("width=1 : la sortie locale prime", not sans_1,
             "tous couverts" if not sans_1 else str(sans_1))

    # 6. L'acyclicite reste structurelle : on ne retombe que sur des suivants.
    ordre = {e.alias: i for i, e in enumerate(chaine)}
    retours = [(s, t) for s, c in rendu.items() for t in c
               if t in ordre and ordre[t] <= ordre[s]]
    check("acyclicite structurelle preservee", not retours,
             "aucun retour en arriere" if not retours else str(retours))


def test_noms_js() -> None:
    """
    Une fonction appelee dans le pont existe-t-elle encore ?

    Defaut REEL du 2026-08-30, paye en production. Un correctif a remplace
    une REGION de server.js delimitee par deux commentaires, et cette region
    contenait aussi sansRaisonnement() et mentionsReponse(). Les deux sont
    restees appelees en six endroits.

    Rien ne pouvait le voir : `node --check` valide la SYNTAXE et jamais la
    resolution des noms, et les autres epreuves extraient des blocs isoles.
    Le serveur a plante a son redemarrage suivant, chez une session voisine,
    sur « sansRaisonnement is not defined ».

    Le controle est volontairement ETROIT, comme son cousin Python : un appel
    NU a un nom lie nulle part et absent des globals connus. Un detecteur qui
    crie a tort est desarme le jour meme -- trois faux positifs ont d'ailleurs
    du etre traites avant qu'il ne serve : deux mots-cles, et « separement
    (phase MAP) » dans un commentaire francais, dont le fragment « ment » se
    lisait comme un appel.
    """
    jouer_epreuve_node("epreuve_noms_js.js", "noms du pont",
                       "NOMS DU PONT : une fonction appelee existe-t-elle ?")


def test_registre_epreuves() -> None:
    """
    Une mesure ratee efface-t-elle une preuve acquise ?

    Defaut mesure le 2026-08-30, et invisible dans le fichier. `consigner`
    ecrit sous DEUX noms : l'alias demande et l'alias reellement servi. Quand
    `releve-locale` a passe 4/4, `glm-4.7-flash-local` portait donc 4/4 lui
    aussi -- a juste titre, c'est le meme modele. Puis `--tous` a interroge
    `glm-4.7-flash-local` directement, l'appel n'a jamais abouti, et le 0/4
    a ECRASE le 4/4.

    Le registre affirmait alors simultanement que le meme modele orchestre
    et n'orchestre pas. Ce n'est pas un etiquetage trompeur : c'est une
    preuve detruite. 105.2 est explicite -- l'absence de preuve n'est pas une
    preuve d'absence.

    Un echec REEL, lui, doit bien remplacer le verdict : sans quoi un modele
    qui se degrade resterait promu sur une mesure perimee.
    """
    import json as _json
    import shutil as _shutil
    import tempfile as _tempfile

    print("\n--- REGISTRE DES EPREUVES : une mesure ratee efface-t-elle ? ---")

    try:
        import nexus_releve as releve
    except Exception as exc:
        skip("registre des epreuves", str(exc).splitlines()[0][:60])
        return

    json = _json
    shutil = _shutil
    tempfile = _tempfile

    def rapport(modele, servi, reussies, plan, adresse):
        return {
            "modele": modele, "servi": servi, "reussies": reussies,
            "echouees": 4 - reussies if plan != "inconnu" else 0,
            "ignorees": 0 if plan != "inconnu" else 4,
            "concluante": bool(plan and plan != "inconnu" and adresse != "?"),
            "plan": plan, "adresse": adresse, "epreuves": [], "version": "1.1",
        }


    bac = tempfile.mkdtemp(prefix="epreuve_consigner_")
    ancien_root = releve.PLATEFORME
    try:
        releve.PLATEFORME = bac
        chemin = os.path.join(bac, ".nexus", "epreuves.json")

        # 1. Une reussite s'inscrit.
        #
        # L'epreuve ne s'appuie PAS sur la resolution d'alias : `alias_expose`
        # interroge le catalogue de la passerelle, qui n'a rien a voir avec la
        # regle testee ici. On consigne donc deux fois sous le MEME nom, ce qui
        # est exactement la sequence qui a detruit la preuve en production.
        releve.consigner(rapport("glm-4.7-flash-local", "ollama_chat/glm-4.7-flash",
                                 4, "local", "http://host.docker.internal:11434"))
        reg = json.load(io.open(chemin, encoding="utf-8"))["modeles"]
        check("une reussite s'inscrit",
                 reg.get("glm-4.7-flash-local", {}).get("complet") is True,
                 "noms inscrits : %s" % ", ".join(sorted(reg)))

        # 2. LE CAS REEL. Une tentative qui n'atteint pas le modele ne doit pas
        # effacer le 4/4 precedent.
        releve.consigner(rapport("glm-4.7-flash-local", "?", 0, "inconnu", "?"))
        reg = json.load(io.open(chemin, encoding="utf-8"))["modeles"]
        garde = reg.get("glm-4.7-flash-local", {})
        check("une tentative vaine n'efface pas la preuve acquise",
                 garde.get("complet") is True and garde.get("reussies") == 4,
                 "reussies=%s complet=%s" % (garde.get("reussies"), garde.get("complet")))
        check("la tentative vaine est tout de meme tracee",
                 bool(garde.get("derniere_tentative_vaine")),
                 garde.get("derniere_tentative_vaine") or "aucune trace")

        # 3. Un ECHEC REEL, lui, doit bien remplacer : c'est un verdict, pas une
        # absence de verdict. Sans quoi un modele qui se degrade resterait promu.
        releve.consigner(rapport("glm-4.7-flash-local", "ollama_chat/glm-4.7-flash", 1,
                                 "local", "http://host.docker.internal:11434"))
        reg = json.load(io.open(chemin, encoding="utf-8"))["modeles"]
        garde = reg.get("glm-4.7-flash-local", {})
        check("un echec REEL remplace bien le verdict precedent",
                 garde.get("reussies") == 1 and garde.get("complet") is False,
                 "reussies=%s complet=%s" % (garde.get("reussies"), garde.get("complet")))

        # 4. La distinction est PERSISTEE, pas seulement affichee.
        check("echouees, ignorees et concluante sont ecrits",
                 all(k in garde for k in ("echouees", "ignorees", "concluante")),
                 "champs presents : %s" % ", ".join(sorted(garde)))

        # 5. CONTRE-EPREUVE : l'ancienne regle, qui ecrasait sans condition, doit
        # etre VUE par cette epreuve. Sans elle, les cas d'avant ne prouvent rien.
        reg2 = {"modeles": {"x": {"reussies": 4, "complet": True, "concluante": True}}}
        entree_vaine = {"reussies": 0, "complet": False, "concluante": False}
        reg2["modeles"]["x"] = dict(entree_vaine)          # l'ancienne regle
        check("contre-epreuve : l'ancienne regle est bien VUE",
                 reg2["modeles"]["x"]["reussies"] == 0,
                 "sans garde, le 4/4 devient 0/4")
    finally:
        releve.PLATEFORME = ancien_root
        shutil.rmtree(bac, ignore_errors=True)


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
            ruche.decouvrir_cibles = lambda _racine: []
            sys.argv = ["nexus_ruche.py"]
            code = ruche.main()
            check("aucune cible decouverte => code de sortie en echec",
                  code == 1, "code %s" % code)

            # ALLER, niveau ruche entiere -- le meme garde-fou ne doit pas
            # se declencher a tort quand des cibles existent reellement.
            ruche.decouvrir_cibles = lambda _racine: [cible_a]
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
def test_vitrine() -> None:
    """
    Regression des deux defauts du 2026-08-30, garde par garde.

    Ils ont ete corriges le meme jour, et rien n'empechait leur retour : le
    correctif vivait dans le code, pas dans un controle. C'est precisement ce
    que la section 0.2.1 du contrat interdit de laisser passer.
    """
    import tempfile

    print("\n--- VITRINE : les garde-fous de publication ---")

    racine_vitrine = os.path.join(ROOT, "scripts", "nexus_vitrine.py")
    check("scripts/nexus_vitrine.py present", os.path.isfile(racine_vitrine),
          racine_vitrine)
    if not os.path.isfile(racine_vitrine):
        return

    # -- 1. Le detecteur de secrets detecte-t-il encore ?
    #
    # Zero declenchement sur le depot ne prouve rien : un motif casse rend le
    # meme silence. L'epreuve injecte quatre faux secrets et exige de les voir.
    r = subprocess.run([sys.executable, racine_vitrine, "--epreuve"],
                       capture_output=True, text=True, timeout=120,
                       encoding="utf-8", errors="replace")
    check("le detecteur de secrets detecte (4 cas + 1 texte anodin)",
          r.returncode == 0,
          (r.stdout.strip().splitlines() or ["aucune sortie"])[-1])

    # -- 2. Le verdict ment-il en simulation ?
    #
    # Le premier jet lisait le MODE avant le RESULTAT et annoncait
    # « SIMULATION » sur un blocage. Un depot sale, en simulation, doit
    # s'annoncer REFUSE.
    with tempfile.TemporaryDirectory() as rep:
        subprocess.run(["git", "init", "-q"], cwd=rep, timeout=60)
        with io.open(os.path.join(rep, "sale.txt"), "w", encoding="utf-8") as fh:
            fh.write("non commite\n")
        r = subprocess.run([sys.executable, racine_vitrine, "--simulation",
                            "--racine", rep, "--sauf-tests"],
                           capture_output=True, text=True, timeout=180,
                           encoding="utf-8", errors="replace")
        sortie = r.stdout or ""
        check("un blocage en simulation s'annonce REFUSEE, pas « passerait »",
              r.returncode == 1 and "REFUSEE" in sortie
              and "passerait" not in sortie,
              (sortie.strip().splitlines() or ["aucune sortie"])[-1])

    # -- 3. Une suite tuee peut-elle encore detruire la configuration ?
    #
    # run_validator_on echange la vraie configuration contre une cassee. Tue
    # apres l'echange, il laissait CONFIG = configuration de TEST et
    # .testswap = la vraie -- et la recuperation SUPPRIMAIT la vraie, lisant
    # « CONFIG present » comme « CONFIG sain ». Commit 72b13df en porte la
    # trace.
    swapped = CONFIG + ".testswap"
    if os.path.isfile(CONFIG) and not os.path.exists(swapped):
        with io.open(CONFIG, encoding="utf-8", errors="replace") as fh:
            vraie = fh.read()
        try:
            with io.open(swapped, "w", encoding="utf-8") as fh:
                fh.write(vraie)
            with io.open(CONFIG, "w", encoding="utf-8") as fh:
                fh.write("model_list:\n- model_name: cible-de-test\n")
            recover_swapped_config()
            with io.open(CONFIG, encoding="utf-8", errors="replace") as fh:
                revenue = fh.read()
            check("une suite tuee apres l'echange rend la VRAIE configuration",
                  "# >>> AUTOGEN:" in revenue and "cible-de-test" not in revenue,
                  "%d marqueur(s) AUTOGEN, %d trace(s) de test"
                  % (revenue.count("# >>> AUTOGEN:"),
                     revenue.count("cible-de-test")))
        finally:
            # Quoi qu'il arrive, la vraie configuration revient. Ce finally-ci
            # est en dernier ressort : le controle ci-dessus existe justement
            # parce qu'un finally ne suffit pas.
            with io.open(CONFIG, "w", encoding="utf-8") as fh:
                fh.write(vraie)
            if os.path.exists(swapped):
                os.remove(swapped)
    else:
        skip("recuperation de configuration",
             "configuration absente ou echange deja en cours")


def test_isolation() -> None:
    """
    Le contrat 0.4 devient un controle : un worker corrige une COPIE.

    L'essaim ecrivait sur la cible elle-meme et restaurait en cas d'echec.
    L'ordre a ete renverse -- copier, corriger la copie, promouvoir apres
    verification -- et sans ce test rien n'empecherait de le remettre a
    l'endroit d'avant. Un correctif qui vit dans le code seul ne protege
    personne : c'est la section 0.2.1 du contrat.

    La difference porte sur ce qui arrive quand rien ne va : un processus
    tue laissait l'original ECRASE, il le laisse desormais intact.
    """
    import inspect
    import tempfile
    from pathlib import Path

    print("\n--- ISOLATION : le worker corrige une copie, jamais la source ---")

    chemin = os.path.join(ROOT, "scripts")
    if chemin not in sys.path:
        sys.path.insert(0, chemin)
    try:
        import nexus_essaim
    except Exception as exc:
        check("nexus_essaim importable", False, str(exc).splitlines()[0][:60])
        return

    # -- 1. La copie est hors du depot, et elle est bien une copie.
    #
    # Hors du depot volontairement : ce qu'un modele ecrit la ne peut etre
    # commite par megarde ni ramasse par un outil qui parcourt l'arbre.
    with tempfile.TemporaryDirectory() as rep:
        source = os.path.join(rep, "exemple.py")
        with io.open(source, "w", encoding="utf-8") as fh:
            fh.write("ORIGINAL\n")
        try:
            copie = nexus_essaim.preparer_copie(Path(source), "abcd1234")
        except Exception as exc:
            check("preparer_copie fabrique une copie", False,
                  str(exc).splitlines()[0][:60])
            return
        dedans = os.path.abspath(str(copie)).startswith(
            os.path.abspath(ROOT) + os.sep)
        check("la copie de travail est HORS du depot", not dedans, str(copie))

        # Ecrire dans la copie ne doit rien changer a la source : c'est
        # toute la garantie, et elle se verifie plutot qu'elle ne se suppose.
        with io.open(str(copie), "w", encoding="utf-8") as fh:
            fh.write("REECRIT PAR UN MODELE\n")
        with io.open(source, encoding="utf-8") as fh:
            reste = fh.read()
        check("reecrire la copie laisse l'original intact",
              reste == "ORIGINAL\n", repr(reste[:40]))
        try:
            os.remove(str(copie))
        except OSError:
            pass

    # -- 2. Le cycle passe bien la COPIE aux outils qui ecrivent.
    #
    # Verifie sur le source de la fonction : si quelqu'un remet « cible » a
    # la place de « cible_travail », ce test tombe, et c'est precisement ce
    # qu'on lui demande.
    try:
        code = inspect.getsource(nexus_essaim.traiter_cible)
    except Exception as exc:
        check("traiter_cible lisible", False, str(exc).splitlines()[0][:60])
        return

    check("la correction porte sur la copie",
          "str(cible_travail)," in code and "str(cible)," not in code,
          "nexus_patch recoit cible_travail")
    check("la verification de syntaxe porte sur la copie",
          "verifier_syntaxe(cible_travail)" in code
          and "verifier_syntaxe(cible)" not in code,
          "verifier_syntaxe(cible_travail)")
    # Le court-circuit du « and » est ici une necessite, pas un style : sans
    # la garde de presence, code.index() leverait ValueError au lieu de rendre
    # un echec -- un test qui plante ne rapporte rien.
    ordre_bon = ("promotion_en_cours = True" in code
                 and "verifier_syntaxe(cible_travail)" in code
                 and code.index("verifier_syntaxe(cible_travail)")
                     < code.index("promotion_en_cours = True"))
    check("l'original n'est ecrit qu'apres verification", ordre_bon,
          "promotion posterieure a la verification")

    # -- 3. Le filet ne se declenche plus a tort.
    #
    # Le backup ne sert QUE la fenetre de promotion, seul instant ou
    # l'original peut etre a moitie ecrit. Restaurer ailleurs reecrirait
    # par-dessus un fichier sain -- une regression, pas une protection.
    check("le backup ne couvre plus que la promotion",
          "if promotion_en_cours and backup_path.exists():" in code,
          "finally borne a la fenetre de promotion")

    # -- 4. Le pont, lui, ne se protege pas par une copie mais par un
    # invariant : il ne modifie AUCUN fichier source. Lui faire copier les
    # fichiers avant lecture n'aurait protege de rien -- il ne les ouvre
    # jamais en ecriture -- et une protection decorative se lit comme une
    # garantie, ce qui est pire qu'aucune.
    try:
        import nexus_conformite
    except Exception as exc:
        skip("pont en lecture seule", str(exc).splitlines()[0][:60])
        return

    pont = os.path.join(ROOT, "tools", "nexus-mcp", "server.js")
    if not os.path.isfile(pont):
        skip("pont en lecture seule", "server.js introuvable")
        return
    with io.open(pont, encoding="utf-8", errors="replace") as fh:
        source_pont = fh.read()
    reelles = nexus_conformite.ecritures_hors_reserve(source_pont)
    check("le pont n'ecrit rien hors de .nexus", not reelles,
          "%d ecriture(s) : %s" % (len(reelles), reelles[:2]) if reelles
          else "les cinq ecritures visent observations et index")

    # Et l'epreuve du controle lui-meme : zero sur un pont sain ne prouve
    # rien, un motif casse rendrait le meme silence.
    injecte = source_pont + chr(10) +         'fs.writeFileSync(cheminSource, resultatDuModele, "utf8");' + chr(10)
    vues = nexus_conformite.ecritures_hors_reserve(injecte)
    check("le controle voit une ecriture illegitime injectee",
          len(vues) == len(reelles) + 1,
          "%d -> %d apres injection" % (len(reelles), len(vues)))


def test_garde_lecture() -> None:
    """
    Le garde « lire avant d'ecrire » refuse-t-il encore ?

    Ecrit par le banc gratuit (gpt-oss-120b-cloud) apres un premier jet
    REJETE : il avait invente le format d'entree -- « operation »/« target »
    au lieu de tool_name/tool_input.file_path -- si bien que le script
    n'aurait reconnu aucun outil, aurait tout autorise, et six cas sur sept
    auraient passe PAR ACCIDENT. Son « finally » faisait en outre un
    rmtree du repertoire de memoire, detruisant les sessions des autres.

    Deux corrections arbitrees sur le second jet :

    * le cas du session_id piege employait « Write », qui est REFUSE et
      n'ecrit donc aucune memoire : il ne testait rien. C'est « Read » qui
      declenche l'ecriture, donc c'est « Read » qu'il faut piquer ;
    * le nettoyage visait le chemin non evade, laissant derriere lui le
      fichier reellement cree.
    """
    import uuid

    print("\n--- LECTURE AVANT ECRITURE : le garde refuse-t-il ? ---")

    script = os.path.join(ROOT, "scripts", "nexus_garde_lecture.py")
    if not os.path.isfile(script):
        skip("garde de lecture", "nexus_garde_lecture.py introuvable")
        return
    readme = os.path.join(ROOT, "README.md")
    if not os.path.isfile(readme):
        skip("garde de lecture", "README.md absent")
        return

    memoires = os.path.join(ROOT, ".nexus", "lectures")
    crees = []

    def appeler(session, outil, chemin):
        crees.append(os.path.join(memoires, "%s.json" % session))
        charge = {"session_id": session, "tool_name": outil,
                  "tool_input": {"file_path": chemin}}
        return subprocess.run([sys.executable, script],
                              input=json.dumps(charge), capture_output=True,
                              text=True, encoding="utf-8", errors="replace",
                              timeout=60, cwd=ROOT)

    def brut(entree):
        return subprocess.run([sys.executable, script], input=entree,
                              capture_output=True, text=True,
                              encoding="utf-8", errors="replace",
                              timeout=60, cwd=ROOT)

    try:
        # 1. Le cas qui justifie tout le garde : ecrire sur ce qu'on n'a pas vu.
        s1 = "epreuve-%s" % uuid.uuid4().hex[:12]
        r = appeler(s1, "Write", readme)
        check("Write sur fichier existant jamais lu => refus",
              '"permissionDecision": "deny"' in (r.stdout or ""),
              (r.stdout or "").strip()[:70] or "aucune sortie")

        # 2. Et le cas symetrique : avoir lu doit suffire a passer. Un garde
        # qui refuse toujours serait desactive le jour meme.
        s2 = "epreuve-%s" % uuid.uuid4().hex[:12]
        appeler(s2, "Read", readme)
        r = appeler(s2, "Write", readme)
        check("Read puis Write sur le meme fichier => autorise",
              r.stdout == "", (r.stdout or "").strip()[:70] or "silence")

        # 3. Sous Windows, deux casses designent UN fichier. Les traiter comme
        # deux refuserait quelqu'un qui a pourtant lu.
        s3 = "epreuve-%s" % uuid.uuid4().hex[:12]
        appeler(s3, "Read", readme)
        autre = os.path.join(os.path.dirname(readme),
                             os.path.basename(readme).swapcase())
        r = appeler(s3, "Write", autre)
        check("casse differente du meme chemin => autorise",
              r.stdout == "", (r.stdout or "").strip()[:70] or "silence")

        # 4. Creer un fichier neuf n'ecrase rien : il n'y a rien a avoir lu.
        s4 = "epreuve-%s" % uuid.uuid4().hex[:12]
        r = appeler(s4, "Write", os.path.join(ROOT, "fichier_inexistant.txt"))
        check("Write sur fichier inexistant => autorise",
              r.stdout == "", (r.stdout or "").strip()[:70] or "silence")

        # 4 bis. Et il faut S'EN SOUVENIR. Mesure du 2026-08-30 : un script
        # d'extraction ecrit par la session, puis corrige dans le meme tour,
        # etait REFUSE au second passage -- au motif que la session en
        # ignorerait le contenu, alors qu'elle en etait l'auteur. Le garde
        # n'alimentait sa memoire que sur « Read ».
        #
        # L'enregistrement n'a lieu que sur un fichier INEXISTANT, et c'est
        # ce qui le rend sur : si l'ecriture echoue, le fichier reste absent,
        # donc la suivante est une creation, autorisee de toute facon.
        s4b = "epreuve-%s" % uuid.uuid4().hex[:12]
        neuf = os.path.join(ROOT, "epreuve_garde_%s.txt" % uuid.uuid4().hex[:8])
        appeler(s4b, "Write", neuf)          # creation : autorisee, et retenue
        with io.open(neuf, "w", encoding="utf-8") as fh:
            fh.write("ecrit par la session")
        try:
            r = appeler(s4b, "Write", neuf)  # le fichier existe maintenant
            check("Write sur un fichier que la session vient de creer => autorise",
                  r.stdout == "", (r.stdout or "").strip()[:70] or "silence")
        finally:
            try:
                os.remove(neuf)
            except OSError:
                pass

        # 4 ter. Le symetrique, qui prouve que la memoire n'est pas devenue
        # une passoire : une AUTRE session n'a rien ecrit, donc rien vu.
        s4c = "epreuve-%s" % uuid.uuid4().hex[:12]
        r = appeler(s4c, "Write", readme)
        check("autre session sur le meme fichier => refus maintenu",
              '"permissionDecision": "deny"' in (r.stdout or ""),
              (r.stdout or "").strip()[:70] or "aucune sortie")

        # 5 et 6. Une anomalie AUTORISE en silence : un garde qui plante
        # empeche de travailler, ce qui est pire que le defaut surveille.
        r = brut("{ ceci n'est pas du json")
        check("JSON invalide => silence et code 0",
              r.stdout == "" and r.returncode == 0,
              "rc=%s" % r.returncode)
        r = brut("")
        check("stdin vide => silence et code 0",
              r.stdout == "" and r.returncode == 0,
              "rc=%s" % r.returncode)

        # 7. Un identifiant de session sert de NOM DE FICHIER. Non filtre, il
        # ecrirait ou il veut. On emploie « Read » et non « Write » : seul
        # Read ecrit la memoire, donc seul Read peut sortir du repertoire.
        evade = os.path.normpath(os.path.join(memoires, "..", "..", "evade.json"))
        avant = os.path.isfile(evade)
        appeler("../../evade", "Read", readme)
        crees.append(os.path.join(memoires, "evade.json"))
        check("session_id piege => rien hors de .nexus/lectures",
              os.path.isfile(evade) == avant,
              "hors perimetre : %s" % evade)

    finally:
        # UNIQUEMENT ce que ce test a pu creer, fichier par fichier. Jamais un
        # repertoire : le premier jet supprimait .nexus/lectures en entier,
        # donc la memoire de toutes les autres sessions.
        for fichier in crees:
            try:
                if os.path.isfile(fichier):
                    os.remove(fichier)
            except OSError:
                pass


def test_garde_shell() -> None:
    """
    Le garde des heredocs refuse-t-il encore les deux pieges vecus ?

    Le 2026-08-30, dans une seule session, le shell a mutile QUATRE
    commandes -- dont un message de commit parti ampute de ses noms
    techniques. La regle etait ecrite et recente ; seul un controle protege.

    Les huit premiers cas comptent autant dans un sens que dans l'autre : un
    garde qui refuserait tous les heredocs serait desarme le jour de sa pose,
    et six des huit verifient donc qu'il AUTORISE.
    """
    print("\n--- GARDE SHELL : heredocs et accents graves ---")

    garde = os.path.join(ROOT, "scripts", "nexus_garde_shell.py")
    if not os.path.isfile(garde):
        skip("garde shell", "nexus_garde_shell.py introuvable")
        return

    barre = chr(92)
    grave = chr(96)

    def juger(commande, outil="Bash"):
        charge = json.dumps({"tool_name": outil,
                             "tool_input": {"command": commande}})
        r = subprocess.run([sys.executable, garde], input=charge,
                           capture_output=True, text=True, timeout=60,
                           encoding="utf-8", errors="replace")
        return ("deny" in (r.stdout or "")), r.returncode

    cas = [
        ("heredoc python avec antislash => REFUS",
         "python - <<'PYEOF'" + chr(10) + "rx = r'[^" + barre + "s]+'"
         + chr(10) + "PYEOF", True, "Bash"),
        ("accent grave entre guillemets doubles => REFUS",
         'git commit -m "voir ' + grave + 'py_compile' + grave + '"',
         True, "Bash"),
        ("heredoc python sans antislash => autorise",
         "python - <<'PYEOF'" + chr(10) + "print('ok')" + chr(10) + "PYEOF",
         False, "Bash"),
        ("accent grave entre guillemets simples => autorise",
         "echo 'ni " + grave + "ceci" + grave + " ni cela'", False, "Bash"),
        ("accent grave echappe => autorise",
         'echo "protege ' + barre + grave + 'ainsi' + barre + grave + '"',
         False, "Bash"),
        ("commande ordinaire => autorise", "git status", False, "Bash"),
        ("heredoc bash sans python => autorise",
         "cat <<EOF" + chr(10) + "avec " + barre + " antislash" + chr(10)
         + "EOF", False, "Bash"),
        ("outil autre que Bash => autorise",
         "peu importe " + grave + "ceci" + grave, False, "Read"),
    ]
    for nom, commande, attendu, outil in cas:
        refuse, code = juger(commande, outil)
        check(nom, refuse == attendu and code == 0,
              "%s, rc=%s" % ("refuse" if refuse else "autorise", code))

    # Une anomalie AUTORISE en silence : un garde qui plante empeche de
    # travailler, ce qui est pire que le defaut qu'il surveille.
    for nom, entree in (("JSON invalide => silence", "{pas du json"),
                        ("stdin vide => silence", "")):
        r = subprocess.run([sys.executable, garde], input=entree,
                           capture_output=True, text=True, timeout=60,
                           encoding="utf-8", errors="replace")
        check(nom, r.stdout == "" and r.returncode == 0,
              "rc=%s" % r.returncode)


if __name__ == "__main__":
    sys.exit(main())
