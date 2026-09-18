"""Diagnostic de l'etat de la base Postgres de la pile, a partir du journal du conteneur.

Mesure du 2026-09-18 : apres une migration de Docker vers un autre disque, la pile
a ete remontee et le conteneur litellm-db est reste unhealthy. Onze minutes ont ete
perdues a croire a une initialisation lente, parce que le journal montrait
"syncing data directory (fsync), elapsed time: 62.58 s" -- lecture plausible sur un
disque USB externe. Elle etait fausse. Le journal disait en realite :

    10:38:35  LOG:  database system is ready to accept connections
    10:38:38  FATAL:  database "litellm" does not exist

puis un redemarrage, et onze minutes de :

    FATAL:  the database system is not yet accepting connections
    DETAIL:  Consistent recovery state has not been yet reached.

L'initdb avait ete interrompu apres la creation du cluster et avant celle de la base
applicative. Le serveur demarrait, la base n'existait pas, le healthcheck echouait, et
aucune attente ne pouvait y changer quoi que ce soit. Le remede est de recreer le volume.

Le piege, en une phrase : une base interrompue pendant son initialisation ne se repare
pas en attendant, elle boucle, et chaque minute d'attente ressemble a une initialisation
lente.
"""

import argparse
import os
import subprocess
import sys

# Racine du depot : ce fichier vit dans outillage/, la racine est LE PARENT de son repertoire.
RACINE_DEPOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from console_tools import forcer_utf8
except ImportError as erreur:
    sys.stderr.write("console_tools indisponible, encodage non force : %s\n" % erreur)
else:
    forcer_utf8()


SIGNATURE_ABSENTE = "does not exist"
SIGNATURE_PRET = "ready to accept connections"
SIGNATURE_DEMARRAGE = "the database system is starting up"
SIGNATURE_RECUPERATION = "Consistent recovery state has not been yet reached"
SIGNATURE_SYNCHRO = "syncing data directory"


def diagnostiquer(lignes_journal, redemarrages):
    """Rend un couple (etat, explication) a partir des lignes du journal.

    Fonction pure, appelable sans Docker. Trois etats possibles :
    INTERROMPUE, EN_COURS, SAINE ; sinon INCONNU.
    """
    index_pret = None
    index_absent = None
    vu_demarrage = False
    vu_recuperation = False
    vu_synchro = False

    for index, ligne in enumerate(lignes_journal):
        if SIGNATURE_PRET in ligne and index_pret is None:
            index_pret = index
        if SIGNATURE_ABSENTE in ligne and index_absent is None:
            index_absent = index
        if SIGNATURE_DEMARRAGE in ligne:
            vu_demarrage = True
        if SIGNATURE_RECUPERATION in ligne:
            vu_recuperation = True
        if SIGNATURE_SYNCHRO in ligne:
            vu_synchro = True

    if index_pret is not None and index_absent is not None and index_absent > index_pret:
        return (
            "INTERROMPUE",
            "Le serveur a demarre puis a refuse une base absente : l'initialisation a ete "
            "coupee entre la creation du cluster et celle de la base applicative. "
            "Attendre ne guerit pas ce cas : il faut recreer le volume.",
        )

    if vu_demarrage or vu_recuperation or vu_synchro:
        explication = (
            "Le serveur est en cours d'initialisation ou de recuperation : l'attente est "
            "legitime, aucune signature d'echec n'a ete vue."
        )
        if redemarrages:
            explication += (
                " Attention : %d redemarrage(s) deja comptes, indice de risque a surveiller."
                % redemarrages
            )
        return ("EN_COURS", explication)

    if index_pret is not None:
        return (
            "SAINE",
            "Le serveur accepte les connexions et aucune base manquante n'a ete signalee.",
        )

    return (
        "INCONNU",
        "Aucune signature reconnue dans le journal : le diagnostic n'est pas prononcable.",
    )


def lire_journal(conteneur):
    """Lit les 200 dernieres lignes du journal du conteneur. Rend (ok, texte)."""
    try:
        resultat = subprocess.run(
            ["docker", "logs", conteneur, "--tail", "200"],
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        return (False, "docker est introuvable sur cette machine.")
    if resultat.returncode != 0:
        return (False, "docker logs a echoue pour le conteneur %s : %s"
                % (conteneur, resultat.stderr.strip()))
    return (True, resultat.stdout)


def lire_redemarrages(conteneur):
    """Lit le nombre de redemarrages du conteneur. Rend (ok, entier)."""
    try:
        resultat = subprocess.run(
            ["docker", "inspect", conteneur, "--format", "{{.RestartCount}}"],
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        return (False, 0)
    if resultat.returncode != 0:
        return (False, 0)
    try:
        return (True, int(resultat.stdout.strip()))
    except ValueError:
        return (False, 0)


def contre_epreuve():
    """Nourrit diagnostiquer() de journaux simules et verifie les trois cas."""
    cas = [
        (
            "INTERROMPUE",
            [
                "10:38:35  LOG:  database system is ready to accept connections",
                '10:38:38  FATAL:  database "litellm" does not exist',
            ],
            0,
        ),
        (
            "EN_COURS",
            ["LOG:  the database system is starting up"],
            0,
        ),
        (
            "SAINE",
            ["LOG:  database system is ready to accept connections"],
            0,
        ),
    ]

    tout_juste = True
    for attendu, lignes, redemarrages in cas:
        obtenu, _ = diagnostiquer(lignes, redemarrages)
        print("attendu : %s | obtenu : %s" % (attendu, obtenu))
        if obtenu != attendu:
            tout_juste = False

    if tout_juste:
        print("conclusion : les trois cas tombent juste.")
        return 0
    print("conclusion : au moins un cas est faux, le detecteur est suspect.")
    return 1


def main():
    analyseur = argparse.ArgumentParser(
        description="Diagnostique l'etat de la base Postgres de la pile."
    )
    analyseur.add_argument("--conteneur", default="litellm-db")
    analyseur.add_argument("--contre-epreuve", action="store_true")
    arguments = analyseur.parse_args()

    if arguments.contre_epreuve:
        return contre_epreuve()

    ok_journal, texte_journal = lire_journal(arguments.conteneur)
    if not ok_journal:
        print("mesure impossible : %s" % texte_journal)
        return 3

    ok_redemarrages, redemarrages = lire_redemarrages(arguments.conteneur)
    if not ok_redemarrages:
        print("mesure impossible : docker inspect n'a pas rendu le nombre de redemarrages.")
        return 3

    etat, explication = diagnostiquer(texte_journal.splitlines(), redemarrages)
    print("etat : %s" % etat)
    print("explication : %s" % explication)

    if etat == "SAINE":
        return 0
    if etat == "INTERROMPUE":
        return 1
    if etat == "EN_COURS":
        return 2
    return 3


if __name__ == "__main__":
    sys.exit(main())
