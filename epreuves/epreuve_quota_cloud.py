# -*- coding: utf-8 -*-
"""Épreuve fonctionnelle pour le script ``scripts/nexus_quota_cloud.py``.

Cette épreuve suit le protocole attendu par ``outillage/nexus_test.py`` :
chaque cas écrit sur STDOUT une ligne commençant exactement par
`[OK  ] ` (OK suivi de deux espaces) ou `[RATE] `, puis le nom du cas,
un deux‑points et un détail optionnel.
Le code de sortie du processus est 0 si tous les cas réussissent,
1 sinon.

Utilisation :
    python epreuves/epreuve_quota_cloud.py
"""

import importlib.util
import io
import pathlib
import sys
import subprocess
from contextlib import redirect_stdout

# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------
def check(nom, condition, detail=""):
    """Affiche le résultat d’un cas de test et renvoie le booléen."""
    if condition:
        print(f"[OK  ] {nom} : {detail}")
    else:
        print(f"[RATE] {nom} : {detail}")
    return condition

# ----------------------------------------------------------------------
# Fake ``subprocess.run`` infrastructure
# ----------------------------------------------------------------------
class _FakeRun:
    """Enregistre les appels et renvoie un ``CompletedProcess`` configuré."""
    def __init__(self):
        self.calls = []          # liste des commandes reçues
        self.behavior = {}       # dict décrivant le comportement attendu

    def set_behavior(self, *, stdout="", returncode=0, raise_exc=None):
        """Configure le comportement du prochain appel."""
        self.behavior = {
            "stdout": stdout,
            "returncode": returncode,
            "raise_exc": raise_exc,
        }

    def __call__(self, cmd, *_, capture_output=True, text=True, timeout=None, **__):
        """Imite ``subprocess.run``."""
        self.calls.append(cmd)
        if self.behavior.get("raise_exc"):
            raise self.behavior["raise_exc"]
        return subprocess.CompletedProcess(
            args=cmd,
            returncode=self.behavior.get("returncode", 0),
            stdout=self.behavior.get("stdout", ""),
            stderr="",
        )

