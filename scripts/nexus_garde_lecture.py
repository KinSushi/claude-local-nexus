#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Lire avant d'écrire. Refusé sinon.

Hook `PreToolUse` sur Edit / Write / NotebookEdit. Il refuse d'écrire dans un
fichier EXISTANT qui n'a pas été lu pendant cette session : écrire sur un
contenu supposé écrase ce qu'on n'a pas vu, et le travail perdu ne se
distingue pas d'un travail jamais fait.

Repris du dépôt SAS (`hook_lecture_avant_ecriture.py`), où il a mordu le jour
même où nous l'inscrivions « à reprendre » — il a arrêté une écriture sur un
fichier de test non lu.

CE QU'IL NE VOIT PAS, et il faut le dire pour ne pas s'en croire protégé :
il ne voit **que** les outils qui passent par ce hook. Ce qu'un script lancé
par le shell écrit, ce qu'un éditeur externe modifie, ce qu'un autre
processus touche — rien de tout cela ne lui parvient. Le garde borne un
chemin d'écriture, pas tous.

Squelette produit par le banc (`gpt-oss-120b-cloud`, 2613 jetons, coût nul),
intégré après arbitrage de trois défauts :

* `.nexus/lectures` était RELATIF au répertoire courant. Un hook peut être
  lancé de n'importe où : la mémoire des lectures serait allée ailleurs, et
  le garde aurait refusé des écritures légitimes en ayant oublié les lectures
  correspondantes. C'est la troisième fois aujourd'hui qu'une racine relative
  passe pour absolue dans ce dépôt ;
* accents dans le motif IMPRIMÉ, alors que ce motif s'affiche à l'opérateur
  et casse sous cp1252 ;
* `portee()` était une fonction vide, avec un `pass` et un docstring — de la
  documentation déguisée en code, que rien n'appelle et que rien ne vérifie.
  La limite est ici, dans le docstring du module, là où elle se lit.
