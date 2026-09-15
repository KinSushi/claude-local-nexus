#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import importlib.util
from pathlib import Path

# Chargement du module à tester
racine = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "_epreuve_ctx_natif", racine / "scripts" / "nexus_generate.py"
)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)

# Helper pour l'affichage des résultats
def _affiche_ok(nom, valeur):
    print(f"[OK  ] {nom} : {valeur}")

def _affiche_rate(nom, valeur):
    print(f"[RATE] {nom} : {valeur}")

# Compteurs
total = 0
rate = 0

# ----------------------------------------------------------------------
# C0 : contre‑épreuve – présence des attributs
total += 1
attrs = ["lire_contexte_natif", "plafonner_contexte", "contexte_natif_ollama"]
manquants = [a for a in attrs if not hasattr(module, a)]
if manquants:
    rate += 1
    _affiche_rate("C0 CONTRE-EPREUVE", f"absents : {', '.join(manquants)}")
else:
    _affiche_ok("C0 CONTRE-EPREUVE", "tous présents")

# ----------------------------------------------------------------------
# F1 : forward – lire_contexte_natif sur texte complet
total += 1
texte_f1 = (
    "  Model\n"
    "    architecture        llama     \n"
    "    parameters          1.2B      \n"
    "    context length      131072    \n"
    "    embedding length    2048      \n"
    "\n"
    "  Capabilities\n"
    "    completion    \n"
)
try:
    res = module.lire_contexte_natif(texte_f1)
    if res == 131072:
        _affiche_ok("F1 FORWARD", res)
    else:
        rate += 1
        _affiche_rate("F1 FORWARD", f"obtenu {res}")
except Exception as e:
    rate += 1
    _affiche_rate("F1 FORWARD", f"{type(e).__name__}({e})")

# ----------------------------------------------------------------------
# F2 : forward – plafonner_contexte
def _test_plafonner(ctx, natif, attendu, nom):
    global total, rate
    total += 1
    try:
        res = module.plafonner_contexte(ctx, natif)
        if res == attendu:
            _affiche_ok(nom, res)
        else:
            rate += 1
            _affiche_rate(nom, f"obtenu {res}")
    except Exception as e:
        rate += 1
        _affiche_rate(nom, f"{type(e).__name__}({e})")

_test_plafonner(16384, 2048, 2048, "F2 FORWARD 1")
_test_plafonner(16384, 131072, 16384, "F2 FORWARD 2")

# ----------------------------------------------------------------------
# R1 : reverse – lire_contexte_natif cas d'erreur
def _test_lire_texte(texte, attendu, nom):
    global total, rate
    total += 1
    try:
        res = module.lire_contexte_natif(texte)
        if res is attendu:
            _affiche_ok(nom, "None")
        else:
            rate += 1
            _affiche_rate(nom, f"obtenu {res}")
    except Exception as e:
        rate += 1
        _affiche_rate(nom, f"{type(e).__name__}({e})")

_test_lire_texte(
    "  Model\n    architecture llama\n",
    None,
    "R1 REVERSE 1",
)
_test_lire_texte(
    "    context length      abc\n",
    None,
    "R1 REVERSE 2",
)
_test_lire_texte(
    "    context length      0\n",
    None,
    "R1 REVERSE 3",
)
_test_lire_texte(
    None,
    None,
    "R1 REVERSE 4",
)

# ----------------------------------------------------------------------
# R2 : reverse – ne pas confondre embedding length
total += 1
try:
    res = module.lire_contexte_natif("    embedding length    2048\n")
    if res is None:
        _affiche_ok("R2 REVERSE", "None")
    else:
        rate += 1
        _affiche_rate("R2 REVERSE", f"obtenu {res}")
except Exception as e:
    rate += 1
    _affiche_rate("R2 REVERSE", f"{type(e).__name__}({e})")

# ----------------------------------------------------------------------
# R3 : inconnu – plafonner_contexte avec None ou 0
_test_plafonner(16384, None, 16384, "R3 INCONNU 1")
_test_plafonner(16384, 0, 16384, "R3 INCONNU 2")

# ----------------------------------------------------------------------
# L1 : fuite / dégradation – mock subprocess.run
total += 1
original_run = getattr(module.subprocess, "run", None)

def _mock_run(*_args, **_kwargs):
    raise OSError("ollama absent")

module.subprocess.run = _mock_run
try:
    try:
        res = module.contexte_natif_ollama("x")
        if res is None:
            _affiche_ok("L1 FUITE / DEGRADATION", "None")
        else:
            rate += 1
            _affiche_rate("L1 FUITE / DEGRADATION", f"obtenu {res}")
    except Exception as e:
        rate += 1
        _affiche_rate("L1 FUITE / DEGRADATION", f"{type(e).__name__}({e})")
finally:
    # restauration du comportement original
    if original_run is not None:
        module.subprocess.run = original_run
    else:
        delattr(module.subprocess, "run")

# ----------------------------------------------------------------------
# Résumé
print(f"{total} cas, {rate} RATE")
if rate > 0:
    sys.exit(1)
else:
    sys.exit(0)
