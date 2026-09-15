# -*- coding: utf-8 -*-
"""
Mesure du registre des tâches – 2026-09-15
Ce module implémente les décisions du plan « Registre des tâches — plan arbitré ».
Il ne réalise aucune action de mesure à l’import : tout accès disque ou sous‑processus
est limité aux fonctions explicites. Le timeout du rituel (120 s) impose de séparer
la phase de mesure (option --deriver) de la phase d’affichage (utilisée par
nexus_progres.py).

La mesure du 2026‑09‑15 (PROGRESS.MD) indiquait **35 sujets ouverts** alors que le
hook de reprise en annonçait plus de **1 081**. Aucun fichier
`CHECKLIST_PROGRESS.md` n’a jamais été produit et `scripts/nexus_rituel.py`
lance `nexus_progres` avec `timeout=120`, d’où la séparation entre `--deriver`
et le rendu.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
import datetime
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Any

# --------------------------------------------------------------------------- #
# Constantes
# --------------------------------------------------------------------------- #

RACINE: Path = Path(__file__).resolve().parent.parent
REGISTRE: Path = RACINE / "outillage" / "rituels" / "taches.jsonl"
CACHE: Path = RACINE / ".nexus" / "taches_verdicts.json"
DELAI_FAMILLE_S: int = 420

# Liste blanche des commandes autorisées (clé → argv).  À étendre en ajoutant
# des entrées du type "cle": ["executable", "arg1", "arg2"].
LISTE_BLANCHE: dict[str, list[str]] = {}

ETATS: tuple[str, ...] = ("FAIT", "A_FAIRE", "NON_MECANISABLE", "INCONNU")

# --------------------------------------------------------------------------- #
# Exceptions
# --------------------------------------------------------------------------- #

class RegistreInvalide(ValueError):
    """Erreur de lecture du registre.

    Args:
        ligne: Numéro de ligne (1‑based) où l’erreur a été détectée.
        message: Description de la règle violée.
    """
    def __init__(self, ligne: int, message: str) -> None:
        super().__init__(f"Ligne {ligne}: {message}")
        self.ligne = ligne
        self.message = message

# --------------------------------------------------------------------------- #
# Modèle de donnée
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class Tache:
    """Représente une tâche du registre."""
    id: str
    titre: str
    origine: str
    preuve: dict[str, Any] | None
    cree_le: str
    non_mecanisable: str | None

# --------------------------------------------------------------------------- #
# Lecture du registre
# --------------------------------------------------------------------------- #

_ID_PATTERN = re.compile(r"^T-\d{8}-\d{3}$")
_DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_FAMILLE_CLE_PATTERN = re.compile(r'args\.only\s+in\s+\(None,\s*"([^"]+)"\)')

def lire_registre(chemin: Path) -> list[Tache]:
    """Lit le registre JSON‑L et renvoie la liste des tâches validées.

    Lève :class:`RegistreInvalide` dès la première anomalie détectée.
    """
    if not chemin.is_file():
        raise RegistreInvalide(0, f"registre absent : {chemin}")

    taches: list[Tache] = []
    ids_vus: set[str] = set()

    try:
        f = chemin.open("r", encoding="utf-8")
    except OSError as exc:
        raise RegistreInvalide(0, f"registre illisible : {exc}") from None

    with f:
        for num, ligne in enumerate(f, start=1):
            ligne = ligne.strip()
            if not ligne:
                continue

            try:
                data = json.loads(ligne)
            except json.JSONDecodeError as exc:
                raise RegistreInvalide(num, f"JSON invalide ({exc})") from None

            if not isinstance(data, dict):
                raise RegistreInvalide(num, "l’objet JSON n’est pas un dictionnaire")

            # Clés autorisées
            cles_autorisees = {"id", "titre", "origine", "preuve", "cree_le", "non_mecanisable"}
            cles_inconnues = set(data) - cles_autorisees
            if cles_inconnues:
                raise RegistreInvalide(num, f"clés inconnues {sorted(cles_inconnues)}")

            # Champs obligatoires
            for champ in ("id", "titre", "origine", "cree_le"):
                if champ not in data:
                    raise RegistreInvalide(num, f"champ obligatoire « {champ} » manquant")
                if not isinstance(data[champ], str) or not data[champ].strip():
                    raise RegistreInvalide(num, f"champ « {champ} » vide ou non‑string")

            # Validation de l’identifiant
            ident = data["id"]
            if not _ID_PATTERN.fullmatch(ident):
                raise RegistreInvalide(num, f"id « {ident} » ne correspond pas au format T-YYYYMMDD-NNN")
            if ident in ids_vus:
                raise RegistreInvalide(num, f"id dupliqué « {ident} »")
            ids_vus.add(ident)

            # Validation de la date
            if not _DATE_PATTERN.fullmatch(data["cree_le"]):
                raise RegistreInvalide(num, f"date « {data['cree_le']} » invalide (format AAAA-MM-JJ)")

            # Preuve / non_mecanisable – exclusivité
            preuve = data.get("preuve")
            non_mec = data.get("non_mecanisable")
            if preuve is not None and non_mec is not None:
                raise RegistreInvalide(num, "les champs « preuve » et « non_mecanisable » sont mutuellement exclusifs")
            if preuve is None and non_mec is None:
                raise RegistreInvalide(num, "aucune preuve ni non_mecanisable fourni")

            # Validation de la preuve le cas échéant
            if preuve is not None:
                if not isinstance(preuve, dict):
                    raise RegistreInvalide(num, "le champ « preuve » doit être un dictionnaire")
                if "type" not in preuve:
                    raise RegistreInvalide(num, "preuve sans champ « type »")
                ptype = preuve["type"]
                if ptype not in {"famille", "commit", "commande"}:
                    raise RegistreInvalide(num, f"type de preuve inconnu « {ptype} »")
                if ptype in {"famille", "commande"}:
                    if "cible" not in preuve or not isinstance(preuve["cible"], str) or not preuve["cible"]:
                        raise RegistreInvalide(num, f"preuve de type « {ptype} » doit contenir une cible non vide")
                else:  # commit
                    if "cible" in preuve:
                        raise RegistreInvalide(num, "preuve de type « commit » ne doit pas contenir de champ « cible »")

            tache = Tache(
                id=ident,
                titre=data["titre"],
                origine=data["origine"],
                preuve=preuve,
                cree_le=data["cree_le"],
                non_mecanisable=non_mec,
            )
            taches.append(tache)

    return taches

# --------------------------------------------------------------------------- #
# Extraction des familles connues
# --------------------------------------------------------------------------- #

def familles_connues(racine: Path) -> set[str]:
    """Retourne l’ensemble des clés « --only » reconnues dans nexus_test.py."""
    chemin_test = racine / "outillage" / "nexus_test.py"
    if not chemin_test.is_file():
        return set()
    try:
        contenu = chemin_test.read_text(encoding="utf-8")
    except OSError:
        return set()
    return set(_FAMILLE_CLE_PATTERN.findall(contenu))

# --------------------------------------------------------------------------- #
# Exécution injectable
# --------------------------------------------------------------------------- #

Executer = Callable[[list[str], float], int | None]
LireSortie = Callable[[list[str], float], tuple[int, str] | None]

def executer_reel(argv: list[str], delai: float) -> int | None:
    """Exécute *argv* avec un timeout de *delai* secondes.

    Retourne le code de retour ou ``None`` en cas de timeout ou d’erreur système.
    """
    try:
        result = subprocess.run(
            argv,
            cwd=RACINE,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=delai,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        return result.returncode
    except (subprocess.TimeoutExpired, OSError):
        return None

def lire_sortie_reelle(argv: list[str], delai: float) -> tuple[int, str] | None:
    """Exécute *argv* et renvoie (code_retour, stdout) ou ``None`` en cas d’erreur."""
    try:
        result = subprocess.run(
            argv,
            cwd=RACINE,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=delai,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        return result.returncode, result.stdout
    except (subprocess.TimeoutExpired, OSError):
        return None

def head_courant(lire_sortie: LireSortie = lire_sortie_reelle) -> str | None:
    """Retourne le SHA complet du HEAD git, ou ``None`` si impossible."""
    sortie = lire_sortie(["git", "rev-parse", "HEAD"], 30.0)
    if sortie is None:
        return None
    code, out = sortie
    if code != 0:
        return None
    out = out.strip()
    return out if out else None

# --------------------------------------------------------------------------- #
# Dérivation d’un état
# --------------------------------------------------------------------------- #

def _type_cible(tache: Tache) -> tuple[str | None, str | None]:
    """Extrait (type, cible) de la preuve, ou (None, None) si non applicable."""
    if tache.preuve is None:
        return None, None
    ptype = tache.preuve.get("type")
    cible = tache.preuve.get("cible")
    return ptype, cible

def deriver(
    tache: Tache,
    *,
    familles: set[str],
    executer: Executer,
    lire_sortie: LireSortie,
) -> tuple[str, str]:
    """Calcule l’état et la raison d’une tâche.

    Retourne un tuple ``(etat, raison)`` où *raison* peut être vide.
    """
    if tache.non_mecanisable is not None:
        return "NON_MECANISABLE", tache.non_mecanisable

    ptype, cible = _type_cible(tache)

    if ptype == "famille":
        if cible not in familles:
            return "INCONNU", f"famille inconnue « {cible} »"
        code = executer(
            [sys.executable, str(RACINE / "outillage" / "nexus_test.py"), "--only", cible],
            DELAI_FAMILLE_S,
        )
        if code == 0:
            return "FAIT", ""
        if code is None:
            return "INCONNU", f"timeout ou erreur lors de l’exécution de la famille « {cible} »"
        return "A_FAIRE", f"code retour {code}"

    if ptype == "commit":
        cmd = ["git", "log", f"--grep=Tache: {tache.id}", "--format=%H", "-n", "1"]
        sortie = lire_sortie(cmd, 30.0)
        if sortie is None:
            return "INCONNU", "impossible d’interroger git"
        code, out = sortie
        if code != 0:
            return "INCONNU", f"git log retour {code}"
        sha = out.strip()
        if sha:
            return "FAIT", sha[:7]  # SHA court
        return "A_FAIRE", "commit absent"

    if ptype == "commande":
        if cible not in LISTE_BLANCHE:
            return "INCONNU", f"commande « {cible} » hors liste blanche"
        argv_cmd = LISTE_BLANCHE[cible]
        code = executer(argv_cmd, DELAI_FAMILLE_S)
        if code == 0:
            return "FAIT", ""
        if code is None:
            return "INCONNU", f"timeout ou erreur commande « {cible} »"
        return "A_FAIRE", f"code retour {code}"

    # Cas impossible (schéma déjà validé)
    return "INCONNU", f"type de preuve inconnu « {ptype} »"

# --------------------------------------------------------------------------- #
# Gestion du cache
# --------------------------------------------------------------------------- #

def lire_cache(chemin: Path) -> dict:
    """Lit le fichier de cache, renvoie un dictionnaire vide en cas d’erreur."""
    try:
        with chemin.open("r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}

def ecrire_cache(chemin: Path, donnees: dict) -> None:
    """Écriture atomique du cache JSON."""
    chemin.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(
        dir=chemin.parent,
        prefix=".taches_verdicts.",
        suffix=".tmp",
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(donnees, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, chemin)
    finally:
        with suppress(OSError):
            os.unlink(tmp_path)

# --------------------------------------------------------------------------- #
# Mesure
# --------------------------------------------------------------------------- #

def mesurer(
    chemin_registre: Path,
    chemin_cache: Path,
    *,
    executer: Executer = executer_reel,
    lire_sortie: LireSortie = lire_sortie_reelle,
    racine: Path = RACINE,
) -> dict:
    """Mesure les tâches, met à jour le cache et renvoie un résumé.

    Le résultat possède les clés :
    - ``head`` : SHA du HEAD (ou ``None``)
    - ``verdicts`` : dict id → verdict
    - ``mesures`` : nombre de tâches dérivées
    - ``reutilises`` : nombre de verdicts réutilisés depuis le cache
    """
    taches = lire_registre(chemin_registre)
    head = head_courant(lire_sortie)
    cache = lire_cache(chemin_cache)

    cache_head = cache.get("head")
    cache_verdicts = cache.get("verdicts", {})

    familles = familles_connues(racine)

    verdicts: dict[str, dict] = {}
    n_derives = 0
    n_reutilises = 0

    for t in taches:
        id_ = t.id
        cached = cache_verdicts.get(id_)
        ptype, cible = _type_cible(t)

        if (
            cached
            and cache_head == head
            and cached.get("type") == ptype
            and cached.get("cible") == cible
        ):
            verdicts[id_] = cached
            n_reutilises += 1
            continue

        etat, raison = deriver(
            t,
            familles=familles,
            executer=executer,
            lire_sortie=lire_sortie,
        )
        verdicts[id_] = {
            "etat": etat,
            "raison": raison,
            "type": ptype,
            "cible": cible,
            "mesure_le": datetime.datetime.now().isoformat(timespec="seconds"),
        }
        n_derives += 1

    nouveau_cache = {"head": head, "verdicts": verdicts}
    ecrire_cache(chemin_cache, nouveau_cache)

    return {
        "head": head,
        "verdicts": verdicts,
        "mesures": n_derives,
        "reutilises": n_reutilises,
    }

# --------------------------------------------------------------------------- #
# Lecture pour rendu (sans mesure)
# --------------------------------------------------------------------------- #

def etats_pour_rendu(
    chemin_registre: Path,
    chemin_cache: Path,
    head: str | None,
) -> list[tuple[Tache, str, str]]:
    """Renvoie la liste (tâche, état, raison) à afficher.

    Aucun sous‑processus n’est lancé ; si le cache ne correspond pas au *head*
    fourni, l’état retourné est ``NON_MESURE``.
    """
    taches = lire_registre(chemin_registre)
    cache = lire_cache(chemin_cache)
    cache_head = cache.get("head")
    cache_verdicts = cache.get("verdicts", {})

    resultat: list[tuple[Tache, str, str]] = []
    for t in taches:
        if head is not None and cache_head == head:
            v = cache_verdicts.get(t.id)
            if v:
                resultat.append((t, v.get("etat", "INCONNU"), v.get("raison", "")))
                continue
        # Pas de verdict valable
        raison = (
            f"non mesurée depuis {head[:7]}" if head else "non mesurée (HEAD inconnu)"
        )
        resultat.append((t, "NON_MESURE", raison))
    return resultat

# --------------------------------------------------------------------------- #
# Interface en ligne de commande
# --------------------------------------------------------------------------- #

def _afficher_resume(resume: dict) -> None:
    """Affiche un petit résumé après une mesure."""
    print("Résumé de la mesure :")
    for etat in ETATS:
        nb = sum(1 for v in resume["verdicts"].values() if v["etat"] == etat)
        if nb:
            print(f"  {etat}: {nb}")
    print(f"  mesures effectuées : {resume['mesures']}")
    print(f"  verdicts réutilisés : {resume['reutilises']}")

def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="Gestion du registre de tâches Nexus."
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--deriver",
        action="store_true",
        help="Mesurer les preuves, mettre à jour le cache et afficher un résumé.",
    )
    group.add_argument(
        "--verifier",
        action="store_true",
        help="Vérifier la validité du registre (lecture seule).",
    )

    args = parser.parse_args(argv)

    if args.deriver:
        try:
            resume = mesurer(REGISTRE, CACHE)
        except RegistreInvalide as exc:
            print(f"Erreur de registre : {exc}", file=sys.stderr)
            return 2
        _afficher_resume(resume)
        return 0

    if args.verifier:
        try:
            _ = lire_registre(REGISTRE)
        except RegistreInvalide as exc:
            print(f"Erreur de registre : {exc}", file=sys.stderr)
            return 2
        print("Registre valide.")
        return 0

    parser.print_usage()
    return 2

if __name__ == "__main__":
    sys.exit(main())
