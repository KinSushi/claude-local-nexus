import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / 'outillage'))
import nexus_loi1


def test_is_delegated_forward():
    result = nexus_loi1._is_delegated("hello", ["some text", "greeting hello world"])
    if result is True:
        print('[OK  ] _is_delegated_forward : ligne presente dans une trace')
        return True
    print('[RATE] _is_delegated_forward : attendu True obtenu %s' % result)
    return False


def test_is_delegated_absente():
    result = nexus_loi1._is_delegated("absent", ["some text", "other"])
    if result is False:
        print('[OK  ] _is_delegated_absente : ligne absente de toute trace')
        return True
    print('[RATE] _is_delegated_absente : attendu False obtenu %s' % result)
    return False


def test_is_delegated_reverse():
    try:
        nexus_loi1._is_delegated("test", None)
    except Exception as e:
        print('[OK  ] _is_delegated_reverse : traces None leve %s' % type(e).__name__)
        return True
    print('[RATE] _is_delegated_reverse : aucune exception sur traces None')
    return False


def main():
    resultats = [test_is_delegated_forward(), test_is_delegated_absente(), test_is_delegated_reverse()]
    return 0 if all(resultats) else 1


if __name__ == '__main__':
    sys.exit(main())