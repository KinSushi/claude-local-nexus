# -*- coding: utf-8 -*-
"""
Génère la boussole : index navigable du dépôt, avec empreintes.

Objet
-----
Localiser un fichier et vérifier son intégrité sans commande jetable. Chaque
entrée porte son rôle en une ligne, sa taille, sa date et son empreinte
SHA‑256 tronquée — de quoi dire si le dépôt correspond encore à ce qu'on
croit, et où regarder.

Deux sorties, pour deux usages :
    rituels/BOUSSOLE.md   versionnée par git, lisible telle quelle
    rituels/BOUSSOLE.csv  ouvrable dans un tableur

Le fichier .xlsx d'origine n'est pas alimenté : il est exclu par .gitignore,
donc invisible de l'historique — ce qui contredit l'objet même d'un rituel
de traçabilité.

Usage :
    python scripts/nexus_boussole.py
"""
from __future__ import annotations

import csv
import datetime
import hashlib
import logging
import os
import sys
import tempfile

# La sortie est souvent redirigée : journaux, STATE.md, sous‑processus.
# Sans cette ligne, Python écrit dans la page de codes locale de Windows
# et les accents se dégradent dès que la sortie est capturée -- le
# résultat finissait commité dans rituels/STATE.md, donc visible sur
# GitHub. PYTHONUTF8 est déjà posé pour LiteLLM dans le compose ;
# il manquait ici.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Configuration du logger minimaliste.
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_MD = os.path.join(ROOT, "rituels", "BOUSSOLE.md")
OUT_CSV = os.path.join(ROOT, "rituels", "BOUSSOLE.csv")

SKIP_DIRS = {".git", "node_modules", "__pycache__", ".nexus", "backups",
             "logs", ".venv", "venv", "images"}
SKIP_EXT = {".pyc", ".log", ".bak", ".xlsx", ".tar", ".gz", ".png", ".jpg"}

# Rôle de chaque fichier, en une ligne. Un index sans intention n'est
# qu'une liste : ce qui fait gagner du temps, c'est de savoir à quoi sert
# le fichier avant de l'ouvrir.
ROLES = {
    "docker-compose.yml": ("Infrastructure", "Définition des services et volumes"),
    "litellm_config.yaml": ("Configuration", "Modèles, routeurs, fallbacks — mi-généré, mi-manuel"),
    "model_list.txt": ("Inventaire", "Modèles locaux à télécharger"),
    "cloud_models.txt": ("Inventaire", "Catalogue Ollama Cloud, généré, droits annotés"),
    ".env.example": ("Configuration", "Modèle de fichier d'environnement"),
    ".mcp.json": ("Pont", "Déclaration du serveur MCP pour Claude Code"),
    "Set-ClaudeModel.ps1": ("Pont", "Choix explicite du mode d'exécution de Claude Code"),
    "README.md": ("Documentation", "Vue d'ensemble et installation"),
    "AGENTS.md": ("Contrat", "Contrat d'agent universel"),
    "tools/nexus-mcp/server.js": ("Pont", "Serveur MCP : les modèles comme outils"),
    "scripts/nexus_generate.py": ("Génération", "Régénère les zones AUTOGEN"),
    "scripts/nexus_validate.py": ("Vérification", "Intégrité — bloque tout redémarrage douteux"),
    "scripts/nexus_capability.py": ("Vérification", "Profil matériel et verdict par modèle"),
    "scripts/nexus_test.py": ("Vérification", "Suite forward / reverse / policy / code"),
    "scripts/nexus_state.py": ("Rituel", "Régénère STATE.md par mesure"),
    "scripts/nexus_boussole.py": ("Rituel", "Régénère cette boussole"),
    "scripts/nexus_switch_engine.py": ("Migration", "Bascule le moteur Docker ↔ hôte"),
    "scripts/nexus_migration_plan.py": ("Migration", "Plan de sortie des modèles hors de Docker"),
    "scripts/nexus_mcp_probe.py": ("Vérification", "Sonde les outils du pont MCP"),
    "scripts/Update-NexusModels.ps1": ("Génération", "Orchestrateur de mise à jour"),
    "scripts/Test-NexusConfig.ps1": ("Vérification", "Enveloppe du validateur"),
    "scripts/Test-NexusSmoke.ps1": ("Vérification", "Smoke test runtime"),
    "scripts/Register-NexusAutoUpdate.ps1": ("Automatisation", "Tâche planifiée quotidienne"),
    "scripts/update_cloud_models.ps1": ("Obsolète", "Remplacé — neutralisé par garde-fou"),
    "scripts/update_local_models.ps1": ("Obsolète", "Remplacé — neutralisé par garde-fou"),
    "scripts/backup.ps1": ("Exploitation", "Sauvegarde configuration et volumes"),
    "scripts/restore.ps1": ("Exploitation", "Restauration"),
    "scripts/start.ps1": ("Exploitation", "Démarrage de la pile"),
    "scripts/stop.ps1": ("Exploitation", "Arrêt de la pile"),
    "docs/pont-local-abonnement.md": ("Documentation", "Associer modèles locaux et abonnement"),
    "rituels/STATE.md": ("Rituel", "État mesuré — généré, ne pas éditer"),
    "rituels/PROGRESS.md": ("Rituel", "Historique des décisions et des erreurs"),
    "rituels/CHECKLIST_COCKPIT.MD": ("Rituel", "Sujets ouverts"),
    "rituels/RESUME.ps1": ("Rituel", "Reprise de session"),
    "rituels/BOUSSOLE.md": ("Rituel", "Cet index"),
    ".claude/CLAUDE.md": ("Contrat", "Contrat d'exploitation de la plateforme"),
}

