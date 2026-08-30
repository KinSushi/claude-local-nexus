#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Ce qu'une session fraîche doit savoir, imprimé AU DÉMARRAGE.

POURQUOI CE FICHIER EXISTE
--------------------------
Le cockpit se terminait sur « les trois commandes de la prochaine session ».
Une consigne que l'opérateur doit penser à exécuter n'est pas une reprise :
c'est un pense-bête, et il ne survit pas à un redémarrage. La session fraîche
doit repartir seule, et charger son contexte sans qu'on le lui demande.

Appelé par un hook `SessionStart` (`.claude/settings.json`), sa sortie
standard est injectée dans le contexte au démarrage : l'orchestrateur la lit
avant d'avoir rien fait.

TROIS PRINCIPES, repris du `reprise_session.ps1` du dépôt SAS parce qu'ils
sont justes et déjà payés là-bas :

1. TOUT EST DÉRIVÉ, RIEN N'EST CODÉ EN DUR. Commits, état de l'arbre, sujets
   ouverts et tâches armées sont RELUS à chaque démarrage. Écrire ici « le
   pool fait 4 modèles » reproduirait le défaut que ce dépôt a déjà payé :
   une mesure figée que plus rien ne re-dérive, et qui ment le lendemain.

2. IL NE LANCE RIEN DE LONG. Ni conformité, ni banc, ni tests, ni réseau :
   ces rituels durent des minutes et chargent la machine. Un hook de
   démarrage qui bloque une session est désactivé au premier essai. Il DIT
   quoi lancer.

3. IL N'ÉCHOUE JAMAIS. Un hook qui plante au démarrage empêche de
   travailler. Chaque bloc est gardé, et un bloc qui ne peut pas répondre le
   DIT plutôt que de se taire : « je n'ai pas pu lire » et « il n'y a rien »
   sont deux états distincts, et les confondre est la faute que ce dépôt
   traque partout.

ÉCRIT PAR LE BANC LOCAL (`qwen3-coder-30b-local`, 2320 jetons, coût nul),
intégré après arbitrage de cinq défauts. Ils valent d'être nommés, car
quatre sur cinq sont des fautes que ce dépôt a déjà commises :

* `ROOT = dirname(abspath(__file__))` rendait `scripts/`, pas la racine —
  EXACTEMENT le défaut corrigé le matin même dans `nexus_essaim.py`, où une
  fonction nommée « racine du dépôt » rendait `scripts` et faisait atterrir
  quarante sauvegardes au mauvais endroit ;
* `executer()` rendait `(True, ...)` sans jamais regarder `returncode` : une
  commande en échec passait pour un succès muet ;
* le chemin du cockpit était relatif au répertoire courant et non à `ROOT`,
  donc introuvable dès qu'on lance le script d'ailleurs ;
* accents dans les chaînes IMPRIMÉES malgré la consigne — sous cp1252 la
  sortie d'un hook devient illisible au moment précis où elle compte ;
* `main()` ne rendait aucun code de sortie.

