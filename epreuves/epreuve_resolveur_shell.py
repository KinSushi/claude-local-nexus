#!/usr/bin/env python3
# -*- coding: cp1252 -*-

"""
epreuve_resolveur_shell.py

Cette epreuve verifie le script PowerShell outillage/Resolve-NexusShell.ps1.
Elle comporte quatre cas :

1. Controle statique - recherche d'une affectation ou d'un return construisant
   un chemin vers « Microsoft\\WindowsApps\\pwsh.exe ». Si trouve, le cas
   rougit (defaut detecte).

2. Controle dynamique - execution du script dans PowerShell, appel de
   Resolve-NexusShell et validation du chemin retourne via valider_chemin :
   * le chemin n'est pas vide,
   * le fichier existe,
   * la taille est > 0,
   * l'attribut ReparsePoint n'est pas present.
   Tout manquement fait rougir le cas.

3. Contre-epreuve - creation d'un faux resolveur qui renvoie un chemin
   inexistant. La meme fonction valider_chemin que le CAS 2 est appelee sur
   ce resultat ; le cas reussit quand la validation REFUSE ce chemin, et
   echoue si elle l'accepte.

4. Garde du defaut corrige - appel de Resolve-NexusShell et verification que
   le chemin rendu ne correspond PAS au motif d'un chemin versionne du Store,
   des lors qu'un binaire stable existe sur la machine. Si aucun binaire
   stable n'existe, le cas est IGNORE avec un message expliquant pourquoi.

Le script imprime le verdict attendu et le verdict obtenu pour chaque cas,
puis une conclusion. Le code de sortie est 0 si tous les cas passent,
sinon 1. Si PowerShell est introuvable, le script indique l'erreur et renvoie
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
# 2. Gestion de l'encodage
# ------------------------------------------------------------
try:
    # ajouter le dossier outillage de la racine a sys.path
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    outillage_path = os.path.join(repo_root, "outillage")
    if outillage_path not in sys.path:
        sys.path.insert(0, outillage_path)

    from console_tools import forcer_utf8
    forcer_utf8()
except Exception as e:
    sys.stderr.write(f"Import forcer_utf8 echoue : {e}\n")

# ------------------------------------------------------------
# Helpers
# ------------------------------------------------------------
def is_reparse_point(path):
    """Retourne True si le fichier possede l'attribut ReparsePoint."""
    FILE_ATTRIBUTE_REPARSE_POINT = 0x0400
    GetFileAttributesW = ctypes.windll.kernel32.GetFileAttributesW
    GetFileAttributesW.argtypes = [ctypes.c_wchar_p]
    GetFileAttributesW.restype = ctypes.c_uint32
    attrs = GetFileAttributesW(path)
    if attrs == 0xFFFFFFFF:
        return False
    return bool(attrs & FILE_ATTRIBUTE_REPARSE_POINT)

def run_powershell(script):
    """Execute le script PowerShell fourni et retourne (stdout, stderr, rc)."""
    # choisir l'interpreteur disponible (powershell.exe ou pwsh.exe)
    exe = shutil.which("powershell.exe") or shutil.which("pwsh.exe")
    if not exe:
        return None, "PowerShell introuvable", 1
    cmd = [exe, "-NoProfile", "-NonInteractive", "-Command", script]
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    return proc.stdout.strip(), proc.stderr.strip(), proc.returncode

def verdict(expect, got):
    return "OK" if expect == got else "KO"

def valider_chemin(path):
    """
    Validation unique d'un chemin de resolveur, employee a la fois par le
    CAS 2 (controle dynamique) et par le CAS 3 (contre-epreuve).

    Retourne (ok, message) :
      * ok=True  si le chemin est non vide, existe, de taille > 0 et n'est
        pas un ReparsePoint ;
      * ok=False sinon, avec un message expliquant le refus.
    """
    if not path:
        return False, "Resultat vide ou null"
    if not os.path.isfile(path):
        return False, f"Chemin retourne n'existe pas : {path}"
    if os.path.getsize(path) == 0:
        return False, f"Fichier de taille nulle : {path}"
    if is_reparse_point(path):
        return False, f"Chemin est un ReparsePoint : {path}"
    return True, f"Chemin valide retourne : {path}"

# ------------------------------------------------------------
# 3. CAS 1 - Controle statique
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
        return False, "Alias WindowsApps detecte dans le texte (defaut statique)"
    return True, "Aucun alias WindowsApps detecte (statique OK)"

# ------------------------------------------------------------
# 4. CAS 2 - Controle dynamique
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
        return False, f"PowerShell a renvoye un code {rc} : {err}"
    return valider_chemin(out)

