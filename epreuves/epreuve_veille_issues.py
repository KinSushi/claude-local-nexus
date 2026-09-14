# -*- coding: utf-8 -*-
"""Épreuve fonctionnelle pour les fonctions `executer`, `issues_generation`
et `verdict` du module `outillage/nexus_veille_moteur.py`.

Chaque cas écrit sur STDOUT une ligne commençant exactement par
`[OK  ] ` (OK suivi de deux espaces) ou `[RATE] `, puis le nom du cas,
un deux‑points et un détail optionnel.
Le code de sortie du processus est 0 si tous les cas réussissent,
1 sinon.

Utilisation :
    python epreuves/epreuve_veille_issues.py
"""

import datetime
import importlib.util
import pathlib
import sys
import tempfile
import os

# ----------------------------------------------------------------------
# Chargement du module à tester (chemin relatif à la racine du dépôt)
# ----------------------------------------------------------------------
def _load_module():
    repo_root = pathlib.Path(__file__).resolve().parents[1]   # dépôt racine
    module_path = repo_root / "outillage" / "nexus_veille_moteur.py"
    spec = importlib.util.spec_from_file_location("nexus_veille_moteur", str(module_path))
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod, repo_root

# ----------------------------------------------------------------------
# Helpers d’affichage
# ----------------------------------------------------------------------
def _check(nom, condition, detail=""):
    if condition:
        print(f"[OK  ] {nom} : {detail}")
    else:
        print(f"[RATE] {nom} : {detail}")
    return condition

# ----------------------------------------------------------------------
# Fausse implémentation des fonctions réseau / relance
# ----------------------------------------------------------------------
class _Fakes:
    """Fonctions factices et compteurs d’appels."""
    relancer_calls = 0
    purger_calls = 0
    modify_journal = False   # si True, la sonde ajoute une ligne au journal
    current_journal_path = None

    @staticmethod
    def version_repond(url):
        # Toujours disponible
        return True

    @staticmethod
    def lire_ps(url):
        # Aucun modèle « coincé », aucun modèle listé
        return {}

    @staticmethod
    def sonder(url, modele, delai, num_predict=4, num_ctx=None):
        # Simule une sonde qui échoue (return False)
        if _Fakes.modify_journal and _Fakes.current_journal_path:
            with open(_Fakes.current_journal_path, "a", encoding="utf-8") as f:
                f.write("[GIN] dummy modification\n")
        return False

    @staticmethod
    def relancer_moteur(racine):
        _Fakes.relancer_calls += 1
        # Simule un redémarrage réussi
        return True

    @staticmethod
    def purger_orphelins(cible='llama-server.exe', module=None):
        _Fakes.purger_calls += 1
        # Retourne une liste vide pour éviter toute interaction réelle
        return []

# ----------------------------------------------------------------------
# Construction d’un journal de test à partir du texte fourni
# ----------------------------------------------------------------------
def _ecrire_journal(base_dir, lignes):
    """Crée un fichier journal contenant les lignes fournies."""
    chemin = os.path.join(base_dir, "journal.txt")
    with open(chemin, "w", encoding="utf-8") as f:
        f.write("\n".join(lignes))
    return chemin

