#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Qui appelle réellement chaque script ? Et le nombre d'orphelins baisse-t-il ?

« Tout mécaniser, ne rien oublier dans les câblages » est inscrit au contrat
(§0.2.1) avec une checklist de six maillons — et rien ne vérifiait qu'un
mécanisme neuf les avait tous. Le sujet était ouvert au cockpit. Ceci le
ferme, pour le maillon le plus souvent oublié : *l'appelant*.

CLIQUET PAR NOM, JAMAIS PAR COMPTE
----------------------------------
Un cliquet par comptage laisserait câbler un script pendant qu'un autre
devient orphelin dans le même lot : la somme ne bouge pas, l'échange est
invisible, et le chiffre a l'air stable pendant que l'état se dégrade. La
référence garde donc les NOMS.

QUATRE CATÉGORIES, ET LA TROISIÈME EST TOUT L'INTÉRÊT
-----------------------------------------------------
`cable`        nommé par un hook, une tâche planifiée ou l'entrée unique.
`appele`       nommé par un autre script — il sert, en second rang.
`preuve_seule` nommé SEULEMENT par un test ou de la documentation.
               **Prouvé, et connecté à rien.**
`orphelin`     personne ne le nomme.

« Prouvé » et « utilisé » sont deux faits différents, et tout décompte de
« scripts livrés » les confond. C'est ce que ce fichier cesse de confondre.

Mesuré ici le 2026-08-30 par cet outil : 14 câblés, 29 appelés,
5 prouvés-seuls, 1 orphelin. Parmi les prouvés-seuls, `nexus_posterior.py`,
écrit le matin même pour l'AIC, et `nexus_worktree.py` — prescrit par le
contrat §0.4, cité uniquement dans de la documentation. Ces chiffres sont
ceux que rend le script ; une première estimation faite à la main en donnait
d'autres, et c'est celle de l'outil qui fait foi.

IL N'EXIGE PAS ZÉRO. Il ne le peut pas : une règle que tout le monde
enfreint le premier jour est une règle qu'on apprend à contourner. Il
garantit que la liste ne s'allonge pas.

Squelette produit par le banc gratuit, intégré après arbitrage de trois
défauts bloquants :

* `--rebaseline` était déclaré dans l'analyseur d'arguments et **jamais
  traité** — l'option existait, elle ne faisait rien ;
* la comparaison portait sur le nom SANS extension, si bien que
  `nexus_test` aurait reconnu `nexus_test_outillage.py` ;
* le docstring justifiait le « par nom » en parlant de comptes
  d'utilisateurs : le modèle a lu « compte » comme *account* au lieu de
  *comptage*, et a retourné la raison d'être du mécanisme.

    python scripts/nexus_cablage.py              # porte : echec si regression
    python scripts/nexus_cablage.py --rapport    # le tableau complet
    python scripts/nexus_cablage.py --rebaseline # figer l'etat courant
