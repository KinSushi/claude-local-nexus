#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Ingerer une documentation pour qu'un PETIT modele puisse la consulter.

POURQUOI CE FICHIER EXISTE. Une instance voisine, chargee de la securite, a
demande « une documentation complete, parsee, prete a l'ingestion par des
agents, digeste meme pour un modele de 1 a 3 milliards de parametres ».

Ce depot possedait deja la moitie de la reponse et l'ignorait : `nexus_doc.py`
sert 166 507 symboles par `seek`, a environ 280 jetons la consultation --
l'entree est lue A SON OFFSET, jamais le fichier entier. C'est exactement ce
qu'un modele de cette taille peut absorber.

MAIS LA VOIE D'INGESTION N'EXISTAIT PAS. Les trois corpus annexes -- bash,
PowerShell, lecons -- sont arrives DEJA INDEXES depuis un depot voisin. Le
format etait CONSOMME ici, jamais PRODUIT :

    references/<corpus>/index.tsv      id, offset_octets, longueur_octets,
                                       type, resume
    references/<corpus>/symbols.jsonl  une entree JSON par ligne

LE PIEGE PRINCIPAL, ET IL SE JOUE AU PREMIER ACCENT. Les offsets sont en
OCTETS, jamais en caracteres. `len(chaine)` compte des caracteres ; le lecteur
fait `seek` sur des octets. Le corpus vise est en francais : la divergence est
certaine, pas hypothetique. Chaque ligne est donc encodee en UTF-8 AVANT
d'etre mesuree.

SECOND PIEGE, propre a Windows : le mode texte par defaut traduit le saut de
ligne en deux octets, ce qui DECALE tous les offsets suivants d'un octet par
ligne. D'ou `newline=""` a l'ecriture.

TROISIEME, propre a l'usage vise : une tabulation ou un saut de ligne dans un
resume decale les colonnes de l'index et le rend illisible a partir de la. Or
l'index est ce qu'un petit modele lit EN ENTIER pour choisir quoi consulter.

USAGE :

    python scripts/nexus_ingerer.py --source docs/securite --nom securite
    python scripts/nexus_ingerer.py --source docs/securite --nom securite --appliquer

