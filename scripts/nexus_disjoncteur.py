"""nexus_disjoncteur module
Implements a durable circuit breaker pattern.
It protects calls to external services by opening the circuit after a
configured number of consecutive failures and blocking further calls
until a recovery timeout expires.
It does not protect the internal logic of the agent itself nor any
persistent data other than the circuit state stored in a json file.
Source of the pattern: classic circuit breaker design as described in
AI agent literature.
"""

import os
import json
import time
import argparse
from threading import RLock

_STATE_DIR = ".nexus"
_STATE_FILE = "circuit_state.json"
MAX_RETRIES = 5

def _retry_delay(attempt):
    """
    Return delay in seconds for the given attempt number (starting at 0).
    Base delay is 0.1 s, doubled each attempt, capped at 30 s,
    plus a random jitter uniformly distributed between 0 and the current delay.
    """
    import random
    base = 0.1 * (2 ** attempt)
    delay = min(base, 30.0)
    jitter = random.uniform(0, delay)
    return delay + jitter


def _state_path():
    """Return absolute path to the json file that stores the circuit state."""
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    return os.path.join(base_dir, _STATE_DIR, _STATE_FILE)


def _load_state():
    """Load state from json file. Return empty dict on any error."""
    path = _state_path()
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_state(state):
    """Write state to json file. Silently ignore any error."""
    path = _state_path()
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(state, f)
    except Exception:
        pass


def echec_transitoire(message):
    """
    Return True if the given message (case insensitive) contains any of the
    transient failure signals defined in the original pattern description.
    Signals: 429, rate limit, timeout, timed out, connection, unavailable, 503.
    The pattern source is the AI agent literature circuit breaker chapter.
    """
    if not isinstance(message, str):
        return False
    lowered = message.lower()
    signals = ["429", "rate limit", "timeout", "timed out", "connection", "unavailable", "503"]
    if any(sig in lowered for sig in signals):
        return True
    # Mesure du 2026-09-02 : seul le code 503 etait reconnu parmi les 5xx.
    # "HTTP 500" et "HTTP 502" (constates par construction du message dans
    # nexus_agent.py : "HTTP %s : %s" % (exc.code, detail)) ne correspondaient
    # a AUCUN signal ci-dessus et etaient donc classes PERMANENTS -- le
    # disjoncteur bannit alors la cible 300 s des le PREMIER echec, seuil
    # ignore -- alors qu'un 5xx generique denote par convention une panne
    # cote fournisseur, transitoire (contrat SS25 de ce depot : "5xx ->
    # panne fournisseur/serveur"). Reconnait desormais tout code HTTP 5xx.
    import re as _re
    return bool(_re.search(r"\bhttp\s*5\d{2}\b", lowered))


