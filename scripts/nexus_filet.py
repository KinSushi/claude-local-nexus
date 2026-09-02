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
"""

import sys
import argparse
import subprocess
from pathlib import Path

# RACINE derivee de Path(__file__).resolve().parent.parent (jamais de chemin absolu)
RACINE = Path(__file__).resolve().parent.parent

def worktrees(racine: Path):
    """Retourne la liste des worktrees d'agents sous <racine>/.claude/worktrees/agent-*/."""
    base = racine / '.claude' / 'worktrees'
    if not base.is_dir():
        return []
    return [p for p in base.iterdir() if p.is_dir() and p.name.startswith('agent-')]

def diff_de(wt: Path, exclure):
    """
    Retourne le texte du git diff du worktree wt, en excluant les chemins donnes.
    Si la commande echoue ou si le diff est vide, retourne ''.
    """
    excl_args = []
    for e in exclure:
        excl_args.append(f':!{e}')
    cmd = ['git', '-C', str(wt), 'diff', '--', '.'] + excl_args
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if result.returncode != 0:
        return ''
    # subprocess peut rendre None la ou on attend une chaine, et un or '' evite de faire dependre l'outil d'une hypothese sur le systeme
    diff_text = result.stdout or ''
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
        else:
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
    args = parser.parse_args()

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

    for wt in worktrees(RACINE):
        total += 1
        name = wt.name
        diff_txt = diff_de(wt, args.exclure)
        if not diff_txt:
            vides += 1
            print(f'{name}: vide')
            continue

        lignes = len(diff_txt.splitlines())
        suppr = suppressions(diff_txt)
        if suppr and not args.avec_suppressions:
            refuses += 1
            suppr_str = ', '.join(suppr)
            print(f'{name}: {lignes} lignes - refuse suppression [{suppr_str}]')
            continue

        # appliquer() renvoie maintenant (etat, message, appliquable)
        etat_check, msg_check, _ = appliquer(RACINE, diff_txt, verifier_seulement=True)
        if etat_check == 'conflit':
            echec_check += 1
            print(f'{name}: {lignes} lignes - echec check [{msg_check}]')
            continue

        if args.appliquer:
            etat_apply, msg_apply, _ = appliquer(RACINE, diff_txt, verifier_seulement=False)
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
    # Pourquoi cette distinction compte : un lot deja integre a la main se lisait comme un echec, et un vrai conflit se noyait dans le meme total
    sys.exit(1 if conflits > 0 else 0)

if __name__ == '__main__':
    main()
