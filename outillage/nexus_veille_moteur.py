"""Monitor Ollama runner health and optionally restart it.

Based on measurement from 2026-09-14 (Ollama 0.34.0, Vulkan on AMD Radeon 890M iGPU):
twice in 30 minutes a 19-20 GB model stayed in 'Stopping...' for tens of minutes;
/api/version responded but any inference (even a 1 GB model) remained silent;
only a service restart unblocked. Known Ollama bug (runner never exits, GPU busy without work).

This tool does NOT measure system load or memory usage; see nexus_charge for that.
"""

import argparse
import datetime
import json
import os
import platform
import shutil
import subprocess
import sys
import time
import urllib.request
import urllib.error

def _parse_iso(iso_str):
    """Parse ISO 8601 string, handling trailing Z and long fractions."""
    if iso_str.endswith('Z'):
        iso_str = iso_str[:-1] + '+00:00'
    # Truncate fractional seconds to 6 digits if longer
    if '.' in iso_str:
        base, frac = iso_str.split('.', 1)
        # frac may contain timezone offset after digits
        digits = ''
        tz = ''
        for i, ch in enumerate(frac):
            if ch.isdigit():
                digits += ch
            else:
                tz = frac[i:]
                break
        if len(digits) > 6:
            digits = digits[:6]
        iso_str = base + '.' + digits + tz
    return datetime.datetime.fromisoformat(iso_str)

def coince(ps, maintenant_iso, seuil_s):
    """Return list of models whose expires_at is older than maintenant by more than seuil_s seconds."""
    maintenant = _parse_iso(maintenant_iso)
    coinces = []
    for model in ps.get('models', []):
        expires_str = model.get('expires_at')
        if not expires_str:
            continue
        try:
            expires = _parse_iso(expires_str)
        except Exception:
            continue
        delta = (maintenant - expires).total_seconds()
        if delta > seuil_s:
            coinces.append({
                'nom': model.get('name', '?'),
                'taille_go': model.get('size', 0) / (1024 ** 3),
                'depuis_s': delta
            })
    return coinces

def verdict(coinces, sonde_ok, journal_avance=None):
    """Return health verdict based on stuck models, probe result and journal liveness."""
    if journal_avance is None:
        # legacy rule when journal is absent
        if coinces and sonde_ok is False:
            return 'BLOQUE'
        if (coinces and sonde_ok is None) or (coinces and sonde_ok is True) or (not coinces and sonde_ok is False):
            return 'SUSPECT'
        return 'SAIN'
    # new rule with journal liveness signal
    if coinces and sonde_ok is False:
        if journal_avance is False:
            return 'BLOQUE'
        # journal_avance is True
        return 'SUSPECT'
    if (coinces and sonde_ok is None) or (coinces and sonde_ok is True) or (not coinces and sonde_ok is False):
        return 'SUSPECT'
    return 'SAIN'

def version_repond(url):
    """Return True if GET /api/version succeeds within 5 seconds."""
    try:
        with urllib.request.urlopen(url + '/api/version', timeout=5) as resp:
            return resp.status == 200
    except Exception:
        return False

def lire_ps(url):
    """Return dict from GET /api/ps, or {} on any error."""
    try:
        with urllib.request.urlopen(url + '/api/ps', timeout=5) as resp:
            if resp.status == 200:
                return json.loads(resp.read().decode('utf-8'))
    except Exception:
        pass
    return {}

def sonder(url, modele, delai):
    """Return True if POST /api/chat with tiny prompt succeeds within delai seconds."""
    body = {
        "model": modele,
        "messages": [{"role": "user", "content": "ping"}],
        "stream": False,
        "options": {"num_predict": 4}
    }
    data = json.dumps(body).encode('utf-8')
    req = urllib.request.Request(url + '/api/chat', data=data, headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=delai) as resp:
            return resp.status == 200
    except Exception:
        return False

