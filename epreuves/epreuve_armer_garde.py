import sys
import os
import json
import tempfile
import shutil
import subprocess

def log_status(prefix, message):
    print(f"[{prefix}] {message}")

def create_temp_config():
    temp_dir = tempfile.mkdtemp()
    temp_config = os.path.join(temp_dir, "settings.json")
    with open(temp_config, "w", encoding="utf-8") as f:
        json.dump({"hooks": {"PreToolUse": []}}, f)
    return temp_dir, temp_config

def cleanup(temp_dir):
    shutil.rmtree(temp_dir)

def run_test(args, temp_config=None, expect_success=True):
    cmd = [sys.executable, "scripts/nexus_armer_garde.py"] + args
    if temp_config:
        env = os.environ.copy()
        env["USERPROFILE"] = temp_config.rsplit(os.sep, 2)[0]
        result = subprocess.run(cmd, capture_output=True, text=True, env=env)
    else:
        result = subprocess.run(cmd, capture_output=True, text=True)
    success = (result.returncode == 0) == expect_success
    log_status("OK  " if success else "RATE", f"Commande: {' '.join(args)}")
    if not success:
        log_status("RATE", f"Code retour: {result.returncode}, Sortie: {result.stdout.strip() or result.stderr.strip()}")
    return success

def main():
    tests = []
    all_passed = True

    # Préparation: créer un script de garde fictif
    guard_script = os.path.join("scripts", "nexus_garde_fictif.py")
    with open(guard_script, "w", encoding="utf-8") as f:
        f.write("# Fichier fictif pour les tests\n")

    # Cas 1: Appel sans arguments requis
    tests.append(("Appel sans arguments", lambda: run_test([], expect_success=False)))

    # Cas 2: Cible inexistante
    tests.append(("Script de garde inexistant", lambda: run_test(["nexus_garde_inexistant.py", "Bash", "--simulation"], expect_success=False)))

    # Cas 3: Chemin nominal (simulation)
    temp_dir, temp_config = create_temp_config()
    tests.append(("Chemin nominal (simulation)", lambda: run_test(["nexus_garde_fictif.py", "Bash", "--simulation"], temp_config=temp_config)))
    cleanup(temp_dir)

    # Cas 4: Refus d'armement double (simulation)
    temp_dir, temp_config = create_temp_config()
    run_test(["nexus_garde_fictif.py", "Bash", "--armer"], temp_config=temp_config)  # Premier armement
    tests.append(("Refus armement double", lambda: run_test(["nexus_garde_fictif.py", "Bash", "--armer"], temp_config=temp_config, expect_success=False)))
    cleanup(temp_dir)

    # Cas 5: Restauration sans sauvegarde
    temp_dir, temp_config = create_temp_config()
    tests.append(("Restauration sans sauvegarde", lambda: run_test(["--restaurer"], temp_config=temp_config, expect_success=False)))
    cleanup(temp_dir)

    # Exécution des tests
    for _name, test_func in tests:
        if not test_func():
            all_passed = False

    # Nettoyage du script fictif
    if os.path.exists(guard_script):
        os.remove(guard_script)

    if not all_passed:
        sys.exit(1)
    log_status("OK  ", "Tous les tests passés")

if __name__ == "__main__":
    main()
