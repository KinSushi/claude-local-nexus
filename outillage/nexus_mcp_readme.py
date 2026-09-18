#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generateur (et verificateur) du README des outils du pont MCP Nexus.

Ce script lit tools/nexus-mcp/server.js, y repere le bloc

    const TOOLS = [ ... ];

et en extrait, pour chaque entree, le nom, la description, et les proprietes
de inputSchema (type, description, enum, requis). Il produit ensuite un
README_MCP.md dans outillage/rituels/.

Le document est GENERE : il ne doit pas etre edite a la main, sinon la
verification echouera des la prochaine evolution du serveur.

Mode --verifier : ne touche pas au disque, rend 0 si le README reflete le
serveur, 1 sinon (avec detail des ecarts), 1 aussi si le README est absent
ou si server.js est introuvable.

Emplacement : ce fichier vit dans outillage/, la racine du depot est donc
le parent du repertoire qui contient ce script (et non le repertoire
lui-meme, sinon tout chemin derive devient vide et le script pret
rien trouver sans rien chercher).
"""

from __future__ import annotations

import argparse
import datetime
import io
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Garde d'encodage : forcer la console en UTF-8 si possible.
# ---------------------------------------------------------------------------

def _activer_utf8() -> None:
    """
    Tente d'appliquer la fonction forcer_utf8() de console_tools.
    Si l'import echoue (module absent, depot partiellement copie, etc.),
    on l'ecrit sur stderr mais on ne leve pas : le script doit toujours
    pouvoir tourner, quitte a imprimer en cp1252.
    """
    try:
        # Le dossier du fichier est ajoute a sys.path pour permettre
        # l'import de console_tools situe dans le meme outillage/.
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import console_tools  # type: ignore
        if hasattr(console_tools, "forcer_utf8"):
            console_tools.forcer_utf8()
    except Exception as exc:  # noqa: BLE001 - on veut tout avaler
        sys.stderr.write(
            "Avertissement : impossible d'appliquer forcer_utf8 "
            "(import console_tools echoue : " + repr(exc) + "). "
            "Le script continue en utilisant l'encodage courant.\n"
        )


# ---------------------------------------------------------------------------
# Emplacements.
# ---------------------------------------------------------------------------

def _racine() -> Path:
    """
    Racine du depot.

    Le fichier vit dans <racine>/outillage/, donc la racine est le parent
    du dossier contenant ce script. Toute autre convention (par exemple
    prendre parent.parent) ferait sortir des limites du depot et le script
    ne trouverait plus tools/nexus-mcp/server.js.
    """
    return Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# Mini-parseur JS : on ne veut pas evaluer du JS, juste compter les
# accolades en respectant les chaines et les commentaires. C'est la seule
# maniere d'extraire une entree complete d'un tableau d'objets literal
# dont la fermeture peut apparaitre au milieu d'une description.
# ---------------------------------------------------------------------------

_CHAINES = ('"', "'", "`")


def _iter_tokens(source: str):
    """
    Parcourt source et yield (genre, texte) :
        genre 0 = commentaire //...
        genre 1 = commentaire /* ... */
        genre 2 = chaine simple / double / backticks
        genre 3 = reste du code
    Permet au parseur d'ignorer accolades et crochets dans les commentaires
    et les chaines.
    """
    i = 0
    n = len(source)
    while i < n:
        c = source[i]
        nxt = source[i + 1] if i + 1 < n else ""

        if c == "/" and nxt == "/":
            j = source.find("\n", i)
            if j == -1:
                j = n
            yield (0, source[i:j])
            i = j
            continue

        if c == "/" and nxt == "*":
            j = source.find("*/", i + 2)
            if j == -1:
                j = n
            else:
                j += 2
            yield (1, source[i:j])
            i = j
            continue

        if c in _CHAINES:
            quote = c
            j = i + 1
            while j < n:
                ch = source[j]
                if ch == "\\" and j + 1 < n:
                    j += 2
                    continue
                if ch == quote:
                    j += 1
                    break
                j += 1
            yield (2, source[i:j])
            i = j
            continue

        yield (3, c)
        i += 1


def _bloc_tableau(source: str, nom: str) -> str:
    """
    Trouve 'const <nom> = [' puis renvoie le contenu du tableau (sans
    les crochets externes) jusqu'au '];' correspondant, en equilibrant
    les crochets. Leve ValueError si introuvable.
    """
    idx_const = source.find("const " + nom + " ")
    if idx_const == -1:
        raise ValueError("Bloc const " + nom + " introuvable.")

    # Chercher le premier '[' apres le '=' qui suit.
    eq = source.find("=", idx_const)
    if eq == -1:
        raise ValueError("Signe '=' absent pour const " + nom + ".")
    bracket_open = source.find("[", eq)
    if bracket_open == -1:
        raise ValueError("Crochet ouvrant absent pour const " + nom + ".")

    profondeur = 0
    for genre, tok in _iter_tokens(source[bracket_open:]):
        if genre in (0, 1, 2):
            continue
        if tok == "[":
            profondeur += 1
        elif tok == "]":
            profondeur -= 1
            if profondeur == 0:
                break

    # Reconstruction propre de la fin (la boucle ci-dessus casse a la
    # premiere fermeture car on ne garde pas la position). On recommence
    # en gardant l'index.
    profondeur = 0
    pos_fin = -1
    decalage = 0
    for genre, tok in _iter_tokens(source[bracket_open:]):
        if genre in (0, 1, 2):
            # Avancer d'autant de caracteres que le token.
            decalage += len(tok)
            continue
        if tok == "[":
            profondeur += 1
        elif tok == "]":
            profondeur -= 1
            if profondeur == 0:
                pos_fin = bracket_open + decalage
                break
        decalage += len(tok)

    if pos_fin == -1:
        raise ValueError("Crochet fermant de " + nom + " introuvable.")

    return source[bracket_open + 1:pos_fin]


def _decouper_entrees(tableau: str):
    """
    Renvoie la liste des sous-chaines, une par objet top-level du tableau.
    Decoupage par comptage des accolades '{' et '}', en respectant les
    chaines et commentaires via _iter_tokens.
    """
    entrees = []
    profondeur = 0
    debut = None
    decalage = 0
    for genre, tok in _iter_tokens(tableau):
        if genre in (0, 1, 2):
            if debut is not None and tok.startswith("{") is False:
                # Ignorer : on est dans une entree, mais on reste a
                # l'interieur, on ne fait rien.
                pass
            if debut is not None and tok.startswith("}"):
                # Une fermeture d'accolade se trouve a l'interieur d'une
                # chaine ; on l'ignore pour le comptage.
                pass
            # On incremente le decalage mais on ne touche pas profondeur.
            decalage += len(tok)
            continue

        if tok == "{":
            if profondeur == 0:
                debut = decalage
            profondeur += 1
        elif tok == "}":
            profondeur -= 1
            if profondeur == 0 and debut is not None:
                entrees.append(tableau[debut:decalage + 1])
                debut = None
        decalage += len(tok)

    return entrees


# ---------------------------------------------------------------------------
# Extraction des champs qui nous interessent dans une entree JS.
# ---------------------------------------------------------------------------

_RE_CHAMP_STRING = re.compile(
    r'(?P<cle>"(?P<k1>[A-Za-z_$][A-Za-z0-9_$]*)"\s*:\s*(?P<val>"(?:[^"\\]|\\.)*"))',
    re.DOTALL,
)


def _lire_chaine(texte: str, debut_valeur: int) -> tuple[str, int]:
    """
    debut_valeur pointe sur le guillemet ouvrant. Renvoie (contenu_decode,
    index_apres_guillemet_fermant).
    """
    assert texte[debut_valeur] == '"'
    i = debut_valeur + 1
    buf: list[str] = []
    while i < len(texte):
        ch = texte[i]
        if ch == "\\" and i + 1 < len(texte):
            esc = texte[i + 1]
            # On dechiffre un sous-ensemble utile.
            table = {
                "n": "\n",
                "t": "\t",
                "r": "\r",
                '"': '"',
                "\\": "\\",
                "'": "'",
                "`": "`",
            }
            buf.append(table.get(esc, "\\" + esc))
            i += 2
            continue
        if ch == '"':
            return ("".join(buf), i + 1)
        buf.append(ch)
        i += 1
    raise ValueError("Chaine non terminee dans l'entree.")


def _extraire_chaine_suivant(entree: str, cle: str) -> str | None:
    """
    Cherche '<cle>:' et renvoie la chaine qui suit, ou None.
    Robuste face aux espaces et sauts de ligne.
    """
    motif = re.compile(r"\b" + re.escape(cle) + r"\s*:\s*\"")
    m = motif.search(entree)
    if not m:
        return None
    val, _ = _lire_chaine(entree, m.end() - 1)
    return val


def _extraire_objet_suivant(entree: str, cle: str) -> str | None:
    """
    Renvoie la sous-chaine de l'objet literal suivant '<cle> :', ou None.
    Compte les accolades en evitant les chaines.
    """
    motif = re.compile(r"\b" + re.escape(cle) + r"\s*:\s*\{")
    m = motif.search(entree)
    if not m:
        return None
    # Position du '{' ouvrant : m.end() - 1.
    debut = m.end() - 1
    profondeur = 0
    pos = debut
    for genre, tok in _iter_tokens(entree[debut:]):
        if genre in (0, 1, 2):
            pos += len(tok)
            continue
        if tok == "{":
            profondeur += 1
        elif tok == "}":
            profondeur -= 1
            if profondeur == 0:
                fin = pos + 1
                return entree[debut:fin]
        pos += len(tok)
    raise ValueError("Objet non ferme pour la cle " + cle + ".")


def _extraire_champ_texte_simple(entree: str, cle: str) -> str | None:
    """
    Renvoie la valeur d'un champ dont la valeur est un identifiant nu
    (ex: DEFAULT_CHAT_MODEL, PROFILES...). On recupere le texte brut.
    """
    motif = re.compile(r"\b" + re.escape(cle) + r"\s*:\s*([^,}\n]+)")
    m = motif.search(entree)
    if not m:
        return None
    return m.group(1).strip()


def _parser_input_schema(schéma_brut: str) -> dict:
    """
    A partir de la sous-chaine d'un inputSchema (objet literal JS),
    renvoie un dict :
        {
            "properties": [
                {"name": str, "type": str, "description": str,
                 "enum": list[str] | None, "required": bool},
                ...
            ],
            "required": [str, ...],
        }

    On gere les valeurs :
        - type : "string" | "integer" | "number" | "boolean" | "object"
                | "array"
        - description : chaine
        - enum : tableau ["a", "b", ...]
        - items.type : quand la propriete est un tableau

    Pour un tableau (type:"array"), on regarde items.type.
    """
    propriétés = []
    bloc_props = _extraire_objet_suivant(schéma_brut, "properties")
    if bloc_props is None:
        # Schema {} ou sans properties.
        bloc_props = "{}"

    # Proprietes : on les decoupe par accolades top-level, comme des
    # entites distinctes.
    sous_entrées = _decouper_entrees(bloc_props[1:-1]) if bloc_props and bloc_props != "{}" else []

    for sous in sous_entrées:
        nom = _extraire_chaine_suivant(sous, "name") or ""
        if not nom:
            continue
        type_val = _extraire_chaine_suivant(sous, "type")
        # Cas array : on prend items.type si present.
        if type_val == "array":
            items_bloc = _extraire_objet_suivant(sous, "items")
            if items_bloc is not None:
                items_type = _extraire_chaine_suivant(items_bloc, "type")
                if items_type:
                    type_val = "array<" + items_type + ">"
        description = _extraire_chaine_suivant(sous, "description") or ""

        # enum : on cherche un tableau literal ["a","b",...] ou
        # Object.keys(...) qu'on ne tente pas de resoudre ; dans ce cas
        # on note la mention sans enum resolu.
        enum_vals: list[str] | None = None
        m_enum = re.search(r"\benum\s*:\s*\[", sous)
        if m_enum:
            j = m_enum.end()
            # Avancer jusqu'a ']' en respectant les chaines.
            buf: list[str] = []
            for genre, tok in _iter_tokens(sous[j:]):
                if genre == 2:
                    # Chaine ; on decode.
                    val, _ = _lire_chaine(sous[j:], 0)
                    buf.append(val)
                if genre in (0, 1, 2):
                    continue
                if tok == "]":
                    break
            enum_vals = buf

        propriétés.append({
            "name": nom,
            "type": type_val or "?",
            "description": description,
            "enum": enum_vals,
            "required": False,  # ajuste apres.
        })

    # Requis : tableau 'required' du schema.
    requis = []
    m_req = re.search(r"\brequired\s*:\s*\[", schéma_brut)
    if m_req:
        j = m_req.end()
        for genre, tok in _iter_tokens(schéma_brut[j:]):
            if genre == 2:
                val, _ = _lire_chaine(schéma_brut[j:], 0)
                requis.append(val)
            if genre in (0, 1, 2):
                continue
            if tok == "]":
                break

    for prop in propriétés:
        if prop["name"] in requis:
            prop["required"] = True

    return {"properties": propriétés, "required": requis}


def _extraire_outils(source: str) -> list[dict]:
    """
    Renvoie la liste des outils :
        { "name", "description", "properties": [...], "required": [...] }
    """
    tableau = _bloc_tableau(source, "TOOLS")
    entrees = _decouper_entrees(tableau)
    outils = []
    for entree in entrees:
        nom = _extraire_chaine_suivant(entree, "name")
        if not nom:
            continue
        description = _extraire_chaine_suivant(entree, "description") or ""
        schema_brut = _extraire_objet_suivant(entree, "inputSchema")
        schema = _parser_input_schema(schema_brut) if schema_brut else {
            "properties": [],
            "required": [],
        }
        outils.append({
            "name": nom,
            "description": description,
            "properties": schema["properties"],
            "required": schema["required"],
        })
    return outils


# ---------------------------------------------------------------------------
# Formatage du README.
# ---------------------------------------------------------------------------

def _formater_readme(outils: list[dict]) -> str:
    """
    Compose le README. Le contenu peut porter des accents ordinaires ; les
    separateurs et la mise en page sont en ASCII pour la portabilite.
    """
    tampon = io.StringIO()
    tampon.write("# Outils du pont MCP Nexus\n\n")
    tampon.write(
        "Ce document est GENERE automatiquement par "
        "outillage/nexus_mcp_readme.py a partir de "
        "tools/nexus-mcp/server.js. Il ne doit pas etre edite a la main : "
        "toute modification manuelle sera effacee a la prochaine "
        "generation, et le mode --verifier signalera l'ecart.\n\n"
    )
    tampon.write("- Generation : " + datetime.datetime.now().isoformat(timespec="seconds") + "\n")
    tampon.write("- Nombre d'outils : " + str(len(outils)) + "\n\n")
    tampon.write("---\n\n")

    for outil in outils:
        tampon.write("## " + outil["name"] + "\n\n")
        if outil["description"]:
            tampon.write(outil["description"].strip() + "\n\n")
        else:
            tampon.write("_Aucune description._\n\n")

        props = outil["properties"]
        if not props:
            tampon.write("Aucun parametre declare.\n\n")
        else:
            tampon.write("Parametres :\n\n")
            tampon.write("| Nom | Type | Requis | Description | Enum |\n")
            tampon.write("| --- | ---- | ------ | ----------- | ---- |\n")
            for p in props:
                requis = "oui" if p["required"] else "non"
                description = (p["description"] or "").replace("\n", " ").replace("|", "\\|")
                if p["enum"]:
                    enum_txt = ", ".join(p["enum"])
                else:
                    enum_txt = ""
                tampon.write(
                    "| " + p["name"] + " | " + p["type"] + " | " + requis +
                    " | " + description + " | " + enum_txt + " |\n"
                )
            tampon.write("\n")
        tampon.write("---\n\n")

    return tampon.getvalue()


# ---------------------------------------------------------------------------
# Verification : comparer serveur et README sans toucher au disque.
# ---------------------------------------------------------------------------

def _lire_readme(chemin: Path) -> str | None:
    if not chemin.exists():
        return None
    return chemin.read_text(encoding="utf-8")


def _verifier(outils: list[dict], contenu_readme: str) -> int:
    """
    Rend 0 si tout concorde, 1 sinon (imprime les ecarts).
    """
    ecarts: list[str] = []

    noms_serveur = {o["name"] for o in outils}
    noms_présents_dans_readme = set(re.findall(r"^## ([A-Za-z0-9_]+)\s*$", contenu_readme, re.MULTILINE))

    for nom in sorted(noms_serveur - noms_présents_dans_readme):
        ecarts.append("Outil declare absent du document : " + nom + ".")
    for nom in sorted(noms_présents_dans_readme - noms_serveur):
        ecarts.append("Outil documente absent du serveur : " + nom + ".")

    # Pour chaque outil du serveur, on extrait du README la sous-section
    # '## <nom>' ... '## ' suivante (ou fin de fichier), et on relit le
    # tableau de parametres pour verifier que les types n'ont pas change.
    sections = re.split(r"(?m)^## ([A-Za-z0-9_]+)\s*$", contenu_readme)
    # sections : [preambule, nom1, contenu1, nom2, contenu2, ...]
    sections_map = {}
    for i in range(1, len(sections), 2):
        sections_map[sections[i]] = sections[i + 1]

    for outil in outils:
        if outil["name"] not in sections_map:
            # Deja signale par 'absent du document'.
            continue
        bloc = sections_map[outil["name"]]
        # Types annonces dans le tableau :
        types_annoncés = {}
        for ligne in bloc.splitlines():
            m = re.match(r"\|\s*([A-Za-z0-9_]+)\s*\|\s*([^|]+?)\s*\|", ligne)
            if not m:
                continue
            nom_prop = m.group(1)
            type_prop = m.group(2).strip()
            # Eviter la ligne d'en-tete.
            if nom_prop == "Nom":
                continue
            types_annoncés[nom_prop] = type_prop

        for prop in outil["properties"]:
            if prop["name"] not in types_annoncés:
                ecarts.append(
                    "Parametre manquant dans le README pour "
                    + outil["name"] + "." + prop["name"] + "."
                )
                continue
            if types_annoncés[prop["name"]] != prop["type"]:
                ecarts.append(
                    "Type change pour " + outil["name"] + "."
                    + prop["name"] + " : serveur='"
                    + prop["type"] + "', README='"
                    + types_annoncés[prop["name"]] + "'."
                )

    if ecarts:
        sys.stderr.write("README MCP non conforme au serveur :\n")
        for e in ecarts:
            sys.stderr.write(" - " + e + "\n")
        return 1
    return 0


# ---------------------------------------------------------------------------
# Point d'entree.
# ---------------------------------------------------------------------------

def main(argv: list[str]) -> int:
    _activer_utf8()

    ap = argparse.ArgumentParser(
        description=(
            "Genere (par defaut) ou verifie (--verifier) le README des "
            "outils du pont MCP Nexus a partir de tools/nexus-mcp/server.js."
        )
    )
    ap.add_argument(
        "--verifier",
        action="store_true",
        help=(
            "Ne touche pas au disque. Rend 0 si le README est conforme au "
            "serveur, 1 sinon (ou si le README ou server.js est absent)."
        ),
    )
    args = ap.parse_args(argv)

    racine = _racine()
    serveur = racine / "tools" / "nexus-mcp" / "server.js"
    readme = racine / "outillage" / "rituels" / "README_MCP.md"

    if not serveur.exists():
        sys.stderr.write(
            "Serveur introuvable : " + str(serveur) + ". "
            "Verifiez que ce script est bien place dans outillage/ "
            "a la racine du depot.\n"
        )
        return 1

    try:
        source = serveur.read_text(encoding="utf-8")
    except OSError as exc:
        sys.stderr.write("Lecture impossible de server.js : " + repr(exc) + ".\n")
        return 1

    try:
        outils = _extraire_outils(source)
    except Exception as exc:  # noqa: BLE001
        sys.stderr.write("Extraction impossible des outils : " + repr(exc) + ".\n")
        return 1

    # Detection d'echec d'extraction : aucun outil alors que server.js non vide.
    if not args.verifier and len(outils) == 0:
        sys.stderr.write(
            "Extraction a echoue : aucun outil trouve alors que server.js n'est pas vide.\n"
        )
        return 1

    if args.verifier:
        contenu = _lire_readme(readme)
        if contenu is None:
            sys.stderr.write(
                "README absent : " + str(readme) + ". "
                "Lancez le script sans --verifier pour le generer.\n"
            )
            return 1
        return _verifier(outils, contenu)

    # Generation.
    texte = _formater_readme(outils)
    readme.parent.mkdir(parents=True, exist_ok=True)
    readme.write_text(texte, encoding="utf-8")
    sys.stdout.write(
        "README genere : " + str(readme) +
        " (" + str(len(outils)) + " outils).\n"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
