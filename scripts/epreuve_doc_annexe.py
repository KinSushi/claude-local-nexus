# -*- coding: utf-8 -*-
"""
Pourquoi cette epreuve existe ?

Le module `nexus_doc` produit du texte destiné à être affiché dans la console
ou dans des documents markdown. Un rendu vide est le plus dangereux des trois
états possibles (vide, partiel, complet) car il se lit comme une absence de
contenu et masque les régressions. Cette epreuve vérifie, à travers sept
situations réelles observées le 31‑08‑2026, que :

* les index d’annexes sont correctement peuplés,
* les offsets sont conservés entre copies,
* les symboles de cmdlet sont rendus avec un texte non vide,
* les leçons sont affichées même sans clé `type`,
* les objets de type inconnu génèrent un message explicite,
* la fonction de recherche privilégie les suffixes réels,
* la console est forcée en UTF‑8 pour éviter les caractères illisibles.

En cas d’échec, le compteur global `echecs` est incrémenté et le script
retourne un code de sortie non‑zéro.
"""
import os
import sys

# Ajout du répertoire du script au PATH afin d’importer les modules du dépôt
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nexus_doc
import console_tools

echecs = 0


def verifier(nom, condition, detail):
    """Affiche le résultat d’un test et incrémente le compteur d’échecs."""
    global echecs
    print("[{}] {} : {}".format("OK  " if condition else "RATE", nom, detail))
    if not condition:
        echecs += 1


