#!/usr/bin/env python3
"""
nexus_ruche.py – coordinateur qui découvre les cibles du dépôt et lance
plusieurs essaims concurrents jusqu’à ce que le dépôt soit couvert.

Pourquoi ?  La version précédente ne traitait qu’une cible à la fois et
requérait de les nommer manuellement.  Cette ruche automatise la découverte,
la priorisation, le découpage en lots et la relance en cas d’échec, tout en
respectant les limites de ressources de l’hôte.

Le script ne dépend que de la bibliothèque standard.
"""

# --------------------------------------------------------------------------- #
# Protection de l'encodage de la sortie
# --------------------------------------------------------------------------- #
# La console Windows utilise souvent cp1252 qui ne sait pas encoder certains
# caractères (ex. espace fine insécable) provenant de réponses de modèles.
# On reconfigure stdout et stderr en UTF‑8 avec errors="replace" afin que
# tout caractère non supporté soit remplacé plutôt que de provoquer une
# UnicodeEncodeError qui interromprait l'exécution.
import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import argparse
import concurrent.futures
import json
import os
import time
from pathlib import Path
from subprocess import run, CalledProcessError

# nexus_agent etait EMPLOYE (racine_travail) sans etre importe : toute
# execution sans --racine levait NameError. Trouve par la suite complete du
# 2026-08-30, jamais jouee depuis les changements du jour -- le sujet
# « suite complete apres tous les changements » etait ouvert au cockpit, et
# il a paye des sa premiere execution.
#
# On suit la convention des autres scripts du depot (nexus_essaim,
# nexus_patch, nexus_relais) : le repertoire de ce fichier est ajoute au
# chemin, puis l'import est tente.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    import nexus_agent  # noqa: E402
except Exception:  # pragma: no cover
    # Repli : sans le module, la racine reste derivable de la position de ce
    # fichier. Mieux vaut une racine deduite qu'un plantage -- et le repli
    # donne le meme resultat dans le cas normal.
    nexus_agent = None

# --------------------------------------------------------------------------- #
# Constantes
# --------------------------------------------------------------------------- #
# Le répertoire racine du dépôt (celui contenant ce script) est utilisé
# pour toutes les opérations de découverte et pour le journal d’état.
BASE_DIR = Path(__file__).resolve().parent.parent

ETAT_FICHIER = BASE_DIR / ".nexus" / "ruche-etat.json"
MAX_ESSAIMS = 4
TAILLE_LOT_DEFAUT = 6
ESSAIMS_DEFAUT = 2
LIGNES_MIN = 30
EXCLUSIONS_DIR = {"__pycache__", ".nexus"}
SECRET_MOTS = {"secret", "passwd", "password", "token", "key"}

# Chemin absolu du script d'essaim, résolu depuis le répertoire contenant ce fichier.
# On utilise os.path.abspath(__file__) pour obtenir le chemin réel du script,
# puis os.path.dirname pour en extraire le répertoire. Cette méthode ne dépend
# d'aucun répertoire de travail courant et évite le problème du doublement
# « scripts/scripts » qui survenait avec un chemin relatif.
ESSAIM_SCRIPT = Path(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "nexus_essaim.py")
)