# ----------------------------------------------------------------------
# Cas de test pour `issues_generation` (famille A)
# ----------------------------------------------------------------------
def _test_issues_generation():
    mod, _ = _load_module()
    now = datetime.datetime.now()
    ok = True

    # Forward – 3 lignes valides dans la fenêtre
    with tempfile.TemporaryDirectory() as td:
        lignes = [
            f"[GIN] {(now - datetime.timedelta(seconds=60)).strftime('%Y/%m/%d - %H:%M:%S')} | 200 | 10s | 127.0.0.1 | POST \"/api/chat\"",
            f"[GIN] {(now - datetime.timedelta(seconds=50)).strftime('%Y/%m/%d - %H:%M:%S')} | 200 | 12s | 127.0.0.1 | POST \"/api/generate\"",
            f"[GIN] {(now - datetime.timedelta(seconds=40)).strftime('%Y/%m/%d - %H:%M:%S')} | 500 | 14m59s | 127.0.0.1 | POST \"/v1/chat/completions\""
        ]
        journal_path = _ecrire_journal(td, lignes)
        maintenant_iso = now.astimezone(datetime.timezone.utc).isoformat()
        result = mod.issues_generation(journal_path, maintenant_iso, fenetre_s=1800)
        ok &= _check("issues_forward_reussies", result.get("reussies") == 2)
        ok &= _check("issues_forward_echecs_longs", result.get("echecs_longs") == 1)
        ok &= _check("issues_forward_illisibles", result.get("illisibles", 0) == 0)

    # Reverse – ligne hors fenêtre
    with tempfile.TemporaryDirectory() as td:
        lignes = [
            f"[GIN] {(now - datetime.timedelta(seconds=7200)).strftime('%Y/%m/%d - %H:%M:%S')} | 200 | 10s | 127.0.0.1 | POST \"/api/chat\""
        ]
        journal_path = _ecrire_journal(td, lignes)
        maintenant_iso = now.astimezone(datetime.timezone.utc).isoformat()
        result = mod.issues_generation(journal_path, maintenant_iso, fenetre_s=1800)
        ok &= _check("issues_reverse_reussies", result.get("reussies") == 0)
        ok &= _check("issues_reverse_illisibles", result.get("illisibles", 0) == 0)

    # Fuite – ligne illisible (format correct mais date impossible)
    with tempfile.TemporaryDirectory() as td:
        lignes = [
            "[GIN] 2026/13/45 - 25:61:61 | 200 | 10s | 127.0.0.1 | POST \"/api/chat\""
        ]
        journal_path = _ecrire_journal(td, lignes)
        maintenant_iso = now.astimezone(datetime.timezone.utc).isoformat()
        result = mod.issues_generation(journal_path, maintenant_iso, fenetre_s=1800)
        ok &= _check("issues_fuite_illisibles", result.get("illisibles", 0) == 1)
        ok &= _check("issues_fuite_reussies", result.get("reussies") == 0)

    return ok

# ----------------------------------------------------------------------
# Cas de test pour `verdict` (famille B)
# ----------------------------------------------------------------------
def _test_verdict_cases():
    mod, _ = _load_module()
    ok = True

    # 1. 0 réussite, 3 échecs longs → BLOQUE (règle prioritaire)
    ok &= _check(
        "verdict_B1",
        mod.verdict([], None, None, {"reussies": 0, "echecs_longs": 3}) == "BLOQUE",
        "attendu BLOQUE"
    )

    # 2. 1 réussite, 3 échecs longs → SAIN (pas de blocage car il y a une réussite)
    ok &= _check(
        "verdict_B2",
        mod.verdict([], None, None, {"reussies": 1, "echecs_longs": 3}) == "SAIN",
        "attendu SAIN"
    )

    # 3. 0 réussite, 2 échecs longs → SAIN (pas assez d'échecs longs)
    ok &= _check(
        "verdict_B3",
        mod.verdict([], None, None, {"reussies": 0, "echecs_longs": 2}) == "SAIN",
        "attendu SAIN"
    )

    # 4. modèle coincé, sonde KO, journal_avance=False → BLOQUE
    ok &= _check(
        "verdict_B4",
        mod.verdict(["m"], False, False, None) == "BLOQUE",
        "attendu BLOQUE"
    )

    # 5. modèle coincé, sonde OK, journal_avance=None → SUSPECT
    ok &= _check(
        "verdict_B5",
        mod.verdict(["m"], True, None, None) == "SUSPECT",
        "attendu SUSPECT"
    )

    # 6. aucun modèle coincé, sonde KO, journal_avance=True → SUSPECT
    ok &= _check(
        "verdict_B6",
        mod.verdict([], False, True, None) == "SUSPECT",
        "attendu SUSPECT"
    )

    return ok

