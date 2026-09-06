# -*- coding: utf-8 -*-
"""
Forcer la console en UTF-8, parce que cp1252 fait tomber un script qui AFFICHE.

CE QUI ETAIT FAUX, mesure le 2026-08-31. `nexus_doc.py` ouvre par ceci :

    try:
        from console_tools import forcer_utf8 as _forcer_utf8
        _forcer_utf8()
    except ImportError:
        pass

et son commentaire annonce « 7e panne cp1252 payee le 2026-08-10 : plus
jamais ». Or le module N'EXISTAIT PAS dans ce depot. L'`except ImportError`
avalait l'absence en silence, et le remede n'a jamais tourne une seule fois.
Un garde importe depuis le vide protege exactement autant que pas de garde --
avec, en plus, la certitude de son auteur qu'il est protege.

Ce que cela coutait : `sys.stdout.encoding` vaut cp1252 sur cette machine, et
tout affichage portant une etoile, un tiret cadratin ou un accent non latin-1
leve UnicodeEncodeError. Une lecon de 1888 octets s'est ainsi rapportee
« ENTREE ILLISIBLE » alors qu'elle etait parfaitement lisible : c'est la
CONSOLE qui ne savait pas l'ecrire. Diagnostiquer la donnee quand la panne est
a l'affichage envoie chercher au mauvais endroit -- meme classe que la
confusion « absent » / « casse » corrigee le meme jour dans nexus_outillage.

`errors="replace"` est deliberé : une console qui ne sait pas rendre un
caractere doit afficher un substitut, jamais interrompre le programme. Perdre
une etoile est sans consequence ; perdre la sortie entiere ne l'est pas.

Verification par execution reelle, le 2026-09-02 : quatre essais dans un
interprete Python jetable, jamais dans l'arbre du depot. Un audit anterieur
avait releve deux appelants reels, nexus_doc.py:46 et epreuve_doc_annexe.py:206 ;
cette verification en ajoute un troisieme que l'audit n'avait pas vu :
scripts/mesure_rendu_vide.py ligne 26 (from console_tools import forcer_utf8).
En revanche scripts/nexus_test.py, scripts/nexus_cablage.py et
epreuves/epreuve_cablage.py ne font que mentionner console_tools dans un
commentaire ou une chaine, sans jamais l'importer : ce ne sont pas de vrais
appelants. Essai 1 (FORWARD, console reelle cp1252) : premier appel
reconfigure en utf-8 (change=True), deuxieme appel idempotent (change=False) ;
etoile, tiret cadratin, coche, guillemets francais et e accent aigu
s'affichent sans UnicodeEncodeError. Essai 2 (REVERSE, flux degrade sans
encoding ni reconfigure, cas d'un flux redirige vers un fichier ou un tube) :
aucune exception, change=False. Essai 3 (REVERSE, flux hostile dont la simple
lecture de encoding leve, au-dela du AttributeError deja couvert par getattr) :
absorbe par le try/except, rien ne leve. Essai 4 (import console_tools puis
from console_tools import forcer_utf8) : le cache sys.modules rend le second
import un no-op sur le meme objet module, sans reinitialisation ni effet de
bord. Verdict : comportement sain sur les quatre scenarios, rien a corriger.
"""
from __future__ import annotations

import sys


def forcer_utf8() -> bool:
    """Reconfigure stdout et stderr en UTF-8. Rend True si au moins un flux a change.

    Ne leve JAMAIS : un utilitaire d'affichage qui plante arrete le travail
    qu'il devait seulement rendre lisible. Les flux rediriges vers un fichier
    ou un tube n'exposent pas toujours `reconfigure` -- l'absence de la methode
    n'est pas une panne, c'est un flux d'un autre genre.
    """
    change = False
    for flux in (sys.stdout, sys.stderr):
        try:
            if getattr(flux, "encoding", "").lower().replace("-", "") == "utf8":
                continue
            reconfigurer = getattr(flux, "reconfigure", None)
            if reconfigurer is None:
                continue
            reconfigurer(encoding="utf-8", errors="replace")
            change = True
        except Exception:
            continue
    return change


if __name__ == "__main__":
    avant = sys.stdout.encoding
    bouge = forcer_utf8()
    print("encodage : %s -> %s (change=%s)" % (avant, sys.stdout.encoding, bouge))
    print("epreuve des caracteres qui tombaient en cp1252 : ★ — ✓ « » é")