# --------------------------------------------------------------------------- #
# Fonctions utilitaires
# --------------------------------------------------------------------------- #
def ecrire_etat_atomique(delta: dict) -> None:
    """
    Fusionne "delta" dans le journal sur disque et l'ecrit atomiquement.

    Relit l'etat courant sur disque avant d'ecrire, plutot que de faire
    confiance a la copie en memoire de l'appelant : si deux invocations de
    la ruche tournent en parallele (deux terminaux, une reprise apres
    coupure), chacune ne connait que ses propres lots. Ecrire sa vue
    entiere a chaque fois ecraserait la progression enregistree par
    l'autre entre-temps -- une cible deja corrigee et verifiee par l'une
    reapparaitrait "a refaire" pour la suivante. Ne fusionner que le delta
    (les cibles que CET appel vient de traiter) reduit la fenetre de
    course a la duree d'une lecture-ecriture au lieu de toute l'execution.

    Limite assumee : un delta peut encore effacer des entrees legitimement
    purgees par une autre invocation (cibles qui n'existent plus). Une
    entree perimee qui reapparait ainsi n'est pas dangereuse : elle est
    filtree du calcul de cette execution par main() avant tout traitement,
    au pire retraitee inutilement une fois.
    """
    ETAT_FICHIER.parent.mkdir(parents=True, exist_ok=True)
    disque = charger_etat()
    disque.update(delta)
    tmp = ETAT_FICHIER.with_suffix(".tmp")
    tmp.write_text(json.dumps(disque, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, ETAT_FICHIER)


def charger_etat() -> dict:
    """Charger le journal d’état s’il existe, sinon retourner un dict vide."""
    if ETAT_FICHIER.is_file():
        try:
            return json.loads(ETAT_FICHIER.read_text(encoding="utf-8"))
        except Exception:
            # Corruption éventuelle : repartir de zéro.
            return {}
    return {}


def est_secret(nom: str) -> bool:
    """Détecter si le nom évoque un secret (ex. contient 'secret', 'token', …)."""
    lower = nom.lower()
    return any(mot in lower for mot in SECRET_MOTS)


def fichier_valide(p: Path) -> bool:
    """Vérifier qu’un fichier doit être traité : extension, taille, secret, etc."""
    if not p.is_file():
        return False
    if p.parent.name in EXCLUSIONS_DIR:
        return False
    if est_secret(p.name):
        return False
    try:
        lignes = sum(1 for _ in p.open(encoding="utf-8", errors="ignore"))
        if lignes < LIGNES_MIN:
            return False
    except Exception:
        return False
    return True


def decouvrir_cibles(racine: Path) -> list[Path]:
    """Lister les cibles auditables du dépôt selon les règles de découverte."""
    # Convertir en Path si nécessaire.
    racine_path = Path(racine) if not isinstance(racine, Path) else racine
    cibles = set()
    cibles.update(racine_path.glob("scripts/*.py"))
    cibles.update(racine_path.glob("scripts/*.ps1"))
    cibles.update(racine_path.glob("*.ps1"))
    cibles.update(racine_path.glob("tools/nexus-mcp/*.js"))
    return [p for p in cibles if fichier_valide(p)]


def prioriser(cibles: list[Path]) -> list[Path]:
    """Trier les cibles du plus gros et le plus récemment modifié au plus petit."""
    def cle(p: Path):
        try:
            stat = p.stat()
            taille = stat.st_size
            mtime = stat.st_mtime
        except Exception:
            taille = 0
            mtime = 0
        # On veut décroissant sur taille puis mtime
        return (-taille, -mtime)

    return sorted(cibles, key=cle)


def decouper_lots(cibles: list[Path], taille_lot: int) -> list[list[Path]]:
    """Diviser la liste ordonnée en lots de taille donnée."""
    return [cibles[i:i + taille_lot] for i in range(0, len(cibles), taille_lot)]


def lancer_essaim(lot: list[Path], simuler: bool, plan: str, essaims: int) -> dict:
    """
    Lancer un essaim (sous‑processus) sur le lot fourni.
    Retourne un dict {str(cible): {"verdict": "ok"|"echec", "cause": str}}.
    """
    resultats = {}
    if simuler:
        # Message sans accents, comme requis.
        print(f"Simuler essaim sur {len(lot)} cible(s).")
        for p in lot:
            resultats[str(p)] = {"verdict": "ok", "cause": ""}
        return resultats

    # Verifier que le script d'essaim existe avant de le lancer.
    if not ESSAIM_SCRIPT.is_file():
        msg = f"Script essaim introuvable: {ESSAIM_SCRIPT}"
        print(msg)
        for p in lot:
            resultats[str(p)] = {"verdict": "echec", "cause": msg}
        return resultats

    # --------------------------------------------------------------
    # Construction de la ligne de commande.
    # --------------------------------------------------------------
    # COMMENTAIRE : seules les options reconnues par nexus_essaim.py
    # sont transmises.  L'option --essaims appartient a la ruche et
    # provoquerait "unrecognized arguments" dans l'essaim, ce qui
    # ferait échouer tout le lot.  De même, l'option correcte pour le
    # plan est --plans (pluriel).  En filtrant ainsi, on évite que
    # l'ajout futur d'options à la ruche ne casse l'essaim.
    cmd = [
        sys.executable,
        str(ESSAIM_SCRIPT),
        "--cibles"
    ] + [str(p) for p in lot] + [
        "--plans", plan
    ]

    # Delai maximal avant de considerer l'essaim comme expire. nexus_essaim.py
    # borne deja chacune de ses etapes internes (audit, correction) a 900 s
    # via NEXUS_AGENT_TIMEOUT / NEXUS_TIMEOUT, mais rien ici ne bornait le
    # sous-processus dans son ensemble : sans ce delai, un lot dont une seule
    # cible restait bloquee (reseau, modele qui ne repond plus) suspendait la
    # ruche entiere indefiniment, sans jamais produire ni rapport ni code de
    # sortie. Une variable d'environnement permet de l'elargir pour un gros
    # lot (plusieurs vagues internes si taille-lot depasse le --parallele de
    # l'essaim) sans toucher au code.
    import subprocess
    timeout_sec = int(os.getenv("NEXUS_RUCHE_TIMEOUT", "1800"))

    try:
        proc = run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            timeout=timeout_sec,
        )
        code = proc.returncode
        sortie_err = proc.stderr.strip()
        sortie_out = proc.stdout.strip()
    except subprocess.TimeoutExpired:
        # Le sous-processus est tue par subprocess.run : on ne peut plus
        # affirmer quoi que ce soit sur l'etat individuel de chaque cible
        # (nexus_essaim.py restaure lui-meme sa sauvegarde avant d'atteindre
        # ses propres delais internes, mais un delai externe plus court peut
        # interrompre avant cette restauration). On les marque donc toutes en
        # echec plutot que de deviner un succes.
        msg = f"Essaim expire apres {timeout_sec}s"
        print(msg)
        for p in lot:
            resultats[str(p)] = {"verdict": "echec", "cause": msg}
        return resultats
    except FileNotFoundError as e:
        code = 1
        sortie_err = str(e)
        sortie_out = ""
    except CalledProcessError as e:
        code = e.returncode
        sortie_err = e.stderr.strip() if e.stderr else str(e)
        sortie_out = e.stdout.strip() if e.stdout else ""

    # Lecture du rapport reel de l'essaim : une ligne CSV par cible
    # ("nom,verdict,nb_trouvailles,tokens,modele,plan"), jamais du JSON --
    # nexus_essaim.py n'en a jamais produit. La tentative json.loads()
    # precedente echouait donc a chaque appel et retombait systematiquement
    # sur le seul code de retour du sous-processus pour TOUT le lot : un
    # echec sur une cible parmi plusieurs faisait alors classer "echec" les
    # cibles reellement corrigees du meme lot, qui repassaient inutilement
    # au banc a l'execution suivante. Les cibles non reconnues (nom
    # ambigu, ligne absente parce que l'essaim a ete interrompu en cours de
    # lot) retombent sur ce meme verdict global, seul renseignement fiable
    # qui reste alors disponible pour elles.
    par_nom = parser_rapport_essaim(sortie_out, lot) if sortie_out else {}

    statut_defaut = "ok" if code == 0 else "echec"
    cause_defaut = "" if statut_defaut == "ok" else (sortie_err or "code de retour non nul")
    for p in lot:
        cle = str(p)
        resultats[cle] = par_nom.get(cle, {"verdict": statut_defaut, "cause": cause_defaut})
    return resultats


