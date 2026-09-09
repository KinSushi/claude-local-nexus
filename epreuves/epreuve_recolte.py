import sys, os, json, tempfile
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / 'scripts'))
import nexus_recolte as nr


def test_cible():
    ok = True
    if nr.cible_de({"fichiers": ["a.py", "b.py"]}) != "a.py":
        ok = False
    if nr.cible_de({"fichiers": []}) is not None:
        ok = False
    if nr.cible_de({}) is not None:
        ok = False
    return ok


def test_vers_jsonl():
    ok = True
    if nr.vers_jsonl({"nom": "n", "patch": "P"}) != {"nom": "n", "texte": "P"}:
        ok = False
    if nr.vers_jsonl({}) != {"nom": "proposition", "texte": ""}:
        ok = False
    return ok


def test_appliquer_mock():
    called = []
    def mock_apply(jsonl_path, nom, cible):
        with open(jsonl_path, 'r', encoding='utf-8') as f:
            data = json.loads(f.readline())
        if data.get("nom") != "t1" or data.get("texte") != "PATCH":
            return (1, "bad json")
        called.append((nom, cible))
        return (0, "ok")
    with tempfile.TemporaryDirectory() as td:
        prop = {"nom": "t1", "fichiers": ["x.py"], "patch": "PATCH"}
        code, out = nr.appliquer(prop, td, mock_apply)
        if code != 0 or out != "ok":
            return False
        if not called or called[0] != ("t1", "x.py"):
            return False
        if os.path.exists(os.path.join(td, ".nexus", "recolte_t1.jsonl")):
            return False
    return True


def test_appliquer_sans_cible():
    called = []
    def mock_apply(*args, **kwargs):
        called.append(True)
        return (0, "ok")
    with tempfile.TemporaryDirectory() as td:
        code, out = nr.appliquer({"nom": "t2", "patch": "P"}, td, mock_apply)
        if code != 2:
            return False
        if called:
            return False
    return True


def test_charger():
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        (d / "a.json").write_text(json.dumps({"nom": "a", "timestamp": 20}), encoding='utf-8')
        (d / "b.json").write_text(json.dumps({"nom": "b", "timestamp": 10}), encoding='utf-8')
        (d / "c.json").write_text("pas du json", encoding='utf-8')
        props = nr.charger_propositions(td)
        if len(props) != 2:
            return False
        if os.path.basename(props[0][0]) != "b.json" or os.path.basename(props[1][0]) != "a.json":
            return False
        if nr.charger_propositions(os.path.join(td, "absent")) != []:
            return False
    return True


def test_archiver():
    with tempfile.TemporaryDirectory() as td:
        src = os.path.join(td, "p.json")
        with open(src, "w", encoding="utf-8") as f:
            f.write(json.dumps({"x": 1}))
        new_path = nr.archiver(src, os.path.join(td, "appliquees"))
        if new_path is None or not os.path.exists(new_path):
            return False
        if os.path.exists(src):
            return False
    return True


def main():
    tests = [
        ("cible", test_cible),
        ("vers_jsonl", test_vers_jsonl),
        ("appliquer_mock", test_appliquer_mock),
        ("appliquer_sans_cible", test_appliquer_sans_cible),
        ("charger", test_charger),
        ("archiver", test_archiver),
    ]
    all_ok = True
    for name, func in tests:
        try:
            ok = func()
        except Exception as exc:
            ok = False
            print("[RATE] %s : exception %s" % (name, str(exc)[:60]))
            all_ok = False
            continue
        if ok:
            print("[OK  ] %s : passed" % name)
        else:
            print("[RATE] %s : failed" % name)
            all_ok = False
    return 0 if all_ok else 1


if __name__ == '__main__':
    sys.exit(main())