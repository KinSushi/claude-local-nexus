import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / 'outillage'))
import nexus_rebasement


def _cas(nom, obtenu, attendu):
    if obtenu == attendu:
        print('[OK  ] %s : %s' % (nom, attendu))
        return True
    print('[RATE] %s : attendu %s obtenu %s' % (nom, attendu, obtenu))
    return False


def test_classify_rule_forward():
    c = nexus_rebasement._classify_rule
    r = []
    r.append(_cas('classify REGRESSION (old > ref)', c('F823', {'F823': 1}, {'F823': 2}, {'F823': 2}), 'REGRESSION'))
    r.append(_cas('classify ATTRIBUABLE (new > ref, old == ref)', c('B009', {'B009': 2}, {'B009': 2}, {'B009': 3}), 'ATTRIBUABLE'))
    r.append(_cas('classify IMPROVEMENT (old < ref)', c('C001', {'C001': 5}, {'C001': 3}, {'C001': 3}), 'IMPROVEMENT'))
    r.append(_cas('classify UNCHANGED (tout a zero)', c('D123', {}, {}, {}), 'UNCHANGED'))
    return all(r)


def test_classify_rule_reverse():
    try:
        nexus_rebasement._classify_rule('X', [], [], [])
    except Exception as e:
        print('[OK  ] classify reverse : des listes a la place des dicts levent %s' % type(e).__name__)
        return True
    print('[RATE] classify reverse : aucune exception')
    return False


def test_compare_counts_forward():
    verdicts = nexus_rebasement._compare_counts({'A': 1, 'B': 0}, {'A': 2}, {'B': 3})
    return _cas('compare_counts mapping', verdicts, {'A': 'REGRESSION', 'B': 'ATTRIBUABLE'})


def test_compare_counts_reverse():
    try:
        nexus_rebasement._compare_counts(None, {}, {})
    except Exception as e:
        print('[OK  ] compare_counts reverse : reference None leve %s' % type(e).__name__)
        return True
    print('[RATE] compare_counts reverse : aucune exception')
    return False


def main():
    resultats = [
        test_classify_rule_forward(),
        test_classify_rule_reverse(),
        test_compare_counts_forward(),
        test_compare_counts_reverse(),
    ]
    return 0 if all(resultats) else 1


if __name__ == '__main__':
    sys.exit(main())