ORDER = ["Contrat", "Infrastructure", "Configuration", "Inventaire", "Pont",
         "Génération", "Vérification", "Migration", "Automatisation",
         "Exploitation", "Rituel", "Documentation", "Architecture", "Obsolète"]


def _escape_md(text: str) -> str:
    """
    Échappe les caractères spéciaux du Markdown dans les cellules de tableau.
    """
    return text.replace("|", r"\|").replace("`", r"\`")


def sha256(path: str) -> str:
    """
    Calcule le hachage SHA‑256 complet d'un fichier.

    Paramètres
    ----------
    path: str
        Chemin absolu du fichier à hacher.

    Retour
    ------
    str
        Hexadécimal du hachage complet (64 caractères) ou « N/A » si le
        fichier n'est pas lisible.
    """
    digest = hashlib.sha256()
    # Vérification préalable des droits de lecture.
    if not os.access(path, os.R_OK):
        logger.warning("Accès en lecture refusé pour %s", path)
        return "N/A"
    try:
        with open(path, "rb") as fh:
            for block in iter(lambda: fh.read(65536), b""):
                digest.update(block)
        return digest.hexdigest()
    except Exception as exc:
        logger.warning("Impossible de lire %s : %s", path, exc)
        return "N/A"


def walk() -> list[tuple[str, str, str, int, str, str]]:
    """
    Parcourt l'arborescence du dépôt et collecte les métadonnées utiles.

    Retour
    ------
    list[tuple[str, str, str, int, str, str]]
        Chaque tuple contient :
        (catégorie, chemin relatif, rôle, taille en octets,
         date de modification (YYYY‑MM‑DD), empreinte SHA‑256 tronquée à 16 caractères)
    """
    rows: list[tuple[str, str, str, int, str, str]] = []

    def _onerror(err):
        logger.warning("Erreur d'accès à %s : %s", err.filename, err.strerror)

    for base, dirs, files in os.walk(ROOT, onerror=_onerror):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for name in files:
            full = os.path.join(base, name)
            # Normalisation portable du chemin relatif.
            relative = os.path.relpath(full, ROOT)
            relative = os.path.normpath(relative).replace(os.sep, "/")
            if os.path.splitext(name)[1].lower() in SKIP_EXT:
                continue
            if relative == ".env":  # jamais indexé, jamais empreinté
                continue
            category, role = ROLES.get(relative, ("Architecture", ""))
            if not role and relative.endswith(".txt"):
                role = "Note d'architecture"
            try:
                stat = os.stat(full)
                rows.append((
                    category,
                    relative,
                    role,
                    stat.st_size,
                    datetime.datetime.fromtimestamp(stat.st_mtime)
                    .strftime("%Y-%m-%d"),
                    sha256(full)[:16],
                ))
            except Exception as exc:
                logger.warning("Erreur lors du traitement de %s : %s", full, exc)
                continue
    return rows


