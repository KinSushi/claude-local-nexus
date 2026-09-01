import io
import json
import pathlib
import subprocess
import sys
import tempfile

def _ecrire(chemin, contenu):
    with io.open(chemin, "w", encoding="utf-8", newline="\n") as f:
        f.write(contenu)
    return chemin

def _jsonl(chemin, texte):
    return _ecrire(chemin, json.dumps({"nom": "t", "texte": texte}) + "\n")

def _trouver_nexus():
    p = pathlib.Path(__file__).resolve()
    while p.parent != p:
        cand = p.parent / "scripts" / "nexus_appliquer.py"
        if cand.is_file():
            return cand
        p = p.parent
    raise FileNotFoundError("nexus_appliquer.py introuvable")

def main():
    # localisation du script a tester
    try:
        nexus_path = _trouver_nexus()
    except FileNotFoundError as e:
        print("[RATE] localisation :", e)
        return 1

    A, P, F = "<<<AVANT>>>", "<<<APRES>>>", "<<<FIN>>>"
    resultats = []
    echec = False

    with tempfile.TemporaryDirectory() as tmp:
        base = pathlib.Path(tmp)

        # ---------- cas A ----------
        cibleA = base / "cibleA.txt"
        _ecrire(cibleA, "\n".join(["alpha", "beta", "gamma", ""]))
        casA = base / "casA.jsonl"
        _jsonl(casA, "\n".join([A, "alpha", P, "ALPHA", F,
                                A, "gamma", P, "GAMMA", F]))
        rc = subprocess.run([sys.executable, str(nexus_path), str(casA), "t", str(cibleA)],
                            capture_output=True, text=True).returncode
        contenu = cibleA.read_text(encoding="utf-8")
        ok = (rc == 0 and "ALPHA" in contenu and "GAMMA" in contenu)
        resultats.append(("[OK  ] casA : code=%d, ALPHA/GAMMA presentes" % rc) if ok else
                         ("[RATE] casA : code=%d, verification echec" % rc))
        echec = echec or not ok

        # ---------- cas B ----------
        cibleB = base / "cibleB.txt"
        originalB = "\n".join(["alpha", "beta", "gamma", ""])
        _ecrire(cibleB, originalB)
        casB = base / "casB.jsonl"
        _jsonl(casB, "\n".join([A, "alpha", P, "ALPHA", F,
                                A, "absent-du-fichier", P, "X", F]))
        rc = subprocess.run([sys.executable, str(nexus_path), str(casB), "t", str(cibleB)],
                            capture_output=True, text=True).returncode
        contenu = cibleB.read_text(encoding="utf-8")
        ok = (rc == 1 and contenu == originalB)
        resultats.append(("[OK  ] casB : code=%d, fichier intact" % rc) if ok else
                         ("[RATE] casB : code=%d, verification echec" % rc))
        echec = echec or not ok

        # ---------- cas C ----------
        cibleC = base / "cibleC.txt"
        ligne = 'avant = texte.split("' + A + '", 1)[1].split("' + P + '", 1)[0]'
        _ecrire(cibleC, "\n".join(["debut", ligne, "fin", ""]))
        casC = base / "casC.jsonl"
        _jsonl(casC, "\n".join([A, ligne, P, "REMPLACE", F]))
        rc = subprocess.run([sys.executable, str(nexus_path), str(casC), "t", str(cibleC)],
                            capture_output=True, text=True).returncode
        contenu = cibleC.read_text(encoding="utf-8")
        attendu = "\n".join(["debut", "REMPLACE", "fin", ""])
        ok = (rc == 0 and contenu == attendu)
        resultats.append(("[OK  ] casC : code=%d, remplacement correct" % rc) if ok else
                         ("[RATE] casC : code=%d, verification echec" % rc))
        echec = echec or not ok

    for ligne in resultats:
        print(ligne)

    return 1 if echec else 0

if __name__ == "__main__":
    sys.exit(main())