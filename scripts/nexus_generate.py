# -*- coding: utf-8 -*-
"""
Générateur de configuration Claude-Local-Nexus.

Ne réécrit que les zones délimitées par les marqueurs :
    # >>> AUTOGEN:<NOM> ... # <<< AUTOGEN:<NOM>

Tout le reste de litellm_config.yaml est main-maintenu : les blocs des
modèles locaux, leurs fenêtres de contexte et leurs profils de capacité
relèvent d'un jugement humain et ne sont jamais touchés ici.

Ce qui est généré l'est à partir de deux sources de vérité vivantes :
    - le catalogue Ollama Cloud (https://ollama.com/api/tags) ;
    - la liste des modèles réellement déclarés dans la configuration.

Les graphes de fallback sont dérivés, jamais écrits à la main. Ils sont
donc acycliques par construction (chaîne strictement descendante) et ne
franchissent jamais une frontière de modalité ni de fournisseur (§17, §65, §66).

Usage :
    python scripts/nexus_generate.py [--dry-run] [--no-validate]

La validation des droits est active par defaut.
"""
from __future__ import annotations

import argparse
import datetime
import io
import itertools
import json
import os
import re
import statistics
import subprocess
import sys
import urllib.request

try:
    import yaml
except ImportError:
    print("ERREUR: PyYAML est requis (pip install pyyaml)")
    sys.exit(1)

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
CONFIG = os.path.join(ROOT, "litellm_config.yaml")
CLOUD_LIST = os.path.join(ROOT, "cloud_models.txt")
TAGS_URL = "https://ollama.com/api/tags"

# Adresse du moteur d'inférence local, vue depuis le conteneur LiteLLM.
#   http://ollama:11434                 Ollama dans Docker
#   http://host.docker.internal:11434   Ollama sur l'hôte
# Sortir Ollama de Docker n'est pas cosmétique : dans le conteneur, le
# moteur est plafonné par la mémoire allouée à la VM WSL2 — sur cette
# machine, la moitié de la RAM lui est inaccessible.
SONDES = {
    "http://ollama:11434": "http://127.0.0.1:11435",
    "http://host.docker.internal:11434": "http://127.0.0.1:11434",
}


def _endpoint_par_defaut() -> str:
    """
    Adresse du moteur, déduite de la configuration en place.

    La valeur était auparavant `http://ollama:11434` en dur, à charge pour
    l'appelant de poser `NEXUS_OLLAMA_ENDPOINT`. Après la sortie du moteur
    hors de Docker, une régénération lancée sans cette variable a réécrit
    dix déclarations vers le conteneur supprimé — silencieusement, puisque
    le fichier restait syntaxiquement valide. Un défaut qui ne se
    manifeste qu'à travers une variable d'environnement oubliée est un
    défaut qui se reproduira.

    La configuration sait déjà où LiteLLM envoie ses requêtes : c'est elle
    qui décide, et la variable ne sert plus qu'à forcer une bascule.

    Le moteur est celui de la MAJORITÉ des déclarations, pas le premier
    rencontré. Une configuration peut être partiellement réécrite — c'est
    exactement l'état laissé par la régénération fautive, dix adresses
    Docker parmi vingt adresses hôte. Trancher sur la première occurrence
    aurait alors désigné le moteur minoritaire, et figé l'erreur au lieu
    de la corriger.
    """
    try:
        texte = io.open(CONFIG, encoding="utf-8").read()
    except Exception:
        return "http://host.docker.internal:11434"
    compte = {a: texte.count(a) for a in SONDES}
    gagnant = max(compte, key=lambda a: compte[a])
    return gagnant if compte[gagnant] else "http://host.docker.internal:11434"


OLLAMA_ENDPOINT = os.environ.get("NEXUS_OLLAMA_ENDPOINT") or _endpoint_par_defaut()

# Classement de capacité du catalogue cloud. Plus le rang est bas, plus le
# modèle est considéré capable. Un modèle inconnu tombe en fin de chaîne
# plutôt que d'être ignoré : le script reste tolérant aux nouveautés.
CLOUD_RANKS = [
    (r"^qwen3\.5:397b", 10),
    (r"^deepseek-v4-pro", 20),
    (r"^kimi-k3", 30),
    (r"^glm-5\.3$", 40),
    (r"^mistral-large-3", 50),
    (r"^minimax-m3", 60),
    (r"^nemotron-3-ultra", 70),
    (r"^kimi-k2\.7-code", 80),
    (r"^glm-5\.2$", 90),
    (r"^deepseek-v4-flash", 100),
    (r"^gpt-oss:120b", 110),
    (r"^nemotron-3-super", 120),
    (r"^glm-5\.3-flash", 130),
    (r"^minimax-m2\.7", 140),
    (r"^kimi-k2\.6", 150),
    (r"^glm-5\.1$", 160),
    (r"^gpt-oss:20b", 170),
    (r"^nemotron-3-nano", 180),
    (r"^gemma4", 190),
]

# Codes qui prouvent une absence de droit. Tout le reste (429, 5xx,
# timeout, coupure reseau) est traite comme passager.
ENTITLEMENT_CODES = {401, 402, 403, 404}

CODE_HINT = re.compile(r"cod(er|e)|devstral|qwen|codestral")
VISION_HINT = re.compile(r"vision|llava")
EMBED_HINT = re.compile(r"embed|minilm")


def cloud_rank(name: str) -> int:
    for pattern, rank in CLOUD_RANKS:
        if re.search(pattern, name):
            return rank
    return 900


def cloud_alias(base: str) -> str:
    """Seuls les ':' deviennent '-' : les points restent lisibles."""
    return base.replace(":", "-") + "-cloud"


def quality_tier(rank: int) -> int:
    if rank <= 60:
        return 3
    if rank <= 140:
        return 2
    return 1


