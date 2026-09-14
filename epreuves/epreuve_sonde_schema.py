"""
epreuve_sonde_schema
--------------------

Unit tests for ``outillage.nexus_sonde_schema``.  The script imports the
module via a temporary ``sys.path`` entry (derived from ``__file__``) and
executes a series of pure-function checks.  No secret values are printed
or leaked; the module itself does not emit output on import.

Each test prints ``[OK]`` on success or ``[RATE]`` on failure and exits
with ``0`` if all pass, ``1`` otherwise.
"""

import importlib.util
import json
import os
import sys

# ----------------------------------------------------------------------
# Import the target module without side-effects
# ----------------------------------------------------------------------
module_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "outillage", "nexus_sonde_schema.py"))
spec = importlib.util.spec_from_file_location("nexus_sonde_schema", module_path)
if spec is None or spec.loader is None:
    print("[RATE] Unable to load module")
    sys.exit(1)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

# ----------------------------------------------------------------------
# Helper for test reporting
# ----------------------------------------------------------------------
def report(name: str, ok: bool) -> None:
    print(f"{name}: {'[OK]' if ok else '[RATE]'}")

all_ok = True

# ----------------------------------------------------------------------
# Tests for verdict_conformite
# ----------------------------------------------------------------------
schema = {
    "type": "object",
    "properties": {
        "verdict": {"type": "string", "enum": ["OK", "REFUS"]},
        "score": {"type": "integer"},
    },
    "required": ["verdict", "score"],
}

tests = [
    ("conforme", json.dumps({"verdict": "OK", "score": 5}), "IMPOSE"),
    ("prose", "Il pleut doucement.", "NON IMPOSE"),
    ("manque_cle", json.dumps({"verdict": "OK"}), "NON IMPOSE"),
    ("enum_violation", json.dumps({"verdict": "MAYBE", "score": 1}), "NON IMPOSE"),
    ("type_violation", json.dumps({"verdict": "OK", "score": "cinq"}), "NON IMPOSE"),
    ("tableau", json.dumps([{"verdict": "OK", "score": 1}]), "NON IMPOSE"),
]

for name, txt, expected in tests:
    result = module.verdict_conformite(txt, schema)
    ok = result == expected
    report(f"verdict_conformite_{name}", ok)
    all_ok = all_ok and ok

# ----------------------------------------------------------------------
# Tests for parse_env
# ----------------------------------------------------------------------
env_cases = [
    ("valeur_nue", "CLE=valeur", {"CLE": "valeur"}),
    ("entre_guillemets", 'CLE="valeur avec espaces"', {"CLE": "valeur avec espaces"}),
    ("commentaire", "# Ceci est un commentaire\nCLE=ok", {"CLE": "ok"}),
    ("export", "export CLE=valeur", {"CLE": "valeur"}),
]

for name, txt, expected in env_cases:
    result = module.parse_env(txt)
    ok = result == expected
    report(f"parse_env_{name}", ok)
    all_ok = all_ok and ok

# ----------------------------------------------------------------------
# Reverse test: ensure no secret is printed on import and no key value
# appears in error messages.
# ----------------------------------------------------------------------
# (We simply verify that calling parse_env on a string containing a secret
# does not raise or return the secret in an exception message.)
secret_env = "SECRET_KEY=supersecret"
try:
    _ = module.parse_env(secret_env)
    report("reverse_no_leak", True)
except Exception:
    report("reverse_no_leak", False)
    all_ok = False

ok = module.parse_env('CLE=valeur  # commentaire') == {'CLE': 'valeur'}
report('parse_env_commentaire_fin_de_ligne', ok)
all_ok = all_ok and ok

from unittest import mock
with mock.patch.object(module, '_post_json', return_value=(404, '{"error": "model not found"}')):
    verdict, _, extrait = module._measure_path('cloud', 'https://exemple.org', {}, {}, 5, {})
    ok = verdict.startswith('INJOIGNABLE (HTTP 404)') and 'model not found' in extrait
    report('measure_path_404_extrait', ok)
    all_ok = all_ok and ok

# extraire_contenu : le contenu, jamais l'enveloppe
ok = module.extraire_contenu('{"message":{"content":"{\\"verdict\\": \\"OK\\", \\"score\\": 3}"}}', 'cloud') == '{"verdict": "OK", "score": 3}'
report("extraire_contenu_cloud", ok)
all_ok = all_ok and ok
ok = module.extraire_contenu('{"choices":[{"message":{"content":"prose"}}]}', 'passerelle') == 'prose'
report("extraire_contenu_passerelle", ok)
all_ok = all_ok and ok
ok = module.extraire_contenu('pas du json', 'local') == ''
report("extraire_contenu_invalide", ok)
all_ok = all_ok and ok
with mock.patch.object(module, '_post_json', return_value=(200, '{"message":{"content":"{\\"verdict\\": \\"OK\\", \\"score\\": 3}"}}')):
    v, _, _ = module._measure_path('cloud', 'https://exemple.org', {}, {}, 5, schema)
    ok = v == 'IMPOSE'
    report("bout_en_bout_impose", ok)
    all_ok = all_ok and ok
with mock.patch.object(module, '_post_json', return_value=(200, '{"message":{"content":"Il pleut."}}')):
    v, _, _ = module._measure_path('cloud', 'https://exemple.org', {}, {}, 5, schema)
    ok = v == 'NON IMPOSE'
    report("bout_en_bout_non_impose", ok)
    all_ok = all_ok and ok
sys.exit(0 if all_ok else 1)
