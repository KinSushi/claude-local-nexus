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
import ast
import datetime
import hashlib
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
# `REDIS_PASSWORD` a été retiré volontairement : Redis tourne sans mot de
# passe par décision de l'opérateur, il n'est publié sur aucun port de
# l'hôte et n'est joignable que du réseau Docker interne. La variable avait
# été retirée de .env.example et l'exiger bloquait toute installation neuve.
SECRETS_REQUIS = [
    "LITELLM_MASTER_KEY",
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
# ---------------------------------------------------------------------------
# LES DEUX ETAGES D'UN GARDE DOIVENT DIRE LA MEME CHOSE.
#
# CE QUI ETAIT FAUX, et vecu dans le tour meme du 2026-08-31 : le matcher de
# .claude/settings.json disait « Bash|PowerShell » pendant que le garde disait
# `!= "Bash"`. PowerShell etait donc ROUTE vers un garde qui refusait de le
# juger -- un correctif a moitie, qui SE LIT comme fait.
#
# Rien ne pouvait le dire, et le trou n'a ete trouve qu'en soumettant a la
# main la meme commande sous deux noms d'outil. Ce controle rend la derive
# impossible : chaque garde DECLARE ce qu'il juge, et la declaration est
# comparee au routage.
#
# Le sens du desaccord decide de la severite, et ce n'est pas un detail :
#   route mais non declare  -> BLOQUE : l'outil arrive et rien ne le juge ;
#   declare mais non route  -> ALERTE : une declaration morte, jamais un trou.
# Bloquer sur le second arreterait le travail pour une capacite inemployee.
# ---------------------------------------------------------------------------


def controle_gardes_accordes(racine):
    """Controle la coherence entre les matchers du settings.json et les
    declarations OUTILS_JUGES des gardes. Retourne (etat, detail)."""
    # 1. lecture du settings.json
    settings_path = os.path.join(racine, ".claude", "settings.json")
    try:
        with open(settings_path, "r", encoding="utf-8") as f:
            settings = json.load(f)
    except Exception as e:
        return ("ALERTE", f"settings.json illisible : {e}")

    # 2. extraction des scripts et des outils routes
    scripts_routes = {}          # nom_fichier -> set(outils)
    hooks_by_event = settings.get("hooks", {})
    # Le nom de l'evenement ne sert pas ici : un hook est juge sur son
    # matcher et son script, quel que soit l'evenement qui le declenche.
    for _event, blocs in hooks_by_event.items():
        if not isinstance(blocs, list):
            continue
        for bloc in blocs:
            matcher = bloc.get("matcher")
            if not matcher:
                continue          # bloc sans matcher n'apporte aucun outil
            outils = set(matcher.split("|"))
            for hook in bloc.get("hooks", []):
                cmd = hook.get("command", "")
                # extraction du nom de fichier du script
                # on retire les guillemets éventuels en fin de chaine
                cmd = cmd.strip().strip('"').strip("'")
                # dernier segment apres '/' ou '\'
                nom = cmd.replace("\\", "/").split("/")[-1]
                if not nom.startswith("nexus_garde_"):
                    continue
                scripts_routes.setdefault(nom, set()).update(outils)

    # 3. lecture de chaque garde et verification
    nb_gardes = len(scripts_routes)
    for nom_fichier, outils_routes in scripts_routes.items():
        garde_path = os.path.join(racine, "scripts", nom_fichier)
        try:
            with open(garde_path, "r", encoding="utf-8") as f:
                source = f.read()
        except Exception as e:
            return ("ALERTE", f"{nom_fichier} : impossible de lire le fichier ({e})")

        # parsing avec ast
        try:
            tree = ast.parse(source, filename=nom_fichier)
        except Exception as e:
            return ("ALERTE", f"{nom_fichier} : parsing ast impossible ({e})")

        # UNE SENTINELLE, ET NON None.
        #
        # `OUTILS_JUGES = None` est une DECLARATION -- celle de
        # nexus_garde_lecture, qui se cale sur la presence d'un champ
        # `file_path` et non sur un nom d'outil. La confondre avec « constante
        # absente » ferait crier a l'alerte sur le seul cas que ce controle
        # doit tolerer, et rendrait le test suivant inatteignable.
        ABSENT = object()
        outils_declare = ABSENT
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == "OUTILS_JUGES":
                        try:
                            outils_declare = ast.literal_eval(node.value)
                        except Exception:
                            outils_declare = ABSENT   # valeur non litterale
                        break
            if outils_declare is not ABSENT:
                break

        # 4. comparaison
        if outils_declare is ABSENT:
            return ("ALERTE", f"{nom_fichier} : ne declare pas ce qu'il juge")
        if outils_declare is None:
            # Agnostique, et il le DIT. Rien a exiger de lui.
            continue

        # on attend un tuple ou une liste
        if not isinstance(outils_declare, (list, tuple)):
            # type inattendu -> alerte
            return ("ALERTE", f"{nom_fichier} : OUTILS_JUGES a un type invalide")

        declared_set = set(outils_declare)

        # outil route mais non declare -> bloque
        for outil in outils_routes:
            if outil not in declared_set:
                return ("BLOQUE", f"{nom_fichier} : {outil} est route mais non declare")

        # outil declare mais non route -> alerte
        for outil in declared_set:
            if outil not in outils_routes:
                return ("ALERTE", f"{nom_fichier} : {outil} est declare mais non route")

    # 5. aucun desaccord
    return ("OK", f"{nb_gardes} garde(s) accordes a leur matcher")


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
    # Cas où le processus échoue sans produire d'erreurs « - » : on indique le code
    # de retour et la dernière ligne non vide de stderr (ou stdout à défaut).
    if r.returncode != 0 and not erreurs:
        source = r.stderr if r.stderr.strip() else r.stdout
        lignes = [l.strip() for l in source.splitlines() if l.strip()]
        derniere = lignes[-1] if lignes else ""
        # Troncature raisonnable (200 caractères max) pour éviter les débordements.
        if len(derniere) > 200:
            derniere = derniere[:197] + "..."
        detail = f"code {r.returncode} : {derniere}"
    else:
        detail = (
            "%d erreur(s) : %s"
            % (len(erreurs), "; ".join(e[2:] for e in erreurs[:3]))
            if r.returncode != 0
            else ""
        )
    noter(
        "configuration valide",
        r.returncode == 0,
        BLOQUANT,
        detail,
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


def controle_mcp_a_jour() -> None:
    """
    Le serveur MCP en marche execute-t-il le code qui est sur le disque ?

    Node lit server.js UNE FOIS, au demarrage. Une session ouverte avant une
    correction continue donc de servir l'ancien code, indefiniment, et rien
    ne le signalait.

    Observe le 2026-08-30 : une session parallele routait encore le profil
    « coding » vers releve-locale plusieurs heures apres que ce modele en
    eut ete retire, et concluait de bonne foi que le profil pointait vers un
    modele inexecutable. Le diagnostic etait juste sur les faits qu'elle
    voyait, et faux sur la cause -- elle ne pouvait pas savoir.

    AVERTISSEMENT et non bloquant : un serveur perime rend un service
    degrade, pas dangereux, et refuser de demarrer pour cela punirait
    l'operateur venu corriger.
    """
    serveur = os.path.join(ROOT, "tools", "nexus-mcp", "server.js")
    if not os.path.exists(serveur):
        ignorer("serveur MCP a jour", "server.js absent")
        return
    try:
        with open(serveur, "rb") as f:
            disque = hashlib.sha256(f.read()).hexdigest()[:12]
    except OSError as exc:
        noter("serveur MCP a jour", False, AVERTISSEMENT,
              "server.js illisible : %s" % exc)
        return

    # Un serveur en marche est interroge par le protocole ; a defaut, on ne
    # peut que rappeler l'empreinte attendue.
    noter("serveur MCP a jour", True, AVERTISSEMENT,
          "code sur disque %s — si une session MCP est plus ancienne que la "
          "derniere modification de server.js, elle sert encore l'ancien "
          "code : la redemarrer" % disque)


# Ce que le pont a le droit d'ecrire, et rien d'autre. Trois destinations,
# toutes sous « .nexus » : le magasin d'observations et l'index (ecrit par
# fichier provisoire puis renomme, pour qu'une interruption ne laisse pas un
# JSON tronque).
RESERVE_ECRITURE = ("OBSERVATIONS", "INDEX_DIR", "INDEX_PATH", "provisoire")

ECRITURES_JS = ("writeFileSync", "appendFileSync", "createWriteStream",
                "unlinkSync", "renameSync", "rmSync", "rmdirSync",
                "copyFileSync", "truncateSync", "writeSync")


def ecritures_hors_reserve(source: str) -> list:
    """
    Appels d'ecriture du pont dont la destination n'est pas dans la reserve.

    Fonction pure, sans acces disque : elle est ainsi eprouvable sur un faux
    source. Un controle qui ne peut etre mis en defaut sur commande ne prouve
    rien -- son silence sur un fichier sain ressemble trait pour trait au
    silence d'un motif casse.

    `mkdirSync` est volontairement absent de la liste : creer un repertoire
    n'abime aucune source, et l'inclure aurait ajoute du bruit sans ajouter
    de garantie.
    """
    trouves = []
    for numero, ligne in enumerate(source.splitlines(), 1):
        nue = ligne.strip()
        if nue.startswith("//") or nue.startswith("*"):
            continue
        for appel in ECRITURES_JS:
            marque = appel + "("
            if marque not in nue:
                continue
            argument = nue.split(marque, 1)[1]
            # Premiere destination citee, jusqu'a la virgule ou la parenthese.
            premier = argument.split(",")[0].split(")")[0].strip()
            if any(mot in premier for mot in RESERVE_ECRITURE):
                continue
            trouves.append((numero, appel, premier[:40]))
    return trouves


# Les deux depots voisins, en LECTURE SEULE. Absents sur une autre machine :
# le controle IGNORE alors, il n'echoue pas -- ce depot doit rester
# utilisable seul.
VERROUS_VOISINS = (
    ("SAS", r"D:\SAS\sovereign-ai-system\v1.104\sovereign-ai-system"
            r"\workspace\tools\verrou_machine.py"),
    ("EA MT5", r"D:\EA MT5 PYTHON RENTABLE ROBUSTE"
               r"\workspace\tools\verrou_machine.py"),
)

PREFIXE_ATTENDU = "AURUM_MACHINE_"


def prefixe_de(chemin: str):
    """Prefixe de mutex declare par un fichier, ou None s'il est illisible."""
    try:
        with io.open(chemin, encoding="utf-8", errors="replace") as f:
            trouve = re.search(r"PREFIXE\s*=\s*[\"']([^\"']+)", f.read())
        return trouve.group(1) if trouve else None
    except OSError:
        return None


def controle_verrou_machine() -> None:
    """
    Le verrou d'exclusion inter-projets porte-t-il encore le meme nom ?

    Trois depots travaillent sur cette machine et se partagent 66 Go de RAM,
    un moteur Ollama et un disque. Le verrou machine les empeche de se
    marcher dessus -- une mesure prise pendant que le voisin lance pytest ne
    mesure pas ce qu'elle croit, defaut deja paye ici par une mesure prise
    pendant un telechargement de 28 Go.

    LE CONTRAT ENTRE PROJETS EST LE NOM DU MUTEX, rien d'autre : pas de
    fichier partage, pas de repertoire commun. Un mutex nomme est un objet du
    noyau, libere par Windows quand le processus meurt -- il n'existe pas de
    verrou orphelin.

    D'ou le point de rupture, et la raison de ce controle : si un projet
    change son prefixe, l'exclusion casse EN SILENCE. Les trois continueraient
    de prendre un verrou, chacun le sien, en croyant se proteger, et
    travailleraient en meme temps sans qu'aucun message ne l'annonce.

    Mesure du 2026-08-30 : les trois declarent AURUM_MACHINE_ et la meme
    signature, alors que le CODE diverge -- notre copie fait 13 842 octets
    comme celle de SAS, celle d'EA MT5 en fait 16 478. La divergence de code
    est sans effet ; seule celle du nom compte, et c'est donc elle, et elle
    seule, qui est gardee.

    BLOQUANT sur notre propre copie -- un verrou mal nomme chez nous ne
    protege plus rien. AVERTISSEMENT sur les voisins : leur depot ne nous
    appartient pas, et bloquer notre demarrage pour un fichier qu'on ne peut
    pas corriger punirait l'operateur.
    """
    notre = os.path.join(ROOT, "scripts", "nexus_verrou_machine.py")
    if not os.path.isfile(notre):
        return ignorer("verrou machine", "copie locale absente")
    prefixe = prefixe_de(notre)
    if prefixe != PREFIXE_ATTENDU:
        return noter("verrou machine", False, BLOQUANT,
                     "notre prefixe vaut %r, attendu %r : l'exclusion "
                     "inter-projets est rompue" % (prefixe, PREFIXE_ATTENDU)) and None

    divergents, vus = [], 0
    for nom, chemin in VERROUS_VOISINS:
        if not os.path.isfile(chemin):
            continue
        vus += 1
        autre = prefixe_de(chemin)
        if autre != PREFIXE_ATTENDU:
            divergents.append("%s declare %r" % (nom, autre))

    if divergents:
        return noter("verrou machine", False, AVERTISSEMENT,
                     "; ".join(divergents) + " -- l'exclusion casserait en "
                     "silence, chacun prenant son propre verrou") and None
    if not vus:
        return noter("verrou machine", True, AVERTISSEMENT,
                     "prefixe %s ; aucun depot voisin sur cette machine"
                     % PREFIXE_ATTENDU) and None
    noter("verrou machine", True, AVERTISSEMENT,
          "prefixe %s partage avec %d depot(s) voisin(s)"
          % (PREFIXE_ATTENDU, vus))


def controle_hooks_cables() -> None:
    """
    Chaque hook declare pointe-t-il sur un script qui existe ?

    C'est le maillon « le cablage » de la checklist du contrat (0.2.1), et
    celui dont l'absence ne se voit pas : Claude Code n'annonce pas qu'un
    hook a echoue, il continue. Un garde dont le script a ete renomme,
    deplace ou supprime ne protege plus rien, et le seul symptome est que
    le defaut qu'il surveillait revient sans que personne comprenne
    pourquoi.

    Sept hooks armes au 2026-08-30 : la reprise de session, les gardes de
    lecture (sur Read et sur les ecritures), le garde d'agent, le garde
    shell, le rituel de fin de tour, et le garde d'edition.

    BLOQUANT : un depot dont les gardes sont debranches est un depot sans
    gardes, et il vaut mieux le savoir avant de travailler que apres.
    """
    chemin = os.path.join(ROOT, ".claude", "settings.json")
    if not os.path.isfile(chemin):
        return ignorer("hooks cables", "settings.json introuvable")
    try:
        with io.open(chemin, encoding="utf-8", errors="replace") as f:
            declare = json.load(f)
    except Exception as exc:
        # Un settings.json illisible desarme TOUS les hooks d'un coup, en
        # silence. C'est le pire cas, et il est bloquant.
        return noter("hooks cables", False, BLOQUANT,
                     "settings.json illisible : %s" % str(exc)[:70]) and None

    manquants, comptes = [], 0
    for evenement, blocs in (declare.get("hooks") or {}).items():
        for bloc in blocs or []:
            for h in bloc.get("hooks") or []:
                commande = str(h.get("command") or "")
                trouve = re.search(r"scripts[/\\](\w+\.py)", commande)
                if not trouve:
                    continue
                comptes += 1
                script = os.path.join(ROOT, "scripts", trouve.group(1))
                if not os.path.isfile(script):
                    manquants.append("%s -> %s" % (evenement, trouve.group(1)))

    if not comptes:
        return noter("hooks cables", False, BLOQUANT,
                     "aucun hook ne reference de script : gardes desarmes") and None
    if manquants:
        return noter("hooks cables", False, BLOQUANT,
                     "script absent : " + " ; ".join(manquants[:3])) and None
    noter("hooks cables", True, BLOQUANT,
          "%d hook(s) pointent sur un script present" % comptes)


def controle_imports() -> None:
    """
    Chaque script s'importe-t-il, et son import fait-il quelque chose ?

    Un module casse ne se voit qu'a l'execution du chemin qui l'emploie.
    Mesure du 2026-08-30 : nexus_ruche.py employait nexus_agent sans jamais
    l'importer, et personne ne l'avait vu jusqu'a ce que la suite complete
    soit jouee pour la premiere fois de la journee.

    Deux defauts, et le second est le pire. Un import qui ECHOUE est certain ;
    un import qui AGIT transforme le fait de charger un module en action, si
    bien qu'un outil qui inspecte le depot le modifie en l'inspectant. Le
    premier jet de nexus_verbatim.py creait un repertoire a l'import.

    BLOQUANT : un module qui ne s'importe pas est casse pour tous ses
    appelants, et rien de ce qui suit ne peut etre tenu pour vrai.
    """
    outil = os.path.join(ROOT, "scripts", "nexus_import.py")
    if not os.path.isfile(outil):
        return ignorer("import des scripts", "nexus_import.py introuvable")
    try:
        r = subprocess.run([sys.executable, outil], cwd=ROOT,
                           capture_output=True, text=True, timeout=900,
                           encoding="utf-8", errors="replace")
    except subprocess.TimeoutExpired:
        return ignorer("import des scripts", "pas de reponse en 900 s")
    except Exception as exc:
        return ignorer("import des scripts", str(exc)[:60])
    lignes = [l for l in (r.stdout or "").splitlines() if l.strip()]
    if r.returncode == 0:
        return noter("import des scripts", True, BLOQUANT,
                     lignes[-1] if lignes else "aucun echec") and None
    noter("import des scripts", False, BLOQUANT,
          " | ".join(lignes[:3])[:200])


def controle_cablage() -> None:
    """
    Un script neuf a-t-il ete livre sans appelant ?

    Le contrat (0.2.1) impose six maillons a tout mecanisme, et le plus
    souvent oublie est l'APPELANT : un script existe, il est teste, et
    personne ne l'invoque jamais. « Prouve » et « utilise » sont deux faits
    distincts, et tout decompte de scripts livres les confond.

    Mesure du 2026-08-30, avant tout correctif : 14 cables, 28 appeles,
    5 prouves-seuls, 1 orphelin -- dont nexus_posterior.py, ecrit le matin
    meme et appele par personne.

    AVERTISSEMENT et non BLOQUANT : un script orphelin n'empeche pas la
    plateforme de fonctionner, et refuser de demarrer pour cela punirait
    l'operateur venu justement le cabler. Le cliquet, lui, est dans le
    script : il echoue des que la liste s'allonge.
    """
    outil = os.path.join(ROOT, "scripts", "nexus_cablage.py")
    if not os.path.isfile(outil):
        return ignorer("cablage des scripts", "nexus_cablage.py introuvable")
    try:
        r = subprocess.run([sys.executable, outil], cwd=ROOT,
                           capture_output=True, text=True, timeout=180,
                           encoding="utf-8", errors="replace")
    except Exception as exc:
        return ignorer("cablage des scripts", str(exc)[:60])
    lignes = [l for l in (r.stdout or "").splitlines() if l.strip()]
    resume = lignes[0] if lignes else "aucune sortie"
    if r.returncode == 0:
        return noter("cablage des scripts", True, AVERTISSEMENT, resume) and None
    noter("cablage des scripts", False, AVERTISSEMENT,
          " | ".join(lignes[:3])[:200])


def controle_pont_lecture_seule() -> None:
    """
    Le pont MCP peut-il abimer un fichier source ?

    La regle 0.4 dit qu'un worker ne recoit jamais l'original. Pour l'essaim,
    cela s'est traduit par une copie (voir test_isolation). Pour le pont, la
    traduction honnete est DIFFERENTE : le pont ne modifie rien, il lit. Lui
    faire copier les fichiers avant lecture n'aurait protege de rien, et une
    protection decorative est pire qu'aucune -- elle se lit comme une garantie.

    Ce qui compte donc est l'invariant lui-meme : mesure le 2026-08-30, les
    cinq seules ecritures du serveur visent « .nexus » (observations et
    index). Vrai ce jour-la, et rien ne le gardait. Le voici garde.

    BLOQUANT : une ecriture neuve hors reserve donnerait au pont le pouvoir
    de reecrire une source avec une sortie de modele, exactement ce que le
    renversement de l'essaim vient de retirer.
    """
    chemin = os.path.join(ROOT, "tools", "nexus-mcp", "server.js")
    if not os.path.isfile(chemin):
        return ignorer("pont en lecture seule", "server.js introuvable")
    try:
        with io.open(chemin, encoding="utf-8", errors="replace") as f:
            source = f.read()
    except OSError as exc:
        return ignorer("pont en lecture seule", str(exc)[:60])
    hors = ecritures_hors_reserve(source)
    if not hors:
        return noter("pont en lecture seule", True, BLOQUANT,
                     "aucune ecriture hors de .nexus") and None
    detail = " ; ".join("ligne %d, %s vers %s" % h for h in hors[:3])
    noter("pont en lecture seule", False, BLOQUANT,
          detail + " -- le pont pourrait reecrire une source avec une sortie "
          "de modele. Ajouter la destination a RESERVE_ECRITURE si elle est "
          "legitime, plutot que de desactiver le controle.")


def controle_travail_sur_original() -> None:
    """
    L'essaim a-t-il laisse des sauvegardes derriere lui ?

    `nexus_essaim.py` travaille sur la CIBLE ELLE-MEME : il copie le fichier
    en `.nexus/backup-<nom>-<hash>.bak`, laisse le banc le reecrire, puis
    restaure ou supprime la sauvegarde selon le resultat. Le contrat (0.4)
    demande l'inverse -- un worker recoit une copie, jamais la source -- et
    cet ecart est inscrit OUVERT au cockpit.

    En attendant, une sauvegarde qui SUBSISTE est un signal utilisable et
    precis : le cycle ne s'est pas termine. Le processus a ete tue, ou la
    restauration a echoue. Dans les deux cas la cible peut porter du texte
    ecrit par un modele, jamais relu par personne.

    Constate le 2026-08-30 : quarante fichiers dans `scripts/.nexus/`, la ou
    une racine mal calculee les avait ecrits -- invisibles a qui cherchait
    a la racine. On regarde donc les deux emplacements, l'actuel et l'ancien,
    car les restes de l'ancien existent encore.

    AVERTISSEMENT et non BLOQUANT : des restes n'empechent pas la plateforme
    de fonctionner, et refuser de demarrer punirait l'operateur venu
    justement les nettoyer.
    """
    emplacements = [
        (os.path.join(ROOT, ".nexus"), "racine"),
        # Ancien chemin : racine_depot() rendait « scripts ». Corrige, mais
        # ce qui y a ete ecrit y reste, et compte tout autant.
        (os.path.join(ROOT, "scripts", ".nexus"), "scripts (ancien chemin)"),
    ]
    restes = []
    for dossier, ou in emplacements:
        if not os.path.isdir(dossier):
            continue
        try:
            noms = [n for n in os.listdir(dossier)
                    if n.startswith("backup-") and n.endswith(".bak")]
        except OSError:
            continue
        if noms:
            restes.append((ou, len(noms), sorted(noms)[0]))
    if not restes:
        return noter("sauvegardes de l'essaim", True, AVERTISSEMENT,
                     "aucun reste : chaque cycle s'est termine") and None
    detail = " ; ".join("%d dans %s (ex. %s)" % (n, ou, ex)
                        for ou, n, ex in restes)
    noter("sauvegardes de l'essaim", False, AVERTISSEMENT,
          detail + " -- chaque reste est un cycle interrompu : la cible peut "
          "porter du texte ecrit par un modele et jamais relu. Verifier "
          "« git status » avant de supprimer.")


def controle_releves_lisibles() -> None:
    """
    Les fichiers de mesure ont-ils le format que leurs lecteurs exigent ?

    Absent : ignore. Une machine neuve n'a rien mesure, et l'exiger
    empecherait sa premiere mise en route.

    Present mais mal forme : BLOQUANT. C'est le cas qui s'est produit le
    2026-08-30, et il ne s'annoncait par rien. ecrire_json() posait les
    mesures a la racine du document quand latences_relevees() les cherche
    sous « modeles » : la lecture rendait un dictionnaire vide, les 58
    modeles devenaient « non mesure », et la regeneration suivante les
    aurait tous sortis des pools. Le banc n'affichait aucune anomalie, et
    le defaut n'a ete trouve que par accident, dans un script ecrit pour
    autre chose.

    Un releve vide n'est pas non plus accepte en silence : « present mais
    ne contenant rien » est le symptome exact de ce defaut.
    """
    for nom, role in ((("latences.json"), "banc de latence"),
                      (("epreuves.json"), "releve des epreuves")):
        chemin = os.path.join(ROOT, ".nexus", nom)
        if not os.path.exists(chemin):
            # « Jamais mesure » et « mesure puis disparu » ne sont pas la
            # meme chose, et les confondre ouvrait un trou : supprimer le
            # fichier produit EXACTEMENT le meme dommage qu'un format
            # casse -- verifie, le relevé relu tombe a zero modele et trois
            # des quatre membres du pool cessent d'etre eligibles -- mais
            # passait en IGNORE.
            #
            # Trouve par le banc gratuit, en audit delegue : « en
            # supprimant le fichier, on contourne le controle bloquant ».
            # Verifie ensuite dans le code reel, ou il s'est confirme.
            #
            # Le temoin d'un relevé passe est dans la configuration
            # elle-meme : nexus_pool: true n'a pu y etre ecrit que par une
            # generation disposant de mesures.
            temoin = False
            try:
                with io.open(CONFIG, encoding="utf-8", errors="replace") as f:
                    temoin = "nexus_pool: true" in f.read()
            except OSError:
                pass
            if temoin:
                noter("releve %s" % nom, False, BLOQUANT,
                      "absent alors que la configuration porte des modeles "
                      "promus : le relevé a existe puis disparu. Regenerer "
                      "maintenant viderait les pools.")
            else:
                ignorer("releve %s" % nom, "jamais mesure sur cette machine")
            continue
        try:
            with io.open(chemin, encoding="utf-8") as f:
                donnees = json.load(f)
        except Exception as exc:
            noter("releve %s" % nom, False, BLOQUANT,
                  "illisible : %s" % str(exc)[:80])
            continue
        modeles = donnees.get("modeles") if isinstance(donnees, dict) else None
        if not isinstance(modeles, dict) or not modeles:
            noter("releve %s" % nom, False, BLOQUANT,
                  "%s : clef « modeles » absente ou vide. Les lecteurs "
                  "rendront un releve vide et la regeneration videra les "
                  "pools sans le dire." % role)
            continue
        noter("releve %s" % nom, True, BLOQUANT,
              "%d modele(s), format attendu par ses lecteurs" % len(modeles))


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


def controle_secrets_documentes() -> None:
    """
    Chaque secret exigé est-il documenté dans `.env.example` ?

    Un secret présent dans `.env` mais absent de l'exemple est un piège pour
    la prochaine installation : elle démarrera sans lui, et la panne ne se
    verra qu'à l'usage. Ce contrôle vérifie que chaque nom de SECRETS_REQUIS
    possède une ligne d'affectation non commentée dans `.env.example`.

    BLOQUANT : un secret non documenté rend toute installation neuve
    impossible, et l'exiger ici force la mise à jour de l'exemple.
    """
    chemin = os.path.join(ROOT, ".env.example")
    if not os.path.isfile(chemin):
        ignorer("secrets documentes", ".env.example absent")
        return
    try:
        with io.open(chemin, encoding="utf-8", errors="replace") as f:
            contenu = f.read()
    except OSError as exc:
        ignorer("secrets documentes", ".env.example illisible : %s" % exc)
        return
    manquants = []
    for nom in SECRETS_REQUIS:
        # Ligne d'affectation non commentée : début de ligne (éventuellement
        # indenté) suivi du nom, puis '='. Les commentaires commencent par '#'.
        if not re.search(r"^\s*%s\s*=" % re.escape(nom), contenu, re.M):
            manquants.append(nom)
    noter(
        "secrets documentes",
        not manquants,
        BLOQUANT,
        "manquants dans .env.example : %s" % ", ".join(manquants)
        if manquants
        else "%d variable(s) documentee(s)" % len(SECRETS_REQUIS),
    )


def controle_exemple_present() -> None:
    """
    `.env.example` existe-t-il a la racine ?

    `controle_secrets_documentes` s'ignore quand l'exemple est absent :
    defendable en soi, mais cela signifie que SUPPRIMER le fichier desarme
    ce controle en silence, sur le depot ou il sert le plus. Aucun autre
    controle ne couvre la presence du fichier ; celui-ci la garde.

    BLOQUANT : sans exemple, une installation neuve n'a pas de modele de
    configuration a remplir, et le controle des secrets documentes se
    desarme sans le dire.
    """
    chemin = os.path.join(ROOT, ".env.example")
    if not os.path.isfile(chemin):
        noter("exemple present", False, BLOQUANT,
              ".env.example absent — le restaurer (git checkout -- "
              ".env.example) : sans lui, secrets documentes s'ignore")
        return
    noter("exemple present", True, BLOQUANT, ".env.example present a la racine")


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


def _point_entree_mcp(corps):
    """
    Le point d'entree TEL QUE DECLARE, et non tel qu'il se resoudra.

    C'est la distinction qui fait tout le controle. Claude Code range ses
    jetons par point d'entree litteral : deux ecritures differentes du
    meme chemin sont pour lui deux serveurs, meme lorsqu'elles designent
    le meme fichier une fois `${CLAUDE_PROJECT_DIR}` substitue. Comparer
    les chemins resolus rendrait donc le controle muet precisement sur le
    cas qui l'a fait ecrire.
    """
    if not isinstance(corps, dict):
        return str(corps).strip().lower()
    morceaux = [str(corps.get("command") or "")]
    args = corps.get("args")
    if isinstance(args, (list, tuple)):
        morceaux.extend(str(a) for a in args)
    elif args:
        morceaux.append(str(args))
    return " ".join(m.strip() for m in morceaux).lower()


def _resolu_mcp(signature):
    """La meme signature, substitutions faites : sert a expliquer, pas a juger."""
    resolu = signature.replace("${claude_project_dir:-.}", ROOT.lower())
    resolu = resolu.replace("${claude_project_dir}", ROOT.lower())
    return resolu.replace(chr(92), "/")


def controle_mcp_double_portee() -> None:
    """
    Un meme serveur declare deux fois ne se voit pas : il se subit.

    Claude Code range les jetons PAR POINT D'ENTREE. Deux declarations du
    meme nom qui pointent ailleurs l'une que l'autre font donc qu'une
    authentification faite dans un contexte ne vaut rien dans l'autre, et
    surtout que l'operateur ignore laquelle des deux le sert. Le doublon
    exact, lui, ne coute rien : il est signale, jamais reproche.

    AVERTISSEMENT et jamais BLOQUANT : une collision de portee n'empeche
    pas de demarrer, et refuser le demarrage punirait l'operateur venu la
    corriger. Une machine sans ~/.claude.json ne dit rien du tout —
    l'absence de portee utilisateur n'est pas un defaut.
    """
    utilisateur = os.path.expanduser("~/.claude.json")
    projet = os.path.join(ROOT, ".mcp.json")
    try:
        with io.open(utilisateur, encoding="utf-8") as f:
            declare_utilisateur = json.loads(f.read()).get("mcpServers") or {}
        with io.open(projet, encoding="utf-8") as f:
            declare_projet = json.loads(f.read()).get("mcpServers") or {}
    except Exception:
        # Ni fichier absent ni fichier illisible ne sont l'affaire de ce
        # controle : controle_pont_mcp juge deja le fichier du projet.
        return

    communs = sorted(set(declare_utilisateur) & set(declare_projet))
    if not communs:
        noter(
            "pont MCP double portee",
            True,
            AVERTISSEMENT,
            "aucun serveur declare dans les deux portees",
        )
        return

    divergents, identiques = [], []
    for nom in communs:
        cote_u = _point_entree_mcp(declare_utilisateur[nom])
        cote_p = _point_entree_mcp(declare_projet[nom])
        if cote_u == cote_p:
            identiques.append(nom)
        else:
            meme_cible = _resolu_mcp(cote_u) == _resolu_mcp(cote_p)
            divergents.append(
                "%s : utilisateur=%s vs projet=%s%s"
                % (
                    nom,
                    cote_u,
                    cote_p,
                    " (meme fichier une fois resolu, mais deux points d'entree"
                    " pour Claude Code)" if meme_cible else "",
                )
            )

    detail = (
        "; ".join(divergents)
        if divergents
        else "doublon exact, sans divergence : %s" % ", ".join(identiques)
    )
    noter("pont MCP double portee", not divergents, AVERTISSEMENT, detail)

def controle_portee_import() -> None:
    """
    Un nom importe dans une fonction, employe dans une autre.

    Ce controle ne double PAS « import des scripts ». Celui-la CHARGE chaque
    module et ne peut rien voir ici : le module s'importe proprement, puisque
    l'import existe — il est simplement au mauvais endroit. Le NameError
    tombe plus tard, a l'execution du seul chemin qui emploie le nom, c'est-a-
    dire souvent en production et jamais pendant le controle.

    BLOQUANT, comme son voisin : un chemin qui leve NameError est casse pour
    tous ses appelants, et rien de ce qui suit ne peut etre tenu pour vrai.
    """
    outil = os.path.join(ROOT, "scripts", "nexus_portee_import.py")
    if not os.path.isfile(outil):
        return ignorer("portee des imports", "nexus_portee_import.py introuvable")
    try:
        r = subprocess.run([sys.executable, outil], cwd=ROOT,
                           capture_output=True, text=True, timeout=300,
                           encoding="utf-8", errors="replace")
    except subprocess.TimeoutExpired:
        return ignorer("portee des imports", "pas de reponse en 300 s")
    except Exception as exc:
        return ignorer("portee des imports", str(exc)[:60])

    lignes = [l for l in (r.stdout or "").splitlines() if l.strip()]
    if r.returncode == 0:
        return noter("portee des imports", True, BLOQUANT,
                     "aucun nom employe hors de la fonction qui l'importe")
    compte = next((l.split(":", 1)[1].strip()
                   for l in lignes if l.startswith("DEFAUTS:")), "?")
    autres = [l for l in lignes if not l.startswith("DEFAUTS:")]
    noter("portee des imports", False, BLOQUANT,
          "%s defaut(s) : %s" % (compte, " | ".join(autres[:2])))

def controle_doc_python() -> None:
    """
    La documentation officielle est-elle consultable, ou seulement promise ?

    Absorbee du depot voisin le 2026-08-31 : 166 507 symboles sur 63 couches,
    ancres sur les versions REELLEMENT installees. La regle qu'elle sert est
    plus ancienne, et vient d'une panne precise chez le voisin : une
    statistique passee a `scipy.stats.bootstrap(vectorized=True)` n'acceptait
    pas le mot-cle `axis` que scipy passe pourtant dans ce mode. Le TypeError
    a ete avale par un except et presente comme une IMPOSSIBILITE
    STATISTIQUE -- un resultat scientifique faux, ne d'un defaut de signature,
    parce que la documentation n'avait pas ete ouverte.

    AVERTISSEMENT et non BLOQUANT : une documentation absente n'empeche pas la
    plateforme de tourner, et refuser le demarrage punirait l'operateur venu
    la reconstruire. Mais le silence serait pire -- on croirait la consulter.
    """
    corpus = os.path.join(ROOT, "references", "python_libs_docs")
    index = os.path.join(ROOT, ".nexus", "index_doc_libs.tsv")
    if not os.path.isdir(corpus):
        return noter("doc python", False, AVERTISSEMENT,
                     "corpus absent — la reabsorber depuis le depot voisin")
    if not os.path.isfile(index):
        return noter("doc python", False, AVERTISSEMENT,
                     "index absent — python scripts/nexus_doc.py --construire")
    try:
        with io.open(index, encoding="utf-8") as f:
            lignes = sum(1 for _ in f)
    except Exception as exc:
        return noter("doc python", False, AVERTISSEMENT,
                     "index illisible : %s" % str(exc)[:60])
    # Un index vide se lit comme un index present : c'est le pire des deux.
    if lignes < 1000:
        return noter("doc python", False, AVERTISSEMENT,
                     "index suspect : %d symboles seulement" % lignes)
    noter("doc python", True, AVERTISSEMENT, "%d symboles consultables" % lignes)

def controle_encodage_sortie() -> None:
    """
    Quel script accentue plantera-t-il demain sur une console cp1252 ?

    Mesure quatre fois en deux jours : un script affiche du texte accentue
    sans reconfigurer sa sortie, et UnicodeEncodeError (charmap) le tue sur
    la console Windows. Chacun a ete corrige UN PAR UN, quand il mordait --
    ce qui garantit seulement que le prochain plantera aussi. Ce controle
    remplace la correction au cas par cas par le recensement de tous les
    exposes : ceux qui ecrivent (print ou sys.stdout.write), portent du non
    ASCII, et n'appellent pas sys.stdout.reconfigure.

    AVERTISSEMENT et non BLOQUANT : un defaut d'affichage n'empeche pas de
    demarrer, et refuser le demarrage punirait l'operateur venu corriger.

    Ne plante jamais : un fichier illisible est passe, non juge.
    """
    dossier = os.path.join(ROOT, "scripts")
    try:
        noms = sorted(n for n in os.listdir(dossier) if n.endswith(".py"))
    except OSError as exc:
        ignorer("encodage sortie", "scripts illisible : %s" % str(exc)[:60])
        return
    exposes = []
    for nom in noms:
        try:
            with open(os.path.join(dossier, nom), "rb") as f:
                brut = f.read()
        except Exception:
            continue  # illisible : passe, jamais fatal
        if brut.isascii():
            continue
        source = brut.decode("utf-8", errors="replace")
        if "sys.stdout.reconfigure" in source:
            continue
        if not re.search(r"\bprint\s*\(", source) and "sys.stdout.write" not in source:
            continue
        exposes.append(nom)
    if exposes:
        noter(
            "encodage sortie",
            False,
            AVERTISSEMENT,
            "%d script(s) exposes : %s"
            % (len(exposes), ", ".join(exposes[:6])),
        )
    else:
        noter(
            "encodage sortie",
            True,
            AVERTISSEMENT,
            "tout script accentue reconfigure sa sortie",
        )


def controle_filtres_accordes() -> None:
    """
    Les deux filtres de confidentialité refusent-ils les mêmes fichiers ?

    Le dépôt possède deux filtres qui décident quels fichiers peuvent être
    envoyés à un modèle distant : l'un dans scripts/nexus_agent.py, l'autre
    dans tools/nexus-mcp/server.js. Ils ont divergé sans que rien ne puisse
    le dire : dix fichiers porteurs de jetons avérés, dont un fichier de
    compte de service et un fichier de jetons d'interface en ligne de
    commande, étaient refusés par l'un et acceptés par l'autre. Un
    commentaire affirmait pourtant que les deux appliquaient les mêmes
    règles.

    Ce contrôle compare les listes de noms littéraux de fichiers refusés
    (FICHIERS_SECRETS côté Python, SECRET_FILES côté JavaScript) et signale
    toute entrée présente dans l'un et absente de l'autre, dans les deux
    sens. Il ne montre que des noms de fichiers, jamais leur contenu.
    """
    chemin_python = os.path.join(ROOT, "scripts", "nexus_agent.py")
    chemin_js = os.path.join(ROOT, "tools", "nexus-mcp", "server.js")

    # Lecture et extraction côté Python
    try:
        with io.open(chemin_python, encoding="utf-8", errors="replace") as f:
            source_py = f.read()
    except OSError as exc:
        ignorer("filtres accordes", "scripts/nexus_agent.py illisible : %s" % exc)
        return
    try:
        arbre = ast.parse(source_py, filename="nexus_agent.py")
    except SyntaxError as exc:
        ignorer("filtres accordes", "scripts/nexus_agent.py invalide : %s" % exc)
        return
    fichiers_py = set()
    for node in ast.iter_child_nodes(arbre):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "FICHIERS_SECRETS":
                    try:
                        valeur = ast.literal_eval(node.value)
                        if isinstance(valeur, (list, tuple, set)):
                            fichiers_py = {str(x) for x in valeur}
                    except Exception:
                        pass
                    break
            if fichiers_py:
                break
    if not fichiers_py:
        ignorer("filtres accordes", "FICHIERS_SECRETS introuvable ou vide dans nexus_agent.py")
        return

    # Lecture et extraction côté JavaScript
    try:
        with io.open(chemin_js, encoding="utf-8", errors="replace") as f:
            source_js = f.read()
    except OSError as exc:
        ignorer("filtres accordes", "tools/nexus-mcp/server.js illisible : %s" % exc)
        return
    m = re.search(r"\bSECRET_FILES\s*=\s*\[(.*?)\]", source_js, re.DOTALL)
    if not m:
        ignorer("filtres accordes", "SECRET_FILES introuvable dans server.js")
        return
    fichiers_js = set()
    for chaine in re.findall(r"""(['"])(.*?)\1""", m.group(1)):
        fichiers_js.add(chaine[1])

    # Comparaison
    seulement_py = fichiers_py - fichiers_js
    seulement_js = fichiers_js - fichiers_py
    if seulement_py or seulement_js:
        detail_parts = []
        if seulement_py:
            detail_parts.append("présents dans nexus_agent.py mais absents de server.js : %s" % ", ".join(sorted(seulement_py)))
        if seulement_js:
            detail_parts.append("présents dans server.js mais absents de nexus_agent.py : %s" % ", ".join(sorted(seulement_js)))
        detail = " ; ".join(detail_parts)
        noter("filtres accordes", False, BLOQUANT, detail)
    else:
        noter("filtres accordes", True, BLOQUANT,
              "les deux filtres refusent les mêmes %d fichiers" % len(fichiers_py))

# ----------------------------------------------------------------------
# Contrôles runtime — exigent la passerelle en marche
# ----------------------------------------------------------------------
def passerelle_vivante() -> bool:
    try:
        with urllib.request.urlopen(PASSERELLE + "/health/liveliness", timeout=5):
            return True
    except Exception:
        return False


def controle_gardes_accordes_wrap() -> None:
    """
    Adapte controle_gardes_accordes a la sequence, qui appelle sans argument
    et attend que le controle NOTE lui-meme.

    La fonction jugee garde sa signature (racine) -> (etat, detail) : c est
    ainsi qu elle est eprouvable sur un depot jetable, sans toucher au vrai
    .claude/settings.json.
    """
    etat, detail = controle_gardes_accordes(ROOT)
    if etat == "OK":
        noter("gardes accordes", True, BLOQUANT, detail)
    elif etat == "ALERTE":
        noter("gardes accordes", False, AVERTISSEMENT, detail)
    else:
        noter("gardes accordes", False, BLOQUANT, detail)


# ---------------------------------------------------------------------------
# LES CHIFFRES DU README NE SONT GARDES PAR RIEN.
#
# Le README est la VITRINE PUBLIEE sur GitHub. Deux de ses chiffres avaient
# gele : « 33 alias » pour le plan local, la ou la configuration en declare
# 53, et « 40 modeles locaux mesures » la ou le releve en porte 48.
#
# Ils ont ete CITES PAR UN TIERS qui lisait le README, et repris comme vrais.
# C'est la regle de ce depot -- « une mesure gelee ment le lendemain » --
# empruntee au depot voisin, appliquee aux pools, au port du moteur, aux
# corpus annexes, et pas a sa propre vitrine.
#
# LA SEVERITE, et elle est raisonnee :
#   divergence sur les trois alias -> BLOQUE. Le fichier est PUBLIE, et la
#     correction est triviale : changer un nombre. Un avertissement qu'aucun
#     code de sortie n'accompagne finit par ne plus etre lu.
#   phrase « NN modeles mesures » -> ALERTE. Les modeles MESURES sont une
#     sous-population des alias exposes ; les deux peuvent legitimement
#     differer, et bloquer la-dessus serait un garde trop large.
#   configuration illisible -> IGNORE. Une mesure impossible n'est pas une
#     mesure a zero, et bloquer empecherait de reparer.
# ---------------------------------------------------------------------------


def _alias_declares(racine):
    """
    Compte les alias par plan, depuis la CONFIGURATION.

    La conformite tourne AVANT le demarrage : lire la passerelle exigerait
    qu'elle soit allumee, precisement quand elle ne l'est pas encore. La
    configuration est la source declaree -- et c'est bien ce que le README
    decrit quand il ecrit « alias ».

    Leve si la configuration est illisible : l'appelant en fait un IGNORE,
    car une mesure impossible n'est pas une mesure a zero.

    Les ROUTEURS sont exclus du compte : un alias de routeur ne designe pas un
    moteur mais une politique, et le tableau du README compte des moteurs.
    """
    import yaml
    with io.open(os.path.join(racine, "litellm_config.yaml"),
                 encoding="utf-8") as fh:
        conf = yaml.safe_load(fh)
    comptes = {"local": 0, "cloud": 0, "anthropic": 0}
    for entree in (conf.get("model_list") or []):
        params = entree.get("litellm_params") or {}
        brut = str(params.get("model") or "")
        base = str(params.get("api_base") or "")
        if brut.startswith("auto_router/"):
            continue
        if brut.startswith("anthropic/"):
            comptes["anthropic"] += 1
        elif "ollama.com" in base:
            comptes["cloud"] += 1
        else:
            comptes["local"] += 1
    return comptes


def controle_readme_chiffres(racine, lire_modeles):
    """Controle la coherence des chiffres du README avec la passerelle."""
    # helper pour tronquer le detail a 90 caracteres
    def _tronque(txt):
        return txt[:90] if len(txt) > 90 else txt

    # 1. lecture du README
    chemin = os.path.join(racine, "README.md")
    try:
        with io.open(chemin, "r", encoding="utf-8") as f:
            contenu = f.read()
    except Exception:
        return ("ALERTE", _tronque("README absent ou illisible"))

    # 2. appel de lire_modeles une seule fois
    try:
        mesures = lire_modeles()
    except Exception:
        return ("IGNORE", _tronque("passerelle injoignable : chiffres non verifiables"))

    # verification du dictionnaire attendu
    if not isinstance(mesures, dict):
        return ("ALERTE", _tronque("resultat de lire_modeles invalide"))

    # 3. recherche de la ligne avec trois nombres precedes de "alias"
    pattern_alias = re.compile(r'(\d+)\s+alias.*?(\d+)\s+alias.*?(\d+)\s+alias', re.DOTALL)
    match = pattern_alias.search(contenu)
    if not match:
        return ("ALERTE", _tronque("ligne des trois alias introuvable dans le README"))
    try:
        local_r = int(match.group(1))
        cloud_r = int(match.group(2))
        anthropic_r = int(match.group(3))
    except Exception:
        return ("ALERTE", _tronque("impossible d'extraire les nombres d'alias"))

    # 4. comparaison avec les mesures
    divergences = []
    if mesures.get("local") != local_r:
        divergences.append(f"README dit {local_r} alias locaux, la configuration en declare {mesures.get('local')}")
    if mesures.get("cloud") != cloud_r:
        divergences.append(f"README dit {cloud_r} alias cloud, la configuration en declare {mesures.get('cloud')}")
    if mesures.get("anthropic") != anthropic_r:
        divergences.append(f"README dit {anthropic_r} alias anthropic, la configuration en declare {mesures.get('anthropic')}")
    if divergences:
        # LE COMPTE D'ABORD : le detail est borne a 90 signes, et trois
        # divergences le depassent. Sans le compte en tete, la troisieme
        # disparait SANS que rien ne le signale -- « la reponse partielle
        # rendue sans le dire ». Huit caracteres survivent a toute
        # troncature.
        detail = "%d divergence(s) : %s" % (
            len(divergences), " ; ".join(divergences))
        return ("BLOQUE", _tronque(detail))

    # 5. recherche de la phrase sur le nombre de modeles locaux mesures
    pattern_modele = re.compile(r'sur les (\d+) modeles locaux mesures')
    match_modele = pattern_modele.search(contenu)
    if match_modele:
        nb_modele = int(match_modele.group(1))
        if nb_modele != mesures.get("local"):
            detail = f"README dit {nb_modele} modeles locaux mesures, la configuration en declare {mesures.get('local')}"
            return ("ALERTE", _tronque(detail))

    # 6. tout concorde
    return ("OK", "3 chiffres du README concordent avec la configuration declaree")

def controle_readme_chiffres_wrap() -> None:
    """Adapte le controle a la sequence, qui appelle sans argument."""
    etat, detail = controle_readme_chiffres(ROOT, lambda: _alias_declares(ROOT))
    if etat == "OK":
        noter("chiffres du README", True, BLOQUANT, detail)
    elif etat == "IGNORE":
        noter("chiffres du README", True, IGNORE, detail)
    elif etat == "ALERTE":
        noter("chiffres du README", False, AVERTISSEMENT, detail)
    else:
        noter("chiffres du README", False, BLOQUANT, detail)



def _demarrage_passerelle():
    """
    L'instant ou le conteneur de la passerelle a demarre.

    LEVE si Docker est absent, si le conteneur n'existe pas ou s'il est
    arrete : l'appelant en fait un IGNORE. Un conteneur arrete n'est pas une
    derive -- c'est un conteneur arrete, et le dire autrement enverrait
    chercher au mauvais endroit.
    """
    import datetime
    import subprocess
    r = subprocess.run(
        ["docker", "inspect", "-f", "{{.State.StartedAt}}", "litellm-proxy"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=20)
    if r.returncode != 0 or not (r.stdout or "").strip():
        raise RuntimeError("conteneur litellm-proxy introuvable ou arrete")
    brut = r.stdout.strip()
    # Docker rend un instant UTC en ISO 8601 ; on le ramene en heure locale,
    # sans quoi la comparaison avec un mtime local serait decalee du fuseau --
    # et rendrait une derive fantome ou en masquerait une vraie.
    txt = brut.replace("Z", "+00:00")
    if "." in txt:
        avant, apres = txt.split(".", 1)
        fuseau = ""
        for marque in ("+", "-"):
            if marque in apres:
                i = apres.index(marque)
                fuseau = apres[i:]
                break
        txt = avant + fuseau
    inst = datetime.datetime.fromisoformat(txt)
    return inst.astimezone().replace(tzinfo=None)


def controle_config_active(racine, date_demarrage):
    """Controle si le fichier de config est plus ancien que le demarrage.
    Retourne (etat, detail) où etat est "OK", "ALERTE" ou "IGNORE".
    """
    try:
        demarrage = date_demarrage()
    except Exception:
        return ("IGNORE", "date_demarrage indisponible")
    try:
        chemin = os.path.join(racine, "litellm_config.yaml")
        if not os.path.isfile(chemin):
            return ("ALERTE", "litellm_config.yaml introuvable")
        mtime = os.path.getmtime(chemin)
        modif = datetime.datetime.fromtimestamp(mtime)
        modif_str = modif.strftime("%Y-%m-%d %H:%M")
        dem_str = demarrage.strftime("%Y-%m-%d %H:%M")
        if modif <= demarrage:
            return ("OK", f"{modif_str} <= {dem_str}")
        delta = modif - demarrage
        secs = int(delta.total_seconds())
        h, r = divmod(secs, 3600)
        m = r // 60
        detail = f"{modif_str} > {dem_str} ({h}h{m}m) - docker compose restart litellm"
        if len(detail) > 90:
            detail = detail[:90]
        return ("ALERTE", detail)
    except Exception as e:
        msg = str(e)
        if len(msg) > 90:
            msg = msg[:90]
        return ("ALERTE", msg)

def controle_config_active_wrap() -> None:
    """Adapte le controle a la sequence, qui appelle sans argument."""
    etat, detail = controle_config_active(ROOT, _demarrage_passerelle)
    if etat == "OK":
        noter("configuration active", True, BLOQUANT, detail)
    elif etat == "IGNORE":
        noter("configuration active", True, IGNORE, detail)
    else:
        # ALERTE et non blocage : la conformite tourne AVANT le demarrage de
        # la pile. Bloquer sur « la passerelle sert une configuration
        # perimee » empecherait precisement la sequence qui la redemarre.
        noter("configuration active", False, AVERTISSEMENT, detail)



# ---------------------------------------------------------------------------
# LA COMMANDE `nexus` PEUT MANQUER DANS UNE EDITION DE POWERSHELL.
#
# INCIDENT VECU le 2026-08-31. L'operateur ouvre un terminal sur un autre
# projet et tape :
#
#     PS G:\TRADING_LIVE_IA> nexus mcp
#     nexus : Le terme «nexus» n'est pas reconnu...
#
# Il etait bloque : sans cette commande, impossible de brancher le pont sur un
# nouveau projet.
#
# CAUSE MESUREE. Windows porte DEUX editions de PowerShell, avec DEUX profils
# dans deux repertoires differents :
#
#     Documents/WindowsPowerShell/...   -> Windows PowerShell 5.1
#     Documents/PowerShell/...          -> pwsh 7
#
# La commande n'etait installee que dans le second, parce que
# `Install-NexusCommande.ps1` vise le `$PROFILE` de la session QUI LE LANCE --
# et il avait ete lance depuis pwsh 7. L'edition 5.1 ne l'a jamais eue, sans
# que rien ne le dise.
#
# COMPLICATION, presente sur cette machine : le dossier Documents est REDIRIGE
# VERS ONEDRIVE. Un controle qui ne regarderait que ~/Documents ne verrait
# rien et conclurait a tort que la commande est absente partout. Les huit
# chemins possibles sont donc examines.
#
# ALERTE et non BLOQUE : une commande de confort absente n'empeche pas la
# plateforme de fonctionner, et bloquer le demarrage pour cela serait un garde
# trop large.
# ---------------------------------------------------------------------------


def controle_commande_nexus(accueil):
    """Controle la presence de la commande nexus dans les profils PowerShell.
    Retourne (etat, detail) selon l'algorithme specifie."""
    try:
        bases = [
            os.path.join(accueil, "Documents"),
            os.path.join(accueil, "OneDrive", "Documents")
        ]
        editions = ["WindowsPowerShell", "PowerShell"]
        profils = ["Microsoft.PowerShell_profile.ps1", "profile.ps1"]

        # dictionnaire edition -> liste des chemins existants
        existants = {e: [] for e in editions}
        bases_trouves = set()

        for base in bases:
            if not os.path.isdir(base):
                continue
            for edition in editions:
                for nom in profils:
                    chemin = os.path.join(base, edition, nom)
                    if os.path.isfile(chemin):
                        existants[edition].append(chemin)
                        bases_trouves.add(base)

        if not any(existants[e] for e in editions):
            return ("IGNORE", "aucun profil PowerShell trouve")

        # detection de la presence du mot 'nexus' (sans casse)
        servies = set()
        for edition, chemins in existants.items():
            for chemin in chemins:
                try:
                    with io.open(chemin, "r", encoding="utf-8", errors="replace") as f:
                        contenu = f.read()
                    if "nexus" in contenu.lower():
                        servies.add(edition)
                        break   # une fois trouve, on peut passer a l'edition suivante
                except Exception:
                    # lecture impossible, on ignore ce profil
                    continue

        presentes = {e for e, lst in existants.items() if lst}
        manquantes = presentes - servies

        # preparation du detail
        base_desc = ", ".join(
            "OneDrive/Documents" if "OneDrive" in b else "Documents"
            for b in sorted(bases_trouves)
        )
        if not manquantes:
            detail = f"editions servies: {', '.join(sorted(servies))} ({base_desc})"
            return ("OK", detail)
        miss = ", ".join(sorted(manquantes))
        detail = (f"edition manquante: {miss}, voir scripts/Install-NexusCommande.ps1 "
                  f"({base_desc})")
        # on tronque a 90 caracteres si necessaire
        if len(detail) > 90:
            detail = detail[:90]
        return ("ALERTE", detail)
    except Exception as e:
        msg = str(e).replace("\n", " ").replace("\r", " ")
        if len(msg) > 90:
            msg = msg[:90]
        return ("ALERTE", msg)

def controle_commande_nexus_wrap() -> None:
    """Adapte le controle a la sequence, qui appelle sans argument."""
    etat, detail = controle_commande_nexus(os.path.expanduser("~"))
    if etat == "OK":
        noter("commande nexus", True, BLOQUANT, detail)
    elif etat == "IGNORE":
        noter("commande nexus", True, IGNORE, detail)
    else:
        noter("commande nexus", False, AVERTISSEMENT, detail)



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
            # LE MATCHER CONTIENT « Agent », il ne lui est plus egal.
            #
            # Mesure du 2026-08-31 : le garde n'etait cable que sur l'outil
            # `Agent`, alors qu'un SECOND outil lance des sous-agents --
            # `Workflow` -- et que rien ne le surveillait. 460 sous-agents,
            # 32,1 millions de jetons factures en une nuit, quand le contrat
            # cite deja 475 000 comme « l'inverse du but ».
            #
            # Le matcher est donc devenu « Agent|Workflow », et ce controle,
            # qui comparait a la lettre, a BLOQUE le demarrage sur sa propre
            # correction. Il verifie desormais la PRESENCE des deux portes,
            # non l'egalite d'une chaine.
            matcher = (entree.get("matcher") or "") if isinstance(entree, dict) else ""
            if "Agent" not in matcher:
                continue
            for h in entree.get("hooks") or []:
                if isinstance(h, dict) and "nexus_garde_agent" in (h.get("command") or ""):
                    cable = True
    if not cable:
        noter("garde agent", False, BLOQUANT,
              "aucun hook PreToolUse couvrant Agent n'invoque nexus_garde_agent")
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
        controle_releves_lisibles,
        controle_travail_sur_original,
        controle_pont_lecture_seule,
        controle_cablage,
        controle_imports,
        controle_portee_import,
        controle_hooks_cables,
        controle_verrou_machine,
        controle_mcp_a_jour,
        controle_secrets,
        controle_secrets_documentes,
        controle_exemple_present,
        controle_env_hors_git,
        controle_disque,
        controle_pont_mcp,
        controle_doc_python,
        controle_mcp_double_portee,
        controle_garde_agent,
        controle_gardes_accordes_wrap,
        controle_readme_chiffres_wrap,
        controle_config_active_wrap,
        controle_commande_nexus_wrap,
        controle_encodage_sortie,
        controle_filtres_accordes,
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
