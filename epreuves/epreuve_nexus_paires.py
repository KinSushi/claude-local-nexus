#!/usr/bin/env python3
"""
Épreuve de validation de l'outil ``outillage/nexus_paires.py``.

Chaque cas est affiché sous la forme :

    [OK  ] nom_du_cas : mesure
    [RATE] nom_du_cas : mesure   (en cas d'échec)

Le script se termine avec le code de sortie 0 si tous les cas passent,
ou 1 dès le premier échec.
"""

import contextlib
import io
import sys
import shutil
import subprocess
import tempfile
import importlib.util
from pathlib import Path

# ----------------------------------------------------------------------
# Helpers d'affichage
# ----------------------------------------------------------------------
def _print_ok(name, detail=""):
    print(f"[OK  ] {name} : {detail}")

def _print_rate(name, detail=""):
    print(f"[RATE] {name} : {detail}")

def _ok(cond, name, mesure=""):
    """Affiche le résultat d'un cas en réutilisant la même description
    que la condition soit vraie ou fausse."""
    if cond:
        _print_ok(name, mesure)
    else:
        _print_rate(name, mesure)
    return cond

# ----------------------------------------------------------------------
# Chargement du module ``outillage/nexus_paires.py`` depuis le dépôt
# temporaire.
# ----------------------------------------------------------------------
def _charger_module(racine: Path):
    """Charge le module ``outillage/nexus_paires.py`` sous le nom
    ``_epreuve_nexus_paires`` et le place dans ``sys.modules``."""
    module_path = racine / "outillage" / "nexus_paires.py"
    spec = importlib.util.spec_from_file_location("_epreuve_nexus_paires", module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Impossible de créer le spec pour {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["_epreuve_nexus_paires"] = module
    try:
        spec.loader.exec_module(module)  # type: ignore[arg-type]
    except Exception:
        sys.modules.pop("_epreuve_nexus_paires", None)
        raise
    return module

# ----------------------------------------------------------------------
# Lancement des cas
# ----------------------------------------------------------------------
def _muet(fonction):
    """Exécute la fonction en masquant stdout et stderr."""
    def appel(*args, **kwargs):
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return fonction(*args, **kwargs)
    return appel


def lancer_cas():
    all_ok = True
    racine = Path(tempfile.mkdtemp())
    try:
        # ------------------------------------------------------------------
        # Création de l'arborescence minimale
        # ------------------------------------------------------------------
        (racine / "scripts").mkdir()
        (racine / "outillage").mkdir()

        # ------------------------------------------------------------------
        # Cas P1 – même contenu, différences de fins de ligne
        # ------------------------------------------------------------------
        try:
            # scripts : CRLF, outillage : LF
            (racine / "scripts" / "m.py").write_bytes(b"a = 1\r\nb = 2\r\n")
            (racine / "outillage" / "m.py").write_bytes(b"a = 1\nb = 2\n")
            # l'outil eprouve est celui du VRAI depot ; seules les donnees (scripts/, outillage/m.py) vivent dans la racine temporaire.
            mod = _charger_module(Path(__file__).resolve().parents[1])
            # Les messages de l'outil ne doivent pas être interprétés comme des cas de l'épreuve
            mod.main = _muet(mod.main)
            mod.synchroniser = _muet(mod.synchroniser)

            diverg = mod.divergentes(racine)
            ok_div = diverg == []
            verifier_ret = mod.main(['--verifier', '--racine', str(racine)])
            ok_verif = verifier_ret == 0
            mesure = f"divergentes={diverg}; verifier={verifier_ret}"
            all_ok &= _ok(ok_div and ok_verif, "P1", mesure)
        except Exception as exc:
            all_ok &= _ok(False, "P1", f"exception : {exc}")

        # ------------------------------------------------------------------
        # Cas P2 – copie en retard (source a une ligne en plus)
        # ------------------------------------------------------------------
        try:
            # ajouter une ligne supplémentaire dans scripts/m.py
            (racine / "scripts" / "m.py").write_bytes(b"a = 1\r\nb = 2\r\nc = 3\r\n")
            diverg = mod.divergentes(racine)
            ok_div = diverg == ['m.py']
            verifier_ret = mod.main(['--verifier', '--racine', str(racine)])
            ok_verif = verifier_ret == 1
            mesure = f"divergentes={diverg}; verifier={verifier_ret}"
            all_ok &= _ok(ok_div and ok_verif, "P2", mesure)
        except Exception as exc:
            all_ok &= _ok(False, "P2", f"exception : {exc}")

        # ------------------------------------------------------------------
        # Cas S1 – synchroniser(tmp, 'm')
        # ------------------------------------------------------------------
        try:
            ok_sync, lignes = mod.synchroniser(racine, 'm')
            out_bytes = (racine / "outillage" / "m.py").read_bytes()
            src_bytes = (racine / "scripts" / "m.py").read_bytes()
            ok_eq = out_bytes == src_bytes
            mesure = f"synchroniser=True={ok_sync}; lignes={lignes}; out_eq_src={ok_eq}"
            all_ok &= _ok(ok_sync and ok_eq, "S1", mesure)
        except Exception as exc:
            all_ok &= _ok(False, "S1", f"exception : {exc}")

        # ------------------------------------------------------------------
        # Cas S1b – synchroniser(tmp, 'm.py')
        # ------------------------------------------------------------------
        try:
            ok_sync, lignes = mod.synchroniser(racine, 'm.py')
            out_bytes = (racine / "outillage" / "m.py").read_bytes()
            src_bytes = (racine / "scripts" / "m.py").read_bytes()
            ok_eq = out_bytes == src_bytes
            mesure = f"synchroniser_ext=True={ok_sync}; lignes={lignes}; out_eq_src={ok_eq}"
            all_ok &= _ok(ok_sync and ok_eq, "S1b", mesure)
        except Exception as exc:
            all_ok &= _ok(False, "S1b", f"exception : {exc}")

        # ------------------------------------------------------------------
        # Cas S2 – ligne propre dans la copie
        # ------------------------------------------------------------------
        try:
            # ajouter une ligne propre dans outillage/m.py
            with open(racine / "outillage" / "m.py", "a", encoding="utf-8") as f:
                f.write("valeur_propre_a_la_copie = 42\n")
            ok_sync, lignes = mod.synchroniser(racine, 'm')
            # on attend False et la ligne propre dans la liste
            ok_false = not ok_sync
            ok_ligne = "valeur_propre_a_la_copie = 42" in lignes
            # le fichier outillage ne doit pas avoir changé (comparé au src)
            out_bytes = (racine / "outillage" / "m.py").read_bytes()
            src_bytes = (racine / "scripts" / "m.py").read_bytes()
            ok_unchanged = out_bytes != src_bytes  # il reste la ligne propre
            mesure = f"synchroniser=False={ok_false}; lignes_contient={ok_ligne}; unchanged={ok_unchanged}"
            all_ok &= _ok(ok_false and ok_ligne and ok_unchanged, "S2", mesure)
        except Exception as exc:
            all_ok &= _ok(False, "S2", f"exception : {exc}")

        # ------------------------------------------------------------------
        # Cas S3 – même état, forcer=True
        # ------------------------------------------------------------------
        try:
            ok_sync, lignes = mod.synchroniser(racine, 'm', forcer=True)
            out_bytes = (racine / "outillage" / "m.py").read_bytes()
            src_bytes = (racine / "scripts" / "m.py").read_bytes()
            ok_eq = out_bytes == src_bytes
            mesure = f"synchroniser_forcer=True={ok_sync}; out_eq_src={ok_eq}"
            all_ok &= _ok(ok_sync and ok_eq, "S3", mesure)
        except Exception as exc:
            all_ok &= _ok(False, "S3", f"exception : {exc}")

        # ------------------------------------------------------------------
        # Préparation de deux paires divergentes pour S4
        # ------------------------------------------------------------------
        try:
            # paire sûre : o.py (différence sans ligne propre)
            (racine / "scripts" / "o.py").write_text("x = 1\n", encoding="utf-8")
            (racine / "outillage" / "o.py").write_text("x = 2\n", encoding="utf-8")
            # paire avec ligne propre : n.py
            (racine / "scripts" / "n.py").write_text("y = 1\n", encoding="utf-8")
            (racine / "outillage" / "n.py").write_text("y = 1\nvaleur_propre_a_la_copie = 42\n", encoding="utf-8")
        except Exception as exc:
            all_ok &= _ok(False, "prep_S4", f"exception : {exc}")

        # ------------------------------------------------------------------
        # Cas S4 – main(--synchroniser) avec deux divergentes
        # ------------------------------------------------------------------
        try:
            ret = mod.main(['--synchroniser', '--racine', str(racine)])
            # on attend code 1
            ok_ret = ret == 1
            # o.py doit être synchronisé
            o_out = (racine / "outillage" / "o.py").read_text(encoding="utf-8")
            o_src = (racine / "scripts" / "o.py").read_text(encoding="utf-8")
            ok_o = o_out == o_src
            # n.py doit rester inchangé (conserver la ligne propre)
            n_out = (racine / "outillage" / "n.py").read_text(encoding="utf-8")
            ok_n = "valeur_propre_a_la_copie = 42" in n_out
            mesure = f"main_ret={ret}; o_sync={ok_o}; n_unchanged={ok_n}"
            all_ok &= _ok(ok_ret and ok_o and ok_n, "S4", mesure)
        except Exception as exc:
            all_ok &= _ok(False, "S4", f"exception : {exc}")

        # ------------------------------------------------------------------
        # Cas H1 – forward sync (scripts modify, outillage should follow)
        # ------------------------------------------------------------------
        try:
            depot = tempfile.mkdtemp()
            subprocess.run(['git','init'], cwd=depot, capture_output=True, check=True)
            subprocess.run(['git','config','user.email','e@e'], cwd=depot, check=True)
            subprocess.run(['git','config','user.name','e'], cwd=depot, check=True)
            (Path(depot)/'scripts').mkdir()
            (Path(depot)/'outillage').mkdir()
            # contenu avec au moins trois lignes longues (>12 caractères)
            contenu = (
                "def fonction_très_longue(parametre):\n"
                "    return parametre * 2\n"
                "# commentaire très long pour dépasser douze caractères\n"
            )
            (Path(depot)/'scripts'/'m.py').write_text(contenu, encoding='utf-8')
            (Path(depot)/'outillage'/'m.py').write_text(contenu, encoding='utf-8')
            subprocess.run(['git','add','.'], cwd=depot, capture_output=True, check=True)
            subprocess.run(['git','commit','-m','init'], cwd=depot, capture_output=True, check=True)
            # modifier le script source
            nouveau = contenu.replace('return parametre * 2', 'return parametre * 3')
            (Path(depot)/'scripts'/'m.py').write_text(nouveau, encoding='utf-8')
            ok_sync, lignes = mod.synchroniser(Path(depot), 'm')
            out_eq = (Path(depot)/'outillage'/'m.py').read_text(encoding='utf-8') == nouveau
            mesure = f"H1 sync={ok_sync}; out_eq_src={out_eq}"
            all_ok &= _ok(ok_sync and out_eq, "H1", mesure)
        except Exception as exc:
            all_ok &= _ok(False, "H1", f"exception : {exc}")
        finally:
            shutil.rmtree(depot, ignore_errors=True)

        # ------------------------------------------------------------------
        # Cas H2 – reverse sync (outillage gets clean line, source also changes)
        # ------------------------------------------------------------------
        try:
            depot = tempfile.mkdtemp()
            subprocess.run(['git','init'], cwd=depot, capture_output=True, check=True)
            subprocess.run(['git','config','user.email','e@e'], cwd=depot, check=True)
            subprocess.run(['git','config','user.name','e'], cwd=depot, check=True)
            (Path(depot)/'scripts').mkdir()
            (Path(depot)/'outillage').mkdir()
            (Path(depot)/'scripts'/'m.py').write_text(contenu, encoding='utf-8')
            (Path(depot)/'outillage'/'m.py').write_text(contenu, encoding='utf-8')
            subprocess.run(['git','add','.'], cwd=depot, capture_output=True, check=True)
            subprocess.run(['git','commit','-m','init'], cwd=depot, capture_output=True, check=True)
            # ajouter une ligne propre dans la copie outillage
            (Path(depot)/'outillage'/'m.py').write_text(contenu + "ligne_propre = 99\n", encoding='utf-8')
            # modifier le script source
            nouveau_src = contenu.replace('return parametre * 2', 'return parametre * 4')
            (Path(depot)/'scripts'/'m.py').write_text(nouveau_src, encoding='utf-8')
            ok_sync, lignes = mod.synchroniser(Path(depot), 'm')
            garde_propre = "ligne_propre = 99" in (Path(depot)/'outillage'/'m.py').read_text(encoding='utf-8')
            mesure = f"H2 sync={ok_sync}; lignes={lignes}; clean_kept={garde_propre}"
            all_ok &= _ok(not ok_sync and bool(lignes) and garde_propre, "H2", mesure)
        except Exception as exc:
            all_ok &= _ok(False, "H2", f"exception : {exc}")
        finally:
            shutil.rmtree(depot, ignore_errors=True)

        # ------------------------------------------------------------------
        # Cas H3 – dégradation (pas de dépôt git)
        # ------------------------------------------------------------------
        try:
            depot = tempfile.mkdtemp()
            (Path(depot)/'scripts').mkdir()
            (Path(depot)/'outillage').mkdir()
            (Path(depot)/'scripts'/'m.py').write_text(contenu, encoding='utf-8')
            (Path(depot)/'outillage'/'m.py').write_text(contenu + "ligne_propre = 123\n", encoding='utf-8')
            src_last = mod.source_au_dernier_commit(Path(depot), 'm.py')
            ok_none = src_last is None
            ok_sync, lignes = mod.synchroniser(Path(depot), 'm')
            mesure = f"H3 src_none={ok_none}; sync={ok_sync}; lignes={lignes}"
            all_ok &= _ok(not ok_sync and ok_none and bool(lignes), "H3", mesure)
        except Exception as exc:
            all_ok &= _ok(False, "H3", f"exception : {exc}")
        finally:
            shutil.rmtree(depot, ignore_errors=True)

        # ------------------------------------------------------------------
        # Cas L1 – lignes_propres(['    )'], [])
        # ------------------------------------------------------------------
        try:
            res = mod.lignes_propres(['    )'], [])
            ok_res = res == []
            mesure = f"lignes_propres={res}"
            all_ok &= _ok(ok_res, "L1", mesure)
        except Exception as exc:
            all_ok &= _ok(False, "L1", f"exception : {exc}")

        # ------------------------------------------------------------------
        # Cas A1 – appel main sans mode (devrait renvoyer 2)
        # ------------------------------------------------------------------
        try:
            ret = mod.main(['--racine', str(racine)])
            ok_ret = ret == 2
            mesure = f"main_ret={ret}"
            all_ok &= _ok(ok_ret, "A1", mesure)
        except Exception as exc:
            all_ok &= _ok(False, "A1", f"exception : {exc}")

        # ------------------------------------------------------------------
        # Vérification du chargement initial (attributs obligatoires)
        # ------------------------------------------------------------------
        try:
            required = ['synchroniser', 'divergentes', 'lignes_propres', 'main']
            missing = [name for name in required if not hasattr(mod, name)]
            if missing:
                _print_rate("import", f"attributs manquants : {missing}")
                sys.exit(1)
        except Exception as exc:
            _print_rate("import", f"exception lors de la vérification des attributs : {exc}")
            sys.exit(1)

    finally:
        # Nettoyage du répertoire temporaire
        shutil.rmtree(racine, onerror=lambda func, path, exc: None, ignore_errors=True)

    sys.exit(0 if all_ok else 1)

if __name__ == "__main__":
    lancer_cas()
