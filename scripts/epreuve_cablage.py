# -*- coding: utf-8 -*-
"""
Pourquoi cette épreuve existe ?

Le mécanisme de classification « câblage » du dépôt (module
`scripts/nexus_cablage.py`) a classé une épreuve réellement jouée par
`nexus_test.py` comme « prouvée, connectée à rien », ce qui a été compté en
régression. Le contrat impose que seules les épreuves réellement
exécutées soient considérées comme « câblées », sinon le mécanisme est
puni. Cette dérogation restreinte garantit que :

* un script de production cité uniquement par un test reste « preuve_seule »,
* une épreuve mentionnée en commentaire mais jamais invoquée reste
  « preuve_seule »,
* une épreuve qui n’est nommée nulle part reste « orphelin ».

Les cas 1, 3 et 4 assurent que la dérogation ne s’étend pas aux vraies
épreuves jouées (cas 2). Cette épreuve vérifie donc que `classer()` se
comporte exactement comme attendu pour ces quatre scénarios.
"""
import os
import sys

# Ajout du répertoire du script au PATH afin d’importer nexus_cablage
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nexus_cablage

echecs = 0


def verifier(nom, condition, detail):
    """Affiche le résultat d’un test et incrémente le compteur d’échecs."""
    global echecs
    print("[{}] {} : {}".format("OK  " if condition else "RATE", nom, detail))
    if not condition:
        echecs += 1


def jouer() -> int:
    """Exécute les quatre cas de test décrits dans la docstring."""
    # Cas 1 – Production citée uniquement par un test → preuve_seule
    cible = "scripts/machin_production.py"
    textes = {
        "scripts/nexus_test.py": (
            'subprocess.run([sys.executable, "scripts/machin_production.py"])'
        )
    }
    cat, citants = nexus_cablage.classer(cible, textes)
    verifier(
        "Cas 1 – production citée uniquement",
        cat == "preuve_seule",
        "cat={}; citants={}".format(cat, citants),
    )

    # Cas 2 – Épreuve réellement jouée → cable
    cible = "scripts/epreuve_bidon.py"
    textes = {
        "scripts/nexus_test.py": (
            'subprocess.run([sys.executable, "scripts/epreuve_bidon.py"])'
        )
    }
    cat, citants = nexus_cablage.classer(cible, textes)
    verifier(
        "Cas 2 – épreuve réellement jouée",
        cat == "cable",
        "cat={}; citants={}".format(cat, citants),
    )

    # Cas 3 – Épreuve mentionnée en commentaire uniquement → preuve_seule
    cible = "scripts/epreuve_bidon.py"
    textes = {
        "scripts/rien.py": "# epreuve_bidon.py est mentionnee en commentaire"
    }
    cat, citants = nexus_cablage.classer(cible, textes)
    verifier(
        "Cas 3 – mention en commentaire seulement",
        cat == "preuve_seule",
        "cat={}; citants={}".format(cat, citants),
    )

    # Cas 4 – Épreuve orpheline (aucune référence) → orphelin
    cible = "scripts/epreuve_bidon.py"
    textes = {}
    cat, citants = nexus_cablage.classer(cible, textes)
    verifier(
        "Cas 4 – épreuve orpheline",
        cat == "orphelin",
        "cat={}; citants={}".format(cat, citants),
    )

    print("-" * 66)

    # ------------------------------------------------------------------
    # CAS 5 a 8 — UN IMPORT CREUX N'EST PAS UN CABLAGE.
    #
    # Un module Python s'importe SANS son extension, si bien que le cliquet,
    # qui compare le nom AVEC extension, declarait ORPHELIN tout module
    # pourtant importe -- mesure : console_tools.py, importe par nexus_doc.py
    # dans le commit qui le cree.
    #
    # Mais reconnaitre l'import ouvre aussitot un piege, nomme par une session
    # voisine a l'instant ou il etait ouvert :
    #     from models.gguf_vram import estimate_gguf_vram_mb  # noqa: F401
    # `noqa: F401` dit « import inutilise », et le corps ne l'appelle jamais.
    # Un tel import ferait passer le module d'orphelin a cable SANS que le
    # produit change. Le chiffre bouge, rien n'est joint. Le compte est
    # necessaire, il n'est pas suffisant.
    creux = "from machin import truc  # noqa: F401\n\ndef rien():\n    return 0\n"
    verifier("Cas 5 - import creux (noqa F401) ne cable pas",
             nexus_cablage._import_reellement_employe("machin", creux) is False,
             "refuse")

    employe = "from machin import truc\n\ndef ok():\n    return truc(1)\n"
    verifier("Cas 6 - import employe cable",
             nexus_cablage._import_reellement_employe("machin", employe) is True,
             "accepte")

    prefixe = "import machin\n\ndef ok():\n    return machin.faire()\n"
    verifier("Cas 7 - module employe par prefixe cable",
             nexus_cablage._import_reellement_employe("machin", prefixe) is True,
             "accepte")

    nu = "import machin\n\ndef rien():\n    return 0\n"
    verifier("Cas 8 - import jamais employe ne cable pas",
             nexus_cablage._import_reellement_employe("machin", nu) is False,
             "refuse")

    print("VERDICT : {}"
          .format("épreuve tenue" if echecs == 0 else "{} échec(s)".format(echecs)))
    return 1 if echecs else 0


if __name__ == "__main__":
    # RIEN NE S'EXÉCUTE À L'IMPORT.
    sys.exit(jouer())
