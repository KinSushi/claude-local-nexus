import sys
from pathlib import Path

def _load_source():
    """
    Load the source file outillage/nexus_test.py relative to the project root.
    Returns the list of lines (including newline characters).
    """
    root = Path(__file__).resolve().parent.parent
    source_path = root / "outillage" / "nexus_test.py"
    try:
        with source_path.open("r", encoding="utf-8") as f:
            return f.readlines()
    except FileNotFoundError:
        # If the source file itself is missing, treat as a failure for both cases.
        return None

def _find_skip_introuvable(lines):
    """
    Return a list of tuples (lineno, line) for lines that contain both
    'skip(' and 'introuvable'.
    """
    matches = []
    for idx, line in enumerate(lines, start=1):
        if "skip(" in line and "introuvable" in line:
            matches.append((idx, line.rstrip("\n")))
    return matches

def _run_checks():
    lines = _load_source()
    if lines is None:
        print("[RATE] case1 : source file outillage/nexus_test.py not found")
        print("[RATE] case2 : source file outillage/nexus_test.py not found")
        sys.exit(1)

    matches = _find_skip_introuvable(lines)

    # ----- Case 1 -----
    # Success if at most one match and, if present, it mentions 'node'.
    case1_success = True
    case1_detail = ""

    if len(matches) == 0:
        # No skip introuvable lines: acceptable for case1
        case1_detail = "no skip introuvable lines found"
    elif len(matches) == 1:
        lineno, line = matches[0]
        if "node" in line:
            case1_detail = f"single skip introuvable line at {lineno}"
        else:
            case1_success = False
            case1_detail = f"line {lineno} does not mention node: {line}"
    else:
        case1_success = False
        lines_str = ", ".join(str(l[0]) for l in matches)
        case1_detail = f"multiple skip introuvable lines at {lines_str}"

    # ----- Case 2 -----
    # The legitimate runtime node skip must be present.
    case2_success = any("node" in line for _, line in matches)
    if case2_success:
        case2_detail = "runtime node skip line present"
    else:
        case2_detail = "runtime node skip line missing"

    # Output results
    if case1_success:
        print(f"[OK  ] case1 : {case1_detail}")
    else:
        print(f"[RATE] case1 : {case1_detail}")

    if case2_success:
        print(f"[OK  ] case2 : {case2_detail}")
    else:
        print(f"[RATE] case2 : {case2_detail}")

    # Exit code: 0 only if both cases succeeded
    sys.exit(0 if case1_success and case2_success else 1)

if __name__ == "__main__":
    _run_checks()