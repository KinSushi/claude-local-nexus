import os
import sys
import subprocess
import tempfile
import json

def run_tool(args, files=None):
    tool_path = "scripts/nexus_schema.py"
    if not os.path.exists(tool_path):
        print("Outil introuvable: " + tool_path)
        sys.exit(127)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        created_files = []
        if files:
            for name, content in files.items():
                path = os.path.join(tmpdir, name)
                with open(path, "w", encoding="utf-8") as f:
                    f.write(content)
                created_files.append(path)
        
        cmd = [sys.executable, tool_path] + args
        # On remplace les noms de fichiers relatifs par les chemins temporaires
        final_cmd = []
        for a in cmd:
            if a in ["--profondeur-max", "--echantillon", "--json"]:
                final_cmd.append(a)
            elif a.isdigit() or a.startswith("-"):
                final_cmd.append(a)
            elif a in (f for f in files.keys() if files.keys()):
                # On cherche le chemin complet correspondant au nom du fichier
                final_cmd.append(os.path.join(tmpdir, a))
            else:
                final_cmd.append(a)

        # Correction pour les arguments positionnels (chemins)
        # On reconstruit la commande pour etre sur que les chemins sont corrects
        actual_args = []
        for arg in args:
            if arg in files and files:
                actual_args.append(os.path.join(tmpdir, arg))
            else:
                actual_args.append(arg)
        
        full_cmd = [sys.executable, tool_path] + actual_args

        try:
            proc = subprocess.Popen(
                full_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=tmpdir
            )
            stdout, stderr = proc.communicate(timeout=10)
            return proc.returncode, stdout, stderr
        except subprocess.TimeoutExpired:
            proc.kill()
            return -1, "", "L'outil n'a pas rendu la main"
        except Exception as e:
            return -2, "", "Erreur execution: " + str(e)

def main():
    test_files = {
        "ok.json": '{"a": 1, "b": [1, 2], "c": {"d": "txt"}}',
        "ok.jsonl": '{"x": 1}\n{"x": 2}\n',
        "ok.csv": "nom,age\nAlice,30\nBob,25",
        "bad.txt": "Ceci n'est pas un format supporte",
        "malformed.json": '{"a": 1, "b": '
    }

    cases = [
        ("NOMINAL", ["ok.json", "ok.csv"], 0, True),
        ("INVERSE", ["bad.txt"], 2, False),
        ("MALFORME", ["malformed.json"], 1, False),
        ("USAGE", [], 2, False), # Sans arguments requis
    ]

    success_all = True
    for name, args, exp_code, should_succeed in cases:
        code, out, err = run_tool(args, test_files)
        
        # Pour USAGE, on verifie que le code est non nul et que l'usage est affiche
        if name == "USAGE":
            # argparse rend souvent 2 pour les erreurs d'arguments
            res = (code != 0 and ("usage:" in out.lower() or "usage:" in err.lower()))
        elif name == "INVERSE":
            # Doit refuser et ecrire un motif
            res = (code == 2 and "Aucun fichier n'a pu etre decrit" in stderr_msg(err, out))
        elif name == "MALFORME":
            # Doit classer sans planter (code 1 car un fichier a echoue)
            res = (code == 1 and "ERREUR" in out)
        else:
            res = (code == exp_code)

        marker = "[OK  ]" if res else "[FAIL]"
        print(f"{marker} {name}")
        if not res:
            success_all = False

    if not success_all:
        sys.exit(1)

def stderr_msg(err, out):
    return err + " " + out

if __name__ == "__main__":
    main()
