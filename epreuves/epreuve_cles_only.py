"""Contre-epreuve : toute cle testee par --only est-elle ATTEIGNABLE ?

Defaut mesure le 2026-09-02 : nexus_test.py testait 66 cles sous la forme
`args.only in (None, "<cle>")` et n en declarait que 56 dans `choices`. DIX
cles etaient donc inatteignables — argparse refusait la valeur que le code
traitait. Parmi elles, `vide`, qui commande l epreuve du RENDU VIDE : celle-la
meme qui existe pour attraper les rendus vides ne pouvait pas etre jouee seule.

Le remede n est pas d avoir complete la liste — elle se serait
redesynchronisee au prochain ajout — mais de la DERIVER du source. Cette
epreuve garde contre le retour d une liste gravee.

Sortie non nulle si une cle testee n est pas acceptee par --only.
"""
import re
import subprocess
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
CIBLE = RACINE / "scripts" / "nexus_test.py"
MOTIF = r'args\.only\s+in\s+\(None,\s*"([^"]+)"\)'


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if not CIBLE.is_file():
        print("[RATE] cles --only : nexus_test.py introuvable")
        return 1

    source = CIBLE.read_text(encoding="utf-8")
    testees = sorted(set(re.findall(MOTIF, source)))
    if not testees:
        # Un motif casse rendrait ZERO et se lirait comme une reussite :
        # sans cles trouvees, cette epreuve ne prouve rien.
        print("[RATE] cles --only : aucune cle trouvee, le motif est casse")
        return 1

    # Temoin POSITIF : argparse doit refuser une valeur qui n existe pas.
    # Sans lui, un --only qui accepte TOUT passerait pour un succes.
    bidon = subprocess.run(
        [sys.executable, str(CIBLE), "--only", "cle-qui-n-existe-pas-xyz"],
        cwd=RACINE, capture_output=True, text=True, encoding="utf-8",
        errors="replace", timeout=60)
    if "invalid choice" not in (bidon.stderr or ""):
        print("[RATE] temoin positif : --only accepte une cle inventee, "
              "l epreuve ne discriminerait rien")
        return 1
    print("[OK  ] temoin positif : une cle inventee est bien refusee")

    aide = subprocess.run(
        [sys.executable, str(CIBLE), "--help"],
        cwd=RACINE, capture_output=True, text=True, encoding="utf-8",
        errors="replace", timeout=60)
    texte = (aide.stdout or "") + (aide.stderr or "")

    # On lit le bloc entre accolades après --only car argparse n'entoure pas les clés de guillemets
    m = re.search(r'--only\s*\{([^}]*)\}', texte)
    if m:
        cles = {k.strip() for k in m.group(1).split(',') if k.strip()}
    else:
        cles = set()
    manquantes = [c for c in testees if c not in cles]
    if manquantes:
        for c in manquantes:
            print(f"[RATE] cle inatteignable : {c}")
        print(f"\n[X] {len(manquantes)} cle(s) testee(s) que --only refuse, "
              f"sur {len(testees)}")
        return 1

    print(f"[OK  ] cles --only : les {len(testees)} cles testees sont atteignables")
    return 0


if __name__ == "__main__":
    sys.exit(main())
