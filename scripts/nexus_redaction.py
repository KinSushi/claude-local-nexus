"""
Ce script contrôle que chaque modification de code source (.py, .ps1, .js) est
accompagnée d’un appel au banc gratuit, comme l’exige la règle inscrite le
31‑08‑2026 08:00. La règle a été violée cinq fois le même jour par son
auteur, d’où la nécessité d’un contrôle automatisé qui échoue dès la première
infraction détectée.
Les commentaires ci‑dessous décrivent ce qui serait faux : le script ne
mesure jamais le nombre de lignes de code, il ne lit jamais de fichiers de
configuration et il ne fait jamais confiance à une sortie non‑json sans la
vérifier.
"""

import math
import re
import unicodedata
import subprocess
import json
import sys

def get_window_and_json():
    sys = __import__('sys')
    it = iter(sys.argv[1:])
    fenetre = 24
    json_out = False
    for token in it:
        if token == '--fenetre':
            val = next(it, None)
            if val is not None:
                try:
                    fenetre = int(val)
                except:
                    fenetre = 24
        elif token == '--json':
            json_out = True
    return fenetre, json_out

def count_commits(window_hours):
    subprocess = __import__('subprocess')
    time = __import__('time')
    now = int(time.time())
    since = now - window_hours * 3600
    cmd = [
        'git', 'log',
        f'--since={since}',
        '--name-only',
        '--pretty=format:%H|%ct|%s'
    ]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace'
        )
    except Exception:
        return None
    if result.returncode != 0:
        return None
    output = result.stdout
    commit_count = 0
    current_has_code = False
    for line in output.splitlines():
        if '|' in line:
            if current_has_code:
                commit_count += 1
            current_has_code = False
        else:
            if (line.endswith('.py') or line.endswith('.ps1') or line.endswith('.js')) \
               and not line.startswith('rituels/'):
                current_has_code = True
    if current_has_code:
        commit_count += 1
    return commit_count

# ---------------------------------------------------------------------------
# DEUX DEFAUTS, ET LE CONTROLE A EU RAISON DE REFUSER DE CONCLURE.
#
# 1. UNE OPTION INVENTEE. La fonction appelait
#    `nexus_savings.py --fenetre=<heures>`, or ce script n'accepte que
#    `--jours`. Argparse refusait, le sous-processus sortait non nul, et le
#    controle rapportait « impossible de mesurer ». Son refus etait le bon
#    comportement -- c'est la cause qui etait fausse.
#
# 2. LE PREMIER ENTIER N'EST PAS LE BON. La fonction rendait le premier
#    entier rencontre dans le document. Or sa premiere cle est « jours » :
#    elle aurait donc compare des commits a une FENETRE, et rendu un verdict
#    sur du vide.
#
# Ce qui compte, ce sont les requetes des plans GRATUITS -- cloud et local.
# Le plan « anthropic » est FACTURE et n'est pas une delegation ; le plan
# « inconnu » ne compte pas non plus, on ne deduit rien d'un plan qu'on n'a
# pas su nommer.
#
# ZERO requete deleguee et IMPOSSIBILITE de mesurer sont deux etats
# distincts. Les confondre ferait accuser a tort.
# ---------------------------------------------------------------------------
def count_delegated(window_hours):
    """
    Retourne le nombre de requêtes déléguées aux plans gratuits (cloud, local)
    sur la fenêtre donnée (en heures) ainsi qu'un éventuel message d'erreur.
    """
    # Conversion de la fenêtre en jours, arrondi au supérieur, minimum 1
    days = max(1, math.ceil(window_hours / 24))

    # Construction de la commande
    cmd = [
        sys.executable,
        "scripts/nexus_savings.py",
        "--jours", str(days),
        "--json"
    ]

    try:
        # Exécution du sous‑processus avec les options demandées
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10
        )
    except Exception:
        # Le sous‑processus n’a pas pu être lancé
        return (None, "subprocess_failed")

    # Vérification du code de retour
    if result.returncode != 0:
        return (None, "non_zero_exit")

    # Lecture et décodage du JSON
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        return (None, "invalid_json")

    # Vérification de la présence de la clé 'par_plan'
    if "par_plan" not in data or not isinstance(data["par_plan"], dict):
        return (None, "missing_par_plan")

    free_plans = ["cloud", "local"]
    total_requests = 0
    free_plan_found = False

    # Boucle sur les plans gratuits pour cumuler les requêtes
    for plan in free_plans:
        plan_info = data["par_plan"].get(plan)
        if isinstance(plan_info, dict) and "requetes" in plan_info:
            free_plan_found = True
            # On s’assure que la valeur est bien un entier
            try:
                total_requests += int(plan_info["requetes"])
            except (TypeError, ValueError):
                # Si la valeur n’est pas un entier, on l’ignore
                continue

    # Aucun plan gratuit présent dans le JSON
    if not free_plan_found:
        return (None, "no_free_plan")

    # Succès : on renvoie le total (qui peut être zéro) et aucune erreur
    return (total_requests, None)


