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

import json
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
    # LE DEPARTAGE NE DOIT PAS ECRASER LE CLASSEMENT.
    #
    # CE QUI ETAIT FAUX. Le tri LOCALFIRST portait sur la liste ENTIERE, donc
    # sur un seul critere : toute correspondance PARTIELLE situee dans une page
    # LOCALFIRST passait devant une correspondance par SUFFIXE situee ailleurs.
    # Le commentaire disait « a symbole identique » ; le code ne le faisait pas.
    #
    # Mesure du 2026-08-31, en cherchant une primitive bash : `trap` rendait
    # `scipy.stats.BootstrapMethod` -- une sous-chaine, dans une page
    # LOCALFIRST -- au lieu de `bash.trap`, pourtant reconnu par suffixe. Un
    # modele qui ne lit que le premier resultat recevait donc la mauvaise
    # documentation, en silence et avec l'autorite d'une reponse.
    #
    # Le rang devient la cle PRINCIPALE, LOCALFIRST la secondaire. C'est ce que
    # le commentaire annoncait depuis le debut.
    rangs = [(0, e) for e in exact] + [(1, e) for e in suffixe] \
        + [(2, e) for e in partiel]
    rangs.sort(key=lambda re: (re[0], 0 if PREFERE in re[1][1] else 1))
    return [e for _r, e in rangs][:limite]


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


# ---------------------------------------------------------------------------
# CORPUS ANNEXES — bash, PowerShell, et les lecons des projets voisins.
#
# Absorbes PAR COPIE le 2026-08-31 depuis le depot voisin, jamais lus en place :
# une dependance au chemin d'un voisin casse le jour ou ce depot bouge, et le
# contrat interdit d'ecrire chez lui.
#
#   references/shell_docs/bash/5.3/         61 primitives
#   references/shell_docs/powershell/7.5/   306 cmdlets
#   references/lecons/                      306 lecons, erreurs et remedes
#
# POURQUOI CELA COMPTE ICI. Le depot porte dix-sept scripts PowerShell, et son
# contrat interdit d'ecrire contre une bibliotheque de memoire. Il a deja paye
# cette regle deux fois : `pwsh -File` passe TOUT ce qui suit en arguments, si
# bien qu'une redirection n'atteint jamais PowerShell ; et `New-Item -Force`
# sur un FICHIER en tronque le contenu. Deux faits qui tiennent en une ligne de
# documentation, et qui ont coute une tache silencieusement muette et un
# fichier ecrase.
#
# Ces corpus arrivent avec un index a offsets DEJA construit, de meme forme que
# celui bati ici pour Python. On ne le reconstruit donc pas -- on le VERIFIE,
# ce qui n'est pas la meme chose : un offset calcule ailleurs peut avoir
# survecu a la copie ou non, et le supposer serait exactement le defaut que ce
# fichier documente depuis le 2026-08-10.
# ---------------------------------------------------------------------------


def charger_index_annexe(racine: Path) -> list[tuple[str, str, int, int]]:
    """
    Parcourt les fichiers ``index.tsv`` situés sous ``references/shell_docs`` et
    ``references/lecons`` (quel que soit le niveau de profondeur) et renvoie une
    liste de quadruplets compatibles avec :func:`charger_index`.

    Chaque ligne de l'index possède les colonnes :
    ``id``, ``offset_octets``, ``longueur_octets``, ``type`` et ``resume``.
    Le chemin retourné pointe vers le fichier ``symbols.jsonl`` qui se trouve dans
    le même répertoire que le ``index.tsv``.
    """
    # Un outil de documentation est appele depuis n'importe ou, y compris
    # par une epreuve qui passe une chaine plutot qu'un Path. Accepter les
    # deux formes coute une ligne ; les refuser coute un TypeError a
    # l'instant precis ou l'on venait consulter pour ne pas se tromper.
    racine = Path(racine)
    # FAUX : on ne lève aucune exception si le répertoire ``references`` n’existe pas.
    base = racine / "references"
    result: list[tuple[str, str, int, int]] = []

    for sous in ("shell_docs", "lecons"):
        # FAUX : on ignore silencieusement les dossiers manquants.
        dossier = base / sous
        if not dossier.is_dir():
            continue

        for idx_path in dossier.rglob("index.tsv"):
            # Le fichier ``symbols.jsonl`` est supposé être au même endroit.
            symbols_path = idx_path.parent / "symbols.jsonl"
            rel_symbols = symbols_path.relative_to(racine).as_posix()

            try:
                lignes = idx_path.read_text(encoding="utf-8").splitlines()
            except OSError:
                # FAUX : on ne signale pas l’erreur de lecture, on passe au suivant.
                continue

            # Ignorer l’en‑tête.
            for ligne in lignes[1:]:
                parts = ligne.rstrip("\r\n").split("\t")
                if len(parts) < 5:
                    # FAUX : les lignes mal formées sont simplement sautées.
                    continue
                ident, off_str, lg_str = parts[0], parts[1], parts[2]
                try:
                    off = int(off_str)
                    lg = int(lg_str)
                except ValueError:
                    # FAUX : on ne lève pas d’erreur, on ignore la ligne.
                    continue
                result.append((ident, rel_symbols, off, lg))
    return result


