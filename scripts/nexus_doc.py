#!/usr/bin/env python3
"""doc_lib.py — consulter la doc Python officielle parsée SANS jamais la charger.

POURQUOI CET OUTIL EXISTE (Enzo, 2026-08-10, règle rendue NON NÉGOCIABLE)
    « ne jamais acter de mémoire, ni répondre de mémoire. tout ce qui est au sujet de python
      ⇒ consulter documentation officielle parsée »
Une règle n'est tenue que si l'obéir coûte moins cher que la contourner. Or consulter cette doc
coûtait cher : 136 Mo répartis en fichiers dont les plus gros font **8,9 Mo** (`torch_api_nn.md`)
et **7,9 Mo** (`pandas_api_core.md`) — de l'ordre de deux millions de tokens. Personne, humain ou
modèle, n'ouvre ça pour vérifier une signature. Le coût d'accès était donc l'ennemi réel de la
règle, et c'est lui que cet outil supprime.

★ LA QUESTION QUI A DÉCLENCHÉ CE MODULE, posée par Enzo : « *a-t-on bien tout de parsé et mâché
tel qu'un Qwen 2.5 3B puisse y arriver ?* » Mesures faites avant de répondre :
  · **couverture** : 28 des 43 paquets tiers réellement importés par le dépôt sont documentés ;
    les manquants réels se réduisent à 7 paquets marginaux (1-2 imports chacun). **La couverture
    n'était pas le problème.**
  · **forme** : la doc est déjà excellemment mâchée — `### \\`symbole\\`` + Type + Signature +
    description. **La forme n'était pas le problème non plus.**
  · **accès** : 166 511 symboles, et aucun index symbole → emplacement. **C'était le problème.**
Un modèle de 3 Md de paramètres tient ~32 k tokens de contexte. Il ne peut pas lire un fichier de
8,9 Mo — mais il peut parfaitement lire **vingt lignes** si on sait lesquelles. Cet outil produit
ces vingt lignes.

## CE QU'IL FAIT
    doc_lib.py --construire            construit l'index (à relancer si la doc change)
    doc_lib.py scipy.stats.bootstrap   rend l'entrée exacte : signature + description
    doc_lib.py bootstrap               recherche floue quand le chemin complet est inconnu
    doc_lib.py --paquets               ce qui est documenté localement, et ce qui ne l'est pas

## OÙ VIT L'INDEX, ET POURQUOI PAS À CÔTÉ DE LA DOC
Sous `workspace/`, jamais sous `references/` : ce dernier est un **corpus externe verbatim**, gelé
en écriture par la politique de permissions — toute retouche y fausserait une citation. L'index est
un DÉRIVÉ, il se régénère ; le corpus est une source, il ne se touche pas.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

try:                                    # 7e panne cp1252 payée le 2026-08-10 : plus jamais.
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from console_tools import forcer_utf8 as _forcer_utf8
    _forcer_utf8()
except ImportError:
    pass

# La racine se DEDUIT de la position de ce fichier, jamais du repertoire
# courant ni d'un marqueur cherche en remontant : ce script est appele
# depuis n'importe ou, y compris depuis un autre projet.
MARQUEUR_RACINE = "CLAUDE.md"
RACINE_FIXE = Path(__file__).resolve().parent.parent
DOSSIER_DOC = Path("references") / "python_libs_docs"
# `.nexus/` est deja ignore par git : un index a offsets ne se partage
# pas entre machines, il decrit CE corpus a CET endroit.
INDEX = Path(".nexus") / "index_doc_libs.tsv"

# Une entrée de doc commence par `### ` suivi du symbole entre accents graves. Format produit par
# `scrape_pylib_docs.py`, vérifié sur le corpus réel — pas supposé.
ENTREE = re.compile(r"^### `([^`]+)`\s*$")

# Les pages `__LOCALFIRST_<date>` remplacent LOGIQUEMENT une page homonyme antérieure et incomplète
# (extraction d'avant le correctif du 2026-08-02), mais les deux coexistent : leur promotion est
# une décision réservée à Enzo. On indexe donc les deux et on PRÉFÈRE la LOCALFIRST à la lecture —
# indexer l'ancienne seule ferait citer une doc que son propre en-tête déclare périmée.
PREFERE = "__LOCALFIRST"


def trouver_racine(depart: Path):
    """Racine = premier ancêtre portant le marqueur. Aucune lettre de lecteur, aucun niveau figé."""
    for candidat in [depart, *depart.parents]:
        if (candidat / MARQUEUR_RACINE).is_file():
            return candidat
    # Repli sur la racine deduite du fichier : ce depot porte son CLAUDE.md
    # dans .claude/, et la remontee ne trouverait donc rien.
    if (RACINE_FIXE / DOSSIER_DOC).is_dir():
        return RACINE_FIXE
    return None


def construire_index(racine: Path, verifier: int = 200) -> tuple[int, int, int]:
    """Écrit `symbole \\t fichier \\t offset_octets \\t longueur_octets`. Rend (symboles, fichiers, vérifs).

    ★ INDEX À OFFSETS, ET NON À NUMÉROS DE LIGNE — refonte du 2026-08-10 après une mesure du projet
    voisin qui a démoli la première version. Avec des numéros de ligne, la lecture d'une entrée
    passait par `read_text()`, donc chargeait le fichier ENTIER : **8,7 Mo lus pour rendre 1,5 Ko**,
    soit un facteur 5 928 gaspillé sur `torch_api_nn.md`. L'outil réduisait le contexte du modèle,
    pas le coût de lecture. Avec un offset, la lecture est un `seek` + `read(longueur)` : de 1 à
    8 Ko, quelle que soit la taille du fichier. C'est structurel, pas une optimisation.

    ★★ LE PIÈGE DES OFFSETS, signalé par le voisin et VÉRIFIÉ dans la doc officielle locale
    (`doc_lib.py builtins.open` → `python_0059.md`). **Deux puces distinctes, et il faut LES DEUX** :

    - **lecture** (`python_0059.md`, l. 99-102) — c'est CELLE-CI qui fonde le piège :
      *« On input, if newline is None, universal newlines mode is enabled. Lines in the input can
      end in '\\n', '\\r', or '\\r\\n', and these are translated into '\\n' before being returned to
      the caller. »*
      ⇒ un fichier CRLF lu en mode texte rend des lignes **plus courtes de un octet** que sur le
      disque. Tout offset calculé ainsi est décalé d'un octet par ligne précédente, silencieusement.

    - **écriture** (`python_0059.md`, l. 107-108) — elle fonde le `newline=""` côté écriture :
      *« On output, if newline is None, any '\\n' characters written are translated to the system
      default line separator, os.linesep. »*

    ★ CORRECTION DE CHAÎNE DE PREUVE (audit LOI 1, 2026-08-10) : ce docstring ne citait QUE la
    seconde puce, et franchissait l'écart par le mot « symétrique ». La citation était **verbatim
    exacte** — mais elle régit l'ÉCRITURE, alors que la conclusion énoncée porte sur la LECTURE.
    J'avais la bonne citation pour une affirmation et l'ai réemployée pour une autre qu'elle ne
    couvre pas ; le pont était une **inférence**, présentée comme une vérification.
    La règle d'Enzo — « tout ce qui est au sujet de python ⇒ consulter la documentation officielle
    parsée, non négociable » — n'exige pas seulement qu'une citation existe et soit exacte : elle
    exige qu'**elle porte l'affirmation qu'on lui fait porter**. Une citation juste, déplacée d'une
    puce, ne prouve pas ce qu'on croit prouver.

    ⇒ On lit donc en BINAIRE (`read_bytes`), on découpe sur `b"\\n"`, et on compte les octets réels.

    ★★★ ET ON RELIT POUR VÉRIFIER. Un offset faux est **invisible** : le fichier paraît sain et
    l'outil rend simplement le mauvais symbole à la première question. `verifier` échantillons sont
    donc relus par `seek(offset)` et leur identifiant comparé. Sans cette relecture, l'index serait
    un instrument aveugle — il répondrait, mais à côté.
    """
    base = racine / DOSSIER_DOC
    entrees, n_fic = [], 0
    for md in sorted(base.rglob("*.md")):
        if "_QUARANTINE" in str(md):        # extraction web mise en quarantaine : jamais citée
            continue
        rel = md.relative_to(racine).as_posix()
        try:
            brut = md.read_bytes()          # BINAIRE : aucune traduction, offsets réels
        except OSError:
            continue
        n_fic += 1
        positions = []                      # (symbole, offset) dans l'ordre du fichier
        offset = 0
        for ligne in brut.split(b"\n"):
            try:
                m = ENTREE.match(ligne.decode("utf-8", errors="replace").rstrip("\r"))
            except Exception:
                m = None
            if m:
                positions.append((m.group(1), offset))
            offset += len(ligne) + 1        # +1 pour le "\n" retiré par split
        # La longueur d'une entrée va jusqu'au symbole suivant, ou jusqu'à la fin du fichier.
        for i, (sym, off) in enumerate(positions):
            fin = positions[i + 1][1] if i + 1 < len(positions) else len(brut)
            entrees.append((sym, rel, off, fin - off))

    cible = racine / INDEX
    cible.parent.mkdir(parents=True, exist_ok=True)
    # `newline=""` : sans lui, Python traduirait "\n" en "\r\n" à l'écriture sur Windows. L'index
    # DÉCRIT des offsets sans en contenir, donc l'effet serait ici inoffensif — mais l'habitude de
    # laisser une traduction implicite dans un outil qui manipule des offsets est ce qui produit
    # la panne un jour où elle compte.
    with open(cible, "w", encoding="utf-8", newline="") as f:
        for sym, rel, off, lg in entrees:
            f.write(f"{sym}\t{rel}\t{off}\t{lg}\n")

    # ── RELECTURE DE VÉRIFICATION ─────────────────────────────────────────────────────────────
    pas = max(1, len(entrees) // verifier) if verifier else 0
    verifs = 0
    if pas:
        for sym, rel, off, lg in entrees[::pas]:
            try:
                with open(racine / rel, "rb") as f:
                    f.seek(off)
                    tete = f.read(min(lg, 400)).decode("utf-8", errors="replace")
            except OSError:
                continue
            if not tete.startswith(f"### `{sym}`"):
                raise RuntimeError(
                    f"OFFSET FAUX pour {sym} dans {rel} (offset {off}) — index NON écrit comme "
                    f"fiable. Cause probable : traduction de fins de ligne à la lecture.")
            verifs += 1
    return len(entrees), n_fic, verifs


def charger_index(racine: Path) -> list[tuple[str, str, int, int]]:
    """Charge l'index. `newline=""` par symétrie avec l'écriture — on ne traduit rien, jamais."""
    cible = racine / INDEX
    if not cible.is_file():
        return []
    out = []
    with open(cible, "r", encoding="utf-8", newline="") as f:
        for l in f:
            p = l.rstrip("\r\n").split("\t")
            if len(p) == 4:
                out.append((p[0], p[1], int(p[2]), int(p[3])))
    return out


def chercher(index, requete: str, limite: int = 12):
    """Exact d'abord, puis suffixe, puis sous-chaîne — du plus précis au plus large.

    L'ordre compte : `bootstrap` doit rendre `scipy.stats.bootstrap` avant
    `sklearn…bootstrap_something`. Rendre les correspondances larges en premier ferait manquer la
    bonne réponse à un modèle qui ne lit que le premier résultat.
    """
    r = requete.lower()
    exact = [e for e in index if e[0].lower() == r]
    suffixe = [e for e in index if e[0].lower().endswith("." + r) and e not in exact]
    partiel = [e for e in index if r in e[0].lower() and e not in exact and e not in suffixe]
    ordonne = exact + suffixe + partiel
    # À symbole identique, préférer la page LOCALFIRST : l'ancienne se déclare elle-même incomplète.
    ordonne.sort(key=lambda e: (0 if PREFERE in e[1] else 1))
    return ordonne[:limite]


def extraire(racine: Path, fichier: str, offset: int, longueur: int, contexte: int = 22) -> str:
    """Lit UNIQUEMENT l'entrée demandée : `seek(offset)` puis `read(longueur)`.

    Le fichier n'est jamais chargé. Sur `torch_api_nn.md` (8,7 Mo), cette fonction lit quelques
    kilo-octets — c'est tout l'objet de la refonte par offsets.

    Double bornage, volontaire : `longueur` borne la LECTURE (coût disque), `contexte` borne le
    RENDU (contexte du modèle). Une entrée de classe peut faire des centaines de lignes ; un petit
    modèle doit recevoir de quoi répondre, pas de quoi saturer.
    """
    p = racine / fichier
    try:
        with open(p, "rb") as f:            # BINAIRE : aucune traduction, l'offset reste valide
            f.seek(offset)
            brut = f.read(max(0, longueur))
    except OSError as e:
        return f"(illisible : {e})"
    texte = brut.decode("utf-8", errors="replace")
    return "\n".join(texte.splitlines()[:contexte]).rstrip()


def paquets(racine: Path) -> None:
    base = racine / DOSSIER_DOC
    docs = sorted(d.name for d in base.iterdir() if d.is_dir() and not d.name.startswith("_"))
    print(f"{len(docs)} paquets documentés localement :\n")
    for i in range(0, len(docs), 6):
        print("  " + "  ".join(f"{d:<18}" for d in docs[i:i + 6]))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("symbole", nargs="?", help="ex. scipy.stats.bootstrap, ou juste bootstrap")
    ap.add_argument("--construire", action="store_true", help="(re)construit l'index")
    ap.add_argument("--paquets", action="store_true", help="liste les paquets documentés")
    ap.add_argument("--contexte", type=int, default=22, help="lignes rendues par entrée")
    args = ap.parse_args(argv)

    racine = trouver_racine(Path(__file__).resolve().parent)
    if racine is None:
        print(f"REFUS : aucun {MARQUEUR_RACINE} trouvé en remontant.")
        return 2

    if args.construire:
        n, f, v = construire_index(racine)
        print(f"index écrit : {INDEX.as_posix()} — {n} symboles, {f} fichiers de doc")
        # ★ CORRIGÉ 2026-08-10 (audit LOI 1) — ce message affichait « {v}/{v} concordants », soit LA
        # MÊME VARIABLE DEUX FOIS. Le ratio ne pouvait donc valoir autre chose que 100 %, quoi qu'il
        # arrive : un indicateur qui ne peut pas mal tourner n'indique rien. C'est la quatrième forme
        # d'instrument défaillant rencontrée dans ce fichier — après celui qui répond à côté, celui
        # qui ne répond qu'à ses propres échecs, et celui qui rend une réponse partielle sans le dire.
        # La grandeur réelle est un COMPTE, pas un taux ; on l'énonce donc comme un compte, et on dit
        # ce qui garantit la concordance : toute discordance lève `RuntimeError` et interrompt la
        # construction — c'est la garde qui porte la preuve, pas ce message.
        print(f"offsets relus par seek : {v} vérifiés, tous concordants "
              f"(une seule discordance aurait levé RuntimeError)")
        return 0
    if args.paquets:
        paquets(racine)
        return 0
    if not args.symbole:
        ap.print_help()
        return 1

    index = charger_index(racine)
    if not index:
        print(f"index absent — le construire : python {Path(__file__).name} --construire")
        return 2

    trouves = chercher(index, args.symbole)
    if not trouves:
        print(f"aucun symbole ne correspond à « {args.symbole} » dans la doc locale.")
        print("⚠️ ABSENCE DE DOC ≠ AUTORISATION D'ÉCRIRE DE MÉMOIRE. C'est un fait à déclarer.")
        return 1

    # ★ CE BLOC A ÉTÉ CASSÉ PENDANT ~1 JOURNÉE, ET AUCUN TEST NE L'A VU.
    #
    # La refonte en offsets (de31bb2f) a fait passer l'index de 3-uplets `(sym, fichier, ligne)` à
    # 4-uplets `(sym, fichier, offset, longueur)`. `charger_index()` et `extraire()` ont suivi ;
    # `main()` non. Résultat : `sym, fic, no = trouves[0]` levait
    #     ValueError: too many values to unpack (expected 3)
    # sur TOUTE requête qui TROUVE un symbole. L'outil ne « fonctionnait » donc que sur ses propres
    # échecs — le seul chemin que la CLI savait encore parcourir était celui du message « aucun
    # symbole ne correspond ». Les 12 tests étaient verts parce qu'ils appellent les fonctions
    # (`chercher`, `extraire`) sans jamais passer par `main()` avec un symbole existant.
    #
    # LEÇON, plus large que ce fichier : tester les pièces ne teste pas l'assemblage. Un lot de
    # tests unitaires verts peut coexister avec un outil totalement inutilisable en pratique.
    # D'où le test de bout en bout ajouté en regard (`test_main_rend_une_entree_pour_un_symbole_
    # existant`) : il exécute la CLI comme un appelant réel, seule façon d'attraper cette classe.
    sym, fic, off, lg = trouves[0]
    print(f"### {sym}\n    source : {fic} (offset {off}, {lg} o)\n")
    print(extraire(racine, fic, off, lg, args.contexte))
    if len(trouves) > 1:
        print(f"\n--- {len(trouves) - 1} autre(s) correspondance(s) ---")
        for s, f, _o, _l in trouves[1:8]:
            print(f"  {s:<52} {f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
