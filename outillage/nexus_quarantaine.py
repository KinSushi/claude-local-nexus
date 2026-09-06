# -*- coding: utf-8 -*-
"""nexus_quarantaine.py -- rassembler en quarantaine ce que les agents en
worktree ont produit, pour qu'un tiers puisse l'auditer SANS connaitre git.

Pourquoi ce script existe
--------------------------
Le worktree isole (`outillage/nexus_worktree.py`) est une isolation
D'EXECUTION : chaque agent travaille dans sa propre copie, sans collision
avec les autres ni avec l'arbre principal. Mais rien n'oblige cette
execution a se terminer par un commit, et rien n'oblige un commit a se
terminer par une fusion. Mesure le 2026-09-02 : cinq agents ont repare des
fichiers dans cinq worktrees isoles, et TROIS SUR CINQ ont laisse leur
travail non commite -- des fichiers qui n'existent que dans l'arbre de
travail d'un worktree et disparaissent avec lui si ce worktree est retire.

L'isolation d'execution a tenu. L'isolation de LIVRAISON -- rendre visible,
sans git, ce qui a ete produit et par qui -- n'existait pas. C'est l'objet
de ce script : il ne fusionne rien et ne decide de rien, il COPIE, avec la
provenance, pour que l'audit du gabarit (`rituels/GABARIT_QUARANTAINE.md`)
puisse avoir lieu sans que l'auditeur ouvre un terminal git.

Le piege qui a coute une premiere mesure fausse
-------------------------------------------------
Un premier comptage naif (`git diff --name-only main HEAD`) donnait 32 a 34
fichiers "modifies" par agent. C'etait faux : ce diff inclut tout le RETARD
DE BRANCHE entre le point de depart de l'agent et l'etat courant de main,
pas seulement ce que l'agent a produit. La bonne mesure passe par la base
de fusion :

    git -C <worktree> merge-base HEAD main
    git -C <worktree> diff --name-status -z <base> HEAD

Sans cela, un worktree qui a produit 3 fichiers reels s'affiche avec 32,
parce que main a avance de son cote pendant que l'agent travaillait.

Ce que ce script fait, et ce qu'il NE fait PAS
------------------------------------------------
Pour chaque sous-dossier "agent-*" du dossier des worktrees :

  - il lit, en LECTURE SEULE, l'etat non commite (`git status --porcelain`)
    et l'etat commite au-dela de la base de fusion avec main ;
  - il copie chaque fichier concerne sous `<cible>/<worktree>/<chemin>` ;
  - il copie AUSSI l'original qu'il remplace, depuis l'arbre PRINCIPAL
    (decouvert via `git worktree list`, jamais suppose), sous
    `<cible>/<worktree>/_ORIGINAL/<chemin>` -- sans original, aucun diff
    n'est possible et l'audit ne peut pas avoir lieu ;
  - il ecrit un manifeste JSON et un manifeste Markdown.

Il n'ecrit JAMAIS dans un worktree, jamais dans l'arbre principal, et
n'appelle jamais git sans `-C` explicite. Un worktree illisible ou un git
en echec ne l'arrete pas : l'erreur est comptee, nommee dans le manifeste,
et le programme continue -- une garde qui plante est pire qu'une garde
absente.

Portabilite (contrat §0.5)
---------------------------
La racine se derive de `__file__`, jamais d'un chemin grave. `--racine` la
force explicitement. Aucune fonction de lecture git n'assume l'existence
d'un remote particulier : ce script degrade (erreur nommee) plutot que de
planter des qu'un worktree ou un depot est absent ou corrompu.

Preuve, jamais seulement provenance
------------------------------------
Le manifeste enregistrait branche, tete, retard de commits et statut git --
la PROVENANCE d'un fichier, jamais la preuve qu'il a ete verifie. Pour
chaque worktree, ce script cherche maintenant un fichier de preuve
(`<worktree>/QUARANTAINE.md`, puis `<worktree>/rituels/QUARANTAINE.md`)
suivant le gabarit a huit rubriques `rituels/GABARIT_QUARANTAINE.md`, et
rapporte pour chacune si elle est REMPLIE ou VIDE -- jamais si elle est
BONNE : ce collecteur ne juge aucun contenu et ne calcule aucune couleur,
il RAPPORTE ce que l'auteur a ecrit, ou son absence (contrat §0.7.1).
MANIFESTE.md separe desormais SANS PREUVE, PREUVE PARTIELLE et PREUVE
COMPLETE en sections distinctes : un fichier sans preuve ne figure plus
jamais dans le meme tableau qu'un fichier prouve.

Usage
-----
    python outillage/nexus_quarantaine.py --simulation
    python outillage/nexus_quarantaine.py
    python outillage/nexus_quarantaine.py --json
    python outillage/nexus_quarantaine.py --cible D:/ailleurs/QUARANTAINE ^
        --worktrees D:/ailleurs/.claude/worktrees
"""
from __future__ import annotations

import os
import re
import sys

# Reconfiguration de la console AVANT toute autre instruction executable :
# la console Windows par defaut est en cp1252 et fait tomber tout print()
# qui porte un accent ou un guillemet typographique. `console_tools` est
# l'utilitaire deja partage du depot pour cela (scripts/console_tools.py) ;
# si ce fichier est copie hors du depot sans son voisin, le repli inline
# fait le meme travail sans lever d'exception -- degrader, jamais planter.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from console_tools import forcer_utf8 as _forcer_utf8
    _forcer_utf8()
except Exception:
    import contextlib
    with contextlib.suppress(Exception):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import argparse
import json
import shutil
import subprocess
from datetime import datetime, timezone

BRANCHE_PRINCIPALE = "main"
PREFIXE_AGENT = "agent-"
DELAI_GIT_S = 30


# ------------------------------------------------------------------
# Derivation de la racine et de l'arbre principal
# ------------------------------------------------------------------

