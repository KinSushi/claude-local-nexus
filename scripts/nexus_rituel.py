#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Rituel de fin de tour, exécuté plutôt que lu.

Ce script existe parce qu'une liste qu'on doit *penser* à suivre ne protège
personne — c'est la règle inscrite en tête du cockpit, et elle a été
enfreinte ici même, le jour où elle a été écrite. Un rituel déclaratif est
un rituel oublié.

Il constate et rapporte ; il ne corrige rien. Un MANQUE n'est pas une
erreur du script : c'est son résultat.

    python scripts/nexus_rituel.py
    python scripts/nexus_rituel.py --json

Écrit par le banc gratuit sur consigne, intégré après correction d'un
défaut : il traitait `par_plan` comme un dictionnaire de listes, alors que
`nexus_savings --json` rend un dictionnaire de dictionnaires. Le contrôle
de délégation aurait donc rendu MANQUE en toute circonstance — un garde-fou
qui crie toujours n'avertit jamais.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

OK, MANQUE, IGNORE = "OK", "MANQUE", "IGNORE"


def racine_git() -> Path:
    """Racine découverte, jamais déclarée — la faute que ce dépôt combat."""
    r = subprocess.run(["git", "rev-parse", "--show-toplevel"],
                       capture_output=True, text=True, timeout=30)
    if r.returncode != 0 or not r.stdout.strip():
        raise RuntimeError("hors d'un depot git")
    return Path(r.stdout.strip())


def travail_commite(racine: Path) -> tuple[str, str]:
    """Rien ne doit rester non commité : un travail non commité est perdu."""
    try:
        r = subprocess.run(["git", "status", "--porcelain"], cwd=racine,
                           capture_output=True, text=True, timeout=60)
        if r.returncode != 0:
            raise RuntimeError("git status a echoue")
        lignes = [l for l in r.stdout.splitlines() if l.strip()]
        if not lignes:
            return OK, "arbre propre"
        noms = ", ".join(l[3:].strip() for l in lignes[:5])
        suite = " (+%d)" % (len(lignes) - 5) if len(lignes) > 5 else ""
        return MANQUE, "%s%s" % (noms, suite)
    except Exception as exc:
        return IGNORE, str(exc).splitlines()[0][:60]


def cockpit_frais(racine: Path) -> tuple[str, str]:
    """
    Le cockpit doit être postérieur au dernier changement de code.

    Rouvert le 2026-08-30 après vingt-et-une heures, il annonçait 44 modèles
    et une configuration INVALIDE là où il y en avait 67 et une saine. Un
    tableau de bord périmé décrit un état qui n'existe plus, avec l'autorité
    d'un fichier écrit.

    Corrigé le même jour : comparer le *mtime du fichier* à la *date du
    commit* mêle deux horloges, et rendait le contrôle insatisfiable dans le
    tour qu'il prescrit lui-même. Le rituel demande d'écrire le cockpit puis
    de commiter ; quand cockpit et code partent dans le même commit, le
    fichier est forcément antérieur à ce commit. Mesuré : commit du code
    17:27:47, commit du cockpit 17:27:47 — le même — et mtime 17:26:37, donc
    MANQUE sur un cockpit parfaitement à jour.

    D'où deux critères, dont un seul suffit : le fichier plus récent que le
    dernier commit de code (édition pas encore commitée), ou le commit du
    cockpit au moins aussi récent que celui du code (les deux partis
    ensemble).
    """
    try:
        fichier = racine / "rituels" / "CHECKLIST_COCKPIT.MD"
        if not fichier.is_file():
            return IGNORE, "pas de cockpit dans ce depot"
        r = subprocess.run(["git", "log", "-1", "--format=%ct", "--",
                            "scripts/", "tools/"], cwd=racine,
                           capture_output=True, text=True, timeout=60)
        if r.returncode != 0 or not r.stdout.strip():
            return OK, "aucun changement de code a suivre"
        dernier = int(r.stdout.strip())

        # Critère 1 — le cockpit a été retouché depuis, sans être commité.
        if fichier.stat().st_mtime > dernier:
            return OK, "posterieur au dernier changement de code"

        # Critère 2 — cockpit et code sont partis dans le même commit, ou le
        # cockpit dans un commit plus récent. Ici les deux dates viennent de
        # la MEME horloge, celle de git, et sont donc comparables.
        rc = subprocess.run(["git", "log", "-1", "--format=%ct", "--",
                             "rituels/CHECKLIST_COCKPIT.MD"], cwd=racine,
                            capture_output=True, text=True, timeout=60)
        if rc.returncode == 0 and rc.stdout.strip():
            if int(rc.stdout.strip()) >= dernier:
                return OK, "commite avec le code, ou apres lui"

        return MANQUE, "plus ancien que le dernier changement de code"
    except Exception as exc:
        return IGNORE, str(exc).splitlines()[0][:60]