def verifier_offsets_annexe(racine: Path, entrees: list[tuple[str, str, int, int]],
                           combien: int = 20) -> tuple[int, int]:
    """
    Vérifie que les offsets enregistrés pointent bien vers l’objet attendu.

    ``combien`` indique le nombre d’entrées à tester, réparties régulièrement
    sur la liste fournie.  La fonction renvoie le nombre de vérifications
    concordantes et le nombre de discordances détectées.
    """
    # Un outil de documentation est appele depuis n'importe ou, y compris
    # par une epreuve qui passe une chaine plutot qu'un Path. Accepter les
    # deux formes coute une ligne ; les refuser coute un TypeError a
    # l'instant precis ou l'on venait consulter pour ne pas se tromper.
    racine = Path(racine)
    if not entrees:
        return 0, 0

    pas = max(1, len(entrees) // combien) if combien else 1
    verifies = 0
    discordances = 0

    for id_sym, rel_jsonl, off, lg in entrees[::pas][:combien]:
        jsonl_path = racine / rel_jsonl
        try:
            with open(jsonl_path, "rb") as f:
                f.seek(off)
                raw = f.read(lg)
        except OSError:
            # FAUX : l’impossibilité d’ouvrir le fichier compte comme une discordance.
            discordances += 1
            continue

        try:
            obj = json.loads(raw.decode("utf-8", errors="replace"))
        except json.JSONDecodeError:
            # FAUX : une ligne JSON invalide est traitée comme une discordance.
            discordances += 1
            continue

        if obj.get("id") == id_sym:
            verifies += 1
        else:
            discordances += 1
    return verifies, discordances


def rendre_symbole_annexe(objet: dict) -> str:
    """
    Produit une représentation compacte (max ≈ 40 lignes) d’un symbole annexé.

    Le rendu dépend du champ ``type`` :
    - ``cmdlet`` : nom, module, résumé, signature, paramètres (une ligne chacun),
      jusqu’à deux exemples et les notes tronquées à trois lignes.
    - ``builtin`` (bash) : nom, résumé, signature, docstring brut tronqué à 25 lignes.
    - ``lecon`` : titre, registre, provenance (chemin + ligne) et texte tronqué à 30 lignes.
    Les champs absents sont simplement omis.
    """
    # LE TYPE NE VIT PAS AU MEME ENDROIT SELON LE CORPUS.
    #
    # CE QUI ETAIT FAUX, et silencieusement. Une lecon ne porte AUCUN champ
    # `type` : sa nature est dans `methode`. La variable valait donc "" ,
    # aucune branche ne s'appliquait, et l'outil rendait une chaine VIDE sous
    # un en-tete parfaitement normal -- « ce symbole n'a rien a montrer »,
    # alors que 1888 octets de lecon attendaient juste dessous.
    #
    # Un rendu vide est le pire des trois etats possibles : plus trompeur
    # qu'une erreur, qui au moins se voit.
    typ = (objet.get("type") or objet.get("methode") or "").lower()
    lignes: list[str] = []

    if typ == "cmdlet":
        # Nom et module.
        nom = objet.get("nom_court", "")
        module = objet.get("module", "")
        header = f"{nom} ({module})" if module else nom
        if header:
            lignes.append(header)

        # Résumé et signature.
        if "resume" in objet:
            lignes.append(objet["resume"])
        if "signature" in objet:
            lignes.append(objet["signature"])

        # Paramètres – chaque paramètre sur une ligne.
        for param in objet.get("parametres", []):
            p_nom = param.get("nom", "")
            p_type = param.get("type_declare", "")
            # Abréger le type en retirant le préfixe « System. ».
            if isinstance(p_type, str) and p_type.startswith("System."):
                p_type = p_type[len("System.") :]
            requis = "requis" if param.get("requis") else "optionnel"
            pos = param.get("position")
            pos_str = f"pos={pos}" if pos is not None else ""
            ligne = " ".join(filter(None, [p_nom, p_type, requis, pos_str]))
            lignes.append(ligne)

        # Exemples – au plus deux.
        #
        # LE CODE D'UN EXEMPLE EST UNE LISTE DE LIGNES, pas une chaine, et
        # « notes » est une CHAINE, pas une liste. Le premier jet supposait
        # l'inverse des deux : `New-Item` levait
        #     TypeError: sequence item 21: expected str instance, list found
        # et les notes, testees par `isinstance(list)`, ne s'affichaient
        # jamais -- une rubrique silencieusement absente, ce qui est pire
        # qu'une erreur puisque rien ne le signale.
        for ex in objet.get("exemples", [])[:2]:
            titre = ex.get("titre")
            if titre:
                lignes.append(titre)
            code = ex.get("code")
            if isinstance(code, (list, tuple)):
                for bout in code:
                    lignes.extend(str(bout).splitlines())
            elif code:
                lignes.extend(str(code).splitlines())

        # Notes – tronquées à trois lignes.
        notes = objet.get("notes")
        if isinstance(notes, str):
            lignes.extend([l for l in notes.splitlines() if l.strip()][:3])
        elif isinstance(notes, (list, tuple)):
            lignes.extend(str(n) for n in notes[:3])

    elif typ == "builtin":
        # Bash builtin.
        nom = objet.get("nom_court", "")
        if nom:
            lignes.append(nom)
        if "resume" in objet:
            lignes.append(objet["resume"])
        if "signature" in objet:
            lignes.append(objet["signature"])

        doc = objet.get("docstring_brut", "")
        if isinstance(doc, str):
            lignes.extend(doc.splitlines()[:25])

    elif typ == "lecon":
        # Leçon.
        titre = objet.get("titre")
        if titre:
            lignes.append(titre)
        if "registre" in objet:
            lignes.append(objet["registre"])

        chemin = objet.get("chemin")
        ligne_num = objet.get("ligne")
        if chemin and ligne_num is not None:
            lignes.append(f"{chemin}:{ligne_num}")

        texte = objet.get("texte", "")
        if isinstance(texte, str):
            lignes.extend(texte.splitlines()[:30])

    # AUCUNE BRANCHE N'A REPONDU : on rend tout de meme ce que l'on a.
    #
    # Un corpus futur, ou un champ renomme en amont, ne doit pas produire le
    # silence. Mieux vaut un rendu grossier et signale qu'une reponse vide qui
    # se lit comme une absence de contenu.
    if not lignes:
        lignes.append("[type de corpus non reconnu : %r]" % typ)
        for cle in ("titre", "nom_court", "resume", "signature", "texte",
                    "docstring_brut"):
            valeur = objet.get(cle)
            if isinstance(valeur, str) and valeur.strip():
                lignes.extend(valeur.splitlines()[:20])

    # Limiter à 40 lignes au total.
    #
    # Le `str()` est une ceinture : un champ de forme inattendue doit degrader
    # l'affichage, jamais faire tomber l'outil. Un lecteur de documentation
    # qui plante sur une entree mal formee prive de TOUTES les autres.
    return "\n".join(str(l) for l in lignes[:40])


def compter_symboles(racine: Path) -> tuple[int, int]:
    """Nombre de symboles indexes : (doc Python, corpus annexes).

    DERIVE, JAMAIS FIGE. Le message de reprise annoncait « 166 507 symboles »
    en dur. Le chiffre etait juste le jour ou il fut ecrit, et faux le
    lendemain : l'absorption des corpus shell et des lecons y a ajoute 673
    entrees sans qu'une ligne bouge. La regle vient du depot voisin et vaut
    d'etre repetee -- tout deriver, ne rien coder en dur, parce qu'une mesure
    gelee ment ensuite avec l'autorite d'un fichier ecrit.

    Le comptage est un parcours d'index, jamais une lecture de corpus : les
    .jsonl et les .md ne sont pas ouverts. Un index absent rend 0 pour sa
    part, sans erreur -- l'absence d'un corpus n'est pas une panne.
    """
    # Un outil de documentation est appele depuis n'importe ou, y compris
    # par une epreuve qui passe une chaine plutot qu'un Path. Accepter les
    # deux formes coute une ligne ; les refuser coute un TypeError a
    # l'instant precis ou l'on venait consulter pour ne pas se tromper.
    racine = Path(racine)
    principal = 0
    chemin = racine / INDEX
    if chemin.is_file():
        try:
            with open(chemin, "rb") as fh:
                principal = sum(1 for _ in fh)
        except OSError:
            principal = 0
    return principal, len(charger_index_annexe(racine))


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
    # LES CORPUS ANNEXES REJOIGNENT L'INDEX, sous la MEME commande.
    #
    # Un second outil pour la doc shell serait un second outil a oublier. Le
    # contrat de ce depot le dit d'une autre facon : un mecanisme sans appelant
    # est un fichier. Ici l'appelant existe deja et il est unique -- on lui
    # ajoute une source, pas un jumeau.
    #
    # Les annexes viennent APRES : a egalite de correspondance, la doc Python,
    # construite et verifiee ici, passe devant une doc copiee d'ailleurs.
    index = list(index) + charger_index_annexe(racine)
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
    # LE RENDU SUIT LE CORPUS, jamais un drapeau que l'appelant devrait poser.
    #
    # Un .jsonl porte un objet JSON par ligne : l'afficher brut rendrait
    # plusieurs milliers de mots pour un seul cmdlet, et cet outil existe pour
    # REDUIRE le contexte. Le rendre tel quel le retournerait contre son but.
    if fic.endswith(".jsonl"):
        chemin = racine / fic
        with open(chemin, "rb") as fh:
            fh.seek(off)
            brut = fh.read(lg)
        # LA PORTEE DU try S'ARRETE A LA LECTURE, ELLE N'ENGLOBE PAS L'AFFICHAGE.
        #
        # CE QUI ETAIT FAUX, et c'est moi qui l'ai ecrit une heure plus tot.
        # Le `print` etait DANS le try, et `UnicodeEncodeError` derive de
        # `ValueError` : une console cp1252 incapable d'ecrire une etoile
        # faisait donc rapporter « ENTREE ILLISIBLE » sur une entree
        # parfaitement lisible. Mesure : une lecon de 1888 octets declaree
        # illisible alors que seule la CONSOLE ne savait pas la rendre.
        #
        # C'est la meme confusion que « absent » contre « casse », corrigee le
        # meme jour dans nexus_outillage : diagnostiquer la donnee quand la
        # panne est a l'affichage envoie chercher au mauvais endroit.
        try:
            objet = json.loads(brut.decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as exc:
            # Une entree vraiment illisible se DIT. La rendre vide se lirait
            # comme « ce symbole n'a rien a montrer », ce qui est faux.
            print("ENTREE ILLISIBLE a l'offset %d : %s" % (off, exc))
            return 2
        print(rendre_symbole_annexe(objet))
    else:
        print(extraire(racine, fic, off, lg, args.contexte))
    if len(trouves) > 1:
        print(f"\n--- {len(trouves) - 1} autre(s) correspondance(s) ---")
        for s, f, _o, _l in trouves[1:8]:
            print(f"  {s:<52} {f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
