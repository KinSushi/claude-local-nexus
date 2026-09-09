import sys, tempfile
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / 'scripts'))
import nexus_boucle_locale as bl

def _report(test_name, subcase, ok):
    if ok:
        print('[OK  ] %s : %s' % (test_name, subcase))
    else:
        print('[RATE] %s : %s' % (test_name, subcase))
    return ok

def test_decision():
    ok = True
    cases = [
        (("OK", 0, 3), "APPLIQUER", "case1"),
        (("RETRY", 0, 3), "REPENSER", "case2"),
        (("RETRY", 2, 3), "ABANDONNER", "case3"),
        (("REJET", 0, 3), "ABANDONNER", "case4"),
    ]
    for args, expected, name in cases:
        try:
            result = bl.decision_suivante(*args)
            ok = ok and _report("test_decision", name, result == expected)
        except Exception:
            ok = ok and _report("test_decision", name, False)
    return ok

def test_parser():
    ok = True
    cases = [
        ("blabla\nVERDICT: OK", "OK", "case1"),
        ("Verdict: Retry", "RETRY", "case2"),
        ("verdict: REJET", "REJET", "case3"),
        ("", "RETRY", "case4"),
        (None, "RETRY", "case5"),
        ("rien", "RETRY", "case6"),
    ]
    for texte, expected, name in cases:
        try:
            result = bl.parser_verdict(texte)
            ok = ok and _report("test_parser", name, result == expected)
        except Exception:
            ok = ok and _report("test_parser", name, False)
    return ok

def test_loi1():
    def dummy_appli(*a, **k):
        return ""
    try:
        bl.un_cycle({"tache": "x"}, "m", "m", dummy_appli)
        _report("test_loi1", "no_error", False)
        return False
    except ValueError:
        _report("test_loi1", "value_error", True)
        return True
    except Exception:
        _report("test_loi1", "unexpected_error", False)
        return False

def _appel_ok(modele, consigne, fichiers):
    if modele == "pilote":
        return "PATCH"
    if modele == "auditeur":
        return "VERDICT: OK"
    return ""

def test_cycle_mock():
    ok = True
    try:
        patch, verdict, detail = bl.un_cycle(
            {"tache": "x", "fichiers": []}, "pilote", "auditeur", _appel_ok)
        ok = ok and _report("test_cycle_mock", "patch", patch == "PATCH")
        ok = ok and _report("test_cycle_mock", "verdict", verdict == "OK")
    except Exception:
        ok = ok and _report("test_cycle_mock", "exception", False)
    return ok

def test_boucle_forward():
    ok = True
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        def deposer_fn(tache, patch, verdict):
            return bl.deposer_proposition(tache, patch, verdict, td_path)
        taches = [{"nom": "t1", "tache": "x", "fichiers": []}]
        rapport = bl.boucle(taches, lambda: False, _appel_ok, "pilote", "auditeur", deposer_fn)
        ok = ok and _report("test_boucle_forward", "traitees", rapport.get("traitees") == 1)
        ok = ok and _report("test_boucle_forward", "deposees", rapport.get("deposees") == 1)
        ok = ok and _report("test_boucle_forward", "retrait", rapport.get("retrait") is False)
        json_files = list(td_path.glob("*.json"))
        return ok and _report("test_boucle_forward", "json_written", len(json_files) == 1)

def test_boucle_reverse_retrait():
    ok = True
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        def deposer_fn(tache, patch, verdict):
            return bl.deposer_proposition(tache, patch, verdict, td_path)
        taches = [{"nom": "t1", "tache": "x", "fichiers": []}]
        rapport = bl.boucle(taches, lambda: True, lambda m, c, f: "", "pilote", "auditeur", deposer_fn)
        ok = ok and _report("test_boucle_reverse_retrait", "retrait", rapport.get("retrait") is True)
        ok = ok and _report("test_boucle_reverse_retrait", "traitees", rapport.get("traitees") == 0)
        return ok and _report("test_boucle_reverse_retrait", "deposees", rapport.get("deposees") == 0)

def test_boucle_abandon():
    ok = True
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        def deposer_fn(tache, patch, verdict):
            return bl.deposer_proposition(tache, patch, verdict, td_path)
        def appel_rejet(modele, consigne, fichiers):
            if modele == "pilote":
                return "PATCH"
            return "VERDICT: REJET"
        taches = [{"nom": "t1", "tache": "x", "fichiers": []}]
        rapport = bl.boucle(taches, lambda: False, appel_rejet, "pilote", "auditeur", deposer_fn)
        ok = ok and _report("test_boucle_abandon", "abandonnees", rapport.get("abandonnees") == 1)
        return ok and _report("test_boucle_abandon", "deposees", rapport.get("deposees") == 0)

def main():
    results = [
        test_decision(),
        test_parser(),
        test_loi1(),
        test_cycle_mock(),
        test_boucle_forward(),
        test_boucle_reverse_retrait(),
        test_boucle_abandon(),
    ]
    return 0 if all(results) else 1

if __name__ == '__main__':
    sys.exit(main())