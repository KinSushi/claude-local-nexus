# -*- coding: utf-8 -*-
"""Épreuve fonctionnelle pour ``scripts/nexus_orphelins.py``.

Incident du 2026‑09‑14 : 4 processus ``llama‑server`` orphelins, 68 Go d’engagement,
et ``ollama ps`` ne montre aucun processus.  
Cette épreuve reproduit les mêmes scénarios que les tests unitaires d’origine,
mais utilise le protocole de validation attendu par ``outillage/nexus_test.py`` :
chaque cas doit écrire sur STDOUT une ligne commençant exactement par
`[OK  ] ` (OK suivi de deux espaces) ou `[RATE] `, puis le nom du cas,
un deux‑points et un détail optionnel.  
Une épreuve muette (aucune ligne) est considérée comme un échec.

Le script charge dynamiquement le module à tester depuis le répertoire
``scripts`` (qui n’est pas un paquet) et exécute successivement tous les
cas : forward orphan, reverse parent présent plus ancien, PID réutilisé,
fuite autre nom, table sans clé ``debut``, code de sortie 1, code de sortie 0,
et structure JSON.  Le résultat global détermine le code de sortie du
processus (0 = succès, 1 = échec).

Utilisation :
    python epreuves/epreuve_orphelins.py
"""

import importlib.util
import pathlib
import sys
import io
import json
import contextlib

def check(nom, condition, detail=""):
    """Affiche le résultat d’un cas de test et renvoie le booléen.

    - ``nom`` : identifiant du cas.
    - ``condition`` : booléen indiquant le succès.
    - ``detail`` : texte libre affiché après le deux‑points.
    """
    if condition:
        print(f"[OK  ] {nom} : {detail}")
    else:
        print(f"[RATE] {nom} : {detail}")
    return condition

def _load_module():
    """Charge ``scripts/nexus_orphelins.py`` depuis la racine du dépôt."""
    base_dir = pathlib.Path(__file__).resolve().parents[1]   # repository root
    script_path = base_dir / "scripts" / "nexus_orphelins.py"
    spec = importlib.util.spec_from_file_location("nexus_orphelins", script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module

def main():
    ok = True
    module = _load_module()
    cible = "llama-server.exe"

    # 1. forward orphan
    table = [
        {"pid": 30000, "ppid": 99999, "nom": "llama-server.exe", "prive_octets": 0, "debut": 1000},
        {"pid": 1, "ppid": 0, "nom": "system.exe", "prive_octets": 0, "debut": 0},
    ]
    res = module.orphelins(table, cible)
    ok &= check(
        "forward_orphelin",
        len(res) == 1 and res[0].get("pid") == 30000,
        f"orphelins détectés : {len(res)}"
    )

    # 2. reverse parent présent plus ancien (pas orphelin)
    table = [
        {"pid": 20000, "ppid": 20001, "nom": "llama-server.exe", "prive_octets": 0, "debut": 2000},
        {"pid": 20001, "ppid": 0, "nom": "cmd.exe", "prive_octets": 0, "debut": 1000},
    ]
    res = module.orphelins(table, cible)
    ok &= check(
        "reverse_pas_orphelin",
        res == [],
        "aucun orphelin attendu"
    )

    # 3. PID réutilisé (parent présent mais démarré après l’enfant)
    table = [
        {"pid": 40000, "ppid": 50000, "nom": "llama-server.exe", "prive_octets": 0, "debut": 1500},
        {"pid": 50000, "ppid": 0, "nom": "someparent.exe", "prive_octets": 0, "debut": 2000},
    ]
    res = module.orphelins(table, cible)
    ok &= check(
        "pid_reutilise_orphelin",
        len(res) == 1 and res[0].get("pid") == 40000,
        f"orphelin pid={res[0].get('pid') if res else 'none'}"
    )

    # 4. fuite autre nom (processus d’un autre nom ne doit pas être retourné)
    table = [
        {"pid": 40000, "ppid": 50000, "nom": "other.exe", "prive_octets": 0, "debut": 0},
        {"pid": 50000, "ppid": 0, "nom": "system.exe", "prive_octets": 0, "debut": 0},
    ]
    res = module.orphelins(table, cible)
    ok &= check(
        "leak_ignores_other_names",
        res == [],
        "aucun orphelin pour autre nom"
    )

    # 5. table sans clé ``debut`` (cas absent)
    table_absent = [
        {"pid": 30000, "ppid": 99999, "nom": "llama-server.exe", "prive_octets": 0},
    ]
    res_absent = module.orphelins(table_absent, cible)
    ok &= check(
        "orphan_table_sans_debut_absent",
        len(res_absent) == 1 and res_absent[0].get("pid") == 30000,
        "orphelin détecté même sans ``debut``"
    )

    # 5b. table sans clé ``debut`` (cas présent)
    table_present = [
        {"pid": 30000, "ppid": 99999, "nom": "llama-server.exe", "prive_octets": 0},
        {"pid": 99999, "ppid": 0, "nom": "parent.exe", "prive_octets": 0, "debut": 0},
    ]
    res_present = module.orphelins(table_present, cible)
    ok &= check(
        "orphan_table_sans_debut_present",
        res_present == [],
        "pas d'orphelin quand le parent existe"
    )

    # 6. exit code 1 lorsqu’un orphelin est présent (intégration)
    table = [
        {"pid": 12345, "ppid": 99999, "nom": "llama-server.exe", "prive_octets": 0, "debut": 0},
    ]
    exit_code = module.main(table=table, argv=[])
    ok &= check(
        "exit_code_forward",
        exit_code == 1,
        f"code={exit_code}"
    )

    # 7. exit code 0 lorsqu’aucun orphelin n’est trouvé
    table = [
        {"pid": 11111, "ppid": 22222, "nom": "llama-server.exe", "prive_octets": 0, "debut": 0},
        {"pid": 22222, "ppid": 0, "nom": "cmd.exe", "prive_octets": 0, "debut": 0},
    ]
    exit_code = module.main(table=table, argv=[])
    ok &= check(
        "exit_code_none",
        exit_code == 0,
        f"code={exit_code}"
    )

    # 8. structure JSON avec l’option ``--json``
    table = [
        {"pid": 30000, "ppid": 99999, "nom": "llama-server.exe", "prive_octets": 12345, "debut": 0},
    ]
    captured = io.StringIO()
    with contextlib.redirect_stdout(captured):
        module.main(table=table, argv=["--json"])
    output = captured.getvalue()
    try:
        data = json.loads(output)
        json_ok = (
            isinstance(data, dict) and
            "orphelins" in data and
            "total_prive_octets" in data and
            "tues" in data and
            data.get("total_prive_octets") == 12345
        )
    except Exception:  # pragma: no cover
        json_ok = False
        data = {}
    ok &= check(
        "json_structure",
        json_ok,
        f"clés={list(data.keys())} total={data.get('total_prive_octets')}"
    )

    # Résultat final
    sys.exit(0 if ok else 1)

if __name__ == "__main__":
    main()
