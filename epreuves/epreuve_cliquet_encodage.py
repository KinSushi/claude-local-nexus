# -*- coding: utf-8 -*-
"""
Cliquet d'encodage cp1252.

Mesure : sur cette machine la console Windows est en cp1252. Un `print`
portant un caractere non encodable en cp1252 leve UnicodeEncodeError et
tue le script. Ce fichier parcourt les sources Python du depot, detecte
ceux qui emettent un tel caractere sans protection, et verifie que la
liste TOLERES ne peut que retrecir.
"""
from __future__ import annotations

import ast
import argparse
import sys
import contextlib
from pathlib import Path


# Les trois premiers sont DELIBERES et ne seront jamais retires :
# les deux console_tools.py affichent expres les caracteres qui tombaient,
# epreuve_garde_shell.py eprouve expres une console cp1252.
TOLERES = [
    "scripts/console_tools.py",
    "outillage/console_tools.py",
    "epreuves/epreuve_garde_shell.py",
    "outillage/nexus_indexer_ast.py",
    "outillage/nexus_indexer_concepts.py",
    "outillage/nexus_indexer_resumes.py",
    "outillage/nexus_indexer_texte.py",
]


def _char_hors_cp1252(caractere: str) -> bool:
    """Vrai si le caractere ne peut pas s'encoder en cp1252."""
    try:
        caractere.encode("cp1252")
    except UnicodeEncodeError:
        return True
    return False


def _chaine_hors_cp1252(valeur: str) -> bool:
    """Vrai si au moins un caractere de la chaine echoue en cp1252."""
    for caractere in valeur:
        if _char_hors_cp1252(caractere):
            return True
    return False


def _qualifier(source: str):
    """Rend le couple (emet, protege) pour le code source donne.

    - emet   : un appel a print contient dans son sous-arbre une chaine
               litterale avec au moins un caractere non encodable en cp1252.
    - protege : le fichier importe console_tools ET appelle une fonction
                dont le nom contient forcer_utf8, OU il appelle
                une methode reconfigure avec le mot-cle encoding.
    """
    try:
        arbre = ast.parse(source)
    except SyntaxError:
        return False, False

    # 1. Detection des imports de console_tools.
    import_console_tools = False
    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.ImportFrom):
            module = noeud.module or ""
            if module.endswith("console_tools"):
                import_console_tools = True
        elif isinstance(noeud, ast.Import):
            for alias in noeud.names:
                if alias.name.endswith("console_tools"):
                    import_console_tools = True

    # 2. Detection des appels a forcer_utf8 (nom contenant forcer_utf8).
    appel_forcer_utf8 = False
    for noeud in ast.walk(arbre):
        if not isinstance(noeud, ast.Call):
            continue
        fonction = noeud.func
        nom = ""
        if isinstance(fonction, ast.Name):
            nom = fonction.id
        elif isinstance(fonction, ast.Attribute):
            nom = fonction.attr
        if "forcer_utf8" in nom:
            appel_forcer_utf8 = True

    # 3. Detection d'un appel a reconfigure(encoding=...).
    reconfigure_encoding = False
    for noeud in ast.walk(arbre):
        if not isinstance(noeud, ast.Call):
            continue
        fonction = noeud.func
        if isinstance(fonction, ast.Attribute) and fonction.attr == "reconfigure":
            for mot_cle in noeud.keywords:
                if mot_cle.arg == "encoding":
                    reconfigure_encoding = True

    protege = (import_console_tools and appel_forcer_utf8) or reconfigure_encoding

    # 4. Detection d'emission : appel a print contenant une chaine hors cp1252.
    emet = False
    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.Call) and isinstance(noeud.func, ast.Name) and noeud.func.id == "print":
                for descendant in ast.walk(noeud):
                    if (
                        isinstance(descendant, ast.Constant)
                        and isinstance(descendant.value, str)
                        and _chaine_hors_cp1252(descendant.value)
                    ):
                        emet = True
                        break
        if emet:
            break

    return emet, protege


def _racine() -> Path:
    """Racine du depot : parent du repertoire de ce fichier."""
    return Path(__file__).resolve().parent.parent


