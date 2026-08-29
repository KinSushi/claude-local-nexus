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


def installed_on(engine: str) -> set[str] | None:
    """
    Inventaire du moteur visé, pour mesurer ce qu'une bascule coûterait.

    Renvoie **None** quand l'inventaire n'a pas pu être lu — jamais un
    ensemble vide. Les deux se lisent autrement pareil, et la confusion
    est ici dangereuse : `show_status` soustrait ces deux inventaires pour
    annoncer ce qu'une bascule laisserait en arrière. Un moteur
    injoignable rendu comme « aucun modèle » fait dire soit que tout
    serait perdu, soit — bien pire — que rien ne le serait, juste avant
    une bascule dont le rattrapage se compte en dizaines de gigaoctets.
    """
    import subprocess
    args = (["ollama", "list"] if engine == "host"
            else ["docker", "exec", "ollama-server", "ollama", "list"])
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=60,
                                encoding="utf-8", errors="replace")
        if result.returncode != 0:
            return None
        return {line.split()[0] for line in result.stdout.splitlines()[1:]
                if line.strip() and not line.split()[0].endswith(":cloud")}
    except Exception:
        return None


def show_status() -> int:
    with io.open(CONFIG, encoding="utf-8") as fh:
        text = fh.read()
    active = current_engine(text)

    print("=" * 66)
    print(" Moteur d'inference local")
    print("=" * 66)
    print("  Configure : %s" % active)
    # La sonde est un appel reseau : son resultat est retenu au lieu d'etre
    # rejoue plus bas pour le code de retour. Deux sondes successives
    # peuvent differer, et le code de retour contredirait alors la ligne
    # qui vient d'etre affichee -- un diagnostic qui se dement lui-meme
    # coute plus de temps qu'il n'en fait gagner.
    versions: dict[str, str | None] = {}
    for name, cfg in ENGINES.items():
        version = probe(cfg["probe"])
        versions[name] = version
        models = installed_on(name)
        state = ("repond (v%s)" % version) if version else "ne repond pas"
        print("  %-7s %-32s %-18s %s"
              % (name, cfg["label"], state,
                 "inventaire illisible" if models is None
                 else "%d modele(s)" % len(models)))

    # L'alerte est placee juste sous le tableau, et non en fin de sortie :
    # RESUME.ps1 tronque a `Select-Object -First 8` et Initialize-Nexus.ps1
    # a `-First 6`, si bien qu'un avertissement final ne serait jamais lu
    # par les deux seuls appelants du mode --status.
    #
    # Seul le moteur CONFIGURE comme actif compte. L'autre est muet en
    # permanence dans une installation normale, et le signaler ferait
    # echouer chaque reprise sur un fait sans consequence.
    muet = active in ENGINES and not versions[active]
    if muet:
        print("  ATTENTION : le moteur configure ('%s') ne repond pas sur %s."
              % (active, ENGINES[active]["probe"]))
        print("  LiteLLM pointe vers %s : tout appel local echouera."
              % ENGINES[active]["api_base"])

    if active in ENGINES:
        other = "host" if active == "docker" else "docker"
        here, there = installed_on(active), installed_on(other)
        if here is None or there is None:
            # Sans les deux inventaires, l'ecart n'est pas calculable. Se
            # taire vaut mieux que l'inventer : annoncer « rien ne serait
            # perdu » sur une mesure absente est precisement le message
            # qui ferait basculer sans precaution.
            print()
            print("  Ecart non calculable : l'inventaire du moteur '%s' n'a pas pu"
                  % (active if here is None else other))
            print("  etre lu. Rien n'est affirme sur ce qu'une bascule couterait.")
            return 1
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

    # Rendre 0 quel que soit l'etat constate revient a dire « tout va bien »
    # a un appelant automatise, et c'est le seul signal dont il dispose : ni
    # RESUME.ps1 ni Initialize-Nexus.ps1 ne testent $LASTEXITCODE, faute
    # d'avoir quoi que ce soit a tester. Un moteur disparu -- conteneur
    # arrete, service de l'hote non redemarre apres Windows -- passait ainsi
    # inapercu jusqu'au premier appel de modele.
    return 1 if muet else 0


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
    # La variable d'environnement n'est plus necessaire : le generateur
    # deduit le moteur de la configuration en place. La conseiller ici
    # entretenait l'idee inverse, et l'oublier une fois a suffi pour que
    # dix declarations soient reecrites vers un conteneur supprime.
    print("\nSuite :")
    print("    python scripts/nexus_conformite.py    verifier avant de demarrer")
    print("    .\\scripts\\start.ps1 -Restart         redemarrer sous controle")
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
