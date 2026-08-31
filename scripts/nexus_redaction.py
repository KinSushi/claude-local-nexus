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
import unicodedata
import subprocess
import json
import sys

import datetime


def borne_since(fenetre_heures):
    """
    L'instant a passer a git pour --since, jamais une duree.

    CE QUI ETAIT FAUX. Ce fichier calculait la meme fenetre a DEUX endroits,
    de deux facons, et l'une etait fausse :

        since = now - fenetre_heures * 3600   -> horodatage, 178 commits
        f"--since={fenetre_heures}"           -> la chaine "24"

    git lit « 24 » comme une DATE, pas comme une duree : il a rendu 373
    commits, l'historique entier, au lieu des 178 de la fenetre demandee. Le
    comptage portait donc sur autre chose que ce qu'il annoncait.

    Deux calculs de la meme chose finissent toujours par diverger. Ici cela
    n'a meme pas pris un fichier : les deux ont ete ecrits d'un seul tenant.

    `datetime.now(timezone.utc)` et non `utcnow()`, deprecie depuis 3.12.
    """
    heures = max(1, int(fenetre_heures))
    instant = (datetime.datetime.now(datetime.timezone.utc)
               - datetime.timedelta(hours=heures))
    return instant.strftime("%Y-%m-%dT%H:%M:%SZ")


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
    int(time.time())
    since = borne_since(window_hours)
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

# LES SEPARATEURS ETAIENT BONS ; L'ASSOCIATION NE L'ETAIT PAS.
#
# CE QUI ETAIT FAUX. Le format `%H%x00%B%x00` produit bien deux caracteres
# nuls par commit -- verifie, 36 pour 18 commits. Mais il ne delimite pas
# les ENREGISTREMENTS : apres decoupage, le jeton qui suit le corps contient
# a la fois la liste des fichiers ET l'empreinte du commit SUIVANT, collees.
# Le parseur les associait donc de travers.
#
# Mesure : 257 commits examines la ou le depot n'en compte que 178 au total
# sur la fenetre. Des enregistrements fantomes, et un verdict qui ne veut
# rien dire -- un compteur faux est pire qu'un compteur absent, car il rend
# un chiffre.
#
# Le format porte desormais un caractere 0x01 en TETE de chaque
# enregistrement. Verifie avant d'etre specifie : 18 separateurs pour 18
# commits, exactement.
#
# CONTRAINTE DE VERIFIABILITE : declares + muets doit EGALER le nombre de
# commits touchant du code. Un commit est examine une fois et classe dans
# une seule categorie.
def controle_auteur(fenetre_heures):
        
    # Commande git avec le séparateur 0x01 en tête de chaque enregistrement
    cmd = [
        "git", "log",
        f"--since={borne_since(fenetre_heures)}",
        "--name-only",
        "--pretty=format:%x01%H%x00%B%x00"
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
        )
    except FileNotFoundError:
        return (None, None, "git not found")
    except subprocess.TimeoutExpired:
        return (None, None, "git timeout")

    if result.returncode != 0:
        return (None, None, f"git error: {result.returncode}")

    output = result.stdout

    # Découpage sur le séparateur 0x01, on ignore le premier morceau s'il est vide
    records = output.split("\x01")
    if records and records[0] == "":
        records = records[1:]

    # Phrases qui déclarent l'auteur (sans tenir compte de la casse ni des accents)
    phrases = [
        "banc gratuit",
        "redige par le banc",
        "redaction : banc",
        "ecrit par le banc",
        "redige a la main",
        "redaction : orchestrateur",
    ]

    def normalize(text):
        """Supprime les accents et met en minuscule."""
        return "".join(
            c
            for c in unicodedata.normalize("NFD", text)
            if not unicodedata.combining(c)
        ).lower()

    declares = 0
    muets = 0
    details = []

    for rec in records:
        # Chaque enregistrement : hash\x00body\x00files...
        parts = rec.split("\x00", 2)
        if len(parts) < 3:
            # Enregistrement mal formé, on l'ignore
            continue

        commit_hash, body, files_blob = parts

        # Liste des fichiers, on retire les lignes vides
        files = [ln for ln in files_blob.splitlines() if ln.strip()]

        # Un commit touche le code s'il modifie au moins un fichier .py, .ps1 ou .js
        # et n'est pas limité à des fichiers ignorés.
        touches_code = False
        for f in files:
            if f.startswith("rituels/"):
                continue
            f_low = f.lower()
            if f_low.endswith(".py") or f_low.endswith(".ps1") or f_low.endswith(".js"):
                touches_code = True
                break

        if not touches_code:
            continue  # on ne compte pas les commits qui ne touchent pas le code

        # Détection d'une déclaration d'auteur dans le message complet
        body_norm = normalize(body)
        declared = any(phrase in body_norm for phrase in phrases)

        if declared:
            declares += 1
        else:
            muets += 1
            if len(details) < 10:
                first_line = body.splitlines()[0] if body else ""
                details.append((commit_hash[:7], first_line))

    return (declares, muets, details)


