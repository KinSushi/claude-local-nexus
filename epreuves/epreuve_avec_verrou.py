# -*- coding: utf-8 -*-
"""Ce lanceur existe car aucun chemin legitime ne permettait d'executer
une commande arbitraire sous verrou, donc la mesure comparant appel
direct et passerelle etait impossible sans contourner le verrou.

L'epreuve verifie que le lanceur :
1. Signale l'absence de commande par le code 2.
2. Transmet le code de sortie 0 d'une commande reussie.
3. Propage le code de sortie non nul (ex: 42) d'une commande en echec.
4. Refuse l'execution (code 75) si le verrou est tenu par un tiers.

LIMITE : L'epreuve ne verifie pas que le verrou est reellement liberé
apres l'execution, seulement que le code de sortie est correct.
"""
import os
import subprocess
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LANCEUR = os.path.join(RACINE, "scripts", "nexus_avec_verrou.py")
SCRIPTS_DIR = os.path.join(RACINE, "scripts")

def _dire(ok, nom, detail):
    print("%s %s : %s" % ("[OK  ]" if ok else "[RATE]", nom, detail))
    return ok

def main():
    code_final = 0

    # Cas 1: Usage sans argument
    rc = subprocess.run([sys.executable, LANCEUR], capture_output=True).returncode
    if not _dire(rc == 2, "Usage sans argument", "code %d (attendu 2)" % rc):
        code_final = 1

    # Cas 2: Forward (succes)
    cmd_ok = [sys.executable, "-c", "import sys; sys.exit(0)"]
    rc = subprocess.run([sys.executable, LANCEUR, "banc", "--attente-s", "0", "--"] + cmd_ok, 
                        capture_output=True).returncode
    if not _dire(rc == 0, "Forward succes", "code %d (attendu 0)" % rc):
        code_final = 1

    # Cas 3: Propagation (echec commande)
    cmd_fail = [sys.executable, "-c", "import sys; sys.exit(42)"]
    rc = subprocess.run([sys.executable, LANCEUR, "banc", "--attente-s", "0", "--"] + cmd_fail, 
                        capture_output=True).returncode
    if not _dire(rc == 42, "Propagation echec", "code %d (attendu 42)" % rc):
        code_final = 1

    # Cas 4: Reverse (verrou tenu)
    tiers_code = (
        "import sys; sys.path.insert(0, %r); "
        "import nexus_verrou_machine as v; "
        "import time; "
        "ctx = v.verrou('banc', projet='epreuve', attente_s=0, bavard=False); "
        "ctx.__enter__(); print('tenu', flush=True); time.sleep(60)"
    ) % SCRIPTS_DIR
    
    tiers = subprocess.Popen([sys.executable, "-c", tiers_code], 
                              stdout=subprocess.PIPE, text=True)
    try:
        line = tiers.stdout.readline().strip()
        if line != "tenu":
            _dire(False, "Tiers verrou", "Ligne attendue 'tenu', recu '%s'" % line)
            code_final = 1
        else:
            rc = subprocess.run([sys.executable, LANCEUR, "banc", "--attente-s", "0", "--", 
                                sys.executable, "-c", "print('should not run')"], 
                                capture_output=True).returncode
            if not _dire(rc == 75, "Reverse verrou", "code %d (attendu 75)" % rc):
                code_final = 1
    finally:
        tiers.kill()
        tiers.wait()

    return code_final

if __name__ == "__main__":
    sys.exit(main())
