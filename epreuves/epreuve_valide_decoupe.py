#!/usr/bin/env python3
"""
Cas de test pour la decoupe des diffs dans nexus_valide.py
"""

import os
import sys
from unittest import mock

# Ajout du dossier scripts au chemin de recherche des modules
SCRIPTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts")
sys.path.insert(0, SCRIPTS_DIR)
import nexus_valide


def forward_1():
    """Diff de trois fichiers dont le total depasse DEFAULT_MAX_TOKENS*4 mais chaque fichier tient"""
    diff_text = (
        "diff --git a/f1 b/f1\n" + "a\n" * 7000 +
        "diff --git a/f2 b/f2\n" + "b\n" * 7000 +
        "diff --git a/f3 b/f3\n" + "c\n" * 7000
    )
    # Le total depasse DEFAULT_MAX_TOKENS*4 (8000*4=32000, 3*7000*2=42000)
    # Chaque fichier tient dans DEFAULT_MAX_TOKENS*4 (7000*2=14000 < 32000)

    with mock.patch.object(nexus_valide.agent, 'executer') as mock_executer, \
         mock.patch.object(nexus_valide.agent, 'cle_maitre') as mock_cle:
        mock_cle.return_value = "fake_key"
        mock_executer.return_value = {
            "texte": "VERDICT_FINAL: RAS",
            "modele": "faux",
            "plan": "cloud",
            "tokens": 1
        }

        try:
            nexus_valide.free_plan_judgment(diff_text, {})
        except Exception as e:
            print(f"[RATE] forward_1 : exception inattendue {e}")
            return False

        if mock_executer.call_count != 3:
            print(f"[RATE] forward_1 : executer appele {mock_executer.call_count} fois au lieu de 3")
            return False

        # Verifier que les appels contiennent bien 3 morceaux
        args_list = mock_executer.call_args_list
        if len(args_list) != 3:
            print(f"[RATE] forward_1 : nombre d'appels incorrect {len(args_list)}")
            return False

        for i, call_args in enumerate(args_list):
            tache = call_args[0][0]
            if f"diff --git a/f{i+1}" not in tache["tache"]:
                print(f"[RATE] forward_1 : morceau {i} ne contient pas le fichier attendu")
                return False

        return True

def forward_2():
    """Diff d'un seul fichier qui depasse le plafond"""
    diff_text = "diff --git a/f1 b/f1\n" + "x\n" * 35000  # 35000*2 > 32000

    with mock.patch.object(nexus_valide.agent, 'executer') as mock_executer:
        try:
            nexus_valide.free_plan_judgment(diff_text, {})
            print("[RATE] forward_2 : aucune exception levee")
            return False
        except RuntimeError as e:
            if "morceau trop grand" not in str(e):
                print(f"[RATE] forward_2 : message d'erreur incorrect '{e}'")
                return False
            if mock_executer.call_count != 0:
                print(f"[RATE] forward_2 : executer appele {mock_executer.call_count} fois")
                return False
            return True
        except Exception as e:
            print(f"[RATE] forward_2 : exception inattendue {e}")
            return False

def forward_3():
    """_split_diff_by_file remplace par une fonction qui compte ses appels et rend [texte[:-1]]"""
    diff_text = "diff --git a/f1 b/f1\n" + "x\n" * 35000  # Depasse le plafond

    call_count = 0

    def mock_split(text):
        nonlocal call_count
        call_count += 1
        return [text[:-1]]  # Retourne une liste avec le texte tronque d'un caractere

    with mock.patch.object(nexus_valide, '_split_diff_by_file', side_effect=mock_split), \
         mock.patch.object(nexus_valide.agent, 'executer'):
        try:
            nexus_valide.free_plan_judgment(diff_text, {})
            print("[RATE] forward_3 : aucune exception levee")
            return False
        except RuntimeError as e:
            if "morceau trop grand" not in str(e):
                print(f"[RATE] forward_3 : message d'erreur incorrect '{e}'")
                return False
            if call_count > nexus_valide.PALIERS_MAX_DECOUPE + 1:
                print(f"[RATE] forward_3 : nombre d'appels {call_count} depasse PALIERS_MAX_DECOUPE + 1 ({nexus_valide.PALIERS_MAX_DECOUPE + 1})")
                return False
            return True
        except Exception as e:
            print(f"[RATE] forward_3 : exception inattendue {e}")
            return False

def contre_epreuve():
    """Meme remplacant, PALIERS_MAX_DECOUPE remplace par 100000, sys.setrecursionlimit(200)"""
    diff_text = "diff --git a/f1 b/f1\n" + "x\n" * 35000

    call_count = 0

    def mock_split(text):
        nonlocal call_count
        call_count += 1
        return [text[:-1]]

    original_limit = sys.getrecursionlimit()
    try:
        sys.setrecursionlimit(200)
        with mock.patch.object(nexus_valide, '_split_diff_by_file', side_effect=mock_split), \
             mock.patch.object(nexus_valide, 'PALIERS_MAX_DECOUPE', 100000), \
             mock.patch.object(nexus_valide.agent, 'executer'):
            try:
                nexus_valide.free_plan_judgment(diff_text, {})
                print("[RATE] contre-epreuve : aucune exception levee")
                return False
            except RecursionError:
                return True
            except Exception as e:
                print(f"[RATE] contre-epreuve : exception inattendue {e}")
                return False
    finally:
        sys.setrecursionlimit(original_limit)

def lancer_tests():
    """Lance tous les cas de test et affiche les resultats"""
    tests = [
        ("forward_1", forward_1),
        ("forward_2", forward_2),
        ("forward_3", forward_3),
        ("contre-epreuve", contre_epreuve),
    ]

    tous_reussis = True
    for nom, test_func in tests:
        try:
            resultat = test_func()
            if resultat:
                print(f"[OK] {nom}")
            else:
                tous_reussis = False
        except Exception as e:
            print(f"[RATE] {nom} : exception non geree {e}")
            tous_reussis = False

    sys.exit(0 if tous_reussis else 1)

if __name__ == "__main__":
    lancer_tests()
