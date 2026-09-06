#!/usr/bin/env python3
"""
Test harness for scripts/nexus_libs.py
"""

import sys, json, subprocess, tempfile, pathlib

SCRIPT_DIR = pathlib.Path(__file__).resolve().parent
TOOL_PATH = SCRIPT_DIR / "nexus_libs.py"

def run_tool(doc_dir, cfg_path):
    return subprocess.run(
        [sys.executable, str(TOOL_PATH), "--doc-dir", str(doc_dir), "--config", str(cfg_path)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

def report(tag, ok, detail=""):
    prefix = "[OK]" if ok else "[FAIL]"
    print(f"{prefix} {tag}{' : ' + detail if detail else ''}")
    return ok

def main():
    # verify tool exists
    if not TOOL_PATH.is_file():
        print(f"[FAIL] TOOL_NOT_FOUND : {TOOL_PATH}")
        sys.exit(2)

    failures = 0

    # 1 - NOMINAL : module json present, no absence
    with tempfile.TemporaryDirectory() as td:
        doc = pathlib.Path(td) / "doc"
        (doc / "json").mkdir(parents=True)
        cfg = pathlib.Path(td) / "cfg.json"
        cfg.write_text(json.dumps({}))
        res = run_tool(doc, cfg)
        if not report("NOMINAL", res.returncode == 0):
            failures += 1

    # 2 - POSITIF : module nonexistent signaled absent
    with tempfile.TemporaryDirectory() as td:
        doc = pathlib.Path(td) / "doc"
        (doc / "nonexistent_mod").mkdir(parents=True)
        cfg = pathlib.Path(td) / "cfg.json"
        cfg.write_text(json.dumps({}))
        res = run_tool(doc, cfg)
        if not report("POSITIF", res.returncode != 0):
            failures += 1

    # 3 - PROFONDEUR : deep submodule missing
    with tempfile.TemporaryDirectory() as td:
        doc = pathlib.Path(td) / "doc"
        (doc / "json").mkdir(parents=True)
        cfg = pathlib.Path(td) / "cfg.json"
        cfg.write_text(json.dumps({"deep_modules": {"json": "json.nonexistent"}}))
        res = run_tool(doc, cfg)
        ok = res.returncode != 0 and "Importables mais non utilisables en profondeur" in res.stdout
        if not report("PROFONDEUR", ok):
            failures += 1

    # 4 - VIDE : empty directory, no error
    with tempfile.TemporaryDirectory() as td:
        doc = pathlib.Path(td) / "doc"
        doc.mkdir()
        cfg = pathlib.Path(td) / "cfg.json"
        cfg.write_text(json.dumps({}))
        res = run_tool(doc, cfg)
        if not report("VIDE", res.returncode == 0):
            failures += 1

    # 5 - CONFIG issues
    # 5a - missing file
    with tempfile.TemporaryDirectory() as td:
        doc = pathlib.Path(td) / "doc"
        doc.mkdir()
        missing_cfg = pathlib.Path(td) / "absent.json"
        res = run_tool(doc, missing_cfg)
        if not report("CONFIG_ABSENT", res.returncode != 0):
            failures += 1
    # 5b - invalid json
    with tempfile.TemporaryDirectory() as td:
        doc = pathlib.Path(td) / "doc"
        doc.mkdir()
        bad_cfg = pathlib.Path(td) / "bad.json"
        bad_cfg.write_text("{ invalid json")
        res = run_tool(doc, bad_cfg)
        if not report("CONFIG_INVALIDE", res.returncode != 0):
            failures += 1

    sys.exit(1 if failures else 0)

if __name__ == "__main__":
    main()
