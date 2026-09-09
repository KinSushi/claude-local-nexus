import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / 'outillage'))

import nexus_boussole as nb


def test_escape_md_forward():
    try:
        input_str = "a|b`c"
        expected = "a\\|b\\`c"
        result = nb._escape_md(input_str)
        if result == expected:
            print("[OK  ] escape_md_forward : output matches")
            return True
        print(f"[RATE] escape_md_forward : expected '{expected}' got '{result}'")
        return False
    except Exception as exc:
        print(f"[RATE] escape_md_forward : unexpected exception {exc}")
        return False

def test_escape_md_reverse():
    try:
        nb._escape_md(None)
        print("[RATE] escape_md_reverse : no exception raised for None")
        return False
    except Exception:
        print("[OK  ] escape_md_reverse : exception raised as expected")
        return True

def main():
    all_ok = True
    all_ok &= test_escape_md_forward()
    all_ok &= test_escape_md_reverse()
    return 0 if all_ok else 1

if __name__ == '__main__':
    sys.exit(main())