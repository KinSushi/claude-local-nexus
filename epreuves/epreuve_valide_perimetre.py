#!/usr/bin/env python3
"""
Épreuve de validation du périmètre (`choisir_perimetre`) de `nexus_valide.py`.

Chaque cas doit être affiché sous la forme :

    [OK  ] nom_du_cas : détail
    [RATE] nom_du_cas : détail   (en cas d'échec)

Le script se termine avec le code de sortie 0 si tous les cas passent,
ou 1 dès le premier échec.
"""

import os
import sys
import subprocess
import tempfile
import shutil
import importlib.util

# ----------------------------------------------------------------------
# Helpers d'affichage
# ----------------------------------------------------------------------
def _print_ok(name, detail=""):
    print(f"[OK  ] {name} : {detail}")

def _print_rate(name, detail=""):
    print(f"[RATE] {name} : {detail}")

def _ok(cond, name, mesure=""):
    """Affiche le résultat d'un cas en réutilisant la même description
    que la condition soit vraie ou fausse."""
    if cond:
        _print_ok(name, mesure)
    else:
        _print_rate(name, mesure)
    return cond

# ----------------------------------------------------------------------
# Chargement du module `nexus_valide` sans exécuter son `main`
# ----------------------------------------------------------------------
def _load_nexus_valide(module_name, path):
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None:
        raise ImportError(f"Impossible de créer le spec pour {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        # nettoyage en cas d'échec
        sys.modules.pop(module_name, None)
        raise
    return module

# ----------------------------------------------------------------------
# Création d'un dépôt Git temporaire et préparation des commits C0 / C1
# ----------------------------------------------------------------------
def _init_repo():
    repo_dir = tempfile.mkdtemp()
    try:
        subprocess.run(["git", "init"], cwd=repo_dir, check=True, stdout=subprocess.DEVNULL)
        subprocess.run(["git", "config", "user.email", "e@e"], cwd=repo_dir, check=True)
        subprocess.run(["git", "config", "user.name", "e"], cwd=repo_dir, check=True)

        # C0 : a.py = "x = 1\n"
        a_path = os.path.join(repo_dir, "a.py")
        with open(a_path, "w", encoding="utf-8") as f:
            f.write("x = 1\n")
        subprocess.run(["git", "add", "a.py"], cwd=repo_dir, check=True)
        subprocess.run(["git", "commit", "-m", "C0"], cwd=repo_dir, check=True, stdout=subprocess.DEVNULL)
        c0_sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo_dir).decode().strip()

        # C1 : modification a.py et ajout gros.csv (≈70 000 caractères)
        with open(a_path, "w", encoding="utf-8") as f:
            f.write("x = 2\n")
        gros_path = os.path.join(repo_dir, "gros.csv")
        with open(gros_path, "w", encoding="utf-8") as f:
            f.write("0" * 70000)  # 70 000 caractères
        subprocess.run(["git", "add", "a.py", "gros.csv"], cwd=repo_dir, check=True)
        subprocess.run(["git", "commit", "-m", "C1"], cwd=repo_dir, check=True, stdout=subprocess.DEVNULL)
        c1_sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo_dir).decode().strip()

        return repo_dir, c0_sha, c1_sha
    except Exception:
        shutil.rmtree(repo_dir, ignore_errors=True)
        raise

# ----------------------------------------------------------------------
# Nettoyage robuste d'un répertoire (gestion du readonly sous Windows)
# ----------------------------------------------------------------------
def _on_rm_error(func, path, exc_info):
    try:
        os.chmod(path, 0o700)
        func(path)
    except Exception:
        pass

