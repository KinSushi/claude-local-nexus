import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / 'outillage'))
import nexus_indexer_node as mod


def _cas(nom, fn, entree, attendu):
    try:
        got = fn(entree)
    except Exception as e:
        print("[RATE] %s : raised %s" % (nom, e))
        return False
    if got == attendu:
        print("[OK  ] %s : %r -> %r" % (nom, entree, got))
        return True
    print("[RATE] %s : expected %r got %r" % (nom, attendu, got))
    return False


def test_clean_html_forward():
    return _cas("clean_html_forward", mod.clean_html, "<b>Hello &amp; World</b>", "Hello & World")


def test_clean_html_reverse():
    try:
        mod.clean_html(123)
    except TypeError:
        print("[OK  ] clean_html_reverse : TypeError raised as expected")
        return True
    except Exception as e:
        print("[RATE] clean_html_reverse : unexpected exception %s" % e)
        return False
    print("[RATE] clean_html_reverse : expected TypeError not raised")
    return False


def test_is_valid_name_forward():
    return _cas("is_valid_name_forward", mod.is_valid_name, "validName", True)


def test_is_valid_name_reverse():
    return _cas("is_valid_name_reverse", mod.is_valid_name, "invalid name", False)


def test_normalize_field_forward():
    return _cas("normalize_field_forward", mod.normalize_field, "  a \n b\tc  ", "a b c")


def test_normalize_field_reverse():
    return _cas("normalize_field_reverse (non-str unchanged)", mod.normalize_field, 123, 123)


def main():
    results = [
        test_clean_html_forward(),
        test_clean_html_reverse(),
        test_is_valid_name_forward(),
        test_is_valid_name_reverse(),
        test_normalize_field_forward(),
        test_normalize_field_reverse(),
    ]
    return 0 if all(results) else 1


if __name__ == '__main__':
    sys.exit(main())