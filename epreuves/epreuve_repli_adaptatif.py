import sys
import json
import shutil
import tempfile
from pathlib import Path

# Setup import path for the agent module
RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / 'scripts'))
import nexus_agent as agent

def _write_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8') as f:
        json.dump(data, f)

def _run_case(name, func):
    try:
        ok, detail = func()
    except Exception as e:  # safety net, should not happen
        ok, detail = False, f"exception {e}"
    prefix = "[OK  ]" if ok else "[RATE]"
    print(f"{prefix} {name} : {detail}")
    return ok

def case_forward_cloud_first():
    original_root = agent.ROOT
    original_plans = agent.plans_par_alias
    temp_dir = tempfile.mkdtemp()
    try:
        # Prepare fake .nexus files
        nexus_dir = Path(temp_dir) / '.nexus'
        _write_json(nexus_dir / 'epreuves.json',
                    {"modeles": {"zz-cloud": {"complet": True},
                                 "aa-local": {"complet": True}}})
        _write_json(nexus_dir / 'latences.json',
                    {"modeles": {}})

        # Monkey-patch
        agent.ROOT = Path(temp_dir)
        agent.plans_par_alias = lambda cle: {"zz-cloud": "cloud", "aa-local": "local"}

        # Call function under test
        r = agent.replis_gratuits("x")
        # Verify order
        try:
            cloud_idx = r.index("zz-cloud")
            local_idx = r.index("aa-local")
            ok = cloud_idx < local_idx
            detail = "cloud precedes local" if ok else "cloud does not precede local"
        except ValueError as ve:
            ok = False
            detail = f"missing alias: {ve}"
        return ok, detail
    finally:
        # Restore originals and clean tempdir
        agent.ROOT = original_root
        agent.plans_par_alias = original_plans
        shutil.rmtree(temp_dir, ignore_errors=True)

def case_fuite_exclusion():
    original_root = agent.ROOT
    original_plans = agent.plans_par_alias
    temp_dir = tempfile.mkdtemp()
    try:
        nexus_dir = Path(temp_dir) / '.nexus'
        _write_json(nexus_dir / 'epreuves.json',
                    {"modeles": {"zz-cloud": {"complet": True},
                                 "aa-local": {"complet": True},
                                 "pp-paid": {"complet": True}}})
        _write_json(nexus_dir / 'latences.json',
                    {"modeles": {}})

        agent.ROOT = Path(temp_dir)
        agent.plans_par_alias = lambda cle: {"zz-cloud": "cloud",
                                             "aa-local": "local",
                                             "pp-paid": "anthropic"}

        r = agent.replis_gratuits("x")
        # Exclusion checks
        contains_paid = "pp-paid" in r
        contains_forbidden = any('claude' in alias.lower() or 'anthropic' in alias.lower()
                                 for alias in r)
        ok = not contains_paid and not contains_forbidden
        detail = ("excluded paid and forbidden" if ok
                  else "paid present or forbidden found")
        return ok, detail
    finally:
        agent.ROOT = original_root
        agent.plans_par_alias = original_plans
        shutil.rmtree(temp_dir, ignore_errors=True)

def case_garde_aucun_cloud():
    original_root = agent.ROOT
    original_plans = agent.plans_par_alias
    temp_dir = tempfile.mkdtemp()
    try:
        nexus_dir = Path(temp_dir) / '.nexus'
        _write_json(nexus_dir / 'epreuves.json',
                    {"modeles": {"aa-local": {"complet": True}}})
        _write_json(nexus_dir / 'latences.json',
                    {"modeles": {}})

        agent.ROOT = Path(temp_dir)
        agent.plans_par_alias = lambda cle: {"aa-local": "local"}

        r = agent.replis_gratuits("x")
        ok = r == agent.REPLIS_GRATUITS_PLANCHER
        detail = "returned plancer" if ok else "unexpected result"
        return ok, detail
    finally:
        agent.ROOT = original_root
        agent.plans_par_alias = original_plans
        shutil.rmtree(temp_dir, ignore_errors=True)

def case_reverse_degradation():
    original_root = agent.ROOT
    original_plans = agent.plans_par_alias
    temp_dir = tempfile.mkdtemp()
    try:
        # No need to write files; the function will fail before reading them
        agent.ROOT = Path(temp_dir)
        def bad_plans(cle):
            raise Exception('boom')
        agent.plans_par_alias = bad_plans

        r = agent.replis_gratuits("x")
        ok = r == agent.REPLIS_GRATUITS_PLANCHER
        detail = "graceful degradation" if ok else "did not fallback"
        return ok, detail
    finally:
        agent.ROOT = original_root
        agent.plans_par_alias = original_plans
        shutil.rmtree(temp_dir, ignore_errors=True)

def main():
    successes = []
    successes.append(_run_case("FORWARD cloud-first", case_forward_cloud_first))
    successes.append(_run_case("FUITE exclusion", case_fuite_exclusion))
    successes.append(_run_case("GARDE aucun cloud", case_garde_aucun_cloud))
    successes.append(_run_case("REVERSE degradation", case_reverse_degradation))
    all_ok = all(successes)
    sys.exit(0 if all_ok else 1)

if __name__ == "__main__":
    main()