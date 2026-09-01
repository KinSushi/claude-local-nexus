# -*- coding: utf-8 -*-
import os
import sys
import importlib.util
import inspect

def _load_module():
    # Resolve repository root by locating the 'scripts' directory relative to this file
    cur = os.path.abspath(os.path.dirname(__file__))
    while True:
        if os.path.isdir(os.path.join(cur, 'scripts')):
            break
        parent = os.path.abspath(os.path.join(cur, os.pardir))
        if parent == cur:
            raise FileNotFoundError("Unable to locate repository root containing 'scripts'")
        cur = parent
    module_path = os.path.join(cur, 'scripts', 'nexus_garde_shell.py')
    spec = importlib.util.spec_from_file_location('nexus_garde_shell', module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load module from {module_path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

def _build_cases():
    # newline and backtick characters as required
    nl = chr(10)
    bt = chr(96)

    # detecter_cas_a : true when non‑quoted Python heredoc contains a backslash
    true_a = f"cat <<PYEOF{nl}some\\path{nl}PYEOF"
    false_a = "echo hello"

    # detecter_cas_b : true when an unescaped backtick appears inside double quotes
    true_b = f'echo "run {bt}ls{bt} now"'
    false_b = 'echo "no backticks here"'

    # detecter_cas_ps : true when PowerShell here‑string closing delimiter is indented
    true_ps = f"Write-Output @'{nl}    some text{nl}    '@{nl}"
    false_ps = f"Write-Output @'{nl}    some text{nl}'@{nl}"

    return {
        'detecter_cas_a': (true_a, false_a),
        'detecter_cas_b': (true_b, false_b),
        'detecter_cas_ps': (true_ps, false_ps),
    }

def main():
    module = _load_module()
    cases = _build_cases()
    failures = 0

    # Discover all functions whose name starts with detecter_cas_
    funcs = {
        name: func
        for name, func in inspect.getmembers(module, inspect.isfunction)
        if name.startswith('detecter_cas_')
    }

    # Check for functions missing in the cases table
    for name in funcs:
        if name not in cases:
            print(f"[RATE] {name} : missing test cases")
            failures += 1

    # Verify each function against its true/false commands
    for name, func in funcs.items():
        if name not in cases:
            continue  # already counted as failure
        true_cmd, false_cmd = cases[name]

        # True case
        try:
            result_true = func(true_cmd)
        except Exception as e:
            result_true = None
            print(f"[RATE] {name} : exception on true case ({e})")
            failures += 1
        else:
            if result_true is True:
                print(f"[OK  ] {name} : true case passed")
            else:
                print(f"[RATE] {name} : true case expected True, got {result_true}")
                failures += 1

        # False case
        try:
            result_false = func(false_cmd)
        except Exception as e:
            result_false = None
            print(f"[RATE] {name} : exception on false case ({e})")
            failures += 1
        else:
            if result_false is False:
                print(f"[OK  ] {name} : false case passed")
            else:
                print(f"[RATE] {name} : false case expected False, got {result_false}")
                failures += 1

    sys.exit(0 if failures == 0 else 1)

if __name__ == "__main__":
    main()