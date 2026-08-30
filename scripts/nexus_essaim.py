#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
nexus_essaim.py

DISPATCHEUR qui enchaine le cycle complet d'amélioration sur plusieurs
cibles en parallèle, sans passer par un orchestrateur externe.

Le script :

1. lance un audit via ``nexus_agent.executer`` ;
2. s'arrête si aucune trouvaille ;
3. écrit les résultats de l'audit dans un fichier temporaire
   ``.nexus/essaim-<cible>.md`` ;
4. lance ``nexus_patch.py`` en sous‑processus avec ce fichier comme consigne ;
5. vérifie la syntaxe du fichier corrigé ;
6. restaure la version d'origine en cas d'échec ;
7. produit un rapport d'une ligne par cible, incluant le PLAN réellement employé.

Toutes les fonctions sont documentées en français avec les accents.
Les messages affichés sur la console sont sans accents (compatibilité Windows).
"""

import argparse
import ast
import hashlib
import json
import os
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, List, Tuple, Any

# --------------------------------------------------------------------------- #
# Pré‑chargement du module nexus_agent (une seule fois, avant le multithreading)
# --------------------------------------------------------------------------- #

# Ajout du répertoire du dépôt au PYTHONPATH avant l'import du module.
# Cette opération est effectuée au moment du chargement du script,
# donc elle n'est plus exécutée simultanément par plusieurs threads.
sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    import nexus_agent as agent  # type: ignore
except ImportError as e:
    print(f"Import error: {e}")
    sys.exit(1)

# --------------------------------------------------------------------------- #
# Helpers généraux
# --------------------------------------------------------------------------- #

def racine_depot() -> Path:
    """Retourne le répertoire racine du dépôt (le répertoire contenant ce script)."""
    return Path(__file__).resolve().parent

def dossier_nexus() -> Path:
    """Assure l'existence du répertoire ``.nexus`` à la racine du dépôt."""
    d = racine_depot() / ".nexus"
    d.mkdir(parents=True, exist_ok=True)
    return d

def charger_fichier(path: Path) -> str:
    """Lit le contenu texte d'un fichier en UTF‑8, remplace les erreurs."""
    return path.read_text(encoding="utf-8", errors="replace")

def ecrire_fichier(path: Path, contenu: str) -> None:
    """Écrit le texte fourni dans le fichier indiqué, UTF‑8, remplace les erreurs."""
    path.write_text(contenu, encoding="utf-8", errors="replace")

def _hash_path(cible: Path) -> str:
    """Retourne un identifiant court basé sur le chemin complet de la cible."""
    h = hashlib.sha256(str(cible).encode("utf-8")).hexdigest()
    return h[:8]

# --------------------------------------------------------------------------- #
# Interaction avec nexus_agent
# --------------------------------------------------------------------------- #

def executer_audit(cible: Path, consigne: str, modele: str) -> Dict:
    """
    Lance l'audit sur la cible en appelant ``nexus_agent.executer``.
    Retourne le dictionnaire brut renvoyé par l'agent.
    """
    cle = agent.cle_maitre()
    payload = {
        "nom": f"audit-{cible.name}",
        "modele": modele,
        "tache": consigne,
        "fichiers": [str(cible)],
        "max_tokens": 4096,
    }
    resultat = agent.executer(payload, cle)
    return resultat if isinstance(resultat, dict) else {}

# --------------------------------------------------------------------------- #
# Vérification syntaxique
# --------------------------------------------------------------------------- #

def verifier_syntaxe(cible: Path) -> bool:
    """
    Vérifie que le fichier corrigé possède une syntaxe valide.
    - .py : ast.parse
    - .js : ``node --check``
    - .ps1 : ``pwsh -Command "[System.Management.Automation.Language.Parser]::ParseFile(...)"``
    Retourne True si la syntaxe est correcte, False sinon.
    """
    suffix = cible.suffix.lower()
    try:
        if suffix == ".py":
            ast.parse(cible.read_text(encoding="utf-8", errors="replace"))
            return True
        elif suffix == ".js":
            cmd = ["node", "--check", str(cible)]
            res = subprocess.run(
                cmd,
                capture_output=True,
                encoding="utf-8",
                errors="replace",
                timeout=30,
            )
            return res.returncode == 0
        elif suffix == ".ps1":
            # Utilisation du parser PowerShell pour une vraie vérification.
            chemin = str(cible).replace("'", "''")
            ps_cmd = (
                "[System.Management.Automation.Language.Parser]::ParseFile("
                f"'{chemin}', [ref]$null, [ref]$null) | Out-Null"
            )
            cmd = [
                "pwsh",
                "-NoLogo",
                "-NoProfile",
                "-Command",
                ps_cmd,
            ]
            res = subprocess.run(
                cmd,
                capture_output=True,
                encoding="utf-8",
                errors="replace",
                timeout=30,
            )
            return res.returncode == 0
        else:
            # Type inconnu : on considère que la vérification échoue.
            return False
    except Exception as e:
        print(f"Syntax check error for {cible.name}: {e}")
        return False

