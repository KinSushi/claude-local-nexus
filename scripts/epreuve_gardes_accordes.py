# -*- coding: utf-8 -*-
"""Les deux etages d'un garde disent-ils la meme chose ?

CE QUI ETAIT FAUX, et vecu le 2026-08-31 : le matcher de settings.json
disait « Bash|PowerShell » pendant que le garde disait `!= "Bash"`.
PowerShell etait ROUTE vers un garde qui refusait de le juger. Rien ne
pouvait le dire, et le trou n'a ete trouve qu'en soumettant a la main la
meme commande sous deux noms d'outil.

Le CAS 2 rejoue exactement cette configuration.
"""
import os
import sys
import json
import io
import shutil
import tempfile

# try to import the function under test
try:
    sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
    from nexus_conformite import controle_gardes_accordes
except Exception as e:  # pragma: no cover
    print("[RATE] import : %s" % e)
    sys.exit(1)

echecs = 0


def verifier(nom, condition, detail):
    """Print result and count failures."""
    global echecs
    if condition:
        print("  [OK  ] %s : %s" % (nom, detail))
    else:
        print("  [RATE] %s : %s" % (nom, detail))
        echecs += 1


def depot(matchers, gardes, write_settings=True):
    """
    Create a temporary repository.

    matchers : list of (matcher_or_None, guard_name)
    gardes   : dict {guard_name: const_value or "NO_CONST"}
               const_value is a python object that will be written as a literal.
               "NO_CONST" means the file contains no OUTILS_JUGES line.
    write_settings : if False, do not create .claude/settings.json
    Returns the path to the temporary root.
    """
    root = tempfile.mkdtemp()
    try:
        # create scripts directory
        scripts_dir = os.path.join(root, "scripts")
        os.makedirs(scripts_dir, exist_ok=True)

        # write guard files
        for guard, const in gardes.items():
            guard_path = os.path.join(scripts_dir, guard + ".py")
            with io.open(guard_path, "w", encoding="utf-8") as f:
                f.write('"""guard script %s"""\n' % guard)
                if const == "NO_CONST":
                    # no constant line
                    pass
                elif const is not None:
                    f.write("OUTILS_JUGES = %s\n" % repr(const))
                else:
                    f.write("OUTILS_JUGES = None\n")

        # write settings.json if requested
        if write_settings:
            claude_dir = os.path.join(root, ".claude")
            os.makedirs(claude_dir, exist_ok=True)
            hooks = {}
            # we put everything under PreToolUse for simplicity
            pretool = []
            for matcher, guard in matchers:
                entry = {"hooks": [{"type": "command",
                                    "command": 'python "$CLAUDE_PROJECT_DIR/scripts/%s.py"' % guard}]}
                if matcher is not None:
                    entry["matcher"] = matcher
                pretool.append(entry)
            hooks["PreToolUse"] = pretool
            settings = {"hooks": hooks}
            settings_path = os.path.join(claude_dir, "settings.json")
            with io.open(settings_path, "w", encoding="utf-8") as f:
                json.dump(settings, f, ensure_ascii=False, indent=2)
        return root
    except Exception:
        # cleanup on error
        shutil.rmtree(root, ignore_errors=True)
        raise


def main():
    # ---------- CASE 1 ----------
    root = depot(
        matchers=[("Bash|PowerShell", "nexus_garde_shell")],
        gardes={"nexus_garde_shell": ("Bash", "PowerShell")},
    )
    try:
        etat, detail = controle_gardes_accordes(root)
        verifier(
            "CAS 1",
            etat == "OK",
            detail,
        )
    finally:
        shutil.rmtree(root, ignore_errors=True)

    # ---------- CASE 2 ----------
    root = depot(
        matchers=[("Bash|PowerShell", "nexus_garde_shell")],
        gardes={"nexus_garde_shell": ("Bash",)},
    )
    try:
        etat, detail = controle_gardes_accordes(root)
        verifier(
            "CAS 2",
            etat == "BLOQUE" and "PowerShell" in detail,
            detail,
        )
    finally:
        shutil.rmtree(root, ignore_errors=True)

    # ---------- CASE 3 ----------
    root = depot(
        matchers=[("Bash", "nexus_garde_shell")],
        gardes={"nexus_garde_shell": ("Bash", "PowerShell")},
    )
    try:
        etat, detail = controle_gardes_accordes(root)
        verifier(
            "CAS 3",
            etat == "ALERTE" and "PowerShell" in detail,
            detail,
        )
    finally:
        shutil.rmtree(root, ignore_errors=True)

    # ---------- CASE 4 ----------
    root = depot(
        matchers=[("Read", "nexus_garde_read")],
        gardes={"nexus_garde_read": None},
    )
    try:
        etat, detail = controle_gardes_accordes(root)
        verifier(
            "CAS 4",
            etat == "OK",
            detail,
        )
    finally:
        shutil.rmtree(root, ignore_errors=True)

    # ---------- CASE 5 ----------
    root = depot(
        matchers=[("Read", "nexus_garde_missing")],
        gardes={"nexus_garde_missing": "NO_CONST"},
    )
    try:
        etat, detail = controle_gardes_accordes(root)
        verifier(
            "CAS 5",
            etat == "ALERTE" and "nexus_garde_missing.py" in detail,
            detail,
        )
    finally:
        shutil.rmtree(root, ignore_errors=True)

    # ---------- CASE 6 ----------
    root = depot(
        matchers=[
            ("Read", "nexus_garde_multi"),
            ("Edit|Write", "nexus_garde_multi"),
        ],
        gardes={"nexus_garde_multi": ("Read", "Edit", "Write")},
    )
    try:
        etat, detail = controle_gardes_accordes(root)
        verifier(
            "CAS 6",
            etat == "OK",
            detail,
        )
    finally:
        shutil.rmtree(root, ignore_errors=True)

    # ---------- CASE 7 ----------
    root = depot(
        matchers=[],
        gardes={"nexus_garde_any": ("Bash",)},
        write_settings=False,
    )
    try:
        etat, detail = controle_gardes_accordes(root)
        verifier(
            "CAS 7",
            etat == "ALERTE",
            detail,
        )
    finally:
        shutil.rmtree(root, ignore_errors=True)

    # final report
    if echecs:
        print("%d test(s) failed" % echecs)
        sys.exit(1)
    else:
        print("all tests passed")
        sys.exit(0)


if __name__ == "__main__":
    main()
