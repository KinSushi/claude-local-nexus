# -*- coding: utf-8 -*-
"""Verifie que nexus_charge.py detecte correctement la charge CPU et RAM.

L'epreuve est differentielle pour eviter les faux positifs (outil toujours 
positif ou toujours negatif). Elle valide :
  1. Le format JSON et la presence des cles requises.
  2. La detection d'un processus Python gourmand en CPU.
  3. L'absence de fausse alerte quand le seuil est inatteignable.
"""
import os
import sys
import subprocess
import json
import time

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(RACINE, "scripts", "nexus_charge.py")

def _dire(ok, nom, detail):
    print("%s %s : %s" % ("[OK  ]" if ok else "[RATE]", nom, detail))
    return ok

def main():
    code = 0
    
    # Cas 1 : JSON VALIDE
    # On lance sans charge particulière pour verifier la structure
    res1 = subprocess.run([sys.executable, SCRIPT, "--json"], 
                          capture_output=True, text=True)
    try:
        data = json.loads(res1.stdout)
        cles = ["au_repos", "verdict", "processus_significatifs", "ram_libre_go", "ram_totale_go"]
        ok_cles = all(k in data for k in cles)
        if not _dire(ok_cles, "format JSON", "toutes les cles sont presentes"):
            code = 1
    except Exception as e:
        _dire(False, "format JSON", "erreur de parse : %s" % e)
        code = 1

    # Processus de charge pour Cas 2 et 3
    # Boucle serree pour accumuler du temps CPU
    charge_proc = subprocess.Popen([sys.executable, "-c", "while True: pass"])
    
    try:
        # Attente pour que le processus accumule du temps CPU (UserModeTime)
        time.sleep(3)

        # Cas 2 : IL DETECTE
        # On force un seuil tres bas et on neutralise la RAM
        env2 = os.environ.copy()
        env2["NEXUS_CHARGE_SEUIL_MIN"] = "0.001"
        env2["NEXUS_CHARGE_RAM_MIN"] = "0"
        
        # IMPERATIF : lire returncode via subprocess.run, JAMAIS via tube shell
        res2 = subprocess.run([sys.executable, SCRIPT, "--json"], 
                              capture_output=True, text=True, env=env2)
        
        rc2 = res2.returncode
        try:
            data2 = json.loads(res2.stdout)
            pids = [p["pid"] for p in data2.get("processus_significatifs", [])]
            detecte = (rc2 == 1 and charge_proc.pid in pids)
            if not _dire(detecte, "detection de charge", "RC=%d, PID %d trouve=%s" % (rc2, charge_proc.pid, charge_proc.pid in pids)):
                code = 1
        except Exception as e:
            _dire(False, "detection de charge", "erreur JSON : %s" % e)
            code = 1

        # Cas 3 : IL NE CRIE PAS TOUJOURS
        # Seuil inatteignable, RAM neutralisee
        env3 = os.environ.copy()
        env3["NEXUS_CHARGE_SEUIL_MIN"] = "100000"
        env3["NEXUS_CHARGE_RAM_MIN"] = "0"
        
        res3 = subprocess.run([sys.executable, SCRIPT, "--json"], 
                              capture_output=True, text=True, env=env3)
        
        rc3 = res3.returncode
        try:
            data3 = json.loads(res3.stdout)
            signif = data3.get("processus_significatifs", [])
            silence = (rc3 == 0 and len(signif) == 0)
            if not _dire(silence, "absence de faux positif", "RC=%d, nb_proc=%d" % (rc3, len(signif))):
                code = 1
        except Exception as e:
            _dire(False, "absence de faux positif", "erreur JSON : %s" % e)
            code = 1

    finally:
        charge_proc.kill()
        charge_proc.wait()

    return code

if __name__ == "__main__":
    sys.exit(main())