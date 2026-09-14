# -*- coding: utf-8 -*-
"""
Épreuve « chemin pwsh stable ».

Cette épreuve vérifie que le résolveur PowerShell `Resolve-NexusShell.ps1`
rend un chemin stable lorsqu'il s'agit d'un exécutable du Microsoft Store,
et qu'il laisse inchangé un chemin classique. Elle s'assure également que
les scripts d'enregistrement n'utilisent plus `Get-Command pwsh`.

Les résultats sont imprimés sous la forme :

    [OK  ] <nom> : <detail>
    [RATE] <nom> : <detail>

et le processus se termine avec le code 1 en cas d'échec.
"""

import os
import sys
import shutil
import subprocess

# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------
def _root_dir() -> str:
    """Racine du dépôt (parent du dossier contenant ce fichier)."""
    return os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def _print_ok(name: str, detail: str = "") -> None:
    print("[OK  ] %s : %s" % (name, detail))


def _print_rate(name: str, detail: str = "") -> None:
    print("[RATE] %s : %s" % (name, detail))


def _check(name: str, condition: bool, detail: str = "") -> bool:
    """Imprime le résultat et renvoie la condition."""
    if condition:
        _print_ok(name, detail)
    else:
        _print_rate(name, detail)
    return condition


# ----------------------------------------------------------------------
# 1. forward – chemin du Store
# ----------------------------------------------------------------------
def _test_forward() -> bool:
    """Vérifie que Resolve-NexusShell rend un chemin stable pour le Store."""
    if os.name != "nt":
        _print_ok("forward", "ignore hors Windows")
        return True

    pwsh_path = shutil.which("pwsh")
    if not pwsh_path:
        _print_ok("forward", "ignore pwsh non trouvé")
        return True

    root = _root_dir()
    resolver = os.path.join(root, "outillage", "Resolve-NexusShell.ps1")
    if not os.path.isfile(resolver):
        return _check("forward", False, "Resolve-NexusShell.ps1 introuvable")

    candidate = r"C:\Program Files\WindowsApps\Microsoft.PowerShell_7.6.5.0_x64__8wekyb3d8bbwe\pwsh.exe"
    cmd = [
        "pwsh",
        "-NoProfile",
        "-NonInteractive",
        "-Command",
        f". '{resolver}'; Resolve-NexusShell -Candidat '{candidate}'",
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
        )
    except Exception as exc:
        return _check("forward", False, f"exception : {exc}")

    if result.returncode != 0:
        return _check("forward", False, f"exit {result.returncode}")

    output = result.stdout.strip()
    # Le résultat ne doit pas contenir le fragment du Store et doit être un fichier existant.
    ok = ("Microsoft.PowerShell_" not in output) and os.path.isfile(output)
    return _check("forward", ok, f"output='{output}'")


# ----------------------------------------------------------------------
# 2. reverse – chemin classique
# ----------------------------------------------------------------------
def _test_reverse() -> bool:
    """Vérifie que Resolve-NexusShell laisse inchangé un chemin classique."""
    if os.name != "nt":
        _print_ok("reverse", "ignore hors Windows")
        return True

    pwsh_path = shutil.which("pwsh")
    if not pwsh_path:
        _print_ok("reverse", "ignore pwsh non trouvé")
        return True

    root = _root_dir()
    resolver = os.path.join(root, "outillage", "Resolve-NexusShell.ps1")
    if not os.path.isfile(resolver):
        return _check("reverse", False, "Resolve-NexusShell.ps1 introuvable")

    candidate = r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"
    cmd = [
        "pwsh",
        "-NoProfile",
        "-NonInteractive",
        "-Command",
        f". '{resolver}'; Resolve-NexusShell -Candidat '{candidate}'",
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
        )
    except Exception as exc:
        return _check("reverse", False, f"exception : {exc}")

    if result.returncode != 0:
        return _check("reverse", False, f"exit {result.returncode}")

    output = result.stdout.strip()
    ok = output == candidate
    return _check("reverse", ok, f"output='{output}'")


# ----------------------------------------------------------------------
# 3. static – vérification des scripts d'enregistrement
# ----------------------------------------------------------------------
_SCRIPT_PATHS = [
    os.path.join("outillage", "Register-NexusTraque.ps1"),
    os.path.join("outillage", "Register-NexusVitrine.ps1"),
    os.path.join("outillage", "Register-NexusBoucleLocale.ps1"),
    os.path.join("scripts", "Register-NexusAutoUpdate.ps1"),
    os.path.join("scripts", "Register-NexusDemarrage.ps1"),
]


def _verify_script(rel_path: str) -> bool:
    """Vérifie le contenu d'un script d'enregistrement."""
    root = _root_dir()
    full_path = os.path.join(root, rel_path)
    try:
        with open(full_path, "r", encoding="utf-8", errors="replace") as fh:
            content = fh.read()
    except Exception as exc:
        return _check(rel_path, False, f"lecture échouée : {exc}")

    has_resolver = "Resolve-NexusShell" in content
    no_get_cmd = "Get-Command pwsh" not in content
    has_execute = "-Execute $shell" in content

    ok = has_resolver and no_get_cmd and has_execute
    detail_parts = []
    if not has_resolver:
        detail_parts.append("absent Resolve-NexusShell")
    if not no_get_cmd:
        detail_parts.append("présence Get-Command pwsh")
    if not has_execute:
        detail_parts.append("absent -Execute $shell")
    detail = ", ".join(detail_parts) if detail_parts else "ok"
    return _check(rel_path, ok, detail)


def _test_static_scripts() -> bool:
    """Exécute la vérification statique sur les cinq scripts."""
    results = [_verify_script(p) for p in _SCRIPT_PATHS]
    return all(results)


# ----------------------------------------------------------------------
# 4. detection – texte factice contenant Get-Command pwsh
# ----------------------------------------------------------------------
_FAKE_TEXT = "$pwshCmd = Get-Command pwsh -ErrorAction SilentlyContinue"


def _test_detection() -> bool:
    """Le même vérificateur doit échouer sur un texte factice."""
    # On réutilise la logique de _verify_script mais sur une chaîne.
    content = _FAKE_TEXT
    has_resolver = "Resolve-NexusShell" in content
    no_get_cmd = "Get-Command pwsh" not in content
    has_execute = "-Execute $shell" in content

    ok = has_resolver and no_get_cmd and has_execute
    # Le test doit rendre un échec (ok == False)
    return _check("detection", not ok, "le texte factice a été accepté")


# ----------------------------------------------------------------------
def main() -> int:
    failures = 0

    # Étape 1 – forward
    if not _test_forward():
        failures += 1

    # Étape 2 – reverse
    if not _test_reverse():
        failures += 1

    # Étape 3 – scripts statiques
    if not _test_static_scripts():
        failures += 1

    # Étape 4 – détection du faux positif
    if not _test_detection():
        failures += 1

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
