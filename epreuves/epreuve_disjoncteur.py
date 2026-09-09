import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / 'outillage'))

import nexus_disjoncteur as nd


def _run_forward_state_path():
    try:
        result = nd._state_path()
        expected = str(Path(nd.__file__).resolve().parent.parent / ".nexus" / "circuit_state.json")
        if result == expected:
            print('[OK  ] _state_path_forward : returned expected path')
            return True
        print('[RATE] _state_path_forward : expected %r, got %r' % (expected, result))
        return False
    except Exception as e:
        print('[RATE] _state_path_forward : raised unexpected exception %s' % e)
        return False

def _run_reverse_state_path():
    try:
        nd._state_path(123)
        print('[RATE] _state_path_reverse : did not raise TypeError on extra argument')
        return False
    except TypeError:
        print('[OK  ] _state_path_reverse : raised TypeError as expected')
        return True
    except Exception as e:
        print('[RATE] _state_path_reverse : raised unexpected exception %s' % e)
        return False

def _run_forward_echec_transitoire():
    try:
        msg = "Server responded with HTTP 503 Service Unavailable"
        result = nd.echec_transitoire(msg)
        if result is True:
            print('[OK  ] echec_transitoire_forward : detected transient failure')
            return True
        print('[RATE] echec_transitoire_forward : expected True, got False')
        return False
    except Exception as e:
        print('[RATE] echec_transitoire_forward : raised unexpected exception %s' % e)
        return False

def _run_reverse_echec_transitoire():
    try:
        result = nd.echec_transitoire(42)
        if result is False:
            print('[OK  ] echec_transitoire_reverse : non-string input returns False')
            return True
        print('[RATE] echec_transitoire_reverse : expected False for non-string, got True')
        return False
    except Exception as e:
        print('[RATE] echec_transitoire_reverse : raised unexpected exception %s' % e)
        return False

def main():
    tests = [
        _run_forward_state_path,
        _run_reverse_state_path,
        _run_forward_echec_transitoire,
        _run_reverse_echec_transitoire,
    ]
    all_ok = True
    for test in tests:
        if not test():
            all_ok = False
    return 0 if all_ok else 1

if __name__ == '__main__':
    sys.exit(main())