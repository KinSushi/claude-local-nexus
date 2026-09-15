#!/usr/bin/env python3
"""
Épreuve unitaire pour la gestion du flag « sans_repli » dans nexus_agent.py.

Chaque cas utilise son propre fichier de disjoncteur (dans un répertoire
temporaire) et vide le cache ``appeler._cache_plans`` avant d’appeler l’agent.
Les variables d’environnement modifiées sont restaurées dans un ``finally``
par cas. En cas d’échec, le résultat obtenu et le nombre d’appels enregistrés
sont affichés.
"""

import os
import sys
import urllib.error
import tempfile
import importlib.util
from pathlib import Path

# ---------------------------------------------------------------------------

def _faux_appeler(candidat, messages, plafond, cle, temperature):
    """Fake `appeler` used by the tests."""
    _faux_appeler.recorded.append(candidat)
    scenario = _faux_appeler.scenario
    if scenario == "exception":
        raise urllib.error.URLError("network failure")
    texte = "réponse factice" if scenario == "non_vide" else ""
    return {
        "texte": texte,
        "tronque": False,
        "tokens": 42,
        "servi_par": candidat,
        "adresse": "https://api.cloud-provider.com/v1",
        "cout": "0.0012",
        "duree": 1.23,
        "part_raisonnement": 0.123,
        "tokens_sortie": 10,
        "car_par_jeton": 4.2,
        "cause_vide": "contenu_present" if texte else "raisonnement_0",
        "modele": candidat,
    }

# ---------------------------------------------------------------------------

def _restaurer_env(vars_sauvegardes):
    """Restaure les variables d’environnement sauvegardées."""
    for name, value in vars_sauvegardes.items():
        if value is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = value

# ---------------------------------------------------------------------------