def racine_defaut() -> str:
    """La racine du depot ou vit ce script : le parent de scripts/."""
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _git(args: list, cwd: str) -> subprocess.CompletedProcess:
    """Execute git -C <cwd> <args>. Jamais sans -C, jamais sans delai."""
    return subprocess.run(
        ["git", "-C", cwd] + args,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=DELAI_GIT_S,
    )


def arbre_principal(racine: str):
    """Decouvre l'arbre principal via `git worktree list`, jamais suppose.

    Le premier "worktree <chemin>" rendu par git est TOUJOURS l'arbre
    d'origine (celui qui existait avant tout `git worktree add`) : c'est
    documente par git lui-meme, pas une convention de ce depot. Verifie
    empiriquement sur ce depot le 2026-09-02 : la premiere entree est bien
    `C:/local-llm-docker`, la seule ou vivent les originaux "de reference".
    Repli sur `racine` si la commande echoue : degrader plutot que
    planter, ce qui reste correct dans le cas normal ou ce script vit
    directement dans l'arbre principal.

    Retourne (chemin, erreur_ou_None).
    """
    try:
        r = _git(["worktree", "list", "--porcelain"], racine)
    except (OSError, subprocess.SubprocessError) as exc:
        return racine, "git worktree list injoignable (%s) -- repli sur --racine" % exc
    if r.returncode != 0:
        detail = (r.stderr or r.stdout or "code %d" % r.returncode).strip()[:200]
        return racine, "git worktree list a echoue (%s) -- repli sur --racine" % detail
    for ligne in r.stdout.splitlines():
        if ligne.startswith("worktree "):
            return ligne[len("worktree "):].strip(), None
    return racine, "aucune entree 'worktree' dans la sortie -- repli sur --racine"


# ------------------------------------------------------------------
# Lecture de l'etat d'un worktree (toujours en lecture seule)
# ------------------------------------------------------------------

def tete_et_branche(w: str):
    tete = branche = None
    try:
        r = _git(["rev-parse", "--short", "HEAD"], w)
        if r.returncode == 0:
            tete = r.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        pass
    try:
        r = _git(["rev-parse", "--abbrev-ref", "HEAD"], w)
        if r.returncode == 0:
            branche = r.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        pass
    return tete, branche


def lister_non_commites(w: str):
    """{chemin_relatif: code_statut_porcelain} pour le NON commite.

    `-z` est imperatif : sans lui, git cite entre guillemets tout chemin
    portant un caractere non-ASCII ou un espace, et le decoupage se romp.
    Format verifie empiriquement le 2026-09-02 sur un depot jetable :
    chaque entree est `XY<espace><chemin>` ; pour un renommage (X ou Y
    valant R/C), un jeton SUPPLEMENTAIRE et NU (sans prefixe de statut)
    suit, portant l'ANCIEN chemin -- on garde le NOUVEAU (celui deja lu),
    qui est l'etat reel sur disque.
    """
    try:
        r = _git(["status", "--porcelain=v1", "-z"], w)
    except (OSError, subprocess.SubprocessError) as exc:
        return {}, str(exc)
    if r.returncode != 0:
        return {}, (r.stderr or r.stdout or "code %d" % r.returncode).strip()[:300]
    jetons = [j for j in r.stdout.split("\0") if j]
    out = {}
    i = 0
    while i < len(jetons):
        jeton = jetons[i]
        i += 1
        if len(jeton) < 3:
            continue
        statut, chemin = jeton[:2], jeton[3:]
        if statut[0] in ("R", "C") and i < len(jetons):
            i += 1  # ancien chemin, non retenu
        out[chemin.replace("\\", "/")] = statut
    return out, None


def base_fusion(w: str, branche_principale: str = BRANCHE_PRINCIPALE):
    try:
        r = _git(["merge-base", "HEAD", branche_principale], w)
    except (OSError, subprocess.SubprocessError) as exc:
        return None, str(exc)
    if r.returncode != 0:
        return None, (r.stderr or r.stdout or "code %d" % r.returncode).strip()[:300]
    return r.stdout.strip(), None


def lister_commits(w: str, base: str):
    """{chemin_relatif: code_statut} pour ce que HEAD porte au-dela de `base`.

    C'est le remede exact au piege mesure : jamais `diff main HEAD` (qui
    inclut le retard de branche), toujours `diff <base_de_fusion> HEAD`.
    Format `-z` verifie empiriquement le 2026-09-02 : jetons NUL-separes
    `statut, [ancien_chemin,] nouveau_chemin` -- pour R/C, l'ANCIEN chemin
    precede le NOUVEAU (ordre inverse de `status -z`, verifie separement).
    """
    try:
        r = _git(["diff", "--name-status", "-z", base, "HEAD"], w)
    except (OSError, subprocess.SubprocessError) as exc:
        return {}, str(exc)
    if r.returncode != 0:
        return {}, (r.stderr or r.stdout or "code %d" % r.returncode).strip()[:300]
    jetons = [j for j in r.stdout.split("\0") if j]
    out = {}
    i = 0
    while i < len(jetons):
        statut = jetons[i]
        i += 1
        if statut[:1] in ("R", "C"):
            if i + 1 >= len(jetons):
                break
            i += 1  # ancien chemin, non retenu
            chemin = jetons[i]
            i += 1
        else:
            if i >= len(jetons):
                break
            chemin = jetons[i]
            i += 1
        out[chemin.replace("\\", "/")] = statut
    return out, None


def compter_commits(w: str, base: str, cible: str):
    try:
        r = _git(["rev-list", "--count", "%s..%s" % (base, cible)], w)
    except (OSError, subprocess.SubprocessError):
        return None
    if r.returncode != 0:
        return None
    try:
        return int(r.stdout.strip())
    except ValueError:
        return None


