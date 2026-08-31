# -*- coding: utf-8 -*-
"""Le resume produit par un modele local peut-il GLISSER d'une entree ?

C'est le seul defaut de ce mecanisme qui serait INVISIBLE. Si la reponse du
modele est plus courte que le lot -- ce qui arrive des qu'il tronque -- et que
l'on redistribue les lignes recues sur les entrees dans l'ordre, alors chaque
entree porte le resume d'une AUTRE. Le corpus est faux et se lit comme bon :
l'index annonce un contenu, le seek en rend un different, et rien ne signale
la discordance puisque les offsets, eux, sont exacts.

Les autres cas sont des refus francs, deja visibles. Celui-la ne l'est pas :
il merite d'etre eprouve en premier.

Le transport est BOUCHONNE : on eprouve la logique, pas le reseau. Un modele
froid ou injoignable rendrait l'epreuve rouge pour une raison sans rapport
avec ce qu'elle mesure.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import nexus_ingerer as ING  # noqa: E402

echecs = 0


def verifier(nom, condition, detail):
    global echecs
    print("  [%s] %s : %s" % ("OK  " if condition else "RATE", nom, detail))
    if not condition:
        echecs += 1


def entrees(n):
    return [{"titre": "Titre numero %d" % i, "texte": "Contenu %d" % i}
            for i in range(1, n + 1)]


def bouchon(contenu):
    """Remplace le transport par une reponse figee."""
    def faux(url, payload, timeout, cle):
        return {"choices": [{"message": {"content": contenu}}]}
    return faux


def bouchon_qui_leve(exc):
    def faux(url, payload, timeout, cle):
        raise exc
    return faux


def main():
    global echecs
    echecs = 0
    vrai = ING.appel_post
    try:
        # --- LE CAS DECISIF : reponse plus COURTE que le lot --------------
        #
        # Trois entrees, deux lignes rendues, et la ligne manquante est celle
        # du MILIEU. Une redistribution naive donnerait a l'entree 2 le resume
        # de l'entree 3.
        ING.appel_post = bouchon("1: resume un\n3: resume trois")
        e = entrees(3)
        faits, rates = ING.resumer_entrees(e, "modele-bouchon", lot=12)
        verifier("l'entree 1 garde SON resume", e[0]["resume"] == "resume un",
                 repr(e[0]["resume"]))
        verifier("l'entree 2, sans ligne, garde son TITRE",
                 e[1]["resume"] == e[1]["titre"], repr(e[1]["resume"]))
        verifier("l'entree 3 garde SON resume", e[2]["resume"] == "resume trois",
                 repr(e[2]["resume"]))
        verifier("le compte distingue produits et echecs",
                 (faits, rates) == (2, 1), "%s produits, %s echecs" % (faits, rates))

        # --- UN RESUME VIDE est refuse -----------------------------------
        ING.appel_post = bouchon("1:    \n2: vrai resume")
        e = entrees(2)
        ING.resumer_entrees(e, "modele-bouchon", lot=12)
        verifier("un resume vide est refuse, le titre reste",
                 e[0]["resume"] == e[0]["titre"], repr(e[0]["resume"]))

        # --- TABULATION ET SAUT DE LIGNE sont nettoyes -------------------
        #
        # Une tabulation dans un resume decale toutes les colonnes de l'index
        # a partir de la -- et l'index est ce qu'un petit modele lit en entier.
        ING.appel_post = bouchon("1: avec\tune tabulation")
        e = entrees(1)
        ING.resumer_entrees(e, "modele-bouchon", lot=12)
        verifier("aucune tabulation ne survit", "\t" not in e[0]["resume"],
                 repr(e[0]["resume"]))
        verifier("aucun saut de ligne ne survit", "\n" not in e[0]["resume"], "")

        # --- LE RESUME EST BORNE -----------------------------------------
        ING.appel_post = bouchon("1: " + ("x" * 400))
        e = entrees(1)
        ING.resumer_entrees(e, "modele-bouchon", lot=12)
        verifier("le resume est borne a 120 signes",
                 len(e[0]["resume"]) <= 120, "%d signes" % len(e[0]["resume"]))

        # --- UNE PANNE NE BLOQUE PAS -------------------------------------
        #
        # Un outil d'ingestion qui echoue parce qu'un modele est froid rend le
        # corpus inutilisable pour une raison sans rapport avec le corpus.
        ING.appel_post = bouchon_qui_leve(OSError("moteur injoignable"))
        e = entrees(4)
        try:
            faits, rates = ING.resumer_entrees(e, "modele-bouchon", lot=12)
            leve = False
        except Exception as exc:
            leve, faits, rates = True, -1, -1
            print("      (exception : %s)" % exc)
        verifier("une panne ne leve pas", not leve, "")
        verifier("toutes les entrees gardent leur titre",
                 all(x["resume"] == x["titre"] for x in e), "")
        verifier("la panne est COMPTEE, pas tue", rates == 4,
                 "%s echecs pour 4 entrees" % rates)

        # --- PLUSIEURS LOTS ----------------------------------------------
        #
        # La numerotation repart a 1 dans chaque lot : si elle etait globale,
        # le second lot ne trouverait aucune de ses lignes.
        ING.appel_post = bouchon("1: a\n2: b")
        e = entrees(4)
        faits, rates = ING.resumer_entrees(e, "modele-bouchon", lot=2)
        verifier("la numerotation repart a 1 a chaque lot",
                 faits == 4 and rates == 0,
                 "%s produits, %s echecs sur 2 lots de 2" % (faits, rates))
    finally:
        ING.appel_post = vrai

    print("")
    if echecs:
        print("epreuve ratee : %d cas" % echecs)
        sys.exit(1)
    print("epreuve tenue")
    sys.exit(0)


if __name__ == "__main__":
    main()
