"""Epreuve de nexus_livres_semantique : cosine_similarity et _selectionner_top."""
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / 'scripts'))
import nexus_livres_semantique as nls


def test_cosine_similarity_forward():
    try:
        v = [1, 2, 3]
        res = nls.cosine_similarity(v, v)
        if abs(res - 1.0) < 1e-12:
            print('[OK  ] cosine_similarity forward : vecteurs identiques -> 1.0')
            return True
        print('[RATE] cosine_similarity forward : attendu 1.0 rendu %r' % res)
        return False
    except Exception as e:
        print('[RATE] cosine_similarity forward : exception %s' % e)
        return False


def test_cosine_similarity_reverse():
    try:
        nls.cosine_similarity([1, 2], [1, 2, 3])
        print('[RATE] cosine_similarity reverse : longueurs differentes acceptees')
        return False
    except Exception:
        print('[OK  ] cosine_similarity reverse : longueurs differentes -> exception (zip strict)')
        return True


def test_selectionner_top_forward():
    try:
        paires = [(0.5, 'a'), (0.9, 'b'), (0.2, 'c')]
        top = nls._selectionner_top(paires, 2)
        expected = [(0.9, 'b'), (0.5, 'a')]
        if top == expected:
            print('[OK  ] selectionner_top forward : les 2 meilleurs, scores decroissants')
            return True
        print('[RATE] selectionner_top forward : rendu %r attendu %r' % (top, expected))
        return False
    except Exception as e:
        print('[RATE] selectionner_top forward : exception %s' % e)
        return False


def test_selectionner_top_reverse():
    try:
        top = nls._selectionner_top([(0.1, 'x')], 0)
        if top == []:
            print('[OK  ] selectionner_top reverse : top_n 0 -> liste vide')
            return True
        print('[RATE] selectionner_top reverse : attendu [] rendu %r' % top)
        return False
    except Exception as e:
        print('[RATE] selectionner_top reverse : exception %s' % e)
        return False


def main():
    results = [
        test_cosine_similarity_forward(),
        test_cosine_similarity_reverse(),
        test_selectionner_top_forward(),
        test_selectionner_top_reverse(),
    ]
    return 0 if all(results) else 1


if __name__ == '__main__':
    sys.exit(main())