# ------------------------------------------------------------------
# Verification de la preuve (gabarit a huit rubriques)
# ------------------------------------------------------------------
#
# Le manifeste enregistrait la PROVENANCE (branche, tete, retard, statut
# git) mais aucune PREUVE : un fichier dont l'auteur a joue ses trois
# epreuves et un fichier dont l'auteur n'en a joue aucune arrivaient
# identiques en quarantaine. Ce qui suit cherche, pour chaque worktree,
# un fichier de preuve suivant `rituels/GABARIT_QUARANTAINE.md` (huit
# rubriques numerotees, la quatrieme portant les trois epreuves 4a/4b/4c),
# et rapporte pour chaque rubrique si elle est REMPLIE ou VIDE.
#
# Le critere ne juge JAMAIS le CONTENU d'une rubrique -- seulement sa
# PRESENCE. Une rubrique compte comme VIDE si sa zone de reponse est un
# crochet vide (`[ ]`), un tiret seul (`-`), moins de trois caracteres
# utiles, ou l'une des listes d'options non tranchees que porte le
# gabarit vide lui-meme (`ROUGE / JAUNE / VERT`, `commite / non-commite`,
# `chemin relatif ou FICHIER NEUF`) : ces listes sont copiees telles
# quelles quand la rubrique n'a pas ete touchee, jamais une reponse.
#
# Choix delibere : une rubrique a PLUSIEURS zones de reponse (section 1
# porte trois crochets) compte comme remplie seulement si TOUTES ses
# zones portent une reponse, pas seulement une. Un outil de quarantaine
# sert a ne jamais confondre sain et contamine (consigne de l'operateur) ;
# une rubrique a moitie renseignee reste, par construction, une preuve
# incomplete.
#
# Ce collecteur ne calcule et ne propose AUCUNE couleur : il RAPPORTE
# celle que l'auteur a ecrite, ou son absence. Le jugement reste au tiers
# qui audite (contrat §0.7.1).

NOMS_PREUVE = ("QUARANTAINE.md", os.path.join("rituels", "QUARANTAINE.md"))

# Mesure du 2026-09-03, sur la flotte REELLE (10 fichiers de preuve reels
# trouves sous .claude/worktrees) : 10 sur 10 emploient '##' pour leurs
# huit rubriques, jamais le '###' du gabarit de reference -- confirme par
# grep independant, pas suppose. Le motif accepte donc {2,3} dieses. Le
# lookahead (?!\d) est necessaire : au moins 3 des 10 fichiers reels
# numerotent leurs sous-parties '4.1', '4.2', ... (une entree par fichier
# audite) -- sans lui, '### 4.1' serait lu comme une SECONDE rubrique 4
# et tronquerait le corps de la vraie rubrique 4 a sa premiere ligne.
# Pour les sous-epreuves 4a/4b/4c, AUCUN des 10 fichiers reels n'emploie
# la lettre a/b/c (ils numerotent par fichier, voir plus haut) : {3,4}
# dieses est une largeur symetrique avec la rubrique-mere, non confirmee
# par une mesure -- elle ne change rien sur les 10 fichiers connus.
_RE_SECTION = re.compile(r"^#{2,3}\s+([1-8])\.(?!\d)\s*.*$", re.MULTILINE)
_RE_SOUS_EPREUVE = re.compile(r"^#{3,4}\s+4([abc])\.\s*.*$", re.MULTILINE)
_RE_COULEUR_MOT = re.compile(r"\b(ROUGE|JAUNE|VERT)\b", re.IGNORECASE)
_RE_PROPOSE_LABEL = re.compile(r"\*{0,2}Propos[ée]\*{0,2}\s*:\s*([^\n]*)", re.IGNORECASE)

SOUS_EPREUVES = (("a", "test"), ("b", "reverse"), ("c", "forward"))

# Options non tranchees copiees telles quelles depuis le gabarit vide :
# leur presence signale une rubrique NON REMPLIE, jamais une reponse.
_PLACEHOLDERS_OPTIONS = (
    re.compile(r"rouge\s*/\s*jaune\s*/\s*vert", re.IGNORECASE),
    re.compile(r"commit[ée]\s*/\s*non[- ]commit[ée]", re.IGNORECASE),
    re.compile(r"chemin\s+relatif\s+ou.*fichier\s+neuf", re.IGNORECASE),
)


def _decouper_sections(texte: str) -> dict:
    """{numero: corps_texte} pour chaque '### N.' rencontre (N=1..8).

    Un fichier de preuve est traite comme UNE evaluation par worktree :
    seule la PREMIERE occurrence de chaque numero est retenue. Si un
    fichier empile plusieurs entrees (une par fichier audite), les
    suivantes sont ignorees -- limite assumee, jamais silencieuse : elle
    est nommee dans le rapport de la tache, pas dans ce commentaire."""
    positions = [(int(m.group(1)), m.end()) for m in _RE_SECTION.finditer(texte)]
    bornes = [p[1] for p in positions] + [len(texte)]
    corps = {}
    for idx, (numero, fin_entete) in enumerate(positions):
        if numero not in corps:
            corps[numero] = texte[fin_entete:bornes[idx + 1]]
    return corps


def _decouper_sous_epreuves(corps_s4: str) -> dict:
    """{'a'|'b'|'c': corps_texte} pour chaque '#### 4x.' de la rubrique 4."""
    positions = [(m.group(1), m.end()) for m in _RE_SOUS_EPREUVE.finditer(corps_s4)]
    bornes = [p[1] for p in positions] + [len(corps_s4)]
    corps = {}
    for idx, (lettre, fin_entete) in enumerate(positions):
        if lettre not in corps:
            corps[lettre] = corps_s4[fin_entete:bornes[idx + 1]]
    return corps


# Correction du 2026-09-03 -- audit du troisieme temps (§0.7.1), FAUX VERT
# mesure sur deux fiches REELLES :
#   agent-a6d8fb7354cc50b30 : rubrique 8 = une phrase en italique
#     ('rien n'a ete inscrit ici par l'auteur') PUIS un tableau markdown
#     '| champ | reponse |' dont chaque ligne de donnees est '| champ | |'
#     -- ni crochet ni bloc code, donc AUCUNE zone vue par l'ancienne
#     _extraire_slots ; le repli sur texte brut lisait le texte comme
#     'assez long donc rempli'.
#   agent-a95a4421aa8062ff1 : rubrique 8 = '(laisse vide)', trois mots,
#     meme repli, meme verdict errone.
# Les deux etaient RESPECTIVEMENT verifiees REMPLIE=True avant ce patch
# (voir la contre-epreuve dediee, qui rejoue ces deux textes exacts).