# --------------------------------------------------------------------------- #
# Gestion du cycle complet pour une cible
# --------------------------------------------------------------------------- #

def creer_consigne_temp(cible: Path, audit_texte: str) -> Path:
    """
    Crée le fichier temporaire ``.nexus/essaim-<cible>.md`` contenant :

    - une phrase d'introduction,
    - le texte brut de l'audit,
    - les contraintes de style du dépôt.
    Retourne le chemin du fichier créé.
    """
    dossier = dossier_nexus()
    ident = _hash_path(cible)
    temp_path = dossier / f"essaim-{cible.name}-{ident}.md"

    intro = f"Ces trouvailles servent à corriger la cible {cible.name}.\n\n"
    contraintes = (
        "Contraintes de style du dépôt :\n"
        "- Les commentaires et docstrings doivent être en français avec accents, "
        "expliquant le POURQUOI et le dommage évité.\n"
        "- Les messages imprimés sur la console ne doivent pas contenir d'accents.\n"
        "- Utiliser le plus petit changement possible, ne rien changer d'autre.\n"
    )
    contenu = intro + audit_texte + "\n\n" + contraintes
    ecrire_fichier(temp_path, contenu)
    return temp_path

def restaurer_backup(cible: Path, backup_path: Path) -> None:
    """Restaure le fichier d'origine depuis le backup."""
    shutil.copy2(backup_path, cible)

