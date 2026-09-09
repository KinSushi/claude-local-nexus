import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / 'outillage'))

import nexus_redaction as nr

def _run_subtest(name, func):
    try:
        func()
        print('[OK  ] %s : passed' % name)
        return True
    except AssertionError as e:
        print('[RATE] %s : %s' % (name, e))
        return False
    except Exception as e:
        print('[RATE] %s : unexpected exception %s' % (name, e))
        return False

def test_forward_valid_fenetre_and_json():
    original_argv = sys.argv[:]
    sys.argv = ['dummy', '--fenetre', '5', '--json']
    try:
        fenetre, json_out = nr.get_window_and_json()
        assert fenetre == 5, 'expected fenetre 5 got %s' % fenetre
        assert json_out is True, 'expected json_out True got %s' % json_out
    finally:
        sys.argv = original_argv

def test_forward_valid_fenetre_no_json():
    original_argv = sys.argv[:]
    sys.argv = ['dummy', '--fenetre', '10']
    try:
        fenetre, json_out = nr.get_window_and_json()
        assert fenetre == 10, 'expected fenetre 10 got %s' % fenetre
        assert json_out is False, 'expected json_out False got %s' % json_out
    finally:
        sys.argv = original_argv

def test_reverse_invalid_fenetre_value():
    original_argv = sys.argv[:]
    sys.argv = ['dummy', '--fenetre', 'abc']
    try:
        fenetre, json_out = nr.get_window_and_json()
        assert fenetre == 24, 'expected fallback fenetre 24 got %s' % fenetre
        assert json_out is False, 'expected json_out False got %s' % json_out
    finally:
        sys.argv = original_argv

def test_reverse_missing_fenetre_value():
    original_argv = sys.argv[:]
    sys.argv = ['dummy', '--fenetre']
    try:
        fenetre, json_out = nr.get_window_and_json()
        assert fenetre == 24, 'expected fallback fenetre 24 got %s' % fenetre
        assert json_out is False, 'expected json_out False got %s' % json_out
    finally:
        sys.argv = original_argv

def test_reverse_no_arguments():
    original_argv = sys.argv[:]
    sys.argv = ['dummy']
    try:
        fenetre, json_out = nr.get_window_and_json()
        assert fenetre == 24, 'expected default fenetre 24 got %s' % fenetre
        assert json_out is False, 'expected default json_out False got %s' % json_out
    finally:
        sys.argv = original_argv

def main():
    tests = [
        ('forward_valid_fenetre_and_json', test_forward_valid_fenetre_and_json),
        ('forward_valid_fenetre_no_json', test_forward_valid_fenetre_no_json),
        ('reverse_invalid_fenetre_value', test_reverse_invalid_fenetre_value),
        ('reverse_missing_fenetre_value', test_reverse_missing_fenetre_value),
        ('reverse_no_arguments', test_reverse_no_arguments),
    ]
    all_ok = True
    for name, func in tests:
        ok = _run_subtest(name, func)
        all_ok = all_ok and ok
    return 0 if all_ok else 1

if __name__ == '__main__':
    sys.exit(main())