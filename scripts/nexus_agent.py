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
import contextlib
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


def decaper_cloture_englobante(texte: str) -> str:
    """
    Retourne *texte* après avoir éventuellement retiré les balises de bloc
    Markdown.

    - Si la première ligne non vide est exactement une ouverture de bloc
      (trois accents graves, éventuellement suivis d’un nom de langage) **et**
      que la dernière ligne non vide est exactement une fermeture de bloc
      (trois accents graves), les deux lignes sont supprimées.
    - Sinon le texte est renvoyé tel quel.
    """
    lignes = texte.splitlines()
    # Recherche de la première ligne non vide
    i = 0
    while i < len(lignes) and not lignes[i].strip():
        i += 1
    # Recherche de la dernière ligne non vide
    j = len(lignes) - 1
    while j >= 0 and not lignes[j].strip():
        j -= 1
    if i < j:
        # Vérifier que les délimiteurs sont à la toute première colonne
        debut_ok = lignes[i].startswith("```")
        fin_ok = lignes[j].startswith("```") and lignes[j].strip() == "```"
        if debut_ok and fin_ok:
            # Conserver toutes les lignes sauf les deux délimiteurs
            nouvelles = lignes[:i] + lignes[i + 1 : j] + lignes[j + 1 :]
            return "\n".join(nouvelles)
    return texte


import sys
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

# Plafond maximal autorise pour la reprise automatique en cas de plafond
# insuffisant. Mesure du 2026-08-31 : onze taches sur quarante-quatre, a
# 4000 jetons, ont echoue par plafond trop bas ; le pont MCP a recu ce jour
# une reprise unique a budget double.
PLAFOND_REPRISE = 16384

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

# PLANCHER de repli gratuit, dernier recours (jamais moins d'options, meme
# abonnements coupes ; aucun alias Claude). La chaine REELLE est DERIVEE par
# replis_gratuits() : cloud d'abord par latence mesuree, puis local.
REPLIS_GRATUITS_PLANCHER = ["gpt-oss-120b-cloud", "glm-4.7-flash-local", "qwen3-coder-30b-local", "llama3.2-3b-local"]

def replis_gratuits(cle: str) -> List[str]:
    """Derive la chaine de repli gratuite : cloud d'abord puis local, tries par latence mesuree, capacite prouvee (epreuves), puis le plancher. Degrade gracieusement."""
    try:
        plans = plans_par_alias(cle)
        with io.open(os.path.join(ROOT, ".nexus", "epreuves.json"), encoding="utf-8") as f:
            epreuves = json.load(f)
        with io.open(os.path.join(ROOT, ".nexus", "latences.json"), encoding="utf-8") as f:
            latences = json.load(f)
        capable = [a for a, info in epreuves.get("modeles", {}).items() if info.get("complet")]
        def latence(alias):
            lat = latences.get("modeles", {}).get(alias, {})
            if lat.get("ok"):
                return lat.get("latence_etablie_ms") or lat.get("latence_ms") or float("inf")
            return float("inf")
        cloud = sorted([a for a in capable if plans.get(a) == "cloud"], key=latence)
        local = sorted([a for a in capable if plans.get(a) == "local"], key=latence)
        # GARDE : ne renvoyer la chaine derivee QUE si au moins un cloud capable y
        # figure ; sinon le plancher (cloud-first : gpt-oss d'abord). Jamais local-first.
        if cloud:
            return list(dict.fromkeys(cloud + local + REPLIS_GRATUITS_PLANCHER))
        return list(REPLIS_GRATUITS_PLANCHER)
    except Exception:
        return list(REPLIS_GRATUITS_PLANCHER)

# ----------------------------------------------------------------------
# Limitation du nombre de replis locaux conservés.
# Le plafond est configurable via la variable d'environnement NEXUS_MAX_REPLIS_LOCAUX
# (défaut : 2). La fonction est pure et ne dépend que des arguments fournis.
MAX_REPLIS_LOCAUX = int(os.environ.get("NEXUS_MAX_REPLIS_LOCAUX", "2"))

def borner_replis_locaux(candidats: list, plans: dict, maximum: int = MAX_REPLIS_LOCAUX) -> tuple:
    """
    Retourne une paire (candidats_gardes, ecartes).

    - Le premier candidat (le modèle demandé) est toujours conservé.
    - Tous les candidats dont le plan n'est pas « local » sont conservés.
    - Parmi les candidats « local », on ne garde que les *maximum* premiers
      (dans l'ordre d'apparition) ; les suivants sont listés dans *ecartes*.
    - Si *maximum* ≤ 0, aucun repli local supplémentaire n'est conservé.
    - Chaque entrée d'*ecartes* a la forme
      "%s : ecarte, plafond de %d repli(s) local(aux) (NEXUS_MAX_REPLIS_LOCAUX)".
    """
    if not candidats:
        return [], []

    # Le premier candidat (modèle demandé) est toujours conservé.
    gardes = [candidats[0]]
    ecartes = []

    # Compteur des replis locaux déjà conservés (hors modèle demandé).
    locaux_gardes = 0

    for cand in candidats[1:]:
        plan = plans.get(cand)
        if plan != "local":
            # Tout ce qui n'est pas explicitement local est conservé.
            gardes.append(cand)
        else:
            # Candidat local : on ne garde que jusqu'au plafond.
            if maximum > 0 and locaux_gardes < maximum:
                gardes.append(cand)
                locaux_gardes += 1
            else:
                ecartes.append(
                    f"{cand} : ecarte, plafond de {maximum} repli(s) local(aux) (NEXUS_MAX_REPLIS_LOCAUX)"
                )
    return gardes, ecartes

# ----------------------------------------------------------------------
# Fonctions pures ajoutées pour la garde‑mémoire avant repli local
# ----------------------------------------------------------------------
def memoire_suffisante(poids_go, libre_go, marge_go: float = 2.0) -> bool:
    """
    Retourne True si la mémoire libre est suffisante pour le poids du modèle
    (avec une marge de sécurité). Règles :

    - Si poids_go est None → on ne peut pas comparer, on considère qu'il y a
      suffisamment de mémoire (True) afin de ne pas bloquer le repli.
    - Si libre_go est None → on ne sait pas, on considère qu'il n'y a pas
      assez de mémoire (False).
    - Sinon, retourne poids_go + marge_go <= libre_go.
    """
    if poids_go is None:
        return True
    if libre_go is None:
        return False
    return (poids_go + marge_go) <= libre_go


def tag_depuis_alias(alias: str, tags_installes: list) -> str | None:
    """
    Recherche le tag d'origine correspondant à un alias local.

    L'alias est dérivé par `local_alias` dans nexus_generate.py.
    Cette fonction importe `local_alias` de façon paresseuse et renvoie le
    tag correspondant ou None si aucun ne correspond.
    """
    try:
        from nexus_generate import local_alias
    except Exception:
        return None

    for t in tags_installes:
        try:
            if local_alias(t) == alias:
                return t
        except Exception:
            continue
    return None


def poids_et_libre(alias: str) -> tuple:
    """
    Retourne (poids_go, libre_go) pour l'alias donné.

    - `installed_models()` (nexus_capability) fournit le dictionnaire
      tag → poids.
    - `tag_depuis_alias` permet de retrouver le tag à partir de l'alias.
    - `mesurer_ram()` (nexus_charge) fournit la RAM libre.
    - En cas d'échec à n'importe quelle étape, renvoie (None, None).
    """
    try:
        from nexus_capability import installed_models
    except Exception:
        return (None, None)

    try:
        models = installed_models()
    except Exception:
        return (None, None)

    if not models:
        return (None, None)

    tags = list(models.keys())
    tag = tag_depuis_alias(alias, tags)
    if tag is None:
        return (None, None)

    poids = models.get(tag)

    try:
        from nexus_charge import mesurer_ram
    except Exception:
        return (poids, None)

    try:
        ram = mesurer_ram()
        libre = ram.get("libre_go")
    except Exception:
        libre = None

    return (poids, libre)

# Règles de filtrage des fichiers secrets. Les deux étages (ce script et le serveur MCP)
# sont désormais alignés sur le filtre le plus strict, celui du serveur MCP. Un même fichier
# ne doit pas être accepté ici puis refusé là-bas, ou inversement, car les deux canaux
# aboutissent au même fournisseur distant : toute divergence créerait une fuite ou un blocage
# selon le chemin emprunté.
FICHIERS_SECRETS = {
    ".env", ".env.local", ".env.production", ".npmrc", ".netrc",
    "credentials", "credentials.json", "id_rsa", "id_ed25519",
    ".htpasswd", "hosts.yml", "known_hosts", "config.json", "auth.json",
    "service-account.json", ".dockercfg",
}
MOTIFS_SECRETS = re.compile(
    r"(^\.env($|\.)|\.pem$|\.key$|\.pfx$|\.p12$|_rsa$|_ed25519$|"
    r"secrets?\.(ya?ml|json|toml)$|"
    r"\.keystore$|\.jks$|\.ppk$|"
    r"(^|[._-])(secret|secrets|credential|credentials)(?=$|[._-]))",
    re.IGNORECASE,
)


