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
        if fichier.stat().st_mtime > dernier:
            return OK, "posterieur au dernier changement de code"
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
