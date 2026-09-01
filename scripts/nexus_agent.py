# -*- coding: utf-8 -*-
"""
Lanceur d'agents gratuits.

Pourquoi ce script existe
-------------------------
Déléguer une analyse à un sous‑agent Claude consomme l'abonnement : c'est
le contraire du but poursuivi. Ce script fait exécuter le même travail par
les modèles servis par la passerelle — locaux ou Ollama Cloud — dont le
coût est nul. L'orchestrateur ne dépense alors que ce qu'il faut pour
formuler la tâche et lire la réponse.

Ce qu'il apporte par rapport à un `curl` à la main :

  - plusieurs tâches partent en parallèle sur des modèles différents, ce
    qui est le seul moyen d'amortir les 60 à 120 s de chargement à froid
    d'un modèle local ;
  - le plan réellement servi est PROUVÉ par l'en‑tête de réponse plutôt
    que déduit du nom demandé — un routeur peut basculer, un alias peut
    pointer ailleurs, et une réponse « locale » venue du cloud n'est pas
    une économie mais une fuite ;
  - les fichiers joints subissent les mêmes interdictions que dans le
    serveur MCP : rien hors du dépôt, aucun fichier susceptible de porter
    un secret ;
  - le coût facturé est rapporté, donc vérifiable au lieu d'être supposé.

Usage
-----
    # une tâche, un modèle
    python scripts/nexus_agent.py --tache "Relis et signale les defauts" \
        --fichiers scripts/nexus_validate.py --modele codestral-22b-local

    # plusieurs tâches en parallèle, décrites dans un JSON
    python scripts/nexus_agent.py --lot taches.json

    # lister les modèles gratuits disponibles
    python scripts/nexus_agent.py --modeles

Format du lot (liste d'objets) :

    [
      {"nom": "validateur", "modele": "codestral-22b-local",
       "tache": "...", "fichiers": ["scripts/nexus_validate.py"]},
      {"nom": "generateur", "modele": "qwen3-14b-local",
       "tache": "...", "fichiers": ["scripts/nexus_generate.py"]}
    ]
"""
from __future__ import annotations

import argparse
import concurrent.futures
import queue
import io
import json
import logging
import os
import re
import sys
import time
import urllib.error
import urllib.request
import ssl
from typing import List, Dict, Any

# Configuration du logger minimal pour les diagnostics.
logging.basicConfig(level=logging.ERROR, format="%(levelname)s: %(message)s")

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PASSERELLE = os.environ.get("NEXUS_GATEWAY", "http://localhost:4000")

# Vérifier que la passerelle utilise HTTPS pour éviter les fuites en clair.
if not PASSERELLE.lower().startswith("https://"):
    logging.warning("La passerelle ne semble pas utiliser HTTPS : %s", PASSERELLE)

# ----------------------------------------------------------------------
# Taille maximale d'une fenetre (en caractères) pour un appel modele.
# La marge est necessaire car le corpus n'est pas seul dans la fenetre :
# il y a la consigne, la consigne systeme et la reponse attendue.
FENETRE_CARACTERES = int(os.getenv("NEXUS_FENETRE", "96000"))

# Taille de fenetre quand le plan LOCAL participe au MAP.
#
# 96 000 caracteres valent environ 24 000 jetons. Six des sept modeles du
# pool local plafonnent a 8 192 : une telle fenetre depasse leur contexte de
# trois fois. Mesure du 30 aout 2026, 101 435 caracteres envoyes a
# gemma4-12b-local : aucune reponse au bout de 300 s -- ni erreur franche ni
# troncature visible, le modele rame. Chaque fenetre ainsi envoyee coutait
# donc DELAI_MAP entier avant d'etre rattrapee par le cloud.
#
# Meme formule que le pont MCP : contexte utile moins la reserve de sortie,
# quatre caracteres par jeton, puis 85 % pour la consigne, le message
# systeme et les marqueurs. Mieux vaut sous-remplir une fenetre que la faire
# deborder.
# Le plancher de contexte du plan local est MESURE, pas grave dans le code.
#
# Il depend de la machine hote : nexus_capability.py la mesure, nexus_generate
# en deduit le max_input_tokens de chaque modele, et la passerelle l'expose.
# Une constante ecrite ici deviendrait fausse a la premiere migration vers
# une machine plus capable, et il faudrait la retrouver a la main dans deux
# fichiers. On interroge donc la passerelle, et le decoupage suit tout seul.
#
# NEXUS_CONTEXTE_LOCAL force la valeur ; le repli ne sert que si la passerelle
# est injoignable, auquel cas mieux vaut sous-remplir que faire deborder.
CONTEXTE_LOCAL_REPLI = 8192
_contexte_local_cache = None


def contexte_local_minimal(cle: str | None = None) -> int:
    """
    Plus petit contexte declare parmi les alias locaux exposes.

    Le minimum et non la moyenne : une fenetre doit tenir dans le plus etroit
    des modeles qui peuvent la recevoir, sans quoi celui-la rame jusqu'au
    delai sans rendre ni erreur ni troncature.
    """
    global _contexte_local_cache
    force = os.environ.get("NEXUS_CONTEXTE_LOCAL")
    if force:
        return int(force)
    if _contexte_local_cache is not None:
        return _contexte_local_cache
    valeur = CONTEXTE_LOCAL_REPLI
    try:
        requete = urllib.request.Request(PASSERELLE + "/model/info")
        requete.add_header("Authorization", "Bearer " + (cle or cle_maitre()))
        with urllib.request.urlopen(requete, timeout=15) as reponse:
            donnees = json.load(reponse)
        contextes = [
            (m.get("model_info") or {}).get("max_input_tokens")
            for m in (donnees.get("data") or [])
            if str(m.get("model_name", "")).endswith("-local")
        ]
        contextes = [c for c in contextes if c]
        if contextes:
            valeur = int(min(contextes))
    except Exception:
        # Passerelle muette : on garde le repli plutot que de lever. Le
        # decoupage doit rester possible meme sans elle.
        pass
    _contexte_local_cache = valeur
    return valeur


def fenetre_locale_caracteres(cle: str | None = None) -> int:
    """
    Meme formule que le pont MCP : contexte utile moins la reserve de sortie,
    quatre caracteres par jeton, puis 85 % pour la consigne, le message
    systeme et les marqueurs.
    """
    utile = max(contexte_local_minimal(cle) - 1024, 1024)
    return int(utile * 4 * 0.85)