def cle_ollama() -> str:
    """Cle Ollama Cloud (outils web), meme mecanisme que cle_maitre ; jamais imprimee."""
    cle = os.environ.get("OLLAMA_CLOUD_API_KEY")
    if cle:
        return cle.strip().split(" #")[0].strip().strip('"').strip("'")
    chemin_env = os.path.join(ROOT, ".env")
    if os.path.isfile(chemin_env):
        with open(chemin_env, "r", encoding="utf-8") as f:
            for ligne in f:
                ligne = ligne.strip()
                if ligne.startswith("OLLAMA_CLOUD_API_KEY="):
                    valeur = ligne.split("=", 1)[1].strip()
                    valeur = valeur.split(" #")[0].strip()
                    valeur = valeur.strip('"').strip("'")
                    if valeur:
                        return valeur
    raise SystemExit("OLLAMA_CLOUD_API_KEY introuvable (ni dans l'environnement, ni dans .env).")

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
    try:
        return os.path.commonpath([os.path.realpath(chemin), os.path.realpath(racine)]) == \
            os.path.realpath(racine)
    except ValueError:
        return False


# Compatibilite : l'ancienne fonction conserve le meme comportement avec ROOT.
def dans_depot(chemin: str) -> bool:
    """Alias conserve pour compatibilite interne."""
    return sous_racine(chemin, ROOT)


def charger_fichiers(chemins: List[str], racine: str | None = None) -> tuple[str, List[str], List[Dict[str, Any]]]:
    """Assemble le corpus et rend aussi la liste de ce qui a ete refuse.

    Le parametre `racine` designant la racine de travail. S'il n'est pas fourni,
    il est determine par `racine_travail()`. Les chemins relatifs sont resolves
    depuis cette racine.
    """
    if racine is None:
        racine = racine_travail()
    morceaux, refus, joints = [], [], []
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
        # Mesure du 30 aout 2026 : accepte dossiers pour eviter Argument list too long
        if os.path.isdir(complet):
            for root, _, files in os.walk(complet):
                for f in sorted(files):
                    ext = os.path.splitext(f)[1].lower()
                    if ext not in (".txt", ".py", ".md", ".json", ".yaml", ".yml",
                                   ".csv", ".tsv", ".html", ".htm", ".css", ".js",
                                   ".sh", ".ini", ".cfg", ".conf", ".rst", ".tex",
                                   ".log"):
                        continue
                    chemin_f = os.path.join(root, f)
                    try:
                        chemin_norm = os.fsdecode(chemin_f)
                        contenu = io.open(chemin_norm, encoding="utf-8", errors="replace").read()
                    except (OSError, UnicodeDecodeError) as exc:
                        refus.append("%s (illisible : %s)" % (chemin_f, exc))
                        continue
                    morceaux.append("--- %s ---\n%s" % (chemin_f, contenu))
            continue
        try:
            # Normaliser le chemin pour les systèmes où le nom peut contenir
            # des octets non UTF‑8.
            chemin_norm = os.fsdecode(complet)
            contenu = io.open(chemin_norm, encoding="utf-8", errors="replace").read()
            import hashlib
            joints.append({
                "chemin": brut,
                "taille": len(contenu.encode("utf-8")),
                "empreinte": hashlib.sha256(contenu.encode("utf-8")).hexdigest()[:8]
            })
        except (OSError, UnicodeDecodeError) as exc:
            refus.append("%s (illisible : %s)" % (brut, exc))
            continue
        morceaux.append("--- %s ---\n%s" % (brut, contenu))
    return "\n\n".join(morceaux), refus, joints


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
    # Ne pas ajouter de saut de ligne pour ne pas fausser la mesure de part_raisonnement
    if s == str(texte):
        return s
    return s.rstrip()


SEUIL_RAISONNEMENT = int(os.environ.get("NEXUS_SEUIL_RAISONNEMENT", "4096"))


def demande_fichier_entier(consigne: str) -> bool:
    """
    Heuristique très simple pour détecter une consigne demandant la génération
    d'un fichier complet. Retourne True si la consigne contient l'un des verbes
    ou expressions typiques d'une tâche d'écriture de fichier.
    """
    mots_cles = [
        "écris", "ecris", "génère", "genere", "rends le fichier",
        "fichier complet", "crée", "creer", "creé", "creée", "create"
    ]
    cons = consigne.lower()
    return any(m in cons for m in mots_cles)


def reprise_utile(cause_vide, plafond=0) -> bool:
    """
    Retourne True si relever le plafond est utile.
    - Si `cause_vide` ne commence pas par "raisonnement_" → True.
    - Si commence par "raisonnement_" → True tant que `plafond` < SEUIL_RAISONNEMENT,
      sinon False.
    """
    if not (isinstance(cause_vide, str) and cause_vide.startswith("raisonnement_")):
        return True
    return plafond < SEUIL_RAISONNEMENT

def part_repetee(texte: str, longueur_min: int = 40, repetitions: int = 5) -> float:
    """
    Retourne la fraction de caractères du texte (hors espaces de tête/fin de chaque ligne)
    appartenant à des lignes d'au moins ``longueur_min`` caractères qui apparaissent
    au moins ``repetitions`` fois.
    Le calcul ignore les lignes vides et les espaces de début/fin.
    Si aucune ligne ne satisfait le critère, retourne 0.0.
    """
    if not texte:
        return 0.0
    # Nettoyage des lignes : strip des espaces de tête/fin, on garde les lignes suffisamment longues
    lignes = [l.strip() for l in texte.splitlines() if len(l.strip()) >= longueur_min]
    if not lignes:
        return 0.0
    from collections import Counter
    compteur = Counter(lignes)
    # Sélection des lignes qui apparaissent au moins ``repetitions`` fois
    lignes_repetees = {ligne for ligne, cnt in compteur.items() if cnt >= repetitions}
    if not lignes_repetees:
        return 0.0
    # Calcul du nombre total de caractères (hors espaces de tête/fin) du texte
    total_chars = sum(len(l) for l in lignes)
    # Caractères appartenant aux lignes répétées
    rep_chars = sum(len(l) * compteur[l] for l in lignes_repetees)
    return rep_chars / total_chars if total_chars else 0.0


def texte_degenere(texte, longueur_min: int = 40, repetitions: int = 5) -> bool:
    """
    Détecte un texte dégénéré :
    - découpe le texte en lignes stripées, ignore celles de moins de
      ``longueur_min`` caractères ;
    - renvoie ``True`` si une même ligne apparaît au moins ``repetitions``
      fois ;
    - ou si, sur le texte sans sauts de ligne, un même bloc de 200 caractères
      (extrait tous les 100 caractères) apparaît au moins ``repetitions``
      fois ;
    - renvoie ``False`` pour un texte vide ou trop court. Aucun
      exception n’est levée.
    """
    if not texte:
        return False

    # 1. Critère de lignes répétées via part_repetee
    part = part_repetee(texte, longueur_min=longueur_min, repetitions=repetitions)
    if part >= 0.6:
        return True

    # 2. Recherche de blocs répétés (fenêtre glissante) – critère inchangé
    compact = "".join(texte.splitlines())
    if len(compact) < 200:
        return False

    blocs = [
        compact[i:i + 200]
        for i in range(0, len(compact) - 200 + 1, 100)
    ]
    if blocs:
        from collections import Counter
        if any(cnt >= repetitions for cnt in Counter(blocs).values()):
            return True

    return False


def repli_passerelle_effectif(entetes) -> bool | None:
    """
    Retourne True si la passerelle a servi un autre modele que celui demande.

    - True si x-litellm-attempted-fallbacks vaut '1', 'true' ou 'True'
    - False si l'en-tete est present avec '0', 'false' ou ''
    - None si absent ou si entetes n'est pas un dict
    """
    if not isinstance(entetes, dict):
        return None
    if "x-litellm-attempted-fallbacks" not in entetes:
        return None
    valeur = entetes["x-litellm-attempted-fallbacks"]
    if valeur in ("1", "true", "True"):
        return True
    if valeur in ("0", "false", ""):
        return False
    return None

