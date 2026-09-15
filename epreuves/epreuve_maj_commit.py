# -*- coding: utf-8 -*-
"""Épreuve fonctionnelle pour la fonction PowerShell Save-FichiersGeneres
du script scripts/Update-NexusModels.ps1.

Protocole similaire à epreuve_start_moteur.py : une ligne [OK  ] ou [RATE]
par cas, sortie 1 si un cas RATE.
"""

import os
import pathlib
import shutil
import subprocess
import sys
import tempfile

def _on_rm_error(func, path, exc_info):
    """Gestion d'erreur lors de la suppression de fichiers en lecture seule."""
    try:
        os.chmod(path, 0o700)
        func(path)
    except Exception:
        pass

def _git(*args, cwd):
    """Exécute une commande git et renvoie stdout décodé."""
    result = subprocess.run(['git'] + list(args), cwd=cwd,
                           capture_output=True, text=True, encoding='utf-8')
    if result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout.strip()

def main():
    racine = pathlib.Path(__file__).resolve().parents[1]
    script_ps1 = racine / "scripts" / "Update-NexusModels.ps1"
    ok_global = True

    # 1. Extraction de la fonction Save-FichiersGeneres
    try:
        with open(script_ps1, 'r', encoding='utf-8') as f:
            lignes = f.readlines()
    except Exception as e:
        print(f"[RATE] lecture_ps1 : {e}")
        sys.exit(1)

    debut = fin = -1
    for i, ligne in enumerate(lignes):
        if ligne.strip() == "function Save-FichiersGeneres {":
            debut = i
        elif debut != -1 and ligne.rstrip("\r\n") == "}":
            fin = i
            break

    if debut == -1 or fin == -1:
        print("[RATE] extraction_fonction : fonction introuvable")
        sys.exit(1)

    texte_fonction = ''.join(lignes[debut:fin + 1])

    # 2. Recherche de pwsh ou powershell
    pwsh = shutil.which('pwsh') or shutil.which('powershell')
    if not pwsh:
        print("[RATE] pwsh : introuvable")
        sys.exit(1)

    # 3. Cas de test
    cas = [
        # (nom, setup_callable, verif_callable)
        ("C1", lambda repo: None,  # aucun changement
         lambda repo, result, before_cnt: (
             result.startswith("RIEN") and
             _git('rev-list', '--count', 'HEAD', cwd=repo) == before_cnt
         )),
        ("C2", lambda repo: (
            # modifier README.md
            pathlib.Path(repo, "README.md").write_text("modifié\n", encoding='utf-8')
        ),
         lambda repo, result, before_cnt: (
             result.startswith("COMMIT") and
             int(_git('rev-list', '--count', 'HEAD', cwd=repo)) == int(before_cnt) + 1 and
             _git('status', '--porcelain', '--', 'README.md', cwd=repo) == ""
         )),
        ("C3", lambda repo: (
            # modifier README.md
            pathlib.Path(repo, "README.md").write_text("modifié C3\n", encoding='utf-8'),
            # créer et indexer autre.txt
            pathlib.Path(repo, "autre.txt").write_text("contenu\n", encoding='utf-8'),
            subprocess.run(['git', 'add', 'autre.txt'], cwd=repo,
                           capture_output=True, text=True, check=True)
        ),
         lambda repo, result, before_cnt: (
             result.startswith("COMMIT") and
             int(_git('rev-list', '--count', 'HEAD', cwd=repo)) == int(before_cnt) + 1 and
             set(_git('show', '--name-only', '--format=', 'HEAD', cwd=repo).splitlines()) == {"README.md"} and
             _git('diff', '--cached', '--name-only', cwd=repo).strip() == "autre.txt"
         )),
        ("C4", lambda repo: None,  # dépôt invalide
         lambda repo, result, _: (
             result.startswith("ECHEC")
         )),
    ]

    temp_dirs = []  # pour nettoyage global
    try:
        for nom, setup, verif in cas:
            # création d'un dépôt git temporaire (ou répertoire vide pour C4)
            repo_dir = tempfile.mkdtemp(prefix='epreuve_maj_commit_')
            temp_dirs.append(repo_dir)

            # initialisation du dépôt (sauf C4 où on garde vide)
            if nom != "C4":
                subprocess.run(['git', 'init'], cwd=repo_dir,
                               capture_output=True, check=True)
                subprocess.run(['git', 'config', 'user.email', 'e@e'],
                               cwd=repo_dir, capture_output=True, check=True)
                subprocess.run(['git', 'config', 'user.name', 'e'],
                               cwd=repo_dir, capture_output=True, check=True)

                # fichiers initiaux
                pathlib.Path(repo_dir, "README.md").write_text("initial\n", encoding='utf-8')
                pathlib.Path(repo_dir, "litellm_config.yaml").write_text("config: true\n", encoding='utf-8')
                subprocess.run(['git', 'add', '.'], cwd=repo_dir,
                               capture_output=True, check=True)
                subprocess.run(['git', 'commit', '-m', 'init'], cwd=repo_dir,
                               capture_output=True, check=True)

            # état avant appel
            before_cnt = _git('rev-list', '--count', 'HEAD', cwd=repo_dir) if os.path.isdir(os.path.join(repo_dir, ".git")) else "0"

            # exécution du setup spécifique au cas
            try:
                setup(repo_dir)
            except Exception as e:
                print(f"[RATE] {nom} : setup échoué ({e})")
                ok_global = False
                continue

            # construction du script PowerShell
            script_ps = texte_fonction + f"""
$Result = Save-FichiersGeneres -Racine '{repo_dir}' -Chemins @('README.md','litellm_config.yaml') -Message 'test commit'
"RESULTAT=$Result"
"""
            # le script est ecrit hors du depot pour ne pas le salir
            script_dir = tempfile.mkdtemp(prefix='epreuve_maj_commit_ps1_')
            temp_dirs.append(script_dir)
            script_path = os.path.join(script_dir, f"{nom}.ps1")
            with open(script_path, 'w', encoding='utf-8-sig') as f:
                f.write(script_ps)

            # exécution du script
            try:
                result = subprocess.run(
                    [pwsh, '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass',
                     '-File', script_path],
                    capture_output=True,
                    text=True,
                    encoding='utf-8',
                    errors='replace',
                    timeout=60,
                    env=os.environ.copy(),
                    creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0)
                )
                stdout = result.stdout.strip()
                lignes = stdout.splitlines()
                resultat = None
                for ligne in lignes:
                    if ligne.startswith("RESULTAT="):
                        resultat = ligne.split("=", 1)[1].strip()
                        break

                if resultat is None:
                    detail = f"code={result.returncode} stderr={result.stderr[:300].replace(chr(10), ' ')}"
                    ok = False
                else:
                    try:
                        ok = verif(repo_dir, resultat, before_cnt)
                        detail = f"RESULTAT={resultat}"
                    except Exception as e:
                        ok = False
                        detail = f"verif_error={e}"

                ok_global &= ok
                print(f"[{'OK  ' if ok else 'RATE'}] {nom} : {detail}")

                # Cas C4 : on attend que le script se termine avec code 0 même en échec
                if nom == "C4" and result.returncode != 0:
                    print(f"[RATE] {nom} : code retour attendu 0, obtenu {result.returncode}")
                    ok_global = False

            except subprocess.TimeoutExpired:
                print(f"[RATE] {nom} : timeout")
                ok_global = False
            except Exception as e:
                print(f"[RATE] {nom} : {e}")
                ok_global = False

    finally:
        for d in temp_dirs:
            shutil.rmtree(d, onerror=_on_rm_error, ignore_errors=True)

    sys.exit(0 if ok_global else 1)

if __name__ == "__main__":
    main()
