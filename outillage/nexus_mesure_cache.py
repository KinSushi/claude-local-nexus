"""Measure whether the Ollama KV prefix cache is active.

This tool performs a warmup call, a reference call, and several follow-up
calls with the same large prefix but different questions. It compares
prompt_eval_count and time-to-first-token (TTFT) between the reference and
the follow-ups to decide if the prefix was served from cache.

It does NOT measure generation throughput (tokens per second).
"""

import argparse
import json
import statistics
import sys
import time
import urllib.error
import urllib.request


def prefixe(n):
    """Return a deterministic string 'mot0 mot1 ... mot{n-1}'."""
    if n <= 0:
        return ""
    return " ".join("mot%d" % i for i in range(n))


def appel(url, modele, systeme, question, timeout):
    """Send a chat request to Ollama and return timing and metrics.

    Returns a dict with keys:
        ttft_ms: milliseconds from just before urlopen to first non-empty content
        prompt_eval_count: number of prompt tokens evaluated (from done line)
        prompt_eval_duration_ms: prompt evaluation duration in ms
        eval_count: number of generated tokens
    """
    body = {
        "model": modele,
        "messages": [
            {"role": "system", "content": systeme},
            {"role": "user", "content": question},
        ],
        "stream": True,
        "options": {"temperature": 0, "num_predict": 32},
    }
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url.rstrip("/") + "/api/chat",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    t0 = time.perf_counter()
    ttft_ms = None
    prompt_eval_count = None
    prompt_eval_duration_ms = None
    eval_count = None

    with urllib.request.urlopen(req, timeout=timeout) as response:
        for ligne in response:
            ligne = ligne.decode("utf-8").strip()
            if not ligne:
                continue
            obj = json.loads(ligne)
            content = obj.get("message", {}).get("content", "")
            if ttft_ms is None and content:
                ttft_ms = (time.perf_counter() - t0) * 1000.0
            if obj.get("done"):
                prompt_eval_count = obj.get("prompt_eval_count", 0)
                prompt_eval_duration_ns = obj.get("prompt_eval_duration", 0)
                prompt_eval_duration_ms = prompt_eval_duration_ns / 1e6
                eval_count = obj.get("eval_count", 0)
                break

    if ttft_ms is None:
        ttft_ms = (time.perf_counter() - t0) * 1000.0
    return {
        "ttft_ms": ttft_ms,
        "prompt_eval_count": prompt_eval_count,
        "prompt_eval_duration_ms": prompt_eval_duration_ms,
        "eval_count": eval_count,
    }


def detecte_contention(ps, modele, seuil_go):
    """Return (True, message, size_go) if another model occupies more than seuil_go GB."""
    models = ps.get("models", [])
    target_names = {modele, modele + ":latest"}
    for entry in models:
        name = entry.get("name", "")
        model = entry.get("model", "")
        if name in target_names or model in target_names:
            continue
        size_bytes = entry.get("size", 0)
        size_go = size_bytes / (1024 ** 3)
        if size_go > seuil_go:
            nom = name if name else model
            msg = f"MOTEUR OCCUPE par {nom} ({size_go:.1f} Go) : mesure differee"
            return True, msg, size_go
    return False, "", 0.0


def verdict_cache(reference, suivants):
    """Return 'CACHE ACTIF', 'CACHE INACTIF', or 'CACHE INCERTAIN'."""
    if not suivants:
        return "CACHE INCERTAIN"
    if reference.get("prompt_eval_count", 0) == 0 or reference.get("ttft_ms", 0) == 0:
        return "CACHE INCERTAIN"

    ref_count = reference["prompt_eval_count"]
    ref_ttft = reference["ttft_ms"]

    counts = [s["prompt_eval_count"] for s in suivants]
    ttfts = [s["ttft_ms"] for s in suivants]

    median_count = statistics.median(counts)
    median_ttft = statistics.median(ttfts)

    ratio_count = median_count / ref_count
    ratio_ttft = median_ttft / ref_ttft

    if ratio_count < 0.5 or ratio_ttft < 0.5:
        return "CACHE ACTIF"
    if ratio_count >= 0.9 and ratio_ttft >= 0.9:
        return "CACHE INACTIF"
    return "CACHE INCERTAIN"


