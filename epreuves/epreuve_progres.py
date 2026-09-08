# -*- coding: utf-8 -*-
"""Epreuve de nexus_progres.py : le generateur de PROGRESS.MD fait-il ce qu'il annonce ?

CE QUI ETAIT FAUX, mesure le 2026-09-02 en JOUANT l'epreuve plutot qu'en la
lisant. L'ancienne version ne pouvait jamais passer, pour quatre raisons
independantes, chacune suffisante :

  * elle cherchait `PROGRES.MD` dans un repertoire temporaire, alors que le
    generateur ecrit `PROGRESS.MD` a la racine du depot ou il est POSE (racine
    derivee de __file__) -- « Fichier PROGRES.MD non genere » a chaque
    execution, et le vrai PROGRESS.MD du depot reecrit au passage ;
  * elle exigeait un echec « sans depot git », la ou le generateur DEGRADE
    volontairement (« Git non disponible ») et rend 0 -- contrat §0.5 :
    degrader, jamais planter, quand le depot est absent ;
  * elle exigeait a la fois un succes sans argument (cas nominal) et un echec
    sans argument (cas usage) : deux cas contradictoires, l'un rougit toujours ;
  * elle imprimait `[OK_NOMINAL]` et `[ECHEC_...]`, que nexus_test.py ne lit
    pas -- il n'accepte que « [OK  ] nom : detail » et « [RATE] ... ». Meme
    verte, elle aurait ete comptee « aucun cas rendu ».

Resultat mesure dans la suite, avant correction :
    [FAIL] progres    aucun cas rendu par l'epreuve (code 1)
-- une epreuve cablee (nexus_test.py, cle « progres »), jouee a chaque passe
complete, et qui ne prouvait rien.

Ce que cette version fait : elle COPIE le generateur dans un depot jetable (il
derive sa racine de __file__, donc il y ecrit son PROGRESS.MD sans toucher au
depot reel), joue le chemin nominal, le chemin degrade, une checklist
malformee, et une CONTRE-EPREUVE ou le verificateur doit rougir sur un
PROGRESS.MD ampute d'une rubrique -- un controle qui ne peut pas rougir ne
prouve rien (contrat §0.1.4.1).
"""
import os
import shutil
import subprocess
import sys
import tempfile

# Duree accordee a UNE generation. Jugement de conception, pas une mesure du
# generateur seul : sa rubrique TACHES PLANIFIEES interroge le planificateur
# Windows (Get-ScheduledTask, ~200 taches sur cet hote), et le commit f364f40
# mesure une generation complete a 13,7 s. L'ancienne valeur, 10 s, etait nue
# et pouvait expirer sur une machine chargee -- une expiration se lisait
# alors comme un defaut du generateur.
DELAI_S = 120

ICI = os.path.dirname(os.path.abspath(__file__))
GENERATEUR = os.path.join(os.path.dirname(ICI), "outillage", "nexus_progres.py")

# Les rubriques que nexus_progres.py ecrit, dans son ordre. « *GENERE
# AUTOMATIQUEMENT le » est le debut reel de sa ligne d'horodatage ;
# l'ancienne epreuve cherchait « *GENERE AUTOMATIQUEMENT* », qui n'y est pas.
RUBRIQUES = (
    "# PROGRESS.MD",
    "*GENERE AUTOMATIQUEMENT le",
    "## ETAT DU DEPOT",
    "## MECANISMES",
    "## SUJETS OUVERTS",
    "## TACHES PLANIFIEES",
    "## CE QUI N'EST PAS MECANISE",
)

echecs = 0


def verifier(nom, condition, detail):
    global echecs
    if condition:
        print("  [OK  ] %s : %s" % (nom, detail))
    else:
        print("  [RATE] %s : %s" % (nom, detail))
        echecs += 1


def depot_jetable(avec_git, checklist=None):
    """Un depot minimal : le generateur COPIE sous scripts/, et rien d'autre.

    Le generateur ecrit a la racine du depot ou il est pose : c'est cette
    copie qui isole l'epreuve du depot reel (contrat §0.4 : une copie, jamais
    la source)."""
    racine = tempfile.mkdtemp(prefix="epreuve_progres_")
    # créer les dossiers requis avant la copie du générateur
    os.makedirs(os.path.join(racine, "scripts"))
    os.makedirs(os.path.join(racine, "outillage"))
    shutil.copy(GENERATEUR, os.path.join(racine, "outillage", "nexus_progres.py"))
    if checklist is not None:
        os.makedirs(os.path.join(racine, "outillage", "rituels"))
        with open(os.path.join(racine, "outillage", "rituels", "CHECKLIST_COCKPIT.MD"),
                  "w", encoding="utf-8") as f:
            f.write(checklist)
    if avec_git:
        env = dict(os.environ, GIT_AUTHOR_NAME="epreuve", GIT_AUTHOR_EMAIL="e@x",
                   GIT_COMMITTER_NAME="epreuve", GIT_COMMITTER_EMAIL="e@x")
        for cmd in (["git", "init", "-q"],
                    ["git", "commit", "-q", "--allow-empty", "-m", "initial"]):
            r = subprocess.run(cmd, cwd=racine, capture_output=True, text=True,
                               encoding="utf-8", errors="replace", timeout=60,
                               env=env)
            if r.returncode != 0:
                shutil.rmtree(racine, ignore_errors=True)
                raise RuntimeError("git indisponible : %s"
                                   % (r.stderr or "").strip()[:80])
    return racine