def _est_ligne_separateur_tableau(ligne: str) -> bool:
    """VRAI si `ligne` est la ligne de separateurs d'un tableau markdown
    (ex. '| --- | --- |') : chaque cellule ne contient que des tirets et,
    au besoin, des ':' d'alignement -- jamais du texte."""
    corps = ligne.strip()
    if "-" not in corps or "|" not in corps:
        return False
    cellules = corps.strip("|").split("|")
    if not cellules:
        return False
    return all(re.fullmatch(r"\s*:?-{2,}:?\s*", c) for c in cellules)


def _extraire_cellules_tableaux(texte: str) -> list:
    """Cellules de REPONSE des tableaux markdown : pour chaque tableau
    (une ligne d'en-tete, une ligne de separateurs, puis des lignes de
    donnees), rend la DEUXIEME cellule et les suivantes de chaque ligne de
    DONNEES -- jamais l'en-tete (elle porterait le mot 'reponse' et
    fausserait tout), jamais la ligne de separateurs, et jamais la
    premiere colonne (le libelle du champ, ex. 'auditeur', 'date').
    Mesure du 2026-09-03 sur agent-a6d8fb7354cc50b30 : une rubrique 8
    entierement faite de '| auditeur | |', '| date | |' etc. ne portait
    NI crochet NI bloc code -- invisible a _extraire_slots avant cet
    ajout, donc lue comme remplie par le seul repli sur texte brut."""
    lignes = texte.split("\n")
    cellules = []
    i = 0
    while i < len(lignes) - 1:
        if "|" in lignes[i] and _est_ligne_separateur_tableau(lignes[i + 1]):
            j = i + 2
            while j < len(lignes) and "|" in lignes[j] and lignes[j].strip():
                cols = [c.strip() for c in lignes[j].strip().strip("|").split("|")]
                cellules.extend(cols[1:])  # jamais la colonne de libelle
                j += 1
            i = j
        else:
            i += 1
    return cellules


def _extraire_slots(texte: str) -> list:
    """Zones de reponse d'une rubrique : le corps de chaque bloc code
    (```...```), hors bloc code chaque groupe entre crochets [...], et
    chaque cellule de reponse (hors libelle) des tableaux markdown.
    C'est exactement la ou le gabarit ET les fiches reelles placent leurs
    blancs (verifie contre `rituels/GABARIT_QUARANTAINE.md` ET contre les
    fiches reelles de `.claude/worktrees` -- voir la correction du
    2026-09-03 ci-dessus)."""
    zones = []

    def _capture(m):
        zones.append(m.group(1))
        return ""

    sans_code = re.sub(r"```[^\n]*\n(.*?)```", _capture, texte, flags=re.DOTALL)
    for m in re.finditer(r"\[([^\[\]]*)\]", sans_code):
        zones.append(m.group(1))
    zones.extend(_extraire_cellules_tableaux(sans_code))
    return zones


def _normaliser_slot(c: str) -> str:
    c = c.strip()
    if c.startswith("[") and c.endswith("]") and c.count("[") == 1 and c.count("]") == 1:
        c = c[1:-1].strip()
    return c


# Declarations explicites de vacance en PROSE LIBRE, mesurees sur les deux
# memes fiches reelles ('rien n'a ete inscrit ici par l'auteur' ;
# 'laisse vide') : ni l'une ni l'autre ne porte de crochet [ ], donc
# seul le repli sur texte brut de _rubrique_remplie les voit. Ancre en
# DEBUT de texte normalise (apres avoir retire la ponctuation decorative
# de tete) pour ne jamais confondre avec un usage substantiel du mot au
# milieu d'une reponse reelle : '(aucun)' comme reponse a « effets de
# bord » reste une reponse valide, jamais VIDE par ce motif, parce que
# 'aucun' seul n'y figure pas et que le motif est ancre en tete, pas
# cherche n'importe ou dans le texte.
_RE_DECLARE_VIDE = re.compile(
    r"^(vide\b"
    r"|laiss[ée]e?\s+vide"
    r"|reste\s+vide"
    r"|rien\s+n['\s]a\s+(?:ete|été)?\s*(?:inscrit|ecrit|écrit|renseigne|renseigné|rempli)"
    r"|non[- ]rempli"
    r"|pas\s+(?:encore\s+)?rempli"
    r"|sans\s+reponse"
    r"|aucune\s+reponse"
    r"|a\s+remplir\s+par)",
    re.IGNORECASE,
)

_TETE_DECORATIVE = "*_()«»\"'-–— \t\n"


def _slot_vide(contenu: str) -> bool:
    """VIDE si crochet vide, tiret seul, moins de trois caracteres utiles,
    une des listes d'options non tranchees du gabarit vide, OU si le texte
    declare lui-meme sa vacance (_RE_DECLARE_VIDE). Ce dernier cas ne
    depend JAMAIS de la longueur : une phrase de vingt mots qui ne fait
    que dire qu'elle est vide reste VIDE -- la detection porte sur la
    PRESENCE d'une reponse, pas sur le nombre de caracteres (correction du
    2026-09-03, voir _extraire_slots ci-dessus pour la mesure)."""
    c = _normaliser_slot(contenu or "")
    if not c or c == "-" or len(c) < 3:
        return True
    if any(p.search(c) for p in _PLACEHOLDERS_OPTIONS):
        return True
    tete = c.lstrip(_TETE_DECORATIVE)
    return bool(_RE_DECLARE_VIDE.match(tete))