# ----------------------------------------------------------------------
# Loader du module cible
# ----------------------------------------------------------------------
def _load_target_module():
    """Charge ``scripts/nexus_quota_cloud.py`` depuis la racine du dépôt."""
    repo_root = pathlib.Path(__file__).resolve().parents[1]   # dépôt racine
    script_path = repo_root / "scripts" / "nexus_quota_cloud.py"
    spec = importlib.util.spec_from_file_location("nexus_quota_cloud", script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module, repo_root

# ----------------------------------------------------------------------
# Exécution d’un cas de test
# ----------------------------------------------------------------------
def _run_case(
    name,
    argv,
    fake_behavior,
    expected_code,
    stdout_contains=None,
    expect_no_run=False,
    forbidden_substrings=None,
):
    """
    Exécute le module avec les arguments fournis et vérifie le résultat.

    - ``argv`` : liste d’arguments à passer à ``module.main``.
    - ``fake_behavior`` : dict passé à ``_FakeRun.set_behavior``.
    - ``expected_code`` : code de sortie attendu (int).
    - ``stdout_contains`` : chaîne ou liste de chaînes attendues dans la sortie.
    - ``expect_no_run`` : si True, aucune appel à ``subprocess.run`` doit être enregistré.
    - ``forbidden_substrings`` : chaîne ou liste de chaînes qui ne doivent **pas**
      apparaître dans la sortie.
    """
    fake_run = _FakeRun()
    fake_run.set_behavior(**fake_behavior)

    module, repo_root = _load_target_module()
    # patch du subprocess.run du module cible
    module.subprocess.run = fake_run  # type: ignore[attr-defined]

    # capture stdout / stderr
    buf = io.StringIO()
    exit_code = None
    with redirect_stdout(buf):
        try:
            if hasattr(module, "main"):
                exit_code = module.main(argv)  # Correction : récupération du code de retour
            else:
                raise RuntimeError("module sans fonction main")
        except SystemExit as e:
            exit_code = e.code if isinstance(e.code, int) else 0
        except Exception as e:
            exit_code = 1
            print(f"Exception inattendue : {e}", file=sys.stderr)

    out = buf.getvalue()

    # Vérification du code de sortie (correction appliquée)
    if exit_code is None:
        ok_code = check(
            f"{name}_code",
            False,
            f"code=None attendu={expected_code}",
        )
    else:
        ok_code = check(
            f"{name}_code",
            exit_code == expected_code,
            f"code={exit_code} attendu={expected_code}",
        )

    # Vérifications restantes (inchangées)
    ok = ok_code

    if isinstance(stdout_contains, (list, tuple)):
        for sub in stdout_contains:
            ok &= check(
                f"{name}_stdout_contains",
                sub in out,
                f"absent «{sub}»",
            )
    elif isinstance(stdout_contains, str):
        ok &= check(
            f"{name}_stdout_contains",
            stdout_contains in out,
            f"absent «{stdout_contains}»",
        )

    if forbidden_substrings:
        if isinstance(forbidden_substrings, (list, tuple)):
            for sub in forbidden_substrings:
                ok &= check(
                    f"{name}_stdout_forbidden",
                    sub not in out,
                    f"présent «{sub}»",
                )
        else:
            ok &= check(
                f"{name}_stdout_forbidden",
                forbidden_substrings not in out,
                f"présent «{forbidden_substrings}»",
            )

    if expect_no_run:
        ok &= check(
            f"{name}_no_subprocess",
            len(fake_run.calls) == 0,
            f"{len(fake_run.calls)} appel(s) enregistré(s)",
        )
    else:
        ok &= check(
            f"{name}_subprocess_called",
            len(fake_run.calls) > 0,
            f"{len(fake_run.calls)} appel(s) enregistré(s)",
        )

    return ok

# ----------------------------------------------------------------------
# Cas de test
# ----------------------------------------------------------------------
def main():
    overall_ok = True

    # ------------------------------------------------------------------
    # 1. forward – état « EPUISE » (code 3)
    # ------------------------------------------------------------------
    overall_ok &= _run_case(
        name="forward_epuise",
        argv=["--etat"],
        fake_behavior={"stdout": "0|4|0\n", "returncode": 0},
        expected_code=3,
        stdout_contains="EPUISE",
    )

    # ------------------------------------------------------------------
    # 2. forward – état « SAIN » (code 0)
    # ------------------------------------------------------------------
    overall_ok &= _run_case(
        name="forward_sain",
        argv=["--etat"],
        fake_behavior={"stdout": "5|0|0\n", "returncode": 0},
        expected_code=0,
        stdout_contains="SAIN",
    )

    # ------------------------------------------------------------------
    # 3. forward – état « PLAFOND » (code 4)
    # ------------------------------------------------------------------
    overall_ok &= _run_case(
        name="forward_plafond",
        argv=["--etat"],
        fake_behavior={"stdout": "0|0|3\n", "returncode": 0},
        expected_code=4,
        stdout_contains="PLAFOND",
    )

    # ------------------------------------------------------------------
    # 4. forward – usage avec tarif connu
    #    (exemple : gpt-oss-120b-cloud, tarif 0.60 $)
    # ------------------------------------------------------------------
    usage_line = "gpt-oss-120b-cloud|19|1|0|1000000\n"
    overall_ok &= _run_case(
        name="forward_usage_known",
        argv=["--usage"],
        fake_behavior={"stdout": usage_line, "returncode": 0},
        expected_code=0,
        stdout_contains=["0.60", "gpt-oss-120b-cloud"],
        forbidden_substrings="metadata::text",
    )

    # ------------------------------------------------------------------
    # 5. forward – usage avec alias sans tarif (doit être listé séparément,
    #    mais ne doit pas contribuer au total)
    # ------------------------------------------------------------------
    usage_mixed = (
        "gpt-oss-120b-cloud|19|1|0|1000000\n"
        "glm-5.3-cloud|20|1|0|500000\n"
    )
    overall_ok &= _run_case(
        name="forward_usage_mixed",
        argv=["--usage"],
        fake_behavior={"stdout": usage_mixed, "returncode": 0},
        expected_code=0,
        stdout_contains=["0.60", "gpt-oss-120b-cloud"],
        # le coût de l'alias sans tarif ne doit pas apparaître
        forbidden_substrings="glm-5.3-cloud",
    )

    # ------------------------------------------------------------------
    # 6. reverse – docker absent (FileNotFoundError)
    # ------------------------------------------------------------------
    overall_ok &= _run_case(
        name="reverse_docker_absent",
        argv=["--etat"],
        fake_behavior={"raise_exc": FileNotFoundError("docker not found")},
        expected_code=5,
        stdout_contains="docker",
    )

    # ------------------------------------------------------------------
    # 7. reverse – minutes invalide (non numérique ou zéro)
    # ------------------------------------------------------------------
    overall_ok &= _run_case(
        name="reverse_minutes_non_numerique",
        argv=["--minutes", "abc"],
        fake_behavior={},  # aucune commande ne doit être exécutée
        expected_code=2,
        expect_no_run=True,
    )
    overall_ok &= _run_case(
        name="reverse_minutes_zero",
        argv=["--minutes", "0"],
        fake_behavior={},  # aucune commande ne doit être exécutée
        expected_code=2,
        expect_no_run=True,
    )

    # ------------------------------------------------------------------
    # 8. fuite – injection de commande dans le paramètre minutes
    # ------------------------------------------------------------------
    overall_ok &= _run_case(
        name="fuite_injection_minutes",
        argv=["--minutes", "5; drop table x"],
        fake_behavior={},  # aucune exécution Docker attendue
        expected_code=2,
        expect_no_run=True,
        forbidden_substrings="metadata",
    )

    sys.exit(0 if overall_ok else 1)

if __name__ == "__main__":
    main()