def jouer() -> int:
    """Exécute les sept cas de test décrits dans la docstring."""
    # Racine du dépôt (dossier parent du répertoire contenant ce script)
    racine = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    # -----------------------------------------------------------------
    # Cas 1 – charger_index_annexe doit retourner >= 600 entrées valides
    entrees = nexus_doc.charger_index_annexe(racine)
    condition1 = (
        isinstance(entrees, list)
        and len(entrees) >= 600
        and all(
            isinstance(e, tuple)
            and len(e) == 4
            and isinstance(e[1], str)
            and e[1].endswith(".jsonl")
            for e in entrees
        )
    )
    verifier(
        "Cas 1 – charger_index_annexe",
        condition1,
        "nb_entrees={}".format(len(entrees) if isinstance(entrees, list) else "NA"),
    )

    # -----------------------------------------------------------------
    # Cas 2 – verifier_offsets_annexe doit rendre zéro discordance
    verifies, discordances = nexus_doc.verifier_offsets_annexe(racine, entrees, 25)
    verifier(
        "Cas 2 – verifier_offsets_annexe",
        discordances == 0,
        "discordances={}".format(discordances),
    )

    # -----------------------------------------------------------------
    # Cas 3 – rendre_symbole_annexe doit produire un texte non vide contenant le nom court
    cmdlet = {
        "type": "cmdlet",
        "nom_court": "New-Item",
        "module": "Microsoft.PowerShell.Management",
        "resume": "Creates a new item.",
        "signature": "New-Item [-Path] <String> [-Name] <String> ...",
        "parametres": [
            {
                "nom": "Path",
                "type_declare": "String",
                "requis": True,
                "position": 0,
                "description": "Specifies the path.",
            }
        ],
        "exemples": [
            {
                "titre": "Créer un fichier texte",
                "code": ["New-Item -Path . -Name \"file.txt\" -ItemType File"],
            }
        ],
        "notes": "Cette cmdlet est disponible depuis PowerShell 3.0.",
    }
    texte_cmdlet = nexus_doc.rendre_symbole_annexe(cmdlet)
    condition3 = (
        isinstance(texte_cmdlet, str)
        and len(texte_cmdlet.strip()) > 0
        and cmdlet["nom_court"] in texte_cmdlet
        and len(texte_cmdlet.splitlines()) <= 40
    )
    verifier(
        "Cas 3 – rendre_symbole_annexe",
        condition3,
        "len_lignes={}".format(len(texte_cmdlet.splitlines()) if isinstance(texte_cmdlet, str) else "NA"),
    )

    # -----------------------------------------------------------------
    # Cas 4 – rendre_symbole_annexe doit produire un texte non vide même sans clé `type`
    lecon = {
        "methode": "lecon",
        "titre": "Gestion des processus",
        "registre": "powershell",
        "chemin": "docs/lecons/processus.md",
        "ligne": 42,
        "texte": "Cette leçon décrit comment manipuler les processus sous Windows.",
    }
    texte_lecon = nexus_doc.rendre_symbole_annexe(lecon)
    condition4 = isinstance(texte_lecon, str) and len(texte_lecon.strip()) > 0
    verifier(
        "Cas 4 – rendre_symbole_annexe",
        condition4,
        "texte_vide={}".format(not condition4),
    )

    # -----------------------------------------------------------------
    # Cas 5 – objet de type inconnu doit rendre un texte non vide mentionnant l'absence de type
    inconnu = {"resume": "Objet sans type connu."}
    texte_inconnu = nexus_doc.rendre_symbole_annexe(inconnu)
    condition5 = (
        isinstance(texte_inconnu, str)
        and len(texte_inconnu.strip()) > 0
        and "type" in texte_inconnu.lower()
    )
    verifier(
        "Cas 5 – rendu objet inconnu",
        condition5,
        "texte={}".format(texte_inconnu[:30] + "..." if isinstance(texte_inconnu, str) else "NA"),
    )

    # -----------------------------------------------------------------
    # Cas 5 bis – TYPE INCONNU MAIS RENDABLE : on rend, sans crier.
    #
    # CE QUI ETAIT FAUX : tout type non prevu criait « corpus non reconnu »,
    # y compris quand l'objet portait un titre et un texte parfaitement
    # rendables. Un corpus sain -- 18 000 entrees de livres empruntes --
    # s'annoncait casse a chaque entree.
    #
    # Corriger cela type par type est un remede qui se represente a chaque
    # corpus neuf : c'est le troisieme qui l'a montre. On distingue donc
    # RENDABLE de VIDE.
    rendable = {"type": "section", "titre": "Un titre de chapitre",
                "texte": "Le contenu du chapitre, parfaitement lisible."}
    texte_rendable = nexus_doc.rendre_symbole_annexe(rendable)
    condition5b = (
        isinstance(texte_rendable, str)
        and "Un titre de chapitre" in texte_rendable
        and "parfaitement lisible" in texte_rendable
        and "non reconnu" not in texte_rendable
    )
    verifier(
        "Cas 5 bis – type inconnu mais rendable",
        condition5b,
        "le contenu remonte, sans cri",
    )

    # Cas 5 ter – ANTI-CONTROLE : l'alarme reste quand elle dit vrai.
    #
    # Sans ce cas, une correction qui supprimerait le cri partout passerait --
    # et un objet reellement vide se lirait comme une absence de contenu,
    # « le pire des trois etats » selon ce fichier lui-meme.
    vide = {"type": "inconnu-total"}
    texte_vide2 = nexus_doc.rendre_symbole_annexe(vide)
    condition5t = (
        isinstance(texte_vide2, str)
        and "non reconnu" in texte_vide2
    )
    verifier(
        "Cas 5 ter – l'alarme reste quand elle dit vrai",
        condition5t,
        "un objet sans rien a montrer doit le DIRE",
    )

    # -----------------------------------------------------------------
    # Cas 6 – chercher doit privilégier le vrai suffixe avant la sous‑chaine
    index_manuel = [
        ("bash.trap", "shell.jsonl", 0, 10),
        ("scipy.stats.BootstrapMethod", "x__LOCALFIRST_y.md", 0, 10),
    ]
    resultats = nexus_doc.chercher(index_manuel, "trap")
    premier = resultats[0] if isinstance(resultats, list) and resultats else None
    condition6 = isinstance(premier, tuple) and premier[0] == "bash.trap"
    verifier(
        "Cas 6 – recherche suffixe",
        condition6,
        "premier={}".format(premier),
    )

    # -----------------------------------------------------------------
    # Cas 7 – forcer_utf8 doit rendre sys.stdout.encoding == 'utf-8'
    console_tools.forcer_utf8()
    enc = getattr(sys.stdout, "encoding", "").lower()
    condition7 = enc == "utf-8"
    verifier(
        "Cas 7 – forcer_utf8",
        condition7,
        "encoding={}".format(enc),
    )

    # -----------------------------------------------------------------
    print("-" * 66)
    print("VERDICT : {}".format("epreuve tenue" if echecs == 0 else "{} echec(s)".format(echecs)))
    return 1 if echecs else 0


if __name__ == "__main__":
    # RIEN NE S'EXECUTE A L'IMPORT.
    sys.exit(jouer())
