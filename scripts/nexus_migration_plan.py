# -*- coding: utf-8 -*-
"""
Plan de sortie des modèles hors de Docker.

Le problème posé
----------------
Le volume Docker contient plus de poids que le disque n'a de place libre :
on ne peut donc pas tout recopier d'un côté à l'autre, et une migration
« tout ou rien » échouerait à mi-parcours.

Ce script établit un plan qui tient réellement. Il ne se contente pas de
trier par taille : il couvre d'abord les rôles indispensables (relève,
codage, généraliste, vision, embeddings), écarte ce que la machine ne peut
de toute façon pas exécuter, dédoublonne les alias qui partagent le même
blob, et s'arrête quand le disque est atteint.

Il n'efface rien et ne télécharge rien. Il produit une liste et un
raisonnement, à exécuter ensuite en connaissance de cause.

Usage :
    python scripts/nexus_migration_plan.py
    python scripts/nexus_migration_plan.py --write model_list.host.txt
"""
from __future__ import annotations

import argparse
import io
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nexus_capability as capability  # noqa: E402

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

# Marge laissée au disque : un système qui frôle la saturation devient
# instable bien avant d'être plein.
DISK_RESERVE_GB = 25.0

# Rôles à couvrir, dans l'ordre où ils comptent. Le premier modèle
# disponible de chaque rôle est retenu avant tout élargissement : une
# plateforme qui sait tout coder mais ne sait pas lire une image n'est
# pas multimodale, quel que soit le nombre de modèles installés.
ROLES = [
    ("releve",     r"^glm-4\.7-flash|^qwen3-coder:30b",              "relève 64K / orchestrateur"),
    ("embedding",  r"^qwen3-embedding|^nomic-embed-text",            "embeddings / recherche"),
    ("code",       r"^qwen3-coder|^qwen2\.5-coder:(32|14)b|^codestral", "codage"),
    ("general",    r"^gemma4:(31|26|12)b|^qwen2\.5:32b|^qwen3\.6",   "généraliste / raisonnement"),
    ("vision",     r"^qwen3-vl:8b|^llava:(7|13)b|^llama3\.2-vision:11b", "multimodal"),
    ("rapide",     r"^llama3\.2:(1|3)b|^phi3:mini",                  "réponses courtes / latence"),
]


