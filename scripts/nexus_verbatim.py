#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Conserver VERBATIM ce que chaque agent a produit.

POURQUOI
--------
Un workflow massif isole ses agents — worktrees, copies, plans séparés — et
c'est bien. Mais l'isolation sans récupération ne vaut rien : aujourd'hui la
sortie d'un agent passe dans le terminal et disparaît. Mesuré : le magasin
d'observations garde `debit_jps`, `duree_ms`, `tokens_in`, `tokens_out` — et
jamais le texte produit. Un travail qu'on ne peut pas relire est un travail
perdu.

Et il doit être récupérable **tel quel**. Faire résumer la production d'un
agent par un autre modèle remplace ce qui a été écrit par ce qu'un second
modèle croit y avoir lu : c'est précisément ce que la trace verbatim
interdit. `--lire` imprime le contenu brut, sans en-tête ni décoration.

Le magasin vit sous `.nexus/`, qui est gitignoré : ces traces sont locales,
volumineuses, et propres à une machine.

Écrit par le banc (`gpt-oss-120b-cloud`, 3919 jetons, coût nul), intégré
après arbitrage de trois défauts, dont deux bloquants :

* `os.makedirs()` était appelé au niveau du MODULE, donc à l'import. Un
  échec de création — droits, disque plein — aurait fait lever l'IMPORT,
  contredisant frontalement la promesse « ne lève jamais » de `deposer` et
  cassant tout script qui l'importe. La création se fait maintenant au
  moment du dépôt, dans le try ;
* `_purger` rendait `0` quand `jours < 1` et un couple sinon ; l'appelant
  dépaquetant un couple, la commande plantait sur `--purger 0` — le cas
  précis que la garde était censée protéger ;
* `datetime.utcnow()`, déprécié, remplacé par un instant conscient du
  fuseau.

Ajouté à l'arbitrage : les fichiers présents sur le disque mais absents de
l'index ne sont plus ignorés par la purge. Un fichier qu'aucun index ne
nomme est le plus difficile à retrouver, donc celui qui s'accumule.

    python scripts/nexus_verbatim.py --lister
    python scripts/nexus_verbatim.py --lire <id>
    python scripts/nexus_verbatim.py --dernier
    python scripts/nexus_verbatim.py --purger 30
