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

Le format d'échange n'est pas un diff. Un diff unifié suppose que le
modèle compte correctement les lignes de contexte, ce qu'un modèle de
14 milliards de paramètres rate régulièrement ; l'échec est alors silencieux
(le patch ne s'applique pas) ou pire, s'applique au mauvais endroit. Le
modèle rend donc des remplacements littéraux `{avant, apres}`, que le
script applique lui-même après avoir vérifié que `avant` apparaît
exactement une fois. Une occurrence ambiguë est un refus, pas un pari.

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
import json
import os
import re
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nexus_agent as agent  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = agent.ROOT
# Hors du dépôt : un arbre de travail placé dedans serait vu par git comme
# un dépôt imbriqué, et `git add -A` l'ajouterait à l'index — c'est
# exactement l'accident déjà survenu une fois sur ce dépôt.
ARBRES = os.path.join(os.path.dirname(ROOT), ".nexus-arbres")

SYSTEME = (
    "Tu es un relecteur de code rigoureux. Tu reponds UNIQUEMENT par un objet "
    "JSON valide, sans texte avant ni apres, sans balises de code.\n\n"
    "Format exact :\n"
    '{"analyse": "<ce que tu as constate, en francais, 3 phrases maximum>",\n'
    ' "remplacements": [{"avant": "<extrait EXACT du fichier>", '
    '"apres": "<le remplacement>", "pourquoi": "<la defaillance evitee>"}]}\n\n'
    "Regles imperatives :\n"
    "- 'avant' doit etre un extrait COPIE CARACTERE POUR CARACTERE du fichier "
    "fourni, indentation comprise. S'il ne correspond pas exactement, ta "
    "proposition sera rejetee.\n"
    "- 'avant' doit etre assez long pour n'apparaitre QU'UNE SEULE FOIS dans "
    "le fichier.\n"
    "- Ne propose que des corrections dont tu es sur. Une liste vide est une "
    "reponse acceptable et preferable a une invention.\n"
    "- Les commentaires que tu ecris expliquent POURQUOI le code est ainsi, "
    "jamais ce qu'il fait. Ils sont en francais."
)


def git(args: list[str], cwd: str | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git"] + args, cwd=cwd or ROOT,
        capture_output=True, text=True, encoding="utf-8", errors="replace",
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


def extraire_json(texte: str) -> dict | None:
    """
    Récupère l'objet JSON d'une réponse.

    Les modèles locaux encadrent volontiers leur JSON de ```json, ou le
    font précéder d'une phrase d'introduction malgré la consigne. Refuser
    ces réponses reviendrait à jeter un travail correct pour un défaut de
    forme, donc on cherche le premier objet équilibré plutôt que d'exiger
    une réponse nue.
    """
    texte = texte.strip()
    bloc = re.search(r"```(?:json)?\s*(.+?)```", texte, re.S)
    if bloc:
        texte = bloc.group(1).strip()
    debut = texte.find("{")
    if debut < 0:
        return None
    profondeur, dans_chaine, echappe = 0, False, False
    for i in range(debut, len(texte)):
        c = texte[i]
        if echappe:
            echappe = False
            continue
        if c == "\\":
            echappe = True
            continue
        if c == '"':
            dans_chaine = not dans_chaine
            continue
        if dans_chaine:
            continue
        if c == "{":
            profondeur += 1
        elif c == "}":
            profondeur -= 1
            if profondeur == 0:
                try:
                    return json.loads(texte[debut:i + 1])
                except Exception:
                    return None
    return None


def appliquer(chemin: str, remplacements: list[dict]) -> tuple[int, list[str]]:
    """
    Applique les remplacements, en refusant tout ce qui est ambigu.

    Un `avant` absent signifie que le modèle a paraphrasé le fichier au lieu
    de le citer ; un `avant` présent plusieurs fois signifie qu'on ne sait
    pas laquelle il visait. Dans les deux cas, appliquer serait deviner.
    """
    source = io.open(chemin, encoding="utf-8").read()
    poses, rejets = 0, []
    for i, r in enumerate(remplacements or [], 1):
        avant, apres = r.get("avant"), r.get("apres")
        if not isinstance(avant, str) or not isinstance(apres, str) or not avant:
            rejets.append("#%d : champs 'avant'/'apres' absents ou non textuels" % i)
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
        io.open(chemin, "w", encoding="utf-8", newline="\n").write(source)
    return poses, rejets


def lancer(nom, fichier, modele, consigne, verifier, max_tokens) -> int:
    complet = os.path.join(ROOT, fichier)
    if not agent.dans_depot(complet) or agent.est_secret(complet):
        print("Fichier refuse : hors du depot ou susceptible de porter un secret.")
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
            [{"role": "system", "content": SYSTEME},
             {"role": "user", "content":
              "Consigne : %s\n\n--- %s ---\n%s" % (consigne, fichier, contenu)}],
            max_tokens, cle,
        )
    except Exception as exc:
        print("  ECHEC de l'appel : %s" % exc)
        return 1

    plan = agent.plan_de(resultat["adresse"])
    print("  servi    : %s [%s] en %.0f s, %d tokens, cout %s"
          % (resultat["servi_par"], plan, resultat["duree"],
             resultat["tokens"], resultat["cout"]))
    if plan == "anthropic":
        print("  [!] servi par Anthropic : cette tache a ete FACTUREE.")

    charge = extraire_json(resultat["texte"])
    if charge is None:
        print("  Reponse inexploitable (aucun JSON valide). Debut de la reponse :")
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
        commande = verifier.replace("{fichier}", fichier.replace("\\", "/"))
        print("  verification : %s" % commande)
        v = subprocess.run(commande, shell=True, cwd=chemin_arbre,
                           capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        if v.returncode != 0:
            # L'arbre est conservé tel quel : c'est la trace de l'échec, et
            # la seule façon de comprendre ce que le modèle a cassé.
            print("  VERIFICATION ECHOUEE (code %d) — arbre conserve pour inspection" % v.returncode)
            print("  " + (v.stderr or v.stdout).strip()[:600].replace("\n", "\n  "))
            return 1
        print("  verification OK")

    d = git(["diff", "--stat"], cwd=chemin_arbre)
    print("  " + (d.stdout.strip() or "(aucun ecart)").replace("\n", "\n  "))
    print("\n  Pour examiner :  git -C %s diff" % chemin_arbre)
    print("  Pour retenir  :  python scripts/nexus_worktree.py --fusionner %s" % nom)
    print("  Pour jeter    :  python scripts/nexus_worktree.py --jeter %s" % nom)
    return 0


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
    git(["add", "-A"], cwd=chemin)
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
    git(["worktree", "remove", "--force", chemin])
    if os.path.isdir(chemin):
        shutil.rmtree(chemin, ignore_errors=True)
    git(["branch", "-D", "agent/" + nom])
    print("Arbre et branche retires : %s" % nom)
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--nom", help="Nom de la tache, donc de l'arbre et de la branche.")
    p.add_argument("--fichier", help="Fichier a relire, relatif a la racine.")
    p.add_argument("--modele", default="qwen3-coder-30b-local")
    p.add_argument("--consigne", help="Ce que le modele doit corriger.")
    p.add_argument("--verifier", help="Commande de validation, '{fichier}' est substitue.")
    p.add_argument("--max-tokens", type=int, default=3000)
    p.add_argument("--lister", action="store_true")
    p.add_argument("--fusionner", metavar="NOM")
    p.add_argument("--jeter", metavar="NOM")
    a = p.parse_args()

    if a.lister:
        return lister()
    if a.fusionner:
        return fusionner(a.fusionner)
    if a.jeter:
        return jeter(a.jeter)
    if not (a.nom and a.fichier and a.consigne):
        p.print_help()
        return 1
    return lancer(a.nom, a.fichier, a.modele, a.consigne, a.verifier, a.max_tokens)


if __name__ == "__main__":
    sys.exit(main())
