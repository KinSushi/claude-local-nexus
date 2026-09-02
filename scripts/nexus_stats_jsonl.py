# -*- coding: utf-8 -*-
"""Croise des motifs regex avec un champ booleen, PAR GROUPE, sur un journal JSONL.

Le besoin derive d'une mesure reelle : un taux global de 76,5 % recouvrait des
groupes allant de 37,0 % a 89,2 % — 52 points d'ecart, invisibles dans la moyenne.
Un chiffre global ment par construction : il fusionne des populations heterogenes
et laisse les poids lourds ecraser les poids legers ; un groupe a 37 % peut couler
sans jamais apparaitre si ses voisins compensent. Le groupement est donc le coeur
de l'outil, pas une option de confort : on ne resume qu'apres avoir stratifie.

Deux tableaux croises sont rendus : motif x groupe, et motif x valeur du booleen,
avec effectifs ET pourcentages. Le pourcentage sans l'effectif cache la fragilite
statistique ; l'effectif sans le pourcentage cache l'ampleur relative.

Robustesse : une ligne JSON invalide est comptee puis ignoree, jamais fatale ;
un champ absent est traite comme vide ; un fichier vide rend des tableaux vides.

Codes de sortie :
0 : analyse effectuee
2 : usage invalide (motif mal forme, regex incorrecte, fichier illisible)
"""
import sys
import re
import json
import argparse
from collections import Counter, defaultdict

VIDE = "(vide)"


def iter_jsonl(chemin, compteurs):
    """Yield des dict ; les lignes invalides sont comptees, jamais fatales."""
    with open(chemin, encoding="utf-8", errors="replace") as f:
        for ligne in f:
            ligne = ligne.strip()
            if not ligne:
                continue
            compteurs["lignes"] += 1
            try:
                obj = json.loads(ligne)
            except json.JSONDecodeError:
                compteurs["invalides"] += 1
                continue
            yield obj if isinstance(obj, dict) else {}


def norm_booleen(v):
    """true/false pour un booleen JSON ; tout le reste est traite comme vide."""
    if isinstance(v, bool):
        return "true" if v else "false"
    return VIDE


def norm_cle(v):
    if v is None or v == "":
        return VIDE
    return str(v)


def table_dict(totaux, hits, noms):
    out = {}
    for cle in sorted(totaux):
        t = totaux[cle]
        out[cle] = {
            "total": t,
            "motifs": {
                n: {"n": hits[cle][n],
                    "pct": round(100.0 * hits[cle][n] / t, 1) if t else 0.0}
                for n in noms
            },
        }
    return out


def afficher_table(titre, totaux, hits, noms):
    print("\n== %s ==" % titre)
    if not totaux:
        print("(aucune donnee)")
        return
    cles = sorted(totaux)
    w0 = max([len(c) for c in cles] + [3])
    larg = [max(len(n), 14) for n in noms]
    entete = "  ".join("%-*s" % (w, n) for n, w in zip(noms, larg))
    print("%-*s %6s  %s" % (w0, "CLE", "N", entete))
    for c in cles:
        t = totaux[c]
        cellules = "  ".join(
            "%-*s" % (w, "%d (%.1f%%)" % (hits[c][n], 100.0 * hits[c][n] / t if t else 0.0))
            for n, w in zip(noms, larg)
        )
        print("%-*s %6d  %s" % (w0, c, t, cellules))


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(
        description="Croise motifs regex x booleen, par groupe, sur du JSONL.")
    parser.add_argument("fichier", help="chemin du journal JSONL")
    parser.add_argument("--champ-texte", required=True,
                        help="champ texte sur lequel appliquer les motifs")
    parser.add_argument("--champ-groupe", required=True, help="champ de groupement")
    parser.add_argument("--champ-booleen", required=True, help="champ booleen")
    parser.add_argument("--motif", action="append", required=True,
                        metavar="NOM=REGEX", help="motif nomme ; repetable")
    parser.add_argument("--json", action="store_true", help="sortie JSON")
    args = parser.parse_args()

    motifs = []
    for m in args.motif:
        if "=" not in m:
            print("Motif mal forme (attendu NOM=REGEX) : %s" % m)
            return 2
        nom, expr = m.split("=", 1)
        try:
            motifs.append((nom, re.compile(expr)))
        except re.error as e:
            print("Regex invalide pour '%s' : %s" % (nom, e))
            return 2
    noms = [n for n, _ in motifs]

    compteurs = {"lignes": 0, "invalides": 0}
    tot_groupe, tot_bool = Counter(), Counter()
    hits_groupe, hits_bool = defaultdict(Counter), defaultdict(Counter)

    try:
        for obj in iter_jsonl(args.fichier, compteurs):
            texte = str(obj.get(args.champ_texte) or "")
            g = norm_cle(obj.get(args.champ_groupe))
            b = norm_booleen(obj.get(args.champ_booleen))
            tot_groupe[g] += 1
            tot_bool[b] += 1
            for nom, rx in motifs:
                if rx.search(texte):
                    hits_groupe[g][nom] += 1
                    hits_bool[b][nom] += 1
    except OSError as e:
        print("Fichier illisible : %s" % e)
        return 2

    if args.json:
        print(json.dumps({
            "fichier": args.fichier,
            "lignes": compteurs["lignes"],
            "lignes_invalides": compteurs["invalides"],
            "motifs": noms,
            "par_groupe": table_dict(tot_groupe, hits_groupe, noms),
            "par_booleen": table_dict(tot_bool, hits_bool, noms),
        }, ensure_ascii=False, indent=2))
    else:
        print("Fichier : %s" % args.fichier)
        print("Lignes : %d (%d invalides ignorees)"
              % (compteurs["lignes"], compteurs["invalides"]))
        afficher_table("MOTIF x GROUPE (%s)" % args.champ_groupe,
                       tot_groupe, hits_groupe, noms)
        afficher_table("MOTIF x BOOLEEN (%s)" % args.champ_booleen,
                       tot_bool, hits_bool, noms)

    return 0


if __name__ == "__main__":
    sys.exit(main())
