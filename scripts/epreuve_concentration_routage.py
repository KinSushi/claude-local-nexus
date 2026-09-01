import sys
import os
from pathlib import Path
import re

def racine_depot():
    cur = Path(__file__).resolve()
    while cur.parent != cur:
        if (cur / "scripts").is_dir():
            return str(cur)
        cur = cur.parent
    return ""

def plan_de(alias):
    if alias.endswith("-local"):
        return "local"
    if alias.endswith("-cloud"):
        return "cloud"
    return "inconnu"

def extraire_defaut_mcp(texte):
    for line in texte.splitlines():
        if "DEFAULT_CHAT_MODEL" in line:
            # look for || "alias"
            m = re.search(r'\|\|\s*"([^"]+)"', line)
            if m:
                return m.group(1)
    return None

def extraire_tete_replis(texte):
    for line in texte.splitlines():
        if line.lstrip().startswith("REPLIS_GRATUITS"):
            # find first double-quoted string
            m = re.search(r'\[\s*"([^"]+)"', line)
            if m:
                return m.group(1)
    return None

def _print_result(ok, nom, detail):
    prefix = "[OK  ]" if ok else "[RATE]"
    print(f"{prefix} {nom} : {detail}")

def main():
    all_ok = True

    # Bloc 1 - tests sur chaines en dur
    # plan_de tests
    cases_plan = [
        ("foo-local", "local"),
        ("bar-cloud", "cloud"),
        ("baz", "inconnu")
    ]
    for alias, attendu in cases_plan:
        resultat = plan_de(alias)
        ok = resultat == attendu
        _print_result(ok, "plan_de rend " + attendu, f"{alias} => {resultat}")
        all_ok = all_ok and ok

    # extraire_defaut_mcp ok
    texte_defaut = 'const DEFAULT_CHAT_MODEL = process.env.NEXUS_CHAT_MODEL || "glm-4.7-flash-local";'
    attendu_defaut = "glm-4.7-flash-local"
    resultat_defaut = extraire_defaut_mcp(texte_defaut)
    ok = resultat_defaut == attendu_defaut
    _print_result(ok, "extraire_defaut_mcp rend alias", f"found {resultat_defaut}")
    all_ok = all_ok and ok

    # extraire_defaut_mcp vide
    resultat_defaut_vide = extraire_defaut_mcp("")
    ok = resultat_defaut_vide is None
    _print_result(ok, "extraire_defaut_mcp vide rend None", "None")
    all_ok = all_ok and ok

    # extraire_tete_replis ok
    texte_replis = 'REPLIS_GRATUITS = ["gpt-oss-120b-cloud", "glm-4.7-flash-local"]'
    attendu_replis = "gpt-oss-120b-cloud"
    resultat_replis = extraire_tete_replis(texte_replis)
    ok = resultat_replis == attendu_replis
    _print_result(ok, "extraire_tete_replis rend premier alias", f"found {resultat_replis}")
    all_ok = all_ok and ok

    # extraire_tete_replis absent
    resultat_replis_absent = extraire_tete_replis("some other line")
    ok = resultat_replis_absent is None
    _print_result(ok, "extraire_tete_replis absent rend None", "None")
    all_ok = all_ok and ok

    # Bloc 2 - fichiers reels
    root = Path(racine_depot())
    files = [
        ("tools/nexus-mcp/server.js", extraire_defaut_mcp, "extraction server.js"),
        ("scripts/nexus_agent.py", extraire_tete_replis, "extraction nexus_agent.py")
    ]
    alias_vals = {}
    for rel_path, func, case_name in files:
        path = root / rel_path
        try:
            with path.open(encoding="utf-8") as f:
                contenu = f.read()
        except Exception as e:
            _print_result(False, case_name, f"impossible de lire le fichier ({e})")
            all_ok = False
            continue

        alias = func(contenu)
        if alias is None:
            _print_result(False, case_name, "extraction None")
            all_ok = False
        else:
            _print_result(True, case_name, f"alias {alias}")
            alias_vals[rel_path] = alias

    # comparaison des plans si les deux alias sont disponibles
    if len(alias_vals) == 2:
        alias1, alias2 = alias_vals.values()
        plan1 = plan_de(alias1)
        plan2 = plan_de(alias2)
        if plan1 == plan2:
            _print_result(True, "plans egaux", f"{alias1} & {alias2} => {plan1}")
        else:
            _print_result(False, "plans differents", f"{alias1} ({plan1}) vs {alias2} ({plan2})")
            all_ok = False
    else:
        # si l'un manque, on ne peut pas comparer
        _print_result(False, "plans comparaison", "un ou deux alias manquants")
        all_ok = False

    return 0 if all_ok else 1

if __name__ == '__main__':
    sys.exit(main())
