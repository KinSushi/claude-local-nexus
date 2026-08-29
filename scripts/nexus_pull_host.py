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
    python scripts/nexus_pull_host.py               # comble ce qui manque
    python scripts/nexus_pull_host.py --dry-run     # simule
    python scripts/nexus_pull_host.py --liste model_list.host.txt
"""
from __future__ import annotations

import argparse
import io
import json
import os
import re
import subprocess
import sys
import time
import urllib.request

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
RESERVE_GB = float(os.getenv("NEXUS_RESERVE_GB", "20.0"))  # configurable via env


def host_models() -> set[str]:
    """
    Retourne l'ensemble des modèles déjà présents sur l'hôte.

    Capture uniquement les exceptions attendues afin de ne pas masquer
    d'éventuelles erreurs de programmation.
    """
    try:
        result = subprocess.run(
            ["ollama", "list"],
            capture_output=True,
            text=True,
            timeout=60,
            encoding="utf-8",
            errors="replace",
        )
        return {l.split()[0] for l in result.stdout.splitlines()[1:] if l.strip()}
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError):
        return set()


def free_disk_gb() -> float | None:
    """
    Retourne l'espace disque libre (en Go) du répertoire OLLAMA_MODELS ou du
    répertoire utilisateur par défaut.

    En cas d'échec (ex. point de montage inaccessible, permissions
    insuffisantes), la fonction renvoie ``None`` au lieu de ``0.0``.
    Retourner 0.0 masquerait une mesure indéterminée et ferait croire que le
    disque est plein, ce qui bloquerait indûment les téléchargements même si
    de l'espace est disponible. En renvoyant ``None`` on indique explicitement
    que la capacité n'a pas pu être mesurée, laissant l'opérateur décider
    de la suite.
    """
    import shutil

    store = os.environ.get(
        "OLLAMA_MODELS",
        os.path.join(os.path.expanduser("~"), ".ollama", "models"),
    )
    probe = store
    while probe and not os.path.exists(probe):
        parent = os.path.dirname(probe)
        if parent == probe:
            break
        probe = parent
    try:
        return shutil.disk_usage(probe).free / (1024 ** 3)
    except Exception:
        return None


def _valide_modele(modele: str) -> bool:
    """
    Valide le format du nom de modèle avant de l'utiliser dans une URL.
    Seuls les caractères alphanumériques, ``-``, ``_``, ``.``, ``:``, ``/``
    sont autorisés.
    """
    return re.fullmatch(r"[A-Za-z0-9_\-./:]+", modele) is not None


def taille_registre(modele: str) -> float | None:
    """
    Poids annoncé par le registre Ollama, en Go, avant tout téléchargement.

    Retourne ``None`` si le registre ne répond pas ou si le nom du modèle
    ne passe pas la validation. Cela permet au code appelant de traiter
    l'absence d'information comme un cas prudent (ignoré).
    """
    if not _valide_modele(modele):
        return None

    nom, _, tag = modele.partition(":")
    url = f"https://registry.ollama.ai/v2/library/{nom}/manifests/{tag or 'latest'}"
    requete = urllib.request.Request(
        url,
        headers={"Accept": "application/vnd.docker.distribution.manifest.v2+json"},
    )
    try:
        with urllib.request.urlopen(requete, timeout=30) as reponse:
            manifeste = json.loads(reponse.read().decode("utf-8"))
        octets = sum(couche.get("size", 0) for couche in manifeste.get("layers", []))
        return octets / 1e9
    except Exception:
        return None


def declares_sans_poids() -> list[str] | None:
    """
    Modèles que la configuration déclare et que le moteur ne sert pas.

    La liste figée `model_list.host.txt` décrit une intention prise à un
    instant donné ; la configuration, elle, décrit ce que LiteLLM va
    réellement router. Les deux ont divergé dès la première suppression de
    volume : le validateur signalait six alias sans poids pendant que le
    script de téléchargement annonçait « rien à faire ». Deux sources pour
    une même question, et donc deux réponses.

    Cette fonction pose la question à la même source que le validateur, ce
    qui rend le désaccord impossible plutôt que simplement improbable.

    Renvoie None si l'inventaire est illisible — jamais une liste vide,
    qui se lirait comme « tout est là ».
    """
    presents = capability.installed_models()
    if presents is None:
        return None
    canon = {n[:-len(":latest")] if n.endswith(":latest") else n for n in presents}
    canon |= set(presents)

    # La configuration est analysée, pas balayée par expression régulière.
    # Une première version cherchait `model: ollama_chat/...` suivi de ses
    # lignes indentées : le motif débordait sur les blocs voisins, y
    # trouvait un `api_base: https://ollama.com`, et classait donc TOUT
    # comme cloud — le script annonçait « rien ne manque » pendant que le
    # validateur listait six absents. Le YAML dit sans ambiguïté où
    # commence et finit un bloc.
    config = os.path.join(ROOT, "litellm_config.yaml")
    try:
        import yaml

        with io.open(config, encoding="utf-8") as fh:
            cfg = yaml.safe_load(fh)
    except Exception:
        return None

    manquants: list[str] = []
    for entree in (cfg.get("model_list") or []):
        params = entree.get("litellm_params") or {}
        cible = str(params.get("model", ""))
        if not cible.startswith(("ollama/", "ollama_chat/")):
            continue
        # Les modèles Ollama Cloud portent la même syntaxe et ne s'installent
        # pas localement : les inclure ferait télécharger sans fin des poids
        # qui n'existent pas côté hôte.
        if "ollama.com" in str(params.get("api_base", "")):
            continue
        cible = cible.split("/", 1)[1]
        base = cible[:-len(":latest")] if cible.endswith(":latest") else cible
        if cible in canon or base in canon:
            continue
        if cible not in manquants:
            manquants.append(cible)
    return manquants


def _format_free(free: float | None) -> str:
    """Retourne une représentation texte de l'espace libre ou 'inconnu'."""
    return f"{free:.0f}" if free is not None else "inconnu"


