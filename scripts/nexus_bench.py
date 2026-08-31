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
import re
import socket
import time
import argparse
import urllib.request
import urllib.error
from statistics import median
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

def mesurer_debit(gateway: str, alias: str, timeout: float) -> tuple:
    """
    Jetons produits par seconde sur une tache reelle. Rend (jps, jetons, ok, motif).

    C'est le second banc que la 112.3 reclamait, et dont la 107.2 a montre
    qu'il manquait pour de bon : qwen2.5-32b-local demarre en 3,8 s et n'a
    pas fini une synthese de 3000 caracteres en 110 s. Le delai avant le
    premier jeton ne dit rien du debit ; les deux se mesurent separement ou
    pas du tout.

    La tache demande une sortie LONGUE a partir d'une entree courte : c'est
    le debit de generation que l'on veut, pas la vitesse de lecture. Un
    corpus volumineux melangerait les deux.

    Le modele est d'abord reveille par un appel court, dont la duree est
    ecartee. Sans cela le chargement des poids serait impute au debit --
    l'erreur exacte que le banc de latence a du corriger.
    """
    if est_embedding(alias):
        return (None, None, False, "non applicable")
    url = f"{gateway.rstrip('/')}/v1/chat/completions"
    commun = {"model": alias, "cache": {"no-cache": True, "no-store": True}}

    # Reveil, non chronometre, et avec SON PROPRE budget.
    #
    # Lui donner le meme timeout que la mesure reproduisait exactement le
    # piege corrige cote latence. Le reveil ne paie pas seulement le
    # chargement du modele : le moteur ne gardant qu'un modele chaud
    # (107.1), il paie aussi l'eviction du precedent. Mesure du
    # 2026-08-30 : mistral-7b-local, pourtant banc a 2,5 s de demarrage,
    # echouait au reveil en 50 s -- un echec impute au modele alors qu'il
    # revenait a la bascule.
    #
    # Le budget de reveil est donc genereux et distinct. S'il expire, le
    # motif le dit : c'est le chargement qui n'a pas tenu, pas le debit.
    reveil = max(timeout * 3, 180)
    try:
        appel_post(url, dict(commun, max_tokens=8,
                             messages=[{"role": "user", "content": "Dis PRET"}]),
                   reveil)
    except Exception as exc:
        return (None, None, False,
                "chargement non tenu en %.0f s : %s" % (reveil, str(exc)[:40]))

    payload = dict(commun, max_tokens=256, messages=[{"role": "user", "content":
        "Explique en detail, en francais et en au moins deux cents mots, "
        "ce qu'est une passerelle de modeles de langage et a quoi elle sert."}])
    depart = time.monotonic()
    try:
        reponse = appel_post(url, payload, timeout)
    except urllib.error.URLError as exc:
        if isinstance(exc.reason, (TimeoutError, socket.timeout)):
            return (None, None, False, "timeout a %.0f s" % timeout)
        return (None, None, False, str(exc.reason)[:60])
    except Exception as exc:
        return (None, None, False, str(exc)[:60])
    secondes = time.monotonic() - depart

    usage = (reponse or {}).get("usage") or {}
    jetons = usage.get("completion_tokens") or 0
    if not jetons:
        # Sans compte de jetons rendu par la passerelle, on ne devine pas :
        # estimer d'apres la longueur du texte melangerait tokenisations.
        return (None, None, False, "aucun compte de jetons rendu")
    return (round(jetons / secondes, 2), jetons, True, "")