def racine_travail() -> str:
    """
    Retourne la racine de travail selon l'ordre de priorité suivant :
    1. Variable d'environnement NEXUS_WORK_ROOT (réglage explicite).
    2. Variable d'environnement CLAUDE_PROJECT_DIR (fourni par l'hôte).
    3. Répertoire courant (os.getcwd()).
    Aucun chemin en dur n'est utilisé afin que le banc reste utilisable
    depuis n'importe quel projet.
    """
    for var in ("NEXUS_WORK_ROOT", "CLAUDE_PROJECT_DIR"):
        val = os.getenv(var)
        if val:
            return val
    return os.getcwd()

# Un modèle local non chargé met 60 à 120 s à répondre au premier appel, et
# davantage pour les gros poids. Un délai court ne protège de rien : il
# transforme un chargement normal en échec, et pousse à réessayer, donc à
# recharger. Mieux vaut attendre.
DELAI = int(os.environ.get("NEXUS_AGENT_TIMEOUT", "900"))

# Delai par FENETRE dans un MAP, distinct du delai d'un appel isole.
#
# 900 s conviennent a une tache unique : mieux vaut attendre qu'echouer.
# Dans un MAP, la logique s'inverse. Les fenetres sont nombreuses et
# independantes, et le resultat n'arrive qu'une fois la DERNIERE rendue :
# une seule fenetre lente immobilise donc tout le lot. Mesure du 30 aout
# 2026 : deux modeles locaux ont expire a 900 s sur la meme cible, bloquant
# l'ensemble pendant une demi-heure pour un fragment sur trois.
#
# Court, la fenetre lente abandonne vite et laisse jouer le repli. C'est le
# lot qui compte, pas l'obstination sur un fragment.
DELAI_MAP = int(os.environ.get("NEXUS_MAP_TIMEOUT", "180"))

# Temperature par defaut. 0.2 et non le defaut des modeles, souvent 0.7 a
# 0.8 : le travail dominant ici est de la relecture de code, de l'extraction
# et des sorties au format strict, ou une temperature haute produit la
# vraisemblance plutot que l'exactitude. Mesure du jour ou elle a ete
# posee : trois echecs consecutifs du banc sur taches a sortie stricte
# -- une reponse vide apres 19 000 jetons, une reponse tronquee dont le code
# etait reecrit de memoire, et une boucle de repetition de 589 secondes.
# Instruction systeme des appels MAP. Le modele doit savoir qu'il ne voit
# qu'un fragment : autrement il conclut sur l'ensemble a partir d'un morceau.
MAP_SYSTEME = (
    "Tu analyses UN fragment parmi d'autres d'un ensemble plus vaste. "
    "Extrais fidelement ce qui repond a la consigne, sans rien inventer. "
    "Ne conclus pas sur l'ensemble : d'autres fragments sont traites "
    "separement. Si le fragment ne contient rien d'utile, reponds "
    "exactement : RIEN."
)

TEMPERATURE_DEFAUT = float(os.getenv("NEXUS_TEMPERATURE", "0.2"))

# Ordre de repli entre plans GRATUITS uniquement. Aucun alias Claude n'y
# figure et aucun ne doit y figurer : retomber sur le paye reviendrait a
# facturer au jeton ce qui devait etre gratuit, sans que personne l'ait
# decide.
REPLIS_GRATUITS = ["gpt-oss-120b-cloud", "glm-4.7-flash-local"]

# Mêmes règles que le serveur MCP : ce qui ne doit pas remonter vers un
# modèle ne doit pas davantage remonter parce que le canal a changé.
FICHIERS_SECRETS = {
    ".env", ".env.local", ".env.production", ".npmrc", ".netrc",
    "credentials", "credentials.json", "id_rsa", "id_ed25519",
}
MOTIFS_SECRETS = re.compile(
    r"(^\.env($|\.)|\.pem$|\.key$|\.pfx$|\.p12$|_rsa$|_ed25519$|"
    r"secrets?\.(ya?ml|json|toml)$)",
    re.IGNORECASE,
)


def cle_maitre() -> str:
    """
    Cle de la passerelle, lue dans l'environnement puis dans .env.

    La valeur n'est jamais journalisee ni renvoyee : elle ne sert qu'a
    remplir un en-tete. Les guillemets et le commentaire de fin de ligne
    sont retires parce que .env les tolere et que la cle, elle, non.
    """
    valeur = os.environ.get("LITELLM_MASTER_KEY")
    if not valeur:
        chemin = os.path.join(ROOT, ".env")
        if os.path.exists(chemin):
            # LE `break` QUITTAIT LA BOUCLE SANS FERMER LE FICHIER.
            # Or il quitte des la premiere ligne utile : le descripteur
            # restait donc ouvert dans le cas NOMINAL, pas dans un cas rare.
            with io.open(chemin, encoding="utf-8", errors="replace") as fh:
                for ligne in fh:
                    if ligne.startswith("LITELLM_MASTER_KEY="):
                        valeur = ligne.split("=", 1)[1]
                        break
    if not valeur:
        raise SystemExit(
            "LITELLM_MASTER_KEY introuvable (ni dans l'environnement, ni dans .env)."
        )
    valeur = valeur.strip()
    if " #" in valeur:
        valeur = valeur.split(" #", 1)[0].strip()
    return valeur.strip("\"'").strip()


def est_secret(chemin: str) -> bool:
    base = os.path.basename(chemin)
    return base.lower() in FICHIERS_SECRETS or bool(MOTIFS_SECRETS.search(base))


def sous_racine(chemin: str, racine: str) -> bool:
    """
    Le fichier est-il sous la racine specifie ?

    Utilise `os.path.commonpath` pour eviter les faux positifs (ex.
    C:\\local-llm-docker-prive). En cas de lecteurs differents sous Windows,
    `commonpath` lève `ValueError` qui est interprete comme un refus.
    """
    # Vérification d'existence avant la résolution du chemin réel.
    if not os.path.exists(chemin):
        return False
    try:
        return os.path.commonpath([os.path.realpath(chemin), os.path.realpath(racine)]) == \
            os.path.realpath(racine)
    except ValueError:
        return False


# Compatibilite : l'ancienne fonction conserve le meme comportement avec ROOT.
def dans_depot(chemin: str) -> bool:
    """Alias conserve pour compatibilite interne."""
    return sous_racine(chemin, ROOT)


