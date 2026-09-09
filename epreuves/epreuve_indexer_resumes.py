"""Epreuve de nexus_indexer_resumes : _slugify, avec sa troncature a 50."""
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / 'outillage'))
import nexus_indexer_resumes


def test_slugify_forward():
    ok = True
    cases = [
        ("  Hello, World!  ", "hello_world"),
        ("A" * 60, "a" * 50),
    ]
    for inp, exp in cases:
        try:
            got = nexus_indexer_resumes._slugify(inp)
            if got != exp:
                print("[RATE] slugify forward : %r -> %r attendu %r" % (inp, got, exp))
                ok = False
        except Exception as e:
            print("[RATE] slugify forward : exception %s sur %r" % (e, inp))
            ok = False
    if ok:
        print("[OK  ] slugify forward : ponctuation et blancs effaces, troncature a 50")
    return ok


def test_slugify_reverse():
    ok = True
    bad_inputs = [None, 123, 45.6]
    for inp in bad_inputs:
        try:
            nexus_indexer_resumes._slugify(inp)
            print("[RATE] slugify reverse : aucune exception sur %r" % (inp,))
            ok = False
        except Exception:
            pass
    if ok:
        print("[OK  ] slugify reverse : None, entier et flottant levent une exception")
    return ok


def main():
    results = [test_slugify_forward(), test_slugify_reverse()]
    return 0 if all(results) else 1


if __name__ == '__main__':
    sys.exit(main())