def mesurer_embedding(gateway: str, alias: str, timeout: float) -> dict:
    """
    Latence et pouvoir discriminant d'un modele d'embedding.

    Ecrite par le banc gratuit (gpt-oss-120b-cloud), integrée et verifiee
    ici. Les identificateurs accentues qu'il avait employes ont ete ramenes
    a l'ASCII, par coherence avec le reste du depot.

    Elle comble un angle mort : le banc classait les embeddings « non
    applicable » et ne les mesurait jamais, faute de repondre a un endpoint
    de conversation. Leur choix par defaut n'etait donc fonde sur rien --
    et nexus_index_build, qui emploie qwen3-embedding-8b-local par defaut,
    a expire apres 600 s sur le seul dossier scripts/.

    LA MARGE PRIME SUR LA LATENCE. Un embedding rapide qui ne separe pas le
    sens proche du sens eloigne rend la recherche inutile : il repond vite
    n'importe quoi. La marge est la difference de cosinus entre une paire
    proche et une paire eloignee ; c'est la mesure que la suite de tests
    emploie deja, plutot qu'un proxy d'isotropie moins interpretable.
    """
    url = "%s/v1/embeddings" % gateway.rstrip("/")

    def _vecteur(texte):
        reponse = appel_post(url, {"model": alias, "input": texte}, timeout)
        vec = (reponse.get("data") or [{}])[0].get("embedding")
        if not vec:
            raise ValueError("pas d'embedding rendu")
        return vec

    try:
        # Reveil non chronometre, budget separe et genereux.
        #
        # TROISIEME fois que ce piege est pose dans ce depot, et deuxieme
        # fois que je le repose apres l'avoir corrige : le banc de latence
        # a du separer chargement et regime etabli, puis le banc de debit
        # a du recevoir un budget de reveil distinct -- et cette fonction,
        # ecrite entre les deux, ne l'avait pas.
        #
        # Mesure : all-minilm pese 46 Mo et expirait a 120 s. Ce n'etait
        # pas lui, c'etait son chargement, impute a sa latence.
        try:
            _vecteur("reveil")
        except Exception as exc:
            return {"latence_ms": None, "marge": None, "ok": False,
                    "motif": "chargement non tenu : %s" % str(exc)[:50]}

        durees = []
        for _ in range(3):
            depart = time.monotonic()
            _vecteur("temps")
            durees.append(time.monotonic() - depart)
        latence_ms = int(round(sum(durees) / len(durees) * 1000))

        ancre = _vecteur("La passerelle route les requetes vers le modele adapte.")
        proche = _vecteur("Le routeur choisit le modele qui convient a la demande.")
        loin = _vecteur("La confiture de mures se prepare en fin d'ete.")
        if not (len(ancre) == len(proche) == len(loin)):
            raise ValueError("dimensions incoherentes")

        def _cos(a, b):
            na = sum(x * x for x in a) ** 0.5
            nb = sum(y * y for y in b) ** 0.5
            if not na or not nb:
                return 0.0
            return sum(x * y for x, y in zip(a, b)) / (na * nb)

        marge = round(_cos(ancre, proche) - _cos(ancre, loin), 3)
        return {"latence_ms": latence_ms, "marge": marge, "ok": True, "motif": ""}
    except Exception as exc:
        motif = (str(exc).splitlines() or ["erreur inattendue"])[0][:60]
        return {"latence_ms": None, "marge": None, "ok": False, "motif": motif}


QUESTIONS_BINAIRES = [
    "L'eau bout-elle a 100 degres au niveau de la mer ?",
    "Un triangle a-t-il toujours trois cotes ?",
    "Le francais est-il une langue officielle en Belgique ?",
    "Un cercle a-t-il toujours un rayon ?",
    "Le nombre 7 est-il pair ?",
]