"""
import json
import os
import re
import sys

# Racine ABSOLUE. `CLAUDE_PROJECT_DIR` quand le hook est lance par Claude
# Code ; sinon, deduite de la position de ce fichier -- jamais du repertoire
# courant, qui n'est pas celui du projet des qu'un outil change de dossier.
ROOT = os.environ.get("CLAUDE_PROJECT_DIR") or os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))

ECRITURES = ("Edit", "Write", "NotebookEdit")


def normaliser(chemin: str) -> str:
    """
    Forme canonique d'un chemin.

    `normcase` autant qu'`abspath` : sous Windows, « C:/a/B.py » et
    « c:\\a\\b.py » designent le meme fichier, et les traiter comme deux
    refuserait une ecriture pourtant legitime -- le garde punirait alors
    quelqu'un qui a bel et bien lu.
    """
    return os.path.normcase(os.path.abspath(str(chemin)))


def memoire(session: str) -> str:
    """
    Fichier de memoire de cette session.

    L'identifiant est filtre avant de servir de nom de fichier : un
    identifiant contenant « .. » ou un separateur ecrirait ailleurs sur le
    disque. On ne garde que ce qui ne peut designer aucun autre repertoire.
    """
    propre = re.sub(r"[^A-Za-z0-9_-]", "", str(session or ""))
    return os.path.join(ROOT, ".nexus", "lectures",
                        (propre or "sans-session") + ".json")


def lus(chemin_memoire: str) -> set:
    try:
        with open(chemin_memoire, encoding="utf-8") as fh:
            return set(json.load(fh).get("lus") or [])
    except Exception:
        # Memoire absente ou illisible : on repart de rien. Le garde refusera
        # peut-etre une ecriture de trop, jamais une de moins -- et il suffit
        # de lire le fichier pour passer.
        return set()


def retenir(chemin_memoire: str, connus: set) -> None:
    try:
        os.makedirs(os.path.dirname(chemin_memoire), exist_ok=True)
        with open(chemin_memoire, "w", encoding="utf-8") as fh:
            json.dump({"lus": sorted(connus)}, fh, ensure_ascii=False)
    except Exception:
        # Un echec d'ecriture ne doit JAMAIS empecher d'autoriser : le pire
        # que l'on risque est d'oublier une lecture, pas de perdre un fichier.
        pass


def refuser(chemin_affiche: str) -> None:
    """
    Le nom montre est celui du chemin D'ORIGINE, jamais la forme canonique.

    `normaliser` applique `normcase`, qui met tout en minuscules sous
    Windows : le motif annoncait « readme.md » pour un fichier nomme
    « README.md ». La forme canonique sert a COMPARER, pas a AFFICHER, et un
    message qui renomme le fichier qu'il designe fait douter de ce qu'il dit.
    """
    motif = ("REFUS -- LIRE AVANT D'ECRIRE. Le fichier %s existe et n'a pas "
             "ete lu dans cette session : ecrire dessus ecraserait un contenu "
             "suppose. Le lire d'abord (outil Read), puis ecrire."
             % os.path.basename(chemin_affiche))
    try:
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": motif,
        }}, ensure_ascii=False))
    except Exception:
        pass


# CE GARDE EST AGNOSTIQUE A L'OUTIL : il se cale sur la presence d'un
# champ `file_path` ou `notebook_path`, jamais sur un nom d'outil.
# `None` le dit explicitement, pour que le controle ne l'exige pas --
# et pour qu'un futur lecteur ne prenne pas l'absence de constante
# pour un oubli.
# ---------------------------------------------------------------------------
# LE SHELL ECRIT AUSSI, ET CE GARDE NE LE VOYAIT PAS.
#
# MESURE du 2026-08-31 :
#     Write sur un fichier non lu  -> REFUSE
#     sed -i / echo > / Set-Content -> PASSE, trois fois sur trois
# et 79,5 % des invocations de la session passent par le shell.
#
# CE QUI SUIT NE REFUSE RIEN. Il JOURNALISE. Une session voisine a tente le
# refus direct le meme jour : sa greffe a refuse `ls > /dev/null` et bloque une
# restauration depuis sauvegarde, et a du etre retiree de la production. Un
# garde trop large se fait desarmer -- c'est pire que le trou.
#
# On produit donc la mesure sur laquelle decider la politique, plutot que de
# la deviner. Le journal dit ce qui est REELLEMENT ecrit par le shell sans
# avoir ete lu ; la decision de refuser viendra de ces chiffres, ou ne viendra
# pas.
#
# L'extraction passe un banc d'acceptation de 17 cas, dont les anti-controles
# qui ont fait tomber la greffe voisine : `ls > /dev/null` et la restauration.
# Voir scripts/epreuve_cibles_shell.py.
# ---------------------------------------------------------------------------


# Cibles inoffensives : ignorees SANS rien signaler. `ls > /dev/null` refuse
# est ce qui a fait retirer la greffe d'une session voisine, le meme jour.
_IGNORED = {
    '/dev/null', '/dev/stdout', '/dev/stderr',
    'nul', 'nul:', '$null'
}

# Caracteres qui rendent une cible INDETERMINEE. On ne devine pas : une mesure
# impossible n'est pas une mesure a zero.
_PROHIBITED = set('$(`*?')


def _strip_quotes(s):
    if (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")):
        return s[1:-1]
    return s

def _analyse_target(tok):
    t = _strip_quotes(tok)
    low = t.lower()
    if low in _IGNORED:
        return None, False
    if any(ch in _PROHIBITED for ch in t):
        return None, True
    return t, False

def _split_segments(cmd):
    segs = []
    cur = []
    in_sgl = False
    in_dbl = False
    i = 0
    while i < len(cmd):
        c = cmd[i]
        if c == "'" and not in_dbl:
            in_sgl = not in_sgl
        elif c == '"' and not in_sgl:
            in_dbl = not in_dbl
        if not in_sgl and not in_dbl and c in ';|&':
            # treat &&, || as single separator
            if i + 1 < len(cmd) and cmd[i+1] == c:
                i += 1
            segs.append(''.join(cur))
            cur = []
        else:
            cur.append(c)
        i += 1
    segs.append(''.join(cur))
    return segs

def _parse_redirections(seg):
    targets = []
    indet = False
    pattern = re.compile(
        r'(?<!<)>(>?)(\s*)'                     # > or >> not preceded by <
        r'(?:'                                 # start target
        r'"([^"]*)"'                           # double quoted
        r'|'                                   # or
        r'\'([^\']*)\''                        # single quoted
        r'|'                                   # or
        r'([^ \t\r\n;|&]+)'                    # unquoted token
        r')'
    )
    for m in pattern.finditer(seg):
        # LES GROUPES SONT 3, 4, 5 -- il n'y en a que cinq.
        #
        # Le decalage ne se voyait QUE dans le cas guillemets doubles :
        # le `or` court-circuite, donc group(6) n'etait atteint que la, et
        # son IndexError etait avale par le except global qui rend
        # ([], True). Un filet de securite transformait un bug en
        # « indetermine » parfaitement plausible -- et le cas etait le seul
        # qui compte pour une racine contenant des espaces.
        raw = m.group(3) or m.group(4) or m.group(5)
        if raw is None:
            continue
        tgt, det = _analyse_target(raw)
        if tgt:
            targets.append(tgt)
        indet = indet or det
    return targets, indet

def _tokenize(seg):
    # keep quoted strings as single tokens
    return re.findall(r'''[^\s'"]+|"(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*' ''', seg)

def _parse_commands(seg):
    tokens = _tokenize(seg)
    if not tokens:
        return [], False
    cmd = tokens[0].lower()
    targets = []
    indet = False

    # cp, mv, tee : last argument is destination
    if cmd in ('cp', 'mv', 'tee'):
        tgt, det = _analyse_target(tokens[-1])
        if tgt:
            targets.append(tgt)
        indet = indet or det
        return targets, indet

    # dd : look for of=FICHIER
    if cmd == 'dd':
        for tok in tokens[1:]:
            if tok.startswith('of='):
                raw = tok[3:]
                tgt, det = _analyse_target(raw)
                if tgt:
                    targets.append(tgt)
                indet = indet or det
                break
        return targets, indet

    # PowerShell Set-Content, Add-Content, Out-File
    if cmd in ('set-content', 'add-content', 'out-file'):
        for i, tok in enumerate(tokens[1:]):
            low = tok.lower()
            if low in ('-path', '-literalpath'):
                if i + 2 < len(tokens):
                    raw = tokens[i + 2]
                    tgt, det = _analyse_target(raw)
                    if tgt:
                        targets.append(tgt)
                    indet = indet or det
                break
        return targets, indet

    # sed -i[.suffix] ... file
    if cmd == 'sed':
        inplace = any(re.match(r'^-i(\..*)?$', t) for t in tokens[1:])
        if not inplace:
            return [], False
        # last non-option token is file
        non_opt = [t for t in tokens[1:] if not t.startswith('-')]
        if non_opt:
            raw = non_opt[-1]
            tgt, det = _analyse_target(raw)
            if tgt:
                targets.append(tgt)
            indet = indet or det
        return targets, indet

    return [], False

def cibles_ecrites(commande):
    try:
        segments = _split_segments(commande)
        all_targets = []
        indeterminate = False
        for seg in segments:
            seg = seg.strip()
            if not seg:
                continue
            t1, d1 = _parse_redirections(seg)
            t2, d2 = _parse_commands(seg)
            all_targets.extend(t1)
            all_targets.extend(t2)
            indeterminate = indeterminate or d1 or d2
        return (all_targets, indeterminate)
    except Exception:
        return ([], True)

def journaliser_ecriture_shell(session, commande, chemins, indetermine):
    """
    Inscrit ce que le shell ecrit sans que le fichier ait ete lu.

    N'ECHOUE JAMAIS et ne refuse rien : ce n'est pas une barriere, c'est un
    instrument de mesure. Une panne d'ecriture du journal ne doit pas empecher
    de travailler -- ce serait echanger une mesure contre un blocage.

    « indetermine » est inscrit AUSSI, et separement : une mesure impossible
    n'est pas une mesure a zero, et savoir combien de commandes echappent a
    l'extraction est aussi utile que savoir lesquelles ne lui echappent pas.
    """
    try:
        dossier = os.path.join(ROOT, ".nexus")
        os.makedirs(dossier, exist_ok=True)
        ligne = json.dumps({
            "session": session or "",
            "commande": commande[:300],
            "chemins": chemins,
            "indetermine": bool(indetermine),
        }, ensure_ascii=False)
        with open(os.path.join(dossier, "ecritures_shell.jsonl"),
                  "a", encoding="utf-8") as fh:
            fh.write(ligne + "\n")
    except Exception:
        pass


OUTILS_JUGES = None


def main() -> None:
    try:
        brut = sys.stdin.read()
    except Exception:
        return
    if not brut or not brut.strip():
        return
    try:
        charge = json.loads(brut)
    except Exception:
        return
    if not isinstance(charge, dict):
        return

    outil = charge.get("tool_name") or ""
    entree = charge.get("tool_input")
    entree = entree if isinstance(entree, dict) else {}
    # LA BRANCHE SHELL PASSE AVANT le test sur `file_path` : une commande n'en
    # porte pas, et le garde sortait donc immediatement -- c'est exactement par
    # la que 79,5 % des invocations echappaient.
    if outil in ("Bash", "PowerShell"):
        commande = entree.get("command")
        if isinstance(commande, str) and commande.strip():
            chemins, indet = cibles_ecrites(commande)
            if chemins or indet:
                try:
                    fichier_memoire = memoire(charge.get("session_id"))
                    connus = lus(fichier_memoire)
                    inconnus = [c for c in chemins
                                if normaliser(c) not in connus]
                except Exception:
                    inconnus = chemins
                if inconnus or indet:
                    journaliser_ecriture_shell(
                        charge.get("session_id"), commande, inconnus, indet)
        # On NE REFUSE PAS. Voir l'en-tete : la politique de refus se decidera
        # sur le journal, pas sur une supposition.
        return

    chemin = entree.get("file_path") or entree.get("notebook_path") or ""
    if not isinstance(chemin, str) or not chemin.strip():
        return

    try:
        cible = normaliser(chemin)
        fichier_memoire = memoire(charge.get("session_id"))
    except Exception:
        # Sans chemin canonique, aucune decision prudente n'est possible :
        # autoriser plutot que refuser sur une base incertaine.
        return

    if outil == "Read":
        connus = lus(fichier_memoire)
        connus.add(cible)
        retenir(fichier_memoire, connus)
        return

    if outil not in ECRITURES:
        return

    try:
        existe = os.path.exists(cible)
    except Exception:
        return
    if not existe:
        # Creer un fichier neuf n'ecrase rien : il n'y a rien a avoir lu.
        #
        # Mais il faut S'EN SOUVENIR. Sans cela, la session qui vient
        # d'ecrire un fichier se voit refuser la deuxieme ecriture dessus,
        # au motif qu'elle n'en connaitrait pas le contenu -- alors qu'elle
        # en est l'auteur. Mesure du 2026-08-30 : un script d'extraction
        # ecrit puis corrige dans le meme tour, refuse au second passage.
        #
        # L'enregistrement n'a lieu QUE sur un fichier inexistant, et c'est
        # ce qui le rend sur : si l'ecriture echoue, le fichier reste
        # absent, donc la prochaine sera une creation, autorisee de toute
        # facon. Aucun contenu non vu ne peut ainsi devenir ecrasable.
        connus = lus(fichier_memoire)
        connus.add(cible)
        retenir(fichier_memoire, connus)
        return
    if cible in lus(fichier_memoire):
        return
    refuser(chemin)


if __name__ == "__main__":
    try:
        main()
    except BaseException:
        # Rempart final. La contrainte est absolue : ce garde n'echoue jamais,
        # et une anomalie AUTORISE en silence. Un garde qui plante empeche de
        # travailler, ce qui est pire que le defaut qu'il surveille.
        pass
    sys.exit(0)
