"""Epreuve de forme des rendus du serveur MCP du depot.

Mesure du 2026-09-18 : le serveur repond aux appels d'outils par
    reply(id, { content: [{ type: "text", text }], isError: false });
ou text est ce que rend le handler. Presque tous rendent une CHAINE. Deux
rendaient un OBJET, qui se retrouvait PLACE DANS le champ text : celui-ci
cessait d'etre une chaine et le client rejetait toute la reponse comme
malformee. Les deux cas etaient des chemins de REFUS -- ceux qu'on emprunte
quand on s'est trompe de parametre, donc au moment ou un message lisible
compte le plus.

Un refus qui devient illisible au moment ou il compte coute plus cher que
pas de refus du tout.

L'epreuve parle au serveur par son protocole reel : node, JSON-RPC ligne par
ligne sur stdin/stdout, sequence initialize puis tools/call.
"""

import json
import os
import shutil
import subprocess
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RACINE, "outillage"))

try:
    from console_tools import forcer_utf8

    forcer_utf8()
except Exception as raison:  # noqa: BLE001
    sys.stderr.write("garde d'encodage indisponible : %s\n" % (raison,))

CHEMIN_SERVEUR = os.path.join(RACINE, "tools", "nexus-mcp", "server.js")

DELAI_DEFAUT = 20.0
DELAI_RECHERCHE = 90.0


def ligne_harness(ok, nom, detail):
    """Emet une ligne au format du harnais du depot."""
    marque = "[OK  ]" if ok else "[RATE]"
    print("%s %s : %s" % (marque, nom, detail))


def _lire_reponse(processus, identifiant, delai):
    """Lit stdout ligne par ligne jusqu'a la reponse d'identifiant donne."""
    import threading

    resultat = {}

    def lecteur():
        try:
            for ligne in processus.stdout:
                ligne = ligne.strip()
                if not ligne:
                    continue
                try:
                    message = json.loads(ligne)
                except ValueError:
                    continue
                if isinstance(message, dict) and message.get("id") == identifiant:
                    resultat["message"] = message
                    return
        except Exception:  # noqa: BLE001
            return

    fil = threading.Thread(target=lecteur, daemon=True)
    fil.start()
    fil.join(delai)
    return resultat.get("message")


def _terminer(processus):
    """Termine le processus dans tous les cas."""
    if processus is None:
        return
    try:
        processus.terminate()
        processus.wait(timeout=5)
    except Exception:  # noqa: BLE001
        try:
            processus.kill()
            processus.wait(timeout=5)
        except Exception:  # noqa: BLE001
            pass


def appeler_outil(nom_outil, arguments, delai):
    """Lance le serveur, fait initialize puis tools/call, rend la reponse."""
    processus = subprocess.Popen(
        ["node", CHEMIN_SERVEUR],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        cwd=RACINE,
        text=True,
        encoding="utf-8",
        bufsize=1,
    )
    try:
        demande_init = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "epreuve-forme", "version": "1.0"},
            },
        }
        processus.stdin.write(json.dumps(demande_init) + "\n")
        processus.stdin.flush()
        _lire_reponse(processus, 1, DELAI_DEFAUT)

        demande_appel = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {"name": nom_outil, "arguments": arguments},
        }
        processus.stdin.write(json.dumps(demande_appel) + "\n")
        processus.stdin.flush()
        return _lire_reponse(processus, 2, delai)
    finally:
        _terminer(processus)


def extraire_text(reponse):
    """Rend (texte, raison) : texte si content[0].text est une chaine."""
    if not isinstance(reponse, dict):
        return None, "reponse absente ou non-objet"
    resultat = reponse.get("result")
    if not isinstance(resultat, dict):
        return None, "champ result absent ou non-objet"
    contenu = resultat.get("content")
    if not isinstance(contenu, list) or len(contenu) < 1:
        return None, "champ content absent ou vide"
    premier = contenu[0]
    if not isinstance(premier, dict):
        return None, "content[0] n'est pas un objet"
    texte = premier.get("text")
    if not isinstance(texte, str):
        return None, "content[0].text n'est pas une chaine (type %s)" % (
            type(texte).__name__,
        )
    return texte, None


