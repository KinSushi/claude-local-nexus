import importlib.util
import sys
import pathlib
import json
import tempfile
import io
import contextlib
import re
import subprocess
import traceback

# ----------------------------------------------------------------------
# Chargement du module à tester
# ----------------------------------------------------------------------
racine = pathlib.Path(__file__).resolve().parents[1]
outillage_dir = racine / "outillage"
progres_path = outillage_dir / "nexus_progres.py"

spec = importlib.util.spec_from_file_location(
    "_epreuve_progres_registre", str(progres_path)
)
progres = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = progres
spec.loader.exec_module(progres)  # le module n'exécute main() que sous __main__

# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------
def _ecrire_registre(path, lignes):
    """Écrit un fichier JSONL à partir d'une liste de dicts."""
    with open(path, "w", encoding="utf-8") as f:
        for obj in lignes:
            json.dump(obj, f, ensure_ascii=False)
            f.write("\n")


def _ecrire_cache(path, head, verdicts):
    data = {"head": head, "verdicts": verdicts}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)


# mesure du 2026-09-15 : rendre_registre renvoie ses lignes, il n'imprime rien
def _capturer_sortie(func, *args, **kwargs):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        resultat = func(*args, **kwargs)
    if isinstance(resultat, list):
        return [str(ligne) for ligne in resultat]
    return buf.getvalue().splitlines()


def _assert_contains(lines, pattern, case_name, msg):
    if not any(re.search(pattern, line) for line in lines):
        raise AssertionError(f"{case_name}: {msg} (pattern '{pattern}' absent)")


def _assert_not_contains(lines, pattern, case_name, msg):
    if any(re.search(pattern, line) for line in lines):
        raise AssertionError(f"{case_name}: {msg} (pattern '{pattern}' présent)")


# ----------------------------------------------------------------------
# Cas de test
# ----------------------------------------------------------------------
cas_total = 0
cas_rate = 0
resultats = []


def _run_case(nom, fonction):
    global cas_total, cas_rate
    cas_total += 1
    try:
        fonction()
        resultats.append(f"[OK  ] {nom}")
    except Exception as e:
        cas_rate += 1
        tb = traceback.format_exc()
        resultats.append(f"[RATE] {nom} : {e}\n{tb}")


# C0 : présence des fonctions attendues
def cas_C0():
    if not (hasattr(progres, "rendre_registre") and hasattr(progres, "_charger_taches")):
        raise AssertionError("Fonctions rendre_registre ou _charger_taches manquantes")


# F1 : rendu normal (head concordant)
def cas_F1():
    with tempfile.TemporaryDirectory() as td:
        td_path = pathlib.Path(td)
        registre_path = td_path / "registre.jsonl"
        cache_path = td_path / "cache.json"

        # registre de référence (3 tâches)
        registre_lignes = [
            {
                "id": "T-20260915-001",
                "titre": "alpha",
                "origine": "cockpit (epreuve)",
                "cree_le": "2026-09-15",
                "preuve": {"type": "famille", "cible": "taches"},
            },
            {
                "id": "T-20260915-002",
                "titre": "beta",
                "origine": "cockpit (epreuve)",
                "cree_le": "2026-09-15",
                "preuve": {"type": "commit"},
            },
            {
                "id": "T-20260915-003",
                "titre": "gamma",
                "origine": "cockpit (epreuve)",
                "cree_le": "2026-09-15",
                "non_mecanisable": "decision operateur",
            },
        ]
        _ecrire_registre(registre_path, registre_lignes)

        # cache de référence
        cache_verdicts = {
            "T-20260915-001": {"etat": "FAIT", "raison": "famille verte"},
            "T-20260915-002": {
                "etat": "A_FAIRE",
                "raison": "aucun commit Tache: T-20260915-002",
            },
        }
        _ecrire_cache(cache_path, "abc1234def", cache_verdicts)

        # charger les tâches
        taches_mod = progres._charger_taches(str(outillage_dir))

        # exécuter et capturer
        lignes = _capturer_sortie(
            progres.rendre_registre, taches_mod, str(registre_path), str(cache_path), "abc1234def"
        )

        # vérifications
        _assert_contains(lignes, r"### A FAIRE", "F1", "section A FAIRE manquante")
        _assert_contains(lignes, r"T-20260915-002.*beta", "F1", "tâche 002 absente dans A FAIRE")
        _assert_contains(lignes, r"### FAIT", "F1", "section FAIT manquante")
        _assert_contains(lignes, r"T-20260915-001", "F1", "tâche 001 absente dans FAIT")
        _assert_contains(lignes, r"### A TRANCHER", "F1", "section A TRANCHER manquante")
        _assert_contains(
            lignes,
            r"T-20260915-003.*decision operateur",
            "F1",
            "tâche 003 absente dans A TRANCHER",
        )
        _assert_contains(lignes, r"A faire\s*:\s*1", "F1", "compteur A faire incorrect")
        _assert_contains(lignes, r"Fait\s*:\s*1", "F1", "compteur Fait incorrect")


