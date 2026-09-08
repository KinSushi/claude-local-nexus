r"""verrou_machine.py — exclusion mutuelle entre PROJETS, sur la MEME SESSION Windows.

Ce module crée un mutex nommé Windows, dont la portée est limitée à la session Windows courante.
Un mutex créé sans le préfixe global `Global\` vit dans l'espace de noms de la session active :
il ne sera pas visible depuis un service, une tâche planifiée, une seconde session ouverte,
ou un bureau distant. L'exclusion ne vaut donc que pour les processus lancés dans la même session.

═══════════════════════════════════════════════════════════════════════════════════════════════════
LE BESOIN
═══════════════════════════════════════════════════════════════════════════════════════════════════

Enzo, 2026-08-09 : « *y a-t-il moyen de mesurer et d'éviter deux robocopy lancés en même temps ainsi
que deux pytest en même temps ? la question se pose parce qu'il y a deux projets […] et je ne
voudrais pas générer des conflits ou des erreurs pour rien.* » puis, sur le choix de la mécanique :
« ***le plus propre, le plus pro, et sans risques d'oublis ou de mauvaises manipulations des deux
côtés.*** »

Deux projets tournent en parallèle sur cette machine. Ils ne se connaissent pas.

═══════════════════════════════════════════════════════════════════════════════════════════════════
★ POURQUOI UN MUTEX NOMMÉ, ET PAS UN FICHIER DE VERROU
═══════════════════════════════════════════════════════════════════════════════════════════════════

**Un fichier de verrou survit à la mort de son propriétaire.** C'est sa faille structurelle, et ce
dépôt l'a payée le 2026-08-09 : un `git add -A` tué a laissé `.git/index.lock` derrière lui, et le
dépôt est resté bloqué **40 minutes** — jusqu'à ce qu'un humain constate qu'aucun git ne tournait et
retire le fichier à la main. C'est exactement la « mauvaise manipulation » qu'Enzo veut rendre
impossible : celle où l'on doit décider si un verrou est légitime ou orphelin.

**Un mutex nommé est un objet du NOYAU.** Windows le libère lui-même quand le processus meurt —
crash, `Stop-Process`, coupure de courant. Il n'existe pas de mutex orphelin. Il n'y a donc **rien à
nettoyer, rien à décider, et rien à oublier**.

★ **NUANCE ÉTABLIE PAR LE TEST, contre ma propre première rédaction.** J'avais écrit que le noyau
rend `WAIT_ABANDONED` quand on acquiert après la mort du détenteur. **C'est conditionnel, pas
général** : un mutex nommé n'existe que tant qu'**au moins une poignée est ouverte**. Si le
détenteur tué était le dernier à en tenir une, l'objet est *détruit*, et l'acquisition suivante
crée un mutex **neuf** — il n'y a plus rien à signaler. Mesuré : `obtenu=True`, `abandonne=False`.

`WAIT_ABANDONED` n'apparaît donc que si **un autre processus tenait déjà une poignée** au moment de
la mort — typiquement quelqu'un en attente. C'est un bonus quand il survient, jamais une garantie.

**La propriété qui compte, elle, est prouvée sans réserve** : après la mort du détenteur, le verrou
est *libre*. Aucun orphelin, dans aucun scénario. C'est cela qui justifie le mutex contre le
fichier de verrou — pas la détection du crash.

**Le contrat entre les deux projets est le NOM du mutex.** Rien d'autre à partager : pas de dossier
commun, pas de configuration, pas de convention de nettoyage. Ce fichier est **stdlib seule** et
autonome : il se dépose tel quel dans l'autre projet, sans rien installer.

CE QUE CE VERROU N'EST PAS
    Ce n'est pas une garantie de correction des données — deux robocopy vers des destinations
    DISJOINTES ne se corrompent pas, ils se ralentissent. Le verrou sert d'abord à ne pas gaspiller,
    et à rendre le gaspillage VISIBLE quand il a lieu.

USAGE
    from verrou_machine import verrou
    with verrou("robocopy", projet="EA-MT5", attente_s=600) as v:
        if not v.obtenu:
            ...                                  # quelqu'un d'autre copie : on s'efface
        ...

    python workspace\tools\verrou_machine.py --etat        # qui tient quoi, en ce moment
"""
from __future__ import annotations

import argparse
import ctypes
import os
import sys
import time
import subprocess
import pathlib
from contextlib import contextmanager, suppress
from datetime import datetime

