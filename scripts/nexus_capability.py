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

Unités
------
Tout ce module compte en **gigaoctets décimaux** (Go = 10^9 octets), parce
que c'est l'unité dans laquelle `ollama list` publie le poids des modèles.
Les octets rendus par Windows ou par le système de fichiers sont donc
divisés par 1e9, jamais par 1024**3.

Le mélange des deux n'était pas une coquette imprécision : un poids
décimal était comparé à un budget binaire, ce qui rétrécissait le budget
de 7 % — 61,6 au lieu de 66,2 Go ici. L'erreur allait dans le sens
prudent, mais un chiffre faux dans le bon sens reste faux, et en mode
« docker+host » la même expression soustrayait un Gio d'un Go décimal,
où la prudence n'était plus garantie du tout.

Usage :
    python scripts/nexus_capability.py            # rapport lisible
    python scripts/nexus_capability.py --json     # profil exploitable
    python scripts/nexus_capability.py --can-download qwen3-coder:30b
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
    # 1 KiB vaut 1024 octets, donc 1.024e-6 Go. La valeur 1.049e-6 qui
    # figurait ici était le carré du facteur — juste pour le Mio, faux
    # pour le Kio.
    scale = {
        "b": 1e-9, "kb": 1e-6, "mb": 1e-3, "gb": 1.0, "tb": 1e3,
        "kib": 1.024e-6, "mib": 1.049e-3, "gib": 1.074, "tib": 1099.5,
    }
    return value * scale.get(match.group(2).lower(), 0.0)


