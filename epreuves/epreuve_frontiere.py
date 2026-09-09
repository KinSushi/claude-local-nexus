import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / 'outillage'))
import nexus_frontiere as fr

def _print_result(ok, name, detail):
    prefix = '[OK  ]' if ok else '[RATE]'
    print(f"{prefix} {name} : {detail}")

def main():
    all_ok = True

    try:
        ok = fr._run_epreuve() == 0
        _print_result(ok, 'auto-test integre', 'expected 0')
        all_ok = all_ok and ok
    except Exception as e:
        _print_result(False, 'auto-test integre', f'exception {e}')
        all_ok = False

    try:
        expr = "reg = os.path.join(ROOT, 'outillage', 'nexus_frontiere.py')"
        ok = fr._extract_tool(expr) == 'nexus_frontiere.py'
        _print_result(ok, 'extract execution', "expected 'nexus_frontiere.py'")
        all_ok = all_ok and ok
    except Exception as e:
        _print_result(False, 'extract execution', f'exception {e}')
        all_ok = False

    try:
        expr = 'x = 3  # rien ici'
        ok = fr._extract_tool(expr) == ''
        _print_result(ok, 'extract absent', "expected ''")
        all_ok = all_ok and ok
    except Exception as e:
        _print_result(False, 'extract absent', f'exception {e}')
        all_ok = False

    try:
        line = "    r = os.path.join(ROOT, 'outillage', 'nexus_foo.py')"
        ok = fr._classify_line('a.py', line) == ('EXECUTION', 'nexus_foo.py')
        _print_result(ok, 'classify py execution', "expected ('EXECUTION','nexus_foo.py')")
        all_ok = all_ok and ok
    except Exception as e:
        _print_result(False, 'classify py execution', f'exception {e}')
        all_ok = False

    try:
        line = "    print('outillage/nexus_foo.py trouve')"
        ok = fr._classify_line('a.py', line) == ('MENTION', 'nexus_foo.py')
        _print_result(ok, 'classify py mention', "expected ('MENTION','nexus_foo.py')")
        all_ok = all_ok and ok
    except Exception as e:
        _print_result(False, 'classify py mention', f'exception {e}')
        all_ok = False

    try:
        line = "# outillage/nexus_foo.py"
        ok = fr._classify_line('a.py', line) == ('', '')
        _print_result(ok, 'classify commentaire ignore', "expected ('','')")
        all_ok = all_ok and ok
    except Exception as e:
        _print_result(False, 'classify commentaire ignore', f'exception {e}')
        all_ok = False

    try:
        line = "path.join(INSTALL_ROOT, 'outillage', 'nexus_bar.py')"
        ok = fr._classify_line('a.js', line) == ('EXECUTION', 'nexus_bar.py')
        _print_result(ok, 'classify js execution', "expected ('EXECUTION','nexus_bar.py')")
        all_ok = all_ok and ok
    except Exception as e:
        _print_result(False, 'classify js execution', f'exception {e}')
        all_ok = False

    try:
        line = "Join-Path $root 'outillage' 'nexus_baz.py'"
        ok = fr._classify_line('a.ps1', line) == ('EXECUTION', 'nexus_baz.py')
        _print_result(ok, 'classify ps1 execution', "expected ('EXECUTION','nexus_baz.py')")
        all_ok = all_ok and ok
    except Exception as e:
        _print_result(False, 'classify ps1 execution', f'exception {e}')
        all_ok = False

    try:
        line = "    x = calcul(2)"
        ok = fr._classify_line('a.py', line) == ('', '')
        _print_result(ok, 'classify non pertinent', "expected ('','')")
        all_ok = all_ok and ok
    except Exception as e:
        _print_result(False, 'classify non pertinent', f'exception {e}')
        all_ok = False

    sys.exit(0 if all_ok else 1)

if __name__ == '__main__':
    main()