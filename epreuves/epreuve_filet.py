import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / 'outillage'))

import nexus_filet

def _run_forward():
    ok = True
    diff1 = (
        "diff --git a/file1.txt b/file1.txt\n"
        "index e69de29..4b825dc 100644\n"
        "--- a/file1.txt\n"
        "+++ b/file1.txt\n"
        "deleted file mode 100644\n"
        "diff --git a/dir/file2.py b/dir/file2.py\n"
        "index 83db48f..f735c2d 100644\n"
        "--- a/dir/file2.py\n"
        "+++ b/dir/file2.py\n"
        "@@ -1 +0,0 @@\n"
        "-print('hello')\n"
        "deleted file mode 100644\n"
    )
    expected1 = ["file1.txt", "dir/file2.py"]
    try:
        result1 = nexus_filet.suppressions(diff1)
        if result1 == expected1:
            print("[OK  ] suppressions_forward_simple : returned expected list")
        else:
            print("[RATE] suppressions_forward_simple : expected {}, got {}".format(expected1, result1))
            ok = False
    except Exception as e:
        print("[RATE] suppressions_forward_simple : raised unexpected exception {}".format(e))
        ok = False

    diff2 = (
        "diff --git a/file3.txt b/file3.txt\n"
        "index e69de29..4b825dc 100644\n"
        "--- a/file3.txt\n"
        "+++ b/file3.txt\n"
        "@@ -0,0 +1 @@\n"
        "+new line\n"
    )
    expected2 = []
    try:
        result2 = nexus_filet.suppressions(diff2)
        if result2 == expected2:
            print("[OK  ] suppressions_forward_none : returned empty list")
        else:
            print("[RATE] suppressions_forward_none : expected {}, got {}".format(expected2, result2))
            ok = False
    except Exception as e:
        print("[RATE] suppressions_forward_none : raised unexpected exception {}".format(e))
        ok = False

    diff3 = (
        "diff --git a/ b/\n"
        "deleted file mode 100644\n"
    )
    expected3 = []
    try:
        result3 = nexus_filet.suppressions(diff3)
        if result3 == expected3:
            print("[OK  ] suppressions_forward_malformed : returned empty list")
        else:
            print("[RATE] suppressions_forward_malformed : expected {}, got {}".format(expected3, result3))
            ok = False
    except Exception as e:
        print("[RATE] suppressions_forward_malformed : raised unexpected exception {}".format(e))
        ok = False

    return ok

def _run_reverse():
    ok = True
    try:
        nexus_filet.suppressions(None)
        print("[RATE] suppressions_reverse_none : expected exception, got none")
        ok = False
    except Exception:
        print("[OK  ] suppressions_reverse_none : raised expected exception")
    return ok

def main():
    all_ok = True
    if not _run_forward():
        all_ok = False
    if not _run_reverse():
        all_ok = False
    return 0 if all_ok else 1

if __name__ == '__main__':
    sys.exit(main())