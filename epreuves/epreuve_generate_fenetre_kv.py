import sys
import importlib.util
from pathlib import Path

# ----------------------------------------------------------------------
# Chargement du module à tester
racine = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "_epreuve_fenetre_kv", racine / "scripts" / "nexus_generate.py"
)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)

# ----------------------------------------------------------------------
# Constantes attendues
PLAFOND_FENETRE = 65536
FENETRE_MIN = 4096
NUM_PREDICT_MIN = 4096
NUM_PREDICT_MAX = 32768
MARGE_CALCUL_GO = 2.0

# ----------------------------------------------------------------------
# Fixtures (texte réel de `ollama show -v`)
QWEN = (
    "  Model\n"
    "    architecture        qwen3moe    \n"
    "\n"
    "  Parameters\n"
    "    general.architecture                          qwen3moe    \n"
    "    qwen3moe.attention.head_count                 32          \n"
    "    qwen3moe.attention.head_count_kv              4           \n"
    "    qwen3moe.attention.key_length                 128         \n"
    "    qwen3moe.attention.value_length               128         \n"
    "    qwen3moe.block_count                          48          \n"
    "    qwen3moe.context_length                       262144      \n"
    "    qwen3moe.embedding_length                     2048        \n"
)

PHI = (
    "    general.architecture                 phi2        \n"
    "    phi2.attention.head_count            32          \n"
    "    phi2.attention.head_count_kv         32          \n"
    "    phi2.block_count                     32          \n"
    "    phi2.context_length                  2048        \n"
    "    phi2.embedding_length                2560        \n"
)

# ----------------------------------------------------------------------
# Collecte des résultats
total_cases = 0
rate_cases = 0
rate_messages = []

def record_success(name):
    global total_cases
    total_cases += 1
    # Mesure du 2026-09-15 : une epreuve muette en vert etait refusee par le lanceur
    print(f"[OK  ] {name} : conforme")

def record_rate(name, exc):
    global total_cases, rate_cases
    total_cases += 1
    rate_cases += 1
    rate_messages.append(f"[RATE] {name} : {type(exc).__name__} {exc}")

# ----------------------------------------------------------------------
# C0 – Contre‑épreuve : existence des fonctions
def test_existence():
    required = [
        "lire_architecture",
        "octets_kv_par_jeton",
        "fenetre_par_memoire",
        "num_predict_pour",
    ]
    missing = [n for n in required if not hasattr(module, n)]
    if missing:
        raise AssertionError(f"fonctions manquantes : {missing}")

# ----------------------------------------------------------------------
# F1 – Lire architecture QWEN
def test_f1():
    arch = module.lire_architecture(QWEN)
    if arch is None:
        raise AssertionError("arch is None")
    expected = {
        "block_count": 48,
        "head_count_kv": 4,
        "key_length": 128,
        "value_length": 128,
        "context_length": 262144,
    }
    for k, v in expected.items():
        if arch.get(k) != v:
            raise AssertionError(f"{k}={arch.get(k)} != {v}")

# ----------------------------------------------------------------------
# F2 – Octets KV pour QWEN
def test_f2():
    arch = module.lire_architecture(QWEN)
    result = module.octets_kv_par_jeton(arch)
    if result != 98304:
        raise AssertionError(f"result={result} != 98304")

# ----------------------------------------------------------------------
# F3 – Octets KV pour PHI (sans key_length)
def test_f3():
    arch = module.lire_architecture(PHI)
    result = module.octets_kv_par_jeton(arch)
    if result != 327680:
        raise AssertionError(f"result={result} != 327680")

# ----------------------------------------------------------------------
# F4 – Fenêtre par mémoire (cas plafond)
def test_f4():
    result = module.fenetre_par_memoire(98304, 18.6, 66.2)
    if result != PLAFOND_FENETRE:
        raise AssertionError(f"result={result} != {PLAFOND_FENETRE}")

# ----------------------------------------------------------------------
# F5 – Numéro de prédiction
def test_f5():
    if module.num_predict_pour(65536) != 16384:
        raise AssertionError("num_predict_pour(65536) != 16384")
    if module.num_predict_pour(8192) != 4096:
        raise AssertionError("num_predict_pour(8192) != 4096")
    if module.num_predict_pour(262144) != NUM_PREDICT_MAX:
        raise AssertionError("num_predict_pour(262144) != 32768")

# ----------------------------------------------------------------------
# R1 – Entrées non‑architecturales
def test_r1():
    if module.lire_architecture("texte sans architecture") is not None:
        raise AssertionError("expected None for unknown text")
    if module.lire_architecture(None) is not None:
        raise AssertionError("expected None for None input")

# ----------------------------------------------------------------------
# R2 – Poids au‑delà du budget
def test_r2():
    result = module.fenetre_par_memoire(98304, 60.0, 66.2)
    if result != FENETRE_MIN:
        raise AssertionError(f"result={result} != {FENETRE_MIN}")

