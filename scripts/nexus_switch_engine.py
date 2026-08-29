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
import traceback
import datetime
import tempfile

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
        "label": "Ollama sur l'hote",
    },
}


def probe(url: str) -> str | None:
    """Teste la disponibilité d'une instance Ollama et renvoie sa version."""
    try:
        with urllib.request.urlopen(url + "/api/version", timeout=8) as response:
            return json.loads(response.read().decode("utf-8")).get("version")
    except Exception as exc:  # pragma: no cover
        # On conserve la trace pour le diagnostic, mais on ne l'affiche pas
        # dans la sortie standard afin de ne pas polluer les scripts qui
        # consomment la sortie.
        sys.stderr.write(f"Probe error for {url}: {exc}\n")
        sys.stderr.write(traceback.format_exc())
        return None


def _strip_comments(text: str) -> str:
    """Supprime les lignes ou parties de lignes commentées du YAML."""
    # Retire tout ce qui suit un caractère # qui n'est pas dans une chaîne.
    # Cette approche simple suffit pour les usages du script.
    return re.sub(r"(?m)^\s*#.*\n?|(?<!['\"]).*#.*", "", text)


def current_engine(text: str) -> str:
    """Détermine le moteur actuellement configuré dans le fichier."""
    clean = _strip_comments(text)
    counts = {name: clean.count(cfg["api_base"]) for name, cfg in ENGINES.items()}
    if counts["host"] and not counts["docker"]:
        return "host"
    if counts["docker"] and not counts["host"]:
        return "docker"
    if counts["host"] and counts["docker"]:
        return "mixte"
    return "inconnu"


def installed_on(engine: str) -> set[str] | None:
    """
    Inventaire du moteur visé, pour mesurer ce qu'une bascule coûterait.

    Renvoie **None** quand l'inventaire n'a pas pu être lu — jamais un
    ensemble vide. Les deux se lisent autrement pareil, et la confusion
    est ici dangereuse : `show_status` soustrait ces deux inventaires pour
    annoncer ce qu'une bascule laisserait en arrière. Un moteur
    injoignable rendu comme « aucun modele » fait dire soit que tout
    serait perdu, soit — bien pire — que rien ne le serait, juste avant
    une bascule dont le rattrapage se compte en dizaines de gigaoctets.
    """
    import subprocess
    args = (["ollama", "list"] if engine == "host"
            else ["docker", "exec", "ollama-server", "ollama", "list"])
    try:
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=60,
            encoding="utf-8",
            errors="replace",
        )
        if result.returncode != 0:
            return None
        lines = result.stdout.splitlines()
        if not lines:
            return set()
        # La première ligne est l'en-tête, on l'ignore.
        models = set()
        for line in lines[1:]:
            line = line.strip()
            if not line:
                continue
            parts = line.split()
            if not parts:
                continue
            name = parts[0]
            if not name.endswith(":cloud"):
                models.add(name)
        return models
    except Exception as exc:  # pragma: no cover
        sys.stderr.write(f"installed_on error for {engine}: {exc}\n")
        sys.stderr.write(traceback.format_exc())
        return None


def show_status() -> int:
    with io.open(CONFIG, encoding="utf-8") as fh:
        text = fh.read()
    active = current_engine(text)

    print("=" * 66)
    print(" Moteur d'inference local")
    print("=" * 66)
    print("  Configure : %s" % active)
    versions: dict[str, str | None] = {}
    for name, cfg in ENGINES.items():
        version = probe(cfg["probe"])
        versions[name] = version
        models = installed_on(name)
        state = ("repond (v%s)" % version) if version else "ne repond pas"
        print(
            "  %-7s %-32s %-18s %s"
            % (
                name,
                cfg["label"],
                state,
                "inventaire illisible" if models is None else "%d modele(s)" % len(models),
            )
        )

    muet = active in ENGINES and not versions[active]
    if muet:
        print(
            "  ATTENTION : le moteur configure ('%s') ne repond pas sur %s."
            % (active, ENGINES[active]["probe"])
        )
        print(
            "  LiteLLM pointe vers %s : tout appel local echouera."
            % ENGINES[active]["api_base"]
        )

    if active in ENGINES:
        other = "host" if active == "docker" else "docker"
        here, there = installed_on(active), installed_on(other)
        if here is None or there is None:
            print()
            print(
                "  Ecart non calculable : l'inventaire du moteur '%s' n'a pas pu"
                % (active if here is None else other)
            )
            print(
                "  etre lu. Rien n'est affirme sur ce qu'une bascule couterait."
            )
            return 1
        missing = sorted(here - there)
        if missing:
            print("\n  Une bascule vers '%s' laisserait %d modele(s) en arriere :" % (other, len(missing)))
            for name in missing[:12]:
                print("    - %s" % name)
            if len(missing) > 12:
                print("    ... et %d autres" % (len(missing) - 12))
            print("\n  Ils devront etre retelecharges cote '%s'. Les poids ne sont" % other)
            print("  pas transferables d'un moteur a l'autre par simple copie de")
            print("  configuration : c'est model_list.txt qui les reconstitue.")

    # Retour 0 uniquement si tout est OK ; sinon 1.
    return 1 if muet else 0


