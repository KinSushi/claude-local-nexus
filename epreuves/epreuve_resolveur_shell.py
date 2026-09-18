#!/usr/bin/env python3
# -*- coding: cp1252 -*-

"""
epreuve_resolveur_shell.py

Cette epreuve vérifie le script PowerShell outillage/Resolve-NexusShell.ps1.
Elle comporte trois cas :

1. Contrôle statique – recherche d’une affectation ou d’un return construisant
   un chemin vers « Microsoft\\WindowsApps\\pwsh.exe ». Si trouvé, le cas
   rougit (défaut détecté).

2. Contrôle dynamique – exécution du script dans PowerShell, appel de
   Resolve‑NexusShell et validation du chemin retourné :
   * le chemin n’est pas vide,
   * le fichier existe,
   * la taille est > 0,
   * l’attribut ReparsePoint n’est pas présent.
   Tout manquement fait rougir le cas.

3. Contre‑épreuve – création d’un faux résolveur qui renvoie un chemin nul ou
   inexistant. Le contrôle dynamique doit refuser ce résultat, sinon le cas
   rougit.

Le script imprime le verdict attendu et le verdict obtenu pour chaque cas,
puis une conclusion. Le code de sortie est 0 si tous les cas passent,
sinon 1. Si PowerShell est introuvable, le script indique l’erreur et renvoie
un code de sortie non nul.
"""

import sys
import os
import re
import subprocess
import shutil
import tempfile
import ctypes

# ------------------------------------------------------------
# 2. Gestion de l’encodage
# ------------------------------------------------------------
try:
    # ajouter le dossier outillage de la racine à sys.path
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    outillage_path = os.path.join(repo_root, "outillage")
    if outillage_path not in sys.path:
        sys.path.insert(0, outillage_path)

    from console_tools import forcer_utf8
    forcer_utf8()
except Exception as e:
    sys.stderr.write(f"Import forcer_utf8 échoué : {e}\n")

# ------------------------------------------------------------
# Helpers
# ------------------------------------------------------------
def is_reparse_point(path):
    """Retourne True si le fichier possède l’attribut ReparsePoint."""
    FILE_ATTRIBUTE_REPARSE_POINT = 0x0400
    GetFileAttributesW = ctypes.windll.kernel32.GetFileAttributesW
    GetFileAttributesW.argtypes = [ctypes.c_wchar_p]
    GetFileAttributesW.restype = ctypes.c_uint32
    attrs = GetFileAttributesW(path)
    if attrs == 0xFFFFFFFF:
        return False
    return bool(attrs & FILE_ATTRIBUTE_REPARSE_POINT)

def run_powershell(script):
    """Exécute le script PowerShell fourni et retourne (stdout, stderr, rc)."""
    # choisir l’interpréteur disponible (powershell.exe ou pwsh.exe)
    exe = shutil.which("powershell.exe") or shutil.which("pwsh.exe")
    if not exe:
        return None, "PowerShell introuvable", 1
    cmd = [exe, "-NoProfile", "-NonInteractive", "-Command", script]
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    return proc.stdout.strip(), proc.stderr.strip(), proc.returncode

def verdict(expect, got):
    return "OK" if expect == got else "KO"

# ------------------------------------------------------------
# 3. CAS 1 – Contrôle statique
# ------------------------------------------------------------
def test_static():
    ps_path = os.path.join(repo_root, "outillage", "Resolve-NexusShell.ps1")
    try:
        with open(ps_path, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        return False, f"Impossible de lire le script : {e}"

    pattern = re.compile(r'(?:=|\breturn\b).*\bMicrosoft\\WindowsApps\\pwsh\.exe\b', re.IGNORECASE)
    if pattern.search(content):
        return False, "Alias WindowsApps détecté dans le texte (défaut statique)"
    return True, "Aucun alias WindowsApps détecté (statique OK)"

# ------------------------------------------------------------
# 4. CAS 2 – Contrôle dynamique
# ------------------------------------------------------------
def test_dynamic():
    ps_path = os.path.join(repo_root, "outillage", "Resolve-NexusShell.ps1")
    # script PowerShell qui source le fichier puis appelle la fonction
    ps_script = f'''
        . "{ps_path}"
        $result = Resolve-NexusShell
        if ($null -eq $result) {{ Write-Output "" }} else {{ Write-Output $result }}
    '''
    out, err, rc = run_powershell(ps_script)
    if rc != 0:
        return False, f"PowerShell a renvoyé un code {rc} : {err}"
    if not out:
        return False, "Résultat vide ou null"
    if not os.path.isfile(out):
        return False, f"Chemin retourné n’existe pas : {out}"
    if os.path.getsize(out) == 0:
        return False, f"Fichier de taille nulle : {out}"
    if is_reparse_point(out):
        return False, f"Chemin est un ReparsePoint : {out}"
    return True, f"Chemin valide retourné : {out}"

# ------------------------------------------------------------
# 5. CAS 3 – Contre‑épreuve
# ------------------------------------------------------------
def test_counter():
    temp_dir = None
    try:
        temp_dir = tempfile.mkdtemp()
        fake_ps = os.path.join(temp_dir, "FakeResolve.ps1")
        # Le faux résolveur renvoie un chemin inexistant
        with open(fake_ps, "w", encoding="utf-8") as f:
            f.write("""
function Resolve-NexusShell {
    return "C:\\nonexistent\\file.exe"
}
""")
        ps_script = f'''
            . "{fake_ps}"
            $result = Resolve-NexusShell
            if ($null -eq $result) {{ Write-Output "" }} else {{ Write-Output $result }}
        '''
        out, err, rc = run_powershell(ps_script)
        if rc != 0:
            return False, f"PowerShell a renvoyé {rc} : {err}"
        # On attend que le contrôle dynamique refuse ce résultat
        if not out:
            return False, "Le faux résolveur a retourné une chaîne vide (unexpected)"
        if os.path.isfile(out):
            return False, f"Le faux résolveur a retourné un fichier existant : {out}"
        # Si on arrive ici, le contrôle dynamique aurait accepté le mauvais résultat
        return False, f"Le contrôle dynamique n’a pas rejeté le chemin faux : {out}"
    finally:
        if temp_dir and os.path.isdir(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)

# ------------------------------------------------------------
# Main
# ------------------------------------------------------------
def main():
    overall_success = True
    messages = []

    # Cas 1
    ok1, msg1 = test_static()
    messages.append(f"CAS 1 – Statique – attendu : OK – obtenu : {verdict(True, ok1)} – {msg1}")
    overall_success &= ok1

    # Cas 2
    ok2, msg2 = test_dynamic()
    messages.append(f"CAS 2 – Dynamique – attendu : OK – obtenu : {verdict(True, ok2)} – {msg2}")
    overall_success &= ok2

    # Cas 3
    ok3, msg3 = test_counter()
    messages.append(f"CAS 3 – Contre‑épreuve – attendu : OK – obtenu : {verdict(True, ok3)} – {msg3}")
    overall_success &= ok3

    # Impression des résultats
    for line in messages:
        print(line)

    if overall_success:
        print("CONCLUSION : Tous les cas passent, le défaut est absent.")
        sys.exit(0)
    else:
        print("CONCLUSION : Un ou plusieurs cas ont échoué, le défaut persiste.")
        sys.exit(1)

if __name__ == "__main__":
    main()
