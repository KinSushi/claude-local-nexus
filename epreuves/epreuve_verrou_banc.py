# -*- coding: utf-8 -*-
"""Le verrou du banc doit MORDRE sur le local, et se taire sur le cloud.

Demande de la session sovereign-ai-system-8e le 2026-09-01, apres une
contention MESUREE : deux sessions s'etaient annoncees mutuellement le tour
local et se sont genees quand meme -- llava:13b et glm-4.7-flash occupant
31,6 Go, 8,0 Go libres sur 61,6, un essaim en demandant 15.

    Deux sessions de bonne foi peuvent respecter la convention chacune de son
    cote et se gener quand meme. Rien ne fait echouer une convention quand
    elle est violee, donc rien ne signale qu'elle l'est.

Ce que l'epreuve verifie, et l'ordre compte :

  1. ARMEMENT -- le mecanisme est-il branche ? Un `push()` au lieu d'un
     `enter_context()` n'entre PAS le contexte : le verrou ne serait jamais
     pris tout en ayant l'air de l'etre, et une epreuve differentielle
     rendrait alors une INFIRMATION FAUSSE du mecanisme. Le voisin a nomme
     ce piege avant de tomber dedans.
  2. REVERSE -- verrou deja tenu par un tiers, une tache LOCALE doit sortir
     en 75 et ne rien executer.
  3. FORWARD -- verrou deja tenu, une tache CLOUD doit passer : le cloud
     parallelise, le rendre exclusif serait une perte seche.

Aucun appel reseau n'est fait : les taches visent un modele inexistant, et
seul le CODE DE SORTIE est juge. Le verrou se decide avant tout appel.
"""
import io
import json
import os
import re
import subprocess
import sys
import tempfile

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LANCEUR = os.path.join(RACINE, "scripts", "nexus_agent.py")
VERROU = os.path.join(RACINE, "scripts", "nexus_verrou_machine.py")
CODE_REFUS = 75


def _dire(ok, nom, detail):
    print("%s %s : %s" % ("[OK  ]" if ok else "[RATE]", nom, detail))
    return ok


def _armement():
    """Le mecanisme est-il BRANCHE, et non seulement present ?"""
    with io.open(LANCEUR, encoding="utf-8") as fh:
        source = fh.read()
    manques = []
    for nom, motif in (
        ("import contextlib", r"^import contextlib$"),
        ("import du verrou", r"from nexus_verrou_machine import verrou"),
        ("enter_context", r"pile_verrou\.enter_context\(verrou\("),
        ("refus 75", r"return 75"),
        ("liberation", r"pile_verrou\.close\(\)"),
    ):
        if not re.search(motif, source, re.M):
            manques.append(nom)
    if "pile_verrou.push(" in source:
        manques.append("push() employe la ou enter_context est requis")
    return manques


def _lot(chemin, modele):
    with io.open(chemin, "w", encoding="utf-8", newline="\n") as fh:
        json.dump([{"nom": "t", "modele": modele, "tache": "peu importe",
                    "max_tokens": 100}], fh)
    return chemin


def _lancer(lot):
    """Lance le lanceur sur un lot, rend son code de sortie."""
    env = os.environ.copy()
    # L'attente est mise a zero pour que la contention se manifeste en REFUS
    # immediat plutot qu'en attente, et qu'une epreuve doit porter ses propres conditions.
    env["NEXUS_VERROU_ATTENTE_S"] = "0"
    return subprocess.run([sys.executable, LANCEUR, "--lot", lot],
                          capture_output=True, text=True, timeout=180, env=env).returncode


def main():
    manques = _armement()
    if not _dire(not manques, "le mecanisme est ARME",
                 "manque : " + ", ".join(manques) if manques else "tout est branche"):
        # Sans armement, les deux epreuves suivantes ne prouveraient rien :
        # un verrou qui ne peut pas mordre ne mord pas, et cela ne dit rien
        # de la protection.
        return 1

    code = 0
    with tempfile.TemporaryDirectory() as tmp:
        local = _lot(os.path.join(tmp, "local.json"), "modele-inexistant-local")
        cloud = _lot(os.path.join(tmp, "cloud.json"), "modele-inexistant-cloud")

        # Un tiers tient le verrou pendant toute la duree des deux essais.
        tenant = subprocess.Popen(
            [sys.executable, "-c",
             "import sys; sys.path.insert(0, %r);"
             "import nexus_verrou_machine as v;"
             "import time;"
             "ctx = v.verrou('banc', projet='epreuve', attente_s=0, bavard=False);"
             "ctx.__enter__(); print('tenu', flush=True); time.sleep(60)"
             % os.path.join(RACINE, "scripts")],
            stdout=subprocess.PIPE, text=True)
        try:
            if tenant.stdout.readline().strip() != "tenu":
                return _dire(False, "un tiers tient le verrou", "il ne l'a pas pris") or 1

            # REVERSE : le local doit etre REFUSE, proprement.
            rc = _lancer(local)
            if not _dire(rc == CODE_REFUS, "une tache LOCALE est refusee",
                         "code %d (attendu %d)" % (rc, CODE_REFUS)):
                code = 1

            # FORWARD : le cloud doit passer. Il echouera sur un modele
            # inexistant, mais avec un code AUTRE que le refus de verrou --
            # c'est la distinction qui prouve que le verrou ne l'a pas bloque.
            rc = _lancer(cloud)
            if not _dire(rc != CODE_REFUS, "une tache CLOUD n'est pas bloquee",
                         "code %d (le refus %d serait faux ici)" % (rc, CODE_REFUS)):
                code = 1
        finally:
            tenant.kill()
            tenant.wait(timeout=10)

    return code


if __name__ == "__main__":
    sys.exit(main())
