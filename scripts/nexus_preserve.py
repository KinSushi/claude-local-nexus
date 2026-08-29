# -*- coding: utf-8 -*-
"""
Sépare ce qui se retélécharge de ce qui ne se retélécharge pas.

Le principe
-----------
Sauvegarder ce qui peut être reconstitué est du gaspillage ; ne pas
sauvegarder ce qui ne le peut pas est une perte. La question n'est donc
jamais « est‑ce volumineux » mais « existe‑t‑il une source pour le
reconstruire ».

Appliqué à cette plateforme, le verdict est net : sur 541 Go occupés par
Docker, 541 Go se retéléchargent — les poids de modèles ont une source
publique et un manifeste local. Ce qui ne se retélécharge pas tient dans
quelques dizaines de mégaoctets : l'historique de dépense, les sessions de
routage, les clés virtuelles.

C'est cette poignée de mégaoctets qui doit rester dans Docker et être
sauvegardée. Le reste doit en sortir.

Usage :
    python scripts/nexus_preserve.py              # audit
    python scripts/nexus_preserve.py --backup     # sauvegarde l'irremplaçable
"""
from __future__ import annotations

import argparse
import datetime
import io
import os
import re
import subprocess
import sys
import tempfile
import zipfile

# La sortie est souvent redirigée : journaux, STATE.md, sous‑processus.
# Sans cette ligne, Python écrit dans la page de codes locale de Windows
# et les accents se dégradent dès que la sortie est capturée — le
# résultat finissait commité dans rituels/STATE.md, donc visible sur
# GitHub. PYTHONUTF8 est déjà posé pour LiteLLM dans le compose ;
# il manquait ici.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKUP_DIR = os.path.join(ROOT, "backups")

RECONSTRUCTIBLE = "reconstructible"
IRREMPLACABLE = "irremplacable"


def run(args, timeout=120):
    """
    Exécute une commande et renvoie la sortie standard si le retour est 0,
    sinon renvoie une chaîne vide.

    Cette fonction masque les erreurs liées à l'absence d'exécutable
    (FileNotFoundError) ou aux dépassements de délai, afin que le script
    continue son audit même si Docker ou Git ne sont pas installés.
    """
    try:
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace",
        )
        return result.stdout if result.returncode == 0 else ""
    except (subprocess.SubprocessError, OSError):
        # OSError couvre FileNotFoundError qui n’est pas un SubprocessError.
        return ""


def _exec_subprocess(args, timeout):
    """
    Exécute une commande et renvoie l'objet CompletedProcess.

    En cas d'erreur (exécutable introuvable, timeout, autre SubprocessError)
    un message explicite est affiché et ``None`` est retourné. Cette fonction
    permet de différencier les causes d'échec, contrairement à ``run`` qui
    masque tout.
    """
    try:
        return subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace",
        )
    except FileNotFoundError:
        print(f"  [!] executable introuvable : {' '.join(args)}")
    except subprocess.TimeoutExpired:
        print(f"  [!] timeout depasse : {' '.join(args)}")
    except subprocess.SubprocessError as exc:
        print(f"  [!] erreur de sous‑processus : {exc}")
    except OSError as exc:
        print(f"  [!] erreur OS : {exc}")
    return None


def parse_size(text: str) -> float:
    match = re.match(r"([\d.,]+)\s*([kKmMgGtT]?[iI]?[bB])", text.strip())
    if not match:
        return 0.0
    value = float(match.group(1).replace(",", "."))
    unit = match.group(2).lower()
    scale = {
        "b": 1e-9,
        "kb": 1e-6,
        "mb": 1e-3,
        "gb": 1.0,
        "tb": 1e3,
        "kib": 1.05e-6,
        "mib": 1.049e-3,
        "gib": 1.074,
        "tib": 1100.0,
    }
    return value * scale.get(unit, 0.0)