def traiter_lots(
    lots: list[list[Path]],
    essaims: int,
    simuler: bool,
    etat: dict,
    plan: str,
) -> tuple[dict, int]:
    """
    Exécuter les lots en parallèle, au maximum `essaims` processus simultanés.
    Met à jour le dictionnaire d’état et renvoie le dictionnaire ainsi que le
    nombre de cibles réellement traitées durant cet appel.
    """
    # Limiter la concurrence
    if essaims > MAX_ESSAIMS:
        # Message sans accents.
        print(f"Limite atteinte : le nombre d'essaims est plafonne a {MAX_ESSAIMS}.")
        essaims = MAX_ESSAIMS

    traitees = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=essaims) as pool:
        futures = []
        for lot in lots:
            # Ignorer les cibles déjà traitées avec succes.
            lot_a_traiter = [p for p in lot if etat.get(str(p), {}).get("verdict") != "ok"]
            if not lot_a_traiter:
                continue
            futures.append(pool.submit(lancer_essaim, lot_a_traiter, simuler, plan, essaims))

        for fut in concurrent.futures.as_completed(futures):
            res = fut.result()
            # Delta de cet appel seulement : ecrire_etat_atomique() fusionne
            # avec le disque plutot que d'ecraser avec toute la copie en
            # memoire (voir sa docstring) -- lui passer "etat" en entier a
            # chaque iteration aurait annule cette protection.
            delta = {}
            for cible, info in res.items():
                verdict = info["verdict"]
                cause = info.get("cause", "")
                # En mode simulation, on ne persiste pas les résultats.
                if not simuler:
                    etat[cible] = {
                        "verdict": verdict,
                        "timestamp": time.time(),
                        "processed": True,
                        "cause": cause,
                    }
                    delta[cible] = etat[cible]
                else:
                    # On compte les cibles simulées pour le rapport mais on ne les enregistre pas.
                    traitees += 1
                if not simuler:
                    traitees += 1
            if delta:
                ecrire_etat_atomique(delta)  # écriture atomique après chaque lot
    return etat, traitees


