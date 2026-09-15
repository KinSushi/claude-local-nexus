import os
import sys
import tempfile
import importlib.util
import types
import shutil

# ----------------------------------------------------------------------
# Helpers and safety constructions
# ----------------------------------------------------------------------
failures = 0

def check(condition, name, cause=''):
    global failures
    if condition:
        print(f'[OK] {name}')
    else:
        failures += 1
        print(f'[RATE] {name} : {cause}')

class FauxSubprocess:
    """Fake subprocess module with run and Popen that only record calls."""
    DEVNULL = object()
    CREATE_NO_WINDOW = 0x08000000  # arbitrary non‑zero value

    class TimeoutExpired(Exception):
        pass

    def __init__(self):
        self.run_calls = []
        self.popen_calls = 0

    def run(self, *args, **kwargs):
        self.run_calls.append((args, kwargs))
        # Do nothing, pretend success
        return types.SimpleNamespace(returncode=0)

    def Popen(self, *args, **kwargs):
        self.popen_calls += 1
        # Return a dummy process object with minimal interface
        return types.SimpleNamespace(pid=12345, poll=lambda: None, terminate=lambda: None)

# ----------------------------------------------------------------------
# Load the target module (outillage/nexus_veille_moteur.py)
# ----------------------------------------------------------------------
root_temp = tempfile.mkdtemp()
module_path = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__), '..', 'outillage', 'nexus_veille_moteur.py'
    )
)

spec = importlib.util.spec_from_file_location('_nexus_veille_moteur', module_path)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

# ----------------------------------------------------------------------
# Capture the real subprocess module for later safety check
# ----------------------------------------------------------------------
import subprocess as real_subprocess
ORIGINE_RUN = real_subprocess.run
ORIGINE_POPEN = real_subprocess.Popen

# ----------------------------------------------------------------------
# Replace module attributes with fakes (never touch the real modules)
# ----------------------------------------------------------------------
fake_subprocess = FauxSubprocess()
mod.subprocess = fake_subprocess
mod.time = types.SimpleNamespace(sleep=lambda s: None)
mod.platform = types.SimpleNamespace(system=lambda: 'Windows')
mod.shutil = types.SimpleNamespace(which=lambda name: r'C:\faux\ollama.exe')

# Replace auxiliary functions with lambdas (they may be missing in the original)
mod.version_repond = lambda url: False
mod.application_ollama_vivante = lambda: False
mod.nombre_serveurs_ollama = lambda: None

# ----------------------------------------------------------------------
# Install a fake winreg module in sys.modules
# ----------------------------------------------------------------------
original_winreg = sys.modules.get('winreg')
class FakeWinReg:
    HKEY_CURRENT_USER = 0x80000001
    HKEY_LOCAL_MACHINE = 0x80000002
    def OpenKey(self, *args, **kwargs):
        raise OSError('Fake winreg')
sys.modules['winreg'] = FakeWinReg()

# ----------------------------------------------------------------------
# Verify that we did not accidentally keep the real subprocess module
# ----------------------------------------------------------------------
if mod.subprocess is real_subprocess:
    print('[RATE] safety check: mod.subprocess must not be the real subprocess module')
    sys.exit(1)

# ----------------------------------------------------------------------
# Test cases
# ----------------------------------------------------------------------
def reset_popen_counter():
    fake_subprocess.popen_calls = 0

# Helper to run relancer_moteur with a fresh temporary racine
def run_relancer():
    racine = tempfile.mkdtemp()
    try:
        result = mod.relancer_moteur(racine)
    finally:
        shutil.rmtree(racine, ignore_errors=True)
    return result

# ----------------------------------------------------------------------
# F1 : application vivante, moteur répond, 1 serveur -> True, 0 Popen
# ----------------------------------------------------------------------
reset_popen_counter()
mod.application_ollama_vivante = lambda: True
mod.version_repond = lambda url: True
mod.nombre_serveurs_ollama = lambda: 1
res_f1 = run_relancer()
check(res_f1 is True and fake_subprocess.popen_calls == 0,
      'F1 application vivante, moteur répond, 1 serveur',
      f'result={res_f1}, popen_calls={fake_subprocess.popen_calls}')

# ----------------------------------------------------------------------
# F2 : application absente, moteur répond, 1 serveur -> True, 1 Popen
# ----------------------------------------------------------------------
reset_popen_counter()
mod.application_ollama_vivante = lambda: False
mod.version_repond = lambda url: True
mod.nombre_serveurs_ollama = lambda: 1
res_f2 = run_relancer()
check(res_f2 is True and fake_subprocess.popen_calls == 1,
      'F2 application absente, moteur répond, 1 serveur',
      f'result={res_f2}, popen_calls={fake_subprocess.popen_calls}')

# ----------------------------------------------------------------------
# R1 : application vivante, moteur répond, 2 serveurs -> False, 0 Popen
# ----------------------------------------------------------------------
reset_popen_counter()
mod.application_ollama_vivante = lambda: True
mod.version_repond = lambda url: True
mod.nombre_serveurs_ollama = lambda: 2
res_r1 = run_relancer()
check(res_r1 is False and fake_subprocess.popen_calls == 0,
      'R1 application vivante, moteur répond, 2 serveurs',
      f'result={res_r1}, popen_calls={fake_subprocess.popen_calls}')

# ----------------------------------------------------------------------
# R2 : application vivante, moteur répond, nombre None -> True (no block)
# ----------------------------------------------------------------------
reset_popen_counter()
mod.application_ollama_vivante = lambda: True
mod.version_repond = lambda url: True
mod.nombre_serveurs_ollama = lambda: None
res_r2 = run_relancer()
check(res_r2 is True,
      'R2 application vivante, moteur répond, nombre None',
      f'result={res_r2}')

# ----------------------------------------------------------------------
# R3 : application vivante, moteur ne répond jamais -> False, 0 Popen
# ----------------------------------------------------------------------
reset_popen_counter()
mod.application_ollama_vivante = lambda: True
mod.version_repond = lambda url: False
mod.nombre_serveurs_ollama = lambda: 1
res_r3 = run_relancer()
check(res_r3 is False and fake_subprocess.popen_calls == 0,
      'R3 application vivante, moteur ne répond jamais',
      f'result={res_r3}, popen_calls={fake_subprocess.popen_calls}')

# ----------------------------------------------------------------------
# S1 : safety – ensure real subprocess.run was never called
# ----------------------------------------------------------------------
# Vérification que les objets capturés avant le premier cas sont intacts
check(real_subprocess.run is ORIGINE_RUN and real_subprocess.Popen is ORIGINE_POPEN,
      'S1 surete : vrais subprocess.run et Popen intacts',
      'le vrai module subprocess a ete modifie')

# ----------------------------------------------------------------------
# Cleanup
# ----------------------------------------------------------------------
if original_winreg is not None:
    sys.modules['winreg'] = original_winreg
else:
    del sys.modules['winreg']

shutil.rmtree(root_temp, ignore_errors=True)

sys.exit(1 if failures else 0)
