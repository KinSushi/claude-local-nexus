# -*- coding: utf-8 -*-
"""Un corpus ingere est-il PRODUIT, DECOUVERT, et LU a son offset ?

POURQUOI CE FICHIER. Une instance voisine, chargee de la securite, a demande
« une documentation complete, parsee, prete a l'ingestion par des agents,
digeste meme pour un modele de 1 a 3 milliards de parametres ».

Ce depot possedait la moitie de la reponse : `nexus_doc.py` sert 166 507
symboles par `seek`, a ~280 jetons la consultation. Mais la voie d'INGESTION
n'existait pas -- les trois corpus annexes etaient arrives DEJA indexes.

TROIS DEFAUTS TROUVES EN S'EN SERVANT, aucun par relecture :

  1. Les identifiants finissaient par un COMPTEUR. Le chercheur matche le
     DERNIER SEGMENT (`bash.trap` se consulte par « trap ») : un corpus entier
     etait donc correct et INTROUVABLE.
  2. Le chargeur portait `for sous in ("shell_docs", "lecons")` -- deux noms
     GRAVES. Un corpus neuf etait indexe et verifie (201 offsets relus par
     seek, tous concordants) et pourtant invisible. Deux verites
     contradictoires dont aucune ne mentait : elles portaient sur deux chemins
     de code differents.
  3. Le champ `type` n'etait ecrit que dans l'index, jamais dans l'objet. Le
     rendu s'aiguille dessus : chaque entree d'un corpus sain s'annoncait
     « type de corpus non reconnu ».

LE PIEGE PRINCIPAL, lui, a ete tenu des le premier jet parce qu'il etait DIT
dans la consigne : les offsets sont en OCTETS, jamais en caracteres. Le corpus
vise est en francais ; la divergence serait certaine, pas hypothetique.
"""
import json
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from nexus_ingerer import decouper_markdown, ecrire_corpus  # noqa: E402

echecs = 0


def verifier(nom, condition, detail):
    global echecs
    print("  [%s] %s : %s" % ("OK  " if condition else "RATE", nom, detail))
    if not condition:
        echecs += 1


DOC = """# Titre accentue : securite reseau

Une premiere section avec des accents : donnees, integrite, cle privee.

## Sous-section

Du contenu ici.

# Deuxieme titre

Autre contenu.
"""


