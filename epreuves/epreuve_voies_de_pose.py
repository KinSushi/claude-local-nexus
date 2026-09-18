# -*- coding: utf-8 -*-
"""Epreuve : les deux outils joints nomment-ils la bonne voie de pose ?

Mesure du 2026-09-18. Une session voisine avait fait produire un fichier de
tests NEUF. La garde anti-production a refuse son ecriture directe -- a juste
titre -- et lui a prescrit de faire produire un patch puis de l'appliquer avec
nexus_appliquer.py. Elle a suivi la prescription a la lettre. nexus_appliquer,
qui MODIFIE un fichier existant et ne le cree pas, a rendu « impossible
d'ouvrir le fichier cible : No such file or directory ». La session en a
conclu qu'aucune voie n'existait pour poser un fichier neuf, a archive son
rendu dans un .txt et a declare son travail non fait. La voie existait :
scripts/nexus_creer.py. Deux messages la taisaient.

Un garde qui indique la mauvaise sortie coute plus cher qu'un garde muet,
car l'agent honnete suit l'indication.

Cette epreuve rougit si l'un des deux outils cesse de nommer la voie de pose
qui convient. Six cas, dont une contre-epreuve qui prouve que le critere
DETECTE un message appauvri, un cas qui distingue le refus de perimetre du
refus de racine INTROUVABLE, et un cas qui exige que le refus de
nexus_creer.py cite la ligne fautive ET n'ait pas tolere la creation.
"""

import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Garde d'encodage : ajouter le dossier outillage du depot a sys.path.
_OUTILLAGE = os.path.join(RACINE, "outillage")
if os.path.isdir(_OUTILLAGE) and _OUTILLAGE not in sys.path:
    sys.path.insert(0, _OUTILLAGE)
try:
    from console_tools import forcer_utf8
    forcer_utf8()
except Exception as exc:
    sys.stderr.write("garde d'encodage indisponible : %s\n" % exc)

# Marqueurs construits par concatenation : un fichier qui les porte en clair
# perturbe les outils qui les cherchent (meme technique que
# tools/nexus-mcp/server.js). La chaine reste rigoureusement egale au litteral.
CHEVRONS = ">" * 3
OUVERTURE = "<" * 3 + "CREER" + CHEVRONS
FERMETURE = "<" * 3 + "FIN" + CHEVRONS

GARDE = os.path.join(RACINE, "scripts", "nexus_garde_production.py")
APPLIQUER = os.path.join(RACINE, "scripts", "nexus_appliquer.py")
CREER = os.path.join(RACINE, "scripts", "nexus_creer.py")

CIBLE_EXISTANTE = "scripts/nexus_agent.py"
CIBLE_ABSENTE = "scripts/nexus_cible_absente_epreuve_voies_de_pose.py"


def _lancer_garde(chemin_relatif):
    """Lance le garde sur un JSON PreToolUse et rend le motif, ou None."""
    charge = {
        "tool_name": "Write",
        "tool_input": {"file_path": chemin_relatif},
    }
    proc = subprocess.run(
        [sys.executable, GARDE],
        input=json.dumps(charge),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=RACINE,
    )
    if not proc.stdout.strip():
        return None
    try:
        sortie = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return None
    hook = sortie.get("hookSpecificOutput")
    if not isinstance(hook, dict):
        return None
    motif = hook.get("permissionDecisionReason")
    if not isinstance(motif, str):
        return None
    return motif


def _critere_cible_absente(motif):
    """Critere du CAS 2 : nomme nexus_creer.py ET porte les deux marqueurs."""
    if motif is None:
        return False
    if "nexus_creer.py" not in motif:
        return False
    if OUVERTURE not in motif:
        return False
    return FERMETURE in motif


def _verdict(numero, libelle, attendu, obtenu, ok):
    print("CAS %d -- %s" % (numero, libelle))
    print("  attendu : %s" % attendu)
    print("  obtenu  : %s" % obtenu)
    print("  verdict : %s" % ("OK" if ok else "ECHEC"))
    print()
    return ok


def cas1():
    motif = _lancer_garde(CIBLE_EXISTANTE)
    ok = (
        motif is not None
        and "nexus_appliquer.py" in motif
        and OUVERTURE not in motif
    )
    obtenu = "motif absent" if motif is None else motif.replace("\n", " | ")[:300]
    return _verdict(
        1,
        "garde, cible EXISTANTE",
        "le motif nomme nexus_appliquer.py et ne porte PAS le marqueur d'ouverture",
        obtenu,
        ok,
    )


def cas2():
    motif = _lancer_garde(CIBLE_ABSENTE)
    ok = _critere_cible_absente(motif)
    obtenu = "motif absent" if motif is None else motif.replace("\n", " | ")[:300]
    return _verdict(
        2,
        "garde, cible ABSENTE",
        "le motif nomme nexus_creer.py ET porte les DEUX marqueurs",
        obtenu,
        ok,
    )