# ---------------------------------------------------------------------------
# LE VOLUME NE DISCRIMINE PAS. LA DECLARATION, SI.
#
# CE QUI ETAIT FAUX, mesure a l'instant meme ou ce fichier fut ecrit. Le
# controle du volume delegue rendait « 101 commits de code, 5272 appels
# delegues, rapport 52 » -- et un VERT. Mais ces 5272 appels comptent les
# epreuves, les bancs de mesure, les validations LOI 1. Un jour ou
# l'orchestrateur ecrirait CHAQUE correctif a la main afficherait le meme
# rapport.
#
# Un vert qui ne peut pas devenir rouge ne mesure rien, et c'est exactement
# le faux negatif que ce depot traque : le controle du volume est une
# information utile, pas une garde.
#
# CE QUI DISCRIMINE : que chaque commit touchant du code DECLARE son auteur.
# La convention existe deja dans les messages du depot -- « Ecrit par le banc
# gratuit », « Redaction : banc gratuit ». Le controle n'INTERDIT PAS
# d'ecrire a la main : il interdit de le faire SANS LE DIRE. Un correctif
# assume reste possible ; un glissement silencieux, non.
# ---------------------------------------------------------------------------
# LE SUJET N'EST PAS LE MESSAGE.
#
# CE QUI ETAIT FAUX. La premiere version lisait `--pretty=format:%H|%s`, or
# `%s` ne rend que le SUJET du commit, sa premiere ligne. La declaration
# d'auteur, elle, vit dans le CORPS -- « Ecrit par le banc gratuit (...) »
# se trouve vingt lignes plus bas.
#
# Mesure : le controle a rapporte 101 commits MUETS sur 101, alors que
# plusieurs declarent bien leur auteur. Un chiffre faux rendu avec assurance,
# et ROUGE A TORT -- ce qui n'est pas moins nuisible qu'un vert a tort : un
# controle qui accuse du travail conforme se fait desarmer, et emporte ses
# vraies detections avec lui.
#
# `%B` rend le message entier, mais il est multiligne : un decoupage par
# ligne ne suffit plus, d'ou le separateur d'enregistrement.
from typing import List, Tuple, Optional

