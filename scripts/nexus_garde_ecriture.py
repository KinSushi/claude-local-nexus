#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Garde d'écriture pour le shell : refuse d'écrire dans un chemin protégé.

Hook `PreToolUse` sur Bash et PowerShell. Il lit la commande, extrait les
cibles d'écriture avec `cibles_ecrites` du module `nexus_garde_lecture`,
et les compare aux chemins protégés lus dans la configuration du projet
(sous la clé `refus`, règles portant sur Edit, Write ou NotebookEdit,
chemin entre parenthèses).

RÈGLE DE DÉCISION MESURÉE :
- si le résultat est INDÉTERMINÉ, laisser passer sans rien dire ;
- si le résultat est DÉTERMINÉ, comparer chaque cible aux chemins protégés ;
- si une cible correspond, REFUSER avec un motif qui nomme la voie.

MESURE du 2026-08-31 : sur 886 commandes réelles, 89,6 % d'indéterminées
laissées passer, 10,4 % de déterminées dont ZÉRO fausse.

Ce garde ne doit JAMAIS planter : toute exception, tout JSON invalide,
toute entrée vide, toute absence de configuration se solde par un passage
silencieux. Un garde qui plante bloque le travail qu'il devait protéger.
"""
import json
import os
import re
import sys

# Racine ABSOLUE, comme dans nexus_garde_lecture.
ROOT = os.environ.get("CLAUDE_PROJECT_DIR") or os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))


def charger_chemins_proteges():
    """
    Lit la configuration du projet et retourne l'ensemble des chemins
    protégés (normalisés) pour les outils Edit, Write, NotebookEdit.

    Retourne un ensemble vide si la configuration est absente, illisible,
    ou ne contient aucune règle exploitable.
    """
    chemins = set()
    chemin_config = os.path.join(ROOT, ".claude", "settings.json")
    if not os.path.isfile(chemin_config):
        return chemins
    try:
        with open(chemin_config, encoding="utf-8") as fh:
            config = json.load(fh)
    except Exception:
        return chemins
    permissions = config.get("permissions")
    if not isinstance(permissions, dict):
        return chemins
    deny = permissions.get("deny")
    if not isinstance(deny, list):
        return chemins
    for regle in deny:
        chemin = extraire_chemin(regle)
        if chemin:
            try:
                chemins.add(normaliser_relatif(chemin))
            except Exception:
                pass
    return chemins


def extraire_chemin(regle):
    """
    Extrait un chemin protégé d'une règle de refus.

    La règle peut être :
    - une chaîne du type "Edit(chemin)" ou "Edit: (chemin)" ;
    - un dictionnaire avec des clés "tool"/"outil" et "path"/"chemin".

    Ne retourne un chemin que si l'outil est Edit, Write ou NotebookEdit.
    """
    outil = None
    valeur_chemin = None

    if isinstance(regle, str):
        # Format "Outil(chemin)" ou "Outil: (chemin)"
        m = re.match(r'^(Edit|Write|NotebookEdit)\s*\(\s*(.*?)\s*\)\s*$', regle.strip())
        if m:
            outil = m.group(1)
            valeur_chemin = m.group(2).strip()
        else:
            # Ancien format "Outil: (chemin)" ou "(chemin)"
            m = re.search(r'\((.*?)\)', regle)
            if m:
                valeur_chemin = m.group(1).strip()
            for nom in ("Edit", "Write", "NotebookEdit"):
                if nom in regle:
                    outil = nom
                    break
    elif isinstance(regle, dict):
        outil = regle.get("tool") or regle.get("outil")
        valeur_chemin = regle.get("path") or regle.get("chemin")
        if isinstance(valeur_chemin, str):
            m = re.search(r'\((.*?)\)', valeur_chemin)
            if m:
                valeur_chemin = m.group(1).strip()
            else:
                valeur_chemin = valeur_chemin.strip()
        else:
            valeur_chemin = None

    if outil not in ("Edit", "Write", "NotebookEdit"):
        return None
    if not valeur_chemin:
        return None
    return valeur_chemin


def normaliser_relatif(chemin):
    """
    Normalise un chemin en forme relative à la racine du dépôt,
    avec des séparateurs uniformes '/' et en minuscules.
    """
    if os.path.isabs(chemin):
        rel = os.path.relpath(chemin, ROOT)
    else:
        rel = chemin
    rel = rel.replace('\\', '/')
    rel = rel.lower()
    rel = re.sub(r'^\./+', '', rel)
    rel = re.sub(r'/+', '/', rel)
    return rel


def refuser(chemin_affiche):
    """
    Émet la décision de refus au format attendu par le hook.
    """
    motif = ("REFUS -- CHEMIN PROTÉGÉ. Le fichier %s est protégé et toute "
             "modification doit passer par une décision explicite."
             % os.path.basename(chemin_affiche))
    try:
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": motif,
            }
        }, ensure_ascii=False))
    except Exception:
        pass


def main():
    try:
        from nexus_garde_lecture import cibles_ecrites, normaliser
    except ImportError:
        # Sans le module d'extraction, on ne peut rien décider : on laisse
        # passer silencieusement.
        return

    try:
        brut = sys.stdin.read()
    except Exception:
        return
    if not brut or not brut.strip():
        return
    try:
        charge = json.loads(brut)
    except Exception:
        return
    if not isinstance(charge, dict):
        return

    outil = charge.get("tool_name") or ""
    entree = charge.get("tool_input")
    entree = entree if isinstance(entree, dict) else {}

    if outil not in ("Bash", "PowerShell"):
        return

    commande = entree.get("command")
    if not isinstance(commande, str) or not commande.strip():
        return

    try:
        chemins, indetermine = cibles_ecrites(commande)
    except Exception:
        return

    # Indéterminé : on laisse passer sans rien dire.
    if indetermine:
        return

    # Aucun chemin déterminé : rien à comparer.
    if not chemins:
        return

    # Charge les chemins protégés (peut être vide si config absente).
    try:
        proteges = charger_chemins_proteges()
    except Exception:
        return

    if not proteges:
        return

    for cible in chemins:
        try:
            cible_norm = normaliser_relatif(cible)
        except Exception:
            continue
        for protege in proteges:
            if protege.endswith('*'):
                prefixe = protege[:-1]
                if cible_norm.startswith(prefixe):
                    refuser(cible)
                    return
            elif cible_norm == protege:
                refuser(cible)
                return


if __name__ == "__main__":
    try:
        main()
    except BaseException:
        # Rempart final : ce garde n'échoue jamais.
        pass
    sys.exit(0)
