import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))
import nexus_agent

def check(name, condition, detail=""):
    if condition:
        print("[OK] %s" % name)
        return True
    print("[RATE] %s : %s" % (name, detail))
    return False

def main():
    ok = True

    result = nexus_agent.identifiant_lot(1234, 1757800000.123)
    expected = "1234-1757800000"
    ok &= check("forme", result == expected, "attendu %s, obtenu %s" % (expected, result))

    result = nexus_agent.identifiant_lot(5678, 1757800001.999)
    expected = "5678-1757800001"
    ok &= check("troncature", result == expected, "attendu %s, obtenu %s" % (expected, result))

    id1 = nexus_agent.identifiant_lot(1111, 1757800000.0)
    id2 = nexus_agent.identifiant_lot(2222, 1757800000.0)
    ok &= check("pids differents a meme epoch", id1 != id2, "identifiants identiques: %s" % id1)

    sys.exit(0 if ok else 1)

if __name__ == "__main__":
    main()
