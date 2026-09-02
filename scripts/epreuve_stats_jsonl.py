import os
import sys
import subprocess
import tempfile
import json
from pathlib import Path

TIMEOUT = 10
CODE_FICHIER_INEXISTANT = 2
MSG_FICHIER_INEXISTANT = "Fichier illisible"
MSG_USAGE = "usage: nexus_stats_jsonl.py"
MSG_REGEX_INVALID = "Regex invalide"
MSG_MOTIF_MAL_FORME = "Motif mal forme"
MSG_JSONL_INVALID = "lignes invalides ignorees"

def run_cmd(cmd, cwd=None):
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=TIMEOUT,
            encoding="utf-8",
            errors="replace"
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return None, "", "ECHEC : delai depasse (outil bloque ?)"

def test_fichier_inexistant():
    with tempfile.TemporaryDirectory() as tmpdir:
        cmd = [sys.executable, "nexus_stats_jsonl.py", "fichier_inexistant.jsonl",
               "--champ-texte=texte", "--champ-groupe=groupe",
               "--champ-booleen=booleen", "--motif=test=.*"]
        code, stdout, stderr = run_cmd(cmd, cwd=tmpdir)
        if code != CODE_FICHIER_INEXISTANT:
            return False, f"Code {code} != {CODE_FICHIER_INEXISTANT}"
        if MSG_FICHIER_INEXISTANT not in stderr:
            return False, f"Message absent : {MSG_FICHIER_INEXISTANT}"
        return True, ""

def test_usage_sans_arguments():
    with tempfile.TemporaryDirectory() as tmpdir:
        cmd = [sys.executable, "nexus_stats_jsonl.py"]
        code, stdout, stderr = run_cmd(cmd, cwd=tmpdir)
        if code == 0:
            return False, "Code 0 avec arguments manquants"
        if MSG_USAGE not in stderr:
            return False, f"Usage absent : {MSG_USAGE}"
        return True, ""

def test_motif_mal_forme():
    with tempfile.TemporaryDirectory() as tmpdir:
        cmd = [sys.executable, "nexus_stats_jsonl.py", "fichier.jsonl",
               "--champ-texte=texte", "--champ-groupe=groupe",
               "--champ-booleen=booleen", "--motif=test_sans_egal"]
        code, stdout, stderr = run_cmd(cmd, cwd=tmpdir)
        if code != 2:
            return False, f"Code {code} != 2"
        if MSG_MOTIF_MAL_FORME not in stderr:
            return False, f"Message absent : {MSG_MOTIF_MAL_FORME}"
        return True, ""

def test_regex_invalide():
    with tempfile.TemporaryDirectory() as tmpdir:
        cmd = [sys.executable, "nexus_stats_jsonl.py", "fichier.jsonl",
               "--champ-texte=texte", "--champ-groupe=groupe",
               "--champ-booleen=booleen", "--motif=test=("]
        code, stdout, stderr = run_cmd(cmd, cwd=tmpdir)
        if code != 2:
            return False, f"Code {code} != 2"
        if MSG_REGEX_INVALID not in stderr:
            return False, f"Message absent : {MSG_REGEX_INVALID}"
        return True, ""

def test_jsonl_invalide():
    with tempfile.TemporaryDirectory() as tmpdir:
        fichier = Path(tmpdir) / "test.jsonl"
        fichier.write_text('{"texte": "test", "groupe": "A", "booleen": true}\n{invalid json\n')
        cmd = [sys.executable, "nexus_stats_jsonl.py", str(fichier),
               "--champ-texte=texte", "--champ-groupe=groupe",
               "--champ-booleen=booleen", "--motif=test=test"]
        code, stdout, stderr = run_cmd(cmd, cwd=tmpdir)
        if code != 0:
            return False, f"Code {code} != 0"
        if MSG_JSONL_INVALID not in stdout:
            return False, f"Message absent : {MSG_JSONL_INVALID}"
        return True, ""

def test_sortie_json():
    with tempfile.TemporaryDirectory() as tmpdir:
        fichier = Path(tmpdir) / "test.jsonl"
        fichier.write_text('{"texte": "test", "groupe": "A", "booleen": true}\n')
        cmd = [sys.executable, "nexus_stats_jsonl.py", str(fichier),
               "--champ-texte=texte", "--champ-groupe=groupe",
               "--champ-booleen=booleen", "--motif=test=test", "--json"]
        code, stdout, stderr = run_cmd(cmd, cwd=tmpdir)
        if code != 0:
            return False, f"Code {code} != 0"
        try:
            data = json.loads(stdout)
            if "par_groupe" not in data or "par_booleen" not in data:
                return False, "Structure JSON incomplete"
        except json.JSONDecodeError:
            return False, "Sortie non JSON valide"
        return True, ""

def test_sortie_texte():
    with tempfile.TemporaryDirectory() as tmpdir:
        fichier = Path(tmpdir) / "test.jsonl"
        fichier.write_text('{"texte": "test", "groupe": "A", "booleen": true}\n')
        cmd = [sys.executable, "nexus_stats_jsonl.py", str(fichier),
               "--champ-texte=texte", "--champ-groupe=groupe",
               "--champ-booleen=booleen", "--motif=test=test"]
        code, stdout, stderr = run_cmd(cmd, cwd=tmpdir)
        if code != 0:
            return False, f"Code {code} != 0"
        if "MOTIF x GROUPE" not in stdout or "MOTIF x BOOLEEN" not in stdout:
            return False, "Sortie texte incomplete"
        return True, ""

def main():
    script_path = Path("scripts") / "nexus_stats_jsonl.py"
    if not script_path.exists():
        print(f"[ERREUR] Fichier introuvable : {script_path}")
        return CODE_FICHIER_INEXISTANT

    tests = [
        ("Fichier inexistant", test_fichier_inexistant),
        ("Usage sans arguments", test_usage_sans_arguments),
        ("Motif mal forme", test_motif_mal_forme),
        ("Regex invalide", test_regex_invalide),
        ("JSONL invalide", test_jsonl_invalide),
        ("Sortie JSON", test_sortie_json),
        ("Sortie texte", test_sortie_texte),
    ]

    failed = 0
    for name, test_func in tests:
        try:
            success, msg = test_func()
            if not success:
                print(f"[ECHEC] {name} : {msg}")
                failed += 1
            else:
                print(f"[OK] {name}")
        except Exception as e:
            print(f"[ERREUR] {name} : {str(e)}")
            failed += 1

    return 1 if failed else 0

if __name__ == "__main__":
    sys.exit(main())
