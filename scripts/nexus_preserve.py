# -*- coding: utf-8 -*-
"""
Sépare ce qui se retélécharge de ce qui ne se retélécharge pas.

Le principe
-----------
Sauvegarder ce qui peut être reconstitué est du gaspillage ; ne pas
sauvegarder ce qui ne le peut pas est une perte. La question n'est donc
jamais « est-ce volumineux » mais « existe-t-il une source pour le
reconstruire ».

Appliqué à cette plateforme, le verdict est net : sur 541 Go occupés par
Docker, 541 Go se retéléchargent — les poids de modèles ont une source
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

# La sortie est souvent redirigee : journaux, STATE.md, sous-processus.
# Sans cette ligne, Python ecrit dans la page de codes locale de Windows
# et les accents se degradent des que la sortie est capturee -- le
# resultat finissait commite dans rituels/STATE.md, donc visible sur
# GitHub. PYTHONUTF8 est deja pose pour LiteLLM dans le compose ;
# il manquait ici.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKUP_DIR = os.path.join(ROOT, "backups")

RECONSTRUCTIBLE = "reconstructible"
IRREMPLACABLE = "irremplacable"


def run(args, timeout=120):
    try:
        result = subprocess.run(args, capture_output=True, text=True,
                                timeout=timeout, encoding="utf-8",
                                errors="replace")
        return result.stdout if result.returncode == 0 else ""
    except (subprocess.SubprocessError, OSError):
        # `OSError` est indispensable et non décoratif : `docker` ou
        # `ollama` absents du PATH lèvent `FileNotFoundError`, qui n'est
        # PAS un `SubprocessError`. L'omettre ferait mourir le script sur
        # la machine qu'il sert justement à décrire — un poste neuf, ou
        # celui d'où l'on vient de retirer Docker.
        return ""


def parse_size(text: str) -> float:
    match = re.match(r"([\d.,]+)\s*([kKmMgGtT]?[iI]?[bB])", text.strip())
    if not match:
        return 0.0
    value = float(match.group(1).replace(",", "."))
    unit = match.group(2).lower()
    scale = {"b": 1e-9, "kb": 1e-6, "mb": 1e-3, "gb": 1.0, "tb": 1e3,
             "kib": 1.05e-6, "mib": 1.049e-3, "gib": 1.074, "tib": 1100.0}
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
                items.append({
                    "artefact": name, "type": "volume", "taille": parse_size(size),
                    "verdict": RECONSTRUCTIBLE,
                    "source": "ollama pull, pilote par model_list.txt",
                })
            elif "redis" in name:
                items.append({
                    "artefact": name, "type": "volume", "taille": parse_size(size),
                    "verdict": RECONSTRUCTIBLE,
                    "source": "cache : se reconstitue a l'usage, par definition",
                })
            elif "pgdata" in name:
                items.append({
                    "artefact": name, "type": "volume", "taille": parse_size(size),
                    "verdict": IRREMPLACABLE,
                    "source": "aucune — historique de depense, sessions, cles",
                })
            else:
                items.append({
                    "artefact": name, "type": "volume", "taille": parse_size(size),
                    "verdict": IRREMPLACABLE, "source": "origine inconnue : prudence",
                })

    # --- Images --------------------------------------------------------
    for line in run(["docker", "images", "--format", "{{.Repository}}:{{.Tag}}\t{{.Size}}"]).splitlines():
        if "\t" not in line:
            continue
        name, size = line.split("\t", 1)
        items.append({
            "artefact": name, "type": "image", "taille": parse_size(size),
            "verdict": RECONSTRUCTIBLE,
            "source": "docker pull, declare dans docker-compose.yml",
        })

    # --- Fichiers du depot ---------------------------------------------
    tracked = run(["git", "-C", ROOT, "ls-files"]).splitlines()
    total = 0.0
    for relative in tracked:
        try:
            total += os.path.getsize(os.path.join(ROOT, relative)) / (1024 ** 3)
        except Exception:
            pass
    if tracked:
        items.append({
            "artefact": "%d fichiers suivis par git" % len(tracked),
            "type": "source", "taille": total, "verdict": RECONSTRUCTIBLE,
            "source": "git — l'historique EST la sauvegarde",
        })

    # --- Historique git ------------------------------------------------
    #
    # `.git` n'est reconstructible que jusqu'au dernier `push`. Au-dela, il
    # n'existe qu'ici : un `git clone` ne ramenerait pas ce que le distant
    # n'a jamais recu. Le verdict depend donc de l'etat de synchronisation,
    # pas de la simple presence d'un remote.
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
        amont = run(["git", "-C", ROOT, "rev-parse", "--abbrev-ref",
                     "--symbolic-full-name", "@{u}"]).strip()
        non_pousses = 0
        if remote:
            reference = amont or ("origin/%s" % branche)
            sortie = run(["git", "-C", ROOT, "log", "--oneline",
                          "%s..HEAD" % reference])
            non_pousses = len([l for l in sortie.splitlines() if l.strip()])

        modifies = [l for l in run(["git", "-C", ROOT, "status", "--porcelain"]).splitlines()
                    if l.strip()]

        if not remote:
            verdict, source = IRREMPLACABLE, "aucun depot distant : tout l'historique n'existe qu'ici"
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

        items.append({"artefact": ".git", "type": "historique",
                      "taille": taille, "verdict": verdict, "source": source})

    # --- Secrets -------------------------------------------------------
    env_file = os.path.join(ROOT, ".env")
    if os.path.exists(env_file):
        items.append({
            "artefact": ".env", "type": "secret",
            "taille": os.path.getsize(env_file) / (1024 ** 3),
            "verdict": IRREMPLACABLE,
            "source": "aucune — exclu de git a dessein, a sauvegarder hors depot",
        })

    # --- Index local ---------------------------------------------------
    index = os.path.join(ROOT, ".nexus", "index.json")
    if os.path.exists(index):
        items.append({
            "artefact": ".nexus/index.json", "type": "index",
            "taille": os.path.getsize(index) / (1024 ** 3),
            "verdict": RECONSTRUCTIBLE,
            "source": "nexus_index_build — lent, mais refaisable",
        })

    return items


def backup_irreplaceable() -> int:
    """Sauvegarde ce qui n'a aucune source de reconstruction."""
    os.makedirs(BACKUP_DIR, exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    fait = []

    # PostgreSQL : un dump SQL, pas une archive de volume. Le dump est
    # lisible, comparable d'une version a l'autre, et se restaure sur une
    # autre version de PostgreSQL — ce qu'un volume brut ne permet pas.
    target = os.path.join(BACKUP_DIR, "litellm-db-%s.sql" % stamp)
    dump = subprocess.run(
        ["docker", "exec", "litellm-db", "pg_dump", "-U", "litellm_user",
         "--clean", "--if-exists", "litellm"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=600)
    if dump.returncode == 0 and dump.stdout:
        with io.open(target, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(dump.stdout)
        taille = os.path.getsize(target) / (1024 ** 2)
        fait.append("base PostgreSQL : %s (%.1f Mo)" % (os.path.basename(target), taille))
    else:
        print("  [!] pg_dump a echoue : %s" % (dump.stderr or "")[:200])
        return 1

    # Historique git : un bundle contient TOUS les commits en un fichier,
    # et se clone directement. C'est la forme la plus compacte et la plus
    # fidele de sauvegarde d'un depot.
    bundle = os.path.join(BACKUP_DIR, "depot-%s.bundle" % stamp)
    result = subprocess.run(["git", "-C", ROOT, "bundle", "create", bundle, "--all"],
                            capture_output=True, text=True, timeout=600)
    if result.returncode == 0 and os.path.exists(bundle):
        fait.append("historique git : %s (%.1f Mo, %s)"
                    % (os.path.basename(bundle),
                       os.path.getsize(bundle) / (1024 ** 2),
                       "restaurable par git clone <bundle>"))

    # Un bundle ne contient que ce qui est COMMITE. Le travail en cours
    # n'y figure pas — or c'est souvent lui le plus recent, donc le plus
    # couteux a refaire. On l'archive separement.
    modifies = [l[3:].strip().strip('"')
                for l in subprocess.run(["git", "-C", ROOT, "status", "--porcelain"],
                                        capture_output=True, text=True,
                                        timeout=120).stdout.splitlines()
                if l.strip() and not l.startswith(" D") and not l.startswith("D ")]
    if modifies:
        import zipfile
        archive = os.path.join(BACKUP_DIR, "travail-en-cours-%s.zip" % stamp)
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zf:
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
        fait.append("travail non commite : %s (%d fichiers, %.1f Mo)"
                    % (os.path.basename(archive), ajoutes,
                       os.path.getsize(archive) / (1024 ** 2)))

    # .env n'est PAS copie dans backups/ : ce dossier vit a cote du depot,
    # sur le meme disque, et une copie de secret multiplie les endroits ou
    # il peut fuir. On rappelle seulement qu'il doit etre sauvegarde
    # ailleurs, deliberement.
    print("\n=== Sauvegarde de l'irremplacable ===")
    for ligne in fait:
        print("  %s" % ligne)
    print("\n  .env n'est volontairement pas copie ici : dupliquer un secret")
    print("  sur le meme disque multiplie les endroits ou il peut fuir.")
    print("  Le sauvegarder hors du depot, dans un gestionnaire de secrets.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--backup", action="store_true",
                        help="sauvegarde ce qui n'a aucune source de reconstruction")
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
    print(" Ce qui se retelecharge, et ce qui ne se retelecharge pas")
    print("=" * 76)

    print("\n  RECONSTRUCTIBLE — %.1f Go, aucune sauvegarde justifiee" % poids_r)
    for item in sorted(reconstructible, key=lambda i: -i["taille"]):
        print("    %-34s %9s   %s"
              % (item["artefact"][:34],
                 ("%.1f Go" % item["taille"]) if item["taille"] >= 0.1
                 else ("%.0f Mo" % (item["taille"] * 1024)),
                 item["source"]))

    print("\n  IRREMPLACABLE — %.0f Mo, a sauvegarder" % (poids_i * 1024))
    for item in sorted(irremplacable, key=lambda i: -i["taille"]):
        print("    %-34s %9s   %s"
              % (item["artefact"][:34],
                 ("%.1f Go" % item["taille"]) if item["taille"] >= 0.1
                 else ("%.1f Mo" % (item["taille"] * 1024)),
                 item["source"]))

    if total:
        part = poids_i / total * 100
        print("\n" + "-" * 76)
        print("  L'irremplacable represente %.3f %% du volume total." % part)
        print("  Autrement dit : %.0f Mo meritent une sauvegarde, %.0f Go n'en"
              % (poids_i * 1024, poids_r))
        print("  meritent aucune. Archiver les seconds couterait plus de disque")
        print("  qu'il n'en reste libre, pour reconstituer ce qu'une commande")
        print("  reconstitue seule.")

    print("""
  Consequence sur l'implantation :

    reste dans Docker    PostgreSQL   son volume est le seul irremplacable
                         Redis        cache, mais lie a LiteLLM et minuscule
                         LiteLLM      la passerelle, sa valeur est sa config

    sort de Docker       Ollama       et ses %0.0f Go de poids, tous
                                      retelechargeables depuis model_list.txt
""" % (next((i["taille"] for i in items if "ollama" in i["artefact"]), 0)))

    if args.backup:
        return backup_irreplaceable()

    print("  Sauvegarder l'irremplacable : python scripts/nexus_preserve.py --backup")
    return 0


if __name__ == "__main__":
    sys.exit(main())
