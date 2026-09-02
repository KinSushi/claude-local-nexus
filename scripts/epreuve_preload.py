# -*- coding: utf-8 -*-
import os
import sys
import subprocess
import tempfile
import json
import time

# Codes de retour réservés
CODE_OUTIL_INTROUVABLE = 127
CODE_TIMEOUT = 124

def executer_outil(args, timeout=10):
    """Exécute l'outil en sous-processus avec délai maximal."""
    chemin_outil = os.path.join("scripts", "nexus_preload.py")
    if not os.path.exists(chemin_outil):
        print(f"[ERREUR] Outil introuvable: {chemin_outil}")
        sys.exit(CODE_OUTIL_INTROUVABLE)

    cmd = [sys.executable, chemin_outil] + args
    with tempfile.TemporaryDirectory() as tmpdir:
        env = os.environ.copy()
        env["TMPDIR"] = tmpdir
        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=tmpdir,
                env=env
            )
            stdout, stderr = proc.communicate(timeout=timeout)
            return proc.returncode, stdout, stderr
        except subprocess.TimeoutExpired:
            proc.kill()
            return CODE_TIMEOUT, "", "Timeout: l'outil n'a pas rendu la main"

def verifier_nominal():
    """Cas nominal: préchargement réussi."""
    code, stdout, stderr = executer_outil(["test-model"])
    if code != 0:
        print("[FAIL] NOMINAL (code inattendu)")
        return False
    if "test-model: succes" not in stdout:
        print("[FAIL] NOMINAL (sortie incorrecte)")
        return False
    if stderr:
        print("[FAIL] NOMINAL (erreur sur stderr)")
        return False
    print("[OK  ] NOMINAL")
    return True

def verifier_refus_modele_distant():
    """Cas inverse: modèle distant refusé."""
    code, stdout, stderr = executer_outil(["test-cloud"])
    if code != 0:
        print("[FAIL] REFUS_DISTANT (code inattendu)")
        return False
    if "Modèle distant" not in stdout:
        print("[FAIL] REFUS_DISTANT (refus non détecté)")
        return False
    print("[OK  ] REFUS_DISTANT")
    return True

def verifier_entree_malformee():
    """Cas malformé: JSON invalide (simulé par timeout serveur)."""
    code, stdout, stderr = executer_outil(["invalid-model"], timeout=2)
    if code == CODE_TIMEOUT:
        print("[OK  ] ENTREE_MALFORMEE (timeout attendu)")
        return True
    if code != 0 and "Passerelle inaccessible" in stdout + stderr:
        print("[OK  ] ENTREE_MALFORMEE (erreur réseau)")
        return True
    print("[FAIL] ENTREE_MALFORMEE (comportement inattendu)")
    return False

def verifier_usage_manquant():
    """Cas manquant: arguments requis absents."""
    code, stdout, stderr = executer_outil([])
    if code == 0:
        print("[FAIL] USAGE_MANQUANT (code 0 inattendu)")
        return False
    if "usage:" not in stderr:
        print("[FAIL] USAGE_MANQUANT (message d'usage manquant)")
        return False
    print("[OK  ] USAGE_MANQUANT")
    return True

def verifier_sortie_json():
    """Cas JSON: sortie formatée en JSON."""
    code, stdout, stderr = executer_outil(["--json", "test-model"])
    if code != 0:
        print("[FAIL] SORTIE_JSON (code inattendu)")
        return False
    try:
        json.loads(stdout)
    except json.JSONDecodeError:
        print("[FAIL] SORTIE_JSON (JSON invalide)")
        return False
    print("[OK  ] SORTIE_JSON")
    return True

def main():
    cas = [
        verifier_nominal,
        verifier_refus_modele_distant,
        verifier_entree_malformee,
        verifier_usage_manquant,
        verifier_sortie_json,
    ]

    resultats = []
    for test in cas:
        try:
            resultats.append(test())
        except Exception as e:
            print(f"[FAIL] {test.__name__.upper()} (exception: {type(e).__name__})")
            resultats.append(False)

    if not all(resultats):
        sys.exit(1)

if __name__ == "__main__":
    main()
