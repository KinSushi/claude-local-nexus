#!/usr/bin/env python3
"""
Module nexus_bench
Ce script mesure la latence des modeles locaux exposes par la passerelle Nexus.
Il genere un releve (latences.json) que le generateur lira pour decide quels
modeles entrer dans les pools de routage.

CE QUE CE BANC MESURE, ET CE QU'IL NE MESURE PAS
------------------------------------------------
Il demande seize jetons. Il mesure donc le delai avant de COMMENCER a
repondre, pas le debit sur une tache reelle. Un modele prompt a rendre
« PRET » peut ramer sur deux mille jetons.

Le critere de promotion bati sur ce releve est par consequent NECESSAIRE et
NON SUFFISANT : un modele trop lent a demarrer est inutilisable, mais un
modele rapide a demarrer n'est pas pour autant prouve utilisable. Un modele
admis ici puis lent en production est un defaut du critere, pas du releve ;
le remede est un second banc en jetons par seconde, pas un retour au comptage
des parametres.

Deux precautions, apprises a leurs depens :

* Le cache exact de Redis est neutralise (no-cache / no-store). Sans cela le
  second appel mesure le cache et non le modele -- observe : phi3-mini rendu
  a « 2,1 s » mesurait en realite 8,6 s.
* Le chargement des poids et le regime etabli sont chronometres separement.
  Les confondre attribue au modele, definitivement, un cout paye une fois.
"""

import os
import sys
import json
import time
import argparse
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

# ----- fonctions utilitaires -------------------------------------------------
def charger_env(racine: Path) -> dict:
    """Lire le fichier .env a la racine et retourner un dictionnaire."""
    env_path = racine / ".env"
    env = {}
    if env_path.is_file():
        with env_path.open(encoding="utf-8") as f:
            for ligne in f:
                ligne = ligne.strip()
                if not ligne or ligne.startswith("#"):
                    continue
                if "=" in ligne:
                    cle, val = ligne.split("=", 1)
                    env[cle.strip()] = val.strip()
    return env

# Clef de la passerelle, posee une fois pour toutes les requetes.
#
# La lire sans la transmettre donnait un 401, rapporte comme « impossible de
# joindre la passerelle » : le message envoyait chercher une panne reseau la
# ou l'appel etait simplement refuse.
CLEF = {"valeur": ""}


def _entetes() -> dict:
    entetes = {"Content-Type": "application/json"}
    if CLEF["valeur"]:
        entetes["Authorization"] = "Bearer " + CLEF["valeur"]
    return entetes


def appel_get(url: str, timeout: float) -> dict:
    """Effectuer un GET et retourner le JSON decode."""
    req = urllib.request.Request(url, method="GET", headers=_entetes())
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = resp.read()
        return json.loads(data.decode("utf-8"))

def appel_post(url: str, payload: dict, timeout: float) -> dict:
    """Effectuer un POST avec le payload JSON et retourner le JSON decode."""
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST", headers=_entetes())
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = resp.read()
        return json.loads(body.decode("utf-8"))

def est_embedding(nom: str) -> bool:
    """Detecter les modeles d'embedding par leur nom."""
    nom_lower = nom.lower()
    return any(tok in nom_lower for tok in ("embed", "minilm", "bge"))