def charger_fichiers(chemins: List[str], racine: str | None = None) -> tuple[str, List[str]]:
    """Assemble le corpus et rend aussi la liste de ce qui a ete refuse.

    Le parametre `racine` designant la racine de travail. S'il n'est pas fourni,
    il est determine par `racine_travail()`. Les chemins relatifs sont resolves
    depuis cette racine.
    """
    if racine is None:
        racine = racine_travail()
    morceaux, refus = [], []
    for brut in chemins:
        complet = brut if os.path.isabs(brut) else os.path.join(racine, brut)
        if not sous_racine(complet, racine):
            # Nommer l'issue, et non seulement la fermeture : une garde qui
            # refuse sans dire par ou passer se fait contourner, ou renoncer.
            refus.append(
                "%s (hors de la racine de travail %s ; --racine pour en"
                " designer une autre, ou copier le fichier sous la racine)"
                % (brut, racine)
            )
            continue
        if est_secret(complet):
            refus.append("%s (susceptible de contenir un secret)" % brut)
            continue
        if not os.path.exists(complet):
            refus.append("%s (introuvable)" % brut)
            continue
        try:
            # Normaliser le chemin pour les systèmes où le nom peut contenir
            # des octets non UTF‑8.
            chemin_norm = os.fsdecode(complet)
            contenu = io.open(chemin_norm, encoding="utf-8", errors="replace").read()
        except (OSError, UnicodeDecodeError) as exc:
            refus.append("%s (illisible : %s)" % (brut, exc))
            continue
        morceaux.append("--- %s ---\n%s" % (brut, contenu))
    return "\n\n".join(morceaux), refus


def _sans_raisonnement(texte):
    """
    Retire la chaine de pensee que certains modeles laissent dans `content`.

    Constate le 30 aout 2026 : une reponse rendue a l'utilisateur contenait
    tout le raisonnement du modele, puis « </think>702 ». Le raisonnement
    n'est pas la reponse ; le livrer tel quel donne au lecteur un brouillon
    a la place d'un resultat.
    """
    if not texte:
        return ""
    s = str(texte)
    balises = r"think|thinking|reasoning"
    # 1. Blocs complets, y compris repetes.
    s = re.sub(r"<\s*(%s)\s*>.*?<\s*/\s*\1\s*>" % balises, "", s,
               flags=re.DOTALL | re.IGNORECASE)
    # 2. Ouverture sans fermeture : la reponse n'est jamais venue. Rendre du
    #    raisonnement brut serait pire que ne rien rendre -- l'appelant croirait
    #    tenir un resultat.
    if re.search(r"<\s*(%s)\s*>" % balises, s, flags=re.IGNORECASE):
        return ""
    # 3. Fermeture sans ouverture : le raisonnement a ete tronque en amont, la
    #    reponse est ce qui suit la derniere fermeture.
    fermetures = list(re.finditer(r"<\s*/\s*(%s)\s*>" % balises, s,
                                  flags=re.IGNORECASE))
    if fermetures:
        s = s[fermetures[-1].end():]
    return s.strip()


def appeler(modele: str, messages: List[Dict[str, Any]], max_tokens: int,
            cle: str, temperature: float | None = None,
            delai: int | None = None) -> Dict[str, Any]:
    """
    Un appel a la passerelle, avec la preuve du plan réellement servi.

    `no-cache` est pose volontairement : une reponse de cache mesurerait la
    latence de Redis, pas celle du modele, et ferait croire a un travail
    accompli qui ne l'a pas ete.
    """
    # Determination du plan pour adapter les tokens (Ollama ignore max_tokens si present).
    # Mesure : max_tokens=12 rend 523 jetons, num_predict=12 en rend 12.
    plan = "inconnu"
    if not hasattr(appeler, "_cache_plans"):
        try:
            appeler._cache_plans = plans_par_alias(cle)
        except Exception:
            appeler._cache_plans = {}
    plan = appeler._cache_plans.get(modele, "inconnu")

    corps_requete = {
        "model": modele,
        "messages": messages,
        "cache": {"no-cache": True},
    }
    # Inconnu retombe sur max_tokens parce qu'Anthropic l'exige et qu'Ollama se contente de l'ignorer.
    # Utilise num_predict uniquement lorsque le plan est connu et vaut 'local' ou 'cloud'.
    if plan in ("local", "cloud"):
        corps_requete["num_predict"] = max_tokens
    else:
        corps_requete["max_tokens"] = max_tokens
    if temperature is not None:
        corps_requete["temperature"] = temperature
    charge = json.dumps(corps_requete).encode("utf-8")
    requete = urllib.request.Request(
        PASSERELLE + "/v1/chat/completions",
        data=charge,
        headers={
            "Authorization": "Bearer " + cle,
            "Content-Type": "application/json",
        },
        method="POST",
    )
    depart = time.time()
    ctx = ssl.create_default_context()
    with urllib.request.urlopen(requete, timeout=(delai or DELAI), context=ctx) as reponse:
        corps = json.loads(reponse.read().decode("utf-8"))
        entetes = {k.lower(): v for k, v in reponse.getheaders()}
    duree = time.time() - depart
    choix = (corps.get("choices") or [{}])[0]
    texte = _sans_raisonnement(choix.get("message", {}).get("content", ""))

    # LA TRACE VERBATIM, deposee ici et nulle part ailleurs : c'est le seul
    # point ou la reponse brute existe avant d'etre consommee, decoupee ou
    # imprimee. Plus loin, elle est deja transformee.
    #
    # Un workflow massif isole ses agents -- worktrees, plans separes -- et
    # l'isolation sans recuperation ne vaut rien : la sortie passait dans le
    # terminal et disparaissait. Le magasin d'observations gardait le debit,
    # la duree et les jetons, JAMAIS le texte.
    #
    # Le depot ne peut pas faire echouer l'appel : nexus_verbatim.deposer ne
    # leve jamais et rend "" en cas d'echec. Perdre la trace est regrettable,
    # perdre le travail serait inacceptable.
    try:
        import nexus_verbatim
        nexus_verbatim.deposer(
            texte, modele,
            (messages[-1].get("content", "") if messages else "")[:120],
            plan_de(entetes.get("x-litellm-model-api-base", "")))
    except Exception:
        pass

    return {
        "texte": texte,
        "tronque": choix.get("finish_reason") == "length",
        "tokens": (corps.get("usage") or {}).get("total_tokens", 0),
        "servi_par": entetes.get("x-litellm-model-name", "?"),
        "adresse": entetes.get("x-litellm-model-api-base", "?"),
        "cout": entetes.get("x-litellm-response-cost", "0"),
        "duree": duree,
    }


def plans_par_alias(cle: str) -> Dict[str, str]:
    """
    Plan d'execution de chaque alias, lu dans le catalogue de la passerelle.
    """
    requete = urllib.request.Request(
        PASSERELLE + "/v1/model/info", headers={"Authorization": "Bearer " + cle})
    try:
        ctx = ssl.create_default_context()
        with urllib.request.urlopen(requete, timeout=30, context=ctx) as reponse:
            donnees = json.loads(reponse.read().decode("utf-8")).get("data", [])
    except Exception as exc:
        logging.error("Erreur lors de la récupération des plans d'alias : %s", exc)
        return {}
    plans: Dict[str, str] = {}
    for entree in donnees:
        nom = entree.get("model_name")
        if not nom:
            continue
        params = entree.get("litellm_params") or {}
        cible = str(params.get("model", ""))
        base = str(params.get("api_base", ""))
        if cible.startswith("anthropic/"):
            plans[nom] = "anthropic"
        elif "ollama.com" in base:
            plans[nom] = "cloud"
        elif cible.startswith("ollama"):
            plans[nom] = "local"
        else:
            plans[nom] = "inconnu"
    return plans


