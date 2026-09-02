import os
import sys
import json
import subprocess
import tempfile

# Path to the tool relative to this file
TOOL_PATH = os.path.join(os.path.dirname(__file__), "scripts", "nexus_stats_jsonl.py")

if not os.path.isfile(TOOL_PATH):
    print("[ERROR] Tool not found at " + TOOL_PATH)
    sys.exit(3)

def run(args, input_data=None):
    try:
        result = subprocess.run(
            [sys.executable, TOOL_PATH] + args,
            input=input_data,
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return None, "", "Timeout expired"

def write_jsonl(path, lines):
    with open(path, "w", encoding="utf-8") as f:
        for line in lines:
            f.write(line + "\n")

def case_success(tmpdir):
    jsonl = os.path.join(tmpdir, "data.jsonl")
    lines = [
        json.dumps({"text": "hello world", "group": "A", "flag": True}),
        json.dumps({"text": "goodbye", "group": "B", "flag": False}),
        "invalid json line",
    ]
    write_jsonl(jsonl, lines)
    args = [
        jsonl,
        "--champ-texte", "text",
        "--champ-groupe", "group",
        "--champ-booleen", "flag",
        "--motif", "hello=hello",
    ]
    rc, out, err = run(args)
    if rc != 0:
        return False, f"expected rc 0 got {rc}"
    if "MOTIF x GROUPE" not in out:
        return False, "missing group table"
    if "invalides" not in out:
        return False, "missing invalid line count"
    return True, ""

def case_bad_regex(tmpdir):
    jsonl = os.path.join(tmpdir, "data.jsonl")
    write_jsonl(jsonl, [json.dumps({"text": "test", "group": "X", "flag": True})])
    args = [
        jsonl,
        "--champ-texte", "text",
        "--champ-groupe", "group",
        "--champ-booleen", "flag",
        "--motif", "bad=[",
    ]
    rc, out, err = run(args)
    if rc != 2:
        return False, f"expected rc 2 got {rc}"
    if "Regex invalide" not in out:
        return False, "missing regex error message"
    return True, ""

def case_malformed_input(tmpdir):
    jsonl = os.path.join(tmpdir, "data.jsonl")
    lines = [
        "not a json",
        json.dumps({"text": "ok", "group": "G", "flag": False}),
    ]
    write_jsonl(jsonl, lines)
    args = [
        jsonl,
        "--champ-texte", "text",
        "--champ-groupe", "group",
        "--champ-booleen", "flag",
        "--motif", "ok=ok",
    ]
    rc, out, err = run(args)
    if rc != 0:
        return False, f"expected rc 0 got {rc}"
    if "invalides" not in out:
        return False, "invalid line count not reported"
    return True, ""

def case_missing_args(tmpdir):
    jsonl = os.path.join(tmpdir, "data.jsonl")
    write_jsonl(jsonl, [json.dumps({"text": "x", "group": "Y", "flag": True})])
    args = [jsonl]  # no required options
    rc, out, err = run(args)
    if rc == 0 or rc is None:
        return False, f"expected non-zero rc got {rc}"
    if "usage:" not in err.lower():
        return False, "usage message not found"
    return True, ""

def case_unreadable_file(tmpdir):
    missing = os.path.join(tmpdir, "nope.jsonl")
    args = [
        missing,
        "--champ-texte", "text",
        "--champ-groupe", "group",
        "--champ-booleen", "flag",
        "--motif", "any=.",
    ]
    rc, out, err = run(args)
    if rc != 2:
        return False, f"expected rc 2 got {rc}"
    if "Fichier illisible" not in out:
        return False, "missing unreadable file message"
    return True, ""

cases = [
    ("SUCCESS", case_success),
    ("BAD_REGEX", case_bad_regex),
    ("MALFORMED", case_malformed_input),
    ("MISSING_ARGS", case_missing_args),
    ("UNREADABLE", case_unreadable_file),
]

overall_ok = True
with tempfile.TemporaryDirectory() as td:
    for name, func in cases:
        ok, msg = func(td)
        if ok:
            print(f"[{name}] OK")
        else:
            print(f"[{name}] FAIL {msg}")
            overall_ok = False

sys.exit(0 if overall_ok else 1)
