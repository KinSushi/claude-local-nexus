import sys
import os
import inspect

# Ensure the scripts directory is in the import path
script_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'scripts'))
sys.path.insert(0, script_dir)

import nexus_agent

def main() -> int:
    # Test 1: constant is at least 8
    if getattr(nexus_agent, 'PLAFOND_INFERENCE_CLOUD', 0) < 8:
        print("[RATE] PLAFOND_INFERENCE_CLOUD trop bas")
        return 1
    print("[OK] PLAFOND_INFERENCE_CLOUD >= 8")

    # Test 2: source contains the expected string
    source = inspect.getsource(nexus_agent)
    expected = "NEXUS_SEMAPHORE_INFERENCE_N', PLAFOND_INFERENCE_CLOUD"
    if expected not in source:
        print("[RATE] la variable d'environnement ne prend plus le plafond en defaut")
        return 1
    print("[OK] NEXUS_SEMAPHORE_INFERENCE_N reste prioritaire, defaut = PLAFOND_INFERENCE_CLOUD")
    return 0

if __name__ == "__main__":
    sys.exit(main())
