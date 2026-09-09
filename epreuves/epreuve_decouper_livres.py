import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / 'outillage'))
import nexus_decouper_livres as mod


def _verdict(nom, ok, detail=''):
    if ok:
        print('[OK  ] %s : %s' % (nom, detail or 'ok'))
    else:
        print('[RATE] %s : %s' % (nom, detail or 'echec'))
    return ok


def test_is_title_forward():
    try:
        res = mod.is_title(["1. Chapter"], 0)
    except Exception as e:
        return _verdict('is_title_forward', False, 'raised %s' % e)
    return _verdict('is_title_forward', res is True, '"1. Chapter" est un titre')


def test_is_title_reverse():
    try:
        mod.is_title([], 0)
    except IndexError:
        return _verdict('is_title_reverse', True, 'liste vide -> IndexError')
    except Exception as e:
        return _verdict('is_title_reverse', False, 'unexpected %s' % e)
    return _verdict('is_title_reverse', False, 'no exception')


def test_split_chapters_forward():
    body_a = "a" * 1500
    body_b = "b" * 1500
    text = "1. Title\n" + body_a + "\n2. Next\n" + body_b
    expected = [("1. Title", "1. Title\n" + body_a), ("2. Next", "2. Next\n" + body_b)]
    try:
        res = mod.split_chapters(text)
    except Exception as e:
        return _verdict('split_chapters_forward', False, 'raised %s' % e)
    return _verdict('split_chapters_forward', res == expected, '2 chapitres')


def test_split_chapters_reverse():
    try:
        mod.split_chapters(None)
    except AttributeError:
        return _verdict('split_chapters_reverse', True, 'None -> AttributeError (splitlines sur None)')
    except Exception as e:
        return _verdict('split_chapters_reverse', False, 'unexpected %s' % e)
    return _verdict('split_chapters_reverse', False, 'no exception')


def test_cut_menu_forward():
    try:
        res = mod.cut_menu("short text", 100)
    except Exception as e:
        return _verdict('cut_menu_forward', False, 'raised %s' % e)
    return _verdict('cut_menu_forward', res == ["short text"], 'texte court -> un seul morceau')


def test_cut_menu_reverse():
    try:
        res = mod.cut_menu("", 50)
    except Exception as e:
        return _verdict('cut_menu_reverse', False, 'raised %s' % e)
    return _verdict('cut_menu_reverse', res == [], 'texte vide -> liste vide')


def main():
    results = [
        test_is_title_forward(),
        test_is_title_reverse(),
        test_split_chapters_forward(),
        test_split_chapters_reverse(),
        test_cut_menu_forward(),
        test_cut_menu_reverse(),
    ]
    return 0 if all(results) else 1


if __name__ == '__main__':
    sys.exit(main())