def plan_de(adresse: str) -> str:
    """Plan d'execution deduit de l'adresse réellement servie."""
    if not adresse or adresse == "?":
        return "inconnu"
    if "ollama.com" in adresse:
        return "cloud"
    if "anthropic" in adresse:
        return "anthropic"
    if "11434" in adresse or "11435" in adresse or "ollama" in adresse:
        return "local"
    return "inconnu"


def _decouper_en_fenetres(corpus: str, taille: int | None = None) -> List[str]:
    """
    Decoupe le corpus en fenetres de taille maximale FENETRE_CARACTERES.
    Preference est donne a la coupe sur une fin de ligne afin de ne pas
    tronquer une instruction.
    """
    fenetres = []
    start = 0
    while start < len(corpus):
        fin = min(start + (taille or FENETRE_CARACTERES), len(corpus))
        # chercher le dernier \n avant fin
        coupe = corpus.rfind("\n", start, fin)
        if coupe == -1 or coupe <= start:
            # pas de \n ou trop proche du debut, on coupe a la limite
            coupe = fin
        # Garantir la progression pour éviter boucle infinie
        if coupe <= start:
            coupe = min(start + 1, len(corpus))
        fenetres.append(corpus[start:coupe])
        start = coupe
    return fenetres


# Ce que l'ancien commentaire affirmait, et qui n'etait pas soutenu : au-dela de trois appels concurrents le cloud n'accelererait plus.
# Ce que la rampe du 2026-08-31 montre : de 4 a 20 connexions simultanees, zero refus et zero 429, et une latence p95 qui BAISSE de 6,3 s a 2,6 s. Le cloud accepte donc bien plus que trois.
# Ce qu'un essai ALTERNE de trois tours par valeur ne montre PAS : sur une charge MAP de huit fenetres, la mediane vaut 36 s avec trois fils et 36 s avec seize. Aucun gain discernable du bruit. Le goulot est ailleurs, et il reste a trouver.
# Pourquoi la valeur passe quand meme de 3 a 16 : non pour un gain prouve, mais pour que le chiffre cesse d'affirmer une mesure que rien ne soutient, et parce qu'il devient reglable sans toucher au code.
# Le plafond local de 2 tient pour une raison PHYSIQUE : l'hote a 61,6 Go partages avec un iGPU sans VRAM dediee, et deux modeles de 20 Go n'y coexistent pas.
# Les noms des variables d'environnement : NEXUS_FILS_CLOUD et NEXUS_FILS_LOCAL.
PLAFOND_FILS = {"cloud": int(os.getenv("NEXUS_FILS_CLOUD", "16")), "local": int(os.getenv("NEXUS_FILS_LOCAL", "2"))}


def _map_sur_plan(taches, alias, fils, plafond_jetons, cle, temperature):
    """
    Traite les fenetres d'UN plan, et rend des couples (indice, resultat).

    `fils` borne la concurrence, `plafond_jetons` borne la taille de chaque
    reponse. Les confondre est l'erreur qui guette ici : un plafond de
    jetons passe a max_workers donnerait trois threads pour trois jetons.
    """
    if not taches:
        return []
    resultats = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=fils) as executeur:
        futurs = {
            executeur.submit(
                appeler, alias,
                [{"role": "system", "content": MAP_SYSTEME},
                 {"role": "user", "content": contenu}],
                plafond_jetons, cle, temperature, DELAI_MAP): indice
            for indice, contenu in taches
        }
        for futur in concurrent.futures.as_completed(futurs):
            indice = futurs[futur]
            try:
                resultats.append((indice, futur.result()))
            except Exception as exc:
                # None a sa place plutot qu'un trou : le fragment manquant
                # se verra en aval, la ou un silence se confondrait avec un
                # fragment vide.
                resultats.append((indice, {"erreur": str(exc)}))
    return resultats


def _repartir_map(contenus, modele, cle, plafond_jetons, temperature,
                  local_seul=False, journal=None):
    """
    Traite les fenetres du MAP en piochant dans une FILE COMMUNE.

    Pourquoi une file et non une part assignee d'avance. Une repartition a
    ratio fixe suppose connu le rapport de debit entre les plans -- rapport
    qui change avec la machine, le modele et la charge. Donner au plan lent
    une part decidee a l'avance fait attendre tout le lot.

    Verifie en laboratoire, latences controlees : avec un plan trente fois
    plus rapide que l'autre, il prend 18 fenetres sur 20 sans qu'aucun ratio
    ne lui soit souffle. Les durees relevees en conditions reelles ont ete
    ecartees : le cache exact de la passerelle et la charge concurrente les
    rendaient incomparables.

    Avec une file commune, aucun ratio n'est suppose : chaque ouvrier prend
    la fenetre suivante des qu'il est libre. Le plan rapide en traite
    naturellement davantage, le lent moins, et l'equilibre se mesure a
    l'execution au lieu de se deviner a l'ecriture. Si un plan s'effondre,
    l'autre absorbe le reste sans qu'aucune regle ne le prevoie.

    L'ordre d'entree est preserve : chaque resultat retourne a son indice.
    """
    n = len(contenus)
    sorties = [None] * n
    if not n:
        return sorties

    # Un modele nomme explicitement par l'appelant n'est jamais substitue.
    if not modele.startswith("adaptive-router"):
        plans = [(modele, min(4, n))]
    elif local_seul or modele == "adaptive-router-local":
        # Corpus sensible : aucune fenetre ne part en cloud. Le repartir
        # entre deux plans serait une fuite, pas une optimisation.
        plans = [("adaptive-router-local", PLAFOND_FILS["local"])]
    elif modele == "adaptive-router-cloud":
        # Un routeur de plan NOMME designe ce plan, et lui seul. La condition
        # ne testait que le prefixe « adaptive-router » : demander
        # explicitement le cloud faisait donc quand meme travailler le local,
        # et la bascule decidee plus haut pour l'ecarter restait sans effet.
        plans = [("adaptive-router-cloud", PLAFOND_FILS["cloud"])]
    else:
        plans = [("adaptive-router-cloud", PLAFOND_FILS["cloud"]),
                 ("adaptive-router-local", PLAFOND_FILS["local"])]

    file = queue.Queue()
    for couple in enumerate(contenus):
        file.put(couple)

    compte = {}

    def _ouvrier(alias):
        pris = 0
        while True:
            try:
                indice, contenu = file.get_nowait()
            except queue.Empty:
                return pris
            try:
                sorties[indice] = appeler(
                    alias,
                    [{"role": "system", "content": MAP_SYSTEME},
                     {"role": "user", "content": contenu}],
                    plafond_jetons, cle, temperature, DELAI_MAP)
            except Exception as exc:
                sorties[indice] = {"erreur": str(exc)}
            pris += 1

    fils_total = sum(fils for _, fils in plans)
    with concurrent.futures.ThreadPoolExecutor(max_workers=fils_total) as pool:
        futurs = {}
        for alias, fils in plans:
            for _ in range(fils):
                futurs[pool.submit(_ouvrier, alias)] = alias
        for futur in concurrent.futures.as_completed(futurs):
            alias = futurs[futur]
            try:
                compte[alias] = compte.get(alias, 0) + futur.result()
            except Exception as exc:
                if journal is not None:
                    journal.append("ouvrier %s en echec : %s" % (alias, exc))

    # La part reellement prise par chaque plan est une MESURE, pas un
    # reglage : elle dit lequel a porte le lot, et le journal la conserve.
    if journal is not None and len(plans) > 1:
        journal.append("fenetres traitees par plan : " + ", ".join(
            "%s %d" % (a.replace("adaptive-router-", ""), c)
            for a, c in sorted(compte.items())))

    _rattraper_perdues(sorties, contenus, plans, cle, plafond_jetons,
                       temperature, journal)
    return sorties


