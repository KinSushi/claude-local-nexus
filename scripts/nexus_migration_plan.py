# -*- coding: utf-8 -*-
"""
Plan de sortie des modeles hors de Docker.

Le probleme pose
----------------
Le volume Docker contient plus de poids que le disque n'a de place libre :
on ne peut donc pas tout recopier d'un cote a l'autre, et une migration
"tout ou rien" echouerait a mi-parcours.

Ce script etablit un plan qui tient réellement. Il ne se contente pas de
trier par taille : il couvre d'abord les roles indispensables (relève,
codage, generaliste, vision, embeddings), ecarte ce que la machine ne peut
de toute facon pas executer, dedoublonne les alias qui partagent le meme
blob, et s'arrete quand le disque est atteint.

Il n'efface rien et ne telecharge rien. Il produit une liste et un
raisonnement, a executer ensuite en connaissance de cause.

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

# ---------------------------------------------------------------------------
# Verification de la version Python minimale (3.7) requise pour
# sys.stdout.reconfigure et la syntaxe de type liste[...].
# ---------------------------------------------------------------------------
if sys.version_info < (3, 7):
    print("Erreur : Python 3.7 ou superieur est requis.", file=sys.stderr)
    sys.exit(2)

# ---------------------------------------------------------------------------
# Gestion de la dependance externe ``nexus_capability``.
# Si le module est absent, on indique clairement le probleme et on quitte
# avec un code d'erreur explicite.  Cela evite une trace de type
# ``ModuleNotFoundError`` qui ne serait pas compréhensible pour l'utilisateur.
# ---------------------------------------------------------------------------
try:
    import nexus_capability as capability  # noqa: E402
except ImportError as exc:  # pragma: no cover
    # LA CAUSE EST DITE, pas seulement le symptome.
    #
    # `exc` etait capture puis jete : l'operateur lisait « module
    # introuvable » sans jamais savoir POURQUOI -- chemin absent, dependance
    # manquante du module lui-meme, erreur de syntaxe a l'import. Trois
    # pannes differentes derriere un seul message.
    print("Erreur : le module requis 'nexus_capability' est introuvable — %s"
          % exc, file=sys.stderr)
    sys.exit(2)

# ---------------------------------------------------------------------------
# Configuration flexible du nom du conteneur Docker contenant Ollama.
# Le nom etait code en dur ("ollama-server").  En le rendant paramettrable
# via une variable d'environnement, on evite l'echec du script lorsqu'un
# utilisateur a choisi un autre nom dans son ``docker-compose.yml``.
# ---------------------------------------------------------------------------
OLLAMA_CONTAINER = os.getenv("OLLAMA_CONTAINER", "ollama-server")

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

# Marge laissee au disque : un systeme qui frôle la saturation devient
# instable bien avant d'etre plein.
DISK_RESERVE_GB = 25.0

# Roles a couvrir, dans l'ordre où ils comptent. Le premier modele
# disponible de chaque role est retenu avant tout elargissement : une
# plateforme qui sait tout coder mais ne sait pas lire une image n'est
# pas multimodale, quel que soit le nombre de modeles installes.
ROLES = [
    ("releve",     r"^(glm-4\.7-flash|qwen3-coder:30b)$",              "relève 64K / orchestrateur"),
    ("embedding",  r"^(qwen3-embedding|nomic-embed-text)$",            "embeddings / recherche"),
    ("code",       r"^(qwen3-coder|qwen2\.5-coder:(32|14)b|codestral)$", "codage"),
    ("general",    r"^(gemma4:(31|26|12)b|qwen2\.5:32b|qwen3\.6)$",   "generaliste / raisonnement"),
    ("vision",     r"^(qwen3-vl:8b|llava:(7|13)b|llama3\.2-vision:11b)$", "multimodal"),
    ("rapide",     r"^(llama3\.2:(1|3)b|phi3:mini)$",                  "reponses courtes / latence"),
]


def _extract_size(text: str) -> str | None:
    """
    Extrait la chaine representant la taille d'un modele dans la sortie
    de ``ollama list``.  Le format peut etre "4.7 GB", "4.7GB" ou
    toute variante contenant un suffixe d'unite (K, M, G, T) suivi de
    "B".  Retourne None si aucune correspondance n'est trouvee.
    """
    match = re.search(r"(\d+(?:[.,]\d+)?\s*[KMGT]?B)", text, re.IGNORECASE)
    return match.group(1).replace(" ", "") if match else None


def docker_models() -> list[tuple[str, str, float]]:
    """
    (nom, identifiant de blob, taille) tels que vus par le moteur servant.

    La commande etait `docker exec ollama-server ollama list`, ecrite en
    dur. Une fois le moteur sorti de Docker et le conteneur supprime, elle
    a echoue en silence et le script a conclu "aucun modele lisible" --
    diagnostic faux, puisque vingt-deux modeles etaient servis depuis
    l'hote. C'est `ollama_location()` qui sait ou regarder ; l'ignorer
    revient a decrire une machine qui n'existe plus.
    """
    lieu = capability.ollama_location()
    commande = (["ollama", "list"] if lieu.get("host_native")
                else ["docker", "exec", OLLAMA_CONTAINER, "ollama", "list"])
    try:
        result = subprocess.run(
            commande,
            capture_output=True, text=True, timeout=60,
            encoding="utf-8", errors="replace",
        )
    except (subprocess.SubprocessError, OSError) as exc:
        # Conserver le diagnostic pour le debogage.
        print(f"Erreur lors de l'execution de {' '.join(commande)} : {exc}", file=sys.stderr)
        return []
    rows = []
    for line in result.stdout.splitlines()[1:]:
        parts = line.split()
        if len(parts) < 2:
            continue
        # Ignorer les modeles cloud qui n'ont pas de poids local.
        if parts[0].endswith(":cloud"):
            continue
        size_str = _extract_size(line)
        if not size_str:
            continue
        try:
            taille = capability.parse_size(size_str)
        except Exception:  # pragma: no cover
            # Si le parsing echoue, on ignore simplement ce modele.
            continue
        if taille <= 0:
            continue
        rows.append((parts[0], parts[1], taille))
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", metavar="FICHIER",
                        help="ecrit la liste retenue, prête pour ollama pull")
    args = parser.parse_args()

    # -----------------------------------------------------------------------
    # Construction du profil materiel avec gestion d'erreur et validation
    # des cles attendues.
    # -----------------------------------------------------------------------
    try:
        profile = capability.build_profile()
    except Exception as exc:  # pragma: no cover
        print(f"Erreur lors de la construction du profil : {exc}", file=sys.stderr)
        return 1

    # Validation explicite des champs du profil.
    required_keys = ["free_disk_gb", "model_store", "inference_memory_gb", "ollama"]
    for key in required_keys:
        if key not in profile:
            print(f"Erreur : le profil ne contient pas la cle '{key}'.", file=sys.stderr)
            return 1
    if "mode" not in profile["ollama"]:
        print("Erreur : le sous-dictionnaire 'ollama' ne contient pas la cle 'mode'.", file=sys.stderr)
        return 1

    rows = docker_models()
    if not rows:
        print("Aucun modele lisible sur le moteur Ollama servant.", file=sys.stderr)
        return 1

    # Un meme blob peut porter deux noms (codestral:latest et codestral:22b
    # partagent le meme identifiant). Le compter deux fois surestimerait
    # gravement le volume a migrer.
    by_blob: dict[str, list[tuple[str, float]]] = {}
    for name, blob, size in rows:
        by_blob.setdefault(blob, []).append((name, size))

    unique = []
    for blob, names in by_blob.items():
        canonical = sorted(names, key=lambda n: (len(n[0]), n[0]))[0]
        unique.append((canonical[0], canonical[1], [n for n, _ in names]))

    total_raw = sum(size for _, _, size in rows)
    total_unique = sum(size for _, size, _ in unique)

    # Verdict materiel : inutile de migrer ce qui ne s'executera jamais.
    runnable, rejected = [], []
    for name, size, aliases in unique:
        state, reason = capability.verdict(size, profile)
        (rejected if state == capability.REJECT else runnable).append(
            (name, size, aliases, state, reason))

    budget = max(profile["free_disk_gb"] - DISK_RESERVE_GB, 0.0)

    # Couverture des roles d'abord, elargissement ensuite.
    chosen: list[tuple[str, float, str]] = []
    used = 0.0
    taken: set[str] = set()

    for key, pattern, label in ROLES:
        candidates = [r for r in runnable
                      if re.match(pattern, r[0]) and r[0] not in taken]
        # A role couvre, le plus leger suffit : la place economisee
        # profite aux roles suivants.
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
        chosen.append((name, size, "elargissement"))
        taken.add(name)
        used += size

    left = [(n, s) for n, s, a, st, r in runnable if n not in taken]

    print("=" * 72)
    print(" Plan de sortie des modeles hors de Docker")
    print("=" * 72)
    print("  Poids listes         : %.0f Go" % total_raw)
    print("  Poids reels (dedoublonnes) : %.0f Go" % total_unique)
    print("  Disque libre         : %.0f Go sur %s"
          % (profile["free_disk_gb"], profile["model_store"]))
    print("  Budget de migration  : %.0f Go (reserve de %.0f Go)"
          % (budget, DISK_RESERVE_GB))
    print("  Memoire du moteur    : %.0f Go (%s)"
          % (profile["inference_memory_gb"], profile["ollama"]["mode"]))

    print("\n" + "-" * 72)
    print("\n  A MIGRER — %d modeles, %.0f Go" % (len(chosen), used))
    for name, size, label in chosen:
        print("    %-28s %6.1f Go   %s" % (name, size, label))

    if rejected:
        total_rejected = sum(size for _, size, _, _, _ in rejected)
        print("\n  A NE PAS MIGRER — inexecutable ici, %.0f Go recuperables"
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
        print("\n  Ils redeviendront telechargeables une fois le volume Docker")
        print("  supprime : c'est lui qui occupe la place aujourd'hui.")

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
        # `--write ../../ailleurs.txt` ecrivait hors du depot sans un mot.
        # La comparaison se fait par `commonpath` et non par `startswith` :
        # un repertoire voisin nommé `local-llm-docker-prive` commence par
        # la racine sans etre dedans, et un controle par prefixe l'aurait
        # accepte -- c'est-a-dire precisely le cas qu'il pretend couvrir.
        try:
            dedans = os.path.commonpath(
                [os.path.realpath(target), os.path.realpath(ROOT)]
            ) == os.path.realpath(ROOT)
        except ValueError:
            # Lecteurs differents sous Windows : `commonpath` lève plutôt que
            # de rendre un resultat trompeur. C'est donc un refus.
            dedans = False
        if not dedans:
            print("Refus : %s est hors du depot." % target)
            return 1
        lines = [
            "# Inventaire local a telecharger sur l'hote.",
            "# Genere par scripts/nexus_migration_plan.py - %d modeles, %.0f Go."
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
