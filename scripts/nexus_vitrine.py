#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sauvegarde vitrine : ne publie que si l'état est sain.

Pousser vers un dépôt **public** est la seule action de ce dépôt qui soit à
la fois sortante et irréversible : ce qui part est indexable, et le retirer
ensuite ne le retire pas des caches. Le garde-fou compte donc plus que le
geste, et ce script est écrit comme un garde-fou auquel on a ajouté un
push — pas comme un push auquel on a ajouté des vérifications.

Il constate et publie ; il ne corrige rien. Un BLOQUE n'est pas une panne
du script : c'est son résultat.

    python scripts/nexus_vitrine.py --simulation
    python scripts/nexus_vitrine.py
    python scripts/nexus_vitrine.py --epreuve

Squelette produit par le banc gratuit, intégré après correction de trois
défauts réels :

* le verdict MENTAIT en simulation — un blocage s'affichait « SIMULATION »
  parce que la condition testait le mode avant le résultat. Un rapport qui
  annonce un succès sur un échec est pire qu'aucun rapport ;
* `git rev-parse` était appelé deux fois, la seconde sans garde ;
* l'enchaînement était un escalier de huit `else` imbriqués, où l'ajout d'un
  contrôle imposait de ré-indenter tout le reste.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

OK, BLOQUE, IGNORE = "OK", "BLOQUE", "IGNORE"

# Nommés, jamais anonymes : en cas de détection on imprime le NOM du motif et
# le chemin, jamais la valeur trouvée — un garde-fou qui recopie le secret
# dans un journal l'a publié lui aussi.
MOTIFS = (
    ("cle-openai", re.compile(r"sk-[A-Za-z0-9]{16,}")),
    ("jeton-github", re.compile(r"ghp_[A-Za-z0-9]{20,}")),
    ("cle-aws", re.compile(r"AKIA[0-9A-Z]{16}")),
)
MOTIF_ENV = re.compile(r"^[A-Z_]{4,}=(\S{20,})", re.MULTILINE)

# Un `.env.example` EST fait pour être suivi : ses valeurs sont des consignes,
# pas des secrets. Le motif brut ci-dessus a bloqué la première publication sur
# POSTGRES_PASSWORD, LITELLM_MASTER_KEY et LANGFUSE_HOST — deux marque-places
# « REMPLACER… » et une URL publique. Trois blocages, zéro secret.
#
# Un garde-fou qui bloque toujours finit désactivé, et c'est alors le vrai
# secret qui passe. On écarte donc ce qui ne peut pas être un secret, et rien
# d'autre : une valeur qui n'est ni un marque-place ni une URL reste bloquante.
INOFFENSIF = re.compile(
    r"^(https?://|\$\{|<|REMPLACER|A_REMPLIR|CHANGE|CHANGEME|TODO|X{3,}|"
    r"VOTRE|YOUR|EXEMPLE|EXAMPLE|PLACEHOLDER|DUMMY|FAKE)", re.IGNORECASE)

PLAFOND_OCTETS = 2 * 1024 * 1024


def executer(cmd: list, cwd: Path, delai: int = 60) -> subprocess.CompletedProcess:
    """Jamais de trace : un échec de sous-processus est un résultat, pas un bug."""
    try:
        return subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True,
                              timeout=delai, encoding="utf-8", errors="replace")
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(cmd, 124, "", "delai depasse")
    except OSError as exc:
        return subprocess.CompletedProcess(cmd, 125, "", str(exc))


def racine_git(depart: Path):
    r = executer(["git", "rev-parse", "--show-toplevel"], depart, 30)
    if r.returncode != 0 or not r.stdout.strip():
        return None
    return Path(r.stdout.strip())


def arbre_propre(racine: Path) -> tuple:
    r = executer(["git", "status", "--porcelain"], racine)
    if r.returncode != 0:
        return BLOQUE, "git status a echoue"
    lignes = [l for l in r.stdout.splitlines() if l.strip()]
    if lignes:
        return BLOQUE, "%d fichier(s) non commite(s)" % len(lignes)
    return OK, "rien a commiter"


def env_hors_git(racine: Path) -> tuple:
    """
    `.env` suivi par git est un blocage absolu, sans discussion possible.

    Un commit suffit : le secret est dans l'historique, donc publié même si
    le fichier disparaît au commit suivant.
    """
    r = executer(["git", "ls-files", "--error-unmatch", ".env"], racine, 30)
    if r.returncode == 0:
        return BLOQUE, ".env est SUIVI par git -- publication refusee"
    return OK, ".env non suivi"


