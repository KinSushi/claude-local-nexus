#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import os
import subprocess
import sys
import tempfile
import time

def verifier_fichier_outil():
    chemin_outil = os.path.join("scripts", "nexus_garde_lecture.py")
    if not os.path.exists(chemin_outil):
        print(f"[ERREUR] Fichier de l'outil introuvable : {chemin_outil}")
        sys.exit(3)

def lancer_epreuve(cas, entree, attendu, code_attendu=None):
    with tempfile.NamedTemporaryFile(mode="w+", encoding="utf-8", delete=False) as f_entree:
        json.dump(entree, f_entree)
        f_entree.flush()

        try:
            cmd = [sys.executable, os.path.join("scripts", "nexus_garde_lecture.py")]
            debut = time.time()
            resultat = subprocess.run(
                cmd,
                stdin=open(f_entree.name, "r", encoding="utf-8"),
                capture_output=True,
                text=True,
                timeout=10
            )
            duree = time.time() - debut
        except subprocess.TimeoutExpired:
            print(f"[{cas}] ECHEC - Timeout apres {duree:.1f}s")
            os.unlink(f_entree.name)
            return False
        finally:
            os.unlink(f_entree.name)

    if code_attendu is not None and resultat.returncode != code_attendu:
        print(f"[{cas}] ECHEC - Code retour {resultat.returncode}, attendu {code_attendu}")
        return False

    if attendu is None:
        return True

    try:
        sortie = json.loads(resultat.stdout)
    except json.JSONDecodeError:
        print(f"[{cas}] ECHEC - Sortie non JSON : {resultat.stdout}")
        return False

    if "hookSpecificOutput" not in sortie:
        print(f"[{cas}] ECHEC - Structure de sortie inattendue : {resultat.stdout}")
        return False

    motif = sortie["hookSpecificOutput"].get("permissionDecisionReason", "")
    if attendu not in motif:
        print(f"[{cas}] ECHEC - Motif absent : {motif}")
        return False

    return True

def creer_fichier_test():
    with tempfile.NamedTemporaryFile(mode="w+", encoding="utf-8", delete=False) as f:
        f.write("contenu test")
        return f.name

def main():
    verifier_fichier_outil()

    # Cas 1 : Ecriture legitime (fichier lu puis ecrit)
    fichier_test = creer_fichier_test()
    try:
        entree_lecture = {
            "tool_name": "Read",
            "tool_input": {"file_path": fichier_test},
            "session_id": "session1"
        }
        if not lancer_epreuve("LECTURE", entree_lecture, None):
            print("[LECTURE] ECHEC")
            sys.exit(1)

        entree_ecriture = {
            "tool_name": "Write",
            "tool_input": {"file_path": fichier_test},
            "session_id": "session1"
        }
        if not lancer_epreuve("ECRITURE_LEGITIME", entree_ecriture, None):
            print("[ECRITURE_LEGITIME] ECHEC")
            sys.exit(1)
        print("[ECRITURE_LEGITIME] OK")
    finally:
        os.unlink(fichier_test)

    # Cas 2 : Ecriture refusee (fichier non lu)
    fichier_test = creer_fichier_test()
    try:
        entree_refus = {
            "tool_name": "Write",
            "tool_input": {"file_path": fichier_test},
            "session_id": "session2"
        }
        if not lancer_epreuve("REFUS", entree_refus, "REFUS -- LIRE AVANT D'ECRIRE"):
            print("[REFUS] ECHEC")
            sys.exit(1)
        print("[REFUS] OK")
    finally:
        os.unlink(fichier_test)

    # Cas 3 : Creation de fichier (autorisee sans lecture)
    with tempfile.NamedTemporaryFile(delete=False) as f:
        fichier_inexistant = f.name
    try:
        entree_creation = {
            "tool_name": "Write",
            "tool_input": {"file_path": fichier_inexistant},
            "session_id": "session3"
        }
        if not lancer_epreuve("CREATION", entree_creation, None):
            print("[CREATION] ECHEC")
            sys.exit(1)
        print("[CREATION] OK")
    finally:
        if os.path.exists(fichier_inexistant):
            os.unlink(fichier_inexistant)

    # Cas 4 : Outil non gere (ne doit rien faire)
    entree_inconnu = {
        "tool_name": "UnknownTool",
        "tool_input": {"file_path": "dummy.txt"},
        "session_id": "session4"
    }
    if not lancer_epreuve("OUTIL_INCONNU", entree_inconnu, None):
        print("[OUTIL_INCONNU] ECHEC")
        sys.exit(1)
    print("[OUTIL_INCONNU] OK")

    # Cas 5 : Entree malformee (ne doit rien faire)
    if not lancer_epreuve("ENTREE_MALFORMEE", "texte non json", None):
        print("[ENTREE_MALFORMEE] ECHEC")
        sys.exit(1)
    print("[ENTREE_MALFORMEE] OK")

    # Cas 6 : Appel sans arguments requis (doit rendre usage)
    try:
        cmd = [sys.executable, os.path.join("scripts", "nexus_garde_lecture.py")]
        resultat = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if resultat.returncode == 0:
            print("[USAGE] ECHEC - Code retour 0 au lieu de non nul")
            sys.exit(1)
        print("[USAGE] OK")
    except subprocess.TimeoutExpired:
        print("[USAGE] ECHEC - Timeout")
        sys.exit(1)

    # Cas 7 : Commande shell avec redirection (journalisation)
    entree_shell = {
        "tool_name": "Bash",
        "tool_input": {"command": f"echo test > {tempfile.gettempdir()}/test_shell.txt"},
        "session_id": "session5"
    }
    if not lancer_epreuve("SHELL_JOURNAL", entree_shell, None):
        print("[SHELL_JOURNAL] ECHEC")
        sys.exit(1)

    # Verifier que le journal a ete ecrit
    journal_path = os.path.join("scripts", "..", ".nexus", "ecritures_shell.jsonl")
    if not os.path.exists(journal_path):
        print("[SHELL_JOURNAL] ECHEC - Fichier journal non cree")
        sys.exit(1)

    with open(journal_path, "r", encoding="utf-8") as f:
        lignes = f.readlines()
        if not any("test_shell.txt" in ligne for ligne in lignes):
            print("[SHELL_JOURNAL] ECHEC - Commande non journalisee")
            sys.exit(1)
    print("[SHELL_JOURNAL] OK")

    print("[TOUS_CAS_OK]")

if __name__ == "__main__":
    main()