def _manquante(res):
    """Une fenetre sans resultat exploitable : vide, en erreur, ou sans texte."""
    if not res or not isinstance(res, dict):
        return True
    return bool(res.get("erreur")) or not (res.get("texte") or "").strip()


def _rattraper_perdues(sorties, contenus, plans, cle, plafond_jetons,
                       temperature, journal):
    """
    Relance UNE fois les fenetres perdues, sur les plans encore disponibles.

    Sans cela, un plan en panne laisse ses fenetres a None et le REDUCE
    resume un corpus ampute de sa part. Une seule tentative : si tous les
    plans echouent sur la meme fenetre, insister ne fait que retarder le lot.
    """
    perdues = [i for i, res in enumerate(sorties) if _manquante(res)]
    if not perdues:
        return

    file = queue.Queue()
    for i in perdues:
        file.put((i, contenus[i]))

    def _ouvrier(alias):
        while True:
            try:
                indice, contenu = file.get_nowait()
            except queue.Empty:
                return
            try:
                res = appeler(alias,
                              [{"role": "system", "content": MAP_SYSTEME},
                               {"role": "user", "content": contenu}],
                              plafond_jetons, cle, temperature, DELAI_MAP)
                if not _manquante(res):
                    sorties[indice] = res
                    if journal is not None:
                        journal.append("fenetre %d rattrapee sur %s"
                                       % (indice + 1, alias))
            except Exception:
                # La fenetre retourne dans la file : un autre ouvrier, sur un
                # autre plan, peut encore la prendre.
                file.put((indice, contenu))
                return

    fils = sum(f for _, f in plans)
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, fils)) as pool:
        for alias, nb in plans:
            for _ in range(nb):
                pool.submit(_ouvrier, alias)

    for i in perdues:
        if _manquante(sorties[i]) and journal is not None:
            journal.append("fenetre %d perdue sur tous les plans" % (i + 1))


def carte_reduction(corpus: str, consigne: str, modele: str,
                   cle: str, plafond: int, temperature: float | None = None,
                   local_seul: bool = False) -> Dict[str, Any]:
    """
    MAP-REDUCE du corpus trop volumineux.

    MAP : le corpus est decoupe en fenetres (max FENETRE_CARACTERES). Chaque
    fenetre est analysee separement, le modele recevant une indication
    du type "Fragment i sur n. Ne concluez pas sur ce que vous n'avez pas vu."

    REDUCE : les resultats sont concatenees. Si la concatenation tient dans
    une seule fenetre, on effectue une reduction (une seconde passe) pour
    obtenir une synthese. Sinon on renvoie la concatenation telle quelle et
    on indique que la fusion n'a pas converge.

    Retourne un dictionnaire contenant le texte final, le nombre de tokens,
    la duree totale, le nombre de fenetres (MAP), le nombre de paliers
    (REDUCE) et le flag converge.
    """
    # La taille des fenetres suit le plus PETIT contexte des plans qui peuvent
    # les recevoir. Depuis que le MAP repartit entre plans, une fenetre taillee
    # pour le cloud peut atterrir sur un modele local a 8 192 jetons : elle y
    # depasse le contexte, et le modele ne repond pas -- ni erreur ni
    # troncature, il rame jusqu'au delai. Mieux vaut plus de fenetres que des
    # fenetres qu'un plan sur deux ne peut pas lire.
    # Les fenetres gardent leur taille pleine, et c'est une MESURE qui l'a
    # impose. Un premier correctif les avait reduites au contexte du plan
    # local, pour qu'aucune ne le deborde : le meme corpus est alors passe de
    # Neuf fenetres au lieu de trois pour le meme corpus, et le surcout
    # d'appels depasse de loin ce qu'on economise en evitant le depassement.
    #
    # C'est donc le PLAN qui s'ecarte, pas la fenetre qui retrecit : quand une
    # fenetre depasse ce que le local peut lire, il ne participe pas au MAP.
    # Le priver de fenetres qu'il ne peut pas lire ne lui retire rien : il y
    # ramerait jusqu'au delai sans rendre ni erreur ni troncature, et la
    # fenetre serait de toute facon rattrapee par l'autre plan.
    fenetres = _decouper_en_fenetres(corpus)
    local_exclu = False
    if fenetres and not local_seul:
        if max(len(f) for f in fenetres) > fenetre_locale_caracteres(cle):
            local_exclu = True
    n = len(fenetres)

    # Utilisation d'un ThreadPoolExecutor pour paralléliser les appels MAP.
    map_textes: List[str] = []
    total_tokens = 0
    total_duree = 0.0
    last_map_result: Dict[str, Any] = {}

    # Les contenus sont prepares dans l'ordre du corpus, puis repartis entre
    # les plans. Le numero de fragment reste celui du corpus : le modele doit
    # savoir ou il se situe, meme si le plan qui le traite varie.
    contenus = [
        "%s\n\n[Fragment %d/%d]\n\n%s" % (consigne, i, n, fragment)
        for i, fragment in enumerate(fenetres, start=1)
    ]
    incidents: List[str] = []
    # Un modele explicitement nomme reste respecte : seul le routeur global,
    # qui melange les plans, bascule vers le cloud seul.
    modele_map = modele
    if local_exclu and modele == "adaptive-router":
        modele_map = "adaptive-router-cloud"
        incidents.append(
            "plan local ecarte du MAP : fenetres de %d caracteres au-dela de "
            "son contexte (%d)" % (max(len(f) for f in fenetres),
                                   fenetre_locale_caracteres(cle)))

    resultats_map = _repartir_map(contenus, modele_map, cle, plafond, temperature,
                                  local_seul=local_seul, journal=incidents)

    for res in resultats_map:
        if not res:
            continue
        total_tokens += res.get("tokens", 0)
        total_duree += res.get("duree", 0.0)
        last_map_result = res
        # Un fragment sans rien d'utile repond RIEN, comme MAP_SYSTEME l'exige :
        # concatener ces reponses noierait le REDUCE sous des negations.
        texte = (res.get("texte") or "").strip()
        if texte and texte.upper() != "RIEN":
            map_textes.append(texte)

    for incident in incidents:
        print("  %s" % incident, file=sys.stderr)

    texte_concat = "\n\n".join(map_textes)

    if len(texte_concat) <= FENETRE_CARACTERES:
        # Reduction : on demande au modele de synthétiser le tout.
        messages = [
            {"role": "system", "content": consigne},
            {"role": "user", "content": texte_concat}
        ]
        reduction = appeler(modele, messages, plafond, cle, temperature)
        total_tokens += reduction.get("tokens", 0)
        total_duree += reduction.get("duree", 0.0)
        final_texte = reduction.get("texte", "")
        converge = True
        paliers = 1
        meta = reduction
    else:
        # Pas de reduction possible : on renvoie la concatenation brute.
        final_texte = texte_concat
        converge = False
        paliers = 0
        # Conserver les métadonnées du dernier appel MAP.
        meta = last_map_result

    resultat = {
        "texte": final_texte,
        "tokens": total_tokens,
        "duree": total_duree,
        "fenetres": n,
        "paliers": paliers,
        "converge": converge,
    }
    # on ajoute les champs du dernier appel (ou de la reduction) s'ils existent
    resultat.update({
        "servi_par": meta.get("servi_par", "?"),
        "adresse": meta.get("adresse", "?"),
        "cout": meta.get("cout", "0"),
    })
    return resultat


