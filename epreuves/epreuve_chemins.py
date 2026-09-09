import sys
import subprocess
import tempfile
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
OUTIL = RACINE / "outillage" / "nexus_chemins.py"
TIMEOUT = 120

def _ok(name, detail):
    print("[OK  ] %s : %s" % (name, detail))

def _rate(name, detail):
    print("[RATE] %s : %s" % (name, detail))

def _run(args, cwd):
    completed = subprocess.run(
        args, cwd=str(cwd), capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=TIMEOUT,
    )
    return completed.returncode, completed.stdout, completed.stderr

def test_auto_integre():
    name = "auto-test integre"
    try:
        rc, out, err = _run([sys.executable, str(OUTIL), "--epreuve"], RACINE)
    except subprocess.TimeoutExpired:
        _rate(name, "pas de reponse en %d s" % TIMEOUT)
        return False
    if rc == 0:
        _ok(name, "l auto-test interne (detection + correction) passe")
        return True
    _rate(name, "code retour %d" % rc)
    return False

def test_reverse_mort_detecte():
    # Detection testee EN MEMOIRE via analyse_file : plus fiable qu'un subprocess
    # qui depend de la decouverte de racine. Un mort doit etre vu, un vivant ignore.
    name = "reverse : un mort est detecte, un vivant ignore"
    sys.path.insert(0, str(RACINE / "outillage"))
    try:
        import nexus_chemins as ch
    except Exception as exc:
        _rate(name, "import impossible : %s" % exc)
        return False
    with tempfile.TemporaryDirectory() as tmp:
        tp = Path(tmp)
        (tp / "scripts").mkdir()
        (tp / "outillage").mkdir()
        mort = tp / "scripts" / "faux.py"
        mort.write_text("chemin = 'scripts/nexus_inexistant_zzz.py'\n", encoding="utf-8")
        refs_mort = ch.analyse_file(mort, tp)
        (tp / "scripts" / "nexus_present.py").write_text("# present\n", encoding="utf-8")
        vivant = tp / "scripts" / "vivant.py"
        vivant.write_text("chemin = 'scripts/nexus_present.py'\n", encoding="utf-8")
        refs_vivant = ch.analyse_file(vivant, tp)
        if len(refs_mort) >= 1 and len(refs_vivant) == 0:
            _ok(name, "mort=%d vivant=%d" % (len(refs_mort), len(refs_vivant)))
            return True
        _rate(name, "mort=%d (attendu >=1), vivant=%d (attendu 0)" % (len(refs_mort), len(refs_vivant)))
        return False

def main():
    if not OUTIL.is_file():
        _rate("chemins", "outil introuvable : %s" % OUTIL)
        return 1
    resultats = [test_auto_integre(), test_reverse_mort_detecte()]
    return 0 if all(resultats) else 1

if __name__ == "__main__":
    sys.exit(main())