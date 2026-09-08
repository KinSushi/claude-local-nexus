#!/usr/bin/env python3

"""
outillage/nexus_plan.py

Outil « nexus_plan » – dérive mécaniquement le plan de production unifié à partir des
sujets ouverts du cockpit.

Fonctionnement :
  * Découpe le fichier markdown en sections (titres « # », « ## », …).
  * Conserve les sections dont le titre contient « ouvert » (insensible à la casse).
  * Dans chaque section, extrait les lignes de tableau (débutant par « | ») en
    ignorant les séparateurs et les en‑têtes.
  * Chaque ligne devient un *item* ouvert.  Si la ligne contient l’un des mots
    clés « FAIT », « DECIDE », « PRET » (en majuscules) l’item est classé « CLOS »
    et exclu du plan actif.
  * Classification mécanique (premier match) :
        CODE      → chemin *.py/*.ps1/*.js ou mots clés spécifiques
        MESURE    → mots liés à la mesure / benchmark
        DECISION  → mots liés à une décision d’opération
        RECHERCHE → mots liés à la recherche / méta‑heuristique
        AUTRE    → défaut
  * Génère un rapport lisible ou JSON, avec option de n’afficher que la catégorie
    CODE.
  * Option « --epreuve » : exécute un test autonome en répertoire temporaire.
"""

import argparse
import json
import re
import sys
import tempfile
from pathlib import Path

# --------------------------------------------------------------------------- #
#   Constantes de classification
# --------------------------------------------------------------------------- #

CODE_KEYWORDS = {
    "cabler", "cabl", "corriger", "corrig", "garde",
    "build", "batir", "indexer", "script", "patch",
    "generateur", "hook", "wire", "wrapper"
}
MESURE_KEYWORDS = {
    "mesurer", "mesure manquante", "debit", "jetons/s",
    "jetons par", "benchmark", "a mesurer", "chiffrer", "latence"
}
DECISION_KEYWORDS = {
    "decision", "operateur", "arbitrage", "a trancher",
    "environnement hote", "reglage d'environnement",
    "host", "keep_alive", "max_loaded"
}
RECHERCHE_KEYWORDS = {
    "metaheuristique", "bandit", "bayesien", "recherche",
    "piste", "litterature"
}
CLOSED_MARKERS = {"FAIT", "DECIDE", "PRET"}

# --------------------------------------------------------------------------- #
#   Structures de données
# --------------------------------------------------------------------------- #

class Item:
    """Représente un sujet extrait du checklist."""
    def __init__(self,
                 section_idx: int,
                 raw_line: str,
                 cells: list[str],
                 closed: bool = False):
        self.section_idx = section_idx          # numéro de section d’origine (1‑based)
        self.raw_line = raw_line                # ligne brute du tableau
        self.cells = cells                      # cellules du tableau (déjà strip)
        self.closed = closed                    # True si marqué FAIT/DECIDE/PRET
        self.category = self.classify()        # CODE, MESURE, … ou AUTRE

    def text(self) -> str:
        """Texte court utilisé dans les rapports (première cellule non vide)."""
        for cell in self.cells:
            if cell:
                return cell
        return ""

    # ------------------------------------------------------------------- #
    #   Classification
    # ------------------------------------------------------------------- #
    def classify(self) -> str:
        """Détermine la catégorie de l’item selon les règles décrites."""
        # Si déjà fermé, on ne le classe pas dans les catégories actives.
        if self.closed:
            return "CLOS"

        line = self.raw_line.lower()

        # 1️⃣ CODE – recherche d’un chemin ou d’un mot‑clé
        if re.search(r"\b[\w/\\]+\.(py|ps1|js)\b", line):
            return "CODE"
        if any(kw in line for kw in CODE_KEYWORDS):
            return "CODE"

        # 2️⃣ MESURE
        if any(kw in line for kw in MESURE_KEYWORDS):
            return "MESURE"

        # 3️⃣ DECISION
        if any(kw in line for kw in DECISION_KEYWORDS):
            return "DECISION"

        # 4️⃣ RECHERCHE
        if any(kw in line for kw in RECHERCHE_KEYWORDS):
            return "RECHERCHE"

        # 5️⃣ AUTRE
        return "AUTRE"


# --------------------------------------------------------------------------- #
#   Parsing du markdown
# --------------------------------------------------------------------------- #

def split_into_sections(lines: list[str]) -> list[tuple[str, list[str]]]:
    """
    Découpe le texte en sections.
    Retourne une liste de tuples (titre, corps) où le titre inclut le(s) '#'.
    """
    sections = []
    current_title = None
    current_body = []

    for line in lines:
        if re.match(r"^\s*#{1,6}\s+", line):
            # Nouvelle section
            if current_title is not None:
                sections.append((current_title, current_body))
            current_title = line.rstrip()
            current_body = []
        else:
            if current_title is not None:
                current_body.append(line.rstrip())
    # Dernière section
    if current_title is not None:
        sections.append((current_title, current_body))
    return sections


def extract_items_from_section(section_idx: int,
                              title: str,
                              body: list[str]) -> list[Item]:
    """
    Extrait les items d’une section dont le titre contient « ouvert ».
    """
    if "ouvert" not in title.lower():
        return []

    items = []
    for raw in body:
        stripped = raw.strip()
        if not stripped.startswith("|"):
            continue
        # Ignorer séparateurs de tableau
        if "---" in stripped:
            continue
        # Découper les cellules
        cells = [c.strip() for c in stripped.strip("|").split("|")]
        if not cells:
            continue
        # Ignorer les en‑têtes (première cellule = Sujet…)
        first = cells[0].lower()
        if first in {"sujet", "sujet ouvert", "item"}:
            continue

        # Détection d’un marqueur de clôture
        closed = any(marker in raw for marker in CLOSED_MARKERS)

        item = Item(section_idx=section_idx,
                    raw_line=raw,
                    cells=cells,
                    closed=closed)
        # On ne garde pas les items déjà fermés dans le plan actif
        if not closed:
            items.append(item)
    return items


