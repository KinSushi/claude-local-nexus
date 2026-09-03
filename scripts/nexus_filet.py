#!/usr/bin/env python3
"""
Script nexus_filet.py

Contraintes de conception :
- DRY-RUN par defaut. L'application reelle exige --appliquer.
- Il ne modifie jamais le contenu d'un patch : il le reprend verbatim par git diff.
- Il refuse tout diff contenant une suppression de fichier suivi, sauf si --avec-suppressions est passe.
  Pourquoi : un agent a supprime docker-compose.yml dans son worktree en fabriquant une condition d echec ;
  un git apply aveugle aurait emporte le fichier du depot reel, la suppression figurant comme un D ordinaire.
- Il exclut par defaut les fichiers listes dans --exclure (defaut : scripts/nexus_doc.py), qui sont des copies posees
  par l orchestrateur et non du travail d agent.
- Chaque patch est teste par git apply --check AVANT toute ecriture ; un patch qui ne s applique pas proprement
  est signale et saute, il n interrompt pas les autres.
- Il n'affiche que des comptes et des noms de fichiers, jamais le contenu des diffs.
- La sortie de git est lue en OCTETS BRUTS puis decodee en UTF-8 explicitement (jamais text=True) ;
  une sortie qui ne se decode pas leve une erreur NOMMEE et se compte a part, jamais comme 'vide'.
- Le diff recolte est UNIQUEMENT celui des modifications NON INDEXEES ('git diff -- .'). Un worktree
  dont le travail est COMMITE est donc hors de la recolte automatique ; ce cas n'est jamais confondu
  avec 'vide' -- voir commits_non_vus() -- mais il n'est pas non plus recolte ici.
- --racine permet de surcharger la racine derivee de __file__ (contrat §0.5) : sans elle, l'outil
  est intestable depuis un worktree (il cherche <lui-meme>/.claude/worktrees/, absent d'un worktree
  d'agent, et rend silencieusement 'Total worktrees: 0').
"""

import sys
import argparse
import subprocess
from pathlib import Path

# RACINE derivee de Path(__file__).resolve().parent.parent (jamais de chemin absolu)
RACINE = Path(__file__).resolve().parent.parent


class ErreurDecodageDiff(Exception):
    """
    git a repondu (le processus s'est acheve normalement) mais sa sortie ne
    s'est pas decodee en UTF-8. Ne JAMAIS avaler ce cas en rendant une chaine
    vide : un diff illisible n'est pas un diff absent, et confondre les deux
    est exactement le defaut que ce module existe pour empecher -- un
    worktree porteur d'un vrai travail se compterait comme "vide" a cote de
    ceux qui n'ont vraiment rien produit.
    """


def worktrees(racine: Path):
    """Retourne la liste des worktrees d'agents sous <racine>/.claude/worktrees/agent-*/."""
    base = racine / '.claude' / 'worktrees'
    if not base.is_dir():
        return []
    return [p for p in base.iterdir() if p.is_dir() and p.name.startswith('agent-')]

def diff_de(wt: Path, exclure):
    """
    Retourne le texte du git diff du worktree wt, en excluant les chemins donnes.
    Si la commande git echoue (code de sortie non nul) ou si le diff est vide,
    retourne ''.

    Leve ErreurDecodageDiff si git a repondu mais que sa sortie ne se decode
    pas en UTF-8 -- ce cas ne doit JAMAIS produire '' silencieusement.

    Pourquoi des octets bruts, et jamais text=True :
    Sous Windows, subprocess.run(..., text=True) SANS encoding= explicite
    decode stdout/stderr avec l'encodage LOCAL de la machine
    (locale.getencoding(), Lib/subprocess.py:890) -- jamais utf-8. Sur cet
    hote, mesure : locale.getencoding() == 'cp1252'. Ce depot est ecrit en
    francais ; le moindre octet de diff hors du sous-ensemble cp1252 (par
    exemple Ï, Á, Í, ou tout caractere dont le 2e octet UTF-8 tombe sur l'une
    des 5 positions que cp1252 laisse non definies -- 0x81, 0x8D, 0x8F, 0x90,
    0x9D -- CPython 3.14 le confirme : Lib/encodings/cp1252.py) declenche
    UnicodeDecodeError.

    Et cette exception ne remonte JAMAIS jusqu'ici : quand stdout ET stderr
    sont tous deux captures, Popen lit chacun dans un fil separe
    (Lib/subprocess.py:1613, _readerthread) pour eviter un verrou mutuel.
    Une exception levee DANS ce fil est interceptee par threading, imprimee
    sur stderr, et le fil meurt -- sans jamais remonter au thread appelant.
    _communicate() rejoint ensuite ce fil mort (il n'est plus "vivant", donc
    aucun TimeoutExpired), puis rend
        stdout = stdout[0] if stdout else None      (Lib/subprocess.py:1682)
    ou `stdout` est justement la liste-tampon que le fil mort n'a jamais
    remplie : liste vide, donc falsy, donc `None` -- pas d'exception, pas de
    code de sortie non nul, rien qui distingue ce cas d'une reponse normale.
    Verifie en isolation (voir QUARANTAINE.md, epreuve 4a) : returncode == 0,
    type(result.stdout) is NoneType.
    """
    excl_args = []
    for e in exclure:
        excl_args.append(f':!{e}')
    cmd = ['git', '-C', str(wt), 'diff', '--', '.'] + excl_args
    # bytes bruts : aucun fil de lecture ne peut plus decoder quoi que ce
    # soit, donc aucun ne peut plus mourir d'un UnicodeDecodeError invisible.
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode != 0:
        return ''
    # defense generale (process tue, etc.) : ne fait plus partie du chemin
    # de crash decrit ci-dessus, qui est desormais structurellement impossible.
    brut = result.stdout or b''
    if not brut.strip():
        return ''
    try:
        diff_text = brut.decode('utf-8')
    except UnicodeDecodeError as exc:
        raise ErreurDecodageDiff(
            f'{len(brut)} octets recus de git diff, non decodables en UTF-8 : {exc}'
        ) from exc
    return diff_text if diff_text.strip() else ''

