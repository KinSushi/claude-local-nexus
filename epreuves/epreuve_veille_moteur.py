import os
import sys
import tempfile
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'outillage'))
import nexus_veille_moteur as nvm

failures = 0

def check(condition, name, cause=''):
    global failures
    if condition:
        print(f'[OK] {name}')
    else:
        failures += 1
        print(f'[RATE] {name} : {cause}')

# Test coince with two models
ps = {
    'models': [
        {'name': 'model1', 'size': 10 * 1024**3, 'expires_at': '2026-09-14T10:00:00+00:00'},
        {'name': 'model2', 'size': 5 * 1024**3, 'expires_at': '2026-09-14T10:05:00+00:00'}
    ]
}
maintenant = '2026-09-14T10:05:00+00:00'
seuil = 120
res = nvm.coince(ps, maintenant, seuil)
check(len(res) == 1 and res[0]['nom'] == 'model1' and abs(res[0]['depuis_s'] - 300) < 1,
      'coince two models', f'got {res}')

# Test coince with Z and 9-digit fraction
ps = {
    'models': [
        {'name': 'modelZ', 'size': 1, 'expires_at': '2026-09-14T10:00:00.123456789Z'}
    ]
}
maintenant = '2026-09-14T10:05:00+00:00'
res = nvm.coince(ps, maintenant, seuil)
check(len(res) == 1 and res[0]['nom'] == 'modelZ' and abs(res[0]['depuis_s'] - 300) < 1,
      'coince Z and fraction', f'got {res}')

# Test coince with empty dict
res = nvm.coince({}, maintenant, seuil)
check(res == [], 'coince empty', f'got {res}')

# Test verdict combinations
check(nvm.verdict([{'nom': 'x'}], False) == 'BLOQUE', 'verdict BLOQUE')
check(nvm.verdict([{'nom': 'x'}], None) == 'SUSPECT', 'verdict SUSPECT coinces+None')
check(nvm.verdict([{'nom': 'x'}], True) == 'SUSPECT', 'verdict SUSPECT coinces+True')
check(nvm.verdict([], False) == 'SUSPECT', 'verdict SUSPECT no coinces+False')
check(nvm.verdict([], True) == 'SAIN', 'verdict SAIN')

# Test reverse: healthy, no restart
with mock.patch.object(nvm, 'version_repond', return_value=True), \
     mock.patch.object(nvm, 'lire_ps', return_value={'models': []}), \
     mock.patch.object(nvm, 'sonder', return_value=True), \
     mock.patch.object(nvm, 'relancer_moteur') as mock_relance:
    result = nvm.executer('http://x', 'model', 25, 120, True)
    check(result['verdict'] == 'SAIN' and not mock_relance.called,
          'reverse no restart', f"verdict={result['verdict']}, relance_called={mock_relance.called}")

# Test forward: BLOQUE and restart
# The expires_at is set in the past because executer compares to real time.
ps_bloque = {
    'models': [
        {'name': 'stuck', 'size': 20 * 1024**3, 'expires_at': '2020-01-01T00:00:00+00:00'}
    ]
}
with mock.patch.object(nvm, 'version_repond', return_value=True), \
     mock.patch.object(nvm, 'lire_ps', return_value=ps_bloque), \
     mock.patch.object(nvm, 'sonder', return_value=False), \
     mock.patch.object(nvm, 'relancer_moteur', return_value=True) as mock_relance:
    result = nvm.executer('http://x', 'model', 25, 120, True)
    check(result['verdict'] == 'BLOQUE' and mock_relance.call_count == 1,
          'forward restart', f"verdict={result['verdict']}, relance_calls={mock_relance.call_count}")

# Test journal absent -> legacy rule applies (BLOQUE and restart)
journal_absent = os.path.join(tempfile.gettempdir(), 'nexus_veille_journal_absent_' + str(os.getpid()))
if os.path.exists(journal_absent):
    os.remove(journal_absent)
with mock.patch.object(nvm, 'version_repond', return_value=True), \
     mock.patch.object(nvm, 'lire_ps', return_value=ps_bloque), \
     mock.patch.object(nvm, 'sonder', return_value=False), \
     mock.patch.object(nvm, 'relancer_moteur', return_value=True) as mock_relance:
    result = nvm.executer('http://x', 'model', 25, 120, True, journal=journal_absent)
    check(result['verdict'] == 'BLOQUE' and mock_relance.call_count == 1 and result['journal_avance'] is None,
          'journal absent legacy BLOQUE', f"verdict={result['verdict']}, relance_calls={mock_relance.call_count}, journal_avance={result['journal_avance']}")

# Test journal advances during probe -> SUSPECT, no restart
journal_avance_path = tempfile.NamedTemporaryFile(mode='w', delete=False)
journal_avance_path.write('initial\n')
journal_avance_path.close()
def sonder_modifie(url, modele, delai):
    with open(journal_avance_path.name, 'a') as f:
        f.write('progression\n')
    return False
with mock.patch.object(nvm, 'version_repond', return_value=True), \
     mock.patch.object(nvm, 'lire_ps', return_value=ps_bloque), \
     mock.patch.object(nvm, 'sonder', side_effect=sonder_modifie), \
     mock.patch.object(nvm, 'relancer_moteur') as mock_relance:
    result = nvm.executer('http://x', 'model', 25, 120, True, journal=journal_avance_path.name)
    check(result['verdict'] == 'SUSPECT' and not mock_relance.called and result['journal_avance'] is True,
          'journal advances SUSPECT', f"verdict={result['verdict']}, relance_called={mock_relance.called}, journal_avance={result['journal_avance']}")
os.unlink(journal_avance_path.name)

# Test journal silent during probe -> BLOQUE and restart
journal_silencieux_path = tempfile.NamedTemporaryFile(mode='w', delete=False)
journal_silencieux_path.write('initial\n')
journal_silencieux_path.close()
with mock.patch.object(nvm, 'version_repond', return_value=True), \
     mock.patch.object(nvm, 'lire_ps', return_value=ps_bloque), \
     mock.patch.object(nvm, 'sonder', return_value=False), \
     mock.patch.object(nvm, 'relancer_moteur', return_value=True) as mock_relance:
    result = nvm.executer('http://x', 'model', 25, 120, True, journal=journal_silencieux_path.name)
    check(result['verdict'] == 'BLOQUE' and mock_relance.call_count == 1 and result['journal_avance'] is False,
          'journal silent BLOQUE', f"verdict={result['verdict']}, relance_calls={mock_relance.call_count}, journal_avance={result['journal_avance']}")
os.unlink(journal_silencieux_path.name)

sys.exit(1 if failures else 0)
