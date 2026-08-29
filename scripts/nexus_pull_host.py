# -*- coding: utf-8 -*-
"""
Télécharge sur l'hôte les modèles retenus par le plan de migration.

Pourquoi un script plutôt qu'une boucle
---------------------------------------
Le téléchargement dure des heures et se déroule sans surveillance. Trois
choses doivent donc être vraies à chaque itération, et non une seule fois
au départ :

    le disque a encore la place       un `ollama pull` qui sature le disque
                                      laisse un blob partiel et un système
                                      instable
    le modèle est exécutable ici      inutile de tirer 42 Go que la machine
                                      ne pourra pas charger
    l'échec d'un modèle n'arrête pas  le reste de la liste garde sa valeur
    la liste

Le script est relançable : ce qui est déjà présent est ignoré, ce qui a
échoué est retenté au passage suivant.

Usage :
    python scripts/nexus_pull_host.py [--liste model_list.host.txt] [--dry-run]
"""
from __future__ import annotations

import argparse
import io
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nexus_capability as capability  # noqa: E402

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

# Marge sous laquelle on s'arrête. Un disque saturé pendant un `pull` ne
# coûte pas qu'un téléchargement : il laisse un blob incomplet et met le
# système en difficulté.
RESERVE_GB = 20.0


def host_models() -> set[str]:
    try:
        result = subprocess.run(["ollama", "list"], capture_output=True,
                                text=True, timeout=60, encoding="utf-8",
                                errors="replace")
        return {l.split()[0] for l in result.stdout.splitlines()[1:] if l.strip()}
    except Exception:
        return set()


def free_disk_gb() -> float:
    import shutil
    store = os.environ.get(
        "OLLAMA_MODELS",
        os.path.join(os.path.expanduser("~"), ".ollama", "models"))
    probe = store
    while probe and not os.path.exists(probe):
        parent = os.path.dirname(probe)
        if parent == probe:
            break
        probe = parent
    try:
        return shutil.disk_usage(probe).free / (1024 ** 3)
    except Exception:
        return 0.0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--liste", default="model_list.host.txt")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    chemin = args.liste if os.path.isabs(args.liste) else os.path.join(ROOT, args.liste)
    if not os.path.exists(chemin):
        print("Liste introuvable : %s" % chemin)
        print("La produire : python scripts/nexus_migration_plan.py --write model_list.host.txt")
        return 1

    with io.open(chemin, encoding="utf-8") as fh:
        voulus = [l.strip() for l in fh
                  if l.strip() and not l.strip().startswith("#")]

    profile = capability.build_profile()
    tailles = capability.installed_models()
    presents = host_models()

    print("=" * 68)
    print(" Telechargement vers l'hote")
    print("=" * 68)
    print("  Liste          : %d modele(s)" % len(voulus))
    print("  Deja presents  : %d" % len([m for m in voulus if m in presents]))
    print("  Disque libre   : %.0f Go" % free_disk_gb())
    print()

    faits, ignores, echecs = 0, 0, []
    for i, modele in enumerate(voulus, 1):
        if modele in presents:
            print("  [%2d/%d] %-28s deja present" % (i, len(voulus), modele))
            ignores += 1
            continue

        taille = tailles.get(modele, 0.0)
        etat, motif = capability.verdict(taille, profile)
        if etat == capability.REJECT:
            print("  [%2d/%d] %-28s ecarte : %s" % (i, len(voulus), modele, motif))
            ignores += 1
            continue

        libre = free_disk_gb()
        if taille and libre - taille < RESERVE_GB:
            print("  [%2d/%d] %-28s ARRET : %.0f Go libres, %.0f Go requis + %.0f de reserve"
                  % (i, len(voulus), modele, libre, taille, RESERVE_GB))
            print("\n  Le reste de la liste attendra que de la place soit liberee.")
            break

        if args.dry_run:
            print("  [%2d/%d] %-28s a telecharger (%.1f Go)"
                  % (i, len(voulus), modele, taille))
            continue

        print("  [%2d/%d] %-28s telechargement..." % (i, len(voulus), modele), flush=True)
        debut = time.time()
        result = subprocess.run(["ollama", "pull", modele],
                                capture_output=True, text=True,
                                encoding="utf-8", errors="replace", timeout=7200)
        if result.returncode == 0:
            print("           %-28s termine en %.0f s (%.0f Go libres)"
                  % ("", time.time() - debut, free_disk_gb()), flush=True)
            faits += 1
        else:
            # Un echec ne doit pas emporter la liste : les suivants gardent
            # leur valeur, et celui-ci sera retente au prochain passage.
            message = (result.stderr or result.stdout or "").strip().splitlines()
            print("           echec : %s" % (message[-1][:80] if message else "?"))
            echecs.append(modele)

    print("\n" + "-" * 68)
    print("  Telecharges : %d    Ignores : %d    Echecs : %d"
          % (faits, ignores, len(echecs)))
    if echecs:
        print("  A retenter : %s" % ", ".join(echecs))
    print("  Disque libre : %.0f Go" % free_disk_gb())
    print("""
  Suite, dans cet ordre :
    1. python scripts/nexus_switch_engine.py --to host
    2. $env:NEXUS_OLLAMA_ENDPOINT = "http://host.docker.internal:11434"
       .\\scripts\\Update-NexusModels.ps1 -Restart
    3. python scripts/nexus_test.py
    4. SEULEMENT si tout passe : retirer COMPOSE_PROFILES de .env,
       puis docker compose down et supprimer le volume ollama_data.
""")
    return 1 if echecs else 0


if __name__ == "__main__":
    sys.exit(main())
