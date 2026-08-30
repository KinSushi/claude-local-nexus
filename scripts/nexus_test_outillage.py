#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Suite de tests ALLER / RETOUR pour l'outillage qui porte desormais tout le
cycle d'auto-amelioration du depot : nexus_fonctions.py, nexus_patch.py et
nexus_valide.py.

Pourquoi ce fichier existe : ces trois outils REECRIVENT des fichiers du
depot (Python, PowerShell) mais n'avaient jusqu'ici aucun test. C'etait le
trou le plus grave de la couverture -- un defaut dans l'un d'eux corrompt
silencieusement le depot qu'il est cense ameliorer, ou pire, execute un
script qu'il devait seulement analyser.

Deux tests portent les defauts REELS les plus instructifs, constates a
l'usage :

  * nexus_fonctions.py : une fonction AJOUTEE atterrissait apres le bloc
    `if __name__ == "__main__":`, donc n'existait pas encore quand main()
    s'executait -> NameError A L'EXECUTION, alors que la syntaxe restait
    parfaitement valide. Seule l'EXECUTION du fichier resultant peut
    attraper ce defaut ; aucune verification syntaxique ne le voit.

  * nexus_valide.py : la verification PowerShell employait `pwsh -File`,
    qui EXECUTE le script au lieu de le PARSER -- sur restore.ps1 cela
    aurait supprime les volumes Docker.

Meme forme de rapport que scripts/nexus_test.py : fonctions check()/skip(),
listes PASSED/FAILED/SKIPPED, decompte final, code de sortie 1 des qu'un
test echoue.