def _rubrique_remplie(corps: str) -> bool:
    """VRAI seulement si TOUTES les zones de reponse de la rubrique
    portent une reponse (voir le choix delibere plus haut). Sans zone
    reconnue (ni crochet, ni bloc code, ni tableau), le texte brut est
    juge par le meme critere -- accommode un auteur qui a ecrit en prose
    libre sans suivre la ponctuation exacte du gabarit."""
    slots = _extraire_slots(corps or "")
    if slots:
        return all(not _slot_vide(s) for s in slots)
    return not _slot_vide(corps or "")


def _extraire_couleur(corps_section5: str):
    """Couleur ECRITE PAR L'AUTEUR dans la rubrique 5, ou None. Ne calcule
    et ne propose RIEN (§0.7.1) : rapporte ce qui est ecrit, ou son
    absence."""
    if not _rubrique_remplie(corps_section5 or ""):
        return None
    for m in _RE_PROPOSE_LABEL.finditer(corps_section5):
        c = _RE_COULEUR_MOT.search(m.group(1))
        if c:
            return c.group(1).upper()
    nettoye = corps_section5
    for motif in _PLACEHOLDERS_OPTIONS:
        nettoye = motif.sub("", nettoye)
    m = _RE_COULEUR_MOT.search(nettoye)
    return m.group(1).upper() if m else None


def _chercher_preuve(chemin_w: str):
    """Rend (chemin_relatif_ou_None, texte_ou_None, erreur_ou_None).
    Cherche d'abord '<worktree>/QUARANTAINE.md', puis
    '<worktree>/rituels/QUARANTAINE.md'. L'absence des deux n'est PAS une
    erreur de collecte : c'est un fait a rapporter (PREUVE_ABSENTE)."""
    for rel in NOMS_PREUVE:
        chemin = os.path.join(chemin_w, rel)
        if os.path.isfile(chemin):
            try:
                with open(chemin, encoding="utf-8", errors="replace") as f:
                    return rel.replace(os.sep, "/"), f.read(), None
            except OSError as exc:
                return rel.replace(os.sep, "/"), None, str(exc)
    return None, None, None


def analyser_preuve(texte) -> dict:
    """Bloc 'verification' pour un texte de preuve, ou pour son absence
    (texte=None). Le critere porte sur la PRESENCE d'une reponse par
    rubrique, jamais sur son contenu."""
    if texte is None:
        return {
            "preuve_presente": False,
            "rubriques_remplies": 0,
            "trois_epreuves": {"test": False, "reverse": False, "forward": False},
            "couleur_proposee": None,
            "audit_tiers_rempli": False,
        }
    sections = _decouper_sections(texte)
    remplies = sum(1 for n in range(1, 9) if _rubrique_remplie(sections.get(n, "")))
    sous = _decouper_sous_epreuves(sections.get(4, ""))
    trois = {nom: _rubrique_remplie(sous.get(lettre, "")) for lettre, nom in SOUS_EPREUVES}
    return {
        "preuve_presente": True,
        "rubriques_remplies": remplies,
        "trois_epreuves": trois,
        "couleur_proposee": _extraire_couleur(sections.get(5, "")),
        "audit_tiers_rempli": _rubrique_remplie(sections.get(8, "")),
    }


def classer_preuve(verification: dict) -> str:
    """SANS_PREUVE / PREUVE_PARTIELLE / PREUVE_COMPLETE. Jamais de
    couleur ici -- seulement l'etat de la preuve elle-meme.

    Correction du 2026-09-03 (audit du troisieme temps, §0.7.1) :
    PREUVE_COMPLETE n'exigeait que 8/8 rubriques, ce qui admettait une
    contradiction mesuree sur la flotte reelle -- deux fiches a '8/8'
    dont les trois epreuves de la rubrique 4 lisaient VIDE/VIDE/VIDE
    (fiches qui numerotent leurs sous-parties par fichier audite,
    '4.1'/'4.2', jamais par lettre 'a'/'b'/'c' -- voir _RE_SOUS_EPREUVE
    et le rapport de tache pour la mesure : 0 fiche reelle sur 10
    n'emploie la lettre). Le contrat de ce depot (§0.1.4.1) rend les
    trois epreuves TOUTES obligatoires, aucune optionnelle : une fiche ne
    peut donc plus etre COMPLETE si l'une d'elles reste illisible pour ce
    parseur, meme si les huit rubriques sont par ailleurs remplies. Rend
    PARTIELLE, jamais COMPLETE, tant que le parseur ne sait pas lire la
    convention par fichier -- conservateur par construction, jamais
    l'inverse (contrat : ne jamais confondre sain et contamine)."""
    if not verification["preuve_presente"]:
        return "SANS_PREUVE"
    trois = verification["trois_epreuves"]
    if verification["rubriques_remplies"] >= 8 and all(trois.values()):
        return "PREUVE_COMPLETE"
    return "PREUVE_PARTIELLE"


# ------------------------------------------------------------------
# Traitement d'un worktree
# ------------------------------------------------------------------

