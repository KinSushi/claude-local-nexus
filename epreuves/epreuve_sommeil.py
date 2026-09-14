import os
import sys

# Insert the scripts directory in the path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))
try:
    from nexus_generate import mettre_en_sommeil
except Exception as e:
    print("[RATE] import : %s" % e)
    sys.exit(1)

# ----------------------------------------------------------------------
# Fixture used for all tests
FIXTURE = """model_list:

  - model_name: claude-x
    litellm_params:
      model: anthropic/claude-x
      api_key: os.environ/ANTHROPIC_API_KEY
    model_info:
      description: "anthropic"

  - model_name: installe-local
    litellm_params:
      model: ollama_chat/installe:8b
      api_base: http://host.docker.internal:11434
    model_info:
      description: "installe"

  - model_name: absent-local
    litellm_params:
      model: ollama_chat/absent:14b
      api_base: http://host.docker.internal:11434
    model_info:
      description: "absent"

  # >>> AUTOGEN:LOCAL_MODELS_EXTRA
  - model_name: absent-autogen-local
    litellm_params:
      model: ollama_chat/absent:14b
      api_base: http://host.docker.internal:11434
  # <<< AUTOGEN:LOCAL_MODELS_EXTRA

  - model_name: absent-cloud
    litellm_params:
      model: ollama_chat/absent:14b
      api_base: https://ollama.com
    model_info:
      description: "cloud"

  - model_name: codestral-local
    litellm_params:
      model: ollama_chat/codestral
      api_base: http://host.docker.internal:11434
    model_info:
      description: "sans tag"

router_settings:
  x: 1

litellm_settings:
  fallbacks:
    - installe-local:
        - absent-local
        - codestral-local
    - absent-local:
        - installe-local
"""

# ----------------------------------------------------------------------
# Helper functions

def _strip_prefix(line):
    """Remove a leading '#~ ' if present."""
    if line.startswith("#~ "):
        return line[3:]
    return line

def bloc(texte, alias):
    """
    Return the list of lines that belong to the block whose first
    (unprefixed) line is exactly '  - model_name: <alias>'.
    The returned lines are taken exactly as they appear in texte.
    """
    lines = texte.splitlines()
    start = None
    for i, line in enumerate(lines):
        if _strip_prefix(line) == "  - model_name: %s" % alias:
            start = i
            break
    if start is None:
        return []
    block = []
    for j in range(start, len(lines)):
        cur = lines[j]
        stripped = _strip_prefix(cur)
        # Stop condition: next line that starts a new block or AUTOGEN marker
        if j != start:
            if stripped.startswith("  - model_name: "):
                break
            if "AUTOGEN:" in stripped:
                break
            if stripped.lstrip().startswith("# DORMANT depuis"):
                break
            if stripped and not stripped.startswith(" ") and not cur.startswith("#~ "):
                break
        block.append(cur)
    return block

def est_endormi(texte, alias):
    """Return True if the block exists and every line starts with '#~ '."""
    b = bloc(texte, alias)
    if not b:
        return False
    return all(line.startswith("#~ ") for line in b)

def est_intact(texte, alias, original):
    """Return True if the block for alias is identical in texte and original."""
    return bloc(texte, alias) == bloc(original, alias)

def _autogen_zone(text):
    """Extract the AUTOGEN zone (including markers) from text."""
    lines = text.splitlines()
    start = end = None
    for i, line in enumerate(lines):
        if line.strip() == "# >>> AUTOGEN:LOCAL_MODELS_EXTRA":
            start = i
        if line.strip() == "# <<< AUTOGEN:LOCAL_MODELS_EXTRA":
            end = i
            break
    if start is not None and end is not None:
        return "\n".join(lines[start:end+1]) + "\n"
    return ""

# ----------------------------------------------------------------------
# Verification helpers for the test cases

def verifie_forward(fn):
    """
    Apply the forward logic (case 1) using the supplied function fn.
    Return True if all expectations are met, False otherwise.
    """
    texte, endormis, reveilles = fn(FIXTURE, {"installe:8b", "codestral:latest"})
    if endormis != ["absent-local"]:
        return False
    if reveilles:
        return False
    if not est_endormi(texte, "absent-local"):
        return False
    # Find the first line of the block
    lines = texte.splitlines()
    idx = None
    for i, line in enumerate(lines):
        if line.startswith("#~   - model_name: absent-local"):
            idx = i
            break
    if idx is None or idx == 0:
        return False
    prev = lines[idx-1]
    return "DORMANT depuis" in prev and "absent:14b" in prev

# ----------------------------------------------------------------------
# Test cases

failures = 0
texte_fwd = None

