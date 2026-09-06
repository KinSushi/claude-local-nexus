# -*- coding: utf-8 -*-
"""
Sonde du serveur MCP nexus-local : exerce les outils de bout en bout.

Cette sonde doit rester robuste même lorsque l'environnement est défectueux.
Elle attrape les erreurs liées à l'exécution du serveur Node et renvoie un
code de sortie explicite afin que les scripts d'automatisation puissent
distinguuer :

* « le pont a répondu une erreur »  → le serveur a renvoyé un payload
  avec isError = true.
* « le pont n'a pas répondu »       → le serveur n'a pas pu être lancé
  (exécutable absent, délai expiré, autre exception).

Le code minimise les changements : il ne touche que la fonction
`call_tool`, la logique de détection d'erreur et la validation des
arguments de `main()`.
"""
from __future__ import annotations

import json
import os
import subprocess
import re
import sys
from json import JSONDecodeError

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SERVER = os.path.join(ROOT, "tools", "nexus-mcp", "server.js")

# La console Windows reste en cp1252 : une reponse de modele contient
# souvent des caracteres qu'elle ne sait pas encoder (espace fine, tirets
# longs, symboles). Sans cela, une reponse correcte se perdrait sur une
# exception d'affichage.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception as e:  # pragma: no cover
    # avertir si la reconfiguration échoue
    print(
        f"ERROR: failed to reconfigure stdout/stderr ({type(e).__name__}: {e})",
        file=sys.stderr,
    )


# SOIXANTE SECONDES EXPIRAIENT SUR UN FICHIER ORDINAIRE DU DEPOT.
#
# L'hote n'a pas de GPU et le resume local passe par la RAM systeme ;
# nexus_agent.py travaille a 900 s pour la meme raison. Un delai trop court
# transforme un travail lent en panne rapportee -- et, avant le correctif de
# _probe_success, en panne rapportee AVEC un code de succes.
DELAI_SONDE_DEFAUT = 900


def _avec_modele(arguments: dict) -> dict:
    """Ajoute le modele demande, s'il y en a un. Ne force jamais rien."""
    modele = _modele_sonde()
    if modele:
        arguments = dict(arguments)
        arguments["model"] = modele
    return arguments


def _modele_sonde():
    """Alias a employer, ou None pour laisser le pont choisir son defaut.

    CE QUI MANQUAIT, mesure le 2026-08-31. La sonde ne pouvait pas choisir
    son plan : elle prenait toujours le defaut du pont, `glm-4.7-flash-local`.
    Sur cet hote sans GPU, un resume de deux fichiers ordinaires du depot a
    depasse DIX MINUTES par ce chemin, quand le meme appel en cloud rend en
    une quinzaine de secondes.

    Consequence : la seule sonde du depot n'exercait que le plan le plus
    lent, donc en pratique n'exercait presque jamais rien -- elle expirait
    avant. C'est ce qui a fait conclure a une panne du pont dans une session
    voisine, alors que le pont travaillait.

    Le defaut reste le plan LOCAL, gratuit et prive : sonder ne doit pas
    faire sortir des donnees sans qu'on l'ait demande. NEXUS_PROBE_MODEL
    permet de demander explicitement autre chose.
    """
    brut = os.environ.get("NEXUS_PROBE_MODEL")
    return brut.strip() if brut and brut.strip() else None


def _delai_sonde(defaut: int = DELAI_SONDE_DEFAUT) -> int:
    """Delai en secondes, reglable par NEXUS_PROBE_TIMEOUT.

    Une valeur illisible ou nulle retombe sur le defaut sans rien casser :
    une sonde qui refuse de partir a cause de son propre reglage ne mesure
    plus rien du tout.
    """
    brut = os.environ.get("NEXUS_PROBE_TIMEOUT")
    if not brut:
        return defaut
    try:
        valeur = int(brut)
    except (TypeError, ValueError):
        return defaut
    return valeur if valeur > 0 else defaut