def traiter_worktree(chemin_w: str, nom_w: str, arbre_princ: str,
                      cible_racine: str, simulation: bool,
                      branche_principale: str = BRANCHE_PRINCIPALE) -> dict:
    preuve_fichier, preuve_texte, preuve_erreur = _chercher_preuve(chemin_w)
    verification = analyser_preuve(preuve_texte)
    resultat = {
        "nom": nom_w, "chemin": chemin_w, "branche": None, "tete": None,
        "retard_commits": None, "commits_agent": None, "erreur": None,
        "preuve_fichier": preuve_fichier, "preuve_erreur": preuve_erreur,
        "verification": verification, "classification": classer_preuve(verification),
        "fichiers": [],
    }

    a_git = os.path.exists(os.path.join(chemin_w, ".git"))
    if not a_git:
        resultat["erreur"] = "pas un depot git ('.git' absent de %s)" % chemin_w
        return resultat

    resultat["tete"], resultat["branche"] = tete_et_branche(chemin_w)

    non_commites, err_statut = lister_non_commites(chemin_w)
    if err_statut:
        resultat["erreur"] = "git status a echoue : %s" % err_statut
        return resultat

    commites = {}
    base, err_base = base_fusion(chemin_w, branche_principale)
    if err_base:
        resultat["erreur"] = "git merge-base a echoue : %s" % err_base
        # Degrade : les non-commites restent exploitables, on les traite
        # quand meme plutot que de tout perdre pour cette seule erreur.
    else:
        commites, err_diff = lister_commits(chemin_w, base)
        if err_diff:
            resultat["erreur"] = "git diff a echoue : %s" % err_diff
        else:
            resultat["retard_commits"] = compter_commits(chemin_w, base, branche_principale)
            resultat["commits_agent"] = compter_commits(chemin_w, base, "HEAD")

    fusion = {}
    for chemin, statut in commites.items():
        fusion[chemin] = {"etat": "commite", "statut_git": statut}
    for chemin, statut in non_commites.items():
        # Le non-commite prime : c'est l'etat REEL sur disque, celui qui
        # sera copie. Un fichier commite puis encore modifie ne doit pas
        # etre compte deux fois.
        fusion[chemin] = {"etat": "non_commite", "statut_git": statut}

    for chemin_rel in sorted(fusion):
        info = fusion[chemin_rel]
        entree = {
            "chemin": chemin_rel, "etat": info["etat"], "statut_git": info["statut_git"],
            "octets": None, "copie_erreur": None,
            "original_present": False, "original_octets": None, "original_erreur": None,
            "verification": resultat["verification"],
        }
        chemin_os = chemin_rel.replace("/", os.sep)
        src = os.path.join(chemin_w, chemin_os)
        if os.path.isfile(src):
            try:
                entree["octets"] = os.path.getsize(src)
                if not simulation:
                    dst = os.path.join(cible_racine, nom_w, chemin_os)
                    os.makedirs(os.path.dirname(dst), exist_ok=True)
                    shutil.copy2(src, dst)
            except OSError as exc:
                entree["copie_erreur"] = str(exc)
        else:
            entree["copie_erreur"] = "absent du worktree (supprime depuis ?)"

        orig = os.path.join(arbre_princ, chemin_os)
        if os.path.isfile(orig):
            entree["original_present"] = True
            try:
                entree["original_octets"] = os.path.getsize(orig)
                if not simulation:
                    dst_orig = os.path.join(cible_racine, nom_w, "_ORIGINAL", chemin_os)
                    os.makedirs(os.path.dirname(dst_orig), exist_ok=True)
                    shutil.copy2(orig, dst_orig)
            except OSError as exc:
                entree["original_erreur"] = str(exc)

        resultat["fichiers"].append(entree)

    return resultat


# ------------------------------------------------------------------
# Manifestes
# ------------------------------------------------------------------

def _comptes_par_population(resultats) -> dict:
    """{"SANS_PREUVE"|"PREUVE_PARTIELLE"|"PREUVE_COMPLETE": {"fichiers": n, "worktrees": n}}
    -- calcule UNE fois, lu par le JSON et par le Markdown, pour que les
    deux ne puissent jamais diverger."""
    comptes = {p: {"fichiers": 0, "worktrees": 0} for p in
               ("SANS_PREUVE", "PREUVE_PARTIELLE", "PREUVE_COMPLETE")}
    for r in resultats:
        pop = r.get("classification", "SANS_PREUVE")
        comptes[pop]["worktrees"] += 1
        comptes[pop]["fichiers"] += len(r["fichiers"])
    return comptes


def construire_manifeste(racine, arbre_princ, err_arbre_princ, cible,
                          worktrees_dir, simulation, resultats) -> dict:
    return {
        "genere_le": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "outil": "outillage/nexus_quarantaine.py",
        "gabarit_audit": "rituels/GABARIT_QUARANTAINE.md",
        "racine": racine,
        "arbre_principal": arbre_princ,
        "arbre_principal_erreur": err_arbre_princ,
        "cible": cible,
        "worktrees_dir": worktrees_dir,
        "simulation": simulation,
        "resume": {
            "worktrees_examines": len(resultats),
            "worktrees_en_erreur": sum(1 for r in resultats if r["erreur"]),
            "fichiers_total": sum(len(r["fichiers"]) for r in resultats),
            "comptes_preuve": _comptes_par_population(resultats),
        },
        "worktrees": resultats,
    }


def ecrire_manifeste_json(cible: str, manifeste: dict) -> None:
    chemin = os.path.join(cible, "MANIFESTE.json")
    with open(chemin, "w", encoding="utf-8", newline="\n") as f:
        json.dump(manifeste, f, ensure_ascii=False, indent=2)
        f.write("\n")


def _ligne_fichier(f: dict) -> str:
    chemin = f["chemin"].replace("|", "\\|")
    etat = f["etat"] + (" (%s)" % f["statut_git"] if f["statut_git"] else "")
    octets = "%d" % f["octets"] if f["octets"] is not None else "?"
    if f["copie_erreur"]:
        octets += " [ERREUR COPIE: %s]" % f["copie_erreur"]
    if f["original_present"]:
        orig = "oui (%s octets)" % (f["original_octets"] if f["original_octets"] is not None else "?")
    else:
        orig = "NON -- FICHIER NEUF"
    if f["original_erreur"]:
        orig += " [ERREUR: %s]" % f["original_erreur"]
    return "| `%s` | %s | %s | %s |" % (chemin, etat, octets, orig)


POPULATIONS_PREUVE = ("SANS_PREUVE", "PREUVE_PARTIELLE", "PREUVE_COMPLETE")
TITRES_POPULATION = {
    "SANS_PREUVE": "SANS PREUVE",
    "PREUVE_PARTIELLE": "PREUVE PARTIELLE",
    "PREUVE_COMPLETE": "PREUVE COMPLETE",
}


