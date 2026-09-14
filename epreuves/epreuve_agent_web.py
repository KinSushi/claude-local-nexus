import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))
import nexus_agent
from unittest import mock


def cas_forward():
    tache = {}
    messages = [{"role": "user", "content": "q"}]
    premier = {
        "texte": "",
        "tool_calls": [{"id": "c1", "type": "function", "function": {"name": "web_search", "arguments": "{\"query\": \"q\"}"}}],
        "adresse": "https://ollama.com",
        "servi_par": "x",
        "tokens": 1,
        "tronque": False
    }
    second = {
        "texte": "Reponse.",
        "tool_calls": [],
        "adresse": "https://ollama.com",
        "servi_par": "x",
        "tokens": 1,
        "tronque": False
    }
    with mock.patch.object(nexus_agent, "cle_ollama", return_value="x"), \
         mock.patch.object(nexus_agent, "appeler", side_effect=[premier, second]), \
         mock.patch.object(nexus_agent, "appel_web", return_value={"results": [{"title": "t", "url": "https://exemple.org/a", "content": "c"}]}) as faux_web:
        final = nexus_agent.executer_web(tache, "cle", "modele", messages, 100, 0.2, "nom", [], [], False)
        ok = "source : https://exemple.org/a" in final["texte"] and final["web"]["recherches"] == 1 and faux_web.call_count == 1 and any(m.get("role") == "tool" for m in messages) and final["plan"] == "cloud"
        return ok, "forward"


def cas_reverse():
    tache = {}
    messages = [{"role": "user", "content": "q"}]
    with mock.patch.object(nexus_agent, "cle_ollama", side_effect=SystemExit("OLLAMA_CLOUD_API_KEY introuvable")), \
         mock.patch.object(nexus_agent, "appeler") as faux_appeler, \
         mock.patch.object(nexus_agent, "appel_web") as faux_web:
        resultat = nexus_agent.executer_web(tache, "cle", "modele", messages, 100, 0.2, "nom", [], [], False)
        ok = resultat["code"] == 2 and "OLLAMA_CLOUD_API_KEY" in resultat["erreur"] and not faux_appeler.called and not faux_web.called
        return ok, "reverse"


def cas_fuite_sans_consentement():
    tache = {}
    messages = [{"role": "user", "content": "q"}]
    with mock.patch.object(nexus_agent, "cle_ollama", return_value="x"), \
         mock.patch.object(nexus_agent, "appeler") as faux_appeler, \
         mock.patch.object(nexus_agent, "appel_web") as faux_web:
        resultat = nexus_agent.executer_web(tache, "cle", "x-local", messages, 100, 0.2, "nom", [], [], False)
        ok = resultat["code"] == 2 and "--web-consenti" in resultat["erreur"] and not faux_appeler.called and not faux_web.called
        return ok, "fuite sans consentement"


def cas_fuite_avec_consentement():
    tache = {}
    messages = [{"role": "user", "content": "q"}]
    second = {
        "texte": "Reponse.",
        "tool_calls": [],
        "adresse": "https://ollama.com",
        "servi_par": "x",
        "tokens": 1,
        "tronque": False
    }
    with mock.patch.object(nexus_agent, "cle_ollama", return_value="x"), \
         mock.patch.object(nexus_agent, "appeler", return_value=second) as faux_appeler, \
         mock.patch.object(nexus_agent, "appel_web") as faux_web:
        nexus_agent.executer_web(tache, "cle", "x-local", messages, 100, 0.2, "nom", [], [], True)
        ok = faux_appeler.call_count == 1 and not faux_web.called
        return ok, "fuite avec consentement"


def main():
    cas = [cas_forward, cas_reverse, cas_fuite_sans_consentement, cas_fuite_avec_consentement]
    code = 0
    for c in cas:
        ok, cause = c()
        if ok:
            print("[OK] " + cause)
        else:
            print("[RATE] " + cause)
            code = 1
    sys.exit(code)


if __name__ == "__main__":
    main()
