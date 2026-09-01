# -*- coding: utf-8 -*-
"""Une troncature ne doit PAS declencher les replis.

Defaut mesure par une session voisine le 2026-09-01. Une reponse vide et
tronquee n'est pas une panne du modele : c'est un budget de jetons trop
petit. Changer de modele n'y change rien, seul le budget compte.

Le code passait pourtant au candidat suivant, qui est un modele LOCAL de
20 Go. Sequence relevee sur un appel reel :

    1. gpt-oss-120b-cloud a 2500 jetons  -> TRONQUE
    2. glm-4.7-flash-local a 2500 jetons -> ~495 s
    3. reprise a 5000 -> reponse en 16,5 s

Le lanceur annoncait « 512 s au total » quand le champ `duree` du rendu
portait 16,5 : les 495 s manquantes etaient l'etape 2, qui ne pouvait pas
aboutir. Pousse plus loin, avec --max-tokens 50, la meme mecanique a tourne
25 minutes sans afficher une ligne.

L'epreuve force la troncature sur le premier candidat et verifie qu'AUCUN
second candidat n'est appele avant la reprise du plafond.
"""
import contextlib
import importlib.util
import io
import os
import sys

PLANS = {
    "gpt-oss-120b-cloud": "cloud",
    "glm-4.7-flash-local": "local",
    "deepseek-coder-33b-local": "local",
}


def _charger():
    racine = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    chemin = os.path.join(racine, "scripts", "nexus_agent.py")
    spec = importlib.util.spec_from_file_location("nexus_agent_epreuve", chemin)
    module = importlib.util.module_from_spec(spec)
    sys.modules["nexus_agent_epreuve"] = module
    spec.loader.exec_module(module)
    return module


def _essais(modele, plafond):
    """Retourne la liste des candidats REELLEMENT appeles."""
    module = _charger()
    vus = []

    def faux_appeler(*args, **kwargs):
        nom = str(args[0] if args else kwargs.get("modele", ""))
        vus.append(nom)
        # Une reponse vide et tronquee : le budget est trop petit, le modele
        # n'est pas en panne.
        return {"texte": "", "tronque": True, "tokens": 42, "adresse": "?",
                "cout": "0", "duree": 0.1}

    faux_appeler._cache_plans = dict(PLANS)
    module.appeler = faux_appeler
    with contextlib.suppress(Exception):
        module.executer({"nom": "t", "modele": modele, "tache": "peu importe",
                         "max_tokens": plafond}, "cle")
    return vus


def _dire(ok, nom, detail):
    print("%s %s : %s" % ("[OK  ]" if ok else "[RATE]", nom, detail))
    return ok


def main():
    code = 0

    # Le silence de la sortie standard n'est pas juge ici : seule compte la
    # liste des modeles appeles.
    tampon = io.StringIO()
    with contextlib.redirect_stdout(tampon):
        vus = _essais("gpt-oss-120b-cloud", 2500)
    annonce = tampon.getvalue()

    # Cas 1 : un SEUL modele distinct doit avoir ete appele avant la reprise.
    # La reprise rappelle le meme modele avec un plafond double, donc le nom
    # peut apparaitre deux fois -- mais jamais un AUTRE nom.
    distincts = []
    for nom in vus:
        if nom not in distincts:
            distincts.append(nom)
    if not _dire(len(distincts) == 1, "aucun repli sur troncature",
                 "modeles appeles : %s" % (", ".join(vus) or "aucun")):
        code = 1

    # Cas 2 : le local ne doit jamais avoir ete sollicite. C'est lui qui
    # coutait les 495 secondes.
    locaux = [n for n in distincts if PLANS.get(n) == "local"]
    if not _dire(not locaux, "le plan local n'est pas sollicite",
                 "locaux appeles : %s" % (", ".join(locaux) or "aucun")):
        code = 1

    # Cas 3 : la reprise doit avoir eu lieu, sinon le correctif aurait
    # simplement supprime le rattrapage au lieu de le rendre immediat.
    if not _dire(len(vus) >= 2, "la reprise du plafond a bien lieu",
                 "%d appel(s) au total" % len(vus)):
        code = 1

    # Cas 4 : l'attente doit etre NOMMEE. Une attente muette est
    # indiscernable d'un gel -- c'est le reproche exact de la session voisine.
    if not _dire("troncature" in annonce.lower(), "la troncature est annoncee",
                 repr(annonce.strip()[:80]) or "rien d'imprime"):
        code = 1

    return code


if __name__ == "__main__":
    sys.exit(main())
