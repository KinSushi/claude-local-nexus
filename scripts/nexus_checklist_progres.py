"""Module qui genere un rapport CHECKLIST_PROGRESS.md.
Chaque chiffre est mesure a la generation et un chiffre fige le lendemain.
"""

import subprocess
import sys
import re
import datetime
from pathlib import Path

def _run_git_cmd(args, cwd):
    try:
        result = subprocess.run(
            ["git"] + args,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except Exception:
        return None

def get_git_status(root):
    # commits non pushes
    commits = "inconnu"
    try:
        out = _run_git_cmd(["rev-list", "--count", "@{u}..HEAD"], cwd=root)
        if out is not None:
            commits = int(out)
    except Exception:
        pass

    # etat du working tree
    status = "inconnu"
    try:
        out = _run_git_cmd(["status", "--porcelain"], cwd=root)
        if out == "":
            status = "propre"
        else:
            status = "modifie"
    except Exception:
        pass

    # date du dernier commit
    last_date = "inconnu"
    try:
        out = _run_git_cmd(["log", "-1", "--format=%cd", "--date=iso"], cwd=root)
        if out:
            last_date = out
    except Exception:
        pass

    return {"commits_non_pousses": commits, "etat_arbre": status, "dernier_commit": last_date}

def run_ritual(script_path):
    regressions = "inconnu"
    try:
        result = subprocess.run(
            [sys.executable, str(script_path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=120,
        )
        # chercher un entier dans la sortie
        # check=True levait des qu un rituel rendait un code non nul,
        # or c est le cas NORMAL quand il detecte des regressions.
        m = re.search(r"(\d+)", result.stdout)
        if m:
            regressions = int(m.group(1))
    except Exception:
        pass
    return regressions

def count_nexus_scripts(scripts_dir):
    try:
        return len(list(scripts_dir.glob("nexus*.py")))
    except Exception:
        return "inconnu"

def count_mcp_tools(root):
    server_path = root / "tools" / "nexus-mcp" / "server.js"
    try:
        text = server_path.read_text(encoding="utf-8")
        # le fichier ecrit name, deux points, un ESPACE, puis le guillemet ;
        # sans les blancs le compte rendait ZERO, ce qui affirmait qu aucun outil
        # n est expose — un zero faux est pire qu une valeur inconnue.
        return len(re.findall(r'name:\s*"nexus_', text))
    except Exception:
        return "inconnu"

def checklist_vs_code(root):
    file_path = root / "rituels" / "CHECKLIST_LIVRE_VS_CODE.md"
    counts = {"vert": "inconnu", "jaune": "inconnu", "rouge": "inconnu"}
    if not file_path.is_file():
        return counts
    try:
        text = file_path.read_text(encoding="utf-8")
        counts["vert"] = text.count("🟢")
        counts["jaune"] = text.count("🟡")
        counts["rouge"] = text.count("🔴")
    except Exception:
        pass
    return counts

def count_backups(root):
    backup_dir = root / "cache" / ".nexus"
    try:
        files = list(backup_dir.glob("*.bundle"))
        nb = len(files)
        if nb == 0:
            recent = "inconnu"
        else:
            most_recent = max(files, key=lambda p: p.stat().st_mtime)
            dt = datetime.datetime.fromtimestamp(most_recent.stat().st_mtime)
            recent = dt.isoformat(sep=' ', timespec='seconds')
        return nb, recent
    except Exception:
        return "inconnu", "inconnu"

def count_corpus_lines(root):
    file_path = root / ".nexus" / "fragments_embeddings.jsonl"
    try:
        with file_path.open("r", encoding="utf-8") as f:
            return sum(1 for _ in f)
    except Exception:
        return "inconnu"

def generate_markdown(data, out_path):
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = []
    lines.append(f"# Checklist Progress")
    lines.append(f"Generated: {now}")
    lines.append("")
    # Section 1: Depot
    lines.append("## 1. Depot")
    lines.append("| Metric | Value |")
    lines.append("|---|---|")
    lines.append(f"| Commits non pushes | {data['git']['commits_non_pousses']} |")
    lines.append(f"| Etat de l'arbre | {data['git']['etat_arbre']} |")
    lines.append(f"| Date du dernier commit | {data['git']['dernier_commit']} |")
    lines.append("")
    # Section 2: Rituels
    lines.append("## 2. Rituels")
    lines.append("| Script | Regressions annoncees |")
    lines.append("|---|---|")
    lines.append(f"| nexus_cablage.py | {data['cablage']} |")
    lines.append(f"| nexus_outillage.py | {data['outillage']} |")
    lines.append("")
    # Section 3: Outils
    lines.append("## 3. Outils")
    lines.append("| Description | Value |")
    lines.append("|---|---|")
    lines.append(f"| Scripts nexus dans scripts/ | {data['nb_scripts']} |")
    lines.append(f"| Occurrences name:\"nexus_\" dans server.js | {data['mcp']} |")
    lines.append("")
    # Section 4: Checklist VS Code
    lines.append("## 4. Checklist VS Code")
    lines.append("| Couleur | Nombre |")
    lines.append("|---|---|")
    lines.append(f"| Vert | {data['checklist']['vert']} |")
    lines.append(f"| Jaune | {data['checklist']['jaune']} |")
    lines.append(f"| Rouge | {data['checklist']['rouge']} |")
    lines.append("")
    # Section 5: Sauvegardes
    lines.append("## 5. Sauvegardes")
    lines.append("| Metric | Value |")
    lines.append("|---|---|")
    lines.append(f"| Nombre de fichiers .bundle | {data['backups_nb']} |")
    lines.append(f"| Date du plus recent | {data['backups_recent']} |")
    lines.append("")
    # Section 6: Corpus
    lines.append("## 6. Corpus")
    lines.append("| Metric | Value |")
    lines.append("|---|---|")
    lines.append(f"| Lignes dans fragments_embeddings.jsonl | {data['corpus']} |")
    lines.append("")
    # Section ouvert
    lines.append("## CE QUI RESTE OUVERT")
    open_items = []
    if isinstance(data['cablage'], int) and data['cablage'] > 0:
        open_items.append(f"- Regressions de cablage : {data['cablage']}")
    if isinstance(data['outillage'], int) and data['outillage'] > 0:
        open_items.append(f"- Regressions d outillage : {data['outillage']}")
    rouge = data['checklist']['rouge']
    if isinstance(rouge, int) and rouge > 0:
        open_items.append(f"- Prescriptions rouges : {rouge}")
    commits = data['git']['commits_non_pousses']
    if isinstance(commits, int) and commits > 0:
        open_items.append(f"- Commits non pousses : {commits}")
    if open_items:
        lines.extend(open_items)
    else:
        lines.append("- Aucun element restant")
    content = "\n".join(lines) + "\n"
    try:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(content, encoding="utf-8")
        return True
    except Exception:
        return False

def main():
    root = Path(__file__).resolve().parent.parent
    data = {}
    data['git'] = get_git_status(root)

    scripts_dir = root / "scripts"
    data['cablage'] = run_ritual(root / "scripts" / "nexus_cablage.py")
    data['outillage'] = run_ritual(root / "scripts" / "nexus_outillage.py")
    data['nb_scripts'] = count_nexus_scripts(scripts_dir)
    data['mcp'] = count_mcp_tools(root)
    data['checklist'] = checklist_vs_code(root)
    data['backups_nb'], data['backups_recent'] = count_backups(root)
    data['corpus'] = count_corpus_lines(root)

    out_path = root / "rituels" / "CHECKLIST_PROGRESS.md"
    success = generate_markdown(data, out_path)
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()