"""
from __future__ import annotations

import argparse
import io
import json
import os
import re
import sys
import uuid
from datetime import datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAGASIN = os.path.join(ROOT, ".nexus", "verbatim")
INDEX = os.path.join(MAGASIN, "index.jsonl")


def _nom_sur(modele: str) -> str:
    """
    Le nom du modèle sert de NOM DE FICHIER.

    Non filtré, un alias contenant « .. » ou un séparateur écrirait ailleurs
    sur le disque. On ne garde que ce qui ne peut désigner aucun autre
    répertoire.
    """
    return re.sub(r"[^A-Za-z0-9._-]", "_", str(modele or "inconnu"))


def deposer(reponse: str, modele: str, tache: str = "",
            plan: str = "inconnu") -> str:
    """
    Écrit la production brute et rend son identifiant, ou "" en cas d'échec.

    Ne lève JAMAIS. Conserver une trace ne doit pas pouvoir faire échouer le
    travail qu'elle trace : perdre la trace est regrettable, perdre le
    travail est inacceptable.
    """
    try:
        propre = _nom_sur(modele)
        maintenant = datetime.now(timezone.utc)
        ident = "%s-%s-%s" % (maintenant.strftime("%Y%m%d-%H%M%S"), propre,
                              uuid.uuid4().hex[:8])
        # La creation du repertoire est ICI, et non a l'import : un echec ne
        # doit casser que le depot, jamais le chargement du module.
        os.makedirs(MAGASIN, exist_ok=True)
        with io.open(os.path.join(MAGASIN, ident + ".txt"), "w",
                     encoding="utf-8", errors="replace") as fh:
            fh.write(reponse if isinstance(reponse, str) else str(reponse))
        
        # Une preuve placee hors de l'arbre echappe a l'isolement par worktree, 
        # donc l'origine de chaque entree doit etre lisible, et la menace 
        # pensee etait l'effacement quand la menace reelle est l'AJOUT.
        origine = os.getcwd()[-120:]

        entree = {
            "id": ident,
            "le": maintenant.isoformat(),
            "modele": propre,
            "tache": str(tache or "")[:120],
            "octets": len((reponse or "").encode("utf-8", "replace")),
            "plan": plan,
            "origine": origine,
        }
        with io.open(INDEX, "a", encoding="utf-8", errors="replace") as fh:
            fh.write(json.dumps(entree, ensure_ascii=False) + "\n")
        return ident
    except Exception:
        return ""


def charger_index() -> tuple:
    """Entrées lisibles et compte des lignes sautées. Ne lève jamais."""
    entrees, sautees = [], 0
    if not os.path.isfile(INDEX):
        return entrees, sautees
    try:
        with io.open(INDEX, encoding="utf-8", errors="replace") as fh:
            for ligne in fh:
                ligne = ligne.strip()
                if not ligne:
                    continue
                try:
                    e = json.loads(ligne)
                    if isinstance(e, dict) and e.get("id"):
                        entrees.append(e)
                    else:
                        sautees += 1
                except Exception:
                    # Une ligne corrompue -- interruption, ecriture
                    # concurrente -- ne doit pas cacher les entrees saines.
                    sautees += 1
    except OSError:
        pass
    return entrees, sautees


def lire(ident: str):
    chemin = os.path.join(MAGASIN, str(ident) + ".txt")
    if not os.path.isfile(chemin):
        return None
    try:
        with io.open(chemin, encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except OSError:
        return None


def purger(jours: int) -> tuple:
    """
    Supprime les productions plus vieilles que N jours, index compris.

    Rend TOUJOURS un couple (supprimes, sautees) — le jet d'origine rendait
    un entier quand le garde se déclenchait, et l'appelant, qui dépaquette,
    plantait sur le cas même que le garde protégeait.
    """
    if jours < 1:
        return -1, 0
    limite = datetime.now(timezone.utc) - timedelta(days=jours)
    entrees, sautees = charger_index()
    gardees, supprimes, connus = [], 0, set()
    for e in entrees:
        connus.add(e["id"])
        try:
            quand = datetime.fromisoformat(e.get("le") or "")
            if quand.tzinfo is None:
                quand = quand.replace(tzinfo=timezone.utc)
        except Exception:
            # Date illisible : on GARDE. Supprimer sur une date qu'on ne sait
            # pas lire reviendrait a supprimer au hasard.
            gardees.append(e)
            continue
        if quand >= limite:
            gardees.append(e)
            continue
        try:
            os.remove(os.path.join(MAGASIN, e["id"] + ".txt"))
        except OSError:
            pass
        supprimes += 1

    # Les fichiers qu'aucune ligne d'index ne nomme sont les plus difficiles a
    # retrouver, donc ceux qui s'accumulent. Le jet d'origine les ignorait.
    try:
        for nom in os.listdir(MAGASIN):
            if not nom.endswith(".txt") or nom[:-4] in connus:
                continue
            chemin = os.path.join(MAGASIN, nom)
            try:
                age = datetime.fromtimestamp(os.path.getmtime(chemin),
                                             timezone.utc)
                if age < limite:
                    os.remove(chemin)
                    supprimes += 1
            except OSError:
                continue
    except OSError:
        pass

    try:
        with io.open(INDEX, "w", encoding="utf-8", errors="replace") as fh:
            for e in gardees:
                fh.write(json.dumps(e, ensure_ascii=False) + "\n")
    except OSError:
        pass
    return supprimes, sautees


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    p = argparse.ArgumentParser(description=__doc__)
    g = p.add_mutually_exclusive_group()
    g.add_argument("--lister", nargs="?", const=20, type=int, metavar="N")
    g.add_argument("--lire", metavar="ID")
    g.add_argument("--dernier", action="store_true")
    g.add_argument("--purger", metavar="JOURS", type=int)
    p.add_argument("--json", action="store_true")
    a = p.parse_args()

    if a.lire:
        contenu = lire(a.lire)
        if contenu is None:
            sys.stderr.write("Production introuvable : %s\n" % a.lire)
            return 1
        # Brut, sans en-tete ni decoration : c'est le sens du mot verbatim.
        sys.stdout.write(contenu)
        return 0

    if a.dernier:
        entrees, _ = charger_index()
        if not entrees:
            sys.stderr.write("Aucune production conservee.\n")
            return 1
        recente = max(entrees, key=lambda e: e.get("le") or "")
        contenu = lire(recente["id"])
        if contenu is None:
            sys.stderr.write("Fichier absent pour %s\n" % recente["id"])
            return 1
        sys.stdout.write(contenu)
        return 0

    if a.purger is not None:
        supprimes, sautees = purger(a.purger)
        if supprimes < 0:
            sys.stderr.write("JOURS doit valoir au moins 1.\n")
            return 1
        print("%d production(s) supprimee(s)." % supprimes)
        if sautees:
            print("%d ligne(s) d'index illisibles, ignorees." % sautees)
        return 0

    entrees, sautees = charger_index()
    entrees.sort(key=lambda e: e.get("le") or "", reverse=True)
    montrees = entrees[:(a.lister or 20)]

    if a.json:
        print(json.dumps({"productions": montrees, "lignes_ignorees": sautees},
                         ensure_ascii=False, indent=2))
        return 0

    if not montrees:
        print("Aucune production conservee. Le magasin se remplit a chaque")
        print("appel d'agent : %s" % MAGASIN)
        return 0

    print("%-26s %-20s %-24s %9s  %s"
          % ("id", "quand", "modele", "octets", "tache"))
    print("-" * 108)
    for e in montrees:
        print("%-26s %-20s %-24s %9d  %s"
              % (e["id"][:26], (e.get("le") or "")[:19],
                 (e.get("modele") or "")[:24], e.get("octets") or 0,
                 (e.get("tache") or "")[:36]))
    print("-" * 108)
    print("%d production(s) sur %d conservee(s)." % (len(montrees), len(entrees)))
    if sautees:
        print("%d ligne(s) d'index illisibles, ignorees." % sautees)
    return 0


if __name__ == "__main__":
    sys.exit(main())
