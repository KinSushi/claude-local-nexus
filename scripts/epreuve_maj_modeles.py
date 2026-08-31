# -*- coding: utf-8 -*-
"""Un modele mis a jour invalide-t-il REELLEMENT ses deux releves ?

Le premier jet employait un drapeau partage entre latences.json et
epreuves.json : un modele nettoye dans le premier etait saute dans le
second, et sa preuve de CAPACITE survivait au changement de poids -- or
c'est elle qui autorise une derogation au seuil de latence (contrat
105.2). Une demi-invalidation se lit comme faite.
"""
import os
import sys
import json
import io
import shutil
import tempfile

# add the directory containing this script to sys.path
script_dir = os.path.abspath(os.path.dirname(__file__))
if script_dir not in sys.path:
    sys.path.insert(0, script_dir)

from nexus_maj_modeles import invalider_mesures

echecs = 0


def verifier(nom, condition, detail):
    global echecs
    if condition:
        print(f"  [OK  ] {nom} : {detail}")
    else:
        print(f"  [RATE] {nom} : {detail}")
        echecs += 1


def ecrire_json(chemin, data):
    """Write JSON atomically."""
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(chemin))
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, chemin)


def lire_json(chemin):
    with open(chemin, "r", encoding="utf-8") as f:
        return json.load(f)


def cas1():
    """FORWARD, forme 'modeles'."""
    tmp = tempfile.mkdtemp()
    try:
        nexus = os.path.join(tmp, ".nexus")
        os.makedirs(nexus)

        lat_path = os.path.join(nexus, "latences.json")
        epr_path = os.path.join(nexus, "epreuves.json")

        data = {"modeles": {"qwen3.6-27b-local": {}, "llama3.2-3b-local": {}}}
        ecrire_json(lat_path, data)
        ecrire_json(epr_path, data)

        ret = invalider_mesures(["qwen3.6:27b"], racine=tmp)

        lat = lire_json(lat_path)
        epr = lire_json(epr_path)

        verifier(
            "cas1 latences retire",
            "qwen3.6-27b-local" not in lat.get("modeles", {}),
            "alias removed from latences",
        )
        verifier(
            "cas1 epreuves retire",
            "qwen3.6-27b-local" not in epr.get("modeles", {}),
            "alias removed from epreuves",
        )
        verifier(
            "cas1 temoin intact latences",
            "llama3.2-3b-local" in lat.get("modeles", {}),
            "temoin still present in latences",
        )
        verifier(
            "cas1 temoin intact epreuves",
            "llama3.2-3b-local" in epr.get("modeles", {}),
            "temoin still present in epreuves",
        )
        verifier(
            "cas1 retour latences",
            "latences" in ret and "qwen3.6-27b-local" in ret["latences"],
            "alias listed in latences",
        )
        verifier(
            "cas1 retour epreuves",
            "epreuves" in ret and "qwen3.6-27b-local" in ret["epreuves"],
            "alias listed in epreuves",
        )
    finally:
        shutil.rmtree(tmp)


def cas2():
    """les deux relevés, pas un seul."""
    tmp = tempfile.mkdtemp()
    try:
        nexus = os.path.join(tmp, ".nexus")
        os.makedirs(nexus)

        lat_path = os.path.join(nexus, "latences.json")
        epr_path = os.path.join(nexus, "epreuves.json")

        data = {"modeles": {"qwen3.6-27b-local": {}, "llama3.2-3b-local": {}}}
        ecrire_json(lat_path, data)
        ecrire_json(epr_path, data)

        invalider_mesures(["qwen3.6:27b"], racine=tmp)

        epr = lire_json(epr_path)

        verifier(
            "cas2 epreuves nettoye",
            "qwen3.6-27b-local" not in epr.get("modeles", {}),
            "alias absent from epreuves after call",
        )
    finally:
        shutil.rmtree(tmp)


def cas3():
    """forme sans la cle 'modeles'."""
    tmp = tempfile.mkdtemp()
    try:
        nexus = os.path.join(tmp, ".nexus")
        os.makedirs(nexus)

        lat_path = os.path.join(nexus, "latences.json")
        epr_path = os.path.join(nexus, "epreuves.json")

        data = {"qwen3.6-27b-local": {}, "llama3.2-3b-local": {}}
        ecrire_json(lat_path, data)
        ecrire_json(epr_path, data)

        ret = invalider_mesures(["qwen3.6:27b"], racine=tmp)

        lat = lire_json(lat_path)
        epr = lire_json(epr_path)

        verifier(
            "cas3 latences retire",
            "qwen3.6-27b-local" not in lat,
            "alias removed from latences",
        )
        verifier(
            "cas3 epreuves retire",
            "qwen3.6-27b-local" not in epr,
            "alias removed from epreuves",
        )
        verifier(
            "cas3 retour latences",
            "latences" in ret and "qwen3.6-27b-local" in ret["latences"],
            "alias listed in latences",
        )
        verifier(
            "cas3 retour epreuves",
            "epreuves" in ret and "qwen3.6-27b-local" in ret["epreuves"],
            "alias listed in epreuves",
        )
    finally:
        shutil.rmtree(tmp)


