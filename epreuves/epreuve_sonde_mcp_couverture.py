# -*- coding: utf-8 -*-
"""Epreuve autonome vérifiant la fonction pure _agreger de outillage/nexus_mcp_probe.py."""

import os
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def _dire(ok, nom, detail):
    print("%s %s : %s" % ("[OK  ]" if ok else "[RATE]", nom, detail))
    return ok

def _import_agreger():
    try:
        if RACINE not in sys.path:
            sys.path.insert(0, RACINE)
        from outillage.nexus_mcp_probe import _agreger
        return _agreger, None
    except Exception as e:
        return None, str(e)

def main():
    code = 0

    _agreger, err = _import_agreger()
    if _agreger is None:
        _dire(False, "import", f"import : {err}")
        return 1

    # Cas 1 : tous vrais -> 0
    cas1 = [("a", True), ("b", True)]
    res1 = _agreger(cas1)
    ok1 = (res1 == 0)
    if not _dire(ok1, "cas 1", f"attendu 0, obtenu {res1}"):
        code = 1

    # Cas 2 : un faux -> 1
    cas2 = [("a", True), ("b", False)]
    res2 = _agreger(cas2)
    ok2 = (res2 == 1)
    if not _dire(ok2, "cas 2", f"attendu 1, obtenu {res2}"):
        code = 1

    # Cas 3 : liste vide -> 1
    cas3 = []
    res3 = _agreger(cas3)
    ok3 = (res3 == 1)
    if not _dire(ok3, "cas 3", f"attendu 1, obtenu {res3}"):
        code = 1

    return code

if __name__ == "__main__":
    sys.exit(main())
