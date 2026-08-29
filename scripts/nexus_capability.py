# -*- coding: utf-8 -*-
"""
Profil matériel de la machine et verdict automatique par modèle.

Raison d'être
-------------
Un modèle plus lourd que la mémoire réellement disponible n'échoue pas
franchement : il s'exécute en pagination, à une lenteur qui rend la réponse
inutilisable. Le laisser dans un pool de routage automatique revient à tirer
au sort une réponse qui n'arrivera pas. Le fait a été observé sur cette
machine : `llama3.3:70b` (42 Go) sélectionné par le routeur alors que le
moteur d'inférence n'avait que 32 Go.

Ce module mesure la machine — jamais ne la suppose — et rend pour chaque
modèle un verdict opposable :

    ACCEPT    éligible au routage automatique
    DEGRADED  adressable explicitement, mais hors des pools
    REJECT    ne peut pas s'exécuter utilement ici

Le même profil sert de garde-fou au téléchargement : rien ne sert de tirer
40 Go de poids sur un disque qui n'a pas la place, ni de les tirer pour un
moteur qui ne pourra pas les charger.

Usage :
    python scripts/nexus_capability.py            # rapport lisible
    python scripts/nexus_capability.py --json     # profil exploitable
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys

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

# Fractions de la mémoire utilisable. Les poids ne sont pas seuls en
# mémoire : le cache KV, le contexte et le reste du système partagent la
# même enveloppe. Un modèle occupant plus de 60 % ne laisse plus de quoi
# travailler ; au-delà de 85 % il ne se charge pas.
POOL_FRACTION = 0.60
RUNNABLE_FRACTION = 0.85

# Marge disque exigée pour un téléchargement : les poids, plus la place
# de manoeuvre du téléchargement lui-même.
DISK_MARGIN = 1.25

ACCEPT, DEGRADED, REJECT = "ACCEPT", "DEGRADED", "REJECT"


def _run(args: list[str], timeout: int = 60) -> str:
    try:
        result = subprocess.run(args, capture_output=True, text=True,
                                timeout=timeout, encoding="utf-8",
                                errors="replace")
        return result.stdout if result.returncode == 0 else ""
    except Exception:
        return ""


def parse_size(text: str) -> float:
    """Taille en gigaoctets, quelle que soit l'unité écrite."""
    match = re.match(r"([\d.,]+)\s*([KMGT]?i?B)", text.strip(), re.I)
    if not match:
        return 0.0
    value = float(match.group(1).replace(",", "."))
    scale = {
        "b": 1e-9, "kb": 1e-6, "mb": 1e-3, "gb": 1.0, "tb": 1e3,
        "kib": 1.049e-6, "mib": 1.049e-3, "gib": 1.074, "tib": 1099.5,
    }
    return value * scale.get(match.group(2).lower(), 0.0)


# ----------------------------------------------------------------------
# Mesures
# ----------------------------------------------------------------------
def host_memory_gb() -> float:
    out = _run(["powershell", "-NoProfile", "-Command",
                "(Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory"])
    try:
        return float(out.strip()) / (1024 ** 3)
    except Exception:
        pass
    try:  # Linux / WSL
        with open("/proc/meminfo") as fh:
            for line in fh:
                if line.startswith("MemTotal:"):
                    return float(line.split()[1]) / (1024 ** 2)
    except Exception:
        pass
    return 0.0


def cpu_cores() -> tuple[int, int]:
    out = _run(["powershell", "-NoProfile", "-Command",
                "$c=Get-CimInstance Win32_Processor|Select-Object -First 1;"
                "\"$($c.NumberOfCores) $($c.NumberOfLogicalProcessors)\""])
    parts = out.split()
    if len(parts) == 2 and all(p.isdigit() for p in parts):
        return int(parts[0]), int(parts[1])
    return os.cpu_count() or 0, os.cpu_count() or 0


