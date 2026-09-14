import os
import sys

# Le dossier outillage est mis en tete du chemin d'import
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'outillage'))
import nexus_traque

def run_test(verdict, sans_relance):
    action = nexus_traque.decision_veille(verdict, sans_relance)
    expected = {
        ("BLOQUE", False): "relancer",
        ("BLOQUE", True): "signaler",
        ("SAIN", False): "rien",
        ("SUSPECT", False): "rien",
    }[(verdict, sans_relance)]

    ok = action == expected
    print(f"[{'OK' if ok else 'RATE'}] {verdict}/{sans_relance} -> {action}")
    return ok

def main():
    tests = [
        ("BLOQUE", False),
        ("BLOQUE", True),
        ("SAIN", False),
        ("SUSPECT", False),
    ]
    resultats = [run_test(v, sr) for v, sr in tests]
    sys.exit(0 if all(resultats) else 1)

if __name__ == "__main__":
    main()