Contrat de securite : chaque test travaille sur des fichiers TEMPORAIRES
(tempfile.mkdtemp), jamais sur un fichier du depot. Un test qui abime le
depot qu'il verifie est pire que l'absence de test. Aucun modele n'est
appele : les deux garde-fous de nexus_patch.py sont exerces en remplacant
nexus_agent.executer par une fonction fabriquee, ce qui joue le vrai code
de l'outil (vrais garde-fous, vrai chemin d'ecriture) sans depenser un
jeton.
"""
from __future__ import annotations

import ast
import io
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, "scripts")
sys.path.insert(0, SCRIPTS)

# Meme raison que nexus_test.py : sans ceci, Python ecrit dans la page de
# code locale de Windows et les accents des commentaires/rapports se
# degradent des que la sortie est capturee.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

PASSED: list[str] = []
FAILED: list[tuple[str, str]] = []
SKIPPED: list[tuple[str, str]] = []


def check(name: str, condition: bool, detail: str = "") -> bool:
    if condition:
        PASSED.append(name)
        print("  [PASS] %-58s %s" % (name, detail))
    else:
        FAILED.append((name, detail))
        print("  [FAIL] %-58s %s" % (name, detail))
    return condition


def skip(name: str, reason: str) -> None:
    SKIPPED.append((name, reason))
    print("  [SKIP] %-58s %s" % (name, reason))


# ---------------------------------------------------------------------------
# Utilitaires communs -- fichiers temporaires uniquement
# ---------------------------------------------------------------------------

def _tmpdir() -> str:
    """Repertoire temporaire dedie, hors du depot."""
    return tempfile.mkdtemp(prefix="nexus_test_outillage_")


def _ecrire(chemin: str, contenu: str) -> None:
    with io.open(chemin, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(contenu)


def _lire(chemin: str) -> str:
    with io.open(chemin, encoding="utf-8") as fh:
        return fh.read()


def _run(args, timeout: int = 60):
    """subprocess.run avec capture texte UTF-8 et timeout par defaut."""
    return subprocess.run(args, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=timeout)


# ---------------------------------------------------------------------------
# nexus_fonctions.py -- remplacement de fonctions par bornes AST
# ---------------------------------------------------------------------------

def test_fonctions() -> None:
    """
    nexus_fonctions.py localise une fonction par l'AST (bornes 1-based,
    decorateurs inclus) puis remplace ou insere son bloc de code. Les tests
    suivent le contrat ALLER/RETOUR demande : remplacement, ajout,
    decorateurs conserves, fonctions voisines intactes (ALLER) ; bloc
    invalide -> rien ecrit + code 1, --simuler -> rien ecrit, et surtout
    l'ordre d'insertion d'une fonction ajoutee (RETOUR).
    """
    print("\n--- nexus_fonctions.py : remplacement par bornes AST ---")
    outil = os.path.join(SCRIPTS, "nexus_fonctions.py")
    d = _tmpdir()
    try:
        # ---- ALLER : remplacer une fonction existante, voisins intacts ---
        cible = os.path.join(d, "cible.py")
        original = (
            "def avant():\n"
            "    return \"avant\"\n"
            "\n"
            "\n"
            "def cible():\n"
            "    return \"vieux\"\n"
            "\n"
            "\n"
            "def apres():\n"
            "    return \"apres\"\n"
        )
        _ecrire(cible, original)
        blocs = os.path.join(d, "blocs.txt")
        _ecrire(blocs,
                "@@FONCTION cible@@\n"
                "def cible():\n"
                "    return \"neuf\"\n"
                "@@FIN@@\n")
        resultat = _run([sys.executable, outil, "--cible", cible, "--blocs", blocs])
        check("aller: remplacement d'une fonction existante -> code 0",
              resultat.returncode == 0, resultat.stdout.strip())
        nouveau = _lire(cible)
        check("aller: corps de la fonction bien remplace",
              "return \"neuf\"" in nouveau and "return \"vieux\"" not in nouveau)
        # Defaut evite : une localisation de bornes trop large qui mangerait
        # les fonctions voisines au lieu de s'arreter a la bonne ligne.
        check("aller: fonction voisine (avant) intacte",
              "def avant():\n    return \"avant\"" in nouveau)
        check("aller: fonction voisine (apres) intacte",
              "def apres():\n    return \"apres\"" in nouveau)

        # ---- ALLER : ajouter une nouvelle fonction (pas de bloc __main__) -
        cible2 = os.path.join(d, "cible2.py")
        _ecrire(cible2, "def utilitaire():\n    return 1\n")
        blocs2 = os.path.join(d, "blocs2.txt")
        _ecrire(blocs2,
                "@@FONCTION inedite@@\n"
                "def inedite():\n"
                "    return 2\n"
                "@@FIN@@\n")
        resultat = _run([sys.executable, outil, "--cible", cible2, "--blocs", blocs2])
        check("aller: ajout d'une fonction nouvelle -> code 0",
              resultat.returncode == 0, resultat.stdout.strip())
        contenu2 = _lire(cible2)
        check("aller: fonction ajoutee presente dans le fichier",
              "def inedite():" in contenu2)
        try:
            ast.parse(contenu2)
            check("aller: fichier reste syntaxiquement valide apres ajout", True)
        except SyntaxError as exc:
            check("aller: fichier reste syntaxiquement valide apres ajout", False, str(exc))

        # ---- ALLER : conserver les decorateurs d'une fonction decoree ----
        # Defaut possible si les bornes ignoraient les decorateurs : le
        # vieux decorateur resterait au-dessus du bloc remplace, duplique
        # avec celui fourni par le bloc de remplacement.
        cible3 = os.path.join(d, "cible3.py")
        _ecrire(cible3,
                "import functools\n"
                "\n"
                "\n"
                "@functools.lru_cache\n"
                "def decoree():\n"
                "    return \"vieux\"\n")
        blocs3 = os.path.join(d, "blocs3.txt")
        _ecrire(blocs3,
                "@@FONCTION decoree@@\n"
                "@functools.lru_cache\n"
                "def decoree():\n"
                "    return \"neuf\"\n"
                "@@FIN@@\n")
        resultat = _run([sys.executable, outil, "--cible", cible3, "--blocs", blocs3])
        check("aller: remplacement d'une fonction decoree -> code 0",
              resultat.returncode == 0, resultat.stdout.strip())
        contenu3 = _lire(cible3)
        check("aller: decorateur present une seule fois (pas duplique)",
              contenu3.count("@functools.lru_cache") == 1,
              "trouve %d fois" % contenu3.count("@functools.lru_cache"))
        check("aller: nouveau corps present sous le decorateur",
              "return \"neuf\"" in contenu3)

        # ---- RETOUR : bloc syntaxiquement invalide -> rien ecrit, code 1 -
        cible4 = os.path.join(d, "cible4.py")
        original4 = "def f():\n    return 1\n"
        _ecrire(cible4, original4)
        empreinte_avant = _lire(cible4)
        blocs4 = os.path.join(d, "blocs4.txt")
        _ecrire(blocs4,
                "@@FONCTION f@@\n"
                "def f(:\n"          # syntaxe cassee, deliberement
                "    return 1\n"
                "@@FIN@@\n")
        resultat = _run([sys.executable, outil, "--cible", cible4, "--blocs", blocs4])
        check("retour: bloc invalide -> code de sortie 1",
              resultat.returncode == 1, resultat.stdout.strip())
        check("retour: bloc invalide -> fichier cible intact",
              _lire(cible4) == empreinte_avant)

        # ---- RETOUR : --simuler n'ecrit rien ------------------------------
        cible5 = os.path.join(d, "cible5.py")
        original5 = "def g():\n    return 1\n"
        _ecrire(cible5, original5)
        empreinte_avant5 = _lire(cible5)
        blocs5 = os.path.join(d, "blocs5.txt")
        _ecrire(blocs5,
                "@@FONCTION g@@\n"
                "def g():\n"
                "    return 2\n"
                "@@FIN@@\n")
        resultat = _run([sys.executable, outil, "--cible", cible5, "--blocs", blocs5, "--simuler"])
        check("retour: --simuler -> code 0", resultat.returncode == 0, resultat.stdout.strip())
        check("retour: --simuler -> fichier non modifie",
              _lire(cible5) == empreinte_avant5)

        # ---- RETOUR : LE TEST LE PLUS IMPORTANT ---------------------------
        # Defaut REEL constate : une fonction AJOUTEE atterrissait apres le
        # bloc `if __name__ == "__main__":`. Elle n'existait donc pas
        # encore quand main() s'executait -> NameError A L'EXECUTION, alors
        # que la syntaxe restait parfaitement valide. Aucune verification
        # syntaxique ne peut voir ce defaut : il faut EXECUTER le fichier
        # resultant pour l'attraper. C'est ce que fait ce test.
        cible6 = os.path.join(d, "cible6.py")
        _ecrire(cible6,
                "def fonction_existante():\n"
                "    return \"existante\"\n"
                "\n"
                "\n"
                "def main():\n"
                "    print(fonction_existante())\n"
                "    print(nouvelle_fonction())\n"
                "    return 0\n"
                "\n"
                "\n"
                "if __name__ == \"__main__\":\n"
                "    import sys as _sys\n"
                "    _sys.exit(main())\n")
        blocs6 = os.path.join(d, "blocs6.txt")
        _ecrire(blocs6,
                "@@FONCTION nouvelle_fonction@@\n"
                "def nouvelle_fonction():\n"
                "    return \"nouvelle\"\n"
                "@@FIN@@\n")
        resultat = _run([sys.executable, outil, "--cible", cible6, "--blocs", blocs6])
        check("retour: insertion d'une fonction ajoutee -> code 0",
              resultat.returncode == 0, resultat.stdout.strip())
        contenu6 = _lire(cible6)
        lignes6 = contenu6.splitlines()
        idx_def = next((i for i, l in enumerate(lignes6)
                         if l.startswith("def nouvelle_fonction")), -1)
        idx_main = next((i for i, l in enumerate(lignes6)
                          if "__name__" in l and "__main__" in l), -1)
        check("retour: definition situee AVANT le bloc __main__ (structure)",
              idx_def != -1 and idx_main != -1 and idx_def < idx_main,
              "def a la ligne %d, __main__ a la ligne %d" % (idx_def + 1, idx_main + 1))
        # La preuve qui compte reellement : EXECUTER le fichier resultant.
        execution = _run([sys.executable, cible6])
        check("retour: le fichier resultant s'execute sans NameError",
              execution.returncode == 0 and "nouvelle" in execution.stdout
              and "NameError" not in execution.stderr,
              (execution.stdout.strip() + " | " + execution.stderr.strip())[:160])
    finally:
        shutil.rmtree(d, ignore_errors=True)


# ---------------------------------------------------------------------------
# nexus_patch.py -- correction par le banc puis application
# ---------------------------------------------------------------------------

def _appeler_main_patch(argv: list[str]) -> int:
    """
    Appelle nexus_patch.main() EN PROCESS (pas en sous-processus), argv
    patche, et capture le code de sortie via SystemExit.

    En process est indispensable : c'est ce qui permet au monkeypatch de
    nexus_agent.executer, pose par l'appelant, de s'appliquer. Un
    sous-processus reimporterait le vrai module nexus_agent et tenterait un
    vrai appel reseau.
    """
    import nexus_patch
    ancien_argv = sys.argv
    sys.argv = ["nexus_patch.py"] + argv
    try:
        nexus_patch.main()
        return 0
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else (1 if exc.code else 0)
    finally:
        sys.argv = ancien_argv


def test_patch() -> None:
    """
    nexus_patch.py envoie un fichier au banc gratuit et applique sa
    reponse. Les deux garde-fous demandes (taille, syntaxe) protegent le
    depot contre une reponse de modele mauvaise ou tronquee -- ils se
    testent SANS appeler aucun modele : nexus_agent.executer est remplace
    par une fonction qui renvoie un contenu FABRIQUE, ce qui exerce le vrai
    chemin de code de l'outil (vrais garde-fous, vrai `sys.exit`, vrai
    `ecrire_fichier_atomique` ou son absence) sans depenser un seul jeton.
    """
    print("\n--- nexus_patch.py : garde-fous taille et syntaxe ---")

    import nexus_patch
    import nexus_agent

    # verifier_syntaxe() est une fonction interne pure : testee directement,
    # sans passer par main() ni par un modele.
    check("aller: verifier_syntaxe accepte du python valide",
          nexus_patch.verifier_syntaxe("f.py", "def ok():\n    return 1\n") is True)
    check("retour: verifier_syntaxe rejette du python casse",
          nexus_patch.verifier_syntaxe("f.py", "def casse(:\n    return 1\n") is False)

    d = _tmpdir()
    ancien_executer = nexus_agent.executer
    ancien_cle = nexus_agent.cle_maitre
    try:
        nexus_agent.cle_maitre = lambda: "cle-factice"

        def reponse_fixe(texte, tronque=False, erreur=None):
            def _faux(tache, cle):
                return {"texte": texte, "tronque": tronque, "erreur": erreur,
                        "modele": "test-fixe", "tokens": 0, "cout": 0, "bascule": False}
            return _faux

        # ---- ALLER : --simuler n'ecrit pas --------------------------------
        cible = os.path.join(d, "aller.py")
        original = "def a():\n    return 1\n\n\ndef b():\n    return 2\n"
        _ecrire(cible, original)
        contenu_valide = "def a():\n    return 1\n\n\ndef b():\n    return 3\n"
        nexus_agent.executer = reponse_fixe("@@FICHIER@@\n" + contenu_valide + "@@FIN@@\n")
        code = _appeler_main_patch(["--cible", cible, "--consigne-texte", "x", "--simuler"])
        check("aller: --simuler -> code 0", code == 0, "code=%s" % code)
        check("aller: --simuler -> rien ecrit sur disque", _lire(cible) == original)

        # ---- RETOUR : perte de plus de 40% des lignes -> refuse ----------
        cible2 = os.path.join(d, "taille.py")
        original2 = "".join("def f%d():\n    return %d\n\n\n" % (i, i) for i in range(10))
        _ecrire(cible2, original2)
        # Le banc "renvoie" un fichier reduit a 15 lignes sur 40 d'origine
        # (perte de 62.5%, tres au-dela du seuil de 40% -- marge large,
        # aucun risque d'effet de bord sur une frontiere exacte).
        tronque = "\n".join(original2.splitlines()[:15]) + "\n"
        nexus_agent.executer = reponse_fixe("@@FICHIER@@\n" + tronque + "@@FIN@@\n")
        code = _appeler_main_patch(["--cible", cible2, "--consigne-texte", "x"])
        check("retour: fichier ampute de 40%+ des lignes -> refuse (code != 0)",
              code != 0, "code=%s" % code)
        check("retour: fichier ampute -> original conserve sur disque",
              _lire(cible2) == original2)

        # ---- RETOUR : syntaxe cassee -> original conserve -----------------
        cible3 = os.path.join(d, "syntaxe.py")
        original3 = "def a():\n    return 1\n"
        _ecrire(cible3, original3)
        casse = "def a(:\n    return 1\n"
        nexus_agent.executer = reponse_fixe("@@FICHIER@@\n" + casse + "@@FIN@@\n")
        code = _appeler_main_patch(["--cible", cible3, "--consigne-texte", "x"])
        check("retour: syntaxe cassee -> refuse (code != 0)",
              code != 0, "code=%s" % code)
        check("retour: syntaxe cassee -> original conserve sur disque",
              _lire(cible3) == original3)
    finally:
        nexus_agent.executer = ancien_executer
        nexus_agent.cle_maitre = ancien_cle
        shutil.rmtree(d, ignore_errors=True)


# ---------------------------------------------------------------------------
# nexus_valide.py -- batterie mecanique
# ---------------------------------------------------------------------------

def test_valide() -> None:
    """
    nexus_valide.py fait passer une batterie mecanique (syntaxe Python,
    syntaxe PowerShell, conformite) avant tout appel au banc gratuit. Le
    test critique porte sur check_powershell_syntax : elle doit PARSER un
    script .ps1 sans jamais l'EXECUTER. Defaut REEL vise : un usage de
    `pwsh -File`, qui execute au lieu de parser -- sur restore.ps1 cela
    aurait supprime les volumes Docker. On le verifie en ecrivant un script
    TEMOIN qui cree un fichier quand il s'execute, en le faisant "verifier",
    et en s'assurant que ce fichier n'apparait jamais.
    """
    print("\n--- nexus_valide.py : batterie mecanique ---")

    try:
        import nexus_valide
    except Exception as exc:
        skip("nexus_valide.py : import du module", "echec d'import (%s)" % exc)
        return

    d = _tmpdir()
    try:
        # ---- ALLER : python valide -> aucune erreur mecanique ------------
        py_valide = os.path.join(d, "valide.py")
        _ecrire(py_valide, "def ok():\n    return 1\n")
        try:
            nexus_valide.check_python_syntax(py_valide)
            check("aller: python valide -> aucune erreur mecanique", True)
        except Exception as exc:
            check("aller: python valide -> aucune erreur mecanique", False, str(exc))

        # Le depot lui-meme est le cas "propre" le plus direct : ce test
        # verifie nexus_valide.py PAR nexus_valide.py, en lecture seule
        # (aucune ecriture sur un fichier du depot).
        try:
            nexus_valide.check_python_syntax(os.path.join(SCRIPTS, "nexus_valide.py"))
            check("aller: sur un depot propre, aucune erreur mecanique (auto-verification)", True)
        except Exception as exc:
            check("aller: sur un depot propre, aucune erreur mecanique (auto-verification)",
                  False, str(exc))

        # ---- ALLER (miroir) : python casse -> erreur mecanique levee -----
        py_casse = os.path.join(d, "casse.py")
        _ecrire(py_casse, "def casse(:\n    return 1\n")
        leve = False
        try:
            nexus_valide.check_python_syntax(py_casse)
        except Exception:
            leve = True
        check("aller: python casse -> erreur mecanique levee", leve)

        # ---- ALLER : detection de signature changee -----------------------
        diff_change = "-def calculer(a, b):\n+def calculer(a, b, c):\n"
        changees = nexus_valide.extract_changed_functions(diff_change)
        check("aller: changement de signature detecte", changees == ["calculer"], str(changees))

        # Un renommage n'est PAS un non-evenement : `calculer` disparait et
        # tous ses appelants cassent. L'attente precedente etait [] , ce qui
        # verrouillait l'angle mort au lieu de le signaler.
        diff_renomme = "-def calculer(a, b):\n+def autre(a, b):\n"
        changees2 = nexus_valide.extract_changed_functions(diff_renomme)
        check("aller: renommage -> les deux noms signales",
              changees2 == ["autre", "calculer"], str(changees2))

        # Corps modifie sans toucher a la signature : le cas le plus courant,
        # et celui qui echappait entierement a la detection. Le nom vient du
        # contexte que git place apres le second @@.
        diff_corps = "@@ -10,7 +10,7 @@ def calculer(a, b):\n-    return a + b\n+    return a - b\n"
        changees3 = nexus_valide.extract_changed_functions(diff_corps)
        check("aller: corps modifie detecte par le contexte de hunk",
              changees3 == ["calculer"], str(changees3))

        # Une fonction sans aucun appelant ne doit plus lever : la levee
        # faisait rendre le code 2, qui pousse vers un agent PAYANT.
        sans_appelant = nexus_valide.find_callers(["ZZZ_fonction_inexistante_ZZZ"])
        check("retour: fonction sans appelant -> liste vide, pas d'exception",
              sans_appelant == {"ZZZ_fonction_inexistante_ZZZ": []}, str(sans_appelant))

        # Le verdict n'est jamais en tete de ligne : build_task impose le
        # format « <nom> : VERDICT - phrase ».
        check("aller: REGRESSION lue au milieu de la ligne",
              nexus_valide.analyse_result("_safe_int : REGRESSION - signature cassee"))
        check("retour: INDETERMINE citant REGRESSION ne compte pas",
              not nexus_valide.analyse_result("x : INDETERMINE - aucune REGRESSION visible"))

        # ---- ALLER / RETOUR : validate_base --------------------------------
        leve = False
        try:
            nexus_valide.validate_base("HEAD~1")
        except Exception:
            leve = True
        check("aller: validate_base accepte une reference normale", not leve)

        leve = False
        try:
            nexus_valide.validate_base("--evil")
        except ValueError:
            leve = True
        check("retour: validate_base refuse une valeur qui ressemble a une option", leve)

        # ---- RETOUR : LE TEST CRITIQUE -------------------------------------
        if shutil.which("pwsh") is None:
            skip("retour: verification PowerShell n'execute jamais le script",
                 "pwsh introuvable dans le PATH de cet environnement")
        else:
            temoin = os.path.join(d, "temoin.txt")
            script_ps1 = os.path.join(d, "sonde.ps1")
            _ecrire(script_ps1,
                    "Set-Content -Path '%s' -Value 'EXECUTE'\n" % temoin.replace("'", "''"))
            erreur_outil = None
            try:
                nexus_valide.check_powershell_syntax(script_ps1)
            except Exception as exc:
                # Une erreur ici ne tranche rien seule : seule la presence
                # du temoin prouve si le script a ete execute.
                erreur_outil = str(exc)
            temoin_existe = os.path.exists(temoin)
            check("retour: verification PowerShell n'execute jamais le script",
                  not temoin_existe,
                  "le temoin existe : le script a ete EXECUTE, pas seulement parse"
                  if temoin_existe else
                  ("temoin absent (erreur outil: %s)" % erreur_outil if erreur_outil
                   else "temoin absent, aucune erreur"))
    finally:
        shutil.rmtree(d, ignore_errors=True)


# ---------------------------------------------------------------------------
# Rapport final -- meme forme que scripts/nexus_test.py
# ---------------------------------------------------------------------------

def main() -> int:
    print("=" * 72)
    print(" Suite de tests -- outillage d'auto-amelioration (aller/retour)")
    print("=" * 72)

    # Chaque famille est isolee : une exception inattendue dans l'une (ex.
    # timeout sous-processus) ne doit pas empecher les deux autres de
    # rendre leur verdict.
    for nom, fonction in (("nexus_fonctions.py", test_fonctions),
                           ("nexus_patch.py", test_patch),
                           ("nexus_valide.py", test_valide)):
        try:
            fonction()
        except Exception as exc:
            check("%s : suite interrompue par une exception" % nom, False, str(exc))

    print("\n" + "=" * 72)
    print("  Reussis : %d    Echecs : %d    Ignores : %d"
          % (len(PASSED), len(FAILED), len(SKIPPED)))
    if FAILED:
        print("\n  Echecs :")
        for name, detail in FAILED:
            print("    - %s  (%s)" % (name, detail))
    print("=" * 72)
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
