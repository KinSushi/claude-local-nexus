#!/usr/bin/env python3
import os
import sys
import subprocess
import time
from pathlib import Path

# Codes de retour reserves
CODE_OUTIL_ABSENT = 127
CODE_ECHEC_TEST = 1

def verifier_existence_outil():
    chemin = Path("scripts/nexus_secours.py")
    if not chemin.exists():
        print(f"[ERREUR] Outil introuvable : {chemin.absolute()}")
        return False
    return True

def lister_fichiers(repertoire):
    return {f for f in repertoire.iterdir() if f.is_file()}

def executer_test(args, timeout=90, capture_sortie=True):
    cmd = [sys.executable, "scripts/nexus_secours.py"] + args
    try:
        resultat = subprocess.run(
            cmd,
            timeout=timeout,
            capture_output=capture_sortie,
            text=True,
            check=False
        )
        return resultat.returncode, resultat.stdout, resultat.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "Timeout"

def test_1_sortie_non_vide():
    code, stdout, stderr = executer_test([])
    if code != 0:
        print("[FAIL] Test 1 - Code retour non nul sans argument")
        return False
    if not stdout.strip():
        print("[FAIL] Test 1 - Sortie vide sans argument")
        return False
    if "moteur" not in stdout.lower():
        print("[FAIL] Test 1 - Sortie ne mentionne pas le moteur")
        return False
    print("[OK] Test 1 - Sortie non vide mentionnant le moteur")
    return True

def test_2_moteur_injoignable():
    # Verifier si l'outil accepte une option ou variable pour l'adresse
    code, stdout, stderr = executer_test(["--help"], capture_sortie=True)
    if "--adresse" in stdout or "--url" in stdout:
        adresse_test = "http://192.0.2.1:9999"  # RFC 5737 - adresse test
        code, stdout, stderr = executer_test(["--adresse", adresse_test], timeout=10)
    elif "NEXUS_MOTEUR_URL" in os.environ or "NEXUS_ADRESSE" in os.environ:
        var = "NEXUS_MOTEUR_URL" if "NEXUS_MOTEUR_URL" in os.environ else "NEXUS_ADRESSE"
        adresse_originale = os.environ.get(var)
        os.environ[var] = "http://192.0.2.1:9999"
        try:
            code, stdout, stderr = executer_test([], timeout=10)
        finally:
            if adresse_originale is not None:
                os.environ[var] = adresse_originale
            else:
                os.environ.pop(var, None)
    else:
        print("[INFO] Test 2 - Outil ne semble pas accepter d'adresse detournee")
        return True  # On ne peut pas tester, mais ce n'est pas un echec

    if code == 0:
        print("[FAIL] Test 2 - Code retour nul avec moteur injoignable")
        return False
    if not stdout.strip() and not stderr.strip():
        print("[FAIL] Test 2 - Aucune sortie avec moteur injoignable")
        return False
    if "injoignable" not in stdout.lower() and "injoignable" not in stderr.lower():
        print("[FAIL] Test 2 - Sortie ne mentionne pas l'injoignabilite")
        return False
    print("[OK] Test 2 - Moteur injoignable correctement rapporte")
    return True

def test_3_aucun_fichier_ecrit():
    repertoire = Path(".")
    fichiers_avant = lister_fichiers(repertoire)
    code, stdout, stderr = executer_test([], timeout=10)
    fichiers_apres = lister_fichiers(repertoire)

    if fichiers_avant != fichiers_apres:
        nouveaux = fichiers_apres - fichiers_avant
        print(f"[FAIL] Test 3 - Fichiers ecrits : {', '.join(str(f) for f in nouveaux)}")
        return False

    # Verifier aussi les dates de modification
    for f in fichiers_avant:
        if f.stat().st_mtime > time.time() - 10:  # Modifie dans les 10 dernieres secondes
            print(f"[FAIL] Test 3 - Fichier modifie : {f}")
            return False

    print("[OK] Test 3 - Aucun fichier ecrit ou modifie")
    return True

def test_4_delai_respecte():
    # Verifier si l'outil accepte une option de delai
    code, stdout, stderr = executer_test(["--help"], capture_sortie=True)
    if "--delai" in stdout or "--timeout" in stdout:
        delai_court = "1"
        debut = time.time()
        code, stdout, stderr = executer_test(["--delai", delai_court], timeout=15)
        duree = time.time() - debut
        if duree > 10:
            print(f"[FAIL] Test 4 - Delai non respecte : {duree:.1f}s")
            return False
    else:
        print("[INFO] Test 4 - Outil ne semble pas accepter d'option de delai")
        return True  # On ne peut pas tester, mais ce n'est pas un echec

    print("[OK] Test 4 - Delai respecte")
    return True

def main():
    if not verifier_existence_outil():
        sys.exit(CODE_OUTIL_ABSENT)

    tests = [
        test_1_sortie_non_vide,
        test_2_moteur_injoignable,
        test_3_aucun_fichier_ecrit,
        test_4_delai_respecte,
    ]

    echecs = 0
    for test in tests:
        if not test():
            echecs += 1

    if echecs > 0:
        print(f"[ECHEC] {echecs} test(s) en echec")
        sys.exit(CODE_ECHEC_TEST)
    else:
        print("[SUCCES] Tous les tests passes")
        sys.exit(0)

if __name__ == "__main__":
    main()