def suppressions(diff_text: str):
    """
    Retourne la liste des chemins supprimes dans le diff.
    On identifie les suppressions par une ligne 'deleted file mode' precedee d'un
    'diff --git a/<path> b/<path>'.
    """
    suppress = []
    current_path = None
    for line in diff_text.splitlines():
        if line.startswith('diff --git'):
            parts = line.split()
            # format: diff --git a/X b/X
            if len(parts) >= 4:
                a_path = parts[2][2:]  # retire le prefix 'a/'
                current_path = a_path
            else:
                current_path = None
        elif line.startswith('deleted file mode') and current_path:
            suppress.append(current_path)
            current_path = None
    return suppress

def commits_non_vus(wt: Path):
    """
    Retourne (nb_commits, nb_fichiers) pour les commits presents dans le
    worktree wt mais absents de main. Les commits comptent en DEUX points
    (main..HEAD : "quoi que HEAD ait, que main n'a pas" -- la bonne question
    pour un log). Les fichiers comptent en TROIS points (main...HEAD : diff
    entre HEAD et la BASE COMMUNE de main et HEAD) -- deux points donnerait
    le diff entre les deux SNAPSHOTS, qui inclut tout ce que main a change
    de son cote depuis la divergence. Pour un diff, deux points ne repond
    pas a la meme question que pour un log.

    Pourquoi cette fonction existe : diff_de() ne regarde QUE les
    modifications NON INDEXEES ('git diff -- .', sans reference). Un agent
    qui commit son travail -- le comportement discipline -- rend son
    worktree invisible a diff_de(), qui rend '' comme pour un worktree
    reellement vide. Les deux se lisaient alors sous le meme mot : "vide".
    C'est la meme famille de defaut que le crash d'encodage que ce fichier
    corrige par ailleurs -- un vrai travail qui se lit comme une absence --
    et l'incitation qu'il cree est inversee : il recompense l'agent qui n'a
    RIEN commite plutot que celui qui a cloture son travail proprement.

    Mesure sur la flotte reelle le 2026-09-03, parmi les worktrees "vide" au
    sens de diff_de() : 2 worktrees sur 14 portaient en realite des commits
    -- agent-a0bb278a9ee2836a5 (2 commits, 9 fichiers) et
    agent-a96910bce09e87b38 (1 commit, 1 fichier). Chiffres corriges : une
    premiere mesure avait compte les fichiers en DEUX points (25 et 46) --
    ceux-la comptaient aussi les fichiers ou seul MAIN avait avance depuis
    la divergence (jusqu'a 90 fichiers pour un worktree a ZERO commit
    propre). Voir QUARANTAINE.md, rubrique 6, pour l'origine de l'erreur.

    Ne recolte ni n'applique rien : cette fonction NOMME le manque, elle ne
    le comble pas. Fusionner un diff de commits avec un diff non-indexe dans
    le meme patch risquerait de produire des hunks qui se chevauchent sur un
    fichier touche par les deux a la fois -- une extension a part, pas une
    correction a la sauvette dans ce meme geste.

    Degrade a (0, 0) sur tout echec (worktree sans branche main resolvable,
    git injoignable, etc.) : l'information est un COMPLEMENT au dry-run
    existant, jamais une raison de le faire echouer.
    """
    try:
        r_log = subprocess.run(['git', '-C', str(wt), 'log', '--oneline', 'main..HEAD'],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        # TROIS points ici, jamais deux : voir la docstring. 'main..HEAD' compterait
        # aussi les fichiers ou seul main a avance depuis la divergence.
        r_names = subprocess.run(['git', '-C', str(wt), 'diff', '--name-only', 'main...HEAD'],
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except OSError:
        return 0, 0
    if r_log.returncode != 0 or r_names.returncode != 0:
        return 0, 0
    # errors='replace' : ce decompte est informatif (compte de lignes), il
    # n'est jamais reinjecte dans un git apply -- contrairement au texte de
    # diff_de(), une perte de fidelite ici ne corrompt aucun patch.
    log_out = (r_log.stdout or b'').decode('utf-8', errors='replace')
    names_out = (r_names.stdout or b'').decode('utf-8', errors='replace')
    nb_commits = len([l for l in log_out.splitlines() if l.strip()])
    nb_fichiers = len([l for l in names_out.splitlines() if l.strip()])
    return nb_commits, nb_fichiers

def appliquer(racine: Path, texte: str, verifier_seulement: bool):
    """
    Applique le patch texte sur le depot principal.
    Retourne un tuple (etat: str, message: str, appliquable: bool).
    Etats possibles : 'applicable', 'deja-applique', 'conflit', 'applique'.
    """
    # premier test : le patch peut-il etre applique normalement ?
    cmd_check = ['git', '-C', str(racine), 'apply', '--check', '--whitespace=nowarn']
    result = subprocess.run(cmd_check, input=texte.encode(),
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode == 0:
        # le patch est applicable
        if verifier_seulement:
            return 'applicable', result.stderr.decode(errors='replace').strip(), True
        # appliquer le patch avec resolution a 3 voies
        cmd_apply = ['git', '-C', str(racine), 'apply', '--3way', '--whitespace=nowarn']
        apply_res = subprocess.run(cmd_apply, input=texte.encode(),
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if apply_res.returncode == 0:
            return 'applique', apply_res.stderr.decode(errors='replace').strip(), True
        return 'conflit', apply_res.stderr.decode(errors='replace').strip(), False
    # echec du check : verifier si le patch est deja applique
    # le --reverse permet de detecter un patch deja applique car appliquer le patch a l'envers
    # reussit si le changement est deja present dans le fichier.
    cmd_rev = ['git', '-C', str(racine), 'apply', '--check', '--reverse', '--whitespace=nowarn']
    rev_res = subprocess.run(cmd_rev, input=texte.encode(),
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if rev_res.returncode == 0:
        return 'deja-applique', rev_res.stderr.decode(errors='replace').strip(), False
    # sinon, c'est un vrai conflit
    return 'conflit', result.stderr.decode(errors='replace').strip(), False

def main():
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    parser = argparse.ArgumentParser(description='Recuperer les diffs des worktrees agents et les appliquer.')
    parser.add_argument('--appliquer', action='store_true', help='Appliquer les patches valides.')
    parser.add_argument('--avec-suppressions', action='store_true', help='Autoriser les suppressions de fichiers.')
    parser.add_argument('--exclure', nargs='*', default=['scripts/nexus_doc.py'],
                        help='Chemins a exclure du diff.')
    parser.add_argument("--racine", type=Path, default=None,
                        help="Racine explicite (contrat 0.5) : remplace la racine derivee de "
                             "__file__. Sans elle, lance depuis un worktree agent, l'outil se "
                             "cherche LUI-MEME sous .claude/worktrees/, absent d'un worktree "
                             "agent, et rend silencieusement Total worktrees: 0.")
    args = parser.parse_args()

    # L'appelant decide ou l'outil travaille, jamais l'outil lui-meme (contrat §0.5) :
    # une racine explicite l'emporte sur celle derivee de __file__.
    racine_effective = args.racine or RACINE

    total = 0
    vides = 0
    refuses = 0
    # Ces deux compteurs manquaient et main() plantait en les lisant :
    # UnboundLocalError. Un outil qui compte doit initialiser TOUS ses
    # compteurs avant la boucle, sinon un chemin qui n incremente jamais
    # fait tomber l affichage final — la ou l information est.
    deja_appliques = 0
    conflits = 0
    echec_check = 0
    appliques = 0
    # Une lecture qui echoue n'est PAS un worktree vide : les confondre a
    # perdu deux worktrees en silence cette nuit, comptes "vide" alors que
    # git avait repondu avec un vrai diff, illisible seulement sous cp1252
    # (voir ErreurDecodageDiff). Compteur et branche separes pour que ce cas
    # ne puisse plus jamais retomber dans "vide".
    erreurs_lecture = 0
    # Meme famille : un worktree "vide" au sens de diff_de() (rien en
    # modification NON INDEXEE) peut porter des COMMITS que ce dry-run ne
    # regarde pas. Voir commits_non_vus(). Compte a part pour que ce cas ne
    # se confonde jamais avec un worktree reellement sans rien.
    commits_masques = 0

    for wt in worktrees(racine_effective):
        total += 1
        name = wt.name
        try:
            diff_txt = diff_de(wt, args.exclure)
        except ErreurDecodageDiff as exc:
            erreurs_lecture += 1
            print(f'{name}: ERREUR DE LECTURE (non compte comme vide) - {exc}')
            continue
        if not diff_txt:
            nb_commits, nb_fichiers = commits_non_vus(wt)
            if nb_commits > 0:
                commits_masques += 1
                print(f'{name}: vide en modifications non indexees, MAIS {nb_commits} '
                      f'commit(s) non recoltes par ce dry-run ({nb_fichiers} fichier(s) '
                      f'touches, main...HEAD)')
            else:
                vides += 1
                print(f'{name}: vide')
            continue

        lignes = len(diff_txt.splitlines())
        suppr = suppressions(diff_txt)
        if suppr and not args.avec_suppressions:
            refuses += 1
            suppr_str = ', '.join(suppr)
            # Nommer la voie de contournement dans le message lui-meme : un refus qui ne dit
            # pas comment passer outre se desarme (voir aussi le code de sortie plus bas).
            print(f'{name}: {lignes} lignes - refuse suppression [{suppr_str}] '
                  f'(repasser avec --avec-suppressions pour autoriser)')
            continue

        # appliquer() renvoie maintenant (etat, message, appliquable)
        etat_check, msg_check, _ = appliquer(racine_effective, diff_txt, verifier_seulement=True)
        # POURQUOI la distinction compte : un lot deja integre a la main se lisait comme un echec, et un vrai conflit se noyait dans le meme total
        if etat_check == 'deja-applique':
            deja_appliques += 1
            print(f'{name}: {lignes} lignes - deja applique [{msg_check}]')
            continue
        if etat_check == 'conflit':
            conflits += 1
            print(f'{name}: {lignes} lignes - conflit [{msg_check}]')
            continue
        # etat_check == 'applicable' : laisser le reste du code s'executer

        if args.appliquer:
            etat_apply, msg_apply, _ = appliquer(racine_effective, diff_txt, verifier_seulement=False)
            if etat_apply == 'applique':
                appliques += 1
                print(f'{name}: {lignes} lignes - applique')
            elif etat_apply == 'deja-applique':
                deja_appliques += 1
                print(f'{name}: {lignes} lignes - deja applique')
            elif etat_apply == 'conflit':
                conflits += 1
                print(f'{name}: {lignes} lignes - conflit [{msg_apply}]')
            else:
                # etat_apply == 'applicable' (pas encore applique) ou autre cas inattendu
                # on le compte comme echec inattendu
                print(f'{name}: {lignes} lignes - echec apply [{msg_apply}]')
        else:
            print(f'{name}: {lignes} lignes - ok')

    print(f'Total worktrees: {total}')
    print(f'Vides: {vides}')
    print(f'Refuses (suppressions): {refuses}')
    print(f'Echecs check: {echec_check}')
    print(f'Deja appliques: {deja_appliques}')
    print(f'Conflits: {conflits}')
    print(f'Appliques: {appliques}')
    print(f'Erreurs de lecture: {erreurs_lecture}')
    print(f'Commits non recoltes (vide en diff, non vus par ce dry-run): {commits_masques}')
    # Pourquoi cette distinction compte : un lot deja integre a la main se lisait comme un echec, et un vrai conflit se noyait dans le meme total.
    # Une erreur de lecture pese AUTANT qu'un conflit dans le code de sortie : les deux signifient
    # qu'il reste quelque chose que ce dry-run n'a pas pu trancher, et taire l'un des deux serait
    # exactement la perte silencieuse que ce correctif existe pour eliminer.
    # Un worktree "vide" porteur de commits pese pareil : le laisser hors du code de sortie
    # reviendrait a dire que du travail commite ne compte pas comme un manque a traiter.
    # Un refus de suppression AUSSI : trouve par l'epreuve reverse elle-meme -- le message
    # nommait deja la voie (--avec-suppressions) et aucun fichier n'etait touche, mais le
    # code de sortie restait 0. Une garde qui refuse et rend 0 se lit comme une reussite.
    sys.exit(1 if (conflits > 0 or erreurs_lecture > 0 or commits_masques > 0 or refuses > 0) else 0)

if __name__ == '__main__':
    main()
