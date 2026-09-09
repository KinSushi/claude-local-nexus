import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / 'outillage'))
import nexus_livres


def _cas(nom, obtenu, attendu):
    if obtenu == attendu:
        print('[OK  ] %s : %r' % (nom, obtenu))
        return True
    print('[RATE] %s : attendu %r obtenu %r' % (nom, attendu, obtenu))
    return False


def test_format_fragment_forward():
    r = []
    r.append(_cas('format_fragment texte', nexus_livres._format_fragment({"texte": "Hello world"}),
                  ("Hello world", ["texte"])))
    r.append(_cas('format_fragment code (signature + implementation)',
                  nexus_livres._format_fragment({"signature": "def foo()", "implementation": "return 42"}),
                  ("def foo()\n\nreturn 42", ["signature", "implementation"])))
    return all(r)


def test_format_fragment_reverse():
    r = []
    r.append(_cas('format_fragment sans cle utile', nexus_livres._format_fragment({"other": "value"}), (None, [])))
    r.append(_cas('format_fragment cles code toutes vides',
                  nexus_livres._format_fragment({"signature": "", "docstring_brut": "", "implementation": ""}),
                  (None, ["signature", "docstring_brut", "implementation"])))
    return all(r)


def test_score_entry_forward():
    row = {"id": "AlphaBeta", "resume": "This is a test resume", "type": "module"}
    r = []
    r.append(_cas('score_entry un terme dans id (x3)', nexus_livres._score_entry(row, ["alpha"]), (True, 3)))
    r.append(_cas('score_entry deux termes', nexus_livres._score_entry(row, ["alpha", "test"]), (True, 4)))
    return all(r)


def test_score_entry_reverse():
    row = {"id": "Gamma", "resume": "No matching terms here", "type": "class"}
    r = []
    r.append(_cas('score_entry terme absent', nexus_livres._score_entry(row, ["delta"]), (False, 0)))
    r.append(_cas('score_entry requete vide', nexus_livres._score_entry(row, []), (True, 1)))
    return all(r)


def main():
    results = [
        test_format_fragment_forward(),
        test_format_fragment_reverse(),
        test_score_entry_forward(),
        test_score_entry_reverse(),
    ]
    return 0 if all(results) else 1


if __name__ == '__main__':
    sys.exit(main())