def appeler(modele: str, messages: List[Dict[str, Any]], max_tokens: int,
            cle: str, temperature: float | None = None,
            delai: int | None = None, outils: Any = None) -> Dict[str, Any]:
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
    if outils:
        corps_requete["tools"] = outils
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
    # 15 min de silence, 0.05s CPU: l'appelant ne distingue pas requete non partie et inference.
    # Annonce sur stderr pour ne pas polluer le rendu.
    print(f"Appel modele {modele} (timeout {delai or DELAI}s) : depart maintenant", file=sys.stderr, flush=True)
    with urllib.request.urlopen(requete, timeout=(delai or DELAI), context=ctx) as reponse:
        corps = json.loads(reponse.read().decode("utf-8"))
        entetes = {k.lower(): v for k, v in reponse.getheaders()}
    duree = time.time() - depart
    choix = (corps.get("choices") or [{}])[0]

    # Capture du texte brut avant le nettoyage.
    # La mesure de la part retiree est exacte car elle se base sur la longueur
    # du texte brut et du texte nettoye, sans aucune conversion intermediaire.
    texte_brut = choix.get("message", {}).get("content", "")
    texte = _sans_raisonnement(texte_brut)

    # Mesure voisin: 1.0 en direct vs 0.0 passerelle, meme modele/question.
    # car_par_jeton reste la grandeur valable dans le cas hors bande.
    part_raisonnement = (len(texte_brut) - len(texte)) / len(texte_brut) if texte_brut and len(texte) != len(texte_brut) else None

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
    except Exception as exc:
        print("lecture de la tracabilite du plan ratee : %s" % exc, file=sys.stderr)

    return {
        "texte": texte,
        "tronque": choix.get("finish_reason") == "length",
        "tokens": (corps.get("usage") or {}).get("total_tokens", 0),
        "servi_par": entetes.get("x-litellm-model-name", "?"),
        "adresse": entetes.get("x-litellm-model-api-base", "?"),
        "cout": entetes.get("x-litellm-response-cost", "0"),
        "duree": duree,
        # 'inconnu' si mesure impossible (None), sinon proportion arrondie a trois decimales.
        "part_raisonnement": 'inconnu' if part_raisonnement is None else round(part_raisonnement, 3),
        # Nombre de tokens de sortie (completion) ; 0 par defaut si absent.
        "tokens_sortie": (corps.get("usage") or {}).get("completion_tokens", 0),
        # part_raisonnement voit le raisonnement INLINE et cette grandeur voit le raisonnement HORS BANDE, mesures 0,02 contre 3,15
        "car_par_jeton": round(len(texte) / (corps.get("usage") or {}).get("completion_tokens", 0), 2) if (corps.get("usage") or {}).get("completion_tokens", 0) else None,
        "cause_vide": (
            "raisonnement_" + str(len(choix.get('message', {}).get('reasoning_content', '')))
        ) if not texte else "contenu_present",
        "repli_passerelle": repli_passerelle_effectif(entetes),
        "tool_calls": (choix.get("message") or {}).get("tool_calls") or [],
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

TAILLE_MODELE_GB = float(os.getenv('NEXUS_TAILLE_MODELE_GB', '20'))

def plafond_local():
    try:
        from nexus_capability import build_profile
        profile = build_profile()
        if not profile.get("gpu_usable_for_offload", False):
            return 2
        vram_gb = (profile.get('gpu') or {}).get('vram_gb', 0)
        if vram_gb <= 0:
            return 2
        # Ce diviseur est une hypothese NON MESUREE, le profil materiel n'expose pas la taille des modeles, la contre-epreuve doit etre rejouee des qu'un GPU dedie existera
        return max(2, min(8, int(vram_gb / TAILLE_MODELE_GB)))
    except Exception:
        return 2

PLAFOND_FILS = {
    "cloud": int(os.getenv("NEXUS_FILS_CLOUD", "16")),
    "local": int(os.getenv("NEXUS_FILS_LOCAL") or plafond_local())
}





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
    import hashlib
    # le journal preserve ET reprend desormais
    # l'empreinte existe pour qu'un journal d'un AUTRE corpus ne soit jamais fusionne, ce qui serait pire que la perte evitee
    # le refus est dit plutot que tu
    # calcul de l'empreinte du corpus
    _sep = b'\x1e'
    _hasher = hashlib.sha256()
    for _i, _c in enumerate(contenus):
        if _i:
            _hasher.update(_sep)
        _hasher.update(_c.encode() if isinstance(_c, str) else _c)
    _empreinte = _hasher.hexdigest()
    _journal = os.getenv('NEXUS_MAP_JOURNAL')
    if _journal:
        try:
            if os.path.exists(_journal) and os.path.getsize(_journal) > 0:
                with open(_journal, 'r', encoding='utf-8') as _f:
                    _first = _f.readline()
                    _header = json.loads(_first)
                    if _header.get('empreinte') == _empreinte:
                        _reprise = 0
                        for _line in _f:
                            _data = json.loads(_line)
                            _idx = _data.get('indice')
                            _res = _data.get('resultat')
                            if _idx is not None:
                                sorties[_idx] = _res
                                _reprise += 1
                        sys.stderr.write(f"{_reprise} fenetres reprises sur {n}\n")
                    else:
                        sys.stderr.write(f"Refus de reprendre le journal {_journal} car il porte un autre corpus\n")
            else:
                with open(_journal, 'w', encoding='utf-8') as _f:
                    json.dump({'empreinte': _empreinte, 'fenetres': n}, _f)
                    _f.write('\n')
        except Exception as _e:
            sys.stderr.write(f"Erreur de lecture/ecriture du journal {_journal}: {_e}\n")

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
    # une fenetre deja reprise du journal ne doit pas etre recalculee, sinon la reprise ne servirait a rien
    for couple in enumerate(contenus):
        if sorties[couple[0]] is None:
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
                # Mesure 2026-08-31: ecriture du journal pour chaque fenetre
                # Evite perte de travail en cas d'arret brutal du processus
                journal_path = os.environ.get('NEXUS_MAP_JOURNAL')
                if journal_path:
                    try:
                        with open(journal_path, 'a', encoding='utf-8') as f:
                            json.dump({"indice": indice, "resultat": sorties[indice]}, f)
                            f.write('\n')
                    except Exception:
                        pass
            except Exception as exc:
                sorties[indice] = {"erreur": str(exc)}
                # Mesure 2026-08-31: ecriture du journal pour chaque fenetre
                # Evite perte de travail en cas d'arret brutal du processus
                journal_path = os.environ.get('NEXUS_MAP_JOURNAL')
                if journal_path:
                    try:
                        with open(journal_path, 'a', encoding='utf-8') as f:
                            json.dump({"indice": indice, "resultat": sorties[indice]}, f)
                            f.write('\n')
                    except Exception:
                        pass
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
    # Taille adaptee au local si force, sinon standard pour permettre l'exclusion
    taille = fenetre_locale_caracteres(cle) if local_seul else None
    fenetres = _decouper_en_fenetres(corpus, taille)
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
    fenetres_perdues = sum(1 for res in resultats_map if _manquante(res))

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

    if fenetres_perdues:
        mention = ("[ATTENTION] %d fenetre(s) perdue(s) sur %d : "
                   "la reponse porte sur un corpus ampute.\n\n"
                   % (fenetres_perdues, n))
        final_texte = mention + final_texte

    resultat = {
        "texte": final_texte,
        "tokens": total_tokens,
        "duree": total_duree,
        "fenetres": n,
        "fenetres_perdues": fenetres_perdues,
        "paliers": paliers,
        "converge": converge,
    }
    if fenetres_perdues:
        resultat["erreur"] = ("%d fenetre(s) perdue(s) sur %d"
                              % (fenetres_perdues, n))
    # on ajoute les champs du dernier appel (ou de la reduction) s'ils existent
    resultat.update({
        "servi_par": meta.get("servi_par", "?"),
        "adresse": meta.get("adresse", "?"),
        "cout": meta.get("cout", "0"),
    })
    return resultat


import os

def etiqueter_ecritures(resultat: dict, tache: dict, consigne: str) -> dict:
    try:
        import re as _re
        _txt = resultat.get("texte") or ""
        _pats = ["Out-File","Set-Content","Add-Content","open\\s*\\([^)]*['\"][wa+]","unlink","\\bremove\\b","rmtree","shutil\\.copy","Move-Item","Remove-Item"]
        _chemins = list(tache.get("fichiers") or [])
        _chemins_avec_base = []
        for _c in _chemins:
            if _c:
                _chemins_avec_base.append(_c)
                _base = _c.replace('\\', '/').rsplit('/', 1)[-1]
                if len(_base) >= 5:
                    _chemins_avec_base.append(_base)
        _chemins = _chemins_avec_base
        _marques = []
        for _p in _pats:
            for _m in _re.finditer(_p, _txt, _re.I):
                _marques.append(_m.group(0))
        _chemins_presents = [_c for _c in _chemins if _c and _c in _txt]
        if _marques and _chemins_presents:
            # On ne modifie plus le champ texte afin de ne pas corrompre le code Python.
            # On ne garde le drapeau d'étiquetage que si la marque et le chemin
            # apparaissent dans la même instruction (même ligne).
            _ligne_concernée = None
            for _line in _txt.splitlines():
                # recherche d'une marque sur la ligne
                _marque_sur_ligne = any(_re.search(p, _line, _re.I) for p in _pats)
                # recherche d'un chemin sur la ligne
                _chemin_sur_ligne = any(c in _line for c in _chemins)
                if _marque_sur_ligne and _chemin_sur_ligne:
                    _ligne_concernée = _line
                    break
            if _ligne_concernée is not None:
                _motif = "[!] ECRITURE DETECTEE : marque et chemin dans la même instruction."
                resultat["motif"] = _motif
                resultat["etiquete"] = True
        try:
            _all_paths = _re.findall(r"(?:[A-Za-z]:)?[\w./\\_-]+\.[a-zA-Z0-9]+", _txt)
            _hors = [p for p in _all_paths if p not in _chemins]
            resultat["mentions_hors_perimetre"] = len(_hors)
        except Exception:
            resultat["mentions_hors_perimetre"] = 0
    except Exception as exc:
        print("comptage des mentions hors perimetre rate : %s" % exc, file=sys.stderr)
    return resultat

# Consigne systeme par defaut du banc.
SYSTEME_DEFAUT = (
    "Tu es un relecteur technique rigoureux. Tu reponds en francais, de "
    "maniere concise et factuelle. Tu ne pretends jamais avoir verifie ce "
    "que tu n'as pas lu, et tu dis explicitement quand tu n'es pas sur."
)

def consigne_sans_web() -> str:
    return (
        "Tu n as AUCUN acces au web ni a aucun outil. Ce que tu rapportes vient de "
        "ta memoire d entrainement : ne presente jamais un souvenir comme le resultat "
        "d une recherche, cite tes sources comme des souvenirs, et marque NON VERIFIE tout "
        "fait dont tu n es pas certain."
    )

def composer_systeme(systeme_demande, web) -> str:
    base = systeme_demande if systeme_demande else SYSTEME_DEFAUT
    if not web:
        base = f"{base} {consigne_sans_web()}"
    return base

# Outils web natifs d'Ollama, exposes au modele en function calling OpenAI.
# La requete de recherche part vers ollama.com : avec un modele LOCAL, --web
# est refuse sans --web-consenti (regle 108 : un repli est subi, jamais choisi).
OUTILS_WEB = [
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the web for current information.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "max_results": {"type": "integer", "minimum": 1, "maximum": 10, "description": "Maximum number of results"}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "web_fetch",
            "description": "Fetch content from a URL.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "URL to fetch"}
                },
                "required": ["url"]
            }
        }
    }
]

