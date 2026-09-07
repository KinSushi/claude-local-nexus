"""outillage/nexus_avant_apres.py

Outil de mesure et de comparaison d'executions.

Fonctions publiques :

- releve_commande(cmd) -> dict
  Execute la commande *cmd* (liste de chaines) et retourne un releve
  contenant le code de sortie, le nombre de lignes de la sortie standard,
  et une empreinte SHA256 du contenu.

- comparer_releves(avant, apres) -> str
  Compare deux releves (dict) et rend un verdict parmi :
  IDENTIQUE, AMELIORE, DEGRADE, INDECIS.

Utilisation en ligne de commande :

  --releve CMD...          execute CMD et ecrit le releve au format JSON.
  --avant FICHIER          fichier JSON du releve avant.
  --apres FICHIER          fichier JSON du releve apres.
  --epreuve                lance la contre-epreuve interne.
  --racine CHEMIN          racine utilisee pour les chemins relatifs.

Le programme ne modifie aucun fichier. Le code de sortie est :

  0  si le verdict est IDENTIQUE ou AMELIORE
  1  si le verdict est DEGRADE
  2  sinon (INDECIS ou erreur d'utilisation)
"""

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import contextlib

def _hash_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def releve_commande(cmd):
    """Execute la commande *cmd* et retourne un releve.

    Le releve est un dictionnaire avec les cles :
        code      : code de sortie (int)
        lignes    : nombre de lignes de la sortie (int)
        empreinte : SHA256 du contenu de la sortie (str)
    """
    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=False,
            timeout=30,
        )
        stdout = result.stdout or b""
        code = result.returncode
    except subprocess.TimeoutExpired:
        # Expiration => verdict INDECIS, on encode cela dans le releve
        return {"code": None, "lignes": None, "empreinte": None}
    except Exception:
        return {"code": None, "lignes": None, "empreinte": None}

    lignes = stdout.decode("utf-8", errors="replace").splitlines()
    return {
        "code": code,
        "lignes": len(lignes),
        "empreinte": _hash_bytes(stdout),
    }

def _charge_releve(chemin):
    try:
        with open(chemin, "r", encoding="utf-8", errors="replace") as f:
            data = json.load(f)
        # Normaliser les champs manquants
        for key in ("code", "lignes", "empreinte"):
            if key not in data:
                data[key] = None
        return data
    except Exception:
        return None

def comparer_releves(avant, apres):
    """Compare deux releves et rend un verdict.

    Retourne l'une des chaines : IDENTIQUE, AMELIORE, DEGRADE, INDECIS.
    """
    # Si l'un des releves est invalide ou incomplet, on ne peut pas trancher
    if not avant or not apres:
        return "INDECIS"

    # Tous les champs doivent etre presentes
    for key in ("code", "lignes", "empreinte"):
        if avant.get(key) is None or apres.get(key) is None:
            return "INDECIS"

    if avant == apres:
        return "IDENTIQUE"

    lignes_av = avant["lignes"]
    lignes_ap = apres["lignes"]
    code_av = avant["code"]
    code_ap = apres["code"]

    # Degradation si la substance s'effondre de plus de la moitie
    if lignes_av > 0 and lignes_ap < lignes_av / 2:
        return "DEGRADE"

    # Degradation si la sortie devient vide alors qu'avant elle contenait du texte
    if lignes_av > 0 and lignes_ap == 0:
        return "DEGRADE"

    # Amelioration si le code passe de non-nul a nul sans effondrement
    if code_av != 0 and code_ap == 0:
        return "AMELIORE"

    # Amelioration si la substance augmente
    if lignes_ap > lignes_av:
        return "AMELIORE"

    # Aucun critere ne s'applique => INDECIS
    return "INDECIS"

def _verdict_to_exit(verdict):
    if verdict in ("IDENTIQUE", "AMELIORE"):
        return 0
    if verdict == "DEGRADE":
        return 1
    return 2

def _executer_epreuve():
    """Lance la contre-epreuve interne.

    Retourne le code de sortie du processus.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        # Chemins des releves
        avant_path = os.path.join(tmpdir, "avant.json")
        apres_path = os.path.join(tmpdir, "apres.json")

        # 1. Cas AMELIORE : avant vide, apres non vide, code 0 dans les deux
        # Avant : commande qui ne produit rien
        releve_av = releve_commande([sys.executable, "-c", "import sys; sys.exit(0)"])
        with open(avant_path, "w", encoding="utf-8") as f:
            json.dump(releve_av, f)

        # Apres : commande qui ecrit du texte
        releve_ap = releve_commande(
            [sys.executable, "-c", "import sys; sys.stdout.write('ligne\\n'); sys.exit(0)"]
        )
        with open(apres_path, "w", encoding="utf-8") as f:
            json.dump(releve_ap, f)

        avant = _charge_releve(avant_path)
        apres = _charge_releve(apres_path)
        verdict1 = comparer_releves(avant, apres)

        # 2. Cas DEGRADE : avant texte, code 0 ; apres vide, code 1
        releve_av2 = releve_commande(
            [sys.executable, "-c", "import sys; sys.stdout.write('data\\n'); sys.exit(0)"]
        )
        with open(avant_path, "w", encoding="utf-8") as f:
            json.dump(releve_av2, f)

        releve_ap2 = releve_commande(
            [sys.executable, "-c", "import sys; sys.exit(1)"]
        )
        with open(apres_path, "w", encoding="utf-8") as f:
            json.dump(releve_ap2, f)

        avant2 = _charge_releve(avant_path)
        apres2 = _charge_releve(apres_path)
        verdict2 = comparer_releves(avant2, apres2)

        ok = (verdict1 == "AMELIORE") and (verdict2 == "DEGRADE")
        return 0 if ok else 1

def main():
    # Securite encodage sortie
    with contextlib.suppress(Exception):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(
        description="Mesure et comparaison d'executions."
    )
    parser.add_argument(
        "--releve",
        nargs=argparse.REMAINDER,
        help="Commande a executer et a relever.",
    )
    parser.add_argument(
        "--avant",
        help="Fichier JSON du releve avant.",
    )
    parser.add_argument(
        "--apres",
        help="Fichier JSON du releve apres.",
    )
    parser.add_argument(
        "--epreuve",
        action="store_true",
        help="Lance la contre-epreuve interne.",
    )
    parser.add_argument(
        "--racine",
        help="Chemin racine utilise pour les chemins relatifs.",
    )

    args = parser.parse_args()

    # Gestion prioritaire de l'epreuve
    if args.epreuve:
        code = _executer_epreuve()
        sys.exit(code)

    # Execution d'une commande et emission du releve
    if args.releve is not None and len(args.releve) > 0:
        releve = releve_commande(args.releve)
        json.dump(releve, sys.stdout, ensure_ascii=False)
        sys.stdout.write("\n")
        sys.exit(_verdict_to_exit("IDENTIQUE"))  # toujours 0 pour un releve

    # Comparaison de deux releves
    if args.avant and args.apres:
        avant = _charge_releve(args.avant)
        apres = _charge_releve(args.apres)
        verdict = comparer_releves(avant, apres)
        print(verdict)
        sys.exit(_verdict_to_exit(verdict))

    parser.error("one of the arguments --releve, --avant/--apres, or --epreuve is required")

if __name__ == "__main__":
    sys.exit(main())
