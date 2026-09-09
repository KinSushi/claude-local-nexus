"""Epreuve de nexus_indexer_texte : _slugify, la fonction pure de l'indexeur."""
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / 'outillage'))
import nexus_indexer_texte as nit


def test_slugify_forward():
    name = 'slugify forward'
    try:
        result = nit._slugify('Hello World!')
        if result == 'hello_world':
            print('[OK  ] %s : %s' % (name, 'Hello World! -> hello_world'))
            return True
        print('[RATE] %s : %s' % (name, 'slug inattendu %r' % result))
        return False
    except Exception as e:
        print('[RATE] %s : %s' % (name, 'exception %s' % e))
        return False


def test_slugify_reverse():
    name = 'slugify reverse'
    try:
        result = nit._slugify('')
        if result == 'unknown':
            print('[OK  ] %s : %s' % (name, 'chaine vide -> sentinelle unknown'))
        else:
            print('[RATE] %s : %s' % (name, 'chaine vide -> %r' % result))
            return False
    except Exception as e:
        print('[RATE] %s : %s' % (name, 'exception sur chaine vide %s' % e))
        return False
    try:
        nit._slugify(123)
        print('[RATE] %s : %s' % (name, 'aucune exception sur un entier'))
        return False
    except Exception:
        print('[OK  ] %s : %s' % (name, 'un entier leve une exception'))
        return True


def main():
    results = [test_slugify_forward(), test_slugify_reverse()]
    return 0 if all(results) else 1


if __name__ == '__main__':
    sys.exit(main())