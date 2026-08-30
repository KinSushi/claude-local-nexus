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
            for ligne in io.open(chemin, encoding="utf-8", errors="replace"):
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
            refus.append("%s (hors de la racine de travail %s)" % (brut, racine))
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
    corps_requete = {
        "model": modele,
        "messages": messages,
        "max_tokens": max_tokens,
        "cache": {"no-cache": True},
    }
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
    return {
        "texte": _sans_raisonnement(choix.get("message", {}).get("content", "")),
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


def _decouper_en_fenetres(corpus: str) -> List[str]:
    """
    Decoupe le corpus en fenetres de taille maximale FENETRE_CARACTERES.
    Preference est donne a la coupe sur une fin de ligne afin de ne pas
    tronquer une instruction.
    """
    fenetres = []
    start = 0
    while start < len(corpus):
        fin = min(start + FENETRE_CARACTERES, len(corpus))
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


# Fils simultanes par plan. Ces deux nombres sont MESURES : au-dela de trois
# appels concurrents le cloud n'accelere plus, et le plan local plafonne des
# le deuxieme. Ce ne sont pas des reglages a gout.
PLAFOND_FILS = {"cloud": 3, "local": 2}


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
    Repartit les fenetres du MAP entre les plans, et rend les resultats
    DANS L'ORDRE D'ENTREE quel que soit l'ordre d'arrivee.

    Les deux plans ne se disputent aucune ressource : le local est borne par
    la machine, le cloud par le reseau. Les faire travailler ensemble divise
    le temps du MAP sans rien couter, tous deux etant gratuits.
    """
    sorties = [None] * len(contenus)
    taches = list(enumerate(contenus))

    # Un modele nomme explicitement par l'appelant n'est jamais substitue.
    if not modele.startswith("adaptive-router"):
        for indice, res in _map_sur_plan(taches, modele, min(4, len(contenus) or 1),
                                         plafond_jetons, cle, temperature):
            sorties[indice] = res
        return sorties

    # Corpus sensible : le repartir entre deux plans serait une fuite, pas
    # une optimisation.
    if local_seul:
        for indice, res in _map_sur_plan(taches, "adaptive-router-local",
                                         PLAFOND_FILS["local"], plafond_jetons,
                                         cle, temperature):
            sorties[indice] = res
        return sorties

    # Repartition AU PRORATA des plafonds mesures, et non a parts egales.
    #
    # Une alternance pair/impair donne autant de fenetres a chaque plan alors
    # que leurs debits n'ont rien de comparable : le cloud rend en 7 a 30 s,
    # le plan local vient d'expirer deux fois a 900 s sur la meme cible. A
    # parts egales, le lot entier attend le plan le plus lent -- la
    # repartition coute alors plus qu'elle ne rapporte.
    #
    # Le ratio employe est celui des fils simultanes, 3 contre 2, seuls
    # chiffres MESURES dont on dispose. Le debit reel penche bien davantage
    # vers le cloud, mais l'inventer serait pire que d'etre prudent : ce
    # ratio-la, au moins, repose sur une mesure du depot.
    cycle = PLAFOND_FILS["cloud"] + PLAFOND_FILS["local"]
    pairs = [t for t in taches if t[0] % cycle < PLAFOND_FILS["cloud"]]
    impairs = [t for t in taches if t[0] % cycle >= PLAFOND_FILS["cloud"]]

    def _recolter(futur, nom_plan):
        try:
            for indice, res in futur.result():
                sorties[indice] = res
        except Exception as exc:
            # Un plan effondre laisse ses emplacements a None, ce qui se voit
            # en aval ; mais sans cette trace, nul ne saurait POURQUOI. Une
            # panne muette se confond avec un plan sans travail.
            if journal is not None:
                journal.append("plan %s en echec : %s" % (nom_plan, exc))

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executeur:
        futur_cloud = executeur.submit(_map_sur_plan, pairs, "adaptive-router-cloud",
                                       PLAFOND_FILS["cloud"], plafond_jetons,
                                       cle, temperature)
        futur_local = executeur.submit(_map_sur_plan, impairs, "adaptive-router-local",
                                       PLAFOND_FILS["local"], plafond_jetons,
                                       cle, temperature)
        _recolter(futur_cloud, "cloud")
        _recolter(futur_local, "local")

    # --- Rattrapage : une fenetre perdue repart sur l'AUTRE plan ----------
    #
    # Sans lui, un plan en panne laisse ses fenetres a None et le REDUCE
    # resume un corpus amoute de sa part. Le trou etait visible, mais le
    # travail perdu : or l'autre plan, lui, tourne.
    def _manquante(res):
        if not res or not isinstance(res, dict):
            return True
        return bool(res.get("erreur")) or not (res.get("texte") or "").strip()

    perdus = [i for i, res in enumerate(sorties) if _manquante(res)]
    if perdus:
        origine_cloud = {i for i, _ in pairs}
        # Chaque fenetre repart chez l'autre : celle qui a echoue en cloud
        # tente le local, et reciproquement. Reessayer sur le meme plan
        # reproduirait la panne qui vient de se produire.
        vers_local = [(i, contenus[i]) for i in perdus if i in origine_cloud]
        vers_cloud = [(i, contenus[i]) for i in perdus if i not in origine_cloud]

        def _rattraper(taches_secours, plan):
            if not taches_secours:
                return []
            return _map_sur_plan(taches_secours, "adaptive-router-" + plan,
                                 PLAFOND_FILS[plan], plafond_jetons, cle,
                                 temperature)

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as secours:
            f_local = secours.submit(_rattraper, vers_local, "local")
            f_cloud = secours.submit(_rattraper, vers_cloud, "cloud")
            for futur, plan in ((f_local, "local"), (f_cloud, "cloud")):
                try:
                    for indice, res in futur.result():
                        if not _manquante(res):
                            sorties[indice] = res
                            if journal is not None:
                                journal.append(
                                    "fenetre %d rattrapee sur le plan %s"
                                    % (indice + 1, plan))
                except Exception as exc:
                    if journal is not None:
                        journal.append("rattrapage %s en echec : %s" % (plan, exc))

        # UNE seule tentative. Si les deux plans echouent sur la meme fenetre,
        # insister ne fait que retarder le lot entier.
        for i in perdus:
            if _manquante(sorties[i]) and journal is not None:
                journal.append("fenetre %d perdue sur les deux plans" % (i + 1))

    return sorties


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
    fenetres = _decouper_en_fenetres(corpus)
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
    resultats_map = _repartir_map(contenus, modele, cle, plafond, temperature,
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
    # Le mode local_seul force l'utilisation exclusive de modèles dont le nom se termine par '-local'.
    # Lu depuis la TACHE d'abord, l'environnement ensuite.
    #
    # os.environ est global au processus : depuis que les deux plans de
    # l'essaim tournent en meme temps, un thread qui poserait
    # NEXUS_LOCAL_SEUL=1 pour sa cible sensible contraindrait aussi le
    # thread cloud, et sa restauration effacerait le reglage de l'autre.
    # Une clef portee par la tache suit la tache, et rien d'autre.
    local_seul = bool(tache.get("local_seul")) or         os.environ.get("NEXUS_LOCAL_SEUL") == "1"

    nom = tache.get("nom") or tache.get("modele") or "tache"
    # Defaut : le ROUTEUR, pas un modele nomme.
    #
    # Nommer un modele en dur revient a arbitrer une fois pour toutes, a la
    # place de la piece qui existe pour cela. Le routeur choisit selon la
    # tache, et son pool suit l'inventaire : un modele ajoute devient
    # candidat sans qu'aucun script ne change. `adaptive-router` couvre le
    # local ET le cloud Ollama, gratuits tous les deux ; il n'atteint jamais
    # un alias facture, qui vit derriere adaptive-router-anthropic.
    #
    # Contrepartie mesuree, a connaitre : son pool compte 42 candidats
    # DISTINCTS dont 18 locaux -- parmi lesquels qwen3-coder-30b-local et
    # qwen2.5-coder-32b-local, qui peuvent tenir la ligne jusqu'au delai de
    # 900 s. Mesure du 30 aout 2026 : un repli sur qwen3-coder:30b a rendu
    # en 597 s la ou la meme tache prenait 13 s en cloud. Borner par
    # NEXUS_AGENT_TIMEOUT, ou demander adaptive-router-cloud (19 candidats,
    # aucun local) quand la latence prime sur la confidentialite.
    #
    # Compter les occurrences et non les entrees distinctes donne 107 au
    # lieu de 42 : un meme alias figure plusieurs fois dans le bloc, une
    # fois par role. Le pool suit d'ailleurs l'inventaire, qui n'a aucun
    # plafond -- 39 modeles installes le 30 aout 2026, 33 exposes.
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

    # Si le corpus depasse la taille d'une fenetre, on utilise le MAP-REDUCE.
    if corpus and len(corpus) > FENETRE_CARACTERES:
        resultat = carte_reduction(corpus, consigne, modele, cle, plafond,
                                   temperature, local_seul=local_seul)
        # on ajoute les champs communs attendus par le reste du code
        resultat.update({
            "nom": nom,
            "modele": modele,
            "refus": refus,
            "plan": plan_de(resultat.get("adresse", "?")),
        })
        if local_seul:
            # Verifier que le plan utilise bien le mode local.
            if resultat.get("plan") != "local":
                return {"nom": nom, "modele": modele,
                        "erreur": f"plan {resultat.get('plan')} servi alors que local_seul exigé"}
            resultat["local_seul"] = True
        return resultat

    # Sinon appel direct (chemin existant)
    essais, echecs = [], []
    # Déduplication des candidats tout en conservant l'ordre.
    candidats = list(dict.fromkeys([modele] + REPLIS_GRATUITS))

    if local_seul:
        # Restreindre aux alias terminant par '-local'.
        candidats = [c for c in candidats if c.endswith("-local")]
        if not candidats:
            return {"nom": nom, "modele": modele,
                    "erreur": "aucun modele local disponible pour NEXUS_LOCAL_SEUL=1"}

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

        # Gestion du cas ou la reponse est vide
        texte_vide = not (resultat.get("texte") or "").strip()
        if texte_vide:
            if resultat.get("tronque"):
                # Le modele a atteint son plafond sans produire de texte.
                # On signale le probleme sans basculer.
                # Ajout de la cle `erreur` pour que les appelants qui ne
                # testent que `erreur` detectent correctement le probleme.
                resultat.update({
                    "nom": nom,
                    "modele": candidat,
                    "refus": refus,
                    "plan": plan_de(resultat.get("adresse", "?")),
                    "plafond_insuffisant": True,
                    "detail": f"demande {plafond} jetons, augmenter le plafond",
                    "erreur": f"plafond insuffisant : demande {plafond} jetons, augmenter le plafond"
                })
                return resultat
            else:
                echecs.append("%s : reponse vide (%d jetons consommes)"
                              % (candidat, resultat.get("tokens", 0)))
                continue

        resultat.update({"nom": nom, "modele": candidat, "refus": refus,
                         "plan": plan_de(resultat["adresse"])})
        if local_seul:
            # Verifier que le plan utilise bien le mode local.
            if resultat.get("plan") != "local":
                return {"nom": nom, "modele": candidat,
                        "erreur": f"plan {resultat.get('plan')} servi alors que local_seul exigé"}
            resultat["local_seul"] = True

        if candidat != modele:
            resultat["bascule"] = "%s -> %s apres : %s" % (
                modele, candidat, " | ".join(echecs))
        return resultat

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
    parseur.add_argument("--max-tokens", type=int, default=1500)
    parseur.add_argument("--temperature", type=float, default=None,
                         help="Defaut %.1f. Ne monter au-dessus de 0.5 que "
                              "pour une redaction libre." % TEMPERATURE_DEFAUT)
    parseur.add_argument("--racine", help="Racine de travail explicite (remplace le calcul par défaut).")
    parseur.add_argument("--lot", help="Fichier JSON decrivant plusieurs taches.")
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

    # Le parallélisme est plafonné : au-delà, plusieurs gros modèles sont
    # chargés en même temps sur une machine qui n'a qu'une réserve de RAM,
    # et l'ensemble ralentit au lieu d'accélérer.
    # On limite le nombre de threads à 8 pour éviter une consommation excessive.
    largeur = max(1, min(args.parallele, 8, len(taches)))
    depart = time.time()
    resultats: List[dict] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=largeur) as pool:
        futurs = {pool.submit(executer, t, cle): t for t in taches}
        for futur in concurrent.futures.as_completed(futurs):
            resultats.append(futur.result())

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
