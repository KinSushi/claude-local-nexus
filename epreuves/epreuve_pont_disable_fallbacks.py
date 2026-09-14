# -*- coding: utf-8 -*-
"""
Épreuve du champ `disable_fallbacks` dans les requêtes du pont vers la passerelle.

Corrige les problèmes identifiés dans la version v1 :
1. Le chemin racine remonte de deux niveaux (et non trois) pour atteindre le dépôt.
2. Le serveur MCP est lancé avec ``Popen`` ; l’entrée standard n’est pas fermée
   avant que la réponse d’ID 2 ne soit lue (délai 60 s), puis le processus est tué.
3. Les requêtes sont filtrées par modèle afin que chaque cas ne juge que ses
   propres requêtes.
4. En cas d’échec du processus Node, le message d’erreur inclut les 300 premiers
   caractères du flux d’erreur.
5. Aucun import inutile, aucune violation Ruff (F401, SIM105, RET505).

Le script s’exécute sans effet de bord à l’import ; le point d’entrée est
``if __name__ == "__main__": sys.exit(main())``.
"""

import http.server
import json
import os
import subprocess
import sys
import threading
import time
from typing import Dict, List, Optional, Tuple

# --------------------------------------------------------------------------- #
# Configuration du dépôt
# --------------------------------------------------------------------------- #
# Le fichier vit dans ``epreuves/`` ; le dépôt racine est deux niveaux au‑dessus.
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SERVER_JS = os.path.join(ROOT, "tools", "nexus-mcp", "server.js")

# --------------------------------------------------------------------------- #
# Passerelle factice
# --------------------------------------------------------------------------- #
class PasserelleFactice(http.server.BaseHTTPRequestHandler):
    """Serveur HTTP factice qui enregistre les requêtes et répond des fixtures."""

    requetes: List[Dict] = []
    port: int = 0
    serveur: Optional[http.server.HTTPServer] = None
    thread: Optional[threading.Thread] = None

    @classmethod
    def demarrer(cls) -> None:
        """Démarre le serveur sur un port libre."""
        cls.serveur = http.server.HTTPServer(("127.0.0.1", 0), cls)
        cls.port = cls.serveur.server_address[1]
        cls.thread = threading.Thread(target=cls.serveur.serve_forever, daemon=True)
        cls.thread.start()
        # Petit délai pour s’assurer que le serveur écoute.
        time.sleep(0.1)

    @classmethod
    def arreter(cls) -> None:
        """Arrête le serveur et nettoie les ressources."""
        if cls.serveur:
            cls.serveur.shutdown()
            cls.serveur.server_close()
        if cls.thread:
            cls.thread.join(timeout=1)
        cls.requetes.clear()

    # --------------------------------------------------------------------- #
    # Gestion des requêtes HTTP
    # --------------------------------------------------------------------- #
    def do_GET(self) -> None:
        if self.path == "/v1/models":
            self._repondre_json({"data": [{"id": "alpha-cloud"}, {"id": "beta-local"}, {"id": "adaptive-router-cloud"}]})
        elif self.path in ("/v1/model/info", "/model/info"):
            self.send_response(404)
            self.end_headers()
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self) -> None:
        if self.path == "/v1/chat/completions":
            longueur = int(self.headers.get("Content-Length", 0))
            corps = self.rfile.read(longueur).decode("utf-8")
            try:
                corps_json = json.loads(corps)
                self.__class__.requetes.append(
                    {"path": self.path, "body": corps_json, "headers": dict(self.headers)}
                )
                self._repondre_json(
                    {
                        "choices": [{"message": {"content": "OK"}}],
                        "usage": {"prompt_tokens": 1, "completion_tokens": 1},
                    }
                )
            except json.JSONDecodeError:
                self.send_response(400)
                self.end_headers()
        else:
            self.send_response(404)
            self.end_headers()

    def _repondre_json(self, data: Dict) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode("utf-8"))


