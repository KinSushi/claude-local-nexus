# -*- coding: utf-8 -*-
"""Épreuve fonctionnelle pour la fonction PowerShell Confirm-MoteurOllama
du script scripts/start.ps1.

Protocole identique à epreuve_agent_familles.py : une ligne [OK  ] ou [RATE]
par cas, sortie 1 si un cas RATE.
"""

import os
import pathlib
import shutil
import subprocess
import sys
import tempfile

def main():
    racine = pathlib.Path(__file__).resolve().parents[1]
    script_ps1 = racine / "scripts" / "start.ps1"
    ok_global = True

    # 1. Extraction de la fonction Confirm-MoteurOllama
    try:
        with open(script_ps1, 'r', encoding='utf-8') as f:
            lignes = f.readlines()
    except Exception as e:
        print(f"[RATE] lecture_ps1 : {e}")
        sys.exit(1)

    debut = -1
    fin = -1
    for i, ligne in enumerate(lignes):
        if ligne.strip() == "function Confirm-MoteurOllama {":
            debut = i
        elif debut != -1 and ligne.rstrip("\r\n") == "}":
            fin = i
            break

    if debut == -1 or fin == -1:
        print("[RATE] extraction_fonction : fonction introuvable")
        sys.exit(1)

    texte_fonction = ''.join(lignes[debut:fin + 1])

    # garde de longueur / présence du retour d'échec
    if len(texte_fonction) < 400 or "return $false" not in texte_fonction:
        print("[RATE] extraction_fonction : texte trop court ou retour $false absent")
        sys.exit(1)

    # 2. Recherche de pwsh ou powershell
    pwsh = shutil.which('pwsh') or shutil.which('powershell')
    if not pwsh:
        print("[RATE] pwsh : introuvable")
        sys.exit(1)

    # 3. Vérification du prélude (garde Start-Process)
    prelude = """
$global:lancements = @()
$global:essais = 0
function Write-Host { param([Parameter(ValueFromRemainingArguments=$true)]$a) }
function Start-Sleep { param([Parameter(ValueFromRemainingArguments=$true)]$a) }
function Invoke-WebRequest {
    param([Parameter(ValueFromRemainingArguments=$true)]$a)
    if ($env:EPREUVE_SONDE -eq 'ok') { return 'ok' }
    $global:essais++
    if ($env:EPREUVE_SONDE -eq 'apres' -and $global:essais -ge 2) { return 'ok' }
    throw 'sonde muette'
}
function Get-NetTCPConnection {
    param([Parameter(ValueFromRemainingArguments=$true)]$a)
    if ($env:EPREUVE_PORT -eq 'occupe') { return 'ecoute' }
    return $null
}
function Test-Path {
    param([Parameter(ValueFromRemainingArguments=$true)]$a)
    return ($env:EPREUVE_APP -eq 'present')
}
function Start-Process {
    param([Parameter(ValueFromRemainingArguments=$true)]$a)
    $global:lancements += ($a -join ' ')
}
"""
    if "function Start-Process" not in prelude:
        print("[RATE] prelude : Start-Process absent")
        sys.exit(1)

    # 4. Cas de test
    cas = [
        ("S1", {"EPREUVE_SONDE": "ok", "EPREUVE_PORT": "libre", "EPREUVE_APP": "present"},
         True, []),
        ("P1", {"EPREUVE_SONDE": "apres", "EPREUVE_PORT": "occupe", "EPREUVE_APP": "present"},
         True, []),
        ("A1", {"EPREUVE_SONDE": "apres", "EPREUVE_PORT": "libre", "EPREUVE_APP": "present"},
         True, ["ollama app.exe"]),
        ("A2", {"EPREUVE_SONDE": "muette", "EPREUVE_PORT": "libre", "EPREUVE_APP": "absent"},
         False, []),
        ("M1", {"EPREUVE_SONDE": "muette", "EPREUVE_PORT": "libre", "EPREUVE_APP": "present"},
         False, ["ollama app.exe"]),
    ]

    fuite_detectee = False
    temp_dir = tempfile.mkdtemp(prefix='epreuve_start_')
    try:
        for nom, env, attendu_resultat, attendu_lancements in cas:
            script = prelude + texte_fonction + """
$r = Confirm-MoteurOllama
"RESULTAT=$r"
"LANCEMENTS=" + ($global:lancements -join '|')
"""
            env_local = os.environ.copy()
            env_local.update({"LOCALAPPDATA": "C:\\faux\\LocalAppData"})
            env_local.update(env)

            script_path = os.path.join(temp_dir, f"{nom}.ps1")
            with open(script_path, 'w', encoding='utf-8-sig') as f:
                f.write(script)

            try:
                result = subprocess.run(
                    [pwsh, '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass',
                     '-File', script_path],
                    capture_output=True,
                    text=True,
                    encoding='utf-8',
                    errors='replace',
                    timeout=60,
                    env=env_local,
                    creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0)
                )
                stdout = result.stdout.strip()
                lignes_sortie = stdout.splitlines()

                resultat = None
                lancements = []
                for ligne in lignes_sortie:
                    if ligne.startswith("RESULTAT="):
                        resultat = ligne.split("=", 1)[1].strip().lower() == "true"
                    elif ligne.startswith("LANCEMENTS="):
                        lancements_str = ligne.split("=", 1)[1].strip()
                        lancements = lancements_str.split("|") if lancements_str else []

                if resultat is None:
                    detail = f"code={result.returncode} stderr={result.stderr[:300].replace(chr(10), ' ')}"
                    ok = False
                else:
                    ok = (resultat == attendu_resultat)
                    if ok and attendu_lancements:
                        ok = all(any(lancement.endswith(app) for lancement in lancements)
                                 for app in attendu_lancements)
                    elif ok:
                        ok = (len(lancements) == 0)
                    detail = f"RESULTAT={resultat} LANCEMENTS={lancements}"

                ok_global &= ok
                print(f"[{'OK  ' if ok else 'RATE'}] {nom} : {detail}")

                # Vérification FUITE_SERVE
                if any("serve" in lancement.lower() for lancement in lancements):
                    print("[RATE] FUITE_SERVE : lancement interdit détecté")
                    ok_global = False
                    fuite_detectee = True

            except subprocess.TimeoutExpired:
                print(f"[RATE] {nom} : timeout")
                ok_global = False
            except Exception as e:
                print(f"[RATE] {nom} : {e}")
                ok_global = False

        # 4b. Message de succès FUITE_SERVE si aucune fuite
        if not fuite_detectee:
            print("[OK  ] FUITE_SERVE : aucun lancement ne contient serve")

        # 5. Cas R1 (contre‑épreuve)
        texte_fonction_faux = texte_fonction.replace(
            "Start-Process -FilePath $app",
            "Start-Process -FilePath 'ollama' -ArgumentList 'serve'"
        )
        if texte_fonction_faux == texte_fonction:
            print("[RATE] R1 : substitution non appliquée")
            ok_global = False
        else:
            script = prelude + texte_fonction_faux + """
$r = Confirm-MoteurOllama
"RESULTAT=$r"
"LANCEMENTS=" + ($global:lancements -join '|')
"""
            env_local = os.environ.copy()
            env_local.update({
                "LOCALAPPDATA": "C:\\faux\\LocalAppData",
                "EPREUVE_SONDE": "apres",
                "EPREUVE_PORT": "libre",
                "EPREUVE_APP": "present"
            })

            script_path = os.path.join(temp_dir, "R1.ps1")
            with open(script_path, 'w', encoding='utf-8-sig') as f:
                f.write(script)

            try:
                result = subprocess.run(
                    [pwsh, '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass',
                     '-File', script_path],
                    capture_output=True,
                    text=True,
                    encoding='utf-8',
                    errors='replace',
                    timeout=60,
                    env=env_local,
                    creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0)
                )
                stdout = result.stdout.strip()
                lignes_sortie = stdout.splitlines()

                lancements = []
                for ligne in lignes_sortie:
                    if ligne.startswith("LANCEMENTS="):
                        lancements_str = ligne.split("=", 1)[1].strip()
                        lancements = lancements_str.split("|") if lancements_str else []

                fuite = any("serve" in lancement.lower() for lancement in lancements)
                ok = fuite
                detail = "fuite attendue détectée" if ok else "fuite attendue non détectée"
                ok_global &= ok
                print(f"[{'OK  ' if ok else 'RATE'}] R1 : {detail}")

            except subprocess.TimeoutExpired:
                print("[RATE] R1 : timeout")
                ok_global = False
            except Exception as e:
                print(f"[RATE] R1 : {e}")
                ok_global = False

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

    sys.exit(0 if ok_global else 1)

if __name__ == "__main__":
    main()
