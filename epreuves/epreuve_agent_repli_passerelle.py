#!/usr/bin/env python3
"""
Epreuve unitaire pour repli_passerelle_effectif.

Cas purs importes du vrai module.
"""

import os
import sys

# Importer le module depuis le dossier scripts
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

from nexus_agent import repli_passerelle_effectif


def test_repli_passerelle_effectif():
    """6 cas purs : True, true, 1, 0, absent, entetes None."""
    cas = [
        ({"x-litellm-attempted-fallbacks": "1"}, True, "True pour '1'"),
        ({"x-litellm-attempted-fallbacks": "true"}, True, "True pour 'true'"),
        ({"x-litellm-attempted-fallbacks": "True"}, True, "True pour 'True'"),
        ({"x-litellm-attempted-fallbacks": "0"}, False, "False pour '0'"),
        ({"x-litellm-attempted-fallbacks": ""}, False, "False pour vide"),
        ({}, None, "None si absent"),
        (None, None, "None si entetes None"),
    ]

    for entetes, attendu, message in cas:
        obtenu = repli_passerelle_effectif(entetes)
        assert obtenu == attendu, f"{message} : attendu {attendu}, obtenu {obtenu}"

    print("[OK] Tous les cas passent")

if __name__ == "__main__":
    test_repli_passerelle_effectif()
    sys.exit(0)
