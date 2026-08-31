#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import subprocess
import sys
import shutil
import json
import tempfile

# Constantes
MARGE_DISQUE_GO = 50
DELAI_PULL_S = 1800

def execute_command(cmd, encoding='utf-8'):
    """Execute une commande et retourne stdout, stderr, code de sortie."""
    try:
        # `text=False` ET `encoding=` se contredisent : le premier demande des
        # octets, le second du texte. Le `.decode()` qui suivait s'appliquait
        # alors a une chaine, levait AttributeError, et l'except generique
        # rendait un code non nul -- rapporte a l'ecran comme « Ollama
        # introuvable » alors qu'Ollama repondait parfaitement. Un diagnostic
        # faux ne d'un defaut interne envoie chercher au mauvais endroit.
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            encoding=encoding,
            errors='replace'
        )
        return result.stdout, result.stderr, result.returncode
    except Exception as e:
        return '', str(e), 1

def get_disk_space():
    """Retourne l'espace libre en Go ou None si impossible."""
    try:
        total, used, free = shutil.disk_usage(os.path.abspath('.'))
        return free // (1024**3)
    except Exception:
        # PIEGE A : os.statvfs n'existe pas sous Windows
        return None

def parse_size(size_str):
    """Convertit une taille comme '6.7 GB' ou '725 MB' en Go."""
    size_str = size_str.strip()
    if size_str.endswith('GB'):
        return float(size_str[:-2])  # Extrait le nombre avant 'GB'
    if size_str.endswith('MB'):
        return float(size_str[:-2]) / 1024.0  # Convertit MB en Go
    # PIEGE B : Ne pas confondre colonne taille avec ID
    return 0.0

# ---------------------------------------------------------------------------
# L'ETAT SE LIT SUR L'EMPREINTE, JAMAIS SUR LE TEXTE DE LA SORTIE.
#
# CE QUI ETAIT FAUX, mesure le 2026-08-31 sur la vraie sortie de la commande.
# Un `ollama pull` sur un modele DEJA A JOUR affiche :
#     pulling manifest / pulling <couche>: 100% / verifying sha256 digest
#     writing manifest / success
# et sort en code 0. Il ne dit JAMAIS « already up to date », et jamais
# « done ». Or le code classait ainsi :
#     'already up to date' present  -> deja a jour
#     'pulling' ET 'done' presents  -> mis a jour
#     sinon                         -> ECHEC
# Aucune des deux premieres conditions ne pouvait etre vraie. CHAQUE modele
# aurait donc ete classe ECHEC, et l'outil aurait rapporte cent pour cent de
# pannes sur un parc parfaitement sain. Un outil qui invente des pannes est
# pire qu'un outil absent : il envoie reparer ce qui fonctionne.
#
# La seule methode exacte est de comparer l'EMPREINTE avant et apres --
# identique, le modele n'a pas bouge ; differente, il a ete mis a jour.
#
# SECOND DEFAUT, du meme jet. Le code faisait `time.sleep(1800)` ENTRE chaque
# tirage. Le nombre 1800 avait ete specifie comme un DELAI D'EXPIRATION par
# modele, pas comme une pause : le script dormait donc trente minutes apres
# chaque modele, et une execution en tache de fond n'a jamais rendu la main.
# Le delai est desormais passe a `subprocess.run(timeout=...)`, ou il a
# toujours eu sa place.
#
# Mesure apres correction : un modele a jour est classe en 0,7 seconde, un
# modele absent en 0,1 seconde.
# ---------------------------------------------------------------------------


def empreinte_modele(nom):
    # AVANT : le code comparait 'already up to date' dans la sortie
    # MAINTENANT : on lit directement l'empreinte depuis 'ollama list'
    # La sortie de 'ollama list' est : NAME ID SIZE MODIFIED
    try:
        result = subprocess.run(['ollama', 'list'], capture_output=True, text=True, encoding='utf-8', errors='replace')
        if result.returncode != 0:
            return None
        for ligne in result.stdout.splitlines():
            if not ligne.strip():
                continue
            parties = ligne.split(None, 3)  # Separe sur les espaces multiples
            if len(parties) < 4:
                continue
            nom_ligne = parties[0]
            id_ligne = parties[1]
            # Gestion du cas ou le nom n'a pas de tag (ex: 'nom' au lieu de 'nom:latest')
            if nom == nom_ligne or (':' not in nom and nom_ligne.startswith(nom + ':')):
                return id_ligne
        return None
    except Exception:
        return None

