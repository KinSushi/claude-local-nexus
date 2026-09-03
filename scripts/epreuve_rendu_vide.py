"""Epreuve de l'outil nexus_epreuve_vide.py : refuse-t-il proprement sans
argument, et DETECTE-t-il une epreuve muette quand on lui en donne un ?

Defaut mesure le 2026-09-02 : nexus_test.py appelait l'outil lui-meme par
jouer_epreuve_python, donc SANS ARGUMENT, et en attendant des lignes
« [OK  ] » / « [RATE] » que cet outil n'a jamais parlees. Resultat, mesure
par `nexus_test.py --only vide` :

    [FAIL] rendu vide    aucun cas rendu par l'epreuve (code 2)

Un rouge PERMANENT : une ligne de la suite qui ne pouvait passer dans aucun
etat du depot, et qui ne prouvait donc rien -- ni en rouge ni en vert. Lui
donner un argument n'aurait rien change : l'outil rend des lignes de signal
et un code de sortie, pas le contrat de la suite. L'outil, lui, refusait
proprement (code 2, usage nommant <path>, aucun effet de bord) : la faute
etait chez l'APPELANT. Cette epreuve est l'appelant qui manquait. Elle
fabrique des epreuves dans un repertoire temporaire, les donne a l'outil, et
traduit ses codes de sortie dans le contrat de la suite.

Cinq cas, tous sur des fichiers fabriques -- jamais sur scripts/, dont le
verdict reel n'est pas l'objet ici :

    refus sans argument   code 2, usage sur stderr, rien sur stdout, et rien
                          d'ecrit dans le repertoire courant
    temoin positif        une epreuve muette est SIGNALEE, code 1 -- sans lui,
                          un outil devenu aveugle passerait pour sain
    epreuve saine         une epreuve qui lance et compare passe, code 0
    epreuve cassee        une erreur de syntaxe est un signal, pas un crash
    fichier hors motif    un script qui n'est pas « epreuve*.py » est ignore

Sortie non nulle des qu'un cas echoue. Pas d'epreuve de fuite : l'outil ne
touche ni au reseau ni a aucun plan, il ne fait que lire des sources.
"""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
OUTIL = RACINE / "scripts" / "nexus_epreuve_vide.py"

# Une epreuve qui ne lance rien, n'importe rien, et ne peut pas echouer.
MUETTE = 'print("bonjour")\n'
# Une epreuve qui lance un sous-processus ET compare son resultat. L'outil
# ne l'EXECUTE pas, il la lit : le contenu n'a donc qu'a etre analysable.
SAINE = (
    "import subprocess\n"
    "import sys\n"
    'r = subprocess.run([sys.executable, "-c", "pass"])\n'
    "if r.returncode != 0:\n"
    '    print("[RATE] cas : code", r.returncode)\n'
)
CASSEE = "def (\n"

echecs = 0


def cas(nom: str, condition: bool, detail: str) -> None:
    global echecs
    print("[%s] %s : %s" % ("OK  " if condition else "RATE", nom, detail))
    if not condition:
        echecs += 1


def lancer(arguments, cwd) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(OUTIL)] + [str(a) for a in arguments],
        cwd=cwd, capture_output=True, text=True, encoding="utf-8",
        errors="replace", timeout=60)


def dossier(base: str, nom: str, fichier: str = "", contenu: str = "") -> str:
    """Un sous-repertoire propre par cas : l'outil parcourt recursivement."""
    chemin = os.path.join(base, nom)
    os.mkdir(chemin)
    if fichier:
        with open(os.path.join(chemin, fichier), "w", encoding="utf-8") as fh:
            fh.write(contenu)
    return chemin


def resume(r: subprocess.CompletedProcess) -> str:
    return "code %s, stdout=%r, stderr=%r" % (
        r.returncode, (r.stdout or "").strip()[:70],
        (r.stderr or "").strip()[:70])


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if not OUTIL.is_file():
        print("[RATE] outil introuvable : %s" % OUTIL)
        return 1

    with tempfile.TemporaryDirectory(prefix="epreuve_rendu_vide_") as tmp:
        # 1. Sans argument : refus propre, au sens du contrat 0.1.4.1 --
        #    code non nul, message nommant la voie, aucun effet de bord.
        vide = dossier(tmp, "sans_argument")
        r = lancer([], cwd=vide)
        cas("refus sans argument",
            r.returncode == 2
            and "Usage" in (r.stderr or "") and "<path>" in (r.stderr or "")
            and not (r.stdout or "").strip()
            and not os.listdir(vide),
            resume(r) + ", cree=%s" % os.listdir(vide))

        # 2. Temoin positif : une epreuve muette DOIT etre signalee. C'est le
        #    cas qui distingue un outil qui detecte d'un outil qui se tait.
        muette = dossier(tmp, "muette", "epreuve_muette.py", MUETTE)
        r = lancer([muette], cwd=tmp)
        sortie = r.stdout or ""
        cas("temoin positif : epreuve muette signalee",
            r.returncode == 1
            and "epreuve_muette.py" in sortie
            and "does not launch anything" in sortie
            and "cannot fail" in sortie
            and "SIGNAL" in sortie,
            resume(r))

        # 3. Chemin nominal : une epreuve qui lance et compare passe.
        saine = dossier(tmp, "saine", "epreuve_saine.py", SAINE)
        r = lancer([saine], cwd=tmp)
        cas("epreuve saine acceptee",
            r.returncode == 0 and not (r.stdout or "").strip(),
            resume(r))

        # 4. Une epreuve illisible est un signal, pas un plantage : le
        #    fichier est nomme sur stdout, et aucune trace Python ne sort.
        cassee = dossier(tmp, "cassee", "epreuve_cassee.py", CASSEE)
        r = lancer([cassee], cwd=tmp)
        cas("epreuve cassee signalee sans plantage",
            r.returncode == 1
            and "epreuve_cassee.py" in (r.stdout or "")
            and "syntax error" in (r.stdout or "")
            and "Traceback" not in (r.stderr or ""),
            resume(r))

        # 5. L'outil ne juge que les « epreuve*.py » : un script de
        #    production muet n'est pas son affaire.
        hors = dossier(tmp, "hors_motif", "outil.py", MUETTE)
        r = lancer([hors], cwd=tmp)
        cas("fichier hors motif ignore",
            r.returncode == 0 and not (r.stdout or "").strip(),
            resume(r))

    if echecs > 0:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
