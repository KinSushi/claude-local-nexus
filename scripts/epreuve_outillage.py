#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

# Codes de retour reserves
CODE_OUTIL_INTROUVABLE = 127
CODE_TIMEOUT = 124

# Delai maximal par sous-processus (10 secondes)
TIMEOUT = 10

# Chemins et noms exacts lus dans le fichier
NOM_FICHIER_OUTIL = "scripts/nexus_outillage.py"
OPTIONS = [
    "--installer",
    "--cliquet",
    "--rebaseline",
    "--json"
]
ARG_POSITIONNELS = []  # Aucun argument positionnel dans le fichier
CODES_RETOUR = {
    "succes_aucun_outil_joue": 2,
    "succes_aucune_violation": 0,
    "succes_violations_trouvees": 1
}

def verifier_existence_outil():
    """Verifie que le fichier de l'outil existe. Si non, affiche le chemin cherche et rend 127."""
    if not Path(NOM_FICHIER_OUTIL).is_file():
        print(f"[ERREUR] Outil introuvable : {NOM_FICHIER_OUTIL}")
        sys.exit(CODE_OUTIL_INTROUVABLE)

def lancer_outil(args, cwd=None, timeout=TIMEOUT):
    """Lance l'outil en sous-processus avec sys.executable et un timeout strict."""
    cmd = [sys.executable, NOM_FICHIER_OUTIL] + args
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            timeout=timeout
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return CODE_TIMEOUT, "", "Timeout: l'outil n'a pas rendu la main dans le delai imparti"
    except Exception as e:
        return -1, "", f"Exception lors de l'execution : {str(e)}"

def verifier_sortie_erreur(code, stderr, motif_attendu):
    """Verifie que stderr contient le motif attendu et que le code est non nul."""
    if code == 0:
        return False
    return motif_attendu in stderr

def verifier_sortie_standard(stdout, motif_attendu):
    """Verifie que stdout contient le motif attendu."""
    return motif_attendu in stdout

def creer_fichier_temporaire(contenu, suffixe=""):
    """Cree un fichier temporaire avec le contenu donne et retourne son chemin."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=suffixe, delete=False, encoding="utf-8") as f:
        f.write(contenu)
        return f.name

def supprimer_fichier_temporaire(chemin):
    """Supprime un fichier temporaire si il existe."""
    try:
        os.unlink(chemin)
    except OSError:
        pass

def test_chemin_nominal():
    """Test nominal : l'outil s'execute sans arguments et rend un rapport."""
    verifier_existence_outil()
    with tempfile.TemporaryDirectory() as tmpdir:
        code, stdout, stderr = lancer_outil([], cwd=tmpdir)
        if code not in CODES_RETOUR.values():
            print("[ECHEC] NOMINAL : Code de retour inattendu", code)
            return False
        if "ruff" not in stdout or "eslint" not in stdout or "psscriptanalyzer" not in stdout:
            print("[ECHEC] NOMINAL : Sortie standard ne contient pas les outils attendus")
            return False
        print("[OK  ] NOMINAL")
        return True

def test_invocation_incomplete():
    """Test invocation incomplete : l'outil refuse sans arguments requis et rend l'usage."""
    verifier_existence_outil()
    with tempfile.TemporaryDirectory() as tmpdir:
        code, stdout, stderr = lancer_outil(["--rebaseline"], cwd=tmpdir)  # --rebaseline necessite --cliquet
        if code == 0:
            print("[ECHEC] INVOCATION_INCOMPLETE : Code de retour 0 alors qu'un refus etait attendu")
            return False
        if not verifier_sortie_erreur(code, stderr, "usage:"):
            print("[ECHEC] INVOCATION_INCOMPLETE : Stderr ne contient pas l'usage attendu")
            return False
        print("[OK  ] INVOCATION_INCOMPLETE")
        return True

def test_entree_malformee():
    """Test entree malformee : l'outil classe sans planter (JSON invalide via --json)."""
    verifier_existence_outil()
    chemin_json = creer_fichier_temporaire("contenu invalide", suffixe=".json")
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            code, stdout, stderr = lancer_outil(["--json", chemin_json], cwd=tmpdir)
            if code == CODE_TIMEOUT:
                print("[ECHEC] ENTREE_MALFORMEE : Timeout, l'outil n'a pas rendu la main")
                return False
            if "Erreur ecriture JSON" not in stderr:
                print("[ECHEC] ENTREE_MALFORMEE : Stderr ne contient pas le motif attendu pour une entree malformee")
                return False
            print("[OK  ] ENTREE_MALFORMEE")
            return True
    finally:
        supprimer_fichier_temporaire(chemin_json)

