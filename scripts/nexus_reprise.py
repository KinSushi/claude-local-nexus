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

# Intitules de colonne du cockpit. Un en-tete qui echappe au separateur --
# second en-tete dans un meme tableau, mise en forme irreguliere -- serait
# sinon annonce comme un sujet ouvert, du bruit qui ressemble a une
# information.
# Un numero de ligne ou de section : « 3 », « 1.1 », « 2.3.4 ». isdigit()
# seul laissait passer les decimaux, et « 1.1 » etait annonce comme sujet.
NUMERO = re.compile(r"^[0-9]+([.][0-9]+)*[.]?$")

INTITULES = {"#", "sujet", "statut", "detail", "détail", "preuve", "regle",
             "règle", "mecanisme", "mécanisme", "etat", "état", "lien",
             "ou elle est ecrite", "où elle est écrite"}

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
    print("")
    print("  CE PROJET EST PRIORITAIRE sur les mecanismes des autres depots :")
    print("  il en est la source, non le suiveur, et les plus-values")
    print("  construites ici redescendent vers eux. S'en inspirer n'est pas")
    print("  interdit, au contraire -- mais on emprunte une idee, on ne s'y")
    print("  subordonne pas.")
    print("")
    print("  MISSION PERMANENTE, jamais achevee : traquer la MOINDRE")
    print("  amelioration possible. Repondre a la demande n'est pas une fin,")
    print("  c'est un element d'une file qui n'est jamais vide.")
    print("  L'environnement est vaste et sous-employe : 71 modeles mesures,")
    print("  deux bancs, douze outils voisins reperes, plus de 33 000")
    print("  fichiers de documentation et de bibliotheques a portee de copie.")
    print("  Voir « CE DONT JE DISPOSE » dans rituels/CHECKLIST_COCKPIT.MD.")


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
    # Les noms sont ceux que Windows porte REELLEMENT, releves par
    # Get-ScheduledTask. « NexusDemarrage » etait une supposition : la tache
    # existante s'appelle « Claude-Local-Nexus - Demarrage », si bien que la
    # reprise l'annoncait ABSENTE alors qu'elle etait armee -- et invitait a
    # la reenregistrer pour rien. Un tableau de bord qui se trompe sur ce qui
    # tourne est pire qu'un tableau de bord vide.
    taches = (
        ("NexusTraque", "traque des defauts + cockpit, PT10M",
         "Register-NexusTraque.ps1"),
        ("NexusVitrine", "publication si sain, PT6H",
         "Register-NexusVitrine.ps1"),
        ("Claude-Local-Nexus - Demarrage", "pile au logon",
         "Register-NexusDemarrage.ps1"),
        ("Claude-Local-Nexus - Mise a jour", "modeles, quotidien",
         "Register-NexusAutoUpdate.ps1"),
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
    dedans, montres, corps, non_affiches = False, 0, False, 0
    for ligne in lignes:
        if ligne.startswith("### "):
            # « jamais » seul captait « CE DONT JE DISPOSE — inventaire mesure le
            # 30/08, jamais suppose », qui n'est pas une liste de sujets
            # ouverts mais un inventaire de ressources. Le critere doit viser
            # ce qui reste A FAIRE, pas tout titre contenant le mot.
            dedans = ("ouvert" in ligne.lower()
                      or "jamais faites" in ligne.lower()
                      or "jamais traitees" in ligne.lower()
                      or "jamais traitées" in ligne.lower())
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
            # Certains tableaux du cockpit ont une premiere colonne « # »
            # qui ne porte qu'un NUMERO de ligne. La prendre pour le sujet
            # affichait « 1 », « 2 », « # » -- du bruit qui ressemblait a de
            # l'information, ce qui est pire que pas d'information du tout.
            # On retient donc la premiere cellule qui dit vraiment quelque
            # chose, au lieu de compter sur une position.
            cellules = [c.strip() for c in ligne.split("|")[1:-1]]
            cellule = ""
            for c in cellules:
                # Ni un numero de ligne, ni un intitule de colonne. Le
                # premier essai filtrait sur la LONGUEUR (>= 4), ce qui
                # sautait « AST » et retenait le statut a sa place : un
                # critere de forme la ou il fallait un critere de sens.
                if c and not NUMERO.match(c) and c.lower() not in INTITULES:
                    cellule = c
                    break
            # Le gras est RETIRE, non exclu : le filtre precedent sautait
            # les cellules commencant par « ** », c'est-a-dire justement les
            # sujets qu'on avait pris la peine de mettre en avant.
            cellule = cellule.replace("**", "")
            if cellule and montres < 18:
                print("     - %s" % cellule[:96])
                montres += 1
            elif cellule:
                non_affiches += 1
    if not montres:
        print("  Aucun sujet ouvert lisible — verifier le cockpit a la main.")
    elif non_affiches > 0:
        print("  %d sujet(s) non affiché(s) — voir rituels/CHECKLIST_COCKPIT.MD. La SECTION 62, intitulée REPRISE APRES REDEMARRAGE, porte l'état en vol et se lit en premier." % non_affiches)
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
    print("  NE JAMAIS ECRIRE CONTRE UNE BIBLIOTHEQUE DE MEMOIRE :")
    print("    python scripts/nexus_doc.py <symbole>   # ex. subprocess.run,")
    print("                                            #    New-Item, trap")
    # LE NOMBRE SE DERIVE. Il etait ecrit en dur, donc juste un seul jour :
    # l'absorption des corpus shell et des lecons y a ajoute 673 entrees sans
    # qu'une ligne bouge. Un hook de demarrage ne doit rien faire de long --
    # ici, un parcours d'index, aucun corpus ouvert.
    try:
        # `Path` n'est pas importe dans ce fichier, et `scripts/` n'est pas sur
        # sys.path quand la reprise est lancee par le hook. Le premier jet
        # supposait les deux : le repli s'est declenche et a TU la cause, ce
        # qui est precisement le defaut que ce depot traque en classe 1.
        from pathlib import Path as _Path
        _ici = _Path(__file__).resolve().parent
        if str(_ici) not in sys.path:
            sys.path.insert(0, str(_ici))
        import nexus_doc as _doc
        _p, _a = _doc.compter_symboles(_ici.parent)
        print("    %d symboles Python + %d annexes (PowerShell, bash, lecons),"
              % (_p, _a))
        print("    ancres sur les versions INSTALLEES ici.")
    except Exception:
        # Un compteur en panne ne doit pas priver la reprise du reste : la
        # regle vaut meme sans son chiffre.
        print("    doc Python, PowerShell, bash et lecons, ancrees ici.")
    print("    ~280 jetons par consultation : l'index lit l'entree par seek,")
    print("    jamais le fichier. Moins cher que relire trois lignes de code.")
    print()
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