# ----------------------------------------------------------------------
# Découverte du catalogue cloud
# ----------------------------------------------------------------------
def discover_cloud() -> list[str]:
    """
    Catalogue Ollama Cloud.

    La lecture est gardée comme celle de `discover_local`, et pour la même
    raison : une trace nue au milieu d'une régénération laisse la
    configuration dans un état à moitié réécrit, alors qu'un message clair
    permet de recommencer. La différence de contrat est voulue — ici
    l'échec est levé plutôt que rendu comme None, parce qu'un catalogue
    cloud vide ne doit jamais servir de base à une régénération : ce
    serait effacer la zone CLOUD_MODELS au premier incident réseau.
    """
    try:
        with urllib.request.urlopen(TAGS_URL, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        # LA CAUSE VOYAGE AVEC LE REFUS.
        #
        # Sans `from exc`, Python affiche « During handling of the above
        # exception, another exception occurred » et le traceback d'origine
        # devient un bruit dont rien ne dit qu'il EST la cause. Le message
        # cite deja `exc`, mais un message n'est pas un traceback : il ne
        # porte ni le fichier, ni la ligne, ni la pile de l'echec reel.
        # C'est la classe 1 de nexus_traque, sous une forme plus discrete.
        raise RuntimeError(
            "catalogue cloud illisible sur %s (%s) — regeneration interrompue "
            "plutot que d'ecrire une zone CLOUD_MODELS vide" % (TAGS_URL, exc)) from exc
    names = sorted({m["name"] for m in payload.get("models", [])})
    if not names:
        raise RuntimeError("catalogue cloud vide")
    return sorted(names, key=lambda n: (cloud_rank(n), n))


def choisir_pool_exact(candidats: list, budget_go: float,
                       taille_min: int = 2, taille_max: int = 6) -> tuple:
    """
    Meilleur sous-ensemble de modeles, par ENUMERATION EXACTE.

    C'est un sac a dos 0-1 a contrainte de cardinalite. La piste
    metaheuristique a ete poursuivie puis REJETEE SUR MESURE (106.2) : pour
    40 candidats en tailles 4 a 6, il y a 4 587 778 combinaisons, et le
    balayage complet des tailles 2 a 4 s'acheve en 0,00 s sur cet hote. Une
    metaheuristique rendrait une reponse approchee a un probleme qui en a une
    exacte, avec plus de code et plus de parametres a regler.

    Le glouton qu'elle remplace n'etait pas optimal non plus : trier puis
    accumuler jusqu'au budget donne l'optimum quand les poids sont egaux, et
    seulement alors. Ici ils vont de 0,4 a 20 Go.

    Trois departages, dans cet ordre, et chacun compte :

      score decroissant   la qualite d'abord ;
      POIDS CROISSANT     a score egal, laisser de la memoire libre est
                          strictement meilleur -- elle sert au moteur ;
      taille croissante,  pour que le resultat soit DETERMINISTE. Deux
      puis alphabetique   executions sur les memes donnees doivent rendre
                          exactement le meme pool, sinon la configuration
                          generee change sans raison et le diff ment.

    Un debit non mesure prend la MEDIANE des debits connus, et non zero :
    l'absence de mesure n'est pas une mesure de zero. Si rien n'est mesure,
    tous prennent 1.0 et le score retombe sur le seul tier.
    """
    mesures = [c["debit"] for c in candidats if c.get("debit") is not None]
    defaut = statistics.median(mesures) if mesures else 1.0

    # Les scores sont calcules A COTE, jamais ecrits dans les dicts recus :
    # muter l'entree d'une fonction de choix est un effet de bord silencieux
    # que l'appelant ne voit pas venir.
    score = {c["alias"]: c.get("tier", 0) *
             (c["debit"] if c.get("debit") is not None else defaut)
             for c in candidats}
    poids = {c["alias"]: float(c.get("poids") or 0.0) for c in candidats}
    alias = sorted(poids)

    meilleur, cle_meilleure, examinees = None, None, 0
    haut = min(taille_max, len(alias))
    for taille in range(max(taille_min, 1), haut + 1):
        for combo in itertools.combinations(alias, taille):
            examinees += 1
            p = sum(poids[a] for a in combo)
            if p > budget_go:
                continue
            s = sum(score[a] for a in combo)
            # Maximiser le score, minimiser le poids, minimiser la taille,
            # puis ordre alphabetique croissant -- d'ou les signes.
            cle = (-s, p, taille, combo)
            if cle_meilleure is None or cle < cle_meilleure:
                cle_meilleure, meilleur = cle, combo

    if meilleur is None:
        # Aucun sous-ensemble admissible : les plus legers, plutot que rien.
        # Un pool vide ne route pas, et un minimum degrade se voit dans la
        # configuration alors qu'une absence passerait inapercue.
        legers = sorted(alias, key=lambda a: (poids[a], a))[:taille_min]
        return legers, 0.0, sum(poids[a] for a in legers), examinees

    ordonnes = sorted(meilleur, key=lambda a: (-score[a], a))
    return (ordonnes, sum(score[a] for a in meilleur),
            sum(poids[a] for a in meilleur), examinees)


def capacites_ollama(nom_base: str, timeout: int = 20) -> set:
    """
    Capacites que le MOTEUR declare pour un modele. Set vide = inconnu.

    Le nom d'un modele est une convention ; la declaration du moteur est un
    fait. Les motifs qui devinaient la capacite d'apres le nom se sont tous
    reveles faux, mesure le 2026-08-30 sur 36 modeles locaux :

      VISION_HINT « vision|llava » ne voyait pas qwen3-vl : DEUX modeles de
      vision etaient classes texte, ce que les 17 et 92 interdisent.
      CODE_HINT contenait « qwen » : six generalistes passaient pour des
      specialistes du code, dont qwen3:0.6b, destine a repondre par oui ou
      par non.
      EMBED_HINT « embed|minilm » ne voyait pas bge-m3 -- angle mort corrige
      deux fois ailleurs sans jamais l'etre a sa source.

    Un set VIDE signifie « inconnu », jamais « aucune capacite ». L'appelant
    doit alors se rabattre sur autre chose plutot que de conclure.

    Ecrite par le banc gratuit sur consigne, integrée apres verification.
    """
    try:
        r = subprocess.run(["ollama", "show", nom_base], capture_output=True,
                           text=True, timeout=timeout, encoding="utf-8",
                           errors="replace")
        if r.returncode != 0:
            return set()
        dedans, trouvees = False, set()
        for ligne in r.stdout.splitlines():
            if not dedans:
                if ligne.strip().lower() == "capabilities":
                    dedans = True
                continue
            if not ligne.strip() or not ligne[0].isspace():
                break
            trouvees.add(ligne.strip().lower())
        return trouvees
    except Exception:
        return set()


def local_alias(base: str) -> str:
    """
    Alias d'un modèle Ollama installé.

    Le tag ':latest' est retiré car il n'apporte rien au nom logique, puis
    les ':' deviennent '-'. La règle reproduit exactement les alias déjà
    écrits à la main (qwen3-coder:30b -> qwen3-coder-30b-local), ce qui
    permet de reconnaître un modèle déjà déclaré et de ne pas le doubler.
    """
    if base.endswith(":latest"):
        base = base[: -len(":latest")]
    return base.replace(":", "-") + "-local"


# Adresse du moteur telle qu'ecrite dans la configuration, et adresse
# equivalente vue depuis cette machine. La premiere sert aux conteneurs,
# la seconde a ce script -- qui tourne sur l'hote et ne resout ni
# `ollama` ni `host.docker.internal`. La table double celle de
# nexus_switch_engine.py : elles doivent rester alignees.


def sonde_moteur() -> str:
    """
    Adresse a interroger pour inventorier le moteur local.

    Elle est déduite de la même façon que l'adresse écrite dans la
    configuration : les deux doivent désigner le même moteur, sinon le
    script inventorie une machine et configure l'autre.
    """
    return SONDES.get(OLLAMA_ENDPOINT, "http://127.0.0.1:11434")


def discover_local() -> list[str] | None:
    """
    Inventaire réel du moteur Ollama.

    Renvoie **None** si l'inventaire n'a pas pu être lu — jamais une liste
    vide. La confusion coûtait cher : la zone LOCAL_MODELS_EXTRA était
    alors régénérée à vide, supprimant d'un coup dix-huit déclarations,
    sans un mot.

    L'inventaire suit le moteur CONFIGURE, pas un emplacement en dur. La
    version precedente appelait `docker exec ollama-server ollama list` :
    apres la sortie du moteur hors de Docker, elle a continue de decrire
    le conteneur pendant que LiteLLM servait depuis l'hote. Les deux
    inventaires divergeaient de dix-huit modeles ; la configuration
    generee aurait declare des alias que le moteur servant ne connaissait
    plus, soit dix-huit 404 differes.
    """
    url = sonde_moteur() + "/api/tags"
    try:
        with urllib.request.urlopen(url, timeout=30) as reponse:
            charge = json.loads(reponse.read().decode("utf-8"))
        entrees = [(m["name"], m.get("size") or 0)
                   for m in charge.get("models", []) if m.get("name")]
        if entrees:
            # Les modeles cloud apparaissent dans le meme inventaire depuis
            # qu'Ollama les expose localement ; ils relevent du pool cloud,
            # pas du pool local, et ne doivent pas etre declares deux fois.
            #
            # DEUX criteres, et non un seul. Le suffixe ':cloud' est une
            # CONVENTION DE NOM : si Ollama la change, un modele cloud
            # passerait le filtre et serait declare sous un alias '-local'
            # pointant vers le moteur local. Ce serait une fuite silencieuse,
            # exactement ce que la section 34 interdit -- annoncer local ce
            # qui sort de la machine.
            #
            # Le second critere est physique et ne depend d'aucune
            # convention : un modele cloud n'a pas ses poids ici. Mesure du
            # 2026-08-30 sur cet hote :
            #
            #     glm-5.2:cloud          290 octets   (756B annonces)
            #     glm-5.3-flash:cloud    317 octets   (321B annonces)
            #     all-minilm:latest       45,9 Mo     <- plus petit modele reel
            #
            # Sept cent cinquante milliards de parametres ne tiennent pas
            # dans 290 octets : c'est un manifeste. Cinq ordres de grandeur
            # separent les deux populations, d'ou le seuil ci-dessous, qui
            # garde 3000x de marge d'un cote et 45x de l'autre.
            locaux, ecartes = [], []
            for nom, taille in entrees:
                par_nom = nom.endswith(":cloud")
                par_taille = taille < SEUIL_POIDS_REELS
                if par_nom or par_taille:
                    ecartes.append((nom, par_nom, par_taille, taille))
                else:
                    locaux.append(nom)
            # Une DIVERGENCE entre les deux criteres n'est pas resolue en
            # silence : elle signale que la convention a bouge, ou qu'un
            # modele local est anormalement leger. Le resultat reste sur
            # l'exclusion -- prudent par defaut -- mais il est dit.
            for nom, par_nom, par_taille, taille in ecartes:
                if par_nom != par_taille:
                    print("  [!] %s ecarte du pool local sur un seul critere "
                          "(nom cloud: %s, poids absents: %s, %s octets) — "
                          "verifier si la convention Ollama a change"
                          % (nom, par_nom, par_taille, format(taille, ",")))
            return sorted(set(locaux))
        print("  [!] inventaire vide sur %s" % url)
        return None
    except Exception as exc:
        print("  [!] inventaire local illisible sur %s (%s)" % (url, exc))
        return None


def local_context(base: str, profile: dict | None = None) -> int:
    """
    Fenêtre attribuée aux modèles exposés automatiquement.

    Elle suit le matériel plutôt qu'une constante. Sur un hôte CPU, le
    contexte se paie en RAM et en latence, et la capacité annoncée d'un
    modèle ne rend pas son allocation raisonnable (§26) : on reste donc
    conservateur. Avec une VRAM dédiée, le cache KV cesse d'être le
    facteur limitant et les fenêtres s'élargissent d'elles-mêmes.

    C'est ce qui permet d'ajouter une carte graphique plus tard sans
    réécrire quoi que ce soit : les seuils suivent la mesure.
    """
    if EMBED_HINT.search(base):
        return 8192

    match = re.search(r"(\d+(?:\.\d+)?)b", base.lower())
    petit = bool(match and float(match.group(1)) <= 9)

    if profile and profile.get("gpu_usable_for_offload"):
        # VRAM dédiée : la fenêtre devient abordable. On reste en deçà de
        # ce que le modèle annonce, car le cache KV doit tenir à côté des
        # poids dans la même VRAM.
        vram = profile["gpu"]["vram_gb"]
        if vram >= 24:
            return 131072 if petit else 65536
        if vram >= 12:
            return 65536 if petit else 32768
        return 32768 if petit else 16384

    return 16384 if petit else 8192


def render_local_extra(installed: list[str], declared: set[str],
                       profile: dict | None = None,
                       sizes: dict[str, float] | None = None) -> list[str]:
    """
    Expose les modèles Ollama non déclarés à la main.

    Le profil matériel tranche : un modèle que la machine ne peut pas
    exécuter n'est pas déclaré du tout — l'exposer reviendrait à offrir
    une porte qui ne mène nulle part.
    """
    out: list[str] = []
    sizes = sizes or {}
    extra = [b for b in installed if local_alias(b) not in declared]
    rendered = []
    for base in extra:
        if profile:
            state, reason = capability.verdict(sizes.get(base, 0.0), profile)
            if state in (capability.REJECT, capability.UNKNOWN):
                print("  [ecarte] %s : %s" % (base, reason))
                continue
        else:
            state, reason = capability.ACCEPT, ""
        rendered.append((base, state, reason))

    releve = latences_relevees()
    for i, (base, state, reason) in enumerate(rendered):
        alias = local_alias(base)
        ctx = local_context(base, profile)
        is_embed = bool(EMBED_HINT.search(base))
        # PROMOTION MECANISEE.
        #
        # Le verdict de capability juge la MEMOIRE ; il ne dit rien de la
        # vitesse. Un modele qui tient dans la RAM peut mettre plusieurs
        # minutes a rendre un mot, et n'a alors pas sa place dans un routage
        # automatique. Le releve de nexus_bench.py fournit ce second critere.
        #
        # Les deux doivent etre satisfaits : DEGRADED reste hors pool quelle
        # que soit sa latence, et un ACCEPT jamais mesure y reste aussi --
        # l'absence de preuve n'est pas une preuve.
        rapide, motif_latence = eligible_au_pool(alias, releve)
        dans_pool = (state == capability.ACCEPT) and rapide
        note = "expose automatiquement"
        if state == capability.DEGRADED:
            note = "expose automatiquement — hors pool : " + reason
        elif dans_pool:
            note = "promu automatiquement — %s" % motif_latence
            # LA CAPACITE MESUREE EST DITE, meme quand elle ne decide pas.
            #
            # `eligible_au_pool` promeut sur l'epreuve OU sur la latence : une
            # epreuve REUSSIE ouvre la porte, une epreuve ECHOUEE ne la ferme
            # pas -- le modele repasse simplement par la vitesse. Les epreuves
            # promeuvent donc, et ne retrogradent jamais.
            #
            # Ce n'est pas forcement un defaut : un modele incapable d'appeler
            # un outil peut parfaitement resumer, et l'exclure perdrait cette
            # capacite-la. Mais l'asymetrie n'etait ecrite nulle part, et le
            # pool ne disait rien de ce que la mesure savait.
            #
            # Mesure du 2026-08-31 : le pool du routeur local comptait quatre
            # membres, dont deux PROUVES incapables d'orchestrer --
            # deepseek-coder-33b a 3/4 et phi3-mini a 1/4 -- pendant que onze
            # modeles prouves 4/4 restaient dehors. Personne ne pouvait le
            # voir sans ouvrir le registre a la main.
            #
            # La decision reste au generateur ; le CONSTAT revient a
            # l'operateur.
            verdict = epreuves_relevees().get(alias)
            if isinstance(verdict, dict) and not verdict.get("complet"):
                manque = ", ".join(verdict.get("epreuves_echouees") or []) or "detail non releve"
                note += " — mais epreuve %s/%s : %s" % (
                    verdict.get("reussies"), verdict.get("total"), manque)
        else:
            note = "expose automatiquement — hors pool : " + motif_latence
        out += [
            "  - model_name: %s" % alias,
            "    litellm_params:",
            "      model: ollama%s/%s" % ("" if is_embed else "_chat", base),
            "      api_base: %s" % OLLAMA_ENDPOINT,
            "      litellm_health_check: true",
        ]
        if not is_embed:
            # Temperature declaree, et non laissee au defaut du modele.
            #
            # Aucun modele du YAML n'en fixait : chaque appel qui n'en
            # precisait pas une tournait donc a 0,7-0,8, le defaut des
            # modeles. C'est la lecon la plus chere du depot -- a 0,7, un
            # modele a rendu un document dont TOUTES les mesures etaient
            # inventees, et une boucle de repetition de 589 s ; a 0,2, la
            # meme tache a reussi en 11 s.
            #
            # Declaree et non imposee : un parametre envoye dans la requete
            # l'emporte sur celui du litellm_params. C'est donc un filet de
            # securite pour tout appelant distrait, et non une contrainte
            # pour celui qui sait ce qu'il veut.
            #
            # Un embedding n'en recoit pas : la notion n'a pas de sens pour
            # lui, et la lui envoyer serait au mieux ignore, au pire refuse.
            out += ["      num_ctx: %d" % ctx, "      num_predict: 4096",
                    "      temperature: %s" % TEMPERATURE_DEFAUT]
        out += [
            "    model_info:",
            "      max_input_tokens: %d" % ctx,
            '      description: "%s (%s)"' % (base, note),
            # Deux marques distinctes, et il faut les deux :
            #   nexus_generated : d'ou vient le bloc (evite de le redeclarer)
            #   nexus_pool      : s'il est eligible au routage automatique
            # Les confondre ferait redeclarer tout modele ecarte des pools
            # a la main, donc un alias en double.
            "      nexus_generated: true",
            "      nexus_pool: %s" % ("true" if dans_pool else "false"),
        ]
        if i < len(rendered) - 1:
            out.append("")
    return out


def read_env(name: str) -> str | None:
    if os.environ.get(name):
        return os.environ[name]
    env_file = os.path.join(ROOT, ".env")
    if not os.path.exists(env_file):
        return None
    with io.open(env_file, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            match = re.match(r"^\s*%s\s*=\s*(.*)$" % re.escape(name), line)
            if match and match.group(1).strip():
                return match.group(1).strip()
    return None


# Seuil d'admission au pool, en millisecondes.
#
# Mesure : une requete de seize jetons, sur une machine au repos, chargement
# du modele compris. Le chargement est volontairement inclus -- c'est le pire
# cas, et un pool automatique doit tenir le pire cas.
#
# Ce nombre est une DECISION, pas une mesure : au-dela d'une minute pour
# rendre un mot, un modele n'a pas sa place dans un routage automatique, quoi
# qu'il reponde ensuite. Surchargeable par NEXUS_POOL_LATENCE_MAX.
#
# Le releve porte sur seize jetons : il mesure le delai avant de commencer a
# repondre, pas le debit d'une tache reelle. Ce filtre est donc NECESSAIRE et
# NON SUFFISANT -- il ecarte a coup sur les modeles inutilisables, il ne
# prouve pas utilisables ceux qu'il laisse passer.
#
# Il reste malgre tout le bon critere, parce que l'alternative mesuree est
# pire : trie par latence, le banc donne qwen3-coder-30b a 2,4 s et
# gemma4-12b a 51 s. Un seuil sur le nombre de parametres aurait garde le
# lent et jete le rapide.
SEUIL_POOL_MS = int(os.environ.get("NEXUS_POOL_LATENCE_MAX", "60000"))

# En deca de ce poids, un modele n'a pas ses poids sur la machine : c'est un
# manifeste vers un modele distant. Mesure : les manifestes cloud pesent 290
# a 317 octets, le plus petit modele local reel 45,9 Mo. Le seuil est place
# entre les deux, loin des deux.
SEUIL_POIDS_REELS = 1024 * 1024

# Temperature declaree pour tout modele de conversation genere.
#
# 0,2 : le defaut des modeles (~0,7-0,8) produit de la vraisemblance la ou
# l'on veut de l'exactitude. Surchargeable par NEXUS_TEMPERATURE_DEFAUT, et
# par tout appelant qui en envoie une dans sa requete.
TEMPERATURE_DEFAUT = os.environ.get("NEXUS_TEMPERATURE_DEFAUT", "0.2")


def latences_relevees() -> dict:
    """
    Releve de nexus_bench.py, ou un dictionnaire vide.

    Ne leve jamais : un releve absent ne doit pas empecher de generer une
    configuration. Il rend seulement tout modele « non mesure », donc hors
    pool -- ce qui est le comportement d'avant cette mecanisation.
    """
    chemin = os.path.join(ROOT, ".nexus", "latences.json")
    try:
        with io.open(chemin, encoding="utf-8") as fh:
            donnees = json.load(fh)
        modeles = donnees.get("modeles")
        if isinstance(modeles, dict):
            return modeles
    except Exception:
        pass
    return {}


def epreuves_relevees() -> dict:
    """
    Registre des epreuves reelles, ecrit par scripts/nexus_releve.py.

    Meme contrat que latences_relevees() : ne leve jamais. Un registre absent
    rend simplement la derogation inoperante, donc le seuil de latence seul
    decide -- le comportement d'avant.
    """
    chemin = os.path.join(ROOT, ".nexus", "epreuves.json")
    try:
        with open(chemin, encoding="utf-8") as f:
            registre = json.load(f)
        modeles = registre.get("modeles")
        if isinstance(modeles, dict):
            return modeles
    except Exception:
        pass
    return {}


def eligible_au_pool(alias, releve, seuil_ms=SEUIL_POOL_MS):
    """
    (eligible, motif) pour un alias, d'apres le releve de latence.

    L'absence de preuve n'est pas une preuve : un modele jamais mesure
    n'entre pas dans un pool. C'est le lien qui manquait entre BENCHMARK et
    PROMOTE dans le cycle de vie -- la decision se prenait a la main.
    """
    # Une epreuve reelle reussie l'emporte sur le banc de demarrage.
    #
    # Les deux ne mesurent pas la meme chose : le banc chronometre le delai
    # avant de commencer a repondre (seize jetons), la releve fait passer
    # quatre epreuves de capacite -- protocole, demande d'outil, exploitation
    # du resultat, enchainement. La seconde est la preuve forte.
    #
    # CORRECTION, 2026-08-30. Cette derogation a d'abord ete justifiee par
    # glm-4.7-flash-local, « qui sortait du pool a 61,8 s ». C'etait FAUX :
    # ce modele est declare A LA MAIN dans litellm_config.yaml, hors de la
    # zone AUTOGEN, et sans champ nexus_pool. Ce chemin ne le juge donc
    # jamais -- ni avant la derogation, ni apres.
    #
    # L'erreur venait d'un script qui appelait eligible_au_pool() sur tous
    # les alias du releve, sans verifier lesquels traversent reellement ce
    # code. L'analyse avait ete prise pour une preuve.
    #
    # Le mecanisme, lui, reste juste et il est conserve : le jour ou un
    # modele AUTO-EXPOSE se revele lent a demarrer mais capable, la preuve
    # forte doit l'emporter sur la faible. Il n'a simplement, a ce jour,
    # aucun cas d'usage demontre -- et cela vaut d'etre ecrit plutot que
    # d'etre laisse croire.
    epreuve = epreuves_relevees().get(alias)
    if isinstance(epreuve, dict) and epreuve.get("complet"):
        return True, "epreuve reelle %s/%s" % (epreuve.get("reussies"),
                                               epreuve.get("total"))

    mesure = releve.get(alias)
    if not isinstance(mesure, dict):
        return False, "non mesure"
    motif = mesure.get("motif") or ""
    # Un embedding ne repond pas a un endpoint de conversation : ce n'est pas
    # un echec de sa part, et il ne releve d'aucun pool de chat.
    if motif == "non applicable":
        return False, "non applicable"
    if not mesure.get("ok"):
        return False, "mesure en echec : %s" % (motif or "sans motif")
    latence = mesure.get("latence_ms")
    if not isinstance(latence, (int, float)):
        return False, "mesure sans latence exploitable"
    if latence > seuil_ms:
        return False, "trop lent : %.1f s" % (latence / 1000.0)
    return True, "%.1f s" % (latence / 1000.0)


def pool_precedent() -> set[str]:
    """
    Modèles cloud déjà déclarés dans la configuration en place.

    Ils constituent les « titulaires » : eux seuls sont conservés lorsqu'une
    sonde échoue sans conclure. Un entrant, lui, doit avoir été prouvé.
    """
    try:
        with io.open(CONFIG, encoding="utf-8") as fh:
            config = yaml.safe_load(fh)
    except Exception:
        return set()
    titulaires = set()
    for model in (config.get("model_list") or []):
        params = model.get("litellm_params") or {}
        if "ollama.com" in str(params.get("api_base", "")):
            raw = str(params.get("model", ""))
            if "/" in raw:
                titulaires.add(raw.split("/", 1)[1])
    return titulaires


def validate_cloud(names: list[str],
                   titulaires: set[str] | None = None) -> tuple[list[str], dict[str, str]]:
    """
    Ne conserve que les modèles réellement exécutables par CE compte.

    Le catalogue publié n'est pas le catalogue autorisé : un modèle hors
    du palier souscrit répond 402. Publier un tel modèle dans le pool
    reviendrait à router vers un échec garanti.

    Le verdict n'est jamais figé : la validation est rejouée à chaque
    mise à jour, donc le pool s'élargit de lui-même dès qu'un palier
    supérieur est souscrit, sans aucune retouche de configuration.

    Distinction essentielle : un échec n'est pas l'autre.

        402/401/403/404  droit manquant       -> le modèle est écarté
        429/5xx/timeout  condition passagère  -> le modèle est CONSERVÉ

    Un quota momentanément épuisé ou un démarrage à froid ne prouve rien
    sur les droits du compte. Retirer un modèle du pool pour cette raison
    l'amputerait jusqu'à la mise à jour suivante, sur la foi d'un incident
    déjà terminé.

    Retourne (modèles retenus, {modèle: motif d'exclusion}).
    """
    key = read_env("OLLAMA_CLOUD_API_KEY")
    if not key:
        raise RuntimeError("OLLAMA_CLOUD_API_KEY absente : validation impossible")

    titulaires = titulaires or set()
    accepted: list[str] = []
    rejected: dict[str, str] = {}
    for name in names:
        body = json.dumps({
            "model": name,
            "messages": [{"role": "user", "content": "ping"}],
            "stream": False,
            "options": {"num_predict": 1},
        }).encode("utf-8")
        request = urllib.request.Request(
            "https://ollama.com/api/chat",
            data=body,
            headers={"Authorization": "Bearer %s" % key,
                     "Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                if response.status == 200:
                    accepted.append(name)
                    print("  [OK]    %s" % name)
                else:
                    rejected[name] = "HTTP %s" % response.status
                    print("  [ecart] %s : HTTP %s" % (name, response.status))
        except Exception as exc:
            code = getattr(exc, "code", None)
            if code in ENTITLEMENT_CODES:
                reason = {
                    402: "402 palier non souscrit",
                    401: "401 cle invalide",
                    403: "403 acces refuse",
                    404: "404 modele absent",
                }[code]
                rejected[name] = reason
                print("  [ecart] %s : %s" % (name, reason))
            elif name in titulaires:
                # Incident passager sur un modèle DÉJÀ dans le pool : on le
                # conserve plutôt que d'amputer le pool sur la foi d'un
                # échec déjà terminé.
                accepted.append(name)
                print("  [garde] %s : %s (echec passager, titulaire conserve)"
                      % (name, code or exc))
            else:
                # Mais un modèle JAMAIS prouvé exécutable n'entre pas sur une
                # sonde non concluante.
                #
                # Sans cette distinction, une coupure réseau — ou le simple
                # délai de 120 s sur les 19 sondes — faisait entrer tout le
                # catalogue publié. Le biais était défavorable : les plus
                # gros modèles sont à la fois les plus susceptibles de
                # dépasser un démarrage à froid **et** les mieux classés,
                # donc `cloud[0]` devenait le modèle par défaut du routeur
                # et la tête de chaîne de repli.
                rejected[name] = "%s (non concluant, jamais prouve)" % (code or "echec")
                print("  [attente] %s : %s — entrant non prouve, ecarte ce tour"
                      % (name, code or exc))
    return accepted, rejected


# ----------------------------------------------------------------------
# Classification des modèles déjà déclarés
# ----------------------------------------------------------------------
class Entry:
    __slots__ = ("alias", "domain", "modality", "family", "tier", "ctx", "order")

    def __init__(self, alias, domain, modality, family, tier, ctx, order):
        self.alias = alias
        self.domain = domain
        self.modality = modality
        self.family = family
        self.tier = tier
        self.ctx = ctx
        self.order = order


def classify(config: dict, profile: dict | None = None,
             sizes: dict[str, float] | None = None) -> list[Entry]:
    """
    Modèles éligibles à la construction des chaînes de routage.

    Trois exclusions, dans cet ordre : les routeurs eux-mêmes, ce qui a été
    écarté des pools à la main, et ce que la machine ne peut pas exécuter
    avec une marge suffisante. La dernière est mesurée, pas déclarée : un
    modèle trop lourd rendrait la chaîne de fallback inopérante là où elle
    devrait précisément sauver la requête.
    """
    sizes = sizes or {}
    entries: list[Entry] = []
    for order, model in enumerate(config.get("model_list") or []):
        alias = model["model_name"]
        params = model.get("litellm_params") or {}
        info = model.get("model_info") or {}
        prefs = info.get("adaptive_router_preferences") or {}
        raw = str(params.get("model", ""))
        api_base = str(params.get("api_base", ""))

        if raw.startswith("auto_router/"):
            continue
        # Exposé automatiquement : adressable, mais hors pool et hors
        # chaînes de fallback tant qu'il n'a pas été évalué (§76).
        if info.get("nexus_pool") is False:
            continue
        if profile and raw.startswith(("ollama/", "ollama_chat/")) \
                and "ollama.com" not in api_base:
            base = raw.split("/", 1)[1]
            size = sizes.get(base) or sizes.get(base + ":latest") or 0.0
            state, reason = capability.verdict(size, profile)
            if state != capability.ACCEPT:
                print("  [hors chaine] %s : %s" % (alias, reason))
                continue
        if raw.startswith("anthropic/"):
            domain = "anthropic"
        elif "ollama.com" in api_base:
            domain = "cloud"
        else:
            domain = "local"

        if EMBED_HINT.search(alias):
            modality = "embedding"
        elif VISION_HINT.search(alias):
            modality = "vision"
        else:
            modality = "text"

        # La declaration du moteur l'emporte sur le nom.
        #
        # Les motifs ci-dessus restent, mais en REPLI : ils servent quand le
        # moteur ne repond pas, ou pour un modele qui n'est pas chez lui
        # (cloud, Anthropic). Quand il repond, c'est lui qui tranche -- un
        # nom est une convention, une declaration est un fait.
        #
        # Mesure : VISION_HINT ne voyait pas qwen3-vl, EMBED_HINT ne voyait
        # pas bge-m3, et CODE_HINT prenait tout Qwen pour un modele de code.
        if domain == "local" and raw.startswith(("ollama/", "ollama_chat/")):
            # `base` n'est definie plus haut que dans une branche
            # conditionnelle ; la rederiver ici evite un NameError selon le
            # chemin pris.
            capacites = capacites_ollama(raw.split("/", 1)[1])
            if capacites:
                if "embedding" in capacites:
                    modality = "embedding"
                elif "vision" in capacites:
                    modality = "vision"
                else:
                    modality = "text"

        # La spécialisation coding/general ne discrimine que le pool local :
        # les modèles Anthropic et cloud sont généralistes, les séparer
        # isolerait des modèles seuls dans leur chaîne.
        strengths = prefs.get("strengths") or []
        if modality != "text":
            family = modality
        elif domain == "local":
            family = "coding" if ("code_generation" in strengths or CODE_HINT.search(alias)) else "general"
        else:
            family = "text"

        entries.append(Entry(
            alias=alias,
            domain=domain,
            modality=modality,
            family=family,
            tier=int(prefs.get("quality_tier") or 0),
            ctx=int(info.get("max_input_tokens") or 0),
            order=order,
        ))
    return entries


def group_of(entry: Entry) -> tuple[str, str]:
    """Un fallback ne franchit jamais ces deux frontières."""
    return (entry.domain, entry.family)


def ranked(entries: list[Entry], domain: str) -> dict[tuple[str, str], list[Entry]]:
    """Chaînes ordonnées du plus capable au moins capable, par groupe."""
    groups: dict[tuple[str, str], list[Entry]] = {}
    for entry in entries:
        if entry.domain != domain:
            continue
        groups.setdefault(group_of(entry), []).append(entry)
    for chain in groups.values():
        chain.sort(key=lambda e: (-e.tier, e.order))
    return groups


def ranked_by_modality(entries: list[Entry], domain: str) -> dict[tuple[str, str], list[Entry]]:
    """
    Regroupement plus large, réservé aux fallbacks de contexte.

    Un dépassement de fenêtre n'est pas un problème de spécialité : il faut
    une fenêtre plus grande, dans le même domaine et la même modalité. Garder
    ici la séparation coding/general priverait les modèles généralistes de
    toute issue, alors qu'un seul modèle local dépasse 8K.
    """
    groups: dict[tuple[str, str], list[Entry]] = {}
    for entry in entries:
        if entry.domain != domain:
            continue
        groups.setdefault((entry.domain, entry.modality), []).append(entry)
    for chain in groups.values():
        chain.sort(key=lambda e: (-e.tier, e.order))
    return groups


# ----------------------------------------------------------------------
# Rendu des blocs
# ----------------------------------------------------------------------
def render_chain(groups: dict, indent: int, width: int = 2,
                 terminal: list[str] | None = None) -> list[str]:
    """
    Chaîne descendante : chacun retombe sur les suivants, jamais sur un
    précédent — l'acyclicité est donc structurelle.

    `terminal` prolonge la chaîne au-delà de son plan, et n'est légitime
    que dans un seul sens. Une place lui est RÉSERVÉE dans la liste de chaque
    maillon : sans cela, seuls les derniers maillons en recevaient un, et une
    chaîne externe pouvait n'offrir aucune issue au moment où son plan entier
    tombe.

    Règle de direction, asymétrique et volontairement stricte :

        cloud     -> local      autorisé   (le repli protège davantage)
        anthropic -> local      autorisé   (idem, et évite l'interruption)
        local     -> cloud      INTERDIT   (les données sortiraient)
        local     -> anthropic  INTERDIT   (idem, et la facturation change)

    Un repli est une dégradation subie, pas une décision : il ne doit
    jamais élargir l'exposition des données ni engager une dépense que
    personne n'a demandée. L'inverse — se replier vers le local quand un
    quota s'épuise — ne fait perdre que de la capacité.
    """
    pad = " " * indent
    out: list[str] = []
    for cle, chain in sorted(groups.items()):
        # Le terminal est composé de modèles locaux TEXTUELS. Le greffer sur
        # une chaîne d'embeddings ou de vision produirait exactement le
        # franchissement de modalité que la plateforme interdit ailleurs :
        # une image envoyée à un modèle aveugle ne renvoie pas d'erreur,
        # elle renvoie une réponse fausse.
        modalite = chain[0].modality if chain else "text"
        terminal_valide = terminal if modalite == "text" else None

        for i, entry in enumerate(chain):
            # UNE PLACE EST RESERVEE au terminal, au lieu de ne le greffer
            # que s'il reste de la place.
            #
            # Mesure du 2026-08-30 : la version precedente n'ajoutait le
            # terminal QUE si `len(targets) < width`, donc uniquement sur les
            # deux derniers maillons de chaque chaine. Resultat dans la
            # configuration produite : 35 replis cloud -> cloud pour 3
            # cloud -> local, alors que ce docstring et l'appelant affirmaient
            # tous deux que « toute chaine externe s'acheve en local ».
            #
            # Le mode de panne dominant du plan cloud est le 429, qui frappe
            # le QUOTA DU COMPTE : les successeurs cloud echouent donc
            # exactement comme le premier. Pire, chaque tentative ajoute a la
            # pression qui a cause le 429 -- mesure le meme soir, six taches
            # simultanees produisaient 36 refus et zero succes, parce que
            # chacune se demultipliait en replis cloud.
            #
            # Une sortie locale dans la liste de CHAQUE maillon transforme
            # cette amplification en degradation : on perd de la capacite,
            # jamais le service.
            reserve = 1 if terminal_valide else 0
            targets = [e.alias for e in chain[i + 1:i + 1 + max(0, width - reserve)]]
            if terminal_valide:
                for extra in terminal_valide:
                    if extra not in targets and extra != entry.alias:
                        targets.append(extra)
                        break
            if not targets:
                continue
            out.append("%s- %s:" % (pad, entry.alias))
            for target in targets:
                out.append("%s    - %s" % (pad, target))
            out.append("")
    return out


def render_ctx_chain(groups: dict, indent: int) -> list[str]:
    """Contexte : on ne remonte que vers une fenêtre strictement plus large."""
    pad = " " * indent
    out: list[str] = []
    for _, chain in sorted(groups.items()):
        for entry in chain:
            larger = sorted(
                (e for e in chain if e.ctx > entry.ctx),
                key=lambda e: e.ctx,
            )[:2]
            if not larger:
                continue
            out.append("%s- %s:" % (pad, entry.alias))
            for target in larger:
                out.append("%s    - %s" % (pad, target.alias))
            out.append("")
    return out


def render_cloud_models(cloud: list[str]) -> list[str]:
    out: list[str] = []
    for i, base in enumerate(cloud):
        rank = cloud_rank(base)
        out += [
            "  - model_name: %s" % cloud_alias(base),
            "    litellm_params:",
            "      model: ollama_chat/%s" % base,
            "      api_base: https://ollama.com",
            "      api_key: os.environ/OLLAMA_CLOUD_API_KEY",
            "      num_ctx: 131072",
            "      num_predict: 8192",
            "    model_info:",
            "      max_input_tokens: 131072",
            '      description: "%s (Ollama Cloud)"' % base,
            "      adaptive_router_preferences:",
            "        quality_tier: %d" % quality_tier(rank),
            "        strengths:",
            "          - general",
            "          - analytical_reasoning",
        ]
        if CODE_HINT.search(base):
            out += ["          - code_generation", "          - code_understanding"]
        if i < len(cloud) - 1:
            out.append("")
    return out


def render_router_fallbacks(entries: list[Entry], cloud: list[str]) -> list[str]:
    """
    Repli de chaque routeur.

    Les routeurs externes s'achèvent sur le routeur local : un quota
    Ollama épuisé ou des crédits Anthropic consommés doivent dégrader la
    capacité, pas interrompre le service. L'inverse n'existe pas — le
    routeur local ne sort jamais.
    """
    def top(domain: str, count: int = 2) -> list[str]:
        pool = [e for e in entries if e.domain == domain and e.modality == "text"]
        pool.sort(key=lambda e: (-e.tier, e.order))
        return [e.alias for e in pool[:count]]

    cloud_top = [cloud_alias(b) for b in cloud[:2]]
    out: list[str] = []
    for router, targets in (
        ("adaptive-router-local", top("local")),
        # Quota Ollama epuise : on retombe en local plutot que d'echouer.
        ("adaptive-router-cloud", cloud_top + ["adaptive-router-local"]),
        # Abonnement ou credits Anthropic epuises : meme principe.
        ("adaptive-router-anthropic", top("anthropic") + ["adaptive-router-local"]),
        # Le routeur global ne monte jamais vers Anthropic de lui-meme :
        # engager une depense n'est pas une degradation, c'est une decision.
        ("adaptive-router", ["adaptive-router-local", "adaptive-router-cloud"]),
    ):
        if not targets:
            continue
        out.append("    - %s:" % router)
        for target in targets:
            out.append("        - %s" % target)
        out.append("")
    return out


# ----------------------------------------------------------------------
# Remplacement par marqueurs
# ----------------------------------------------------------------------
def aliases_inside(lines: list[str], marker: str) -> set[str]:
    """
    Alias declares a l'interieur d'une zone AUTOGEN.

    Discriminant fiable de l'origine d'un bloc : sa POSITION, et non une
    marque posee dans son contenu. Une marque de contenu depend de la
    version qui l'a ecrite, donc echoue exactement lors des migrations
    ou l'on en a le plus besoin.
    """
    inside = False
    found: set[str] = set()
    open_re = re.compile(r"^\s*# >>> AUTOGEN:%s(\s|$)" % re.escape(marker))
    close_re = re.compile(r"^\s*# <<< AUTOGEN:%s\s*$" % re.escape(marker))
    for line in lines:
        if open_re.match(line):
            inside = True
            continue
        if close_re.match(line):
            inside = False
            continue
        if inside:
            match = re.match(r"^\s*- model_name:\s*(\S+)\s*$", line)
            if match:
                found.add(match.group(1))
    return found


def set_block(lines: list[str], marker: str, content: list[str]) -> list[str]:
    start = end = -1
    open_re = re.compile(r"^\s*# >>> AUTOGEN:%s(\s|$)" % re.escape(marker))
    close_re = re.compile(r"^\s*# <<< AUTOGEN:%s\s*$" % re.escape(marker))
    for i, line in enumerate(lines):
        if start < 0 and open_re.match(line):
            start = i
        elif start >= 0 and close_re.match(line):
            end = i
            break
    if start < 0:
        raise RuntimeError("marqueur AUTOGEN:%s introuvable" % marker)
    if end < 0:
        raise RuntimeError("marqueur AUTOGEN:%s jamais fermé" % marker)
    return lines[:start + 1] + content + lines[end:]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true",
                        help="affiche ce qui serait généré sans rien écrire")
    # La validation est le comportement par defaut : generer sans elle
    # remplit le pool de modeles que le compte ne peut pas executer, ce
    # qui produit des echecs garantis au routage.
    parser.add_argument("--no-validate", dest="validate", action="store_false",
                        default=True,
                        help="ne pas tester les droits reels (deconseille : le "
                             "pool peut alors contenir des modeles inutilisables)")
    args = parser.parse_args()

    print("=== Découverte du catalogue Ollama Cloud ===")
    cloud = discover_cloud()
    print("  %d modèle(s) publiés" % len(cloud))

    published = list(cloud)
    rejected: dict[str, str] = {}
    if args.validate:
        print("\n=== Validation par requête réelle ===")
        cloud, rejected = validate_cloud(cloud, pool_precedent())
        if not cloud:
            print("\nAucun modèle cloud utilisable : configuration inchangée.")
            return 1
        print("  %d modèle(s) retenus sur %d" % (len(cloud), len(published)))
        gated = [n for n, r in rejected.items() if r.startswith("402")]
        if gated:
            print("  %d modèle(s) attendent un palier supérieur ; ils entreront"
                  % len(gated))
            print("  automatiquement dans le pool à la prochaine mise à jour"
                  " après souscription.")

    with io.open(CONFIG, encoding="utf-8") as fh:
        raw = fh.read()
    config = yaml.safe_load(raw)

    # Garde-fou materiel : mesure avant toute decision de routage.
    #
    # Une mesure absente n'est pas une mesure nulle. Sans ce controle, un
    # Docker arrete faisait peser 0 Go a tous les modeles, donc ACCEPT a
    # tous : la generation ecrivait alors des modeles inexecutables en tete
    # des chaines de repli, et le validateur, partageant l'angle mort, les
    # approuvait.
    profile = capability.build_profile()
    sizes = capability.installed_models()
    if sizes is None:
        print("\nInventaire des modeles illisible : Docker et Ollama sont-ils")
        print("joignables ? La generation s'arrete — supposer que tous les")
        print("modeles tiennent en memoire serait pire que ne rien ecrire.")
        return 1
    print("  Moteur %s — %.0f Go de memoire d'inference, budget pool %.0f Go"
          % (profile["ollama"]["mode"], profile["inference_memory_gb"],
             profile["pool_budget_gb"]))

    # Le relevé a-t-il disparu depuis la derniere generation ?
    #
    # Le meme garde-fou que pour l'inventaire, et pour la meme raison :
    # generer sans mesure ne rend pas une configuration neutre, elle rend
    # une configuration VIDE -- tous les modeles « non mesure », donc hors
    # de tout pool.
    #
    # Il doit vivre ici et non dans la conformite, car celle-ci s'execute
    # APRES la generation dans Update-NexusModels : elle constaterait le
    # degat au lieu de l'empecher. Pire, le vidage efface la marque
    # nexus_pool: true qui permet de le detecter, si bien que le controle
    # suivant ne verrait plus rien d'anormal.
    #
    # Trou identifie par le banc gratuit en audit delegue, puis precise en
    # lisant l'ordre reel des etapes : trois modeles sur trois ont pointe
    # « effacer la marque contourne le controle », ce qui etait faux sous
    # cette forme -- effacer la marque EST le degat -- mais juste sous
    # celle-ci.
    if not latences_relevees():
        promus = "nexus_pool: true" in open(CONFIG, encoding="utf-8",
                                            errors="replace").read()
        if promus:
            print(chr(10) + "Le relevé de mesures est absent alors que la configuration")
            print("porte des modeles promus. Generer maintenant les sortirait")
            print("TOUS des pools, et effacerait du meme coup la trace qui")
            print("permet de s'en apercevoir. La generation s'arrete.")
            print(chr(10) + "Remedes : restaurer .nexus/latences.json depuis une")
            print("sauvegarde, ou remesurer avec scripts/nexus_bench.py.")
            return 1

    entries = classify(config, profile, sizes)

    # Les entrées cloud déjà déclarées sont remplacées par la découverte :
    # on les retire avant de dériver les chaînes.
    entries = [e for e in entries if e.domain != "cloud"]

    anthropic_groups = ranked(entries, "anthropic")
    local_groups = ranked(entries, "local")

    def modalite_cloud(base: str) -> str:
        # Les memes indices que pour le local. Figer « text » aurait declare
        # un embedding cloud en ollama_chat/ avec num_ctx 131072, et l'aurait
        # verse dans les deux pools de routage -- dont la modalite n'est
        # controlee nulle part.
        if EMBED_HINT.search(base):
            return "embedding"
        if VISION_HINT.search(base):
            return "vision"
        return "text"

    cloud_chain = [
        Entry(cloud_alias(b), "cloud", modalite_cloud(b), modalite_cloud(b),
              quality_tier(cloud_rank(b)), 131072, i)
        for i, b in enumerate(cloud)
    ]
    cloud_groups: dict[tuple[str, str], list[Entry]] = {}
    for entry in cloud_chain:
        cloud_groups.setdefault(group_of(entry), []).append(entry)
    for chain in cloud_groups.values():
        chain.sort(key=lambda e: e.order)

    # Exposition automatique de l'inventaire Ollama. La liste est relue à
    # chaque exécution : un modèle téléchargé après coup apparaît de
    # lui-même, sans plafond ni liste à tenir à jour.
    installed = discover_local()
    raw_lines = raw.replace("\r\n", "\n").split("\n")
    generated_aliases = aliases_inside(raw_lines, "LOCAL_MODELS_EXTRA")
    declared_aliases = {m["model_name"] for m in (config.get("model_list") or [])
                        if m["model_name"] not in generated_aliases}

    local_extra = (render_local_extra(installed, declared_aliases, profile, sizes)
                   if installed else [])
    if installed:
        # Compte des blocs REELLEMENT ecrits, et non des candidats : c'est
        # cette ligne que l'operateur lit pour verifier ce qui s'est passe.
        ecrits = len([l for l in local_extra if l.startswith("  - model_name:")])
        print("  %d modele(s) installes, %d exposes automatiquement"
              % (len(installed), ecrits))

    # Terminal de repli : les meilleurs modeles locaux. Toute chaine
    # externe s'y acheve, pour qu'un quota epuise degrade la capacite
    # sans interrompre le service.
    local_text = [e for e in entries if e.domain == "local" and e.modality == "text"]
    local_text.sort(key=lambda e: (-e.tier, e.order))
    terminal_local = [e.alias for e in local_text[:2]]

    # Le pool du routeur local, trie par latence MESUREE.
    #
    # Il etait tenu a la main, et la mesure du 2026-08-30 a montre ce que
    # cela coutait : sur ses sept modeles, trois figuraient parmi les plus
    # lents du banc -- glm-4.7-flash a 61,8 s, gemma4-12b a 51,5 s,
    # gemma4-31b a 41,6 s -- et gemma4-12b etait le modele PAR DEFAUT.
    # Le routeur partait donc, par defaut, sur un modele 22 fois plus lent
    # que le meilleur dont il disposait.
    #
    # Pendant ce temps, quinze modeles mesures rapides portaient bien
    # nexus_pool: true et n'etaient cites nulle part : le marquage etait
    # ecrit, et sans effet. La promotion s'arretait au YAML sans atteindre
    # le routeur.
    #
    # Le tri combine QUALITE puis latence, et l'ordre compte : le premier
    # de la liste sert de modele par defaut au routeur.
    #
    # Trier par la seule latence serait l'erreur symetrique de celle qu'on
    # corrige. Elle mettrait llama3.2-1b en tete -- 2,3 s, un milliard de
    # parametres -- et ce modele deviendrait le defaut du routeur local.
    # La 37 interdit de promouvoir sur la seule vitesse, comme la 10
    # interdit de choisir sur la seule taille.
    #
    # A qualite egale, la mesure tranche. Resultat sur ce banc :
    # qwen3-coder-30b-local, tier 2 et 2,4 s -- capable et rapide.
    latences = latences_relevees()

    def _debit(alias):
        """
        Jetons par seconde, ou None si jamais mesure.

        Le debit prime sur le demarrage des qu'il est connu, parce qu'il se
        paie a CHAQUE jeton quand le demarrage ne se paie qu'une fois --
        et que les outils qui emploient ces pools produisent de longues
        sorties.

        Mesure du 2026-08-30, sur le pool alors en place :

          qwen3-coder-30b-local    2,4 s   20,22 j/s
          qwen2.5-coder-32b-local  3,4 s   moins de 2,1 j/s
          llama3.2-3b-local        2,3 s   11,84 j/s
          ultime-recourse-local    2,6 s   22,89 j/s

        Trie par demarrage, ce pool placait le PIRE debit en deuxieme et le
        MEILLEUR en dernier. Les quatre demarrages tiennent en 1,1 s
        d'ecart ; les debits vont de 1 a 11.
        """
        mesure = latences.get(alias) or {}
        return mesure.get("debit_jps")

    def _ms(alias):
        # Un modele sans releve part en fin de liste plutot que d'etre
        # exclu : il est deja passe par eligible_au_pool, donc soit il a
        # une mesure, soit il tient par une epreuve reelle -- laquelle ne
        # produit pas de latence. L'exclure ici annulerait la derogation.
        mesure = latences.get(alias) or {}
        return mesure.get("latence_etablie_ms") or mesure.get("latence_ms") or 10 ** 9

    # Le pool local est BORNE, et cette borne est la lecon d'une mesure.
    #
    # Ouvert d'abord a tous les modeles eligibles (29), il a DEGRADE la
    # latence qu'il devait ameliorer. Trois appels au routeur, trois
    # modeles differents, chacun payant le chargement de ses poids :
    # 78 s, 41 s, 60 s -- pour des modeles mesures a 22, 4 et 12 s.
    #
    # La cause est physique : le moteur ne garde qu'une POIGNEE de modeles
    # chauds -- trois mesures le meme jour, pour 36,7 Go, chacun expirant
    # quatre minutes apres son dernier usage. Un pool bien plus large
    # disperse donc les appels sur des modeles froids, et plus il est
    # large, plus le chargement devient certain.
    #
    # Correction du meme jour : ce commentaire disait « UN SEUL modele ».
    # C'etait une observation unique erigee en propriete -- l'erreur meme
    # que la 112.3 corrige, recommise en documentant sa correction. Un
    # modele etait resident parce qu'un seul servait, non parce que le
    # moteur en garde un ; le defaut d'Ollama est de trois.
    #
    # La borne est donc petite a dessein. Le levier complementaire est
    # OLLAMA_MAX_LOADED_MODELS cote moteur : le relever permettrait
    # d'elargir cette borne d'autant, la memoire du moteur le permettant
    # (66 Go). Tant qu'il vaut 1, elargir le pool nuit.
    # La borne porte sur le POIDS CUMULE, non sur un compte.
    #
    # Une borne en nombre supposait implicitement que les elus pouvaient
    # coexister en memoire. Verification faite : les quatre premiers pesent
    # 19 + 18 + 19 + 18 = 74 Go pour 66,2 Go de memoire hote. Ils ne
    # tiennent pas ensemble, et un compte ne pouvait pas le savoir.
    #
    # Le budget vient du profil materiel (107), deja calcule et deja
    # affiche. Il s'adapte donc seul : gros modeles, pool etroit ; petits
    # modeles, pool large ; machine plus puissante, pool plus large sans
    # qu'une ligne change.
    #
    # Le minimum de deux est delibere : a un seul membre il n'y a plus de
    # routage, seulement un alias deguise.
    budget_go = float((profile or {}).get("pool_budget_gb") or 0) or 40.0
    if os.environ.get("NEXUS_POOL_LOCAL_MAX"):
        budget_go = float(os.environ["NEXUS_POOL_LOCAL_MAX"])

    # sizes est indexe par NOM OLLAMA (« qwen3-coder:30b »), le pool par
    # ALIAS LiteLLM (« qwen3-coder-30b-local »). Interroger l'un avec
    # l'autre rend 0 pour chacun : le budget ne serait jamais atteint et la
    # borne ne bornerait rien, sans que rien ne le signale. D'ou l'index
    # inverse, construit avec la meme fonction que la declaration.
    poids_par_alias = {local_alias(nom): go for nom, go in (sizes or {}).items()}

    # Le pool cloud est TRIE par la mesure, et deliberement PAS filtre par
    # le seuil de latence.
    #
    # Ce seuil existe parce qu'en local un modele lent occupe la machine :
    # il charge ses poids, tient la memoire, et evince le voisin. Rien de
    # tel a distance -- un modele cloud lent fait attendre, sans rien
    # consommer ici. Lui appliquer le seuil local reviendrait a transposer
    # une contrainte materielle la ou il n'y a pas de materiel.
    #
    # La question ne se pose d'ailleurs pas aujourd'hui : les dix-neuf
    # modeles mesures tiennent entre 2,5 et 11,2 s, tous tres en deca des
    # 60 s. Mais qu'elle ne se pose pas ne dispense pas de dire pourquoi
    # elle ne se poserait pas davantage si un modele cloud ralentissait.
    pool_cloud = sorted((cloud_alias(b) for b in cloud
                         if modalite_cloud(b) == "text"), key=_ms)

    # Tri a trois niveaux : qualite, puis debit mesure, puis demarrage.
    #
    # Un modele dont le debit est connu se classe par lui. Ceux qui ne le
    # sont pas gardent leur classement par demarrage, ENTRE EUX, et
    # passent apres les mesures : une mesure vaut mieux qu'une absence,
    # mais l'absence ne vaut pas condamnation -- ils restent dans le pool.
    def _rang(e):
        d = _debit(e.alias)
        return (-e.tier, 0 if d is not None else 1,
                -(d or 0), _ms(e.alias))

    # Le choix est EXACT, plus glouton.
    #
    # Le glouton -- trier puis accumuler jusqu'au budget -- n'est optimal que
    # si les poids sont egaux. Ici ils vont de 0,4 a 20 Go, et le contre-
    # exemple est immediat : avec un budget de 20 Go et trois candidats
    # pesant 19, 10 et 10 Go pour des scores de 22, 20 et 20, le glouton
    # prend le lourd en premier, bloque le budget et rend 22 ; l'exact refuse
    # le lourd et rend 40. Verifie.
    #
    # L'exhaustif tient parce que le probleme est petit : 4 587 778
    # combinaisons pour 40 candidats en tailles 4 a 6, et 0,00 s mesurees
    # pour un balayage complet des tailles 2 a 4 (106.2).
    candidats = [{"alias": e.alias, "tier": e.tier, "debit": _debit(e.alias),
                  "poids": float(poids_par_alias.get(e.alias) or 0)}
                 for e in local_text]
    pool_local, score_pool, poids_pool, examinees = choisir_pool_exact(
        candidats, budget_go, taille_min=2, taille_max=6)
    print("  Pool local : %d modele(s), score %.1f, %.1f Go sur %.0f, "
          "%s combinaison(s) examinees"
          % (len(pool_local), score_pool, poids_pool, budget_go,
             format(examinees, ",")))

    blocks = {
        # Le bloc couvre le modele par defaut ET la liste : les deux sont
        # dictes par la meme mesure, et les separer laisserait le defaut
        # derriver a la main -- ce qui est precisement ce qui s'etait
        # produit, gemma4-12b restant defaut a 51,5 s.
        # Le routeur GLOBAL partage la meme partie locale et le meme
        # defaut. Il portait le meme travers, en pire : son defaut etait
        # aussi gemma4-12b-local a 51,5 s, et c'est lui que nexus_agent.py
        # emploie par defaut -- donc toute delegation partait de la.
        #
        # Son defaut reste LOCAL a dessein, bien que son pool contienne du
        # cloud : la 29 prefere le local a capacite suffisante, et un defaut
        # cloud engagerait une sortie de donnees sans que rien ne l'ait
        # demande.
        "GLOBAL_POOL": ([
            "      adaptive_router_default_model: %s" % (pool_local[0]
                                                         if pool_local else "phi3-mini-local"),
            "      adaptive_router_config:",
            "        available_models:",
        ] + ["          - %s" % a for a in pool_local]),
        "LOCAL_POOL": ([
            "      adaptive_router_default_model: %s" % (pool_local[0]
                                                         if pool_local else "phi3-mini-local"),
            "      adaptive_router_config:",
            "        available_models:",
        ] + ["          - %s" % a for a in pool_local]),
        "LOCAL_MODELS_EXTRA": local_extra,
        "CLOUD_MODELS": render_cloud_models(cloud),
        # Seuls les modeles textuels entrent dans un pool de routage : un
        # embedding ou une vision n'y a pas sa place, et rien d'autre ne
        # verifie la modalite d'un pool.
        # Les pools cloud sont tries par la mesure eux aussi, depuis que le
        # banc couvre ce plan.
        #
        # Le gain y est modeste et il faut le dire : les dix-neuf modeles
        # cloud tiennent entre 2,5 et 11,2 s, un ecart de 4,5x contre 45x
        # cote local. N'ayant aucun poids a charger ici, ils n'ont pas le
        # probleme que ce tri corrige en local. Le seul defaut reel etait
        # que le premier candidat, qwen3.5-397b-cloud a 5,6 s, etait plus
        # lent que la moitie du pool -- gemma4-31b-cloud rend en 2,5 s.
        "CLOUD_POOL_CLOUD": ["          - %s" % a for a in pool_cloud],
        "CLOUD_POOL_GLOBAL": ["          - %s" % a for a in pool_cloud],
        # Les chaines externes s'achevent en local ; la chaine locale,
        # elle, ne sort jamais.
        "ANTHROPIC_FALLBACKS": render_chain(anthropic_groups, 4,
                                            terminal=terminal_local),
        "LOCAL_FALLBACKS": render_chain(local_groups, 4),
        # width=1 : un -cloud replie sur le LOCAL, et sur rien d'autre.
        #
        # Un voisin cloud n'aide jamais dans le mode de panne dominant : le
        # 429 frappe le QUOTA DU COMPTE, donc tous les alias cloud a la fois.
        # Pire, il amplifie. Mesure d'une session voisine le 2026-08-30 :
        # chaque appel client devenait environ TREIZE requetes vers
        # ollama.com -- une, fois trois tentatives, fois trois groupes
        # (l'original plus deux replis cloud) -- soit 40 connexions
        # sortantes constatees pour 3 appels clients. Le plafond du compte
        # porte sur ces 40.
        #
        # Avec un repli local unique, un seul groupe atteint ollama.com : le
        # repli, lui, part sur la machine et ne consomme aucun quota. Il
        # termine la chaine au lieu de la propager.
        "CLOUD_FALLBACKS": render_chain(cloud_groups, 4, width=1,
                                        terminal=terminal_local),
        "ROUTER_FALLBACKS": render_router_fallbacks(entries, cloud),
        "ANTHROPIC_CTX_FALLBACKS": render_ctx_chain(
            ranked_by_modality(entries, "anthropic"), 2),
        "LOCAL_CTX_FALLBACKS": render_ctx_chain(
            ranked_by_modality(entries, "local"), 2),
        "CLOUD_CTX_FALLBACKS": [],
    }

    if args.dry_run:
        print("\n=== [Simulation] blocs générés ===")
        for name, content in blocks.items():
            print("  %-26s %d ligne(s)" % (name, len(content)))
        print("\n  Routeur cloud par défaut : %s" % cloud_alias(cloud[0]))
        return 0

    lines = raw.replace("\r\n", "\n").split("\n")
    for name, content in blocks.items():
        lines = set_block(lines, name, content)

    # Version de la politique de routage : empreinte de ce qui decide
    # reellement du modele servi. Elle rend un resultat rattachable aux
    # regles qui l'ont produit (§88).
    signature = "|".join([
        "|".join(sorted(blocks["CLOUD_POOL_CLOUD"])),
        "|".join(sorted(blocks["CLOUD_POOL_GLOBAL"])),
        "|".join(blocks["ROUTER_FALLBACKS"]),
        "%.0f" % profile["pool_budget_gb"],
    ])
    router_version = "r%s" % __import__("hashlib").sha256(
        signature.encode("utf-8")).hexdigest()[:10]
    hardware_sig = capability.profile_signature(profile)

    default_cloud = cloud_alias(cloud[0])
    for i, line in enumerate(lines):
        match = re.match(r"^(\s*adaptive_router_default_model:\s*)\S+-cloud\s*$", line)
        if match:
            lines[i] = match.group(1) + default_cloud
        if line.startswith("# NEXUS-ROUTER-VERSION:"):
            lines[i] = "# NEXUS-ROUTER-VERSION: %s" % router_version
        if line.startswith("# NEXUS-HARDWARE-SIGNATURE:"):
            lines[i] = "# NEXUS-HARDWARE-SIGNATURE: %s" % hardware_sig

    # Écriture en deux temps : un candidat, puis le remplacement.
    #
    # Écrire directement la configuration avant de la valider laissait, en
    # cas d'échec, un fichier invalide sur disque. LiteLLM tournait encore
    # sur sa copie chargée, donc rien ne paraissait cassé — jusqu'au
    # prochain redémarrage, qui la chargeait sans repasser par aucun
    # contrôle. La garantie ne portait donc que sur *ce* redémarrage-là,
    # pas sur l'état du dépôt.
    candidat = CONFIG + ".candidat"
    with io.open(candidat, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(lines).rstrip() + "\n")

    verdict = subprocess.run(
        [sys.executable, os.path.join(ROOT, "scripts", "nexus_validate.py"),
         "--config", candidat],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=600)
    if verdict.returncode != 0:
        os.remove(candidat)
        print("\nLa configuration produite est invalide : elle n'a pas ete")
        print("mise en place, et l'existante reste intacte.\n")
        for ligne in verdict.stdout.splitlines():
            if ligne.strip().startswith("- ") or "=>" in ligne:
                print("  " + ligne.strip())
        # stderr etait ignore : une EXCEPTION du validateur -- par
        # opposition a un verdict d'invalidite -- ne laissait donc aucune
        # trace, et le generateur refusait sans dire pourquoi. C'est le
        # meme defaut que celui corrige le matin meme dans nexus_valide.py :
        # un refus sans motif n'est pas actionnable.
        if verdict.stderr.strip():
            print("  [erreur du validateur]")
            for ligne in verdict.stderr.strip().splitlines()[-6:]:
                print("    " + ligne)
        return 1

    os.replace(candidat, CONFIG)
    # cloud_models.txt documente le catalogue COMPLET : les modèles actifs
    # en clair, ceux qu'un palier supérieur débloquerait en commentaire.
    # Rien n'est à décommenter à la main — la prochaine validation les
    # réintègre d'elle-même.
    inventory = [
        "# Catalogue Ollama Cloud — généré le %s par scripts/nexus_generate.py"
        % datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "# Actifs : exécutables avec l'abonnement Ollama Cloud actuel.",
        "# Commentés : publiés mais non autorisés — ils redeviendront actifs",
        "# automatiquement dès qu'un palier supérieur sera souscrit.",
        "",
    ]
    inventory += list(cloud)
    if rejected:
        inventory.append("")
        for name in published:
            if name in rejected:
                inventory.append("# %-24s # %s" % (name, rejected[name]))
    # Meme precaution que pour la configuration, vingt lignes plus haut :
    # un candidat, puis un remplacement atomique. L'ecriture etait ici
    # faite en place, alors que ce fichier est une source de verite --
    # c'est lui qui documente quels modeles cloud l'abonnement autorise
    # reellement. Interrompue a mi-chemin, elle laissait un inventaire
    # tronque qu'aucun controle ne relit : la generation suivante s'y
    # fierait, et des modeles pourtant autorises disparaitraient du pool
    # sans que rien ne signale pourquoi.
    candidat_inventaire = CLOUD_LIST + ".candidat"
    with io.open(candidat_inventaire, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(inventory) + "\n")
    os.replace(candidat_inventaire, CLOUD_LIST)

    print("\n=== Génération terminée ===")
    for name, content in blocks.items():
        print("  %-26s %d ligne(s)" % (name, len(content)))
    print("  Routeur cloud par défaut : %s" % default_cloud)
    print("  Version de routage       : %s" % router_version)
    return 0


if __name__ == "__main__":
    sys.exit(main())
