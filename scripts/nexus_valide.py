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
import tokenize
import shutil  # pour vérifier la présence de pwsh

# ---------------------------------------------------------------------------

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import nexus_agent as agent  # noqa: E402

# Constantes configurables
DEFAULT_MAX_TOKENS = 8000
ALLOWED_EXTENSIONS = {".py", ".ps1"}

# ---------------------------------------------------------------------------

def _ensure_pwsh_available():
    """Vérifie que l’exécutable PowerShell est présent dans le PATH."""
    if shutil.which("pwsh") is None:
        raise RuntimeError("L’exécutable 'pwsh' est introuvable dans le PATH.")

def run_git(args):
    """Exécute une commande git et renvoie stdout décodé."""
    result = subprocess.run(
        ["git"] + args,
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout

def get_modified_files_from_base(base):
    """
    Retourne la liste des fichiers modifiés entre <base> et HEAD.
    Utilisé lorsque l’on compare deux commits déjà existants.
    """
    out = run_git(["diff", "--name-only", f"{base}..HEAD"])
    return [f for f in out.splitlines() if f]

def get_modified_files_uncommitted():
    """
    Retourne la liste des fichiers modifiés dans l’arbre de travail
    (diff non commité). Aucun commit n’est impliqué.
    """
    out = run_git(["diff", "--name-only"])
    return [f for f in out.splitlines() if f]

def _filter_allowed_files(file_list):
    """Ne conserve que les fichiers dont l’extension est autorisée."""
    return [f for f in file_list if os.path.splitext(f)[1] in ALLOWED_EXTENSIONS]

def check_python_syntax(file_path):
    """Vérifie que le fichier Python se parse sans erreur."""
    if not os.path.isfile(file_path):
        raise RuntimeError(f"Fichier Python introuvable : {file_path}")
    # Détection de l’encodage déclaré dans le fichier pour éviter les
    # erreurs lorsqu’il n’est pas UTF‑8.
    with open(file_path, "rb") as f:
        encoding, _ = tokenize.detect_encoding(f.readline)
    with open(file_path, "r", encoding=encoding, errors="replace") as f:
        source = f.read()
    ast.parse(source, filename=file_path)

def check_powershell_syntax(file_path):
    """Utilise le parseur PowerShell pour vérifier la syntaxe."""
    # Vérifie que l'exécutable pwsh est disponible.
    _ensure_pwsh_available()
    # Vérifie que le fichier existe.
    if not os.path.isfile(file_path):
        raise RuntimeError(f"Fichier PowerShell introuvable : {file_path}")
    # Convertit le chemin en absolu et double les apostrophes pour éviter les erreurs de parsing.
    abs_path = os.path.abspath(file_path)
    escaped_path = abs_path.replace("'", "''")
    # Utilisation de ParseFile au lieu de -File : -File exécute le script,
    # ce qui peut déclencher des actions dangereuses (ex. restore.ps1 qui supprime
    # des volumes Docker). ParseFile ne fait qu'analyser la syntaxe, évitant ainsi
    # toute exécution non désirée.
    ps_cmd = (
        f"$e=$null; "
        f"$null=[System.Management.Automation.Language.Parser]::ParseFile('{escaped_path}',[ref]$null,[ref]$e); "
        f"if ($e.Count -gt 0) {{ "
        f"Write-Output '{{0}} errors: {{1}}' -f $e.Count, $e[0].Message; exit 1 }} else {{ exit 0 }}"
    )
    cmd = ["pwsh", "-NoProfile", "-Command", ps_cmd]
    result = subprocess.run(
        cmd,
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        # Le message d'erreur ne doit pas contenir d'accents.
        error_msg = result.stdout.strip().splitlines()[0] if result.stdout else "parse error"
        raise RuntimeError(error_msg)

def run_conformite():
    """Lance le script de conformité et attend un code de sortie 0."""
    cmd = [
        sys.executable,
        os.path.join(ROOT, "scripts", "nexus_conformite.py"),
        "--avant-demarrage",
    ]
    result = subprocess.run(cmd, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"nexus_conformite.py a renvoye un code d'erreur ({result.returncode})\n"
            f"stdout: {result.stdout}\n"
            f"stderr: {result.stderr}"
        )

def mechanical_battery(modified):
    """Exécute la batterie mécanique sur les fichiers modifiés."""
    for f in modified:
        abs_path = os.path.join(ROOT, f)
        if f.endswith(".py"):
            check_python_syntax(abs_path)
        elif f.endswith(".ps1"):
            check_powershell_syntax(abs_path)
    run_conformite()

def get_diff_from_base(base):
    """Retourne le diff complet entre <base> et HEAD."""
    return run_git(["diff", f"{base}..HEAD"])

def get_diff_uncommitted():
    """Retourne le diff complet du travail non commité (HEAD vs arbre)."""
    return run_git(["diff"])

def extract_changed_functions(diff_text):
    """
    Extrait les noms de fonctions dont la signature a changé.
    Recherche des paires -def ... / +def ... (avec ou sans annotation de retour).
    """
    changed = set()
    # Le groupe capture le nom de fonction ; la partie retour est optionnelle.
    pattern = re.compile(r"^[-+]def\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\(.*\)\s*(?:->\s*[^:]*)?")
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
    Lève une exception si aucun appelant n’est trouvé pour une fonction.
    """
    callers = {fn: [] for fn in func_names}
    for fn in func_names:
        # Échapper le nom de fonction pour éviter toute injection dans git grep
        escaped_fn = re.escape(fn)
        try:
            out = run_git(["grep", "-n", f"{escaped_fn}\\s*\\(", "--", "."])
        except RuntimeError as e:
            # Loguer l’erreur mais ne pas masquer le problème
            print(f"Warning: git grep failed for {fn} : {e}", file=sys.stderr)
            raise RuntimeError(f"Impossible de rechercher les appelants de {fn}") from e

        for line in out.splitlines():
            # format: path:line:content
            parts = line.split(":", 2)
            if len(parts) != 3:
                continue
            path, lineno, content = parts
            # ignorer la ligne de définition déjà capturée
            if re.search(rf"\bdef\s+{re.escape(fn)}\s*\(", content):
                continue
            callers[fn].append((path, int(lineno), content.strip()))

        if not callers[fn]:
            raise RuntimeError(f"Aucun appelant trouvé pour la fonction '{fn}'")
    return callers

def build_task(diff_text, callers, max_tokens=DEFAULT_MAX_TOKENS):
    """
    Construit le dictionnaire de tâche attendu par l'agent gratuit.
    La clé `tache` contient le texte complet à analyser.
    Le paramètre max_tokens est fixé à DEFAULT_MAX_TOKENS (minimum requis) mais peut être
    augmenté en cas de troncature.
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
        "max_tokens": max_tokens,
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
    """
    Envoie la tâche à l'agent gratuit et interprète le résultat.
    Gère les cas de troncature (clé `tronque`) en relançant une fois avec
    un plafond de tokens doublé. Si la réponse est vide sans troncature,
    lève une erreur explicite.
    """
    plafond = DEFAULT_MAX_TOKENS  # plafond minimal requis
    for attempt in range(2):  # première tentative + une relance éventuelle
        tache = build_task(diff_text, callers, max_tokens=plafond)
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

        # Cas de troncature détecté
        if reponse.get("tronque"):
            # Si c'est la première tentative, doubler le plafond et réessayer
            if attempt == 0:
                plafond *= 2
                continue
            # Sinon, on a déjà doublé et ça ne suffit toujours pas
            raise RuntimeError(
                f"Réponse tronquée même après double plafond (plafond {plafond} tokens, diff {len(diff_text)} caractères)"
            )

        # Cas où le texte est vide sans indication de troncature
        if not reponse["texte"].strip():
            raise RuntimeError(
                f"Réponse vide sans troncature (plafond {plafond} tokens, diff {len(diff_text)} caractères)"
            )

        # Réponse valide
        regression = analyse_result(reponse["texte"])
        bascule = reponse.get("bascule")
        return regression, bascule, reponse["texte"]

    # Si on sort de la boucle sans retour, c'est une situation anormale
    raise RuntimeError(
        f"Impossible d'obtenir une réponse valide (plafond final {plafond} tokens, diff {len(diff_text)} caractères)"
    )

def validate_base(base):
    """Valide que la valeur fournie pour --base ne peut pas être interprétée comme une option."""
    if not base or base.startswith("-") or re.search(r"\s", base):
        raise ValueError(f"Valeur invalide pour --base : '{base}'")

def main():
    parser = argparse.ArgumentParser(description="Validation Nexus sans cout")
    # Defaut HEAD~1 et non main : juger toute l'histoire d'une branche en un
    # seul appel produit un diff de plus de 100 000 caracteres, que le jugement
    # ne peut pas rendre -- et un code 2 pousse alors vers un agent PAYE pour un
    # defaut d'unite, pas de capacite. Mesure : 112 553 caracteres sur 30
    # commits, echec ; le dernier commit seul, code 0. `--base main` reste
    # disponible pour une revue complete.
    parser.add_argument(
        "--base",
        default="HEAD~1",
        help="Base de comparaison git (defaut HEAD~1).",
    )
    parser.add_argument("--json", action="store_true", help="Sortie JSON detaillee")
    args = parser.parse_args()

    # -----------------------------------------------------------------------
    # Détermination du périmètre : travail non commité vs comparaison de commits
    # -----------------------------------------------------------------------
    try:
        validate_base(args.base)

        # Si des changements non commités existent, on les utilise.
        uncommitted = get_modified_files_uncommitted()
        if uncommitted:
            # On travaille sur le diff HEAD (travail non commit)
            modified = _filter_allowed_files(uncommitted)
            diff_text = get_diff_uncommitted()
            # Information explicite pour le journal
            print("Utilisation du diff du travail non commit (HEAD).")
        else:
            # Aucun changement non commit : on utilise le périmètre fourni
            modified = _filter_allowed_files(get_modified_files_from_base(args.base))
            diff_text = get_diff_from_base(args.base)
            print(
                f"Aucun changement non commit detecte ; utilisation du perimetre {args.base}..HEAD."
            )
        mechanical_battery(modified)
    except Exception as e:
        print("Erreur mecanique :", e)
        return 1

    changed_funcs = extract_changed_functions(diff_text)

    if not changed_funcs:
        # Aucun changement de contrat détecté
        if args.json:
            print(json.dumps({"verdict": "OK", "code": 0}))
        else:
            print("Aucune regression detectee.")
        return 0

    try:
        callers = find_callers(changed_funcs)
    except Exception as e:
        print("Erreur lors de la recherche des appelants :", e)
        return 2

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

if __name__ == "__main__":
    sys.exit(main())
