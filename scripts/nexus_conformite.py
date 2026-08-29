# -*- coding: utf-8 -*-
"""
Porte de conformité : tout est-il en ordre avant de (re)démarrer ?

Pourquoi ce script existe
-------------------------
`Update-NexusModels.ps1` refuse de redémarrer LiteLLM sur une
configuration invalide. Mais un `docker compose restart litellm` tapé à la
main contourne entièrement cette garde — et c'est la commande que l'on
tape réellement, plusieurs fois par jour. Une garde que le chemin le plus
court évite ne protège de rien.

Ce script est la porte unique. Il répond à une seule question — *peut-on
démarrer ?* — en interrogeant toutes les dimensions qui peuvent rendre un
démarrage nuisible, et non seulement celles que le validateur YAML couvre.

Il fonctionne **passerelle éteinte** : c'est justement l'état dans lequel
on se trouve avant un démarrage. Les contrôles qui exigent un service en
marche sont alors ignorés avec leur motif, jamais réputés réussis.

Trois niveaux, et la distinction compte :

    BLOQUANT      démarrer causerait un dommage ou une panne silencieuse
    AVERTISSEMENT démarrer fonctionnera, mais quelque chose se dégrade
    IGNORE        non vérifiable dans l'état actuel — jamais « réussi »

Usage :
    python scripts/nexus_conformite.py            # verdict complet
    python scripts/nexus_conformite.py --json
    python scripts/nexus_conformite.py --avant-demarrage   # ignore le runtime

Codes de sortie :
    0  conforme (des avertissements restent possibles)
    1  au moins un contrôle bloquant a échoué
"""
from __future__ import annotations

import argparse
import io
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nexus_capability as capability  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG = os.path.join(ROOT, "litellm_config.yaml")
ENV = os.path.join(ROOT, ".env")
PASSERELLE = os.environ.get("NEXUS_GATEWAY", "http://localhost:4000")

BLOQUANT, AVERTISSEMENT, IGNORE = "BLOQUANT", "AVERT", "IGNORE"

# Secrets sans lesquels la passerelle démarre mais ne sert rien d'utile.
# `ANTHROPIC_API_KEY` n'y figure pas : son absence est un choix de coût
# légitime, pas un défaut de conformité.
SECRETS_REQUIS = ["LITELLM_MASTER_KEY", "REDIS_PASSWORD",
                  "POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_DB"]

resultats: list[dict] = []


def noter(nom: str, ok: bool, niveau: str, detail: str = "") -> bool:
    resultats.append({"controle": nom, "ok": ok, "niveau": niveau, "detail": detail})
    return ok


def ignorer(nom: str, motif: str) -> None:
    resultats.append({"controle": nom, "ok": None, "niveau": IGNORE, "detail": motif})


# ----------------------------------------------------------------------
# Contrôles statiques — ne demandent aucun service en marche
# ----------------------------------------------------------------------
def controle_config_valide() -> None:
    """Le validateur d'intégrité, tel quel : il est déjà la référence."""
    r = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "nexus_validate.py")],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    erreurs = [l.strip() for l in r.stdout.splitlines() if l.strip().startswith("- ")]
    noter("configuration valide", r.returncode == 0, BLOQUANT,
          "%d erreur(s) : %s" % (len(erreurs), "; ".join(e[2:] for e in erreurs[:3]))
          if r.returncode != 0 else "")