"""
from __future__ import annotations

import argparse
import fnmatch
import io
import json
import os
import subprocess
import sys
from datetime import datetime, timezone

PLAFOND = 2 * 1024 * 1024
LISIBLES = (".py", ".ps1", ".json", ".md", ".yaml", ".yml", ".js")

# Ce qui CÂBLE : un hook, une tâche planifiée, l'entrée unique. Un script
# nommé là est appelé sans que personne ait à y penser — c'est la définition
# retenue par le contrat, et la seule qui compte.
CABLEURS = (".claude/settings.json", "scripts/nexus.ps1",
            "scripts/Register-*.ps1")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# VERSIONNEE, et non sous « .nexus ». La distinction n'est pas cosmetique :
# .nexus est gitignore parce qu'il mesure CETTE machine -- latences, epreuves,
# profil materiel -- et qu'y committer ces relevés imposerait les verdicts
# d'un hote a tous les autres. Le cablage, lui, est une propriete du DEPOT :
# identique partout, et sans interet s'il ne voyage pas avec lui. Pose sous
# .nexus, la reference aurait ete absente sur toute autre machine, et la porte
# y aurait annonce « aucune reference » a chaque execution -- silencieusement
# inutile.
REFERENCE = os.path.join(ROOT, "rituels", "cablage_reference.json")


def suivis() -> list:
    """Fichiers suivis par git. Sort en 2 si git ne répond pas : sans lui, le
    verdict porterait sur un périmètre inconnu, ce qui est pire que rien."""
    try:
        r = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True,
                           text=True, timeout=60, encoding="utf-8",
                           errors="replace")
    except Exception as exc:
        sys.stderr.write("git ls-files injoignable : %s\n" % exc)
        raise SystemExit(2)
    if r.returncode != 0:
        sys.stderr.write("git ls-files a rendu %d\n" % r.returncode)
        raise SystemExit(2)
    return [l.strip() for l in r.stdout.splitlines() if l.strip()]


def contenus(fichiers: list) -> dict:
    textes = {}
    for rel in fichiers:
        if not rel.lower().endswith(LISIBLES):
            continue
        chemin = os.path.join(ROOT, rel)
        try:
            if os.path.getsize(chemin) > PLAFOND:
                continue
            with io.open(chemin, encoding="utf-8", errors="replace") as fh:
                textes[rel] = fh.read()
        except OSError:
            # Supprimé entre le ls-files et la lecture : ce n'est pas une
            # panne, c'est une course, et elle ne mérite pas d'arrêter.
            continue
    return textes


def est_cableur(rel: str) -> bool:
    return any(fnmatch.fnmatch(rel, motif) for motif in CABLEURS)


def invoque(nom: str, texte: str) -> bool:
    """
    Le script est-il nomme AILLEURS que dans un commentaire pur ?

    Critere volontairement large, et la mesure explique pourquoi. Un premier
    essai exigeait une marque d'invocation explicite -- « subprocess »,
    « sys.executable », « Start-Process »... Resultat mesure : les appels
    passaient de 29 a 11 et les prouves-seuls de 4 a 22. Dix-huit faux
    negatifs, parce qu'un appel reel s'ecrit souvent sans aucune de ces
    marques sur la meme ligne :

        str(dossier_scripts() / "nexus_patch.py"),

    Un faux positif fait croire un script cable a tort ; dix-huit faux
    negatifs font crier le controle sans raison, et un garde-fou qui crie
    toujours n'avertit jamais. On garde donc la seule regle qui ne se trompe
    pas : une ligne ENTIEREMENT commentee ne peut rien invoquer.

    LIMITE ASSUMEE, ecrite plutot que tue : une mention en docstring compte
    encore comme un appel. Constate sur ce mecanisme lui-meme -- en ecrivant
    « dont nexus_posterior.py » dans un commentaire de la conformite, j'ai
    fait passer ce script d'orphelin a appele alors que rien n'avait change
    pour lui. Le controle mesure donc « nomme dans du code », pas « execute ».
    """
    for ligne in texte.splitlines():
        if nom not in ligne:
            continue
        nue = ligne.strip()
        if nue.startswith("#") or nue.startswith("//") or nue.startswith("*"):
            continue
        return True
    return False


def classer(cible: str, textes: dict) -> tuple:
    """
    Catégorie d'un script, et les deux premiers fichiers qui le nomment.

    Le nom est comparé AVEC son extension. Sans elle, « nexus_test »
    reconnaîtrait « nexus_test_outillage.py » et le classerait câblé à tort —
    un contrôle qui se trompe en faveur du silence ne sert à rien.
    """
    nom = os.path.basename(cible)
    citants = [rel for rel, t in textes.items() if rel != cible and nom in t]
    if not citants:
        return "orphelin", []
    cables = [r for r in citants if est_cableur(r)]
    if cables:
        return "cable", cables[:2]
    scripts = [r for r in citants
               if r.lower().endswith((".py", ".ps1"))
               and "test" not in r.lower()
               and invoque(nom, textes[r])]
    if scripts:
        return "appele", scripts[:2]
    return "preuve_seule", citants[:2]


def etat() -> dict:
    fichiers = suivis()
    textes = contenus(fichiers)
    cibles = [f for f in fichiers
              if f.startswith("scripts/") and f.lower().endswith((".py", ".ps1"))]
    resultat = {"cable": [], "appele": [], "preuve_seule": [], "orphelin": []}
    details = {}
    for cible in sorted(cibles):
        categorie, citants = classer(cible, textes)
        resultat[categorie].append(cible)
        details[cible] = citants
    return {"categories": resultat, "citants": details}


def lire_reference() -> dict:
    if not os.path.isfile(REFERENCE):
        return {}
    try:
        with io.open(REFERENCE, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        # Une référence illisible n'est pas une référence vide : la traiter
        # comme telle ferait passer toute regression pour un progres.
        sys.stderr.write("reference illisible : %s\n" % REFERENCE)
        raise SystemExit(2)


def ecrire_reference(categories: dict) -> None:
    os.makedirs(os.path.dirname(REFERENCE), exist_ok=True)
    # Seules les deux categories FAIBLES sont figees : les autres n'ont pas
    # besoin de reference, puisqu'on ne surveille qu'une degradation.
    document = {
        "mesure_le": datetime.now(timezone.utc).isoformat(),
        "categories": {
            "orphelin": sorted(categories["orphelin"]),
            "preuve_seule": sorted(categories["preuve_seule"]),
        },
    }
    with io.open(REFERENCE, "w", encoding="utf-8") as fh:
        fh.write(json.dumps(document, ensure_ascii=False, indent=2) + "\n")


def main() -> int:
    # La console Windows est en cp1252 : sans cela, tout tiret cadratin ou
    # accent devient « ? » des que la sortie est redirigee -- et elle l'est,
    # puisque ce script est appele par la conformite.
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--rapport", action="store_true")
    p.add_argument("--rebaseline", action="store_true")
    p.add_argument("--json", action="store_true")
    a = p.parse_args()

    courant = etat()
    categories = courant["categories"]

    if a.rebaseline:
        ecrire_reference(categories)
        print("Reference ecrite : %d orphelin(s), %d preuve(s) seule(s)."
              % (len(categories["orphelin"]), len(categories["preuve_seule"])))
        return 0

    if a.json:
        print(json.dumps(courant, ensure_ascii=False, indent=2))
        return 0

    if a.rapport:
        print("Cablage des scripts — %s" % ROOT)
        print("-" * 72)
        for nom in ("cable", "appele", "preuve_seule", "orphelin"):
            print("  %-14s %d" % (nom, len(categories[nom])))
        for nom in ("preuve_seule", "orphelin"):
            if not categories[nom]:
                continue
            print("")
            print("  %s :" % nom.upper())
            for cible in categories[nom]:
                cites = courant["citants"].get(cible) or []
                print("    %-34s %s" % (os.path.basename(cible),
                                        ", ".join(cites) if cites else "personne"))
        print("-" * 72)
        return 0

    reference = lire_reference()
    if not reference:
        print("Aucune reference : rien a comparer. Etat courant —")
        print("  %d cable(s), %d appele(s), %d preuve(s) seule(s), %d orphelin(s)"
              % tuple(len(categories[n]) for n in
                      ("cable", "appele", "preuve_seule", "orphelin")))
        print("  Figer cet etat : python scripts/nexus_cablage.py --rebaseline")
        # Pas d'echec : une premiere execution ne peut pas constater de
        # regression, et echouer ici apprendrait a contourner l'outil.
        return 0

    connus = reference.get("categories", {})
    regressions = []
    for nom in ("orphelin", "preuve_seule"):
        avant = set(connus.get(nom) or [])
        for cible in categories[nom]:
            if cible not in avant:
                regressions.append((nom, cible))

    if not regressions:
        gagnes = (len(connus.get("orphelin") or []) - len(categories["orphelin"])
                  + len(connus.get("preuve_seule") or [])
                  - len(categories["preuve_seule"]))
        print("Cablage : aucune regression.%s"
              % ("" if gagnes <= 0 else " %d script(s) mieux cable(s) qu'avant."
                 % gagnes))
        return 0

    # NOMMEMENT, jamais un compte : « 3 regressions » n'apprend rien a qui
    # doit les corriger.
    print("Cablage : %d REGRESSION(S)." % len(regressions))
    for nom, cible in regressions:
        cites = courant["citants"].get(cible) or []
        print("  %-14s %s%s" % (nom, cible,
                                ("  <- %s" % ", ".join(cites)) if cites else ""))
    print("")
    print("Un script devenu orphelin ou seulement prouve n'est appele par")
    print("personne : le cabler, ou le retirer. Si la degradation est voulue,")
    print("l'assumer explicitement par --rebaseline.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
