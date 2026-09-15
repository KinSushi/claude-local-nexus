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

    with tempfile.TemporaryDirectory(dir=nexus_path.parent.parent) as tmp:
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

        # ---------- cas R ----------
        cibleR = base / "cibleR.txt"
        _ecrire(cibleR, "un\ndeux\ntrois\n")
        casR = base / "casR.jsonl"
        _jsonl(casR, "\n".join([A, "deux", P, "DEUX_NEUF", F]))
        rR = subprocess.run([sys.executable, str(nexus_path), str(casR), "t", str(cibleR)], capture_output=True, text=True)
        retireR = next((l for l in rR.stdout.splitlines() if l.startswith("RETIRE")), "aucune ligne RETIRE")
        ok = (rR.returncode == 0 and "DEUX_NEUF" in cibleR.read_text(encoding="utf-8") and retireR.startswith("RETIRE : le bloc 1 supprime 1 ligne(s)"))
        resultats.append(("[OK  ] casR : code=%d, %s" % (rR.returncode, retireR)) if ok else ("[RATE] casR : code=%d, %s" % (rR.returncode, retireR)))
        echec = echec or not ok

        # ---------- cas S ----------
        cibleS = base / "cibleS.txt"
        _ecrire(cibleS, "un\ndeux\ntrois\n")
        casS = base / "casS.jsonl"
        _jsonl(casS, "\n".join([A, "deux", P, "deux", "deux_bis", F]))
        rS = subprocess.run([sys.executable, str(nexus_path), str(casS), "t", str(cibleS)], capture_output=True, text=True)
        retireS = next((l for l in rS.stdout.splitlines() if l.startswith("RETIRE")), "aucune ligne RETIRE")
        ok = (rS.returncode == 0 and "deux_bis" in cibleS.read_text(encoding="utf-8") and not any(l.startswith("RETIRE") for l in rS.stdout.splitlines()))
        resultats.append(("[OK  ] casS : code=%d, aucune ligne RETIRE" % rS.returncode) if ok else ("[RATE] casS : code=%d, %s" % (rS.returncode, retireS)))
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

        # ---------- cas D ----------
        cibleD = base / "cibleD.txt"
        originalD = "\n".join(["alpha", "beta", "gamma", ""])
        _ecrire(cibleD, originalD)
        casD = base / "casD.jsonl"
        _jsonl(casD, "\n".join([A, "alpha", P, "ALPHA", F,
                                A, "beta", P, "BETA"]))  # missing FIN
        rc = subprocess.run([sys.executable, str(nexus_path), str(casD), "t", str(cibleD)],
                            capture_output=True, text=True).returncode
        contenu = cibleD.read_text(encoding="utf-8")
        ok = (rc != 0 and contenu == originalD)
        resultats.append(("[OK  ] casD : code=%d, texte tronque -> refus, fichier intact" % rc) if ok else
                         ("[RATE] casD : code=%d, verification echec" % rc))
        echec = echec or not ok

        # ---------- cas E ----------
        # ---------- cas F (reverse) ----------
        cibleF = base / "cibleF.py"
        originalF = "\n".join(["def call(path):", "    url = BASE_URL + path", "    return url", ""])
        _ecrire(cibleF, originalF)
        casF = base / "casF.jsonl"
        _jsonl(casF, "\n".join([A, "url = BASE_URL + path", P, "url = BASE_URL + chemin", F]))
        rc = subprocess.run([sys.executable, str(nexus_path), str(casF), "t", str(cibleF)],
                            capture_output=True, text=True)
        contenu = cibleF.read_text(encoding="utf-8")
        ok = (rc.returncode != 0 and contenu == originalF and
              "debut de ligne" in rc.stdout + rc.stderr and
              "la ligne reelle est" in rc.stdout + rc.stderr)
        resultats.append(("[OK  ] casF (reverse) : refus attendu, code=%d" % rc.returncode) if ok else
                         ("[RATE] casF (reverse) : code=%d, verification echec" % rc.returncode))
        echec = echec or not ok

        # ---------- cas G (forward) ----------
        cibleG = base / "cibleG.py"
        originalG = "\n".join(["def call(path):", "    url = BASE_URL + path", "    return url", ""])
        _ecrire(cibleG, originalG)
        casG = base / "casG.jsonl"
        _jsonl(casG, "\n".join([A, "    url = BASE_URL + path", P, "    url = BASE_URL + '/' + path", F]))
        rc = subprocess.run([sys.executable, str(nexus_path), str(casG), "t", str(cibleG)],
                            capture_output=True, text=True).returncode
        contenu = cibleG.read_text(encoding="utf-8")
        ok = (rc == 0 and "url = BASE_URL + '/' + path" in contenu)
        resultats.append(("[OK  ] casG (forward) : code=%d, remplacement applique" % rc) if ok else
                         ("[RATE] casG (forward) : code=%d, verification echec" % rc))
        echec = echec or not ok

        # ---------- cas H (fuite) ----------
        cibleH = base / "cibleH.py"
        originalH = "\n".join(["def call(path):", "    url = BASE_URL + path", "    return url", ""])
        _ecrire(cibleH, originalH)
        casH = base / "casH.jsonl"
        _jsonl(casH, "\n".join([A, "BASE_URL", P, "BASE_URL_REPLACED", F]))
        rc = subprocess.run([sys.executable, str(nexus_path), str(casH), "t", str(cibleH)],
                            capture_output=True, text=True).returncode
        contenu = cibleH.read_text(encoding="utf-8")
        ok = (rc != 0 and contenu == originalH)
        resultats.append(("[OK  ] casH (fuite) : refus attendu, code=%d" % rc) if ok else
                         ("[RATE] casH (fuite) : code=%d, verification echec" % rc))
        echec = echec or not ok
        cibleE = base / "cibleE.txt"
        originalE = "\n".join(["alpha", "beta", "gamma", ""])
        _ecrire(cibleE, originalE)
        casE = base / "casE.jsonl"
        _jsonl(casE, "\n".join([A, "alpha", P, "ALPHA", F,
                                A, "beta", P, "BETA", F]))
        rc = subprocess.run([sys.executable, str(nexus_path), str(casE), "t", str(cibleE)],
                            capture_output=True, text=True).returncode
        contenu = cibleE.read_text(encoding="utf-8")
        ok = (rc == 0 and "ALPHA" in contenu and "BETA" in contenu)
        resultats.append(("[OK  ] casE : code=%d, deux remplacements appliques" % rc) if ok else
                         ("[RATE] casE : code=%d, verification echec" % rc))
        echec = echec or not ok

    for ligne in resultats:
        print(ligne)

    return 1 if echec else 0

if __name__ == "__main__":
    sys.exit(main())
