#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""epreuve_stats_jsonl.py – test de scripts/nexus_stats_jsonl.py"""
import json
import os
import subprocess
import sys
import tempfile

TOOL = os.path.join(os.path.dirname(__file__), "scripts", "nexus_stats_jsonl.py")


def run_tool(args, input_path=None):
    """Exécute l'outil et renvoie (code, stdout, stderr)."""
    cmd = [sys.executable, TOOL] + args
    if input_path is not None:
        cmd += [input_path]
    res = subprocess.run(cmd, capture_output=True, text=True)
    return res.returncode, res.stdout, res.stderr


def test_known_proportions():
    """Deux groupes, proportions connues."""
    data = [
        {"text": "abc", "group": "A", "flag": True},
        {"text": "abc", "group": "A", "flag": False},
        {"text": "xyz", "group": "A", "flag": True},
        {"text": "def", "group": "B", "flag": False},
        {"text": "def", "group": "B", "flag": True},
    ]
    with tempfile.NamedTemporaryFile("w", delete=False, encoding="utf-8") as f:
        for obj in data:
            f.write(json.dumps(obj) + "\n")
        path = f.name
    try:
        code, out, _ = run_tool([
            "--champ-texte", "text",
            "--champ-groupe", "group",
            "--champ-booleen", "flag",
            "--motif", "M=abc",
            "--json",
            path,
        ])
        assert code == 0, f"code retour inattendu: {code}"
        payload = json.loads(out)
        groupe = payload["par_groupe"]
        assert groupe["A"]["total"] == 3
        assert groupe["A"]["motifs"]["M"]["n"] == 2
        assert abs(groupe["A"]["motifs"]["M"]["pct"] - 66.7) < 0.05
        assert groupe["B"]["total"] == 2
        assert groupe["B"]["motifs"]["M"]["n"] == 0
        assert groupe["B"]["motifs"]["M"]["pct"] == 0.0
    finally:
        os.unlink(path)


def test_invalid_line():
    """Une ligne JSON invalide doit être comptée et ignorée."""
    with tempfile.NamedTemporaryFile("w", delete=False, encoding="utf-8") as f:
        f.write('{"text":"foo","group":"X","flag":true}\n')
        f.write('{invalid json}\n')
        f.write('{"text":"bar","group":"Y","flag":false}\n')
        path = f.name
    try:
        code, out, err = run_tool([
            "--champ-texte", "text",
            "--champ-groupe", "group",
            "--champ-booleen", "flag",
            "--motif", "M=foo",
            path,
        ])
        assert code == 0
        assert "Lignes : 2 (1 invalides ignorees)" in out
    finally:
        os.unlink(path)


def test_missing_field():
    """Champ absent traité comme vide sans planter."""
    data = [
        {"text": "hello", "group": "G1"},  # manque flag
        {"group": "G2", "flag": True},    # manque text
    ]
    with tempfile.NamedTemporaryFile("w", delete=False, encoding="utf-8") as f:
        for obj in data:
            f.write(json.dumps(obj) + "\n")
        path = f.name
    try:
        code, out, _ = run_tool([
            "--champ-texte", "text",
            "--champ-groupe", "group",
            "--champ-booleen", "flag",
            "--motif", "M=hello",
            "--json",
            path,
        ])
        assert code == 0
        payload = json.loads(out)
        groupe = payload["par_groupe"]
        # G1: text présent, flag absent => VIDE pour booléen mais on ne vérifie pas ici
        # G2: text absent => traité comme vide => pas de hit
        assert groupe["G1"]["total"] == 1
        assert groupe["G2"]["total"] == 1
        # aucun hit attendu
        assert groupe["G1"]["motifs"]["M"]["n"] == 0
        assert groupe["G2"]["motifs"]["M"]["n"] == 0
    finally:
        os.unlink(path)


def test_empty_file():
    """Fichier vide => résultat vide, pas de plantage."""
    with tempfile.NamedTemporaryFile("w", delete=False, encoding="utf-8") as f:
        path = f.name
    try:
        code, out, err = run_tool([
            "--champ-texte", "text",
            "--champ-groupe", "group",
            "--champ-booleen", "flag",
            "--motif", "M=test",
            path,
        ])
        assert code == 0
        assert "Lignes : 0 (0 invalides ignorees)" in out
        assert "(aucune donnee)" in out
    finally:
        os.unlink(path)


def test_missing_args():
    """Appel sans arguments requis => usage et code non nul."""
    code, out, err = run_tool([])
    assert code != 0
    assert "usage:" in err.lower() or "usage:" in out.lower()


def main():
    failures = 0
    for name, func in [
        ("known_proportions", test_known_proportions),
        ("invalid_line", test_invalid_line),
        ("missing_field", test_missing_field),
        ("empty_file", test_empty_file),
        ("missing_args", test_missing_args),
    ]:
        try:
            func()
            print(f"[OK] {name}")
        except AssertionError as e:
            print(f"[FAIL] {name}: {e}")
            failures += 1
        except Exception as e:
            print(f"[ERROR] {name}: {e}")
            failures += 1
    if failures:
        print(f"\n{failures} test(s) échoué(s)")
        sys.exit(1)
    else:
        print("\nTous les tests passent")
        sys.exit(0)


if __name__ == "__main__":
    main()