def _installer_forcer_utf8():
    """Ajoute outillage a sys.path, importe et appelle forcer_utf8."""
    racine = _racine()
    outillage = str(racine / "outillage")
    if outillage not in sys.path:
        sys.path.insert(0, outillage)
    try:
        from console_tools import forcer_utf8

        forcer_utf8()
    except ImportError as exc:
        sys.stderr.write("Echec import forcer_utf8 : %s\n" % exc)


def _parcourir_sources(racine: Path):
    """Rend les chemins .py relatifs de scripts/, outillage/ et epreuves/."""
    for repertoire in ("scripts", "outillage", "epreuves"):
        chemin = racine / repertoire
        if not chemin.is_dir():
            continue
        for fichier in chemin.rglob("*.py"):
            if fichier.is_file():
                relatif = fichier.relative_to(racine).as_posix()
                yield relatif, fichier


def _fichiers_fautifs(racine: Path):
    """Liste des fichiers fautifs, chemins relatifs tries."""
    fautifs = []
    for relatif, chemin in _parcourir_sources(racine):
        try:
            source = chemin.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        emet, protege = _qualifier(source)
        if emet and not protege:
            fautifs.append(relatif)
    return sorted(fautifs)


def _executer_audit():
    """Cliquet principal : compare les fautifs mesures a TOLERES."""
    racine = _racine()
    fautifs = _fichiers_fautifs(racine)
    toleres_set = set(TOLERES)

    manquants = [p for p in fautifs if p not in toleres_set]
    obsoletes = [p for p in TOLERES if p not in fautifs]

    print("Fichiers fautifs mesures : %d" % len(fautifs))
    for chemin in manquants:
        print("Nouveau fautif (a corriger ou ajouter a TOLERES) : %s" % chemin)
    for chemin in obsoletes:
        print("Chemin tolere inutile (a retirer de TOLERES) : %s" % chemin)
    if not manquants and not obsoletes:
        print("Aucun ecart : le cliquet est coherent.")

    return 1 if (manquants or obsoletes) else 0


def _executer_contre_epreuve():
    """Verifie que _qualifier distingue un module non protege d'un protege."""
    racine = _racine()
    dossier = racine / "epreuves"
    nom = "_contre_epreuve_cliquet_encodage_jetable.py"
    chemin = dossier / nom

    etape1 = '''# -*- coding: utf-8 -*-
print("contre-epreuve hors cp1252: \\u2605")
'''
    etape2 = '''# -*- coding: utf-8 -*-
from console_tools import forcer_utf8
forcer_utf8()
print("contre-epreuve hors cp1252: \\u2605")
'''

    ok_global = True
    try:
        # Etape 1 : sans garde -> fautif.
        chemin.write_text(etape1, encoding="utf-8")
        emet1, protege1 = _qualifier(etape1)
        fautif1 = emet1 and not protege1
        print("=== Contre-epreuve etape 1 : module sans garde ===")
        print("Attendu : fautif ; obtenu : %s" % ("fautif" if fautif1 else "non fautif"))
        if not fautif1:
            ok_global = False

        # Etape 2 : avec forcer_utf8 -> non fautif.
        chemin.write_text(etape2, encoding="utf-8")
        emet2, protege2 = _qualifier(etape2)
        fautif2 = emet2 and not protege2
        print("=== Contre-epreuve etape 2 : module avec forcer_utf8 ===")
        print(
            "Attendu : non fautif ; obtenu : %s"
            % ("fautif" if fautif2 else "non fautif")
        )
        if fautif2:
            ok_global = False

        if ok_global:
            print("Conclusion : les deux etapes tombent juste")
        else:
            print("Conclusion : au moins une etape est fausse")
    finally:
        with contextlib.suppress(FileNotFoundError):
            chemin.unlink()

    return 0 if ok_global else 1


def main(argv=None):
    _installer_forcer_utf8()

    analyseur = argparse.ArgumentParser(description="Cliquet d'encodage cp1252")
    analyseur.add_argument(
        "--contre-epreuve",
        action="store_true",
        help="Lance la contre-epreuve du qualifier",
    )
    arguments = analyseur.parse_args(argv)

    if arguments.contre_epreuve:
        code = _executer_contre_epreuve()
    else:
        code = _executer_audit()
    sys.exit(code)


if __name__ == "__main__":
    main()
