#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
nexus_patch.py

Outil en ligne de commande qui envoie une consigne et un fichier cible au
banc de modeles gratuits via nexus_agent, extrait le resultat et le
applique de façon atomique.  Il supporte deux modes :

* mode fichier entier (par défaut) : le modele renvoie le fichier complet
  entre les balises @@FICHIER@@ et @@FIN@@.
* mode triplets (option --triplets) : le modele renvoie des triplets
  @@REMPLACER@@ / @@PAR@@ / @@FIN@@ comme auparavant.

Le script inclut plusieurs garde-fous pour eviter les echecs
silencieux : verification syntaxique, controle de taille, detection de
troncature, etc.

Les messages console sont sans accents pour compatibilite Windows.
"""

import argparse
import ast
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

# ---------------------------------------------------------------------------

def charger_fichier(chemin):
    """Lit le contenu d'un fichier en utf-8."""
    with open(chemin, "r", encoding="utf-8") as f:
        return f.read()

def ecrire_fichier_atomique(chemin, contenu):
    """
    Ecrit le contenu dans un fichier temporaire puis le remplace atomiquement.
    Conserve une copie de sauvegarde du fichier original.
    """
    dossier = os.path.dirname(os.path.abspath(chemin))
    fd, tmp_path = tempfile.mkstemp(dir=dossier)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as tmp:
            tmp.write(contenu)
        sauvegarde = chemin + ".candidat"
        shutil.copy2(chemin, sauvegarde)
        os.replace(tmp_path, chemin)
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)

def lire_consigne(args):
    """Retourne la consigne fournie soit par fichier, soit en ligne."""
    if args.consigne:
        return charger_fichier(args.consigne)
    elif args.consigne_texte:
        return args.consigne_texte
    else:
        raise ValueError("Une consigne doit etre fournie")

def ajouter_exigence_fichier(consigne):
    """
    Ajoute l'exigence de format fichier complet au texte de la consigne.
    Le modele doit repondre exactement :

    @@FICHIER@@
    <contenu du fichier corrige>
    @@FIN@@
    """
    exigence = (
        "\n\nRepondez exactement dans le format suivant :\n"
        "@@FICHIER@@\n"
        "<le fichier complet, corrige, pret a ecrire>\n"
        "@@FIN@@\n"
    )
    return consigne.rstrip() + exigence

def ajouter_exigence_triplet(consigne):
    """
    Ajoute l'exigence de format triplet (mode legacy) au texte de la consigne.
    """
    exigence = (
        "\n\nRepondez exactement dans le format suivant :\n"
        "@@REMPLACER@@\n"
        "<lignes exactes>\n"
        "@@PAR@@\n"
        "<remplacement>\n"
        "@@FIN@@\n"
    )
    return consigne.rstrip() + exigence

def appeler_agent(consigne, cible_path, modele, max_tokens, cle):
    """Envoie la requete au serveur nexus_agent."""
    payload = {
        "nom": "nexus_patch",
        "modele": modele,
        "tache": consigne,
        "fichiers": [cible_path],
        "max_tokens": max_tokens,
    }
    import nexus_agent as agent
    return agent.executer(payload, cle)

def extraire_fichier(texte):
    """
    Retourne le contenu situe entre @@FICHIER@@ et @@FIN@@.
    Si le bloc est absent, renvoie None.
    """
    pattern = re.compile(r"@@FICHIER@@\s*(.*?)\s*@@FIN@@", re.DOTALL)
    m = pattern.search(texte)
    if not m:
        return None
    return m.group(1).rstrip("\n") + "\n"

def extraire_triplets(texte):
    """
    Retourne une liste de dicts: {"anchor": str, "replace": str}
    Utilise le format triplet legacy.
    """
    pattern = re.compile(
        r"@@REMPLACER@@\s*(.*?)\s*@@PAR@@\s*(.*?)\s*@@FIN@@",
        re.DOTALL,
    )
    triplets = []
    for m in pattern.finditer(texte):
        anchor = m.group(1).rstrip("\n")
        replace = m.group(2).rstrip("\n")
        triplets.append({"anchor": anchor, "replace": replace})
    return triplets

