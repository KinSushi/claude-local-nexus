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
