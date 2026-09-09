import sys
import io
import contextlib
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / 'outillage'))
import nexus_poser_socle


def _merge(src, tgt):
    # Le module imprime ses refus avec le prefixe [RATE] : les capturer, sinon
    # le lanceur les compterait comme des echecs de CETTE epreuve (faux rouge).
    with contextlib.redirect_stdout(io.StringIO()):
        return nexus_poser_socle.merge_permissions(src, tgt)


def test_merge_permissions_forward():
    src = {"permissions": {"deny": ["rule1", "rule2"], "ask": ["ruleA"]}}
    tgt = {"permissions": {"deny": ["rule2", "rule3"], "ask": []}}
    result = _merge(src, tgt)
    if result is None:
        print('[RATE] merge_permissions_forward : result is None')
        return False
    new_target, deny_added, ask_added = result
    exp_new_target = {"permissions": {"deny": ["rule2", "rule3", "rule1"], "ask": ["ruleA"]}}
    if new_target != exp_new_target:
        print('[RATE] merge_permissions_forward : new_target %r' % (new_target,))
        return False
    if deny_added != ["rule1"] or ask_added != ["ruleA"]:
        print('[RATE] merge_permissions_forward : added %r %r' % (deny_added, ask_added))
        return False
    print('[OK  ] merge_permissions_forward : fusion sans doublon, ajouts listes')
    return True


def test_merge_permissions_reverse():
    cases = [
        (None, {}, "source None"),
        ({}, {}, "source sans permissions"),
        ({"permissions": []}, {}, "permissions non dict"),
        ({"permissions": {"deny": "notlist", "ask": []}}, {}, "deny non liste"),
        ({"permissions": {"deny": [], "ask": "notlist"}}, {}, "ask non liste"),
        ({"permissions": {"deny": [], "ask": []}}, [], "cible non dict"),
        ({"permissions": {"deny": [], "ask": []}}, {"permissions": []}, "cible permissions non dict"),
        ({"permissions": {"deny": [], "ask": []}}, {"permissions": {"deny": "bad", "ask": []}}, "cible deny non liste"),
        ({"permissions": {"deny": [], "ask": []}}, {"permissions": {"deny": [], "ask": "bad"}}, "cible ask non liste"),
    ]
    all_ok = True
    for src, tgt, desc in cases:
        try:
            result = _merge(src, tgt)
        except Exception as e:
            print('[RATE] merge_permissions_reverse : %s raised %s' % (desc, e))
            all_ok = False
            continue
        if result is not None:
            print('[RATE] merge_permissions_reverse : %s returned non-None' % desc)
            all_ok = False
        else:
            print('[OK  ] merge_permissions_reverse : %s -> None' % desc)
    result = _merge({"permissions": {"deny": ["r1"], "ask": ["a1"]}}, None)
    if result is None:
        print('[RATE] merge_permissions_reverse : cible None doit etre acceptee')
        return False
    new_target, deny_added, ask_added = result
    if new_target != {"permissions": {"deny": ["r1"], "ask": ["a1"]}} or deny_added != ["r1"] or ask_added != ["a1"]:
        print('[RATE] merge_permissions_reverse : cible None produit %r' % (new_target,))
        return False
    print('[OK  ] merge_permissions_reverse : cible None -> socle copie')
    return all_ok


def main():
    results = [test_merge_permissions_forward(), test_merge_permissions_reverse()]
    return 0 if all(results) else 1


if __name__ == '__main__':
    sys.exit(main())