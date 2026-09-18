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

# ---------------------------------------------------------------------------
# Verrou d'instance unique
# ---------------------------------------------------------------------------

import atexit
import tempfile
import time

def verrou_est_libre(contenu: str, pid_vivant) -> bool:
    """
    Retourne True si le verrou est libre.
    - contenu vide ou illisible → libre
    - sinon le PID contenu doit ne plus être vivant.
    """
    if not contenu or not contenu.strip():
        return True
    try:
        pid = int(contenu.strip())
    except ValueError:
        return True
    return not pid_vivant(pid)

def _pid_vivant_defaut(pid: int) -> bool:
    """Détection de processus vivant selon la plateforme."""
    if os.name == "nt":
        # Windows : tasklist
        try:
            result = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}"],
                capture_output=True, text=True, encoding="utf-8", errors="replace"
            )
            return str(pid) in result.stdout
        except Exception:
            return False
    else:
        # Unix : os.kill avec signal 0
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False

def prendre_verrou(chemin: str, pid: int, pid_vivant=_pid_vivant_defaut) -> bool:
    """
    Essaie de prendre le verrou.
    - Lit le fichier s'il existe et applique `verrou_est_libre`.
    - Si libre, écrit atomiquement le PID courant.
    - Retourne True si le verrou a été pris, sinon False.
    """
    try:
        contenu = ""
        if os.path.isfile(chemin):
            with open(chemin, "r", encoding="utf-8", errors="replace") as fh:
                contenu = fh.read()
        if not verrou_est_libre(contenu, pid_vivant):
            return False

        # écriture atomique
        dir_name = os.path.dirname(chemin)
        # Le dossier est ignoré par git et absent de tout arbre de travail neuf.
        os.makedirs(dir_name, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(dir=dir_name, text=True)
        with os.fdopen(fd, "w", encoding="utf-8") as tmp:
            tmp.write(str(pid))
        os.replace(tmp_path, chemin)
        return True
    except Exception:
        return False

def _liberer_verrou(chemin: str, pid: int):
    """Supprime le verrou si c'est bien notre PID."""
    try:
        if not os.path.isfile(chemin):
            return
        with open(chemin, "r", encoding="utf-8", errors="replace") as fh:
            contenu = fh.read().strip()
        if contenu == str(pid):
            os.remove(chemin)
    except Exception:
        pass

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")



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
PALIERS_MAX_DECOUPE = 8
ALLOWED_EXTENSIONS = {".py", ".ps1"}

def _split_diff_by_file(text):
    """Retourne une liste de sous-diffs, chacun commencant par 'diff --git'."""
    parts = []
    current = []
    for line in text.splitlines(keepends=True):
        if line.startswith("diff --git"):
            if current:
                parts.append("".join(current))
            current = [line]
        else:
            current.append(line)
    if current:
        parts.append("".join(current))
    return parts

def _exceeds_token_limit(text, limit):
    """Estimation tres simple du nombre de tokens requis"""
    return len(text) // 4 > limit  # 4 caracteres pour 1 token

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
    Retourne la liste des fichiers modifiés entre <base> et HEAD,
    en excluant les fichiers supprimés (statut D).
    Utilisé lorsque l’on compare deux commits déjà existants.
    """
    out = run_git(["diff", "--name-status", f"{base}..HEAD"])
    fichiers = []
    for ligne in out.splitlines():
        if not ligne:
            continue
        # le format est «<statut>\t<chemin>», par ex. «M\tsrc/foo.py» ou «D\told.py».
        parts = ligne.split("\t", 1)
        if len(parts) != 2:
            continue
        statut, chemin = parts
        if statut.upper() != "D":
            fichiers.append(chemin)
    return fichiers

def _tete_existe():
    """Vrai si le depot a au moins un commit."""
    try:
        run_git(["rev-parse", "--verify", "HEAD"])
        return True
    except RuntimeError:
        return False

def creer_copie_detachee(racine: str) -> str:
    """
    Cree une copie detachee (git worktree) de HEAD sous .nexus/valide_wt/.
    Le validateur juge cette copie, jamais l'arbre vivant (regle 0.4).
    """
    chemin = os.path.join(racine, '.nexus', 'valide_wt',
                         time.strftime('%Y%m%d-%H%M%S') + '-' + str(os.getpid()))
    parent = os.path.dirname(chemin)
    os.makedirs(parent, exist_ok=True)
    result = subprocess.run(
        ['git', 'worktree', 'add', '--detach', chemin, 'HEAD'],
        cwd=racine,
        capture_output=True,
        text=True,
        encoding='utf-8',
        errors='replace',
    )
    if result.returncode != 0:
        if os.path.isdir(chemin):
            shutil.rmtree(chemin, ignore_errors=True)
        raise RuntimeError('copie impossible : ' + result.stderr.strip())
    return chemin

def retirer_copie(racine: str, chemin: str):
    """
    Supprime la copie detachee et nettoie les residus ; ne leve jamais.
    """
    try:
        subprocess.run(
            ['git', 'worktree', 'remove', '--force', chemin],
            cwd=racine,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
        )
        subprocess.run(
            ['git', 'worktree', 'prune'],
            cwd=racine,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
        )
        if os.path.isdir(chemin):
            shutil.rmtree(chemin, ignore_errors=True)
    except Exception:
        pass


def get_modified_files_uncommitted():
    """
    Fichiers modifiés depuis HEAD : index ET arbre de travail,
    en excluant les fichiers supprimés (statut D).

    `git diff` seul compare l'arbre à l'INDEX, pas à HEAD. Conséquence
    mesurée : après un `git add` – le geste naturel avant de valider –
    le diff devenait vide, le script basculait sur un périmètre de commits
    lui‑aussi vide, et concluait qu'il n'y avait rien à juger. Indexer son
    travail désarmait donc le validateur.

    Les fichiers neufs jamais indexés sont ajoutés à part : aucun diff ne
    les contient, mais la batterie mécanique peut au moins vérifier qu'ils
    tiennent debout.
    """
    if _tete_existe():
        # HEAD existe : comparer l'index + l'arbre de travail à HEAD.
        portee = ["diff", "--name-status", "HEAD"]
    else:
        # Aucun commit : comparer l'arbre de travail à rien.
        portee = ["diff", "--name-status"]
    lignes = run_git(portee).splitlines()
    fichiers = []
    for ligne in lignes:
        if not ligne:
            continue
        # format «<statut>\t<chemin>»
        parts = ligne.split("\t", 1)
        if len(parts) != 2:
            continue
        statut, chemin = parts
        if statut.upper() != "D":
            fichiers.append(chemin)
    # Ajouter les fichiers non suivis (untracked) qui ne figurent pas dans le diff.
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

def epreuves_du_perimetre(fichiers_modifies):
    """Retourne les epreuves Python presentes dans le diff.

    Cet outil JUGEAIT le diff sans jamais MESURER, et a rendu trois
    fausses regressions le 2026-09-18 alors que l'epreuve concernee
    etait dans le diff et passait.
    """
    selection = []
    for chemin in fichiers_modifies or []:
        if not chemin.endswith('.py'):
            continue
        parties = chemin.replace('\\', '/').split('/')
        if 'epreuves' in parties:
            selection.append(chemin)
    return selection


def lancer_epreuves(epreuves):
    """Lance chaque epreuve et rend un compte rendu mesurable.

    Cet outil JUGEAIT le diff sans jamais MESURER, et a rendu trois
    fausses regressions le 2026-09-18 alors que l'epreuve concernee
    etait dans le diff et passait.
    """

    def _resume(texte):
        if len(texte) <= 600:
            return texte
        lignes = texte.splitlines()
        marquees = [l for l in lignes if 'ECHEC' in l or 'PLANTE' in l]
        if marquees:
            extrait = '\n'.join(marquees)
            if len(extrait) > 600:
                extrait = extrait[:600]
            return extrait
        return texte[-600:]

    resultats = []
    for chemin in epreuves:
        sortie = ''
        try:
            proc = subprocess.run(
                [sys.executable, chemin],
                cwd=ROOT,
                capture_output=True,
                text=True,
                timeout=300,
            )
            code = proc.returncode
            sortie = (proc.stdout or '') + (proc.stderr or '')
            concluante = code == 0
        except subprocess.TimeoutExpired as e:
            code = -1
            concluante = False
            sortie = (e.stdout or '') + (e.stderr or '')
            if not sortie:
                sortie = 'L epreuve a depasse le delai de 300 secondes.'
        except OSError as e:
            code = -2
            concluante = False
            sortie = str(e)
        except Exception as e:
            code = -3
            concluante = False
            sortie = str(e)
        resultats.append({
            'nom': chemin,
            'code_sortie': code,
            'concluante': concluante,
            'extrait': _resume(sortie),
        })
    return resultats


def _etat_de_la_mesure(epreuves, mesures):
    """Renvoie une ligne decrivant l'etat de la mesure."""
    if not epreuves:
        return "Aucune epreuve ne figurait dans le perimetre : rien n'a ete mesure, le verdict repose sur le seul jugement."
    total = len(mesures)
    vertes = sum(1 for m in mesures if m.get("concluante"))
    non_concluantes = [m["nom"] for m in mesures if not m.get("concluante")]
    if non_concluantes:
        return "%d epreuve(s) lancee(s), %d verte(s) ; non concluante(s) : %s" % (total, vertes, ", ".join(non_concluantes))
    return "%d epreuve(s) lancee(s), %d verte(s)" % (total, vertes)


def get_diff_from_base(base, fichiers=None):
    """
    Retourne le diff complet entre <base> et HEAD.
    Si *fichiers* est fourni et non vide, le diff est limité à ces chemins.
    """
    if fichiers:
        return run_git(["diff", f"{base}..HEAD", "--", *fichiers])
    return run_git(["diff", f"{base}..HEAD"])


def get_diff_uncommitted(fichiers=None):
    """
    Diff complet depuis HEAD, index compris.

    La docstring precedente annoncait deja « HEAD vs arbre » alors que le
    code faisait `git diff`, soit index vs arbre. L'ecart entre les deux
    est exactement ce qui rendait le trou invisible.
    """
    if fichiers:
        return run_git(["diff", "HEAD", "--", *fichiers]) if _tete_existe() else run_git(["diff", "--", *fichiers])
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

    # Mesure du 2026-09-16, signalee par deux sessions voisines : le nom que
    # git place apres le second @@ est le CONTEXTE du hunk, pas ce qui change.
    # Un diff de docstring produit un hunk A L'INTERIEUR d'une fonction, dont
    # le nom etait donc compte : 54 fonctions « touchees » a AST identique.
    # Le contexte n'est retenu que si le hunk porte au moins une ligne de CODE.
    contexte = None
    porte_du_code = False
    dans_docstring = False
    for line in lines:
        if line.startswith("@@"):
            if contexte and porte_du_code:
                changed.add(contexte)
            m = hunk.search(line)
            contexte = (m.group(1) or m.group(2)) if m else None
            porte_du_code = False
            dans_docstring = False
            continue
        if line[:1] in ("+", "-"):
            corps = line[1:].strip()
            delimiteurs = corps.count('\"\"\"') + corps.count("'''")
            documentaire = (not corps) or corps.startswith("#") or dans_docstring or delimiteurs > 0
            if delimiteurs % 2 == 1:
                dans_docstring = not dans_docstring
            if not documentaire:
                porte_du_code = True
        for motif in (py_def, ps_def):
            m = motif.match(line)
            if m:
                changed.add(m.group(1))
                porte_du_code = True
                break
    if contexte and porte_du_code:
        changed.add(contexte)

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

def free_plan_judgment(diff_text, callers, modele=None, _profondeur=0):
    """
    Envoie la tâche à l'agent gratuit et interprète le résultat.
    Gère les cas de troncature (clé `tronque`) en relançant une fois avec
    un plafond de tokens doublé. Si la réponse est vide sans troncature,
    lève une erreur explicite.
    Si le diff dépasse le plafond de tokens, il est découpé par fichier
    et chaque morceau est jugé séparément. Le verdict global est négatif
    dès qu’un seul morceau rend une régression.
    La recursion est bornee : PALIERS_MAX_DECOUPE paliers au plus, et un
    morceau qui ne se decoupe plus (un seul fichier trop grand) est REFUSE
    avec sa cause, jamais juge en silence (mesure du 2026-09-14 : 11 morceaux
    juges puis 'maximum recursion depth exceeded').
    """
    # -----------------------------------------------------------------------
    # Découpage du diff si nécessaire (approx. 4 caractères ≈ 1 token)
    # -----------------------------------------------------------------------
    # Si le diff complet dépasse le plafond, on le découpe et on traite chaque morceau.
    if _exceeds_token_limit(diff_text, DEFAULT_MAX_TOKENS):
        morceaux = _split_diff_by_file(diff_text)
        # Si aucun morceau n’est trouvé (diff ne suit pas le format attendu), on garde le texte entier.
        if not morceaux:
            morceaux = [diff_text]

        # Condition d'arret : aucun decoupage effectif ou profondeur maximale atteinte
        if (len(morceaux) == 1 and len(morceaux[0]) == len(diff_text)) or _profondeur >= PALIERS_MAX_DECOUPE:
            first_line = morceaux[0].splitlines()[0] if morceaux[0].splitlines() else ''
            first_line = first_line[:80]
            n = len(morceaux[0])
            raise RuntimeError(
                f"morceau trop grand pour etre juge : {first_line} ({n} caracteres, plafond {DEFAULT_MAX_TOKENS*4}) -- relancer avec une base plus proche ou juger ce fichier a part"
            )

        regression_global = False
        bascule_global = None
        textes = []

        for morceau in morceaux:
            # On applique la logique existante sur chaque morceau.
            try:
                reg, bas, txt = free_plan_judgment(morceau, callers, modele, _profondeur=_profondeur+1)  # appel récursif contrôlé
            except RuntimeError:
                # Propagation de l’erreur si un morceau ne peut être jugé.
                raise
            regression_global = regression_global or reg
            # Conserver la première bascule rencontrée (si plusieurs, la première suffit).
            if bascule_global is None and bas is not None:
                bascule_global = bas
            textes.append(txt)

        # Retourner le verdict agrégé.
        return regression_global, bascule_global, "\n".join(textes)

    # -----------------------------------------------------------------------
    # Traitement du diff qui tient dans le plafond (comportement original)
    # -----------------------------------------------------------------------
    plafond = DEFAULT_MAX_TOKENS  # plafond minimal requis
    for attempt in range(2):  # première tentative + une relance éventuelle
        tache = build_task(diff_text, callers, max_tokens=plafond, modele=modele)
        cle = agent.cle_maitre()
        try:
            reponse = agent.executer(tache, cle)
        except Exception as e:
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

# Mesure du 2026-09-15 :
def choisir_perimetre(base: str) -> tuple[str, list[str], str, str]:
    """
    Détermine le périmètre de validation.
    Retourne (mode, fichiers_retenus, diff_text, message).
    - mode : 'non_commit' ou 'base'
    - fichiers_retenus : liste des fichiers .py/.ps1 retenus pour la batterie mécanique
    - diff_text : texte du diff correspondant au périmètre
    - message : texte informatif affiché avant la batterie mécanique
    """
    # Travail non commité
    non_commit = _filter_allowed_files(get_modified_files_uncommitted())
    if non_commit:
        mode = 'non_commit'
        diff_text = get_diff_uncommitted(non_commit)
        message = f"Utilisation du diff du travail non commit (HEAD) : {len(non_commit)} fichier(s) .py/.ps1."
        return mode, non_commit, diff_text, message

    # Aucun fichier non commité .py/.ps1
    # Comptage des fichiers non commités hors extensions autorisées
    tous_non_commit = get_modified_files_uncommitted()
    ecartes = len([f for f in tous_non_commit if os.path.splitext(f)[1] not in ALLOWED_EXTENSIONS])

    fichiers = _filter_allowed_files(get_modified_files_from_base(base))
    mode = 'base'
    diff_text = get_diff_from_base(base, fichiers) if fichiers else ''
    message = f"Perimetre {base}..HEAD : {len(fichiers)} fichier(s) .py/.ps1"
    if ecartes:
        message += f" ({ecartes} fichier(s) non commite(s) hors .py/.ps1 ignore(s))"
    return mode, fichiers, diff_text, message


def main():
    global ROOT
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
    parser.add_argument(
        "--copie", action="store_true",
        help="Juger une copie detachee de HEAD (git worktree) au lieu de l'arbre vivant.")
    args = parser.parse_args()

    # -----------------------------------------------------------------------
    # Verrou d'instance unique : on ne doit lancer qu'une seule validation à la fois
    # -----------------------------------------------------------------------
    lock_path = os.path.join(PLATEFORME, ".nexus", "valide.lock")
    my_pid = os.getpid()
    if not prendre_verrou(lock_path, my_pid):
        holder_pid = None
        if os.path.exists(lock_path):
            try:
                with open(lock_path, encoding='utf-8', errors='replace') as f:
                    holder_pid = f.read().strip()
            except (OSError, ValueError):
                print(f"REFUS : le verrou dans {lock_path} vient d'etre libere ou est illisible -- relancer")
                return 2
        if holder_pid:
            print(f"REFUS : une autre instance de nexus_valide tourne (PID detenteur {holder_pid} dans {lock_path}) -- attendre sa fin ou l'arreter")
        else:
            print(f"REFUS : le verrou dans {lock_path} vient d'etre libere ou est illisible -- relancer")
        return 2
    # S'assurer que le verrou est libéré à la sortie du script
    atexit.register(_liberer_verrou, lock_path, my_pid)
    if args.copie:
        try:
            copie = creer_copie_detachee(ROOT)
            atexit.register(retirer_copie, ROOT, copie)
            sha = run_git(['rev-parse', '--short', 'HEAD']).strip()
            print('Juge sur la copie %s au commit %s' % (copie, sha))
            ROOT = copie
        except RuntimeError as e:
            print('REFUS : %s' % e)
            return 2

    # -----------------------------------------------------------------------
    # Détermination du périmètre : travail non commité vs comparaison de commits
    # -----------------------------------------------------------------------
    try:
        validate_base(args.base)

        mode, modified, diff_text, message = choisir_perimetre(args.base)
        print(message)
        mechanical_battery(modified)
        epreuves = epreuves_du_perimetre(modified)
        mesures = lancer_epreuves(epreuves)
    except Exception as e:
        print("Erreur mecanique :", e)
        return 1
    epreuves_ech = [m for m in mesures if m["code_sortie"] != 0]
    regression_mesuree = bool(epreuves_ech)
    epreuves_vertes = bool(epreuves) and all(m["code_sortie"] == 0 for m in mesures)

    changed_funcs = extract_changed_functions(diff_text)

    # Un diff vide est le seul cas ou l'on peut conclure sans juger.
    if not diff_text.strip():
        if args.json:
            print(json.dumps({"verdict": "RIEN", "code": 0}))
        else:
            print("Aucun fichier .py/.ps1 a juger dans le perimetre retenu.")
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
            "code": 1 if regression or regression_mesuree else 0,
            "epreuves": epreuves,
            "mesures": mesures,
            "regression_mesuree": regression_mesuree,
            "epreuves_ech": epreuves_ech,
            "epreuves_vertes": epreuves_vertes,
        }
        print(json.dumps(payload, ensure_ascii=False))
    else:
        if regression_mesuree:
            print("REGRESSION MESUREE")
            for m in epreuves_ech:
                print(f"  {m['nom']} : code {m['code_sortie']}")
                print(f"    extrait : {m['extrait']}")
            if regression:
                print("Le banc signalait aussi une anomalie.")
            else:
                print("Le banc ne voyait rien ; la mesure tranche.")
            return 1
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
            print("  %s" % _etat_de_la_mesure(epreuves, mesures))
            if epreuves_vertes:
                print("  Regression jugee mais non mesuree : les epreuves du perimetre sont toutes passees.")
            return 1
        portee = ("%d fonction(s) touchee(s)" % len(changed_funcs)
                  if changed_funcs else "diff entier, aucune fonction isolee")
        print("Aucune regression detectee — juge par le banc gratuit (%s)." % portee)
        # l'incertitude doit se dire SURTOUT sur le verdict rassurant
        # car c'est celui apres lequel on passe a la suite
        for ligne in (texte or "").splitlines():
            if ligne.startswith("[!]"):
                print("  %s" % ligne.rstrip())
        print("  %s" % _etat_de_la_mesure(epreuves, mesures))
        if bascule:
            print("  (bascule de plan : %s)" % bascule)
        return 0
    return None

if __name__ == "__main__":
    sys.exit(main())
