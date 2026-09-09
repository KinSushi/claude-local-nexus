import ast
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
CIBLE = RACINE / 'outillage' / 'nexus_vitrine.py'


def _ok(nom, detail):
    print('[OK  ] %s : %s' % (nom, detail))


def _rate(nom, detail):
    print('[RATE] %s : %s' % (nom, detail))


def main():
    success = True
    try:
        source = CIBLE.read_text(encoding='utf-8')
    except Exception as e:
        _rate('lecture_fichier', 'Impossible de lire %s: %s' % (CIBLE, e))
        return 1

    try:
        tree = ast.parse(source, filename=str(CIBLE))
    except SyntaxError as e:
        _rate('syntax_error', 'Erreur de syntaxe dans %s: %s' % (CIBLE, e))
        return 1

    # script name -> troisieme argument attendu. Une chaine => on attend un
    # ast.Attribute portant ce .attr. False => on attend la constante False.
    expected = {
        'nexus_test.py': 'sauf_tests',
        'nexus_conformite.py': False,
        'nexus_rituel.py': False,
    }
    found = dict.fromkeys(expected, False)

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue

        func = node.func
        is_target = False
        if isinstance(func, ast.Name) and func.id == 'sous_controle' or isinstance(func, ast.Attribute) and func.attr == 'sous_controle':
            is_target = True
        if not is_target:
            continue

        if len(node.args) < 3:
            _rate('arguments_insuffisants', 'sous_controle appele avec moins de 3 arguments')
            success = False
            continue

        script_arg = node.args[1]
        if not isinstance(script_arg, ast.Constant) or not isinstance(script_arg.value, str):
            _rate('script_non_constant', 'le deuxieme argument n est pas une chaine constante')
            success = False
            continue

        script_name = script_arg.value
        if script_name not in expected:
            continue

        found[script_name] = True
        third_arg = node.args[2]
        expected_val = expected[script_name]

        if isinstance(expected_val, str):
            if isinstance(third_arg, ast.Attribute) and third_arg.attr == expected_val:
                _ok('sous_controle_%s' % script_name, 'troisieme argument est l attribut .%s' % expected_val)
            else:
                _rate('sous_controle_%s' % script_name, 'troisieme argument doit etre l attribut .%s' % expected_val)
                success = False
        else:
            if isinstance(third_arg, ast.Constant) and third_arg.value is False:
                _ok('sous_controle_%s' % script_name, 'troisieme argument est la constante False')
            else:
                _rate('sous_controle_%s' % script_name, 'troisieme argument doit etre la constante False')
                success = False

    for script_name, was_found in found.items():
        if not was_found:
            _rate('sous_controle_%s' % script_name, 'appel manquant ou structure modifiee')
            success = False

    return 0 if success else 1


if __name__ == '__main__':
    sys.exit(main())