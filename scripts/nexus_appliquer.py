# -*- coding: utf-8 -*-
"""Appliquer un patch rendu par le banc, apres verification.

L'orchestrateur ne retape pas : il verifie que chaque bloc AVANT est REEL
et UNIQUE dans le fichier cible, applique tous les blocs, et laisse
l'epreuve juger. Un bloc absent ou multiple provoque un REFUS total.
Le script verifie la syntaxe Python avant ecriture et lance ruff apres.
"""
import io
import json
import re
import sys
import ast
import os
import subprocess
import contextlib

with contextlib.suppress(Exception):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

def main():
    if len(sys.argv) < 4:
        print("Usage: python nexus_appliquer.py <fichier_jsonl> <nom_tache> <fichier_cible>")
        return 2

    jsonl_path, nom_tache, cible_path = sys.argv[1], sys.argv[2], sys.argv[3]

    # Lecture du JSONL
    texte = None
    try:
        fh_jsonl = io.open(jsonl_path, encoding="utf-8")
    except (FileNotFoundError, PermissionError, OSError) as e:
        print(f"ERREUR : impossible d'ouvrir le fichier JSONL '{jsonl_path}' : {e}")
        print("Usage: python nexus_appliquer.py <fichier_jsonl> <nom_tache> <fichier_cible>")
        return 1
    with fh_jsonl as fh:
        for ligne in fh:
            ligne = ligne.strip()
            if not ligne:
                continue
            d = json.loads(ligne)
            if d.get("nom") == nom_tache:
                texte = d.get("texte") or ""
                break

    if texte is None:
        print("REFUS : aucune tache nommee %s dans %s" % (nom_tache, jsonl_path))
        return 1

    if "AUCUN DEFAUT" in texte.upper():
        print("Le banc declare AUCUN DEFAUT SUR -- rien a appliquer.")
        return 2

    # Extraction de tous les blocs AVANT/APRES/FIN
    pattern = re.compile(
        r'^<<<AVANT>>>[ \t]*\r?$(.*?)^<<<APRES>>>[ \t]*\r?$(.*?)^<<<FIN>>>[ \t]*\r?$',
        re.MULTILINE | re.DOTALL
    )
    blocs = []
    for m in pattern.finditer(texte):
        avant = m.group(1).strip("\r\n")
        apres = m.group(2).strip("\r\n")
        blocs.append((avant, apres))

    if not blocs:
        counts = {m: texte.count(m) for m in ["<<<AVANT>>>", "<<<APRES>>>", "<<<FIN>>>"]}
        if any(counts.values()):
            print(f"REFUS : marqueurs mal places (doivent etre seuls sur leur ligne). Occurrences : {counts}")
        else:
            print("REFUS : le rendu ne porte pas les triplets de marqueurs.")
        print(texte[:400])
        return 1

    # Verification du chemin cible sous la racine du depot
    script_dir = os.path.dirname(os.path.realpath(__file__))
    racine_depot = os.path.dirname(script_dir)
    cible_real = os.path.realpath(cible_path)
    racine_real = os.path.realpath(racine_depot)
    try:
        chemin_commun = os.path.commonpath([cible_real, racine_real])
    except ValueError:
        print(f"REFUS : chemin refuse '{cible_path}' (hors racine du depot '{racine_depot}')")
        return 1
    if chemin_commun != racine_real:
        print(f"REFUS : chemin refuse '{cible_path}' (hors racine du depot '{racine_depot}')")
        return 1

    # Lecture du fichier cible
    try:
        with io.open(cible_path, encoding="utf-8") as f:
            src = f.read()
    except (FileNotFoundError, PermissionError, OSError) as e:
        print(f"ERREUR : impossible d'ouvrir le fichier cible '{cible_path}' : {e}")
        print("Usage: python nexus_appliquer.py <fichier_jsonl> <nom_tache> <fichier_cible>")
        sys.exit(1)

    # Verification qu'aucun bloc APRES n'est vide ou blanc
    for idx, (_, apres) in enumerate(blocs, start=1):
        if not apres.strip():
            print("REFUS : le bloc %d a un texte APRES vide ou blanc ; une suppression pure doit etre demandee explicitement." % idx)
            return 1

    # Verification de chaque bloc AVANT
    for idx, (avant, _) in enumerate(blocs, start=1):
        occ = src.count(avant)
        if occ != 1:
            print("REFUS : le bloc %d doit etre unique et reel. Occurrences trouvees : %d" % (idx, occ))
            print("--- ce que le banc a cru trouver ---")
            print(avant[:400])
            return 1

    # Application de tous les remplacements
    nouveau_src = src
    for avant, apres in blocs:
        nouveau_src = nouveau_src.replace(avant, apres)

    # Verification syntaxique avant ecriture pour eviter de casser le fichier
    if cible_path.endswith(".py"):
        try:
            ast.parse(nouveau_src)
        except SyntaxError as e:
            print("[!] Le patch produirait un fichier SYNTAXIQUEMENT INVALIDE")
            print("[!] Erreur : %s" % (e))
            return 1

    # Verification syntaxique pour les fichiers JavaScript
    if cible_path.endswith(('.js', '.mjs', '.cjs')):
        try:
            import tempfile
            with tempfile.NamedTemporaryFile('w', delete=False, suffix='.js', encoding='utf-8') as tmp:
                tmp_path = tmp.name
                tmp.write(nouveau_src)
            result = subprocess.run(['node', '--check', tmp_path],
                                    capture_output=True, text=True,
                                    encoding='utf-8', errors='replace', timeout=60)
            os.remove(tmp_path)
            if result.returncode != 0:
                print("[!] Le patch produirait un fichier SYNTAXIQUEMENT INVALIDE")
                first_line = result.stderr.splitlines()[0] if result.stderr else ''
                print(first_line)
                return 1
        except FileNotFoundError:
            print("L'analyseur n'a PAS PU se prononcer", file=sys.__stderr__)

    # Ecriture atomique du fichier cible
    temp_path = cible_path + ".tmp"
    try:
        with io.open(temp_path, "w", encoding="utf-8", newline="\n") as f:
            f.write(nouveau_src)
        os.replace(temp_path, cible_path)
    except Exception:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        raise

    print("APPLIQUE : %d bloc(s) dans %s" % (len(blocs), cible_path))

    # Analyse ruff apres ecriture reussie
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

        if ruff_exe:
            args = [ruff_exe, "check", "--select", "E9,F,B,C4,SIM,RET", cible_path]
            proc = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8', errors='replace')
            stdout, stderr = proc.communicate()
            if stdout:
                print("[!] Violations detectees :\n%s" % stdout)
            if stderr:
                print("[!] L'analyseur n'a PAS PU se prononcer :\n%s" % stderr)
    except Exception:
        pass

    return 0

if __name__ == "__main__":
    sys.exit(main())
