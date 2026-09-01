# -*- coding: utf-8 -*-
"""Appliquer un patch rendu par le banc, apres verification.

L'orchestrateur ne retape pas : il verifie que le bloc AVANT est REEL et
UNIQUE dans le fichier, applique, et laisse l'epreuve juger. Un bloc absent
ou multiple n'est pas applique -- il est refuse, bruyamment.

Lecture depuis le JSONL en UTF-8 : l'affichage console mutile les accents,
et un patch juge sur son affichage serait juge sur un artefact.
"""
import io
import json
import sys

if len(sys.argv) < 4:
    print("Usage: python nexus_appliquer.py <fichier_jsonl> <nom_tache> <fichier_cible>")
    sys.exit(2)
jsonl, nom, cible = sys.argv[1], sys.argv[2], sys.argv[3]

texte = None
for ligne in io.open(jsonl, encoding="utf-8"):
    ligne = ligne.strip()
    if not ligne:
        continue
    d = json.loads(ligne)
    if d.get("nom") == nom:
        texte = d.get("texte") or ""
        break

if texte is None:
    print("REFUS : aucune tache nommee %s dans %s" % (nom, jsonl))
    sys.exit(1)

if "AUCUN DEFAUT" in texte.upper():
    print("Le banc declare AUCUN DEFAUT SUR -- rien a appliquer.")
    sys.exit(2)

try:
    avant = texte.split("<<<AVANT>>>", 1)[1].split("<<<APRES>>>", 1)[0]
    apres = texte.split("<<<APRES>>>", 1)[1].split("<<<FIN>>>", 1)[0]
except IndexError:
    print("REFUS : le rendu ne porte pas les trois marqueurs.")
    print(texte[:400])
    sys.exit(1)

# Les marqueurs sont poses sur leur propre ligne : on retire le saut qui suit
# l'ouverture et celui qui precede la fermeture, jamais l'indentation.
avant = avant.strip("\r\n")
apres = apres.strip("\r\n")

src = io.open(cible, encoding="utf-8").read()
n = src.count(avant)
print("bloc AVANT : %d occurrence(s) dans %s" % (n, cible))
if n != 1:
    print("REFUS : le bloc doit etre unique et reel. Non applique.")
    print("--- ce que le banc a cru trouver ---")
    print(avant[:400])
    sys.exit(1)

io.open(cible, "w", encoding="utf-8", newline="\n").write(src.replace(avant, apres))
print("APPLIQUE : %s" % cible)
