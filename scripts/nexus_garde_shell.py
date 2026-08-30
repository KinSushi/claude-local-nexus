#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Un heredoc shell mange les échappements du code Python qu'il porte.

LA MESURE QUI REND CE GARDE NÉCESSAIRE
--------------------------------------
Le 30 août 2026, dans une seule session de ce dépôt, le piège a frappé
QUATRE fois — dont une sur un message de commit, parti amputé de ses noms
techniques sans que rien ne le signale. La règle était écrite, récente, et
son auteur l'a enfreinte dans l'heure, une fois en documentant sa correction.

C'est la thèse du dépôt vérifiée sur son propre auteur : une règle non
mécanisée ne protège personne. Le livrable n'est pas un paragraphe, c'est un
contrôle qui refuse.

CE QUI SE PASSE EXACTEMENT
--------------------------
Le shell interprète les antislashs AVANT que Python ne voie le texte. Un
`re.compile(r"[^\\"]+")` écrit dans un heredoc arrive à Python privé de son
échappement — ou pire, la chaîne se termine là où personne ne l'a voulu.

Et `<<'EOF'` protège des SUBSTITUTIONS de variables, **pas** des échappements
consommés par l'analyseur de la commande. C'est ce qui rend le piège tenace :
la parade évidente ne marche pas, et l'erreur ressemble à une faute de frappe.

CE QU'IL REFUSE
---------------
Uniquement deux conjonctions, jamais davantage :

  A. un heredoc Python **et** un antislash dans son corps ;
  B. un accent grave non échappé **à l'intérieur de guillemets doubles**.

Sans antislash, aucun échappement ne peut être mangé : rien à refuser. Un
garde qui refuserait tous les heredocs serait désarmé le jour de sa pose.

CE QU'IL NE VOIT PAS
--------------------
Un script lancé par `python outil.py` : la commande ne porte pas le code. Un
heredoc `bash` ou `node`. Un antislash qui traverse sans dommage. Ces faux
positifs sont assumés — le coût d'un faux positif est une seconde, celui d'un
faux négatif une commande perdue, et l'un des quatre du 30 août était un
commit.

ÉPROUVÉ : 8 cas sur 8 — les deux refus attendus, et six autorisations
(heredoc sans antislash, accent grave entre guillemets simples, accent grave
échappé, commande ordinaire, heredoc bash, outil autre que Bash).

PROVENANCE, ET UN SECOND JET REJETÉ. La logique de détection vient du banc
(`gpt-oss-120b-cloud`, 2873 jetons) et est reprise ICI TELLE QUELLE, parce
qu'elle a passé les huit cas. Un second appel, qui ne demandait que trois
ajouts en gardant la logique identique, a rendu un script qui : ne lisait
plus le JSON du hook mais l'entrée brute, refusait tout heredoc quoté portant
un antislash, cherchait les accents graves dans le corps des heredocs au lieu
des guillemets doubles, et sortait en code 1 sur stderr au lieu d'imprimer un
refus et de rendre 0. Il détruisait un jet éprouvé. Demander une retouche à
un modèle peut coûter ce qui marchait : c'est pourquoi l'arbitrage garde le
dernier mot, et pourquoi l'épreuve précède l'intégration.
"""
import json
import re
import sys


def lire_entree():
    """Toute anomalie rend un dictionnaire vide, donc autorise en silence."""
    try:
        return json.loads(sys.stdin.read())
    except Exception:
        return {}


def refuser(motif):
    try:
        sys.stdout.write(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": motif,
        }}, ensure_ascii=False))
    except Exception:
        pass
    sys.exit(0)


def detecter_cas_a(commande):
    """
    Heredoc Python portant un antislash dans son corps.

    Le heredoc est reconnu Python par son delimiteur (« PYEOF », « PY »...)
    ou par la presence de « python » avant le « << ». On n'examine QUE le
    corps : un antislash dans la ligne d'ouverture ne sera pas mange.
    """
    lignes = commande.splitlines()
    for i, ligne in enumerate(lignes):
        m = re.search(r'<<\s*([\'"]?)(\S+)\1', ligne)
        if not m:
            continue
        delimiteur = m.group(2)
        avant = ligne[:m.start()]
        if "py" not in delimiteur.lower() and "python" not in avant.lower():
            continue
        corps = []
        for suite in lignes[i + 1:]:
            if suite.strip() == delimiteur:
                break
            corps.append(suite)
        if "\\" in "\n".join(corps):
            return True
    return False


def detecter_cas_b(commande):
    """
    Accent grave non echappe a l'interieur de guillemets DOUBLES.

    Entre guillemets doubles, le shell execute ce qui est entre accents
    graves et REMPLACE le tout par sa sortie : un message de commit citant du
    code perd donc silencieusement ses noms techniques. Entre guillemets
    SIMPLES, rien n'est substitue -- refuser la serait un faux positif pur.
    """
    dans_double = dans_simple = echappe = False
    for c in commande:
        if echappe:
            echappe = False
            continue
        if c == "\\":
            echappe = True
            continue
        if c == '"' and not dans_simple:
            dans_double = not dans_double
            continue
        if c == "'" and not dans_double:
            dans_simple = not dans_simple
            continue
        if dans_double and c == "`":
            return True
    return False


def main():
    donnees = lire_entree()
    if not isinstance(donnees, dict):
        return
    if donnees.get("tool_name") != "Bash":
        return
    entree = donnees.get("tool_input")
    entree = entree if isinstance(entree, dict) else {}
    commande = entree.get("command")
    if not isinstance(commande, str) or not commande:
        return

    if detecter_cas_a(commande):
        refuser(
            "CAS A -- heredoc Python portant un antislash. Le shell le "
            "consomme AVANT que Python ne voie le texte, et le code arrive "
            "mutile : une expression reguliere perd son echappement, ou la "
            "chaine se termine ou personne ne l'a voulu. Le quotage "
            "<<'EOF' n'y change rien : il protege des variables, pas des "
            "echappements. REMEDE : ecrire le fichier avec l'outil Write, "
            "puis l'executer.")

    if detecter_cas_b(commande):
        refuser(
            "CAS B -- accent grave non echappe entre guillemets doubles. Le "
            "shell execute ce qu'il entoure et REMPLACE le tout par sa "
            "sortie : un message de commit citant du code part ampute de ses "
            "noms techniques, sans que rien ne le signale. Arrive ici le "
            "2026-08-30. REMEDE : passer le texte par un fichier (-F "
            "fichier) plutot qu'en ligne de commande.")


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except BaseException:
        # Rempart final, absent du jet du banc : detecter_cas_a et
        # detecter_cas_b peuvent lever sur une entree inattendue, et un garde
        # qui plante empeche de travailler -- pire que le defaut surveille.
        pass
    sys.exit(0)
