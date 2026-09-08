# -*- coding: utf-8 -*-
"""Epreuve autonome vérifiant la fonction pure _selectionner_top de scripts/nexus_livres_semantique.py."""

import os
import sys
import traceback

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def _dire(ok, nom, detail):
    print("%s %s : %s" % ("[OK  ]" if ok else "[RATE]", nom, detail))
    return ok

def _import_selectionner_top():
    try:
        if RACINE not in sys.path:
            sys.path.insert(0, RACINE)
        from scripts.nexus_livres_semantique import _selectionner_top
        return _selectionner_top, None
    except Exception as e:
        return None, str(e)

def main():
    code = 0

    _selectionner_top, err = _import_selectionner_top()
    if _selectionner_top is None:
        _dire(False, "import", f"import : {err}")
        return 1

    # Cas 1 : scores égaux ne doivent pas lever d'exception et retourner 2 couples
    try:
        r1 = _selectionner_top(
            [(0.5, {"id": "a"}), (0.5, {"id": "b"}), (0.5, {"id": "c"})],
            2
        )
        ok1 = isinstance(r1, list) and len(r1) == 2
    except Exception:
        ok1 = False
        r1 = None
        err1 = traceback.format_exc().strip()
    if not _dire(ok1, "cas 1", f"attendu 2 éléments, obtenu {r1 if ok1 else err1}"):
        code = 1

    # Cas 2 : scores distincts, ordre décroissant
    try:
        r2 = _selectionner_top(
            [(0.1, {"id": "a"}), (0.9, {"id": "b"}), (0.5, {"id": "c"})],
            2
        )
        attendu2 = [(0.9, {"id": "b"}), (0.5, {"id": "c"})]
        ok2 = r2 == attendu2
    except Exception:
        ok2 = False
        r2 = None
        err2 = traceback.format_exc().strip()
    if not _dire(ok2, "cas 2", f"attendu {attendu2}, obtenu {r2 if ok2 else err2}"):
        code = 1

    # Cas 3 : top_n supérieur au nombre d'éléments
    try:
        r3 = _selectionner_top(
            [(0.2, {"id": "x"})],
            5
        )
        ok3 = isinstance(r3, list) and len(r3) == 1
    except Exception:
        ok3 = False
        r3 = None
        err3 = traceback.format_exc().strip()
    if not _dire(ok3, "cas 3", f"attendu 1 élément, obtenu {r3 if ok3 else err3}"):
        code = 1

    # Cas 4 : iterable vide
    try:
        r4 = _selectionner_top([], 3)
        ok4 = isinstance(r4, list) and len(r4) == 0
    except Exception:
        ok4 = False
        r4 = None
        err4 = traceback.format_exc().strip()
    if not _dire(ok4, "cas 4", f"attendu [], obtenu {r4 if ok4 else err4}"):
        code = 1

    return code

if __name__ == "__main__":
    sys.exit(main())
