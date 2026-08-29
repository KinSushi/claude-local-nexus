# -*- coding: utf-8 -*-
"""
Le local prend-il réellement le relais ?

Pourquoi ce script existe
-------------------------
La promesse de la plateforme n'est pas « des modèles locaux existent ».
Elle est : *le jour où l'abonnement expire ou son quota est épuisé, le
travail continue*. Ces deux affirmations sont très différentes, et seule
la seconde a de la valeur.

Un modèle qui répond à une question n'orchestre rien. Orchestrer suppose
quatre choses, et l'échec d'une seule suffit à ruiner la relève :

    1. parler le protocole      /v1/messages, l'API que Claude Code emploie
    2. demander un outil        stop_reason = tool_use, nom et arguments justes
    3. exploiter le retour      lire un tool_result et en tirer une conclusion
    4. enchaîner                plusieurs outils d'affilée sans perdre le fil

Chacune est vérifiée séparément, sur le modèle réellement déclaré comme
relève, en conditions réelles. Aucune n'est déduite d'une autre : un
modèle peut parfaitement émettre un `tool_use` bien formé puis ignorer le
résultat qu'on lui renvoie.

Le test échoue bruyamment plutôt que d'accorder le bénéfice du doute. Une
relève dont on croit à tort qu'elle fonctionne est pire qu'une relève
absente : on ne s'aperçoit de rien jusqu'au jour où l'on en a besoin.

Usage :
    python scripts/nexus_releve.py                     # modèle de relève déclaré
    python scripts/nexus_releve.py --modele <alias>    # un autre candidat
    python scripts/nexus_releve.py --tous              # tous les candidats locaux
    python scripts/nexus_releve.py --json
"""
from __future__ import annotations

import argparse
import io
import json
import os
import sys
import time
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nexus_agent as agent  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = agent.ROOT
PASSERELLE = agent.PASSERELLE

# L'alias que la configuration désigne comme relève. Il est interrogé par
# son nom logique, jamais par le modèle sous-jacent : c'est ce nom que
# Claude Code recevra, et donc ce nom qu'il faut éprouver.
RELEVE = "releve-locale"

# Un modèle non chargé met une à deux minutes à répondre au premier appel,
# et la relève est justement le modèle qui ne tourne pas d'habitude.
DELAI = int(os.environ.get("NEXUS_RELEVE_TIMEOUT", "900"))

OUTIL_LIRE = {
    "name": "lire_fichier",
    "description": "Lit un fichier du depot et rend son contenu.",
    "input_schema": {
        "type": "object",
        "properties": {"chemin": {"type": "string", "description": "Chemin relatif au depot."}},
        "required": ["chemin"],
    },
}

OUTIL_COMPTER = {
    "name": "compter_lignes",
    "description": "Compte les lignes d'un fichier du depot.",
    "input_schema": {
        "type": "object",
        "properties": {"chemin": {"type": "string"}},
        "required": ["chemin"],
    },
}


