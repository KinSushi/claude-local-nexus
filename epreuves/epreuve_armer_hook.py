import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / 'outillage'))
import nexus_armer_hook as mod


def test_find_groups_by_command_forward():
    settings = {
        'hooks': {
            'PreToolUse': [
                {'matcher': 'A', 'hooks': [{'type': 'command', 'command': 'run nexus_garde_agent now'}]},
                {'matcher': 'B', 'hooks': [{'type': 'command', 'command': 'do something else'}]},
                {'matcher': 'C', 'hooks': [{'type': 'command', 'command': 'nexus_garde_agent extra'}]},
            ]
        }
    }
    expected = [settings['hooks']['PreToolUse'][0], settings['hooks']['PreToolUse'][2]]
    result = mod.find_groups_by_command(settings, 'nexus_garde_agent')
    if result == expected:
        print('[OK  ] find_groups_by_command_forward : les 2 groupes citant la commande')
        return True
    print('[RATE] find_groups_by_command_forward : unexpected result %r' % (result,))
    return False


def test_find_groups_by_command_reverse():
    result = mod.find_groups_by_command(None, 'any')
    if result == []:
        print('[OK  ] find_groups_by_command_reverse : settings None -> liste vide')
        return True
    print('[RATE] find_groups_by_command_reverse : attendu [] obtenu %r' % (result,))
    return False


def main():
    results = [test_find_groups_by_command_forward(), test_find_groups_by_command_reverse()]
    return 0 if all(results) else 1


if __name__ == '__main__':
    sys.exit(main())