def parse_checklist(path: Path) -> list[Item]:
    """
    Parse le fichier markdown et renvoie la liste de tous les items ouverts.
    """
    with path.open(encoding="utf-8") as f:
        lines = f.readlines()

    sections = split_into_sections(lines)
    all_items = []
    for idx, (title, body) in enumerate(sections, start=1):
        items = extract_items_from_section(idx, title, body)
        all_items.extend(items)
    return all_items


# --------------------------------------------------------------------------- #
#   Génération de rapports
# --------------------------------------------------------------------------- #

def group_by_category(items: list[Item]) -> dict[str, list[Item]]:
    """Regroupe les items par catégorie (exclut CLOS)."""
    groups: dict[str, list[Item]] = {}
    for it in items:
        if it.category == "CLOS":
            continue
        groups.setdefault(it.category, []).append(it)
    return groups


def report_text(groups: dict[str, list[Item]]) -> str:
    """Construit le rapport lisible."""
    order = ["CODE", "MESURE", "DECISION", "RECHERCHE", "AUTRE"]
    lines = []
    total = sum(len(v) for v in groups.values())
    lines.append("Plan de production unifié – résumé")
    lines.append("-" * 40)
    for cat in order:
        items = groups.get(cat, [])
        if not items:
            continue
        lines.append(f"{cat} ({len(items)}):")
        if cat == "CODE":
            for it in items:
                lines.append(f"  - §{it.section_idx}: {it.text()}")
        else:
            for it in items:
                lines.append(f"  - {it.text()}")
        lines.append("")
    lines.append(f"TOTAL : {total}")
    return "\n".join(lines)


def report_json(groups: dict[str, list[Item]]) -> str:
    """Construit le rapport JSON."""
    data = {
        "categories": {cat: [it.text() for it in items]
                       for cat, items in groups.items()},
        "comptes": {cat: len(items) for cat, items in groups.items()},
        "total": sum(len(v) for v in groups.values())
    }
    return json.dumps(data, ensure_ascii=False, indent=2)


def output_report(items: list[Item], args: argparse.Namespace) -> None:
    """Affiche le rapport selon les options."""
    groups = group_by_category(items)

    if args.json:
        print(report_json(groups))
        return

    # Option --seulement-code
    if args.seulement_code:
        code_items = groups.get("CODE", [])
        groups = {"CODE": code_items}

    print(report_text(groups))


# --------------------------------------------------------------------------- #
#   Fonction de test autonome (--epreuve)
# --------------------------------------------------------------------------- #

def _write_temp_checklist(root: Path) -> Path:
    """
    Crée un fichier CHECKLIST_COCKPIT.MD minimal dans le répertoire fourni.
    Retourne le chemin du fichier.
    """
    content = """# Sujets ouverts

## Sujets ouverts
| Sujet | Description |
|-------|-------------|
| script.py | Implémenter la fonction principale | 
| Mesure du débit | besoin de mesurer le débit sur le canal |
| Étude metaheuristique | recherche d’une metaheuristique adaptée |

## Fait
| Sujet | Description |
|-------|-------------|
| ancien.py | FAIT - déjà réalisé |
"""
    checklist_path = root / "CHECKLIST_COCKPIT.MD"
    checklist_path.write_text(content, encoding="utf-8")
    return checklist_path


def run_self_test() -> int:
    """
    Exécute le test décrit dans la spécification.
    Retourne 0 si tout passe, 1 sinon.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        checklist = _write_temp_checklist(tmp_path)

        # 1️⃣ Test « FORWARD » – on attend 3 items actifs, classés correctement
        items = parse_checklist(checklist)
        groups = group_by_category(items)

        expected = {
            "CODE": 1,
            "MESURE": 1,
            "RECHERCHE": 1,
        }

        for cat, cnt in expected.items():
            if len(groups.get(cat, [])) != cnt:
                return 1

        # Aucun item CLOS ne doit être présent
        if any(it.closed for it in items):
            return 1

        # 2️⃣ Test « REVERSE » – checklist sans section « ouvert »
        empty_content = """# Rien d'ouvert

## Autre section
| Sujet | Description |
|-------|-------------|
| foo | bar |
"""
        empty_path = tmp_path / "EMPTY.MD"
        empty_path.write_text(empty_content, encoding="utf-8")
        items2 = parse_checklist(empty_path)
        if items2:
            return 1

    return 0


# --------------------------------------------------------------------------- #
#   Entrée du script
# --------------------------------------------------------------------------- #

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Derive le plan de production unifié à partir du checklist cockpit."
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Produit la sortie au format JSON."
    )
    parser.add_argument(
        "--seulement-code",
        dest="seulement_code",
        action="store_true",
        help="N’affiche que la catégorie CODE."
    )
    parser.add_argument(
        "--epreuve",
        action="store_true",
        help="Exécute le test autonome et renvoie le code de sortie approprié."
    )
    args = parser.parse_args()

    if args.epreuve:
        sys.exit(run_self_test())

    # Chemin du checklist – racine dérivée de __file__
    script_dir = Path(__file__).resolve().parent
    checklist_path = script_dir / "rituels" / "CHECKLIST_COCKPIT.MD"

    if not checklist_path.is_file():
        sys.stderr.write(f"Erreur : fichier introuvable : {checklist_path}\n")
        sys.exit(2)

    items = parse_checklist(checklist_path)
    output_report(items, args)


if __name__ == "__main__":
    main()