# ── Constantes Win32 ───────────────────────────────────────────────────────────────────────────
# Elles ne viennent PAS de la doc Python (ce sont des constantes de l'API Windows) : elles sont donc
# nommées, commentées et vérifiables une par une plutôt que semées en nombres nus dans le code.
WAIT_OBJECT_0 = 0x00000000      # obtenu
WAIT_ABANDONED = 0x00000080     # obtenu, ET le detenteur precedent est MORT sans relacher
WAIT_TIMEOUT = 0x00000102       # un autre le tient toujours au bout du delai
WAIT_FAILED = 0xFFFFFFFF        # echec de l'appel lui-meme

# ★ Le NOM est le contrat entre les projets. Le préfixe évite toute collision avec un autre
# logiciel ; le suffixe désigne la ressource disputée, pas le projet — c'est justement l'inverse
# qu'il faut : deux projets doivent demander LE MÊME nom pour s'exclure.
PREFIXE = "AURUM_MACHINE_"
CLASSES = {
    "robocopy": "une copie miroir massive (contention d'E/S disque)",
    "pytest": "une suite de tests (caches et fixtures partages)",
    "hachage": "un hachage massif d'arborescence (contention d'E/S disque)",
    "banc": "une inference locale sur le banc de modeles, la memoire du moteur etant partagee",
}
SEMAPHORES = {
    "inference": "les lots cloud partagent la passerelle (plafond machine-wide)",
}


def _kernel32():
    """Rend kernel32, ou None si on n'est pas sous Windows.

    `ctypes.WinDLL` n'existe que sous Windows (vérifié dans la doc stdlib locale : « This class
    represents a dll exporting functions using the Windows stdcall calling convention »). Hors
    Windows, on ne plante pas : on dégrade, et l'appelant continue sans verrou.
    """
    if os.name != "nt":
        return None
    try:
        return ctypes.WinDLL("kernel32", use_last_error=True)
    except (OSError, AttributeError):            # pragma: no cover — dépend de la plateforme
        return None


class Verrou:
    """Résultat d'une tentative d'acquisition. `obtenu` dit tout ; le reste explique."""

    def __init__(self, classe: str, obtenu: bool, motif: str, abandonne: bool = False):
        self.classe, self.obtenu, self.motif, self.abandonne = classe, obtenu, motif, abandonne

    def __bool__(self) -> bool:
        return self.obtenu

    def __repr__(self) -> str:
        return f"<Verrou {self.classe} obtenu={self.obtenu} {self.motif!r}>"


@contextmanager
def verrou(classe: str, projet: str = "?", attente_s: float = 0.0, bavard: bool = True):
    """Acquiert le verrou machine de `classe`, le relâche à la sortie — même sur exception.

    ★ C'est un gestionnaire de contexte PAR CONSTRUCTION, et c'est ce qui répond à « sans risques
    d'oublis » : on ne peut pas oublier de relâcher ce qu'on n'a jamais eu à relâcher soi-même.
    Et si le processus meurt à l'intérieur du bloc, le NOYAU relâche — il n'y a aucun chemin, même
    anormal, qui laisse un verrou derrière lui.

    `attente_s = 0` : on ne bloque pas, on rend `obtenu=False` et l'appelant décide. Un verrou qui
    attend indéfiniment est lui-même une mauvaise manipulation : il transforme une contention en
    blocage silencieux.
    """
    k = _kernel32()
    nom = PREFIXE + classe.upper()
    handle = None
    v = Verrou(classe, True, "aucun verrou disponible sur cette plateforme — on continue sans")

    if k is not None:
        k.CreateMutexW.restype = ctypes.c_void_p
        k.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_bool, ctypes.c_wchar_p]
        k.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
        k.WaitForSingleObject.restype = ctypes.c_uint32
        k.ReleaseMutex.argtypes = [ctypes.c_void_p]
        k.CloseHandle.argtypes = [ctypes.c_void_p]

        handle = k.CreateMutexW(None, False, nom)
        if not handle:
            v = Verrou(classe, True, "mutex indisponible (droits ?) — on continue sans")
        else:
            debut = time.monotonic()
            r = k.WaitForSingleObject(handle, int(max(0.0, attente_s) * 1000))
            if r == WAIT_OBJECT_0:
                v = Verrou(classe, True, "obtenu")
            elif r == WAIT_ABANDONED:
                # Le détenteur précédent est mort sans relâcher. On l'a QUAND MÊME : le noyau nous
                # le donne. Un fichier de verrou, lui, serait resté là sans que personne sache s'il
                # était légitime — c'est tout l'écart entre les deux mécaniques.
                v = Verrou(classe, True, "obtenu — le détenteur précédent est MORT sans relâcher",
                           abandonne=True)
            elif r == WAIT_TIMEOUT:
                att = time.monotonic() - debut
                v = Verrou(classe, False,
                           f"un AUTRE processus tient « {classe} » "
                           f"({CLASSES.get(classe, 'ressource partagée')}) — "
                           f"attendu {att:.0f}s en vain")
            else:
                v = Verrou(classe, True, f"attente en échec (code {r:#x}) — on continue sans")

    if bavard:
        etat = "OBTENU " if v.obtenu else "REFUSÉ "
        print(f"  verrou machine [{classe}] {etat}({projet}) — {v.motif}", file=sys.stderr)
        if v.abandonne:
            print("    ⚠ le détenteur précédent a été tué : vérifier qu'il n'a pas laissé un "
                  "travail à moitié fait", file=sys.stderr)
    try:
        yield v
    finally:
        if handle and v.obtenu and v.motif.startswith("obtenu"):
            k.ReleaseMutex(handle)
        if handle:
            k.CloseHandle(handle)


