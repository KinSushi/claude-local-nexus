# -*- coding: utf-8 -*-
"""Créer un nouveau fichier à partir d'un rendu JSONL.

Le script reproduit les mécanismes de sécurité de ``nexus_appliquer.py`` :
* découverte de la racine du dépôt,
* vérification que le chemin cible est bien sous cette racine,
* compilation du contenu Python avant écriture,
* exécution de ``ruff`` après écriture (pour les *.py*).

Aucun effet de bord n’est produit à l’import.
"""

import io
import json
import os
import sys
import subprocess
import contextlib
import nexus_rendu

with contextlib.suppress(Exception):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def _trouver_racine_depot(start_path: str) -> str:
    """Retourne le répertoire racine du dépôt à partir de ``start_path``.

    La logique est identique à celle de ``nexus_appliquer.py`` :
    on remonte jusqu’à trouver ``.git`` ou ``CLAUDE.md`` ; à défaut,
    on utilise le répertoire parent du script.
    """
    script_dir = os.path.dirname(os.path.realpath(__file__))
    racine = start_path
    while True:
        if any(os.path.exists(os.path.join(racine, marker)) for marker in (".git", "CLAUDE.md")):
            break
        parent = os.path.dirname(racine)
        if parent == racine:
            racine = os.path.dirname(script_dir)
            break
        racine = parent
    return racine


def _verifier_dans_racine(cible_path: str) -> bool:
    """Vérifie que ``cible_path`` est bien sous la racine du dépôt."""
    cible_real = os.path.realpath(cible_path)
    racine_depot = _trouver_racine_depot(os.path.dirname(cible_real))
    racine_real = os.path.realpath(racine_depot)
    try:
        commun = os.path.commonpath([cible_real, racine_real])
    except ValueError:
        return False
    return commun == racine_real


def _lancer_ruff(cible_path: str) -> None:
    """Recherche l’exécutable ``ruff`` dans le dépôt et l’exécute sur le fichier."""
    try:
        ruff_exe = None
        dir_actuel = os.path.dirname(os.path.abspath(cible_path))
        while dir_actuel != os.path.dirname(dir_actuel):
            for marqueur in [".git", ".nexus"]:
                if os.path.exists(os.path.join(dir_actuel, marqueur)):
                    if os.name == "nt":
                        cand = os.path.join(dir_actuel, ".nexus", "outillage", "ruff_venv", "Scripts", "ruff.exe")
                    else:
                        cand = os.path.join(dir_actuel, ".nexus", "outillage", "ruff_venv", "bin", "ruff")
                    if os.path.exists(cand):
                        ruff_exe = cand
                    break
            if ruff_exe:
                break
            dir_actuel = os.path.dirname(dir_actuel)

        if not ruff_exe:
            return  # aucun ruff trouvé, on ne signale rien

        args = [ruff_exe, "check", "--select", "E9,F,B,C4,SIM,RET", cible_path]
        proc = subprocess.Popen(
            args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        stdout, stderr = proc.communicate()
        if proc.returncode != 0 and stdout:
            print("[!] Violations détectées :\n%s" % stdout)
        if stderr:
            print("[!] L'analyseur n'a PAS PU se prononcer :\n%s" % stderr)
    except Exception:
        pass  # on ne fait jamais échouer le script à cause de ruff


def _extraire_contenu(texte: str) -> str | None:
    """Extrait le texte entre les marqueurs <<<CREER>>> et <<<FIN>>>."""
    lines = texte.splitlines()
    start_idx = None
    end_idx = None
    for i, line in enumerate(lines):
        if line.strip() == "<<<CREER>>>":
            start_idx = i
            continue
        if line.strip() == "<<<FIN>>>":
            end_idx = i
            break
    if start_idx is None or end_idx is None or end_idx <= start_idx:
        return None
    # on exclut les lignes de marqueurs
    return "\n".join(lines[start_idx + 1 : end_idx])


def main() -> int:
    if len(sys.argv) < 4:
        print("Usage: python nexus_creer.py <fichier_jsonl> <nom_tache> <fichier_cible>")
        return 2

    jsonl_path, nom_tache, cible_path = sys.argv[1], sys.argv[2], sys.argv[3]

    # --- Lecture du JSONL -------------------------------------------------
    texte = None
    try:
        with io.open(jsonl_path, encoding="utf-8") as fh:
            for num_ligne, ligne in enumerate(fh, start=1):
                ligne = ligne.strip()
                if not ligne:
                    continue
                try:
                    d = json.loads(ligne)
                except json.JSONDecodeError as e:
                    print(
                        "REFUS : ligne JSONL %d invalide ou tronquée dans '%s' : %s"
                        % (num_ligne, jsonl_path, e)
                    )
                    return 1
                if d.get("nom") == nom_tache:
                    texte = d.get("texte") or ""
                    # Defaut #8 mesure : de-encode les entites HTML SEULEMENT sans
                    # marqueur brut (sinon un &lt; legitime serait corrompu), et dit.
                    texte, deencode = nexus_rendu.deencoder_si_entites(texte)
                    if deencode:
                        print("NOTE : rendu aux entites HTML encodees (defaut #8), de-encode avant analyse.")
                    break
    except (FileNotFoundError, PermissionError, OSError) as e:
        print(f"ERREUR : impossible d'ouvrir le fichier JSONL '{jsonl_path}' : {e}")
        print("Usage: python nexus_creer.py <fichier_jsonl> <nom_tache> <fichier_cible>")
        return 1

    if texte is None:
        print("REFUS : aucune tache nommee %s dans %s" % (nom_tache, jsonl_path))
        return 1

    # --- Extraction du contenu à créer ------------------------------------
    contenu = _extraire_contenu(texte)
    if contenu is None:
        print(
            "REFUS : les marqueurs <<<CREER>>> et <<<FIN>>> sont manquants ou mal placés dans la tâche %s"
            % nom_tache
        )
        return 1

    # --- Vérifications préliminaires --------------------------------------
    if os.path.exists(cible_path):
        print(
            f"REFUS : le fichier cible '{cible_path}' existe déjà. Utilisez nexus_appliquer.py pour le modifier."
        )
        return 1

    if not _verifier_dans_racine(cible_path):
        print(
            f"REFUS : chemin refusé '{cible_path}' (hors racine du dépôt détectée)"
        )
        return 1

    # Vérification syntaxique pour les fichiers Python
    if cible_path.endswith(".py"):
        try:
            compile(contenu, "<string>", "exec")
        except SyntaxError as e:
            print(f"REFUS : le contenu proposé est syntaxiquement invalide : {e}")
            return 1

    # --- Création des répertoires parents ---------------------------------
    try:
        os.makedirs(os.path.dirname(cible_path) or ".", exist_ok=True)
    except (PermissionError, OSError) as e:
        print(f"REFUS : impossible de créer les répertoires parents de '{cible_path}' : {e}")
        return 1

    # --- Écriture atomique du fichier ------------------------------------
    temp_path = cible_path + ".tmp"
    try:
        with io.open(temp_path, "w", encoding="utf-8", newline="\n") as f:
            f.write(contenu)
        os.replace(temp_path, cible_path)
    except (PermissionError, OSError) as e:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        print(f"REFUS : impossible d'écrire '{cible_path}' ({e})")
        return 1
    except Exception:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        raise

    # --- Analyse ruff (pour les .py) --------------------------------------
    if cible_path.endswith(".py"):
        _lancer_ruff(cible_path)

    print(f"CREE : {cible_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
