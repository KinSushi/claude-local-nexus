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

# Deux racines distinctes, et les confondre casse l'un des deux usages.
#
# PLATEFORME : d'ou l'on importe le banc et ou vit nexus_conformite.py. Elle
# se derive de __file__ et de rien d'autre -- une racine deduite du projet
# appelant ne contiendrait pas scripts/nexus_agent.py, et l'import echouerait
# des le premier appel depuis un autre depot.
PLATEFORME = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PLATEFORME, "scripts"))
import nexus_agent as agent  # noqa: E402


def _racine_de_travail() -> str:
    """
    Depot sur lequel porte la validation.

    Sans cela, ROOT valait la plateforme et `nexus_valide.py --base main`
    lance depuis un autre projet validait le depot Nexus au lieu du projet
    appelant : un verdict sur le mauvais code, rendu avec assurance. Le
    contrat presente pourtant cet outil comme employable depuis n'importe
    quel projet.

    Meme ordre que nexus_agent.py, pour que les deux repondent pareil :
    reglage explicite, puis variable fournie par l'hote, puis le depot git
    contenant le repertoire courant. A defaut, la plateforme elle-meme.
    """
    for var in ("NEXUS_WORK_ROOT", "CLAUDE_PROJECT_DIR"):
        valeur = os.environ.get(var)
        if valeur and os.path.isdir(valeur):
            return os.path.abspath(valeur)
    try:
        resultat = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=os.getcwd(), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", errors="replace",
        )
        if resultat.returncode == 0 and resultat.stdout.strip():
            return os.path.abspath(resultat.stdout.strip())
    except Exception:
        pass
    return PLATEFORME


ROOT = _racine_de_travail()

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

def _tete_existe():
    """Vrai si le depot a au moins un commit."""
    try:
        run_git(["rev-parse", "--verify", "HEAD"])
        return True
    except RuntimeError:
        return False


