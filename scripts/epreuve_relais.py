import os
import sys
import subprocess
import tempfile
import pathlib

def run_tool(args, tmp_dir):
    tool_path = pathlib.Path("scripts/nexus_relais.py")
    if not tool_path.exists():
        print(f"Outil introuvable: {tool_path}")
        sys.exit(127)
    
    cmd = [sys.executable, str(tool_path)] + args
    result = subprocess.run(
        cmd,
        cwd=tmp_dir,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace"
    )
    return result

def main():
    # Setup environnement isole
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = pathlib.Path(tmp_dir)
        # Simulation de la structure du depot
        scripts_dir = tmp_path / "scripts"
        scripts_dir.mkdir()
        nexus_dir = tmp_path / ".nexus"
        nexus_dir.mkdir()
        
        # Copie de l'outil dans le dossier temporaire pour l'execution
        tool_src = pathlib.Path("scripts/nexus_relais.py")
        tool_dest = scripts_dir / "nexus_relais.py"
        tool_dest.write_text(tool_src.read_text(encoding="utf-8"), encoding="utf-8")
        
        # Fichier cible pour les tests
        cible = scripts_dir / "test_cible.py"
        cible.write_text("print('hello')", encoding="utf-8")
        
        # On ajuste le chemin de l'outil pour le sous-processus
        # L'outil utilise BASE_DIR = pathlib.Path(__file__).resolve().parent
        # Donc on lance depuis scripts_dir
        
        results = []
        
        # CAS 1: NOMINAL (Simulation avec --simuler pour eviter dependances agent/git)
        # On utilise --file pour forcer la cible
        list_file = tmp_path / "list.txt"
        list_file.write_text(str(cible), encoding="utf-8")
        
        res1 = run_tool(["--simuler", "--file", str(list_file)], scripts_dir)
        results.append(("[NOMINAL]", res1.returncode == 0, res1.stdout))
        
        # CAS 2: INVERSE (Refus attendu)
        # L'outil doit refuser si aucune cible n'est trouvee (rend 2)
        res2 = run_tool(["--simuler", "--file", str(tmp_path / "vide.txt")], scripts_dir)
        # On cree le fichier vide pour eviter une erreur de lecture Python, 
        # mais lister_cibles rendra une liste vide.
        (tmp_path / "vide.txt").write_text("", encoding="utf-8")
        res2 = run_tool(["--simuler", "--file", str(tmp_path / "vide.txt")], scripts_dir)
        results.append(("[INVERSE]", res2.returncode != 0 and "No targets" in res2.stdout, res2.stdout))
        
        # CAS 3: MALFORMEE (Option invalide)
        res3 = run_tool(["--option-inexistante"], scripts_dir)
        results.append(("[MALFORMEE]", res3.returncode != 0, res3.stderr))
        
        # CAS 4: ARGUMENTS REQUIS (Usage)
        # L'outil n'a pas d'args positionnels requis, mais on teste l'invocation
        # sans options pour verifier qu'il ne plante pas et rend un code selon cibles
        # Si on est dans un dossier vide de .py (hors relais), il rend 2.
        res4 = run_tool([], scripts_dir)
        results.append(("[USAGE]", res4.returncode != 0, res4.stdout))

        # Affichage et verdict
        success = True
        for label, ok, out in results:
            print(f"{label} {'OK' if ok else 'FAIL'}")
            if not ok:
                success = False
        
        sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
