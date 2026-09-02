import sys
import subprocess
import tempfile
import pathlib

def run_tool(args, tool_path, tmp_dir):
    cmd = [sys.executable, str(tool_path)] + args
    try:
        return subprocess.run(
            cmd,
            cwd=tmp_dir,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10
        )
    except subprocess.TimeoutExpired:
        return "TIMEOUT"
    except Exception as e:
        return f"ERROR: {str(e)}"

def main():
    tool_rel_path = pathlib.Path("scripts/nexus_relais.py")
    if not tool_rel_path.exists():
        print(f"Outil introuvable: {tool_rel_path}")
        sys.exit(127)

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = pathlib.Path(tmp_dir)
        scripts_dir = tmp_path / "scripts"
        scripts_dir.mkdir()
        nexus_dir = tmp_path / ".nexus"
        nexus_dir.mkdir()
        
        tool_dest = scripts_dir / "nexus_relais.py"
        tool_dest.write_text(tool_rel_path.read_text(encoding="utf-8"), encoding="utf-8")
        
        # L'outil calcule REPO_ROOT = BASE_DIR.parent
        # BASE_DIR = tool_dest.resolve().parent (scripts_dir)
        # REPO_ROOT = tmp_path
        
        results = []
        
        # CAS 1: NOMINAL
        # --simuler evite les imports nexus_agent/nexus_patch
        cible = scripts_dir / "test_ok.py"
        cible.write_text("print('ok')", encoding="utf-8")
        list_file = tmp_path / "list.txt"
        list_file.write_text(str(cible), encoding="utf-8")
        
        res1 = run_tool(["--simuler", "--file", str(list_file)], tool_dest, tmp_path)
        if res1 == "TIMEOUT":
            results.append(("[NOMINAL]", False, "L'outil n'a pas rendu la main"))
        elif isinstance(res1, str) and res1.startswith("ERROR"):
            results.append(("[NOMINAL]", False, res1))
        else:
            results.append(("[NOMINAL]", res1.returncode == 0, res1.stdout))

        # CAS 2: INVERSE (Aucune cible)
        # Un fichier vide pour --file doit rendre 2 et "No targets to process."
        empty_list = tmp_path / "empty.txt"
        empty_list.write_text("", encoding="utf-8")
        res2 = run_tool(["--simuler", "--file", str(empty_list)], tool_dest, tmp_path)
        if res2 == "TIMEOUT":
            results.append(("[INVERSE]", False, "L'outil n'a pas rendu la main"))
        elif isinstance(res2, str) and res2.startswith("ERROR"):
            results.append(("[INVERSE]", False, res2))
        else:
            ok = (res2.returncode == 2 and "No targets to process." in res2.stdout)
            results.append(("[INVERSE]", ok, res2.stdout) if ok else ("[INVERSE]", False, res2.stdout))

        # CAS 3: MALFORMEE (Option invalide)
        res3 = run_tool(["--invalid-opt"], tool_dest, tmp_path)
        if res3 == "TIMEOUT":
            results.append(("[MALFORMEE]", False, "L'outil n'a pas rendu la main"))
        elif isinstance(res3, str) and res3.startswith("ERROR"):
            results.append(("[MALFORMEE]", False, res3))
        else:
            results.append(("[MALFORMEE]", res3.returncode != 0, res3.stderr))

        # CAS 4: USAGE (Sans arguments, dossier vide)
        # Sans --file et sans .nexus/relais-file.txt, il cherche *.py dans scripts/
        # On a seulement nexus_relais.py (exclu), donc 0 cible -> return 2
        res4 = run_tool([], tool_dest, tmp_path)
        if res4 == "TIMEOUT":
            results.append(("[USAGE]", False, "L'outil n'a pas rendu la main"))
        elif isinstance(res4, str) and res4.startswith("ERROR"):
            results.append(("[USAGE]", False, res4))
        else:
            results.append(("[USAGE]", res4.returncode != 0, res4.stdout))

        success = True
        for label, ok, _msg in results:
            print(f"{label} {'OK' if ok else 'FAIL'}")
            if not ok:
                success = False
        
        sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
