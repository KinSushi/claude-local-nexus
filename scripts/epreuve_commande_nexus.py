# -*- coding: utf-8 -*-
"""Le controle des hotes PowerShell, sur cette machine et sur des cas jetables."""
import io
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from nexus_conformite import controle_commande_nexus as ctrl  # noqa: E402

echecs = 0


def verifier(nom, condition, detail):
    global echecs
    print("  [%s] %-46s %s" % ("OK  " if condition else "RATE", nom, detail))
    if not condition:
        echecs += 1


def maison(profils):
    """Un faux repertoire personnel. `profils` : {chemin relatif: contenu}."""
    d = tempfile.mkdtemp()
    for rel, contenu in profils.items():
        p = os.path.join(d, rel.replace("/", os.sep))
        os.makedirs(os.path.dirname(p), exist_ok=True)
        io.open(p, "w", encoding="utf-8").write(contenu)
    return d


def main():
    global echecs
    echecs = 0

    # PS51 et PS7 -- les profils sous un Documents NON redirige -- ont ete
    # retires : sur cette machine Documents est redirige vers OneDrive, et
    # aucun cas ne les employait. Les garder ferait croire qu'un cas les
    # couvre.
    OD51 = "OneDrive/Documents/WindowsPowerShell/Microsoft.PowerShell_profile.ps1"
    OD7 = "OneDrive/Documents/PowerShell/Microsoft.PowerShell_profile.ps1"

    print("--- L'INCIDENT VECU : servie en 7, absente en 5.1 ---")
    d = maison({OD51: "# rien ici\n", OD7: "function nexus { }\n"})
    try:
        e, det = ctrl(d)
        verifier("l'edition manquante est SIGNALEE", e == "ALERTE", "%s" % e)
        verifier("elle est NOMMEE", "WindowsPowerShell" in det, det[:64])
        verifier("le geste qui repare est cite",
                 "Install-NexusCommande" in det, det[-56:])
    finally:
        shutil.rmtree(d, ignore_errors=True)

    print("")
    print("--- LES DEUX EDITIONS SERVIES ---")
    d = maison({OD51: "function nexus { }\n", OD7: "function nexus { }\n"})
    try:
        e, det = ctrl(d)
        verifier("tout est servi -> OK", e == "OK", "%s : %s" % (e, det[:46]))
    finally:
        shutil.rmtree(d, ignore_errors=True)

    print("")
    print("--- LE PIEGE ONEDRIVE : Documents redirige ---")
    #
    # Un controle qui ne regarderait que ~/Documents ne verrait RIEN sur cette
    # machine, et conclurait a tort que la commande est absente partout.
    d = maison({OD51: "function nexus { }\n", OD7: "function nexus { }\n"})
    try:
        e, det = ctrl(d)
        verifier("les profils sous OneDrive sont vus", e == "OK", det[:60])
        verifier("le detail dit OU il a cherche",
                 "OneDrive" in det or "Documents" in det, det[:70])
    finally:
        shutil.rmtree(d, ignore_errors=True)

    print("")
    print("--- AUCUN PROFIL : ce n'est pas une faute ---")
    d = tempfile.mkdtemp()
    try:
        e, det = ctrl(d)
        verifier("aucun profil -> IGNORE, jamais alerte", e == "IGNORE",
                 "%s : une machine neuve n'est pas mal configuree" % e)
    finally:
        shutil.rmtree(d, ignore_errors=True)

    print("")
    print("--- ET SUR CETTE MACHINE ---")
    e, det = ctrl(os.path.expanduser("~"))
    print("  %s : %s" % (e, det[:100]))

    print("")
    print("%d echec(s)" % echecs)
    sys.exit(1 if echecs else 0)


if __name__ == "__main__":
    main()