def appel_web(cle_web: str, outil: str, corps: dict) -> dict:
    url = "https://ollama.com/api/" + outil
    data = json.dumps(corps).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Authorization": "Bearer " + cle_web, "Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            reponse = json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        raise RuntimeError("appel web " + outil + " rate : " + str(exc)) from exc
    if "content" in reponse and isinstance(reponse["content"], str):
        reponse["content"] = reponse["content"][:4000]
    if "results" in reponse and isinstance(reponse["results"], list):
        for r in reponse["results"]:
            if isinstance(r, dict) and "content" in r and isinstance(r["content"], str):
                r["content"] = r["content"][:4000]
    return reponse

def executer_web(tache, cle, modele, messages, plafond, temperature, nom, refus, joints, consentement) -> dict:
    try:
        cle_web = cle_ollama()
    except SystemExit as exc:
        return {"nom": nom, "modele": modele, "erreur": str(exc), "code": 2}
    if modele.endswith("-local") and not consentement:
        return {"nom": nom, "modele": modele, "erreur": "la recherche web envoie la requete a ollama.com : ajouter --web-consenti pour l autoriser avec un modele local", "code": 2}
    recherches = lectures = 0
    urls = []
    final = None
    for _ in range(6):
        resultat = appeler(modele, messages, plafond, cle, temperature, outils=OUTILS_WEB)
        appels = resultat.get("tool_calls") or []
        if not appels:
            final = resultat
            break
        for appel in appels:
            fonction = (appel.get("function") or {}).get("name", "")
            try:
                arguments = json.loads((appel.get("function") or {}).get("arguments", "{}"))
                if not isinstance(arguments, dict):
                    arguments = {}
            except Exception:
                arguments = {}
            try:
                reponse = appel_web(cle_web, fonction, arguments)
            except Exception as exc:
                reponse = {"erreur": str(exc)}
            if fonction == "web_search":
                recherches += 1
                for r in reponse.get("results", []):
                    urls.append(r.get("url", ""))
            elif fonction == "web_fetch":
                lectures += 1
                urls.append(arguments.get("url", ""))
            messages.append({"role": "assistant", "content": "", "tool_calls": [appel]})
            messages.append({"role": "tool", "tool_call_id": appel.get("id"), "content": json.dumps(reponse, ensure_ascii=False)})
    if final is None:
        final = resultat
        final["web_incomplet"] = True
    if urls:
        final["texte"] = (final.get("texte") or "") + "\n\n" + "\n".join("source : " + u for u in urls)
    final["web"] = {"recherches": recherches, "lectures": lectures, "urls": urls}
    final.update({"nom": nom, "modele": modele, "refus": refus, "fichiers_joints": joints, "plan": plan_de(final.get("adresse", "?"))})
    return final

