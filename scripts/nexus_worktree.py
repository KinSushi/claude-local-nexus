# -*- coding: utf-8 -*-
"""
Agent local en arbre de travail isolé.

Pourquoi ce script existe
-------------------------
Faire modifier le dépôt par un modèle local coûte zéro, mais un modèle
local se trompe plus souvent qu'un modèle de tête : lui laisser écrire
directement dans l'arbre courant reviendrait à échanger une dépense contre
un risque. L'isolement résout le dilemme — le modèle travaille dans un
`git worktree` séparé, sa proposition n'est retenue que si elle compile et
passe la validation, et l'arbre principal n'est jamais touché tant que ce
n'est pas le cas.

Le format d'échange n'est ni un diff, ni du JSON — les deux ont été
écartés par la mesure, pas par principe.

Un diff unifié suppose que le modèle compte correctement ses lignes de
contexte, ce qu'un modèle local rate régulièrement ; l'échec est alors
soit silencieux, soit appliqué au mauvais endroit.

Le JSON échoue autrement : un remplacement transporte du code multi‑ligne,
qu'il faut alors échapper caractère par caractère. Sur les deux premières
tâches réelles, qwen3-coder:30b a produit une analyse pertinente dans un
JSON invalide, faute d'avoir échappé les sauts de ligne — le travail était
juste, la mise en forme le rendait inutilisable.

Le modèle rend donc des blocs délimités par des marqueurs `@@` en début de
ligne, où le code passe tel quel. Le script applique lui‑même chaque
remplacement, après avoir vérifié que l'extrait cible apparaît exactement
une fois. Une occurrence ambiguë est un refus, pas un pari.

Usage
-----
    python scripts/nexus_worktree.py \
        --nom validateur \
        --fichier scripts/nexus_validate.py \
        --modele qwen3-coder-30b-local \
        --consigne "Signale et corrige les gestions d'erreur trop larges." \
        --verifier "python -c \"import ast,io;ast.parse(io.open('{fichier}',encoding='utf-8').read())\""

    # inspecter puis fusionner
    python scripts/nexus_worktree.py --lister
    python scripts/nexus_worktree.py --fusionner validateur
    python scripts/nexus_worktree.py --jeter validateur
"""
from __future__ import annotations

import argparse
import io
import os
import re
import shutil
import subprocess
import sys
import tempfile
import shlex

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nexus_agent as agent  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# La racine est DECOUVERTE, jamais declaree.
#
# Ce module figeait ROOT sur la racine de la plateforme. Consequence
# mesuree par une session travaillant sur un autre depot, le 2026-08-30 :
# « --lister » rendait C:/local-llm-docker quel que soit le repertoire
# courant, et lancer l'outil depuis son projet y aurait cree des worktrees
# et fait ecrire un modele -- dans le depot voisin.
#
# La racine suit donc le projet appelant, comme le fait deja
# nexus_ruche.py, et « --racine » permet de la forcer.
ROOT = agent.racine_travail()
# Hors du dépôt : un arbre de travail placé dedans serait vu par git comme
# un dépôt imbriqué, et `git add -A` l'ajouterait à l'index — c'est
# exactement l'accident déjà survenu une fois sur ce dépôt.
ARBRES = os.path.join(os.path.dirname(ROOT), ".nexus-arbres")

SYSTEME = (
    "Tu es un relecteur de code rigoureux. Tu reponds en francais et tu suis "
    "EXACTEMENT le format ci-dessous, sans rien ajouter avant ni apres, et "
    "sans balises de code.\n\n"
    "@@ANALYSE\n"
    "<ce que tu as constate, 3 phrases maximum>\n"
    "@@CORRECTION\n"
    "@@AVANT\n"
    "<extrait copie caractere pour caractere depuis le fichier>\n"
    "@@APRES\n"
    "<le remplacement complet>\n"
    "@@POURQUOI\n"
    "<la defaillance concrete que la correction evite>\n"
    "@@FIN\n\n"
    "Repete le bloc @@CORRECTION ... @@FIN pour chaque correction.\n\n"
    "Regles imperatives :\n"
    "- l'extrait apres @@AVANT est COPIE CARACTERE POUR CARACTERE du fichier "
    "fournis, indentation comprise. S'il ne correspond pas exactement, ta "
    "proposition est rejetee sans etre examinee ;\n"
    "- il doit etre assez long pour n'apparaitre QU'UNE SEULE FOIS dans le "
    "fichier ;\n"
    "- n'ecris jamais une ligne commencant par @@ a l'interieur d'un extrait ;\n"
    "- ne propose que des corrections dont tu es sur. Aucune correction est "
    "une reponse acceptable, et preferable a une invention ;\n"
    "- les commentaires que tu ecris expliquent POURQUOI le code est ainsi, "
    "jamais ce qu'il fait, et sont en francais."
)