def _atomic_write(path: str, write_func) -> None:
    """
    Écriture atomique d'un fichier. Le répertoire parent est créé si nécessaire.
    En cas d'exception, le fichier temporaire est supprimé.
    """
    dir_name = os.path.dirname(path)
    os.makedirs(dir_name, exist_ok=True)

    tmp = tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", newline="\n", delete=False, dir=dir_name
    )
    # LA PROMESSE DU DOCSTRING, TENUE.
    #
    # Il annonce « en cas d'exception, le fichier temporaire est supprime ».
    # C'etait faux pour le cas le plus probable : si `write_func` levait, le
    # `finally` fermait le fichier, l'exception remontait, et le second
    # try/except -- seul a supprimer -- n'etait JAMAIS atteint. Le
    # temporaire restait sur disque a chaque echec d'ecriture.
    #
    # Une documentation qui affirme une garantie inexistante est pire qu'une
    # absence de garantie : on cesse de verifier ce qu'on croit acquis.
    try:
        try:
            write_func(tmp)
            tmp.flush()
            os.fsync(tmp.fileno())
        finally:
            tmp.close()
        os.replace(tmp.name, path)
    except Exception:
        # La suppression ne doit pas masquer l'erreur d'origine : si le
        # temporaire a deja disparu, on laisse remonter la vraie cause.
        try:
            os.remove(tmp.name)
        except OSError:
            pass
        raise


def main() -> int:
    rows = walk()
    rank = {name: i for i, name in enumerate(ORDER)}
    rows.sort(key=lambda r: (rank.get(r[0], 99), r[1]))

    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [
        "# Boussole",
        "",
        f"> Index du dépôt, généré par `python scripts/nexus_boussole.py` le {now}.",
        "> Localiser sans chercher, verifier sans commande jetable.",
        "> `.env` en est volontairement absent : ni indexé, ni empreinté.",
        "",
        "| Rôle | Fichier | Objet | Taille | Modifié | SHA-256 |",
        "|---|---|---|---|---|---|",
    ]
    for category, relative, role, size, modified, digest in rows:
        readable = ("%.0f Ko" % (size / 1024)) if size >= 1024 else ("%d o" % size)
        lines.append(
            "| %s | `%s` | %s | %s | %s | `%s` |"
            % (
                _escape_md(category),
                _escape_md(relative),
                _escape_md(role) or "—",
                readable,
                modified,
                digest,
            )
        )

    counts: dict[str, int] = {}
    for category, *_ in rows:
        counts[category] = counts.get(category, 0) + 1
    lines += [
        "",
        "## Répartition",
        "",
        "| Rôle | Fichiers |",
        "|---|---|",
    ]
    for name in ORDER:
        if counts.get(name):
            lines.append("| %s | %d |" % (name, counts[name]))
    lines += [
        "",
        "---",
        "",
        "État mesuré : [STATE.md](STATE.md) · "
        "Sujets ouverts : [CHECKLIST_COCKPIT.MD](CHECKLIST_COCKPIT.MD) · "
        "Historique : [PROGRESS.md](PROGRESS.md)",
    ]

    # Écriture atomique du fichier Markdown.
    _atomic_write(OUT_MD, lambda fh: fh.write("\n".join(lines) + "\n"))

    # Écriture atomique du fichier CSV.
    def _write_csv(fh):
        writer = csv.writer(fh, delimiter=";")
        writer.writerow(["Role", "Fichier", "Objet", "Taille (o)", "Modifie", "SHA-256 (16)"])
        for row in rows:
            writer.writerow([row[0], row[1], row[2], row[3], row[4], row[5]])

    _atomic_write(OUT_CSV, _write_csv)

    print("Boussole regeneree : %d fichiers indexes" % len(rows))
    print("  %s" % os.path.relpath(OUT_MD, ROOT))
    print("  %s" % os.path.relpath(OUT_CSV, ROOT))

    # Si aucun fichier indexe, l'index n'est pas fiable.
    if not rows:
        print("[!] AUCUN fichier n'a ete indexe ; l'index n'est donc pas fiable", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
