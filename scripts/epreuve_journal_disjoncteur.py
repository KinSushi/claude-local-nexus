"""Contre-epreuve : le journal du POURQUOI porte-t-il les TROIS classes ?

Prescription du livre, verbatim (30 Agents Every AI Engineer Must Build,
chapitre 4) : "Log each retry attempt with context about why it failed so you
can identify patterns."

Ce que cette epreuve garde, et qui a ete trouve par la mesure et non par la
lecture : le chemin PERMANENT de record_failure sortait par un return AVANT
d atteindre le journal. Le journal existait, il fonctionnait, et il perdait
silencieusement la classe d echec la plus importante — celle qui ouvre le
circuit immediatement. Un journal partiel se lit exactement comme un journal
complet : seule une epreuve qui compte les trois classes les separe.

Sortie non nulle si une classe manque.
"""
import importlib.util
import json
import os
import sys
import tempfile

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CAS = [
    ("cible-transitoire", "HTTP 429 rate limit", "transitoire"),
    ("cible-permanente", "Invalid model name", "permanent"),
    ("cible-muette", "", "inconnue"),
]


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    chemin = os.path.join(RACINE, "scripts", "nexus_disjoncteur.py")
    spec = importlib.util.spec_from_file_location("_dj", chemin)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    journal = os.path.join(os.path.dirname(mod._state_path()), "circuit_journal.jsonl")
    avant = os.path.getsize(journal) if os.path.exists(journal) else 0

    breaker = mod.CircuitBreaker(3, 600)
    etat_initial = breaker.get_state()
    try:
        for cible, motif, _ in CAS:
            breaker.record_failure(cible, motif)
    finally:
        # ne jamais laisser l epreuve modifier l etat reel du disjoncteur
        breaker._state = etat_initial
        breaker._persist()

    if not os.path.exists(journal):
        print("[X] aucun journal ecrit : la prescription n est pas satisfaite")
        return 1

    with open(journal, "r", encoding="utf-8") as f:
        f.seek(avant)
        neuf = [json.loads(l) for l in f if l.strip()]

    par_cible = {e["cible"]: e for e in neuf}
    fautes = []
    for cible, motif, classe_attendue in CAS:
        entree = par_cible.get(cible)
        if entree is None:
            fautes.append(f"{cible} : AUCUNE ligne journalisee")
            continue
        if entree.get("classe") != classe_attendue:
            fautes.append(
                f"{cible} : classe '{entree.get('classe')}' au lieu de '{classe_attendue}'"
            )
        if not entree.get("motif"):
            fautes.append(f"{cible} : motif vide, le POURQUOI est perdu")
        for champ in ("le", "echecs", "etat"):
            if champ not in entree:
                fautes.append(f"{cible} : champ '{champ}' absent")

    for cible, _, _ in CAS:
        e = par_cible.get(cible)
        marque = "ok " if e else "MANQUE"
        detail = f"classe={e['classe']:11} etat={e['etat']}" if e else ""
        print(f"  [{marque}] {cible:20} {detail}")

    if fautes:
        print()
        for f_ in fautes:
            print(f"  [X] {f_}")
        print(f"\n[X] {len(fautes)} faute(s) : le journal ne porte pas les trois classes")
        return 1

    print(f"\n[OK] les {len(CAS)} classes sont journalisees avec leur POURQUOI")
    return 0


if __name__ == "__main__":
    sys.exit(main())