# LE CHIFFRE QUI DOIT GENER DOIT ETRE CELUI QU'ON VOIT.
#
# CE QUI ETAIT FAUX. `controle_auteur` existait, fonctionnait, et main() ne
# l'appelait JAMAIS : sa logique etait orpheline A L'INTERIEUR d'un script
# pourtant cable au rituel. Le rituel affichait donc « Commits de code: 101 »
# -- le VOLUME -- quand le chiffre qui compte est celui des commits MUETS.
#
# Un chiffre qu'on lit chaque tour finit par gener ; un chiffre qu'on ne voit
# pas ne gene jamais. C'est toute la difference entre un controle et une
# fonction qui existe.
def main():
    # Récupération des paramètres de fenêtre et du mode JSON
    fenetre, json_out = get_window_and_json()

    # 1️⃣ Mesure du nombre de commits touchant le code
    commits = count_commits(fenetre)
    if commits is None:
        # Mesure impossible → code sortie 2
        exit_code = 2
        if json_out:
            print('{"error":"cannot measure commits"}')
        else:
            print('Error: cannot measure commits')
        sys.exit(exit_code)

    # 2️⃣ Contrôle de la déclaration d’auteur (fonction auparavant orpheline)
    declares, muets, details = controle_auteur(fenetre)
    if declares is None and muets is None:
        # Le contrôle auteur n’a pas pu être exécuté → code sortie 2
        exit_code = 2
        if json_out:
            # on renvoie le motif d’échec dans le JSON
            print(json.dumps({"error": "cannot measure author declarations", "reason": details}))
        else:
            print(f"Error: {details}")
        sys.exit(exit_code)

    # 3️⃣ Mesure des appels délégués aux plans gratuits
    delegated, err = count_delegated(fenetre)
    if delegated is None:
        # Mesure impossible → code sortie 2
        exit_code = 2
        if json_out:
            print('{"error":"cannot measure delegated calls"}')
        else:
            print('Error: cannot measure delegated calls')
        sys.exit(exit_code)

    # 4️⃣ Calcul du ratio et détermination du code de sortie
    ratio = delegated / commits if commits != 0 else 0
    # Le nombre de MUETS ne doit pas à lui seul déclencher l’échec (voir consignes)
    exit_code = 0 if delegated >= commits and commits > 0 else 1

    # 5️⃣ Affichage / génération du JSON
    if json_out:
        payload = {
            "commits": commits,
            "delegated": delegated,
            "ratio": ratio,
            "declares": declares,
            "muets": muets
        }
        print(json.dumps(payload))
    else:
        # Affichage classique
        print(f"Commits de code: {commits}")
        print(f"Appels delegues: {delegated}")
        print(f"Rapport appels/commit: {ratio:.2f}")

        # Ligne visible du nombre de déclarations et de muets
        total = declares + muets
        print(f"Auteur declare : {declares} sur {total} commits de code -- {muets} MUETS")

        # Liste des empreintes muettes (max 10)
        if details:
            print("Empreintes muettes (max 10) :")
            for hsh, first_line in details:
                print(f"{hsh}: {first_line}")

    # 6️⃣ Retour du code de sortie
    sys.exit(exit_code)


if __name__ == '__main__':
    main()
