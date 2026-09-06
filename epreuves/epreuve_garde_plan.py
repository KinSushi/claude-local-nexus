# -*- coding: utf-8 -*-
"""
Le garde refuse-t-il un plan paye, et laisse-t-il passer le gratuit ?

Six cas, dont deux contre-epreuves. Le garde est exerce comme le hook
l'exerce : un JSON sur stdin, un JSON eventuel sur stdout, et surtout un
code de sortie, qui DISTINGUE deux choses longtemps confondues ici :
un garde ne doit jamais PLANTER (anomalie -> 0), mais un refus DOIT
sortir en 2, sans quoi il s'affiche sans rien bloquer. La confusion
des deux est ce qui a laisse passer 460 sous-agents factures --
travailler, ce qui est pire que le defaut surveille.
"""
import json, os, subprocess, sys

GARDE = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "nexus_garde_agent.py")

echecs = 0


def verifier(nom, condition, detail):
    global echecs
    print("[%s] %s : %s" % ("OK  " if condition else "RATE", nom, detail))
    if not condition:
        echecs += 1


def appeler(charge, env_libre=False):
    env = dict(os.environ)
    env.pop("NEXUS_AGENT_LIBRE", None)
    if env_libre:
        env["NEXUS_AGENT_LIBRE"] = "1"
    r = subprocess.run([sys.executable, GARDE], input=json.dumps(charge),
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=60, env=env)
    refuse = '"permissionDecision": "deny"' in (r.stdout or "") \
        or '"permissionDecision":"deny"' in (r.stdout or "")
    return refuse, (r.stdout or ""), r.returncode


def jouer() -> int:
    # 1. LE CAS QUI A COUTE 32 MILLIONS DE JETONS : un Workflow qui lance des
    # agents haiku, sans aucune justification.
    refuse, sortie, code = appeler({
        "tool_name": "Workflow",
        "tool_input": {"script": "agent('fais ceci', { model: 'haiku' })"},
    })
    verifier("Workflow lancant du haiku sans justification => REFUS", refuse,
             (sortie.strip()[:90] or "aucune sortie"))
    # LE CAS QUI AVAIT TOUT FAUX. Il exigeait « code == 0 » sur un REFUS, au
    # nom de « un garde ne doit jamais planter ». Il a donc valide, huit fois
    # de suite, un garde qui imprimait « deny » et sortait 0 -- c'est-a-dire
    # qui n'empechait rien. Le protocole du depot fait du code 2 le refus ;
    # le JSON n'en porte que le motif.
    verifier("un REFUS sort en 2, sans quoi il ne bloque rien", code == 2,
             "code=%s" % code)

    # 2. CONTRE-EPREUVE : c'est bien le PLAN qui declenche, pas le mot Workflow.
    refuse, sortie, _ = appeler({
        "tool_name": "Workflow",
        "tool_input": {"script": "agent('fais ceci')"},
    })
    verifier("Workflow sans model: nomme => laisse passer", not refuse,
             "aucun plan paye demande")

    # 3. La justification explicite ouvre la porte, et doit etre citee.
    refuse, sortie, _ = appeler({
        "tool_name": "Workflow",
        "tool_input": {"script": "// NEXUS_JUSTIFIE_PAYANT arbitrage final, "
                                 "aucun modele gratuit ne tient le protocole\n"
                                 "agent('x', { model: 'opus' })"},
    })
    verifier("une justification explicite laisse passer", not refuse,
             "NEXUS_JUSTIFIE_PAYANT honore")

    # 4. La sortie de secours par variable d'environnement.
    refuse, sortie, _ = appeler({
        "tool_name": "Workflow",
        "tool_input": {"script": "agent('x', { model: 'sonnet' })"},
    }, env_libre=True)
    verifier("NEXUS_AGENT_LIBRE=1 laisse passer", not refuse,
             "sortie de secours honoree")

    # 5. Le refus doit NOMMER L'ISSUE, pas seulement la fermeture. Regle de ce
    # depot, payee plusieurs fois : un garde qui refuse sans dire par ou passer
    # se fait contourner, ou renoncer.
    refuse, sortie, _ = appeler({
        "tool_name": "Workflow",
        "tool_input": {"script": "agent('x', { model: 'haiku' })"},
    })
    issue = ("nexus_agent" in sortie or "nexus_ask" in sortie
             or "NEXUS_JUSTIFIE_PAYANT" in sortie)
    verifier("le refus nomme l'issue, pas seulement la fermeture", refuse and issue,
             "issue citee" if issue else sortie.strip()[:90])

    # 6. LE GARDE N'ECHOUE JAMAIS. Une charge illisible autorise en silence.
    for nom, charge_brute in (("JSON invalide", "{ ceci n'est pas du json"),
                              ("stdin vide", "")):
        r = subprocess.run([sys.executable, GARDE], input=charge_brute,
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=60)
        verifier("%s => silence et code 0" % nom,
                 r.returncode == 0 and not r.stdout.strip(),
                 "code=%s sortie=%r" % (r.returncode, (r.stdout or "")[:40]))

    print("-" * 66)
    print("VERDICT : %s" % ("epreuve tenue" if echecs == 0 else "%d echec(s)" % echecs))
    return 1 if echecs else 0

if __name__ == "__main__":
    # RIEN NE S'EXECUTE A L'IMPORT.
    #
    # Ce fichier lancait ses cas au niveau du module : `controle_imports` l'a
    # bloque, et a juste titre. Un import qui AGIT transforme le fait de
    # charger un module en action, si bien qu'un outil qui inspecte le depot
    # le modifierait en l'inspectant.
    sys.exit(jouer())
