# -*- coding: utf-8 -*-
"""Épreuve fonctionnelle du module ``scripts/nexus_lot_controle.py``.

Chaque cas écrit sur STDOUT une ligne commençant exactement par
`[OK  ] ` (OK suivi de deux espaces) ou `[RATE] `, puis le nom du cas,
un deux‑points et un détail optionnel.
Le code de sortie du processus est 0 si tous les cas réussissent,
1 sinon.

Utilisation :
    python epreuves/epreuve_lot_controle.py
"""

import importlib.util
import pathlib
import sys
import subprocess
import tempfile
from typing import List, Any
import contextlib

# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------
def _load_module():
    """Charge ``scripts/nexus_lot_controle.py`` depuis la racine du dépôt."""
    base_dir = pathlib.Path(__file__).resolve().parents[1]   # repository root
    script_path = base_dir / "scripts" / "nexus_lot_controle.py"
    if not script_path.is_file():
        return None, base_dir
    spec = importlib.util.spec_from_file_location("nexus_lot_controle", script_path)
    if spec is None or spec.loader is None:  # pragma: no cover
        return None, base_dir
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module, base_dir

def check(nom: str, condition: Any, detail: str = "") -> bool:
    """Affiche le résultat d’un cas de test et renvoie le booléen."""
    condition_bool = bool(condition)
    if condition_bool:
        print(f"[OK  ] {nom} : {detail}")
    else:
        print(f"[RATE] {nom} : {detail}")
    return condition_bool

# ----------------------------------------------------------------------
# Fake utilities for time‑sleep & horloge
# ----------------------------------------------------------------------
class FakeChrono:
    """Horloge factice qui avance d'un incrément fixe à chaque appel."""
    def __init__(self, start: float = 0.0, step: float = 0.1):
        self._now = start
        self._step = step
        self.calls: List[float] = []

    def __call__(self) -> float:
        self.calls.append(self._now)
        cur = self._now
        self._now += self._step
        return cur

class FakeSleeper:
    """Enregistre les appels à ``sleep`` sans attendre."""
    def __init__(self):
        self.calls: List[float] = []

    def __call__(self, seconds: float) -> None:
        self.calls.append(seconds)

