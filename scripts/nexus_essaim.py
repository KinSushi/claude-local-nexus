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
import os
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, List, Tuple

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

def dossier_scripts() -> Path:
    """Répertoire contenant ce script — c'est là que vivent ses voisins."""
    return Path(__file__).resolve().parent

def racine_depot() -> Path:
    """
    Racine du dépôt : le PARENT de ``scripts``.

    L'ancienne version rendait ``scripts`` et le nommait « racine du dépôt » —
    son propre docstring disait l'un et son code faisait l'autre. Elle servait
    en outre à deux fins contradictoires : localiser ``.nexus`` (qui appartient
    à la racine) et localiser ``nexus_patch.py`` (qui appartient à ``scripts``).
    Aucun appel n'échouait, puisque chacun était juste pour son propre besoin
    et faux pour l'autre.

    Conséquence mesurée le 2026-08-30 : quarante sauvegardes ``backup-*.bak``
    écrites dans ``scripts/.nexus/`` au lieu de ``.nexus/``. Elles y étaient
    invisibles à qui cherchait à la racine — et elles n'auraient pas dû
    subsister du tout : chacune est le reste d'une exécution qui n'a pas
    nettoyé, donc d'une cible potentiellement laissée modifiée.

    Rien n'a fuité : le motif ``.nexus/`` du .gitignore n'a pas de barre
    oblique initiale, donc il s'applique à tous les niveaux. Vérifié par
    ``git check-ignore``, pas supposé.
    """
    return dossier_scripts().parent

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

def dossier_isole() -> Path:
    """
    Repertoire de travail isole, hors de l'arbre principal.

    Le contrat (0.4) veut qu'un worker recoive une COPIE, jamais la source :
    il peut tronquer, reecrire ou inventer, et le depot ne doit pas pouvoir
    en souffrir. On le place a cote de `.nexus-arbres`, ou vivent deja les
    worktrees isoles, pour qu'un seul repertoire concentre tout ce qui est
    jetable.

    Volontairement hors du depot : ce qu'un modele ecrit ici ne peut etre
    commite par megarde, ni ramasse par un outil qui parcourt l'arbre.
    """
    d = racine_depot().parent / ".nexus-arbres" / "essaim"
    d.mkdir(parents=True, exist_ok=True)
    return d


def preparer_copie(cible: Path, ident: str) -> Path:
    """
    Copie la cible dans l'espace isole et rend le chemin de la copie.

    On copie l'etat REEL du fichier, pas sa version commitee : un worktree
    git refleterait le dernier commit, et une cible modifiee et non commitee
    aurait ete corrigee dans une version ancienne, puis promue par-dessus le
    travail en cours.
    """
    copie = dossier_isole() / ("%s-%s%s" % (cible.stem, ident, cible.suffix))
    shutil.copy2(cible, copie)
    return copie


def _hash_path(cible: Path) -> str:
    """Retourne un identifiant court basé sur le chemin complet de la cible."""
    h = hashlib.sha256(str(cible).encode("utf-8")).hexdigest()
    return h[:8]

# --------------------------------------------------------------------------- #
# Interaction avec nexus_agent
# --------------------------------------------------------------------------- #

