import sys, time, tempfile
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / 'scripts'))
import nexus_pouls as np

def _ok(nom, detail):
    print('[OK  ] %s : %s' % (nom, detail))

def _rate(nom, detail):
    print('[RATE] %s : %s' % (nom, detail))

def test_est_vivant():
    now = time.time()
    all_ok = True
    cas = [
        ({'timestamp': now}, True, 'fresh'),
        ({'timestamp': now - 100}, True, 'recent'),
        ({'timestamp': now - 1000}, False, 'old'),
        ({'timestamp': now + 50}, True, 'future'),
        (None, False, 'none'),
        ({}, False, 'no_timestamp'),
    ]
    for pouls, expected, label in cas:
        result = np.est_vivant(pouls, now, 900)
        if result == expected:
            _ok('est_vivant %s' % label, str(result))
        else:
            _rate('est_vivant %s' % label, 'expected %s got %s' % (expected, result))
            all_ok = False
    return all_ok

def test_cycle_battre_lire():
    all_ok = True
    with tempfile.TemporaryDirectory() as td:
        chemin = Path(td) / 'pouls.json'
        ok = np.battre(chemin, 'modele-test')
        if ok and chemin.is_file():
            _ok('battre', 'created')
        else:
            _rate('battre', 'failed or file missing')
            all_ok = False
        lu = np.lire(chemin)
        if isinstance(lu, dict) and 'timestamp' in lu:
            _ok('lire', 'dict')
        else:
            _rate('lire', 'did not return proper dict')
            all_ok = False
        if isinstance(lu, dict):
            if np.est_vivant(lu, time.time(), 900):
                _ok('est_vivant after battre', 'fresh')
            else:
                _rate('est_vivant after battre', 'expected True')
                all_ok = False
    return all_ok

def test_reverse_lire_absent():
    chemin = Path(tempfile.gettempdir()) / 'nonexistent_pouls_zzz.json'
    lu = np.lire(chemin)
    if lu is None:
        _ok('lire absent', 'none')
        return True
    _rate('lire absent', 'expected None')
    return False

def main():
    results = [
        test_est_vivant(),
        test_cycle_battre_lire(),
        test_reverse_lire_absent(),
    ]
    return 0 if all(results) else 1

if __name__ == '__main__':
    sys.exit(main())