def mesurer_latence(gateway: str, alias: str, timeout: float) -> tuple:
    """
    Mesure un modele DEUX fois, et rend (chargement_ms, etabli_ms, ok, motif).

    Une mesure unique confond deux grandeurs tres differentes. Un modele local
    doit d'abord etre charge en memoire, ce qui domine le premier appel :
    constate le 30 aout 2026, phi3-mini-local a depasse 60 s au premier appel
    apres qu'un autre modele eut occupe la RAM, puis a rendu en 8,6 s au
    suivant. Promouvoir ou ecarter sur le seul premier chiffre reviendrait a
    juger un modele sur son reveil.

    Le cache reste neutralise sur les deux appels : le second recalcule
    vraiment, il ne relit pas la reponse du premier.
    """
    if est_embedding(alias):
        return (None, None, False, "non applicable")
    url = f"{gateway.rstrip('/')}/v1/chat/completions"
    payload = {
        "model": alias,
        "messages": [{"role": "user", "content": "Repond par le seul mot: PRET"}],
        "max_tokens": 16,
        # Cache desactive en LECTURE et en ECRITURE. Une mesure servie par un
        # cache ne mesure que le cache -- constate : 2,1 s annonces pour un
        # modele qui en demande 8,6. Et y ecrire fausserait les mesures
        # suivantes, celles des autres modeles comprises.
        "cache": {"no-cache": True, "no-store": True},
    }

    def _un_appel():
        depart = time.monotonic()
        try:
            appel_post(url, payload, timeout)
            return int((time.monotonic() - depart) * 1000), True, ""
        except urllib.error.URLError as exc:
            duree = int((time.monotonic() - depart) * 1000)
            if isinstance(exc.reason, (TimeoutError, socket.timeout)):
                return int(timeout * 1000), False, "timeout"
            return duree, False, str(exc.reason)
        except Exception as exc:
            return int((time.monotonic() - depart) * 1000), False, str(exc)

    charge_ms, ok1, motif1 = _un_appel()
    if not ok1:
        return (charge_ms, None, False, motif1)

    # Un modele qui repond une fois puis echoue n'est pas fiable : on ne
    # retient pas le premier chiffre comme s'il avait tenu.
    etabli_ms, ok2, motif2 = _un_appel()
    if not ok2:
        return (charge_ms, None, False, motif2)
    return (charge_ms, etabli_ms, True, "")

def latences_existantes(racine) -> dict:
    """
    Releve deja sur disque, ou dictionnaire vide.

    Permet de reprendre une mesure interrompue sans refaire ce qui a ete
    mesure. Ne leve jamais : un fichier absent ou abime doit conduire a
    tout remesurer, pas a s'arreter.
    """
    chemin = racine / ".nexus" / "latences.json"
    try:
        with chemin.open(encoding="utf-8") as fh:
            donnees = json.load(fh)
        modeles = donnees.get("modeles")
        if isinstance(modeles, dict):
            return modeles
    except Exception:
        pass
    return {}


def ecrire_json(racine: Path, mesures: dict):
    """Ecrire le fichier latences.json avec encodage UTF-8 explicite."""
    sortie_dir = racine / ".nexus"
    sortie_dir.mkdir(parents=True, exist_ok=True)
    sortie_path = sortie_dir / "latences.json"
    with sortie_path.open("w", encoding="utf-8") as f:
        json.dump(mesures, f, ensure_ascii=False, indent=2)

def afficher_tableau(resultats: dict):
    """Afficher un tableau simple alias, secondes, verdict."""
    entete = f"{'Alias':30} {'Secondes':>10} {'Verdict':>20}"
    print(entete)
    print("-" * len(entete))
    for alias, info in resultats.items():
        lat = info.get("latence_ms")
        sec = f"{lat/1000:.3f}" if lat is not None else "N/A"
        # Trois verdicts et non deux : un embedding ne repond pas a un
        # endpoint de conversation, ce n'est pas un echec de sa part. Le
        # confondre avec une panne le ferait ecarter des pools pour une
        # raison fausse.
        if info.get("motif") == "non applicable":
            verdict = "N/A (embedding)"
        elif info["ok"]:
            verdict = "OK"
        else:
            verdict = f"FAIL ({info['motif']})"
        print(f"{alias:30} {sec:>10} {verdict:>20}")

