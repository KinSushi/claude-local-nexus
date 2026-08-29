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

# --------------------------------------------------------------------------- #
# Constantes de configuration
# --------------------------------------------------------------------------- #
TIMEOUT_RUN = 60          # Timeout pour les appels subprocess
TIMEOUT_URL = 20          # Timeout pour la requête HTTP vers la passerelle
ROUTER_CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "litellm_config.yaml",
)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nexus_capability as capability  # noqa: E402

# La sortie est souvent redirigée : journaux, STATE.md, sous‑processus.
# Sans cette ligne, Python écrit dans la page de codes locale de Windows
# et les accents se dégradent dès que la sortie est capturée – le résultat
# finissait commité dans rituels/STATE.md, donc visible sur GitHub.
# PYTHONUTF8 est déjà posé pour LiteLLM dans le compose ; il manquait ici.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE = os.path.join(ROOT, "rituels", "STATE.md")

# Fichiers qui commandent le comportement : leur empreinte permet de dire
# si l'état décrit ici correspond encore à la plateforme installée.
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


def run(args, timeout=TIMEOUT_RUN):
    """
    Exécute une commande externe et renvoie sa sortie standard.

    Retourne ``None`` si l'exécution échoue (ex. commande introuvable,
    timeout, permission). Cela évite d'interpréter une erreur comme une
    sortie vide, ce qui aurait pu masquer un problème d'infrastructure et
    conduire à un rapport indiquant à tort que l'arbre de travail était
    propre.
    """
    try:
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace",
        )
        return result.stdout.strip()
    except Exception:
        return None


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
    # `os.path.exists` puis `open` laisse un intervalle : le fichier peut
    # disparaître entre les deux, et un .env illisible par permission
    # passe le premier test pour échouer au second. Ce script produit un
    # état ; il ne doit pas mourir parce qu'un secret est inaccessible —
    # tout le reste de l'état, lui, reste parfaitement calculable.
    try:
        with io.open(env_file, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                if line.startswith("LITELLM_MASTER_KEY="):
                    return line.split("=", 1)[1].strip()
    except OSError:
        return ""
    return ""


def exposed_models():
    """
    Alias exposés, ou **None** si la passerelle n'a pas répondu.

    La distinction n'est pas théorique : ce script a écrit « 0 modèles
    exposés » dans STATE.md alors que la passerelle était simplement
    éteinte. L'état commis affirmait donc une panne catastrophique — plus
    aucun modèle — là où rien n'était cassé. Un état qui ment est pire
    qu'un état absent, parce qu'il fait chercher une cause qui n'existe
    pas.
    """
    try:
        request = urllib.request.Request("http://127.0.0.1:4000/v1/models")
        request.add_header("Authorization", "Bearer " + master_key())
        with urllib.request.urlopen(request, timeout=TIMEOUT_URL) as response:
            data = json.loads(response.read().decode("utf-8"))
        return sorted(d["id"] for d in data.get("data", []))
    except Exception:
        return None


def main() -> int:
    # Horodatage avec fuseau horaire afin d'éviter toute ambiguïté.
    now = datetime.datetime.now(datetime.timezone.utc).astimezone().strftime(
        "%Y-%m-%d %H:%M %Z"
    )
    profile = capability.build_profile()
    models = exposed_models()
    passerelle_muette = models is None

    groups = {"local": [], "cloud": [], "anthropic": [], "routeurs": []}
    for alias in (models or []):
        if alias.startswith("adaptive-router"):
            groups["routeurs"].append(alias)
        elif alias.endswith("-local") or alias == "releve-locale":
            groups["local"].append(alias)
        elif alias.endswith("-cloud"):
            groups["cloud"].append(alias)
        else:
            groups["anthropic"].append(alias)

    services = run(
        ["docker", "compose", "ps", "--format", "{{.Name}}\t{{.Service}}\t{{.Status}}"]
    )

    # Protection symétrique : on capture les erreurs de l'appel direct à
    # nexus_validate.py afin que l'absence du script ne fasse pas planter
    # tout le processus et que la cause soit clairement indiquée.
    try:
        validation = subprocess.run(
            [sys.executable, os.path.join(ROOT, "scripts", "nexus_validate.py")],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except Exception as exc:  # pragma: no cover
        print(
            f"Erreur lors de l'execution de nexus_validate.py : {exc}",
            file=sys.stderr,
        )
        # Simuler un échec de validation
        class DummyResult:
            returncode = 1
            stdout = ""
            stderr = str(exc)

        validation = DummyResult()

    verdict = "valide" if validation.returncode == 0 else "INVALIDE"
    issues = [
        l.strip()
        for l in validation.stdout.splitlines()
        if l.strip().startswith("- ")
    ]

    # Version de la politique de routage : elle rattache un résultat aux
    # règles qui l'ont produit.
    router_version = "?"
    try:
        with io.open(ROUTER_CONFIG_PATH, encoding="utf-8") as fh:
            for line in fh:
                if line.startswith("# NEXUS-ROUTER-VERSION:"):
                    router_version = line.split(":", 1)[1].strip()
                    break
    except Exception:
        # Absence ou lecture impossible du fichier de configuration.
        router_version = "?"

    commit = run(["git", "rev-parse", "--short", "HEAD"])
    branch = run(["git", "rev-parse", "--abbrev-ref", "HEAD"])
    dirty = run(["git", "status", "--porcelain"])

    # Distinction entre arbre propre, modifié et échec de la commande git.
    if dirty is None:
        worktree_status = "inconnu"
    elif dirty == "":
        worktree_status = "propre"
    else:
        worktree_status = "modifie"

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
        "| Arbre de travail | %s |" % worktree_status,
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
        ("## Inventaire exposé — PASSERELLE INJOIGNABLE"
         if passerelle_muette else
         "## Inventaire exposé — %d modèles" % len(models)),
        "",
        # Un zéro et une absence de mesure se ressemblent dans un tableau,
        # et ne veulent pas du tout dire la même chose : le premier annonce
        # une panne totale, le second qu'on n'a rien demandé à personne.
        ("> La passerelle n'a pas répondu sur `127.0.0.1:4000`. Ce qui suit "
         "n'est donc **pas** un inventaire vide : c'est une absence de "
         "mesure. Relancer `.\\scripts\\start.ps1` avant d'en conclure quoi "
         "que ce soit."
         if passerelle_muette else ""),
        "",
        "| Plan | Nombre | Facturation |",
        "|---|---|---|",
        "| Local | %d | aucune, rien ne quitte la machine |" % len(groups["local"]),
        "| Ollama Cloud | %d | abonnement Ollama |" % len(groups["cloud"]),
        "| Anthropic | %d | crédits API, distincts de l'abonnement claude.ai |"
        % len(groups["anthropic"]),
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

    # S'assurer que le répertoire cible existe avant d'écrire le fichier temporaire.
    os.makedirs(os.path.dirname(STATE), exist_ok=True)

    # Écriture atomique : on écrit d'abord dans un fichier temporaire puis on
    # le replace atomiquement. Ainsi, une interruption ne laisse pas un
    # STATE.md partiellement écrit qui pourrait être lu comme valide.
    temp_path = STATE + ".tmp"
    with io.open(temp_path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(lines) + "\n")
    os.replace(temp_path, STATE)

    if passerelle_muette:
        print(
            "STATE.md regenere : PASSERELLE INJOIGNABLE (127.0.0.1:4000), "
            "configuration %s" % verdict
        )
    else:
        print(
            "STATE.md regenere : %d modeles exposes, configuration %s"
            % (len(models), verdict)
        )
    # Propagation du code de retour de la validation : si la validation a
    # échoué, on renvoie un code d'erreur afin que l'orchestrateur puisse
    # prendre la bonne décision.
    return 0 if validation.returncode == 0 else validation.returncode


if __name__ == "__main__":
    sys.exit(main())