# F2 : head différent → NON MESUREES
def cas_F2():
    with tempfile.TemporaryDirectory() as td:
        td_path = pathlib.Path(td)
        registre_path = td_path / "registre.jsonl"
        cache_path = td_path / "cache.json"

        # même registre que F1
        registre_lignes = [
            {
                "id": "T-20260915-001",
                "titre": "alpha",
                "origine": "cockpit (epreuve)",
                "cree_le": "2026-09-15",
                "preuve": {"type": "famille", "cible": "taches"},
            },
            {
                "id": "T-20260915-002",
                "titre": "beta",
                "origine": "cockpit (epreuve)",
                "cree_le": "2026-09-15",
                "preuve": {"type": "commit"},
            },
            {
                "id": "T-20260915-003",
                "titre": "gamma",
                "origine": "cockpit (epreuve)",
                "cree_le": "2026-09-15",
                "non_mecanisable": "decision operateur",
            },
        ]
        _ecrire_registre(registre_path, registre_lignes)

        # même cache que F1
        cache_verdicts = {
            "T-20260915-001": {"etat": "FAIT", "raison": "famille verte"},
            "T-20260915-002": {
                "etat": "A_FAIRE",
                "raison": "aucun commit Tache: T-20260915-002",
            },
        }
        # le cache est ecrit pour un AUTRE head que celui du rendu : c'est ce qui le rend perime
        _ecrire_cache(cache_path, "abc1234def", cache_verdicts)

        taches_mod = progres._charger_taches(str(outillage_dir))

        lignes = _capturer_sortie(
            progres.rendre_registre, taches_mod, str(registre_path), str(cache_path), "autre999"
        )

        _assert_contains(lignes, r"### NON MESUREES", "F2", "section NON MESUREES manquante")
        _assert_contains(lignes, r"T-20260915-001", "F2", "tâche 001 absente dans NON MESUREES")
        _assert_contains(lignes, r"T-20260915-002", "F2", "tâche 002 absente dans NON MESUREES")
        _assert_contains(lignes, r"Fait\s*:\s*0", "F2", "compteur Fait doit être 0")
        _assert_contains(lignes, r"T-20260915-001 alpha -- non mesur", "F2", "tâche 001 non marquée non mesurée")
        _assert_not_contains(lignes, r"T-20260915-001 alpha -- preuve", "F2", "tâche 001 rendue FAIT sur un cache périmé")


# R1 : registre absent
def cas_R1():
    with tempfile.TemporaryDirectory() as td:
        td_path = pathlib.Path(td)
        registre_path = td_path / "registre_absent.jsonl"  # n'existe pas
        cache_path = td_path / "cache.json"

        # créer un cache valide (le contenu n'est pas utilisé)
        _ecrire_cache(cache_path, "abc1234def", {})

        taches_mod = progres._charger_taches(str(outillage_dir))

        lignes = _capturer_sortie(
            progres.rendre_registre, taches_mod, str(registre_path), str(cache_path), "abc1234def"
        )

        _assert_contains(lignes, r"^- Registre absent", "R1", "message Registre absent manquant")
        _assert_not_contains(lignes, r"A faire\s*:\s*0", "R1", "le compteur A faire ne doit pas être 0")


