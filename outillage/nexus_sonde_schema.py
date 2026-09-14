"""
outillage.nexus_sonde_schema
----------------------------

This module measures whether a JSON schema is *imposed* by the three
different Ollama access paths (local, cloud and Litellm gateway).  It
does **not** try to validate the content of the model's prose, the
correctness of the HTTP status codes beyond "2xx = ok", nor does it
perform any network-level security checks.  Only the following is
checked:

* the request can be sent (network reachable, timeout, HTTP status)
* the response body is a JSON object that satisfies the supplied
  ``schema`` (required keys, basic type checking, ``enum`` values)
* the response is **not** required to contain the schema when the model
  is asked to produce plain prose - in that case the verdict will be
  ``NON IMPOSE``.

All helpers are pure, use only the Python standard library and never
expose secret values (environment variables) in logs or exceptions.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from typing import Any

# ----------------------------------------------------------------------
# Pure helpers
# ----------------------------------------------------------------------


def parse_env(text: str) -> dict[str, str]:
    """
    Parse a ``.env``-style string.

    * lines are ``KEY=VALUE``
    * optional leading ``export``
    * comments start with ``#``
    * surrounding single or double quotes are stripped
    * empty lines are ignored
    """
    result: dict[str, str] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.lower().startswith("export "):
            line = line[7:].lstrip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        # Commentaire de fin de ligne retire quand la valeur n'est pas entre guillemets
        if " #" in value and not ((value.startswith("'") and value.endswith("'")) or (value.startswith('"') and value.endswith('"'))):
            value = value.split(" #", 1)[0].rstrip()
        if (value.startswith("'") and value.endswith("'")) or (
            value.startswith('"') and value.endswith('"')
        ):
            value = value[1:-1]
        result[key] = value
    return result


def _type_matches(value: Any, expected: str) -> bool:
    """Return True if *value* matches the JSON schema type *expected*."""
    if expected == "string":
        return isinstance(value, str)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    return False


def verdict_conformite(texte: str, schema: dict[str, Any]) -> str:
    """
    Return ``'IMPOSE'`` if *texte* is a JSON object that respects *schema*,
    otherwise ``'NON IMPOSE'``.
    """
    try:
        data = json.loads(texte)
    except Exception:
        return "NON IMPOSE"

    if not isinstance(data, dict):
        return "NON IMPOSE"

    required = schema.get("required", [])
    properties = schema.get("properties", {})

    # required keys
    for key in required:
        if key not in data:
            return "NON IMPOSE"

    # each property
    for key, prop in properties.items():
        if key not in data:
            continue  # not required
        expected_type = prop.get("type")
        if expected_type and not _type_matches(data[key], expected_type):
            return "NON IMPOSE"
        if "enum" in prop and data[key] not in prop["enum"]:
            return "NON IMPOSE"

    return "IMPOSE"


# ----------------------------------------------------------------------
# HTTP helpers
# ----------------------------------------------------------------------


def _load_env() -> dict[str, str]:
    """Load .env from repository root (parent of this file's directory)."""
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    env_path = os.path.join(repo_root, ".env")
    if not os.path.isfile(env_path):
        return {}
    with open(env_path, "r", encoding="utf-8") as f:
        return parse_env(f.read())


def _get_secret(key: str, env: dict[str, str]) -> tuple[bool, str]:
    """Return (found, value) without ever printing the value."""
    if key in os.environ:
        return True, os.environ[key]
    if key in env:
        return True, env[key]
    return False, ""


def _post_json(url: str, payload: dict[str, Any], headers: dict[str, str], timeout: int) -> tuple[int, str]:
    """POST *payload* as JSON, return (status_code, response_text)."""
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status = resp.getcode()
            text = resp.read().decode("utf-8")
            return status, text
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", errors="ignore")
    except urllib.error.URLError as e:
        raise ConnectionError(str(e)) from e


# ----------------------------------------------------------------------
# Core measurement
# ----------------------------------------------------------------------


def extraire_contenu(corps_texte: str, chemin: str) -> str:
    """
    Extrait le contenu du message rendu par le modele, hors enveloppe HTTP :
    message.content pour Ollama (local, cloud), choices[0].message.content pour
    la passerelle. Rend '' sur JSON invalide ou cle absente, jamais d'exception.
    Mesure du 2026-09-14 : juger l'enveloppe rendait 'NON IMPOSE' quoi qu'il arrive.
    """
    try:
        corps = json.loads(corps_texte)
    except Exception:
        return ""
    if not isinstance(corps, dict):
        return ""
    if chemin in ("local", "cloud"):
        message = corps.get("message") or {}
        return message.get("content", "") if isinstance(message, dict) else ""
    if chemin == "passerelle":
        choix = corps.get("choices") or [{}]
        message = (choix[0] if choix and isinstance(choix[0], dict) else {}).get("message") or {}
        return message.get("content", "") if isinstance(message, dict) else ""
    return ""


def _measure_path(
    name: str,
    url: str,
    body: dict[str, Any],
    headers: dict[str, str],
    timeout: int,
    schema: dict[str, Any],
) -> tuple[str, float, str]:
    """
    Send the request, measure duration, and return a tuple:
    (verdict, duration_seconds, excerpt_of_response)
    """
    start = time.time()
    try:
        status, text = _post_json(url, body, headers, timeout)
    except Exception as exc:
        cause = str(exc)
        if isinstance(exc, ConnectionError):
            cause = "connection error"
        return f"INJOIGNABLE ({cause})", time.time() - start, ""
    duration = time.time() - start

    if not (200 <= status < 300):
        # Le corps de l'erreur est le diagnostic : 120 caracteres, sans sauts de ligne.
        excerpt = text.replace("\n", " ").replace("\r", " ")[:120]
        return f"INJOIGNABLE (HTTP {status})", duration, excerpt

    # Seul le contenu du message est juge, jamais l'enveloppe.
    contenu = extraire_contenu(text, name)
    verdict = "REPONSE VIDE" if not contenu else verdict_conformite(contenu, schema)
    excerpt = contenu.replace("\n", " ").replace("\r", " ")[:60]
    return verdict, duration, excerpt


def build_local_body(schema: dict[str, Any], modele: str) -> dict[str, Any]:
    """Body for the direct Ollama local endpoint."""
    return {
        "model": modele,
        "messages": [
            {
                "role": "user",
                "content": "Ecris deux phrases de prose en francais sur la pluie, sans aucun JSON."
            }
        ],
        "stream": False,
        "options": {
            "temperature": 0,
            "num_predict": 150
        },
        "format": schema  # Ollama expects the raw schema object here
    }


def build_cloud_body(schema: dict[str, Any], modele: str) -> dict[str, Any]:
    """Body for the Ollama cloud endpoint - identical to the local one."""
    return build_local_body(schema, modele)


def build_gateway_body(schema: dict[str, Any], alias: str) -> dict[str, Any]:
    """Body for the Litellm gateway (the transformation code expects this shape)."""
    return {
        "model": alias,
        "messages": [
            {
                "role": "user",
                "content": "Ecris deux phrases de prose en francais sur la pluie, sans aucun JSON."
            }
        ],
        "temperature": 0,
        "max_tokens": 150,
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "sonde",
                "schema": schema,
                "strict": True
            }
        }
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Measure JSON schema enforcement.")
    parser.add_argument(
        "--modele-local",
        default=os.getenv("NEXUS_CANARI_MODELE") or "phi:latest",
        help="Modèle local utilisé par défaut : la variable d’environnement NEXUS_CANARI_MODELE si définie, sinon « phi:latest ».",
    )
    parser.add_argument("--modele-cloud", default="gpt-oss:120b")
    parser.add_argument("--alias-passerelle", default="gpt-oss-120b-cloud")
    parser.add_argument(
        "--chemins",
        default="local,cloud,passerelle",
        help="Comma-separated list among: local,cloud,passerelle",
    )
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--json", action="store_true", help="Output results as JSON list")
    args = parser.parse_args(argv)

    # Load secrets
    env = _load_env()
    # Le moteur local n'exige aucune cle.
    ok, key_cloud = _get_secret("OLLAMA_CLOUD_API_KEY", env)
    _ok, key_gateway = _get_secret("LITELLM_MASTER_KEY", env)

    # Prepare schema
    schema = {
        "type": "object",
        "properties": {
            "verdict": {"type": "string", "enum": ["OK", "REFUS"]},
            "score": {"type": "integer"},
        },
        "required": ["verdict", "score"],
    }

    # Determine which paths to test
    requested = {c.strip().lower() for c in args.chemins.split(",")}
    allowed = {"local", "cloud", "passerelle"}
    paths = [p for p in ["local", "cloud", "passerelle"] if p in requested and p in allowed]

    exit_code = 0
    rows: list[str] = []

    for path in paths:
        if path == "local":
            url = "http://127.0.0.1:11434/api/chat"
            body = build_local_body(schema, args.modele_local)
            headers = {"Content-Type": "application/json"}
        elif path == "cloud":
            if not key_cloud:
                rows.append(f"cloud | {args.modele_cloud} | CLE ABSENTE (OLLAMA_CLOUD_API_KEY) | 0 | ")
                exit_code = 3
                continue
            url = "https://ollama.com/api/chat"
            body = build_cloud_body(schema, args.modele_cloud)
            headers = {
                "Authorization": f"Bearer {key_cloud}",
                "Content-Type": "application/json",
            }
        else:  # passerelle
            if not key_gateway:
                rows.append(f"passerelle | {args.alias_passerelle} | CLE ABSENTE (LITELLM_MASTER_KEY) | 0 | ")
                exit_code = 3
                continue
            url = "http://localhost:4000/v1/chat/completions"
            body = build_gateway_body(schema, args.alias_passerelle)
            headers = {"Authorization": f"Bearer {key_gateway}", "Content-Type": "application/json"}

        verdict, duration, excerpt = _measure_path(
            path, url, body, headers, args.timeout, schema
        )
        model_name = {
            "local": args.modele_local,
            "cloud": args.modele_cloud,
            "passerelle": args.alias_passerelle,
        }[path]
        rows.append(f"{path} | {model_name} | {verdict} | {duration:.2f} | {excerpt}")

        if verdict.startswith(("INJOIGNABLE", "CLE ABSENTE", "REPONSE VIDE")):
            exit_code = 3

    # Output
    if args.json:
        json_rows = []
        for line in rows:
            parts = [p.strip() for p in line.split("|")]
            if len(parts) >= 5:
                json_rows.append({
                    "chemin": parts[0],
                    "modele": parts[1],
                    "verdict": parts[2],
                    "duree_s": float(parts[3]) if parts[3] else 0,
                    "extrait": parts[4],
                })
        print(json.dumps(json_rows, ensure_ascii=False))
    else:
        for line in rows:
            print(line)

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
