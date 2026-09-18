# -*- coding: cp1252 -*-
"""Epreuve de non‑régression du verdict de charge.

Cette mesure était verte sur les deux versions du dépôt, donc
l’épreuve était aveugle. Elle échoue désormais car la logique de
décision est enfermée dans `main()` de `scripts/nexus_charge.py` et
reproduire cette logique donnerait un faux vert, comme déjà constaté.
"""
import os
import sys

# Racine du dépôt : parent du répertoire contenant ce fichier.
RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Ajout du répertoire outillage pour le garde‑d’encodage.
OUTILLAGE = os.path.join(RACINE, "outillage")
if OUTILLAGE not in sys.path:
    sys.path.insert(0, OUTILLAGE)

try:
    from console_tools import forcer_utf8
    forcer_utf8()
except Exception as exc:  # pragma: no cover
    sys.stderr.write("Echec forcer_utf8 : %s\n" % exc)

# Ajout du répertoire scripts pour pouvoir importer nexus_charge.
SCRIPTS = os.path.join(RACINE, "scripts")
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

# Tentative d’import de la fonction de calcul de significativité.
# Le nom présumé, d’après le contexte du dépôt, est
# `calcul_significativite_processus`.
try:
    from nexus_charge import calcul_significativite_processus
except ImportError as exc:
    sys.stderr.write(
        "DEFAUT CONNU DU DEPOT : la logique de décision est enfermée dans "
        "main() de nexus_charge.py, impossible à importer : %s\n" % exc
    )
    sys.exit(1)

# Verdict de charge, nécessaire pour le troisième cas.
try:
    from nexus_charge import verdict_charge
except ImportError as exc:  # pragma: no cover
    sys.stderr.write(
        "Impossible d’importer verdict_charge : %s\n" % exc
    )
    sys.exit(1)


def _cp1252(texte):
    """Retourne le texte encodé en cp1252 (remplacement des caractères non‑supportés)."""
    try:
        texte.encode("cp1252")
        return texte
    except UnicodeEncodeError:
        return texte.encode("cp1252", errors="replace").decode("cp1252")


def _executer_cas(numero, attendu, obtenu, description):
    ok = (obtenu == attendu)
    print(
        "CAS %d (%s) : attendu=%s, obtenu=%s" % (numero, description, attendu, obtenu)
    )
    return ok


def main():
    echecs = 0

    # CAS 1 : processus dormant (68 h, 13 min CPU, aucune activité) → NON significatif.
    try:
        sig1 = calcul_significativite_processus(age_h=68, cpu_min=13, actif=False)
    except Exception as exc:  # pragma: no cover
        sys.stderr.write("Erreur appel fonction significativite (cas 1) : %s\n" % exc)
        sig1 = None
    if not _executer_cas(
        numero=1,
        attendu=False,
        obtenu=sig1,
        description="processus dormant, non significatif",
    ):
        echecs += 1

    # CAS 2 : processus réellement actif → significatif.
    try:
        sig2 = calcul_significativite_processus(age_h=1, cpu_min=5, actif=True)
    except Exception as exc:  # pragma: no cover
        sys.stderr.write("Erreur appel fonction significativite (cas 2) : %s\n" % exc)
        sig2 = None
    if not _executer_cas(
        numero=2,
        attendu=True,
        obtenu=sig2,
        description="processus actif, significatif",
    ):
        echecs += 1

    # CAS 3 : RAM sous le seuil, doit rendre CHARGEE quel que soit le processus.
    etat3, _ = verdict_charge(disponible_go=12.0, seuil_go=30.0)
    if not _executer_cas(
        numero=3,
        attendu="CHARGEE",
        obtenu=etat3,
        description="RAM sous seuil, verdict CHARGEE",
    ):
        echecs += 1

    if echecs:
        sys.stderr.write(_cp1252("ECHEC : %d cas sur 3 ont échoué.\n" % echecs))
        return 1
    print(_cp1252("SUCCES : les 3 cas passent."))
    return 0


if __name__ == "__main__":
    sys.exit(main())
