#!/usr/bin/env python3
"""
Épreuve unitaire pour la détection du quota cloud épuisé dans nexus_agent.py.
Cas forward, reverse et fuite.
"""

import io
import os
import sys
import tempfile
import urllib.error
from pathlib import Path
import importlib.util

def faux_appeler(candidat, messages, plafond, cle, temperature):
    faux_appeler.recorded.append(candidat)
    corps = faux_appeler.corps_erreur
    raise urllib.error.HTTPError(
        "http://factice", 429, "Too Many Requests", None, io.BytesIO(corps.encode())
    )

def main():
    racine = Path(__file__).parent.parent
    sys.path.insert(0, str(racine / "scripts"))

    # Environnement propre
    etat_disjoncteur = os.environ.get("NEXUS_ETAT_DISJONCTEUR")
    max_replis = os.environ.get("NEXUS_MAX_REPLIS_LOCAUX")
    temp_dir = tempfile.TemporaryDirectory()
    os.environ["NEXUS_ETAT_DISJONCTEUR"] = str(Path(temp_dir.name) / "disjoncteur.json")
    os.environ["NEXUS_MAX_REPLIS_LOCAUX"] = "0"

    # Chargement du module
    spec = importlib.util.spec_from_file_location(
        "nexus_agent", racine / "scripts" / "nexus_agent.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    # Faux pour les tests
    module.replis_gratuits = lambda cle: ["cloud2-cloud", "local1-local"]
    module.poids_et_libre = lambda c: (None, None)
    module.memoire_suffisante = lambda p, l: True
    module.appeler = faux_appeler
    module.appeler.recorded = []
    module.appeler._cache_plans = {
        "cloud1-cloud": "cloud",
        "cloud2-cloud": "cloud",
        "local1-local": "local"
    }

    tache = {
        "nom": "t",
        "modele": "cloud1-cloud",
        "tache": "Reponds OK",
        "max_tokens": 16
    }

    def restaurer():
        if etat_disjoncteur is not None:
            os.environ["NEXUS_ETAT_DISJONCTEUR"] = etat_disjoncteur
        else:
            os.environ.pop("NEXUS_ETAT_DISJONCTEUR", None)
        if max_replis is not None:
            os.environ["NEXUS_MAX_REPLIS_LOCAUX"] = max_replis
        else:
            os.environ.pop("NEXUS_MAX_REPLIS_LOCAUX", None)
        temp_dir.cleanup()

    # Cas forward
    try:
        module.QUOTA_CLOUD_EPUISE = None
        faux_appeler.recorded = []
        faux_appeler.corps_erreur = '{"error": "you have reached your session usage limit"}'
        module.executer(tache, "cle-factice")
        cloud_alias = [a for a in faux_appeler.recorded if a.endswith("-cloud")]
        if cloud_alias == ["cloud1-cloud"] and isinstance(module.QUOTA_CLOUD_EPUISE, dict) and "usage limit" in module.QUOTA_CLOUD_EPUISE.get("message", ""):
            print("[OK  ] forward : quota cloud détecté et mémorisé")
        else:
            print(f"[RATE] forward : alias={cloud_alias}, quota={module.QUOTA_CLOUD_EPUISE}")
            return 1
    except Exception as e:
        print(f"[RATE] forward : exception {e}")
        return 1
    finally:
        restaurer()

    # Cas reverse
    try:
        module.QUOTA_CLOUD_EPUISE = None
        faux_appeler.recorded = []
        faux_appeler.corps_erreur = '{"error": "too many concurrent requests"}'
        module.executer(tache, "cle-factice")
        cloud_alias = [a for a in faux_appeler.recorded if a.endswith("-cloud")]
        if cloud_alias == ["cloud1-cloud", "cloud2-cloud"] and module.QUOTA_CLOUD_EPUISE is None:
            print("[OK  ] reverse : quota non détecté, replis tentés")
        else:
            print(f"[RATE] reverse : alias={cloud_alias}, quota={module.QUOTA_CLOUD_EPUISE}")
            return 1
    except Exception as e:
        print(f"[RATE] reverse : exception {e}")
        return 1
    finally:
        restaurer()

    # Cas fuite
    try:
        module.QUOTA_CLOUD_EPUISE = {"depuis": "t", "message": "usage limit"}
        faux_appeler.recorded = []
        module.executer(tache, "cle-factice")
        cloud_alias = [a for a in faux_appeler.recorded if a.endswith("-cloud")]
        if not cloud_alias:
            print("[OK  ] fuite : aucun alias cloud tenté après détection")
        else:
            print(f"[RATE] fuite : alias={cloud_alias}")
            return 1
    except Exception as e:
        print(f"[RATE] fuite : exception {e}")
        return 1
    finally:
        restaurer()

    return 0

if __name__ == "__main__":
    sys.exit(main())