def test_refus_aggravation():
    """Test refus d'aggravation : le cliquet signale une hausse de violations."""
    verifier_existence_outil()
    # Creer une reference artificielle avec 0 violation
    reference = {
        "ruff": {"E9": 0, "F": 0},
        "eslint": {"no-undef": 0},
        "psscriptanalyzer": {"PSAvoidUsingEmptyCatchBlock": 0}
    }
    chemin_ref = creer_fichier_temporaire(json.dumps(reference), suffixe=".json")
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            # Simuler une aggravation en creant un fichier de reference avec 1 violation
            reference_aggravation = {
                "ruff": {"E9": 1, "F": 0},
                "eslint": {"no-undef": 0},
                "psscriptanalyzer": {"PSAvoidUsingEmptyCatchBlock": 0}
            }
            chemin_ref_aggravation = Path(tmpdir) / "outillage_reference.json"
            with open(chemin_ref_aggravation, "w", encoding="utf-8") as f:
                json.dump(reference_aggravation, f)

            # Lancer le cliquet
            code, stdout, stderr = lancer_outil(["--cliquet"], cwd=tmpdir)
            if code != 1:
                print("[ECHEC] REFUS_AGGRAVATION : Code de retour", code, "au lieu de 1")
                return False
            if "1 REGRESSION(S)" not in stdout:
                print("[ECHEC] REFUS_AGGRAVATION : Stdout ne contient pas le motif attendu pour une regression")
                return False
            print("[OK  ] REFUS_AGGRAVATION")
            return True
    finally:
        supprimer_fichier_temporaire(chemin_ref)

def test_baisse_non_signalee():
    """Test baisse non signalee : le cliquet ne signale pas une baisse de violations."""
    verifier_existence_outil()
    # Creer une reference artificielle avec 2 violations
    reference = {
        "ruff": {"E9": 2, "F": 0},
        "eslint": {"no-undef": 0},
        "psscriptanalyzer": {"PSAvoidUsingEmptyCatchBlock": 0}
    }
    chemin_ref = creer_fichier_temporaire(json.dumps(reference), suffixe=".json")
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            # Simuler une baisse en creant un fichier de reference avec 1 violation
            reference_baisse = {
                "ruff": {"E9": 1, "F": 0},
                "eslint": {"no-undef": 0},
                "psscriptanalyzer": {"PSAvoidUsingEmptyCatchBlock": 0}
            }
            chemin_ref_baisse = Path(tmpdir) / "outillage_reference.json"
            with open(chemin_ref_baisse, "w", encoding="utf-8") as f:
                json.dump(reference_baisse, f)

            # Lancer le cliquet
            code, stdout, stderr = lancer_outil(["--cliquet"], cwd=tmpdir)
            if code != 0:
                print("[ECHEC] BAISSE_NON_SIGNALEE : Code de retour", code, "au lieu de 0")
                return False
            if "aucune regression" not in stdout:
                print("[ECHEC] BAISSE_NON_SIGNALEE : Stdout ne contient pas le motif attendu pour aucune regression")
                return False
            print("[OK  ] BAISSE_NON_SIGNALEE")
            return True
    finally:
        supprimer_fichier_temporaire(chemin_ref)

def test_regle_neuve_non_comptee():
    """Test regle neuve non comptee : une regle absente de la reference n'est pas comptee comme regression."""
    verifier_existence_outil()
    # Creer une reference artificielle sans la regle neuve
    reference = {
        "ruff": {"E9": 0},
        "eslint": {"no-undef": 0},
        "psscriptanalyzer": {"PSAvoidUsingEmptyCatchBlock": 0}
    }
    chemin_ref = creer_fichier_temporaire(json.dumps(reference), suffixe=".json")
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            # Simuler une regle neuve en creant un fichier de reference avec une regle non presente avant
            reference_neuve = {
                "ruff": {"E9": 0, "B": 1},  # B est une regle neuve
                "eslint": {"no-undef": 0},
                "psscriptanalyzer": {"PSAvoidUsingEmptyCatchBlock": 0}
            }
            chemin_ref_neuve = Path(tmpdir) / "outillage_reference.json"
            with open(chemin_ref_neuve, "w", encoding="utf-8") as f:
                json.dump(reference_neuve, f)

            # Lancer le cliquet
            code, stdout, stderr = lancer_outil(["--cliquet"], cwd=tmpdir)
            if code != 0:
                print("[ECHEC] REGLE_NEUVE_NON_COMPTEE : Code de retour", code, "au lieu de 0")
                return False
            if "aucune regression" not in stdout:
                print("[ECHEC] REGLE_NEUVE_NON_COMPTEE : Stdout ne contient pas le motif attendu pour aucune regression")
                return False
            print("[OK  ] REGLE_NEUVE_NON_COMPTEE")
            return True
    finally:
        supprimer_fichier_temporaire(chemin_ref)

def main():
    """Lance tous les tests et rend un code non nul si un cas echoue."""
    verifier_existence_outil()

    tests = [
        test_chemin_nominal,
        test_invocation_incomplete,
        test_entree_malformee,
        test_refus_aggravation,
        test_baisse_non_signalee,
        test_regle_neuve_non_comptee
    ]

    resultats = []
    for test in tests:
        try:
            resultats.append(test())
        except Exception as e:
            print(f"[ECHEC] {test.__name__} : Exception non capturee - {str(e)}")
            resultats.append(False)

    if not all(resultats):
        sys.exit(1)

if __name__ == "__main__":
    main()