def call_tool(name: str, arguments: dict, timeout: int = 0) -> str:
    """
    Appelle le serveur Node via le protocole JSON‑RPC.

    En cas d'échec du sous‑processus, la fonction renvoie un message
    diagnostique sans accents, préfixé par ``ERROR:`` et contenant le chemin
    du serveur. Les cas distincts sont :

    * exécutable introuvable (FileNotFoundError)
    * délai d'attente dépassé (subprocess.TimeoutExpired)
    * arguments invalides
    * toute autre exception inattendue (type d'exception indiqué)

    Le format de la réponse serveur (payload) est conservé : si le serveur
    indique une erreur, le texte retourné commence par `` [ERREUR]``.
    """
    # validation des paramètres
    if not name or not isinstance(arguments, dict):
        return f"ERROR: invalid arguments (SERVER={SERVER})"

    messages = "\n".join(
        [
            json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2025-06-18",
                        "capabilities": {},
                        "clientInfo": {"name": "probe", "version": "1"},
                    },
                }
            ),
            json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "tools/call",
                    "params": {"name": name, "arguments": arguments},
                }
            ),
        ]
    ) + "\n"

    # LES DEUX BUDGETS DOIVENT S'ACCORDER, ET RIEN NE LES Y OBLIGEAIT.
    #
    # Le serveur, une fois stdin ferme, attend ses appels en vol pendant
    # NEXUS_GRACE_MS -- 120 s par defaut -- puis FORCE la fermeture. Porter le
    # delai de la sonde a 900 s ne servait donc a rien : le serveur coupait a
    # 120 s et la sonde recevait « ERROR: aucune reponse », c'est-a-dire une
    # panne inventee par son propre reglage.
    #
    # Mesure du 2026-08-31, sur un fichier parfaitement valide du depot :
    #     [nexus-local] 1 appel(s) en vol — sortie dans au plus 120s
    #     [nexus-local] fermeture forcee : 1 appel(s) toujours en vol
    # Un resume local sur cet hote sans GPU depasse largement 120 s : le
    # modele par defaut du pont demande a lui seul une soixantaine de
    # secondes avant de commencer a repondre.
    #
    # La sonde transmet donc SON delai au serveur. Un seul budget, derive, au
    # lieu de deux qui se contredisent en silence. La grace est prise un peu
    # sous le delai de la sonde pour que le serveur rende la main AVANT
    # d'etre tue -- ainsi son message explique la coupure au lieu de la subir.
    delai = timeout or _delai_sonde()
    environnement = dict(os.environ)
    environnement.setdefault("NEXUS_GRACE_MS", str(max(30, delai - 15) * 1000))

    try:
        result = subprocess.run(
            ["node", SERVER],
            input=messages,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=delai,
            env=environnement,
        )
    except FileNotFoundError:
        # node n'est pas dans le PATH
        return f"ERROR: node executable not found (SERVER={SERVER})"
    except subprocess.TimeoutExpired:
        # le serveur n'a pas répondu à temps
        return f"ERROR: timeout expired after {delai}s (SERVER={SERVER})"
    except Exception as e:  # pragma: no cover
        # toute autre erreur inattendue
        return f"ERROR: unexpected error {type(e).__name__}: {e} (SERVER={SERVER})"

    # si le processus s'est terminé avec un code d'erreur et aucune sortie JSON
    if result.returncode != 0 and not result.stdout.strip():
        return f"ERROR: server exited with code {result.returncode} (SERVER={SERVER})"

    # Analyse de la sortie du serveur
    for line in result.stdout.splitlines():
        if not line.strip().startswith("{"):
            continue
        try:
            message = json.loads(line)
        except JSONDecodeError as e:
            return f"ERROR: malformed json from server ({type(e).__name__}: {e}) (SERVER={SERVER})"

        # Gestion d'une réponse d'erreur JSON‑RPC
        if isinstance(message, dict) and "error" in message:
            err = message["error"]
            code = err.get("code", "?")
            msg = err.get("message", "")
            return f"ERROR: server json-rpc error {code}: {msg} (SERVER={SERVER})"

        if not isinstance(message, dict) or "id" not in message:
            continue
        if message.get("id") == 2:
            payload = message.get("result", {})
            if not isinstance(payload, dict):
                return f"ERROR: unexpected payload format (SERVER={SERVER})"
            flag = " [ERREUR]" if payload.get("isError") else ""
            content_list = payload.get("content", [])
            # si la liste est vide ou mal formée, on considère qu'il n'y a rien
            if not isinstance(content_list, list) or not content_list:
                content = ""
            else:
                first = content_list[0]
                content = ""
                if isinstance(first, dict):
                    content = first.get("text", "")
            if not flag and not content.strip():
                return "NO CONTENT: nothing could be measured"
            return flag + "\n" + content

    # Aucun message JSON valide reçu
    stderr_tail = result.stderr[-800:]
    stderr_len = len(result.stderr)
    trunc_info = f" (truncated, {stderr_len} bytes)" if stderr_len > 800 else ""
    return f"ERROR: aucune reponse{trunc_info}\n{stderr_tail}"


