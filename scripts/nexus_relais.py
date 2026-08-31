#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Orchestrateur de relais pour le dépôt Nexus.

Ce script boucle sur les cibles (scripts python) afin d’auditer,
corriger, valider et journaliser chaque modification. Il gère la
dégradation progressive des plans (cloud → local) et évite toute
utilisation d’un alias « claude-* ».
"""

import argparse
import datetime
import json
import os
import pathlib
import subprocess
import sys
import tempfile

# ------------------------------------------------------------
# Configuration globale
# ------------------------------------------------------------
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
BASE_DIR = pathlib.Path(__file__).resolve().parent
# Le répertoire .nexus doit être à la racine du dépôt, c’est‑à‑dire le
# répertoire parent de celui contenant les scripts.  Sinon le journal
# était créé dans scripts/.nexus/, hors de portée du .gitignore et
# différent du chemin attendu par les autres outils du dépôt.
REPO_ROOT = BASE_DIR.parent
NEXUS_DIR = REPO_ROOT / ".nexus"
JOURNAL_PATH = NEXUS_DIR / "relais-journal.json"
RELAIS_FILE = NEXUS_DIR / "relais-file.txt"
BRIEF_DIR = NEXUS_DIR / "briefs"
BRIEF_DIR.mkdir(parents=True, exist_ok=True)

# ------------------------------------------------------------
# Utilitaires
# ------------------------------------------------------------
def charger_journal():
    """Charge le journal s’il existe, sinon retourne un dict vide."""
    if JOURNAL_PATH.is_file():
        with JOURNAL_PATH.open(encoding="utf-8") as f:
            return json.load(f)
    return {}

def sauver_journal(journal):
    """Écrit le journal de façon atomique."""
    tmp_fd, tmp_path = tempfile.mkstemp(dir=JOURNAL_PATH.parent, text=True)
    with os.fdopen(tmp_fd, "w", encoding="utf-8") as tmp_file:
        json.dump(journal, tmp_file, ensure_ascii=False, indent=2)
    os.replace(tmp_path, JOURNAL_PATH)

def lister_cibles(depuis_fichier=None):
    """Renvoie la liste ordonnée des chemins cibles à traiter."""
    # Si un fichier de liste est fourni (option --file), on le lit tel quel.
    if depuis_fichier:
        with open(depuis_fichier, encoding="utf-8") as f:
            cibles = [pathlib.Path(l.strip()) for l in f if l.strip()]
        return cibles

    # Sinon, si le fichier de relais existe déjà, on le réutilise.
    if RELAIS_FILE.is_file():
        with RELAIS_FILE.open(encoding="utf-8") as f:
            cibles = [pathlib.Path(l.strip()) for l in f if l.strip()]
        return cibles

    # Recherche des scripts dans le répertoire de base.
    # Pourquoi *.py et non scripts/*.py ?
    # BASE_DIR pointe déjà vers le répertoire contenant les scripts.
    # Utiliser "scripts/*.py" créerait un chemin double (scripts/scripts/)
    # qui n'existe pas, entraînant l'absence de cibles détectées.
    tous = list(BASE_DIR.glob("*.py"))

    # Exclure le script du relais lui‑même (nexus_relais.py)
    tous = [p for p in tous if p.name != "nexus_relais.py"]

    # Exclure les cibles déjà marquées "ok" dans le journal.
    journal = charger_journal()
    deja = {entry["cible"] for entry in journal.values()}
    cibles = [p for p in tous if str(p) not in deja]

    # Tri des plus gros aux plus petits (taille du fichier en octets).
    cibles.sort(key=lambda p: p.stat().st_size, reverse=True)

    return cibles

def ecrire_brief(cible, audit_texte):
    """Crée un fichier de brief contenant les résultats d’audit."""
    brief_path = BRIEF_DIR / f"brief_{cible.name}.txt"
    contraintes = (
        "Respecter les conventions du dépôt, éviter les écritures non atomiques, "
        "ne pas utiliser d’alias claude-*, etc."
    )
    contenu = f"{audit_texte}\n\n--- Contraintes ---\n{contraintes}\n"
    brief_path.write_text(contenu, encoding="utf-8")
    return brief_path

def supprimer_brief(brief_path):
    """Supprime le fichier de brief même en cas d’échec."""
    try:
        brief_path.unlink()
    except Exception:
        pass

def executer_audit(cible, plan):
    """Appelle nexus_agent.executer avec la consigne d’audit."""
    # insertion du répertoire du script dans le path
    sys.path.insert(0, str(BASE_DIR))
    import nexus_agent as agent  # noqa: E402

    cle = agent.cle_maitre()
    consigne = (
        "Auditer le fichier pour détecter les défauts suivants : "
        "garde asymétrique, mesure confondue avec zéro ou succès, "
        "code de sortie mensonger, écriture non atomique, sous‑processus "
        "sans encodage explicite. Retourner les lignes concernées VERBATIM."
    )
    payload = {
        "nom": "audit",
        "modele": plan,
        "tache": consigne,
        "fichiers": [str(cible)],
        "max_tokens": 3000,
    }
    return agent.executer(payload, cle)

def corriger_cible(cible, brief_path):
    """Lance le correcteur adapté selon la taille du fichier."""
    lignes = cible.read_text(encoding="utf-8").count("\n") + 1
    if lignes < 600:
        cmd = [
            sys.executable,
            str(BASE_DIR / "nexus_patch.py"),
            "--cible", str(cible),
            "--consigne", str(brief_path),
        ]
    else:
        cmd = [
            sys.executable,
            str(BASE_DIR / "nexus_fonctions.py"),
            "--cible", str(cible),
            "--blocs", str(brief_path),
        ]
    result = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        print(f"Correction failed for {cible}: {result.stdout}")
        return False
    return True

def valider_cible():
    """Exécute nexus_valide.py sans argument."""
    cmd = [sys.executable, str(BASE_DIR / "nexus_valide.py")]
    result = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        print(f"Validation failed: {result.stdout}")
        return False
    return True

def restaurer_cible(cible):
    """Restaure la cible depuis le dépôt git."""
    cmd = ["git", "checkout", "--", str(cible)]
    result = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        print(f"Restoration failed for {cible}: {result.stdout}")

def mettre_a_jour_journal(journal, cible, verdict, resultat_audit, plan_actuel):
    """Enregistre une entrée de journal pour la cible."""
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    entry = {
        "cible": str(cible),
        "verdict": verdict,
        "modele": resultat_audit.get("modele", ""),
        "plan": plan_actuel,
        "tokens": resultat_audit.get("tokens", 0),
        "duree": resultat_audit.get("duree", 0),
        "horodatage": now,
    }
    journal[str(cible)] = entry
    sauver_journal(journal)

def choisir_plan(plan_initial, cloud_echoue, compteur_cloud):
    """Détermine le plan à employer pour la prochaine cible."""
    if plan_initial == "cloud":
        if cloud_echoue or compteur_cloud >= 3:
            return "local"
        return "cloud"
    return plan_initial  # "local" ou "auto" déjà résolu

# ------------------------------------------------------------
# Fonction principale
# ------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Relais d'amélioration du dépôt Nexus."
    )
    parser.add_argument("--max-cibles", type=int, default=5)
    parser.add_argument(
        "--plans",
        choices=["cloud", "local", "auto"],
        default="auto",
        help="Plan de modele a employer.",
    )
    parser.add_argument("--simuler", action="store_true")
    parser.add_argument("--file", type=pathlib.Path, help="Fichier listant les cibles.")
    args = parser.parse_args()

    # Determination du plan de base
    plan_courant = "cloud" if args.plans in ("cloud", "auto") else "local"
    cloud_echoue = False
    echec_cloud_consecutif = 0

    cibles = lister_cibles(depuis_fichier=args.file)
    if not cibles:
        print("No targets to process.")
        return 2

    journal = charger_journal()
    reussites = 0
    echecs = 0
    traitees = 0
    total_jetons = 0          # total des tokens consommés
    cibles_echouees = []

    total_cibles = len(cibles)

    for idx, cible in enumerate(cibles, start=1):
        if traitees >= args.max_cibles:
            break
        if str(cible) in journal:
            # cible deja traitee, on la saute
            continue

        # ------------------------------------------------------------
        # 1. Affichage avant le traitement de la cible
        # ------------------------------------------------------------
        print(f"[{idx}/{total_cibles}] Debut traitement de {cible}")

        # 2. AUDIT
        resultat = executer_audit(cible, plan_courant)
        if resultat.get("erreur"):
            # Detection d'epuisement du cloud
            err = resultat["erreur"]
            if any(code in err for code in ("402", "429")) or not resultat.get("texte"):
                echec_cloud_consecutif += 1
                if echec_cloud_consecutif >= 3:
                    cloud_echoue = True
                    # Basculement imminent du cloud vers le local
                    print("Basculement du plan: cloud -> local (3 echecs consecutifs ou code 402/429)")
                    plan_courant = "local"
            else:
                echec_cloud_consecutif = 0
        else:
            echec_cloud_consecutif = 0

        # 3. BRIEF
        brief_path = ecrire_brief(cible, resultat.get("texte", ""))

        # 4. CORRECTION
        if not args.simuler:
            ok_corr = corriger_cible(cible, brief_path)
        else:
            ok_corr = True
        supprimer_brief(brief_path)

        # 5. VALIDATION
        if ok_corr and not args.simuler:
            ok_val = valider_cible()
        else:
            ok_val = ok_corr

        # 6. GESTION DES RESULTATS
        if ok_val:
            verdict = "reussi"
            reussites += 1
        else:
            verdict = "echec"
            echec_cloud_consecutif = 0  # reset pour le local
            restaurer_cible(cible)
            echecs += 1
            cibles_echouees.append(str(cible))

        # 7. Mise a jour du journal et sauvegarde immediate
        mettre_a_jour_journal(journal, cible, verdict, resultat, plan_courant)
        sauver_journal(journal)   # ecriture atomique apres chaque mise a jour
        traitees += 1

        # 8. Accumulation des jetons (si disponible) - on utilise la clef correcte "tokens"
        total_jetons += resultat.get("tokens", 0)

        # 9. Affichage apres le traitement de la cible
        duree = resultat.get("duree", "N/A")
        # on lit la valeur "tokens" mais on l'affiche sous le libelle "jetons" pour garder la sortie attendue
        jetons = resultat.get("tokens", "N/A")
        print(
            f"Fin traitement de {cible}: verdict={verdict}, plan={plan_courant}, "
            f"jetons={jetons}, duree={duree}"
        )

        # 10. Basculement eventuel (deja realise ci-dessus)
        if plan_courant == "cloud" and cloud_echoue:
            plan_courant = "local"
            print("Basculement du plan: cloud -> local (condition detectee)")

    # ------------------------------------------------------------
    # Bilan final
    # ------------------------------------------------------------
    print("=== BILAN FINAL ===")
    print(f"Cibles traitees      : {traitees}")
    print(f"  - reussies        : {reussites}")
    print(f"  - echecs          : {echecs}")
    # Le nombre de cibles sautees ne peut etre calcule sans modifier lister_cibles.
    # On prefere ne pas l'afficher que de fournir une valeur fausse.
    print(f"Jetons gratuits consommes : {total_jetons}")
    if cibles_echouees:
        print("Cibles en echec :")
        for ce in cibles_echouees:
            print(f"  - {ce}")

    # Codes de sortie
    if reussites > 0 and echecs == 0:
        return 0
    if echecs > 0:
        return 1
    return 2

if __name__ == "__main__":
    sys.exit(main())