def rafraichir_modele(nom, delai_s):
    # AVANT : le code faisait time.sleep(1800) entre chaque modele
    # MAINTENANT : pas de pause, le delai est une expiration
    # AVANT : le code cherchait 'already up to date' ou 'done' dans la sortie
    # MAINTENANT : on ne se fie qu'a l'empreinte avant/apres pour savoir si le modele a change
    try:
        id_avant = empreinte_modele(nom)
        if id_avant is None:
            return 'echec'
        result = subprocess.run(
            ['ollama', 'pull', nom],
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            timeout=delai_s
        )
        if result.returncode != 0:
            return 'echec'
        id_apres = empreinte_modele(nom)
        if id_apres is None:
            return 'echec'
        if id_avant == id_apres:
            return 'a_jour'
        return 'mis_a_jour'
    except subprocess.TimeoutExpired:
        return 'echec'
    except Exception:
        return 'echec'



# ---------------------------------------------------------------------------
# UN MODELE MIS A JOUR INVALIDE SES PROPRES MESURES.
#
# .nexus/latences.json et .nexus/epreuves.json decrivent le comportement
# MESURE de chaque modele, et la configuration en DERIVE l'appartenance aux
# pools de routage (contrat 105.2). Quand `ollama pull` change reellement les
# poids, ces mesures decrivent les ANCIENS poids : le modele continuerait
# d'etre route sur une preuve perimee, sans que rien ne le dise.
#
# « Jamais mesure » vaut « jamais promu ». « Mesure sur d'autres poids » est
# PIRE, parce que cela se lit comme une mesure valide.
# ---------------------------------------------------------------------------