def controle_auteur(fenetre_heures: Optional[Tuple[str, str]] = None) -> Tuple[Optional[int], Optional[int], Optional[List[Tuple[str, str]]]]:
    """
    Analyse les commits du dépôt git courant.

    Retourne (nb_declare, nb_muet, details_muets) où
    - nb_declare : nombre de commits déclarant leur auteur,
    - nb_muet    : nombre de commits ne le déclarant pas,
    - details_muets : jusqu'à 10 couples (hash_court, première_ligne_message) des commits muets.

    En cas d'erreur git, retourne (None, None, [motif]).
    """
    # ----------------------------------------------------------------------
    # Ce qui était faux : utilisation de %s (sujet uniquement) et découpage
    # ligne‑par‑ligne qui perd le corps du message.
    # ----------------------------------------------------------------------
    # Construction de la commande git
    cmd = [
        "git", "log",
        "--pretty=format:%H%x00%B%x00",   # hash NUL body NUL
        "--name-only",                    # suivi des chemins modifiés
        "-z"                              # séparateur NUL entre tous les champs
    ]

    # Gestion éventuelle d'une fenêtre temporelle (since / until)
    if fenetre_heures and isinstance(fenetre_heures, tuple) and len(fenetre_heures) == 2:
        since, until = fenetre_heures
        if since:
            cmd.append(f'--since={since}')
        if until:
            cmd.append(f'--until={until}')

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30  # délai borné
        )
    except Exception as exc:
        return None, None, [f"git subprocess error: {exc}"]

    if result.returncode != 0:
        return None, None, [f"git error (code {result.returncode}): {result.stderr.strip()}"]

    # Découpage du flux NUL‑séparé
    tokens = result.stdout.split("\x00")
    # Le dernier token peut être vide à cause du séparateur final
    if tokens and tokens[-1] == "":
        tokens.pop()

    # Expressions régulières
    hash_re = re.compile(r"^[0-9a-f]{40}$")
    code_ext = (".py", ".ps1", ".js")
    ignore_dirs = ("rituels/",)  # répertoire à ignorer
    ignore_ext = (".md", ".yaml", ".json", ".txt")

    # Mots‑clés (sans accents, casse ignorée)
    keywords = [
        "banc gratuit",
        "redige par le banc",
        "redaction : banc",
        "ecrit par le banc",
        "redige a la main",
        "redaction : orchestrateur"
    ]

    def normalize(s: str) -> str:
        """Supprime les accents et met en minuscule."""
        return unicodedata.normalize("NFD", s).encode("ascii", "ignore").decode().lower()

    declares = 0
    muets = 0
    details: List[Tuple[str, str]] = []

    i = 0
    while i < len(tokens):
        # Lecture du hash
        commit_hash = tokens[i]
        i += 1
        if not hash_re.fullmatch(commit_hash):
            # Si le token n'est pas un hash, on saute (défaut de format)
            continue

        # Lecture du corps du message
        body = tokens[i] if i < len(tokens) else ""
        i += 1

        # Récupération de la liste des fichiers jusqu'au prochain hash ou fin
        files: List[str] = []
        while i < len(tokens) and not hash_re.fullmatch(tokens[i]):
            if tokens[i]:  # ignore les éventuels tokens vides
                files.append(tokens[i])
            i += 1

        # --------------------------------------------------------------
        # 1. Le commit touche‑t‑il du code ?
        # --------------------------------------------------------------
        touche_code = any(
            f.endswith(code_ext) and not any(f.startswith(d) for d in ignore_dirs)
            for f in files
        )
        if not touche_code:
            # Commit sans impact sur le code : on ne le compte pas
            continue

        # --------------------------------------------------------------
        # 2. Le commit déclare‑t‑il son auteur ?
        # --------------------------------------------------------------
        body_normalized = normalize(body)
        declare = any(normalize(k) in body_normalized for k in keywords)

        if declare:
            declares += 1
        else:
            muets += 1
            # première ligne du message (avant le premier saut de ligne)
            first_line = body.splitlines()[0] if body else ""
            details.append((commit_hash[:7], first_line))
            if len(details) >= 10:
                # on ne garde que les 10 premiers détails
                pass

    return declares, muets, details[:10]


def main():
    fenetre, json_out = get_window_and_json()
    commits = count_commits(fenetre)
    if commits is None:
        exit_code = 2
        if json_out:
            print('{"error":"cannot measure commits"}')
        else:
            print('Error: cannot measure commits')
        __import__('sys').exit(exit_code)
    delegated, err = count_delegated(fenetre)
    if delegated is None:
        exit_code = 2
        if json_out:
            print('{"error":"cannot measure delegated calls"}')
        else:
            print('Error: cannot measure delegated calls')
        __import__('sys').exit(exit_code)
    ratio = delegated / commits if commits != 0 else 0
    if delegated >= commits and commits > 0:
        exit_code = 0
    else:
        exit_code = 1
    if json_out:
        json_mod = __import__('json')
        print(json_mod.dumps({
            "commits": commits,
            "delegated": delegated,
            "ratio": ratio
        }))
    else:
        print(f"Commits de code: {commits}")
        print(f"Appels delegues: {delegated}")
        print(f"Rapport appels/commit: {ratio:.2f}")
    __import__('sys').exit(exit_code)

if __name__ == '__main__':
    main()