def mesurer_binaire(gateway: str, alias: str, timeout: float,
                    repetitions: int = 5) -> dict:
    """
    Cout fixe d'un appel rendant une reponse BINAIRE, modele deja chaud.

    Troisieme grandeur du banc, distincte des deux autres. La sortie fait un
    jeton : le DEBIT ne joue donc pas, et le DEMARRAGE est ecarte par un
    reveil non chronometre. Ce qui reste est le cout fixe par appel --
    serialisation, file d'attente, decodage du premier jeton.

    C'est la grandeur qui decide pour un modele minuscule servant de garde
    ou d'aiguilleur : on ne lui demande pas de rediger, on lui demande OUI
    ou NON. Et c'est la que le local devrait l'emporter sur le cloud par
    construction, n'ayant aucun aller-retour reseau a payer -- affirmation
    a mesurer, non a supposer.

    La MEDIANE et non la moyenne : sur cinq points, un seul appel lent
    fausserait une moyenne.

    Le respect du format est compte a part de la vitesse. Un modele qui
    repond vite mais pas par OUI ou NON ne remplit pas le role, et les deux
    chiffres doivent rester lisibles separement.

    Ecrite par le banc gratuit, integrée apres correction : tirets Unicode
    ramenes a l'ASCII, une faute d'accord, un motif en anglais, et une
    correspondance trop stricte qui rejetait « OUI. ».
    """
    url = "%s/v1/chat/completions" % gateway.rstrip("/")
    resultat = {"median_ms": None, "min_ms": None, "max_ms": None,
                "respecte_format": 0, "ok": False, "motif": ""}

    def _appel(question):
        return appel_post(url, {
            "model": alias, "max_tokens": 3, "temperature": 0,
            "cache": {"no-cache": True, "no-store": True},
            "messages": [
                {"role": "system", "content": "Reponds par un seul mot : OUI ou NON."},
                {"role": "user", "content": question}]}, timeout)

    try:
        _appel("Reveil.")
        durees = []
        for i in range(repetitions):
            depart = time.monotonic()
            reponse = _appel(QUESTIONS_BINAIRES[i % len(QUESTIONS_BINAIRES)])
            durees.append(int((time.monotonic() - depart) * 1000))
            texte = ""
            try:
                texte = reponse["choices"][0]["message"]["content"] or ""
            except (KeyError, IndexError, TypeError):
                pass
            # Tolerant a la ponctuation et a la casse, strict sur le reste :
            # « OUI. » compte, « Oui, parce que... » non.
            net = re.sub(r"[^a-zA-Z]", "", texte).upper()
            if net in ("OUI", "NON"):
                resultat["respecte_format"] += 1
        tri = sorted(durees)
        n = len(tri)
        mediane = tri[n // 2] if n % 2 else (tri[n // 2 - 1] + tri[n // 2]) // 2
        resultat.update({"median_ms": mediane, "min_ms": tri[0],
                         "max_ms": tri[-1], "ok": True, "motif": ""})
    except Exception as exc:
        resultat["motif"] = ("%s: %s" % (type(exc).__name__, exc))[:60]
    return resultat


# ---------------------------------------------------------------------------
# LE RELEVE ACCUMULE, IL N'ECRASE PLUS.
#
# CE QUI ETAIT FAUX. `.nexus/latences.json` ne gardait qu'UNE lecture par
# modele et un unique horodatage global : chaque passage effacait le
# precedent. Or une mesure de latence isolee ne dit pas laquelle de deux
# realites tres differentes elle a attrapee -- mesure le 2026-08-31, le meme
# appel a rendu 180 300 ms a froid et 2 900 ms a chaud.
#
# CE QUE CELA EMPECHAIT. Sans repetitions accumulees, aucune dispersion n'est
# calculable, donc aucun intervalle de confiance : toute methode qui
# apprendrait sur ces mesures optimiserait du BRUIT (contrat 106.2). C'est le
# prerequis de toute piste d'apprentissage, et il manquait -- alors que
# `.nexus/epreuves.json` accumulait deja, patron applique a un releve et pas
# a l'autre.
#
# `stable` se calcule sur la DISPERSION, jamais sur l'egalite : une latence
# est continue, et exiger deux valeurs egales au millieme rendrait
# l'indicateur toujours faux -- miroir exact d'un defaut deja corrige
# ailleurs ou un ensemble a un element etait trivialement uniforme et le
# rendait toujours vrai.
#
# Ecrit par le banc gratuit (qwen3-coder-30b-local) en un jet complet apres
# une relance a neuf ; le premier jet confondait « fichier absent » et
# « fichier illisible » -- il n'ecrivait donc JAMAIS sur une machine neuve --
# et supprimait du fichier tout modele absent du lot courant, detruisant
# l'historique qu'il devait accumuler. Deux corrections d'application ici :
# la signature, et l'ecriture des champs de la mesure courante.
# ---------------------------------------------------------------------------

# Pose a True quand le fichier existe mais n'est pas lisible. Une liste plutot
# qu'un booleen : le module est importe, et une reaffectation de nom nu ne
# traverserait pas les fonctions.
_ILLISIBLE = [False]


SEUIL_DISPERSION = 0.15  # Mesure reelle : ecart entre 180300 ms (froid) et 2900 ms (chaud) est de plus de 500 %, donc instable. Deux lectures chaudes a quelques pourcents sont stables.

def latences_existantes(racine):
    """Lit le fichier de latences ou en cree un vide si absent."""
    fichier = racine / '.nexus' / 'latences.json'
    try:
        with open(fichier, 'r', encoding='utf-8') as f:
            donnees = json.load(f)
    except FileNotFoundError:
        # PIEGE A : fichier absent est normal, pas une erreur
        _ILLISIBLE[0] = False
        return {}
    except json.JSONDecodeError:
        # PIEGE A : fichier present mais illisible est une erreur
        _ILLISIBLE[0] = True
        return {}
    _ILLISIBLE[0] = False
    return donnees.get('modeles', {})

def ecrire_json(racine, mesures):
    """Ecrit les mesures en accumulant l'historique."""
    fichier = racine / '.nexus' / 'latences.json'
    try:
        with open(fichier, 'r', encoding='utf-8') as f:
            donnees_existantes = json.load(f)
    except FileNotFoundError:
        # PIEGE A : fichier absent est normal
        donnees_existantes = {'modeles': {}}
    except json.JSONDecodeError:
        # PIEGE A : illisible, refuse d'ecrire pour ne pas detruire l'historique
        return False

    # PIEGE B : ne pas perdre les anciens modeles
    tous_les_modeles = donnees_existantes.get('modeles', {})
    nouveaux_modeles = mesures.get('modeles', mesures)
    
    maintenant = datetime.now(timezone.utc).isoformat()
    
    for alias, info in nouveaux_modeles.items():
        if alias not in tous_les_modeles:
            tous_les_modeles[alias] = {'historique': [], 'mesures': 0, 'stable': False}
        
        modele = tous_les_modeles[alias]
        # MIGRATION DEPUIS L'ANCIEN FORMAT.
        #
        # Les 71 alias deja presents ont ete ecrits avant l'accumulation : ils
        # n'ont ni historique, ni compteur, ni indicateur. Le livrable ne les
        # initialisait que pour les alias NEUFS, ce qui faisait tomber le code
        # sur un KeyError des le premier passage reel -- un format nouveau qui
        # refuse le format qu'il doit remplacer.
        modele.setdefault('historique', [])
        modele.setdefault('mesures', 0)
        modele.setdefault('stable', False)
        # LES CHAMPS DE LA MESURE COURANTE SONT ECRITS, ET NON SEULEMENT
        # COMPTES. Sans cette fusion, le releve accumulait un historique tout
        # en cessant de rapporter `latence_ms`, `ok` et `motif` -- que
        # nexus_generate lit pour decider de l'appartenance aux pools. Un
        # fichier qui grossit en perdant ce qu'on vient d'y mesurer.
        for cle, valeur in info.items():
            if cle not in ('historique', 'mesures', 'stable'):
                modele[cle] = valeur
        historique = modele['historique']
        latence_ms = info.get('latence_ms')
        
        if latence_ms is not None and latence_ms > 0:
            historique.append(latence_ms)
            modele['mesures'] += 1
            # Garde les 8 derniers
            if len(historique) > 8:
                historique.pop(0)
            
            if len(historique) >= 2:
                min_lat = min(historique)
                max_lat = max(historique)
                med = median(historique)
                if med != 0 and (max_lat - min_lat) / med <= SEUIL_DISPERSION:
                    modele['stable'] = True
                else:
                    modele['stable'] = False
        else:
            # Ne pas ajouter None a l'historique pour ne pas fausser les calculs
            pass

    donnees_finale = {'mesure_le': maintenant, 'modeles': tous_les_modeles}
    
    # Ecriture atomique
    temp_file = fichier.with_suffix('.tmp')
    try:
        with open(temp_file, 'w', encoding='utf-8') as f:
            json.dump(donnees_finale, f, ensure_ascii=False, indent=2)
        os.replace(temp_file, fichier)
    except Exception:
        # Nettoyage en cas d'erreur
        if temp_file.exists():
            temp_file.unlink()
        raise
    
    return True


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
        # Une entree mesuree en DEBIT ne porte pas les clefs de la latence.
        # Les lire sans precaution levait un KeyError et faisait echouer
        # l'affichage apres des mesures pourtant reussies -- et deja ecrites
        # sur disque, ce qui rendait la panne d'autant plus trompeuse.
        if info.get("debit_jps") is not None or "debit_ok" in info:
            jps = info.get("debit_jps")
            sec = f"{jps:.2f} j/s" if jps else "N/A"
            verdict = "OK" if info.get("debit_ok") else                       f"FAIL ({info.get('debit_motif') or 'inconnu'})"
        elif info.get("motif") == "non applicable":
            verdict = "N/A (embedding)"
        elif info.get("ok"):
            verdict = "OK"
        else:
            verdict = f"FAIL ({info.get('motif') or 'inconnu'})"
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
    parser.add_argument("--manquants", action="store_true",
                        help="Ne mesurer que les modeles exposes qui n'ont "
                             "aucun releve. Rend 0 meme s'il n'y a rien a "
                             "faire : c'est un rattrapage, pas une porte.")
    parser.add_argument("--debit", action="store_true",
                        help="Mesurer les jetons par seconde sur une tache "
                             "reelle, au lieu du delai de demarrage.")
    parser.add_argument("--sans-verrou", action="store_true",
                        help="mesurer sans prendre le verrou machine "
                             "inter-projets (deliberement sous charge)")
    parser.add_argument("--attente-verrou", type=float, default=0,
                        help="secondes d'attente du verrou avant d'abandonner")
    args = parser.parse_args()

    # determiner la racine (parent du repertoire du script)
    script_path = Path(__file__).resolve()
    racine = script_path.parent.parent

    # LE VERROU MACHINE, pris ICI et pas ailleurs.
    #
    # Trois depots travaillent sur cette machine et se partagent 66 Go de RAM,
    # un moteur Ollama et un disque. Une latence mesuree pendant que le voisin
    # lance pytest ne mesure pas la latence du modele : elle mesure la
    # contention. Le defaut a deja ete paye ici, par une mesure prise pendant
    # un telechargement de 28 Go, et il est pernicieux parce que le chiffre
    # obtenu a l'air parfaitement normal.
    #
    # ON N'ATTEND PAS INDEFINIMENT. Attendre sans fin transformerait une
    # contention en blocage muet ; passer outre annulerait le verrou tout en
    # donnant l'impression qu'il protege. On echoue donc, en le disant, et
    # l'appelant decide : reessayer plus tard, ou constater que l'autre projet
    # travaille.
    #
    # --sans-verrou existe pour le cas ou l'on mesure DELIBEREMENT sous
    # charge. Le contourner doit rester possible et explicite : un verrou
    # qu'on ne peut pas lever a la main finit contourne autrement.
    verrou_pris = None
    if not getattr(args, "sans_verrou", False):
        try:
            sys.path.insert(0, str(script_path.parent))
            import nexus_verrou_machine
            verrou_pris = nexus_verrou_machine.verrou(
                "bench", projet="claude-local-nexus",
                attente_s=float(getattr(args, "attente_verrou", 0) or 0),
                bavard=False)
            tenu = verrou_pris.__enter__()
            # LE REFUS NE LEVE PAS : il se lit sur « obtenu ». Ecrit d'abord
            # avec un try/except attendant une exception, ce cablage laissait
            # donc TOUJOURS passer -- le banc mesurait sous contention en
            # croyant tenir le verrou. Trouve par l'epreuve, jamais par la
            # relecture : depuis un processus separe, obtenu vaut False et
            # rien n'est leve.
            #
            # A noter, et c'est ce qui rend le piege tenace : un mutex nomme
            # est REENTRANT dans le meme processus. Un essai fait dans un
            # seul interpreteur rend obtenu=True deux fois de suite et donne
            # a croire que tout va bien.
            if not getattr(tenu, "obtenu", False):
                verrou_pris.__exit__(None, None, None)
                print("[!] verrou machine refuse : un autre projet travaille.")
                print("    Reessayer plus tard, ou --sans-verrou pour mesurer")
                print("    deliberement sous charge.")
                return 75  # EX_TEMPFAIL : contention, pas erreur
        except ImportError:
            # Copie absente : on mesure quand meme, mais on le DIT. « Pas de
            # verrou » et « verrou refuse » sont deux etats distincts.
            print("[i] verrou machine indisponible : mesure sans exclusion")
            verrou_pris = None
        except Exception as exc:
            print("[!] verrou machine refuse : %s" % str(exc).splitlines()[0][:90])
            print("    Un autre projet travaille. Reessayer, ou --sans-verrou")
            print("    pour mesurer deliberement sous charge.")
            return 75  # EX_TEMPFAIL : contention, pas erreur

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

    # --manquants : ne mesurer que ce qui ne l'est pas.
    #
    # Sans cela, un modele telecharge reste « jamais mesure » donc hors
    # pool, indefiniment, et rien ne le signale. Douze modeles etaient dans
    # ce cas le 2026-08-30 : installes, declares au YAML, invisibles au
    # routage -- l'absence de preuve est bien la regle, mais encore
    # faut-il que la preuve finisse par etre produite.
    if args.manquants:
        deja = latences_existantes(racine)
        clef = "debit_jps" if args.debit else "latence_ms"
        modeles = [m for m in modeles
                   if not isinstance(deja.get(m), dict)
                   or deja[m].get(clef) is None]
        if not modeles:
            print("Aucun modele a rattraper : tout est mesure.")
            return 0
        # En rattrapage, le tableau final ne montre QUE les modeles traites.
        # Afficher tout le releve donnerait a croire qu'on vient de tout
        # remesurer -- un compte rendu qui exagere ce qu'il a fait est une
        # forme de mensonge, meme involontaire.
        a_rattraper = set(modeles)
        print("A rattraper : %d modele(s) sans releve." % len(modeles))

    # filtrer selon --modele si fourni
    if args.modele:
        modeles = [m for m in modeles if m in args.modele]
        # ET restreindre le TABLEAU FINAL aux modeles demandes.
        #
        # Le filtre marchait deja ; c'est l'affichage qui trompait. Lance
        # avec « --modele llama3.2-3b-local », le banc mesurait bien ce seul
        # modele mais imprimait ensuite les 71 lignes du releve stocke --
        # verifie en comparant : « phi3-mini-local 2.518 » etait exactement
        # le latence_ms=2518 deja enregistre, pas une mesure du jour.
        #
        # Le code disait deja pourquoi c'est grave, pour le mode rattrapage :
        # « un compte rendu qui exagere ce qu'il a fait est une forme de
        # mensonge, meme involontaire ». La meme raison vaut ici, et le meme
        # mecanisme y repond.
        #
        # J'ai moi-meme conclu de cet affichage que « --modele ne filtre
        # pas », et je l'ai inscrit au cockpit. C'etait faux : un compte
        # rendu trompeur ne trompe pas que les lecteurs pressés.
        a_rattraper = set(modeles)
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
        # Un embedding ne repond pas a un endpoint de conversation : le
        # banc le classait « non applicable » et n'en mesurait aucun. Il a
        # desormais sa propre mesure -- latence et marge discriminante --
        # et l'ecarter reviendrait a garder l'angle mort apres l'avoir
        # comble.
        if est_embedding(alias):
            m = mesurer_embedding(gateway, alias, timeout)
            resultats[alias] = dict(resultats.get(alias) or {},
                                    embed_latence_ms=m["latence_ms"],
                                    embed_marge=m["marge"],
                                    embed_ok=m["ok"], embed_motif=m["motif"],
                                    ok=m["ok"], motif=m["motif"] or "embedding")
            print("  %-34s %8s ms  marge %-7s %s"
                  % (alias, m["latence_ms"] or "-", m["marge"] or "-",
                     m["motif"] or "OK"))
            ecrire_json(racine, resultats)
            continue

        if args.debit:
            # Le debit s'ecrit A COTE de la latence, jamais a sa place : ce
            # sont deux grandeurs distinctes, et ecraser l'une par l'autre
            # ferait juger l'admission au pool sur un chiffre qui n'est pas
            # celui que nexus_generate y attend.
            jps, jetons, ok, motif = mesurer_debit(gateway, alias, timeout)
            ancien = resultats.get(alias) or {}
            resultats[alias] = dict(ancien, debit_jps=jps, debit_jetons=jetons,
                                    debit_ok=ok, debit_motif=motif)
            print("  %-34s %8s j/s  %s" % (alias,
                  ("%.2f" % jps) if jps else "-", motif or "OK"))
            ecrire_json(racine, resultats)
            continue

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
    #
    # La condition portait sur --manquants SEUL, alors que la vraie question
    # est : « un sous-ensemble a-t-il ete demande ? ». Avec --modele, le banc
    # mesurait bien le seul modele voulu puis imprimait les 71 lignes du
    # releve stocke -- verifie en comparant les valeurs affichees aux
    # latence_ms deja enregistres, identiques au millieme.
    #
    # Le code disait deja pourquoi c'est grave : « un compte rendu qui
    # exagere ce qu'il a fait est une forme de mensonge, meme involontaire ».
    # La raison ne dependait pas de l'option qui restreint.
    if args.manquants or args.modele:
        afficher_tableau({k: v for k, v in resultats.items()
                          if k in a_rattraper})
    else:
        afficher_tableau(resultats)
    if args.json:
        print(json.dumps(mesures, ensure_ascii=False, indent=2))

    sys.exit(0)

if __name__ == "__main__":
    # sys.exit(main()) et non main() : le code rendu par main etait PERDU.
    # Le refus de verrou affichait « un autre projet travaille » et rendait
    # pourtant 0 -- le message disait refuse, le code disait succes, et un
    # appelant automatise aurait cru la mesure faite. Trouve par l epreuve.
    sys.exit(main() or 0)