def main():
    parser = argparse.ArgumentParser(description="Measure Ollama KV cache activity")
    parser.add_argument("--modele", default="llama3.2:1b")
    parser.add_argument("--url", default="http://127.0.0.1:11434")
    parser.add_argument("--prefixe-mots", type=int, default=600)
    parser.add_argument("--repetitions", type=int, default=3,
                        help="total measured calls including reference")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--timeout", type=int, default=300)
    args = parser.parse_args()

    # Check engine reachable and not contended
    try:
        with urllib.request.urlopen(args.url.rstrip("/") + "/api/ps", timeout=args.timeout) as resp:
            ps = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
        sys.stderr.write(f"MOTEUR INJOIGNABLE : {e}\n")
        return 2
    except Exception as e:
        sys.stderr.write(f"MOTEUR INJOIGNABLE : {e}\n")
        return 2

    cont, msg, _ = detecte_contention(ps, args.modele, 15.0)
    if cont:
        sys.stderr.write(msg + "\n")
        return 3

    # Build prefix and inverse prefix
    p = prefixe(args.prefixe_mots)
    words = p.split()
    inverse_p = " ".join(reversed(words))

    # Warmup (measured but not part of verdict)
    try:
        echauffement = appel(args.url, args.modele, inverse_p, "Reponds OK.", args.timeout)
    except Exception as e:
        sys.stderr.write(f"APPEL RATE : {e}\n")
        return 2

    # Reference call
    try:
        reference = appel(args.url, args.modele, p, "Quelle est la capitale de la France ?", args.timeout)
    except Exception as e:
        sys.stderr.write(f"APPEL RATE : {e}\n")
        return 2

    # Follow-up calls
    questions = [
        "What is 2+2?",
        "Who wrote Hamlet?",
        "What is the speed of light?",
        "Name a planet.",
        "What is water made of?",
        "Define gravity.",
    ]
    suivants = []
    for i in range(1, args.repetitions):
        q = questions[(i - 1) % len(questions)]
        try:
            res = appel(args.url, args.modele, p, q, args.timeout)
            suivants.append(res)
        except Exception as e:
            sys.stderr.write(f"APPEL RATE : {e}\n")
            return 2

    verdict = verdict_cache(reference, suivants)

    if args.json:
        output = {
            "modele": args.modele,
            "prefixe_mots": args.prefixe_mots,
            "echauffement": echauffement,
            "reference": reference,
            "suivants": suivants,
            "verdict": verdict,
        }
        print(json.dumps(output, indent=2, ensure_ascii=True))
    else:
        # Fixed-width table
        headers = ["appel", "ttft_ms", "prompt_eval_count", "prompt_eval_ms", "eval_count"]
        col_widths = [20, 12, 20, 15, 12]
        header_line = "".join(
            headers[i].ljust(col_widths[i]) for i in range(len(headers))
        )
        print(header_line)
        print("-" * sum(col_widths))

        def print_row(label, d):
            ttft = "{:.2f}".format(d["ttft_ms"])
            pe_count = str(d["prompt_eval_count"])
            pe_ms = "{:.2f}".format(d["prompt_eval_duration_ms"])
            eval_c = str(d["eval_count"])
            row = [
                label,
                ttft,
                pe_count,
                pe_ms,
                eval_c,
            ]
            print("".join(row[i].ljust(col_widths[i]) for i in range(len(row))))

        print_row("echauffement", echauffement)
        print_row("reference", reference)
        for idx, s in enumerate(suivants, start=1):
            print_row("suivant %d" % idx, s)
        print(f"Verdict : {verdict}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