def gpu_info() -> dict:
    """
    Carte graphique et VRAM réellement dédiée.

    Le cas d'un GPU discret ajouté plus tard est prévu ici : `nvidia-smi`
    est interrogé en premier car il rapporte la VRAM exacte, là où
    `Win32_VideoController.AdapterRAM` sature à 4 Go sur beaucoup de
    pilotes et sous-estimerait une carte récente.
    """
    # 1. GPU NVIDIA discret — la source la plus fiable quand elle existe.
    out = _run(["nvidia-smi", "--query-gpu=name,memory.total",
                "--format=csv,noheader,nounits"], timeout=30)
    if out.strip():
        first = out.strip().splitlines()[0]
        if "," in first:
            name, mib = first.split(",", 1)
            try:
                return {"name": name.strip(),
                        "vram_gb": round(float(mib.strip()) / 1024, 1),
                        "integrated": False, "vendor": "nvidia"}
            except Exception:
                pass

    # 2. À défaut, l'inventaire Windows.
    out = _run(["powershell", "-NoProfile", "-Command",
                "$g=Get-CimInstance Win32_VideoController|"
                "Sort-Object AdapterRAM -Descending|Select-Object -First 1;"
                "\"$($g.Name)|$($g.AdapterRAM)\""])
    name, vram = "", 0.0
    if "|" in out:
        name, raw = out.strip().split("|", 1)
        try:
            vram = float(raw) / (1024 ** 3)
        except Exception:
            vram = 0.0

    # Un iGPU ne dispose pas d'une VRAM propre : la valeur annoncée est une
    # réservation prélevée sur la mémoire système, pas un budget distinct.
    # La distinction n'est pas cosmétique — mesuré sur Radeon 890M, passer
    # du CPU au GPU intégré ne gagne que 7 %, parce que le goulot est la
    # bande passante mémoire, que les deux partagent.
    integrated = bool(re.search(r"radeon\s*\d{3}m|iris|uhd|vega|integrated|"
                                r"graphics$", name, re.I))
    vendor = ("amd" if re.search(r"radeon|amd", name, re.I)
              else "intel" if re.search(r"intel|iris|uhd", name, re.I)
              else "inconnu")
    return {"name": name.strip(), "vram_gb": round(vram, 1),
            "integrated": integrated, "vendor": vendor}


def ollama_location() -> dict:
    """
    Où tourne réellement le moteur d'inférence, et de combien il dispose.

    Deux implantations sont possibles et n'ont pas le même budget :
      - dans Docker : plafonné par la mémoire allouée à la VM WSL2 ;
      - sur l'hôte  : toute la mémoire de la machine.
    """
    # Conteneur ?
    stats = _run(["docker", "stats", "--no-stream", "--format",
                  "{{.MemUsage}}", "ollama-server"])
    container_limit = 0.0
    if "/" in stats:
        container_limit = parse_size(stats.split("/")[1])

    # Hôte ?
    native = False
    version = _run(["ollama", "--version"], timeout=20)
    if version.strip():
        try:
            import urllib.request
            urllib.request.urlopen("http://127.0.0.1:11434/api/version",
                                   timeout=5).read()
            native = True
        except Exception:
            native = False

    if container_limit and not native:
        mode = "docker"
    elif native and not container_limit:
        mode = "host"
    elif native and container_limit:
        mode = "docker+host"
    else:
        mode = "inconnu"

    return {"mode": mode,
            "container_limit_gb": round(container_limit, 1),
            "host_native": native}


def model_store_free_gb(location: dict) -> tuple[str, float]:
    """Disque qui reçoit réellement les poids, et sa place libre."""
    if location["mode"] == "host":
        store = os.environ.get(
            "OLLAMA_MODELS",
            os.path.join(os.path.expanduser("~"), ".ollama", "models"))
    else:
        # Le volume Docker vit dans le disque virtuel de la VM WSL2, donc
        # sur le disque système : c'est sa place libre qui commande.
        store = os.environ.get("SystemDrive", "C:") + os.sep
    probe = store
    while probe and not os.path.exists(probe):
        parent = os.path.dirname(probe)
        if parent == probe:
            break
        probe = parent
    try:
        return store, shutil.disk_usage(probe).free / (1024 ** 3)
    except Exception:
        return store, 0.0


def installed_models() -> dict[str, float] | None:
    """
    Modèles présents et leur poids, quelle que soit l'implantation.

    Renvoie **None** si aucun inventaire n'a pu être lu — et cette
    distinction est le coeur du garde-fou.

    Un dictionnaire vide se confondait avec « aucun modèle mesuré » :
    conteneur renommé, Docker arrêté, `ollama` hors du PATH, et toutes
    les tailles valaient 0. Or `verdict(0)` répond ACCEPT. Le générateur
    déclarait alors un modèle de 54 Go en tête de chaîne sur un moteur de
    32 Go, et le validateur — qui appelle la même fonction — l'approuvait.
    Les deux échouaient *ouverts*, ensemble, exactement là où le module
    prétend fermer.

    Un inventaire illisible n'est pas un inventaire vide : l'appelant doit
    s'arrêter, pas supposer.
    """
    sizes: dict[str, float] = {}
    lu = False
    for args in (["docker", "exec", "ollama-server", "ollama", "list"],
                 ["ollama", "list"]):
        out = _run(args)
        if not out.strip():
            continue
        lu = True
        for line in out.splitlines()[1:]:
            parts = line.split()
            if len(parts) >= 4 and parts[2] != "-":
                sizes.setdefault(parts[0], parse_size(parts[2] + parts[3]))
    return sizes if lu else None