def cas_refus(nom_outil, arguments, mots_attendus, nom_cas):
    """Cas 1 et 2 : un refus doit porter un text de type chaine, lisible."""
    try:
        reponse = appeler_outil(nom_outil, arguments, DELAI_DEFAUT)
    except Exception as raison:  # noqa: BLE001
        ligne_harness(False, nom_cas, "appel impossible : %s" % (raison,))
        return False
    texte, raison = extraire_text(reponse)
    if texte is None:
        ligne_harness(False, nom_cas, "type manquant : %s" % (raison,))
        return False
    manquants = [mot for mot in mots_attendus if mot not in texte]
    if manquants:
        ligne_harness(
            False,
            nom_cas,
            "nom manquant : la chaine ne nomme pas %s" % (", ".join(manquants),),
        )
        return False
    ligne_harness(
        True,
        nom_cas,
        "refus lisible, chaine de %d caracteres nommant %s"
        % (len(texte), ", ".join(mots_attendus)),
    )
    return True


def cas_nominal():
    """Cas 3 : le chemin nominal rend une chaine non vide, sans marque de refus."""
    nom_cas = "nexus_livres nominal"
    try:
        reponse = appeler_outil(
            "nexus_livres",
            {"question": "que disent les tests du depot ?"},
            DELAI_RECHERCHE,
        )
    except Exception as raison:  # noqa: BLE001
        ligne_harness(False, nom_cas, "appel impossible : %s" % (raison,))
        return False
    texte, raison = extraire_text(reponse)
    if texte is None:
        ligne_harness(False, nom_cas, "rendu malforme : %s" % (raison,))
        return False
    if not texte.strip():
        ligne_harness(False, nom_cas, "chaine vide")
        return False
    if "question" in texte:
        ligne_harness(
            False,
            nom_cas,
            "le rendu nominal ressemble au message de refus : la chaine nomme "
            "le parametre attendu, l'outil ne fait plus son travail",
        )
        return False
    ligne_harness(True, nom_cas, "chaine non vide de %d caracteres" % (len(texte),))
    return True


def cas_contre_epreuve():
    """Cas 4 : le critere doit REJETER un rendu fautif construit en memoire."""
    nom_cas = "contre-epreuve du critere"
    fautif = {
        "jsonrpc": "2.0",
        "id": 2,
        "result": {
            "content": [{"type": "text", "text": {"erreur": "parametre manquant"}}],
            "isError": False,
        },
    }
    texte, raison = extraire_text(fautif)
    if texte is not None:
        ligne_harness(
            False,
            nom_cas,
            "le critere a accepte un text non-chaine : l'epreuve ne prouve rien",
        )
        return False
    ligne_harness(True, nom_cas, "critere rejette bien le rendu fautif (%s)" % (raison,))
    return True


def main():
    """Execute les quatre cas et rend le code de sortie."""
    if shutil.which("node") is None:
        ligne_harness(False, "environnement", "node introuvable dans le PATH")
        print("conclusion : 0 cas reussi sur 4 -- mesure impossible")
        return 1
    if not os.path.isfile(CHEMIN_SERVEUR):
        ligne_harness(
            False, "environnement", "serveur introuvable : %s" % (CHEMIN_SERVEUR,)
        )
        print("conclusion : 0 cas reussi sur 4 -- mesure impossible")
        return 1

    resultats = [
        cas_refus("nexus_livres", {}, ["question"], "nexus_livres refus"),
        cas_refus("nexus_apply", {}, ["texte", "cible"], "nexus_apply refus"),
        cas_nominal(),
        cas_contre_epreuve(),
    ]
    reussis = sum(1 for r in resultats if r)
    print("conclusion : %d cas reussi(s) sur %d" % (reussis, len(resultats)))
    return 0 if reussis == len(resultats) else 1


if __name__ == "__main__":
    sys.exit(main())