def docker_models() -> list[tuple[str, str, float]]:
    """(nom, identifiant de blob, taille) tel que vu dans le conteneur."""
    try:
        result = subprocess.run(
            ["docker", "exec", "ollama-server", "ollama", "list"],
            capture_output=True, text=True, timeout=60,
            encoding="utf-8", errors="replace",
        )
    except Exception:
        return []
    rows = []
    for line in result.stdout.splitlines()[1:]:
        parts = line.split()
        if len(parts) >= 4:
            rows.append((parts[0], parts[1],
                         capability.parse_size(parts[2] + parts[3])))
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", metavar="FICHIER",
                        help="écrit la liste retenue, prête pour ollama pull")
    args = parser.parse_args()

    profile = capability.build_profile()
    rows = docker_models()
    if not rows:
        print("Aucun modèle lisible dans le conteneur Ollama.")
        return 1

    # Un même blob peut porter deux noms (codestral:latest et codestral:22b
    # partagent le meme identifiant). Le compter deux fois surestimerait
    # gravement le volume a migrer.
    by_blob: dict[str, list[tuple[str, float]]] = {}
    for name, blob, size in rows:
        by_blob.setdefault(blob, []).append((name, size))
    unique = [(sorted(names)[0], names[0][1]) for blob, names in by_blob.items()
              for names in [sorted(names)]]
    unique = []
    for blob, names in by_blob.items():
        canonical = sorted(names, key=lambda n: (len(n[0]), n[0]))[0]
        unique.append((canonical[0], canonical[1], [n for n, _ in names]))

    total_raw = sum(size for _, _, size in rows)
    total_unique = sum(size for _, size, _ in unique)

    # Verdict matériel : inutile de migrer ce qui ne s'exécutera jamais.
    runnable, rejected = [], []
    for name, size, aliases in unique:
        state, reason = capability.verdict(size, profile)
        (rejected if state == capability.REJECT else runnable).append(
            (name, size, aliases, state, reason))

    budget = max(profile["free_disk_gb"] - DISK_RESERVE_GB, 0.0)

    # Couverture des rôles d'abord, élargissement ensuite.
    chosen: list[tuple[str, float, str]] = []
    used = 0.0
    taken: set[str] = set()

    for key, pattern, label in ROLES:
        candidates = [r for r in runnable
                      if re.match(pattern, r[0]) and r[0] not in taken]
        # À rôle couvert, le plus léger suffit : la place économisée
        # profite aux rôles suivants.
        candidates.sort(key=lambda r: r[1])
        for name, size, aliases, state, reason in candidates:
            if used + size > budget:
                continue
            chosen.append((name, size, label))
            taken.add(name)
            used += size
            break

    for name, size, aliases, state, reason in sorted(runnable, key=lambda r: r[1]):
        if name in taken or used + size > budget:
            continue
        chosen.append((name, size, "élargissement"))
        taken.add(name)
        used += size

    left = [(n, s) for n, s, a, st, r in runnable if n not in taken]

    print("=" * 72)
    print(" Plan de sortie des modèles hors de Docker")
    print("=" * 72)
    print("  Poids listés         : %.0f Go" % total_raw)
    print("  Poids réels (dédoublonnés) : %.0f Go" % total_unique)
    print("  Disque libre         : %.0f Go sur %s"
          % (profile["free_disk_gb"], profile["model_store"]))
    print("  Budget de migration  : %.0f Go (réserve de %.0f Go)"
          % (budget, DISK_RESERVE_GB))
    print("  Mémoire du moteur    : %.0f Go (%s)"
          % (profile["inference_memory_gb"], profile["ollama"]["mode"]))

    print("\n" + "-" * 72)
    print("\n  A MIGRER — %d modèles, %.0f Go" % (len(chosen), used))
    for name, size, label in chosen:
        print("    %-28s %6.1f Go   %s" % (name, size, label))

    if rejected:
        total_rejected = sum(size for _, size, _, _, _ in rejected)
        print("\n  A NE PAS MIGRER — inexécutables ici, %.0f Go recuperables"
              % total_rejected)
        for name, size, aliases, state, reason in sorted(rejected, key=lambda r: -r[1]):
            print("    %-28s %6.1f Go   %s" % (name, size, reason))

    if left:
        print("\n  REPORTES — faute de place, %.0f Go"
              % sum(size for _, size in left))
        for name, size in sorted(left, key=lambda r: -r[1])[:10]:
            print("    %-28s %6.1f Go" % (name, size))
        if len(left) > 10:
            print("    ... et %d autres" % (len(left) - 10))
        print("\n  Ils redeviendront téléchargeables une fois le volume Docker")
        print("  supprimé : c'est lui qui occupe la place aujourd'hui.")

    print("\n" + "-" * 72)
    print("""
  Ordre d'execution, et il compte :

    1. Telecharger la liste retenue sur l'hote      (rien n'est encore casse)
    2. Basculer le moteur                            nexus_switch_engine.py --to host
    3. Regenerer et verifier                         Update-NexusModels.ps1 -Restart
    4. Seulement alors, supprimer le service et le volume Docker
    5. Retelecharger les reportes avec la place liberee

  L'etape 4 vient apres la verification, jamais avant : tant qu'elle n'est
  pas franchie, le retour en arriere est immediat.
""")

    if args.write:
        target = args.write if os.path.isabs(args.write) else os.path.join(ROOT, args.write)
        lines = [
            "# Inventaire local a telecharger sur l'hote.",
            "# Genere par scripts/nexus_migration_plan.py — %d modeles, %.0f Go."
            % (len(chosen), used),
            "# Les modeles inexecutables sur cette machine en sont absents.",
            "",
        ] + [name for name, _, _ in chosen]
        with io.open(target, "w", encoding="utf-8", newline="\n") as fh:
            fh.write("\n".join(lines) + "\n")
        print("  Liste ecrite : %s" % target)
        print("  Telechargement : Get-Content %s | Where-Object { $_ -notmatch '^#|^$' } |"
              % os.path.basename(target))
        print("                   ForEach-Object { ollama pull $_ }")

    return 0


if __name__ == "__main__":
    sys.exit(main())
