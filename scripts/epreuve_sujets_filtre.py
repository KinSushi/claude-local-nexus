# -*- coding: utf-8 -*-
"""Un marqueur est-il pris pour un sujet ?

CE QUI ETAIT FAUX, mesure sur une vraie execution du 2026-08-31 : l'outil ne
distinguait pas UNE PHRASE CONTENANT le mot « ouvert » d'UN SUJET OUVERT. Il
rendait 499 occurrences, dont de la doctrine, des lignes de commande, et ma
propre narration d'un travail deja fait. L'outil bati pour eviter de deviner
obligeait donc a deviner.

Les fragments ci-dessous ne sont pas inventes pour la circonstance : ce sont
les sorties REELLES de cette execution. Le dernier est un VRAI sujet ouvert et
doit survivre au filtre -- sans lui, l'epreuve ne prouverait que la severite,
et un filtre qui rejette tout est aussi inutile qu'un filtre qui passe tout.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from nexus_sujets import marqueur_fiable, semble_clos  # noqa: E402

echecs = 0


def verifier(nom, condition, detail):
    print("  [%s] %s : %s" % ("OK  " if condition else "RATE", nom, detail))
    global echecs
    if not condition:
        echecs += 1


def juge(texte, marqueur):
    """Le verdict complet, tel que les trois sources l'appliquent."""
    pos = texte.lower().find(marqueur.lower())
    if pos < 0:
        return None
    if not marqueur_fiable(texte, pos, marqueur):
        return False
    return not semble_clos(texte)


# --- Les quatre fragments REELS ------------------------------------------- #

DOCTRINE = (
    "docs(doctrine): une regle non mecanisee ne protege pas, meme son auteur. "
    "Enonce par l'operateur apres l'avoir vu se produire toute la journee."
)
NARRATION = (
    "Reste a l'appeler -- une fonction que personne n'invoque est un fichier, "
    "pas un mecanisme."
)
COMMANDE = (
    'rm -f _INDEX.md; grep -n "aucun contenu a traiter" -B14 '
    "tools/nexus-mcp/server.js | head -8"
)
VRAI_SUJET = (
    "inutile au pool, ce que rien ne mesure. Le generateur l'ANNONCE "
    "desormais ; la decision de politique reste a l'operateur."
)

verifier("doctrine rejetee", juge(DOCTRINE, "non mecanise") is not True,
         "une doctrine enonce une regle, elle n'ouvre pas de sujet")
verifier("narration rejetee", juge(NARRATION, "reste a") is not True,
         "ma propre narration d'un travail deja fait")
verifier("commande rejetee", juge(COMMANDE, "a traiter") is not True,
         "une ligne de commande n'est jamais un sujet")
verifier("vrai sujet GARDE", juge(VRAI_SUJET, "reste a") is True,
         "corrobore par « l'operateur » : decision differee")

# --- Le marqueur fort se suffit ------------------------------------------- #

FORT = "Trois hypotheses ouvertes ; ce point reste ouvert et personne ne le garde."
verifier("marqueur fort seul", juge(FORT, "reste ouvert") is True,
         "sa seule presence suffit, sans corroboration")

# --- Le piege documente : ferme ET ouvert dans le meme fragment ------------ #
#
# « X est corrige, mais Y reste ouvert ». Le premier jet confiait cette
# exemption a l'appelant, par un commentaire. Les appelants existent deja et ne
# l'auraient pas lue -- et une regle en paragraphe ne protege personne.
MIXTE = (
    "Le port du contrat est corrige et prouve. En revanche l'appariement de "
    "noms reste ouvert : aucune epreuve ne le garde."
)
verifier("ferme ET ouvert : l'ouvert l'emporte", juge(MIXTE, "reste ouvert") is True,
         "semble_clos ne doit pas masquer un marqueur fort")
verifier("semble_clos exempte le marqueur fort", semble_clos(MIXTE) is False,
         "l'exemption vit DANS la fonction, pas dans un commentaire")

# --- Le tiret cadratin n'est pas une commande ----------------------------- #
#
# « -- » figurait dans les motifs de commande. Il sert de tiret cadratin dans
# presque tous les commentaires de ce depot : le garder aurait supprime des
# sujets EN SILENCE, soit l'inverse exact du but.
CADRATIN = (
    "Le crible AST -- celui que la session voisine construit -- reste ouvert "
    "ici : aucun motif ne le porte."
)
verifier("le tiret cadratin ne disqualifie pas", juge(CADRATIN, "reste ouvert") is True,
         "un filtre trop large fait du bruit invisible")

# --- « OUVERT » en capitales est un signal, et il doit JOUER --------------- #
#
# Il figurait dans une liste comparee a du texte MINUSCULE : le controle etait
# mort, et sa presence donnait a croire qu'il jouait.
CAPITALES = "Section 9.3 -- Ce qui reste OUVERT : il reste a decider du perimetre."
verifier("OUVERT en capitales corrobore", juge(CAPITALES, "il reste") is True,
         "la casse EST l'information dans ce depot")

print("")
if echecs:
    print("epreuve ratee : %d cas" % echecs)
    sys.exit(1)
print("epreuve tenue")
sys.exit(0)
