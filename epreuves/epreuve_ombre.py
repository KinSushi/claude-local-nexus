"""Epreuve de nexus_ombre : les quatre fonctions pures du simulateur.

Les marqueurs sont construits par concatenation, jamais ecrits en litteral :
un litteral casserait l'outil qui installe cette epreuve.
"""
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / 'outillage'))
import nexus_ombre


def _mk(word):
    return "<" * 3 + word + ">" * 3


def test_build_marker():
    ok = True
    try:
        res = nexus_ombre.build_marker("TEST")
        if res == _mk("TEST"):
            print('[OK  ] build_marker forward : TEST encadre par les chevrons')
        else:
            print('[RATE] build_marker forward : rendu %r' % res)
            ok = False
    except Exception as e:
        print('[RATE] build_marker forward : exception %s' % e)
        ok = False
    # REVERSE : None n'est PAS rejete, il est rendu tel quel (mesure, pas suppose)
    try:
        res = nexus_ombre.build_marker(None)
        if res == _mk("None"):
            print('[OK  ] build_marker reverse : None rendu litteralement, sans exception')
        else:
            print('[RATE] build_marker reverse : rendu %r' % res)
            ok = False
    except Exception as e:
        print('[RATE] build_marker reverse : exception %s' % e)
        ok = False
    return ok


def test_extract_blocks():
    ok = True
    txt = "\n".join([
        "header",
        _mk("AVANT"),
        "line1",
        "line2",
        _mk("APRES"),
        "line3",
        _mk("FIN"),
        "line4",
    ])
    try:
        blocks = nexus_ombre.extract_blocks(txt)
        exp = {
            "AVANT": ["line1", "line2"],
            "APRES": ["line3"],
            "FIN": ["line4"],
        }
        if blocks == exp:
            print('[OK  ] extract_blocks forward : trois blocs extraits')
        else:
            print('[RATE] extract_blocks forward : rendu %r' % blocks)
            ok = False
    except Exception as e:
        print('[RATE] extract_blocks forward : exception %s' % e)
        ok = False
    # REVERSE : un marqueur manquant rend un dict vide
    txt2 = "\n".join([_mk("AVANT"), "only"])
    try:
        blocks2 = nexus_ombre.extract_blocks(txt2)
        if blocks2 == {}:
            print('[OK  ] extract_blocks reverse : marqueur manquant -> dict vide')
        else:
            print('[RATE] extract_blocks reverse : rendu %r' % blocks2)
            ok = False
    except Exception as e:
        print('[RATE] extract_blocks reverse : exception %s' % e)
        ok = False
    return ok


def test_count_anchor_occurrences():
    ok = True
    anchor = _mk("AVANT")
    lines = ["   %s" % anchor, "foo", "%s   " % anchor, "bar"]
    try:
        cnt = nexus_ombre.count_anchor_occurrences(lines, anchor)
        if cnt == 2:
            print('[OK  ] count_anchor forward : 2 occurrences, blancs ignores')
        else:
            print('[RATE] count_anchor forward : compte %r' % cnt)
            ok = False
    except Exception as e:
        print('[RATE] count_anchor forward : exception %s' % e)
        ok = False
    # REVERSE : lignes non iterables -> exception
    try:
        nexus_ombre.count_anchor_occurrences(None, anchor)
        print('[RATE] count_anchor reverse : aucune exception sur None')
        ok = False
    except Exception:
        print('[OK  ] count_anchor reverse : None leve une exception')
    return ok


def test_simulate_replacement():
    ok = True
    target = ["pre", _mk("AVANT"), "mid", _mk("APRES"), "post"]
    blocks = {"AVANT": ["a1"], "APRES": ["b1", "b2"], "FIN": []}
    try:
        new = nexus_ombre.simulate_replacement(target, blocks)
        exp = ["pre", "a1", "mid", "b1", "b2", "post"]
        if new == exp:
            print('[OK  ] simulate_replacement forward : marqueurs remplaces par leurs blocs')
        else:
            print('[RATE] simulate_replacement forward : rendu %r' % new)
            ok = False
    except Exception as e:
        print('[RATE] simulate_replacement forward : exception %s' % e)
        ok = False
    # REVERSE : marqueur present dans la cible, bloc absent -> exception
    target2 = ["start", _mk("FIN"), "end"]
    blocks2 = {"AVANT": [], "APRES": []}
    try:
        nexus_ombre.simulate_replacement(target2, blocks2)
        print('[RATE] simulate_replacement reverse : aucune exception sur bloc absent')
        ok = False
    except Exception:
        print('[OK  ] simulate_replacement reverse : bloc absent leve une exception')
    return ok


def main():
    results = [
        test_build_marker(),
        test_extract_blocks(),
        test_count_anchor_occurrences(),
        test_simulate_replacement(),
    ]
    return 0 if all(results) else 1


if __name__ == '__main__':
    sys.exit(main())