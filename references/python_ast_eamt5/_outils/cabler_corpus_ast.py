# Produit par gpt-oss-120b-cloud (Ollama Cloud -- les donnees sortent)
import argparse
import csv
import hashlib
import shutil
import sys
from datetime import date
from pathlib import Path
import importlib.util

def _trouver_racine(depart: Path):
    """Retourne le premier ancêtre contenant le marqueur CLAUDE.md."""
    marqueur = "CLAUDE.md"
    for candidat in [depart, *depart.parents]:
        if (candidat / marqueur).is_file():
            return candidat
    return None

def _charger_doc_lib():
    """Charge dynamiquement le module doc_lib.py situé sous workspace/tools."""
    script_dir = Path(__file__).resolve().parent
    racine = _trouver_racine(script_dir)
    if racine is None:
        raise RuntimeError("Marqueur CLAUDE.md introuvable.")
    doc_lib_path = racine / "workspace" / "tools" / "doc_lib.py"
    spec = importlib.util.spec_from_file_location("doc_lib", doc_lib_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Impossible de charger doc_lib.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore
    return module, racine

def _sha256_path(p: Path):
    h = hashlib.sha256()
    try:
        with p.open("rb") as f:
            for blk in iter(lambda: f.read(8192), b""):
                h.update(blk)
        return h.hexdigest()
    except OSError:
        return None

def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Câbler les fichiers AST vers la documentation indexée."
    )
    parser.add_argument(
        "--source",
        default="references/python_COUVERTURE_AST",
        help="Dossier contenant les fichiers *_api_ast.md (défaut %(default)s)",
    )
    parser.add_argument(
        "--destination",
        help="Dossier racine de la documentation (défaut = DOSSIER_DOC du doc_lib)",
    )
    parser.add_argument(
        "--rapport",
        required=True,
        help="Fichier CSV où écrire le rapport d'opérations",
    )
    parser.add_argument(
        "--verifier",
        metavar="SYMBOLE",
        help="Après copie, vérifie la présence du symbole dans l'index",
    )
    args = parser.parse_args(argv)

    # Charger doc_lib et récupérer DOSSIER_DOC
    doc_lib, racine = _charger_doc_lib()
    dossier_doc = doc_lib.DOSSIER_DOC  # Path relative to racine
    dest_root = Path(args.destination) if args.destination else racine / dossier_doc

    source_root = Path(args.source)
    if not source_root.is_dir():
        print(f"Erreur : le dossier source {source_root} n'existe pas.", file=sys.stderr)
        return 2

    rapport_path = Path(args.rapport)
    rapport_path.parent.mkdir(parents=True, exist_ok=True)

    champs = ["bibliotheque", "source", "destination", "taille", "sha256", "statut"]
    rows = []
    any_failure = False
    processed = 0

    for src_file in sorted(source_root.rglob("*_api_ast.md")):
        if not src_file.is_file():
            continue
        lib_name = src_file.stem.removesuffix("_api_ast")
        dest_dir = dest_root / lib_name
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_file = dest_dir / f"{lib_name}_api_ast.md"

        # Lecture du source
        src_hash = _sha256_path(src_file)
        if src_hash is None:
            statut = "ECHEC_LECTURE"
            any_failure = True
            rows.append([lib_name, str(src_file), str(dest_file), "", "", statut])
            continue

        src_size = src_file.stat().st_size
        if dest_file.is_file():
            dest_hash = _sha256_path(dest_file)
            if dest_hash is None:
                statut = "ECHEC_LECTURE"
                any_failure = True
                rows.append([lib_name, str(src_file), str(dest_file), src_size, src_hash, statut])
                continue
            if dest_hash == src_hash:
                statut = "DEJA_A_JOUR"
                rows.append([lib_name, str(src_file), str(dest_file), src_size, src_hash, statut])
                processed += 1
                continue
            # Différent → quarantaine puis copie
            today = date.today().isoformat()
            quarantine_name = f"{dest_file.stem}_QUARANTAINE_{today}.md"
            quarantine_path = dest_file.with_name(quarantine_name)
            try:
                shutil.move(str(dest_file), str(quarantine_path))
            except OSError:
                statut = "ECHEC_LECTURE"
                any_failure = True
                rows.append([lib_name, str(src_file), str(dest_file), src_size, src_hash, statut])
                continue
            try:
                shutil.copy2(str(src_file), str(dest_file))
            except OSError:
                statut = "ECHEC_LECTURE"
                any_failure = True
                rows.append([lib_name, str(src_file), str(dest_file), src_size, src_hash, statut])
                continue
            # Vérifier hash après copie
            post_hash = _sha256_path(dest_file)
            if post_hash != src_hash:
                statut = "ECHEC_HASH"
                any_failure = True
            else:
                statut = "QUARANTAINE_PUIS_COPIE"
            rows.append([lib_name, str(src_file), str(dest_file), src_size, src_hash, statut])
            processed += 1
        else:
            # Destination n'existe pas → copie simple
            try:
                shutil.copy2(str(src_file), str(dest_file))
            except OSError:
                statut = "ECHEC_LECTURE"
                any_failure = True
                rows.append([lib_name, str(src_file), str(dest_file), src_size, src_hash, statut])
                continue
            post_hash = _sha256_path(dest_file)
            if post_hash != src_hash:
                statut = "ECHEC_HASH"
                any_failure = True
            else:
                statut = "COPIE"
            rows.append([lib_name, str(src_file), str(dest_file), src_size, src_hash, statut])
            processed += 1

    # Écriture du CSV
    try:
        with rapport_path.open("w", encoding="utf-8", newline="") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(champs)
            writer.writerows(rows)
    except OSError as e:
        print(f"Erreur d'écriture du rapport CSV : {e}", file=sys.stderr)
        return 2

    # Aucun fichier traité = échec
    if processed == 0:
        any_failure = True

    # Affichage des messages de fin
    print("\n--- Rapport de câblage ---")
    print(f"Fichier CSV : {rapport_path}")
    print(f"Fichiers traités : {processed}")
    if any_failure:
        print("Statut : ECHEC (voir le CSV pour les détails)")
    else:
        print("Statut : SUCCESS")

    # Commande de reconstruction d'index
    index_cmd = f"python {doc_lib.__file__} --construire"
    print("\n⚠️  ATTENTION : les symboles ne seront pas trouvables tant que l'index n'est pas reconstruit.")
    print(f"Pour reconstruire l'index, exécutez : {index_cmd}")

    # Option --verifier
    if args.verifier:
        index = doc_lib.charger_index(racine)
        if not index:
            print("\nIndex absent – impossible de vérifier le symbole.")
        else:
            trouve = doc_lib.chercher(index, args.verifier)
            if trouve:
                print(f"\nVérification : le symbole « {args.verifier} » est présent dans l'index.")
            else:
                print(f"\nVérification : le symbole « {args.verifier} » n'est PAS présent dans l'index.")

    return 0 if not any_failure else 1

if __name__ == "__main__":
    sys.exit(main())