def invalider_mesures(noms_modeles, racine="."):
    """
    Supprime les mesures associees aux modeles mis a jour.
    Retourne un dict {"latences": [...], "epreuves": [...], "absents": [...]}
    """
    if not noms_modeles:
        # LA FORME NE VARIE PAS. Une cle presente seulement quand le cas
        # survient oblige chaque appelant a un .get() defensif, et le
        # premier qui l ecrit en acces direct leve KeyError le jour ou
        # tout va bien -- le pire moment pour tomber.
        return {"latences": [], "epreuves": [], "absents": [], "illisibles": []}

    # Normalisation du nom du modele : suppression du suffixe ":latest",
    # puis ne garder que les caracteres alphanumeriques en minuscule.
    def _norm_modele(nom):
        if nom.endswith(":latest"):
            nom = nom[:-7]
        return "".join(ch for ch in nom.lower() if ch.isalnum())

    # Normalisation de l'alias : suppression du suffixe "-local",
    # puis ne garder que les caracteres alphanumeriques en minuscule.
    def _norm_alias(alias):
        if alias.endswith("-local"):
            alias = alias[:-6]
        return "".join(ch for ch in alias.lower() if ch.isalnum())

    # Charge un fichier JSON en toute securite.
    def _load_json(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            return None          # fichier absent, pas d'erreur
        except Exception as e:
            sys.stderr.write(f"Erreur de lecture JSON {path}: {e}\n")
            return "ILLISIBLE"   # signaler que le fichier ne doit pas etre ecrit

    # Ecriture atomique du JSON uniquement si des modifications ont ete faites.
    def _write_json_atomique(data, path):
        dir_name = os.path.dirname(path)
        fd, tmp_path = tempfile.mkstemp(dir=dir_name, text=True)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as tmp_file:
                json.dump(data, tmp_file, ensure_ascii=False, indent=2)
                tmp_file.flush()
                os.fsync(tmp_file.fileno())
            os.replace(tmp_path, path)
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    # Recherche l'alias correspondant a un modele normalise dans le dictionnaire.
    def _trouver_alias(data, norm_modele):
        # data peut etre un dict d'alias direct ou {"modeles": {...}}
        if "modeles" in data and isinstance(data["modeles"], dict):
            candidates = data["modeles"]
        else:
            candidates = data
        for alias in list(candidates.keys()):
            if _norm_alias(alias) == norm_modele:
                return alias, candidates
        return None, None

    result = {"latences": [], "epreuves": [], "absents": [], "illisibles": []}
    fichiers = {
        "latences": os.path.join(racine, ".nexus", "latences.json"),
        "epreuves": os.path.join(racine, ".nexus", "epreuves.json")
    }

    # Preparer un mapping modele_norm -> alias trouve (ou None)
    mapping = {}
    for nom in noms_modeles:
        norm = _norm_modele(nom)
        mapping[nom] = {"norm": norm, "alias": None, "found": False, "vu": {}}

    for key, path in fichiers.items():
        data = _load_json(path)
        if data is None:
            # fichier absent : rien a faire
            continue
        if data == "ILLISIBLE":
            # NE PAS ECRIRE : ecraser un releve illisible detruirait des
            # mesures recuperables a la main, qui coutent des heures.
            # Mais le SIGNALER : traite comme un fichier absent, l'appelant
            # croirait l'invalidation faite alors que rien ne l'a ete.
            result["illisibles"].append(path)
            continue

        modified = False
        for nom, info in mapping.items():
            # LE DRAPEAU EST PAR FICHIER, ET NON PARTAGE.
            #
            # CE QUI ETAIT FAUX : un `found` unique faisait sauter, dans
            # epreuves.json, tout modele deja nettoye dans latences.json. Sa
            # preuve de CAPACITE aurait donc survecu au changement de poids,
            # alors que c'est precisement elle qui autorise une derogation au
            # seuil de latence (contrat 105.2). Une demi-invalidation est pire
            # qu'aucune : elle se lit comme faite.
            if info["vu"].get(key):
                continue
            alias, container = _trouver_alias(data, info["norm"])
            if alias:
                # suppression de l'entree
                del container[alias]
                info["alias"] = alias
                info["vu"][key] = True
                info["found"] = True
                result[key].append(alias)
                modified = True

        if modified:
            _write_json_atomique(data, path)

    # Les modeles dont aucun alias n'a ete trouve sont listes dans "absents"
    for nom, info in mapping.items():
        if not info["found"]:
            result["absents"].append(nom)

    return result


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Mise a jour des modeles Ollama deja installes.')
    parser.add_argument('--appliquer', action='store_true', help='Appliquer les mises a jour.')
    parser.add_argument('--limite', type=int, default=None, help='Nombre limite de modeles a traiter.')
    args = parser.parse_args()

    # Verifier si ollama est disponible
    stdout, stderr, code = execute_command('ollama --version')
    if code != 0:
        print("ERREUR : Ollama introuvable.")
        sys.exit(2)

    # Recuperer la liste des modeles
    stdout, stderr, code = execute_command('ollama list')
    if code != 0:
        print(f"ERREUR : Impossible de recuperer la liste des modeles. {stderr}")
        sys.exit(2)

    lines = stdout.strip().split('\n')
    if len(lines) < 2:
        print("AUCUN MODELE TROUVE.")
        sys.exit(2)

    # Ignorer l'en-tete
    model_lines = lines[1:]

    models_to_update = []
    total_size = 0.0

    for line in model_lines:
        parts = line.split()
        if len(parts) < 4:
            continue
        name = parts[0]
        # LA TAILLE TIENT EN DEUX CHAMPS, pas un. `ollama list` ecrit
        # « 6.7 GB » : decoupe sur les espaces, le nombre est en parts[2] et
        # l'unite en parts[3]. Ne prendre que parts[2] donnait « 6.7 » sans
        # unite, que parse_size rendait a ZERO -- d'ou un total de 0,00 Go
        # affiche pour cinquante modeles, et une garde disque qui comparait
        # ce zero a son seuil.
        size_str = parts[2] + ' ' + parts[3]
        # Ignorer les modeles marques comme ':cloud'
        if name.endswith(':cloud'):
            continue
        size_go = parse_size(size_str)
        total_size += size_go
        models_to_update.append((name, size_go))

    # LA LIMITE BORNE LA LISTE, ET NON LA SEULE BOUCLE D'APPLICATION.
    #
    # Elle n'etait appliquee qu'a la mise a jour : la simulation
    # affichait CINQUANTE modeles la ou l'application n'en aurait traite
    # que quatre. Une simulation qui ne montre pas ce qui sera fait ne
    # simule rien -- et c'est precisement le geste cense proteger de la
    # surprise.
    if args.limite:
        models_to_update = models_to_update[:args.limite]

    if not models_to_update:
        print("AUCUN MODELE A METTRE A JOUR.")
        sys.exit(2)

    # Afficher les modeles et le total
    print("Modeles a mettre a jour :")
    for name, size in models_to_update:
        print(f"  {name} ({size:.2f} Go)")
    # LE TOTAL PORTE SUR CE QUI EST LISTE, ET NON SUR TOUT LE PARC.
    # Il etait accumule avant l application de --limite : la simulation
    # annoncait 430 Go pour quatre modeles affiches. Une simulation dont le
    # chiffre ne correspond pas a sa liste ne simule rien.
    print(f"Taille totale : {sum(t for _n, t in models_to_update):.2f} Go")

    # Garde disque
    free_space = get_disk_space()
    if free_space is None or free_space < MARGE_DISQUE_GO:
        msg = f"ESPACE DISQUE INSUFFISANT : {free_space} Go (minimum requis : {MARGE_DISQUE_GO} Go)"
        if free_space is None:
            msg = "IMPOSSIBLE DE DETERMINER L'ESPACE LIBRE."
        print(msg)
        sys.exit(2)

    print(f"Espace libre : {free_space} Go")

    if not args.appliquer:
        print("SIMULATION SEULEMENT. AUCUNE MISE A JOUR EFFECTUEE.")
        sys.exit(0)

    # Mode application
    updated = 0
    up_to_date = 0
    failed = 0

    changes = []

    for name, _taille in models_to_update:

        print(f"Traitement de : {name}")
        etat = rafraichir_modele(name, DELAI_PULL_S)
        if etat == 'a_jour':
            up_to_date += 1
            print("  deja a jour")
        elif etat == 'mis_a_jour':
            updated += 1
            changes.append(name)
            print("  MIS A JOUR")
        else:
            failed += 1
            print("  ECHEC")

    # LES MESURES DES MODELES CHANGES SONT PERIMEES, ET DOIVENT PARTIR.
    #
    # Sans cet appel, la fonction ci-dessus existerait sans que rien ne
    # l'invoque -- un fichier, pas un mecanisme. Le parc serait rafraichi et
    # la configuration continuerait de router sur les mesures des anciens
    # poids.
    #
    # Seuls les modeles REELLEMENT changes sont touches : un `pull` sur un
    # modele deja a jour ne doit rien invalider, sans quoi une passe
    # quotidienne effacerait tout le releve chaque nuit et le banc
    # remesurerait 47 modeles pour rien.
    if changes:
        racine = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        bilan = invalider_mesures(changes, racine=racine)
        n = len(bilan.get('latences', [])) + len(bilan.get('epreuves', []))
        print(f"\nMesures invalidees : {n} entree(s) sur {len(changes)} modele(s) change(s)")
        for cle in ('latences', 'epreuves'):
            if bilan.get(cle):
                print(f"  {cle} : {', '.join(bilan[cle])}")
        if bilan.get('absents'):
            # Un modele sans alias n'est pas une anomalie -- tous les
            # installes ne sont pas exposes -- mais le taire empecherait de
            # voir un apparieur casse, qui rendrait TOUS les modeles absents.
            print(f"  sans alias : {', '.join(bilan['absents'])}")
        if bilan.get('illisibles'):
            print(f"  RELEVE ILLISIBLE, laisse intact : {', '.join(bilan['illisibles'])}")

    print("\nRapport final :")
    print(f"  Deja a jour : {up_to_date}")
    print(f"  Mises a jour : {updated}")
    print(f"  Echecs       : {failed}")

    if failed > 0:
        sys.exit(1)
    elif updated > 0 or up_to_date > 0:
        sys.exit(0)
    else:
        sys.exit(2)

if __name__ == '__main__':
    main()