import os

def executer(tache: dict, cle: str) -> dict:
    local_seul = bool(tache.get("local_seul")) or os.environ.get("NEXUS_LOCAL_SEUL") == "1"
    nom = tache.get("nom") or tache.get("modele") or "tache"
    modele = tache.get("modele") or "adaptive-router"
    consigne = tache.get("tache") or ""
    if not consigne:
        return {"nom": nom, "erreur": "champ 'tache' vide"}
    racine_tache = tache.get("racine")
    corpus, refus = charger_fichiers(tache.get("fichiers") or [], racine=racine_tache)
    systeme = tache.get("systeme") or (
        "Tu es un relecteur technique rigoureux. Tu reponds en francais, de "
        "maniere concise et factuelle. Tu ne pretends jamais avoir verifie ce "
        "que tu n'as pas lu, et tu dis explicitement quand tu n'es pas sur."
    )
    contenu = consigne if not corpus else "%s\n\n%s" % (consigne, corpus)
    messages = [{"role": "system", "content": systeme},
                {"role": "user", "content": contenu}]
    plafond = int(tache.get("max_tokens") or 1500)
    temperature = tache.get("temperature", TEMPERATURE_DEFAUT)

    if corpus and len(corpus) > FENETRE_CARACTERES:
        resultat = carte_reduction(corpus, consigne, modele, cle, plafond,
                                   temperature, local_seul=local_seul)
        resultat.update({
            "nom": nom,
            "modele": modele,
            "refus": refus,
            "plan": plan_de(resultat.get("adresse", "?")),
        })
        if local_seul and resultat.get("plan") != "local":
            return {"nom": nom, "modele": modele,
                    "erreur": f"plan {resultat.get('plan')} servi alors que local_seul exigé"}
        if local_seul:
            resultat["local_seul"] = True
        return resultat

    essais, echecs = [], []
    candidats = list(dict.fromkeys([modele] + REPLIS_GRATUITS))

    if local_seul:
        candidats = [c for c in candidats if c.endswith("-local")]
        if not candidats:
            return {"nom": nom, "modele": modele,
                    "erreur": "aucun modele local disponible pour NEXUS_LOCAL_SEUL=1"}

    trunc_failure = None          # garde le premier échec par troncature
    for candidat in candidats:
        if candidat in essais or candidat.startswith("claude-"):
            continue
        essais.append(candidat)
        try:
            resultat = appeler(candidat, messages, plafond, cle, temperature)
        except urllib.error.HTTPError as exc:
            try:
                detail = exc.read().decode("utf-8", "replace")[:300]
            except Exception:
                detail = "<corps d'erreur illisible>"
            if temperature is not None and "temperature" in detail.lower():
                try:
                    resultat = appeler(candidat, messages, plafond, cle, None)
                except Exception as second:
                    echecs.append("%s : %s" % (candidat, second))
                    continue
            else:
                echecs.append("%s : HTTP %s : %s" % (candidat, exc.code, detail))
                continue
        except Exception as exc:
            echecs.append("%s : %s" % (candidat, exc))
            continue

        texte_vide = not (resultat.get("texte") or "").strip()
        if texte_vide:
            if resultat.get("tronque"):
                # Le modèle a consommé tout son budget sans produire de texte.
                # On consigne l'échec et on continue avec le candidat suivant.
                trunc_failure = resultat
                echecs.append("%s : reponse vide tronquee (demande %d jetons)" %
                              (candidat, plafond))
                continue
            else:
                echecs.append("%s : reponse vide (%d jetons consommes)"
                              % (candidat, resultat.get("tokens", 0)))
                continue

        resultat.update({"nom": nom, "modele": candidat, "refus": refus,
                         "plan": plan_de(resultat["adresse"])})
        if local_seul and resultat.get("plan") != "local":
            return {"nom": nom, "modele": candidat,
                    "erreur": f"plan {resultat.get('plan')} servi alors que local_seul exigé"}
        if local_seul:
            resultat["local_seul"] = True
        if candidat != modele:
            resultat["bascule"] = "%s -> %s apres : %s" % (
                modele, candidat, " | ".join(echecs))
            resultat["demande_initiale"] = modele
            motif = next((e for e in echecs if e.startswith(modele + " :")), "")
            if not motif and echecs:
                motif = echecs[-1]
            resultat["motif_bascule"] = motif
        return resultat

    # Aucun candidat n'a produit de texte.
    if trunc_failure:
        # Retourner le premier échec par troncature comme refus de plafond.
        trunc_failure.update({
            "nom": nom,
            "modele": candidat,
            "refus": refus,
            "plan": plan_de(trunc_failure.get("adresse", "?")),
            "plafond_insuffisant": True,
            "detail": f"demande {plafond} jetons, augmenter le plafond",
            "erreur": f"plafond insuffisant : demande {plafond} jetons, augmenter le plafond"
        })
        return trunc_failure

    return {"nom": nom, "modele": modele,
            "erreur": "tous les replis gratuits ont echoue : " + " | ".join(echecs)}


