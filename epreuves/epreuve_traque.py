"""Epreuve de nexus_traque : _texte et _charge_de_refus, sur des noeuds AST construits."""
import ast
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / 'outillage'))
import nexus_traque as nt


def _appel(*args):
    return ast.Call(func=ast.Name(id='print', ctx=ast.Load()), args=list(args), keywords=[])


def _portee(nom, valeur):
    assign = ast.Assign(targets=[ast.Name(id=nom, ctx=ast.Store())], value=valeur)
    return ast.Module(body=[assign], type_ignores=[])


def test_texte_forward():
    call_node = _appel(ast.Constant(value='hello'), ast.Constant(value='world'), ast.Constant(value=123))
    try:
        result = nt._texte(call_node)
        if result == 'hello world':
            print('[OK  ] _texte forward : seules les chaines litterales sont jointes')
            return True
        print('[RATE] _texte forward : rendu %r' % result)
        return False
    except Exception as e:
        print('[RATE] _texte forward : exception %s' % e)
        return False


def test_texte_reverse():
    call_node = _appel(ast.Constant(value=1), ast.Constant(value=False))
    try:
        result = nt._texte(call_node)
        if result == '':
            print('[OK  ] _texte reverse : aucune chaine -> chaine vide')
            return True
        print('[RATE] _texte reverse : attendu chaine vide, rendu %r' % result)
        return False
    except Exception as e:
        print('[RATE] _texte reverse : exception %s' % e)
        return False


def test_charge_de_refus_forward():
    appel = _appel(ast.Name(id='payload', ctx=ast.Load()))
    valeur = ast.Dict(keys=[ast.Constant(value='permissionDecision')], values=[ast.Constant(value='deny')])
    try:
        result = nt._charge_de_refus(appel, _portee('payload', valeur))
        if result is True:
            print('[OK  ] _charge_de_refus forward : la variable imprimee porte un refus')
            return True
        print('[RATE] _charge_de_refus forward : attendu True, rendu %r' % result)
        return False
    except Exception as e:
        print('[RATE] _charge_de_refus forward : exception %s' % e)
        return False


def test_charge_de_refus_reverse():
    appel = _appel(ast.Name(id='x', ctx=ast.Load()))
    try:
        result = nt._charge_de_refus(appel, _portee('x', ast.Constant(value=42)))
        if result is False:
            print('[OK  ] _charge_de_refus reverse : valeur sans refus -> False')
            return True
        print('[RATE] _charge_de_refus reverse : attendu False, rendu %r' % result)
        return False
    except Exception as e:
        print('[RATE] _charge_de_refus reverse : exception %s' % e)
        return False


def main():
    results = [
        test_texte_forward(),
        test_texte_reverse(),
        test_charge_de_refus_forward(),
        test_charge_de_refus_reverse(),
    ]
    return 0 if all(results) else 1


if __name__ == '__main__':
    sys.exit(main())