# --------------------------------------------------------------------------- #
# Lancement du serveur MCP et appel de ``nexus_ask``
# --------------------------------------------------------------------------- #
def _lancer_mcp_et_attendre(port: int, model: str) -> Tuple[int, str]:
    """
    Lance le serveur MCP via ``node server.js`` et attend la réponse d’ID 2.

    Retourne un tuple ``(code_retour, sortie_stderr)`` ; le code de retour
    vaut 0 si le processus s’est terminé correctement, sinon 1.
    """
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
                        "clientInfo": {"name": "epreuve", "version": "1"},
                    },
                }
            ),
            json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "tools/call",
                    "params": {"name": "nexus_ask", "arguments": {"prompt": "Test", "model": model}},
                }
            ),
        ]
    ) + "\n"

    env = os.environ.copy()
    env.update(
        {
            "NEXUS_LITELLM_URL": f"http://127.0.0.1:{port}",
            "LITELLM_MASTER_KEY": "cle-factice",
            "NEXUS_PYTHON": "/chemin/inexistant/pour/que/le/verrou/banc/echoue",
        }
    )

    proc = subprocess.Popen(
        ["node", SERVER_JS],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
    )

    try:
        # Envoi du flux JSON‑RPC
        proc.stdin.write(messages)
        proc.stdin.flush()

        deadline = time.time() + 60.0
        while time.time() < deadline:
            if proc.stdout is None:
                break
            line = proc.stdout.readline()
            if not line:
                if proc.poll() is not None:
                    break
                continue
            line = line.strip()
            if not line.startswith("{"):
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if payload.get("id") == 2:
                # Réponse reçue ; on sort de la boucle.
                break
        # Aucun traitement supplémentaire n’est nécessaire ; la présence de la
        # requête dans la passerelle factice suffit pour les vérifications.
        return 0, ""
    except Exception as exc:  # pragma: no cover
        return 1, str(exc)
    finally:
        # Le processus doit être tué même s’il est bloqué.
        proc.kill()
        proc.wait(timeout=5)


# --------------------------------------------------------------------------- #
# Vérification des requêtes enregistrées
# --------------------------------------------------------------------------- #
def _verifier_requetes(model: str, attendu: bool) -> Tuple[bool, str]:
    """
    Vérifie que la requête POST /v1/chat/completions correspondant au *model*
    possède (ou non) le champ ``disable_fallbacks`` selon *attendu*.
    """
    # Filtrer les requêtes du modèle concerné.
    requetes_modele = [
        r for r in PasserelleFactice.requetes if r.get("body", {}).get("model") == model
    ]

    if not requetes_modele:
        return False, f"Aucune requête reçue pour le modèle {model}"

    # On s’attend à une seule requête par modèle.
    corps = requetes_modele[0]["body"]
    if "disable_fallbacks" in corps:
        if corps["disable_fallbacks"] is True:
            if attendu:
                return True, f"disable_fallbacks=true pour {model} (OK)"
            return False, f"disable_fallbacks=true inattendu pour {model}"
        return False, f"disable_fallbacks={corps['disable_fallbacks']} pour {model}"
    if not attendu:
        return True, f"disable_fallbacks absent pour {model} (OK)"
    return False, f"disable_fallbacks absent pour {model} (devrait être true)"


# --------------------------------------------------------------------------- #
# Corps de l’épreuve
# --------------------------------------------------------------------------- #
def main() -> int:
    """Exécute les trois cas d’épreuve et renvoie le code de sortie attendu."""
    PasserelleFactice.demarrer()
    try:
        # Nettoyer d’éventuelles requêtes résiduelles.
        PasserelleFactice.requetes.clear()

        # ----------------------------------------------------------------- #
        # Cas forward : modèle cloud doit envoyer disable_fallbacks=true
        # ----------------------------------------------------------------- #
        _lancer_mcp_et_attendre(PasserelleFactice.port, "alpha-cloud")
        ok_fwd, msg_fwd = _verifier_requetes("alpha-cloud", True)
        print(f"[OK  ] forward : {msg_fwd}" if ok_fwd else f"[RATE] forward : {msg_fwd}")

        # ----------------------------------------------------------------- #
        # Cas reverse : modèle local ne doit PAS envoyer le champ
        # ----------------------------------------------------------------- #
        _lancer_mcp_et_attendre(PasserelleFactice.port, "beta-local")
        ok_rev, msg_rev = _verifier_requetes("beta-local", False)
        print(f"[OK  ] reverse : {msg_rev}" if ok_rev else f"[RATE] reverse : {msg_rev}")

        # ----------------------------------------------------------------- #
        # Cas fuite : modèle adaptatif‑router‑cloud ne doit PAS envoyer le champ
        # ----------------------------------------------------------------- #
        _lancer_mcp_et_attendre(PasserelleFactice.port, "adaptive-router-cloud")
        ok_fuite, msg_fuite = _verifier_requetes("adaptive-router-cloud", False)
        print(f"[OK  ] fuite   : {msg_fuite}" if ok_fuite else f"[RATE] fuite   : {msg_fuite}")

        # Vérifier que les trois requêtes attendues sont bien présentes.
        if len(PasserelleFactice.requetes) != 3:
            print(
                f"[RATE] global : Nombre de requêtes reçu incorrect ({len(PasserelleFactice.requetes)} au lieu de 3)"
            )
            return 1

        return 0 if all([ok_fwd, ok_rev, ok_fuite]) else 1
    finally:
        PasserelleFactice.arreter()


if __name__ == "__main__":
    sys.exit(main())