# ----------------------------------------------------------------------
# Main test suite
# ----------------------------------------------------------------------
def main() -> int:
    ok = True
    module, repo_root = _load_module()
    if module is None:
        ok &= check("module_absent", False, "scripts/nexus_lot_controle.py introuvable")
        return 1

    # ------------------------------------------------------------------
    # 1. Forward – création, lecture, effacement d’un arrêt.
    # ------------------------------------------------------------------
    with tempfile.TemporaryDirectory() as d:
        dossier = pathlib.Path(d)

        # demander_arret
        try:
            ret = module.demander_arret("123-456", "essai", dossier=dossier)
            ok &= check("forward_demander_ok", True, f"ret={ret}")
        except Exception as e:  # pragma: no cover
            ok &= check("forward_demander_ok", False, str(e))

        # arret_demande
        fiche = module.arret_demande("123-456", dossier=dossier)
        ok &= check(
            "forward_arret_demande",
            isinstance(fiche, dict) and fiche.get("lot_id") == "123-456" and fiche.get("motif") == "essai",
            f"fiche={fiche}"
        )

        # effacer_arret
        try:
            eff = module.effacer_arret("123-456", dossier=dossier)
            ok &= check("forward_effacer_ok", eff is True, f"eff={eff}")
        except Exception as e:  # pragma: no cover
            ok &= check("forward_effacer_ok", False, str(e))

        # arret_demande après effacement
        fiche2 = module.arret_demande("123-456", dossier=dossier)
        ok &= check("forward_arret_apres_effacer", fiche2 is None, f"fiche2={fiche2}")

    # ------------------------------------------------------------------
    # 2. Forward – attendre_cloud_sain avec deux échecs puis succès.
    # ------------------------------------------------------------------
    appel_calls: List[int] = []

    def appel_failable():
        appel_calls.append(len(appel_calls) + 1)
        if len(appel_calls) < 3:
            raise RuntimeError("temporary failure")
        return {"ok": True, "duree_s": 0.05, "erreur": ""}

    chrono = FakeChrono()
    sleeper = FakeSleeper()
    annonces: List[Any] = []

    def annoncer(msg):
        annonces.append(msg)

    try:
        res = module.attendre_cloud_sain(
            appel=appel_failable,
            delai_s=0.2,
            pas_s=0.05,
            attente_max_s=1.0,
            annoncer=annoncer,
            dormir=sleeper,
            horloge=chrono,
        )
        ok &= check(
            "forward_attendre_ok",
            res.get("ok") is True and res.get("tentatives") == 3,
            f"res={res}"
        )
        ok &= check(
            "forward_attendre_sleeps",
            len(sleeper.calls) == 2,
            f"sleeps={sleeper.calls}"
        )
        ok &= check(
            "forward_attendre_annonces",
            len(annonces) >= 3,
            f"annonces={annonces}"
        )
    except Exception as e:  # pragma: no cover
        ok &= check("forward_attendre_exception", False, str(e))

    # ------------------------------------------------------------------
    # 3. Reverse – appels invalides et fichiers corrompus.
    # ------------------------------------------------------------------
    with tempfile.TemporaryDirectory() as d:
        dossier = pathlib.Path(d)

        # demander_arret avec lot_id invalide
        try:
            module.demander_arret("../x", "m", dossier=dossier)
            ok &= check("reverse_demander_raises", False, "no exception")
        except ValueError:
            ok &= check("reverse_demander_raises", True, "ValueError levé")
        except Exception as e:  # pragma: no cover
            ok &= check("reverse_demander_raises", False, f"unexpected {e}")

        # arret_demande avec lot_id invalide → None
        fiche = module.arret_demande("../x", dossier=dossier)
        ok &= check("reverse_arret_none", fiche is None, f"fiche={fiche}")

        # fichier non‑JSON → None
        bad_path = dossier / "badlot.json"
        bad_path.write_text("not a json", encoding="utf-8")
        # le lot_id correspondant est "badlot"
        fiche_bad = module.arret_demande("badlot", dossier=dossier)
        ok &= check("reverse_arret_mauvais_json", fiche_bad is None, f"fiche_bad={fiche_bad}")

    # ------------------------------------------------------------------
    # 4. Reverse – attendre_cloud_sain qui dépasse le temps maximal.
    # ------------------------------------------------------------------
    def appel_always_fail():
        raise RuntimeError("permanent failure")

    chrono2 = FakeChrono(start=0.0, step=0.5)   # avance rapidement
    sleeper2 = FakeSleeper()
    try:
        res2 = module.attendre_cloud_sain(
            appel=appel_always_fail,
            delai_s=0.1,
            pas_s=0.1,
            attente_max_s=0.3,
            dormir=sleeper2,
            horloge=chrono2,
        )
        ok &= check(
            "reverse_attendre_timeout_ok",
            res2.get("ok") is False and isinstance(res2.get("derniere", {}).get("erreur"), str) and res2["derniere"]["erreur"],
            f"res2={res2}"
        )
    except Exception as e:  # pragma: no cover
        ok &= check("reverse_attendre_timeout_exception", False, str(e))

    # ------------------------------------------------------------------
    # 5. Reverse – durée dépassée même sans exception.
    # ------------------------------------------------------------------
    def appel_rapide():
        return {"ok": True, "duree_s": 0.5, "erreur": ""}

    chrono3 = FakeChrono(start=0.0, step=0.2)   # chaque appel avance de 0.2 s
    sleeper3 = FakeSleeper()
    try:
        res3 = module.attendre_cloud_sain(
            appel=appel_rapide,
            delai_s=0.1,          # délai très petit
            pas_s=0.05,
            attente_max_s=1.0,
            dormir=sleeper3,
            horloge=chrono3,
        )
        ok &= check(
            "reverse_attendre_delai_excede",
            res3.get("ok") is False,
            f"res3={res3}"
        )
    except Exception as e:  # pragma: no cover
        ok &= check("reverse_attendre_delai_excede_exception", False, str(e))

    # ------------------------------------------------------------------
    # 6. Reverse – CLI avec lot_id invalide.
    # ------------------------------------------------------------------
    cmd_arreter = [
        sys.executable,
        str(repo_root / "scripts" / "nexus_lot_controle.py"),
        "--arreter",
        "../x",
    ]
    cmd_etat = [
        sys.executable,
        str(repo_root / "scripts" / "nexus_lot_controle.py"),
        "--etat",
    ]
    try:
        # Cas --arreter ../x
        result_arreter = subprocess.run(
            cmd_arreter,
            capture_output=True,
            text=True,
            timeout=30,
            encoding="utf-8",
            errors="replace",
        )
        output_combined = (result_arreter.stdout or "") + (result_arreter.stderr or "")
        rc_ok = result_arreter.returncode != 0
        pid_epoch_present = "<pid>-<epoch>" in output_combined
        no_argparse_error = "error: the following arguments are required" not in output_combined
        ok &= check("reverse_cli_arreter_code", rc_ok, f"rc={result_arreter.returncode}")
        ok &= check("reverse_cli_arreter_pid_epoch", pid_epoch_present, "pattern <pid>-<epoch> absent")
        ok &= check("reverse_cli_arreter_no_argparse", no_argparse_error, "refus argparse présent")

        # Cas --etat
        result_etat = subprocess.run(
            cmd_etat,
            capture_output=True,
            text=True,
            timeout=30,
            encoding="utf-8",
            errors="replace",
        )
        ok &= check("reverse_cli_etat_code", result_etat.returncode == 0, f"rc={result_etat.returncode}")
    except subprocess.TimeoutExpired:
        ok &= check("reverse_cli_timeout", False, "timeout")
    except Exception as e:  # pragma: no cover
        ok &= check("reverse_cli_error", False, str(e))

    # ------------------------------------------------------------------
    # 7. Fuite – aucune création de fichier après les cas interdits.
    # ------------------------------------------------------------------
    with tempfile.TemporaryDirectory() as d:
        dossier = pathlib.Path(d)
        before = {p for p in dossier.rglob("*") if p.is_file()}
        # appel qui lève immédiatement (déjà testé ci‑dessus)
        with contextlib.suppress(ValueError):
            module.demander_arret("../x", "m", dossier=dossier)
        after = {p for p in dossier.rglob("*") if p.is_file()}
        ok &= check("fuite_aucun_fichier", before == after, f"before={len(before)} after={len(after)}")

    # ------------------------------------------------------------------
    # 8. sonder_cloud – appel exactement une fois.
    # ------------------------------------------------------------------
    appel_counter = {"calls": 0}
    def appel_unique():
        appel_counter["calls"] += 1
        return {"ok": True, "duree_s": 0.01, "erreur": ""}

    try:
        res_sc = module.sonder_cloud(appel_unique, delai_s=0.5)
        ok &= check("sonder_cloud_one_call", appel_counter["calls"] == 1, f"calls={appel_counter['calls']}")
        ok &= check("sonder_cloud_ok", res_sc.get("ok") is True, f"res_sc={res_sc}")
    except Exception as e:  # pragma: no cover
        ok &= check("sonder_cloud_exception", False, str(e))

    return 0 if ok else 1

if __name__ == "__main__":
    sys.exit(main())
