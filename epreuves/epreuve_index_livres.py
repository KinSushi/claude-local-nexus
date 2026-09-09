import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / 'outillage'))
import nexus_index_livres as mod


def test_batch_iter_forward():
    try:
        result = list(mod.batch_iter([1, 2, 3, 4, 5], 2))
    except Exception as e:
        print('[RATE] batch_iter_forward : exception %s' % e)
        return False
    expected = [[1, 2], [3, 4], [5]]
    if result == expected:
        print('[OK  ] batch_iter_forward : %s' % result)
        return True
    print('[RATE] batch_iter_forward : unexpected result %s' % result)
    return False


def test_batch_iter_reverse():
    # Le code ne leve PAS sur une taille non entiere : len(batch) == 'a' est
    # toujours faux, tout part dans le dernier lot. C'est le comportement reel,
    # et c'est lui que l'epreuve garde -- pas une exception supposee.
    r = []
    vide = list(mod.batch_iter([], 2))
    if vide == []:
        print('[OK  ] batch_iter_reverse vide : [] -> []')
        r.append(True)
    else:
        print('[RATE] batch_iter_reverse vide : obtenu %r' % (vide,))
        r.append(False)
    un_lot = list(mod.batch_iter([1, 2], 'a'))
    if un_lot == [[1, 2]]:
        print('[OK  ] batch_iter_reverse taille non entiere : un seul lot, sans lever')
        r.append(True)
    else:
        print('[RATE] batch_iter_reverse taille non entiere : obtenu %r' % (un_lot,))
        r.append(False)
    return all(r)


def main():
    results = [test_batch_iter_forward(), test_batch_iter_reverse()]
    return 0 if all(results) else 1


if __name__ == '__main__':
    sys.exit(main())