# Marqueurs d'echec emis par le PONT lui-meme, jamais par le contenu resume.
#
# Ils sont cherches en debut de LIGNE, non en debut de sortie et non n'importe
# ou : « (refuse : hors du depot) », « (introuvable) » et « (illisible : ...) »
# sont ecrits par le serveur sur une ligne a eux. Chercher le mot nu
# « timeout » n'importe ou ferait echouer le resume de tout fichier qui PARLE
# de delais -- et il y en a plusieurs ici. On vise donc la phrase entiere que
# la sonde emet elle-meme.
MARQUEURS_ECHEC = (
    "error:",
    "no content:",
    "[erreur]",
    "(refuse",
    "(introuvable)",
    "(illisible",
    "aucune reponse",
    "timeout expired after",
)

# L'en-tete que le pont place en tete de chaque reponse :
#     [gpt-oss-120b-cloud · Ollama Cloud, les donnees sortent · 9818 tokens]
#
# LE SEPARATEUR EST UN POINT MEDIAN, PAS UN TIRET, et l'alias lui-meme en
# contient plusieurs (« gpt-oss-120b-cloud »). Une expression qui exigerait
# des tirets comme separateurs ne reconnaitrait donc jamais rien -- et un
# controle qui ne reconnait jamais rien se comporte exactement comme le
# defaut qu'il devait corriger. On ne decrit que ce qui est stable : des
# crochets, un nombre, le mot « tokens ».
ENTETE_JETONS = re.compile(r"\[[^\]]*?(\d+)\s+tokens\s*\]", re.IGNORECASE)


