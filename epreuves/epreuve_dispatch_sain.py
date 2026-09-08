#!/usr/bin/env python3
# -*- coding: ascii -*-

import sys
import re
from pathlib import Path

# ------------------------------------------------------------
# Portable setup
# ------------------------------------------------------------
RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / 'outillage'))

try:
    import nexus_test
except Exception as e:
    print(f"[RATE] setup : impossible d'importer nexus_test ({e})")
    sys.exit(1)

# ------------------------------------------------------------
def _print_result(success: bool, name: str, detail: str) -> None:
    """Print a result line respecting the required format."""
    tag = "OK  " if success else "RATE"
    print(f"[{tag}] {name} : {detail}")

# ------------------------------------------------------------
def _case_detection() -> bool:
    """
    Negative case: ensure that a missing dispatch file is counted as a FAIL.
    Returns True if the case succeeds, False otherwise.
    """
    initial_failed = len(nexus_test.FAILED)
    initial_skipped = len(nexus_test.SKIPPED)

    # The called function prints its own line; we just observe the counters.
    nexus_test.jouer_epreuve_python(
        'epreuve_temoin_absente_zzz.py',
        'temoin dispatch absent'
    )

    final_failed = len(nexus_test.FAILED)
    final_skipped = len(nexus_test.SKIPPED)

    delta_failed = final_failed - initial_failed
    delta_skipped = final_skipped - initial_skipped

    success = (delta_failed == 1) and (delta_skipped == 0)
    detail = f"FAILED +{delta_failed}, SKIPPED +{delta_skipped}"
    _print_result(success, "DETECTION", detail)
    return success

# ------------------------------------------------------------
def _case_etat() -> bool:
    """
    Verify that every file referenced in nexus_test.jouer_epreuve_python(...)
    exists in the 'epreuves' directory.
    Returns True if all referenced files exist, False otherwise.
    """
    nexus_path = RACINE / 'outillage' / 'nexus_test.py'
    try:
        source = nexus_path.read_text(encoding='utf-8')
    except Exception as e:
        _print_result(False, "ETAT", f"impossible de lire nexus_test.py ({e})")
        return False

    # Regex to capture the first argument of jouer_epreuve_python("...py")
    pattern = re.compile(
        r'''jouer_epreuve_python\(\s*["']([^"']+\.py)["']\s*,'''
    )
    matches = pattern.findall(source)

    total = len(matches)
    missing = []

    epreuves_dir = RACINE / 'epreuves'

    for filename in matches:
        candidate = epreuves_dir / filename
        if not candidate.is_file():
            missing.append(filename)

    missing_count = len(missing)
    success = missing_count == 0

    if success:
        detail = f"{total} cablees, 0 introuvable"
    else:
        missing_list = ", ".join(missing)
        detail = f"{total} cablees, {missing_count} introuvable: {missing_list}"

    _print_result(success, "ETAT", detail)
    return success

# ------------------------------------------------------------
if __name__ == '__main__':
    all_success = True

    # Case 1 : Detection
    if not _case_detection():
        all_success = False

    # Case 2 : Etat
    if not _case_etat():
        all_success = False

    sys.exit(0 if all_success else 1)