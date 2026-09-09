"""Epreuve de nexus_checklist_progres : lire_regressions, la seule fonction pure."""
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / 'outillage'))
import nexus_checklist_progres


def test_lire_regressions_forward():
    try:
        input_str = "Cablage : 5 REGRESSION(s) detected"
        result = nexus_checklist_progres.lire_regressions(input_str)
        if result == 5:
            print('[OK  ] lire_regressions forward : %r -> %r' % (input_str, result))
            return True
        print('[RATE] lire_regressions forward : %r -> %r (attendu 5)' % (input_str, result))
        return False
    except Exception as e:
        print('[RATE] lire_regressions forward : exception %s' % e)
        return False


def test_lire_regressions_aucune():
    try:
        input_str = "Aucune regression detectee -- juge par le banc"
        result = nexus_checklist_progres.lire_regressions(input_str)
        if result == 0:
            print('[OK  ] lire_regressions aucune : %r -> 0' % input_str)
            return True
        print('[RATE] lire_regressions aucune : %r -> %r (attendu 0)' % (input_str, result))
        return False
    except Exception as e:
        print('[RATE] lire_regressions aucune : exception %s' % e)
        return False


def test_lire_regressions_reverse():
    try:
        input_str = "unexpected output without numbers"
        result = nexus_checklist_progres.lire_regressions(input_str)
        if result == "inconnu":
            print('[OK  ] lire_regressions reverse : %r -> %r' % (input_str, result))
            return True
        print('[RATE] lire_regressions reverse : %r -> %r (attendu inconnu)' % (input_str, result))
        return False
    except Exception as e:
        print('[RATE] lire_regressions reverse : exception %s' % e)
        return False


def main():
    results = [
        test_lire_regressions_forward(),
        test_lire_regressions_aucune(),
        test_lire_regressions_reverse(),
    ]
    return 0 if all(results) else 1


if __name__ == '__main__':
    sys.exit(main())