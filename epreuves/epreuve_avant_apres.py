import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / 'outillage'))
import nexus_avant_apres


def _ok(name, detail):
    print('[OK  ] %s : %s' % (name, detail))


def _rate(name, detail):
    print('[RATE] %s : %s' % (name, detail))


def test_hash_bytes_forward():
    name = 'hash_bytes_forward'
    try:
        result = nexus_avant_apres._hash_bytes(b'abc')
    except Exception as e:
        _rate(name, 'exception %s' % e)
        return False
    expected = 'ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad'
    if result == expected:
        _ok(name, 'sha256 de abc')
        return True
    _rate(name, 'unexpected hash')
    return False


def test_hash_bytes_reverse():
    name = 'hash_bytes_reverse'
    try:
        nexus_avant_apres._hash_bytes('notbytes')
    except Exception:
        _ok(name, 'exception raised on str')
        return True
    _rate(name, 'no exception raised')
    return False


def test_comparer_releves_forward():
    name = 'comparer_releves_forward'
    avant = {'code': 0, 'lignes': 2, 'empreinte': 'a' * 64}
    apres = {'code': 0, 'lignes': 2, 'empreinte': 'a' * 64}
    try:
        verdict = nexus_avant_apres.comparer_releves(avant, apres)
    except Exception as e:
        _rate(name, 'exception %s' % e)
        return False
    if verdict == 'IDENTIQUE':
        _ok(name, 'identical verdict')
        return True
    _rate(name, 'unexpected verdict %s' % verdict)
    return False


def test_comparer_releves_reverse():
    name = 'comparer_releves_reverse'
    apres = {'code': 0, 'lignes': 1, 'empreinte': 'b' * 64}
    try:
        verdict = nexus_avant_apres.comparer_releves(None, apres)
    except Exception as e:
        _rate(name, 'exception %s' % e)
        return False
    if verdict == 'INDECIS':
        _ok(name, 'invalid input yields INDECIS')
        return True
    _rate(name, 'unexpected verdict %s' % verdict)
    return False


def test_verdict_to_exit_forward():
    name = 'verdict_to_exit_forward'
    try:
        code = nexus_avant_apres._verdict_to_exit('IDENTIQUE')
    except Exception as e:
        _rate(name, 'exception %s' % e)
        return False
    if code == 0:
        _ok(name, 'IDENTIQUE -> 0')
        return True
    _rate(name, 'unexpected code %s' % code)
    return False


def test_verdict_to_exit_reverse():
    name = 'verdict_to_exit_reverse'
    try:
        code = nexus_avant_apres._verdict_to_exit('UNKNOWN')
    except Exception as e:
        _rate(name, 'exception %s' % e)
        return False
    if code == 2:
        _ok(name, 'UNKNOWN -> 2')
        return True
    _rate(name, 'unexpected code %s' % code)
    return False


def main():
    tests = [
        test_hash_bytes_forward,
        test_hash_bytes_reverse,
        test_comparer_releves_forward,
        test_comparer_releves_reverse,
        test_verdict_to_exit_forward,
        test_verdict_to_exit_reverse,
    ]
    all_ok = True
    for t in tests:
        if not t():
            all_ok = False
    return 0 if all_ok else 1


if __name__ == '__main__':
    sys.exit(main())