# ----------------------------------------------------------------------
# Helper pour exécuter un cas C (exécution) avec journal personnalisé
# ----------------------------------------------------------------------
def _run_case_c(nom, lignes, relancer_flag, expect_verdict,
                expect_relancer_calls, expect_purger_calls,
                modify_journal=False):
    ok = True
    with tempfile.TemporaryDirectory() as td:
        journal_path = _ecrire_journal(td, lignes)
        _Fakes.current_journal_path = journal_path
        _Fakes.modify_journal = modify_journal
        _Fakes.relancer_calls = 0
        _Fakes.purger_calls = 0

        mod, _ = _load_module()
        # injection des fakes
        mod.version_repond = _Fakes.version_repond
        mod.lire_ps = _Fakes.lire_ps
        mod.sonder = _Fakes.sonder
        mod.relancer_moteur = _Fakes.relancer_moteur
        mod.purger_orphelins = _Fakes.purger_orphelins

        result = mod.executer(
            url="http://127.0.0.1:11434",
            modele_sonde=None,
            delai_sonde=75,
            seuil_stopping=120,
            relancer=relancer_flag,
            journal=journal_path,
            journal_gin=journal_path,
        )

        # calcul du verdict réel via la fonction verdict du module
        issues = mod.issues_generation(
            journal_path,
            mod.datetime.datetime.now(mod.datetime.timezone.utc).isoformat(),
            fenetre_s=1800
        )
        real_verdict = mod.verdict(
            coinces=result.get("coinces", []),
            sonde_ok=result.get("sonde_ok"),
            journal_avance=result.get("journal_avance"),
            issues=issues
        )
        ok &= _check(f"{nom}_verdict", real_verdict == expect_verdict,
                     f"attendu {expect_verdict}, obtenu {real_verdict}")
        ok &= _check(f"{nom}_relancer_calls",
                     _Fakes.relancer_calls == expect_relancer_calls,
                     f"attendu {expect_relancer_calls}, obtenu {_Fakes.relancer_calls}")
        ok &= _check(f"{nom}_purger_calls",
                     _Fakes.purger_calls == expect_purger_calls,
                     f"attendu {expect_purger_calls}, obtenu {_Fakes.purger_calls}")
    return ok

# ----------------------------------------------------------------------
# Cas de test pour `executer` (famille C)
# ----------------------------------------------------------------------
def _test_executer_cases():
    mod, _ = _load_module()
    now = datetime.datetime.now()
    ok = True

    # C‑forward : trois échecs longs, aucune réussite, relancer=True → BLOQUE
    lignes_forward = [
        f"[GIN] {(now - datetime.timedelta(seconds=300)).strftime('%Y/%m/%d - %H:%M:%S')} | 500 | 14m59s | 127.0.0.1 | POST \"/api/chat\"",
        f"[GIN] {(now - datetime.timedelta(seconds=200)).strftime('%Y/%m/%d - %H:%M:%S')} | 500 | 14m59s | 127.0.0.1 | POST \"/api/chat\"",
        f"[GIN] {(now - datetime.timedelta(seconds=100)).strftime('%Y/%m/%d - %H:%M:%S')} | 500 | 14m59s | 127.0.0.1 | POST \"/api/chat\""
    ]
    ok &= _run_case_c(
        "forward",
        lignes_forward,
        relancer_flag=True,
        expect_verdict="BLOQUE",
        expect_relancer_calls=1,
        expect_purger_calls=1,
        modify_journal=False
    )

    # C‑reverse : même journal + une réussite, relancer=True → SAIN
    lignes_reverse = lignes_forward + [
        f"[GIN] {(now - datetime.timedelta(seconds=50)).strftime('%Y/%m/%d - %H:%M:%S')} | 200 | 10s | 127.0.0.1 | POST \"/api/chat\""
    ]
    ok &= _run_case_c(
        "reverse",
        lignes_reverse,
        relancer_flag=True,
        expect_verdict="SAIN",
        expect_relancer_calls=0,
        expect_purger_calls=0,
        modify_journal=False
    )

    # C‑fuite : même journal que forward, relancer=False → BLOQUE
    ok &= _run_case_c(
        "fuite",
        lignes_forward,
        relancer_flag=False,
        expect_verdict="BLOQUE",
        expect_relancer_calls=0,
        expect_purger_calls=0,
        modify_journal=False
    )

    return ok

# ----------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------
def main():
    overall_ok = True

    # Famille A
    overall_ok &= _test_issues_generation()

    # Famille B
    overall_ok &= _test_verdict_cases()

    # Famille C
    overall_ok &= _test_executer_cases()

    sys.exit(0 if overall_ok else 1)

if __name__ == "__main__":
    main()
