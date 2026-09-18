"""Epreuve de validation de la mesure, pour scripts/nexus_valide.py.

Trois defauts constates a l usage, aucun par relecture :

1. L outil JUGEAIT le diff par un modele au lieu de MESURER. Il a rendu trois
   fausses regressions alors que l epreuve concernee figurait dans le diff et
   passait. Mesure ensuite : sur un depot ou une epreuve etait cassee, le
   modele ne voyait rien. Le faux negatif est donc possible aussi.
2. Le refus de verrou annoncait le PID de l instance courante au lieu de celui
   du detenteur, envoyant chercher un processus qui n avait rien bloque.
3. La prise de verrou echouait quand le dossier parent manquait, et l appelant
   en concluait qu un verrou etait detenu alors que rien ne l etait. Ce dossier
   etant ignore par git, l outil etait inutilisable depuis un arbre neuf.

Un outil qui juge sans mesurer peut se tromper dans les deux sens, et c est le
faux negatif qui coute le plus cher.
"""

import importlib.util
import os
import shutil
import sys
import tempfile

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTILLAGE = os.path.join(RACINE, "outillage")

sys.path.insert(0, OUTILLAGE)
try:
    from console_tools import forcer_utf8

    forcer_utf8()
except Exception as raison:  # noqa: BLE001
    sys.stderr.write("garde d encodage indisponible : %s\n" % (raison,))


def _charger_module():
    """Charge scripts/nexus_valide.py par son chemin, sans effet de bord."""
    chemin = os.path.join(RACINE, "scripts", "nexus_valide.py")
    spec = importlib.util.spec_from_file_location("nexus_valide_eprouve", chemin)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _ecrire_script(dossier, nom, code_sortie):
    """Ecrit un script Python minimal qui sort avec le code demande."""
    chemin = os.path.join(dossier, nom)
    with open(chemin, "w", encoding="utf-8") as flux:
        flux.write("import sys\nsys.exit(%d)\n" % (code_sortie,))
    return chemin


def _verdict(nom, attendu, obtenu, juste):
    """Imprime attendu, obtenu et verdict pour un cas."""
    print("CAS %s" % (nom,))
    print("  attendu : %s" % (attendu,))
    print("  obtenu  : %s" % (obtenu,))
    print("  verdict : %s" % ("OK" if juste else "ECHEC",))
    print("%s %s : %s" % ("[OK  ]" if juste else "[RATE]", nom, obtenu))
    return juste


def cas_1_perimetre(module):
    """Le filtre du perimetre retient les epreuves Python, tout separateur."""
    melange = [
        os.path.join("epreuves", "alpha.py"),
        "epreuves\\beta.py",
        os.path.join("scripts", "hors_perimetre.py"),
        os.path.join("epreuves", "notes.txt"),
    ]
    obtenu = module.epreuves_du_perimetre(melange)
    attendu = [os.path.join("epreuves", "alpha.py"), "epreuves\\beta.py"]
    juste = sorted(obtenu) == sorted(attendu)
    return _verdict(
        "1 perimetre",
        "les deux epreuves Python seulement : %s" % (attendu,),
        obtenu,
        juste,
    )


def cas_2_mesure_impossible(module):
    """Une mesure impossible n est pas une mesure favorable."""
    fantome = os.path.join(RACINE, "epreuves", "epreuve_qui_n_existe_pas.py")
    mesures = module.lancer_epreuves([fantome])
    if not mesures:
        return _verdict(
            "2 mesure impossible",
            "un code non nul ET concluante a faux",
            "aucune mesure rendue",
            False,
        )
    mesure = mesures[0]
    code = mesure.get("code_sortie")
    concluante = mesure.get("concluante")
    juste = code != 0 and concluante is False
    return _verdict(
        "2 mesure impossible",
        "un code non nul ET concluante a faux",
        "code_sortie=%r concluante=%r" % (code, concluante),
        juste,
    )


def cas_3_echec_visible(module):
    """Une epreuve qui echoue est vue comme telle, une qui passe aussi."""
    dossier = tempfile.mkdtemp(prefix="epreuve_valide_")
    try:
        echec = _ecrire_script(dossier, "echoue.py", 1)
        succes = _ecrire_script(dossier, "passe.py", 0)
        mesures_echec = module.lancer_epreuves([echec])
        mesures_succes = module.lancer_epreuves([succes])
        code_echec = mesures_echec[0].get("code_sortie") if mesures_echec else None
        code_succes = mesures_succes[0].get("code_sortie") if mesures_succes else None
        juste = code_echec == 1 and code_succes == 0
        return _verdict(
            "3 echec visible",
            "code 1 pour le script qui echoue, code 0 pour celui qui passe",
            "echec=%r succes=%r" % (code_echec, code_succes),
            juste,
        )
    finally:
        shutil.rmtree(dossier, ignore_errors=True)


def cas_4_silence_interdit(module):
    """Le silence sur la mesure est interdit : zero epreuve doit se dire."""
    etat = module._etat_de_la_mesure([], [])
    texte = etat if isinstance(etat, str) else str(etat)
    marque = "aucune epreuve"
    juste = marque in texte.lower()
    return _verdict(
        "4 silence interdit",
        "la chaine dit clairement qu aucune epreuve n a ete mesuree",
        texte,
        juste,
    )


def cas_5_verrou_dossier_absent(module):
    """Le verrou se prend meme si le dossier parent n existe pas."""
    racine_temp = tempfile.mkdtemp(prefix="verrou_valide_")
    try:
        dossier_absent = os.path.join(racine_temp, "sous_dossier_absent")
        chemin_verrou = os.path.join(dossier_absent, "verrou.lock")
        pris = module.prendre_verrou(chemin_verrou, os.getpid())
        existe = os.path.exists(chemin_verrou)
        juste = pris is True and existe
        return _verdict(
            "5 verrou dossier absent",
            "prendre_verrou rend vrai ET le fichier existe ensuite",
            "pris=%r fichier_existe=%r" % (pris, existe),
            juste,
        )
    finally:
        shutil.rmtree(racine_temp, ignore_errors=True)


def principal():
    """Execute les cinq cas et rend le code de sortie global."""
    try:
        module = _charger_module()
    except Exception as raison:  # noqa: BLE001
        sys.stderr.write("chargement du module eprouve impossible : %s\n" % (raison,))
        return 1

    attendues = (
        "epreuves_du_perimetre",
        "lancer_epreuves",
        "_etat_de_la_mesure",
        "prendre_verrou",
    )
    manquantes = [nom for nom in attendues if getattr(module, nom, None) is None]
    if manquantes:
        print(
            "[RATE] absence du correctif : fonctions manquantes %s"
            % (", ".join(manquantes),)
        )
        sys.stderr.write(
            "correctif du 2026-09-18 absent de ce code : fonctions manquantes %s\n"
            % (", ".join(manquantes),)
        )
        return 1

    resultats = [
        cas_1_perimetre(module),
        cas_2_mesure_impossible(module),
        cas_3_echec_visible(module),
        cas_4_silence_interdit(module),
        cas_5_verrou_dossier_absent(module),
    ]
    reussis = sum(1 for resultat in resultats if resultat)
    total = len(resultats)
    print("")
    print("conclusion : %d cas reussis sur %d" % (reussis, total))
    return 0 if reussis == total else 1


if __name__ == "__main__":
    sys.exit(principal())
