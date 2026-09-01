# -*- coding: utf-8 -*-
import os
import sys
import importlib.util
import traceback

def _find_repo_root(start_path):
    """Search upward from start_path for a directory containing a 'scripts' subdirectory."""
    current = os.path.abspath(start_path)
    while True:
        if os.path.isdir(os.path.join(current, 'scripts')):
            return current
        parent = os.path.abspath(os.path.join(current, os.pardir))
        if parent == current:  # reached filesystem root
            raise RuntimeError("Unable to locate repository root containing 'scripts'")
        current = parent

def _load_nexus_module(repo_root):
    module_path = os.path.join(repo_root, 'scripts', 'nexus_rituel.py')
    if not os.path.isfile(module_path):
        raise FileNotFoundError(f"Cannot find nexus_rituel.py at expected location: {module_path}")
    spec = importlib.util.spec_from_file_location('nexus_rituel', module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

class _FakeResult:
    def __init__(self, returncode=0, stdout='', stderr=''):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr

def _make_fake_run(returncode=0, stdout='', stderr='', raise_exc=False):
    """Factory returning a fake subprocess.run implementation."""
    def fake_run(*args, **kwargs):
        if raise_exc:
            raise RuntimeError("simulated subprocess failure")
        return _FakeResult(returncode, stdout, stderr)
    return fake_run

def _run_test(name, fake_run, expected_verdict, expect_detail_contains=None):
    """Execute a single test case, returning (passed, detail_message)."""
    try:
        # monkey‑patch
        original_run = nexus.subprocess.run
        nexus.subprocess.run = fake_run
        try:
            verdict, detail = nexus.redaction_declaree(str(_find_repo_root(os.path.abspath(os.path.dirname(__file__)))))
        finally:
            # always restore even if redaction_declaree raises
            nexus.subprocess.run = original_run
    except Exception:
        # any unexpected exception means failure (except the one we expect)
        return False, f"Unexpected exception:\n{traceback.format_exc()}"
    # verify verdict
    if verdict != expected_verdict:
        return False, f"Verdict {verdict!r} != expected {expected_verdict!r}"
    # verify detail if needed
    if expect_detail_contains is not None:
        if expect_detail_contains not in detail:
            return False, f"Detail does not contain expected text. Got: {detail!r}"
    return True, detail

if __name__ == '__main__':
    # 1. locate repository root and load the module
    repo_root = _find_repo_root(os.path.dirname(__file__))
    nexus = _load_nexus_module(repo_root)

    # keep original run to guarantee restoration even if something goes wrong
    original_run_global = nexus.subprocess.run

    all_pass = True
    results = []

    # ---- case 1: returncode 1 -> MANQUE ----
    fake = _make_fake_run(returncode=1)
    passed, detail = _run_test(
        name="code 1",
        fake_run=fake,
        expected_verdict=nexus.MANQUE,
    )
    results.append(("[OK  ]" if passed else "[RATE]") + f" code 1 : {detail}")
    all_pass = all_pass and passed

    # ---- case 2: returncode 2 -> IGNORE ----
    fake = _make_fake_run(returncode=2)
    passed, detail = _run_test(
        name="code 2",
        fake_run=fake,
        expected_verdict=nexus.IGNORE,
    )
    results.append(("[OK  ]" if passed else "[RATE]") + f" code 2 : {detail}")
    all_pass = all_pass and passed

    # ---- case 3: returncode 0 with author line -> OK ----
    author_line = "Auteur declare: Jean Dupont"
    fake = _make_fake_run(returncode=0, stdout=author_line + "\nquelque chose")
    passed, detail = _run_test(
        name="code 0 author",
        fake_run=fake,
        expected_verdict=nexus.OK,
        expect_detail_contains=author_line,
    )
    results.append(("[OK  ]" if passed else "[RATE]") + f" code 0 author : {detail}")
    all_pass = all_pass and passed

    # ---- case 4: subprocess.run raises -> IGNORE ----
    fake = _make_fake_run(raise_exc=True)
    passed, detail = _run_test(
        name="exception",
        fake_run=fake,
        expected_verdict=nexus.IGNORE,
    )
    results.append(("[OK  ]" if passed else "[RATE]") + f" exception : {detail}")
    all_pass = all_pass and passed

    # Ensure global restoration (defensive)
    try:
        nexus.subprocess.run = original_run_global
    except Exception:
        pass  # best effort; we already reported failures above

    # Print results
    for line in results:
        print(line)

    sys.exit(0 if all_pass else 1)