def cas4():
    """suffixe ':latest'."""
    tmp = tempfile.mkdtemp()
    try:
        nexus = os.path.join(tmp, ".nexus")
        os.makedirs(nexus)

        lat_path = os.path.join(nexus, "latences.json")
        epr_path = os.path.join(nexus, "epreuves.json")

        data = {"modeles": {"codestral-local": {}, "llama3.2-3b-local": {}}}
        ecrire_json(lat_path, data)
        ecrire_json(epr_path, data)

        ret = invalider_mesures(["codestral:latest"], racine=tmp)

        lat = lire_json(lat_path)
        epr = lire_json(epr_path)

        verifier(
            "cas4 latences retire",
            "codestral-local" not in lat.get("modeles", {}),
            "alias removed from latences",
        )
        verifier(
            "cas4 epreuves retire",
            "codestral-local" not in epr.get("modeles", {}),
            "alias removed from epreuves",
        )
        verifier(
            "cas4 retour latences",
            "latences" in ret and "codestral-local" in ret["latences"],
            "alias listed in latences",
        )
        verifier(
            "cas4 retour epreuves",
            "epreuves" in ret and "codestral-local" in ret["epreuves"],
            "alias listed in epreuves",
        )
    finally:
        shutil.rmtree(tmp)


def cas5():
    """REVERSE, releve illisible."""
    tmp = tempfile.mkdtemp()
    try:
        nexus = os.path.join(tmp, ".nexus")
        os.makedirs(nexus)

        lat_path = os.path.join(nexus, "latences.json")
        epr_path = os.path.join(nexus, "epreuves.json")

        # write invalid JSON to latences
        with open(lat_path, "w", encoding="utf-8") as f:
            f.write("{ ceci n'est pas du json")

        # write valid epreuves containing the alias
        epr_data = {"modeles": {"qwen3.6-27b-local": {}, "llama3.2-3b-local": {}}}
        ecrire_json(epr_path, epr_data)

        # capture original bytes of latences
        with open(lat_path, "rb") as f:
            lat_original = f.read()

        ret = invalider_mesures(["qwen3.6:27b"], racine=tmp)

        # verify latences unchanged
        with open(lat_path, "rb") as f:
            lat_after = f.read()
        verifier(
            "cas5 latences inchanged",
            lat_original == lat_after,
            "invalid file left untouched",
        )

        # verify epreuves cleaned
        epr = lire_json(epr_path)
        verifier(
            "cas5 epreuves retire",
            "qwen3.6-27b-local" not in epr.get("modeles", {}),
            "alias removed from epreuves",
        )

        # verify retour contient illisibles
        verifier(
            "cas5 retour illisibles",
            "illisibles" in ret and lat_path in ret["illisibles"],
            "path of unreadable file reported",
        )
    finally:
        shutil.rmtree(tmp)


def cas6():
    """liste vide et fichier absent."""
    # partie 1 : liste vide, .nexus present
    tmp = tempfile.mkdtemp()
    try:
        nexus = os.path.join(tmp, ".nexus")
        os.makedirs(nexus)

        lat_path = os.path.join(nexus, "latences.json")
        epr_path = os.path.join(nexus, "epreuves.json")

        data = {"modeles": {"dummy": {}}}
        ecrire_json(lat_path, data)
        ecrire_json(epr_path, data)

        # record mtimes
        lat_mtime1 = os.path.getmtime(lat_path)
        epr_mtime1 = os.path.getmtime(epr_path)

        ret = invalider_mesures([], racine=tmp)

        lat_mtime2 = os.path.getmtime(lat_path)
        epr_mtime2 = os.path.getmtime(epr_path)

        verifier(
            "cas6 vide aucune modification latences",
            lat_mtime1 == lat_mtime2,
            "latences unchanged",
        )
        verifier(
            "cas6 vide aucune modification epreuves",
            epr_mtime1 == epr_mtime2,
            "epreuves unchanged",
        )
        verifier(
            "cas6 vide retour vide",
            all(k in ret and ret[k] == [] for k in ("latences", "epreuves", "absents", "illisibles")),
            "all lists empty",
        )
    finally:
        shutil.rmtree(tmp)

    # partie 2 : .nexus absent
    tmp2 = tempfile.mkdtemp()
    try:
        # do not create .nexus
        ret2 = invalider_mesures([], racine=tmp2)
        verifier(
            "cas6 absent .nexus pas d'erreur",
            isinstance(ret2, dict),
            "function returns dict",
        )
        verifier(
            "cas6 absent .nexus listes vides",
            all(k in ret2 and ret2[k] == [] for k in ("latences", "epreuves", "absents", "illisibles")),
            "all lists empty when .nexus missing",
        )
    finally:
        shutil.rmtree(tmp2)


if __name__ == "__main__":
    cas1()
    cas2()
    cas3()
    cas4()
    cas5()
    cas6()
    print(f"\nBilan : {echecs} echec(s)")
    sys.exit(1 if echecs else 0)
#
