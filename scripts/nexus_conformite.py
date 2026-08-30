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
    IGNORE        non vérifiable dans l'état actuelle — jamais « réussi »

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

# ----------------------------------------------------------------------
# Import protégé du module externe `nexus_capability`
# ----------------------------------------------------------------------
try:
    import nexus_capability as capability  # noqa: E402
    _capability_import_error = None
except Exception as exc:  # pragma: no cover
    capability = None
    _capability_import_error = exc

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
SECRETS_REQUIS = [
    "LITELLM_MASTER_KEY",
    "REDIS_PASSWORD",
    "POSTGRES_USER",
    "POSTGRES_PASSWORD",
    "POSTGRES_DB",
]

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
    r = subprocess.run(
        [sys.executable, os.path.join(ROOT, "scripts", "nexus_validate.py")],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    erreurs = [l.strip() for l in r.stdout.splitlines() if l.strip().startswith("- ")]
    noter(
        "configuration valide",
        r.returncode == 0,
        BLOQUANT,
        "%d erreur(s) : %s"
        % (len(erreurs), "; ".join(e[2:] for e in erreurs[:3]))
        if r.returncode != 0
        else "",
    )


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
        with io.open(CONFIG, encoding="utf-8") as f:
            texte = f.read()
    except Exception as exc:
        noter("moteur coherent", False, BLOQUANT, "configuration illisible : %s" % exc)
        return
    # Recensement de TOUTES les adresses déclarées, plutôt que le comptage
    # de deux formes connues d'avance.
    adresses: dict[str, int] = {}
    for brut in re.findall(r"api_base:\s*(\S+)", texte):
        adresse = brut.strip().strip("\"'").rstrip(",}]")
        if "ollama.com" in adresse or "anthropic" in adresse:
            continue  # plan distant : hors sujet ici
        adresses[adresse] = adresses.get(adresse, 0) + 1

    if not adresses:
        noter(
            "moteur coherent",
            False,
            AVERTISSEMENT,
            "aucune declaration locale dans la configuration",
        )
    elif len(adresses) > 1:
        noter(
            "moteur coherent",
            False,
            BLOQUANT,
            "configuration partagee entre %d moteurs : %s"
            % (
                len(adresses),
                ", ".join("%s (%d)" % (a, n) for a, n in sorted(adresses.items())),
            ),
        )
    else:
        adresse, nombre = next(iter(adresses.items()))
        noter(
            "moteur coherent",
            True,
            BLOQUANT,
            "%d declaration(s) vers %s" % (nombre, adresse),
        )


def controle_moteur_joignable() -> None:
    """
    Le moteur que la configuration désigne répond-il réellement ?

    Démarrer LiteLLM devant un moteur éteint produit une passerelle qui
    accepte les requêtes et les échoue toutes — le pire des deux états,
    puisqu'elle a l'air en marche.
    """
    if capability is None:
        noter(
            "moteur joignable",
            False,
            BLOQUANT,
            "module nexus_capability indisponible : %s" % _capability_import_error,
        )
        return
    lieu = capability.ollama_location()
    sonde = ("http://127.0.0.1:11434" if lieu.get("host_native") else "http://127.0.0.1:11435")
    try:
        with urllib.request.urlopen(sonde + "/api/version", timeout=10) as reponse:
            version = json.loads(reponse.read().decode("utf-8")).get("version", "?")
        noter(
            "moteur joignable",
            True,
            BLOQUANT,
            "%s sur %s (Ollama %s)" % (lieu.get("mode"), sonde, version),
        )
    except Exception as exc:
        noter(
            "moteur joignable",
            False,
            BLOQUANT,
            "%s injoignable (%s)" % (sonde, exc),
        )


def controle_marqueurs_autogen() -> None:
    """
    Les zones générées sont-elles bien fermées, et une seule fois chacune ?

    Un marqueur ouvrant sans fermant fait avaler au générateur tout ce qui
    suit ; un marqueur en double lui fait écrire deux fois au même endroit.
    Dans les deux cas la configuration reste un YAML valide, et la perte ne
    se voit qu'à l'exécution.
    """
    try:
        with io.open(CONFIG, encoding="utf-8") as f:
            texte = f.read()
    except Exception as exc:
        noter("marqueurs AUTOGEN", False, BLOQUANT, str(exc))
        return
    ouverts = re.findall(r"#\s*>>>\s*AUTOGEN:(\S+)", texte)
    fermes = re.findall(r"#\s*<<<\s*AUTOGEN:(\S+)", texte)
    soucis = []
    for nom in set(ouverts) | set(fermes):
        if ouverts.count(nom) != 1 or fermes.count(nom) != 1:
            soucis.append("%s (%d ouvrant, %d fermant)" % (nom, ouverts.count(nom), fermes.count(nom)))
    noter(
        "marqueurs AUTOGEN",
        not soucis,
        BLOQUANT,
        "; ".join(soucis) if soucis else "%d zone(s) appariees" % len(set(ouverts)),
    )


def controle_residence_modeles() -> None:
    """
    Le moteur garde-t-il assez de modeles chauds pour le pool declare ?

    AVERTISSEMENT, jamais bloquant : c'est un reglage de l'hote, pas du
    depot, et il appartient a l'operateur. Le signaler suffit.

    Mesure du 2026-08-30 : « ollama ps » ne montrait qu'un modele resident.
    Tout pool plus large disperse alors les appels sur des modeles froids,
    et chaque bascule paie le chargement des poids -- 41 a 69 s observees
    sur des modeles bancs a 3 s. Le pool est desormais borne par le budget
    memoire (107.1), ce qui limite les degats ; relever cette variable
    s'attaque a la cause.
    """
    try:
        import subprocess
        sortie = subprocess.run(["ollama", "ps"], capture_output=True,
                                text=True, timeout=20, encoding="utf-8",
                                errors="replace")
    except Exception as exc:
        ignorer("residence des modeles", "moteur non interrogeable : %s" % exc)
        return
    if sortie.returncode != 0:
        ignorer("residence des modeles", "ollama ps a rendu %s" % sortie.returncode)
        return

    # Une seule ligne d'en-tete signifie zero modele charge : ce n'est pas
    # une anomalie, seulement un moteur au repos.
    charges = [l for l in sortie.stdout.splitlines()[1:] if l.strip()]
    plafond = os.environ.get("OLLAMA_MAX_LOADED_MODELS")

    if plafond:
        noter("residence des modeles", True, AVERTISSEMENT,
              "OLLAMA_MAX_LOADED_MODELS=%s, %d modele(s) resident(s)"
              % (plafond, len(charges)))
        return

    # Le compte de residents est RAPPORTE, jamais interprete comme la
    # limite du moteur. Le confondre a produit une affirmation fausse,
    # propagee dans la doctrine et le code : « le moteur garde un seul
    # modele chaud », alors qu'un seul etait resident parce qu'un seul
    # servait. Trois ont ete mesures coexistant, et le defaut d'Ollama est
    # de trois.
    noter("residence des modeles", True, AVERTISSEMENT,
          "OLLAMA_MAX_LOADED_MODELS non defini — le moteur applique son "
          "defaut (trois modeles) ; %d resident(s) a l'instant, ce qui "
          "reflete l'usage et non la limite. Au-dela, chaque changement "
          "paie le chargement des poids. Le relever elargirait d'autant le "
          "pool utile ; la memoire du moteur en dit la borne."
          % len(charges))


def controle_frontiere_alias() -> None:
    """
    Le suffixe d'un alias doit s'accorder avec l'adresse qu'il contacte.

    Sept endroits du code Python decident du plan -- donc de la
    confidentialite -- en lisant la FIN DU NOM : `-local`, `-cloud`. Le nom
    ne prouve pourtant rien. Un alias `-local` declare a la main avec un
    api_base distant ferait mentir ces sept endroits d'un seul coup, et la
    plateforme annoncerait « local » une requete sortie de la machine :
    exactement ce que la section 34 interdit.

    Constat du 2026-08-30 : les 67 alias sont coherents. Mais c'etait une
    propriete CONSTATEE, que rien n'empechait de perdre. Ce controle la rend
    garantie.

    Bloquant, et non consultatif : une frontiere de confidentialite fausse
    ne se signale pas, elle arrete.
    """
    if not os.path.exists(CONFIG):
        return  # controle_config_valide dit deja l'absence
    try:
        with io.open(CONFIG, encoding="utf-8", errors="replace") as f:
            texte = f.read()
    except OSError as exc:
        noter("frontiere des alias", False, BLOQUANT,
              "configuration illisible : %s" % exc)
        return

    # Lecture par blocs plutot que par YAML : ce controle doit tenir meme
    # quand la configuration est syntaxiquement douteuse -- c'est justement
    # le moment ou une frontiere se perd.
    fautifs = []
    alias = None
    for ligne in texte.splitlines():
        d = ligne.strip()
        if d.startswith("- model_name:"):
            alias = d.split(":", 1)[1].strip()
        elif d.startswith("api_base:") and alias:
            base = d.split(":", 1)[1].strip()
            # Distant = HTTPS vers un hote qui n'est pas la machine.
            distant = base.startswith("https://") and "host.docker.internal" not in base
            if alias.endswith("-local") and distant:
                fautifs.append("%s dit local et contacte %s" % (alias, base))
            elif alias.endswith("-cloud") and not distant:
                fautifs.append("%s dit cloud et contacte %s" % (alias, base))
            alias = None

    noter("frontiere des alias", not fautifs, BLOQUANT,
          " ; ".join(fautifs) if fautifs
          else "suffixe et api_base concordent sur chaque alias")


def controle_secrets() -> None:
    """Les variables sans lesquelles la pile démarre sans servir."""
    if not os.path.exists(ENV):
        noter(
            "secrets presents",
            False,
            BLOQUANT,
            ".env absent — copier .env.example et le remplir",
        )
        return
    try:
        with io.open(ENV, encoding="utf-8", errors="replace") as f:
            contenu = f.read()
    except OSError as exc:
        noter("secrets presents", False, BLOQUANT, ".env illisible : %s" % exc)
        return
    manquants = []
    for nom in SECRETS_REQUIS:
        m = re.search(r"^\s*%s\s*=\s*(.*)$" % re.escape(nom), contenu, re.M)
        if not m:
            manquants.append(nom)
            continue
        # Retirer les commentaires éventuels et les guillemets.
        # Le caractère # peut faire partie du mot de passe. On ne le considère
        # comme commentaire que lorsqu'il est précédé d'un espace (" #").
        # Avant, un mot de passe contenant # était tronqué à vide, bloquant le
        # démarrage de la passerelle.
        raw_val = m.group(1)
        if " #" in raw_val:
            valeur = raw_val.split(" #", 1)[0].strip()
        else:
            valeur = raw_val.strip()
        valeur = valeur.strip("\"'")
        if not valeur:
            manquants.append(nom)
    noter(
        "secrets presents",
        not manquants,
        BLOQUANT,
        "manquants ou vides : %s" % ", ".join(manquants) if manquants else "%d variable(s) renseignees" % len(SECRETS_REQUIS),
    )


def controle_env_hors_git() -> None:
    """
    `.env` est-il resté hors de l'index git ?

    Le contrôle est refait à chaque démarrage plutôt qu'une fois pour
    toutes : un `git add -A` suffit à l'y faire entrer, et une fois
    poussé, un secret est compromis même supprimé au commit suivant.
    """
    r = subprocess.run(
        ["git", "ls-files", "--error-unmatch", ".env"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    suivi = r.returncode == 0
    noter(
        ".env hors de git",
        not suivi,
        BLOQUANT,
        "SUIVI PAR GIT — retirer avec 'git rm --cached .env'" if suivi else "non suivi",
    )


def controle_disque() -> None:
    if capability is None:
        noter(
            "espace disque",
            False,
            AVERTISSEMENT,
            "module nexus_capability indisponible : %s" % _capability_import_error,
        )
        return
    profil = capability.build_profile()
    libre = profil.get("free_disk_gb", 0.0)
    noter(
        "espace disque",
        libre >= 15.0,
        AVERTISSEMENT,
        "%.0f Go libres%s" % (libre, "" if libre >= 15 else " — insuffisant pour un pull"),
    )


def substitution_imbriquee(valeur: str) -> str | None:
    """
    Une substitution `${...}` en contient-elle une autre ?

    L'expansion des variables d'un fichier de configuration se fait en une
    passe : la valeur par défaut d'un `${A:-...}` n'est pas ré-examinée.
    Écrire `${A:-${B:-.}}` ne rend donc pas la valeur de B mais la chaîne
    littérale `${B:-.}` — que le programme reçoit ensuite comme un nom de
    répertoire, lequel n'existe pas.

    La panne qui en découle est de la pire espèce : silencieuse et
    d'apparence saine. Ici, le pont MCP démarrait, s'annonçait « connected,
    12 outils », et tout ce qui touchait le disque était mort — la lecture
    de fichiers, l'indexation, la recherche, la vision, le profil matériel.
    Rien ne le signalait, et cette porte affichait ses huit contrôles au
    vert pendant ce temps, parce qu'aucun ne regardait le pont.

    Rend le fragment fautif, ou None si la valeur est saine.
    """
    i = valeur.find("${")
    while i != -1:
        j = valeur.find("}", i)
        if j == -1:
            # Accolade jamais fermée : tout aussi inexpansible.
            return valeur[i : i + 60]
        if "${" in valeur[i + 2 : j]:
            return valeur[i : j + 1]
        i = valeur.find("${", j)
    return None


def _chaines(noeud, chemin: str = ""):
    """Parcourt un JSON et rend (emplacement, chaîne) pour chaque texte."""
    if isinstance(noeud, dict):
        for cle, valeur in noeud.items():
            yield from _chaines(valeur, f"{chemin}.{cle}" if chemin else str(cle))
    elif isinstance(noeud, list):
        for rang, valeur in enumerate(noeud):
            yield from _chaines(valeur, f"{chemin}[{rang}]")
    elif isinstance(noeud, str):
        yield chemin, noeud


def controle_pont_mcp() -> None:
    """
    Le pont MCP lit-il réellement le dépôt, ou seulement en apparence ?

    Le contrôle est statique à dessein : il doit répondre passerelle et
    serveur éteints, c'est-à-dire avant le démarrage, là où la correction
    coûte le moins. Il ne demande donc rien au serveur — dont l'aveu
    « connected » ne prouve que le transport, jamais l'accès aux fichiers.

    Deux assertions, toutes deux vérifiables sans rien lancer :

        1. aucune substitution `${...}` n'en contient une autre ;
        2. le point d'entrée déclaré existe réellement sur le disque.
    """
    chemin = os.path.join(ROOT, ".mcp.json")
    if not os.path.exists(chemin):
        noter(
            "pont MCP",
            False,
            AVERTISSEMENT,
            ".mcp.json absent — aucun outil local n'est expose a Claude Code",
        )
        return
    try:
        with io.open(chemin, encoding="utf-8") as f:
            declaration = json.loads(f.read())
    except Exception as exc:
        noter("pont MCP", False, BLOQUANT, ".mcp.json illisible : %s" % exc)
        return

    serveurs = declaration.get("mcpServers") or {}
    defauts = []
    for nom, corps in serveurs.items():
        for ou, valeur in _chaines(corps, str(nom)):
            fautif = substitution_imbriquee(valeur)
            if fautif:
                defauts.append("%s : substitution inexpansible %s" % (ou, fautif))
        for arg in (corps.get("args") or []):
            if not isinstance(arg, str) or ("/" not in arg and "\\" not in arg):
                continue
            cible = (
                arg.replace("${CLAUDE_PROJECT_DIR:-.}", ROOT)
                .replace("${CLAUDE_PROJECT_DIR}", ROOT)
            )
            # Ignorer les substitutions non résolues restantes
            if "${" in cible:
                continue
            # Résolution relative à ROOT si le chemin n'est pas absolu
            if not os.path.isabs(cible):
                cible = os.path.normpath(os.path.join(ROOT, cible))
            # Vérifier que le point d'entrée est bien un fichier
            if not os.path.isfile(cible):
                defauts.append("%s : point d'entree absent ou non fichier (%s)" % (nom, cible))

    if not serveurs:
        noter("pont MCP", False, AVERTISSEMENT, ".mcp.json ne declare aucun serveur")
        return
    noter(
        "pont MCP",
        not defauts,
        BLOQUANT,
        "; ".join(defauts)
        if defauts
        else "%d serveur(s), substitutions expansibles, points d'entree presents" % len(serveurs),
    )


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
    try:
        r = subprocess.run(
            [sys.executable, os.path.join(ROOT, "scripts", "nexus_releve.py")],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
        )
    except Exception as exc:
        # Timeout ou autre problème d'exécution rend le contrôle non vérifiable.
        ignorer("releve operationnelle", "releve operationnelle injoignable : %s" % exc)
        return
    ligne = next((l.strip() for l in r.stdout.splitlines() if "epreuves reussies" in l), "")
    noter("releve operationnelle", r.returncode == 0, AVERTISSEMENT, ligne or "voir python scripts/nexus_releve.py")


def controle_delegation(avant_demarrage: bool) -> None:
    """
    La plateforme tient-elle encore sa promesse ?

    Tout le reste de cette porte verifie que le systeme peut demarrer. Ce
    controle-ci verifie qu'il sert encore a quelque chose : detourner du
    volume de l'abonnement vers des modeles gratuits est la raison d'etre du
    depot, et rien ne le mesurait. Une plateforme parfaitement conforme dont
    la part deleguee s'effondre est en panne, meme si tous ses voyants sont
    verts.

    Le detail rapporte aussi les requetes du plan `anthropic`, seules
    facturees au token. Une part globale flatteuse peut masquer leur
    augmentation : la moyenne se laisse porter par le volume gratuit.

    Jamais BLOQUANT. Une part qui baisse n'empeche pas de demarrer, elle
    signale une derive -- et refuser le demarrage sur ce motif punirait
    precisement l'operateur qui vient corriger la situation.
    """
    if avant_demarrage:
        ignorer("part deleguee", "controle avant demarrage")
        return
    if not passerelle_vivante():
        # Non mesurable n'est ni bon ni mauvais. Le journal de depense vit
        # dans la passerelle : eteinte, elle ne prouve rien dans un sens ni
        # l'autre.
        ignorer("part deleguee", "passerelle eteinte sur %s" % PASSERELLE)
        return

    try:
        r = subprocess.run(
            [
                sys.executable,
                os.path.join(ROOT, "scripts", "nexus_savings.py"),
                "--jours",
                "7",
                "--json",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
        )
    except Exception as exc:
        ignorer("part deleguee", "releve des depenses injoignable : %s" % exc)
        return
    if r.returncode != 0:
        ignorer("part deleguee", "releve des depenses en erreur (code %d)" % r.returncode)
        return
    try:
        mesure = json.loads(r.stdout)
    except Exception as exc:
        ignorer("part deleguee", "releve des depenses illisible : %s" % exc)
        return

    part = mesure.get("part_deleguee_pct")
    # `is None` et non une comparaison a zero : une part mesuree a 0 % est une
    # mesure, et parmi les plus alarmantes. La confondre avec une absence de
    # mesure ferait taire le seul cas qui exige une reaction immediate.
    if part is None:
        ignorer("part deleguee", "aucune mesure disponible sur 7 jours")
        return

    payantes = ((mesure.get("par_plan") or {}).get("anthropic") or {}).get("requetes", 0)
    noter(
        "part deleguee",
        part >= 90.0,
        AVERTISSEMENT,
        "%.1f%% delegue sur 7 jours, %d requete(s) facturee(s) au token%s"
        % (part, payantes, "" if part >= 90.0 else " — sous le plancher de 90%"),
    )


def controle_garde_agent() -> None:
    """
    Verifie que la garde contre les sous-agents non decides est operative.

    Trois conditions, dans cet ordre : le script existe et s'analyse ; il est
    reellement cable en hook PreToolUse ; et il refuse effectivement un
    sous-agent sans modele. Les deux premieres ne prouvent rien sans la
    troisieme -- une garde presente et cablee peut avoir cesse de refuser.
    C'est arrive : une sortie prematuree sur `subagent_type` absent annulait
    le controle du modele, et la garde laissait passer le cas le plus courant.
    """
    import ast

    # ------------------------------------------------------------------
    # 1. Presence et parsabilite du script
    # ------------------------------------------------------------------
    script_path = os.path.join(ROOT, "scripts", "nexus_garde_agent.py")
    if not os.path.isfile(script_path):
        noter("garde agent", False, BLOQUANT,
              "fichier scripts/nexus_garde_agent.py absent")
        return
    try:
        with io.open(script_path, "r", encoding="utf-8") as f:
            ast.parse(f.read(), filename=script_path)
    except Exception as exc:
        noter("garde agent", False, BLOQUANT,
              "scripts/nexus_garde_agent.py invalide : %s" % exc)
        return

    # ------------------------------------------------------------------
    # 2. Cablage dans .claude/settings.json
    #
    # Le format reel est une LISTE d'entrees, chacune portant un matcher et sa
    # PROPRE liste de hooks. Une version anterieure de ce controle attendait un
    # objet plat expose matcher/command : elle aurait declare absent un hook
    # correctement cable, et bloque le demarrage sur un defaut imaginaire.
    # ------------------------------------------------------------------
    settings_path = os.path.join(ROOT, ".claude", "settings.json")
    if not os.path.isfile(settings_path):
        noter("garde agent", False, BLOQUANT, ".claude/settings.json absent")
        return
    try:
        with io.open(settings_path, "r", encoding="utf-8") as f:
            settings = json.load(f)
    except Exception as exc:
        noter("garde agent", False, BLOQUANT,
              ".claude/settings.json illisible : %s" % exc)
        return

    entrees = (settings.get("hooks") or {}).get("PreToolUse")
    cable = False
    if isinstance(entrees, list):
        for entree in entrees:
            if not isinstance(entree, dict) or entree.get("matcher") != "Agent":
                continue
            for h in entree.get("hooks") or []:
                if isinstance(h, dict) and "nexus_garde_agent" in (h.get("command") or ""):
                    cable = True
    if not cable:
        noter("garde agent", False, BLOQUANT,
              "aucun hook PreToolUse matcher=Agent n'invoque nexus_garde_agent")
        return

    # ------------------------------------------------------------------
    # 3. Comportement effectif : refuser un sous-agent sans modele.
    #
    # NEXUS_AGENT_LIBRE est neutralise : la derogation est legitime a l'usage,
    # mais elle ne doit pas faire conclure que la garde est morte.
    # ------------------------------------------------------------------
    env = dict(os.environ)
    env.pop("NEXUS_AGENT_LIBRE", None)
    try:
        proc = subprocess.run(
            [sys.executable, script_path],
            input='{"tool_name":"Agent","tool_input":{}}',
            capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=30, env=env,
        )
    except Exception as exc:
        noter("garde agent", False, BLOQUANT,
              "execution du script impossible : %s" % exc)
        return

    if proc.returncode != 2:
        noter("garde agent", False, BLOQUANT,
              "sous-agent sans modele accepte (code %s au lieu de 2)" % proc.returncode)
        return

    noter("garde agent", True, BLOQUANT, "")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--avant-demarrage",
        action="store_true",
        help="ignore les controles exigeant la passerelle en marche",
    )
    p.add_argument("--json", action="store_true")
    a = p.parse_args()

    for controle in (
        controle_config_valide,
        controle_moteur_coherent,
        controle_moteur_joignable,
        controle_marqueurs_autogen,
        controle_frontiere_alias,
        controle_residence_modeles,
        controle_secrets,
        controle_env_hors_git,
        controle_disque,
        controle_pont_mcp,
        controle_garde_agent,
    ):
        try:
            controle()
        except Exception as exc:
            # Un contrôle qui plante ne doit pas se lire comme un contrôle
            # réussi : il devient bloquant, faute de pouvoir conclure.
            noter(controle.__name__, False, BLOQUANT, "controle en erreur : %s" % exc)
    controle_runtime(a.avant_demarrage)
    controle_delegation(a.avant_demarrage)

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
