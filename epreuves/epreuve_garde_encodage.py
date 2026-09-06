"""La garde imprime-t-elle son refus sur une console cp1252 ?

Le patch pose a l instant introduit un U+2011 (trait d union insecable) dans
une chaine EMISE -- permissionDecisionReason -- et non dans un commentaire.
La regle du depot autorise les accents dans les commentaires et les interdit
dans ce qui est emis, precisement parce qu un caractere hors cp1252 tue le
script sur la console Windows par defaut.

Un hook qui meurt en imprimant son refus laisse passer la commande.
"""
import json
import os
import subprocess
import sys

CAS = [
    ("entree illisible", "pas du json"),
    ("commande dangereuse", json.dumps(
        {"tool_name": "Bash",
         "tool_input": {"command": 'git commit -m "code ' + chr(96) + "whoami" + chr(96) + ' ici"'}})),
]

echecs = 0
for encodage in ("utf-8", "cp1252"):
    print("  --- console %s ---" % encodage)
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = encodage
    for nom, entree in CAS:
        r = subprocess.run([sys.executable, "scripts/nexus_garde_shell.py"],
                           input=entree, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", env=env)
        plante = "Traceback" in (r.stderr or "") or "UnicodeEncodeError" in (r.stderr or "")
        refuse = '"deny"' in (r.stdout or "")
        etat = "PLANTE" if plante else ("refuse" if refuse else "laisse passer")
        if plante:
            echecs += 1
        print("    %-22s code=%d  %s" % (nom, r.returncode, etat))
        if plante:
            derniere = [x for x in (r.stderr or "").splitlines() if x.strip()][-1]
            print("        %s" % derniere[:110])

print()
if echecs:
    print("  %d PLANTAGE(S) : le refus ne s imprime pas, donc il ne refuse rien." % echecs)
else:
    print("  aucun plantage : le refus s imprime sur les deux consoles.")
sys.exit(1 if echecs else 0)