def lignes_avec_indentation(lignes):
    """Retourne liste de (nb_espaces, texte) pour chaque ligne non vide."""
    res = []
    for l in lignes.splitlines():
        if l.strip() == "":
            continue
        nb = len(l) - len(l.lstrip(" "))
        res.append((nb, l.lstrip(" ")))
    return res

def appliquer_triplet(contenu, triplet, numero):
    """
    Applique un triplet sur le contenu du fichier.
    Retourne le nouveau contenu si l'ancre est trouvee, sinon None.
    Gère le decalage d'indentation.
    """
    anchor = triplet["anchor"]
    replace = triplet["replace"]
    lines = contenu.splitlines(keepends=True)

    # Recherche exacte
    anchor_lines = anchor.splitlines()
    indices = []
    for i in range(len(lines) - len(anchor_lines) + 1):
        segment = "".join(lines[i : i + len(anchor_lines)])
        if segment.rstrip("\n") == anchor.rstrip("\n"):
            indices.append(i)

    if len(indices) == 1:
        start = indices[0]
        new_lines = lines[:start] + [replace + "\n"] + lines[start + len(anchor_lines) :]
        return "".join(new_lines)

    # Gestion indentation (a)
    anchor_info = lignes_avec_indentation(anchor)
    if not anchor_info:
        return None

    # Plage +/- 16 et non +/- 8 : mesure sur ce depot, un corps de boucle
    # imbrique vit a 12 espaces et le banc rend souvent l'ancre desindentee
    # a zero. Une plage trop etroite faisait declarer « inventee » une ancre
    # qui existait bel et bien, ce qui envoie chercher au mauvais endroit.
    for delta in range(-16, 17):
        if delta == 0:
            continue
        decaled = []
        for nb, txt in anchor_info:
            new_nb = nb + delta
            if new_nb < 0:
                break
            decaled.append(" " * new_nb + txt)
        else:
            decaled_str = "\n".join(decaled) + "\n"
            indices = []
            for i in range(len(lines) - len(anchor_info) + 1):
                segment = "".join(lines[i : i + len(anchor_info)])
                if segment == decaled_str:
                    indices.append(i)
            if len(indices) == 1:
                replace_info = lignes_avec_indentation(replace)
                decaled_replace = []
                for nb, txt in replace_info:
                    new_nb = nb + delta
                    if new_nb < 0:
                        new_nb = 0
                    decaled_replace.append(" " * new_nb + txt)
                replace_str = "\n".join(decaled_replace) + "\n"
                start = indices[0]
                new_lines = lines[:start] + [replace_str] + lines[start + len(anchor_info) :]
                return "".join(new_lines)

    # Ancre introuvable ou multiple
    return None

