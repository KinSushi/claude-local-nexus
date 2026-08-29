# -*- coding: utf-8 -*-
"""
Bascule le moteur d'inférence local entre Docker et l'hôte.

Pourquoi ce script existe
-------------------------
Dans Docker sur Windows, Ollama est plafonné par la mémoire allouée à la VM
WSL2 — la moitié de la machine, ici. Le plafond n'est pas théorique : il a
écarté `llama3.3:70b` (42 Go) et empêche d'allouer un contexte confortable
au modèle de relève. Sortir Ollama du conteneur rend la totalité de la RAM
au moteur, et ouvre la question de l'accélération GPU que Docker sur
Windows ne peut de toute façon pas offrir.

Ce que Docker apporte réellement — reproductibilité de LiteLLM, PostgreSQL
et Redis — n'est pas perdu : ces services y restent. Les poids de modèles,
eux, n'ont jamais été un artefact reproductible : c'est `model_list.txt` et
le générateur qui reconstituent l'inventaire, et ils fonctionnent
identiquement quelle que soit l'implantation du moteur.

Le script ne bascule QUE si la cible répond déjà : on ne coupe pas un
moteur qui marche pour un moteur hypothétique.

Usage :
    python scripts/nexus_switch_engine.py --to host     [--dry-run]
    python scripts/nexus_switch_engine.py --to docker   [--dry-run]
    python scripts/nexus_switch_engine.py --status
"""
from __future__ import annotations

import argparse
import io
import json
import os
import re
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG = os.path.join(ROOT, "litellm_config.yaml")

# Adresse vue depuis le conteneur LiteLLM, et adresse équivalente vue
# depuis la machine — la première sert à la configuration, la seconde
# à vérifier que la cible répond avant de basculer.
ENGINES = {
    "docker": {
        "api_base": "http://ollama:11434",
        "probe": "http://127.0.0.1:11435",
        "label": "Ollama dans Docker",
    },
    "host": {
        "api_base": "http://host.docker.internal:11434",
        "probe": "http://127.0.0.1:11434",
        "label": "Ollama sur l'hôte",
    },
}


def probe(url: str) -> str | None:
    try:
        with urllib.request.urlopen(url + "/api/version", timeout=8) as response:
            return json.loads(response.read().decode("utf-8")).get("version")
    except Exception:
        return None


def current_engine(text: str) -> str:
    counts = {name: text.count(cfg["api_base"]) for name, cfg in ENGINES.items()}
    if counts["host"] and not counts["docker"]:
        return "host"
    if counts["docker"] and not counts["host"]:
        return "docker"
    if counts["host"] and counts["docker"]:
        return "mixte"
    return "inconnu"


def installed_on(engine: str) -> set[str]:
    """Inventaire du moteur visé, pour mesurer ce qu'une bascule coûterait."""
    import subprocess
    args = (["ollama", "list"] if engine == "host"
            else ["docker", "exec", "ollama-server", "ollama", "list"])
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=60,
                                encoding="utf-8", errors="replace")
        if result.returncode != 0:
            return set()
        return {line.split()[0] for line in result.stdout.splitlines()[1:]
                if line.strip() and not line.split()[0].endswith(":cloud")}
    except Exception:
        return set()


def show_status() -> int:
    with io.open(CONFIG, encoding="utf-8") as fh:
        text = fh.read()
    active = current_engine(text)

    print("=" * 66)
    print(" Moteur d'inference local")
    print("=" * 66)
    print("  Configure : %s" % active)
    for name, cfg in ENGINES.items():
        version = probe(cfg["probe"])
        models = installed_on(name)
        state = ("repond (v%s)" % version) if version else "ne repond pas"
        print("  %-7s %-32s %-18s %d modele(s)"
              % (name, cfg["label"], state, len(models)))

    if active in ENGINES:
        other = "host" if active == "docker" else "docker"
        here, there = installed_on(active), installed_on(other)
        missing = sorted(here - there)
        if missing:
            print("\n  Une bascule vers '%s' laisserait %d modele(s) en arriere :"
                  % (other, len(missing)))
            for name in missing[:12]:
                print("    - %s" % name)
            if len(missing) > 12:
                print("    ... et %d autres" % (len(missing) - 12))
            print("\n  Ils devront etre retelecharges cote '%s'. Les poids ne sont"
                  % other)
            print("  pas transferables d'un moteur a l'autre par simple copie de")
            print("  configuration : c'est model_list.txt qui les reconstitue.")
    return 0


def switch(target: str, dry_run: bool) -> int:
    source = ENGINES[target]
    version = probe(source["probe"])
    if not version:
        print("Cible '%s' injoignable sur %s : bascule refusee."
              % (target, source["probe"]))
        print("On ne coupe pas un moteur qui fonctionne pour un moteur absent.")
        return 1
    print("Cible '%s' joignable (Ollama %s)." % (target, version))

    with io.open(CONFIG, encoding="utf-8") as fh:
        text = fh.read()
    active = current_engine(text)
    if active == target:
        print("Deja configure sur '%s' : rien a faire." % target)
        return 0

    other = ENGINES["docker" if target == "host" else "host"]["api_base"]
    occurrences = text.count(other)
    if not occurrences:
        print("Aucune adresse a reecrire — configuration deja neutre ?")
        return 1

    models = installed_on(target)
    if not models:
        print("\nAvertissement : le moteur '%s' n'a aucun modele local installe."
              % target)
        print("La bascule aboutira a une plateforme sans modele local tant que")
        print("l'inventaire n'aura pas ete retelecharge :")
        print("    .\\scripts\\Update-NexusModels.ps1 -SyncLocal")

    if dry_run:
        print("\n[Simulation] %d adresse(s) seraient reecrites :" % occurrences)
        print("    %s  ->  %s" % (other, source["api_base"]))
        return 0

    backup = CONFIG + ".avant-bascule"
    with io.open(backup, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    with io.open(CONFIG, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text.replace(other, source["api_base"]))

    print("\n%d adresse(s) reecrites vers %s" % (occurrences, source["api_base"]))
    print("Sauvegarde : %s" % backup)
    print("\nSuite :")
    print("    $env:NEXUS_OLLAMA_ENDPOINT = \"%s\"" % source["api_base"])
    print("    .\\scripts\\Update-NexusModels.ps1 -Restart")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--to", choices=sorted(ENGINES))
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.status or not args.to:
        return show_status()
    return switch(args.to, args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