# R2 : registre invalide (champ inconnu)
def cas_R2():
    with tempfile.TemporaryDirectory() as td:
        td_path = pathlib.Path(td)
        registre_path = td_path / "registre.jsonl"
        cache_path = td_path / "cache.json"

        # ligne invalide : champ "etat" inconnu
        ligne_invalide = {
            "id": "T-20260915-001",
            "titre": "alpha",
            "origine": "cockpit (epreuve)",
            "cree_le": "2026-09-15",
            "etat": "???",
        }
        _ecrire_registre(registre_path, [ligne_invalide])

        _ecrire_cache(cache_path, "abc1234def", {})

        taches_mod = progres._charger_taches(str(outillage_dir))

        lignes = _capturer_sortie(
            progres.rendre_registre, taches_mod, str(registre_path), str(cache_path), "abc1234def"
        )

        _assert_contains(
            lignes,
            r"^- Registre illisible, ligne 1",
            "R2",
            "message Registre illisible manquant",
        )


# L1 : fuite de subprocess (aucun appel)
def cas_L1():
    with tempfile.TemporaryDirectory() as td:
        td_path = pathlib.Path(td)
        registre_path = td_path / "registre.jsonl"
        cache_path = td_path / "cache.json"

        # même registre que F1
        registre_lignes = [
            {
                "id": "T-20260915-001",
                "titre": "alpha",
                "origine": "cockpit (epreuve)",
                "cree_le": "2026-09-15",
                "preuve": {"type": "famille", "cible": "taches"},
            },
            {
                "id": "T-20260915-002",
                "titre": "beta",
                "origine": "cockpit (epreuve)",
                "cree_le": "2026-09-15",
                "preuve": {"type": "commit"},
            },
            {
                "id": "T-20260915-003",
                "titre": "gamma",
                "origine": "cockpit (epreuve)",
                "cree_le": "2026-09-15",
                "non_mecanisable": "decision operateur",
            },
        ]
        _ecrire_registre(registre_path, registre_lignes)

        cache_verdicts = {
            "T-20260915-001": {"etat": "FAIT", "raison": "famille verte"},
            "T-20260915-002": {
                "etat": "A_FAIRE",
                "raison": "aucun commit Tache: T-20260915-002",
            },
        }
        _ecrire_cache(cache_path, "abc1234def", cache_verdicts)

        taches_mod = progres._charger_taches(str(outillage_dir))

        # monkey‑patch subprocess
        calls = {"run": 0, "check_output": 0}

        def fake_run(*a, **kw):
            calls["run"] += 1
            raise AssertionError("sous-processus interdit")

        def fake_check_output(*a, **kw):
            calls["check_output"] += 1
            raise AssertionError("sous-processus interdit")

        original_run = subprocess.run
        original_check_output = subprocess.check_output
        try:
            subprocess.run = fake_run
            subprocess.check_output = fake_check_output

            _capturer_sortie(
                progres.rendre_registre,
                taches_mod,
                str(registre_path),
                str(cache_path),
                "abc1234def",
            )
        finally:
            subprocess.run = original_run
            subprocess.check_output = original_check_output

        if calls["run"] != 0 or calls["check_output"] != 0:
            raise AssertionError(
                f"L1: rendu_registre a appelé subprocess ({calls['run']} run, {calls['check_output']} check_output)"
            )


# ----------------------------------------------------------------------
# Exécution des cas
# ----------------------------------------------------------------------
for nom, fn in [
    ("C0", cas_C0),
    ("F1", cas_F1),
    ("F2", cas_F2),
    ("R1", cas_R1),
    ("R2", cas_R2),
    ("L1", cas_L1),
]:
    _run_case(nom, fn)

# ----------------------------------------------------------------------
# Résumé
# ----------------------------------------------------------------------
for ligne in resultats:
    print(ligne)

print(f"{cas_total} cas, {cas_rate} RATE")
sys.exit(1 if cas_rate > 0 else 0)