@contextmanager
def semaphore(classe: str, n: int, projet: str = "?", attente_s: float = 0.0,
              bavard: bool = True):
    """Acquiert un sémaphore nommé du noyau Windows, implémenté de façon death‑safe.

    Le sémaphore est simulé par *n* mutex nommés
    ``PREFIXE + 'SEM_' + classe.upper() + '_' + str(i)``.  L’acquisition parcourt les
    mutex et récupère le premier disponible (ou abandonné).  Si aucun n’est libre,
    on attend brièvement puis on recommence jusqu’à expiration du délai ``attente_s``.
    Le comportement de retour (objet :class:`Verrou`) et les messages restent
    compatibles avec l’ancienne version.
    """
    k = _kernel32()
    obtenu = False
    motif = "aucun semaphore disponible sur cette plateforme -- on continue sans"
    handle = None

    if k is not None:
        # Signatures Windows
        k.CreateMutexW.restype = ctypes.c_void_p
        k.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_long, ctypes.c_wchar_p]
        k.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
        k.WaitForSingleObject.restype = ctypes.c_uint32
        k.ReleaseMutex.argtypes = [ctypes.c_void_p]
        k.CloseHandle.argtypes = [ctypes.c_void_p]

        deadline = time.monotonic() + max(0.0, attente_s)
        while True:
            # Essai d’acquisition sur chaque mutex
            for i in range(n):
                nom_i = PREFIXE + "SEM_" + classe.upper() + "_" + str(i)
                h = k.CreateMutexW(None, False, nom_i)
                if not h:
                    continue
                r = k.WaitForSingleObject(h, 0)   # non bloquant
                if r == WAIT_OBJECT_0 or r == WAIT_ABANDONED:
                    # Slot obtenu (ou récupéré après abandon)
                    handle = h
                    obtenu = True
                    motif = "obtenu"
                    break
                # Sinon le mutex est occupé : on le ferme et on passe au suivant
                k.CloseHandle(h)
            if obtenu:
                break
            # Aucun mutex libre
            if time.monotonic() >= deadline:
                obtenu = False
                motif = f"semaphore plein, aucun slot disponible après {attente_s:.0f}s"
                break
            time.sleep(0.1)   # petite pause avant nouvelle tentative

    v = Verrou(classe, obtenu, motif)

    if bavard:
        etat = "OBTENU " if v.obtenu else "REFUSÉ "
        print(f"  semaphore [{classe}] {etat}({projet}) — {v.motif}", file=sys.stderr)

    try:
        yield v
    finally:
        if handle:
            if obtenu:
                k.ReleaseMutex(handle)
            k.CloseHandle(handle)