Sans --appliquer, rien n'est ecrit : la simulation dit ce qui le serait.
"""
import argparse
import io
import json
import os
import re
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXTENSIONS = (".md", ".markdown", ".txt", ".rst")


def decouper_markdown(texte, chemin, taille_max=1200):
    """
    Retourne une liste de dicts {"titre", "ligne", "texte"}.
    Chaque dict correspond a une section (ou sous-section) du markdown.
    """
    lignes = texte.splitlines()
    sections = []
    cur_titre = os.path.splitext(os.path.basename(chemin))[0]
    cur_texte = []
    debut_ligne = 1

    titre_regex = re.compile(r'^(#+)\s+(.*)')

    for i, ligne in enumerate(lignes, start=1):
        m = titre_regex.match(ligne)
        if m:
            # on ferme la section precedente
            if cur_texte:
                sections.append((cur_titre, debut_ligne, "\n".join(cur_texte)))
            # nouveau titre
            cur_titre = m.group(2).strip()
            debut_ligne = i
            cur_texte = []
        else:
            cur_texte.append(ligne)

    # derniere section
    if cur_texte:
        sections.append((cur_titre, debut_ligne, "\n".join(cur_texte)))

    # decoupage selon taille_max
    result = []
    for titre, ligne_debut, texte in sections:
        # ignorer sections vides ou contenant seulement des espaces
        if not texte.strip():
            continue
        # si le texte tient dans la taille max, on garde tel quel
        if len(texte) <= taille_max:
            result.append({"titre": titre, "ligne": ligne_debut, "texte": texte})
            continue

        # sinon, couper sur les frontieres de ligne
        lignes_section = texte.splitlines()
        chunk = []
        chunk_len = 0
        chunks = []
        for l in lignes_section:
            l_len = len(l) + 1  # +1 pour le \n qui sera reconstitue
            if chunk_len + l_len > taille_max and chunk:
                chunks.append("\n".join(chunk))
                chunk = [l]
                chunk_len = l_len
            else:
                chunk.append(l)
                chunk_len += l_len
        if chunk:
            chunks.append("\n".join(chunk))

        total = len(chunks)
        for idx, part in enumerate(chunks, start=1):
            suffix = f" ({idx}/{total})" if total > 1 else ""
            result.append({
                "titre": titre + suffix,
                "ligne": ligne_debut,
                "texte": part
            })
    return result


def _slug(titre, secours):
    """
    Un fragment d'identifiant CHERCHABLE, tire du titre.

    Le chercheur de nexus_doc.py matche le dernier segment de l'identifiant.
    Un compteur n'est pas cherchable ; un titre reduit l'est. On garde donc le
    titre, ramene a des caracteres sobres et borne a 48 signes : au-dela,
    personne ne le tape, et l'index devient illisible pour un petit modele qui
    le lit en entier.
    """
    base = []
    for ch in (titre or "").lower():
        if ch.isalnum():
            base.append(ch)
        elif base and base[-1] != "-":
            base.append("-")
    slug = "".join(base).strip("-")[:48].strip("-")
    # Un titre entierement fait de ponctuation rendrait une chaine vide, et
    # deux entrees vides porteraient le meme identifiant. Le secours est le
    # compteur : moins cherchable, mais unique.
    return slug or str(secours)


def ecrire_corpus(entrees, dossier, prefixe, type_entree="doc"):
    """
    Ecrit dossier/symbols.jsonl et dossier/index.tsv.
    Retourne le nombre d'entrees ecrites.
    """
    _vus = {}
    os.makedirs(dossier, exist_ok=True)

    path_jsonl = os.path.join(dossier, "symbols.jsonl")
    path_tsv   = os.path.join(dossier, "index.tsv")

    # ouverture avec newline="\\n" pour garantir les offsets identiques
    with open(path_jsonl, "w", encoding="utf-8", newline="\n") as f_jsonl, \
         open(path_tsv,   "w", encoding="utf-8", newline="\n") as f_tsv:

        # ecriture de l'entete du TSV
        f_tsv.write("id\toffset_octets\tlongueur_octets\ttype\tresume\n")
        offset = 0  # offset du prochain enregistrement dans symbols.jsonl

        for idx, ent in enumerate(entrees, start=1):
            ident = f"{prefixe}.{_slug(ent.get('titre'), idx)}"
            # DEUX ENTREES PEUVENT PORTER LE MEME TITRE -- une section coupee
            # en morceaux, ou deux fichiers aux titres identiques. Un
            # identifiant duplique ferait pointer deux lignes d'index sur la
            # meme entree, et la seconde serait INTROUVABLE sans que rien ne
            # le dise.
            if ident in _vus:
                _vus[ident] += 1
                ident = "%s-%d" % (ident, _vus[ident])
            else:
                _vus[ident] = 1

            # construction du dictionnaire JSON
            obj = {
                "id": ident,
                "resume": ent.get("resume", ""),   # peut etre fourni
                "chemin": ent.get("chemin", ""),
                "titre": ent.get("titre", ""),
                "texte": ent.get("texte", ""),
            # LE TYPE VIT DANS L'OBJET, pas seulement dans l'index :
            # c'est sur lui que le rendu s'aiguille, et son absence
            # faisait annoncer « type de corpus non reconnu » sur chaque
            # entree d'un corpus parfaitement sain.
            "type": type_entree
            }
            # si le champ resume n'est pas fourni, on le prend dans le titre
            if not obj["resume"]:
                obj["resume"] = obj["titre"]

            ligne_json = json.dumps(obj, ensure_ascii=False)
            ligne_json_utf8 = (ligne_json + "\n").encode("utf-8")
            longueur = len(ligne_json_utf8)

            # ecriture dans symbols.jsonl
            f_jsonl.write(ligne_json + "\n")

            # preparation du resume pour l'index (120 chars max, tabs -> espace, newlines -> espace)
            resume_idx = obj["titre"]
            resume_idx = resume_idx.replace("\t", " ").replace("\n", " ")
            if len(resume_idx) > 120:
                resume_idx = resume_idx[:120]
            # ecriture dans index.tsv
            f_tsv.write(f"{ident}\t{offset}\t{longueur}\t{type_entree}\t{resume_idx}\n")

            # mise a jour de l'offset pour la prochaine ligne
            offset += longueur

    return len(entrees)

def parcourir(source, taille_max):
    """
    Lit tous les documents d'une arborescence et les decoupe.

    Les fichiers illisibles sont SIGNALES et sautes, jamais tus : un corpus
    incomplet en silence est pire qu'un corpus incomplet annonce -- on croit
    avoir tout ingere.
    """
    entrees = []
    sautes = []
    for dossier, _sd, fichiers in os.walk(source):
        for nom in sorted(fichiers):
            if not nom.lower().endswith(EXTENSIONS):
                continue
            chemin = os.path.join(dossier, nom)
            try:
                with io.open(chemin, encoding="utf-8", errors="replace") as fh:
                    texte = fh.read()
            except Exception as exc:
                sautes.append((chemin, str(exc)[:60]))
                continue
            relatif = os.path.relpath(chemin, source).replace("\\", "/")
            entrees.extend(decouper_markdown(texte, relatif, taille_max))
    return entrees, sautes


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--source", required=True,
                    help="repertoire des documents a ingerer")
    ap.add_argument("--nom", required=True,
                    help="nom du corpus : references/<nom>/")
    ap.add_argument("--taille-max", type=int, default=1200,
                    help="caracteres par entree (defaut 1200, ~300 jetons)")
    ap.add_argument("--appliquer", action="store_true",
                    help="ecrit reellement ; sans lui, rien n'est ecrit")
    a = ap.parse_args(argv)

    if not os.path.isdir(a.source):
        print("source introuvable : %s" % a.source, file=sys.stderr)
        return 2

    entrees, sautes = parcourir(a.source, a.taille_max)
    for chemin, motif in sautes:
        print("SAUTE %s : %s" % (chemin, motif), file=sys.stderr)

    if not entrees:
        # Un corpus vide est un etat legitime, mais il ne doit pas se lire
        # comme une reussite : rien ne sera consultable.
        print("aucune entree : %d fichier(s) saute(s), extensions %s"
              % (len(sautes), ", ".join(EXTENSIONS)))
        return 1

    total = sum(len(e["texte"]) for e in entrees)
    print("%d entree(s), %d caracteres, %.0f caracteres par entree en moyenne"
          % (len(entrees), total, total / len(entrees)))
    print("  la plus longue : %d caracteres" % max(len(e["texte"]) for e in entrees))

    if not a.appliquer:
        print("SIMULATION : rien n'a ete ecrit. Ajouter --appliquer.")
        return 0

    dossier = os.path.join(RACINE, "references", a.nom)
    n = ecrire_corpus(entrees, dossier, a.nom)
    print("ecrit : %s (%d entrees)" % (dossier, n))
    print("consultable par : python scripts/nexus_doc.py <symbole>")
    return 0


if __name__ == "__main__":
    sys.exit(main())
