"""
Épreuve de la fonction `purger_orphelins` (outillage/nexus_veille_moteur.py).

Contexte (2026‑09‑14) : un incident où taskkill était utilisé sans l’option /T,
laissant 4 processus orphelins consommer 68 Go de mémoire.  
L’objectif de l’épreuve est de vérifier les trois comportements attendus :

* **forward** : un processus cible sans parent vivant est détecté et terminé.
* **reverse** : le parent du processus cible est vivant → aucun terme.
* **fuite** : une erreur lors de l’énumération est gérée sans exception.

Le test injecte un faux module (via l’argument `module`) qui implémente les
fonctions attendues : `enumerer()`, `orphelins(table, cible)` et `_terminer(pid)`.
Le faux module enregistre les PID passés à `_terminer` dans l’attribut
`termines` afin de pouvoir les vérifier.
"""

import importlib.util
import os
import sys

# --------------------------------------------------------------------------- #
# Chargement de la fonction cible depuis le dépôt
# --------------------------------------------------------------------------- #
racine = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
module_path = os.path.join(racine, 'outillage', 'nexus_veille_moteur.py')
spec = importlib.util.spec_from_file_location('nexus_veille_moteur', module_path)
nexus_veille_moteur = importlib.util.module_from_spec(spec)
spec.loader.exec_module(nexus_veille_moteur)   # charge le module sans effets de bord

purger_orphelins = nexus_veille_moteur.purger_orphelins


# --------------------------------------------------------------------------- #
# Faux module d’instrumentation
# --------------------------------------------------------------------------- #
class FauxModule:
    """Imite le module attendu par `purger_orphelins`."""
    def __init__(self):
        self.termines = []          # PID qui ont été passés à _terminer

    def enumerer(self):
        """Doit être remplacée dans chaque scénario de test."""
        raise NotImplementedError

    def orphelins(self, table, cible):
        """Filtre les entrées dont le nom correspond à `cible` et dont le parent
        n’est pas présent dans `table`. Implémentation générique."""
        pids = {p['pid'] for p in table}
        return [
            p for p in table
            if p['nom'] == cible and p['ppid'] not in pids
        ]

    def _terminer(self, pid):
        """Enregistre le PID au lieu de le tuer réellement."""
        self.termines.append(pid)


# --------------------------------------------------------------------------- #
# Outil de vérification
# --------------------------------------------------------------------------- #
def check(nom, condition, detail=""):
    """
    Affiche le résultat d'un test au format attendu par `outillage/nexus_test.py`.

    - Si `condition` est vraie, imprime ``[OK  ] <nom> : <detail>``.
    - Sinon, imprime ``[RATE] <nom> : <detail>``.
    Retourne la valeur booléenne de `condition`.
    """
    if condition:
        print(f"[OK  ] {nom} : {detail}")
    else:
        print(f"[RATE] {nom} : {detail}")
    return condition


# --------------------------------------------------------------------------- #
# Scénarios de test
# --------------------------------------------------------------------------- #
def test_forward():
    """Processus cible sans parent → doit être terminé."""
    fake = FauxModule()

    def enumerer():
        return [{
            'pid': 30000,
            'ppid': 99999,          # PID inexistant dans la table
            'nom': 'llama-server.exe',
            'prive_octets': 21500000000,
            'debut': 0,
        }]
    fake.enumerer = enumerer

    result = purger_orphelins(cible='llama-server.exe', module=fake)

    ok1 = check(
        "forward/result",
        result == [{'pid': 30000, 'prive_octets': 21500000000}],
        "Le processus orphelin doit être retourné"
    )
    ok2 = check(
        "forward/termines",
        30000 in fake.termines,
        "_terminer doit avoir été appelé avec le PID 30000"
    )
    return ok1 and ok2


def test_reverse():
    """Parent vivant → aucun processus ne doit être terminé."""
    fake = FauxModule()

    def enumerer():
        return [
            {'pid': 1000, 'ppid': 0, 'nom': 'parent.exe',
             'prive_octets': 0, 'debut': 0},
            {'pid': 30001, 'ppid': 1000, 'nom': 'llama-server.exe',
             'prive_octets': 123456789, 'debut': 0},
        ]
    fake.enumerer = enumerer

    result = purger_orphelins(cible='llama-server.exe', module=fake)

    ok1 = check(
        "reverse/result",
        result == [],
        "Aucun orphelin ne doit être détecté"
    )
    ok2 = check(
        "reverse/termines",
        fake.termines == [],
        "_terminer ne doit pas être appelé"
    )
    return ok1 and ok2


def test_fuite():
    """Erreur d’énumération → doit être gérée silencieusement."""
    fake = FauxModule()

    def enumerer():
        raise RuntimeError("Impossible d’interroger le système")
    fake.enumerer = enumerer

    result = purger_orphelins(cible='llama-server.exe', module=fake)

    ok1 = check(
        "fuite/result",
        result == [],
        "En cas d’erreur, la fonction doit renvoyer []"
    )
    ok2 = check(
        "fuite/termines",
        fake.termines == [],
        "Aucun appel à _terminer ne doit être fait"
    )
    return ok1 and ok2


# --------------------------------------------------------------------------- #
# Exécution autonome
# --------------------------------------------------------------------------- #
def main():
    ok = True
    ok = test_forward() and ok
    ok = test_reverse() and ok
    ok = test_fuite() and ok
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
