#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
DEFAUT ORIGINALE : chaque fonction _run_* renvoyait une LISTE de violations.
Lorsque l'outil etait absent, que la commande plantait ou que le JSON était
illisible, la fonction retournait [] .  Une liste vide était alors
indiscernable d'un vrai "zero violation", ce qui faisait apparaître
un faux‑negatif : le rapport affichait "0 violation" alors que l'outil n'avait
jamais tourné.  Le code de sortie pouvait aussi rester 0, masquant l'absence
ou la défaillance de l'outil.

CORRECTION APPORTEE : chaque fonction _run_* renvoie maintenant un DICTIONNAIRE
avec les clés suivantes :
    {'outil': <nom>, 'etat': 'joue'|'absent'|'casse',
     'violations': [...], 'detail': <raison>}
- 'joue'   : l'outil a exécuté et a produit un résultat exploitable (violations
            peut être vide, ce qui représente un vrai zéro).
- 'absent' : l'outil n'est pas installé ou le binaire est introuvable.
- 'casse'  : l'outil a exécuté mais la sortie est inutilisable (JSON invalide,
            code de retour inattendu, timeout, etc.).

Le rapport à l'écran indique explicitement l'état de chaque outil et ne
mentionne jamais "0 violation" pour un outil qui n'a pas tourné.  Le code de
sortie suit la spécification :
    0 – au moins un outil a joué et aucune violation.
    1 – au moins une violation trouvée.
    2 – aucun outil n'a joué ou un outil est cassé.
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import List, Dict, Any

# ----------------------------------------------------------------------
# Constantes
# ----------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
# LA RACINE DU DEPOT, ET NON scripts/.
#
# CE QUI ETAIT FAUX, mesure le 2026-08-31 en executant l'outil : les trois
# linters etaient lances avec `cwd=BASE_DIR`, c'est-a-dire depuis `scripts/`,
# sur les chemins « scripts » et « tools ». Or `scripts/scripts` et
# `scripts/tools` n'existent pas. Ruff analysait donc LE VIDE et le rapport
# annoncait « ruff : JOUE (0 violations) » -- l'etat le plus dangereux
# possible, puisqu'il porte le sceau « joue » qui distingue le vrai zero.
#
# Depuis la racine, la meme commande rend 91 violations. Le faux negatif
# avait survecu a une reecriture entiere dont c'etait pourtant l'objet :
# on avait corrige la maniere de RAPPORTER une non-mesure sans voir que la
# mesure elle-meme portait a cote.
#
# Le repertoire d'outillage descend a la racine par la meme occasion :
# `scripts/.nexus/` est l'ANCIEN chemin, et la porte de conformite le
# signale deja en ALERTE pour les sauvegardes qui y trainent.
RACINE = BASE_DIR.parent
OUTIL_DIR = RACINE / ".nexus" / "outillage"
RUFF_VENV = OUTIL_DIR / "ruff_venv"
# SOUS WINDOWS, LE BINAIRE PORTE UNE EXTENSION.
#
# Mesure du 2026-08-31 : l'installateur annoncait « Ruff installe avec
# succes » et la detection le declarait ABSENT au meme instant, parce
# qu'elle cherchait « Scripts/ruff » la ou le venv pose « Scripts/ruff.exe ».
# Un detecteur rendu muet par le nom qu'on lui donne -- et le rapport,
# lui, disait alors « 0 violation » en toute bonne foi.
RUFF_BIN = (RUFF_VENV / ("Scripts" if os.name == "nt" else "bin")
            / ("ruff.exe" if os.name == "nt" else "ruff"))
