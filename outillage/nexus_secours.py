#!/usr/bin/env python3
"""nexus_secours - diagnostic de secours pour le moteur d'inference local.

Ce script verifie trois points :

1. Accessibilite du moteur local et etat des modeles residents.
2. Liste des modeles disponibles et ceux charges en memoire.
3. Conformite du point d'entree /v1/messages du protocole proprietaire.

Il ne modifie aucune configuration et ne plante jamais.
Code de retour :
0  - une voie de secours existe (moteur joignable, avec ou sans modeles).
1  - moteur joignable mais aucune reponse valide du point d'entree.
2  - moteur injoignable.
"""
import sys
import os
import json
import argparse
import urllib.request
import urllib.error
import time

def _print_step(title):
    print()
    print("=== %s ===" % title)

def _http_get(url, timeout):
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return resp.getcode(), resp.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()
    except Exception as e:
        return None, str(e).encode('utf-8')

def _http_post(url, data, timeout, extra_headers=None):
    headers = {'Content-Type': 'application/json'}
    if extra_headers:
        headers.update(extra_headers)
    req = urllib.request.Request(url, data=data, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.getcode(), resp.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()
    except Exception as e:
        return None, str(e).encode('utf-8')

def _is_embedding(name):
    n = name.lower()
    if 'embed' in n or 'minilm' in n or 'bge' in n:
        return True
    for sep in [' ', ':', '/', '_', '-', '.']:
        if (' e5 ' if ' ' in n else f'{sep}e5{sep}') in n or n.startswith('e5' + sep) or n.endswith(sep + 'e5'):
            return True
    return False

def main():
    parser = argparse.ArgumentParser(description='Diagnostic de secours du moteur d\'inference local')
    parser.add_argument('--model', help='Nom du modele a tester (facultatif)', default=None)
    parser.add_argument('--timeout', type=int, help='Delai maximal en secondes pour chaque requete', default=240)
    args = parser.parse_args()

    base_url = os.environ.get('NEXUS_INFERENCE_URL', 'http://localhost:11434')
    base_url = base_url.rstrip('/')
    tags_endpoint = base_url + '/api/tags'
    ps_endpoint = base_url + '/api/ps'
    msg_endpoint = base_url + '/v1/messages'

    _print_step('Etape 1 - Accessibilite du moteur')
    code, _ = _http_get(ps_endpoint, args.timeout)
    if code == 200:
        try:
            with urllib.request.urlopen(ps_endpoint, timeout=args.timeout) as resp:
                data = json.loads(resp.read().decode('utf-8'))
        except Exception as e:
            print('Erreur lors du decodage de la reponse du moteur : %s' % e)
            print('Statut : joignable, etat des modeles inconnu')
            engine_state = 'joignable_inconnu'
        else:
            models = data.get('models', [])
            if not models:
                print('Moteur joignable, aucun modele resident.')
                engine_state = 'joignable_sans_modeles'
            else:
                print('Moteur joignable, %d modele(s) resident(s).' % len(models))
                engine_state = 'joignable_avec_modeles'
    else:
        print('Moteur injoignable (code HTTP %s).' % (code if code is not None else 'aucun'))
        engine_state = 'injoignable'

    _print_step('Etape 2 - Inventaire des modeles')
    available_models = []
    resident_models = []
    if engine_state.startswith('joignable'):
        try:
            with urllib.request.urlopen(tags_endpoint, timeout=args.timeout) as resp:
                t_data = json.loads(resp.read().decode('utf-8'))
                available_models = [m.get('name') for m in t_data.get('models', [])]
            with urllib.request.urlopen(ps_endpoint, timeout=args.timeout) as resp:
                p_data = json.loads(resp.read().decode('utf-8'))
                resident_models = [m.get('name') for m in p_data.get('models', [])]
            conv_residents = [m for m in resident_models if not _is_embedding(m)]
            print('Modeles installes: %d ; Modeles residents: %d (dont %d capables de conversation)' % (len(available_models), len(resident_models), len(conv_residents)))
        except Exception as e:
            print('Impossible d\'obtenir la liste des modeles : %s' % e)
    else:
        print('Moteur injoignable - impossible d\'interroger les modeles.')

    _print_step('Etape 3 - Test du point d\'entree /v1/messages')
    default_model = args.model
    if not default_model:
        conv_residents = [m for m in resident_models if not _is_embedding(m)]
        if conv_residents:
            default_model = conv_residents[0]
        else:
            conv_available = [m for m in available_models if not _is_embedding(m)]
            if conv_available:
                default_model = conv_available[0]
                print('Avertissement : le modele choisi n\'est pas resident, son chargement prendra du temps.')

    if not default_model:
        print('Aucun modele capable de conversation disponible pour le test.')
        backup_available = False
    else:
        payload = {'model': default_model, 'messages': [{'role': 'user', 'content': 'ping'}], 'max_tokens': 32}
        payload_bytes = json.dumps(payload).encode('utf-8')
        headers_prop = {'anthropic-version': '2023-06-01'}
        start = time.time()
        code, resp = _http_post(msg_endpoint, payload_bytes, args.timeout, extra_headers=headers_prop)
        elapsed = time.time() - start

        if code == 200:
            try:
                json.loads(resp.decode('utf-8'))
                print('Reponse valide recue en %.2f secondes.' % elapsed)
                print('ANTHROPIC_BASE_URL="%s"' % base_url)
                print('ANTHROPIC_AUTH_TOKEN="local"')
                print('Le modele employe est indique par une troisieme variable si le client le permet : %s' % default_model)
                print('Avertissement : cette voie a ete verifiee au niveau du PROTOCOLE seulement, et l usage complet du client avec ses outils n a pas ete eprouve.')
                backup_available = True
            except Exception as e:
                print('Reponse 200 mais decodage JSON echec : %s' % e)
                backup_available = False
        elif code is None:
            print('Resultat NON CONCLUANT : expiration du delai (timeout). La machine est peut-etre lente ou chargee. Relancer machine au repos.')
            backup_available = False
        else:
            print('Echec du test du point d\'entree : refus du serveur (code HTTP %s).' % code)
            backup_available = False

    exit_code = 2 if engine_state == 'injoignable' else (0 if backup_available else 1)
    sys.exit(exit_code)

if __name__ == '__main__':
    main()