def _probe_success(output: str, exige_modele: bool = False) -> bool:
    """
    La sonde a-t-elle reussi, ou seulement termine ?

    CE QUI ETAIT FAUX, et mesure trois fois le 2026-08-31. La fonction ne
    testait que des PREFIXES : `output.startswith("ERROR:")`,
    `startswith(" [ERREUR]")`. Or la sortie du pont commence par son en-tete,
    puis « ## Par fichier », puis le corps :

        [modele · plan · 1234 tokens]

        ## Par fichier

        ### chemin/du/fichier
        (refuse : hors du depot)

    Le marqueur d'echec est donc TOUJOURS au corps, et `startswith` ne voyait
    rien. Le `startswith(" [ERREUR]")`, avec son espace initial, n'a
    probablement jamais ete vrai une seule fois.

    Mesure : un fichier hors depot et un fichier inexistant rendaient tous
    deux EXIT 0. La docstring de ce module promet pourtant l'inverse -- « un
    code de sortie explicite afin que les scripts d'automatisation puissent
    distinguer : le pont a repondu une erreur / le pont n'a pas repondu ».

    Toute automatisation appelant cette sonde lisait donc un vert. Un garde
    dont le vert ne signifie rien est PIRE que pas de garde : il consomme de
    l'attention et confere une fausse assurance.

    `exige_modele` ajoute la preuve qu'un modele a REELLEMENT ete appele :
    « 0 tokens » sur un appel cense en invoquer un est un echec, pas un
    resume vide reussi.
    """
    if not output or not output.strip():
        return False

    for ligne in output.splitlines():
        nue = ligne.strip().lower()
        if any(nue.startswith(m) for m in MARQUEURS_ECHEC):
            return False

    if exige_modele:
        trouve = ENTETE_JETONS.search(output)
        if trouve is None:
            return False
        if int(trouve.group(1)) <= 0:
            return False

    return True


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 1

    action = sys.argv[1]
    exit_code = 1  # défaut : échec

    if action == "index":
        root = sys.argv[2] if len(sys.argv) > 2 else "."
        out = call_tool("nexus_index_build", {"root": root})
        print(out)
        exit_code = 0 if _probe_success(out) else 1

    elif action == "search":
        if len(sys.argv) < 3:
            print(f"ERROR: missing query argument (SERVER={SERVER})", file=sys.stderr)
            return 1
        try:
            k_val = int(sys.argv[3]) if len(sys.argv) > 3 else 5
        except ValueError:
            print(f"ERROR: invalid integer for k (SERVER={SERVER})", file=sys.stderr)
            return 1
        out = call_tool(
            "nexus_search",
            {
                "query": sys.argv[2],
                "k": k_val,
            },
        )
        print(out)
        exit_code = 0 if _probe_success(out) else 1

    elif action == "summarize":
        if len(sys.argv) < 3:
            print(f"ERROR: missing path arguments (SERVER={SERVER})", file=sys.stderr)
            return 1
        out = call_tool("nexus_summarize",
                        _avec_modele({"paths": sys.argv[2:]}))
        print(out)
        exit_code = 0 if _probe_success(out, exige_modele=True) else 1

    elif action == "context":
        # context <instruction> <modele> <fenetre> <fichier...>
        if len(sys.argv) < 5:
            print(f"ERROR: insufficient arguments for context (SERVER={SERVER})", file=sys.stderr)
            return 1
        try:
            context_tokens = int(sys.argv[4])
        except ValueError:
            print(f"ERROR: invalid integer for context_tokens (SERVER={SERVER})", file=sys.stderr)
            return 1
        args = {
            "instruction": sys.argv[2],
            "model": sys.argv[3],
            "context_tokens": context_tokens,
            "paths": sys.argv[5:],
        }
        out = call_tool("nexus_context", args)
        print(out)
        exit_code = 0 if _probe_success(out, exige_modele=True) else 1

    elif action == "vision":
        if len(sys.argv) < 3:
            print(f"ERROR: missing path argument for vision (SERVER={SERVER})", file=sys.stderr)
            return 1
        args = {"path": sys.argv[2]}
        if len(sys.argv) > 3:
            args["prompt"] = sys.argv[3]
        if len(sys.argv) > 4:
            args["model"] = sys.argv[4]
        out = call_tool("nexus_vision", args)
        print(out)
        exit_code = 0 if _probe_success(out, exige_modele=True) else 1

    elif action == "models":
        out = call_tool("nexus_models", {})
        print(out)
        exit_code = 0 if _probe_success(out) else 1

    elif action == "ask":
        if len(sys.argv) < 3:
            print(f"ERROR: missing prompt argument for ask (SERVER={SERVER})", file=sys.stderr)
            return 1
        args = {"prompt": sys.argv[2]}
        if len(sys.argv) > 3:
            args["model"] = sys.argv[3]
        out = call_tool("nexus_ask", args)
        print(out)
        exit_code = 0 if _probe_success(out, exige_modele=True) else 1

    elif action == "route":
        if len(sys.argv) < 3:
            print(f"ERROR: missing prompt argument for route (SERVER={SERVER})", file=sys.stderr)
            return 1
        args = {"prompt": sys.argv[2]}
        if len(sys.argv) > 3:
            args["plane"] = sys.argv[3]
        out = call_tool("nexus_route", args)
        print(out)
        exit_code = 0 if _probe_success(out) else 1

    else:
        print(__doc__)
        return 1

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