# ----------------------------------------------------------------------
# Profil et verdicts
# ----------------------------------------------------------------------
def build_profile() -> dict:
    location = ollama_location()
    host_ram = host_memory_gb()
    physical, logical = cpu_cores()
    gpu = gpu_info()
    store, free_disk = model_store_free_gb(location)

    # Mémoire réellement offerte au moteur d'inférence.
    #
    # Cas des deux moteurs simultanés : ils ne s'additionnent PAS. La VM
    # WSL2 prélève sa mémoire sur celle de la machine — faire tourner deux
    # Ollama partitionne les 62 Go, il n'en crée pas 94. Le plus grand
    # modèle exécutable reste donc borné par le plus grand des deux
    # budgets, jamais par leur somme.
    #
    # Ce qu'on y gagne réellement est ailleurs : la résidence simultanée
    # de deux modèles sans éviction, et la continuité de service pendant
    # une migration.
    if location["mode"] == "host":
        usable = host_ram
    elif location["mode"] == "docker+host":
        usable = max(host_ram - location["container_limit_gb"],
                     location["container_limit_gb"])
    elif location["container_limit_gb"]:
        usable = location["container_limit_gb"]
    else:
        usable = host_ram

    # Un GPU discret change la nature du budget, pas seulement sa taille.
    #
    #   iGPU        la VRAM annoncée est prélevée sur la RAM système : il
    #               n'y a qu'un seul budget, et la bande passante mémoire
    #               reste le goulot. Mesuré : +7 % seulement.
    #   GPU discret la VRAM est une mémoire distincte, à bande passante
    #               bien supérieure. Un modèle qui y tient est rapide ;
    #               un modèle qui déborde retombe à la vitesse du CPU.
    #
    # D'où deux budgets quand un GPU discret existe : le budget RAPIDE
    # (la VRAM) commande l'éligibilité au routage automatique, le budget
    # MAXIMAL (la RAM) délimite ce qui reste exécutable, en dégradé.
    # Ajouter une carte plus tard ne demandera donc aucune réécriture :
    # les seuils suivront la mesure.
    discrete = bool(gpu["vram_gb"] >= 6 and not gpu["integrated"])
    if discrete:
        fast_budget = gpu["vram_gb"] * POOL_FRACTION
        max_budget = max(gpu["vram_gb"], usable) * RUNNABLE_FRACTION
    else:
        fast_budget = usable * POOL_FRACTION
        max_budget = usable * RUNNABLE_FRACTION

    return {
        "host_ram_gb": round(host_ram, 1),
        "cpu_cores": physical,
        "cpu_threads": logical,
        "gpu": gpu,
        "gpu_usable_for_offload": discrete,
        "ollama": location,
        "inference_memory_gb": round(usable, 1),
        "pool_budget_gb": round(fast_budget, 1),
        "runnable_budget_gb": round(max_budget, 1),
        "model_store": store,
        "free_disk_gb": round(free_disk, 1),
    }


UNKNOWN = "INCONNU"


def verdict(size_gb: float, profile: dict) -> tuple[str, str]:
    """
    Verdict et motif, pour un modèle d'un poids donné.

    Un poids nul ou négatif signifie « non mesuré », jamais « léger ».
    Le verdict est alors INCONNU : c'est à l'appelant de décider, et non
    au module de trancher en faveur de l'acceptation.
    """
    if size_gb <= 0:
        return UNKNOWN, "poids non mesure : verdict impossible"
    if size_gb > profile["runnable_budget_gb"]:
        return REJECT, ("%.0f Go de poids pour %.0f Go de memoire d'inference"
                        % (size_gb, profile["inference_memory_gb"]))
    if size_gb > profile["pool_budget_gb"]:
        return DEGRADED, ("%.0f Go sur %.0f Go : chargeable, mais sans marge "
                          "pour le contexte et le cache"
                          % (size_gb, profile["inference_memory_gb"]))
    return ACCEPT, "%.0f Go, dans le budget" % size_gb