def get_modified_files_uncommitted():
    """
    Fichiers modifies depuis HEAD : index ET arbre de travail.

    `git diff` seul compare l'arbre a l'INDEX, pas a HEAD. Consequence
    mesuree : apres un `git add` -- le geste naturel avant de valider --
    le diff devenait vide, le script basculait sur un perimetre de commits
    lui aussi vide, et concluait qu'il n'y avait rien a juger. Indexer son
    travail desarmait donc le validateur.

    Les fichiers neufs jamais indexes sont ajoutes a part : aucun diff ne
    les contient, mais la batterie mecanique peut au moins verifier qu'ils
    tiennent debout.
    """
    portee = ["diff", "--name-only", "HEAD"] if _tete_existe() else ["diff", "--name-only"]
    fichiers = [f for f in run_git(portee).splitlines() if f]
    neufs = run_git(["ls-files", "--others", "--exclude-standard"]).splitlines()
    for f in neufs:
        if f and f not in fichiers:
            fichiers.append(f)
    return fichiers

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
        os.path.join(PLATEFORME, "scripts", "nexus_conformite.py"),
        "--avant-demarrage",
    ]
    # La conformite juge la PLATEFORME (moteur, secrets, pile), pas le projet
    # valide : elle doit donc s'executer chez elle.
    result = subprocess.run(cmd, cwd=PLATEFORME, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
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
    """
    Diff complet depuis HEAD, index compris.

    La docstring precedente annoncait deja « HEAD vs arbre » alors que le
    code faisait `git diff`, soit index vs arbre. L'ecart entre les deux
    est exactement ce qui rendait le trou invisible.
    """
    return run_git(["diff", "HEAD"] if _tete_existe() else ["diff"])

def extract_changed_functions(diff_text):
    """
    Noms des fonctions TOUCHEES par le diff.

    La version precedente ne retenait que les SIGNATURES modifiees, c'est-a-dire
    les paires -def/+def de meme nom. Un changement de corps -- le cas le plus
    courant, et la source la plus frequente de regressions -- ne produisait
    donc aucun nom, et main() concluait « Aucune regression detectee » sans
    avoir rien fait juger. Un verdict rassurant rendu sans examen est pire
    qu'aucun verdict : il tient lieu de preuve.

    Trois sources sont reunies :
      a) les paires -def/+def de meme nom (comportement d'origine) ;
      b) le contexte que git place apres le second @@ d'un en-tete de hunk ;
      c) toute ligne ajoutee ou supprimee qui definit une fonction.
    """
    changed = set()
    lines = diff_text.splitlines()

    # a) signature modifiee
    sig = re.compile(r"^[-+]def\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\(")
    for i in range(len(lines) - 1):
        if lines[i].startswith("-") and lines[i + 1].startswith("+"):
            m1, m2 = sig.match(lines[i]), sig.match(lines[i + 1])
            if m1 and m2 and m1.group(1) == m2.group(1):
                changed.add(m1.group(1))

    # b) contexte de hunk : "@@ -1,2 +3,4 @@ def foo(" ou "... @@ function Bar"
    hunk = re.compile(
        r"@@.*@@\s*(?:def\s+([A-Za-z_][A-Za-z0-9_]*)\s*\("
        r"|function\s+([A-Za-z_][A-Za-z0-9_-]*))",
        re.IGNORECASE,
    )
    # c) definition ajoutee ou supprimee. Les noms PowerShell portent un
    #    tiret (Confirm-MoteurOllama), que le motif Python exclut.
    py_def = re.compile(r"^[+-]\s*def\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(")
    ps_def = re.compile(r"^[+-]\s*function\s+([A-Za-z_][A-Za-z0-9_-]*)", re.IGNORECASE)

    for line in lines:
        if line.startswith("@@"):
            m = hunk.search(line)
            if m:
                changed.add(m.group(1) or m.group(2))
            continue
        for motif in (py_def, ps_def):
            m = motif.match(line)
            if m:
                changed.add(m.group(1))
                break

    return sorted(n for n in changed if n)


def git_grep(motif):
    """
    Enveloppe de `git grep` qui distingue « rien trouve » de « en panne ».

    git grep rend 1 quand aucune ligne ne correspond -- un resultat, pas une
    erreur. run_git levait sur tout code non nul, si bien que l'absence
    d'appelant remontait comme une panne de recherche.
    """
    result = subprocess.run(
        ["git", "grep", "-n", motif, "--", "."],
        cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, encoding="utf-8", errors="replace",
    )
    if result.returncode == 0:
        return result.stdout
    if result.returncode == 1:
        return ""
    raise RuntimeError("git grep a echoue : %s" % result.stderr.strip())


def find_callers(func_names):
    """
    Appelants de chaque fonction, sous la forme {nom: [(fichier, ligne, texte)]}.

    Une fonction sans appelant n'est PAS une erreur : elle peut etre neuve,
    privee, ou appelee dynamiquement. La version d'origine levait dans ce
    cas, main() rendait alors le code 2, et ce code pousse l'operateur vers
    un agent PAYANT -- une fonction nouvellement ecrite suffisait donc a
    declencher une depense. La liste reste simplement vide.

    La recherche porte sur tout le depot, si bien que deux modules
    definissant un nom homonyme voient leurs appelants confondus. Cas reel
    du 30 aout 2026 : la signature de executer_audit change dans
    nexus_essaim.py, et l'appel remonte venait de nexus_relais.py, qui
    definit la sienne et n'importe pas l'autre -- le juge a conclu a une
    regression inexistante. On ne filtre pas pour autant : ecarter
    silencieusement des fichiers ecarterait aussi de vrais appelants. Le
    nom ambigu est signale, et le juge decide en le sachant.
    """
    callers = {fn: [] for fn in func_names}
    for fn in func_names:
        # Fichiers qui DEFINISSENT le nom. Le depot melange Python et
        # PowerShell, d'ou les deux mots-clefs.
        # Motif litteral : `git grep` emploie des expressions regulieres
        # BASIQUES, ou  ne vaut pas frontiere de mot. Le motif precedent
        # ne trouvait jamais rien, et l'avertissement ne partait donc
        # jamais -- une garde inerte, indiscernable d'un depot sain.
        lignes_def = git_grep("def %s" % fn).splitlines()
        lignes_def += git_grep("function %s" % fn).splitlines()
        definisseurs = set()
        for ligne in lignes_def:
            if ligne.strip():
                definisseurs.add(ligne.split(":", 1)[0])

        if len(definisseurs) > 1:
            # En TETE de liste : le juge doit lire l'avertissement avant les
            # appelants, pas apres avoir forme son opinion.
            callers[fn].append(
                ("(ambiguite)", 0,
                 "AVERTISSEMENT : le nom '%s' est defini dans %d fichiers (%s). "
                 "Les appelants ci-dessous peuvent viser une autre fonction du "
                 "meme nom." % (fn, len(definisseurs), ", ".join(sorted(definisseurs)))))

        for line in git_grep(r"%s\s*(" % re.escape(fn)).splitlines():
            parts = line.split(":", 2)
            if len(parts) != 3:
                continue
            path, lineno, content = parts
            # La definition elle-meme n'est pas un appelant.
            if re.search(r"\b(def|function)\s+%s\b" % re.escape(fn), content, re.IGNORECASE):
                continue
            try:
                callers[fn].append((path, int(lineno), content.strip()))
            except ValueError:
                continue
    return callers


# Le juge de la LOI 1, et par ou passer quand son plan tombe.
#
# Ce modele etait ecrit EN DUR a deux endroits. Le 2026-08-30, le plan cloud
# a rendu « 429 Too Many Requests » pendant plus d'une heure : la validation
# obligatoire avant tout commit est devenue impossible a executer, et une
# validation qui ne s'execute pas ne protege de rien. La regle centrale du
# contrat dependait d'un seul plan, sans issue.
#
# NEXUS_VALIDE_MODELE, ou --modele, permet de juger en local quand le cloud
# est indisponible. On perd de la capacite, jamais la verification.
MODELE_JUGE = os.environ.get("NEXUS_VALIDE_MODELE", "gpt-oss-120b-cloud")


def build_task(diff_text, callers, max_tokens=DEFAULT_MAX_TOKENS, modele=None):
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
    if not appelants_str:
        # Sans appelant, la consigne d'origine (« pour chaque appelant... »)
        # ne demandait rien de faisable : le modele repondait en prose, et
        # analyse_result n'y voyait aucune REGRESSION. Juger le diff
        # lui-meme est le seul examen possible, et il vaut mieux que rien.
        consigne = (
            "Analyse le diff suivant a la recherche de REGRESSIONS reelles :\n"
            "code qui casserait a l'execution, variable renommee mais encore\n"
            "referencee, condition inversee, flux ou code de sortie perdu.\n"
            "Aucun appelant externe n'a ete identifie : juge le diff seul.\n"
            "Commence chaque constat par un mot parmi TRAITE, REGRESSION,\n"
            "INDETERMINE, suivi d'une phrase courte.\n"
            "N'invente aucun defaut pour remplir la liste.\n\n"
            "Termine OBLIGATOIREMENT par une derniere ligne valant conclusion,\n"
            "et n\'emploie ce mot-cle nulle part ailleurs :\n"
            "  VERDICT_FINAL: REGRESSION   s\'il existe au moins une regression\n"
            "  VERDICT_FINAL: RAS          s\'il n\'y en a aucune\n"
            "DIFF:\n"
            f"{diff_text}\n"
        )
        return {
            "nom": "validation_nexus",
            "modele": modele or MODELE_JUGE,
            "tache": consigne,
            "fichiers": [],
            "max_tokens": max_tokens,
        }

    consigne = (
        "Analyse le diff suivant et la liste des appelants ci-dessous.\n"
        "Pour chaque appelant, réponds d'un seul mot parmi : TRAITE, REGRESSION, INDETERMINE, "
        "suivi d'une courte phrase explicative.\n"
        "Ne fabrique aucune réponse si le contexte est insuffisant.\n\n"
        "Termine OBLIGATOIREMENT par une derniere ligne valant conclusion,\n"
        "et n\'emploie ce mot-cle nulle part ailleurs :\n"
        "  VERDICT_FINAL: REGRESSION   s\'il existe au moins une regression\n"
        "  VERDICT_FINAL: RAS          s\'il n\'y en a aucune\n"
        "DIFF:\n"
        f"{diff_text}\n"
        "APPELANTS:\n"
        f"{appelants_str}"
    )
    return {
        "nom": "validation_nexus",
        "modele": modele or MODELE_JUGE,
        "tache": consigne,
        "fichiers": [],
        "max_tokens": max_tokens,
    }

# Les trois verdicts que build_task impose au modele. On retient le PREMIER
# rencontre sur la ligne : le format demande est « <nom> : VERDICT - phrase »,
# donc le verdict qui compte precede toujours l'explication. Cela evite de
# lire « INDETERMINE - aucune REGRESSION visible » comme une regression.
VERDICT = re.compile(r"\b(REGRESSION|TRAITE|INDETERMINE)\b")

# La conclusion, distincte du verdict par ligne. Un deux-points colle au
# mot-cle en fait une etiquette qu'une rubrique de prose ne produit pas.
CONCLUSION = re.compile(r"VERDICT_FINAL\s*:\s*(REGRESSION|RAS)\b")


def analyse_result(text):
    """
    Vrai des qu'une ligne rend le verdict REGRESSION.

    La version precedente exigeait que la ligne COMMENCE par « REGRESSION ».
    Or build_task demande au modele le format « <nom> : VERDICT - phrase » :
    le verdict n'est jamais en tete. Le validateur pouvait donc lire quatre
    lignes « _safe_int : REGRESSION - la signature attend un parametre de
    plus » et conclure « aucune regression detectee ». Faux negatif mesure,
    sur une signature reellement cassee et trois appelants.

    Le mot est cherche en MAJUSCULES sans accent : « regression » ou
    « régression » en prose ne declenche rien, seul le verdict compte.
    """
    # La ligne de conclusion d'abord, et elle seule si elle existe.
    #
    # Faux positif mesure le 2026-08-30. Le modele avait ecrit :
    #
    #   REGRESSION : aucune variable renommee n'est referencee ; aucune
    #   condition n'est inversee ; aucun flux ou code de sortie n'est perdu
    #
    # C'est une RUBRIQUE -- « au titre des regressions : aucune » -- et le
    # parseur y lisait un verdict. La consigne le permettait : « commence
    # chaque constat par un mot parmi TRAITE, REGRESSION, INDETERMINE »
    # rend un titre et un verdict indiscernables.
    #
    # La double passe n'a rien vu, et ne pouvait rien voir : les deux passes
    # ont concorde. Elle protege de la VARIANCE du modele, pas d'un biais
    # systematique de format. C'est une limite reelle de cette protection,
    # et le remede n'est pas de rejuger mais de demander une conclusion
    # qu'une rubrique ne puisse pas imiter.
    for line in text.splitlines():
        m = CONCLUSION.search(line)
        if m:
            return m.group(1) == "REGRESSION", True

    # Pas de conclusion : repli sur l'heuristique par mot-cle, en signalant
    # que le verdict n'est PAS explicite. L'appelant en tire l'incertitude
    # plutot que de trancher sur une lecture faible.
    for line in text.splitlines():
        m = VERDICT.search(line)
        if m and m.group(1) == "REGRESSION":
            return True, False
    return False, False

def free_plan_judgment(diff_text, callers, modele=None):
    """
    Envoie la tâche à l'agent gratuit et interprète le résultat.
    Gère les cas de troncature (clé `tronque`) en relançant une fois avec
    un plafond de tokens doublé. Si la réponse est vide sans troncature,
    lève une erreur explicite.
    """
    plafond = DEFAULT_MAX_TOKENS  # plafond minimal requis
    for attempt in range(2):  # première tentative + une relance éventuelle
        tache = build_task(diff_text, callers, max_tokens=plafond, modele=modele)
        cle = agent.cle_maitre()
        try:
            reponse = agent.executer(tache, cle)
        except Exception as e:
            # `from e` et non `from None` : ici la trace d'origine est
            # precisement ce qui manque. Le message dit QUE l'appel a echoue ;
            # seule la trace dit OU -- reseau, passerelle, decodage. Sans
            # elle, Python affiche « During handling of the above exception »
            # et rien ne signale que la premiere EST la cause.
            raise RuntimeError(
                f"Erreur lors de l'appel à l'agent gratuit : {e}") from e

        # `erreur` n'est presente QUE sur les chemins d'echec de
        # nexus_agent.executer ; une reponse reussie ne la porte pas.
        # L'exiger faisait donc rejeter TOUTE reponse valide comme
        # « incomplete » : le jugement du banc n'a jamais pu aboutir. Le
        # defaut est reste invisible parce qu'un autre, en amont,
        # empechait d'atteindre cette ligne.
        for key in ("texte", "modele", "plan", "tokens"):
            if key not in reponse:
                # Nommer la cle : sans elle, le diagnostic est a refaire
                # entierement a chaque fois.
                raise RuntimeError("Réponse de l'agent incomplète : clé '%s' absente" % key)

        if reponse.get("erreur"):
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
        regression, explicite = analyse_result(reponse["texte"])
        if not explicite:
            # Le modele n a pas rendu sa conclusion : ne pas faire comme si.
            reponse["texte"] += (chr(10) + "[!] aucune ligne VERDICT_FINAL : "
                                 "verdict lu par heuristique, a confirmer")
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
    parser.add_argument(
        "--modele", default=None,
        help="Modele juge. Defaut %s, ou NEXUS_VALIDE_MODELE. A nommer en "
             "local quand le plan cloud est indisponible." % MODELE_JUGE)
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

    # Un diff vide est le seul cas ou l'on peut conclure sans juger.
    if not diff_text.strip():
        if args.json:
            print(json.dumps({"verdict": "RIEN", "code": 0}))
        else:
            print("Aucun changement a juger.")
        return 0

    # Sans fonction identifiee, on juge le diff LUI-MEME plutot que de
    # conclure. Conclure ici etait le defaut central : « Aucune regression
    # detectee » tombait sans qu'aucun examen ait eu lieu, et rien dans le
    # message ne permettait de le savoir.
    try:
        callers = find_callers(changed_funcs) if changed_funcs else {}
    except Exception as e:
        print("Erreur lors de la recherche des appelants :", e)
        return 2

    try:
        regression, bascule, texte = free_plan_judgment(diff_text, callers, args.modele)
    except Exception as e:
        print("Plan gratuit indisponible :", e)
        return 2

    # Une regression annoncee se confirme avant d'etre rendue.
    #
    # Mesure du 2026-08-30 : deux passes sur le MEME commit ont rendu
    # « Regression detectee. » puis « regression: false ». Le jugement du banc
    # varie d'une passe a l'autre -- il est probabiliste, pas deterministe --
    # et LOI 1 repose entierement sur lui. Un verdict non reproductible n'est
    # pas un verdict.
    #
    # Seule la REGRESSION est re-jugee, et l'asymetrie est voulue : un faux
    # positif coute du temps, un faux negatif laisse passer le defaut. On ne
    # depense donc la seconde passe que du cote ou elle protege.
    #
    # Et un desaccord ne se resout PAS en faveur du silence : concluer « rien
    # a signaler » parce que la seconde passe s'est ravisee effacerait un
    # signal qu'on a bel et bien recu. Le desaccord est rendu comme tel, avec
    # les deux jugements, et l'arbitrage revient a l'orchestrateur.
    desaccord = None
    if regression:
        try:
            regression2, _, texte2 = free_plan_judgment(diff_text, callers, args.modele)
        except Exception as e:
            # La seconde passe indisponible ne doit pas effacer la premiere.
            regression2, texte2 = True, "seconde passe indisponible : %s" % e
        if not regression2:
            desaccord = texte2
            saut = chr(10)
            entete = saut + saut + '--- seconde passe, en desaccord ---' + saut
            texte = (texte or '') + entete + (texte2 or '')

    if args.json:
        payload = {
            "regression": regression,
            "bascule": bascule,
            "texte": texte,
            "desaccord": desaccord is not None,
            "code": 1 if regression else 0,
        }
        print(json.dumps(payload, ensure_ascii=False))
    else:
        if regression:
            # Le motif, pas seulement le verdict.
            #
            # Cette branche detenait `texte` -- le jugement du banc, ligne par
            # ligne -- et ne l'imprimait qu'en mode --json. Le cas ou le motif
            # est le plus necessaire etait donc precisement celui ou il etait
            # tu. Un « Regression detectee. » seul n'est pas actionnable :
            # il oblige a relancer la validation autrement pour apprendre ce
            # qu'elle savait deja.
            portee = ("%d fonction(s) touchee(s)" % len(changed_funcs)
                      if changed_funcs else "diff entier, aucune fonction isolee")
            if desaccord is not None:
                print("Verdict INCERTAIN — les deux passes du banc gratuit se "
                      "contredisent (%s)." % portee)
                print("  Le desaccord porte sur un jugement, pas sur le code. "
                      "Verifier la trouvaille dans le code reel avant d'agir.")
            else:
                print("Regression detectee — juge par le banc gratuit (%s)."
                      % portee)
            for ligne in (texte or "").splitlines():
                if ligne.strip():
                    print("  %s" % ligne.rstrip())
            if bascule:
                # Le plan ayant reellement juge. Un verdict rendu par un plan
                # de repli ne se lit pas comme un verdict du plan demande.
                print("  (bascule de plan : %s)" % bascule)
            return 1
        else:
            portee = ("%d fonction(s) touchee(s)" % len(changed_funcs)
                      if changed_funcs else "diff entier, aucune fonction isolee")
            print("Aucune regression detectee — juge par le banc gratuit (%s)." % portee)
            return 0

if __name__ == "__main__":
    sys.exit(main())