# ----- corps principal -------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Mesure de latence des modeles locaux")
    parser.add_argument("--timeout", type=float, help="Timeout en secondes (defaut 90)")
    parser.add_argument("--json", action="store_true", help="Afficher le JSON de sortie")
    parser.add_argument("--modele", action="append", help="Alias du modele a tester (repetable)")
    parser.add_argument("--plan", choices=("local", "cloud", "tous"),
                        default="local",
                        help="Plan a mesurer. Le plan anthropic est exclu : "
                             "il est le seul facture au jeton.")
    args = parser.parse_args()

    # determiner la racine (parent du repertoire du script)
    script_path = Path(__file__).resolve()
    racine = script_path.parent.parent

    # charger .env
    env = charger_env(racine)
    CLEF["valeur"] = os.getenv("LITELLM_MASTER_KEY", env.get("LITELLM_MASTER_KEY", ""))
    gateway = os.getenv("NEXUS_GATEWAY", env.get("NEXUS_GATEWAY", "http://localhost:4000"))
    timeout_defaut = float(os.getenv("NEXUS_BENCH_TIMEOUT", env.get("NEXUS_BENCH_TIMEOUT", "90")))
    timeout = args.timeout if args.timeout is not None else timeout_defaut

    # recuperer la liste des modeles
    try:
        info = appel_get(f"{gateway.rstrip('/')}/model/info", timeout)
    except urllib.error.HTTPError as exc:
        # Distinguer le refus de l'injoignable : le premier se corrige dans
        # .env, le second en demarrant la pile. Les confondre envoie
        # chercher au mauvais endroit -- c'est arrive.
        sys.stderr.write("Passerelle joignable mais refus HTTP %s : verifier "
                         "LITELLM_MASTER_KEY dans .env\n" % exc.code)
        sys.exit(1)
    except Exception as exc:
        sys.stderr.write("Passerelle injoignable sur %s : %s\n" % (gateway, exc))
        sys.exit(1)

    # Le plan mesure. Le banc ne couvrait que le local, si bien que le pool
    # cloud restait ordonne sans mesure -- le defaut meme corrige cote local.
    #
    # Le plan anthropic est exclu SANS OPTION pour l'activer : il est le seul
    # facture au jeton, et mesurer coute des appels. Un banc qui peut
    # depenser n'a pas sa place dans un depot dont le produit est de ne pas
    # depenser.
    suffixes = {"local": ("-local",), "cloud": ("-cloud",),
                "tous": ("-local", "-cloud")}[args.plan]
    modeles = [m["model_name"] for m in info.get("data", [])
               if m.get("model_name", "").endswith(suffixes)
               and not m.get("model_name", "").startswith("adaptive-router")]
    if not modeles:
        sys.stderr.write("Aucun modele %s trouve." % args.plan + chr(10))
        sys.exit(1)

    # filtrer selon --modele si fourni
    if args.modele:
        modeles = [m for m in modeles if m in args.modele]
        if not modeles:
            sys.stderr.write("Aucun des modeles demandes n'est disponible.\n")
            sys.exit(1)

    # Le releve existant est REPRIS, pas ecrase.
    #
    # Mesurer quarante modeles demande des heures. La version precedente
    # n'ecrivait qu'a la fin : une interruption perdait tout le travail --
    # constate. On repart donc de ce qui existe, et on ecrit apres CHAQUE
    # modele. Une mesure faite est une mesure gardee.
    resultats = dict(latences_existantes(racine))
    for alias in modeles:
        charge_ms, etabli_ms, ok, motif = mesurer_latence(gateway, alias, timeout)
        resultats[alias] = {
            # latence_ms reste la clef lue par nexus_generate : c'est le
            # REGIME ETABLI qui decide de l'admission au pool, le cout de
            # chargement etant paye une fois et non a chaque requete.
            "latence_ms": etabli_ms if etabli_ms is not None else charge_ms,
            "latence_chargement_ms": charge_ms,
            "latence_etablie_ms": etabli_ms,
            "ok": ok,
            "motif": motif,
        }
        # Ecriture immediate : le prochain arret n'effacera que la mesure en
        # cours, jamais celles qui la precedent.
        ecrire_json(racine, {
            "mesure_le": datetime.now(timezone.utc).isoformat(),
            "modeles": resultats,
        })

    # ecrire le fichier json
    mesures = {
        "mesure_le": datetime.now(timezone.utc).isoformat(),
        "modeles": resultats,
    }
    ecrire_json(racine, mesures)

    # affichage
    afficher_tableau(resultats)
    if args.json:
        print(json.dumps(mesures, ensure_ascii=False, indent=2))

    sys.exit(0)

if __name__ == "__main__":
    main()
