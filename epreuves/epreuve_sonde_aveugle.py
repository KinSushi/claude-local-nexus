#!/usr/bin/env python3
import sys, os, subprocess, tempfile, textwrap, pathlib

# --- tool source (nexus_sonde_aveugle) ---------------------------------
TOOL_SRC = """#!/usr/bin/env python3
import ast, os, sys
from pathlib import Path
class NexusSondeAveugle(ast.NodeVisitor):
    def __init__(self, path):
        self.path = path
        self.found = False
        self.keywords = {'injoignable','indisponible','absent','echec','failed',
                         'unavailable','unreachable','missing','error','offline'}
    def visit_Try(self, node):
        for h in node.handlers:
            if self._is_broad_exception(h):
                for s in h.body:
                    if isinstance(s, ast.Assign):
                        self._check_assignment(h, s)
        self.generic_visit(node)
    def _is_broad_exception(self, h):
        if h.type is None: return True
        return isinstance(h.type, ast.Name) and h.type.id in ('Exception','BaseException')
    def _check_assignment(self, h, s):
        for t in s.targets:
            if not isinstance(t, ast.Name): continue
            var = t.id
            v = s.value
            val = ast.unparse(v) if hasattr(ast, 'unparse') else "<?>"
            if any(k in var.lower() for k in self.keywords):
                self._report(h, var, val); continue
            if isinstance(v, ast.Constant) and isinstance(v.value, str):
                if any(k in v.value.lower() for k in self.keywords):
                    self._report(h, var, val); continue
            if isinstance(v, ast.Constant) and v.value is True:
                if any(k in var.lower() for k in self.keywords) or 'not' in var.lower():
                    self._report(h, var, val); continue
            self._report(h, var, val)
    def _report(self, h, var, val):
        print(f"{self.path}:{h.lineno}: Variable '{var}' = {val} dans un bloc except large")
        self.found = True
def scan_file(p):
    try:
        with open(p, 'r', encoding='utf-8') as f: tree = ast.parse(f.read(), filename=p)
        v = NexusSondeAveugle(p); v.visit(tree); return v.found
    except (UnicodeDecodeError, SyntaxError, OSError) as e:
        print(f"{p}: Erreur de lecture/syntaxe - {e}", file=sys.stderr); return False
def scan_path(p):
    found=False
    if os.path.isdir(p):
        for r,_,fs in os.walk(p):
            for f in fs:
                if f.endswith('.py') and scan_file(os.path.join(r,f)): found=True
    elif p.endswith('.py') and scan_file(p): found=True
    return found
if __name__=='__main__':
    if len(sys.argv)<2:
        print(f"Usage: {Path(__file__).name} <chemin>...", file=sys.stderr); sys.exit(2)
    g=False
    for arg in sys.argv[1:]:
        if scan_path(arg): g=True
    sys.exit(1 if g else 0)
"""

# -----------------------------------------------------------------------
def write_file(path, content):
    path.write_text(textwrap.dedent(content), encoding='utf-8')

def run_tool(tool, target):
    proc = subprocess.run([sys.executable, str(tool), str(target)],
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                           text=True)
    return proc.returncode, proc.stdout, proc.stderr

def main():
    with tempfile.TemporaryDirectory() as td:
        base = pathlib.Path(td)
        tool_path = base / "nexus_sonde_aveugle.py"
        write_file(tool_path, TOOL_SRC)
        os.chmod(tool_path, 0o755)

        cases = []

        # 1) Positive by value
        p1 = base / "pos_val.py"
        write_file(p1, """
            try:
                1/0
            except Exception:
                etat_moteur = "injoignable"
        """)
        cases.append(("POS_VAL", p1, True, "value triggers detection"))

        # 2) Negative (pass)
        p2 = base / "neg_pass.py"
        write_file(p2, """
            try:
                1/0
            except Exception:
                pass
        """)
        cases.append(("NEG_PASS", p2, False, "broad except but no indication"))

        # 3) Positive by name
        p3 = base / "pos_name.py"
        write_file(p3, """
            try:
                1/0
            except Exception:
                unavailable = 0
        """)
        cases.append(("POS_NAME", p3, True, "variable name contains keyword"))

        # 4) Syntax error (should not affect exit code)
        p4 = base / "syntax_err.py"
        write_file(p4, "def oops(:\n    pass")
        cases.append(("SYNTAX_ERR", p4, False, "invalid syntax ignored"))

        # 5) Directory traversal with mixed files
        d5 = base / "dir_mix"
        d5.mkdir()
        write_file(d5 / "a.py", "print('ok')")
        write_file(d5 / "b.py", """
            try:
                1/0
            except Exception:
                err = "unavailable"
        """)
        cases.append(("DIR_MIX", d5, True, "detect inside directory"))

        overall_ok = True
        for tag, target, expect_nonzero, desc in cases:
            rc, out, err = run_tool(tool_path, target)
            ok = (rc != 0) if expect_nonzero else (rc == 0)
            overall_ok = overall_ok and ok
            status = "OK" if ok else "FAIL"
            print(f"[{tag}] {status} {desc} (rc={rc})")
            # optional debug output can be uncommented
            # if out: print("STDOUT:", out.strip())
            # if err: print("STDERR:", err.strip())

        sys.exit(0 if overall_ok else 1)

if __name__ == "__main__":
    main()
