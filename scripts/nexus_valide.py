#!/usr/bin/env python3
"""
Script de validation automatisée du dépôt.

Il remplace l’usage d’un agent payant par une chaîne d’étapes purement
mécaniques (analyse syntaxique, parsing PowerShell, conformité) puis,
en cas de besoin, délègue la décision à l’agent gratuit fourni dans
`scripts/nexus_agent.py`.

Le but est d’éviter toute dépense de jetons : aucune requête n’est faite
à un modèle payant tant que la batterie mécanique réussit et que le plan
gratuit ne signale aucune régression.
"""

import os
import sys
import subprocess
import argparse
import ast
import json
import re

# ---------------------------------------------------------------------------

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import nexus_agent as agent  # noqa: E402

# ---------------------------------------------------------------------------

def run_git(args):
    """Exécute une commande git et renvoie stdout décodé."""
    result = subprocess.run(
        ["git"] + args, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        # `text=True` seul retombe sur la page de code du systeme, cp1252 sous
        # Windows. Le diff de ce depot porte des accents : la lecture levait
        # UnicodeDecodeError dans un thread, et la fonction rendait None sans
        # que rien ne le signale.
        text=True, encoding="utf-8", errors="replace"
    )
    if result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    # Une sortie absente n'est pas une sortie vide : la rendre telle quelle
    # ferait analyser un diff inexistant et conclure « aucune regression ».
    if result.stdout is None:
        raise RuntimeError(f"git {' '.join(args)} : sortie illisible")
    return result.stdout

def get_modified_files(base):
    """Retourne la liste des fichiers modifiés entre <base> et HEAD."""
    out = run_git(["diff", "--name-only", f"{base}..HEAD"])
    return [f for f in out.splitlines() if f]

def check_python_syntax(file_path):
    """Vérifie que le fichier Python se parse sans erreur."""
    with open(file_path, "r", encoding="utf-8") as f:
        source = f.read()
    ast.parse(source, filename=file_path)

def check_powershell_syntax(file_path):
    """Utilise le parseur PowerShell pour vérifier la syntaxe."""
    cmd = [
        "pwsh",
        "-NoProfile",
        "-Command",
        f"$e=$null; $null=[System.Management.Automation.Language.Parser]::ParseFile((Resolve-Path '{file_path}'),[ref]$null,[ref]$e); $e.Count",
    ]
    result = subprocess.run(
        cmd, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, encoding="utf-8", errors="replace"
    )
    if result.returncode != 0:
        raise RuntimeError(f"PowerShell parse error in {file_path}")
    count = result.stdout.strip()
    if count != "0":
        raise RuntimeError(f"PowerShell syntax errors in {file_path}: {count}")

def run_conformite():
    """Lance le script de conformité et attend un code de sortie 0."""
    cmd = [sys.executable, os.path.join(ROOT, "scripts", "nexus_conformite.py"), "--avant-demarrage"]
    result = subprocess.run(cmd, cwd=ROOT)
    if result.returncode != 0:
        raise RuntimeError("nexus_conformite.py a renvoyé un code d'erreur")

def mechanical_battery(modified):
    """Exécute la batterie mécanique sur les fichiers modifiés."""
    for f in modified:
        abs_path = os.path.join(ROOT, f)
        if f.endswith(".py"):
            check_python_syntax(abs_path)
        elif f.endswith(".ps1"):
            check_powershell_syntax(abs_path)
    run_conformite()

def get_diff(base):
    """Retourne le diff complet entre <base> et HEAD."""
    return run_git(["diff", f"{base}..HEAD"])

def extract_changed_functions(diff_text):
    """
    Extrait les noms de fonctions dont la signature a changé.
    Recherche des paires -def ... -> X / +def ... -> Y.
    """
    changed = set()
    pattern = re.compile(r"^[-+]def\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\(.*\)\s*->")
    lines = diff_text.splitlines()
    for i in range(len(lines) - 1):
        m1 = pattern.match(lines[i])
        m2 = pattern.match(lines[i + 1])
        if m1 and m2 and lines[i].startswith("-") and lines[i + 1].startswith("+"):
            if m1.group(1) == m2.group(1):
                changed.add(m1.group(1))
    return sorted(changed)

