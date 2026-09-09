import sys, os, subprocess, tempfile, time
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
OUTIL = RACINE / 'scripts' / 'nexus_deposer.py'

def _ok(nom, detail):
    print('[OK  ] %s : %s' % (nom, detail))

def _rate(nom, detail):
    print('[RATE] %s : %s' % (nom, detail))

def _run(args):
    return subprocess.run(
        [sys.executable, str(OUTIL), *args],
        cwd=str(RACINE),
        capture_output=True,
        text=True,
        encoding='utf-8',
        errors='replace',
        timeout=60
    )

def test_forward():
    marker = 'MARQUE_' + str(os.getpid()) + '_' + str(int(time.time()))
    with tempfile.NamedTemporaryFile(delete=False, mode='w', encoding='utf-8') as tf:
        tf.write(marker)
        tf_path = tf.name

    result = _run([tf_path, 'modele-test', 'cloud', 'tache-test'])
    if result.returncode != 0:
        _rate('FORWARD', 'non-zero exit code')
        return False
    if os.path.exists(tf_path):
        _rate('FORWARD', 'temporary file not removed')
        return False

    sys.path.insert(0, str(RACINE / 'scripts'))
    try:
        import nexus_verbatim
        entries, _ = nexus_verbatim.charger_index()
        recent = entries[-20:] if len(entries) >= 20 else entries
        found = False
        for entry in recent:
            content = nexus_verbatim.lire(entry['id'])
            if content and marker in content:
                found = True
                break
        if not found:
            _rate('FORWARD', 'marker not found in verbatim store')
            return False
    finally:
        sys.path.pop(0)

    _ok('FORWARD', 'passed')
    return True

def test_reverse_missing_file():
    missing_path = str(RACINE / ('nonexistent_' + str(os.getpid()) + '_' + str(int(time.time()))))
    result = _run([missing_path, 'modele-test', 'cloud'])
    if result.returncode != 0:
        _rate('REVERSE_MISSING', 'non-zero exit code')
        return False
    _ok('REVERSE_MISSING', 'passed')
    return True

def test_reverse_insufficient_args():
    result = _run([])
    if result.returncode != 0:
        _rate('REVERSE_ARGS', 'non-zero exit code')
        return False
    _ok('REVERSE_ARGS', 'passed')
    return True

def main():
    all_ok = True
    all_ok &= test_forward()
    all_ok &= test_reverse_missing_file()
    all_ok &= test_reverse_insufficient_args()
    return 0 if all_ok else 1

if __name__ == '__main__':
    sys.exit(main())