# ----------------------------------------------------------------------
# Mesures
# ----------------------------------------------------------------------
def host_memory_gb() -> float | None:
    """
    Mémoire physique de la machine, en gigaoctets décimaux.

    Rend **None** quand aucune des deux voies n'a pu mesurer — jamais 0.
    Zéro gigaoctet n'est pas une mesure : c'est l'aveu qu'on n'a pas su
    interroger la machine. Les confondre faisait rendre un verdict
    catégorique — « aucun modèle exécutable ici » — sur un hôte
    parfaitement capable mais momentanément muet, et ce verdict décide
    quels modèles sont téléchargés et routés automatiquement.
    """
    out = _run(["powershell", "-NoProfile", "-Command",
                "(Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory"])
    try:
        return float(out.strip()) / 1e9
    except Exception:
        pass
    # Sous Linux / WSL, `MemTotal` s'affiche en « kB » mais compte des
    # kibioctets : d'où le passage par 1024 avant la conversion décimale.
    try:
        with open("/proc/meminfo") as fh:
            for line in fh:
                if line.startswith("MemTotal:"):
                    return float(line.split()[1]) * 1024 / 1e9
    except Exception:
        pass
    return None


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
                # `nvidia-smi` compte en mébioctets ; la VRAM est ensuite
                # comparée à des poids de modèles en Go décimaux, donc elle
                # se convertit dans la même unité qu'eux. Une carte annoncée
                # « 16 Go » en affichera 17,2 : c'est sa taille réelle, et
                # c'est celle à laquelle un modèle de 17 Go doit se mesurer.
                return {"name": name.strip(),
                        "vram_gb": round(float(mib.strip()) * 1.049e-3, 1),
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
            vram = float(raw) / 1e9
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
    # L'hôte d'abord : c'est l'implantation courante depuis la sortie du
    # moteur hors de Docker, et la sonde HTTP coûte 40 ms.
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

    # Le conteneur reste sondé, à dessein : `docker-compose.yml` déclare
    # toujours le service sous le profil « embedded », qui est le chemin de
    # retour documenté. La sonde ne coûte que 0,13 s quand le conteneur
    # n'existe plus, et son absence est une information — pas une panne.
    stats = _run(["docker", "stats", "--no-stream", "--format",
                  "{{.MemUsage}}", "ollama-server"])
    container_limit = 0.0
    if "/" in stats:
        container_limit = parse_size(stats.split("/")[1])

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
        return store, shutil.disk_usage(probe).free / 1e9
    except Exception:
        return store, 0.0


def installed_models(location: dict | None = None) -> dict[str, float] | None:
    """
    Modèles présents et leur poids, sur le moteur qui sert réellement.

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

    Un seul moteur est interrogé, celui que `ollama_location()` désigne
    comme servant. Les deux inventaires étaient auparavant fusionnés, et
    `setdefault` donnait la priorité au conteneur : un modèle présent dans
    le seul volume Docker était attribué au moteur de l'hôte, qui ne
    l'avait pas — donc un verdict rendu sur un poids que ce moteur-là
    n'aurait jamais pu charger. Le budget de `build_profile()` vient
    désormais du même moteur que cet inventaire : les deux ne peuvent plus
    décrire des machines différentes.
    """
    if location is None:
        location = ollama_location()
    source = (["ollama", "list"] if location["host_native"]
              else ["docker", "exec", "ollama-server", "ollama", "list"])
    out = _run(source)
    if not out.strip():
        return None
    sizes: dict[str, float] = {}
    for line in out.splitlines()[1:]:
        parts = line.split()
        # Les modèles Ollama Cloud apparaissent sans poids (« - ») : ils ne
        # pèsent rien ici, et leur donner un poids nul les ferait entrer
        # dans l'inventaire local comme s'ils y étaient chargeables.
        if len(parts) >= 4 and parts[2] != "-":
            sizes.setdefault(parts[0], parse_size(parts[2] + parts[3]))
    return sizes


# ----------------------------------------------------------------------
# Profil et verdicts
# ----------------------------------------------------------------------
def build_profile() -> dict:
    location = ollama_location()
    host_ram = host_memory_gb()
    physical, logical = cpu_cores()
    gpu = gpu_info()
    store, free_disk = model_store_free_gb(location)

    # Mémoire offerte au moteur qui SERT, jamais au mieux doté des deux.
    #
    # Les deux implantations ne s'additionnent pas : la VM WSL2 prélève sa
    # mémoire sur celle de la machine, faire tourner deux Ollama partitionne
    # les 62 Go, il n'en crée pas 94.
    #
    # Surtout, l'ancienne expression prenait le maximum des deux budgets.
    # Le verdict dépendait donc de l'état du démon Docker à l'instant de la
    # génération : quatre modèles passaient de DEGRADED à ACCEPT selon que
    # le conteneur tournait, pour être ensuite servis par un moteur de
    # 32 Go. Un verdict qui change parce qu'un démon a démarré n'est pas un
    # verdict. Le budget suit maintenant le moteur d'où vient l'inventaire.
    usable = (host_ram if location["host_native"]
              else location["container_limit_gb"] or host_ram)

    # `usable` vaut None quand la mémoire n'a pas pu être mesurée. Les
    # budgets ne sont alors pas calculables, et il faut le dire plutôt que
    # de porter un 0 : un budget nul ferait rejeter TOUS les modèles et
    # rendrait la plateforme inutilisable sur une machine parfaitement
    # capable, sans que rien ne signale que la cause est une mesure
    # manquée et non un manque de mémoire.
    memoire_mesuree = usable is not None

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
    # `discrete` reste calculé hors du cas non mesuré : il décrit le
    # matériel, pas le budget, et il est lu plus bas quoi qu'il arrive.
    discrete = bool(gpu["vram_gb"] >= 6 and not gpu["integrated"])
    if not memoire_mesuree:
        fast_budget = max_budget = None
    elif discrete:
        fast_budget = gpu["vram_gb"] * POOL_FRACTION
        max_budget = max(gpu["vram_gb"], usable) * RUNNABLE_FRACTION
    else:
        fast_budget = usable * POOL_FRACTION
        max_budget = usable * RUNNABLE_FRACTION

    return {
        "host_ram_gb": None if host_ram is None else round(host_ram, 1),
        # Conservée séparément, et non recalculée depuis la valeur arrondie :
        # 66,2 Go réarrondis donnent 61,7 Gio là où Windows en affiche 61,6,
        # et un dixième d'écart suffit à faire douter de la mesure entière.
        "host_ram_gib": (None if host_ram is None
                         else round(host_ram * 1e9 / 1024 ** 3, 1)),
        "cpu_cores": physical,
        "cpu_threads": logical,
        "gpu": gpu,
        "gpu_usable_for_offload": discrete,
        "ollama": location,
        # None et non 0 : un consommateur doit pouvoir distinguer « la
        # machine a 0 Go » — impossible — de « on ne sait pas ».
        "memoire_mesuree": memoire_mesuree,
        "inference_memory_gb": None if usable is None else round(usable, 1),
        "pool_budget_gb": None if fast_budget is None else round(fast_budget, 1),
        "runnable_budget_gb": None if max_budget is None else round(max_budget, 1),
        "model_store": store,
        "free_disk_gb": round(free_disk, 1),
    }


UNKNOWN = "INCONNU"


def profile_signature(profile: dict) -> str:
    """
    Empreinte des seules valeurs dont dépend un verdict.

    Un verdict est calculé à l'instant de la génération, puis figé dans la
    configuration : rien n'y signale ensuite que la machine a changé. Une
    barrette retirée, un GPU ajouté, un moteur redéployé ailleurs, et les
    pools continuent de reposer sur un budget qui n'existe plus.

    L'empreinte est volontairement lisible plutôt que hachée : elle tient
    dans un commentaire YAML, et une divergence dit *laquelle* des valeurs
    a bougé au lieu d'annoncer seulement qu'il y en a une.
    """
    return "%s/%.1f/%.1f/%.1f/%s" % (
        profile["ollama"]["mode"],
        profile["inference_memory_gb"],
        profile["pool_budget_gb"],
        profile["runnable_budget_gb"],
        "gpu" if profile["gpu_usable_for_offload"] else "cpu",
    )


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
    parser.add_argument("--can-download", metavar="MODELE|TAILLE_GO",
                        help="arbitre un telechargement avant de le lancer : "
                             "code 0 autorise, 1 refuse, 2 poids inconnu")
    args = parser.parse_args()

    profile = build_profile()
    location = profile["ollama"]
    models = installed_models(location)
    if models is None:
        print("Inventaire illisible : Docker et Ollama sont-ils joignables ?")
        print("Aucun verdict n'est rendu — supposer serait pire que se taire.")
        return 1

    # Le garde-fou n'existait que sous forme de fonction, appelée par le
    # seul banc de tests : aucun `ollama pull` de la plateforme ne passait
    # par lui, alors que `model_list.txt` contient des modèles déjà classés
    # REJECT. Cette entrée le rend appelable depuis PowerShell, où se
    # trouvent les téléchargements.
    if args.can_download:
        cible = args.can_download
        try:
            taille = float(cible.replace(",", "."))
        except ValueError:
            taille = models.get(cible, 0.0)
        if taille <= 0:
            print("Poids inconnu pour '%s' : ni le disque ni la memoire ne"
                  " peuvent etre arbitres." % cible)
            print("Le module se tait plutot que de trancher a l'aveugle.")
            return 2
        ok, motif = can_download(taille, profile)
        print(("AUTORISE : " if ok else "REFUSE : ") + motif)
        return 0 if ok else 1

    if args.json:
        payload = dict(profile)
        payload["signature"] = profile_signature(profile)
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
    # Le rappel en gibioctets n'est pas decoratif : Windows affiche 61,6
    # la ou ce module compte 66,2, et sans cette equivalence le lecteur
    # conclut a une erreur de mesure au lieu d'un changement d'unite.
    print("  RAM machine      : %.1f Go (%.1f Gio affiches par Windows)"
          % (profile["host_ram_gb"], profile["host_ram_gib"]))
    print("  Moteur Ollama    : %s" % profile["ollama"]["mode"])
    print("  Memoire moteur   : %.1f Go" % profile["inference_memory_gb"])
    mode = profile["ollama"]["mode"]
    if mode == "docker+host":
        print("                     deux moteurs actifs : %.1f Go plafonnes cote"
              " Docker." % profile["ollama"]["container_limit_gb"])
        print("                     Le budget affiche est celui de l'hote, d'ou"
              " vient l'inventaire ;")
        print("                     les deux ne s'additionnent pas : la VM"
              " preleve sa memoire")
        print("                     sur celle de la machine.")
    elif mode.startswith("docker"):
        perdu = profile["host_ram_gb"] - profile["inference_memory_gb"]
        if perdu > 1:
            print("                     (%.1f Go de la machine hors d'atteinte"
                  " du moteur)" % perdu)
    print("  Budget pool      : %.1f Go" % profile["pool_budget_gb"])
    print("  Budget maximal   : %.1f Go" % profile["runnable_budget_gb"])
    print("  Stockage modeles : %s" % profile["model_store"])
    print("  Disque libre     : %.1f Go (%.1f Gio)"
          % (profile["free_disk_gb"], profile["free_disk_gb"] * 1e9 / 1024 ** 3))

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
