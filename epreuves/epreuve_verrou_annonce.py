import os
import sys
import threading
import time

# Ajoute le dossier scripts au chemin de recherche des modules
dossier_scripts = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'scripts'))
sys.path.insert(0, dossier_scripts)

import nexus_verrou_machine as nvm


def epreuve_cadence():
    """Teste la fonction cadence_annonces avec les cas purs demandes."""
    cas = [
        ((0, None), False, "0s sans annonce precedente"),
        ((2, None), True, "2s sans annonce precedente"),
        ((10, 2), False, "10s avec derniere annonce a 2s"),
        ((32, 2), True, "32s avec derniere annonce a 2s"),
        ((61, 32), False, "61s avec derniere annonce a 32s"),
        ((62, 32), True, "62s avec derniere annonce a 32s"),
    ]

    for (attente, derniere), attendu, nom in cas:
        obtenu = nvm.cadence_annonces(attente, derniere)
        if obtenu == attendu:
            print(f"[OK] {nom}")
        else:
            print(f"[RATE] {nom} : attendu {attendu}, obtenu {obtenu}")
            return 1
    return 0

def epreuve_semaphore_forward():
    """Teste l'annonce forward pour un semaphore."""
    if nvm._kernel32() is None:
        print("[OK] semaphore forward : ignore : pas de kernel32")
        return 0

    liste = []
    verrou_tenu = threading.Event()

    def thread_tenant():
        with nvm.semaphore('epreuve_annonce', 1, attente_s=0, bavard=False):
            verrou_tenu.set()
            time.sleep(3)

    t = threading.Thread(target=thread_tenant)
    t.start()

    verrou_tenu.wait(timeout=1)
    if not verrou_tenu.is_set():
        print("[RATE] semaphore forward : thread tenant n'a pas pu obtenir le verrou")
        return 1

    time.sleep(0.2)
    with nvm.semaphore('epreuve_annonce', 1, attente_s=8, bavard=False, annoncer=liste.append):
        pass

    attendu = [
        "verrou epreuve_annonce tenu par un autre processus : attente...",
        "verrou epreuve_annonce obtenu apres"
    ]
    if len(liste) >= 2 and all(msg in liste[0] for msg in attendu[0].split()) and attendu[1] in liste[1]:
        print("[OK] semaphore forward")
        return 0
    print(f"[RATE] semaphore forward : messages attendus non trouves dans {liste}")
    return 1

def epreuve_semaphore_reverse():
    """Teste l'annonce reverse pour un semaphore (verrou libre)."""
    if nvm._kernel32() is None:
        print("[OK] semaphore reverse : ignore : pas de kernel32")
        return 0

    liste = []
    with nvm.semaphore('epreuve_annonce', 1, attente_s=0, bavard=False, annoncer=liste.append):
        pass

    if not liste:
        print("[OK] semaphore reverse")
        return 0
    print(f"[RATE] semaphore reverse : liste non vide {liste}")
    return 1

def epreuve_verrou_forward():
    """Teste l'annonce forward pour un verrou."""
    if nvm._kernel32() is None:
        print("[OK] verrou forward : ignore : pas de kernel32")
        return 0

    liste = []
    verrou_tenu = threading.Event()

    def thread_tenant():
        with nvm.verrou('epreuve_annonce', attente_s=0, bavard=False):
            verrou_tenu.set()
            time.sleep(3)

    t = threading.Thread(target=thread_tenant)
    t.start()

    verrou_tenu.wait(timeout=1)
    if not verrou_tenu.is_set():
        print("[RATE] verrou forward : thread tenant n'a pas pu obtenir le verrou")
        return 1

    time.sleep(0.2)
    with nvm.verrou('epreuve_annonce', attente_s=8, bavard=False, annoncer=liste.append):
        pass

    attendu = [
        "verrou epreuve_annonce tenu par un autre processus : attente...",
        "verrou epreuve_annonce obtenu apres"
    ]
    if len(liste) >= 2 and all(msg in liste[0] for msg in attendu[0].split()) and attendu[1] in liste[1]:
        print("[OK] verrou forward")
        return 0
    print(f"[RATE] verrou forward : messages attendus non trouves dans {liste}")
    return 1

def epreuve_verrou_reverse():
    """Teste l'annonce reverse pour un verrou (verrou libre)."""
    if nvm._kernel32() is None:
        print("[OK] verrou reverse : ignore : pas de kernel32")
        return 0

    liste = []
    with nvm.verrou('epreuve_annonce', attente_s=0, bavard=False, annoncer=liste.append):
        pass

    if not liste:
        print("[OK] verrou reverse")
        return 0
    print(f"[RATE] verrou reverse : liste non vide {liste}")
    return 1

def main():
    """Execute toutes les epreuves et retourne le code de sortie."""
    code = 0
    code |= epreuve_cadence()
    code |= epreuve_semaphore_forward()
    code |= epreuve_semaphore_reverse()
    code |= epreuve_verrou_forward()
    code |= epreuve_verrou_reverse()
    sys.exit(code)

if __name__ == "__main__":
    main()
