import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / 'scripts'))
import nexus_savings as ns

def _report(name, ok, detail):
    if ok:
        print("[OK  ] %s : %s" % (name, detail))
    else:
        print("[RATE] %s : %s" % (name, detail))
    return ok

def main():
    all_ok = True

    try:
        res = ns._clean_env_value('"hello world"')
        ok = res == "hello world"
        all_ok &= _report("_clean_env_value forward", ok, "got '%s'" % res)
    except Exception as e:
        all_ok &= _report("_clean_env_value forward", False, "exception %s" % e)

    try:
        ns._clean_env_value(123)
        all_ok &= _report("_clean_env_value reverse", False, "expected exception")
    except Exception:
        all_ok &= _report("_clean_env_value reverse", True, "exception raised as expected")

    try:
        res = ns._validate_base_url("https://example.com/")
        ok = res == "https://example.com"
        all_ok &= _report("_validate_base_url forward", ok, "got '%s'" % res)
    except Exception as e:
        all_ok &= _report("_validate_base_url forward", False, "exception %s" % e)

    try:
        ns._validate_base_url("ftp://example.com")
        all_ok &= _report("_validate_base_url reverse", False, "expected RuntimeError")
    except RuntimeError:
        all_ok &= _report("_validate_base_url reverse", True, "RuntimeError raised as expected")
    except Exception as e:
        all_ok &= _report("_validate_base_url reverse", False, "wrong exception %s" % e)

    domains = {"myalias": "anthropic", "other": "cloud"}
    cases = [
        ({"api_base": "https://ollama.com/api"}, "cloud"),
        ({"api_base": "http://localhost:11434"}, "local"),
        ({"api_base": "https://api.anthropic.com/v1"}, "anthropic"),
        ({"model_group": "myalias"}, "anthropic"),
        ({"model": "ollama:cloud"}, "cloud"),
        ({"model": "ollama"}, "local"),
    ]
    for i, (entry, expected) in enumerate(cases, 1):
        try:
            res = ns.domain_of(entry, domains)
            ok = res == expected
            all_ok &= _report("domain_of forward %d" % i, ok, "got '%s' expected '%s'" % (res, expected))
        except Exception as e:
            all_ok &= _report("domain_of forward %d" % i, False, "exception %s" % e)

    try:
        res = ns.domain_of({}, {})
        ok = res == "inconnu"
        all_ok &= _report("domain_of reverse unknown", ok, "got '%s'" % res)
    except Exception as e:
        all_ok &= _report("domain_of reverse unknown", False, "exception %s" % e)

    return 0 if all_ok else 1

if __name__ == '__main__':
    sys.exit(main())