def boucle_armee() -> tuple[str, str]:
    """
    Non vérifiable ici, et le dire vaut mieux que le supposer.

    ScheduleWakeup vit dans la session, pas sur le disque. Un script ne peut
    pas savoir si la boucle est armée — prétendre le contrôler donnerait une
    fausse garantie, ce qui est pire qu'aucune.
    """
    return IGNORE, "verifiable seulement par la session"


def part_deleguee(racine: Path) -> tuple[str, str]:
    """
    Du volume a-t-il été confié au banc aujourd'hui ?

    Zéro requête signifie que le tour a produit lui-même ce que la
    plateforme existe pour déléguer.
    """
    try:
        r = subprocess.run([sys.executable, "scripts/nexus_savings.py",
                            "--jours", "1", "--json"], cwd=racine,
                           capture_output=True, text=True, timeout=120,
                           encoding="utf-8", errors="replace")
        if r.returncode != 0:
            raise RuntimeError("nexus_savings a rendu %s" % r.returncode)
        par_plan = json.loads(r.stdout).get("par_plan") or {}
        # par_plan est un dict de DICTS -- {"local": {"requetes": N, ...}} --
        # et non de listes. Le tester comme une liste rendait MANQUE en
        # toute circonstance.
        total = sum((par_plan.get(p) or {}).get("requetes", 0)
                    for p in ("local", "cloud"))
        if total:
            return OK, "%d requete(s) deleguees aujourd'hui" % total
        return MANQUE, "aucune requete deleguee aujourd'hui"
    except subprocess.TimeoutExpired:
        return IGNORE, "nexus_savings n'a pas repondu en 120 s"
    except Exception as exc:
        return IGNORE, str(exc).splitlines()[0][:60]


def releves_lisibles(racine: Path) -> tuple[str, str]:
    """
    Les relevés doivent porter la clef que leurs lecteurs cherchent.

    Défaut réel du 2026-08-30 : l'écriture posait les mesures à la racine du
    document quand la lecture les cherchait sous « modeles ». La régénération
    suivante aurait sorti 58 modèles de tous les pools, sans un mot.
    """
    try:
        chemin = racine / ".nexus" / "latences.json"
        if not chemin.is_file():
            return IGNORE, "jamais mesure sur cette machine"
        modeles = json.loads(chemin.read_text(encoding="utf-8")).get("modeles")
        if isinstance(modeles, dict) and modeles:
            return OK, "%d modele(s) lisibles" % len(modeles)
        return MANQUE, "clef « modeles » absente ou vide"
    except Exception as exc:
        return MANQUE, "releve illisible : %s" % str(exc).splitlines()[0][:40]


def arbres_en_attente(racine: Path) -> tuple[str, str]:
    """
    Des arbres de travail isolés ont-ils été laissés en plan ?

    Un arbre oublié contient le travail d'un worker que personne n'a retenu
    ni jeté : il vieillit, diverge, et finit fusionné ou détruit au hasard.
    La récolte doit donc être réclamée à la fin du tour, pas espérée.

    ELLE N'EST PAS RÉÉCRITE ICI. `nexus_worktree.py --lister` sait déjà
    découvrir les arbres ; cette fonction l'APPELLE. Réimplémenter la
    découverte aurait créé deux sources de vérité qui divergeraient au
    premier changement — c'est la règle de non-concurrence du contrat, et
    elle vaut autant entre nos propres outils qu'avec les automatismes.

    Écrit par le banc (gpt-oss-120b-cloud, 1687 jetons, coût nul), intégré
    sans correction.
    """
    cmd = [sys.executable, "scripts/nexus_worktree.py", "--lister"]
    try:
        result = subprocess.run(
            cmd, cwd=str(racine), capture_output=True, text=True,
            timeout=120, encoding="utf-8", errors="replace",
        )
        if result.returncode != 0:
            sortie = result.stderr.splitlines() or result.stdout.splitlines()
            return (IGNORE, (sortie[0] if sortie else "")[:60])

        # Ne comptent QUE les arbres d'agent, reconnus a leur branche.
        #
        # Defaut trouve a l'usage, et non a la relecture : « git worktree
        # list » commence par l'arbre PRINCIPAL, sur « [main] ». Compte
        # naivement, le rituel annoncait deux arbres pour un seul, et
        # reclamait de « fusionner ou jeter » le depot lui-meme -- une
        # consigne fausse, et dangereuse si quelqu'un l'appliquait.
        #
        # Le critere vient de creer_arbre(), qui nomme toujours la branche
        # « agent/<tache> ». On lit donc la convention plutot qu'une
        # position dans la liste, qui changerait au premier tri.
        compteur = 0
        for ligne in result.stdout.splitlines():
            texte = ligne.strip()
            if not texte:
                continue
            if texte.startswith(("-", "=", "#")):
                continue
            if "aucun" in texte.lower():
                continue
            if "[agent/" not in texte:
                continue
            compteur += 1

        if compteur == 0:
            return (OK, "aucun arbre en attente")
        return (MANQUE,
                "%d arbre(s) en attente : fusionner ou jeter "
                "(nexus_worktree.py --fusionner|--jeter)" % compteur)

    except subprocess.TimeoutExpired:
        return (IGNORE, "nexus_worktree n'a pas repondu en 120 s")
    except Exception as exc:
        msg = str(exc).encode("ascii", "ignore").decode()
        return (IGNORE, msg[:60])


