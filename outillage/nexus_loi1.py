"""nexus_loi1.py

Ce script mecanise la LOI 1 du depot : le producteur ne doit jamais auditor son propre travail.
Il mesure la part de code ecrit a la main entre un commit de base et HEAD, en excluant les lignes
qui sont deja presentes dans les traces du banc de modeles gratuits. La regle a ete gravee le 2026-09-01
par l'operateur, elle a ete violee par son auteur dans l'heure, et le contrat du depot declarait lui-meme
au paragraphe 0.1.5 qu'aucun controle ne la gardait.
"""

import argparse
import json
import sys
import subprocess
from pathlib import Path
from datetime import datetime, timedelta

def _load_traces(base=None, plancher=400):
    """Charge les textes des traces les plus recentes (plancher) entre base et 24h avant."""
    script_dir = Path(__file__).resolve().parent
    sys.path.insert(0, str(script_dir))
    try:
        from nexus_verbatim import charger_index, lire
    except Exception as e:
        raise RuntimeError(f"Impossible d'importer nexus_verbatim: {e}") from e

    entries, _ = charger_index()
    # Determine threshold based on base commit
    seuil = None
    if base is not None:
        try:
            # Obtain commit date string in local format YYYYMMDD-HHMMSS
            result = subprocess.run(
                ["git", "log", "-1", "--format=%cd", "--date=format-local:%Y%m%d-%H%M%S", base],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            if result.returncode == 0:
                commit_dt_str = result.stdout.strip()
                commit_dt = datetime.strptime(commit_dt_str, "%Y%m%d-%H%M%S")
                seuil_dt = commit_dt - timedelta(hours=24)
                seuil = seuil_dt.strftime("%Y%m%d-%H%M%S")
        except Exception as exc:
            print("nexus_loi1.py : subprocess.run impossible : %s" % exc, file=sys.stderr)
            seuil = None

    if seuil is not None:
        # Keep entries whose id timestamp >= seuil
        selected = [e for e in entries if e.get("id", "")[:15] >= seuil]
        # If fewer than plancher, fall back to last plancher entries
        if len(selected) < plancher:
            selected = entries[-plancher:] if plancher else []
    else:
        # Fallback to current behaviour
        selected = entries[-plancher:] if plancher else []

    texts = []
    for e in selected:
        ident = e.get("id")
        if ident:
            txt = lire(ident)
            if txt is not None:
                texts.append(_normaliser_espaces(txt))
    return texts, len(selected)

def _git_diff_name_only(base):
    """Retourne la liste des fichiers modifies entre base et HEAD."""
    result = subprocess.run(
        ["git", "diff", "--name-only", base, "HEAD"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        raise RuntimeError("git diff --name-only a echoue")
    files = result.stdout.splitlines()
    return [
        f for f in files
        if (f.endswith(".py") or f.endswith(".js"))
        and ("epreuve" not in f) and ("test" not in f)
    ]

def _git_added_lines(base, path):
    """Retourne les lignes ajoutees (>=24 caracteres) du fichier path."""
    result = subprocess.run(
        ["git", "diff", "-U0", base, "HEAD", "--", path],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        raise RuntimeError(f"git diff -U0 a echoue pour {path}")
    added = []
    for line in result.stdout.splitlines():
        if line.startswith("+") and not line.startswith("+++"):
            content = line[1:].strip()
            if len(content) >= 24:
                added.append(content)
    return added

def _normaliser_espaces(s):
    """Replace non‑breaking and narrow spaces with ordinary space."""
    return s.replace("\u00A0", " ").replace("\u202F", " ").replace("\u2009", " ")

def _is_delegated(line, traces):
    """Determine si la ligne apparait dans au moins une trace."""
    norm_line = _normaliser_espaces(line)
    return any(norm_line in txt for txt in traces)

def _print_table(stats):
    """Affiche un tableau simple des resultats."""
    header = f"{'Fichier':30} {'Retenues':8} {'Deleguees':9} {'Manuel':6}"
    print(header)
    print("-" * len(header))
    for file, data in stats.items():
        print(f"{file:30} {data['retained']:8} {data['delegated']:9} {data['manual']:6}")
    print()

def _print_files_exceeding(stats):
    """Liste les fichiers dont la part a la main depasse la moitie."""
    exceed = [f for f, d in stats.items() if d['retained'] > 0 and d['manual'] > d['retained'] / 2]
    if exceed:
        print("Fichiers avec plus de 50% de code a la main :")
        for f in exceed:
            print(f"  {f}")
        print()

def main():
    parser = argparse.ArgumentParser(description="Mesure du respect de la LOI 1")
    parser.add_argument("--base", default="HEAD~1", help="Commit de base")
    parser.add_argument("--json", action="store_true", help="Sortie au format JSON")
    parser.add_argument("--reference", action="store_true", help="Reecrire la reference")
    args = parser.parse_args()

    try:
        # Etape 2 : liste des fichiers modifies
        files = _git_diff_name_only(args.base)

        # Etape 5 : charger les traces du banc
        traces, loaded_count = _load_traces(args.base)
        print(f"Traces chargees : {loaded_count} (fenetre : depuis 24 h avant {args.base})")

        # Collecte des stats
        stats = {}
        total_manual = 0
        total_retained = 0
        total_delegated = 0

        for f in files:
            added = _git_added_lines(args.base, f)
            retained = len(added)
            delegated = sum(1 for line in added if _is_delegated(line, traces))
            manual = retained - delegated
            stats[f] = {
                "retained": retained,
                "delegated": delegated,
                "manual": manual,
            }
            total_retained += retained
            total_delegated += delegated
            total_manual += manual

        # Affichage
        if args.json:
            output = {
                "files": stats,
                "total_retained": total_retained,
                "total_delegated": total_delegated,
                "total_manual": total_manual,
            }
            print(json.dumps(output, ensure_ascii=False, indent=2))
        else:
            _print_table(stats)
            _print_files_exceeding(stats)

        # Gestion du cliquet
        repo_root = Path.cwd()
        ref_path = repo_root / ".nexus" / "loi1.json"
        ref_path.parent.mkdir(parents=True, exist_ok=True)

        if args.reference:
            # Reecriture forcée de la reference
            ref_path.write_text(json.dumps({"reference": total_manual}, ensure_ascii=False))
            print(f"Reference mise a jour (force) : {total_manual}")
            sys.exit(0)

        if not ref_path.is_file():
            # Creation du fichier de reference
            ref_path.write_text(json.dumps({"reference": total_manual}, ensure_ascii=False))
            print("Reference creee, aucune preuve encore.")
            sys.exit(0)

        # Lecture de la reference existante
        try:
            ref_data = json.loads(ref_path.read_text(encoding="utf-8"))
            reference = ref_data.get("reference", 0)
        except Exception as e:
            raise RuntimeError("Impossible de lire la reference existante") from e

        if total_manual > reference:
            diff = total_manual - reference
            print(f"Violation : {diff} lignes a la main en plus que la reference ({reference}).")
            sys.exit(1)
        elif total_manual < reference:
            # Mise a jour vers une valeur inferieure (le cliquet ne se desserre jamais)
            ref_path.write_text(json.dumps({"reference": total_manual}, ensure_ascii=False))
            print(f"Reference mise a jour vers valeur inferieure : {total_manual}")
            sys.exit(0)
        else:
            # Egalite
            print("Conformite avec la reference.")
            sys.exit(0)

    except Exception as e:
        # Gestion des pannes internes
        msg = str(e)
        if "git" in msg.lower():
            print("Erreur interne : git absent ou commande echouee.", file=sys.stderr)
        else:
            print("Erreur interne : mesure impossible.", file=sys.stderr)
        # Distinction entre rien a la main et echec de mesure
        if total_manual == 0:
            print("Rien a la main.", file=sys.stderr)
        else:
            print("Mesure non disponible.", file=sys.stderr)
        sys.exit(2)

if __name__ == "__main__":
    main()
