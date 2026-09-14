#!/usr/bin/env python3
"""
Épreuve de validation du verrou unique pour `nexus_valide.py`.

Chaque cas doit être affiché sous la forme :

    [OK  ] nom_du_cas : détail
    [RATE] nom_du_cas : détail   (en cas d'échec)

Le script se termine avec le code de sortie 0 si tous les cas passent,
ou 1 dès le premier échec.
"""

import os
import sys
import tempfile
import shutil

# Importer les fonctions depuis le script testé
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "scripts")))
try:
    from nexus_valide import verrou_est_libre, prendre_verrou, PLATEFORME
except Exception as exc:
    print("[RATE] import : impossible d'importer nexus_valide", str(exc))
    sys.exit(1)

def _print_ok(name, detail=""):
    print(f"[OK  ] {name} : {detail}")

def _print_rate(name, detail=""):
    print(f"[RATE] {name} : {detail}")

def _ok(cond, name, detail=""):
    if cond:
        _print_ok(name, detail)
    else:
        _print_rate(name, detail)
    return cond

def main():
    all_ok = True

    # ------------------------------------------------------------------
    # 1. contenu vide → libre
    # ------------------------------------------------------------------
    all_ok &= _ok(verrou_est_libre("", lambda p: False),
                  "verrou vide", "le verrou doit être considéré libre")

    # ------------------------------------------------------------------
    # 2. PID mort → libre
    # ------------------------------------------------------------------
    all_ok &= _ok(verrou_est_libre("12345", lambda p: False),
                  "pid mort", "PID inexistant doit rendre le verrou libre")

    # ------------------------------------------------------------------
    # 3. PID vivant → pris
    # ------------------------------------------------------------------
    all_ok &= _ok(not verrou_est_libre("12345", lambda p: True),
                  "pid vivant", "PID existant doit rendre le verrou occupé")

    # ------------------------------------------------------------------
    # 4. prendre_verrou dans un répertoire temporaire sous la racine
    # ------------------------------------------------------------------
    temp_root = tempfile.mkdtemp(dir=os.path.join(PLATEFORME, ".nexus"))
    lock_path = os.path.join(temp_root, "valide.lock")
    try:
        pid = os.getpid()
        # première acquisition : doit réussir
        first = prendre_verrou(lock_path, pid, lambda p: True)
        all_ok &= _ok(first, "prendre_verrou première fois", "doit retourner True")
        # deuxième acquisition avec un pid considéré vivant : doit échouer
        second = prendre_verrou(lock_path, pid + 1, lambda p: True)
        all_ok &= _ok(not second, "prendre_verrou deuxième fois", "doit retourner False")
        # le contenu du fichier doit rester le premier PID
        with open(lock_path, "r", encoding="utf-8") as fh:
            contenu = fh.read().strip()
        all_ok &= _ok(contenu == str(pid), "verrou contenu", f"contenu attendu {pid}, trouvé {contenu}")
    finally:
        shutil.rmtree(temp_root, ignore_errors=True)

    # ------------------------------------------------------------------
    # 5. Détection d'une implémentation erronée de `verrou_est_libre`
    # ------------------------------------------------------------------
    # On remplace temporairement la fonction par une version qui renvoie toujours True
    original = verrou_est_libre
    try:
        globals()["verrou_est_libre"] = lambda contenu, pid_vivant: True
        # Avec cette implémentation, le cas 3 (pid vivant) devrait échouer
        result = not verrou_est_libre("12345", lambda p: True)
        all_ok &= _ok(not result, "faux verrou_est_libre détecté",
                     "une implémentation qui renvoie toujours True doit faire échouer le cas pid vivant")
    finally:
        globals()["verrou_est_libre"] = original

    # Nettoyage du répertoire temporaire créé par le test
    # (déjà effectué dans le bloc finally ci‑dessus)

    sys.exit(0 if all_ok else 1)

if __name__ == "__main__":
    main()