def _lignes_verification(w: dict) -> list:
    v = w["verification"]
    L = []
    L.append("- fichier de preuve : %s" % (
        ("`%s`" % w["preuve_fichier"]) if w["preuve_fichier"] else "AUCUN"
    ))
    if w.get("preuve_erreur"):
        L.append("- **ERREUR DE LECTURE DE LA PREUVE** : %s" % w["preuve_erreur"])
    if v["preuve_presente"]:
        te = v["trois_epreuves"]
        L.append("- rubriques remplies : %d/8" % v["rubriques_remplies"])
        L.append("- trois epreuves -- test : %s, reverse : %s, forward : %s" % (
            "remplie" if te["test"] else "VIDE",
            "remplie" if te["reverse"] else "VIDE",
            "remplie" if te["forward"] else "VIDE",
        ))
        L.append("- couleur proposee par l'auteur : %s" % (v["couleur_proposee"] or "(aucune)"))
        L.append("- audit du tiers (rubrique 8) : %s" % (
            "rempli" if v["audit_tiers_rempli"] else "VIDE"
        ))
    return L


def ecrire_manifeste_md(cible: str, manifeste: dict) -> None:
    L = []
    L.append("# MANIFESTE DE QUARANTAINE")
    L.append("")
    L.append("Genere le %s par `%s`." % (manifeste["genere_le"], manifeste["outil"]))
    L.append("")
    L.append("| champ | valeur |")
    L.append("| --- | --- |")
    L.append("| racine | `%s` |" % manifeste["racine"])
    ap = manifeste["arbre_principal"]
    if manifeste["arbre_principal_erreur"]:
        ap += " (%s)" % manifeste["arbre_principal_erreur"]
    L.append("| arbre principal (source des originaux) | `%s` |" % ap)
    L.append("| dossier des worktrees | `%s` |" % manifeste["worktrees_dir"])
    L.append("| dossier de quarantaine | `%s` |" % manifeste["cible"])
    L.append("| simulation | %s |" % ("oui" if manifeste["simulation"] else "non"))
    L.append("")
    r = manifeste["resume"]
    cp = r["comptes_preuve"]
    L.append("## Comptes par population")
    L.append("")
    for p in POPULATIONS_PREUVE:
        L.append("- **%s** : %d fichier(s) dans %d worktree(s)" % (
            TITRES_POPULATION[p], cp[p]["fichiers"], cp[p]["worktrees"]))
    L.append("")
    L.append("## Audit")
    L.append("")
    L.append(
        "Pour auditer chaque fichier liste ci-dessous, suivre le gabarit "
        "`rituels/GABARIT_QUARANTAINE.md` (une ligne du tableau = un "
        "« Fichier » du gabarit). La colonne « original » dit si "
        "`_ORIGINAL/<chemin>` existe sous ce worktree en quarantaine : "
        "sans lui, aucun diff n'est possible et l'audit ne peut pas avoir "
        "lieu. « FICHIER NEUF » signifie qu'aucun original n'a ete trouve "
        "dans l'arbre principal -- attendu pour un fichier cree par "
        "l'agent, a verifier sinon. Les trois sections qui suivent "
        "separent les fichiers SANS aucun fichier de preuve, de ceux dont "
        "la preuve est PARTIELLE (fichier trouve, rubriques non toutes "
        "remplies) et de ceux dont la preuve est COMPLETE (huit rubriques "
        "remplies). Le critere porte sur la PRESENCE d'une reponse par "
        "rubrique, jamais sur son contenu, et aucune couleur n'est "
        "calculee ici : seule celle ECRITE PAR L'AUTEUR est rapportee, ou "
        "son absence (contrat §0.7.1)."
    )
    L.append("")
    L.append("## Resume")
    L.append("")
    L.append("- worktrees examines : %d" % r["worktrees_examines"])
    L.append("- worktrees en erreur : %d" % r["worktrees_en_erreur"])
    L.append("- fichiers au total : %d" % r["fichiers_total"])
    L.append("")

    for p in POPULATIONS_PREUVE:
        L.append("## %s" % TITRES_POPULATION[p])
        L.append("")
        worktrees_pop = [w for w in manifeste["worktrees"] if w.get("classification") == p]
        if not worktrees_pop:
            L.append("(aucun worktree dans cette population)")
            L.append("")
            continue
        for w in worktrees_pop:
            L.append("### %s" % w["nom"])
            L.append("")
            L.append("- branche : `%s`" % (w["branche"] or "?"))
            L.append("- tete : `%s`" % (w["tete"] or "?"))
            L.append("- retard sur %s (commits non repris) : %s" % (
                BRANCHE_PRINCIPALE,
                w["retard_commits"] if w["retard_commits"] is not None else "?",
            ))
            L.append("- commits de l'agent au-dela de la base commune : %s" % (
                w["commits_agent"] if w["commits_agent"] is not None else "?",
            ))
            L.extend(_lignes_verification(w))
            if w["erreur"]:
                L.append("- **ERREUR DE COLLECTE** : %s" % w["erreur"])
            L.append("")
            if w["fichiers"]:
                L.append("| fichier | etat | octets | original |")
                L.append("| --- | --- | --- | --- |")
                for f in w["fichiers"]:
                    L.append(_ligne_fichier(f))
            elif not w["erreur"]:
                L.append("(aucun fichier commite ou non commite au-dela de la base de fusion)")
            L.append("")

    chemin = os.path.join(cible, "MANIFESTE.md")
    with open(chemin, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(L) + "\n")


