# -*- coding: utf-8 -*-
import sys
import pathlib
import re

def find_repo_root(start_path: pathlib.Path) -> pathlib.Path:
    cur = start_path.resolve()
    while True:
        candidate = cur / "tools" / "nexus-mcp" / "server.js"
        if candidate.is_file():
            return cur
        if cur.parent == cur:
            break
        cur = cur.parent
    return None

def main():
    script_path = pathlib.Path(__file__)
    repo_root = find_repo_root(script_path.parent)
    if repo_root is None:
        print(f"[RATE] lisible {script_path.parent}")
        sys.exit(1)

    server_js = repo_root / "tools" / "nexus-mcp" / "server.js"
    try:
        content = server_js.read_text(encoding="utf-8")
    except Exception:
        print(f"[RATE] lisible {server_js}")
        sys.exit(1)

    lines = content.splitlines()
    handler_pattern = re.compile(r'^\s*if\s*\(\s*name\s*===\s*"([^"]+)"\s*\)\s*\{')
    handlers = []
    for idx, line in enumerate(lines):
        m = handler_pattern.search(line)
        if m:
            handlers.append((m.group(1), idx))

    if not handlers:
        print("[RATE] aucune gestionnaire trouvé")
        sys.exit(1)

    results = []
    all_ok = True
    for i, (name, start_idx) in enumerate(handlers):
        end_idx = handlers[i + 1][1] if i + 1 < len(handlers) else len(lines)
        block = lines[start_idx:end_idx]

        if not any("await chat(" in l for l in block):
            continue  # not concerned

        found_marker = None
        for l in block:
            if "mentionsReponse" in l:
                found_marker = "mentionsReponse"
                break
            if "tronquee" in l:
                found_marker = "tronquee"
                break

        if found_marker:
            results.append(f"[OK  ] {name} : {found_marker}")
        else:
            results.append(f"[RATE] {name} : aucune marque trouvee")
            all_ok = False

    if not results:
        print("[RATE] aucune appel au modele trouvé")
        sys.exit(1)

    for line in results:
        print(line)

    sys.exit(0 if all_ok else 1)

if __name__ == "__main__":
    main()