def relancer_moteur(racine):
    """Restart Ollama service on Windows. Return True if engine responds within 30s."""
    if platform.system() != 'Windows':
        print('relance non implementee sur cette plateforme')
        return False

    import winreg

    # Copy OLLAMA_* environment variables from registry
    reg_paths = [
        (winreg.HKEY_CURRENT_USER, r'Environment'),
        (winreg.HKEY_LOCAL_MACHINE, r'SYSTEM\CurrentControlSet\Control\Session Manager\Environment')
    ]
    for hkey, subkey in reg_paths:
        try:
            with winreg.OpenKey(hkey, subkey) as key:
                i = 0
                while True:
                    try:
                        name, value, _ = winreg.EnumValue(key, i)
                        if name.startswith('OLLAMA_'):
                            os.environ[name] = str(value)
                        i += 1
                    except OSError:
                        break
        except OSError:
            pass

    # Locate ollama executable
    ollama = shutil.which('ollama')
    if not ollama:
        local_app_data = os.environ.get('LOCALAPPDATA', '')
        candidate = os.path.join(local_app_data, 'Programs', 'Ollama', 'ollama.exe')
        if os.path.exists(candidate):
            ollama = candidate
    if not ollama:
        return False

    # Kill existing process
    subprocess.run(['taskkill', '/IM', 'ollama.exe', '/F', '/T'],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(3)

    # Prepare log directory
    logs_dir = os.path.join(racine, 'logs')
    os.makedirs(logs_dir, exist_ok=True)
    out_log = os.path.join(logs_dir, 'ollama-serve.out.log')
    err_log = os.path.join(logs_dir, 'ollama-serve.err.log')

    # Start new process
    creationflags = 0x00000008 | 0x00000200  # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
    with open(out_log, 'a') as out_f, open(err_log, 'a') as err_f:
        subprocess.Popen([ollama, 'serve'],
                         stdout=out_f, stderr=err_f,
                         creationflags=creationflags,
                         cwd=racine)

    # Wait for engine to respond (up to 30 seconds)
    for _ in range(30):
        if version_repond('http://127.0.0.1:11434'):
            return True
        time.sleep(1)
    return False

def purger_orphelins(cible='llama-server.exe', module=None):
    """Termine les processus orphelins ``cible`` laisses apres l'arret d'ollama.exe.

    Sans l'option /T de taskkill, des llama-server.exe restaient vivants apres
    la relance du moteur (4 cas mesures, 68 Go d'engagement, 2026-09-14).
    Rend la liste des processus termines : [{'pid': ..., 'prive_octets': ...}].
    Si ``module`` est fourni (epreuve), il est employe tel quel ; sinon
    scripts/nexus_orphelins.py est charge par chemin derive de __file__, sans
    inscription dans sys.modules. Absent, ou en erreur : liste vide, jamais
    d'exception, car une purge qui plante bloquerait la relance qu'elle sert.
    """
    import importlib.util

    if module is None:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        script_path = os.path.join(base_dir, 'scripts', 'nexus_orphelins.py')
        if not os.path.isfile(script_path):
            return []
        try:
            spec = importlib.util.spec_from_file_location('_nexus_orphelins', script_path)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
        except Exception:
            return []
    else:
        mod = module

    try:
        table = mod.enumerer()
        orps = mod.orphelins(table, cible)
    except Exception:
        return []

    result = []
    for o in orps:
        pid = o.get('pid')
        if pid is None:
            continue
        try:
            mod._terminer(pid)
            result.append({'pid': pid, 'prive_octets': o.get('prive_octets')})
        except Exception:
            pass
    return result


def executer(url, modele_sonde, delai_sonde, seuil_stopping, relancer, journal=None):
    """Run health check and optionally restart if BLOQUE.

    journal: path to engine log file. If provided, its size/mtime is sampled
    before and after the probe to determine if the engine is still writing.
    """
    result = {
        'coinces': [],
        'sonde_ok': None,
        'verdict': 'INJOIGNABLE',
        'relance': None,
        'journal_avance': None,
        'orphelins_tues': []
    }

    if not version_repond(url):
        return result

    ps = lire_ps(url)
    maintenant = datetime.datetime.now(datetime.timezone.utc).isoformat()
    coinces = coince(ps, maintenant, seuil_stopping)

    # Measure journal before probe
    journal_avance = None
    journal_existait = False
    taille_avant = None
    mtime_avant = None
    if journal:
        if os.path.exists(journal):
            try:
                stat_avant = os.stat(journal)
                taille_avant = stat_avant.st_size
                mtime_avant = stat_avant.st_mtime_ns
                journal_existait = True
            except OSError:
                journal_existait = False
        # else: journal_existait remains False

    sonde_ok = sonder(url, modele_sonde, delai_sonde)

    # Measure journal after probe if it existed before
    if journal and journal_existait:
        if os.path.exists(journal):
            try:
                stat_apres = os.stat(journal)
                if stat_apres.st_size != taille_avant or stat_apres.st_mtime_ns != mtime_avant:
                    journal_avance = True
                else:
                    journal_avance = False
            except OSError:
                journal_avance = False
        else:
            journal_avance = False

    result['coinces'] = coinces
    result['sonde_ok'] = sonde_ok
    result['journal_avance'] = journal_avance
    result['verdict'] = verdict(coinces, sonde_ok, journal_avance)

    if relancer and result['verdict'] == 'BLOQUE':
        racine = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        result['orphelins_tues'] = purger_orphelins()
        result['relance'] = relancer_moteur(racine)
        if result['relance'] is False:
            result['verdict'] = 'BLOQUE'  # remains BLOQUE if restart failed
    return result

def main():
    parser = argparse.ArgumentParser(description='Monitor Ollama runner health.')
    parser.add_argument('--url', default='http://127.0.0.1:11434')
    parser.add_argument('--modele-sonde', default='llama3.2:1b')
    parser.add_argument('--delai-sonde', type=int, default=75, help='delai de la sonde en secondes ; 25 s expirait sous charge normale (mesure 2026-09-14), 75 s laisse passer une inference de 20 Go devant la sonde')
    parser.add_argument('--seuil-stopping', type=float, default=120)
    parser.add_argument('--relancer', action='store_true')
    parser.add_argument('--json', action='store_true')
    racine_defaut = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    journal_defaut = os.path.join(racine_defaut, 'logs', 'ollama-serve.err.log')
    parser.add_argument('--journal', default=journal_defaut, help='chemin du journal du moteur pour mesurer la vivacite')
    args = parser.parse_args()

    result = executer(args.url, args.modele_sonde, args.delai_sonde, args.seuil_stopping, args.relancer, journal=args.journal)

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        for c in result['coinces']:
            print(f"{c['nom']} : {c['taille_go']:.2f} Go, expire depuis {c['depuis_s']:.0f} s")
        if result['sonde_ok'] is True:
            print('sonde : ok')
        elif result['sonde_ok'] is False:
            print(f'sonde : muette apres {args.delai_sonde} s')
        else:
            print('sonde : non faite')
        if result['journal_avance'] is True:
            print('journal a avance pendant la sonde : oui')
        elif result['journal_avance'] is False:
            print('journal a avance pendant la sonde : non')
        else:
            print('journal a avance pendant la sonde : absent')
        print(f"verdict : {result['verdict']}")
        if result['relance'] is True:
            print('moteur relance')
        elif result['relance'] is False:
            print('relance ratee')

    code = 0
    if result['verdict'] == 'SUSPECT':
        code = 1
    elif result['verdict'] == 'INJOIGNABLE':
        code = 2
    elif result['verdict'] == 'BLOQUE':
        code = 3
    sys.exit(code)

if __name__ == '__main__':
    main()
