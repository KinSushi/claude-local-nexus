#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import json
import subprocess
import tempfile
import shutil
from pathlib import Path
import py_compile

def _imprimer_ok(nom: str, detail: str) -> None:
    print(f"[OK  ] {nom} : {detail}")

def _imprimer_rate(nom: str, detail: str) -> None:
    print(f"[RATE] {nom} : {detail}")

def _creer_jsonl(contenu: str, nom_tache: str) -> Path:
    """Écrit un fichier JSONL temporaire contenant le rendu attendu."""
    texte = f"<<<CREER>>>\n{contenu}\n<<<FIN>>>"
    d = {"nom": nom_tache, "texte": texte}
    fd, path = tempfile.mkstemp(suffix=".jsonl", text=True)
    os.close(fd)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(d, fh, ensure_ascii=False)
        fh.write("\n")
    return Path(path)

def _lancer_outil(outil: Path, jsonl: Path, nom: str, cible: Path) -> int:
    """Exécute nexus_creer.py et renvoie le code retour."""
    proc = subprocess.run(
        [sys.executable, str(outil), str(jsonl), nom, str(cible)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return proc.returncode

def _verifier_fichier(cible: Path, attendu: str) -> bool:
    """Vérifie que le fichier existe, contient le texte attendu et compile."""
    if not cible.is_file():
        return False
    try:
        contenu = cible.read_text(encoding="utf-8")
    except Exception:
        return False
    if contenu != attendu:
        return False
    try:
        py_compile.compile(str(cible), doraise=True)
    except py_compile.PyCompileError:
        return False
    return True

def main() -> int:
    # 1. Localisation de l'outil
    racine = Path(__file__).resolve().parent.parent
    outil = racine / "scripts" / "nexus_creer.py"
    if not outil.is_file():
        _imprimer_rate("outil", "introuvable")
        return 1

    # 2. Répertoire temporaire sous la racine (nettoyé à la fin)
    temp_dir = tempfile.mkdtemp(dir=str(racine))
    overall_ok = True

    try:
        # -----------------------------------------------------------------
        # 1. FORWARD : création valide sous la racine
        # -----------------------------------------------------------------
        cible_forward = Path(temp_dir) / "forward.py"
        contenu_forward = "print('hello world')\n"
        jsonl_forward = _creer_jsonl(contenu_forward, "forward")
        rc = _lancer_outil(outil, jsonl_forward, "forward", cible_forward)
        ok = (
            rc == 0
            and _verifier_fichier(cible_forward, contenu_forward)
        )
        if ok:
            _imprimer_ok("FORWARD", "création réussie")
        else:
            _imprimer_rate("FORWARD", f"rc={rc}")
            overall_ok = False
        jsonl_forward.unlink(missing_ok=True)

        # -----------------------------------------------------------------
        # 2. REVERSE existant : tentative d'écrasement du même fichier
        # -----------------------------------------------------------------
        jsonl_reverse_exist = _creer_jsonl(contenu_forward, "reverse_exist")
        rc = _lancer_outil(outil, jsonl_reverse_exist, "reverse_exist", cible_forward)
        ok = rc != 0 and cible_forward.is_file()
        if ok:
            _imprimer_ok("REVERSE_EXIST", "refus d'écrasement")
        else:
            _imprimer_rate("REVERSE_EXIST", f"rc={rc}")
            overall_ok = False
        jsonl_reverse_exist.unlink(missing_ok=True)

        # -----------------------------------------------------------------
        # 3. REVERSE hors racine : cible en dehors du dépôt
        # -----------------------------------------------------------------
        cible_hors = Path(tempfile.gettempdir()) / "epreuve_creer_HORS.py"
        if cible_hors.exists():
            cible_hors.unlink()
        jsonl_hors = _creer_jsonl(contenu_forward, "hors")
        rc = _lancer_outil(outil, jsonl_hors, "hors", cible_hors)
        ok = rc != 0 and not cible_hors.exists()
        if ok:
            _imprimer_ok("REVERSE_HORS", "refus hors racine")
        else:
            _imprimer_rate("REVERSE_HORS", f"rc={rc}")
            overall_ok = False
        jsonl_hors.unlink(missing_ok=True)
        if cible_hors.exists():
            cible_hors.unlink(missing_ok=True)

        # -----------------------------------------------------------------
        # 4. REVERSE syntaxe : contenu Python invalide
        # -----------------------------------------------------------------
        cible_syntaxe = Path(temp_dir) / "syntax_error.py"
        contenu_syntaxe = "def foo(:\n    pass\n"
        jsonl_syntaxe = _creer_jsonl(contenu_syntaxe, "syntax")
        rc = _lancer_outil(outil, jsonl_syntaxe, "syntax", cible_syntaxe)
        ok = rc != 0 and not cible_syntaxe.exists()
        if ok:
            _imprimer_ok("REVERSE_SYNTAXE", "refus syntaxe")
        else:
            _imprimer_rate("REVERSE_SYNTAXE", f"rc={rc}")
            overall_ok = False
        jsonl_syntaxe.unlink(missing_ok=True)
        if cible_syntaxe.exists():
            cible_syntaxe.unlink(missing_ok=True)

    finally:
        # Nettoyage du répertoire temporaire créé sous la racine
        shutil.rmtree(temp_dir, ignore_errors=True)

    return 0 if overall_ok else 1

if __name__ == "__main__":
    sys.exit(main())