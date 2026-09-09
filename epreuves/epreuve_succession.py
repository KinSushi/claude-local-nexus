import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / 'scripts'))

import nexus_succession as ns


def _ok(nom, detail):
    print('[OK  ] %s : %s' % (nom, detail))


def _rate(nom, detail):
    print('[RATE] %s : %s' % (nom, detail))


def main():
    tests = [
        {
            'disponibilites': {'opus': True, 'fable': False, 'cloud': False, 'local': False},
            'sensibilite': 'L0',
            'niveau_attendu': 'opus',
        },
        {
            'disponibilites': {'opus': False, 'fable': True, 'cloud': False, 'local': False},
            'sensibilite': 'L0',
            'niveau_attendu': 'fable',
        },
        {
            'disponibilites': {'opus': False, 'fable': False, 'cloud': True, 'local': False},
            'sensibilite': 'L0',
            'niveau_attendu': 'cloud',
        },
        {
            'disponibilites': {'opus': False, 'fable': False, 'cloud': False, 'local': True},
            'sensibilite': 'L0',
            'niveau_attendu': 'local',
        },
        {
            'disponibilites': {'opus': False, 'fable': False, 'cloud': False, 'local': False},
            'sensibilite': 'L0',
            'niveau_attendu': None,
        },
        {
            'disponibilites': {'opus': False, 'fable': False, 'cloud': True, 'local': True},
            'sensibilite': 'L2',
            'niveau_attendu': 'local',
        },
        {
            'disponibilites': {'opus': True, 'fable': True, 'cloud': True, 'local': True},
            'sensibilite': 'L3',
            'niveau_attendu': 'local',
        },
        {
            'disponibilites': {'opus': False, 'fable': False, 'cloud': False},
            'sensibilite': 'L0',
            'niveau_attendu': 'local',
        },
        {
            'disponibilites': {'opus': False, 'fable': False, 'cloud': True, 'local': True},
            'sensibilite': 'L1',
            'niveau_attendu': 'cloud',
        },
        {
            'disponibilites': {'opus': False, 'fable': False, 'cloud': True, 'local': True},
            'sensibilite': 'L2',
            'niveau_attendu': 'local',
        },
    ]

    all_ok = True
    for idx, cas in enumerate(tests, 1):
        dispo = cas['disponibilites']
        sens = cas['sensibilite']
        attendu = cas['niveau_attendu']
        resultat = ns.decider(dispo, sens)
        obtenu = resultat.get('niveau')
        nom_test = 'test_%d_%s' % (idx, sens)
        if obtenu == attendu:
            _ok(nom_test, 'niveau=%s' % obtenu)
        else:
            _rate(nom_test, 'attendu=%s, obtenu=%s' % (attendu, obtenu))
            all_ok = False

    return 0 if all_ok else 1


if __name__ == '__main__':
    sys.exit(main())