def main() -> int:
    parser = argparse.ArgumentParser()
    # Le comportement par defaut est de combler ce qui MANQUE reellement,
    # deduit de la configuration. La liste figee est devenue l'option
    # explicite, et l'inversion vient d'un incident : lancee sans option,
    # la version precedente lisait `model_list.host.txt` -- produit quand
    # le disque etait plein, donc reduit a quatre entrees toutes deja
    # presentes -- et annoncait "0 a telecharger, 4 deja presents" pendant
    # que le validateur listait six absents. Rien n'etait faux dans ce
    # message, et il induisait pourtant en erreur : le chemin le plus
    # court doit etre le chemin correct.
    parser.add_argument(
        "--liste",
        metavar="FICHIER",
        help="Lire une liste figee au lieu de deduire les manquants de la configuration.",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--manquants",
        action="store_true",
        help="Comportement par defaut, conserve pour compatibilite.",
    )
    args = parser.parse_args()

    if not args.liste:
        voulus = declares_sans_poids()
        if voulus is None:
            print("Inventaire du moteur illisible : impossible de savoir ce qui manque.")
            return 1
        if not voulus:
            print("Aucun modele declare ne manque sur le moteur.")
            return 0
    else:
        chemin = args.liste if os.path.isabs(args.liste) else os.path.join(ROOT, args.liste)
        if not os.path.exists(chemin):
            print("Liste introuvable : %s" % chemin)
            print(
                "La produire : python scripts/nexus_migration_plan.py --write model_list.host.txt"
            )
            return 1

        with io.open(chemin, encoding="utf-8") as fh:
            voulus = [l.strip() for l in fh if l.strip() and not l.strip().startswith("#")]

    profile = capability.build_profile()
    tailles = capability.installed_models()
    presents = host_models()

    print("=" * 68)
    print(" Telechargement vers l'hote")
    print("=" * 68)
    print("  Liste          : %d modele(s)" % len(voulus))
    print("  Deja presents  : %d" % len([m for m in voulus if m in presents]))
    free_initial = free_disk_gb()
    print("  Disque libre   : %s Go" % _format_free(free_initial))
    print()

    faits, ignores, echecs = 0, 0, []
    # Un arret par manque de place ne remplit ni `ignores` ni
    # `echecs` : sans ce drapeau, l'epilogue concluait "tout est en
    # place" apres s'etre arrete au premier modele.
    interrompu = False
    libre_simule = free_disk_gb()
    for i, modele in enumerate(voulus, 1):
        if modele in presents:
            print("  [%2d/%d] %-28s deja present" % (i, len(voulus), modele))
            ignores += 1
            continue

        taille = tailles.get(modele, None)
        if taille is None:
            # Un modèle absent n'a pas de poids mesurable localement : on le
            # demande au registre AVANT de tirer, sinon le contrôle de place
            # ci-dessous compare le disque libre à zéro et laisse tout passer.
            taille = taille_registre(modele)
        if taille is None:
            print(
                "  [%2d/%d] %-28s poids inconnu : refuse par prudence"
                % (i, len(voulus), modele)
            )
            ignores += 1
            continue
        etat, motif = capability.verdict(taille, profile)
        if etat == capability.REJECT:
            print("  [%2d/%d] %-28s ecarte : %s" % (i, len(voulus), modele, motif))
            ignores += 1
            continue

        # En simulation, rien n'est écrit : `free_disk_gb()` rendrait la même
        # valeur à chaque tour et l'essai à blanc annoncerait six
        # téléchargements là où un seul tient. Une simulation qui ne prédit
        # pas l'arrêt ne prépare à rien.
        libre = libre_simule if args.dry_run else free_disk_gb()
        if taille and libre is not None and libre - taille < RESERVE_GB:
            print(
                "  [%2d/%d] %-28s ARRET : %.0f Go libres, %.0f Go requis + %.0f de reserve"
                % (i, len(voulus), modele, libre, taille, RESERVE_GB)
            )
            print("\n  Le reste de la liste attendra que de la place soit liberee.")
            interrompu = True
            break

        if args.dry_run:
            if libre_simule is not None:
                libre_simule -= taille
            print(
                "  [%2d/%d] %-28s a telecharger (%.1f Go, resterait %.0f Go)"
                % (
                    i,
                    len(voulus),
                    modele,
                    taille,
                    libre_simule if libre_simule is not None else float("nan"),
                )
            )
            continue

        print("  [%2d/%d] %-28s telechargement..." % (i, len(voulus), modele), flush=True)
        debut = time.time()
        result = subprocess.run(
            ["ollama", "pull", modele],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=7200,
        )
        if result.returncode == 0:
            free_now = free_disk_gb()
            print(
                "           %-28s termine en %.0f s (%s Go libres)"
                % ("", time.time() - debut, _format_free(free_now)),
                flush=True,
            )
            faits += 1
        else:
            # Un echec ne doit pas emporter la liste : les suivants gardent
            # leur valeur, et celui-ci sera retente au prochain passage.
            message = (result.stderr or result.stdout or "").strip().splitlines()
            print("           echec : %s" % (message[-1][:80] if message else "?"))
            echecs.append(modele)

    print("\n" + "-" * 68)
    print("  Telecharges : %d    Ignores : %d    Echecs : %d" % (faits, ignores, len(echecs)))
    if echecs:
        print("  A retenter : %s" % ", ".join(echecs))
    print("  Disque libre : %s Go" % _format_free(free_disk_gb()))
    # L'épilogue suit l'état réel du moteur. Il décrivait auparavant la
    # migration vers l'hôte en toutes circonstances : une fois celle-ci
    # faite, il conseillait de la refaire, dont une suppression de volume
    # déjà supprimé. Une consigne périmée qui se présente comme la suite à
    # donner est plus nuisible qu'une absence de consigne.
    lieu = capability.ollama_location()
    if not lieu.get("host_native"):
        print(
            """
  Suite, dans cet ordre :
    1. python scripts/nexus_switch_engine.py --to host
    2. .\\scripts\\Update-NexusModels.ps1 -Restart
    3. python scripts/nexus_test.py
    4. SEULEMENT si tout passe : retirer COMPOSE_PROFILES de .env,
       puis docker compose down et supprimer le volume ollama_data.
"""
        )
    elif echecs or interrompu:
        print(
            """
  Suite :
    python scripts/nexus_conformite.py        ce qui manque encore
    python scripts/nexus_pull_host.py         relancer apres liberation
"""
        )
    else:
        print(
            """
  Suite :
    python scripts/nexus_validate.py
    .\\scripts\\Update-NexusModels.ps1 -Restart
"""
        )
    return 1 if echecs else 0


if __name__ == "__main__":
    sys.exit(main())