# ----------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------
def main():
    all_ok = True
    script_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "scripts"))
    nexus_path = os.path.join(script_dir, "nexus_valide.py")

    # Chargement du module original (corrigé)
    try:
        original_mod = _load_nexus_valide("_epreuve_nexus_valide", nexus_path)
        choisir_perimetre = original_mod.choisir_perimetre
    except Exception as exc:
        _print_rate("import", f"impossible d'importer nexus_valide : {exc}")
        sys.exit(1)

    # Création du dépôt temporaire
    try:
        repo_dir, C0_SHA, C1_SHA = _init_repo()
    except Exception as exc:
        _print_rate("repo_init", f"échec de l'initialisation du dépôt : {exc}")
        sys.exit(1)

    # Sauvegarde de la valeur originale de ROOT (s'il existe)
    original_root = getattr(original_mod, "ROOT", None)

    # ------------------------------------------------------------------
    # V1 – défaut 1 (fichier non suivi hors .py/.ps1)
    # ------------------------------------------------------------------
    try:
        untracked_path = os.path.join(repo_dir, "restes.avant-remplacement")
        with open(untracked_path, "w", encoding="utf-8") as f:
            f.write("quelque chose")

        original_mod.ROOT = repo_dir
        mode, fichiers, diff_text, message = choisir_perimetre(C0_SHA)

        cond = (
            mode == "base" and
            fichiers == ["a.py"] and
            "x = 2" in diff_text and
            "1 fichier" in message and
            ("ign" in message.lower() or "non suivi" in message.lower())
        )
        mesure = f"mode={mode} fichiers={fichiers} diff_contains='x = 2' message='{message}'"
        all_ok &= _ok(cond, "V1", mesure)
    except Exception as exc:
        all_ok &= _ok(False, "V1", f"exception : {exc}")

    # ------------------------------------------------------------------
    # V2 – défaut 2 (diff contenant gros.csv dépassant le plafond)
    # ------------------------------------------------------------------
    try:
        mode, fichiers, diff_text, message = choisir_perimetre(C0_SHA)

        cond = (
            "gros.csv" not in diff_text and
            len(diff_text) < 2000
        )
        mesure = f"diff_len={len(diff_text)} contains_gros={('gros.csv' in diff_text)}"
        all_ok &= _ok(cond, "V2", mesure)
    except Exception as exc:
        all_ok &= _ok(False, "V2", f"exception : {exc}")

    # ------------------------------------------------------------------
    # V3 – travail non commité (forward)
    # ------------------------------------------------------------------
    try:
        a_path = os.path.join(repo_dir, "a.py")
        with open(a_path, "w", encoding="utf-8") as f:
            f.write("x = 3\n")  # modification non commitée

        mode, fichiers, diff_text, message = choisir_perimetre(C0_SHA)

        cond = (
            mode == "non_commit" and
            fichiers == ["a.py"] and
            "x = 3" in diff_text
        )
        mesure = f"mode={mode} fichiers={fichiers} diff_contains='x = 3'"
        all_ok &= _ok(cond, "V3", mesure)
    except Exception as exc:
        all_ok &= _ok(False, "V3", f"exception : {exc}")

    # ------------------------------------------------------------------
    # V4 – périmètre sans code (base = HEAD même commit)
    # ------------------------------------------------------------------
    try:
        # remettre a.py à son état commité (x = 2)
        with open(a_path, "w", encoding="utf-8") as f:
            f.write("x = 2\n")

        mode, fichiers, diff_text, message = choisir_perimetre(C1_SHA)

        cond = (
            mode == "base" and
            fichiers == [] and
            diff_text == "" and
            "0 fichier" in message
        )
        mesure = f"mode={mode} fichiers={fichiers} diff_len={len(diff_text)} message='{message}'"
        all_ok &= _ok(cond, "V4", mesure)
    except Exception as exc:
        all_ok &= _ok(False, "V4", f"exception : {exc}")

    # ------------------------------------------------------------------
    # V5 – contre‑épreuve (ré‑introduction du défaut)
    # ------------------------------------------------------------------
    buggy_temp_dir = None
    try:
        with open(nexus_path, "r", encoding="utf-8") as f:
            source = f.read()

        target_line = "non_commit = _filter_allowed_files(get_modified_files_uncommitted())"
        replacement_line = "non_commit = get_modified_files_uncommitted()"

        if target_line not in source:
            all_ok &= _ok(False, "V5", "ligne cible non trouvée dans le source")
        else:
            buggy_source = source.replace(target_line, replacement_line)

            # écriture du module buggy dans un répertoire temporaire séparé
            buggy_temp_dir = tempfile.mkdtemp()
            buggy_path = os.path.join(buggy_temp_dir, "nexus_valide_bug.py")
            with open(buggy_path, "w", encoding="utf-8") as f:
                f.write(buggy_source)

            buggy_mod = _load_nexus_valide("_epreuve_nexus_valide_bug", buggy_path)
            choisir_perimetre_bug = buggy_mod.choisir_perimetre

            # recréer le fichier non suivi (au cas où il aurait été supprimé)
            with open(untracked_path, "w", encoding="utf-8") as f:
                f.write("quelque chose")

            buggy_mod.ROOT = repo_dir
            mode, fichiers, diff_text, message = choisir_perimetre_bug(C0_SHA)

            cond = mode == "non_commit"
            mesure = f"mode={mode} (attendu non_commit)"
            all_ok &= _ok(cond, "V5", mesure)
    except Exception as exc:
        all_ok &= _ok(False, "V5", f"exception : {exc}")
    finally:
        if buggy_temp_dir:
            shutil.rmtree(buggy_temp_dir, onerror=_on_rm_error, ignore_errors=True)

    # ------------------------------------------------------------------
    # V5b – même état, module corrigé doit rendre 'base'
    # ------------------------------------------------------------------
    try:
        # s'assurer que a.py est bien à la version committée
        with open(a_path, "w", encoding="utf-8") as f:
            f.write("x = 2\n")
        # le fichier non suivi existe déjà (restes.avant-remplacement)

        original_mod.ROOT = repo_dir
        mode, fichiers, diff_text, message = choisir_perimetre(C0_SHA)

        cond = mode == "base"
        mesure = f"mode={mode} (attendu base)"
        all_ok &= _ok(cond, "V5b", mesure)
    except Exception as exc:
        all_ok &= _ok(False, "V5b", f"exception : {exc}")

    # ------------------------------------------------------------------
    # Nettoyage
    # ------------------------------------------------------------------
    try:
        if original_root is not None:
            original_mod.ROOT = original_root
        else:
            delattr(original_mod, "ROOT")
    except Exception:
        pass

    shutil.rmtree(repo_dir, onerror=_on_rm_error, ignore_errors=True)

    sys.exit(0 if all_ok else 1)

if __name__ == "__main__":
    main()
