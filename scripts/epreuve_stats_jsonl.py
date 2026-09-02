import os, sys, subprocess, json, tempfile, pathlib

# ----------------------------------------------------------------------
# Helper to locate the tool and report a reserved error if missing.
def locate_tool():
    path = os.path.join("scripts", "nexus_stats_jsonl.py")
    if not os.path.isfile(path):
        print(f"Outil introuvable: {path}")
        sys.exit(127)          # code reserve
    return path

# ----------------------------------------------------------------------
# Run the tool with given argument list and optional stdin data.
def run_tool(args, stdin_data=None):
    tool = locate_tool()
    # Execute in a temporary directory to avoid touching the repository.
    with tempfile.TemporaryDirectory() as tmpdir:
        cmd = [sys.executable, tool] + args
        proc = subprocess.Popen(
            cmd,
            cwd=tmpdir,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        try:
            out, err = proc.communicate(input=stdin_data, timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            return -1, "", "Timeout"
        return proc.returncode, out, err

# ----------------------------------------------------------------------
# Verify a single test case and print a marker.
def verify(name, args, expected_code, stdin_data=None, check_output=None):
    code, out, err = run_tool(args, stdin_data)
    success = (code == expected_code)
    if success and check_output is not None:
        try:
            data = json.loads(out)
            # The tool may output JSON only when --json is used.
            # check_output is a callable that returns True if content matches.
            success = check_output(data)
        except json.JSONDecodeError:
            success = False
    # Ensure no output on stderr for successful runs.
    if success and code == 0 and err.strip():
        success = False
    marker = "[OK  ]" if success else "[FAIL]"
    print(f"{marker} {name}")
    return success

# ----------------------------------------------------------------------
# Build a temporary JSONL file with given lines.
def make_jsonl(lines):
    fd, path = tempfile.mkstemp(suffix=".jsonl")
    os.close(fd)
    with open(path, "w", encoding="utf-8") as f:
        for line in lines:
            f.write(line + "\n")
    return path

# ----------------------------------------------------------------------
def main():
    results = []

    # CASE 1: nominal success, JSON output, one valid line.
    jsonl_path = make_jsonl(['{"text":"abc","group":"g1","flag":true}'])
    args1 = [
        jsonl_path,
        "--champ-texte", "text",
        "--champ-groupe", "group",
        "--champ-booleen", "flag",
        "--motif", "m1=abc",
        "--json",
    ]
    def check_json(data):
        return data.get("fichier") == jsonl_path and "par_groupe" in data
    results.append(verify("CASE1", args1, 0, check_output=check_json))

    # CASE 2: inverse refusal, malformed motif (missing '=').
    args2 = [
        jsonl_path,
        "--champ-texte", "text",
        "--champ-groupe", "group",
        "--champ-booleen", "flag",
        "--motif", "badmotif",
    ]
    results.append(verify("CASE2", args2, 2))

    # CASE 3: malformed JSONL line, tool must still succeed.
    jsonl_path2 = make_jsonl(['{"text":"ok","group":"g2","flag":false}', 'not a json'])
    args3 = [
        jsonl_path2,
        "--champ-texte", "text",
        "--champ-groupe", "group",
        "--champ-booleen", "flag",
        "--motif", "m2=ok",
    ]
    results.append(verify("CASE3", args3, 0))

    # CASE 4: missing required option, should return non-zero and print usage.
    args4 = [jsonl_path]  # no --champ-texte etc.
    results.append(verify("CASE4", args4, 2))

    # CASE 5: tool invoked without any arguments, should return non-zero.
    results.append(verify("CASE5", [], 2))

    # Clean up temporary files.
    for p in (jsonl_path, jsonl_path2):
        try:
            os.remove(p)
        except OSError:
            pass

    if not all(results):
        sys.exit(1)

if __name__ == "__main__":
    main()
