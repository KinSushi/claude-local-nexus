# -*- coding: utf-8 -*-
"""
Génère rituels/STATE.md à partir de l'état réellement mesuré.

Un fichier d'état saisi à la main vieillit mal : il décrit ce qu'on croyait
au moment de l'écrire. Celui-ci est produit par mesure — services, moteur
d'inférence, inventaire exposé, budget matériel, empreintes SHA-256 des
fichiers qui commandent le comportement de la plateforme.

Il est donc reproductible, auditable et localisable, conformément au
contrat des rituels.

Usage :
    python scripts/nexus_state.py
"""
from __future__ import annotations

import datetime
import hashlib
import io
import json
import os
import subprocess
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nexus_capability as capability  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE = os.path.join(ROOT, "rituels", "STATE.md")

# Fichiers qui commandent le comportement : leur empreinte permet de dire
# si l'etat decrit ici correspond encore a la plateforme installee.
TRACKED = [
    "docker-compose.yml",
    "litellm_config.yaml",
    "model_list.txt",
    "cloud_models.txt",
    ".mcp.json",
    "Set-ClaudeModel.ps1",
    "tools/nexus-mcp/server.js",
    "scripts/nexus_generate.py",
    "scripts/nexus_validate.py",
    "scripts/nexus_capability.py",
    "scripts/nexus_test.py",
    "scripts/Update-NexusModels.ps1",
]


def run(args, timeout=60):
    try:
        result = subprocess.run(args, capture_output=True, text=True,
                                timeout=timeout, encoding="utf-8",
                                errors="replace")
        return result.stdout.strip()
    except Exception:
        return ""


def sha256(path):
    try:
        digest = hashlib.sha256()
        with open(path, "rb") as fh:
            for block in iter(lambda: fh.read(65536), b""):
                digest.update(block)
        return digest.hexdigest()
    except Exception:
        return None