def controle_moteur_coherent() -> None:
    """
    Toutes les déclarations locales visent-elles le MÊME moteur ?

    Une configuration mélangeant `http://ollama:11434` et
    `http://host.docker.internal:11434` n'est pas invalide au sens YAML :
    elle est simplement à moitié fausse. Les modèles pointant vers le
    moteur absent répondent 404 un par un, sans que rien ne relie ces
    échecs entre eux. C'est arrivé ici — dix déclarations réécrites vers
    un conteneur supprimé par une régénération lancée sans variable
    d'environnement.
    """
    try:
        texte = io.open(CONFIG, encoding="utf-8").read()
    except Exception as exc:
        noter("moteur coherent", False, BLOQUANT, "configuration illisible : %s" % exc)
        return
    docker = texte.count("http://ollama:11434")
    hote = texte.count("host.docker.internal:11434")
    if docker and hote:
        noter("moteur coherent", False, BLOQUANT,
              "configuration partagee : %d declaration(s) vers le conteneur, "
              "%d vers l'hote" % (docker, hote))
    else:
        noter("moteur coherent", True, BLOQUANT,
              "%d declaration(s) vers %s" % (docker or hote,
                                             "le conteneur" if docker else "l'hote"))


def controle_moteur_joignable() -> None:
    """
    Le moteur que la configuration désigne répond-il réellement ?

    Démarrer LiteLLM devant un moteur éteint produit une passerelle qui
    accepte les requêtes et les échoue toutes — le pire des deux états,
    puisqu'elle a l'air en marche.
    """
    lieu = capability.ollama_location()
    sonde = ("http://127.0.0.1:11434" if lieu.get("host_native")
             else "http://127.0.0.1:11435")
    try:
        with urllib.request.urlopen(sonde + "/api/version", timeout=10) as reponse:
            version = json.loads(reponse.read().decode("utf-8")).get("version", "?")
        noter("moteur joignable", True, BLOQUANT,
              "%s sur %s (Ollama %s)" % (lieu.get("mode"), sonde, version))
    except Exception as exc:
        noter("moteur joignable", False, BLOQUANT,
              "%s injoignable (%s)" % (sonde, exc))


def controle_marqueurs_autogen() -> None:
    """
    Les zones générées sont-elles bien fermées, et une seule fois chacune ?

    Un marqueur ouvrant sans fermant fait avaler au générateur tout ce qui
    suit ; un marqueur en double lui fait écrire deux fois au même endroit.
    Dans les deux cas la configuration reste un YAML valide, et la perte ne
    se voit qu'à l'exécution.
    """
    try:
        texte = io.open(CONFIG, encoding="utf-8").read()
    except Exception as exc:
        noter("marqueurs AUTOGEN", False, BLOQUANT, str(exc))
        return
    ouverts = re.findall(r"#\s*>>>\s*AUTOGEN:(\S+)", texte)
    fermes = re.findall(r"#\s*<<<\s*AUTOGEN:(\S+)", texte)
    soucis = []
    for nom in set(ouverts) | set(fermes):
        if ouverts.count(nom) != 1 or fermes.count(nom) != 1:
            soucis.append("%s (%d ouvrant, %d fermant)"
                          % (nom, ouverts.count(nom), fermes.count(nom)))
    noter("marqueurs AUTOGEN", not soucis, BLOQUANT,
          "; ".join(soucis) if soucis else "%d zone(s) appariees" % len(set(ouverts)))


def controle_secrets() -> None:
    """Les variables sans lesquelles la pile démarre sans servir."""
    if not os.path.exists(ENV):
        noter("secrets presents", False, BLOQUANT,
              ".env absent — copier .env.example et le remplir")
        return
    try:
        contenu = io.open(ENV, encoding="utf-8", errors="replace").read()
    except OSError as exc:
        noter("secrets presents", False, BLOQUANT, ".env illisible : %s" % exc)
        return
    manquants = []
    for nom in SECRETS_REQUIS:
        m = re.search(r"^\s*%s\s*=\s*(.*)$" % re.escape(nom), contenu, re.M)
        # Une variable declaree vide ne vaut pas mieux qu'absente : elle
        # part telle quelle dans l'en-tete et produit un 401 que rien
        # n'explique.
        if not m or not m.group(1).strip().strip("\"'"):
            manquants.append(nom)
    noter("secrets presents", not manquants, BLOQUANT,
          "manquants ou vides : %s" % ", ".join(manquants) if manquants
          else "%d variable(s) renseignees" % len(SECRETS_REQUIS))


