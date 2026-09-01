# -*- coding: utf-8 -*-
import importlib.util
import json
import os
import sys

def main() -> int:
    # Resolve the path to the target module relative to this file, never using cwd.
    _this_dir = os.path.abspath(os.path.dirname(__file__))
    _target_path = os.path.join(_this_dir, "nexus_agent.py")
    if not os.path.isfile(_target_path):
        sys.stderr.write(f"Impossible de trouver {_target_path}\n")
        sys.exit(1)

    _spec = importlib.util.spec_from_file_location("nexus_agent", _target_path)
    if _spec is None or _spec.loader is None:
        sys.stderr.write("Échec du chargement du module.\n")
        sys.exit(1)

    nexus = importlib.util.module_from_spec(_spec)
    _sys_modules_backup = dict(sys.modules)
    sys.modules["nexus_agent"] = nexus
    try:
        _spec.loader.exec_module(nexus)  # type: ignore
    finally:
        # restore original sys.modules to avoid side‑effects
        sys.modules.clear()
        sys.modules.update(_sys_modules_backup)

    # ----------------------------------------------------------------------
    # Fake network layer that captures the request body without performing I/O.
    # ----------------------------------------------------------------------
    class _FakeResponse:
        def __init__(self, body_bytes: bytes):
            self._body = body_bytes

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self) -> bytes:
            return self._body

        def getheaders(self):
            return []


    _last_request_body = None  # will hold the raw JSON bytes sent to urlopen


    def _fake_urlopen(request, timeout=None, context=None):
        global _last_request_body
        # urllib.request.Request stores the payload in the .data attribute.
        _last_request_body = request.data
        # Return a minimal successful response.
        dummy = {
            "choices": [{"message": {"content": "ok"}}],
            "usage": {"total_tokens": 1},
        }
        return _FakeResponse(json.dumps(dummy).encode("utf-8"))


    # Patch the network call used by the imported module.
    nexus.urllib.request.urlopen = _fake_urlopen

    # ----------------------------------------------------------------------
    # Prepare a deterministic plan cache to avoid real HTTP calls.
    # ----------------------------------------------------------------------
    if hasattr(nexus.appeler, "_cache_plans"):
        del nexus.appeler._cache_plans
    nexus.appeler._cache_plans = {
        "model-local": "local",
        "model-cloud": "cloud",
        "model-anthropic": "anthropic",
        "model-unknown": "inconnu",
    }

    # ----------------------------------------------------------------------
    # Helper to invoke appeler and decode the captured JSON body.
    # ----------------------------------------------------------------------
    def _call_and_capture(model_name: str) -> dict:
        global _last_request_body
        _last_request_body = None
        # Minimal arguments required by appeler().
        nexus.appeler(
            model_name,
            [{"role": "user", "content": "test"}],
            max_tokens=42,
            cle="dummy-key",
            temperature=None,
        )
        if _last_request_body is None:
            raise RuntimeError("Aucun corps de requête capturé")
        return json.loads(_last_request_body.decode("utf-8"))


    # ----------------------------------------------------------------------
    # Test families
    # ----------------------------------------------------------------------
    cases = [
        # FORWARD – should contain num_predict, not max_tokens
        ("FORWARD", "model-local", "local"),
        ("FORWARD", "model-cloud", "cloud"),
        # REVERSE – should contain max_tokens, not num_predict
        ("REVERSE", "model-anthropic", "anthropic"),
        ("REVERSE", "model-unknown", "inconnu"),
    ]

    results = []
    all_ok = True
    overall_fuite_ok = True

    for family, model, _expected_plan in cases:
        body = _call_and_capture(model)
        has_num = "num_predict" in body
        has_max = "max_tokens" in body
        ok = False
        if family == "FORWARD":
            ok = has_num and not has_max
        elif family == "REVERSE":
            ok = has_max and not has_num
        # FUITE check – no body should ever have both fields
        fuite_ok = not (has_num and has_max)
        if not fuite_ok:
            overall_fuite_ok = False
            ok = False
        status = "OK" if ok else "RATE"
        # Format: [OK  ] NAME : DETAIL   or   [RATE] NAME : DETAIL
        formatted = f"[{status}{'  ' if status == 'OK' else ''}] {family} : {model}"
        results.append(formatted)
        if not ok:
            all_ok = False

    # Add explicit FUITE case
    fuite_status = "OK" if overall_fuite_ok else "RATE"
    fuite_formatted = f"[{fuite_status}{'  ' if fuite_status == 'OK' else ''}] FUITE : leak"
    results.append(fuite_formatted)
    if not overall_fuite_ok:
        all_ok = False

    # ----------------------------------------------------------------------
    # Output
    # ----------------------------------------------------------------------
    for line in results:
        print(line)
    total = len(results)
    passed = sum(1 for l in results if l.endswith("OK"))
    print(f"TOTAL {passed}/{total}")

    return 0 if all_ok else 1

if __name__ == "__main__":
    sys.exit(main())