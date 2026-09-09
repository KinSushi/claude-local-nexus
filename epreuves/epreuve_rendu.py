import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / 'scripts'))

import nexus_rendu as nx


def _mk_markers():
    M = "<" * 3 + "AVANT" + ">" * 3
    E = "&lt;" * 3 + "AVANT" + "&gt;" * 3
    return M, E


def _run_test(name, texte, attendu_texte, attendu_flag):
    try:
        resultat_texte, resultat_flag = nx.deencoder_si_entites(texte)
    except Exception as e:
        print('[RATE] %s : exception %s' % (name, e))
        return False
    ok = (resultat_texte == attendu_texte) and (resultat_flag == attendu_flag)
    if ok:
        print('[OK  ] %s : ok' % name)
    else:
        print('[RATE] %s : attendu (%r,%s) obtenu (%r,%s)' % (
            name, attendu_texte, attendu_flag, resultat_texte, resultat_flag))
    return ok


def main():
    M, E = _mk_markers()
    all_ok = True
    all_ok = _run_test('FORWARD encode', E + "\na = 1\n", M + "\na = 1\n", True) and all_ok
    all_ok = _run_test('REVERSE sain avec lt legitime', M + "\nx = '&lt;'\n", M + "\nx = '&lt;'\n", False) and all_ok
    all_ok = _run_test('sain sans rien', "a = 1", "a = 1", False) and all_ok
    all_ok = _run_test('amp seul', "x &amp; y", "x & y", True) and all_ok
    all_ok = _run_test('None', None, None, False) and all_ok
    all_ok = _run_test('vide', "", "", False) and all_ok
    texte6 = M + "\n" + E + "\na = 1\n"
    all_ok = _run_test('contre-epreuve marqueur brut present', texte6, texte6, False) and all_ok
    return 0 if all_ok else 1


if __name__ == '__main__':
    sys.exit(main())