def main():
    global echecs
    echecs = 0

    # --- Decoupage ------------------------------------------------------
    sections = decouper_markdown(DOC, "doc.md")
    verifier("plusieurs sections", len(sections) >= 2, "%d" % len(sections))
    verifier("chaque section a un titre", all(s.get("titre") for s in sections),
             "un titre vide donnerait un identifiant vide")
    verifier("aucune section vide",
             all((s.get("texte") or "").strip() for s in sections), "")
    verifier("la ligne est en base 1",
             all(isinstance(s.get("ligne"), int) and s["ligne"] >= 1
                 for s in sections), str([s.get("ligne") for s in sections]))

    tmp = tempfile.mkdtemp()
    try:
        n = ecrire_corpus(sections, tmp, "essai")
        verifier("le compte rendu est celui des entrees", n == len(sections),
                 "%s" % n)

        jsonl = os.path.join(tmp, "symbols.jsonl")
        tsv = os.path.join(tmp, "index.tsv")
        with open(tsv, encoding="utf-8") as fh:
            lignes = fh.read().split("\n")

        verifier("l'en-tete est exact",
                 lignes[0] == "id\toffset_octets\tlongueur_octets\ttype\tresume",
                 repr(lignes[0][:50]))

        # --- LE PIEGE PRINCIPAL : relire CHAQUE entree par son offset -----
        #
        # C'est le seul cas qui distingue un offset en octets d'un offset en
        # caracteres. Sur un corpus sans accent, les deux coincident et
        # l'epreuve serait verte a tort.
        ok, detail = True, "les offsets sont bien en octets"
        with open(jsonl, "rb") as fh:
            for ligne in lignes[1:]:
                if not ligne.strip():
                    continue
                champs = ligne.split("\t")
                fh.seek(int(champs[1]))
                brut = fh.read(int(champs[2]))
                try:
                    obj = json.loads(brut.decode("utf-8"))
                except Exception as exc:
                    ok, detail = False, "%s illisible : %s" % (champs[0], exc)
                    break
                if obj.get("id") != champs[0]:
                    ok, detail = False, "offset rend %s, attendu %s" % (
                        obj.get("id"), champs[0])
                    break
        verifier("chaque offset rend SON entree, relue en binaire", ok, detail)

        # --- L'IDENTIFIANT DOIT ETRE CHERCHABLE --------------------------
        #
        # Le chercheur matche le dernier segment. Un compteur n'est pas
        # cherchable : le corpus serait correct et introuvable.
        ids = [x.split("\t")[0] for x in lignes[1:] if x.strip()]
        verifier("le dernier segment n'est pas un simple compteur",
                 all(not x.rsplit(".", 1)[-1].isdigit() for x in ids),
                 str(ids[:2]))
        verifier("les identifiants sont uniques", len(set(ids)) == len(ids),
                 "%d identifiants, %d distincts" % (len(ids), len(set(ids))))

        # --- LE RESUME ATTEINT-IL L'INDEX ? ------------------------------
        #
        # CE QUI ETAIT FAUX : la colonne `resume` de l'index portait toujours
        # le TITRE, meme quand un modele local avait produit un resume.
        # L'outil annoncait « 4 resumes produits » et l'index n'en portait
        # aucun -- produit, non consomme. Aucune epreuve ne le voyait, parce
        # qu'aucune ne reliait les deux moities.
        avec_resume = [{"titre": "Un titre", "ligne": 1, "texte": "du texte",
                        "resume": "LE RESUME DU MODELE"}]
        tmp2 = tempfile.mkdtemp()
        try:
            ecrire_corpus(avec_resume, tmp2, "res")
            with open(os.path.join(tmp2, "index.tsv"), encoding="utf-8") as fh:
                derniere = [x for x in fh.read().split("\n") if x.strip()][-1]
            verifier("le resume fourni atteint la colonne de l'index",
                     derniere.split("\t")[4] == "LE RESUME DU MODELE",
                     repr(derniere.split("\t")[4]))
            sans = [{"titre": "Un titre", "ligne": 1, "texte": "du texte"}]
            ecrire_corpus(sans, tmp2, "res")
            with open(os.path.join(tmp2, "index.tsv"), encoding="utf-8") as fh:
                derniere = [x for x in fh.read().split("\n") if x.strip()][-1]
            verifier("sans resume, le titre reste le repli",
                     derniere.split("\t")[4] == "Un titre",
                     "une entree sans resume doit se lire quand meme")
        finally:
            shutil.rmtree(tmp2, ignore_errors=True)

        # --- LE TYPE VIT DANS L'OBJET ------------------------------------
        with open(jsonl, encoding="utf-8") as fh:
            premier = json.loads(fh.readline())
        verifier("l'objet porte son type", bool(premier.get("type")),
                 "le rendu s'aiguille dessus")

        # --- PORTABILITE DES OFFSETS -------------------------------------
        with open(jsonl, "rb") as fh:
            verifier("aucun retour chariot dans le jsonl",
                     b"\r\n" not in fh.read(),
                     "Windows decalerait d'un octet par ligne")
        with open(tsv, "rb") as fh:
            verifier("aucun retour chariot dans l'index",
                     b"\r\n" not in fh.read(), "")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    # --- CE QUI RENDRAIT L'INDEX ILLISIBLE -------------------------------
    #
    # L'index est ce qu'un petit modele lit EN ENTIER pour choisir. Une
    # tabulation dans un resume decale toutes les colonnes a partir de la.
    tmp = tempfile.mkdtemp()
    try:
        piege = [{"titre": "un\ttitre\tavec\tdes\ttabulations", "ligne": 1,
                  "texte": "contenu"},
                 {"titre": "un titre\navec un saut", "ligne": 2,
                  "texte": "contenu"}]
        ecrire_corpus(piege, tmp, "piege")
        with open(os.path.join(tmp, "index.tsv"), encoding="utf-8") as fh:
            lignes = [x for x in fh.read().split("\n") if x.strip()]
        verifier("une ligne d'index = 5 colonnes, toujours",
                 all(len(x.split("\t")) == 5 for x in lignes),
                 str([len(x.split("\t")) for x in lignes]))
        verifier("autant de lignes que d'entrees, plus l'en-tete",
                 len(lignes) == 3, "%d" % len(lignes))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    # --- CORPUS VIDE : legitime, jamais un echec silencieux --------------
    tmp = tempfile.mkdtemp()
    try:
        verifier("un corpus vide rend zero sans lever",
                 ecrire_corpus([], tmp, "vide") == 0, "")
        verifier("l'index existe quand meme",
                 os.path.isfile(os.path.join(tmp, "index.tsv")),
                 "son absence serait indistinguable d'un echec")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    # --- DECOUPE D'UNE SECTION TROP LONGUE -------------------------------
    long_doc = "# Titre\n\n" + "\n".join(
        "ligne %d avec du contenu accentue : donnee" % i for i in range(200))
    morceaux = decouper_markdown(long_doc, "long.md", taille_max=600)
    verifier("une section longue est coupee", len(morceaux) > 1,
             "%d morceaux" % len(morceaux))
    verifier("aucun morceau n'explose la taille demandee",
             all(len(m["texte"]) <= 900 for m in morceaux),
             str(sorted(len(m["texte"]) for m in morceaux)[-2:]))
    verifier("aucune ligne coupee en son milieu",
             all("ligne" in m["texte"] and not m["texte"].startswith("igne")
                 for m in morceaux),
             "un modele de 1 a 3 milliards completerait une phrase tronquee")

    print("")
    if echecs:
        print("epreuve ratee : %d cas" % echecs)
        sys.exit(1)
    print("epreuve tenue")
    sys.exit(0)


if __name__ == "__main__":
    main()
