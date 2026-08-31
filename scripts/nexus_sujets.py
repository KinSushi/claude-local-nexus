#!/usr/bin/env python3
"""
nexus_sujets.py

Extraction des mentions de sujets non clos à partir de trois sources :
commits git, checklist « cockpit », et transcription JSONL.
Le script filtre le bruit, hiérarchise les sources, met en avant les
marques de haute valeur et déduplique les occurrences similaires.
"""

import argparse
import json
import os
import re
import subprocess
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Tuple

# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #

# Motifs de bruit (à ignorer)
# CE QUI ETAIT FAUX : la constante MARKERS avait été supprimée alors que trois fonctions l'utilisaient encore
MARKERS = [
    "reste ouvert",
    "restent ouverts",
    "ce qui reste ouvert",
    "non arbitre",
    "non arbitrees",
    "jamais arbitre",
    "reste a",
    "il reste",
    "a traiter",
    "n'est pas clos",
    "pas encore",
    "je ne tranche pas",
    "decision de l'operateur",
    "revient a l'operateur",
    "non mecanise",
    "pas mecanise",
    "hypothese",
    "non verifie",
    "non prouve",
    "reste inexplique",
]

MOTIFS_BRUIT: List[str] = [
    r"VERDICT\s*:",
    r"\[BLOQUE\]",
    r"\[MANQUE\]",
    r"\[OK\s*\]",
    r"\[IGNORE\]",
    r"\[RATE\]",
    r"\[PASS\]",
    r"manque\(s\)",
    r"epreuve tenue",
    r"Le tour n'est pas clos",
    r"cockpit frais",
    r"------+",                     # six tirets consécutifs ou plus
]

# Détection de fragments ressemblant à du code
CODE_PATTERNS: List[re.Pattern] = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"\bdef\s+",
        r"\bimport\s+",
        r"console\.log",
        r"\bprint\(",
        r"=>",
        r"\$\{",
        r'"""',
        r"[{}()\[\]]{3,}",  # au moins trois caractères parmi {}()[] 
    ]
]

# Marques de haute valeur (fortes)
MARQUES_FORTES: List[str] = [
    "ce qui reste ouvert",
    "reste ouvert",
    "ce qui n'est pas prouve",
    "n'est pas encore prouve",
    "non arbitre",
    "jamais arbitre",
    "je ne tranche pas",
    "revient a l'operateur",
    "decision de l'operateur",
    "non mecanise",
    "reste inexplique",
    "cause non etablie",
]

# Ordre de priorité des sources
SOURCE_ORDER = {"commit": 0, "cockpit": 1, "transcription": 2}

# --------------------------------------------------------------------------- #
# Utilitaires généraux
# --------------------------------------------------------------------------- #

def strip_accents(text: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn"
    )


def normalize_text(text: str) -> str:
    """Normalisation grossière pour le dédoublonnage."""
    text = text.lower()
    text = strip_accents(text)
    text = re.sub(r"[^\w\s]", " ", text)  # ponctuation → espace
    return re.sub(r"\s+", " ", text).strip()


def significant_words(text: str) -> List[str]:
    """Mots de longueur >= 4 après normalisation."""
    return [w for w in normalize_text(text).split() if len(w) >= 4]


def find_markers(text: str, markers: List[str]) -> List[Tuple[int, str]]:
    """Renvoie la liste des (position, marque) trouvées dans le texte."""
    lowered = strip_accents(text.lower())
    results = []
    for marker in markers:
        pattern = re.escape(marker.lower())
        for m in re.finditer(pattern, lowered):
            results.append((m.start(), marker))
    return results