def executer(tache: dict, cle: str) -> dict:
    # Trois etats: preparation en cours, appel reseau parti, attente de reponse
    print(f"PREPARATION commence pour {tache.get('modele') or 'modele inconnu'}: lecture des pieces jointes et resolution du plan", file=sys.stderr, flush=True)
    local_seul = bool(tache.get("local_seul")) or os.environ.get("NEXUS_LOCAL_SEUL") == "1"
    nom = tache.get("nom") or tache.get("modele") or "tache"
    modele = tache.get("modele") or "adaptive-router"
    consigne = tache.get("tache") or ""
    if not consigne:
        return {"nom": nom, "erreur": "champ 'tache' vide"}
    racine_tache = tache.get("racine")
    corpus, refus, joints = charger_fichiers(tache.get("fichiers") or [], racine=racine_tache)
    systeme = composer_systeme(tache.get("systeme"), bool(tache.get("web")))
    contenu = consigne if not corpus else "%s\n\n%s" % (consigne, corpus)
    messages = [{"role": "system", "content": systeme},
                {"role": "user", "content": contenu}]
    plafond = int(tache.get("max_tokens") or 4096)
    temperature = tache.get("temperature", TEMPERATURE_DEFAUT)
    if tache.get("web"):
        return executer_web(tache, cle, modele, messages, plafond, temperature, nom, refus, joints, bool(tache.get("web_consenti")))

    if corpus and len(corpus) > FENETRE_CARACTERES:
        # Si la consigne indique explicitement la génération d'un fichier complet,
        # on refuse le découpage MAP-REDUCE et on renvoie une erreur claire.
        if demande_fichier_entier(consigne):
            return {
                "nom": nom,
                "modele": modele,
                "refus": refus,
                "fichiers_joints": joints,
                "plan": plan_de("?"),
                "decoupe_refusee": True,
                "erreur": ("Le corpus dépasse la fenêtre de caractères et la tâche demande "
                           "l'écriture d'un fichier complet ; réduction requise."),
                "texte": "",
            }
        resultat = carte_reduction(corpus, consigne, modele, cle, plafond,
                                   temperature, local_seul=local_seul)
        resultat.update({
            "nom": nom,
            "modele": modele,
            "refus": refus,
            "fichiers_joints": joints,
            "plan": plan_de(resultat.get("adresse", "?")),
        })
        if local_seul and resultat.get("plan") != "local":
            return {"nom": nom, "modele": modele,
                    "erreur": f"plan {resultat.get('plan')} servi alors que local_seul exigé"}
        if local_seul:
            resultat["local_seul"] = True
        return etiqueter_ecritures(resultat, tache, consigne)

    essais, echecs, ecartes = [], [], []
    troncatures = set()
    def _journal_echec(message: str):
        print(f"Echec candidat : {message}", file=sys.stderr, flush=True)
    if refus and not joints:
        _journal_echec("fichiers joints refuses ou absents : " + ", ".join(refus))
        return {"nom": nom, "modele": modele, "cause_vide": "fichiers_joints_absents",
                "erreur": "aucun fichier joint disponible : " + ", ".join(refus)}
    candidats = list(dict.fromkeys([modele] + replis_gratuits(cle)))
    _dj = None
    try:
        from nexus_disjoncteur import CircuitBreaker
        _dj = CircuitBreaker(failure_threshold=3)
        _c = [c for c in candidats if _dj.is_available(c)]
        # Un candidat ecarte ici ne doit JAMAIS finir dans `echecs` : les
        # deux boucles plus bas rejouent `echecs` dans _dj.record_failure,
        # et cela ferait echouer une SECONDE fois une cible qui n a meme
        # pas ete appelee, repoussant sans fin son recovery_timeout.
        # Trace separee : mesure du 2026-09-02, une cible ecartee parce
        # que son circuit etait deja ouvert ne laissait AUCUNE trace --
        # ni dans echecs, ni dans le message de bascule, ni dans l erreur
        # finale -- alors que c est exactement le cas ou le disjoncteur a
        # fait son travail et ou l appelant a le plus besoin du pourquoi.
        etat_dj = _dj.get_state()
        for c in candidats:
            if c not in _c:
                info = etat_dj.get(c, {})
                ecartes.append("%s : circuit %s (echecs=%s)" % (
                    c, info.get("state", "open"), info.get("fail_count", "?")))
        candidats = _c
    except Exception as e:
        sys.stderr.write(f"Warning: circuit breaker initialization failed: {e}\\n")
        _dj = None
    # la direction local vers cloud est interdite par le contrat et non pas deconseillee
    # auparavant la protection dependait d'une option de l'appelant, ce qui la rendait facultative
    # incident du 2026-09-01 avec les six modules de securite
    # un repli est subi et ne doit jamais elargir l'exposition
    # Populate cache of plans if absent
    try:
        if not hasattr(appeler, "_cache_plans"):
            appeler._cache_plans = plans_par_alias(cle)
    except Exception:
        appeler._cache_plans = {}
    # Ordre d'exposition : local(0) < cloud(1) < anthropic(2).
    # Mesure du 2026-09-02 : un alias INCONNU (jamais declare a la
    # passerelle, ou catalogue temporairement indisponible) ecrasait la
    # liste a lui seul ("candidats = [modele]"), si bien qu'un modele
    # inexistant epuisait le repli gratuit en UN SEUL candidat au lieu
    # des quatre REPLIS_GRATUITS attendus -- repli auto qui s'arretait
    # au premier echec au lieu de parcourir la liste.
    # Correctif : un rang inconnu vaut le rang le PLUS RESTRICTIF (local,
    # 0), jamais le plus permissif -- une intention non prouvee ne doit
    # jamais elargir l'exposition (contrat SS108). Le modele demande
    # reste tente en premier (sa propre resolution tranchera par un echec
    # HTTP explicite s'il n'existe pas) ; si le catalogue est totalement
    # indisponible (cache vide), aucun repli connu ne peut etre prouve
    # local et le comportement d'avant est conserve a l'identique : le
    # seul candidat tente reste le modele demande.
    ordre = {"local": 0, "cloud": 1, "anthropic": 2}
    plan_modele = appeler._cache_plans.get(modele, "inconnu")
    if plan_modele == "inconnu":
        candidats = [modele] + [
            c for c in candidats[1:]
            if ordre.get(appeler._cache_plans.get(c, "inconnu"), 3) == 0
        ]
    else:
        rank_requested = ordre.get(plan_modele, 3)
        candidats = [
            c for c in candidats
            if ordre.get(appeler._cache_plans.get(c, "inconnu"), 3) <= rank_requested
        ]

    if local_seul:
        candidats = [c for c in candidats if c.endswith("-local")]
        if not candidats:
            return {"nom": nom, "modele": modele,
                    "erreur": "aucun modele local disponible pour NEXUS_LOCAL_SEUL=1"}

    # Appliquer le plafond de replis locaux afin d'éviter de charger
    # de trop nombreux modèles locaux en mémoire.
    candidats, _ecartes_plafond = borner_replis_locaux(candidats, appeler._cache_plans)
    ecartes.extend(_ecartes_plafond)

    trunc_failure = None          # garde le premier échec par troncature
    dernier_degenere = None       # mémorise le dernier résultat dégenéré
    for candidat in candidats:
        if candidat in essais or candidat.startswith("claude-"):
            continue
        # BACKOFF EXPONENTIEL AVEC JITTER entre deux tentatives, patron du livre :
        # start 100 ms, double a chaque essai, plafonne a 30 s, plus un tirage
        # aleatoire qui evite que plusieurs agents reessaient au meme instant.
        # Aucune attente avant le PREMIER candidat : on ne paie le delai que
        # lorsqu'on rejoue apres un echec.
        if essais:
            try:
                import time as _t
                from nexus_disjoncteur import _retry_delay as _rd
                _t.sleep(min(_rd(len(essais) - 1), 5.0))
            except Exception:
                pass
        # Garde‑mémoire avant de tenter le repli local
        if appeler._cache_plans.get(candidat) == "local" and candidat != modele:
            poids, libre = poids_et_libre(candidat)
            if not memoire_suffisante(poids, libre):
                msg = "%s : ecarte, memoire insuffisante (%s Go libres pour %s Go)" % (
                    candidat, libre, poids)
                ecartes.append(msg)
                _journal_echec(msg)
                continue
            if poids is None:
                _journal_echec("%s : poids inconnu, repli local tente sans garde memoire" % candidat)

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
                    _journal_echec("%s : %s" % (candidat, second))
                    continue
            else:
                echecs.append("%s : HTTP %s : %s" % (candidat, exc.code, detail))
                _journal_echec("%s : HTTP %s : %s" % (candidat, exc.code, detail))
                continue
        except Exception as exc:
            echecs.append("%s : %s" % (candidat, exc))
            _journal_echec("%s : %s" % (candidat, exc))
            continue

        texte_vide = not (resultat.get("texte") or "").strip()
        if texte_vide:
            if resultat.get("tronque"):
                # Le modèle a consommé tout son budget sans produire de texte.
                # On consigne l'échec et on sort de la boucle pour reprendre le plafond immédiatement.
                if not reprise_utile(resultat.get("cause_vide"), plafond):
                    msg = "%s : raisonnement a epuise le budget (%s), bascule sans relever le plafond" % (
                        candidat, resultat.get("cause_vide"))
                    echecs.append(msg)
                    _journal_echec(msg)  # ligne où _journal_echec est défini : voir fonction locale dans executer
                    continue
                trunc_failure = resultat
                motif_troncature = "%s : reponse vide tronquee (demande %d jetons)" % (candidat, plafond)
                echecs.append(motif_troncature)
                troncatures.add(motif_troncature)
                print(f"troncature a {resultat.get('tokens',0)} jetons : reprise du plafond plutot que repli, un autre modele ne changerait rien", file=sys.stderr, flush=True)
                break
            echecs.append("%s : reponse vide (%d jetons consommes)"
                          % (candidat, resultat.get("tokens", 0)))
            _journal_echec("%s : reponse vide (%d jetons consommes)" % (candidat, resultat.get("tokens", 0)))
            continue
        if texte_degenere(resultat.get("texte") or ""):
            # On ne jette pas le rendu dégenéré : on le mémorise pour un éventuel retour.
            dernier_degenere = resultat
            echecs.append("%s : reponse degeneree (meme bloc repete, %d jetons)"
                          % (candidat, resultat.get("tokens", 0)))
            _journal_echec("%s : reponse degeneree (meme bloc repete, %d jetons)" % (candidat, resultat.get("tokens", 0)))
            continue

        # le champ modele porte le candidat servi; sans demande_initiale le modele demande est perdu (mesure 2026-08-31)
        try:
            if _dj is not None:
                _dj.record_success(candidat)
                for e in echecs:
                    if e in troncatures:
                        continue
                    parts = e.split(" : ", 1)
                    if len(parts) == 2:
                        cible, motif = parts
                        _dj.record_failure(cible, motif)
        except Exception as exc:
            print("enregistrement de la panne au disjoncteur rate : %s" % exc, file=sys.stderr)
        resultat.update({"nom": nom, "modele": candidat, "refus": refus,
                         "fichiers_joints": joints,
                         "plan": plan_de(resultat["adresse"]), "demande_initiale": modele})
        if local_seul and resultat.get("plan") != "local":
            return {"nom": nom, "modele": candidat,
                    "erreur": f"plan {resultat.get('plan')} servi alors que local_seul exigé"}
        if local_seul:
            resultat["local_seul"] = True
        if candidat != modele:
            trace = ecartes + echecs
            resultat["bascule"] = "%s -> %s apres : %s" % (
                modele, candidat, " | ".join(trace))
            resultat["demande_initiale"] = modele
            motif = next((e for e in trace if e.startswith(modele + " :")), "")
            if not motif and trace:
                motif = trace[-1]
            resultat["motif_bascule"] = motif
        servi = resultat.get("servi_par", "?")
        if est_degrade(modele, servi):
            resultat["degrade"] = True
            resultat["motif_degrade"] = "servi par %s (%s B) pour une demande de %s (%s B)" % (
                servi, taille_alias(servi), modele, taille_alias(modele))
        if resultat.get("tronque"):
            # Un rendu NON VIDE mais tronque (finish_reason == length) ne doit pas
            # etre livre incomplet : meme reprise que la troncature vide (banc, v20).
            new_plafond = min(plafond * 2, PLAFOND_REPRISE)
            if new_plafond > plafond and not tache.get("_reprise"):
                copie = dict(tache)
                copie["max_tokens"] = new_plafond
                copie["_reprise"] = True
                resultat = executer(copie, cle)
                resultat["reprise_plafond"] = "%s -> %s" % (plafond, new_plafond)
                return resultat
        return etiqueter_ecritures(resultat, tache, consigne)

    # Enregistrement de tous les échecs dans le disjoncteur (c'est le seul endroit où l'échec total est constaté)
    if _dj is not None:
        try:
            for e in echecs:
                if e in troncatures:
                    continue
                parts = e.split(" : ", 1)
                if len(parts) == 2:
                    cible, motif = parts
                    _dj.record_failure(cible, motif)
        except Exception as exc:
            print("enregistrement de la panne au disjoncteur rate : %s" % exc, file=sys.stderr)
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
        # mesure: onze taches sur 44 a 4000 jetons, reprise a plafond egal reproduirait meme appel
        new_plafond = min(plafond * 2, PLAFOND_REPRISE)
        if new_plafond > plafond and not tache.get('_reprise'):
            copie = dict(tache)
            copie['max_tokens'] = new_plafond
            copie['_reprise'] = True
            resultat = executer(copie, cle)
            resultat['reprise_plafond'] = f"{plafond} -> {new_plafond}"
            return resultat
        return trunc_failure

    # Aucun candidat n'a produit de texte ; si on a mémorisé un résultat dégenéré, le retourner.
    if dernier_degenere is not None:
        part = part_repetee(dernier_degenere.get("texte") or "", longueur_min=40, repetitions=5)
        dernier_degenere.update({
            "nom": nom,
            "modele": dernier_degenere.get("modele", candidat),
            "refus": refus,
            "plan": plan_de(dernier_degenere.get("adresse", "?")),
            "demande_initiale": modele,
            "degenere": True,
            "motif_degenere": f"meme bloc repete (part {part*100:.0f} %%)",
            "bascule": plan_de(dernier_degenere.get("adresse", "?"))
        })
        return dernier_degenere

    return {"nom": nom, "modele": modele,
            "erreur": "tous les replis gratuits ont echoue : " + " | ".join(ecartes + echecs)}


