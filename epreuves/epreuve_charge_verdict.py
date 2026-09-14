import os
import sys

# Ajouter le repertoire scripts au path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))

import nexus_charge

def _run_case(disponible, seuil, attendu_etiquette):
    etiquette, message = nexus_charge.verdict_charge(disponible, seuil)
    ok = (etiquette == attendu_etiquette)
    if ok:
        print("[OK] %s -> %s" % (disponible, attendu_etiquette))
    else:
        print("[RATE] %s : attendu %s, obtenu %s (message: %s)" % (
            disponible, attendu_etiquette, etiquette, message))
    return ok

def main():
    tests = [
        (13.9, 16.0, "CHARGEE"),
        (20.0, 16.0, "LIBRE"),
        (16.0, 16.0, "LIBRE"),
        (0.0, 16.0, "CHARGEE"),
    ]
    results = [_run_case(d, s, e) for d, s, e in tests]
    _, message = nexus_charge.verdict_charge(13.9, 16.0)
    ok_message = "13.9" in message and "16.0" in message
    print("[OK] message porte valeur et seuil" if ok_message else "[RATE] message sans valeur ou seuil : %s" % message)
    results.append(ok_message)
    sys.exit(0 if all(results) else 1)

if __name__ == "__main__":
    main()