def traiter_cible(
    cible_str: str,
    args: argparse.Namespace,
    plan: str,
    modele_audit: str,
) -> Tuple[str, bool, bool]:
    """
    Exécute le cycle complet sur une cible en fonction du plan indiqué.
    Retourne :

    - une chaîne de rapport,
    - un booléen de succès,
    - un booléen indiquant si une fuite (local -> cloud) a été détectée.
    """
    cible = Path(cible_str).resolve()
    nom_cible = cible.name
    ident = _hash_path(cible)

    backup_dir = dossier_nexus()
    backup_path = backup_dir / f"backup-{nom_cible}-{ident}.bak"

    # 1. sauvegarde
    try:
        shutil.copy2(cible, backup_path)
    except Exception as e:
        print(f"Erreur lors de la sauvegarde de {nom_cible}: {e}")
        return f"{nom_cible},echec,0,0,none,{plan}", False, False

    # Flag indiquant si le backup a déjà été géré (restauré ou supprimé)
    backup_gere = False

    try:
        # 2. audit
        if args.consigne_audit:
            try:
                consigne_audit = charger_fichier(Path(args.consigne_audit))
            except FileNotFoundError as e:
                print(f"Consigne audit introuvable: {e}")
                restaurer_backup(cible, backup_path)
                backup_gere = True
                return (
                    f"{nom_cible},echec,0,0,none,{plan}",
                    False,
                    False,
                )
        else:
            consigne_audit = f"Audit du fichier {nom_cible} pour identifier les classes de défaut."

        audit_res = executer_audit(cible, consigne_audit, modele_audit)

        # Validation basique du résultat de l'agent
        if not isinstance(audit_res, dict):
            print(f"Audit result malformed for {nom_cible}")
            restaurer_backup(cible, backup_path)
            backup_gere = True
            return (
                f"{nom_cible},echec,0,0,none,{plan}",
                False,
                False,
            )

        # Gestion d'éventuelles erreurs d'audit
        if audit_res.get("erreur"):
            print(f"Audit error for {nom_cible}")
            restaurer_backup(cible, backup_path)
            backup_gere = True
            return (
                f"{nom_cible},echec,0,{audit_res.get('tokens',0)},{audit_res.get('modele','none')},{plan}",
                False,
                False,
            )

        audit_texte = audit_res.get("texte", "").strip()
        nb_trouvailles = len(audit_texte.splitlines()) if audit_texte else 0

        # 3. aucune trouvaille
        if not audit_texte:
            print(f"{nom_cible} sans trouvaille")
            backup_path.unlink(missing_ok=True)
            backup_gere = True
            return (
                f"{nom_cible},sans trouvaille,0,{audit_res.get('tokens',0)},{audit_res.get('modele','none')},{plan}",
                True,
                False,
            )

        # 4. création du fichier de consigne pour la correction
        consigne_path = creer_consigne_temp(cible, audit_texte)

        # 5. correction via nexus_patch.py
        cmd = [
            sys.executable,
            str(racine_depot() / "nexus_patch.py"),
            "--cible",
            str(cible),
            "--consigne",
            str(consigne_path),
        ]
        # Mode --fonctions au-dela d'un certain volume : mesure sur ce
        # depot (deux runs reels), le mode fichier entier (par defaut)
        # echoue systematiquement la verification au-dela d'environ 600
        # lignes -- c'etait le cas des 3 plus gros fichiers du depot a
        # chaque passage, jamais des plus petits. Reserve aux .py :
        # nexus_fonctions.py, qui applique ce mode, est un outil AST
        # Python et ne sait pas lire un .js ou un .ps1.
        seuil_fonctions_lignes = 600
        if cible.suffix.lower() == ".py":
            try:
                nb_lignes_cible = sum(1 for _ in cible.open(encoding="utf-8", errors="ignore"))
            except OSError:
                nb_lignes_cible = 0
            if nb_lignes_cible > seuil_fonctions_lignes:
                cmd.append("--fonctions")
        if args.modele_correction:
            cmd.extend(["--modele", args.modele_correction])
        if args.simuler:
            print(f"Simulation: {' '.join(cmd)}")
            correction_ok = True
        else:
            # Le délai par défaut était de 60 s, ce qui était trop court.
            # Mesures : 20‑60 s en cloud, jusqu’à 155 s à froid en local.
            # On porte le délai à 900 s (valeur utilisée ailleurs dans le dépôt)
            # et on le rend configurable via la variable d'environnement NEXUS_TIMEOUT.
            timeout_sec = int(os.getenv("NEXUS_TIMEOUT", "900"))
            try:
                res = subprocess.run(
                    cmd,
                    capture_output=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=timeout_sec,
                )
                correction_ok = res.returncode == 0
            except subprocess.TimeoutExpired:
                # Le processus a été tué après le timeout.
                # On vérifie si le fichier a été modifié.
                try:
                    current_hash = hashlib.sha256(cible.read_bytes()).hexdigest()
                    backup_hash = hashlib.sha256(backup_path.read_bytes()).hexdigest()
                except Exception as e:
                    print(f"Erreur lors du calcul des hash pour {nom_cible}: {e}")
                    # On ne peut pas déterminer l'état, on le signale comme inconnu.
                    return (
                        f"{nom_cible},inconnu,{nb_trouvailles},{audit_res.get('tokens',0)},{audit_res.get('modele','none')},{plan}",
                        False,
                        False,
                    )
                if current_hash == backup_hash:
                    # Aucun changement n'a eu lieu.
                    print(f"Timeout expired for {nom_cible} but file unchanged")
                    correction_ok = False
                else:
                    # Le fichier a été modifié mais on ne peut pas garantir la validité.
                    print(f"Timeout expired for {nom_cible}; file may be in unknown state")
                    # On ne restaure pas le backup, on signale l'état inconnu.
                    return (
                        f"{nom_cible},inconnu,{nb_trouvailles},{audit_res.get('tokens',0)},{audit_res.get('modele','none')},{plan}",
                        False,
                        False,
                    )

        # Nettoyage du fichier de consigne, même en cas d'échec
        consigne_path.unlink(missing_ok=True)

        if not correction_ok:
            print(f"Correction failed for {nom_cible}")
            restaurer_backup(cible, backup_path)
            backup_gere = True
            return (
                f"{nom_cible},echec,{nb_trouvailles},{audit_res.get('tokens',0)},{audit_res.get('modele','none')},{plan}",
                False,
                False,
            )

        # 6. vérification syntaxe
        if not verifier_syntaxe(cible):
            print(f"Verification failed for {nom_cible}")
            restaurer_backup(cible, backup_path)
            backup_gere = True
            return (
                f"{nom_cible},echec,{nb_trouvailles},{audit_res.get('tokens',0)},{audit_res.get('modele','none')},{plan}",
                False,
                False,
            )

        # 7. succès : on supprime le backup
        backup_path.unlink(missing_ok=True)
        backup_gere = True

        # Détection d'une fuite : cible prévue locale mais audit exécuté avec le modèle cloud
        fuite = False
        modele_observe = audit_res.get("modele", "")
        if plan == "local" and modele_observe == args.modele_audit:
            fuite = True
            print(f"Fuite detectee: {nom_cible} devait etre traite en local mais a utilise le modele cloud")

        return (
            f"{nom_cible},ok,{nb_trouvailles},{audit_res.get('tokens',0)},{modele_observe},{plan}",
            True,
            fuite,
        )
    finally:
        # Garantie de restauration du backup si celui‑ci n'a pas déjà été géré.
        if not backup_gere and backup_path.exists():
            try:
                restaurer_backup(cible, backup_path)
            except Exception as e:
                print(f"Restoration failed for {nom_cible}: {e}")
            finally:
                backup_path.unlink(missing_ok=True)

