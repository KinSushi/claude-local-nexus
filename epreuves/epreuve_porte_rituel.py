import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / 'outillage'))
import nexus_porte_rituel as mod


def _cas(nom, fn, attendu):
    try:
        result = fn()
    except Exception as e:
        print('[RATE] %s : raised %s' % (nom, e))
        return False
    if result == attendu:
        print('[OK  ] %s : ok' % nom)
        return True
    print('[RATE] %s : unexpected %r' % (nom, result))
    return False


def test_should_block_forward():
    verdict = {"controles": [
        {"nom": "travail commite", "statut": "MANQUE", "detail": "fichier1"},
        {"nom": "autre", "statut": "OK"},
    ]}
    return _cas('should_block_forward (travail commite MANQUE)', lambda: mod._should_block(verdict), (True, "fichier1"))


def test_should_block_reverse():
    verdict = {"controles": [
        {"nom": "travail commite", "statut": "OK", "detail": "ok"},
        {"nom": "autre", "statut": "MANQUE"},
    ]}
    return _cas('should_block_reverse (un autre MANQUE ne bloque pas)', lambda: mod._should_block(verdict), (False, ""))


def test_actionable_message_forward():
    expected = (
        "Fichiers non commites: %s. "
        "Commande: git add -A && git commit -m 'Commit avant cloture du tour'. "
        "Refus restants avant autorisation: %d. "
        "Escalade: definir NEXUS_AGENT_LIBRE=1."
    ) % ("fichierX", 2)
    return _cas('actionable_message_forward', lambda: mod._actionable_message("fichierX", 2), expected)


def test_actionable_message_reverse():
    class BadStr(object):
        def __str__(self):
            raise ValueError("bad str")
    try:
        mod._actionable_message(BadStr(), 1)
    except Exception:
        print('[OK  ] actionable_message_reverse : exception correctly raised')
        return True
    print('[RATE] actionable_message_reverse : no exception raised')
    return False


def test_epreuve_mode_forward_allow():
    return _cas('epreuve_mode allow', lambda: mod._epreuve_mode('{"controles": []}'),
                '{"decision": "allow", "reason": "Aucun blocage requis"}')


def test_epreuve_mode_forward_block():
    expected = (
        '{"decision": "block", "reason": "Fichiers non commites: fileY. '
        "Commande: git add -A && git commit -m 'Commit avant cloture du tour'. "
        'Refus restants avant autorisation: 2. Escalade: definir NEXUS_AGENT_LIBRE=1."}'
    )
    return _cas('epreuve_mode block', lambda: mod._epreuve_mode(
        '{"controles": [{"nom": "travail commite", "statut": "MANQUE", "detail": "fileY"}]}'), expected)


def test_epreuve_mode_reverse_invalid_json():
    return _cas('epreuve_mode json invalide -> vide', lambda: mod._epreuve_mode('not a json'), "")


def main():
    tests = [
        test_should_block_forward,
        test_should_block_reverse,
        test_actionable_message_forward,
        test_actionable_message_reverse,
        test_epreuve_mode_forward_allow,
        test_epreuve_mode_forward_block,
        test_epreuve_mode_reverse_invalid_json,
    ]
    results = [t() for t in tests]
    return 0 if all(results) else 1


if __name__ == '__main__':
    sys.exit(main())