def inventory() -> list[dict]:
    """Chaque artefact, sa taille, et la source qui permet de le refaire."""
    items: list[dict] = []

    # --- Volumes -------------------------------------------------------
    output = run(["docker", "system", "df", "-v"])
    in_volumes = False
    for line in output.splitlines():
        if line.startswith("VOLUME NAME"):
            in_volumes = True
            continue
        if in_volumes:
            if not line.strip():
                break
            parts = line.split()
            if len(parts) < 3:
                continue
            name, size = parts[0], parts[-1]
            if "ollama" in name:
                items.append(
                    {
                        "artefact": name,
                        "type": "volume",
                        "taille": parse_size(size),
                        "verdict": RECONSTRUCTIBLE,
                        "source": "ollama pull, pilote par model_list.txt",
                    }
                )
            elif "redis" in name:
                items.append(
                    {
                        "artefact": name,
                        "type": "volume",
                        "taille": parse_size(size),
                        "verdict": RECONSTRUCTIBLE,
                        "source": "cache : se reconstitue a l'usage, par definition",
                    }
                )
            elif "pgdata" in name:
                items.append(
                    {
                        "artefact": name,
                        "type": "volume",
                        "taille": parse_size(size),
                        "verdict": IRREMPLACABLE,
                        "source": "aucune — historique de depense, sessions, cles",
                    }
                )
            else:
                items.append(
                    {
                        "artefact": name,
                        "type": "volume",
                        "taille": parse_size(size),
                        "verdict": IRREMPLACABLE,
                        "source": "origine inconnue : prudence",
                    }
                )

    # --- Images --------------------------------------------------------
    for line in run(
        ["docker", "images", "--format", "{{.Repository}}:{{.Tag}}\t{{.Size}}"]
    ).splitlines():
        if "\t" not in line:
            continue
        name, size = line.split("\t", 1)
        items.append(
            {
                "artefact": name,
                "type": "image",
                "taille": parse_size(size),
                "verdict": RECONSTRUCTIBLE,
                "source": "docker pull, declare dans docker-compose.yml",
            }
        )

    # --- Fichiers du depot ---------------------------------------------
    tracked = run(["git", "-C", ROOT, "ls-files"]).splitlines()
    total = 0.0
    for relative in tracked:
        try:
            total += os.path.getsize(os.path.join(ROOT, relative)) / (1024 ** 3)
        except Exception:
            pass
    if tracked:
        items.append(
            {
                "artefact": "%d fichiers suivis par git" % len(tracked),
                "type": "source",
                "taille": total,
                "verdict": RECONSTRUCTIBLE,
                "source": "git — l'historique EST la sauvegarde",
            }
        )

    # --- Historique git ------------------------------------------------
    git_dir = os.path.join(ROOT, ".git")
    if os.path.isdir(git_dir):
        taille = 0.0
        for base, _, files in os.walk(git_dir):
            for name in files:
                try:
                    taille += os.path.getsize(os.path.join(base, name))
                except Exception:
                    pass
        taille /= 1024 ** 3

        remote = run(["git", "-C", ROOT, "remote"]).strip()
        branche = run(["git", "-C", ROOT, "rev-parse", "--abbrev-ref", "HEAD"]).strip()
        amont = run(
            [
                "git",
                "-C",
                ROOT,
                "rev-parse",
                "--abbrev-ref",
                "--symbolic-full-name",
                "@{u}",
            ]
        ).strip()
        non_pousses = 0
        if remote:
            reference = amont or ("origin/%s" % branche)
            sortie = run(
                ["git", "-C", ROOT, "log", "--oneline", "%s..HEAD" % reference]
            )
            non_pousses = len([l for l in sortie.splitlines() if l.strip()])

        modifies = [
            l
            for l in run(["git", "-C", ROOT, "status", "--porcelain"]).splitlines()
            if l.strip()
        ]

        if not remote:
            verdict, source = (
                IRREMPLACABLE,
                "aucun depot distant : tout l'historique n'existe qu'ici",
            )
        elif non_pousses or modifies:
            details = []
            if non_pousses:
                details.append("%d commit(s) non pousse(s)" % non_pousses)
            if modifies:
                details.append("%d fichier(s) non commite(s)" % len(modifies))
            if not amont:
                details.append("aucun amont configure pour '%s'" % branche)
            verdict, source = IRREMPLACABLE, " ; ".join(details)
        else:
            verdict, source = RECONSTRUCTIBLE, "git clone %s" % remote

        items.append(
            {
                "artefact": ".git",
                "type": "historique",
                "taille": taille,
                "verdict": verdict,
                "source": source,
            }
        )

    # --- Secrets -------------------------------------------------------
    env_file = os.path.join(ROOT, ".env")
    if os.path.exists(env_file):
        items.append(
            {
                "artefact": ".env",
                "type": "secret",
                "taille": os.path.getsize(env_file) / (1024 ** 3),
                "verdict": IRREMPLACABLE,
                "source": "aucune — exclu de git a dessein, a sauvegarder hors depot",
            }
        )

    # --- Index local ---------------------------------------------------
    index = os.path.join(ROOT, ".nexus", "index.json")
    if os.path.exists(index):
        items.append(
            {
                "artefact": ".nexus/index.json",
                "type": "index",
                "taille": os.path.getsize(index) / (1024 ** 3),
                "verdict": RECONSTRUCTIBLE,
                "source": "nexus_index_build — lent, mais refaisable",
            }
        )

    return items


