import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / 'scripts'))
import nexus_pull_garde as npg


def test_decision_forward():
    orig = npg.capability.can_download
    npg.capability.can_download = lambda size, profile: (True, "ok")
    try:
        etat, autorise, motif = npg.decision(1.0, npg._profil_test())
    finally:
        npg.capability.can_download = orig
    if etat == npg._ACCEPTED and autorise is True and motif == "ok":
        print('[OK  ] decision_forward : accepted (%s)' % etat)
        return True
    print('[RATE] decision_forward : unexpected (%r, %r, %r)' % (etat, autorise, motif))
    return False


def test_decision_reverse_none():
    etat, autorise, motif = npg.decision(None, npg._profil_test())
    expected = "poids inconnu – décision indéterminée"
    if etat == npg._UNKNOWN and autorise is None and motif == expected:
        print('[OK  ] decision_reverse_none : poids None -> %s' % etat)
        return True
    print('[RATE] decision_reverse_none : unexpected (%r, %r, %r)' % (etat, autorise, motif))
    return False


def test_profil_test_forward():
    expected = {
        "disque_mesure": True,
        "free_disk_gb": 1000.0,
        "runnable_budget_gb": 100.0,
        "pool_budget_gb": 200.0,
        "inference_memory_gb": 200.0,
    }
    result = npg._profil_test()
    if result == expected:
        print('[OK  ] profil_test_forward : profil factice attendu')
        return True
    print('[RATE] profil_test_forward : mismatch %r' % (result,))
    return False


def test_profil_test_reverse_args():
    try:
        npg._profil_test(1)
    except TypeError:
        print('[OK  ] profil_test_reverse_args : raised TypeError')
        return True
    print('[RATE] profil_test_reverse_args : no exception')
    return False


def main():
    results = [
        test_decision_forward(),
        test_decision_reverse_none(),
        test_profil_test_forward(),
        test_profil_test_reverse_args(),
    ]
    return 0 if all(results) else 1


if __name__ == '__main__':
    sys.exit(main())