ESLINT_BIN = OUTIL_DIR / "node_modules" / ".bin" / ("eslint.cmd" if os.name == "nt" else "eslint")
# ESLINT 9+ A SUPPRIME LE FORMAT .eslintrc, ET 10 A SUPPRIME --no-eslintrc.
#
# Mesure du 2026-08-31 : la version disponible est 10.9.1. L'installateur
# ecrivait une configuration au format herite que cette version ne sait plus
# lire, et la commande passait un drapeau qui n'existe plus. L'outil se
# serait rapporte « casse » apres installation reussie -- ou pire, aurait
# rendu zero.
ESLINT_CONFIG = OUTIL_DIR / "eslint.config.mjs"
ESLINT_CONFIG_TEXTE = """export default [
  {
    files: ["**/*.js"],
    languageOptions: {
      ecmaVersion: 2023,
      sourceType: "commonjs",
      globals: {
        require: "readonly", module: "writable", process: "readonly",
        console: "readonly", Buffer: "readonly", __dirname: "readonly",
        __filename: "readonly", setTimeout: "readonly", clearTimeout: "readonly",
        setInterval: "readonly", clearInterval: "readonly", exports: "writable",
        URL: "readonly", TextEncoder: "readonly", TextDecoder: "readonly",
        fetch: "readonly", AbortController: "readonly", structuredClone: "readonly",
      },
    },
    rules: {
      "no-undef": "error",
      "no-unused-vars": ["error", { args: "none", varsIgnorePattern: "^_" }],
      "no-unreachable": "error",
      "no-constant-condition": "error",
      "no-dupe-keys": "error",
      "no-dupe-args": "error",
      "no-duplicate-case": "error",
      "no-self-compare": "error",
      "no-unsafe-negation": "error",
      "no-async-promise-executor": "error",
      "require-atomic-updates": "error",
      "no-fallthrough": "error",
      "valid-typeof": "error",
      "use-isnan": "error",
    },
  },
]
"""

PS_ANALYZER_RULES = [
    "PSAvoidUsingEmptyCatchBlock",
    "PSUseDeclaredVarsMoreThanAssignments",
    "PSAvoidAssignmentToAutomaticVariable",
    "PSAvoidOverwritingBuiltInCmdlets",
    "PSReviewUnusedParameter",
    "PSAvoidGlobalVars",
    "PSUseApprovedVerbs",
]

# TRENTE SECONDES NE SUFFISENT PAS A RATISSER LE DEPOT ENTIER.
# `Invoke-ScriptAnalyzer -Path . -Recurse` depuis la racine parcourt aussi
# .git et .nexus. Une expiration se serait rapportee « casse - timeout »,
# c'est-a-dire une panne inventee, exactement le defaut corrige au-dessus.
TIMEOUT = 240  # secondes

# ----------------------------------------------------------------------
# Fonctions utilitaires
# ----------------------------------------------------------------------


def _run_cmd(cmd: List[str], cwd: Path) -> subprocess.CompletedProcess:
    """Execute une commande sans shell, avec timeout.
    Retourne l'objet CompletedProcess, l'exception est capturee par l'appelant."""
    # L'ENCODAGE EST DIT, JAMAIS DEDUIT DE LA CONSOLE.
    #
    # CE QUI ETAIT FAUX, diagnostique le 2026-08-31 en instrumentant cette
    # fonction : `text=True` sans `encoding` fait decoder avec la page de code
    # de la console -- cp1252 ici. Le JSON d'eslint porte un octet 0x81, venant
    # des commentaires accentues UTF-8 de server.js. Le decodage leve
    # UnicodeDecodeError DANS LE THREAD LECTEUR de subprocess, exception que
    # subprocess AVALE : communicate() rend alors des chaines VIDES.
    #
    # Trace relevee : returncode 1, stdout 0 octet, stderr 0 octet.
    # L'outil rapportait « eslint : JOUE (0 violations) » la ou eslint en
    # trouvait NEUF, dont deux require-atomic-updates dans server.js.
    #
    # Les trois linters rendent de l'UTF-8. La page de code de la console n'a
    # rien a voir la-dedans, et elle varie d'une machine a l'autre : la deduire
    # revenait a faire dependre le verdict de la locale de l'operateur.
    return subprocess.run(
        cmd,
        cwd=str(cwd),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=TIMEOUT,
    )


def _install_ruff() -> bool:
    """Installe ruff via uv dans un venv dédié.
    Retourne True si l'installation a reussi, False sinon."""
    try:
        _run_cmd(["uv", "venv", str(RUFF_VENV)], cwd=BASE_DIR)
        _run_cmd(["uv", "pip", "install", "ruff"], cwd=RUFF_VENV)
        return True
    except Exception as e:
        print(f"Installation ruff echouee : {e}", file=sys.stderr)
        return False