def rendre(resultat: dict) -> None:
    print("=" * 72)
    print("  %s" % resultat["nom"])
    if resultat.get("erreur"):
        print("  ECHEC : %s" % resultat["erreur"])
        print("=" * 72)
        return
    if resultat.get("bascule"):
        print("  BASCULE : %s" % resultat["bascule"])
    print("  demande : %s" % resultat["modele"])
    print("  servi   : %s  [%s]  %s" %
          (resultat.get("servi_par", "?"),
           resultat.get("plan", "?"),
           resultat.get("adresse", "?")))
    print("  %d tokens, %.0f s, cout %s" %
          (resultat.get("tokens", 0), resultat.get("duree", 0.0), resultat.get("cout", "0")))
    # Message specifique lorsqu'un plafond est insuffisant
    if resultat.get("plafond_insuffisant"):
        print("  [!] Plafond insuffisant : le modele a consomme tout son budget sans produire de texte. %s" % resultat.get("detail", ""))
    for r in resultat.get("refus") or []:
        print("  [refuse] %s" % r)

    # Affichage specifique du MAP-REDUCE le cas echeant
    if "fenetres" in resultat:
        print("  MAP-REDUCE : %d fenetres, %d paliers" %
              (resultat.get("fenetres", 0), resultat.get("paliers", 0)))
        if not resultat.get("converge", True):
            print("  [!] Fusion non convergee, resultat juxtapose.")

    print("-" * 72)
    print(resultat["texte"].strip())
    print("=" * 72)
    print()


def lister_modeles(cle: str) -> int:
    """
    Modeles exposes, separes par plan.

    Un modele Anthropic n'est pas gratuit ; les melanger dans une meme
    liste inviterait a en choisir un par inadvertance, ce qui est exactement
    ce que ce script cherche a eviter.
    """
    requete = urllib.request.Request(
        PASSERELLE + "/v1/model/info",
        headers={"Authorization": "Bearer " + cle},
    )
    try:
        ctx = ssl.create_default_context()
        with urllib.request.urlopen(requete, timeout=30, context=ctx) as reponse:
            donnees = json.loads(reponse.read().decode("utf-8")).get("data", [])
    except Exception as exc:
        print("Passerelle injoignable sur %s (%s)" % (PASSERELLE, exc))
        return 1
    plans: dict[str, List[str]] = {"local": [], "cloud": [], "anthropic": [], "inconnu": []}
    for entree in donnees:
        nom = entree.get("model_name", "?")
        params = entree.get("litellm_params") or {}
        cible = str(params.get("model", ""))
        base = str(params.get("api_base", ""))
        if cible.startswith("anthropic/"):
            plans["anthropic"].append(nom)
        elif "ollama.com" in base:
            plans["cloud"].append(nom)
        elif cible.startswith("ollama"):
            plans["local"].append(nom)
        else:
            plans["inconnu"].append(nom)
    for plan in ("local", "cloud", "anthropic", "inconnu"):
        noms = sorted(plans[plan])
        if not noms:
            continue
        cout = "gratuit" if plan in ("local", "cloud") else "FACTURE"
        print("\n  %s (%d, %s)" % (plan.upper(), len(noms), cout))
        for nom in noms:
            print("    %s" % nom)
    print()
    return 0


def lister_competences() -> list:
    """
    Noms des consignes systeme disponibles, sans extension.

    Les competences appartiennent a la PLATEFORME et non au projet appelant :
    elles sont donc cherchees sous ROOT, jamais sous --racine ni sous le
    repertoire courant. Un depot tiers qui delegue au banc herite ainsi des
    memes garde-fous sans rien installer.

    Un repertoire absent rend une liste vide plutot que de lever : l'absence
    de competences n'est pas une panne, seulement une fonction inemployee.
    """
    chemin = os.path.join(ROOT, "competences")
    if not os.path.isdir(chemin):
        return []
    return sorted(os.path.splitext(f)[0]
                  for f in os.listdir(chemin) if f.endswith(".txt"))


def charger_competence(nom: str) -> str:
    """
    Contenu d'une competence, ou une erreur qui dit ce qui existe.

    Le message enumere les noms disponibles : une erreur qui se contente de
    « inconnu » oblige a fouiller le depot pour retrouver l'orthographe.
    """
    disponibles = lister_competences()
    if nom not in disponibles:
        raise RuntimeError(
            "Competence '%s' inconnue. Disponibles : %s"
            % (nom, ", ".join(disponibles) or "aucune"))
    chemin = os.path.join(ROOT, "competences", nom + ".txt")
    with io.open(chemin, encoding="utf-8") as fh:
        return fh.read()


