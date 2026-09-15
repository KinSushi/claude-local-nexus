import sys
import os
import tempfile
import shutil
from pathlib import Path
import importlib.util

# ----------------------------------------------------------------------
# Load the module "nexus_disjoncteur" from the repository root
# ----------------------------------------------------------------------
RACINE = Path(__file__).resolve().parent.parent
MODULE_PATH = RACINE / "scripts" / "nexus_disjoncteur.py"

spec = importlib.util.spec_from_file_location("nexus_disjoncteur", str(MODULE_PATH))
nd = importlib.util.module_from_spec(spec)
spec.loader.exec_module(nd)

# ----------------------------------------------------------------------
# Helper to print test result in the same style as epreuve_disjoncteur.py
# ----------------------------------------------------------------------
def _print_ok(name):
    print(f"[OK  ] {name}")

def _print_rate(name, msg):
    print(f"[RATE] {name} : {msg}")

# ----------------------------------------------------------------------
# Forward / reverse tests for echec_transitoire
# ----------------------------------------------------------------------
def _run_F1_forward():
    try:
        msg = "<urlopen error [WinError 10061] Aucune connexion n'a pu etre etablie car l'ordinateur cible l'a expressement refusee>"
        result = nd.echec_transitoire(msg)
        if result is True:
            _print_ok("echec_transitoire_F1_forward")
            return True
        return _print_rate("echec_transitoire_F1_forward", "expected True, got False") or False
    except Exception as e:
        return _print_rate("echec_transitoire_F1_forward", f"raised unexpected exception {e}") or False

def _run_F2_forward():
    try:
        msg = "reponse vide (8840 jetons consommes)"
        result = nd.echec_transitoire(msg)
        if result is True:
            _print_ok("echec_transitoire_F2_forward")
            return True
        return _print_rate("echec_transitoire_F2_forward", "expected True, got False") or False
    except Exception as e:
        return _print_rate("echec_transitoire_F2_forward", f"raised unexpected exception {e}") or False

def _run_F3_forward():
    try:
        msg = "HTTP 429 : too many concurrent requests"
        result = nd.echec_transitoire(msg)
        if result is True:
            _print_ok("echec_transitoire_F3_forward")
            return True
        return _print_rate("echec_transitoire_F3_forward", "expected True, got False") or False
    except Exception as e:
        return _print_rate("echec_transitoire_F3_forward", f"raised unexpected exception {e}") or False

def _run_R1_reverse():
    try:
        result = nd.echec_transitoire("Invalid model name")
        if result is False:
            _print_ok("echec_transitoire_R1_reverse")
            return True
        return _print_rate("echec_transitoire_R1_reverse", "expected False, got True") or False
    except Exception as e:
        return _print_rate("echec_transitoire_R1_reverse", f"raised unexpected exception {e}") or False

def _run_R2_reverse():
    try:
        result = nd.echec_transitoire("HTTP 404 : model not found")
        if result is False:
            _print_ok("echec_transitoire_R2_reverse")
            return True
        return _print_rate("echec_transitoire_R2_reverse", "expected False, got True") or False
    except Exception as e:
        return _print_rate("echec_transitoire_R2_reverse", f"raised unexpected exception {e}") or False

# ----------------------------------------------------------------------
# Isolation test (I1) – temporary directory via env var
# ----------------------------------------------------------------------
def _run_I1_isolation():
    original_env = os.environ.get("NEXUS_ETAT_DISJONCTEUR")
    temp_dir = tempfile.mkdtemp()
    os.environ["NEXUS_ETAT_DISJONCTEUR"] = os.path.join(temp_dir, "disjoncteur.json")
    try:
        # Verify that _state_path returns the exact path we set
        expected_state = os.path.join(temp_dir, "disjoncteur.json")
        state_path = nd._state_path()
        if state_path != expected_state:
            return _print_rate(
                "I1_isolation_state_path",
                f"expected {expected_state!r}, got {state_path!r}"
            ) or False

        # Record a permanent failure – should create the state and journal files
        cb = nd.CircuitBreaker(3, 300)
        cb.record_failure("cible-epreuve", "Invalid model name")

        expected_journal = os.path.join(temp_dir, "circuit_journal.jsonl")
        if not (os.path.isfile(expected_state) and os.path.isfile(expected_journal)):
            missing = []
            if not os.path.isfile(expected_state):
                missing.append("disjoncteur.json")
            if not os.path.isfile(expected_journal):
                missing.append("circuit_journal.jsonl")
            return _print_rate(
                "I1_isolation_files",
                f"missing files: {', '.join(missing)}"
            ) or False

        _print_ok("I1_isolation")
        return True
    except Exception as e:
        return _print_rate("I1_isolation", f"raised unexpected exception {e}") or False
    finally:
        # Restore original environment and clean temporary directory
        if original_env is None:
            os.environ.pop("NEXUS_ETAT_DISJONCTEUR", None)
        else:
            os.environ["NEXUS_ETAT_DISJONCTEUR"] = original_env
        shutil.rmtree(temp_dir, ignore_errors=True)

# ----------------------------------------------------------------------
# Default path test (I2) – env var removed
# ----------------------------------------------------------------------
def _run_I2_default():
    # Ensure the variable is not set
    removed = os.environ.pop("NEXUS_ETAT_DISJONCTEUR", None)
    try:
        state_path = nd._state_path()
        expected_suffix = os.path.join(".nexus", "circuit_state.json")
        if not state_path.endswith(expected_suffix):
            return _print_rate(
                "I2_default",
                f"expected path to end with {expected_suffix!r}, got {state_path!r}"
            ) or False
        _print_ok("I2_default")
        return True
    except Exception as e:
        return _print_rate("I2_default", f"raised unexpected exception {e}") or False
    finally:
        # Restore the variable if it existed before
        if removed is not None:
            os.environ["NEXUS_ETAT_DISJONCTEUR"] = removed

# ----------------------------------------------------------------------
# Main driver – run all tests and exit with appropriate status
# ----------------------------------------------------------------------
def main():
    tests = [
        _run_F1_forward,
        _run_F2_forward,
        _run_F3_forward,
        _run_R1_reverse,
        _run_R2_reverse,
        _run_I1_isolation,
        _run_I2_default,
    ]
    all_ok = True
    for test in tests:
        if not test():
            all_ok = False
    return 0 if all_ok else 1

if __name__ == "__main__":
    sys.exit(main())
