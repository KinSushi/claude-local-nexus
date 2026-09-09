import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / 'scripts'))
import nexus_garde_edition as mod


def _run_test(name, inp, expected):
    try:
        result = mod.chemin_ecrit(inp)
    except Exception as e:
        print('[RATE] %s : exception %s' % (name, e))
        return False
    if result == expected:
        print('[OK  ] %s : ok' % name)
        return True
    print('[RATE] %s : got %r expected %r' % (name, result, expected))
    return False


def main():
    all_ok = True
    all_ok = _run_test('chemin_ecrit_forward_tool_response',
                       {'tool_response': {'filePath': 'script.py'}}, 'script.py') and all_ok
    all_ok = _run_test('chemin_ecrit_forward_tool_input',
                       {'tool_input': {'file_path': 'module.py'}}, 'module.py') and all_ok
    all_ok = _run_test('chemin_ecrit_reverse_missing_fields',
                       {'other': {'nope': 'value'}}, '') and all_ok
    all_ok = _run_test('chemin_ecrit_reverse_non_dict', 12345, '') and all_ok
    all_ok = _run_test('chemin_ecrit_reverse_empty_string',
                       {'tool_response': {'filePath': '   '}}, '') and all_ok
    return 0 if all_ok else 1


if __name__ == '__main__':
    sys.exit(main())