#!/usr/bin/env python3
import os
import sys
import tempfile
import shutil
import subprocess
import time
from pathlib import Path

# Codes réservés
CODE_FICHIER_ABSENT = 100
CODE_RACINE_MANQUANTE = 101
CODE_TEMP_DIR_ECRITURE = 102

# Délai maximal par sous-processus (60s)
TIMEOUT = 60

def creer_fichiers_temporaires(repertoire: Path, nombre: int) -> list[Path]:
    """Crée des fichiers Python valides dans un répertoire temporaire."""
    fichiers = []
    for i in range(nombre):
        chemin = repertoire / f"test_{i}.py"
        chemin.write_text(
            f"# Fichier test {i}\n"
            f"def fonction_{i}():\n"
            f"    return {i}\n"
            f"# Ligne supplémentaire pour atteindre {LIGNES_MIN} lignes\n"
            + "\n".join(f"# Ligne {j}" for j in range(30))
        )
        fichiers.append(chemin)
    return fichiers

def verifier_integrite_repertoire(repertoire: Path, fichiers_initiaux: set) -> bool:
    """Vérifie qu'aucun fichier n'a été créé/modifié hors ceux déclarés."""
    fichiers_finaux = set(repertoire.rglob("*"))
    fichiers_finaux = {f for f in fichiers_finaux if f.is_file()}

    # Fichiers déclarés par l'outil (ex: .nexus/ruche-etat.json)
    fichiers_attendus = {
        repertoire / ".nexus" / "ruche-etat.json",
        repertoire / ".nexus"
    }

    # Fichiers initiaux + fichiers attendus
    fichiers_autorises = fichiers_initiaux.union(fichiers_attendus)

    # Vérifier qu'aucun fichier non autorisé n'existe
    fichiers_non_autorises = fichiers_finaux - fichiers_autorises
    if fichiers_non_autorises:
        print(f"[ERREUR] Fichiers non autorisés créés/modifiés: {fichiers_non_autorises}")
        return False

    # Vérifier que les fichiers attendus existent bien
    fichiers_manquants = fichiers_attendus - fichiers_finaux
    if fichiers_manquants:
        print(f"[ERREUR] Fichiers attendus manquants: {fichiers_manquants}")
        return False

    return True

def executer_cas(nom: str, args: list, repertoire: Path, fichiers_initiaux: set = None) -> int:
    """Exécute un cas de test et retourne le code de sortie."""
    print(f"[{nom}] Début")

    # Vérifier que le script existe
    script = Path("scripts/nexus_ruche.py")
    if not script.is_file():
        print(f"[FAIL] Script introuvable: {script.absolute()}")
        return CODE_FICHIER_ABSENT

    # Préparer la commande
    cmd = [sys.executable, str(script)] + args

    # Exécuter
    try:
        start = time.time()
        result = subprocess.run(
            cmd,
            cwd=repertoire,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=TIMEOUT
        )
        duree = time.time() - start
    except subprocess.TimeoutExpired:
        print(f"[{nom}] Timeout après {TIMEOUT}s")
        return 2

    # Vérifier l'intégrité du répertoire si demandé
    if fichiers_initiaux is not None:
        if not verifier_integrite_repertoire(repertoire, fichiers_initiaux):
            return CODE_TEMP_DIR_ECRITURE

    # Afficher la sortie pour analyse
    print(result.stdout)
    if result.stderr:
        print(f"[STDERR] {result.stderr}")

    # Vérifier le contenu spécifique
    if nom == "DEUX":
        if "2 cibles decouvertes" not in result.stdout:
            print(f"[{nom}] Nombre de cibles incohérent")
            return 1
    elif nom == "TROIS":
        if "Aucune cible a traiter" not in result.stdout:
            print(f"[{nom}] Répertoire vide non détecté")
            return 1
    elif nom == "QUATRE":
        if "3 cibles decouvertes" not in result.stdout:
            print(f"[{nom}] Limite de cibles non respectée")
            return 1
    elif nom == "CINQ":
        if result.returncode == 0:
            print(f"[{nom}] Valeur invalide non rejetée")
            return 1
        if "cloud" not in result.stderr and "local" not in result.stderr and "deux" not in result.stderr:
            print(f"[{nom}] Message d'erreur incomplet")
            return 1

    print(f"[{nom}] Terminé en {duree:.1f}s (code={result.returncode})")
    return result.returncode

def main():
    # Cas UN : Vérifier l'existence du script
    script = Path("scripts/nexus_ruche.py")
    if not script.is_file():
        print(f"[UN] Script introuvable: {script.absolute()}")
        return CODE_FICHIER_ABSENT

    # Préparer un répertoire temporaire
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Créer une structure minimale
        (temp_path / "scripts").mkdir(parents=True)
        (temp_path / "tools" / "nexus-mcp").mkdir(parents=True, exist_ok=True)

        # Enregistrer les fichiers initiaux
        fichiers_initiaux = set(temp_path.rglob("*"))
        fichiers_initiaux = {f for f in fichiers_initiaux if f.is_file()}

        # Cas DEUX : Simulation avec 2 fichiers
        creer_fichiers_temporaires(temp_path / "scripts", 2)
        code = executer_cas(
            "DEUX",
            ["--racine", str(temp_path), "--simuler"],
            temp_path,
            fichiers_initiaux
        )
        if code != 0:
            return code

        # Cas TROIS : Répertoire vide
        code = executer_cas(
            "TROIS",
            ["--racine", str(temp_path), "--simuler"],
            temp_path,
            fichiers_initiaux
        )
        if code != 0:
            return code

        # Cas QUATRE : Limite de cibles
        creer_fichiers_temporaires(temp_path / "scripts", 5)
        code = executer_cas(
            "QUATRE",
            ["--racine", str(temp_path), "--simuler", "--max-cibles", "3"],
            temp_path,
            fichiers_initiaux
        )
        if code != 0:
            return code

        # Cas CINQ : Valeur invalide pour --plans
        code = executer_cas(
            "CINQ",
            ["--racine", str(temp_path), "--simuler", "--plans", "invalide"],
            temp_path
        )
        if code == 0:
            return 1

        # Cas SIX : Vérification de l'intégrité du répertoire
        # (déjà vérifiée dans chaque cas via fichiers_initiaux)

    return 0

if __name__ == "__main__":
    # Constante LIGNES_MIN utilisée dans le script testé
    LIGNES_MIN = 30
    sys.exit(main())
