#!/usr/bin/env python3
"""
Épreuve vérifiant que nexus_test.py refuse les appels aux modèles sans l'option
--appels-modeles ou la variable NEXUS_TEST_APPELS_MODELES=1.
"""

import os
import sys
import json
import time
import socket
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

class MockNexusHandler(BaseHTTPRequestHandler):
    requests_received = []

    def do_GET(self):
        self._handle_request("GET")

    def do_POST(self):
        self._handle_request("POST")

    def _handle_request(self, method):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length) if content_length else b""
        MockNexusHandler.requests_received.append((method, self.path, body))

        if self.path == "/v1/models" and method == "GET":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({
                "data": [{"id": "alpha-cloud"}, {"id": "beta-local"}]
            }).encode("utf-8"))
        elif self.path == "/v1/chat/completions" and method == "POST":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({
                "id": "chatcmpl-123",
                "object": "chat.completion",
                "created": 1700000000,
                "model": "alpha-cloud",
                "choices": [{"message": {"role": "assistant", "content": "OK"}}]
            }).encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        # Désactive les logs du serveur HTTP pour éviter le bruit
        pass

def find_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]

def run_mock_server(port, stop_event):
    server = HTTPServer(("127.0.0.1", port), MockNexusHandler)
    while not stop_event.is_set():
        server.handle_request()

def run_test_suite(port, extra_env=None, args=None):
    env = os.environ.copy()
    env["NEXUS_LITELLM_URL"] = f"http://127.0.0.1:{port}"
    env["LITELLM_MASTER_KEY"] = "cle-factice"
    if extra_env:
        env.update(extra_env)

    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    suite_path = os.path.join(root_dir, "outillage", "nexus_test.py")

    cmd = [sys.executable, suite_path, "--only", "forward"]
    if args:
        cmd.extend(args)

    result = subprocess.run(
        cmd,
        env=env,
        capture_output=True,
        text=True,
        timeout=180
    )
    return result.returncode, result.stdout, result.stderr

def main():
    port = find_free_port()
    stop_event = threading.Event()

    # Démarre le serveur mock en arrière-plan
    server_thread = threading.Thread(
        target=run_mock_server,
        args=(port, stop_event)
    )
    server_thread.daemon = True
    server_thread.start()

    try:
        # Cas 1: Fuite - sans option ni variable, aucun appel interdit
        print("[OK  ] fuite_sans_option : démarrage")
        MockNexusHandler.requests_received.clear()
        returncode, stdout, stderr = run_test_suite(port)
        forbidden_paths = {"/v1/chat/completions", "/chat/completions",
                          "/v1/embeddings", "/embeddings", "/v1/messages", "/health"}
        received_forbidden = any(
            path.startswith(tuple(forbidden_paths))
            for _, path, _ in MockNexusHandler.requests_received
        )
        skip_found = "[SKIP]" in stdout

        if received_forbidden:
            print("[RATE] fuite_sans_option : appel interdit détecté")
            return 1
        if not skip_found:
            print("[RATE] fuite_sans_option : [SKIP] manquant dans la sortie")
            return 1
        print("[OK  ] fuite_sans_option : aucun appel interdit et [SKIP] présent")

        # Cas 2: Reverse - avec NEXUS_TEST_APPELS_MODELES=0 explicite
        print("[OK  ] reverse_explicite : démarrage")
        MockNexusHandler.requests_received.clear()
        returncode, stdout, stderr = run_test_suite(
            port,
            extra_env={"NEXUS_TEST_APPELS_MODELES": "0"}
        )
        received_forbidden = any(
            path.startswith(tuple(forbidden_paths))
            for _, path, _ in MockNexusHandler.requests_received
        )
        skip_found = "[SKIP]" in stdout

        if received_forbidden:
            print("[RATE] reverse_explicite : appel interdit détecté")
            return 1
        if not skip_found:
            print("[RATE] reverse_explicite : [SKIP] manquant dans la sortie")
            return 1
        print("[OK  ] reverse_explicite : aucun appel interdit et [SKIP] présent")

        # Cas 3: Forward - avec --appels-modeles, au moins un POST /v1/chat/completions
        print("[OK  ] forward_avec_option : démarrage")
        MockNexusHandler.requests_received.clear()
        returncode, stdout, stderr = run_test_suite(
            port,
            args=["--appels-modeles"]
        )
        post_completions = any(
            method == "POST" and path == "/v1/chat/completions"
            for method, path, _ in MockNexusHandler.requests_received
        )

        if not post_completions:
            print("[RATE] forward_avec_option : aucun POST /v1/chat/completions détecté")
            return 1
        print("[OK  ] forward_avec_option : POST /v1/chat/completions détecté")

        return 0

    finally:
        stop_event.set()
        # Petite pause pour s'assurer que le serveur s'arrête
        time.sleep(0.1)

if __name__ == "__main__":
    sys.exit(main())