def rapport_final(etat: dict, total_cibles: int, traitees: int, start_time: float) -> None:
    """Afficher le résumé des traitements."""
    # Cibles réellement traitees durant cette execution.
    traitees_durant = traitees
    # Cibles sautees parce qu'elles etaient deja abouties.
    sautees = total_cibles - traitees_durant

    ok = sum(1 for v in etat.values() if v["verdict"] == "ok")
    echec = sum(1 for v in etat.values() if v["verdict"] == "echec")
    ignore = sum(1 for v in etat.values() if v["verdict"] == "ignore")

    # "start_time" etait recu mais jamais lu : la ruche ne pouvait donc pas
    # dire elle-meme combien de temps une execution avait pris, ce qui
    # oblige quiconque veut mesurer l'effet de --essaims a chronometrer de
    # l'exterieur a chaque fois.
    duree = time.time() - start_time

    # Utiliser un bloc try/except pour garantir que le rapport s'affiche même si
    # un caractère non encodable apparaît dans les données.
    try:
        print("\n--- Rapport ---")
        print(f"Duree de cette execution       : {duree:.1f}s")
        print(f"Cibles traitees cette execution : {traitees_durant}")
        print(f"Cibles sautees (deja abouties) : {sautees}")
        print(f"Total cibles connues           : {total_cibles}")
        print(f"Abouties                       : {ok}")
        print(f"Echecs                         : {echec}")
        print(f"Ignorees                       : {ignore}")
        # Le compteur de jetons gratuits n'est pas mesure ici.
        print("Jetons gratuits consommes : non mesure")
        if echec:
            print("\nCibles en echec (a corriger) :")
            for cible, info in etat.items():
                if info["verdict"] == "echec":
                    cause = info.get("cause", "")
                    print(f"- {cible} : {cause}")
    except Exception:
        # En cas d'erreur d'encodage, on réessaye avec remplacement des caractères.
        sys.stdout.buffer.write(
            ("\n--- Rapport (degrade) ---\n"
             f"Duree de cette execution       : {duree:.1f}s\n"
             f"Cibles traitees cette execution : {traitees_durant}\n"
             f"Cibles sautees (deja abouties) : {sautees}\n"
             f"Total cibles connues           : {total_cibles}\n"
             f"Abouties                       : {ok}\n"
             f"Echecs                         : {echec}\n"
             f"Ignorees                       : {ignore}\n"
             "Jetons gratuits consommes : non mesure\n"
            ).encode("utf-8", errors="replace")
        )
        if echec:
            for cible, info in etat.items():
                if info["verdict"] == "echec":
                    cause = info.get("cause", "")
                    line = f"- {cible} : {cause}\n"
                    sys.stdout.buffer.write(line.encode("utf-8", errors="replace"))