# 1. forward
try:
    texte_fwd, endormis_fwd, reveilles_fwd = mettre_en_sommeil(FIXTURE, {"installe:8b", "codestral:latest"})
    ok = True
    if endormis_fwd != ["absent-local"]:
        ok = False
    if reveilles_fwd:
        ok = False
    if not est_endormi(texte_fwd, "absent-local"):
        ok = False
    # locate block start
    lines = texte_fwd.splitlines()
    idx = None
    for i, line in enumerate(lines):
        if line.startswith("#~   - model_name: absent-local"):
            idx = i
            break
    if idx is None or idx == 0:
        ok = False
    else:
        prev = lines[idx-1]
        if "DORMANT depuis" not in prev or "absent:14b" not in prev:
            ok = False
    if ok:
        print("[OK  ] forward : passed")
    else:
        print("[RATE] forward : failed")
        failures += 1
except Exception as e:
    print("[RATE] forward : exception %s" % e)
    failures += 1

# 2. intact
try:
    if texte_fwd is None:
        print("[RATE] intact : cas 1 non rendu")
        failures += 1
    else:
        intact_ok = True
        for alias in ["claude-x", "installe-local", "absent-autogen-local", "absent-cloud", "codestral-local"]:
            if not est_intact(texte_fwd, alias, FIXTURE):
                intact_ok = False
                break
        # AUTOGEN zone
        autogen_original = _autogen_zone(FIXTURE)
        autogen_current = _autogen_zone(texte_fwd)
        if autogen_original != autogen_current:
            intact_ok = False
        if "router_settings:" not in texte_fwd:
            intact_ok = False
        if intact_ok:
            print("[OK  ] intact : passed")
        else:
            print("[RATE] intact : failed")
            failures += 1
except Exception as e:
    print("[RATE] intact : exception %s" % e)
    failures += 1

# 3. idempotence
try:
    texte_idem, endormis_idem, reveilles_idem = mettre_en_sommeil(texte_fwd, {"installe:8b", "codestral:latest"})
    if texte_idem == texte_fwd and not endormis_idem and not reveilles_idem:
        print("[OK  ] idempotence : passed")
    else:
        print("[RATE] idempotence : failed")
        failures += 1
except Exception as e:
    print("[RATE] idempotence : exception %s" % e)
    failures += 1

# 4. reveil
try:
    texte_rev, endormis_rev, reveilles_rev = mettre_en_sommeil(texte_fwd, {"installe:8b", "codestral:latest", "absent:14b"})
    if texte_rev == FIXTURE and reveilles_rev == ["absent-local"] and not endormis_rev:
        print("[OK  ] reveil : passed")
    else:
        print("[RATE] reveil : failed")
        failures += 1
except Exception as e:
    print("[RATE] reveil : exception %s" % e)
    failures += 1

# 5. latest
try:
    texte_latest, endormis_latest, reveilles_latest = mettre_en_sommeil(FIXTURE, {"installe:8b", "codestral:latest"})
    if "codestral-local" not in endormis_latest and est_intact(texte_latest, "codestral-local", FIXTURE):
        print("[OK  ] latest : passed")
    else:
        print("[RATE] latest : failed")
        failures += 1
except Exception as e:
    print("[RATE] latest : exception %s" % e)
    failures += 1

# 7. repli
try:
    texte_repli, endormis_repli, reveilles_repli = mettre_en_sommeil(FIXTURE, {"installe:8b", "codestral:latest"})
    src_prefixed = any(l.startswith("#~     - absent-local:") for l in texte_repli.splitlines())
    item_prefixed = any(l.startswith("#~         - installe-local") for l in texte_repli.splitlines())
    absent_item_prefixed = any(l.startswith("#~         - absent-local") for l in texte_repli.splitlines())
    codestral_intact = any(l == "        - codestral-local" for l in texte_repli.splitlines())
    if src_prefixed and item_prefixed and absent_item_prefixed and codestral_intact:
        print("[OK  ] repli : passed")
    else:
        print("[RATE] repli : failed")
        failures += 1
except Exception as e:
    print("[RATE] repli : exception %s" % e)
    failures += 1

# 8. repli-reveil
try:
    texte_rev2, endormis_rev2, reveilles_rev2 = mettre_en_sommeil(texte_repli, {"installe:8b", "codestral:latest", "absent:14b"})
    if texte_rev2 == FIXTURE and reveilles_rev2 == ["absent-local"] and not endormis_rev2:
        print("[OK  ] repli-reveil : passed")
    else:
        print("[RATE] repli-reveil : failed")
        failures += 1
except Exception as e:
    print("[RATE] repli-reveil : exception %s" % e)
    failures += 1

# 6. detection
try:
    detection_ok = verifie_forward(lambda raw, inst: (raw, [], []))
    if not detection_ok:
        print("[OK  ] detection : passed")
    else:
        print("[RATE] detection : failed")
        failures += 1
except Exception as e:
    print("[RATE] detection : exception %s" % e)
    failures += 1

# Exit with appropriate code
sys.exit(1 if failures else 0)