def executer_audit(cible: Path, consigne: str, modele: str,
                   local_seul: bool = False) -> Dict:
    """
    Lance l'audit sur la cible en appelant ``nexus_agent.executer``.
    Retourne le dictionnaire brut renvoyé par l'agent.

    Reessaie une fois avec un plafond double si la premiere reponse est
    tronquee (finish_reason "length"), comme le fait deja nexus_patch.py
    pour l'etape de correction. Sans ce reessai, un gros fichier (server.js,
    2051 lignes) echouait des l'audit avec "plafond insuffisant", avant
    meme d'atteindre la correction -- observe en conditions reelles sur ce
    depot.
    """
    cle = agent.cle_maitre()

    def appeler(plafond: int) -> Dict:
        payload = {
            "nom": f"audit-{cible.name}",
            "modele": modele,
            # Sans cette clef, un modele local qui echoue fait basculer
            # nexus_agent sur ses replis gratuits, dont le PREMIER est un
            # modele cloud : une cible classee sensible partait alors hors
            # de la machine. Mesure du 30 aout 2026 : nexus_preserve.py,
            # classee locale, servie par gpt-oss-120b-cloud. Un repli qui
            # traverse la frontiere de confidentialite est pire qu'un
            # echec -- l'echec se voit, la fuite non.
            "local_seul": local_seul,
            "tache": consigne,
            "fichiers": [str(cible)],
            "max_tokens": plafond,
        }
        resultat = agent.executer(payload, cle)
        return resultat if isinstance(resultat, dict) else {}

    # Trois paliers, et non deux.
    #
    # Mesure du 2026-08-30, audit delegue sur six scripts : trois ont
    # echoue a 8192 jetons -- nexus_agent.py (21260 jetons d'entree),
    # nexus_patch.py (13175) et nexus_capability.py. Le modele epuise son
    # budget de sortie EN RAISONNANT, avant d'avoir ecrit une ligne : le
    # retour est vide et marque tronque.
    #
    # Chaque palier coute du temps et rien d'autre, le plan etant gratuit.
    # Un echec, lui, coute l'audit entier.
    for plafond in (4096, 8192, 16384):
        resultat = appeler(plafond)
        if not resultat.get("tronque"):
            return resultat

    # Toujours tronque au dernier palier : le dire, et dire lequel.
    #
    # Le message d'origine, « augmenter le plafond », laissait croire qu'on
    # n'avait pas essaye. Un operateur ne peut pas savoir quoi augmenter si
    # on ne lui dit pas jusqu'ou on est alle.
    detail = resultat.get("erreur") or resultat.get("detail") or "reponse tronquee"
    resultat["erreur"] = (
        "%s — trois paliers epuises (4096, 8192, 16384 jetons). "
        "La cible est probablement trop grosse pour un audit d'un seul "
        "tenant : la decouper, ou employer nexus_context qui procede par "
        "fenetres." % detail
    )
    return resultat

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
        if suffix == ".js":
            cmd = ["node", "--check", str(cible)]
            res = subprocess.run(
                cmd,
                capture_output=True,
                encoding="utf-8",
                errors="replace",
                timeout=30,
            )
            return res.returncode == 0
        if suffix == ".ps1":
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

    # La copie de travail. Tout ce qui suit -- audit, correction,
    # verification -- porte sur ELLE. L'original n'est touche qu'a l'etape 7,
    # une fois la syntaxe verifiee.
    try:
        cible_travail = preparer_copie(cible, ident)
    except Exception as e:
        print(f"Copie isolee impossible pour {nom_cible}: {e}")
        backup_path.unlink(missing_ok=True)
        return f"{nom_cible},echec,0,0,none,{plan},copie isolee impossible", False, False

    # Vrai seulement pendant la promotion : c'est la seule fenetre ou
    # l'original peut etre a moitie ecrit, et donc la seule ou le backup
    # sert encore a quelque chose.
    promotion_en_cours = False

    try:
        # 2. audit
        if args.consigne_audit:
            try:
                consigne_audit = charger_fichier(Path(args.consigne_audit))
            except FileNotFoundError as e:
                print(f"Consigne audit introuvable: {e}")
                restaurer_backup(cible, backup_path)
                return (
                    f"{nom_cible},echec,0,0,none,{plan},consigne audit introuvable",
                    False,
                    False,
                )
        else:
            consigne_audit = f"Audit du fichier {nom_cible} pour identifier les classes de défaut."

        audit_res = executer_audit(cible_travail, consigne_audit, modele_audit,
                                   local_seul=(plan == "local"))

        # Validation basique du résultat de l'agent
        if not isinstance(audit_res, dict):
            print(f"Audit result malformed for {nom_cible}")
            # Rien a restaurer : l'original n'a jamais ete ouvert en ecriture.
            backup_path.unlink(missing_ok=True)
            return (
                f"{nom_cible},echec,0,0,none,{plan},reponse d'audit malformee",
                False,
                False,
            )

        # Gestion d'éventuelles erreurs d'audit
        if audit_res.get("erreur"):
            print(f"Audit error for {nom_cible}")
            # Rien a restaurer : l'original n'a jamais ete ouvert en ecriture.
            backup_path.unlink(missing_ok=True)
            detail_audit = str(audit_res.get('erreur', '')).replace(',', ';').replace('\n', ' ')[:160]
            return (
                f"{nom_cible},echec,0,{audit_res.get('tokens',0)},{audit_res.get('modele','none')},{plan},{detail_audit}",
                False,
                False,
            )

        audit_texte = audit_res.get("texte", "").strip()
        nb_trouvailles = len(audit_texte.splitlines()) if audit_texte else 0

        # 3. aucune trouvaille
        if not audit_texte:
            print(f"{nom_cible} sans trouvaille")
            backup_path.unlink(missing_ok=True)
            return (
                f"{nom_cible},sans trouvaille,0,{audit_res.get('tokens',0)},{audit_res.get('modele','none')},{plan}",
                True,
                False,
            )

        # 4. création du fichier de consigne pour la correction
        consigne_path = creer_consigne_temp(cible_travail, audit_texte)

        # 5. correction via nexus_patch.py
        cmd = [
            sys.executable,
            str(dossier_scripts() / "nexus_patch.py"),
            "--cible",
            str(cible_travail),
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
        #
        # Pour les autres extensions (.js, .ps1), --triplets : mesure sur
        # ce depot, la cause precise de l'echec au-dela du seuil n'est pas
        # une ancre introuvable mais "reponse tronquee meme apres double
        # plafond" (server.js, 2051 lignes) -- le mode fichier entier
        # demande de reproduire tout le fichier, --triplets seulement les
        # extraits changes, ce qui evite cette troncature precise meme si
        # une ancre peut encore echouer pour une autre raison.
        seuil_fonctions_lignes = 600
        try:
            nb_lignes_cible = sum(1 for _ in cible_travail.open(encoding="utf-8", errors="ignore"))
        except OSError:
            nb_lignes_cible = 0
        if nb_lignes_cible > seuil_fonctions_lignes:
            if cible.suffix.lower() == ".py":
                cmd.append("--fonctions")
            else:
                cmd.append("--triplets")
        if args.modele_correction:
            cmd.extend(["--modele", args.modele_correction])

        # Detail de l'echec de correction, pour le rapport (7e champ CSV).
        # Sans lui, "echec" ne distingue pas un blocage reseau d'une reponse
        # mal formee ou d'une syntaxe invalide -- il fallait rejouer la
        # meme consigne a la main pour le savoir, ce qui est arrive.
        detail_correction = ""

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
                if not correction_ok:
                    # Dernier message imprime par nexus_patch.py : c'est le
                    # seul indice sur la cause reelle (bloc mal forme,
                    # aucune fonction appliquee, syntaxe invalide...).
                    sortie_brute = (res.stdout or res.stderr or "").strip()
                    derniere_ligne = sortie_brute.splitlines()[-1] if sortie_brute else ""
                    detail_correction = derniere_ligne.replace(",", ";").replace("\n", " ")[:160]
            except subprocess.TimeoutExpired:
                # Le processus a été tué après le timeout.
                # On vérifie si le fichier a été modifié.
                try:
                    current_hash = hashlib.sha256(cible_travail.read_bytes()).hexdigest()
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
                    detail_correction = f"timeout apres {timeout_sec}s"
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
            # Rien a restaurer : l'original n'a jamais ete ouvert en ecriture.
            backup_path.unlink(missing_ok=True)
            return (
                f"{nom_cible},echec,{nb_trouvailles},{audit_res.get('tokens',0)},{audit_res.get('modele','none')},{plan},{detail_correction}",
                False,
                False,
            )

        # 6. vérification syntaxe
        if not verifier_syntaxe(cible_travail):
            print(f"Verification failed for {nom_cible}")
            # Rien a restaurer : l'original n'a jamais ete ouvert en ecriture.
            backup_path.unlink(missing_ok=True)
            return (
                f"{nom_cible},echec,{nb_trouvailles},{audit_res.get('tokens',0)},{audit_res.get('modele','none')},{plan},syntaxe invalide apres correction",
                False,
                False,
            )

        # 7. succes verifie : la copie remplace l'original.
        #
        # C'est le SEUL moment ou l'original est ouvert en ecriture, et il
        # vient apres la verification de syntaxe -- non avant, comme c'etait
        # le cas quand la correction s'appliquait a la source.
        promotion_en_cours = True
        try:
            shutil.copy2(cible_travail, cible)
        except Exception as e:
            print(f"Promotion impossible pour {nom_cible}: {e}")
            restaurer_backup(cible, backup_path)
            backup_path.unlink(missing_ok=True)
            return (
                f"{nom_cible},echec,{nb_trouvailles},{audit_res.get('tokens',0)},{audit_res.get('modele','none')},{plan},promotion impossible",
                False,
                False,
            )
        promotion_en_cours = False
        backup_path.unlink(missing_ok=True)

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
        # Le backup ne sert plus qu'a UNE chose : la fenetre de promotion,
        # seul instant ou l'original peut etre a moitie ecrit. Partout
        # ailleurs il n'a pas bouge, et le restaurer serait au mieux inutile,
        # au pire une regression -- on reecrirait par-dessus un fichier sain.
        if promotion_en_cours and backup_path.exists():
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
    Separe les cibles : ce qui est sensible reste local, le reste peut sortir.

    La decision revient a nexus_agent.est_secret, definition UNIQUE de la
    sensibilite dans ce depot. Auparavant cette fonction avait la sienne --
    six mots-clefs cherches en sous-chaine : preserve, secret, env, cle, key,
    auth -- et les deux divergeaient.

    Mesure du 30 aout 2026, trois divergences dangereuses dans le meme sens :

        credentials.json   essaim CLOUD   agent secret
        id_rsa             essaim CLOUD   agent secret
        serveur.pem        essaim CLOUD   agent secret

    Des identifiants et des cles privees seraient donc partis vers
    ollama.com, alors que l'agent refuse deja de les lire. Deux definitions
    concurrentes de « sensible » valent moins qu'une seule : la plus laxiste
    l'emporte toujours, puisqu'il suffit d'emprunter le chemin qu'elle garde.

    Les divergences inverses -- nexus_preserve.py classe local par la
    sous-chaine « preserve » alors que ce script n'a rien de secret -- se
    corrigent du meme coup. Chercher « key » en sous-chaine attrapait aussi
    « monkey ».
    """
    locales, cloud = [], []
    for c in cibles:
        (locales if agent.est_secret(c) else cloud).append(c)
    return cloud, locales

def traiter_plan(cibles, args, plan, modele, parallele):
    """
    Traite les cibles d'UN plan dans son propre executeur.

    Extraire ce traitement permet de lancer les deux plans en meme temps :
    tant que chacun vivait dans un bloc `with` de main(), le second ne
    pouvait pas demarrer avant que le premier ait vide sa file, et les
    durees s'additionnaient. Or les deux ne se disputent rien -- le plan
    local est borne par la machine, le plan cloud par le reseau.

    Chaque plan garde son propre plafond, qui est mesure : le cloud
    n'accelere plus au-dela de trois appels simultanes, le local plafonne
    des le deuxieme. Les fusionner effacerait ces deux mesures.
    """
    if not cibles:
        return []
    resultats = []
    with ThreadPoolExecutor(max_workers=parallele) as executor:
        futures = {
            executor.submit(traiter_cible, cible, args, plan, modele): cible
            for cible in cibles
        }
        for future in as_completed(futures):
            resultats.append(future.result())
    return resultats


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

    def resultats_ou_echec(future, nom_plan):
        # Un plan qui echoue ne doit pas faire perdre l'autre, mais il ne
        # doit pas non plus passer pour un plan sans travail : on rend un
        # triplet d'echec, que la boucle d'agregation traduira en ligne de
        # rapport et en echec = True. Une panne muette se confond avec un
        # succes, et c'est le pire des deux.
        try:
            return future.result()
        except Exception as exc:
            return [("plan %s en echec : %s" % (nom_plan, exc), False, False)]

    # Les deux plans partent ENSEMBLE. Leurs durees se superposent au lieu
    # de s'additionner : le gain est celui du plan le plus court.
    with ThreadPoolExecutor(max_workers=2) as executor:
        future_cloud = executor.submit(
            traiter_plan, cloud_cibles, args, "cloud",
            args.modele_audit, args.parallele,
        )
        future_local = executor.submit(
            traiter_plan, local_cibles, args, "local",
            args.modele_audit_local, args.parallele_local,
        )
        resultats_cloud = resultats_ou_echec(future_cloud, "cloud")
        resultats_local = resultats_ou_echec(future_local, "local")

    for rapport, ok, fuite in resultats_cloud + resultats_local:
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