def extract_context(text: str, pos: int, marker_len: int, width: int = 200) -> str:
    """Extrait un fragment centré sur la position donnée."""
    start = max(0, pos - width // 2)
    end = min(len(text), start + width)
    fragment = text[start:end]
    return fragment.replace("\n", " ").strip()


def is_noise(text: str) -> bool:
    """Détermine si le texte correspond à un motif de bruit ou ressemble à du code."""
    lowered = strip_accents(text.lower())
    for pat in MOTIFS_BRUIT:
        if re.search(pat, lowered, flags=re.IGNORECASE):
            return True
    return any(regex.search(text) for regex in CODE_PATTERNS)


def is_strong(text: str) -> bool:
    """Vrai si le texte contient une des marques fortes."""
    lowered = strip_accents(text.lower())
    for marque in MARQUES_FORTES:
        if re.search(re.escape(marque.lower()), lowered):
            return True
    return False


# --------------------------------------------------------------------------- #
# Lecture de la transcription (JSONL)
# --------------------------------------------------------------------------- #

def latest_jsonl_path(default_dir: Path) -> Path | None:
    """Retourne le fichier .jsonl le plus récent du répertoire donné."""
    if not default_dir.is_dir():
        return None
    jsonl_files = sorted(default_dir.glob("*.jsonl"),
                         key=lambda p: p.stat().st_mtime,
                         reverse=True)
    return jsonl_files[0] if jsonl_files else None


def recursive_collect_strings(obj: object) -> List[str]:
    """Parcourt récursivement un objet JSON et renvoie toutes les chaînes > 40 caractères."""
    strings = []
    if isinstance(obj, dict):
        for v in obj.values():
            strings.extend(recursive_collect_strings(v))
    elif isinstance(obj, list):
        for item in obj:
            strings.extend(recursive_collect_strings(item))
    elif isinstance(obj, str) and len(obj) > 40:
        strings.append(obj)
    return strings


def process_transcription(path: Path) -> List[Dict]:
    """Analyse le fichier JSONL ligne par ligne et renvoie les occurrences filtrées."""
    occurrences = []
    try:
        with path.open(encoding="utf-8", errors="replace") as f:
            for line_no, raw in enumerate(f, 1):
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    data = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                for txt in recursive_collect_strings(data):
                    for pos, marker in find_markers(txt, MARKERS):
                        ctx = extract_context(txt, pos, len(marker))
                        if is_noise(ctx):
                            continue
                        occurrences.append(
                            {
                                "source": "transcription",
                                "id": f"{path.name}:{line_no}",
                                "text": ctx,
                                "raw_pos": pos,
                                "line_no": line_no,
                                "timestamp": os.path.getmtime(path),
                                "strong": is_strong(ctx),
                            }
                        )
    except Exception as e:
        print(f"Erreur lors de la lecture de la transcription : {e}", file=sys.stderr)
    return occurrences


# --------------------------------------------------------------------------- #
# Lecture des commits git
# --------------------------------------------------------------------------- #

def git_log_commits() -> List[Dict]:
    """Récupère l’historique git complet et extrait les occurrences filtrées."""
    occurrences = []
    try:
        result = subprocess.run(
            ["git", "log", "--pretty=format:%H%n%B%n===END==="],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip())
        payload = result.stdout
        blocks = payload.split("===END===\n")
        for block in blocks:
            lines = block.strip("\n").splitlines()
            if not lines:
                continue
            commit_hash = lines[0].strip()
            message = "\n".join(lines[1:]).strip()
            for pos, marker in find_markers(message, MARKERS):
                ctx = extract_context(message, pos, len(marker))
                if is_noise(ctx):
                    continue
                occurrences.append(
                    {
                        "source": "commit",
                        "id": commit_hash,
                        "text": ctx,
                        "raw_pos": pos,
                        "timestamp": None,
                        "strong": is_strong(ctx),
                    }
                )
    except FileNotFoundError:
        print("git n’est pas disponible sur le système.", file=sys.stderr)
    except Exception as e:
        print(f"Erreur lors de la récupération des commits : {e}", file=sys.stderr)
    return occurrences


# --------------------------------------------------------------------------- #
# Lecture du cockpit (checklist)
# --------------------------------------------------------------------------- #

def process_cockpit(path: Path) -> List[Dict]:
    """Analyse le fichier cockpit s’il existe et renvoie les occurrences filtrées."""
    occurrences = []
    if not path.is_file():
        return occurrences
    try:
        with path.open(encoding="utf-8", errors="replace") as f:
            content = f.read()
        for pos, marker in find_markers(content, MARKERS):
            ctx = extract_context(content, pos, len(marker))
            if is_noise(ctx):
                continue
            occurrences.append(
                {
                    "source": "cockpit",
                    "id": f"{path.name}",
                    "text": ctx,
                    "raw_pos": pos,
                    "timestamp": os.path.getmtime(path),
                    "strong": is_strong(ctx),
                }
            )
    except Exception as e:
        print(f"Erreur lors de la lecture du cockpit : {e}", file=sys.stderr)
    return occurrences


# --------------------------------------------------------------------------- #
# Déduplication et hiérarchisation
# --------------------------------------------------------------------------- #

def deduplicate(occurrences: List[Dict]) -> List[Dict]:
    """Regroupe les occurrences similaires, conserve la plus récente,
    compte les répétitions et indique si le groupe est fort."""
    groups: Dict[str, List[Dict]] = defaultdict(list)

    for occ in occurrences:
        norm = normalize_text(occ["text"])
        groups[norm].append(occ)

    merged = []
    for norm, items in groups.items():
        # Détermination du groupe le plus récent
        def sort_key(o):
            # Priorité : timestamp > line_no > arbitraire
            if o.get("timestamp"):
                return o["timestamp"]
            if o.get("line_no"):
                return o["line_no"]
            return 0

        most_recent = max(items, key=sort_key)
        strong = any(item.get("strong") for item in items)
        sig_words = set(significant_words(norm))

        merged.append(
            {
                "count": len(items),
                "source": most_recent["source"],
                "id": most_recent["id"],
                "text": most_recent["text"],
                "sig_words": list(sig_words),
                "strong": strong,
            }
        )

    # Tri selon la hiérarchie demandée
    merged.sort(
        key=lambda d: (
            SOURCE_ORDER.get(d["source"], 99),
            0 if d["strong"] else 1,          # les forts d'abord
            -d["count"],                      # puis nombre décroissant
        )
    )
    return merged


# --------------------------------------------------------------------------- #
# Génération du rapport
# --------------------------------------------------------------------------- #

def print_human_report(groups: List[Dict], limit: int | None) -> None:
    out = sys.stderr
    displayed = groups[:limit] if limit is not None else groups
    for grp in displayed:
        prefix = "[F]" if grp.get("strong") else ""
        out.write(f"{prefix}[{grp['count']}] ({grp['source']}) {grp['id']}\n")
        out.write(f"    {grp['text']}\n\n")


def print_json_report(groups: List[Dict], limit: int | None) -> None:
    displayed = groups[:limit] if limit is not None else groups
    json.dump(displayed, sys.stdout, ensure_ascii=False, indent=2)


# --------------------------------------------------------------------------- #
# Point d’entrée principal
# --------------------------------------------------------------------------- #

def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Extraction des sujets non clos.")
    parser.add_argument(
        "--transcription",
        type=Path,
        help="Chemin vers le fichier JSONL de transcription (défaut : le plus récent).",
    )
    parser.add_argument(
        "--source",
        choices=["commit", "cockpit", "transcription"],
        help="Restreindre la sortie à une seule source.",
    )
    parser.add_argument("--json", action="store_true", help="Sortie au format JSON sur stdout.")
    parser.add_argument(
        "--limite",
        type=int,
        help="Nombre maximal de groupes à afficher.",
    )
    args = parser.parse_args(argv)

    sources_read = 0
    all_occurrences: List[Dict] = []

    # 1. Transcription
    transcription_path = args.transcription
    if not transcription_path:
        default_dir = Path.home() / ".claude" / "projects" / "C--local-llm-docker"
        transcription_path = latest_jsonl_path(default_dir)
    if transcription_path and transcription_path.is_file():
        occ = process_transcription(transcription_path)
        if occ:
            sources_read += 1
            all_occurrences.extend(occ)
    else:
        print("Aucun fichier de transcription trouvé.", file=sys.stderr)

    # 2. Commits git
    commit_occ = git_log_commits()
    if commit_occ:
        sources_read += 1
        all_occurrences.extend(commit_occ)

    # 3. Cockpit
    cockpit_path = Path("rituels") / "CHECKLIST_COCKPIT.MD"
    cockpit_occ = process_cockpit(cockpit_path)
    if cockpit_occ:
        sources_read += 1
        all_occurrences.extend(cockpit_occ)

    if not all_occurrences:
        return 2 if sources_read == 0 else 0

    # Filtrage éventuel par source demandée
    if args.source:
        all_occurrences = [o for o in all_occurrences if o["source"] == args.source]

    groups = deduplicate(all_occurrences)

    if args.json:
        print_json_report(groups, args.limite)
    else:
        print_human_report(groups, args.limite)

    return 0 if sources_read > 0 else 2


if __name__ == "__main__":
    sys.exit(main())