def messages(charge: dict, cle: str) -> dict:
    """
    Un appel à /v1/messages, l'API Anthropic servie par LiteLLM.

    C'est volontairement le même chemin que celui qu'emprunterait Claude
    Code configuré sur la passerelle. Tester /v1/chat/completions à la
    place mesurerait un protocole que la relève n'utilisera jamais.
    """
    requete = urllib.request.Request(
        PASSERELLE + "/v1/messages",
        data=json.dumps(charge).encode("utf-8"),
        headers={
            "x-api-key": cle,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    debut = time.time()
    try:
        with urllib.request.urlopen(requete, timeout=DELAI) as reponse:
            corps = json.loads(reponse.read().decode("utf-8"))
            entetes = {k.lower(): v for k, v in reponse.getheaders()}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:400]
        return {"echec": "HTTP %s : %s" % (exc.code, detail),
                "duree": time.time() - debut}
    except Exception as exc:
        return {"echec": str(exc), "duree": time.time() - debut}
    corps["_duree"] = time.time() - debut
    corps["_adresse"] = entetes.get("x-litellm-model-api-base", "?")
    corps["_servi"] = entetes.get("x-litellm-model-name", "?")
    return corps


def blocs(reponse: dict, genre: str) -> list[dict]:
    return [b for b in (reponse.get("content") or []) if b.get("type") == genre]


def texte_de(reponse: dict) -> str:
    return " ".join((b.get("text") or "") for b in blocs(reponse, "text")).strip()


# ----------------------------------------------------------------------
# Les quatre épreuves
# ----------------------------------------------------------------------
def epreuve_protocole(modele: str, cle: str) -> dict:
    """Le modèle répond-il par l'API que Claude Code emploie ?"""
    jeton = "RLV%d" % (int(time.time()) % 10000)
    r = messages({
        "model": modele,
        "max_tokens": 32,
        "messages": [{"role": "user",
                      "content": "Repete ce mot et rien d'autre : %s" % jeton}],
    }, cle)
    if r.get("echec"):
        return {"ok": False, "detail": r["echec"], "duree": r.get("duree", 0)}
    corps = texte_de(r)
    return {
        "ok": jeton in corps,
        "detail": corps[:120] if jeton in corps else "jeton absent : %r" % corps[:120],
        "duree": r.get("_duree", 0),
        "adresse": r.get("_adresse"),
        "servi": r.get("_servi"),
    }


def epreuve_demande_outil(modele: str, cle: str) -> dict:
    """Le modèle demande-t-il l'outil, avec le bon nom et le bon argument ?"""
    r = messages({
        "model": modele,
        "max_tokens": 400,
        "tools": [OUTIL_LIRE],
        "messages": [{"role": "user",
                      "content": "Quelle est la premiere ligne de README.md ? "
                                 "Utilise l'outil pour le lire."}],
    }, cle)
    if r.get("echec"):
        return {"ok": False, "detail": r["echec"], "duree": r.get("duree", 0)}
    appels = blocs(r, "tool_use")
    if not appels:
        return {"ok": False, "duree": r.get("_duree", 0),
                "detail": "aucun tool_use (stop_reason=%s) : %r"
                          % (r.get("stop_reason"), texte_de(r)[:120])}
    appel = appels[0]
    chemin = str((appel.get("input") or {}).get("chemin", ""))
    juste = appel.get("name") == "lire_fichier" and "README" in chemin.upper()
    return {
        "ok": juste,
        "duree": r.get("_duree", 0),
        "detail": "%s(%s)" % (appel.get("name"), json.dumps(appel.get("input"), ensure_ascii=False)),
        "appel": appel,
    }


def epreuve_exploite_retour(modele: str, cle: str, appel: dict | None) -> dict:
    """
    Le modèle sait-il tirer une conclusion du résultat qu'on lui renvoie ?

    L'épreuve est distincte de la précédente à dessein : émettre un
    `tool_use` bien formé et exploiter un `tool_result` sont deux
    aptitudes séparées, et un modèle peut posséder la première sans la
    seconde. Les confondre ferait conclure à une relève opérationnelle sur
    la foi d'une demande d'outil restée sans suite.
    """
    if appel is None:
        return {"ok": False, "detail": "epreuve precedente echouee, rien a enchainer",
                "duree": 0}
    try:
        premiere = io.open(os.path.join(ROOT, "README.md"),
                           encoding="utf-8").readline().strip()
    except Exception as exc:
        return {"ok": False, "detail": "README.md illisible : %s" % exc, "duree": 0}

    r = messages({
        "model": modele,
        "max_tokens": 300,
        "tools": [OUTIL_LIRE],
        "messages": [
            {"role": "user",
             "content": "Quelle est la premiere ligne de README.md ? "
                        "Utilise l'outil pour le lire."},
            {"role": "assistant", "content": [appel]},
            {"role": "user", "content": [{
                "type": "tool_result",
                "tool_use_id": appel.get("id", "toolu_01"),
                "content": premiere + "\n\n(suite du fichier omise)",
            }]},
        ],
    }, cle)
    if r.get("echec"):
        return {"ok": False, "detail": r["echec"], "duree": r.get("duree", 0)}
    corps = texte_de(r)
    # La comparaison porte sur le contenu de la ligne, pas sur une reprise
    # mot pour mot : un modèle qui répond « le titre est Claude-Local-Nexus »
    # a parfaitement exploité le résultat.
    noyau = premiere.lstrip("# ").strip()
    return {
        "ok": bool(noyau) and noyau.lower() in corps.lower(),
        "duree": r.get("_duree", 0),
        "detail": corps[:160] if corps else "reponse vide",
        "attendu": noyau,
    }


def epreuve_enchainement(modele: str, cle: str) -> dict:
    """
    Deux outils d'affilée : le modèle choisit-il le bon à chaque étape ?

    Un orchestrateur ne fait presque jamais un seul appel. S'il choisit
    toujours le premier outil de la liste, ou s'il perd le fil après un
    résultat, il enchaînera des actions qui n'ont plus de rapport avec la
    tâche — panne bien plus coûteuse qu'un refus franc.
    """
    depart = time.time()
    r1 = messages({
        "model": modele,
        "max_tokens": 400,
        "tools": [OUTIL_LIRE, OUTIL_COMPTER],
        "messages": [{"role": "user",
                      "content": "Combien de lignes contient README.md ? "
                                 "Choisis l'outil approprie."}],
    }, cle)
    if r1.get("echec"):
        return {"ok": False, "detail": r1["echec"], "duree": time.time() - depart}
    appels = blocs(r1, "tool_use")
    if not appels:
        return {"ok": False, "duree": time.time() - depart,
                "detail": "aucun tool_use au premier tour"}
    if appels[0].get("name") != "compter_lignes":
        return {"ok": False, "duree": time.time() - depart,
                "detail": "mauvais outil choisi : %s au lieu de compter_lignes"
                          % appels[0].get("name")}

    nb = sum(1 for _ in io.open(os.path.join(ROOT, "README.md"), encoding="utf-8"))
    r2 = messages({
        "model": modele,
        "max_tokens": 200,
        "tools": [OUTIL_LIRE, OUTIL_COMPTER],
        "messages": [
            {"role": "user", "content": "Combien de lignes contient README.md ? "
                                        "Choisis l'outil approprie."},
            {"role": "assistant", "content": [appels[0]]},
            {"role": "user", "content": [{
                "type": "tool_result",
                "tool_use_id": appels[0].get("id", "toolu_01"),
                "content": str(nb),
            }]},
        ],
    }, cle)
    if r2.get("echec"):
        return {"ok": False, "detail": r2["echec"], "duree": time.time() - depart}
    corps = texte_de(r2)
    return {
        "ok": str(nb) in corps,
        "duree": time.time() - depart,
        "detail": corps[:160] if corps else "reponse vide",
        "attendu": str(nb),
    }


EPREUVES = [
    ("parle le protocole /v1/messages", epreuve_protocole),
    ("demande un outil",                epreuve_demande_outil),
    ("exploite le resultat d'outil",    epreuve_exploite_retour),
    ("enchaine deux outils",            epreuve_enchainement),
]


def juger(modele: str, cle: str) -> dict:
    print("=" * 72)
    print("  Releve : %s" % modele)
    print("=" * 72)
    resultats, appel, adresse, servi = [], None, "?", "?"
    for i, (titre, fonction) in enumerate(EPREUVES, 1):
        if fonction is epreuve_exploite_retour:
            r = fonction(modele, cle, appel)
        else:
            r = fonction(modele, cle)
        if fonction is epreuve_demande_outil:
            appel = r.get("appel")
        if r.get("adresse"):
            adresse, servi = r["adresse"], r.get("servi", "?")
        etat = "OK  " if r["ok"] else "ECHEC"
        print("  [%s] %d/4 %-34s %5.0f s" % (etat, i, titre, r.get("duree", 0)))
        if not r["ok"] or os.environ.get("NEXUS_VERBEUX"):
            print("         %s" % str(r.get("detail", ""))[:200])
        resultats.append({"epreuve": titre, **{k: v for k, v in r.items() if k != "appel"}})

    reussies = sum(1 for r in resultats if r["ok"])
    # Le plan vient du catalogue, pas de l'en-tete : /v1/messages ne pose
    # pas x-litellm-model-api-base, et en deduire "inconnu" ferait conclure
    # que la releve n'est pas locale alors qu'elle l'est. Le catalogue,
    # lui, decrit ou l'alias enverra ses requetes, quel que soit le
    # protocole employe pour l'appeler.
    plan = agent.plans_par_alias(cle).get(modele) or agent.plan_de(adresse)
    print()
    print("  servi par : %s [%s]%s" % (servi, plan, "" if adresse == "?" else " " + adresse))
    if plan != "local":
        # Une relève servie par le cloud ou par Anthropic ne relève de
        # rien : elle dépend précisément de ce dont on cherche à se rendre
        # indépendant.
        print("  [!] La releve n'a PAS ete servie en local : le test ne prouve rien")
        print("      sur l'autonomie de la machine.")
    print("  %d/4 epreuves reussies" % reussies)
    if reussies == 4:
        print("  => La releve peut orchestrer : outils demandes, resultats exploites,")
        print("     enchainement tenu.")
    elif reussies >= 2:
        print("  => La releve repond mais n'orchestre pas de bout en bout.")
        print("     Elle peut servir de repondeur, pas de remplacant.")
    else:
        print("  => La releve ne tient pas. Le travail s'arreterait avec l'abonnement.")
    print()
    return {"modele": modele, "reussies": reussies, "plan": plan,
            "adresse": adresse, "epreuves": resultats}


def candidats_locaux(cle: str) -> list[str]:
    """Alias locaux exposés, hors embeddings et hors modèles de vision."""
    requete = urllib.request.Request(
        PASSERELLE + "/v1/model/info", headers={"Authorization": "Bearer " + cle})
    with urllib.request.urlopen(requete, timeout=30) as reponse:
        donnees = json.loads(reponse.read().decode("utf-8")).get("data", [])
    noms = []
    for entree in donnees:
        nom = entree.get("model_name", "")
        params = entree.get("litellm_params") or {}
        cible = str(params.get("model", ""))
        if not cible.startswith("ollama"):
            continue
        if "ollama.com" in str(params.get("api_base", "")):
            continue
        if any(m in nom for m in ("embed", "minilm", "llava", "-vl-", "vision")):
            continue
        noms.append(nom)
    return sorted(set(noms))


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--modele", help="Alias a eprouver. Defaut : " + RELEVE)
    p.add_argument("--tous", action="store_true",
                   help="Eprouver tous les candidats locaux (long).")
    p.add_argument("--json", action="store_true")
    a = p.parse_args()

    cle = agent.cle_maitre()
    if a.tous:
        cibles = candidats_locaux(cle)
    else:
        cibles = [a.modele or RELEVE]

    rapports = [juger(m, cle) for m in cibles]

    if a.json:
        print(json.dumps(rapports, ensure_ascii=False, indent=2))

    aptes = [r for r in rapports if r["reussies"] == 4 and r["plan"] == "local"]
    if len(cibles) > 1:
        print("=" * 72)
        print("  Candidats aptes a orchestrer : %d sur %d" % (len(aptes), len(cibles)))
        for r in sorted(rapports, key=lambda r: -r["reussies"]):
            print("    %-32s %d/4" % (r["modele"], r["reussies"]))
        print("=" * 72)
    # Code 1 dès qu'aucune cible n'est apte : ce test sert de garde-fou,
    # pas d'information.
    return 0 if aptes else 1


if __name__ == "__main__":
    sys.exit(main())