# ------------------------------------------------------------
# 5. CAS 3 - Contre-epreuve
# ------------------------------------------------------------
def test_counter():
    temp_dir = None
    try:
        temp_dir = tempfile.mkdtemp()
        fake_ps = os.path.join(temp_dir, "FakeResolve.ps1")
        # Le faux resolveur renvoie un chemin inexistant
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
            return False, f"PowerShell a renvoye {rc} : {err}"
        # On attend que la MEME validation que le CAS 2 refuse ce resultat.
        ok, msg = valider_chemin(out)
        if ok:
            return False, f"La validation a accepte le chemin faux : {out}"
        return True, f"La validation a refuse le chemin faux : {msg}"
    finally:
        if temp_dir and os.path.isdir(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)

# ------------------------------------------------------------
# 6. CAS 4 - Garde du defaut corrige (chemin versionne du Store)
# ------------------------------------------------------------
def chemin_versionne_store(path):
    """
    Critere propre a l'epreuve, ecrit ici et independant du code teste.

    Un chemin est versionne s'il contient, sous un dossier nomme WindowsApps,
    un segment commencant par Microsoft.PowerShell_ suivi d'un numero de
    version fait de chiffres et de points (par exemple
    Microsoft.PowerShell_7.6.6.0_x64__8wekyb3d8bbwe).

    Retourne True si le chemin est versionne, False sinon.
    """
    if not path:
        return False
    segments = re.split(r"[\\/]+", path)
    for i, seg in enumerate(segments):
        if seg.lower() == "windowsapps":
            for suivant in segments[i + 1:]:
                if re.match(r"^Microsoft\.PowerShell_[0-9]+(?:\.[0-9]+)*", suivant):
                    return True
    return False

def test_store_fallback():
    # Un binaire stable doit exister pour que le cas soit significatif.
    stable_candidates = []
    from_cmd = shutil.which("pwsh.exe")
    if from_cmd:
        stable_candidates.append(from_cmd)
    system_pwsh = os.path.join(
        os.environ.get("SystemRoot", r"C:\Windows"),
        "System32", "WindowsPowerShell", "v1.0", "powershell.exe",
    )
    if os.path.isfile(system_pwsh):
        stable_candidates.append(system_pwsh)

    if not stable_candidates:
        return None, "Aucun binaire stable (pwsh.exe non versionne ou powershell.exe systeme) sur cette machine : cas ignore"

    ps_path = os.path.join(repo_root, "outillage", "Resolve-NexusShell.ps1")
    ps_script = f'''
        . "{ps_path}"
        $result = Resolve-NexusShell
        if ($null -eq $result) {{ Write-Output "" }} else {{ Write-Output $result }}
    '''
    out, err_ps, rc = run_powershell(ps_script)
    if rc != 0:
        return False, f"PowerShell a renvoye un code {rc} : {err_ps}"
    if not out:
        return False, "Resolve-NexusShell a retourne un resultat vide"

    # Critere propre a l'epreuve, independant du resolveur teste.
    if chemin_versionne_store(out):
        return False, f"Chemin versionne du Store retourne alors qu'un binaire stable existe : {out}"
    return True, f"Chemin stable retourne (non versionne) : {out}"

# ------------------------------------------------------------
# Main
# ------------------------------------------------------------
def main():
    overall_success = True
    messages = []

    # Cas 1
    ok1, msg1 = test_static()
    messages.append(f"CAS 1 - Statique - attendu : OK - obtenu : {verdict(True, ok1)} - {msg1}")
    overall_success &= ok1

    # Cas 2
    ok2, msg2 = test_dynamic()
    messages.append(f"CAS 2 - Dynamique - attendu : OK - obtenu : {verdict(True, ok2)} - {msg2}")
    overall_success &= ok2

    # Cas 3
    ok3, msg3 = test_counter()
    messages.append(f"CAS 3 - Contre-epreuve - attendu : OK - obtenu : {verdict(True, ok3)} - {msg3}")
    overall_success &= ok3

    # Cas 4
    ok4, msg4 = test_store_fallback()
    if ok4 is None:
        messages.append(f"CAS 4 - Garde Store - IGNORE - {msg4}")
    else:
        messages.append(f"CAS 4 - Garde Store - attendu : OK - obtenu : {verdict(True, ok4)} - {msg4}")
        overall_success &= ok4

    # Impression des resultats
    for line in messages:
        print(line)

    if overall_success:
        print("CONCLUSION : Tous les cas passent, le defaut est absent.")
        sys.exit(0)
    else:
        print("CONCLUSION : Un ou plusieurs cas ont echoue, le defaut persiste.")
        sys.exit(1)

if __name__ == "__main__":
    main()
