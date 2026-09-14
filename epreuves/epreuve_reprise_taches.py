# -*- coding: utf-8 -*-
"""
Epreuve du témoin de reprise sur les tâches cassées.

The test prints one line per case (1‑6) and a detection line (7).
It exits with code 1 if any case fails.
"""

import os
import sys
import io
import contextlib

# ----------------------------------------------------------------------
# Prepare import path (ROOT derived from this file)
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "scripts"))   # keep it in place

# ----------------------------------------------------------------------
# 0 – Silent import test
try:
    with contextlib.redirect_stdout(io.StringIO()) as buf:
        import nexus_reprise
    captured = buf.getvalue()
    if captured:
        raise RuntimeError("unexpected output during import")
except Exception as exc:                     # pragma: no cover
    print("[RATE] import : {}".format(exc))
    sys.exit(1)

# ----------------------------------------------------------------------
def verifier_cas(fn):
    """
    Apply the six test cases to the supplied function `fn`.
    Return a list of case identifiers (e.g. "cas 1") that failed.
    """
    failures = []

    # 1
    try:
        if fn("Ready", 0, True) != ("Ready", ""):
            failures.append("cas 1")
    except Exception:
        failures.append("cas 1")

    # 2
    try:
        r = fn("Ready", 2147942402, True)
        if not (r[0] == "CASSEE" and "0x80070002" in r[1]):
            failures.append("cas 2")
    except Exception:
        failures.append("cas 2")

    # 3
    try:
        if fn("Ready", "2147942402", True)[0] != "CASSEE":
            failures.append("cas 3")
    except Exception:
        failures.append("cas 3")

    # 4
    try:
        r = fn("Ready", 0, False)
        if not (r[0] == "CASSEE" and "introuvable" in r[1].lower()):
            failures.append("cas 4")
    except Exception:
        failures.append("cas 4")

    # 5
    try:
        if fn("Running", "abc", True) != ("Running", "") or fn("Ready", None, True) != ("Ready", ""):
            failures.append("cas 5")
    except Exception:
        failures.append("cas 5")

    # 6
    try:
        if fn("Ready", 1, True) != ("Ready", ""):
            failures.append("cas 6")
    except Exception:
        failures.append("cas 6")

    return failures

# ----------------------------------------------------------------------
def _print_result(case_id, is_ok):
    """Print a single result line."""
    status = "[OK  ]" if is_ok else "[RATE]"
    print("{} {}".format(status, case_id))

def main():
    rates = verifier_cas(nexus_reprise.etat_tache)

    # Cases 1‑6
    for i in range(1, 7):
        case_name = "cas {}".format(i)
        _print_result(case_name, case_name not in rates)

    # Case 7 – detection
    rates_faux = verifier_cas(lambda e, r, x: (e, ""))
    detection_ok = ("cas 2" in rates_faux) and ("cas 4" in rates_faux)
    _print_result("detection", detection_ok)

    # Exit code
    any_failure = bool(rates) or not detection_ok
    sys.exit(1 if any_failure else 0)

# ----------------------------------------------------------------------
if __name__ == "__main__":
    main()
