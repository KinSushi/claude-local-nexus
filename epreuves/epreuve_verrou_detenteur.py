import os
import sys
import tempfile
import json
import shutil
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

import nexus_verrou_machine as nvm


def test_purs(dossier):
    fiche = nvm.fiche_detenteur('Banc', 'projet_test', 123, '2026-09-14T10:00:00')
    cles_attendues = {'classe', 'projet', 'pid', 'depuis', 'hote'}
    if set(fiche.keys()) != cles_attendues:
        return False, "fiche_detenteur n'a pas les 5 cles attendues"

    if not nvm.chemin_fiche(dossier, 'Banc').endswith('banc.json'):
        return False, "chemin_fiche(d, 'Banc') ne se termine pas par banc.json"
    if not nvm.chemin_fiche(dossier, 'inference', 2).endswith('inference_2.json'):
        return False, "chemin_fiche(d, 'inference', 2) ne se termine pas par inference_2.json"

    pid_courant = os.getpid()
    fiche = nvm.fiche_detenteur('Banc', 'projet_test', pid_courant, '2026-09-14T10:00:00')
    chemin = nvm.chemin_fiche(dossier, 'Banc')
    nvm.ecrire_fiche(chemin, fiche)
    info = nvm.detenteur(dossier, 'Banc')
    if info is None:
        return False, "detenteur retourne None apres ecrire_fiche"
    if info.get('pid') != pid_courant or not info.get('vivant'):
        return False, "detenteur ne retourne pas le bon pid ou vivant False"

    fiche_orpheline = {
        "classe": "Banc",
        "projet": "projet_test",
        "pid": 999999,
        "depuis": "2026-09-14T10:00:00",
        "hote": "test"
    }
    chemin_orphelin = nvm.chemin_fiche(dossier, 'Banc')
    with open(chemin_orphelin, 'w', encoding='utf-8') as f:
        json.dump(fiche_orpheline, f)
    info = nvm.detenteur(dossier, 'Banc')
    if info is None or not info.get('orpheline'):
        return False, "detenteur ne signale pas l'orpheline pour pid 999999"

    nvm.effacer_fiche(chemin_orphelin)
    info = nvm.detenteur(dossier, 'Banc')
    if info is not None:
        return False, "detenteur ne retourne pas None apres effacer_fiche"

    return True, ""


def test_forward_windows(dossier):
    if nvm._kernel32() is None:
        print("[OK] forward Windows (ignore)")
        return True, ""
    with mock.patch.object(nvm, 'RACINE_VERROUS', dossier):
        with nvm.verrou('epreuve_detenteur', bavard=False):
            chemin = nvm.chemin_fiche(dossier, 'epreuve_detenteur')
            if not os.path.exists(chemin):
                return False, "la fiche epreuve_detenteur.json n'existe pas pendant le with"
        if os.path.exists(chemin):
            return False, "la fiche epreuve_detenteur.json existe encore apres le with"

        with nvm.semaphore('epreuve_detenteur', 1, bavard=False):
            chemin = nvm.chemin_fiche(dossier, 'epreuve_detenteur', slot=0)
            if not os.path.exists(chemin):
                return False, "la fiche epreuve_detenteur_0.json n'existe pas pendant le with"
        if os.path.exists(chemin):
            return False, "la fiche epreuve_detenteur_0.json existe encore apres le with"

    return True, ""


def main():
    dossier = tempfile.mkdtemp()
    try:
        ok, cause = test_purs(dossier)
        if not ok:
            print(f"[RATE] tests purs : {cause}")
            return 1
        print("[OK] tests purs")

        ok, cause = test_forward_windows(dossier)
        if not ok:
            print(f"[RATE] forward Windows : {cause}")
            return 1
        if nvm._kernel32() is not None:
            print("[OK] forward Windows")
    finally:
        shutil.rmtree(dossier, ignore_errors=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
