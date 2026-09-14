"""Épreuve du pont – session voisine du 2026‑09‑14.
Ce script reproduit le scratchpad de session et crée les copies
dans le répertoire temporaire prévu. Le pont refusait auparavant
les chemins : il faut donc lancer le serveur MCP via Node.

Cette version remplace les appels à **nexus_summarize** par
**nexus_vision**. La garde implémentée dans *nexus_vision* ne dépend
d’aucun modèle ni d’aucun verrou : elle résout le chemin, vérifie
l’existence du fichier, contrôle l’extension et rejette les
fichiers « .txt » avec l’erreur « format non pris en charge : .txt ».
Ainsi aucune inférence n’est déclenchée avant la validation du
chemin.
"""

import os
import sys
import json
import subprocess
import tempfile
import pathlib

# ----------------------------------------------------------------------
# Configuration du test
# ----------------------------------------------------------------------
# Chemin du serveur MCP (relatif au fichier d’épreuve)
SERVER_JS = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..', 'tools', 'nexus-mcp', 'server.js')
)

# Répertoire temporaire qui servira de racine supplémentaire en lecture
TMP_ROOT = tempfile.mkdtemp()
CLAUDE_DIR = os.path.join(TMP_ROOT, 'Temp', 'claude', 'x', 'scratchpad')
AUTRE_DIR = os.path.join(TMP_ROOT, 'Temp', 'autre')
os.makedirs(CLAUDE_DIR, exist_ok=True)
os.makedirs(AUTRE_DIR, exist_ok=True)

# Fichiers de test
COPIE_TXT = os.path.join(CLAUDE_DIR, 'copie.txt')
SECRET_TXT = os.path.join(AUTRE_DIR, 'secret.txt')
with open(COPIE_TXT, 'w', encoding='utf-8') as f:
    f.write('contenu autorisé')
with open(SECRET_TXT, 'w', encoding='utf-8') as f:
    f.write('contenu secret')

# Environnement du serveur : on ajoute LOCALAPPDATA pour activer la racine
# supplémentaire « Temp/claude ».
env = os.environ.copy()
env['LOCALAPPDATA'] = TMP_ROOT

# ----------------------------------------------------------------------
# Construction du flux JSON‑RPC
# ----------------------------------------------------------------------
messages = []

# 1. initialise
messages.append(json.dumps({
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": "2025-06-18",
        "capabilities": {},
        "clientInfo": {"name": "test", "version": "1"}
    }
}))

# 2. reverse – chemin refusé, doit mentionner « Temp/claude »
messages.append(json.dumps({
    "jsonrpc": "2.0",
    "id": 2,
    "method": "tools/call",
    "params": {
        "name": "nexus_vision",
        "arguments": {"path": os.path.join(TMP_ROOT, 'Temp', 'autre', 'secret.txt')}
    }
}))

# 3. fuite – tentative de traversal, doit être refusée (pas de condition sur la mention)
messages.append(json.dumps({
    "jsonrpc": "2.0",
    "id": 3,
    "method": "tools/call",
    "params": {
        "name": "nexus_vision",
        "arguments": {"path": os.path.join(TMP_ROOT, 'Temp', 'claude', '..', 'autre', 'secret.txt')}
    }
}))

# 4. forward – chemin autorisé, le texte de refus ne doit pas apparaître
messages.append(json.dumps({
    "jsonrpc": "2.0",
    "id": 4,
    "method": "tools/call",
    "params": {
        "name": "nexus_vision",
        "arguments": {"path": COPIE_TXT}
    }
}))

# Le protocole attend les messages séparés par « \n » et un « \n » final.
payload = "\n".join(messages) + "\n"

# ----------------------------------------------------------------------
# Lancement du serveur et échange RPC
# ----------------------------------------------------------------------
repo_root = pathlib.Path(__file__).resolve().parents[1]

try:
    result = subprocess.run(
        ['node', SERVER_JS],
        input=payload,
        capture_output=True,
        text=True,
        env=env,
        cwd=str(repo_root),
        timeout=180
    )
except Exception as e:
    print(f"[RATE] pont : {e}")
    sys.exit(1)

# ----------------------------------------------------------------------
# Analyse des réponses
# ----------------------------------------------------------------------
replies = {}
for line in result.stdout.splitlines():
    line = line.strip()
    if line.startswith('{'):
        try:
            obj = json.loads(line)
            replies[obj.get('id')] = obj
        except Exception:
            continue  # ligne non‑JSON, on l’ignore

def check(id_, name, expect_refuse, expect_mention_claude):
    """Vérifie le résultat d’un appel et imprime le statut."""
    resp = replies.get(id_)
    if not resp:
        print(f"[RATE] {name} : aucune réponse")
        return False

    try:
        text = resp['result']['content'][0]['text']
    except Exception:
        print(f"[RATE] {name} : format de réponse inattendu")
        return False

    ok = True
    detail_parts = []

    # Vérification du refus
    if expect_refuse:
        if 'refuse' not in text.lower():
            ok = False
            detail_parts.append("absence du mot « refuse »")
    else:
        if 'refuse' in text.lower():
            ok = False
            detail_parts.append("mot « refuse » présent")

    # Vérification de la mention de la racine « claude » (insensible à la casse et au séparateur)
    if expect_mention_claude:
        if 'claude' not in text.lower():
            ok = False
            detail_parts.append("absence de la mention « claude »")
    # sinon aucune contrainte sur la présence ou l’absence de la mention

    # Cas particulier du forward : le résumé peut échouer faute de modèle.
    if name == 'forward' and not ok and 'refuse' not in text.lower():
        ok = True
        detail_parts = ["résumé manquant mais pas de refus"]

    status = "[OK  ]" if ok else "[RATE]"
    detail = "; ".join(detail_parts) if detail_parts else "OK"
    print(f"{status} {name} : {detail}")
    return ok

all_ok = True
all_ok &= check(2, 'reverse', expect_refuse=True, expect_mention_claude=True)
all_ok &= check(3, 'fuite',   expect_refuse=True, expect_mention_claude=False)
all_ok &= check(4, 'forward', expect_refuse=False, expect_mention_claude=False)

# Nettoyage du répertoire temporaire
try:
    import shutil
    shutil.rmtree(TMP_ROOT)
except Exception:
    pass

sys.exit(0 if all_ok else 1)
