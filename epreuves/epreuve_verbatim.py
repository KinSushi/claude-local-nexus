import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / 'outillage'))
from nexus_verbatim import _nom_sur


def _cas(name, entree, expected):
    try:
        result = _nom_sur(entree)
    except Exception as e:
        print("[RATE] %s : exception %s" % (name, e))
        return False
    if result == expected:
        print("[OK  ] %s : %r -> %r" % (name, entree, result))
        return True
    print("[RATE] %s : got %s expected %s" % (name, result, expected))
    return False


def main():
    all_ok = True
    all_ok = _cas('nom_sur_forward', "model-1.2_ABC", "model-1.2_ABC") and all_ok
    all_ok = _cas('nom_sur_none', None, "inconnu") and all_ok
    all_ok = _cas('nom_sur_traversee', "bad/../model", "bad_.._model") and all_ok
    all_ok = _cas('nom_sur_separateurs', "a\\b:c d", "a_b_c_d") and all_ok
    return 0 if all_ok else 1


if __name__ == '__main__':
    sys.exit(main())