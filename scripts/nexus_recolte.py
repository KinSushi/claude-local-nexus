import os
import sys
import json
import argparse
import subprocess
import contextlib
import glob


def charger_propositions(dossier):
    """Liste les *.json du dossier (sans sous-dossiers), charge chaque JSON.
    Rend une liste de tuples (chemin, dict) triee par timestamp. Ne leve jamais."""
    result = []
    try:
        fichiers = glob.glob(os.path.join(dossier, "*.json"))
    except Exception:
        fichiers = []
    for chemin in fichiers:
        try:
            with open(chemin, "r", encoding="utf-8") as f:
                data = json.load(f)
            result.append((chemin, data))
        except Exception:
            continue
    result.sort(key=lambda t: t[1].get("timestamp", 0))
    return result


def cible_de(prop):
    """Le premier fichier de la proposition, ou None."""
    fichiers = prop.get("fichiers")
    if isinstance(fichiers, list) and fichiers:
        return fichiers[0]
    return None


def vers_jsonl(prop):
    """Le dictionnaire {nom, texte} que nexus_appliquer lit dans son JSONL."""
    return {
        "nom": prop.get("nom", "proposition"),
        "texte": prop.get("patch", "")
    }


def appliquer(prop, racine, appliquer_fn=None):
    """Applique UNE proposition via nexus_appliquer (ou appliquer_fn injecte)."""
    cible = cible_de(prop)
    if cible is None:
        return (2, "pas de cible dans la proposition")
    nom = prop.get("nom", "proposition")
    jsonl_dir = os.path.join(racine, ".nexus")
    with contextlib.suppress(Exception):
        os.makedirs(jsonl_dir, exist_ok=True)
    jsonl_path = os.path.join(jsonl_dir, "recolte_%s.jsonl" % nom)
    try:
        with open(jsonl_path, "w", encoding="utf-8") as f:
            json.dump(vers_jsonl(prop), f, ensure_ascii=True)
            f.write("\n")
    except Exception as e:
        return (3, "echec ecriture jsonl: %s" % str(e))
    code = 1
    sortie = ""
    try:
        if appliquer_fn is not None:
            code, sortie = appliquer_fn(jsonl_path, nom, cible)
        else:
            cmd = [
                sys.executable,
                os.path.join(racine, "scripts", "nexus_appliquer.py"),
                jsonl_path,
                nom,
                cible
            ]
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=300
            )
            code = proc.returncode
            sortie = (proc.stdout or "") + (proc.stderr or "")
    except subprocess.TimeoutExpired as te:
        code = 4
        sortie = "timeout: %s" % str(te)
    except Exception as e:
        code = 5
        sortie = "exception lors de l'appel: %s" % str(e)
    finally:
        with contextlib.suppress(OSError):
            os.remove(jsonl_path)
    return (code, sortie)


def archiver(chemin_prop, dossier_archive):
    """Deplace la proposition vers le dossier d'archive. Ne leve jamais."""
    try:
        os.makedirs(dossier_archive, exist_ok=True)
        dest = os.path.join(dossier_archive, os.path.basename(chemin_prop))
        os.replace(chemin_prop, dest)
        return dest
    except Exception:
        return None


def _racine():
    """La racine du depot, derivee de __file__ (parent du repertoire scripts)."""
    return os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))


if __name__ == "__main__":
    racine = _racine()
    parser = argparse.ArgumentParser(description="Recolte et application, une a une, des propositions de la boucle locale")
    parser.add_argument(
        "--dossier",
        default=os.path.join(racine, ".nexus", "propositions"),
        help="Repertoire contenant les propositions JSON"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--lister",
        action="store_true",
        help="Lister les propositions en attente"
    )
    group.add_argument(
        "--appliquer",
        metavar="NOM",
        help="Appliquer la proposition portant ce nom (une seule, jamais en masse)"
    )
    args = parser.parse_args()

    dossier = args.dossier

    if args.lister:
        props = charger_propositions(dossier)
        if not props:
            sys.stdout.write("aucune proposition en attente\n")
        else:
            for _chemin, prop in props:
                nom = prop.get("nom", "-")
                verdict = prop.get("verdict", "-")
                cible = cible_de(prop) or "-"
                ts = prop.get("timestamp", 0)
                sys.stdout.write("%s\t%s\t%s\t%d\n" % (nom, verdict, cible, ts))
        sys.exit(0)

    if args.appliquer:
        nom_cible = args.appliquer
        props = charger_propositions(dossier)
        matches = [(c, p) for c, p in props if p.get("nom") == nom_cible]
        if not matches:
            sys.stderr.write("proposition nommee '%s' introuvable\n" % nom_cible)
            sys.exit(1)
        # la plus recente si plusieurs portent le meme nom
        chemin_prop, prop = max(matches, key=lambda t: t[1].get("timestamp", 0))
        code, sortie = appliquer(prop, racine)
        sys.stdout.write(sortie)
        if code == 0:
            archive_dir = os.path.join(dossier, "appliquees")
            nouveau = archiver(chemin_prop, archive_dir)
            if nouveau:
                sys.stdout.write("appliquee et archivee\n")
        sys.exit(code)