def verifier_syntaxe(chemin, contenu):
    """
    Verifie la syntaxe du contenu selon l'extension du fichier.
    Retourne True si la syntaxe est valide, False sinon.
    """
    ext = os.path.splitext(chemin)[1].lower()
    if ext == ".py":
        try:
            ast.parse(contenu)
            return True
        except SyntaxError:
            return False
    elif ext == ".js":
        # `encoding` explicite : sans lui, Python retombe sur la page de code
        # du systeme, cp1252 sous Windows, et l'ecriture leve des qu'un
        # commentaire porte un accent -- ce que ce depot exige partout.
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False,
                                         encoding="utf-8") as tf:
            tf.write(contenu)
            tf_path = tf.name
        try:
            result = subprocess.run(
                ["node", "--check", tf_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            return result.returncode == 0
        finally:
            os.unlink(tf_path)
    elif ext == ".ps1":
        with tempfile.NamedTemporaryFile("w", suffix=".ps1", delete=False,
                                         encoding="utf-8") as tf:
            tf.write(contenu)
            tf_path = tf.name
        try:
            result = subprocess.run(
                # ParseFile et NON un point-sourcing. `. 'fichier'` EXECUTE le
                # script : sur un smoke test ou un script de sauvegarde, une
                # simple verification syntaxique aurait donc lance le travail
                # pour de bon. Le parseur analyse sans executer.
                ["pwsh", "-NoProfile", "-Command",
                 "$e=$null; $null=[System.Management.Automation.Language.Parser]"
                 "::ParseFile('%s',[ref]$null,[ref]$e); "
                 "if ($e.Count -gt 0) { exit 1 } else { exit 0 }" % tf_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            return result.returncode == 0
        finally:
            os.unlink(tf_path)
    else:
        # Pas de verification disponible
        return True

def rapport(compteur, reponse):
    """Affiche un resume de l'operation."""
    modele = reponse.get("modele", "inconnu")
    tokens = reponse.get("tokens", 0)
    cout = reponse.get("cout", 0)
    bascule = reponse.get("bascule", False)
    print(
        f"{compteur} operation(s) appliquee(s), modele={modele}, tokens={tokens}, cout={cout}, bascule={bascule}"
    )

def main():
    parser = argparse.ArgumentParser(description="Patch automatique via nexus_agent")
    parser.add_argument("--cible", required=True, help="Chemin du fichier cible")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--consigne", help="Fichier contenant la consigne")
    group.add_argument("--consigne-texte", help="Consigne en ligne")
    parser.add_argument(
        "--modele", default="gpt-oss-120b-cloud", help="Modele a utiliser"
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=8000,
        help="Plafond de tokens (les tokens du modele sont gratuits)",
    )
    parser.add_argument(
        "--simuler",
        action="store_true",
        help="Afficher ce qui serait applique sans ecrire",
    )
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        "--triplets",
        action="store_true",
        help="Utiliser le mode triplets (ancres exactes, fragile sur les gros fichiers)",
    )
    mode_group.add_argument(
        "--fonctions",
        action="store_true",
        help="Utiliser le mode fonctions (seules les fonctions changees, "
             "robuste sur les gros fichiers .py ; voir nexus_fonctions.py)",
    )
    args = parser.parse_args()

    try:
        cible_path = args.cible
        cible_original = charger_fichier(cible_path)
        consigne = lire_consigne(args)

        # Choix du format selon le mode
        if args.fonctions:
            consigne_avec_format = ajouter_exigence_fonctions(consigne)
        elif args.triplets:
            consigne_avec_format = ajouter_exigence_triplet(consigne)
        else:
            consigne_avec_format = ajouter_exigence_fichier(consigne)

        # Appel au modele
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import nexus_agent as agent

        cle = agent.cle_maitre()
        reponse = appeler_agent(
            consigne_avec_format, cible_path, args.modele, args.max_tokens, cle
        )

        # Gestion de la troncature (c)
        if reponse.get("tronque"):
            reponse = appeler_agent(
                consigne_avec_format,
                cible_path,
                args.modele,
                args.max_tokens * 2,
                cle,
            )
            if reponse.get("tronque"):
                print("Erreur: reponse tronquee meme apres double plafond")
                sys.exit(1)

        if reponse.get("erreur"):
            print("Erreur du banc:", reponse["erreur"])
            sys.exit(2)

        texte = reponse.get("texte", "")

        if args.fonctions:
            # Mode fonctions : seules les fonctions changees sont demandees
            # et appliquees via nexus_fonctions.py (voir plus haut).
            nouveau_contenu, appliquees = appliquer_mode_fonctions(cible_original, texte)
            if nouveau_contenu is None:
                sys.exit(1)  # message d'erreur deja imprime

        elif args.triplets:
            # Mode legacy : traitement des triplets
            triplets = extraire_triplets(texte)
            if not triplets:
                print("Erreur: aucune ancre trouvee dans la reponse")
                sys.exit(1)

            nouveau_contenu = cible_original
            appliquees = 0

            for idx, triplet in enumerate(triplets, start=1):
                resultat = appliquer_triplet(nouveau_contenu, triplet, idx)
                if resultat is None:
                    premiere_ligne = triplet["anchor"].splitlines()[0]
                    print(f"Ancre inventee triplet {idx}: '{premiere_ligne}'")
                    sys.exit(1)
                nouveau_contenu = resultat
                appliquees += 1

        else:
            # Mode fichier entier
            nouveau_contenu = extraire_fichier(texte)
            if nouveau_contenu is None:
                print("Erreur: bloc @@FICHIER@@ absent dans la reponse")
                sys.exit(1)

            # Garde-fou de taille (moins de 60% des lignes originales)
            lignes_orig = len(cible_original.splitlines())
            lignes_nouv = len(nouveau_contenu.splitlines())
            if lignes_nouv < 0.6 * lignes_orig:
                print("Erreur: le fichier rendu fait moins de 60% des lignes de l'original")
                sys.exit(1)

            appliquees = 1  # une operation de remplacement complet

        # Verification syntaxe
        if not verifier_syntaxe(cible_path, nouveau_contenu):
            print("Erreur de syntaxe detectee, restauration du fichier original")
            sys.exit(1)

        # Simulation ou ecriture atomique
        if args.simuler:
            print("Simulation: aucune modification ecrite")
        else:
            ecrire_fichier_atomique(cible_path, nouveau_contenu)

        rapport(appliquees, reponse)
        sys.exit(0)

    except Exception as e:
        print("Erreur inattendue:", str(e))
        sys.exit(1)




def ajouter_exigence_fonctions(consigne):
    """
    Ajoute l'exigence de format « fonctions » (mode --fonctions) : le modele
    ne renvoie que les fonctions changees ou ajoutees, jamais le fichier
    complet, au format attendu par nexus_fonctions.py.

    Pourquoi : sur un gros fichier, le mode fichier entier (par defaut) et
    le mode triplets echouent tous deux au-dela d'environ 600 lignes -- le
    premier parce que le modele tronque ou omet une ligne loin du
    changement (le garde-fou de taille en dessous de 60% le detecte, mais
    ne le corrige pas), le second parce qu'une ancre exacte au caractere
    pres devient introuvable des que le fichier est volumineux. Demander
    uniquement les fonctions modifiees supprime la cause commune : il n'y a
    plus de texte inchange a reproduire fidelement.
    """
    exigence = (
        "\n\nRepondez UNIQUEMENT avec les fonctions modifiees ou ajoutees, "
        "jamais le fichier complet ni les fonctions inchangees. Format "
        "exact, un bloc par fonction :\n"
        "@@FONCTION nom_de_la_fonction@@\n"
        "<le corps complet de la fonction corrigee ou nouvelle, avec sa "
        "signature>\n"
        "@@FIN@@\n"
        "Pour une methode de classe, utilisez Classe.methode comme nom.\n"
    )
    return consigne.rstrip() + exigence
def appliquer_mode_fonctions(cible_original, texte):
    """
    Applique la reponse du modele au format --fonctions.

    Reutilise nexus_fonctions.py (deja present dans ce depot) pour le
    remplacement au niveau de l'AST plutot que de dupliquer cette logique :
    c'est l'unite de remplacement la plus robuste sur les gros fichiers
    disponible ici, et la dupliquer aurait cree deux implementations a
    maintenir en parallele.

    Retourne (nouveau_contenu, nb_operations) si l'application reussit,
    (None, 0) sinon (message d'erreur deja imprime, aucune exception levee
    vers l'appelant : main() attend un couple, pas une levee).
    """
    import tempfile as _tempfile
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import nexus_fonctions as fonctions_outil

    # parser_blocs() lit un fichier ; on ecrit donc la reponse du modele
    # dans un fichier temporaire plutot que de dupliquer son analyseur.
    fd, tmp_path = _tempfile.mkstemp(suffix=".blocs.txt", text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as tmp:
            tmp.write(texte)
        try:
            blocs = fonctions_outil.parser_blocs(tmp_path)
        except ValueError as e:
            print(f"Erreur: reponse --fonctions mal formee: {e}")
            return None, 0
    finally:
        os.unlink(tmp_path)

    if not blocs:
        print("Erreur: aucun bloc @@FONCTION@@ trouve dans la reponse")
        return None, 0

    lignes_cible = cible_original.splitlines(keepends=True)
    try:
        fonctions_existantes = fonctions_outil.analyser_ast(lignes_cible)
    except SyntaxError as e:
        print(f"Erreur: le fichier original ne se parse pas: {e}")
        return None, 0

    nouvelles, remplacees, ajoutees = fonctions_outil.appliquer_remplacements(
        lignes_cible, fonctions_existantes, blocs
    )
    if not remplacees and not ajoutees:
        print("Erreur: aucune fonction demandee n'a pu etre appliquee")
        return None, 0
    return "".join(nouvelles), len(remplacees) + len(ajoutees)
if __name__ == "__main__":
    sys.exit(main())
