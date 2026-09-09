"""Epreuve de nexus_migration_plan : _extract_size, la fonction pure du plan."""
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / 'outillage'))
import nexus_migration_plan


def test_extract_size_forward():
    cases = [
        ("4.7 GB", "4.7GB"),
        ("123KB", "123KB"),
        ("0.5 MB", "0.5MB"),
        ("1,2TB", "1,2TB"),
    ]
    for inp, exp in cases:
        got = nexus_migration_plan._extract_size(inp)
        if got != exp:
            print('[RATE] extract_size forward : %r attendu %r rendu %r' % (inp, exp, got))
            return False
    print('[OK  ] extract_size forward : %d formes de taille normalisees' % len(cases))
    return True


def test_extract_size_reverse():
    cases = ["no size", "", "abc123", "GB", " "]
    for inp in cases:
        got = nexus_migration_plan._extract_size(inp)
        if got is not None:
            print('[RATE] extract_size reverse : %r attendu None rendu %r' % (inp, got))
            return False
    print('[OK  ] extract_size reverse : %d entrees sans taille -> None' % len(cases))
    return True


def main():
    results = [test_extract_size_forward(), test_extract_size_reverse()]
    return 0 if all(results) else 1


if __name__ == '__main__':
    sys.exit(main())