def main() -> int:
    # Chemin racine du projet
    racine = Path(__file__).parent.parent
    sys.path.insert(0, str(racine / "scripts"))

    # Variables d’environnement à sauvegarder/restaurer
    env_vars = [
        "NEXUS_ETAT_DISJONCTEUR",
        "NEXUS_MAX_REPLIS_LOCAUX",
        "NEXUS_SANS_REPLI",
    ]
    saved = {k: os.environ.get(k) for k in env_vars}

    # Chargement du module nexus_agent
    spec = importlib.util.spec_from_file_location(
        "nexus_agent", racine / "scripts" / "nexus_agent.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    # Remplacement des fonctions dépendantes du réseau
    module.replis_gratuits = lambda cle: ["cloud1-cloud", "cloud2-cloud"]
    module.poids_et_libre = lambda c: (None, None)
    module.memoire_suffisante = lambda p, l: True
    module.appeler = _faux_appeler
    module.appeler.recorded = []
    module.appeler._cache_plans = {
        "cloud1-cloud": "cloud",
        "cloud2-cloud": "cloud",
    }
    module.appeler.scenario = "non_vide"  # valeur par défaut

    # -----------------------------------------------------------------------
    # Cas A – forward (texte non vide)
    # -----------------------------------------------------------------------
    try:
        temp_dir = tempfile.TemporaryDirectory()
        os.environ["NEXUS_ETAT_DISJONCTEUR"] = str(Path(temp_dir.name) / "disjoncteur.json")
        os.environ["NEXUS_MAX_REPLIS_LOCAUX"] = "0"
        if hasattr(module.appeler, "_cache_plans"):
            module.appeler._cache_plans.clear()

        _faux_appeler.recorded = []
        _faux_appeler.scenario = "non_vide"

        # 1️⃣ Champ "sans_repli": true
        tache_a1 = {
            "nom": "tA1",
            "modele": "cloud1-cloud",
            "tache": "question",
            "sans_repli": True,
        }
        res_a1 = module.executer(tache_a1, "cle")
        if (
            isinstance(res_a1, dict)
            and res_a1.get("sans_repli") is True
            and len(_faux_appeler.recorded) == 1
        ):
            print("[OK  ] A forward (field) – appel unique, drapeau présent")
        else:
            print("[RATE] A forward (field) – résultat inattendu – appels :", len(_faux_appeler.recorded))
            return 1

        # 2️⃣ Variable d’environnement uniquement
        _faux_appeler.recorded = []
        os.environ["NEXUS_SANS_REPLI"] = "1"
        tache_a2 = {
            "nom": "tA2",
            "modele": "cloud1-cloud",
            "tache": "question",
        }
        res_a2 = module.executer(tache_a2, "cle")
        if (
            isinstance(res_a2, dict)
            and res_a2.get("sans_repli") is True
            and len(_faux_appeler.recorded) == 1
        ):
            print("[OK  ] A forward (env) – appel unique, drapeau présent")
        else:
            print("[RATE] A forward (env) – résultat inattendu – appels :", len(_faux_appeler.recorded))
            return 1
    finally:
        _restaurer_env(saved)
        temp_dir.cleanup()

    # -----------------------------------------------------------------------
    # Cas B – reverse (texte vide)
    # -----------------------------------------------------------------------
    try:
        temp_dir = tempfile.TemporaryDirectory()
        os.environ["NEXUS_ETAT_DISJONCTEUR"] = str(Path(temp_dir.name) / "disjoncteur.json")
        os.environ["NEXUS_MAX_REPLIS_LOCAUX"] = "0"
        if hasattr(module.appeler, "_cache_plans"):
            module.appeler._cache_plans.clear()

        _faux_appeler.recorded = []
        _faux_appeler.scenario = "vide"

        # 1️⃣ Champ "sans_repli": true
        tache_b1 = {
            "nom": "tB1",
            "modele": "cloud1-cloud",
            "tache": "question",
            "sans_repli": True,
        }
        res_b1 = module.executer(tache_b1, "cle")
        if (
            isinstance(res_b1, dict)
            and res_b1.get("sans_repli") is True
            and isinstance(res_b1.get("erreur"), str)
            and res_b1["erreur"].startswith("sans_repli :")
            and len(_faux_appeler.recorded) == 1
        ):
            print("[OK  ] B reverse (field) – texte vide, erreur sans_repli")
        else:
            print("[RATE] B reverse (field) – résultat inattendu – appels :", len(_faux_appeler.recorded))
            return 1

        # 2️⃣ Variable d’environnement uniquement
        _faux_appeler.recorded = []
        os.environ["NEXUS_SANS_REPLI"] = "1"
        tache_b2 = {
            "nom": "tB2",
            "modele": "cloud1-cloud",
            "tache": "question",
        }
        res_b2 = module.executer(tache_b2, "cle")
        if (
            isinstance(res_b2, dict)
            and res_b2.get("sans_repli") is True
            and isinstance(res_b2.get("erreur"), str)
            and res_b2["erreur"].startswith("sans_repli :")
            and len(_faux_appeler.recorded) == 1
        ):
            print("[OK  ] B reverse (env) – texte vide, erreur sans_repli")
        else:
            print("[RATE] B reverse (env) – résultat inattendu – appels :", len(_faux_appeler.recorded))
            return 1
    finally:
        _restaurer_env(saved)
        temp_dir.cleanup()

    # -----------------------------------------------------------------------
    # Cas C – fuite (exception réseau)
    # -----------------------------------------------------------------------
    try:
        temp_dir = tempfile.TemporaryDirectory()
        os.environ["NEXUS_ETAT_DISJONCTEUR"] = str(Path(temp_dir.name) / "disjoncteur.json")
        os.environ["NEXUS_MAX_REPLIS_LOCAUX"] = "0"
        if hasattr(module.appeler, "_cache_plans"):
            module.appeler._cache_plans.clear()

        _faux_appeler.recorded = []
        _faux_appeler.scenario = "exception"

        # Champ "sans_repli": true
        tache_c1 = {
            "nom": "tC1",
            "modele": "cloud1-cloud",
            "tache": "question",
            "sans_repli": True,
        }
        res_c1 = module.executer(tache_c1, "cle")
        if (
            isinstance(res_c1, dict)
            and res_c1.get("sans_repli") is True
            and isinstance(res_c1.get("erreur"), str)
            and res_c1["erreur"].startswith("sans_repli :")
            and len(_faux_appeler.recorded) == 1
        ):
            print("[OK  ] C fuite (field) – exception capturée, drapeau présent")
        else:
            print("[RATE] C fuite (field) – résultat inattendu – appels :", len(_faux_appeler.recorded))
            return 1

        # Variable d’environnement uniquement
        _faux_appeler.recorded = []
        os.environ["NEXUS_SANS_REPLI"] = "1"
        tache_c2 = {
            "nom": "tC2",
            "modele": "cloud1-cloud",
            "tache": "question",
        }
        res_c2 = module.executer(tache_c2, "cle")
        if (
            isinstance(res_c2, dict)
            and res_c2.get("sans_repli") is True
            and isinstance(res_c2.get("erreur"), str)
            and res_c2["erreur"].startswith("sans_repli :")
            and len(_faux_appeler.recorded) == 1
        ):
            print("[OK  ] C fuite (env) – exception capturée, drapeau présent")
        else:
            print("[RATE] C fuite (env) – résultat inattendu – appels :", len(_faux_appeler.recorded))
            return 1
    finally:
        _restaurer_env(saved)
        temp_dir.cleanup()

    # -----------------------------------------------------------------------
    # Cas D – témoin (pas de flag, texte non vide)
    # -----------------------------------------------------------------------
    try:
        temp_dir = tempfile.TemporaryDirectory()
        os.environ["NEXUS_ETAT_DISJONCTEUR"] = str(Path(temp_dir.name) / "disjoncteur.json")
        os.environ["NEXUS_MAX_REPLIS_LOCAUX"] = "0"
        if hasattr(module.appeler, "_cache_plans"):
            module.appeler._cache_plans.clear()

        _faux_appeler.recorded = []
        _faux_appeler.scenario = "non_vide"

        tache_d = {
            "nom": "tD",
            "modele": "cloud1-cloud",
            "tache": "question",
        }
        res_d = module.executer(tache_d, "cle")
        if (
            isinstance(res_d, dict)
            and "sans_repli" not in res_d
            and len(_faux_appeler.recorded) == 1
        ):
            print("[OK  ] D témoin – aucun drapeau, appel unique")
        else:
            print("[RATE] D témoin – résultat inattendu – appels :", len(_faux_appeler.recorded))
            return 1
    finally:
        _restaurer_env(saved)
        temp_dir.cleanup()

    return 0

if __name__ == "__main__":
    sys.exit(main())