def _install_eslint() -> bool:
    """Installe eslint via npm dans OUTIL_DIR.
    Retourne True si l'installation a reussi, False sinon."""
    try:
        # NPM PORTE UNE EXTENSION SOUS WINDOWS, exactement comme ruff.
        # Mesure : « Installation eslint echouee : [WinError 2] Le fichier
        # specifie est introuvable » alors que npm ETAIT dans le PATH --
        # c'est npm.cmd qui s'y trouve, jamais npm.
        npm = "npm.cmd" if os.name == "nt" else "npm"
        _run_cmd([npm, "install", "eslint"], cwd=OUTIL_DIR)
        # PAS DE STYLE, QUE DU COMPORTEMENT FAUX OU MORT.
        #
        # Le depot n'a pas de convention JavaScript ecrite, et imposer un
        # style par un linter serait inventer une regle que personne n'a
        # decidee. On ne garde que ce qui designe un defaut : variable non
        # definie, code inatteignable, condition constante, promesse mal
        # geree, ecriture concurrente sur une variable partagee.
        ESLINT_CONFIG.write_text(ESLINT_CONFIG_TEXTE, encoding="utf-8")
        return True
    except Exception as e:
        print(f"Installation eslint echouee : {e}", file=sys.stderr)
        return False


def _install_psscriptanalyzer() -> bool:
    """Installe le module PowerShell PSScriptAnalyzer.
    Retourne True si l'installation a reussi, False sinon."""
    try:
        _run_cmd(
            [
                "pwsh",
                "-NoProfile",
                "-Command",
                "Install-Module",
                "PSScriptAnalyzer",
                "-Scope",
                "CurrentUser",
                "-Force",
                "-ErrorAction",
                "Stop",
            ],
            cwd=RACINE,
        )
        return True
    except Exception as e:
        print(f"Installation PSScriptAnalyzer echouee : {e}", file=sys.stderr)
        return False


def _run_ruff() -> Dict[str, Any]:
    """Execute ruff et retourne un dictionnaire de resultat."""
    if not RUFF_BIN.is_file():
        return {
            "outil": "ruff",
            "etat": "absent",
            "violations": [],
            "detail": "binary not found",
        }
    try:
        result = _run_cmd(
            [
                str(RUFF_BIN),
                "check",
                "scripts",
                "tools",
                "--select",
                "E9,F,B,C4,SIM,RET",
                "--output-format",
                "json",
            ],
            cwd=RACINE,
        )
    except subprocess.TimeoutExpired:
        return {
            "outil": "ruff",
            "etat": "casse",
            "violations": [],
            "detail": "timeout",
        }
    except Exception as e:
        return {
            "outil": "ruff",
            "etat": "casse",
            "violations": [],
            "detail": str(e),
        }

    if result.returncode not in (0, 1):
        return {
            "outil": "ruff",
            "etat": "casse",
            "violations": [],
            "detail": f"unexpected exit {result.returncode}",
        }

    try:
        data = json.loads(result.stdout or "[]")
    except Exception:
        return {
            "outil": "ruff",
            "etat": "casse",
            "violations": [],
            "detail": "invalid json",
        }

    # RUFF REND UNE LISTE PLATE, PAS UNE LISTE DE FICHIERS.
    #
    # Le parseur traitait chaque element comme une ENTREE DE FICHIER et
    # cherchait dedans une cle « violations » imbriquee. Elle n'existe pas :
    # `ruff check --output-format json` rend directement la liste des
    # violations, chacune portant filename, code, location et message.
    # La boucle interne ne tournait donc jamais.
    #
    # Mesure du 2026-08-31 : 91 violations reelles rendues par ruff, lues
    # comme ZERO, et rapportees avec l'etat « joue » -- celui-la meme qui
    # certifie qu'un zero a ete mesure. Troisieme faux negatif superpose dans
    # ce seul outil, apres le repertoire de travail et le nom du binaire :
    # chacun suffisait a tout eteindre, et aucun ne se voyait a la lecture.
    #
    # Le format est verifie plutot que suppose : si un element ne porte pas
    # « filename », l'etat devient « casse ». Un changement de schema chez
    # ruff doit se voir, non se traduire par un silence.
    violations = []
    for item in data:
        if not isinstance(item, dict) or "filename" not in item:
            return {
                "outil": "ruff",
                "etat": "casse",
                "violations": [],
                "detail": "schema json inattendu",
            }
        violations.append(
            {
                "fichier": item.get("filename"),
                "ligne": (item.get("location") or {}).get("row"),
                "regle": item.get("code") or item.get("name"),
                "message": item.get("message"),
            }
        )
    return {
        "outil": "ruff",
        "etat": "joue",
        "violations": violations,
        "detail": "",
    }


