# -*- coding: utf-8 -*-
"""Outil autonome qui décrit la structure de fichiers JSON, JSONL et CSV sans
exposer de valeurs.  Retourne 0 si tous les fichiers sont décrits, 1 si au moins
un a échoué, 2 si aucun n'a pu être décrit."""

import os, sys, json, csv, argparse, io

PROFONDEUR_MAX_DEFAUT = 4
ECHANTILLON_DEFAUT = 50
BS = chr(92)          # antislash sans littéral
NL = BS + 'n'         # newline
TAB = BS + 't'        # tabulation

def type_valeur(v):
    if v is None:
        return "nul"
    if isinstance(v, bool):
        return "booleen"
    if isinstance(v, int):
        return "entier"
    if isinstance(v, float):
        return "reel"
    if isinstance(v, str):
        return "chaine"
    if isinstance(v, list):
        return "liste"
    if isinstance(v, dict):
        return "objet"
    return "inconnu"

def squelette(v, profondeur, profondeur_max):
    t = type_valeur(v)
    if t == "objet":
        if profondeur > profondeur_max:
            return {"type":"objet","tronque":True,"nb_cles":len(v)}
        cles = {}
        for k, sous in v.items():
            cles[k] = squelette(sous, profondeur+1, profondeur_max)
        return {"type":"objet","nb_cles":len(cles),"cles":cles}
    if t == "liste":
        card = {"min":len(v),"max":len(v)}
        if profondeur > profondeur_max:
            return {"type":"liste","tronque":True,"cardinalite":card}
        elements = None
        for item in v:
            elements = fusionner(elements, squelette(item, profondeur+1, profondeur_max))
        return {"type":"liste","cardinalite":card,"elements":elements}
    return {"type":t}

def fusionner(a, b):
    if a is None:
        return b
    if b is None:
        return a
    if a["type"] != b["type"]:
        types = set()
        for n in (a, b):
            if n["type"] == "mixte":
                types.update(n["types"])
            else:
                types.add(n["type"])
        return {"type":"mixte","types":sorted(types)}
    t = a["type"]
    if t == "objet":
        if a.get("tronque") and b.get("tronque"):
            return {"type":"objet","tronque":True,"nb_cles":max(a["nb_cles"],b["nb_cles"])}
        if a.get("tronque"):
            return b
        if b.get("tronque"):
            return a
        cles = dict(a["cles"])
        for k, sk in b["cles"].items():
            cles[k] = fusionner(cles.get(k), sk)   # bug corrigé : utilisation de cles
        return {"type":"objet","nb_cles":len(cles),"cles":cles}
    if t == "liste":
        card = {"min":min(a["cardinalite"]["min"],b["cardinalite"]["min"]),
                "max":max(a["cardinalite"]["max"],b["cardinalite"]["max"])}
        if a.get("tronque") and b.get("tronque"):
            return {"type":"liste","tronque":True,"cardinalite":card}
        if a.get("tronque"):
            return b
        if b.get("tronque"):
            return a
        return {"type":"liste","cardinalite":card,
                "elements":fusionner(a.get("elements"),b.get("elements"))}
    if t == "mixte":
        return {"type":"mixte","types":sorted(set(a["types"])|set(b["types"]))}
    return a

def type_cellule(c):
    c = c.strip()
    if c == "":
        return None
    try:
        int(c)
        return "entier"
    except Exception:
        pass
    try:
        float(c)
        return "reel"
    except Exception:
        pass
    if c.lower() in ("true","false"):
        return "booleen"
    return "chaine"

def inferer_type_colonne(cellules):
    types = set()
    for c in cellules:
        t = type_cellule(c)
        if t is not None:
            types.add(t)
    if not types:
        return "vide"
    if len(types) == 1:
        return next(iter(types))
    return "mixte(" + "|".join(sorted(types)) + ")"

def analyser_json(chemin, profondeur_max):
    with open(chemin,"r",encoding="utf-8",errors="replace") as f:
        v = json.load(f)
    return {"format":"json","squelette":squelette(v,1,profondeur_max)}

def analyser_jsonl(chemin, echantillon, profondeur_max):
    sk = None
    lignes = 0
    ignorees = 0
    with open(chemin,"r",encoding="utf-8",errors="replace") as f:
        for ligne in f:
            if lignes >= echantillon:
                break
            texte = ligne.strip()
            if not texte:
                continue
            try:
                v = json.loads(texte)
            except Exception:
                ignorees += 1
                continue
            sk = fusionner(sk, squelette(v,1,profondeur_max))
            lignes += 1
    return {"format":"jsonl","lignes_echantillonnees":lignes,
            "lignes_ignorees":ignorees,"squelette":sk}

def analyser_csv(chemin, echantillon):
    with open(chemin,"r",encoding="utf-8",errors="replace",newline="") as f:
        extrait = f.read(8192)
        f.seek(0)
        try:
            dialect = csv.Sniffer().sniff(extrait, delimiters=",;"+chr(92)+'t|')
        except csv.Error:
            dialect = csv.excel
        lecteur = csv.reader(f, dialect)
        try:
            entete = next(lecteur)
        except StopIteration:
            return {"format":"csv","colonnes":[],"nb_colonnes":0,"lignes_echantillonnees":0}
        colonnes = [[] for _ in entete]
        lignes = 0
        for ligne in lecteur:
            if lignes >= echantillon:
                break
            if not ligne:
                continue
            for i in range(len(entete)):
                colonnes[i].append(ligne[i] if i < len(ligne) else "")
            lignes += 1
    cols = [{"nom":nom,"type":inferer_type_colonne(cellules)}
            for nom,cellules in zip(entete,colonnes)]
    return {"format":"csv","colonnes":cols,"nb_colonnes":len(cols),
            "lignes_echantillonnees":lignes}