# --------------------------------------------------------------------------- #
# Point d’entrée
# --------------------------------------------------------------------------- #
def main() -> int:
    parser = argparse.ArgumentParser(
        description="Coordinateur de lancement d'essaims pour le depot Nexus."
    )
    parser.add_argument("--racine", help="Chemin racine du depot Nexus.")
    parser.add_argument("--essaims", type=int, default=ESSAIMS_DEFAUT,
                        help="Nombre d'essaims concurrents (max 4).")
    parser.add_argument("--taille-lot", type=int, default=TAILLE_LOT_DEFAUT,
                        help="Taille d'un lot de cibles.")
    parser.add_argument("--plans", choices=["cloud", "local", "deux"],
                        default="local", help="Plan transmis a chaque essaim.")
    parser.add_argument("--tout-refaire", action="store_true",
                        help="Ignorer le journal et tout retraiter.")
    parser.add_argument("--simuler", action="store_true",
                        help="Ne pas lancer de sousprocessus, simuler les resultats.")
    parser.add_argument("--max-cibles", type=int, default=None,
                        help="Plafonner le nombre de cibles traitees par cette execution.")
    args = parser.parse_args()

    # Determiner la racine du depot.
    if args.racine:
        racine = Path(args.racine)
    else:
        racine = (Path(nexus_agent.racine_travail()) if nexus_agent
                  else Path(__file__).resolve().parent.parent)
    print(f"Racine utilisee : {racine}")

    # Charger ou reinitialiser le journal d'etat
    if args.tout_refaire:
        etat = {}
    else:
        etat = charger_etat()

    # Decouverte, priorisation, puis plafond optionnel.
    cibles = decouvrir_cibles(racine)
    print(f"{len(cibles)} cibles decouvertes")
    cibles = prioriser(cibles)
    if args.max_cibles is not None:
        cibles = cibles[: max(0, args.max_cibles)]

    # Aucune cible a traiter : ni une decouverte vide (glob casse, mauvais
    # repertoire courant) ni un plafond nul ne doivent produire un succes
    # silencieux. Avant ce garde-fou, les deux cas laissaient "etat" vide et
    # "return 0 if all(...) else 1" valait 0 : all() sur un dictionnaire
    # vide est vrai en Python, donc "aucun travail" et "tout a reussi"
    # rendaient exactement le meme code de sortie.
    if not cibles:
        print("Aucune cible a traiter : rien n'a ete couvert.")
        return 1

    total_cibles = len(cibles)

    cibles_str = {str(p) for p in cibles}
    etat = {k: v for k, v in etat.items() if k in cibles_str}

    lots = decouper_lots(cibles, args.taille_lot)

    start_time = time.time()

    etat, traitees = traiter_lots(lots, args.essaims, args.simuler, etat, args.plans)

    rapport_final(etat, total_cibles, traitees, start_time)

    return 0 if all(v["verdict"] == "ok" for v in etat.values()) else 1




def parser_rapport_essaim(sortie_out: str, lot: list[Path]) -> dict:
    """
    Interprete le rapport CSV d'un essaim (une ligne par cible : nom de
    fichier, verdict, nb_trouvailles, tokens, modele, plan, et depuis peu
    un 7e champ optionnel portant le detail de l'echec) et le rattache aux
    chemins complets du lot par nom de fichier.

    Retourne {chemin_complet: {"verdict": "ok"|"echec", "cause": str}} pour
    les seules cibles reconnues sans ambiguite. Si deux cibles du meme lot
    partagent le meme nom de fichier, aucune des deux n'est rattachee : la
    correspondance redeviendrait un pari, pas une lecture, et l'appelant
    retombe alors sur le verdict global du lot pour ces cibles-la.
    """
    correspondance = {
        "ok": "ok",
        "sans trouvaille": "ok",
        "echec": "echec",
        "inconnu": "echec",
    }

    par_nom_lot: dict = {}
    for p in lot:
        par_nom_lot.setdefault(p.name, []).append(p)
    noms_uniques = {nom: chemins[0] for nom, chemins in par_nom_lot.items() if len(chemins) == 1}

    resultats = {}
    for ligne in sortie_out.splitlines():
        champs = ligne.strip().split(",")
        if len(champs) < 2:
            continue
        nom, verdict_brut = champs[0], champs[1]
        chemin = noms_uniques.get(nom)
        if chemin is None:
            continue
        verdict = correspondance.get(verdict_brut, "echec")
        # Le 7e champ, quand il existe, porte un diagnostic precis (dernier
        # message de nexus_patch.py, ou "timeout apres Ns"). Sans lui, la
        # cause se limitait a repeter le verdict brut, ce qui n'apprend
        # rien de plus qu'on ne savait deja -- c'est ce qui a oblige a
        # rejouer la meme consigne a la main pour comprendre un echec reel.
        detail = champs[6].strip() if len(champs) > 6 and champs[6].strip() else ""
        if verdict == "ok":
            cause = ""
        elif detail:
            cause = detail
        else:
            cause = f"essaim: {verdict_brut}"
        resultats[str(chemin)] = {"verdict": verdict, "cause": cause}
    return resultats
if __name__ == "__main__":
    sys.exit(main())