def _run_eslint() -> Dict[str, Any]:
    """Execute eslint et retourne un dictionnaire de resultat."""
    if not ESLINT_BIN.is_file():
        return {
            "outil": "eslint",
            "etat": "absent",
            "violations": [],
            "detail": "binary not found",
        }
    try:
        result = _run_cmd(
            [
                str(ESLINT_BIN),
                "tools",
                "--config",
                str(ESLINT_CONFIG),
                "-f",
                "json",
                "--ignore-pattern",
                "**/node_modules/**",
                "--ignore-pattern",
                ".nexus/**",
            ],
            cwd=RACINE,
        )
    except subprocess.TimeoutExpired:
        return {
            "outil": "eslint",
            "etat": "casse",
            "violations": [],
            "detail": "timeout",
        }
    except Exception as e:
        return {
            "outil": "eslint",
            "etat": "casse",
            "violations": [],
            "detail": str(e),
        }

    if result.returncode not in (0, 1):
        return {
            "outil": "eslint",
            "etat": "casse",
            "violations": [],
            "detail": f"unexpected exit {result.returncode}",
        }

    # UN CODE 1 AVEC UN FLUX VIDE EST UNE CONTRADICTION, PAS UN DEPOT PROPRE.
    #
    # eslint sort 1 QUAND IL A TROUVE des problemes, et 0 quand tout est
    # propre. Un code 1 accompagne d'une sortie vide dit donc que le flux n'a
    # pas ete lu, ou qu'il a ete tronque -- jamais que le code est sain.
    #
    # Cette garde est le vrai livrable : elle aurait rougi MEME SANS la
    # correction d'encodage ci-dessus, alors que cette correction, seule,
    # laisserait le meme piege revenir au premier octet illisible d'une autre
    # source. « Une mesure impossible n'est pas une mesure a zero. »
    if result.returncode == 1 and not (result.stdout or "").strip():
        return {
            "outil": "eslint",
            "etat": "casse",
            "violations": [],
            "detail": "contradiction : code 1 (des problemes) mais flux vide",
        }

    try:
        data = json.loads(result.stdout or "[]")
    except Exception:
        return {
            "outil": "eslint",
            "etat": "casse",
            "violations": [],
            "detail": "invalid json",
        }

    violations = []
    for file_entry in data:
        path = file_entry.get("filePath")
        for msg in file_entry.get("messages", []):
            violations.append(
                {
                    "fichier": path,
                    "ligne": msg.get("line"),
                    "regle": msg.get("ruleId"),
                    "message": msg.get("message"),
                }
            )
    if result.returncode == 1 and not violations:
        # Le document etait lisible mais ne portait aucun message, alors
        # qu'eslint dit en avoir trouve. Une troncature au milieu du JSON
        # produirait exactement cela.
        return {
            "outil": "eslint",
            "etat": "casse",
            "violations": [],
            "detail": "contradiction : code 1 mais aucune violation analysee",
        }

    return {
        "outil": "eslint",
        "etat": "joue",
        "violations": violations,
        "detail": "",
    }