def fichiers_suivis(racine: Path) -> list:
    r = executer(["git", "ls-files"], racine)
    if r.returncode != 0:
        return []
    return [l.strip() for l in r.stdout.splitlines() if l.strip()]


def scruter(racine: Path, relatif: str) -> list:
    """Motifs déclenchés par un fichier. Binaires et gros fichiers écartés."""
    chemin = racine / relatif
    try:
        if not chemin.is_file() or chemin.stat().st_size > PLAFOND_OCTETS:
            return []
        brut = chemin.read_bytes()
        if b"\0" in brut[:1024]:
            return []
        texte = brut.decode("utf-8", errors="replace")
    except OSError:
        return []
    touches = [nom for nom, rx in MOTIFS if rx.search(texte)]
    if Path(relatif).name.startswith(".env"):
        for valeur in MOTIF_ENV.findall(texte):
            if not INOFFENSIF.match(valeur):
                touches.append("affectation-env")
                break
    return touches


def aucun_secret(racine: Path) -> tuple:
    suivis = fichiers_suivis(racine)
    if not suivis:
        return BLOQUE, "aucun fichier suivi -- depot inattendu"
    trouves = []
    for relatif in suivis:
        for nom in scruter(racine, relatif):
            trouves.append("%s (%s)" % (relatif, nom))
    if trouves:
        return BLOQUE, "; ".join(trouves[:5])
    return OK, "%d fichier(s) scrutes, aucun motif" % len(suivis)


def sous_controle(racine: Path, script: str, saute: bool) -> tuple:
    if saute:
        return IGNORE, "saute par --sauf-tests"
    chemin = racine / "scripts" / script
    if not chemin.is_file():
        return BLOQUE, "%s introuvable" % script
    r = executer([sys.executable, str(chemin)], racine, 600)
    if r.returncode != 0:
        lignes = [l for l in (r.stdout or "").splitlines() if l.strip()]
        motif = lignes[-1][:60] if lignes else "code %d" % r.returncode
        return BLOQUE, motif
    return OK, "verdict conforme"


def remote_present(racine: Path) -> tuple:
    r = executer(["git", "remote", "get-url", "origin"], racine, 30)
    if r.returncode != 0 or not r.stdout.strip():
        return BLOQUE, "aucun remote origin"
    url = r.stdout.strip()
    # L'URL peut porter un jeton (https://x:JETON@github.com/...). On ne
    # l'imprime jamais telle quelle.
    if "@" in url:
        url = url.split("@", 1)[1]
    return OK, url


def amont_present(racine: Path) -> tuple:
    r = executer(["git", "rev-parse", "--abbrev-ref", "--symbolic-full-name",
                  "@{u}"], racine, 30)
    if r.returncode != 0 or not r.stdout.strip():
        return BLOQUE, "branche sans amont"
    return OK, r.stdout.strip()