def controle_env_hors_git() -> None:
    """
    `.env` est-il resté hors de l'index git ?

    Le contrôle est refait à chaque démarrage plutôt qu'une fois pour
    toutes : un `git add -A` suffit à l'y faire entrer, et une fois
    poussé, un secret est compromis même supprimé au commit suivant.
    """
    r = subprocess.run(["git", "ls-files", "--error-unmatch", ".env"],
                       cwd=ROOT, capture_output=True, text=True)
    suivi = r.returncode == 0
    noter(".env hors de git", not suivi, BLOQUANT,
          "SUIVI PAR GIT — retirer avec 'git rm --cached .env'" if suivi
          else "non suivi")


def controle_disque() -> None:
    profil = capability.build_profile()
    libre = profil.get("free_disk_gb", 0.0)
    noter("espace disque", libre >= 15.0, AVERTISSEMENT,
          "%.0f Go libres%s" % (libre, "" if libre >= 15 else " — insuffisant pour un pull"))


# ----------------------------------------------------------------------
# Contrôles runtime — exigent la passerelle en marche
# ----------------------------------------------------------------------
def passerelle_vivante() -> bool:
    try:
        with urllib.request.urlopen(PASSERELLE + "/health/liveliness", timeout=5):
            return True
    except Exception:
        return False


def controle_runtime(avant_demarrage: bool) -> None:
    if avant_demarrage:
        ignorer("releve operationnelle", "controle avant demarrage")
        return
    if not passerelle_vivante():
        # Non vérifiable n'est pas réussi : le distinguer évite de conclure
        # à une relève opérationnelle parce que personne n'a pu la tester.
        ignorer("releve operationnelle", "passerelle eteinte sur %s" % PASSERELLE)
        return
    r = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "nexus_releve.py")],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    ligne = next((l.strip() for l in r.stdout.splitlines() if "epreuves reussies" in l), "")
    noter("releve operationnelle", r.returncode == 0, AVERTISSEMENT,
          ligne or "voir python scripts/nexus_releve.py")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--avant-demarrage", action="store_true",
                   help="ignore les controles exigeant la passerelle en marche")
    p.add_argument("--json", action="store_true")
    a = p.parse_args()

    for controle in (controle_config_valide, controle_moteur_coherent,
                     controle_moteur_joignable, controle_marqueurs_autogen,
                     controle_secrets, controle_env_hors_git, controle_disque):
        try:
            controle()
        except Exception as exc:
            # Un contrôle qui plante ne doit pas se lire comme un contrôle
            # réussi : il devient bloquant, faute de pouvoir conclure.
            noter(controle.__name__, False, BLOQUANT, "controle en erreur : %s" % exc)
    controle_runtime(a.avant_demarrage)

    if a.json:
        print(json.dumps(resultats, ensure_ascii=False, indent=2))

    bloquants = [r for r in resultats if r["ok"] is False and r["niveau"] == BLOQUANT]
    alertes = [r for r in resultats if r["ok"] is False and r["niveau"] == AVERTISSEMENT]

    if not a.json:
        print("=" * 72)
        print(" Conformite Claude-Local-Nexus")
        print("=" * 72)
        for r in resultats:
            if r["ok"] is None:
                marque = "[IGNORE]"
            elif r["ok"]:
                marque = "[  OK  ]"
            else:
                marque = "[BLOQUE]" if r["niveau"] == BLOQUANT else "[ALERTE]"
            print("  %s %-26s %s" % (marque, r["controle"], r["detail"][:120]))
        print()
        if bloquants:
            print("  => NON CONFORME : %d controle(s) bloquant(s)." % len(bloquants))
            print("     Ne pas demarrer avant correction.")
        elif alertes:
            print("  => Conforme, avec %d avertissement(s)." % len(alertes))
        else:
            print("  => Conforme.")
        print("=" * 72)
    return 1 if bloquants else 0


if __name__ == "__main__":
    sys.exit(main())
