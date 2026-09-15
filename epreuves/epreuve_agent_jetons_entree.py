import os
import sys
import importlib.util
from pathlib import Path
import tempfile

# ----------------------------------------------------------------------
# Pré‑configuration de l’environnement
# ----------------------------------------------------------------------
os.environ["NEXUS_GATEWAY"] = "http://127.0.0.1:9"

# Un fichier factice dans un répertoire temporaire
_tmp_dir = tempfile.TemporaryDirectory()
os.environ["NEXUS_ETAT_DISJONCTEUR"] = os.path.join(_tmp_dir.name, "etat.txt")

# ----------------------------------------------------------------------
# Chargement du module à tester
# ----------------------------------------------------------------------
racine = Path(__file__).resolve().parents[1]
module_path = racine / "scripts" / "nexus_agent.py"
spec = importlib.util.spec_from_file_location("_epreuve_jetons_entree", module_path)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)

# ----------------------------------------------------------------------
# Définition des cas de test
# ----------------------------------------------------------------------
tests = [
    # C0 – présence de la fonction
    {
        "name": "C0",
        "func": lambda: hasattr(module, "car_par_jeton_entree"),
        "expected": True,
        "args": (),
    },
    # F1 – texte simple
    {
        "name": "F1",
        "func": lambda msgs, usg: module.car_par_jeton_entree(msgs, usg),
        "messages": [
            {"role": "system", "content": "a" * 100},
            {"role": "user",   "content": "b" * 200},
        ],
        "usage": {"prompt_tokens": 100},
        "expected": 3.0,
    },
    # F2 – contenu sous forme de liste
    {
        "name": "F2",
        "func": lambda msgs, usg: module.car_par_jeton_entree(msgs, usg),
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "c" * 90},
                    {"type": "image_url", "image_url": {"url": "data:x"}},
                ],
            }
        ],
        "usage": {"prompt_tokens": 30},
        "expected": 3.0,
    },
    # R1 – usages invalides
    {
        "name": "R1a",
        "func": lambda msgs, usg: module.car_par_jeton_entree(msgs, usg),
        "messages": [{"role": "user", "content": "test"}],
        "usage": None,
        "expected": None,
    },
    {
        "name": "R1b",
        "func": lambda msgs, usg: module.car_par_jeton_entree(msgs, usg),
        "messages": [{"role": "user", "content": "test"}],
        "usage": {},
        "expected": None,
    },
    {
        "name": "R1c",
        "func": lambda msgs, usg: module.car_par_jeton_entree(msgs, usg),
        "messages": [{"role": "user", "content": "test"}],
        "usage": {"prompt_tokens": 0},
        "expected": None,
    },
    {
        "name": "R1d",
        "func": lambda msgs, usg: module.car_par_jeton_entree(msgs, usg),
        "messages": [{"role": "user", "content": "test"}],
        "usage": {"prompt_tokens": "abc"},
        "expected": None,
    },
    # R2 – messages vides
    {
        "name": "R2",
        "func": lambda msgs, usg: module.car_par_jeton_entree(msgs, usg),
        "messages": [],
        "usage": {"prompt_tokens": 10},
        "expected": None,
    },
    # R3 – messages mal formés
    {
        "name": "R3",
        "func": lambda msgs, usg: module.car_par_jeton_entree(msgs, usg),
        "messages": [
            "pas un dict",
            {"role": "user", "content": None},
            {"role": "user", "content": ["x", {"type": "text", "text": 5}]},
            {"role": "user", "content": "d" * 40},
        ],
        "usage": {"prompt_tokens": 10},
        "expected": 4.0,
    },
    # L1 – fuite de la passerelle
    {
        "name": "L1",
        "func": lambda: getattr(module, "PASSERELLE", None),
        "expected": "http://127.0.0.1:9",
        "args": (),
    },
]

# ----------------------------------------------------------------------
# Exécution des tests
# ----------------------------------------------------------------------
total_cases = 0
total_rate = 0

for test in tests:
    total_cases += 1
    name = test["name"]
    try:
        # Construction des arguments selon la présence de clés
        if "args" in test:
            observed = test["func"](*test["args"])
        else:
            observed = test["func"](test.get("messages"), test.get("usage"))
        # Comparaison (None ou valeur exacte)
        ok = observed == test["expected"]
    except Exception:
        observed = None
        ok = False

    if ok:
        print(f"[OK  ] {name} : {observed}")
    else:
        total_rate += 1
        print(f"[RATE] {name} : {observed}")

print(f"{total_cases} cas, {total_rate} RATE")
sys.exit(1 if total_rate > 0 else 0)
