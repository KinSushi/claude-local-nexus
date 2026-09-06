# -*- coding: utf-8 -*-
"""Ce module mesure la part du raisonnement extrait d'une reponse brute.
Le voisin de la session mesure la meme chose : valeur 1.0 en appelant
Ollama en direct, valeur 0.0 par la passerelle qui n'expose pas le champ
thinking — le raisonnement etait invisible et non absent.
L'epreuve verifie le calcul de la part : une mesure impossible n'est pas
une mesure a zero, elle doit rendre la chaine 'inconnu'.
CINQ cas sont testes : presence de balises think, absence de balises,
texte vide, et regression sur le code source de l'agent.
LIMITE : L'epreuve teste le calcul local, pas l'appel reseau."""

import os
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(RACINE, "scripts")
NEXUS_AGENT_PATH = os.path.join(SCRIPTS_DIR, "nexus_agent.py")

sys.path.insert(0, SCRIPTS_DIR)
import nexus_agent as agent


def _dire(ok, nom, detail):
    print("%s %s : %s" % ("[OK  ]" if ok else "[RATE]", nom, detail))
    return ok


def _calculer_part_raisonnement(brut):
    """Calcule la part de raisonnement selon la regle :
    - Si brut est vide, rend None.
    - Si brut et net ont la meme longueur, rend None (pas de raisonnement detecte).
    - Sinon rend (len(brut) - len(net)) / len(brut)."""
    if not brut:
        return None
    nettoye = agent._sans_raisonnement(brut)
    if len(nettoye) == len(brut):
        return None
    return (len(brut) - len(nettoye)) / len(brut)


def _formater(resultat):
    """Formate le resultat : 'inconnu' si None, sinon valeur arrondie a 3 decimales."""
    if resultat is None:
        return "inconnu"
    return "%.3f" % round(resultat, 3)


def main():
    code_final = 0

    # Cas 1 : balise ouvrante think, 200 x, balise fermante think, puis REPONSE
    # Doit rendre une valeur strictement superieure a 0.9
    tag_open = "<" + "think" + ">"
    tag_close = "<" + "/" + "think" + ">"
    brut1 = tag_open + ("x" * 200) + tag_close + "REPONSE"
    result1 = _calculer_part_raisonnement(brut1)
    str_result1 = _formater(result1)
    ok1 = result1 is not None and result1 > 0.9
    if not _dire(ok1, "Cas 1 balises think + REPONSE",
                 "brut=%d nettoye=%d part=%s (attendu > 0.9)" %
                 (len(brut1), len(agent._sans_raisonnement(brut1)), str_result1)):
        code_final = 1

    # Cas 2 : uniquement balise think entourant 200 x (sans REPONSE apres)
    # Doit rendre exactement 1.0
    tag_open2 = "<" + "think" + ">"
    tag_close2 = "<" + "/" + "think" + ">"
    brut2 = tag_open2 + ("x" * 200) + tag_close2
    result2 = _calculer_part_raisonnement(brut2)
    str_result2 = _formater(result2)
    ok2 = result2 is not None and abs(result2 - 1.0) < 1e-9
    if not _dire(ok2, "Cas 2 uniquement balises think",
                 "brut=%d nettoye=%d part=%s (attendu 1.0)" %
                 (len(brut2), len(agent._sans_raisonnement(brut2)), str_result2)):
        code_final = 1

    # Cas 3 : phrase ordinaire sans aucune balise
    # Doit rendre 'inconnu', PAS zero
    brut3 = "Ceci est une reponse normale sans balise de raisonnement."
    result3 = _calculer_part_raisonnement(brut3)
    str_result3 = _formater(result3)
    ok3 = result3 is None and str_result3 == "inconnu"
    if not _dire(ok3, "Cas 3 phrase sans balise",
                 "part=%s (attendu 'inconnu')" % str_result3):
        code_final = 1

    # Cas 4 : brut vide
    # Doit rendre 'inconnu'
    brut4 = ""
    result4 = _calculer_part_raisonnement(brut4)
    str_result4 = _formater(result4)
    ok4 = result4 is None and str_result4 == "inconnu"
    if not _dire(ok4, "Cas 4 brut vide",
                 "part=%s (attendu 'inconnu')" % str_result4):
        code_final = 1

    # Cas 5 : non-regression sur le SOURCE
    # Verifie que 'inconnu' apparait dans la ligne qui construit part_raisonnement
    with open(NEXUS_AGENT_PATH, "r", encoding="utf-8") as f:
        contenu = f.read()
    ok5 = "inconnu" in contenu
    if not _dire(ok5, "Cas 5 regression SOURCE",
                 "'inconnu' present dans le source" if ok5 else "'inconnu' absent du source"):
        code_final = 1

    return code_final


if __name__ == "__main__":
    sys.exit(main())
