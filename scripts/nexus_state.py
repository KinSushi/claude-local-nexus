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
import re
import subprocess
import sys
import urllib.error
import urllib.request

# --------------------------------------------------------------------------- #
# Constantes de configuration
# --------------------------------------------------------------------------- #
TIMEOUT_RUN = 60          # Timeout pour les appels subprocess
TIMEOUT_URL = 20          # Timeout pour la requête HTTP vers la passerelle
ROUTER_HOST = "127.0.0.1"
ROUTER_PORT = 4000
ROUTER_ENDPOINT = f"http://{ROUTER_HOST}:{ROUTER_PORT}/v1/models"
ROUTER_CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "litellm_config.yaml",
)

# --------------------------------------------------------------------------- #
# Import du module de capacité sans polluer sys.path
# --------------------------------------------------------------------------- #
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)
try:
    import nexus_capability as capability  # noqa: E402
except ImportError as exc:  # pragma: no cover
    print(f"Erreur d'import du module nexus_capability : {exc}", file=sys.stderr)
    sys.exit(1)
finally:
    # Restaure sys.path pour éviter les effets de bord à l'import.
    if sys.path[0] == _SCRIPT_DIR:
        sys.path.pop(0)

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


def _safe_float(value, default=0.0):
    """Convertit en float en toute sécurité, retourne *default* en cas d'échec."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value, default=0):
    """Convertit en int en toute sécurité, retourne *default* en cas d'échec."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def run(args, timeout=TIMEOUT_RUN):
    """
    Exécute une commande externe et renvoie sa sortie standard.

    Retourne ``None`` si l'exécution échoue (ex. commande introuvable,
    timeout, permission). Le flux d'erreur standard est consigné sur
    ``stderr`` afin de ne pas perdre d'information de diagnostic.
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
        if result.stderr:
            print(result.stderr, file=sys.stderr)
        # UN ECHEC N'EST PAS UNE SORTIE VIDE.
        #
        # `stdout` etait rendu sans jamais regarder le code de retour. Un
        # `git status` lance hors d'un depot rend 128 et une sortie VIDE :
        # indiscernable, pour l'appelant, d'un arbre de travail propre. Le
        # tableau de bord affichait alors « propre » la ou il aurait fallu
        # « inconnu » -- une panne presentee comme un etat sain.
        #
        # `None` est deja le signal d'echec de cette fonction, rendu par la
        # branche d'exception ci-dessous : les appelants le traitent donc
        # deja. On ne cree pas un second vocabulaire.
        if result.returncode != 0:
            return None
        return result.stdout.strip()
    except (subprocess.SubprocessError, OSError, subprocess.TimeoutExpired) as exc:
        # FileNotFoundError est déjà une sous‑classe d'OSError.
        print(f"run error: {exc}", file=sys.stderr)
        return None


def sha256(path):
    """
    Retourne le hachage SHA‑256 du fichier indiqué ou ``None`` en cas
    d'erreur d'accès.
    """
    try:
        digest = hashlib.sha256()
        with open(path, "rb") as fh:
            for block in iter(lambda: fh.read(65536), b""):
                digest.update(block)
        return digest.hexdigest()
    except OSError as exc:
        print(f"sha256 error on {path}: {exc}", file=sys.stderr)
        return None


def master_key():
    """
    Retourne la clé maître LITELLM. Elle peut être fournie via la variable
    d'environnement ``LITELLM_MASTER_KEY`` ou, à défaut, dans le fichier
    ``.env`` à la racine du dépôt.

    Le parsing accepte les formes suivantes :
        LITELLM_MASTER_KEY=abc
        export LITELLM_MASTER_KEY="abc"
        # commentaire
    Les guillemets éventuels sont retirés et les commentaires en ligne sont
    ignorés.
    """
    if os.environ.get("LITELLM_MASTER_KEY"):
        return os.environ["LITELLM_MASTER_KEY"]

    env_file = os.path.join(ROOT, ".env")
    pattern = re.compile(r"""^\s*(?:export\s+)?LITELLM_MASTER_KEY\s*=\s*(?P<val>.+?)\s*$""")
    try:
        with io.open(env_file, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                # Retirer les commentaires
                line = line.split("#", 1)[0]
                if not line.strip():
                    continue
                m = pattern.match(line)
                if m:
                    value = m.group("val").strip()
                    # Enlever les guillemets éventuels
                    if (value.startswith('"') and value.endswith('"')) or (
                        value.startswith("'") and value.endswith("'")
                    ):
                        value = value[1:-1]
                    return value
    except OSError as exc:
        print(f"master_key error: {exc}", file=sys.stderr)
    return ""


def exposed_models():
    """
    Alias exposés, ou **None** si la passerelle n'a pas répondu.

    La distinction n'est pas théorique : ce script a écrit « 0 modèles
    exposés » dans STATE.md alors que la passerelle était simplement
    éteinte. L'état commis affirmait donc une panne catastrophique — plus
    aucun modèle — là où rien n'était cassé. Un état qui ment est pire
    qu'un état absent, parce qu'il fait chercher une cause qui n'existe pas.
    """
    try:
        request = urllib.request.Request(ROUTER_ENDPOINT)
        request.add_header("Authorization", "Bearer " + master_key())
        with urllib.request.urlopen(request, timeout=TIMEOUT_URL) as response:
            raw = response.read().decode("utf-8")
            data = json.loads(raw)
        if not isinstance(data, dict):
            raise ValueError("Réponse JSON inattendue")
        models = []
        for item in data.get("data", []):
            if isinstance(item, dict) and "id" in item:
                models.append(item["id"])
        return sorted(models)
    except (urllib.error.URLError, json.JSONDecodeError, OSError, ValueError) as exc:
        print(f"exposed_models error: {exc}", file=sys.stderr)
        return None


def main() -> int:
    # Horodatage avec fuseau horaire afin d'éviter toute ambiguïté.
    now = datetime.datetime.now(datetime.timezone.utc).astimezone().strftime(
        "%Y-%m-%d %H:%M %Z"
    )
    # Construction du profil avec validation de présence de clés.
    raw_profile = capability.build_profile()
    profile = {
        "ollama": {
            "mode": raw_profile.get("ollama", {}).get("mode", "?")
        },
        "inference_memory_gb": _safe_float(raw_profile.get("inference_memory_gb", 0)),
        "host_ram_gb": _safe_float(raw_profile.get("host_ram_gb", 0)),
        "pool_budget_gb": _safe_float(raw_profile.get("pool_budget_gb", 0)),
        "runnable_budget_gb": _safe_float(raw_profile.get("runnable_budget_gb", 0)),
        "cpu_cores": _safe_int(raw_profile.get("cpu_cores", 0)),
        "cpu_threads": _safe_int(raw_profile.get("cpu_threads", 0)),
        "gpu": {
            "name": raw_profile.get("gpu", {}).get("name", "?"),
            "vram_gb": _safe_float(raw_profile.get("gpu", {}).get("vram_gb", 0)),
        },
        "gpu_usable_for_offload": bool(
            raw_profile.get("gpu_usable_for_offload", False)
        ),
        "model_store": raw_profile.get("model_store", "?"),
        "free_disk_gb": _safe_float(raw_profile.get("free_disk_gb", 0)),
    }

    models = exposed_models()
    passerelle_muette = models is None

    groups = {
        "local": [],
        "cloud": [],
        "anthropic": [],
        "routeurs": [],
        "autres": [],  # pour les alias non reconnus
    }
    for alias in (models or []):
        if alias.startswith("adaptive-router"):
            groups["routeurs"].append(alias)
        elif alias.endswith("-local") or alias == "releve-locale":
            groups["local"].append(alias)
        elif alias.endswith("-cloud"):
            groups["cloud"].append(alias)
        elif alias.startswith("anthropic-"):
            groups["anthropic"].append(alias)
        else:
            groups["autres"].append(alias)

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
            timeout=TIMEOUT_RUN,
            encoding="utf-8",
            errors="replace",
        )
    except (OSError, subprocess.SubprocessError) as exc:  # pragma: no cover
        print(
            f"Erreur lors de l'execution de nexus_validate.py : {exc}",
            file=sys.stderr,
        )
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
    except OSError:
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
        f"> Généré par `python scripts/nexus_state.py` le {now}.",
        "> **Ne pas éditer à la main** : ce fichier décrit ce qui a été mesuré,",
        "> pas ce que l'on croit installé. Le régénérer vaut mieux que le corriger.",
        "",
        "## Dépôt",
        "",
        "| | |",
        "|---|---|",
        f"| Branche | `{branch or '?'}` |",
        f"| Commit | `{commit or '?'}` |",
        f"| Arbre de travail | {worktree_status} |",
        f"| Version de routage | `{router_version}` |",
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
        f"| Implantation | `{profile['ollama']['mode']}` |",
        f"| Mémoire d'inférence | {profile['inference_memory_gb']:.1f} Go |",
        f"| RAM machine | {profile['host_ram_gb']:.1f} Go |",
        f"| Budget pool | {profile['pool_budget_gb']:.1f} Go |",
        f"| Budget maximal | {profile['runnable_budget_gb']:.1f} Go |",
        f"| CPU | {profile['cpu_cores']} cœurs / {profile['cpu_threads']} threads |",
        f"| GPU | {profile['gpu']['name'] or '?'} ({profile['gpu']['vram_gb']:.1f} Go) |",
        f"| Offload GPU | {'oui' if profile['gpu_usable_for_offload'] else 'non'} |",
        f"| Stockage modèles | `{profile['model_store']}` |",
        f"| Disque libre | {profile['free_disk_gb']:.1f} Go |",
        "",
    ]

    if isinstance(profile['ollama']['mode'], str) and profile['ollama']['mode'].startswith("docker"):
        perdu = profile['host_ram_gb'] - profile['inference_memory_gb']
        if perdu > 4:
            lines += [
                f"> {perdu:.0f} Go des {profile['host_ram_gb']:.0f} Go de la machine restent hors d'atteinte de",
                "> l'inférence tant que le moteur tourne dans Docker.",
                "",
            ]

    lines += [
        ("## Inventaire exposé — PASSERELLE INJOIGNABLE"
         if passerelle_muette else
         f"## Inventaire exposé — {len(models)} modèles"),
        "",
        ("> La passerelle n'a pas répondu sur `127.0.0.1:4000`. Ce qui suit "
         "n'est donc **pas** un inventaire vide : c'est une absence de "
         "mesure. Relancer `.\\scripts\\start.ps1` avant d'en conclure quoi "
         "que ce soit."
         if passerelle_muette else ""),
        "",
        "| Plan | Nombre | Facturation |",
        "|---|---|---|",
        f"| Local | {len(groups['local'])} | aucune, rien ne quitte la machine |",
        f"| Ollama Cloud | {len(groups['cloud'])} | abonnement Ollama |",
        f"| Anthropic | {len(groups['anthropic'])} | crédits API, distincts de l'abonnement claude.ai |",
        f"| Routeurs | {len(groups['routeurs'])} | selon le plan retenu |",
        f"| Autres | {len(groups['autres'])} | non classés |",
        "",
        "## Intégrité de la configuration",
        "",
        f"Verdict : **{verdict}**",
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
        lines.append(f"| `{relative}` | `{digest if digest else 'absent'}` |")

    # La traque, mesuree a chaque regeneration.
    #
    # Le cockpit datait de vingt-et-une heures quand il a ete rouvert : il
    # decrivait 44 modeles et une configuration INVALIDE, la ou il y en
    # avait 67 et une configuration saine. Un tableau de bord qu'il faut
    # penser a mettre a jour ne sert qu'a rassurer.
    #
    # Les chiffres de la traque y sont donc joints automatiquement. Ce sont
    # des heuristiques, et le texte le dit : un constat est une piste a
    # verifier dans le code reel, jamais un verdict.
    lines += ["", "## Traque mecanique", ""]
    try:
        r = subprocess.run([sys.executable,
                            os.path.join(ROOT, "scripts", "nexus_traque.py"),
                            "--muet"], capture_output=True, text=True,
                           timeout=180, encoding="utf-8", errors="replace")
        if r.returncode == 0 and r.stdout.strip():
            lines += ["```", r.stdout.strip(), "```", "",
                      "Heuristiques : chaque constat est une piste a verifier",
                      "dans le code reel, jamais un verdict. Detail par",
                      "`python scripts/nexus_traque.py`."]
        else:
            lines.append("_traque indisponible_")
    except Exception as exc:
        # Le cockpit doit s'ecrire meme si la traque echoue : perdre l'etat
        # mesure pour un rapport heuristique serait un mauvais echange.
        lines.append("_traque indisponible : %s_" % str(exc)[:80])

    lines += [
        "",
        "---",
        "",
        "Sujets ouverts : voir [CHECKLIST_COCKPIT.MD](CHECKLIST_COCKPIT.MD).",
        "Historique : voir [PROGRESS.md](PROGRESS.md).",
    ]

    # S'assurer que le répertoire cible existe avant d'écrire le fichier temporaire.
    os.makedirs(os.path.dirname(STATE), exist_ok=True)

    temp_path = STATE + ".tmp"
    try:
        with io.open(temp_path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write("\n".join(lines) + "\n")
        os.replace(temp_path, STATE)
    finally:
        # Nettoyage du fichier temporaire en cas d'échec.
        if os.path.exists(temp_path):
            try:
                os.unlink(temp_path)
            except OSError:
                pass

    if passerelle_muette:
        print(
            "STATE.md regenere : PASSERELLE INJOIGNABLE (127.0.0.1:4000), "
            f"configuration {verdict}"
        )
    else:
        print(
            f"STATE.md regenere : {len(models)} modeles exposes, configuration {verdict}"
        )
    # Propagation du code de retour de la validation : si la validation a
    # échoué, on renvoie un code d'erreur afin que l'orchestrateur puisse
    # prendre la bonne décision.
    return 0 if validation.returncode == 0 else validation.returncode


if __name__ == "__main__":
    sys.exit(main())