def generer(racine):
    """Joue le generateur copie ; rend (code, contenu de PROGRESS.MD ou None)."""
    r = subprocess.run(
        [sys.executable, os.path.join(racine, "outillage", "nexus_progres.py")],
        cwd=racine, capture_output=True, text=True, encoding="utf-8",
        errors="replace", timeout=DELAI_S)
    chemin = os.path.join(racine, "PROGRESS.MD")
    contenu = None
    if os.path.isfile(chemin):
        with open(chemin, encoding="utf-8") as f:
            contenu = f.read()
    return r.returncode, contenu


def rubriques_manquantes(contenu):
    return [r for r in RUBRIQUES if r not in (contenu or "")]


def cas_nominal():
    # Deux lignes de tableau sous un titre portant « ouvert », une sous un
    # titre qui ne le porte pas : le compte attendu est 2, et il prouve le
    # filtre sur le titre autant que le comptage.
    checklist = ("# Cockpit\n\n## OUVERTS ACTUELS\n\n| 1 | a |\n| 2 | b |\n\n"
                 "## Ferme\n\n| 9 | c |\n")
    try:
        racine = depot_jetable(avec_git=True, checklist=checklist)
    except RuntimeError as exc:
        # Un cas qui ne peut pas se jouer n'est pas un succes.
        verifier("NOMINAL", False, str(exc))
        return
    try:
        code, contenu = generer(racine)
        manquantes = rubriques_manquantes(contenu)
        verifier("NOMINAL", code == 0 and contenu is not None and not manquantes,
                 "code %s, PROGRESS.MD %s, rubriques manquantes : %s"
                 % (code, "ecrit" if contenu is not None else "ABSENT",
                    ", ".join(manquantes) if manquantes else "aucune"))
        verifier("NOMINAL git lu",
                 contenu is not None and "- Branche : " in contenu
                 and "Git non disponible" not in contenu,
                 "la branche est lue quand le depot existe")
        verifier("NOMINAL sujets comptes",
                 contenu is not None and "- Sujets ouverts : 2" in contenu,
                 "2 lignes sous un titre « ouvert », 1 sous un titre ferme -> 2")
    finally:
        shutil.rmtree(racine, ignore_errors=True)


def cas_sans_depot():
    racine = depot_jetable(avec_git=False)
    try:
        sonde = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=racine,
                               capture_output=True, text=True, timeout=60)
        if sonde.returncode == 0:
            # Le repertoire temporaire est lui-meme sous un depot : le cas
            # ne se joue pas ici, et le dire vaut mieux qu'un vert.
            verifier("SANS_DEPOT degrade", False,
                     "injouable : le repertoire temporaire est sous un depot git")
            return
        code, contenu = generer(racine)
        verifier("SANS_DEPOT degrade",
                 code == 0 and contenu is not None
                 and "Git non disponible" in contenu,
                 "code %s ; le generateur DEGRADE et le dit, il ne plante pas" % code)
    finally:
        shutil.rmtree(racine, ignore_errors=True)


def cas_checklist_malformee():
    racine = depot_jetable(avec_git=False, checklist="Contenu malforme sans sections")
    try:
        code, contenu = generer(racine)
        verifier("CHECKLIST_MALFORMEE",
                 code == 0 and contenu is not None
                 and "- Sujets ouverts : 0" in contenu
                 and "CHECKLIST_COCKPIT.MD introuvable" not in contenu,
                 "code %s ; fichier present sans section : 0 sujet, jamais « introuvable »"
                 % code)
    finally:
        shutil.rmtree(racine, ignore_errors=True)


def contre_epreuve():
    """Le verificateur rougit-il sur un PROGRESS.MD ampute ?"""
    complet = "\n".join(RUBRIQUES) + " 2026-09-02\n"
    ampute = complet.replace("## MECANISMES\n", "")
    verifier("CONTRE-EPREUVE complet", not rubriques_manquantes(complet),
             "un document portant toutes les rubriques passe")
    verifier("CONTRE-EPREUVE ampute",
             rubriques_manquantes(ampute) == ["## MECANISMES"],
             "la rubrique retiree est nommee : %s" % rubriques_manquantes(ampute))


def main():
    if not os.path.isfile(GENERATEUR):
        print("  [RATE] source : %s introuvable" % GENERATEUR)
        return 1
    for cas in (cas_nominal, cas_sans_depot, cas_checklist_malformee, contre_epreuve):
        try:
            cas()
        except Exception as exc:
            # Une exception est un echec NOMME, jamais un silence.
            verifier(cas.__name__, False, "%s : %s" % (type(exc).__name__, str(exc)[:80]))
    return 1 if echecs else 0


if __name__ == "__main__":
    sys.exit(main())
