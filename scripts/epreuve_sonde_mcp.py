# -*- coding: utf-8 -*-
"""
Le vert de la sonde signifie-t-il quelque chose ?

CE QUI ETAIT FAUX, mesure le 2026-08-31 par une session voisine puis reproduit
ici. `nexus_mcp_probe.py` rendait EXIT 0 sur ses propres echecs : un fichier
hors depot, un fichier inexistant, une expiration de delai. Sa propre
docstring promet pourtant l'inverse -- « un code de sortie explicite afin que
les scripts d'automatisation puissent distinguer : le pont a repondu une
erreur / le pont n'a pas repondu ».

LA CAUSE. `_probe_success` ne testait que des PREFIXES de la sortie entiere.
Or le pont ecrit d'abord son en-tete, puis « ## Par fichier », puis le corps :
le marqueur d'echec -- « (refuse : hors du depot) », « (introuvable) » -- est
TOUJOURS au corps, jamais en tete. Le `startswith(" [ERREUR]")`, avec son
espace initial, n'a probablement jamais ete vrai une seule fois.

Un garde dont le vert ne signifie rien est PIRE que pas de garde : il consomme
de l'attention et confere une fausse assurance.

DEUX PIEGES SYMETRIQUES, et cette epreuve garde les deux. Un controle qui
n'attrape rien est inutile ; un controle qui refuse tout l'est autant, et se
fait desarmer plus vite. Les cas 1 a 5 exigent qu'un echec soit vu ; les cas 6
a 9 exigent qu'un succes passe, y compris quand le CONTENU resume parle de
delais -- chercher le mot nu « timeout » n'importe ou ferait echouer le resume
de tout fichier qui en traite, et il y en a plusieurs ici.

Le dixieme cas garde l'accord des deux budgets : la sonde attend 900 s tandis
que le serveur se fermait de lui-meme a 120 s, si bien que porter le seul
delai de la sonde ne servait a rien -- mesure : « fermeture forcee : 1
appel(s) toujours en vol » sur un fichier parfaitement valide.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import nexus_mcp_probe as sonde  # noqa: E402

ECHECS = 0


def verifier(nom: str, condition: bool, detail: str = "") -> None:
    global ECHECS
    print("[%s] %s : %s" % ("OK  " if condition else "RATE", nom, detail))
    if not condition:
        ECHECS += 1


# La sortie reelle du pont, relevee le 2026-08-31 : en-tete, section, corps.
def sortie(corps: str, jetons: int = 2289) -> str:
    return ("\n[glm-4.7-flash-local · local, cout 0 · %d tokens]\n\n"
            "## Par fichier\n\n### scripts/x.py\n%s\n" % (jetons, corps))


def jouer() -> int:
    # --- ce qui DOIT etre vu comme un echec ---------------------------
    verifier("Cas 1 - refus hors depot",
             sonde._probe_success(sortie("(refuse : hors du depot)")) is False,
             "vu")
    verifier("Cas 2 - fichier introuvable",
             sonde._probe_success(sortie("(introuvable)")) is False, "vu")
    verifier("Cas 3 - fichier illisible",
             sonde._probe_success(sortie("(illisible : EACCES)")) is False, "vu")
    verifier("Cas 4 - expiration du delai",
             sonde._probe_success("ERROR: timeout expired after 60s") is False,
             "vu")
    verifier("Cas 5 - sortie vide",
             sonde._probe_success("   ") is False, "vu")

    # --- ce qui DOIT rester un succes ---------------------------------
    bon = sortie("Voici une synthese technique du fichier.")
    verifier("Cas 6 - resume normal",
             sonde._probe_success(bon) is True, "passe")
    verifier("Cas 7 - resume normal avec preuve d'appel modele",
             sonde._probe_success(bon, exige_modele=True) is True, "passe")
    # LE PIEGE SYMETRIQUE. Un resume qui PARLE de delais contient le mot
    # « timeout » : le chercher n'importe ou condamnerait tout fichier qui en
    # traite. On ne vise donc que la phrase que la sonde emet elle-meme.
    parle_de_delais = sortie(
        "Le module fixe un timeout de 900 s et documente son expiration.")
    verifier("Cas 8 - un resume QUI PARLE de timeout reste un succes",
             sonde._probe_success(parle_de_delais) is True, "passe")

    # --- la preuve qu'un modele a bien ete appele ----------------------
    verifier("Cas 9 - zero jeton sur un appel cense invoquer un modele",
             sonde._probe_success(sortie("Resume.", 0), exige_modele=True) is False,
             "vu")

    # --- l'accord des deux budgets -------------------------------------
    delai = sonde._delai_sonde()
    verifier("Cas 10 - le delai par defaut depasse la grace du serveur (120 s)",
             delai > 120, "delai=%ss" % delai)

    print("-" * 66)
    print("VERDICT : epreuve tenue" if ECHECS == 0
          else "VERDICT : %d echec(s)" % ECHECS)
    return 1 if ECHECS else 0


if __name__ == "__main__":
    sys.exit(jouer())