def find_callers(func_names):
    """
    Recherche les appelants de chaque fonction dans le dépôt.
    Retourne un dict {func: [(file, line_no, line_text), ...]}.
    """
    callers = {fn: [] for fn in func_names}
    for fn in func_names:
        # git grep recherche les appels, exclut les définitions
        try:
            out = run_git(["grep", "-n", f"{fn}\\s*\\(", "--", "."])
        except RuntimeError:
            continue
        for line in out.splitlines():
            # format: path:line:content
            parts = line.split(":", 2)
            if len(parts) != 3:
                continue
            path, lineno, content = parts
            # ignorer la ligne de définition déjà capturée
            if re.search(rf"def\s+{fn}\s*\(", content):
                continue
            callers[fn].append((path, int(lineno), content.strip()))
    return callers

def build_task(diff_text, callers):
    """
    Construit le dictionnaire de tâche attendu par l'agent gratuit.
    La clé `tache` contient le texte complet à analyser.
    """
    appelants_str = ""
    for fn, lst in callers.items():
        for path, lineno, line in lst:
            appelants_str += f"{fn} : {path}:{lineno} : {line}\n"
    consigne = (
        "Analyse le diff suivant et la liste des appelants ci-dessous.\n"
        "Pour chaque appelant, réponds d'un seul mot parmi : TRAITE, REGRESSION, INDETERMINE, "
        "suivi d'une courte phrase explicative.\n"
        "Ne fabrique aucune réponse si le contexte est insuffisant.\n\n"
        "DIFF:\n"
        f"{diff_text}\n"
        "APPELANTS:\n"
        f"{appelants_str}"
    )
    return {
        "nom": "validation_nexus",
        "modele": "gpt-oss-120b-cloud",
        "tache": consigne,
        "fichiers": [],
        "max_tokens": 1500,
    }

def analyse_result(text):
    """
    Parcourt le texte renvoyé par le modèle et détecte la présence d'une
    régression. Retourne True si au moins une ligne contient le mot
    REGRESSION (exact, majuscules).
    """
    for line in text.splitlines():
        if line.strip().upper().startswith("REGRESSION"):
            return True
    return False

def free_plan_judgment(diff_text, callers):
    """Envoie la tâche à l'agent gratuit et interprète le résultat."""
    tache = build_task(diff_text, callers)
    cle = agent.cle_maitre()
    try:
        reponse = agent.executer(tache, cle)
    except Exception as e:
        raise RuntimeError(f"Erreur lors de l'appel à l'agent gratuit : {e}")

    # Vérifier la présence des clés attendues
    for key in ("texte", "erreur", "modele", "plan", "tokens"):
        if key not in reponse:
            raise RuntimeError("Réponse de l'agent incomplète")

    if reponse["erreur"]:
        raise RuntimeError(f"Erreur de l'agent : {reponse['erreur']}")

    regression = analyse_result(reponse["texte"])
    bascule = reponse.get("bascule")
    return regression, bascule, reponse["texte"]

def main():
    parser = argparse.ArgumentParser(description="Validation Nexus sans coût")
    parser.add_argument("--base", default="main", help="Branche de base pour le diff")
    parser.add_argument("--json", action="store_true", help="Sortie JSON détaillée")
    args = parser.parse_args()

    try:
        modified = get_modified_files(args.base)
        mechanical_battery(modified)
    except Exception as e:
        print("Erreur mecanique :", e)
        return 1

    diff_text = get_diff(args.base)
    changed_funcs = extract_changed_functions(diff_text)

    if not changed_funcs:
        # Aucun changement de contrat détecté
        if args.json:
            print(json.dumps({"verdict": "OK", "code": 0}))
        else:
            print("Aucune regression detectee.")
        return 0

    callers = find_callers(changed_funcs)

    try:
        regression, bascule, texte = free_plan_judgment(diff_text, callers)
    except Exception as e:
        print("Plan gratuit indisponible :", e)
        return 2

    if args.json:
        payload = {
            "regression": regression,
            "bascule": bascule,
            "texte": texte,
            "code": 1 if regression else 0,
        }
        print(json.dumps(payload, ensure_ascii=False))
    else:
        if regression:
            print("Regression detectee.")
            return 1
        else:
            print("Aucune regression detectee.")
            return 0

    return 0

if __name__ == "__main__":
    sys.exit(main())