def cas3():
    """nexus_appliquer sur une cible absente, sous la racine du depot."""
    dossier = tempfile.mkdtemp(prefix="epreuve_voies_")
    jsonl = os.path.join(dossier, "taches.jsonl")
    tache = "epreuve_voies_de_pose"
    bloc = (
        "<<" + "<AVANT" + CHEVRONS + "\n"
        "ligne_avant_inexistante\n"
        "<<" + "<APRES" + CHEVRONS + "\n"
        "ligne_apres\n"
        "<<" + "<FIN" + CHEVRONS + "\n"
    )
    enregistrement = {"nom": tache, "texte": bloc}
    with io.open(jsonl, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(enregistrement, ensure_ascii=False) + "\n")

    proc = subprocess.run(
        [sys.executable, APPLIQUER, jsonl, tache, CIBLE_ABSENTE],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=RACINE,
    )
    sortie = (proc.stdout or "") + (proc.stderr or "")
    ok = "nexus_creer.py" in sortie and OUVERTURE in sortie and FERMETURE in sortie
    obtenu = sortie.replace("\n", " | ")[:300] if sortie.strip() else "sortie vide"

    with contextlib.suppress(OSError):
        os.remove(jsonl)
    with contextlib.suppress(OSError):
        os.rmdir(dossier)

    return _verdict(
        3,
        "nexus_appliquer sur une cible ABSENTE",
        "la sortie nomme nexus_creer.py ET porte les DEUX marqueurs",
        obtenu,
        ok,
    )


def cas4():
    """Contre-epreuve : le critere doit ECHOUER sur un motif appauvri."""
    faux_motif = (
        "Le chemin est refuse. Appliquer le patch avec scripts/nexus_appliquer.py\n"
    )
    detecte = _critere_cible_absente(faux_motif)
    ok = not detecte
    return _verdict(
        4,
        "contre-epreuve, motif appauvri",
        "le critere du CAS 2 ECHOUE sur un motif qui ne nomme que nexus_appliquer.py",
        "critere %s" % ("a accepte le faux motif (epreuve sans valeur)" if detecte else "a rejete le faux motif"),
        ok,
    )


def cas5():
    """nexus_appliquer sur une cible HORS de tout depot."""
    dossier = tempfile.mkdtemp(prefix="epreuve_voies_hors_depot_")
    cible = os.path.join(dossier, "cible_hors_depot.txt")
    with io.open(cible, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("contenu initial\n")

    jsonl = os.path.join(dossier, "taches.jsonl")
    tache = "epreuve_voies_hors_depot"
    bloc = (
        "<<" + "<AVANT" + CHEVRONS + "\n"
        "contenu initial\n"
        "<<" + "<APRES" + CHEVRONS + "\n"
        "contenu remplace\n"
        "<<" + "<FIN" + CHEVRONS + "\n"
    )
    enregistrement = {"nom": tache, "texte": bloc}
    with io.open(jsonl, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(enregistrement, ensure_ascii=False) + "\n")

    proc = subprocess.run(
        [sys.executable, APPLIQUER, jsonl, tache, cible],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=RACINE,
    )
    sortie = (proc.stdout or "") + (proc.stderr or "")
    ok = "INTROUVABLE" in sortie and "hors racine du depot" not in sortie
    obtenu = sortie.replace("\n", " | ")[:300] if sortie.strip() else "sortie vide"

    with contextlib.suppress(OSError):
        os.remove(cible)
    with contextlib.suppress(OSError):
        os.remove(jsonl)
    with contextlib.suppress(OSError):
        os.rmdir(dossier)

    return _verdict(
        5,
        "nexus_appliquer sur une cible HORS de tout depot",
        "la sortie porte INTROUVABLE et ne se reduit pas au refus de perimetre",
        obtenu,
        ok,
    )


def cas6():
    """nexus_creer sur un marqueur d'ouverture AMPUTE, cible non creee."""
    dossier = tempfile.mkdtemp(prefix="epreuve_voies_ampute_")
    jsonl = os.path.join(dossier, "taches.jsonl")
    tache = "epreuve_voies_marqueur_ampute"
    ouverture_amputee = "<" * 3 + "CREER" + ">" * 2
    bloc = (
        ouverture_amputee + "\n"
        "print('contenu quelconque')\n"
        "<<" + "<FIN" + CHEVRONS + "\n"
    )
    enregistrement = {"nom": tache, "texte": bloc}
    with io.open(jsonl, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(enregistrement, ensure_ascii=False) + "\n")

    proc = subprocess.run(
        [sys.executable, CREER, jsonl, tache, CIBLE_ABSENTE],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=RACINE,
    )
    sortie = (proc.stdout or "") + (proc.stderr or "")
    cible_creee = os.path.exists(os.path.join(RACINE, CIBLE_ABSENTE))
    citation = "'" + ouverture_amputee + "'"
    mention_attendue = "marqueur attendu : " + OUVERTURE
    ok = citation in sortie and mention_attendue in sortie and not cible_creee
    obtenu = sortie.replace("\n", " | ")[:300] if sortie.strip() else "sortie vide"
    if cible_creee:
        obtenu = "cible creee malgre le refus | " + obtenu

    with contextlib.suppress(OSError):
        os.remove(jsonl)
    with contextlib.suppress(OSError):
        os.rmdir(dossier)
    with contextlib.suppress(OSError):
        os.remove(os.path.join(RACINE, CIBLE_ABSENTE))

    return _verdict(
        6,
        "nexus_creer sur un marqueur d'ouverture AMPUTE",
        "la sortie cite le marqueur ampute ENTRE APOSTROPHES et annonce le marqueur attendu, et la cible n'est PAS creee",
        obtenu,
        ok,
    )


def main():
    resultats = [cas1(), cas2(), cas3(), cas4(), cas5(), cas6()]
    reussis = sum(1 for r in resultats if r)
    print("CONCLUSION : %d cas reussis sur %d" % (reussis, len(resultats)))
    return 0 if reussis == len(resultats) else 1


if __name__ == "__main__":
    sys.exit(main())