def taille_alias(nom: str) -> float | None:
    r"""
    Extrait le nombre de milliards de paramètres d'un nom de modèle ou d'alias.
    Recherche la plus grande valeur correspondant à l'expression
    (\d+(?:\.\d+)?)b(?![a-z0-9]) en minuscules, après suppression du préfixe
    fournisseur (tout avant le dernier '/' retiré).
    """
    # Retirer le préfixe fournisseur
    base = nom.rsplit("/", 1)[-1].lower()
    matches = re.findall(r"(\d+(?:\.\d+)?)b(?![a-z0-9])", base)
    if not matches:
        return None
    # Convertir toutes les correspondances en float et retourner la plus grande
    try:
        valeurs = [float(m) for m in matches]
        return max(valeurs) if valeurs else None
    except ValueError:
        return None


def est_degrade(demande: str, servi: str) -> bool:
    """
    Retourne True si les deux tailles sont connues et que la taille du modèle
    servi est strictement inférieure à la moitié de celle demandée.
    """
    taille_demande = taille_alias(demande)
    taille_servi = taille_alias(servi)
    if taille_demande is None or taille_servi is None:
        return False
    return taille_servi < (taille_demande / 2)


def rendre(resultat: dict) -> None:
    print("=" * 72)
    # Avertissement en cas de service dégradé
    if resultat.get("degrade"):
        print("[DEGRADE] " + resultat.get("motif_degrade", ""))
        print("[DEGRADE] reponse a ne pas utiliser sans relecture : le modele servi est bien plus petit que celui demande (--accepter-degrade pour lever le code 3)")
    if resultat.get("degenere"):
        print("[DEGENERE] " + resultat.get("motif_degenere", ""))
    if resultat.get("repli_passerelle"):
        servi = resultat.get("servi_par", "?")
        demande = resultat.get("demande_initiale") or resultat.get("modele", "?")
        print(f"[REPLI PASSERELLE] servi par {servi} au lieu de {demande}")
    print("  %s" % resultat["nom"])
    if resultat.get("web"):
        print('  [WEB] recherches=%d lectures=%d' % (
            resultat["web"].get("recherches", 0),
            resultat["web"].get("lectures", 0)))
    if resultat.get("erreur"):
        print("  ECHEC : %s" % resultat["erreur"])
        print("TRACABILITE: %s [%s] %s" % (
            resultat.get("servi_par", "?"),
            resultat.get("plan", "?"),
            resultat.get("adresse", "?")))
        print("=" * 72)
        return
    if resultat.get("bascule"):
        print("  BASCULE : %s" % resultat["bascule"])
    print("  demande : %s" % resultat.get("demande_initiale", resultat["modele"]))
    print("  servi   : %s  [%s]  %s" %
          (resultat.get("servi_par", "?"),
           resultat.get("plan", "?"),
           resultat.get("adresse", "?")))
    print("  %d tokens, %.0f s, cout %s" %
          (resultat.get("tokens", 0), resultat.get("duree", 0.0), resultat.get("cout", "0")))
    # Heuristique famille servie vs demande
    servi_par = resultat.get("servi_par", "?")
    if servi_par != "?":
        slash_idx = servi_par.rfind('/')
        colon_idx = servi_par.find(':', slash_idx + 1)
        if slash_idx != -1:
            start = slash_idx + 1
            end = colon_idx if colon_idx != -1 else len(servi_par)
            racine = servi_par[start:end]
        else:
            racine = ""
    else:
        racine = ""
    # exclusion du cas ou l'alias demande commence par adaptive-router
    if racine and racine != "?" and racine not in resultat.get("modele", "") and not resultat.get('modele', '').startswith('adaptive-router'):
        print("  [!] famille servie differente de la demande (heuristique) : %s -> %s" % (resultat["modele"], racine))
    # Avertissement rendu tronque
    if resultat.get('tronque'):
        n = resultat.get('tokens_sortie', 0)
        print("[!] RENDU TRONQUE a %d jetons de sortie" % n)
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
    # la tracabilite doit être PASSIVE, elle ne doit pas dépendre de la coopération du producteur
    print("TRACABILITE: %s [%s] %s" % (
        resultat.get("servi_par", "?"),
        resultat.get("plan", "?"),
        resultat.get("adresse", "?")))
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
    chemin = os.path.join(ROOT, "outillage", "competences")
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
    chemin = os.path.join(ROOT, "outillage", "competences", nom + ".txt")
    with io.open(chemin, encoding="utf-8") as fh:
        return fh.read()


def _ecrire_refus_sortie(sortie_path, taches, cause):
    if not sortie_path:
        return
    try:
        with io.open(sortie_path, 'w', encoding='utf-8', newline='\n') as fh:
            for t in taches:
                fh.write(json.dumps({'nom': t.get('nom', ''), 'refus': cause,
                    'texte': '', 'vide': True, 'cause_vide': 'refus_verrou', 'tokens': 0},
                    ensure_ascii=False) + '\n')
    except Exception as exc:
        print('refus non ecrit dans %s : %s' % (sortie_path, exc), file=sys.stderr)