def _run_psscriptanalyzer() -> Dict[str, Any]:
    """Execute PSScriptAnalyzer et retourne un dictionnaire de resultat."""
    try:
        # LE CHAMP EST SELECTIONNE, ET L'AVERTISSEMENT DISPARAIT AVEC LUI.
        #
        # CE QUI ETAIT FAUX, mesure en jouant la commande a la main :
        # `Invoke-ScriptAnalyzer | ConvertTo-Json` serialise des objets
        # imbriques bien au-dela de la profondeur 2 par defaut, et PowerShell
        # emet alors « WARNING: Resulting JSON is truncated... ». Cet
        # avertissement precede le JSON dans le flux capture : le document
        # devient illisible et l'outil se rapportait « casse - invalid json »
        # alors que PSScriptAnalyzer fonctionnait parfaitement -- 253
        # resultats verifies sur scripts/ au meme instant.
        #
        # Diagnostiquer une panne la ou il n'y en a pas envoie chercher au
        # mauvais endroit ; c'est la raison d'etre de la distinction entre
        # « absent » et « casse », et elle ne vaut que si « casse » dit vrai.
        #
        # Select-Object aplatit aux quatre champs que le parseur lit
        # reellement. Plus d'imbrication, donc plus d'avertissement, et un
        # document plus petit d'un ordre de grandeur.
        ps_cmd = (
            "$ErrorActionPreference='Stop'; "
            "Import-Module PSScriptAnalyzer; "
            "Invoke-ScriptAnalyzer -Path . -Recurse "
            f"-IncludeRule {','.join(PS_ANALYZER_RULES)} "
            "| Select-Object RuleName, Severity, ScriptPath, Line, Message "
            "| ConvertTo-Json -Depth 3 -Compress -AsArray"
        )
        result = _run_cmd(
            ["pwsh", "-NoProfile", "-Command", ps_cmd],
            cwd=RACINE,
        )
    except subprocess.TimeoutExpired:
        return {
            "outil": "psscriptanalyzer",
            "etat": "casse",
            "violations": [],
            "detail": "timeout",
        }
    except Exception as e:
        return {
            "outil": "psscriptanalyzer",
            "etat": "casse",
            "violations": [],
            "detail": str(e),
        }

    if result.returncode != 0:
        return {
            "outil": "psscriptanalyzer",
            "etat": "casse",
            "violations": [],
            "detail": f"non-zero exit {result.returncode}",
        }

    if not result.stdout.strip():
        return {
            "outil": "psscriptanalyzer",
            "etat": "joue",
            "violations": [],
            "detail": "",
        }

    try:
        data = json.loads(result.stdout)
    except Exception:
        return {
            "outil": "psscriptanalyzer",
            "etat": "casse",
            "violations": [],
            "detail": "invalid json",
        }

    if isinstance(data, dict):
        data = [data]

    violations = []
    for entry in data:
        violations.append(
            {
                "fichier": entry.get("ScriptPath"),
                "ligne": entry.get("Line"),
                "regle": entry.get("RuleName"),
                "message": entry.get("Message"),
            }
        )
    return {
        "outil": "psscriptanalyzer",
        "etat": "joue",
        "violations": violations,
        "detail": "",
    }


def _collect_tool_results() -> List[Dict[str, Any]]:
    """Lance les trois analyses et retourne la liste des resultats par outil."""
    return [_run_ruff(), _run_eslint(), _run_psscriptanalyzer()]