def git(args: list[str], cwd: str | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git"] + args,
        cwd=cwd or ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def arbre_de(nom: str) -> str:
    return os.path.join(ARBRES, nom)


def creer_arbre(nom: str) -> str:
    """
    Crée l'arbre isolé, ou réutilise celui qui existe déjà.

    La branche porte le nom de la tâche pour qu'un `git branch` suffise à
    savoir ce qui est en cours — un arbre orphelin dont plus personne ne
    sait à quoi il servait finit par être fusionné ou détruit au hasard.
    """
    chemin = arbre_de(nom)
    if os.path.isdir(chemin):
        return chemin
    os.makedirs(ARBRES, exist_ok=True)
    branche = "agent/" + nom
    existe = git(["rev-parse", "--verify", branche]).returncode == 0
    creation = ["worktree", "add", chemin] + ([branche] if existe else ["-b", branche])
    r = git(creation)
    if r.returncode != 0:
        raise SystemExit("creation de l'arbre impossible :\n" + r.stderr.strip())
    return chemin


def analyser_reponse(texte: str) -> dict | None:
    """
    Découpe la réponse selon les délimiteurs @@.

    Le découpage se fait sur des lignes ENTIÈRES commençant par `@@` : un
    `@@AVANT` apparaissant au milieu d'une ligne de code ne doit pas
    ouvrir une section. Les blocs incomplets — un `@@AVANT` sans `@@APRES`
    parce que la réponse a été coupée — sont écartés plutôt que devinés :
    appliquer la moitié d'une correction est pire que n'en appliquer
    aucune, car le fichier reste syntaxiquement valide tout en ayant
    perdu son sens.

    Les balises de code éventuelles sont retirées : les modèles en
    ajoutent malgré la consigne, et jeter un travail correct pour trois
    accents graves serait absurde.
    """
    texte = texte.strip()
    if texte.startswith("```"):
        texte = re.sub(r"^```[a-zA-Z]*\n", "", texte)
        texte = re.sub(r"\n```\s*$", "", texte)

    sections: list[tuple[str, list[str]]] = []
    for ligne in texte.splitlines():
        marque = re.match(r"^@@([A-Z]+)\s*$", ligne.strip())
        if marque:
            sections.append((marque.group(1), []))
        elif sections:
            sections[-1][1].append(ligne)

    if not sections:
        return None

    analyse, remplacements = "", []
    courant: dict[str, str] = {}
    for nom, lignes in sections:
        corps = "\n".join(lignes).strip("\n")
        if nom == "ANALYSE":
            analyse = corps.strip()
        elif nom == "CORRECTION":
            courant = {}
        elif nom == "AVANT":
            courant["avant"] = corps
        elif nom == "APRES":
            courant["apres"] = corps
        elif nom == "POURQUOI":
            courant["pourquoi"] = corps.strip()
        elif nom == "FIN":
            if "avant" in courant and "apres" in courant:
                remplacements.append(courant)
            courant = {}
    # Un dernier bloc complet mais sans @@FIN reste exploitable.
    if "avant" in courant and "apres" in courant:
        remplacements.append(courant)

    if not analyse and not remplacements:
        return None
    return {"analyse": analyse, "remplacements": remplacements}


def appliquer(chemin: str, remplacements: list[dict]) -> tuple[int, list[str]]:
    """
    Applique les remplacements, en refusant tout ce qui est ambigu.

    Un `avant` absent signifie que le modèle a paraphrasé le fichier au lieu
    de le citer ; un `avant` présent plusieurs fois signifie qu'on ne sait
    pas laquelle il visait. Dans les deux cas, appliquer serait deviner.
    """
    # Lecture en conservant le style de fin de ligne du fichier source.
    with io.open(chemin, encoding="utf-8", newline="") as f:
        source = f.read()
    poses, rejets = 0, []
    for i, r in enumerate(remplacements or [], 1):
        avant, apres = r.get("avant"), r.get("apres")
        if not isinstance(avant, str) or not isinstance(apres, str) or not avant:
            rejets.append("#%d : champs 'avant'/'apres' absents ou non textuels" % i)
            continue
        if apres == avant:
            rejets.append("#%d : remplacement identique a la cible (le modele decline)" % i)
            continue
        n = source.count(avant)
        if n == 0:
            rejets.append("#%d : extrait 'avant' introuvable (le modele a paraphrase)" % i)
            continue
        if n > 1:
            rejets.append("#%d : extrait 'avant' present %d fois (cible ambigue)" % (i, n))
            continue
        source = source.replace(avant, apres, 1)
        poses += 1
    if poses:
        # Ecriture atomique : on écrit d'abord dans un fichier temporaire puis
        # on le remplace en une opération atomique. Cela évite que, en cas
        # d'interruption (ex. coupure d'alimentation), le fichier cible se retrouve
        # partiellement écrasé et donc invalide.
        dir_name = os.path.dirname(chemin)
        fd, tmp_path = tempfile.mkstemp(dir=dir_name, text=True)
        try:
            # Conserver les permissions du fichier original.
            mode_original = os.stat(chemin).st_mode
            with os.fdopen(fd, "w", encoding="utf-8", newline="") as tmp_file:
                tmp_file.write(source)
            os.replace(tmp_path, chemin)
            os.chmod(chemin, mode_original)
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
    return poses, rejets


def lancer(nom, fichier, modele, consigne, verifier, max_tokens) -> int:
    # Calcul de la racine de travail une seule fois.
    racine = agent.racine_travail()
    # Construction du chemin complet en respectant les chemins déjà absolus.
    complet = fichier if os.path.isabs(fichier) else os.path.join(racine, fichier)
    # Utilisation de la fonction moderne pour vérifier l'appartenance au dépôt.
    if not agent.sous_racine(complet, racine) or agent.est_secret(complet):
        print(
            f"Fichier refuse : hors du dépôt (racine utilisée : {racine}) "
            "ou susceptible de porter un secret."
        )
        return 1
    if not os.path.exists(complet):
        print("Fichier introuvable : %s" % fichier)
        return 1

    chemin_arbre = creer_arbre(nom)
    cible = os.path.join(chemin_arbre, fichier.replace("\\", "/"))
    if not os.path.exists(cible):
        print("Le fichier n'existe pas dans l'arbre isole : %s" % cible)
        return 1

    contenu = io.open(cible, encoding="utf-8").read()
    print("  arbre    : %s" % chemin_arbre)
    print("  fichier  : %s (%d lignes)" % (fichier, contenu.count("\n") + 1))
    print("  modele   : %s" % modele)
    print("  appel en cours (un modele non charge met 60 a 120 s)...")

    cle = agent.cle_maitre()
    try:
        resultat = agent.appeler(
            modele,
            [
                {"role": "system", "content": SYSTEME},
                {
                    "role": "user",
                    "content": "Consigne : %s\n\n--- %s ---\n%s"
                    % (consigne, fichier, contenu),
                },
            ],
            max_tokens,
            cle,
        )
    except Exception as exc:
        print("  ECHEC de l'appel : %s" % exc)
        if "10061" in str(exc) or "refus" in str(exc).lower() or "refused" in str(exc).lower():
            print("  La passerelle ne repond pas sur %s." % agent.PASSERELLE)
            print("  Remonter la pile :  .\\scripts\\start.ps1")
        return 1

    plan = agent.plan_de(resultat["adresse"])
    print(
        "  servi    : %s [%s] en %.0f s, %d tokens, cout %s"
        % (
            resultat["servi_par"],
            plan,
            resultat["duree"],
            resultat["tokens"],
            resultat["cout"],
        )
    )
    if plan == "anthropic":
        print("  [!] servi par Anthropic : cette tache a ete FACTUREE.")

    charge = analyser_reponse(resultat["texte"])
    if charge is None:
        if resultat.get("tronque"):
            print(
                "  Reponse COUPEE par le plafond de sortie (%d tokens demandes)."
                % max_tokens
            )
            print(
                "  Relancez avec --max-tokens %d, ou restreignez la consigne."
                % (max_tokens * 2)
            )
        else:
            print("  Reponse inexploitable (aucun bloc @@ reconnu). Debut de la reponse :")
        print("  " + resultat["texte"].strip()[:400].replace("\n", "\n  "))
        return 1

    print("  analyse  : %s" % str(charge.get("analyse", ""))[:400])
    remplacements = charge.get("remplacements") or []
    if not remplacements:
        print("  Aucun remplacement propose : le modele n'a rien trouve a corriger.")
        return 0

    poses, rejets = appliquer(cible, remplacements)
    print("  %d/%d remplacement(s) appliques" % (poses, len(remplacements)))
    for r in rejets:
        print("     [rejet] %s" % r)
    for r in remplacements:
        if r.get("pourquoi"):
            print("     - %s" % str(r["pourquoi"])[:180])
    if not poses:
        return 1

    if verifier:
        # Substitution du placeholder puis découpage sécurisé des arguments.
        commande = verifier.replace("{fichier}", fichier.replace("\\", "/"))
        print("  verification : %s" % commande)
        args = shlex.split(commande)
        v = subprocess.run(
            args,
            cwd=chemin_arbre,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if v.returncode != 0:
            print(
                "  VERIFICATION ECHOUEE (code %d) — arbre conserve pour inspection"
                % v.returncode
            )
            print("  " + (v.stderr or v.stdout).strip()[:600].replace("\n", "\n  "))
            return 1
        print("  verification OK")

    d = git(["diff", "--stat"], cwd=chemin_arbre)
    print("  " + (d.stdout.strip() or "(aucun ecart)").replace("\n", "\n  "))
    print("\n  Pour examiner :  git -C %s diff" % chemin_arbre)
    print("  Pour retenir  :  python scripts/nexus_worktree.py --fusionner %s" % nom)
    print("  Pour jeter    :  python scripts/nexus_worktree.py --jeter %s" % nom)
    return 0


VERIFICATEURS: dict[str, str] = {
    ".py": "python -c \"import ast,io;ast.parse(io.open('{fichier}',encoding='utf-8').read())\"",
    ".js": "node --check {fichier}",
    ".mjs": "node --check {fichier}",
    ".ps1": "powershell -NoProfile -Command \"$e=$null;"
            "[void][System.Management.Automation.Language.Parser]::ParseFile("
            "(Resolve-Path '{fichier}'),[ref]$null,[ref]$e); if($e){exit 1}\"",
    ".yaml": "python -c \"import yaml,io;yaml.safe_load(io.open('{fichier}',encoding='utf-8'))\"",
    ".yml": "python -c \"import yaml,io;yaml.safe_load(io.open('{fichier}',encoding='utf-8'))\"",
    ".json": "python -c \"import json,io;json.load(io.open('{fichier}',encoding='utf-8'))\"",
}


def verificateur_par_defaut(fichier: str) -> str | None:
    """
    Commande de contrôle déduite de l'extension.

    Sans elle, chaque appel devait porter un `--verifier` écrit à la main,
    et l'oublier laissait passer une proposition jamais compilée. Un
    garde-fou qu'il faut penser à activer n'est pas un garde-fou : la
    fois où on l'oublie est exactement celle où le modèle a cassé le
    fichier.
    """
    return VERIFICATEURS.get(os.path.splitext(fichier)[1].lower())


def lister() -> int:
    r = git(["worktree", "list"])
    print(r.stdout.strip() or "(aucun arbre)")
    return 0


def fusionner(nom: str) -> int:
    """
    Rapatrie le travail de l'arbre, après commit dans sa propre branche.

    Le commit a lieu DANS l'arbre : ainsi la proposition du modèle reste
    identifiable dans l'historique, et peut être révoquée seule.
    """
    chemin = arbre_de(nom)
    if not os.path.isdir(chemin):
        print("Arbre inconnu : %s" % nom)
        return 1
    if not git(["diff", "--quiet"], cwd=chemin).returncode:
        print("Aucune modification a fusionner dans %s" % nom)
        return 1
    add_res = git(["add", "-A"], cwd=chemin)
    if add_res.returncode != 0:
        print("Echec de l'ajout des modifications : " + (add_res.stderr or add_res.stdout).strip())
        return 1
    c = git(["commit", "-m", "agent local : %s" % nom], cwd=chemin)
    if c.returncode != 0:
        print(c.stderr.strip() or c.stdout.strip())
        return 1
    m = git(["merge", "--no-ff", "agent/" + nom, "-m", "Fusion agent local : %s" % nom])
    if m.returncode != 0:
        print("Fusion refusee :\n" + (m.stderr or m.stdout).strip())
        return 1
    print("Fusionne. Arbre conserve — utilisez --jeter %s pour le retirer." % nom)
    return 0


def jeter(nom: str) -> int:
    chemin = arbre_de(nom)
    r = git(["worktree", "remove", "--force", chemin])
    if r.returncode != 0:
        print("Echec de la suppression du worktree : " + (r.stderr or r.stdout).strip())
    if os.path.isdir(chemin):
        shutil.rmtree(chemin, ignore_errors=True)
    b = git(["branch", "-D", "agent/" + nom])
    if b.returncode != 0:
        print("Echec de la suppression de la branche : " + (b.stderr or b.stdout).strip())
    print("Arbre et branche retires : %s" % nom)
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--nom", help="Nom de la tache, donc de l'arbre et de la branche.")
    p.add_argument("--racine",
                   help="Racine du depot a traiter. Par defaut, celle du "
                        "projet courant -- jamais celle de la plateforme.")
    p.add_argument("--fichier", help="Fichier a relire, relatif a la racine.")
    p.add_argument(
        "--fichiers",
        nargs="+",
        metavar="CHEMIN",
        help="Plusieurs fichiers, traites en chaine. Le modele reste "
        "charge d'un fichier a l'autre : les appels suivants "
        "coutent quelques secondes au lieu d'une minute.",
    )
    p.add_argument("--modele", default="qwen3-coder-30b-local")
    p.add_argument("--consigne", help="Ce que le modele doit corriger.")
    p.add_argument("--verifier", help="Commande de validation, '{fichier}' est substitue.")
    p.add_argument(
        "--max-tokens",
        type=int,
        default=8000,
        help="Nombre maximal de tokens pour la réponse du modèle.",
    )
    p.add_argument("--lister", action="store_true")
    p.add_argument("--fusionner", metavar="NOM")
    p.add_argument("--jeter", metavar="NOM")
    a = p.parse_args()

    # --racine force la racine du depot traite. Sans elle, celle du projet
    # courant s'applique -- decouverte, jamais celle de la plateforme.
    if a.racine:
        global ROOT, ARBRES
        ROOT = os.path.abspath(a.racine)
        ARBRES = os.path.join(os.path.dirname(ROOT), ".nexus-arbres")

    if a.lister:
        return lister()
    if a.fusionner:
        return fusionner(a.fusionner)
    if a.jeter:
        return jeter(a.jeter)
    cibles = a.fichiers or ([a.fichier] if a.fichier else [])
    if not (cibles and a.consigne):
        p.print_help()
        return 1

    resultats: list[tuple[str, str, int]] = []
    for cible in cibles:
        nom = a.nom if (a.nom and len(cibles) == 1) else re.sub(
            r"[^a-zA-Z0-9_-]", "-", os.path.splitext(os.path.basename(cible))[0]
        )
        if a.nom and len(cibles) > 1:
            nom = "%s-%s" % (a.nom, nom)
        verif = a.verifier or verificateur_par_defaut(cible)
        if len(cibles) > 1:
            print("\n" + "#" * 72)
            print("#  %s" % cible)
            print("#" * 72)
        code = lancer(nom, cible, a.modele, a.consigne, verif, a.max_tokens)
        resultats.append((cible, nom, code))

    if len(cibles) > 1:
        print("\n" + "=" * 72)
        retenus = [r for r in resultats if r[2] == 0]
        print("  %d fichier(s) traites, %d proposition(s) exploitables"
              % (len(resultats), len(retenus)))
        for cible, nom, code in resultats:
            print("    %-40s %s" % (cible, "retenue" if code == 0 else "sans suite"))
        if retenus:
            print("\n  Examiner puis retenir :")
            for _, nom, _ in retenus:
                print("    git -C %s diff" % arbre_de(nom))
                print("    python scripts/nexus_worktree.py --fusionner %s" % nom)
        print("=" * 72)
    return 0 if all(c == 0 for _, _, c in resultats) else 1


if __name__ == "__main__":
    sys.exit(main())