def identifiant_lot(pid: int, debut_epoch: float) -> str:
    """Identifiant d'un lot : pid-epoch, porte par chaque ligne de --sortie."""
    return "%d-%d" % (pid, int(debut_epoch))

# Mesure du 2026-09-14 : 16 appels cloud simultanes vers gpt-oss-120b-cloud
# repondent en 2,5 a 4,8 s chacun, sans degradation ; saturation estimee vers 46.
# Le semaphore machine 'inference' etait a 3 slots, partages par TOUTES les
# sessions et par le validateur : trois processus suffisaient a faire attendre
# tout le monde. 12 garde une marge pour le pont MCP, qui ne prend pas ce semaphore.
PLAFOND_INFERENCE_CLOUD = 12

def main() -> int:
    with contextlib.suppress(Exception):
        # Premiere ligne a 11,6s sur 11,7s; run long indiscernable d'un run gele
        sys.stdout.reconfigure(line_buffering=True)
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
                         help="Consigne systeme prise dans outillage/competences/. "
                              "Disponibles : %s" % (", ".join(lister_competences()) or "aucune"))
    # Le défaut était 1500 quand le paramètre était inerte : la passerelle
    # ignorait max_tokens et appliquait 4096 (ou 8192 en cloud). Depuis que
    # le script envoie num_predict, la borne est réelle. Baisser ce défaut
    # régressait le comportement de tous les appelants qui ne le précisent pas.
    parseur.add_argument("--max-tokens", type=int, default=None,
                         help="Nombre maximum de jetons (défaut 4096). "
                              "Depuis la correction, la borne est réelle ; "
                              "un budget trop court rend une réponse vide. "
                              "Sans valeur explicite, le JSON du lot décide, et à défaut le budget vaut 4096.")
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
    parseur.add_argument(
        "--sortie-brute", default=None, metavar="FICHIER",
        help="Ecrire le seul champ texte du rendu, une ligne par tache, "
             "des qu'elle aboutit. Independant de --sortie : les deux "
             "peuvent etre demandes ensemble.")
    parseur.add_argument(
        "--depuis-jsonl", default=None, metavar="FICHIER",
        help="Lire les taches depuis un fichier JSONL.")
    parseur.add_argument(
        "--nom", default=None, metavar="NOM_TACHE",
        help="Nom de la tache a extraire pour sortie brute.")
    parseur.add_argument("--parallele", type=int, default=3,
                         help="Taches simultanees (defaut 3).")
    parseur.add_argument("--modeles", action="store_true",
                         help="Lister les modeles exposes par plan.")
    parseur.add_argument("--json", action="store_true",
                         help="Sortie machine au lieu du rapport lisible.")
    parseur.add_argument("--accepter-degrade", action="store_true",
                         help="Accepter un modele servi bien plus petit que demande (sinon code de sortie 3).")
    parseur.add_argument("--web", action="store_true",
                         help="Donner au modele les outils web d'Ollama (web_search, web_fetch) : la requete part vers ollama.com.")
    parseur.add_argument("--web-consenti", action="store_true",
                         help="Autoriser --web avec un modele LOCAL malgre la sortie de la requete vers ollama.com.")
    args = parseur.parse_args()

    # Vérifier que --nom est fourni lorsqu'on utilise --depuis-jsonl
    if args.depuis_jsonl and not args.nom:
        print("Erreur : l'option --nom est obligatoire avec --depuis-jsonl.", file=sys.stderr)
        sys.exit(2)

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
        # la symetrie avec la temperature est le but, une option voisine active et l'autre inerte etant un piege silencieux
        if args.max_tokens is not None:
            for t in taches:
                t['max_tokens'] = args.max_tokens
        # troisieme option de cette classe ; le message d'erreur conseillait une option inerte
        if args.racine is not None:
            for t in taches:
                t['racine'] = args.racine
        # regle desormais UNIFORME pour toutes les options : celle passee explicitement en ligne de commande l'emporte sur le JSON, et que c'etait l'asymetrie non dite qui constituait le piege
        if args.fichiers:
            for t in taches:
                t['fichiers'] = args.fichiers
        if args.systeme is not None:
            for t in taches:
                t['systeme'] = args.systeme
    elif args.tache:
        taches = [{"nom": args.modele, "modele": args.modele, "tache": args.tache,
                   "fichiers": args.fichiers, "systeme": args.systeme,
                   "max_tokens": (args.max_tokens or 4096),
                   "temperature": (args.temperature if args.temperature is not None
                                   else TEMPERATURE_DEFAUT),
                   "racine": args.racine,
                   "web": getattr(args, "web", False),
                   "web_consenti": getattr(args, "web_consenti", False)}]
    else:
        if args.depuis_jsonl:
            if not args.nom:
                print("L'option --nom est obligatoire avec --depuis-jsonl.", file=sys.stderr)
                return 2
            try:
                last_any = None
                last_success = None
                last_tache = None
                lignes_invalides = 0
                with io.open(args.depuis_jsonl, "r", encoding="utf-8") as src:
                    for ligne in src:
                        try:
                            obj = json.loads(ligne)
                        except Exception:
                            lignes_invalides += 1
                            continue
                        if obj.get("en_tete") or obj.get("fin"):
                            continue
                        if obj.get("nom") != args.nom:
                            continue
                        last_any = obj
                        if obj.get("tache"):
                            last_tache = obj
                        texte = (obj.get("texte") or "").strip()
                        erreur = (obj.get("erreur") or "").strip()
                        if texte and not erreur:
                            last_success = obj
                if not last_any:
                    print("[!] tache %s introuvable dans %s" % (args.nom, args.depuis_jsonl), file=sys.stderr)
                    return 1
                # choisir la tâche à rejouer
                taches = [last_tache if last_tache else last_any]
                # le nombre de lignes invalides est conservé pour le bloc sortie brute
            except Exception as exc:
                print("[!] erreur lors de la lecture du jsonl : %s" % exc, file=sys.stderr)
                return 1
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
    if args.web:
        for t in taches:
            t["web"] = True
    if args.web_consenti:
        for t in taches:
            t["web_consenti"] = True

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
    pile_verrou = contextlib.ExitStack()
    est_local = False
    try:
        plans = plans_par_alias(cle)
        for t in taches:
            nom = t.get('modele') or ''
            if plans.get(nom) == 'local' or nom.endswith('-local'):
                est_local = True
                break
    except Exception:
        est_local = True  # profil illisible : ne pas desactiver la protection
    if est_local:
        # l'attente est bornee a 120 secondes pour qu'une contention reste visible au lieu de devenir un blocage silencieux
        from nexus_verrou_machine import verrou
        try: attente_verrou = float(os.getenv('NEXUS_VERROU_ATTENTE_S', 120))
        except ValueError: attente_verrou = 120 # une valeur gravee ment le lendemain, et surtout une epreuve ne peut pas solliciter le REFUS du verrou si elle doit le tenir plus de deux minutes — un verrou qu'on n'a jamais vu refuser n'est pas mesure.
        ctx = pile_verrou.enter_context(verrou('banc', projet=(os.path.basename(racine_travail()) or 'nexus'), attente_s=attente_verrou, bavard=True, annoncer=lambda m: print(m, file=sys.stderr, flush=True)))
        if not ctx.obtenu:
            # le refus est un echec assume car un travail local non fait ne doit jamais passer pour un travail fait
            pile_verrou.close()
            print('banc: contention detectee', file=sys.stderr)
            _ecrire_refus_sortie(getattr(args, 'sortie', None), taches, 'banc: contention detectee')
            return 75
    est_cloud = any(str(t.get('modele', '')).endswith('-cloud') for t in taches)
    if est_cloud:
        from nexus_verrou_machine import semaphore
        try: n_inf = int(os.getenv('NEXUS_SEMAPHORE_INFERENCE_N', PLAFOND_INFERENCE_CLOUD))
        except ValueError: n_inf = PLAFOND_INFERENCE_CLOUD
        try: attente_inf = float(os.getenv('NEXUS_SEMAPHORE_INFERENCE_ATTENTE_S', 120))
        except ValueError: attente_inf = 120
        ctx_inf = pile_verrou.enter_context(semaphore('inference', n_inf, projet=(os.path.basename(racine_travail()) or 'nexus'), attente_s=attente_inf, bavard=True, annoncer=lambda m: print(m, file=sys.stderr, flush=True)))
        if not ctx_inf.obtenu:
            pile_verrou.close()
            print('inference: semaphore cloud plein (contention machine)', file=sys.stderr)
            _ecrire_refus_sortie(getattr(args, 'sortie', None), taches, 'inference: semaphore cloud plein (contention machine)')
            return 75
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
        # Protection contre l'écrasement silencieux du fichier de sortie.
        # Si le fichier existe déjà et n'est pas vide, on le renomme avec un
        # horodatage avant d'ouvrir le nouveau fichier en écriture.
        import datetime
        sortie_path = args.sortie
        if sortie_path:
            try:
                if os.path.isfile(sortie_path) and os.path.getsize(sortie_path) > 0:
                    ts = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
                    nouveau_nom = f"{sortie_path}.{ts}"
                    os.rename(sortie_path, nouveau_nom)
                    print(f"[i] fichier de sortie existant renommé en {nouveau_nom}",
                          file=sys.stderr)
                flux = io.open(sortie_path, "w", encoding="utf-8", newline="\n")
                lot_id = identifiant_lot(os.getpid(), time.time())
                en_tete = {"en_tete": True, "lot_id": lot_id, "lot": args.lot or "tache_unique", "parallele": args.parallele, "nb_taches": len(taches)}
                flux.write(json.dumps(en_tete, ensure_ascii=False) + "\n")
                flux.flush()
            except Exception as exc:
                print("[!] sortie incrémentale impossible : %s" % exc,
                      file=sys.stderr)
                flux = None
        else:
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
            if args.sortie_brute and args.depuis_jsonl and args.nom:
                try:
                    last_any = None
                    last_success = None
                    lignes_invalides = 0
                    with io.open(args.depuis_jsonl, "r", encoding="utf-8") as src:
                        for ligne in src:
                            try:
                                obj = json.loads(ligne)
                            except Exception:
                                lignes_invalides += 1
                                continue
                            if obj.get("nom") != args.nom:
                                continue
                            last_any = obj
                            texte = (obj.get("texte") or "").strip()
                            erreur = (obj.get("erreur") or "").strip()
                            if texte and not erreur:
                                last_success = obj
                    if not last_any:
                        print("[!] tache %s introuvable dans %s" % (args.nom, args.depuis_jsonl), file=sys.stderr)
                        sys.exit(1)
                    if last_success:
                        texte = last_success.get("texte") or ""
                        texte = decaper_cloture_englobante(texte)
                        mode = "a" if os.path.exists(args.sortie_brute) and os.path.getsize(args.sortie_brute) > 0 else "w"
                        with io.open(args.sortie_brute, mode, encoding="utf-8", newline="\n") as dst:
                            dst.write(texte + "\n")
                        if lignes_invalides:
                            print("[!] %d ligne(s) JSON invalide(s) ignorée(s) dans %s" % (lignes_invalides, args.depuis_jsonl), file=sys.stderr)
                        sys.exit(0)
                    else:
                        derniere_erreur = (last_any.get("erreur") or "")[:160]
                        print("[!] tache %s : %d ligne(s) dans %s, aucune reussie (derniere erreur : %s)" % (
                            args.nom, 1, args.depuis_jsonl, derniere_erreur), file=sys.stderr)
                        if lignes_invalides:
                            print("[!] %d ligne(s) JSON invalide(s) ignorée(s) dans %s" % (lignes_invalides, args.depuis_jsonl), file=sys.stderr)
                        sys.exit(1)
                except Exception as exc:
                    print("[!] erreur lors de la sortie brute depuis jsonl : %s" % exc, file=sys.stderr)
                    sys.exit(1)
            # Collecte des tâches associées aux résultats pour pouvoir les rejouer si besoin.
            futurs = {pool.submit(executer, t, cle): t for t in taches}
            # Liste parallèle pour garder l'ordre d'arrivée des résultats.
            taches_par_futur = []
            for futur in concurrent.futures.as_completed(futurs):
                r = futur.result()
                resultats.append(r)
                taches_par_futur.append(futurs[futur])
                faits += 1
                if flux is not None:
                    r["lot_id"] = lot_id
                    flux.write(json.dumps(r, ensure_ascii=False) + "\n")
                    flux.flush()
                if args.sortie_brute:
                    try:
                        with io.open(args.sortie_brute, "a", encoding="utf-8",
                                     newline="\n") as fbrut:
                            fbrut.write(decaper_cloture_englobante(r.get("texte") or "") + "\n")
                    except Exception as exc:
                        print("[!] sortie brute impossible : %s" % exc,
                              file=sys.stderr)
                # L'AVANCEMENT VA SUR STDERR, jamais sur stdout : celui-ci porte
                # le rapport, et le polluer le rendrait illisible a un appelant
                # qui le parse.
                print("  [%d/%d] %s" % (faits, len(taches),
                                        r.get("nom") or r.get("modele") or "?"),
                      file=sys.stderr)

            # Si on était en mode parallèle et que certaines fenêtres sont manquantes,
            # les rejouer une seule fois en séquentiel (une par une) afin de récupérer
            # les résultats perdus sans boucler indéfiniment.
            if largeur > 1:
                for idx, (res, t) in enumerate(zip(resultats, taches_par_futur, strict=False)):
                    if _manquante(res):
                        # Rejouer la tâche séquentiellement.
                        new_res = executer(t, cle)
                        # Remplacer le résultat vide par le nouveau.
                        resultats[idx] = new_res
                        # Écrire le nouveau résultat dans le flux de sortie si nécessaire.
                        if flux is not None:
                            flux.write(json.dumps(new_res, ensure_ascii=False) + "\n")
                            flux.flush()
                        if args.sortie_brute:
                            try:
                                with io.open(args.sortie_brute, "a", encoding="utf-8",
                                             newline="\n") as fbrut:
                                    fbrut.write(decaper_cloture_englobante(new_res.get("texte") or "") + "\n")
                            except Exception as exc:
                                print("[!] sortie brute impossible : %s" % exc,
                                      file=sys.stderr)
    finally:
        # Un fichier sans marque de fin est indiscernable d'un fichier tronque.
        # L'absence de cette ligne signifie EN COURS ou INTERROMPU.
        if flux is not None:
            try:
                flux.write(json.dumps({"fin": True, "lot_id": lot_id, "taches_ecrites": faits}, ensure_ascii=False) + "\n")
                flux.flush()
            except Exception:
                pass
            flux.close()
        if flux is not None:
            flux.close()
        # Une erreur a la fermeture ne doit pas masquer l'erreur d'origine
        with contextlib.suppress(Exception):
            pile_verrou.close()

    if args.json:
        print(json.dumps(resultats, ensure_ascii=False, indent=2))
        return 0

    ordre = {t.get("nom") or t.get("modele"): i for i, t in enumerate(taches)}
    for resultat in sorted(resultats, key=lambda r: ordre.get(r["nom"], 99)):
        rendre(resultat)

    echecs = [r for r in resultats if r.get("erreur")]
    tronquees = [r for r in resultats if r.get("tronque") and not r.get("erreur")]
    etiquetees = [r for r in resultats if r.get("etiquete")]
    reussies = [r for r in resultats if not r.get("erreur") and not r.get("tronque") and not r.get("etiquete") and (r.get("texte") or "").strip()]
    vides = [r for r in resultats if not r.get("erreur") and not r.get("tronque") and not r.get("etiquete") and not (r.get("texte") or "").strip()]
    factures = [r for r in resultats if r.get("plan") == "anthropic"]
    total = sum(r.get("tokens", 0) for r in resultats)
    print("  %d tache(s) : %d reussie(s), %d rendues vides, %d etiquetee(s), %d tronquee(s), %d echec(s), "
          "%d token(s), %.0f s au total"
          % (len(resultats), len(reussies), len(vides), len(etiquetees), len(tronquees), len(echecs),
             total, time.time() - depart))
    # question par tache et la question par vague sont differentes
    # comptage des familles distinctes
    resultats_sans_erreur = [r for r in resultats if not r.get("erreur")]
    if len(resultats_sans_erreur) >= 2:
        familles = {r["servi_par"] for r in resultats_sans_erreur
                    if r.get("servi_par") and r["servi_par"] != "?"}
        N = len(resultats_sans_erreur)
        M = len(familles)
        print(f"  {N} alias -> {M} famille(s) distincte(s)")
        if M < N:
            print("  [!] Des taches ont partage une meme famille, le croisement n'a pas eu lieu")
    if factures:
        print("  [!] %d tache(s) servies par Anthropic, donc FACTUREES : %s"
              % (len(factures), ", ".join(r["nom"] for r in factures)))
    if (any(r.get("degrade") for r in resultats) and not args.accepter_degrade) or any(r.get("degenere") for r in resultats):
        return 3
    return 1 if echecs else 0


if __name__ == "__main__":
    sys.exit(main())