def _aggregate_violations(tool_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Extrait toutes les violations des outils qui ont joue."""
    agg: List[Dict[str, Any]] = []
    for tr in tool_results:
        if tr["etat"] == "joue":
            agg.extend(tr["violations"])
    return agg


def _print_tool_status(tool_results: List[Dict[str, Any]]) -> None:
    """Affiche l'etat de chaque outil."""
    for tr in tool_results:
        outil = tr["outil"]
        etat = tr["etat"]
        if etat == "joue":
            nb = len(tr["violations"])
            print(f"{outil} : JOUE ({nb} violations)")
        elif etat == "absent":
            print(f"{outil} : NON JOUE (absent)")
        else:  # casse
            print(f"{outil} : NON JOUE (casse) - {tr['detail']}")


OUTIL_DU_LANGAGE = {
    "Python": "ruff",
    "JavaScript": "eslint",
    "PowerShell": "psscriptanalyzer",
}


def _print_summary(findings: List[Dict[str, Any]],
                   tool_results: List[Dict[str, Any]]) -> None:
    """
    Un ZERO ne vaut que si quelque chose a MESURE.

    CE QUI ETAIT FAUX, et mesure en executant le script. La ligne par outil
    disait deja vrai -- « ruff : NON JOUE (absent) » -- mais le recapitulatif
    par langage, juste en dessous, affichait « Python : 0 violations ». Le
    faux negatif que la reecriture devait supprimer etait simplement remonte
    d'un cran, et c'est la ligne du bas qu'un lecteur retient.

    SEUL l'etat « joue » autorise un chiffre. « absent » ET « casse » sont
    tous deux des non-mesures : la premiere correction ne traitait que
    « absent », si bien qu'un outil CASSE retombait dans la branche du
    chiffre et reaffichait le meme zero menteur.
    """
    langs = {"Python": [], "JavaScript": [], "PowerShell": []}
    for f in findings:
        path = f["fichier"] or ""
        if path.endswith((".py",)):
            langs["Python"].append(f["regle"])
        elif path.endswith((".js", ".jsx", ".ts", ".tsx")):
            langs["JavaScript"].append(f["regle"])
        elif path.endswith((".ps1", ".psm1", ".psd1")):
            langs["PowerShell"].append(f["regle"])
    etats = {tr["outil"]: tr for tr in tool_results}
    for lang, rules in langs.items():
        outil = OUTIL_DU_LANGAGE[lang]
        tr = etats.get(outil)
        if tr is None or tr["etat"] != "joue":
            motif = "outil jamais lance" if tr is None else tr["etat"]
            detail = (tr or {}).get("detail") or ""
            print(f"{lang} : NON MESURE ({outil} : {motif}"
                  + (f" - {detail}" if detail else "") + ")")
            continue
        unique_rules = sorted({r for r in rules if r})
        print(f"{lang} : {len(rules)} violations, regles : {', '.join(unique_rules)}")


def _determine_exit_code(tool_results: List[Dict[str, Any]], findings: List[Dict[str, Any]]) -> int:
    """Retourne le code de sortie selon les specifications."""
    has_joue = any(tr["etat"] == "joue" for tr in tool_results)
    has_casse = any(tr["etat"] == "casse" for tr in tool_results)
    if not has_joue or has_casse:
        return 2
    return 0 if not findings else 1


# ----------------------------------------------------------------------
# Point d'entree
# ----------------------------------------------------------------------


REFERENCE_OUTILLAGE = "rituels/outillage_reference.json"


def _compter_regles(tool_result: Dict[str, Any]) -> Dict[str, int]:
    """Nombre de violations PAR REGLE pour un outil, jamais un total.

    Un total masque un echange : une violation corrigee pendant qu'une autre
    apparait laisse la somme identique, et l'etat se degrade en silence.
    """
    comptes: Dict[str, int] = {}
    for v in tool_result.get("violations", []):
        regle = v.get("regle") or "?"
        comptes[regle] = comptes.get(regle, 0) + 1
    return comptes


def _lire_reference():
    """La reference sur disque, ou None si elle n'existe pas encore."""
    chemin = RACINE / REFERENCE_OUTILLAGE
    if not chemin.is_file():
        return None
    try:
        with open(chemin, "r", encoding="utf-8") as f:
            charge = json.load(f)
    except Exception:
        return None
    return charge if isinstance(charge, dict) else None


def _ecrire_reference(comptes_joues: Dict[str, Dict[str, int]],
                      ancienne=None) -> None:
    """Ecrit la reference SANS effacer ce qui n'a pas ete mesure.

    CE QUI SERAIT FAUX SANS CETTE FUSION. Un premier jet ne conservait que
    les outils joues. Desinstaller eslint puis rebaseliner aurait donc
    SUPPRIME sa dette de la reference, et le cliquet n'aurait plus jamais
    rien eu a comparer -- une dette effacee par la disparition de son
    mesureur, sans qu'une seule ligne le dise.
    """
    fusion: Dict[str, Dict[str, int]] = dict(ancienne or {})
    fusion.update(comptes_joues)
    chemin = RACINE / REFERENCE_OUTILLAGE
    chemin.parent.mkdir(parents=True, exist_ok=True)
    with open(chemin, "w", encoding="utf-8") as f:
        json.dump(fusion, f, ensure_ascii=True, indent=2, sort_keys=True)


def _jouer_cliquet(tool_results: List[Dict[str, Any]],
                   rebaseline: bool = False) -> int:
    """Le passe n'est pas exige repare ; l'aggravation est refusee.

    POURQUOI UN CLIQUET ET NON UNE PORTE. Le depot porte 108 violations. Une
    porte qui refuse au premier defaut bloquerait tout des le premier appel,
    et serait desarmee dans l'heure -- c'est le sort de toute regle qui coute
    plus qu'elle ne protege le jour ou on la pose.

    UN OUTIL QUI N'A PAS JOUE N'EST NI COMPARE NI MIS A JOUR. Sans cela, un
    outil absent ne contribue aucune regle, toutes les siennes passent pour
    DISPARUES, et un linter desinstalle se lit comme un depot assaini. C'est
    le faux negatif que ce fichier entier combat, et il se serait reintroduit
    par la porte du cliquet.
    """
    comptes_joues: Dict[str, Dict[str, int]] = {
        tr["outil"]: _compter_regles(tr)
        for tr in tool_results if tr.get("etat") == "joue"
    }

    reference = _lire_reference()
    if reference is None:
        _ecrire_reference(comptes_joues)
        print("Reference absente : creee a partir des outils JOUES.")
        print("Aucune comparaison possible ce coup-ci -- c'est le point de depart,")
        print("pas un verdict. Le prochain appel comparera.")
        return 0

    if rebaseline:
        _ecrire_reference(comptes_joues, ancienne=reference)
        print("Reference REBASELINEE, degradation assumee explicitement.")
        for tr in tool_results:
            if tr.get("etat") != "joue":
                print("  %s : non joue (%s), sa reference est CONSERVEE"
                      % (tr["outil"], tr.get("etat")))
        return 0

    regressions = []
    ameliorations = []
    premieres: Dict[str, Dict[str, int]] = {}
    for tr in tool_results:
        outil = tr.get("outil")
        if tr.get("etat") != "joue":
            print("  %s : NON COMPARE (%s) -- reference conservee"
                  % (outil, tr.get("etat")))
            continue
        actuel = comptes_joues.get(outil, {})
        # UN OUTIL JAMAIS MESURE NE DEGRADE RIEN.
        #
        # Mesure du 2026-08-31 : eslint, absent depuis toujours faute de npm,
        # a ete provisionne et a rendu 11 violations. Le cliquet a annonce
        # « 2 REGRESSION(S) ». C'est faux : la dette etait deja la, personne
        # ne la voyait. Rien ne s'est aggrave -- on a ouvert les yeux.
        #
        # Et la confusion coute plus que le mot : elle force un --rebaseline,
        # lequel devient alors indiscernable d'une degradation reellement
        # assumee. Le geste qui sert a dire « oui, j'accepte que ce soit
        # pire » aurait servi a dire « je viens d'allumer la lumiere ».
        #
        # La distinction est ETROITE : elle ne joue que si l'outil est
        # ABSENT DE LA REFERENCE, jamais si une regle nouvelle apparait dans
        # un outil deja connu. Effacer une entree pour blanchir une dette se
        # verrait dans le diff -- la reference est versionnee.
        if outil not in reference:
            total = sum(actuel.values())
            print("  %s : PREMIERE MESURE, %d violation(s) inscrite(s)"
                  % (outil, total))
            print("     dette preexistante, non une aggravation ;"
                  " elle sera comparee des le prochain appel")
            premieres[outil] = actuel
            continue
        ancien = reference.get(outil, {})
        for regle, n in sorted(actuel.items()):
            avant = ancien.get(regle, 0)
            if n > avant:
                regressions.append("%s : %s %d -> %d%s"
                                   % (outil, regle, avant, n,
                                      "  (regle neuve)" if avant == 0 else ""))
        for regle, avant in sorted(ancien.items()):
            n = actuel.get(regle, 0)
            if n < avant:
                ameliorations.append("%s : %s %d -> %d" % (outil, regle, avant, n))

    # Une premiere mesure s'INSCRIT sans etre jugee. Ne pas l'inscrire
    # reposerait la meme question a chaque appel, sans jamais rien comparer.
    if premieres:
        _ecrire_reference(premieres, ancienne=reference)
    if regressions:
        print("Outillage : %d REGRESSION(S)." % len(regressions))
        for ligne in regressions:
            print("  " + ligne)
    else:
        print("Outillage : aucune regression.")
    if ameliorations:
        print("  %d amelioration(s) :" % len(ameliorations))
        for ligne in ameliorations:
            print("    " + ligne)
    if regressions:
        print("\nLe passe n'a pas a etre repare pour passer : seule")
        print("l'AGGRAVATION est refusee. Si elle est voulue, l'assumer")
        print("par --cliquet --rebaseline.")
    return 1 if regressions else 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Outillage Nexus")
    parser.add_argument(
        "--installer",
        action="store_true",
        help="Provisionner ruff, eslint et PSScriptAnalyzer",
    )
    parser.add_argument(
        "--cliquet",
        action="store_true",
        help="Refuser toute AGGRAVATION par rapport a "
             + REFERENCE_OUTILLAGE + " (le passe n'a pas a etre repare)",
    )
    parser.add_argument(
        "--rebaseline",
        action="store_true",
        help="Avec --cliquet : reecrire la reference et assumer la degradation",
    )
    parser.add_argument(
        "--json",
        metavar="FICHIER",
        help="Ecrire les resultats au format JSON dans le fichier indique",
    )
    args = parser.parse_args()

    OUTIL_DIR.mkdir(parents=True, exist_ok=True)

    if args.installer:
        ruff_ok = _install_ruff()
        eslint_ok = _install_eslint()
        ps_ok = _install_psscriptanalyzer()
        print("Ruff installe avec succes." if ruff_ok else "Ruff NON installe.")
        print("Eslint installe avec succes." if eslint_ok else "Eslint NON installe.")
        print("PSScriptAnalyzer installe avec succes." if ps_ok else "PSScriptAnalyzer NON installe.")
        # UN PROVISIONNEMENT PARTIEL SORTAIT EN 0. Mesure : eslint a echoue
        # (npm hors du PATH) et la commande a rendu 0, donc « tout va bien ».
        # Un appelant automatique aurait enchaine sur une detection amputee
        # d'un tiers sans rien voir. 0 = les trois, 1 = certains, 2 = aucun.
        poses = sum([bool(ruff_ok), bool(eslint_ok), bool(ps_ok)])
        sys.exit(0 if poses == 3 else (2 if poses == 0 else 1))

    tool_results = _collect_tool_results()
    findings = _aggregate_violations(tool_results)

    if args.cliquet:
        _print_tool_status(tool_results)
        sys.exit(_jouer_cliquet(tool_results, args.rebaseline))

    if args.json:
        try:
            # LE CHEMIN MACHINE PORTE LES ETATS, PAS SEULEMENT LES
            # VIOLATIONS. `--json` n'ecrivait que la liste des violations :
            # un portail qui la consomme lit « tableau vide » et conclut
            # « propre » alors qu'aucun outil n'a tourne. C'est le meme faux
            # negatif que sur le recapitulatif, mais en pire -- personne ne
            # relit un JSON, on l'automatise.
            charge = {
                "outils": [{"outil": t["outil"], "etat": t["etat"],
                            "detail": t.get("detail", ""),
                            "violations": len(t["violations"])}
                           for t in tool_results],
                "mesure": any(t["etat"] == "joue" for t in tool_results),
                "violations": findings,
            }
            with open(args.json, "w", encoding="utf-8") as f:
                json.dump(charge, f, ensure_ascii=True, indent=2)
            print(f"Resultats ecrits dans {args.json}")
        except Exception as e:
            print(f"Erreur ecriture JSON : {e}", file=sys.stderr)
            sys.exit(2)
    else:
        _print_tool_status(tool_results)
        _print_summary(findings, tool_results)

    exit_code = _determine_exit_code(tool_results, findings)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
