# -*- coding: utf-8 -*-
"""Épreuve fonctionnelle pour les options de tâche unique du script
``scripts/nexus_agent.py``.

Chaque cas écrit sur STDOUT une ligne commençant exactement par
`[OK  ] ` (OK suivi de deux espaces) ou `[RATE] `, puis le nom du cas,
un deux‑points et un détail optionnel.  
Le code de sortie du processus est 0 si tous les cas réussissent,
1 sinon.

Utilisation :
    python epreuves/epreuve_agent_tache_unique.py
"""

import os
import pathlib
import sys
import subprocess
import time
import tempfile
import shutil

def check(nom, condition, detail=""):
    """Affiche le résultat d’un cas de test et renvoie le booléen."""
    if condition:
        print(f"[OK  ] {nom} : {detail}")
    else:
        print(f"[RATE] {nom} : {detail}")
    return condition

def main():
    # UTF‑8 pour la sortie standard
    sys.stdout.reconfigure(encoding='utf-8')

    ok = True
    repo_root = pathlib.Path(__file__).resolve().parents[1]

    # Lecture du journal réel avant le cas A
    journal_path = repo_root / ".nexus" / "circuit_journal.jsonl"
    if journal_path.is_file():
        with journal_path.open(encoding='utf-8') as f:
            initial_lines = f.read().splitlines()
    else:
        initial_lines = []

    # Répertoire temporaire isolant l’état du disjoncteur
    temp_dir = tempfile.mkdtemp(prefix='nexus_dj_epreuve_')
    env = os.environ.copy()
    env["NEXUS_GATEWAY"] = "http://127.0.0.1:9"
    env["NEXUS_AGENT_TIMEOUT"] = "5"
    env["NEXUS_ETAT_DISJONCTEUR"] = os.path.join(temp_dir, "disjoncteur.json")

    try:
        # ------------------------------------------------------------------
        # Cas A – forward (régression 43a5261)
        # ------------------------------------------------------------------
        cmd_a = [
            sys.executable,
            str(repo_root / "scripts" / "nexus_agent.py"),
            "--tache", "OK",
            "--modele", "gpt-oss-120b-cloud",
            "--max-tokens", "16",
            "--sans-repli",
        ]
        try:
            result_a = subprocess.run(
                cmd_a,
                capture_output=True,
                text=True,
                env=env,
                timeout=60,
            )
            sortie_a = (result_a.stdout or "") + (result_a.stderr or "")
            condition_a = "usage: nexus_agent.py" not in sortie_a
            ok &= check(
                "forward_A",
                condition_a,
                f"rc={result_a.returncode}"
            )
        except subprocess.TimeoutExpired:
            ok &= check("forward_A", False, "timeout")
        except Exception as e:  # pragma: no cover
            ok &= check("forward_A", False, str(e))

        # ------------------------------------------------------------------
        # Cas D – fuite_etat_reel (détection d’une fuite dans le journal)
        # ------------------------------------------------------------------
        if journal_path.is_file():
            with journal_path.open(encoding='utf-8') as f:
                later_lines = f.read().splitlines()
        else:
            later_lines = []
        new_lines = later_lines[len(initial_lines):]
        fuite = any('10061' in line or '127.0.0.1:9' in line for line in new_lines)
        condition_d = not fuite
        ok &= check(
            "fuite_etat_reel",
            condition_d,
            "leak détectée" if fuite else ""
        )

        # ------------------------------------------------------------------
        # Cas B – reverse (fichier JSONL inexistant, sans --nom)
        # ------------------------------------------------------------------
        cmd_b = [
            sys.executable,
            str(repo_root / "scripts" / "nexus_agent.py"),
            "--depuis-jsonl", "fichier_inexistant.jsonl",
        ]
        try:
            result_b = subprocess.run(
                cmd_b,
                capture_output=True,
                text=True,
                env=env,
                timeout=60,
            )
            sortie_b = (result_b.stdout or "") + (result_b.stderr or "")
            condition_code = result_b.returncode == 2
            condition_msg = "--nom" in sortie_b
            condition_b = condition_code and condition_msg
            detail_b = f"rc={result_b.returncode}, msg={'present' if condition_msg else 'absent'}"
            ok &= check("reverse_B", condition_b, detail_b)
        except subprocess.TimeoutExpired:
            ok &= check("reverse_B", False, "timeout")
        except Exception as e:  # pragma: no cover
            ok &= check("reverse_B", False, str(e))

        # ------------------------------------------------------------------
        # Cas C – reverse, garde amont (aucun argument)
        # ------------------------------------------------------------------
        cmd_c = [
            sys.executable,
            str(repo_root / "scripts" / "nexus_agent.py"),
        ]
        try:
            start = time.time()
            result_c = subprocess.run(
                cmd_c,
                capture_output=True,
                text=True,
                env=env,
                timeout=60,
            )
            duration = time.time() - start
            # un appel sans tache doit etre REFUSE (mesure du 2026-09-15 : rc=0 en silence)
            ok &= check(
                "reverse_garde_amont",
                result_c.returncode == 2 and 'usage' in ((result_c.stdout or '') + (result_c.stderr or '')).lower(),
                f"rc={result_c.returncode}, dur={duration:.2f}s"
            )
        except subprocess.TimeoutExpired:
            ok &= check("reverse_garde_amont", False, "timeout")
        except Exception as e:  # pragma: no cover
            ok &= check("reverse_garde_amont", False, str(e))

    finally:
        # Nettoyage du répertoire temporaire
        shutil.rmtree(temp_dir, ignore_errors=True)

    # ------------------------------------------------------------------
    # Résultat final
    # ------------------------------------------------------------------
    sys.exit(0 if ok else 1)

if __name__ == "__main__":
    main()