def cablage_tenu(racine: Path) -> tuple[str, str]:
    """
    Ce qui a ete livre ce tour est-il CABLE, ou seulement ecrit ?

    Sixieme geste, et le plus oublie : un mecanisme sans appelant n'est pas
    un mecanisme, c'est un fichier. Le contrat (0.2.1) enumere six maillons
    -- script, preuve, appelant, barriere, documentation, regression -- et
    l'appelant est celui qui manque le plus souvent, parce que rien ne le
    reclame au moment ou l'on croit avoir fini.

    Le cliquet de nexus_cablage.py refuse que la liste des orphelins et des
    prouves-seuls s'allonge. Le rituel ne le RAPPELLE pas : il le LANCE.
    """
    try:
        r = subprocess.run([sys.executable, "scripts/nexus_cablage.py"],
                           cwd=racine, capture_output=True, text=True,
                           timeout=180, encoding="utf-8", errors="replace")
        lignes = [l for l in (r.stdout or "").splitlines() if l.strip()]
        if r.returncode == 0:
            return OK, (lignes[0] if lignes else "aucune regression")
        return MANQUE, " | ".join(lignes[:2])[:90]
    except subprocess.TimeoutExpired:
        return IGNORE, "nexus_cablage n'a pas repondu en 180 s"
    except Exception as exc:
        return IGNORE, str(exc).splitlines()[0][:60]


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--racine", type=Path, default=None)
    p.add_argument("--json", action="store_true")
    a = p.parse_args()

    try:
        racine = a.racine or racine_git()
    except Exception as exc:
        sys.stderr.write("Racine introuvable : %s\n" % exc)
        return 1

    controles = [
        ("travail commite", lambda: travail_commite(racine)),
        ("cockpit frais", lambda: cockpit_frais(racine)),
        ("boucle armee", boucle_armee),
        ("part deleguee", lambda: part_deleguee(racine)),
        ("releves lisibles", lambda: releves_lisibles(racine)),
        ("cablage tenu", lambda: cablage_tenu(racine)),
        ("arbres recoltes", lambda: arbres_en_attente(racine)),
    ]

    resultats = []
    for nom, fn in controles:
        try:
            statut, detail = fn()
        except Exception as exc:
            statut, detail = IGNORE, str(exc).splitlines()[0][:60]
        resultats.append((nom, statut, detail))

    manques = [r for r in resultats if r[1] == MANQUE]

    if a.json:
        print(json.dumps({
            "racine": str(racine),
            "controles": [{"nom": n, "statut": s, "detail": d}
                          for n, s, d in resultats],
            "verdict": MANQUE if manques else OK,
        }, ensure_ascii=False, indent=2))
        return 1 if manques else 0

    print("Rituel de fin de tour — %s" % racine)
    print("-" * 72)
    for nom, statut, detail in resultats:
        print("  [%-6s] %-18s %s" % (statut, nom, detail))
    print("-" * 72)
    if manques:
        print("VERDICT : %d manque(s). Le tour n'est pas clos." % len(manques))
    else:
        print("VERDICT : rituel tenu.")
    return 1 if manques else 0


if __name__ == "__main__":
    sys.exit(main())
