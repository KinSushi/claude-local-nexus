import contextlib
import importlib.util
import os
import sys


def _load_nexus_agent():
    # Resolve repository root from this file's location
    current_path = os.path.abspath(__file__)
    repo_root = os.path.abspath(os.path.join(current_path, os.pardir, os.pardir))
    module_path = os.path.join(repo_root, "scripts", "nexus_agent.py")
    spec = importlib.util.spec_from_file_location("nexus_agent", module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load nexus_agent from {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["nexus_agent"] = module
    spec.loader.exec_module(module)
    return module, module_path

def _run_test(requested_model):
    attempted = []

    # Load module
    module, _ = _load_nexus_agent()

    # Preserve original function
    original_appeler = getattr(module, "appeler", None)

    def fake_appeler(*args, **kwargs):
        # Assume the model name is the first positional argument or a kwarg named 'modele'
        if args:
            model_name = args[0]
        else:
            model_name = kwargs.get("modele") or kwargs.get("model") or ""
        attempted.append(str(model_name))
        # Force fallback by raising an exception
        raise RuntimeError("forced fallback")

    # Replace the function
    module.appeler = fake_appeler

    try:
        task = {
            "nom": "test_task",
            "modele": requested_model,
            "tache": "do something"
        }
        # The executer may raise; we swallow it after fallback chain finishes
        # Expected due to fake_appeler; ignore but keep attempted list
        with contextlib.suppress(Exception):
            module.executer(task, "dummy")
        if not attempted:
            raise AssertionError("no models attempted")
    finally:
        # Restore original function even if something went wrong
        if original_appeler is not None:
            module.appeler = original_appeler
        else:
            delattr(module, "appeler")
    return attempted

def _print_result(ok, name, detail):
    status = "[OK  ]" if ok else "[RATE]"
    print(f"{status} {name} : {detail}")

def main():
    exit_code = 0
    # ---------- Test 1 : local request ----------
    try:
        attempts_local = _run_test("deepseek-coder-33b-local")
        # Case 1: No cloud model attempted when local_seul absent
        case1_ok = not any(m.endswith("-cloud") for m in attempts_local)
        _print_result(case1_ok, "no_cloud_without_local_seul", ", ".join(attempts_local) or "none")
        # Case 2: Requested model appears among attempts
        case2_ok = "deepseek-coder-33b-local" in attempts_local
        _print_result(case2_ok, "requested_local_present", ", ".join(attempts_local) or "none")
        # Case 3: At least two distinct models, with at least one local
        distinct = set(attempts_local)
        case3_ok = len(distinct) >= 2 and any(m.endswith("-local") for m in distinct)
        _print_result(case3_ok, "fallback_local_available", ", ".join(attempts_local) or "none")
        if not (case1_ok and case2_ok and case3_ok):
            exit_code = 1
    except Exception as e:
        _print_result(False, "local_test_error", f"{type(e).__name__}: {e}")
        exit_code = 1

    # ---------- Test 2 : cloud request ----------
    try:
        attempts_cloud = _run_test("gpt-oss-120b-cloud")
        # Case 4: When cloud requested, at least one local alias is attempted
        case4_ok = any(m.endswith("-local") for m in attempts_cloud)
        _print_result(case4_ok, "cloud_fallback_to_local", ", ".join(attempts_cloud) or "none")
        if not case4_ok:
            exit_code = 1
    except Exception as e:
        _print_result(False, "cloud_test_error", f"{type(e).__name__}: {e}")
        exit_code = 1

    sys.exit(exit_code)

if __name__ == "__main__":
    main()