def _atomic_write(temp_path, final_path):
    """
    Déplace de façon atomique le fichier temporaire vers son nom définitif.
    Cette opération garantit qu'aucun fichier incomplet ne porte le nom d'une
    sauvegarde réussie.
    """
    os.replace(temp_path, final_path)


def backup_irreplaceable() -> int:
    """Sauvegarde ce qui n'a aucune source de reconstruction."""
    os.makedirs(BACKUP_DIR, exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    fait = []

    # ---------- PostgreSQL dump ----------
    target = os.path.join(BACKUP_DIR, f"litellm-db-{stamp}.sql")
    dump = _exec_subprocess(
        [
            "docker",
            "exec",
            "litellm-db",
            "pg_dump",
            "-U",
            "litellm_user",
            "--clean",
            "--if-exists",
            "litellm",
        ],
        timeout=600,
    )
    if dump is None or dump.returncode != 0 or not dump.stdout:
        print(f"  [!] pg_dump a echoue : {dump.stderr if dump else ''}")
        return 1

    # ecriture atomique
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", delete=False, dir=BACKUP_DIR, newline="\n"
    ) as tmp:
        tmp.write(dump.stdout)
        temp_name = tmp.name
    try:
        _atomic_write(temp_name, target)
    except OSError as exc:
        print(f"  [!] echec ecriture dump postgres : {exc}")
        return 1

    if not os.path.getsize(target):
        print("  [!] dump postgres vide, sauvegarde invalide")
        return 1

    taille = os.path.getsize(target) / (1024 ** 2)
    fait.append(f"base PostgreSQL : {os.path.basename(target)} ({taille:.1f} Mo)")

    # ---------- Git bundle ----------
    bundle_tmp = os.path.join(BACKUP_DIR, f"depot-{stamp}.bundle.tmp")
    bundle_final = os.path.join(BACKUP_DIR, f"depot-{stamp}.bundle")
    result = _exec_subprocess(
        ["git", "-C", ROOT, "bundle", "create", bundle_tmp, "--all"], timeout=600
    )
    if result is None or result.returncode != 0 or not os.path.exists(bundle_tmp):
        print(f"  [!] creation du bundle git a echoue : {result.stderr if result else ''}")
        return 1

    if os.path.getsize(bundle_tmp) == 0:
        print("  [!] bundle git vide, sauvegarde invalide")
        return 1

    try:
        _atomic_write(bundle_tmp, bundle_final)
    except OSError as exc:
        print(f"  [!] echec ecriture bundle git : {exc}")
        return 1

    fait.append(
        f"historique git : {os.path.basename(bundle_final)} ({os.path.getsize(bundle_final)/(1024**2):.1f} Mo, restaurable par git clone <bundle>)"
    )

    # ---------- Travail en cours (fichiers non commités) ----------
    status = _exec_subprocess(
        ["git", "-C", ROOT, "status", "--porcelain"], timeout=120
    )
    modifies = []
    if status and status.returncode == 0:
        modifies = [
            line[3:].strip().strip('"')
            for line in status.stdout.splitlines()
            if line.strip() and not line.startswith(" D") and not line.startswith("D ")
        ]

    if modifies:
        archive_tmp = os.path.join(BACKUP_DIR, f"travail-en-cours-{stamp}.zip.tmp")
        archive_final = os.path.join(BACKUP_DIR, f"travail-en-cours-{stamp}.zip")
        try:
            with zipfile.ZipFile(archive_tmp, "w", zipfile.ZIP_DEFLATED) as zf:
                ajoutes = 0
                for relative in modifies:
                    chemin = os.path.join(ROOT, relative)
                    if os.path.isfile(chemin):
                        zf.write(chemin, relative)
                        ajoutes += 1
                    elif os.path.isdir(chemin):
                        for base, _, files in os.walk(chemin):
                            for name in files:
                                complet = os.path.join(base, name)
                                zf.write(complet, os.path.relpath(complet, ROOT))
                                ajoutes += 1
        except Exception as exc:
            print(f"  [!] echec creation archive travail en cours : {exc}")
            return 1

        if not os.path.getsize(archive_tmp):
            print("  [!] archive travail en cours vide, sauvegarde invalide")
            return 1

        try:
            _atomic_write(archive_tmp, archive_final)
        except OSError as exc:
            print(f"  [!] echec ecriture archive travail en cours : {exc}")
            return 1

        fait.append(
            f"travail non commite : {os.path.basename(archive_final)} ({ajoutes} fichiers, {os.path.getsize(archive_final)/(1024**2):.1f} Mo)"
        )

    # ---------- Rapport ----------
    print("\n=== Sauvegarde de l'irremplacable ===")
    for ligne in fait:
        print(f"  {ligne}")
    print("\n  .env n'est volontairement pas copie ici : dupliquer un secret")
    print("  sur le meme disque multiplie les endroits ou il peut fuir.")
    print("  Le sauvegarder hors du depot, dans un gestionnaire de secrets.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--backup",
        action="store_true",
        help="sauvegarde ce qui n'a aucune source de reconstruction",
    )
    args = parser.parse_args()

    items = inventory()
    if not items:
        print("Rien a inventorier : Docker est-il demarre ?")
        return 1

    reconstructible = [i for i in items if i["verdict"] == RECONSTRUCTIBLE]
    irremplacable = [i for i in items if i["verdict"] == IRREMPLACABLE]
    poids_r = sum(i["taille"] for i in reconstructible)
    poids_i = sum(i["taille"] for i in irremplacable)
    total = poids_r + poids_i

    print("=" * 76)
    print(" Ce qui se retélécharge, et ce qui ne se retélécharge pas")
    print("=" * 76)

    print("\n  RECONSTRUCTIBLE — %.1f Go, aucune sauvegarde justifiee" % poids_r)
    for item in sorted(reconstructible, key=lambda i: -i["taille"]):
        print(
            "    %-34s %9s   %s"
            % (
                item["artefact"][:34],
                ("%.1f Go" % item["taille"])
                if item["taille"] >= 0.1
                else ("%.0f Mo" % (item["taille"] * 1024)),
                item["source"],
            )
        )

    print("\n  IRREMPLACABLE — %.0f Mo, a sauvegarder" % (poids_i * 1024))
    for item in sorted(irremplacable, key=lambda i: -i["taille"]):
        print(
            "    %-34s %9s   %s"
            % (
                item["artefact"][:34],
                ("%.1f Go" % item["taille"])
                if item["taille"] >= 0.1
                else ("%.1f Mo" % (item["taille"] * 1024)),
                item["source"],
            )
        )

    if total:
        part = poids_i / total * 100
        print("\n" + "-" * 76)
        print("  L'irremplacable represente %.3f %% du volume total." % part)
        print(
            "  Autrement dit : %.0f Mo meritent une sauvegarde, %.0f Go n'en"
            % (poids_i * 1024, poids_r)
        )
        print(
            "  meritent aucune. Archiver les seconds couterait plus de disque"
        )
        print(
            "  qu'il n'en reste libre, pour reconstituer ce qu'une commande"
        )
        print("  reconstitue seule.")

    print(
        """
  Consequence sur l'implantation :

    reste dans Docker    PostgreSQL   son volume est le seul irremplacable
                         Redis        cache, mais lie a LiteLLM et minuscule
                         LiteLLM      la passerelle, sa valeur est sa config

    sort de Docker       Ollama       et ses %0.0f Go de poids, tous
                                      retéléchargeables depuis model_list.txt
"""
        % (next((i["taille"] for i in items if "ollama" in i["artefact"]), 0))
    )

    if args.backup:
        return backup_irreplaceable()

    print("  Sauvegarder l'irremplacable : python scripts/nexus_preserve.py --backup")
    return 0


if __name__ == "__main__":
    sys.exit(main())
