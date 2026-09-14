#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Épreuve T13 – vérifie les trois fonctions pures ajoutées à
`scripts/nexus_agent.py` :

* `borner_replis_locaux`
* `taille_alias` / `est_degrade`
* `texte_degenere`

Chaque cas imprime une ligne au format :

    [OK  ] <nom> : <detail>
    [RATE] <nom> : <detail>

Deux espaces après « OK ». Le script compte les échecs et sort avec le code
d’état 1 si au moins un cas a échoué, sinon 0.
"""

import sys
import os

# ----------------------------------------------------------------------
# Import du module cible
# ----------------------------------------------------------------------
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SCRIPTS = os.path.join(ROOT, "scripts")
sys.path.insert(0, SCRIPTS)

try:
    import nexus_agent as agent
except Exception as exc:
    print("[RATE] import : %s" % exc)
    sys.exit(1)

# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------
def _ok(name, detail=""):
    print("[OK  ] %s : %s" % (name, detail))


def _rate(name, detail=""):
    print("[RATE] %s : %s" % (name, detail))


def _check(condition, name, detail=""):
    if condition:
        _ok(name, detail)
        return True
    _rate(name, detail)
    return False


# ----------------------------------------------------------------------
# Cas de test
# ----------------------------------------------------------------------
def test_plafond():
    """
    1. plafond : candidats ["gpt-oss-120b-cloud","mistral-large-3-675b-cloud",
    "a-local","b-local","c-local","d-local"], plans {"gpt-oss-120b-cloud":"cloud",
    "mistral-large-3-675b-cloud":"cloud", les 4 locaux:"local"},
    maximum=2 -> gardes == les 2 cloud + a‑local + b‑local,
    ecartes == 2 chaines mentionnant c‑local puis d‑local.
    """
    candidats = [
        "gpt-oss-120b-cloud",
        "mistral-large-3-675b-cloud",
        "a-local",
        "b-local",
        "c-local",
        "d-local",
    ]
    plans = {
        "gpt-oss-120b-cloud": "cloud",
        "mistral-large-3-675b-cloud": "cloud",
        "a-local": "local",
        "b-local": "local",
        "c-local": "local",
        "d-local": "local",
    }
    gardes, ecartes = agent.borner_replis_locaux(candidats, plans, maximum=2)
    ok_gardes = gardes == [
        "gpt-oss-120b-cloud",
        "mistral-large-3-675b-cloud",
        "a-local",
        "b-local",
    ]
    ok_ecartes = (
        isinstance(ecartes, list)
        and len(ecartes) == 2
        and all(isinstance(e, str) and ("c-local" in e or "d-local" in e) for e in ecartes)
    )
    return _check(ok_gardes and ok_ecartes, "plafond", "gardes=%s ecartes=%s" % (gardes, ecartes))


def test_demande_locale_conservee():
    """
    2. demande locale conservee : candidats ["x-local","y-local","z-local"]
    maximum=0 -> gardes == ["x-local"], 2 ecartes.
    """
    candidats = ["x-local", "y-local", "z-local"]
    plans = {"x-local": "local", "y-local": "local", "z-local": "local"}
    gardes, ecartes = agent.borner_replis_locaux(candidats, plans, maximum=0)
    ok_gardes = gardes == ["x-local"]
    ok_ecartes = isinstance(ecartes, list) and len(ecartes) == 2
    return _check(ok_gardes and ok_ecartes, "demande locale conservee", "gardes=%s ecartes=%s" % (gardes, ecartes))


def test_plan_inconnu_garde():
    """
    3. plan inconnu garde : un alias absent de `plans` n’est pas compté comme local.
    """
    candidats = ["u-unknown", "v-local"]
    plans = {"v-local": "local"}
    gardes, ecartes = agent.borner_replis_locaux(candidats, plans, maximum=1)
    ok_gardes = gardes == ["u-unknown", "v-local"]
    ok_ecartes = isinstance(ecartes, list) and len(ecartes) == 0
    return _check(ok_gardes and ok_ecartes, "plan inconnu garde", "gardes=%s ecartes=%s" % (gardes, ecartes))


def test_tailles():
    """
    4. tailles : les six exemples de (b).
    """
    exemples = {
        "qwen2.5-coder-14b-local": 14.0,
        "ollama_chat/llama3.2:1b": 1.0,
        "gpt-oss-120b-cloud": 120.0,
        "mistral-large-3-675b-cloud": 675.0,
        "glm-4.7-flash-local": None,
        "codestral-local": None,
    }
    all_ok = True
    for alias, attendu in exemples.items():
        obtenu = agent.taille_alias(alias)
        if obtenu != attendu:
            all_ok = False
            _rate("taille %s" % alias, "attendu=%s obtenu=%s" % (attendu, obtenu))
        else:
            _ok("taille %s" % alias, "valeur=%s" % obtenu)
    return all_ok


def test_degrade():
    """
    5. degrade : plusieurs appels à `est_degrade`.
    """
    cas = [
        (("qwen2.5-coder-14b-local", "ollama_chat/llama3.2:1b"), True),
        (("gpt-oss-120b-cloud", "gpt-oss-120b-cloud"), False),
        (("glm-4.7-flash-local", "llama3.2:1b"), False),  # inconnu → pas de verdict
        (("qwen3-14b-local", "qwen3-8b-local"), False),  # 8 >= 7
    ]
    all_ok = True
    for (demande, servi), attendu in cas:
        obtenu = agent.est_degrade(demande, servi)
        if obtenu != attendu:
            all_ok = False
            _rate(
                "degrade %s vs %s" % (demande, servi),
                "attendu=%s obtenu=%s" % (attendu, obtenu),
            )
        else:
            _ok("degrade %s vs %s" % (demande, servi), "ok")
    return all_ok


def test_degenere():
    """
    6. degenere : plusieurs scénarios.
    """
    all_ok = True

    # 6 lignes identiques de 60 caractères → True
    ligne = "x" * 60
    texte_identique = ("\n".join([ligne] * 6)) + "\n"
    if not agent.texte_degenere(texte_identique):
        all_ok = False
        _rate("degenere identique", "devrait être True")
    else:
        _ok("degenere identique", "True")

    # 6 lignes différentes → False
    texte_diff = "\n".join(["a" * 60, "b" * 60, "c" * 60, "d" * 60, "e" * 60, "f" * 60]) + "\n"
    if agent.texte_degenere(texte_diff):
        all_ok = False
        _rate("degenere different", "devrait être False")
    else:
        _ok("degenere different", "False")

    # texte vide → False
    if agent.texte_degenere(""):
        all_ok = False
        _rate("degenere vide", "devrait être False")
    else:
        _ok("degenere vide", "False")

    # paragraphe de 1200 caractères varié → False
    var = ("abcdefghijklmnopqrstuvwxyz" * 46)[:1200]  # 26*46 = 1196 + 4
    if agent.texte_degenere(var):
        all_ok = False
        _rate("degenere varie", "devrait être False")
    else:
        _ok("degenere varie", "False")

    # bloc de 250 caractères répété 6 fois sans saut de ligne → True
    bloc = "y" * 250
    texte_bloc = bloc * 6
    if not agent.texte_degenere(texte_bloc):
        all_ok = False
        _rate("degenere bloc", "devrait être True")
    else:
        _ok("degenere bloc", "True")

    return all_ok


def test_reprise_utile():
    """
    8. reprise_utile : vérifie le comportement de la fonction pure ajoutée.
    """
    ok = True
    if not agent.reprise_utile("raisonnement_30869") is False:
        ok = False
        _rate("reprise_utile raison", "devrait être False")
    if not agent.reprise_utile("contenu_present") is True:
        ok = False
        _rate("reprise_utile contenu", "devrait être True")
    if not agent.reprise_utile(None) is True:
        ok = False
        _rate("reprise_utile None", "devrait être True")
    if not agent.reprise_utile("") is True:
        ok = False
        _rate("reprise_utile vide", "devrait être True")
    if ok:
        _ok("reprise_utile", "tous les cas passent")
    return ok

def test_degenere_detection():
    """
    7. detection : une fausse fonction `lambda t, **k: False` doit faire échouer le
    cas « 6 lignes identiques ».
    """
    original = agent.texte_degenere
    try:
        agent.texte_degenere = lambda *a, **k: False
        ligne = "z" * 60
        texte = ("\n".join([ligne] * 6)) + "\n"
        result = agent.texte_degenere(texte)
        ok = not result  # on attend que le résultat soit False → échec du cas
        if ok:
            _ok("degenere detection", "fausse fonction a bien fait échouer")
        else:
            _rate("degenere detection", "fausse fonction n’a pas fait échouer")
        return ok
    finally:
        agent.texte_degenere = original


def main():
    failures = 0

    if not test_plafond():
        failures += 1
    if not test_demande_locale_conservee():
        failures += 1
    if not test_plan_inconnu_garde():
        failures += 1
    if not test_tailles():
        failures += 1
    if not test_degrade():
        failures += 1
    if not test_degenere():
        failures += 1
    if not test_reprise_utile():
        failures += 1
    if not test_degenere_detection():
        failures += 1

    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