def main() -> int:
    parseur = argparse.ArgumentParser(description=__doc__)
    parseur.add_argument("--tache", help="Consigne adressee au modele.")
    parseur.add_argument("--fichiers", nargs="*", default=[],
                         help="Fichiers du depot a joindre.")
    # Le défaut a été mis à jour : voir commentaire dans `executer`.
    parseur.add_argument("--modele", default="adaptive-router",
                         help="Alias ou routeur. Defaut adaptive-router : la "
                              "plateforme arbitre. adaptive-router-cloud evite "
                              "les modeles locaux lents.")
    parseur.add_argument("--systeme", help="Consigne systeme optionnelle.")
    parseur.add_argument("--competence",
                         help="Consigne systeme prise dans competences/. "
                              "Disponibles : %s" % (", ".join(lister_competences()) or "aucune"))
    # Le défaut était 1500 quand le paramètre était inerte : la passerelle
    # ignorait max_tokens et appliquait 4096 (ou 8192 en cloud). Depuis que
    # le script envoie num_predict, la borne est réelle. Baisser ce défaut
    # régressait le comportement de tous les appelants qui ne le précisent pas.
    parseur.add_argument("--max-tokens", type=int, default=4096,
                         help="Nombre maximum de jetons (défaut 4096). "
                              "Depuis la correction, la borne est réelle ; "
                              "un budget trop court rend une réponse vide.")
    parseur.add_argument("--temperature", type=float, default=None,
                         help="Defaut %.1f. Ne monter au-dessus de 0.5 que "
                              "pour une redaction libre." % TEMPERATURE_DEFAUT)
    parseur.add_argument("--racine", help="Racine de travail explicite (remplace le calcul par défaut).")
    parseur.add_argument("--lot", help="Fichier JSON decrivant plusieurs taches.")
    parseur.add_argument(
        "--sortie", default=None, metavar="FICHIER",
        help="Ecrire une ligne JSON par tache DES QU'ELLE ABOUTIT. Sans "
             "cela, rien ne sort avant la fin du lot et une interruption "
             "perd tout le travail deja paye.")
    parseur.add_argument("--parallele", type=int, default=3,
                         help="Taches simultanees (defaut 3).")
    parseur.add_argument("--modeles", action="store_true",
                         help="Lister les modeles exposes par plan.")
    parseur.add_argument("--json", action="store_true",
                         help="Sortie machine au lieu du rapport lisible.")
    args = parseur.parse_args()

    cle = cle_maitre()

    if args.modeles:
        return lister_modeles(cle)

    if args.lot:
        try:
            taches = json.loads(io.open(args.lot, encoding="utf-8").read())
        except json.JSONDecodeError as exc:
            print("Le fichier de lot n'est pas un JSON valide : %s" % exc)
            return 1
        if not isinstance(taches, list):
            print("Le lot doit etre une liste d'objets.")
            return 1
        # Si la température est fournie en ligne de commande, elle surcharge le JSON.
        if args.temperature is not None:
            for t in taches:
                t["temperature"] = args.temperature
    elif args.tache:
        taches = [{"nom": args.modele, "modele": args.modele, "tache": args.tache,
                   "fichiers": args.fichiers, "systeme": args.systeme,
                   "max_tokens": args.max_tokens,
                   "temperature": (args.temperature if args.temperature is not None
                                   else TEMPERATURE_DEFAUT),
                   "racine": args.racine}]
    else:
        parseur.print_help()
        return 1

    # La competence s'applique ici, et non plus haut : `taches` n'existe pas
    # avant ce point, quelle que soit la branche empruntee.
    if args.competence:
        try:
            texte = charger_competence(args.competence)
        except RuntimeError as exc:
            print(exc)
            return 1
        # --systeme l'emporte : il est plus specifique qu'un nom de competence.
        if not args.systeme:
            args.systeme = texte

    # Rien si aucune consigne n'a ete resolue, sinon la boucle ecraserait par
    # None la valeur qu'une tache du lot porte deja.
    if args.systeme is not None:
        for t in taches:
            if not t.get("systeme"):
                t["systeme"] = args.systeme

    # Le parallélisme est limité par la RAM locale uniquement pour les modèles
    # locaux (alias ne se terminant pas par « -cloud »).  Ces modèles partagent
    # la même machine et sont donc plafonnés à 8 tâches concurrentes.  Les
    # modèles cloud n'utilisent aucune RAM locale et ne sont donc soumis qu'à la
    # limite demandée par l'utilisateur via ``--parallele``.
    # Si aucune tâche locale n'est présente, on retire le plafond de 8.
    local_tasks = sum(1 for t in taches if not str(t.get('modele', '')).endswith('-cloud'))
    if local_tasks == 0:
        largeur = max(1, min(args.parallele, len(taches)))
    else:
        largeur = max(1, min(args.parallele, 8, len(taches)))
    depart = time.time()
    resultats: List[dict] = []
    # CHAQUE RESULTAT EST ECRIT DES QU'IL TOMBE.
    #
    # Le lot accumulait tout en memoire et ne rendait rien avant la fin :
    # une interruption perdait l'integralite du travail deja paye, et un
    # fichier de sortie vide se lisait comme « rien ne se passe » alors que
    # les reponses arrivaient. Mesure du 2026-08-31 : un lot de dix-sept
    # taches a laisse un fichier a ZERO octet pendant six minutes, huit
    # processus vivants et douze reponses 200 deja servies.
    #
    # `--sortie` ecrit une ligne JSON par tache achevee, et vide le tampon a
    # chaque ligne : ce qui est tombe est acquis, meme si la suite ne vient
    # jamais.
    flux = None
    if getattr(args, "sortie", None):
        try:
            flux = io.open(args.sortie, "w", encoding="utf-8", newline="\n")
        except Exception as exc:
            print("[!] sortie incrementale impossible : %s" % exc,
                  file=sys.stderr)
            flux = None
    faits = 0
    # LA FERMETURE EST GARANTIE, ET NE L'ETAIT PAS.
    #
    # Le `flux.close()` se trouvait APRES la boucle : si celle-ci levait --
    # une tache qui echoue, une interruption -- la ligne n'etait jamais
    # atteinte et le fichier restait ouvert. Un `try/except` autour du
    # `close()` n'y aurait rien change : le probleme n'est pas que la
    # fermeture echoue, c'est qu'on n'y arrive pas.
    #
    # Un simple `with` ne convient pas ici : l'ouverture est CONDITIONNELLE et
    # le descripteur traverse tout le bloc. Le `try/finally` est la forme
    # juste.
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=largeur) as pool:
            futurs = {pool.submit(executer, t, cle): t for t in taches}
            for futur in concurrent.futures.as_completed(futurs):
                r = futur.result()
                resultats.append(r)
                faits += 1
                if flux is not None:
                    flux.write(json.dumps(r, ensure_ascii=False) + "\n")
                    flux.flush()
                # L'AVANCEMENT VA SUR STDERR, jamais sur stdout : celui-ci porte
                # le rapport, et le polluer le rendrait illisible a un appelant
                # qui le parse.
                print("  [%d/%d] %s" % (faits, len(taches),
                                        r.get("nom") or r.get("modele") or "?"),
                      file=sys.stderr)
    finally:
        if flux is not None:
            flux.close()

    if args.json:
        print(json.dumps(resultats, ensure_ascii=False, indent=2))
        return 0

    ordre = {t.get("nom") or t.get("modele"): i for i, t in enumerate(taches)}
    for resultat in sorted(resultats, key=lambda r: ordre.get(r["nom"], 99)):
        rendre(resultat)

    echecs = [r for r in resultats if r.get("erreur")]
    factures = [r for r in resultats if r.get("plan") == "anthropic"]
    total = sum(r.get("tokens", 0) for r in resultats)
    print("  %d tache(s), %d token(s), %.0f s au total, %d echec(s)"
          % (len(resultats), total, time.time() - depart, len(echecs)))
    if factures:
        print("  [!] %d tache(s) servies par Anthropic, donc FACTUREES : %s"
              % (len(factures), ", ".join(r["nom"] for r in factures)))
    return 1 if echecs else 0


if __name__ == "__main__":
    sys.exit(main())