La structure, elle, a été gardée telle quelle : elle était juste.
"""
from __future__ import annotations

import io
import os
import re
import subprocess
import sys

# Le separateur d'un tableau Markdown, reconnu a sa FORME et non a un prefixe
# devine : ce depot ecrit « |---|---| » sans espace, et un test sur « | --- »
# rendait zero sujet -- silencieusement, ce qui est la pire facon d'echouer
# pour un outil dont le role est justement de dire ce qui reste ouvert.
SEPARATEUR = re.compile(r"^\s*\|[\s|:-]+\|\s*$")

# Le PARENT de « scripts », et non « scripts ». Voir le docstring : c'est la
# faute la plus reproduite de ce dépôt, et elle ne fait jamais echouer un
# appel — elle le fait viser à côté, en silence.
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def executer(cmd: list, delai: int = 20) -> tuple:
    """
    Rend (succès, sortie). Ne lève jamais : un hook qui plante bloque tout.

    Le code de retour est REGARDÉ. Le premier jet rendait toujours succès,
    si bien qu'une commande en échec passait pour une sortie vide — donc
    pour « il n'y a rien », alors qu'elle disait « je n'ai pas pu ».
    """
    try:
        r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True,
                           timeout=delai, encoding="utf-8", errors="replace")
        return r.returncode == 0, (r.stdout or "").strip()
    except Exception as exc:
        return False, str(exc).splitlines()[0][:80]


def titre(t: str) -> None:
    print("")
    print("=== %s ===" % t)


def bloc_objectif() -> None:
    titre("OBJECTIF PERMANENT — il ne se redemande pas")
    print("  Traquer toutes les ameliorations possibles. Ne rien produire,")
    print("  tout deleguer au banc gratuit. L'orchestrateur arbitre et verifie.")
    print("  Le contrat complet : .claude/CLAUDE.md, section 0.")


def bloc_git() -> None:
    titre("OU EN EST LE DEPOT — relu maintenant, jamais memorise")
    ok, sortie = executer(["git", "log", "--oneline", "-5"])
    if not ok:
        print("  [!] git log illisible : %s" % sortie)
    else:
        for ligne in sortie.splitlines():
            print("  %s" % ligne)

    ok, sortie = executer(["git", "status", "--porcelain"])
    if not ok:
        print("  [!] git status illisible : %s" % sortie)
    elif sortie:
        n = len([l for l in sortie.splitlines() if l.strip()])
        print("  ARBRE SALE : %d fichier(s) non commite(s). La vitrine" % n)
        print("  refusera de publier tant que ce n'est pas commite.")
    else:
        print("  Arbre propre.")

    ok, sortie = executer(["git", "rev-list", "--count", "@{u}..HEAD"])
    if ok and sortie.isdigit() and int(sortie):
        print("  %s commit(s) non pousse(s) vers origin." % sortie)


def bloc_taches() -> None:
    """
    Ce qui tourne sans session — la distinction qui compte au réveil.

    Les tâches planifiées survivent au redémarrage ; la boucle de session
    non. Confondre les deux, c'est croire armé ce qui ne l'est plus.
    """
    titre("CE QUI TOURNE SANS SESSION")
    taches = (
        ("NexusTraque", "traque des defauts + cockpit, PT10M",
         "Register-NexusTraque.ps1"),
        ("NexusVitrine", "publication si sain, PT6H",
         "Register-NexusVitrine.ps1"),
        ("NexusDemarrage", "pile au logon", "Register-NexusDemarrage.ps1"),
    )
    for nom, role, script in taches:
        ok, sortie = executer(
            ["powershell", "-NoProfile", "-Command",
             "(Get-ScheduledTask -TaskName '%s' -ErrorAction SilentlyContinue)"
             ".State" % nom], 25)
        if not ok:
            print("  [ ?      ] %-15s etat illisible" % nom)
            continue
        etat = sortie.strip()
        if etat:
            print("  [%-8s] %-15s %s" % (etat, nom, role))
        else:
            print("  [ABSENTE ] %-15s %s" % (nom, role))
            print("             -> .\\scripts\\%s" % script)


def bloc_sujets() -> None:
    """Sujets encore ouverts, EXTRAITS du cockpit — jamais recopiés ici."""
    titre("SUJETS OUVERTS — extraits du cockpit, non recopies")
    chemin = os.path.join(ROOT, "rituels", "CHECKLIST_COCKPIT.MD")
    if not os.path.isfile(chemin):
        print("  [!] cockpit introuvable : %s" % chemin)
        return
    try:
        with io.open(chemin, encoding="utf-8", errors="replace") as fh:
            lignes = fh.read().splitlines()
    except OSError as exc:
        print("  [!] cockpit illisible : %s" % str(exc)[:60])
        return
    dedans, montres, corps = False, 0, False
    for ligne in lignes:
        if ligne.startswith("### "):
            dedans = ("ouvert" in ligne.lower() or "jamais" in ligne.lower())
            corps = False
            if dedans:
                print("  %s" % ligne[4:])
            continue
        # La ligne « | --- » separe l'en-tete du corps. Avant elle, la
        # premiere cellule est un intitule de colonne (« Sujet », « Regle »),
        # pas un sujet ouvert -- l'afficher etait du bruit qui ressemblait a
        # de l'information.
        if dedans and SEPARATEUR.match(ligne):
            corps = True
            continue
        if dedans and corps and ligne.startswith("|"):
            cellule = ligne.split("|")[1].strip()
            if cellule and not cellule.startswith("**") and montres < 12:
                print("     - %s" % cellule[:96])
                montres += 1
    if not montres:
        print("  Aucun sujet ouvert lisible — verifier le cockpit a la main.")
    print("")
    print("  Un sujet ne se clot que lorsqu'un CONTROLE echoue si la regle est")
    print("  enfreinte. Un paragraphe ne ferme rien (contrat 0.2.1).")


def bloc_gestes() -> None:
    titre("LES GESTES, ET CE QU'ILS COUTENT")
    print("  python scripts/nexus_conformite.py     peut-on demarrer ? (~1 min)")
    print("  python scripts/nexus_rituel.py         le tour est-il clos ?")
    print("  python scripts/nexus_vitrine.py --simulation   publierait-on ?")
    print("  python scripts/nexus_valide.py --base HEAD~1   LOI 1, cout zero")
    print("  python scripts/nexus_test.py --only isolation  regle 0.4 tenue ?")
    print("")
    print("  DELEGUER plutot que produire :")
    print("    mcp__nexus-local__nexus_ask / nexus_summarize / nexus_search")
    print("    python scripts/nexus_agent.py --tache \"...\" --fichiers f.py \\")
    print("        --modele gpt-oss-120b-cloud --max-tokens 2000")


def bloc_boucle() -> None:
    """
    Ce que le redémarrage a effacé, et que rien ne restaurera tout seul.

    `ScheduleWakeup` vit dans la session. Les tâches planifiées survivent, la
    boucle non — et une boucle qu'on croit armée sans qu'elle le soit est
    pire qu'une boucle absente.
    """
    titre("A REARMER A LA MAIN — le redemarrage l'a effacee")
    print("  La boucle de session (ScheduleWakeup, 5 min) NE survit pas a un")
    print("  redemarrage : elle vit dans la session, pas sur le disque.")
    print("  NexusTraque, elle, a continue de tourner sans personne.")
    print("  -> relancer /loop, ou rearmer ScheduleWakeup au premier tour.")


def main() -> int:
    # La sortie de ce hook est injectee dans le contexte d'une session : la
    # fidelite y est le sujet. Sans cette ligne, tout caractere hors cp1252
    # devient « ? » des que stdout est redirige -- ce qui est precisement le
    # cas quand un hook est capture.
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    print("#" * 72)
    print("#  CLAUDE-LOCAL-NEXUS — REPRISE DE SESSION (hook SessionStart)")
    print("#  Tout ci-dessous est RELU maintenant, jamais memorise.")
    print("#" * 72)
    for bloc in (bloc_objectif, bloc_git, bloc_taches, bloc_sujets,
                 bloc_gestes, bloc_boucle):
        try:
            bloc()
        except Exception as exc:
            # Un bloc qui tombe ne doit pas emporter les autres : une reprise
            # partielle vaut mieux que pas de reprise du tout.
            print("")
            print("  [!] bloc « %s » indisponible : %s"
                  % (bloc.__name__, str(exc).splitlines()[0][:60]))
    print("")
    print("#" * 72)
    return 0


if __name__ == "__main__":
    sys.exit(main())