def epreuve() -> int:
    """
    Le garde voit-il quelque chose ?

    Mesuré sur ce dépôt : 121 fichiers suivis, zéro déclenchement. C'est le
    résultat souhaité — et il ne prouve RIEN sur la capacité à détecter. Un
    motif mal écrit rend exactement le même silence. On injecte donc un faux
    secret et on exige qu'il soit vu.

    Les valeurs ci-dessous sont fabriquées par répétition pour ne ressembler
    à aucune clef réelle.
    """
    import tempfile
    cas = [
        ("cle-openai", "config.py", "CLE = sk-" + "A" * 24),
        ("jeton-github", "notes.md", "jeton ghp_" + "B" * 30),
        ("cle-aws", "deploy.sh", "AKIA" + "C" * 16),
        ("affectation-env", ".env.exemple", "SECRET_TRES_LONG=" + "D" * 30),
    ]
    echecs = 0
    with tempfile.TemporaryDirectory() as rep:
        racine = Path(rep)
        for attendu, nom, contenu in cas:
            (racine / nom).write_text(contenu, encoding="utf-8")
            vus = scruter(racine, nom)
            bon = attendu in vus
            print("  [%-6s] %-16s %s" % (OK if bon else BLOQUE, attendu,
                                         "detecte" if bon else "NON DETECTE"))
            echecs += 0 if bon else 1
        # Et le contraire, qui compte tout autant : ce qui NE doit PAS
        # declencher. Les trois cas ci-dessous ne sont pas theoriques -- ils
        # ont bloque la premiere publication reelle de ce depot.
        muets = [
            ("texte-anodin", "lisez.md",
             "Poser sa cle sk dans un fichier suivi est interdit.\n"),
            ("marque-place", ".env.example",
             "POSTGRES_PASSWORD=REMPLACER_PAR_UN_MOT_DE_PASSE\n"),
            ("url-publique", ".env.example",
             "LANGFUSE_HOST=https://cloud.langfuse.com\n"),
        ]
        for nom, fichier, contenu in muets:
            (racine / fichier).write_text(contenu, encoding="utf-8")
            faux = scruter(racine, fichier)
            print("  [%-6s] %-16s %s"
                  % (OK if not faux else BLOQUE, nom,
                     "silencieux" if not faux else "FAUX POSITIF : %s" % faux))
            echecs += 0 if not faux else 1
    print("-" * 60)
    print("Epreuve du garde : %s" % ("tenue." if not echecs
                                     else "%d defaut(s)." % echecs))
    return 1 if echecs else 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--racine", type=Path, default=None)
    p.add_argument("--simulation", action="store_true",
                   help="tout verifier, n'annoncer le push que par ecrit")
    p.add_argument("--json", action="store_true")
    p.add_argument("--sauf-tests", action="store_true",
                   help="sauter conformite et rituel (deconseille)")
    p.add_argument("--epreuve", action="store_true",
                   help="verifier que le detecteur de secrets detecte")
    a = p.parse_args()

    if a.epreuve:
        return epreuve()

    depart = a.racine or Path.cwd()
    racine = a.racine or racine_git(depart)
    if racine is None or not (racine / ".git").exists():
        sys.stderr.write("Hors d'un depot git : %s\n" % depart)
        return 1

    # Une liste plate, pas un escalier : ajouter un controle est une ligne.
    controles = [
        ("arbre propre", lambda: arbre_propre(racine)),
        (".env hors de git", lambda: env_hors_git(racine)),
        ("aucun secret", lambda: aucun_secret(racine)),
        ("conformite", lambda: sous_controle(racine, "nexus_conformite.py",
                                             a.sauf_tests)),
        ("rituel de fin de tour", lambda: sous_controle(racine,
                                                        "nexus_rituel.py",
                                                        a.sauf_tests)),
        ("remote origin", lambda: remote_present(racine)),
        ("amont de la branche", lambda: amont_present(racine)),
    ]

    resultats = []
    for nom, fn in controles:
        try:
            statut, detail = fn()
        except Exception as exc:
            statut, detail = BLOQUE, str(exc).splitlines()[0][:60]
        resultats.append((nom, statut, detail))
        # On s'arrete au premier blocage : les controles suivants coutent des
        # minutes et ne changeraient pas le verdict.
        if statut == BLOQUE:
            break

    sain = not [r for r in resultats if r[1] == BLOQUE]

    if sain:
        if a.simulation:
            resultats.append(("publication", IGNORE,
                              "simulation -- git push origin HEAD non execute"))
        else:
            r = executer(["git", "push", "origin", "HEAD"], racine, 600)
            if r.returncode == 0:
                resultats.append(("publication", OK, "poussee vers origin"))
            else:
                lignes = (r.stderr or r.stdout or "").strip().splitlines()
                resultats.append(("publication", BLOQUE,
                                  lignes[-1][:70] if lignes else "push a echoue"))
                sain = False

    if a.json:
        print(json.dumps({
            "racine": str(racine),
            "simulation": a.simulation,
            "controles": [{"nom": n, "statut": s, "detail": d}
                          for n, s, d in resultats],
            "verdict": OK if sain else BLOQUE,
        }, ensure_ascii=False, indent=2))
        return 0 if sain else 1

    print("Sauvegarde vitrine -- %s" % racine)
    print("-" * 72)
    for nom, statut, detail in resultats:
        print("  [%-6s] %-22s %s" % (statut, nom, detail))
    print("-" * 72)
    # Le verdict lit le RESULTAT d'abord, le mode ensuite. L'inverse -- la
    # faute du premier jet -- annoncait « SIMULATION » sur un blocage.
    if not sain:
        print("VERDICT : publication REFUSEE. Rien n'est parti.")
    elif a.simulation:
        print("VERDICT : sain. La publication reelle passerait.")
    else:
        print("VERDICT : vitrine publiee.")
    return 0 if sain else 1


if __name__ == "__main__":
    sys.exit(main())
