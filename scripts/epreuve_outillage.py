#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

TIMEOUT = 10
OUTIL = Path("scripts") / "nexus_outillage.py"
USAGE = "usage: nexus_outillage.py [-h] [--installer] [--cliquet] [--rebaseline] [--json FICHIER]"

def lancer(cmd, cwd=None):
    try:
        proc = subprocess.run(
            cmd,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            timeout=TIMEOUT
        )
        return proc.returncode, proc.stdout, proc.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "timeout"

def verifier_existence():
    if not OUTIL.is_file():
        print(f"[ERREUR] Fichier introuvable : {OUTIL}")
        sys.exit(2)

def cas_nominal():
    with tempfile.TemporaryDirectory() as tmpdir:
        cmd = [sys.executable, str(OUTIL)]
        code, out, err = lancer(cmd, cwd=tmpdir)
        if code == 0:
            if "ruff : JOUE" in out and "eslint : JOUE" in out and "psscriptanalyzer : JOUE" in out:
                print("[OK] Cas nominal - outil joue et rend les trois etats")
            else:
                print("[ECHEC] Cas nominal - code 0 mais etats manquants")
                return False
        else:
            print(f"[ECHEC] Cas nominal - code {code} (attendu 0)")
            return False
    return True

def cas_absence_args():
    with tempfile.TemporaryDirectory() as tmpdir:
        cmd = [sys.executable, str(OUTIL)]
        code, out, err = lancer(cmd, cwd=tmpdir)
        if code != 0 and USAGE in err:
            print("[OK] Cas sans arguments - usage affiche et code non nul")
        else:
            print(f"[ECHEC] Cas sans arguments - code {code} ou usage absent")
            return False
    return True

def cas_chemin_inexistant():
    with tempfile.TemporaryDirectory() as tmpdir:
        cmd = [sys.executable, str(OUTIL), "--json", "inexistant/chemin.json"]
        code, out, err = lancer(cmd, cwd=tmpdir)
        if code == 2 and "Erreur ecriture JSON" in err:
            print("[OK] Cas chemin JSON inexistant - erreur ecrite et code 2")
        else:
            print(f"[ECHEC] Cas chemin JSON inexistant - code {code} ou message absent")
            return False
    return True

def cas_cliquet_hausse():
    with tempfile.TemporaryDirectory() as tmpdir:
        ref = Path(tmpdir) / "rituels" / "outillage_reference.json"
        ref.parent.mkdir(parents=True, exist_ok=True)
        ref.write_text('{"ruff": {"E9": 1}}', encoding="utf-8")
        cmd = [sys.executable, str(OUTIL), "--cliquet"]
        code, out, err = lancer(cmd, cwd=tmpdir)
        if code == 1 and "1 REGRESSION(S)" in out:
            print("[OK] Cas cliquet hausse - regression signalee et code 1")
        else:
            print(f"[ECHEC] Cas cliquet hausse - code {code} ou regression absente")
            return False
    return True

def cas_cliquet_baisse():
    with tempfile.TemporaryDirectory() as tmpdir:
        ref = Path(tmpdir) / "rituels" / "outillage_reference.json"
        ref.parent.mkdir(parents=True, exist_ok=True)
        ref.write_text('{"ruff": {"E9": 3}}', encoding="utf-8")
        cmd = [sys.executable, str(OUTIL), "--cliquet"]
        code, out, err = lancer(cmd, cwd=tmpdir)
        if code == 0 and "aucune regression" in out:
            print("[OK] Cas cliquet baisse - aucune regression signalee")
        else:
            print(f"[ECHEC] Cas cliquet baisse - code {code} ou regression presente")
            return False
    return True

def cas_cliquet_regle_neuve():
    with tempfile.TemporaryDirectory() as tmpdir:
        ref = Path(tmpdir) / "rituels" / "outillage_reference.json"
        ref.parent.mkdir(parents=True, exist_ok=True)
        ref.write_text('{"ruff": {"E9": 1}}', encoding="utf-8")
        cmd = [sys.executable, str(OUTIL), "--cliquet"]
        code, out, err = lancer(cmd, cwd=tmpdir)
        if code == 0 and "PREMIERE MESURE" in out:
            print("[OK] Cas cliquet regle neuve - premiere mesure inscrite sans regression")
        else:
            print(f"[ECHEC] Cas cliquet regle neuve - code {code} ou regression presente")
            return False
    return True

def main():
    verifier_existence()
    cas = [
        ("Nominal", cas_nominal),
        ("Sans arguments", cas_absence_args),
        ("Chemin JSON inexistant", cas_chemin_inexistant),
        ("Cliquet hausse", cas_cliquet_hausse),
        ("Cliquet baisse", cas_cliquet_baisse),
        ("Cliquet regle neuve", cas_cliquet_regle_neuve),
    ]
    echecs = 0
    for nom, test in cas:
        print(f"[TEST] {nom}...")
        if not test():
            echecs += 1
    sys.exit(1 if echecs else 0)

if __name__ == "__main__":
    main()
