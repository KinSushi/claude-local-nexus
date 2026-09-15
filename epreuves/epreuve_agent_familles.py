# -*- coding: utf-8 -*-
"""Épreuve fonctionnelle pour la fonction ``famille_de`` et l’option
``--familles‑exclues`` du script ``scripts/nexus_agent.py``.

Cette épreuve suit le protocole attendu par ``outillage/nexus_test.py`` :
chaque cas écrit sur STDOUT une ligne commençant exactement par
`[OK  ] ` (OK suivi de deux espaces) ou `[RATE] `, puis le nom du cas,
un deux‑points et un détail optionnel.  
Le code de sortie du processus est 0 si tous les cas réussissent,
1 sinon.

Utilisation :
    python epreuves/epreuve_agent_familles.py
"""

import importlib.util
import pathlib
import sys
import subprocess
import time

def _load_module():
    """Charge ``scripts/nexus_agent.py`` depuis la racine du dépôt."""
    base_dir = pathlib.Path(__file__).resolve().parents[1]   # repository root
    script_path = base_dir / "scripts" / "nexus_agent.py"
    spec = importlib.util.spec_from_file_location("nexus_agent", script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module, base_dir

def check(nom, condition, detail=""):
    """Affiche le résultat d’un cas de test et renvoie le booléen."""
    if condition:
        print(f"[OK  ] {nom} : {detail}")
    else:
        print(f"[RATE] {nom} : {detail}")
    return condition

def main():
    ok = True
    module, repo_root = _load_module()

    # ------------------------------------------------------------------
    # 1. Vérifier la présence de ``famille_de``.
    # ------------------------------------------------------------------
    if not hasattr(module, "famille_de"):
        ok &= check("famille_de_absente", False, "fonction manquante")
        sys.exit(1)

    famille_de = module.famille_de

    # ------------------------------------------------------------------
    # 2. Cas forward – les alias doivent appartenir à la même famille.
    # ------------------------------------------------------------------
    forward_cases = [
        ("gpt-oss-120b-cloud", "ollama_chat/gpt-oss:120b"),
        ("gemma4-31b-cloud", "ollama_chat/gemma4:31b"),
        ("mistral-large-3-675b-cloud", "ollama_chat/mistral-large-3:675b"),
        ("qwen3.5-397b-cloud", "ollama_chat/qwen3.5:397b"),
        ("glm-4.7-flash-local", "ollama_chat/glm-4.7-flash:latest"),
    ]
    for i, (a1, a2) in enumerate(forward_cases, start=1):
        fam1 = famille_de(a1)
        fam2 = famille_de(a2)
        ok &= check(
            f"forward_{i}",
            fam1 == fam2,
            f"{a1}->{fam1} vs {a2}->{fam2}"
        )

    # ------------------------------------------------------------------
    # 3. Cas reverse – les alias doivent appartenir à des familles différentes.
    # ------------------------------------------------------------------
    reverse_cases = [
        ("qwen3.5-397b-cloud", "ollama_chat/gpt-oss:120b"),
        ("nemotron-3-ultra-cloud", "ollama_chat/gpt-oss:120b"),
        ("gemma4-31b-cloud", "ollama_chat/mistral-large-3:675b"),
    ]
    for i, (a1, a2) in enumerate(reverse_cases, start=1):
        fam1 = famille_de(a1)
        fam2 = famille_de(a2)
        ok &= check(
            f"reverse_{i}",
            fam1 != fam2,
            f"{a1}->{fam1} vs {a2}->{fam2}"
        )

    # ------------------------------------------------------------------
    # 4. Reverse par sous‑processus – option ``--familles-exclues``.
    # ------------------------------------------------------------------
    cmd = [
        sys.executable,
        str(repo_root / "scripts" / "nexus_agent.py"),
        "--tache", "Reponds OK",
        "--modele", "gpt-oss-120b-cloud",
        "--familles-exclues", "gpt-oss",
        "--max-tokens", "2000",
    ]
    start = time.time()
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=90,
        )
        duration = time.time() - start
        sortie = (result.stdout or "") + (result.stderr or "")
        condition_code = result.returncode != 0
        condition_msg = "exclue" in sortie.lower()
        condition_no_trac = not any(
            line.startswith("TRACABILITE") for line in sortie.splitlines()
        )
        ok &= check(
            "subprocess_reverse_code",
            condition_code,
            f"rc={result.returncode}"
        )
        ok &= check(
            "subprocess_reverse_msg",
            condition_msg,
            "motif d'exclusion absent"
        )
        ok &= check(
            "subprocess_reverse_no_trac",
            condition_no_trac,
            "TRACABILITE présent"
        )
        ok &= check(
            "subprocess_reverse_timing",
            duration < 60,
            f"{duration:.2f}s"
        )
    except subprocess.TimeoutExpired:
        ok &= check("subprocess_reverse_timeout", False, "délai dépassé")
    except Exception as e:  # pragma: no cover
        ok &= check("subprocess_reverse_error", False, str(e))

    # ------------------------------------------------------------------
    # 5. Fuite – aucune ligne ``TRACABILITE`` ne doit être émise.
    # ------------------------------------------------------------------
    # Le même appel que précédemment suffit : on vérifie uniquement l’absence
    # de toute ligne commençant par ``TRACABILITE``.
    ok &= check(
        "fuite_no_tracabilite",
        condition_no_trac,
        "TRACABILITE détecté"
    )

    # ------------------------------------------------------------------
    # Résultat final
    # ------------------------------------------------------------------
    sys.exit(0 if ok else 1)

if __name__ == "__main__":
    main()