def master_key():
    if os.environ.get("LITELLM_MASTER_KEY"):
        return os.environ["LITELLM_MASTER_KEY"]
    env_file = os.path.join(ROOT, ".env")
    if not os.path.exists(env_file):
        return ""
    with io.open(env_file, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if line.startswith("LITELLM_MASTER_KEY="):
                return line.split("=", 1)[1].strip()
    return ""


def exposed_models():
    try:
        request = urllib.request.Request("http://127.0.0.1:4000/v1/models")
        request.add_header("Authorization", "Bearer " + master_key())
        with urllib.request.urlopen(request, timeout=20) as response:
            data = json.loads(response.read().decode("utf-8"))
        return sorted(d["id"] for d in data.get("data", []))
    except Exception:
        return []


def main() -> int:
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    profile = capability.build_profile()
    models = exposed_models()

    groups = {"local": [], "cloud": [], "anthropic": [], "routeurs": []}
    for alias in models:
        if alias.startswith("adaptive-router"):
            groups["routeurs"].append(alias)
        elif alias.endswith("-local") or alias == "releve-locale":
            groups["local"].append(alias)
        elif alias.endswith("-cloud"):
            groups["cloud"].append(alias)
        else:
            groups["anthropic"].append(alias)

    services = run(["docker", "compose", "ps", "--format",
                    "{{.Name}}\t{{.Service}}\t{{.Status}}"])

    validation = subprocess.run(
        [sys.executable, os.path.join(ROOT, "scripts", "nexus_validate.py")],
        capture_output=True, text=True, encoding="utf-8", errors="replace")
    verdict = "valide" if validation.returncode == 0 else "INVALIDE"
    issues = [l.strip() for l in validation.stdout.splitlines()
              if l.strip().startswith("- ")]

    # Version de la politique de routage : elle rattache un resultat aux
    # regles qui l'ont produit.
    router_version = "?"
    with io.open(os.path.join(ROOT, "litellm_config.yaml"), encoding="utf-8") as fh:
        for line in fh:
            if line.startswith("# NEXUS-ROUTER-VERSION:"):
                router_version = line.split(":", 1)[1].strip()
                break

    commit = run(["git", "rev-parse", "--short", "HEAD"])
    branch = run(["git", "rev-parse", "--abbrev-ref", "HEAD"])
    dirty = run(["git", "status", "--porcelain"])

    lines = [
        "# État de la plateforme",
        "",
        "> Généré par `python scripts/nexus_state.py` le %s." % now,
        "> **Ne pas éditer à la main** : ce fichier décrit ce qui a été mesuré,",
        "> pas ce que l'on croit installé. Le régénérer vaut mieux que le corriger.",
        "",
        "## Dépôt",
        "",
        "| | |",
        "|---|---|",
        "| Branche | `%s` |" % (branch or "?"),
        "| Commit | `%s` |" % (commit or "?"),
        "| Arbre de travail | %s |" % ("modifié" if dirty else "propre"),
        "| Version de routage | `%s` |" % router_version,
        "",
        "## Services",
        "",
        "```",
        services or "(docker compose injoignable)",
        "```",
        "",
        "## Moteur d'inférence",
        "",
        "| | |",
        "|---|---|",
        "| Implantation | `%s` |" % profile["ollama"]["mode"],
        "| Mémoire d'inférence | %.1f Go |" % profile["inference_memory_gb"],
        "| RAM machine | %.1f Go |" % profile["host_ram_gb"],
        "| Budget pool | %.1f Go |" % profile["pool_budget_gb"],
        "| Budget maximal | %.1f Go |" % profile["runnable_budget_gb"],
        "| CPU | %d cœurs / %d threads |" % (profile["cpu_cores"], profile["cpu_threads"]),
        "| GPU | %s (%.1f Go) |" % (profile["gpu"]["name"] or "?", profile["gpu"]["vram_gb"]),
        "| Offload GPU | %s |" % ("oui" if profile["gpu_usable_for_offload"] else "non"),
        "| Stockage modèles | `%s` |" % profile["model_store"],
        "| Disque libre | %.1f Go |" % profile["free_disk_gb"],
        "",
    ]

    if profile["ollama"]["mode"].startswith("docker"):
        perdu = profile["host_ram_gb"] - profile["inference_memory_gb"]
        if perdu > 4:
            lines += [
                "> %.0f Go des %.0f Go de la machine restent hors d'atteinte de"
                % (perdu, profile["host_ram_gb"]),
                "> l'inférence tant que le moteur tourne dans Docker.",
                "",
            ]

    lines += [
        "## Inventaire exposé — %d modèles" % len(models),
        "",
        "| Plan | Nombre | Facturation |",
        "|---|---|---|",
        "| Local | %d | aucune, rien ne quitte la machine |" % len(groups["local"]),
        "| Ollama Cloud | %d | abonnement Ollama |" % len(groups["cloud"]),
        "| Anthropic | %d | crédits API, distincts de l'abonnement claude.ai |" % len(groups["anthropic"]),
        "| Routeurs | %d | selon le plan retenu |" % len(groups["routeurs"]),
        "",
        "## Intégrité de la configuration",
        "",
        "Verdict : **%s**" % verdict,
        "",
    ]
    if issues:
        lines += ["```"] + issues + ["```", ""]

    lines += [
        "## Empreintes SHA-256",
        "",
        "| Fichier | Empreinte |",
        "|---|---|",
    ]
    for relative in TRACKED:
        path = os.path.join(ROOT, relative)
        digest = sha256(path)
        lines.append("| `%s` | `%s` |" % (relative, digest[:32] if digest else "absent"))

    lines += [
        "",
        "---",
        "",
        "Sujets ouverts : voir [CHECKLIST_COCKPIT.MD](CHECKLIST_COCKPIT.MD).",
        "Historique : voir [PROGRESS.md](PROGRESS.md).",
    ]

    with io.open(STATE, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(lines) + "\n")
    print("STATE.md regenere : %d modeles exposes, configuration %s"
          % (len(models), verdict))
    return 0


if __name__ == "__main__":
    sys.exit(main())
