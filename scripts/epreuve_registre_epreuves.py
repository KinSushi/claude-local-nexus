# -*- coding: utf-8 -*-
import json
import os
import sys

# un partage dont les nombres ne totalisent pas est pire qu'aucun partage

def find_repo_root(start_path):
    cur = os.path.abspath(start_path)
    while True:
        candidate = os.path.join(cur, ".nexus", "epreuves.json")
        if os.path.isfile(candidate):
            return cur, candidate
        parent = os.path.dirname(cur)
        if parent == cur:  # reached filesystem root
            return None, None
        cur = parent

def print_case(tag, name, detail):
    # tag is "[OK  ]" or "[RATE]"
    sys.stdout.write(f"{tag} {name} : {detail}\n")

def main():
    # 1. resolve repository root from __file__
    repo_root, json_path = find_repo_root(os.path.dirname(__file__))
    if json_path is None:
        # file absent
        print_case("[OK  ]", "registre", "aucun registre n'existe encore")
        sys.exit(0)

    # 2. file exists, try to read
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print_case("[RATE]", json_path, f"impossible de lire le fichier ({e})")
        sys.exit(2)

    # 3. verify structure
    modeles = data.get("modeles")
    if not isinstance(modeles, dict):
        print_case("[RATE]", json_path, "la clé 'modeles' est manquante ou invalide")
        sys.exit(3)

    incoherent = False
    total_models = len(modeles)
    promoted = 0
    confirmes = 0
    single_pass = 0
    unknown_stability = 0

    for alias, entry in modeles.items():
        # safety defaults
        complet = entry.get("complet")
        total = entry.get("total")
        historique = entry.get("historique", [])

        # count promoted entries (complet == True)
        if complet is True:
            promoted += 1
            if entry.get("stable") is True:
                confirmes += 1
            elif "mesures" not in entry:
                unknown_stability += 1
            else:
                single_pass += 1

        # skip checks if historique empty or total not int
        if not isinstance(historique, list) or not historique:
            continue
        last_val = historique[-1]

        # incoherence 1
        if complet is True and isinstance(total, int) and isinstance(last_val, int) and last_val < total:
            incoherent = True
            detail = f"complet={complet}, total={total}, historique={historique}"
            print_case("[RATE]", alias, detail)
            continue
        # incoherence 2
        if complet is False and isinstance(total, int) and isinstance(last_val, int) and last_val == total:
            incoherent = True
            detail = f"complet={complet}, total={total}, historique={historique}"
            print_case("[RATE]", alias, detail)

    # 5. always print summary
    summary_detail = (f"juges={total_models}, promus={promoted}, "
                     f"confirmes={confirmes}, passe_unique={single_pass}, "
                     f"stabilite_inconnue={unknown_stability}")
    print_case("[OK  ]", "partage mesure", summary_detail)

    sys.exit(1 if incoherent else 0)

if __name__ == "__main__":
    main()