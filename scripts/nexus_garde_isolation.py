#!/usr/bin/env python3
"""nexus_garde_isolation.py - garde PreToolUse.

Refuse tout sous-agent depeche sans arbre de travail isole. Un incident
mesure a supprime 28 456 fichiers en silence: ce geste est le seul du
depot dont l echec soit irreversible, donc toute incertitude se resout
en refusant.

Entree: un objet JSON sur stdin, par exemple
  {"tool_name": "Agent", "tool_input": {"isolation": "worktree"}}

Sortie: en cas de refus, un objet hookSpecificOutput sur stdout puis
code 2. En cas de passage, rien sur stdout et code 0.
"""

import json
import os
import sys

OUTILS_DEPECHAGE = {"Agent", "Task", "Workflow"}

REFUS_BASE = (
    "Un sous-agent depeche sans arbre de travail isole ecrirait dans "
    "l arbre vivant. La cle tool_input.isolation doit valoir exactement "
    "worktree. Si cet agent ne doit rien ecrire, lever le garde avec "
    "NEXUS_ISOLATION_LIBRE=1."
)

REFUS_WORKFLOW = (
    "L outil Workflow n expose aucun champ isolation et depeche des "
    "dizaines de sous-agents: il est refuse sans exception. "
    + REFUS_BASE
)

# Quinze cas derives du format d entree et de la table de decision.
# Les cas a 0 sont les contre-epreuves: un garde qui refuse tout, ou
# qui refuse un outil hors perimetre, doit echouer ici.
CAS_EPREUVE = [
    ("Agent sans champ isolation",
     {"tool_name": "Agent", "tool_input": {"subagent_type": "general-purpose"}}, 2),
    ("Agent avec isolation worktree",
     {"tool_name": "Agent", "tool_input": {"isolation": "worktree"}}, 0),
    ("Agent avec isolation vide",
     {"tool_name": "Agent", "tool_input": {"isolation": ""}}, 2),
    ("Agent avec isolation remote",
     {"tool_name": "Agent", "tool_input": {"isolation": "remote"}}, 2),
    ("Task sans champ isolation",
     {"tool_name": "Task", "tool_input": {"subagent_type": "general-purpose"}}, 2),
    ("Task avec isolation worktree",
     {"tool_name": "Task", "tool_input": {"isolation": "worktree"}}, 0),
    ("Workflow sans champ isolation",
     {"tool_name": "Workflow", "tool_input": {}}, 2),
    ("Workflow avec isolation worktree",
     {"tool_name": "Workflow", "tool_input": {"isolation": "worktree"}}, 2),
    ("Agent de type Explore sans isolation",
     {"tool_name": "Agent", "tool_input": {"subagent_type": "Explore"}}, 2),
    ("Outil Bash hors perimetre",
     {"tool_name": "Bash"}, 0),
    ("Outil Read hors perimetre",
     {"tool_name": "Read"}, 0),
    ("Outil Edit hors perimetre",
     {"tool_name": "Edit"}, 0),
    ("Charge lisible sans tool_name",
     {"tool_input": {"isolation": "worktree"}}, 2),
    ("Isolation a la racine hors tool_input",
     {"tool_name": "Agent", "isolation": "worktree"}, 2),
    ("Mot worktree dans le prompt sans cle isolation",
     {"tool_name": "Agent",
      "tool_input": {"prompt": "travaille dans un worktree isole"}}, 2),
]


def lire_charge(texte):
    """Parse la charge. Retourne (True, objet) si objet JSON, sinon (False, None)."""
    try:
        objet = json.loads(texte)
    except ValueError:
        return False, None
    if not isinstance(objet, dict):
        return False, None
    return True, objet


def decider(charge):
    """Applique la table de decision. Retourne (code, raison).

    Aucune exemption par subagent_type: un agent dit de lecture seule
    dispose de Bash, et un script lance depuis Bash ecrit sans qu aucun
    garde ne le voie. La chaine worktree n est acceptee que comme valeur
    de la cle exacte tool_input["isolation"].
    """
    tool_name = charge.get("tool_name")
    if tool_name is None or tool_name == "":
        return 2, "Champ tool_name absent, None ou vide. " + REFUS_BASE
    if not isinstance(tool_name, str):
        return 2, "Champ tool_name non chaine de caracteres. " + REFUS_BASE
    if tool_name not in OUTILS_DEPECHAGE:
        return 0, ""
    if tool_name == "Workflow":
        return 2, REFUS_WORKFLOW
    tool_input = charge.get("tool_input")
    if not isinstance(tool_input, dict):
        return 2, "Champ tool_input absent ou non objet. " + REFUS_BASE
    if tool_input.get("isolation") == "worktree":
        return 0, ""
    return 2, "Cle tool_input.isolation absente ou differente de worktree. " + REFUS_BASE


def refuser(raison):
    """Ecrit la decision deny sur stdout."""
    sortie = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": raison,
        }
    }
    sys.stdout.write(json.dumps(sortie) + "\n")


def executer_epreuve():
    """Joue les quinze cas. Retourne 0 si tous passent, 1 sinon."""
    rates = 0
    for libelle, charge, attendu in CAS_EPREUVE:
        ok, objet = lire_charge(json.dumps(charge))
        obtenu = 2 if not ok else decider(objet)[0]
        if obtenu == attendu:
            marqueur = "[OK  ]"
        else:
            marqueur = "[RATE]"
            rates += 1
        print("{} {} : attendu={} obtenu={}".format(marqueur, libelle, attendu, obtenu))
    return 0 if rates == 0 else 1


def main():
    # Comparaison par egalite exacte de liste, jamais par operateur in.
    arguments = sys.argv[1:]
    if arguments == ["--sonde"]:
        return 0
    if arguments == ["--epreuve"]:
        return executer_epreuve()
    if os.environ.get("NEXUS_ISOLATION_LIBRE") == "1":
        return 0
    texte = sys.stdin.read()
    if texte.strip() == "":
        refuser("Entree standard vide. " + REFUS_BASE)
        return 2
    ok, charge = lire_charge(texte)
    if not ok:
        refuser("Charge JSON invalide ou non objet. " + REFUS_BASE)
        return 2
    code, raison = decider(charge)
    if code == 0:
        return 0
    refuser(raison)
    return 2


if __name__ == '__main__':
    sys.exit(main())