def detecter_format(chemin):
    ext = os.path.splitext(chemin)[1].lower()
    if ext == ".json":
        return "json"
    if ext in (".jsonl",".ndjson"):
        return "jsonl"
    if ext == ".csv":
        return "csv"
    with open(chemin,"r",encoding="utf-8",errors="replace") as f:
        contenu = f.read()
    try:
        json.loads(contenu)
        return "json"
    except Exception:
        pass
    for ligne in contenu.splitlines():
        texte = ligne.strip()
        if not texte:
            continue
        try:
            json.loads(texte)
            return "jsonl"
        except Exception:
            break
    return "csv"

def resume(noeud):
    if noeud["type"] == "mixte":
        return "mixte(" + "|".join(noeud["types"]) + ")"
    return noeud["type"]

def etiquette(noeud):
    t = noeud["type"]
    if t == "objet":
        base = "objet (%d cle%s)" % (noeud["nb_cles"], "s" if noeud["nb_cles"]>1 else "")
        if noeud.get("tronque"):
            return base + " [tronque : profondeur max]"
        return base
    if t == "liste":
        card = noeud["cardinalite"]
        if card["min"] == card["max"]:
            card_s = str(card["min"])
        else:
            card_s = "%d..%d" % (card["min"],card["max"])
        if noeud.get("tronque"):
            return "liste[%s] [tronque : profondeur max]" % card_s
        elem = noeud.get("elements")
        if elem is None:
            return "liste[%s] (vide)" % card_s
        return "liste[%s] de %s" % (card_s, resume(elem))
    if t == "mixte":
        return "mixte(" + "|".join(noeud["types"]) + ")"
    return t

def afficher_noeud(nom, noeud, prefixe, dernier, lignes):
    branche = "+-- " if dernier else "|-- "
    lignes.append(prefixe + branche + nom + " : " + etiquette(noeud))
    extension = "    " if dernier else "|   "
    if noeud["type"] == "objet" and not noeud.get("tronque"):
        items = list(noeud["cles"].items())
        for i, (k, sous) in enumerate(items):
            afficher_noeud(k, sous, prefixe + extension, i == len(items)-1, lignes)
    elif noeud["type"] == "liste" and not noeud.get("tronque"):
        elem = noeud.get("elements")
        if elem is not None and elem["type"] in ("objet","liste"):
            afficher_noeud("[]", elem, prefixe + extension, True, lignes)

def rendre_texte(resultats):
    blocs = []
    for r in resultats:
        if r.get("erreur"):
            blocs.append("%s : ERREUR (%s)" % (r["chemin"], r["erreur"]))
            continue
        lignes = []
        fmt = r["format"]
        if fmt == "csv":
            lignes.append("%s (CSV, %d colonnes, %d lignes echantillonnees)" % (
                r["chemin"], r["nb_colonnes"], r["lignes_echantillonnees"]))
            for c in r["colonnes"]:
                lignes.append("  %s : %s" % (c["nom"], c["type"]))
        elif fmt == "jsonl":
            lignes.append("%s (JSONL, %d lignes echantillonnees, %d ignorees)" % (
                r["chemin"], r["lignes_echantillonnees"], r["lignes_ignorees"]))
            if r["squelette"] is None:
                lignes.append("  (aucune ligne exploitable)")
            else:
                afficher_noeud("racine", r["squelette"], "", True, lignes)
        else:
            lignes.append("%s (JSON)" % r["chemin"])
            afficher_noeud("racine", r["squelette"], "", True, lignes)
        blocs.append(NL.join(lignes))
    return NL.join(blocs)

def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(
        description="Rend le squelette de fichiers de donnees (JSON, JSONL, CSV) sans aucune valeur.")
    parser.add_argument("chemins", nargs="+", help="Fichiers JSON, JSONL ou CSV a decrire")
    parser.add_argument("--profondeur-max", type=int, default=PROFONDEUR_MAX_DEFAUT,
                        help="Profondeur maximale d'exploration (defaut : %(default)s)")
    parser.add_argument("--echantillon", type=int, default=ECHANTILLON_DEFAUT,
                        help="Nombre de lignes echantillonnees pour JSONL et CSV (defaut : %(default)s)")
    parser.add_argument("--json", action="store_true", help="Sortie en JSON")
    args = parser.parse_args()
    resultats = []
    for chemin in args.chemins:
        try:
            fmt = detecter_format(chemin)
            if fmt == "json":
                info = analyser_json(chemin, args.profondeur_max)
            elif fmt == "jsonl":
                info = analyser_jsonl(chemin, args.echantillon, args.profondeur_max)
            else:
                info = analyser_csv(chemin, args.echantillon)
            entree = {"chemin":chemin}
            entree.update(info)
            resultats.append(entree)
        except RecursionError:
            resultats.append({"chemin":chemin,
                "erreur":"RecursionError : structure trop profondement imbriquee (profondeur atteinte : %d)" % sys.getrecursionlimit()})
        except Exception as e:
            resultats.append({"chemin":chemin,
                "erreur":"%s: %s" % (type(e).__name__, e)})
    if args.json:
        print(json.dumps({"fichiers":resultats}, ensure_ascii=False, indent=2))
    else:
        print(rendre_texte(resultats))
    echecs = sum(1 for r in resultats if r.get("erreur"))
    if echecs == 0:
        return 0
    if echecs == len(resultats):
        print("Aucun fichier n'a pu etre decrit.", file=sys.stderr)
        return 2
    print("%d fichier(s) en echec sur %d." % (echecs, len(resultats)), file=sys.stderr)
    return 1

if __name__ == "__main__":
    sys.exit(main())