# --------------------------------------------------------------------------- #
# Fonction principale
# --------------------------------------------------------------------------- #

def analyser_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="DISPATCHEUR d'amélioration en parallèle."
    )
    parser.add_argument(
        "--cibles",
        nargs="+",
        required=True,
        help="Liste des fichiers à traiter.",
    )
    parser.add_argument(
        "--consigne-audit",
        help="Chemin vers le fichier contenant la consigne d'audit.",
    )
    parser.add_argument(
        "--modele-audit",
        default="adaptive-router-cloud",
        help="Alias du modèle à utiliser pour l'audit (plan cloud).",
    )
    parser.add_argument(
        "--modele-audit-local",
        default="codestral-22b-local",
        help="Alias du modèle à utiliser pour l'audit (plan local).",
    )
    parser.add_argument(
        "--modele-correction",
        default="gpt-oss-120b-cloud",
        help="Alias du modèle à utiliser pour la correction.",
    )
    parser.add_argument(
        "--parallele",
        type=int,
        default=3,
        help="Nombre maximal de cibles traitées en parallèle (plan cloud).",
    )
    parser.add_argument(
        "--parallele-local",
        type=int,
        default=2,
        help="Nombre maximal de cibles traitées en parallèle (plan local).",
    )
    parser.add_argument(
        "--plans",
        choices=["cloud", "local", "deux"],
        default="deux",
        help="Plan à employer : cloud, local ou deux (par défaut deux).",
    )
    parser.add_argument(
        "--simuler",
        action="store_true",
        help="Simuler les actions sans modifier les fichiers.",
    )
    return parser.parse_args()

def repartir_cibles(cibles: List[str]) -> Tuple[List[str], List[str]]:
    """
    Sépare les cibles en deux listes :

    - locales : le nom contient un indice de secret ou de configuration sensible,
    - cloud   : le reste.

    Les mots-clés sensibles sont : preserve, secret, env, cle, key, auth.
    """
    mots_cles = ["preserve", "secret", "env", "cle", "key", "auth"]
    locales = []
    cloud = []
    for c in cibles:
        nom = Path(c).name.lower()
        if any(mot in nom for mot in mots_cles):
            locales.append(c)
        else:
            cloud.append(c)
    return cloud, locales

def main() -> int:
    args = analyser_arguments()

    rapports: List[str] = []
    echec = False
    fuite_detectee = False

    # Détermination des listes de cibles selon le plan choisi
    if args.plans == "cloud":
        cloud_cibles = args.cibles
        local_cibles = []
    elif args.plans == "local":
        cloud_cibles = []
        local_cibles = args.cibles
    else:  # deux
        cloud_cibles, local_cibles = repartir_cibles(args.cibles)

    # Traitement du plan cloud
    if cloud_cibles:
        with ThreadPoolExecutor(max_workers=args.parallele) as executor:
            futures = {
                executor.submit(
                    traiter_cible,
                    cible,
                    args,
                    "cloud",
                    args.modele_audit,
                ): cible
                for cible in cloud_cibles
            }
            for future in as_completed(futures):
                rapport, ok, fuite = future.result()
                rapports.append(rapport)
                if not ok:
                    echec = True
                if fuite:
                    fuite_detectee = True

    # Traitement du plan local
    if local_cibles:
        with ThreadPoolExecutor(max_workers=args.parallele_local) as executor:
            futures = {
                executor.submit(
                    traiter_cible,
                    cible,
                    args,
                    "local",
                    args.modele_audit_local,
                ): cible
                for cible in local_cibles
            }
            for future in as_completed(futures):
                rapport, ok, fuite = future.result()
                rapports.append(rapport)
                if not ok:
                    echec = True
                if fuite:
                    fuite_detectee = True

    # Affichage du rapport
    for ligne in rapports:
        print(ligne)

    # Code de sortie : 1 si échec général ou fuite détectée
    if echec or fuite_detectee or not rapports:
        return 1
    return 0

if __name__ == "__main__":
    sys.exit(main())
