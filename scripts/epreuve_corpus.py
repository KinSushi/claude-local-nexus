#!/usr/bin/env python3
import os
import sys
import tempfile
import subprocess
from pathlib import Path

CHUNK_SIZE = 4096
TIMEOUT = 10

def create_test_files(base_dir, files):
    for name, content in files.items():
        path = base_dir / name
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'wb') as f:
            f.write(content)

def get_file_stats(base_dir):
    stats = {}
    for path in base_dir.rglob('*'):
        if path.is_file():
            stats[str(path.relative_to(base_dir))] = path.stat().st_size
    return stats

def run_nexus_corpus(root, extensions=None, max_depth=None, json_output=False):
    cmd = [sys.executable, 'scripts/nexus_corpus.py', str(root)]
    if extensions:
        cmd.extend(['-e', extensions])
    if max_depth is not None:
        cmd.extend(['-d', str(max_depth)])
    if json_output:
        cmd.append('--json')

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=TIMEOUT
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "Timeout"

def test_case(name, setup_func, check_func, expected_code=0):
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        setup_func(temp_path)

        before_stats = get_file_stats(temp_path)
        code, stdout, stderr = run_nexus_corpus(temp_path)
        after_stats = get_file_stats(temp_path)

        success = (code == expected_code) and check_func(stdout, stderr) and (before_stats == after_stats)
        print(f"[{'OK  ' if success else 'FAIL'}] {name}")
        return success

def case_identical_files(temp_path):
    content = b"same content for testing"
    create_test_files(temp_path, {
        'file1.txt': content,
        'file2.txt': content,
        'subdir/file3.txt': content
    })

def check_identical_files(stdout, stderr):
    if stderr:
        return False
    return "Duplicate groups: 1" in stdout and "Potentially saved bytes" in stdout

def case_same_size_different_content(temp_path):
    create_test_files(temp_path, {
        'file1.txt': b"different content 1",
        'file2.txt': b"different content 2"
    })

def check_same_size_different_content(stdout, stderr):
    if stderr:
        return False
    return "Duplicate groups: 0" in stdout

def case_empty_directory(temp_path):
    pass

def check_empty_directory(stdout, stderr):
    if stderr:
        return False
    return "Duplicate groups: 0" in stdout and "0 files" in stdout

def case_nonexistent_path(temp_path):
    pass

def check_nonexistent_path(stdout, stderr):
    return "Path not found:" in stderr

def case_file_integrity(temp_path):
    create_test_files(temp_path, {
        'file1.txt': b"content 1",
        'file2.txt': b"content 2"
    })

def check_file_integrity(stdout, stderr):
    return not stderr

def main():
    if not os.path.exists('scripts/nexus_corpus.py'):
        print("[FAIL] Fichier de l'outil introuvable: scripts/nexus_corpus.py")
        sys.exit(1)

    test_cases = [
        ("Deux fichiers identiques", case_identical_files, check_identical_files),
        ("Meme taille contenu different", case_same_size_different_content, check_same_size_different_content),
        ("Repertoire vide", case_empty_directory, check_empty_directory, 0),
        ("Chemin inexistant", case_nonexistent_path, check_nonexistent_path, 1),
        ("Integrite des fichiers", case_file_integrity, check_file_integrity)
    ]

    results = []
    for name, setup, check, *expected in test_cases:
        expected_code = expected[0] if expected else 0
        results.append(test_case(name, setup, check, expected_code))

    if not all(results):
        sys.exit(1)

if __name__ == "__main__":
    main()