# ----------------------------------------------------------------------
# R3 – Entrées manquantes
def test_r3():
    if module.fenetre_par_memoire(None, 1.0, 66.2) is not None:
        raise AssertionError("fenetre_par_memoire(None, ...) should be None")
    if module.fenetre_par_memoire(98304, 1.0, None) is not None:
        raise AssertionError("fenetre_par_memoire(..., None) should be None")
    if module.octets_kv_par_jeton(None) is not None:
        raise AssertionError("octets_kv_par_jeton(None) should be None")
    if module.num_predict_pour(None) != NUM_PREDICT_MIN:
        raise AssertionError("num_predict_pour(None) != 4096")

# ----------------------------------------------------------------------
# R4 – Puissance de 2 dans la fenêtre
def test_r4():
    result = module.fenetre_par_memoire(327680, 1.0, 10.0)
    if result < FENETRE_MIN or result > PLAFOND_FENETRE:
        raise AssertionError(f"result={result} out of bounds")
    if result & (result - 1) != 0:
        raise AssertionError(f"result={result} not power of 2")
    print(f"R4 valeur : {result}")

# ----------------------------------------------------------------------
# L1 – Substitution temporaire de subprocess.run et urllib.request.urlopen
def test_l1():
    # sauvegarde éventuelle
    orig_subprocess = getattr(module, "subprocess", None)
    orig_urllib = getattr(module, "urllib", None)

    call_counters = {"subprocess": 0, "urllib": 0}

    class DummySubprocess:
        @staticmethod
        def run(*args, **kwargs):
            call_counters["subprocess"] += 1
            raise AssertionError("subprocess.run should not be called")

    class DummyUrllib:
        @staticmethod
        def request(url, *args, **kwargs):
            call_counters["urllib"] += 1
            raise AssertionError("urllib.request.urlopen should not be called")

    # injection
    module.subprocess = DummySubprocess
    module.urllib = DummyUrllib

    try:
        # Re‑exécuter les tests F1‑F5
        test_f1()
        test_f2()
        test_f3()
        test_f4()
        test_f5()
        if call_counters["subprocess"] != 0 or call_counters["urllib"] != 0:
            raise AssertionError("unexpected external calls")
    finally:
        # restauration
        if orig_subprocess is not None:
            module.subprocess = orig_subprocess
        else:
            delattr(module, "subprocess")
        if orig_urllib is not None:
            module.urllib = orig_urllib
        else:
            delattr(module, "urllib")

NEMOTRON = (
    "    general.architecture                                nemotron_h_moe\n"
    "    nemotron_h_moe.attention.head_count                 32\n"
    "    nemotron_h_moe.attention.head_count_kv              [0 0 0 ...+49 more]\n"
    "    nemotron_h_moe.block_count                          52\n"
    "    nemotron_h_moe.context_length                       1.048576e+06\n"
)

def test_g1():
    result = module.fenetre_derivee_ollama("qwen3-coder:30b", 18.6, 66.2, lire_sortie=lambda nom: QWEN)
    if result != 65536:
        raise AssertionError(f"{result} != 65536")

def test_g2():
    result = module.fenetre_derivee_ollama("phi", 1.6, 66.2, lire_sortie=lambda nom: PHI)
    if result != 2048:
        raise AssertionError(f"{result} != 2048")

def test_g3():
    result = module.fenetre_derivee_ollama("x", 1.0, 66.2, lire_sortie=lambda nom: "")
    if result is not None:
        raise AssertionError(f"{result} is not None")

def test_g4():
    def lever(nom):
        raise OSError("ollama absent")
    result = module.fenetre_derivee_ollama("x", 1.0, 66.2, lire_sortie=lever)
    if result is not None:
        raise AssertionError(f"{result} is not None")

def test_f6():
    arch = module.lire_architecture(NEMOTRON)
    assert arch["context_length"] == 1048576, f"{arch['context_length']}"
    assert arch["head_count_kv"] is None
    assert module.octets_kv_par_jeton(arch) is None

# ----------------------------------------------------------------------
# Exécution des tests
test_functions = [
    ("C0", test_existence),
    ("F1", test_f1),
    ("F2", test_f2),
    ("F3", test_f3),
    ("F4", test_f4),
    ("F5", test_f5),
    ("R1", test_r1),
    ("R2", test_r2),
    ("R3", test_r3),
    ("R4", test_r4),
    ("L1", test_l1),
    ("F6", test_f6),
    ("G1", test_g1),
    ("G2", test_g2),
    ("G3", test_g3),
    ("G4", test_g4),
]

for name, func in test_functions:
    try:
        func()
        record_success(name)
    except Exception as e:
        record_rate(name, e)

# ----------------------------------------------------------------------
# Résultat final
print(f"{total_cases} cas, {rate_cases} RATE")
if rate_cases > 0:
    for msg in rate_messages:
        print(msg)
    sys.exit(1)
else:
    sys.exit(0)