class CircuitBreaker:
    """Durable circuit breaker for multiple targets.

    Args:
        failure_threshold (int): number of consecutive failures to open the circuit.
        recovery_timeout (int): seconds to wait before moving from open to half_open.
    """

    def __init__(self, failure_threshold=3, recovery_timeout=300):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self._lock = RLock()
        # state is loaded lazily; keep a copy in memory for the life of the instance
        self._state = None

    def _ensure_state(self):
        """Load state from storage if not already loaded."""
        if self._state is None:
            self._state = _load_state()

    def _persist(self):
        """Persist current in‑memory state to storage."""
        _save_state(self._state)

    def _init_target(self, target):
        """Create default entry for a new target."""
        self._state[target] = {
            "fail_count": 0,
            "state": "closed",
            "last_failure": 0.0
        }

    def _transition_if_needed(self, target):
        """Handle automatic transition from open to half_open based on timeout."""
        entry = self._state[target]
        if entry["state"] == "open":
            elapsed = time.time() - entry["last_failure"]
            if elapsed >= self.recovery_timeout:
                entry["state"] = "half_open"

    def is_available(self, target):
        """Return True if the target is in a state that allows a call.

        If the circuit is open and the timeout has elapsed, the state is
        switched to half_open and the call is allowed.
        """
        with self._lock:
            self._ensure_state()
            if target not in self._state:
                self._init_target(target)
                self._persist()
                return True

            self._transition_if_needed(target)
            entry = self._state[target]
            if entry["state"] == "open":
                return False
            return True

    def record_success(self, target):
        """Record a successful call for the target.

        Resets failure count and closes the circuit.
        """
        with self._lock:
            self._ensure_state()
            if target not in self._state:
                self._init_target(target)
            entry = self._state[target]
            entry["fail_count"] = 0
            entry["state"] = "closed"
            entry["last_failure"] = 0.0
            self._persist()

    def record_failure(self, target, motif=""):
        """Record a failed call for the target.

        If a motif is provided and it is not considered transient, the circuit
        is opened immediately without consuming the normal failure threshold.
        Otherwise the original behaviour (increment counter, open on threshold)
        is preserved.
        """
        with self._lock:
            self._ensure_state()
            if target not in self._state:
                self._init_target(target)
            entry = self._state[target]

            # Immediate open for permanent failures
            if motif and not echec_transitoire(motif):
                entry["state"] = "open"
                entry["fail_count"] = self.failure_threshold
                entry["last_failure"] = time.time()
                self._persist()
                # Un echec PERMANENT ouvre le circuit immediatement : c est
                # justement celui qu il faut tracer. Sans cette ligne, le
                # journal ne portait que les transitoires.
                self._journal(target, motif, entry["fail_count"], entry["state"])
                return

            # Existing behaviour for transient or unspecified failures
            entry["fail_count"] += 1
            entry["last_failure"] = time.time()
            if entry["state"] == "half_open" or entry["fail_count"] >= self.failure_threshold:
                entry["state"] = "open"
            self._persist()
            self._journal(target, motif, entry["fail_count"], entry["state"])

    def _journal(self, target, motif, count, etat):
        """Log each retry attempt with context about why it failed.

        Prescription du livre, verbatim : Log each retry attempt with context
        about why it failed so you can identify patterns. Sans le POURQUOI,
        aucun motif recurrent ne peut etre identifie.

        Toute erreur d ecriture est ignoree : un journal ne doit JAMAIS
        empecher le disjoncteur de fonctionner.
        """
        try:
            import datetime
            if motif:
                classe = "transitoire" if echec_transitoire(motif) else "permanent"
            else:
                classe = "inconnue"
            ligne = {
                "le": datetime.datetime.now().isoformat(timespec="seconds"),
                "cible": target,
                "motif": motif or "(non fourni)",
                "classe": classe,
                "echecs": count,
                "etat": etat,
            }
            chemin = os.path.join(os.path.dirname(_state_path()),
                                  "circuit_journal.jsonl")
            with open(chemin, "a", encoding="utf-8") as f:
                f.write(json.dumps(ligne, ensure_ascii=False) + chr(10))
        except Exception:
            pass

    def get_state(self):
        """Return a copy of the full circuit state dictionary."""
        with self._lock:
            self._ensure_state()
            # Return a deep copy to avoid external mutation
            return json.loads(json.dumps(self._state))

    def reset(self):
        """Clear all circuit information."""
        with self._lock:
            self._state = {}
            self._persist()


def _print_state(cb):
    state = cb.get_state()
    if not state:
        print("No circuit information stored.")
        return
    for target, info in state.items():
        print(f"Target: {target}")
        print(f"  State       : {info['state']}")
        print(f"  Fail count  : {info['fail_count']}")
        if info['last_failure']:
            ts = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(info['last_failure']))
            print(f"  Last failure: {ts}")
        else:
            print("  Last failure: never")
        print()


def _cli():
    parser = argparse.ArgumentParser(description="Circuit breaker state viewer")
    parser.add_argument("--reset", action="store_true", help="Reset all circuit information")
    args = parser.parse_args()

    cb = CircuitBreaker()
    if args.reset:
        cb.reset()
        print("Circuit state has been reset.")
    else:
        _print_state(cb)


if __name__ == "__main__":
    _cli()