# ------------------------------------------------------------------
# Point d'entree
# ------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--racine", help="Racine du depot. Defaut : derivee de __file__.")
    ap.add_argument("--cible", help="Dossier de quarantaine. Defaut : <racine>/rituels/QUARANTAINE")
    ap.add_argument("--worktrees", help="Dossier des worktrees. Defaut : <racine>/.claude/worktrees")
    ap.add_argument("--simulation", action="store_true", help="N'ecrit rien, affiche ce qui serait fait.")
    ap.add_argument("--json", action="store_true", help="Sortie machine (JSON) sur stdout.")
    a = ap.parse_args()

    racine = os.path.abspath(a.racine) if a.racine else racine_defaut()
    if not os.path.isdir(racine):
        msg = "la racine n'existe pas : %s" % racine
        if a.json:
            print(json.dumps({"erreur": msg}, ensure_ascii=False))
        else:
            print("REFUS : %s" % msg)
        return 3

    cible = os.path.abspath(a.cible) if a.cible else os.path.join(racine, "rituels", "QUARANTAINE")
    worktrees_dir = os.path.abspath(a.worktrees) if a.worktrees else os.path.join(racine, ".claude", "worktrees")

    # Garde-fou mecanique (pas seulement documente) : si --cible tombe
    # A L'INTERIEUR d'un sous-dossier agent-* de --worktrees, ce n'est
    # tolere QUE si ce sous-dossier est EXACTEMENT celui que --racine
    # designe -- l'appelant a alors choisi, en connaissance de cause, de
    # travailler depuis ce worktree-la (c'est le cas normal d'un agent qui
    # teste l'outil depuis son propre worktree). Toute AUTRE cible tombant
    # sous --worktrees (un autre agent-*, ou --worktrees lui-meme) est
    # refusee : ce serait ecrire dans l'arbre vivant d'un tiers, exactement
    # ce que ce script n'a jamais le droit de faire. En usage normal
    # (racine = arbre principal, hors de .claude/worktrees), cette garde
    # ne s'engage jamais.
    def _dossier_agent_parent(chemin: str, worktrees: str):
        """Rend le sous-dossier direct de `worktrees` qui contient `chemin`,
        ou `worktrees` lui-meme si chemin==worktrees, ou None si `chemin`
        n'est pas sous `worktrees` du tout."""
        try:
            rel = os.path.relpath(os.path.normcase(chemin), os.path.normcase(worktrees))
        except ValueError:
            return None
        if rel == os.curdir:
            return worktrees
        if rel.startswith(os.pardir):
            return None
        return os.path.join(worktrees, rel.split(os.sep)[0])

    ancetre = _dossier_agent_parent(cible, worktrees_dir)
    if ancetre is not None and os.path.normcase(ancetre) != os.path.normcase(racine):
        msg = ("--cible (%s) tombe sous --worktrees (%s) en dehors du "
               "sous-dossier designe par --racine (%s) : refuse pour ne "
               "jamais ecrire dans le worktree d'un tiers" % (cible, worktrees_dir, racine))
        if a.json:
            print(json.dumps({"erreur": msg}, ensure_ascii=False))
        else:
            print("REFUS : %s" % msg)
        return 1

    arbre_princ, err_arbre_princ = arbre_principal(racine)

    if not os.path.isdir(worktrees_dir):
        msg = "dossier des worktrees introuvable : %s" % worktrees_dir
        if a.json:
            print(json.dumps({"erreur": msg, "worktrees_dir": worktrees_dir}, ensure_ascii=False))
        else:
            print("AUCUN WORKTREE EXAMINE : %s" % msg)
        return 1

    try:
        candidats = sorted(
            d for d in os.listdir(worktrees_dir)
            if d.startswith(PREFIXE_AGENT) and os.path.isdir(os.path.join(worktrees_dir, d))
        )
    except OSError as exc:
        msg = "dossier des worktrees illisible : %s (%s)" % (worktrees_dir, exc)
        if a.json:
            print(json.dumps({"erreur": msg, "worktrees_dir": worktrees_dir}, ensure_ascii=False))
        else:
            print("AUCUN WORKTREE EXAMINE : %s" % msg)
        return 1

    if not candidats:
        msg = "aucun sous-dossier '%s*' dans %s" % (PREFIXE_AGENT, worktrees_dir)
        if a.json:
            print(json.dumps({"erreur": msg, "worktrees_dir": worktrees_dir}, ensure_ascii=False))
        else:
            print("AUCUN WORKTREE EXAMINE : %s" % msg)
        return 1

    resultats = []
    for nom in candidats:
        chemin_w = os.path.join(worktrees_dir, nom)
        try:
            r = traiter_worktree(chemin_w, nom, arbre_princ, cible, a.simulation)
        except Exception as exc:  # une garde qui plante est pire qu'une garde absente
            verif_defaut = analyser_preuve(None)
            r = {
                "nom": nom, "chemin": chemin_w, "branche": None, "tete": None,
                "retard_commits": None, "commits_agent": None,
                "preuve_fichier": None, "preuve_erreur": None,
                "verification": verif_defaut, "classification": classer_preuve(verif_defaut),
                "erreur": "exception non prevue : %r" % exc, "fichiers": [],
            }
        resultats.append(r)

    manifeste = construire_manifeste(racine, arbre_princ, err_arbre_princ, cible,
                                      worktrees_dir, a.simulation, resultats)

    if not a.simulation:
        os.makedirs(cible, exist_ok=True)
        ecrire_manifeste_json(cible, manifeste)
        ecrire_manifeste_md(cible, manifeste)

    if a.json:
        print(json.dumps(manifeste, ensure_ascii=False, indent=2))
    else:
        r = manifeste["resume"]
        prefixe = "[SIMULATION] " if a.simulation else ""
        print("%sworktrees examines : %d (dont %d en erreur)" % (
            prefixe, r["worktrees_examines"], r["worktrees_en_erreur"]))
        print("%sfichiers collectes  : %d" % (prefixe, r["fichiers_total"]))
        if not a.simulation:
            print("manifeste : %s" % os.path.join(cible, "MANIFESTE.md"))
        for res in resultats:
            marque = "ERREUR" if res["erreur"] else "%d fichier(s)" % len(res["fichiers"])
            print("  - %-32s %s" % (res["nom"], marque))
            if res["erreur"]:
                print("      %s" % res["erreur"])

    return 0


if __name__ == "__main__":
    sys.exit(main())