def _run_epreuve() -> int:
    """Exécute les trois volets d’épreuve demandés par le sujet.

    - **FORWARD** : deux processus distincts acquièrent chacun un slot sur la classe
      ``epreuveF`` (n=2).  La présence simultanée de leurs fichiers *ready* prouve que
      les slots sont accordés **cross‑process**.
    - **CAP** : un processus tient un slot sur ``epreuveC`` (n=1).  Le parent tente d’en
      acquérir un second (attente = 1 s) ; il doit échouer tant que le premier processus
      ne libère pas.
    - **DEATH‑SAFETY** : un sous‑processus acquiert un slot via ``--tenir-slot`` puis meurt.
      Le parent doit récupérer le slot grâce à l’attente normale (le mutex a été libéré).

    Retourne 0 si les trois volets réussissent, sinon un entier >0.
    """
    if _kernel32() is None:
        print("semaphore test : NON APPLICABLE (pas de kernel32)")
        return 0

    import pathlib, tempfile

    # Répertoire temporaire pour les fichiers ready
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = pathlib.Path(tmpdir)

        # ---------- FORWARD ----------
        r1 = tmp / "forward1"
        r2 = tmp / "forward2"
        proc_f1 = subprocess.Popen(
            [sys.executable, __file__, '--tenir-vivant', 'epreuveF', '2', str(r1), '4'],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        proc_f2 = subprocess.Popen(
            [sys.executable, __file__, '--tenir-vivant', 'epreuveF', '2', str(r2), '4'],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        deadline = time.time() + 10
        while time.time() < deadline and not (r1.exists() and r2.exists()):
            time.sleep(0.1)

        if not (r1.exists() and r2.exists()):
            print("FORWARD : ECHEC – timeout d’attente des deux ready files")
            proc_f1.terminate()
            proc_f2.terminate()
            proc_f1.wait()
            proc_f2.wait()
            return 1

        proc_f1.wait()
        proc_f2.wait()
        print("FORWARD : OK")

        # ---------- CAP ----------
        rcap = tmp / "cap"
        proc_c = subprocess.Popen(
            [sys.executable, __file__, '--tenir-vivant', 'epreuveC', '1', str(rcap), '4'],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        deadline = time.time() + 10
        while time.time() < deadline and not rcap.exists():
            time.sleep(0.1)

        if not rcap.exists():
            print("CAP : ECHEC – ready file non créé")
            proc_c.terminate()
            proc_c.wait()
            return 2

        # Le parent tente d’obtenir un second slot, ce qui doit échouer
        with semaphore('epreuveC', 1, projet='epreuve', attente_s=1, bavard=False) as s:
            if s.obtenu:
                print("CAP : ECHEC – le parent a obtenu le slot alors qu’il devait être plein")
                proc_c.terminate()
                proc_c.wait()
                return 3

        proc_c.wait()
        print("CAP : OK")

        # ---------- DEATH‑SAFETY ----------
        proc_d = subprocess.Popen(
            [sys.executable, __file__, '--tenir-slot', 'epreuveD', '1'],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        proc_d.wait()

        with semaphore('epreuveD', 1, projet='epreuve', attente_s=5, bavard=False) as s:
            if not s.obtenu:
                print("DEATH‑SAFETY : ECHEC – le slot n’a pas été récupéré après la mort du processus")
                return 4

        print("DEATH‑SAFETY : OK")
        return 0


# ── Diagnostic humain — SÉPARÉ, et jamais autoritaire ──────────────────────────────────────────

def processus_concurrents() -> list[dict]:
    """Énumère les robocopy/pytest en cours, tous projets confondus.

    ★ Ceci est un DIAGNOSTIC, pas le mécanisme d'exclusion. Le mutex est la vérité ; cette
    énumération sert uniquement à écrire un message lisible (« qui, depuis quand, quel projet »),
    parce qu'un mutex ne porte aucune charge utile. Confondre les deux — se fier à l'énumération
    pour décider — rouvrirait la fenêtre de course que le mutex ferme.
    """
    if os.name != "nt":
        return []
    import subprocess
    ps = ("Get-CimInstance Win32_Process -Filter \"Name='robocopy.exe' OR Name='python.exe'\" | "
          "ForEach-Object { \"$($_.ProcessId)|$($_.Name)|$($_.CommandLine)\" }")
    try:
        sortie = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
                                capture_output=True, text=True, encoding="utf-8",
                                errors="replace", timeout=60).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    trouves = []
    for ligne in sortie.splitlines():
        parts = ligne.split("|", 2)
        if len(parts) < 3:
            continue
        pid, nom, cmd = (p.strip() for p in parts)
        # ★ On classe sur le NOM ET sur la commande, robocopy d'abord. Une première version testait
        # `nom == "robocopy.exe"` puis `"pytest" in cmd`, et a étiqueté un robocopy réel en
        # « pytest » — le nom rendu par PowerShell ne correspondait pas à l'égalité stricte
        # attendue. Un diagnostic qui se trompe de classe est pire qu'un diagnostic absent : il
        # donne un nom faux à ce qu'on voit, et on cherche au mauvais endroit.
        bas_nom, bas_cmd = nom.lower(), (cmd or "").lower()
        if "robocopy" in bas_nom or bas_cmd.startswith("robocopy") or " robocopy " in f" {bas_cmd} ":
            classe = "robocopy"
        elif "pytest" in bas_cmd:
            classe = "pytest"
        else:
            continue
        bas = cmd.lower()
        projet = ("SAS" if ("sas" in bas or "sovereign" in bas)
                  else "EA-MT5" if ("ea mt5" in bas or "rentable" in bas) else "?")
        trouves.append({"pid": pid.strip(), "classe": classe, "projet": projet, "cmd": cmd[:110]})
    return trouves


def main(argv=None) -> int:
    f = sys.stdout
    if (getattr(f, "encoding", "") or "").lower().replace("-", "") != "utf8":
        with suppress(AttributeError, ValueError, OSError):
            f.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    # `--etat` EST le comportement, il ne le declenche pas.
    #
    # Le drapeau etait declare, documente dans l'usage en tete de fichier, et
    # JAMAIS consulte : le script affiche l'etat qu'on le passe ou non. Une
    # option documentee qui ne fait rien est pire qu'une option absente --
    # elle laisse croire qu'il existe un autre mode.
    #
    # Il est CONSERVE plutot que retire : l'usage du fichier le cite, et un
    # appelant pourrait le passer. Mais son aide dit maintenant la verite.
    ap.add_argument("--etat", action="store_true",
                    help="sans effet : ce script n'affiche que l'etat, "
                         "avec ou sans ce drapeau. Conserve pour les "
                         "appelants qui le passent deja.")
    ap.add_argument("--epreuve", action="store_true",
                    help="lance l'épreuve interne forward+reverse et sort")
    ap.add_argument("--tenir-slot", nargs=2, metavar=('CLASSE', 'N'),
                    help="acquiert un slot du semaphore puis meurt sans le relâcher (test death‑safety)")
    ap.add_argument("--tenir-vivant", nargs=4, metavar=('CLASSE', 'N', 'READY_FILE', 'SECS'),
                    help="acquiert un slot, crée le fichier READY_FILE, attend SECS secondes puis libère")
    args = ap.parse_args(argv)

    # Gestion du mode « tenir‑slot » : acquisition d’un slot puis sortie brutale
    if args.tenir_slot:
        classe_ts, n_str = args.tenir_slot
        n_ts = int(n_str)
        # On acquiert le slot puis on quitte immédiatement via os._exit,
        # ce qui empêche le bloc finally du context manager de s’exécuter.
        with semaphore(classe_ts, n_ts, projet="death_test", attente_s=0.0, bavard=False) as _:
            os._exit(0)

    # Gestion du mode « tenir‑vivant » : acquisition, création de fichier, attente, sortie normale
    if args.tenir_vivant:
        classe_tv, n_str, ready_path, secs_str = args.tenir_vivant
        n_tv = int(n_str)
        secs_tv = float(secs_str)
        with semaphore(classe_tv, n_tv, projet="vivant_test", attente_s=5.0, bavard=False) as v:
            if v.obtenu:
                pathlib.Path(ready_path).touch()
                time.sleep(secs_tv)
                sys.exit(0)
            else:
                sys.exit(1)

    if args.epreuve:
        return _run_epreuve()

    horodatage = datetime.now().astimezone().replace(microsecond=0).isoformat()
    print(f"VERROUS DE SESSION — {horodatage}")
    print("  exclusion limitée à la session Windows courante")
    print(f"  contrat entre projets : le NOM du mutex ({PREFIXE}<CLASSE>)")
    for classe, quoi in CLASSES.items():
        with verrou(classe, projet="sonde", attente_s=0.0, bavard=False) as v:
            libre = "LIBRE " if v.obtenu else "TENU  "
            print(f"  {libre} {classe:<10} {quoi}")

    print("\n  SEMAPHORES (plafond, non exclusif) :")
    for classe, quoi in SEMAPHORES.items():
        with semaphore(classe, 1, projet="sonde", attente_s=0.0, bavard=False) as s:
            etat = "LIBRE" if s.obtenu else "PLEIN"
        print(f"  {etat:<6} SEM_{classe:<10} {quoi}")

    procs = processus_concurrents()
    print(f"\n  diagnostic (non autoritaire) — {len(procs)} processus concurrent(s) :")
    for p in procs:
        print(f"      {p['pid']:>7}  {p['classe']:<9} [{p['projet']:<6}] {p['cmd']}")
    if not procs:
        print("      aucun")
    return 0


if __name__ == "__main__":
    sys.exit(main())