def _atomic_write(path: str, data: str) -> None:
    """Ecriture atomique du fichier en utilisant un fichier temporaire."""
    dir_name = os.path.dirname(path)
    fd, tmp_path = tempfile.mkstemp(dir=dir_name, text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as tmp_file:
            tmp_file.write(data)
        os.replace(tmp_path, path)  # Remplace de façon atomique sur la plupart des OS.
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def switch(target: str, dry_run: bool) -> int:
    source = ENGINES[target]
    version = probe(source["probe"])
    if not version:
        print("Cible '%s' injoignable sur %s : bascule refusee." % (target, source["probe"]))
        print("On ne coupe pas un moteur qui fonctionne pour un moteur absent.")
        return 1
    print("Cible '%s' joignable (Ollama %s)." % (target, version))

    with io.open(CONFIG, encoding="utf-8") as fh:
        text = fh.read()
    active = current_engine(text)
    if active == target:
        print("Deja configure sur '%s' : rien a faire." % target)
        return 0

    # Dans le cas mixte, on remplace les deux URL possibles.
    other_urls = [ENGINES["docker"]["api_base"], ENGINES["host"]["api_base"]]
    other_urls.remove(source["api_base"])
    other = other_urls[0]

    occurrences = text.count(other)
    if active == "mixte":
        # Compte les deux URL qui ne sont pas la cible.
        occurrences = sum(text.count(url) for url in other_urls)

    if not occurrences:
        print("Aucune adresse a reecrire — configuration deja neutre ?")
        return 1

    models = installed_on(target)
    if models is None:
        print("\nAvertissement : l'inventaire du moteur '%s' n'a pas pu etre lu." % target)
        print("Ce que la bascule couterait est donc inconnu. Rien n'est affirme")
        print("sur les modeles presents ou absents de ce cote.")
    elif not models:
        print("\nAvertissement : le moteur '%s' n'a aucun modele local installe." % target)
        print("La bascule aboutira a une plateforme sans modele local tant que")
        print("l'inventaire n'aura pas ete retelecharge :")
        print("    .\\scripts\\Update-NexusModels.ps1 -SyncLocal")

    if dry_run:
        print("\n[Simulation] %d adresse(s) seraient reecrites :" % occurrences)
        print("    %s  ->  %s" % (other, source["api_base"]))
        return 0

    # Sauvegarde avec horodatage pour éviter l'écrasement.
    timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    backup = f"{CONFIG}.avant-bascule.{timestamp}"
    with io.open(backup, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)

    # Remplacement prudent : on ne touche pas les lignes commentées.
    pattern = re.compile(r"(?m)^(?!\s*#.*)({})".format("|".join(map(re.escape, other_urls))))
    new_text = pattern.sub(source["api_base"], text)

    # Vérification que le remplacement a bien abouti au moteur attendu.
    if current_engine(new_text) != target:
        print("Erreur : la configuration resultante ne pointe pas vers le moteur cible.")
        print("La sauvegarde a ete conserve dans %s" % backup)
        return 1

    # Ecriture atomique.
    _atomic_write(CONFIG, new_text)

    print("\n%d adresse(s) reecrites vers %s" % (occurrences, source["api_base"]))
    print("Sauvegarde : %s" % backup)
    print("\nSuite :")
    print("    python scripts/nexus_conformite.py    verifier avant de demarrer")
    print("    .\\scripts\\start.ps1 -Restart         redemarrer sous controle")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--to", choices=sorted(ENGINES))
    group.add_argument("--status", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.status or not args.to:
        return show_status()
    return switch(args.to, args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