def can_download(size_gb: float, profile: dict) -> tuple[bool, str]:
    needed = size_gb * DISK_MARGIN
    if needed > profile["free_disk_gb"]:
        return False, ("%.0f Go requis (marge comprise) pour %.0f Go libres sur %s"
                       % (needed, profile["free_disk_gb"], profile["model_store"]))
    state, reason = verdict(size_gb, profile)
    if state == REJECT:
        return False, "inutilisable ici : " + reason
    return True, reason


# ----------------------------------------------------------------------
def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true",
                        help="sortie exploitable par un autre script")
    args = parser.parse_args()

    profile = build_profile()
    models = installed_models()
    if models is None:
        print("Inventaire illisible : Docker et Ollama sont-ils joignables ?")
        print("Aucun verdict n'est rendu — supposer serait pire que se taire.")
        return 1

    if args.json:
        payload = dict(profile)
        payload["models"] = {
            name: {"size_gb": round(size, 1), "verdict": verdict(size, profile)[0],
                   "reason": verdict(size, profile)[1]}
            for name, size in sorted(models.items())
        }
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0

    print("=" * 68)
    print(" Profil materiel — Claude-Local-Nexus")
    print("=" * 68)
    print("  CPU              : %d coeurs / %d threads"
          % (profile["cpu_cores"], profile["cpu_threads"]))
    print("  GPU              : %s (%.1f Go%s)"
          % (profile["gpu"]["name"] or "inconnu", profile["gpu"]["vram_gb"],
             ", integre" if profile["gpu"]["integrated"] else ""))
    print("  Offload GPU      : %s"
          % ("possible" if profile["gpu_usable_for_offload"]
             else "non — inference en RAM systeme"))
    print("  RAM machine      : %.1f Go" % profile["host_ram_gb"])
    print("  Moteur Ollama    : %s" % profile["ollama"]["mode"])
    print("  Memoire moteur   : %.1f Go" % profile["inference_memory_gb"])
    mode = profile["ollama"]["mode"]
    if mode == "docker+host":
        print("                     deux moteurs actifs : %.1f Go plafonnes cote"
              " Docker," % profile["ollama"]["container_limit_gb"])
        print("                     le reste cote hote. Les budgets ne"
              " s'additionnent pas :")
        print("                     la VM preleve sa memoire sur celle de la"
              " machine.")
    elif mode.startswith("docker"):
        perdu = profile["host_ram_gb"] - profile["inference_memory_gb"]
        if perdu > 1:
            print("                     (%.1f Go de la machine hors d'atteinte"
                  " du moteur)" % perdu)
    print("  Budget pool      : %.1f Go" % profile["pool_budget_gb"])
    print("  Budget maximal   : %.1f Go" % profile["runnable_budget_gb"])
    print("  Stockage modeles : %s" % profile["model_store"])
    print("  Disque libre     : %.1f Go" % profile["free_disk_gb"])

    if not models:
        print("\n  Aucun modele detecte.")
        return 0

    buckets: dict[str, list] = {ACCEPT: [], DEGRADED: [], REJECT: [], UNKNOWN: []}
    for name, size in models.items():
        state, reason = verdict(size, profile)
        buckets[state].append((name, size, reason))

    print("\n" + "-" * 68)
    for state, label in ((ACCEPT, "ACCEPTES — eligibles au routage automatique"),
                         (DEGRADED, "DEGRADES — adressables, hors des pools"),
                         (REJECT, "REJETES — inexecutables sur cette machine"),
                         (UNKNOWN, "NON MESURES — verdict impossible")):
        if not buckets[state]:
            continue
        rows = sorted(buckets[state], key=lambda r: -r[1])
        print("\n  %s (%d)" % (label, len(rows)))
        for name, size, reason in rows:
            print("    %-28s %6.1f Go   %s" % (name, size, reason))

    total = sum(size for _, size in models.items())
    print("\n" + "-" * 68)
    print("  Poids total installe : %.0f Go" % total)
    rejected = sum(size for _, size, _ in buckets[REJECT])
    if rejected:
        print("  Dont inexecutable    : %.0f Go" % rejected)
    return 0


if __name__ == "__main__":
    sys.exit(main())
