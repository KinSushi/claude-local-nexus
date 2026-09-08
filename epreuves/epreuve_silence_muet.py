import os
import sys
import ast
from pathlib import Path

# Constantes
# ce chiffre est la mesure du jour faite par cette epreuve elle-meme
# il ne doit bouger qu a la BAISSE
# ruff en compte 56 seulement parce qu il ne detecte pas les memes formes
PLAFOND = 66

# Chemin racine du dépôt (deux niveaux au-dessus du fichier)
RACINE = Path(__file__).resolve().parent.parent

def _is_silent_except(node: ast.ExceptHandler) -> bool:
    """
    Retourne True si le handler ne contient qu'un seul statement Pass.
    """
    return (
        isinstance(node, ast.ExceptHandler) and
        len(node.body) == 1 and
        isinstance(node.body[0], ast.Pass)
    )

def _count_silent_excepts_in_file(filepath: Path) -> int:
    """
    Analyse un fichier Python et renvoie le nombre de ExceptHandler
    dont le corps ne contient qu'un Pass. En cas d'erreur de lecture
    ou de parsing, renvoie 0.
    """
    try:
        source = filepath.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return 0

    try:
        tree = ast.parse(source, filename=str(filepath))
    except SyntaxError:
        return 0

    return sum(1 for node in ast.walk(tree) if _is_silent_except(node))

def _gather_counts() -> dict[Path, int]:
    """
    Parcourt les répertoires 'outillage' et 'scripts' sous RACINE,
    compte les handlers muets par fichier et renvoie un dictionnaire
    {Path: count}.
    """
    counts = {}
    for subdir in ("outillage", "scripts"):
        base = RACINE / subdir
        if not base.is_dir():
            continue
        for root, _, files in os.walk(base):
            for name in files:
                if name.endswith(".py"):
                    file_path = Path(root) / name
                    cnt = _count_silent_excepts_in_file(file_path)
                    if cnt:
                        counts[file_path] = cnt
    return counts

def _format_offenders(counts: dict[Path, int]) -> str:
    """
    Retourne une chaîne listant les cinq premiers fichiers fautifs
    avec leur nombre de handlers muets, séparés par des virgules.
    """
    sorted_items = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)
    parts = [f"{p.relative_to(RACINE)}:{c}" for p, c in sorted_items[:5]]
    return ", ".join(parts)

def main() -> int:
    counts = _gather_counts()
    total = sum(counts.values())

    # Cas 1 : plafond
    if total <= PLAFOND:
        print(f"[OK  ] plafond : total={total} (<= {PLAFOND})")
        case1_ok = True
    else:
        offenders = _format_offenders(counts)
        print(f"[RATE] plafond : total={total} (> {PLAFOND}) – fichiers fautifs : {offenders}")
        case1_ok = False

    # Cas 2 : plafond honnete
    if total > 0:
        print(f"[OK  ] plafond honnete : total={total} (>0)")
        case2_ok = True
    else:
        print("[RATE] plafond honnete : aucun handler muet trouvé – baissez le plafond")
        case2_ok = False

    return 0 if (case1_ok and case2_ok) else 1

if __name__ == "__main__":
    sys.exit(main())