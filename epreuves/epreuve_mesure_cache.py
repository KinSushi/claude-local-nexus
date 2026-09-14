import json
import os
import sys
from unittest.mock import patch

sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "outillage")
)
import nexus_mesure_cache

passed = True


def check(cond, label):
    global passed
    if cond:
        print(f"[OK] {label}")
    else:
        print(f"[RATE] {label}")
        passed = False


# 7 verdict_cache cases
ref_ok = {"prompt_eval_count": 100, "ttft_ms": 100.0}
check(
    nexus_mesure_cache.verdict_cache(
        {"prompt_eval_count": 100, "ttft_ms": 100.0},
        [
            {"prompt_eval_count": 40, "ttft_ms": 100.0},
            {"prompt_eval_count": 40, "ttft_ms": 100.0},
        ],
    ) == "CACHE ACTIF",
    "verdict_cache actif par count",
)

check(
    nexus_mesure_cache.verdict_cache(
        {"prompt_eval_count": 100, "ttft_ms": 1000.0},
        [
            {"prompt_eval_count": 100, "ttft_ms": 400.0},
            {"prompt_eval_count": 100, "ttft_ms": 400.0},
        ],
    ) == "CACHE ACTIF",
    "verdict_cache actif par ttft",
)

check(
    nexus_mesure_cache.verdict_cache(
        {"prompt_eval_count": 100, "ttft_ms": 1000.0},
        [
            {"prompt_eval_count": 95, "ttft_ms": 950.0},
            {"prompt_eval_count": 95, "ttft_ms": 950.0},
        ],
    ) == "CACHE INACTIF",
    "verdict_cache inactif",
)

check(
    nexus_mesure_cache.verdict_cache(
        {"prompt_eval_count": 100, "ttft_ms": 1000.0},
        [
            {"prompt_eval_count": 70, "ttft_ms": 800.0},
            {"prompt_eval_count": 70, "ttft_ms": 800.0},
        ],
    ) == "CACHE INCERTAIN",
    "verdict_cache incertain",
)

check(
    nexus_mesure_cache.verdict_cache({"prompt_eval_count": 100, "ttft_ms": 100.0}, [])
    == "CACHE INCERTAIN",
    "verdict_cache suivants vides",
)

check(
    nexus_mesure_cache.verdict_cache(
        {"prompt_eval_count": 0, "ttft_ms": 100.0},
        [{"prompt_eval_count": 50, "ttft_ms": 50.0}],
    ) == "CACHE INCERTAIN",
    "verdict_cache reference count 0",
)

check(
    nexus_mesure_cache.verdict_cache(
        {"prompt_eval_count": 100, "ttft_ms": 0.0},
        [{"prompt_eval_count": 50, "ttft_ms": 50.0}],
    ) == "CACHE INCERTAIN",
    "verdict_cache reference ttft 0",
)

# 2 prefixe cases
check(
    nexus_mesure_cache.prefixe(5) == "mot0 mot1 mot2 mot3 mot4",
    "prefixe longueur",
)

p1 = nexus_mesure_cache.prefixe(10)
p2 = nexus_mesure_cache.prefixe(10)
check(p1 == p2, "prefixe determinisme")

# 3 detecte_contention cases
ps_big = {"models": [{"name": "other:latest", "model": "other:latest", "size": 20 * 1024**3}]}
cont, msg, size_go = nexus_mesure_cache.detecte_contention(ps_big, "llama3.2:1b", 15.0)
check(
    cont and "MOTEUR OCCUPE par other:latest (20.0 Go)" in msg and abs(size_go - 20.0) < 0.05,
    "detecte_contention autre modele 20 Go",
)

ps_same = {"models": [{"name": "llama3.2:1b", "model": "llama3.2:1b", "size": 30 * 1024**3}]}
cont2, msg2, size2 = nexus_mesure_cache.detecte_contention(ps_same, "llama3.2:1b", 15.0)
check(not cont2, "detecte_contention meme modele ignore")

ps_small = {"models": [{"name": "other:latest", "model": "other:latest", "size": 10 * 1024**3}]}
cont3, msg3, size3 = nexus_mesure_cache.detecte_contention(ps_small, "llama3.2:1b", 15.0)
check(not cont3, "detecte_contention autre modele 10 Go libre")

# appel case with mock
class FakeResponse:
    def __init__(self, lines):
        self.lines = lines

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    def __iter__(self):
        return iter(self.lines)


chunk1 = json.dumps({"message": {"content": "Bonjour"}, "done": False}).encode("utf-8")
chunk2 = json.dumps(
    {
        "done": True,
        "prompt_eval_count": 10,
        "prompt_eval_duration": 5000000,  # ns
        "eval_count": 2,
    }
).encode("utf-8")

fake_lines = [chunk1 + b"\n", chunk2 + b"\n"]


def fake_urlopen(req, timeout=None):
    # Capture request data for assertion
    fake_urlopen.req_data = req.data
    return FakeResponse(fake_lines)


fake_urlopen.req_data = None

with patch("urllib.request.urlopen", side_effect=fake_urlopen):
    res = nexus_mesure_cache.appel(
        "http://127.0.0.1:11434",
        "llama3.2:1b",
        "mot0 mot1 mot2",
        "Test question",
        10,
    )

# Verify request body
req_body = json.loads(fake_urlopen.req_data.decode("utf-8"))
system_msg = req_body["messages"][0]
user_msg = req_body["messages"][1]
check(
    system_msg["role"] == "system" and system_msg["content"] == "mot0 mot1 mot2",
    "appel envoie systeme correct",
)
check(
    res["prompt_eval_count"] == 10
    and abs(res["prompt_eval_duration_ms"] - 5.0) < 0.0001
    and res["eval_count"] == 2
    and res["ttft_ms"] > 0,
    "appel retourne metriques",
)

sys.exit(0 if passed else 1)
