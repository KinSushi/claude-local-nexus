# -*- coding: utf-8 -*-
"""
Le local prend‑il réellement le relais ?

Pourquoi ce script existe
-------------------------
La promesse de la plateforme n’est pas « des modèles locaux existent ».
Elle est : *le jour où l’abonnement expire ou son quota est épuisé, le
travail continue*. Ces deux affirmations sont très différentes, et seule
la seconde a de la valeur.

Un modèle qui répond à une question n’orchestre rien. Orchestrer suppose
quatre choses, et l’échec d’une seule suffit à ruiner la relève :

    1. parler le protocole      /v1/messages, l’API que Claude Code emploie
    2. demander un outil        stop_reason = tool_use, nom et arguments justes
    3. exploiter le retour      lire un tool_result et en tirer une conclusion
    4. enchaîner                plusieurs outils d’affilée sans perdre le fil

Chacune est vérifiée séparément, sur le modèle réellement déclaré comme
relève, en conditions réelles. Aucune n’est déduite d’une autre : un
modèle peut parfaitement émettre un `tool_use` bien formé puis ignorer le
résultat qu’on lui renvoie.

Le test échoue bruyamment plutôt que d’accorder le bénéfice du doute. Une
relève dont on croit à tort qu’elle fonctionne est pire qu’une relève
absente : on ne s’aperçoit de rien jusqu’au jour où l’on en a besoin.

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
# son nom logique, jamais par le modèle sous‑jacent : c’est ce nom que
# Claude Code recevra, et donc ce nom qu’il faut éprouver.
RELEVE = "releve-locale"

# Un modèle non chargé met une à deux minutes à répondre au premier appel,
# et la relève est justement le modèle qui ne tourne pas d’habitude.
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


def _now() -> float:
    """Retourne le temps monotone, utilisable pour mesurer des durées."""
    return time.monotonic()


def messages(charge: dict, cle: str) -> dict:
    """
    Un appel à /v1/messages, l'API Anthropic servie par LiteLLM.

    C’est volontairement le même chemin que celui qu’emprunterait Claude
    Code configuré sur la passerelle. Tester /v1/chat/completions à la
    place mesurerait un protocole que la relève n’utilisera jamais.
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
    debut = _now()
    try:
        with urllib.request.urlopen(requete, timeout=DELAI) as reponse:
            corps = json.loads(reponse.read().decode("utf-8"))
            entetes = {k.lower(): v for k, v in reponse.getheaders()}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:400]
        return {
            "echec": "HTTP %s : %s" % (exc.code, detail),
            "code_http": exc.code,
            "duree": _now() - debut,
        }
    except Exception as exc:
        return {"echec": str(exc), "duree": _now() - debut}
    corps["_duree"] = _now() - debut
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
    """Le modèle répond‑il par l'API que Claude Code emploie ?"""
    jeton = "RLV%d" % (int(time.time()) % 10000)
    r = messages(
        {
            "model": modele,
            "max_tokens": 32,
            "messages": [
                {
                    "role": "user",
                    "content": "Repete ce mot et rien d'autre : %s" % jeton,
                }
            ],
        },
        cle,
    )
    if r.get("echec"):
        return {
            "ok": False,
            "detail": r["echec"],
            "duree": r.get("duree", 0),
            "code_http": r.get("code_http"),
        }
    corps = texte_de(r)
    return {
        "ok": jeton in corps,
        "detail": corps[:120] if jeton in corps else "jeton absent : %r" % corps[:120],
        "duree": r.get("_duree", 0),
        "adresse": r.get("_adresse"),
        "servi": r.get("_servi"),
    }


def epreuve_demande_outil(modele: str, cle: str) -> dict:
    """Le modèle demande‑t‑il l'outil, avec le bon nom et le bon argument ?"""
    r = messages(
        {
            "model": modele,
            "max_tokens": 400,
            "tools": [OUTIL_LIRE],
            "messages": [
                {
                    "role": "user",
                    "content": "Quelle est la premiere ligne de README.md ? "
                    "Utilise l'outil pour le lire.",
                }
            ],
        },
        cle,
    )
    if r.get("echec"):
        return {
            "ok": False,
            "detail": r["echec"],
            "duree": r.get("duree", 0),
            "code_http": r.get("code_http"),
        }
    appels = blocs(r, "tool_use")
    if not appels:
        return {
            "ok": False,
            "duree": r.get("_duree", 0),
            "detail": "aucun tool_use (stop_reason=%s) : %r"
            % (r.get("stop_reason"), texte_de(r)[:120]),
        }
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
    Le modèle sait‑il tirer une conclusion du résultat qu’on lui renvoie ?

    L’épreuve est distincte de la précédente à dessein : émettre un
    `tool_use` bien formé et exploiter un `tool_result` sont deux
    aptitudes séparées, et un modèle peut posséder la première sans la
    seconde. Les confondre ferait conclure à une relève opérationnelle sur
    la foi d’une demande d’outil restée sans suite.
    """
    if appel is None:
        return {
            "ok": None,
            "detail": "epreuve precedente echouee, rien a enchainer",
            "duree": 0,
        }

    chemin_readme = os.path.join(ROOT, "README.md")
    if not os.path.exists(chemin_readme):
        return {
            "ok": None,
            "detail": f"Fichier {chemin_readme} introuvable",
            "duree": 0,
        }

    try:
        premiere = io.open(chemin_readme, encoding="utf-8").readline().strip()
    except Exception as exc:
        return {"ok": None, "detail": "README.md illisible : %s" % exc, "duree": 0}

    r = messages(
        {
            "model": modele,
            "max_tokens": 300,
            "tools": [OUTIL_LIRE],
            "messages": [
                {
                    "role": "user",
                    "content": "Quelle est la premiere ligne de README.md ? "
                    "Utilise l'outil pour le lire.",
                },
                {"role": "assistant", "content": [appel]},
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": appel.get("id", "toolu_01"),
                            "content": premiere + "\n\n(suite du fichier omise)",
                        }
                    ],
                },
            ],
        },
        cle,
    )
    if r.get("echec"):
        return {
            "ok": False,
            "detail": r["echec"],
            "duree": r.get("duree", 0),
            "code_http": r.get("code_http"),
        }
    corps = texte_de(r)
    noyau = premiere.lstrip("# ").strip()
    return {
        "ok": bool(noyau) and noyau.lower() in corps.lower(),
        "duree": r.get("_duree", 0),
        "detail": corps[:160] if corps else "reponse vide",
        "attendu": noyau,
    }


def epreuve_enchainement(modele: str, cle: str) -> dict:
    """
    Deux outils d’affilée : le modèle choisit‑il le bon à chaque étape ?

    Un orchestrateur ne fait presque jamais un seul appel. S’il choisit
    toujours le premier outil de la liste, ou s’il perd le fil après un
    résultat, il enchaînera des actions qui n’ont plus de rapport avec la
    tâche — panne bien plus coûteuse qu’un refus franc.
    """
    depart = _now()
    r1 = messages(
        {
            "model": modele,
            "max_tokens": 400,
            "tools": [OUTIL_LIRE, OUTIL_COMPTER],
            "messages": [
                {
                    "role": "user",
                    "content": "Combien de lignes contient README.md ? "
                    "Choisis l'outil approprie.",
                }
            ],
        },
        cle,
    )
    if r1.get("echec"):
        return {
            "ok": False,
            "detail": r1["echec"],
            "duree": _now() - depart,
            "code_http": r1.get("code_http"),
        }
    appels = blocs(r1, "tool_use")
    if not appels:
        return {"ok": False, "duree": _now() - depart, "detail": "aucun tool_use au premier tour"}
    if appels[0].get("name") != "compter_lignes":
        return {
            "ok": False,
            "duree": _now() - depart,
            "detail": "mauvais outil choisi : %s au lieu de compter_lignes" % appels[0].get("name"),
        }

    chemin_readme = os.path.join(ROOT, "README.md")
    if not os.path.exists(chemin_readme):
        return {
            "ok": None,
            "detail": f"Fichier {chemin_readme} introuvable",
            "duree": _now() - depart,
        }

    try:
        nb = sum(1 for _ in io.open(chemin_readme, encoding="utf-8"))
    except Exception as exc:
        return {"ok": None, "detail": "README.md illisible : %s" % exc, "duree": _now() - depart}
    r2 = messages(
        {
            "model": modele,
            "max_tokens": 200,
            "tools": [OUTIL_LIRE, OUTIL_COMPTER],
            "messages": [
                {
                    "role": "user",
                    "content": "Combien de lignes contient README.md ? "
                    "Choisis l'outil approprie.",
                },
                {"role": "assistant", "content": [appels[0]]},
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": appels[0].get("id", "toolu_01"),
                            "content": str(nb),
                        }
                    ],
                },
            ],
        },
        cle,
    )
    if r2.get("echec"):
        return {
            "ok": False,
            "detail": r2["echec"],
            "duree": _now() - depart,
            "code_http": r2.get("code_http"),
        }
    corps = texte_de(r2)
    return {
        "ok": str(nb) in corps,
        "duree": _now() - depart,
        "detail": corps[:160] if corps else "reponse vide",
        "attendu": str(nb),
    }


EPREUVES = [
    ("parle le protocole /v1/messages", epreuve_protocole),
    ("demande un outil", epreuve_demande_outil),
    ("exploite le resultat d'outil", epreuve_exploite_retour),
    ("enchaine deux outils", epreuve_enchainement),
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
        etat = "OK" if r["ok"] else ("IGNORE" if r["ok"] is None else "ECHEC")
        print("  [%-6s] %d/4 %-34s %5.0f s" % (etat, i, titre, r.get("duree", 0)))
        if not r["ok"] or os.environ.get("NEXUS_VERBEUX"):
            print("         %s" % str(r.get("detail", ""))[:200])
        resultats.append({"epreuve": titre, **{k: v for k, v in r.items() if k != "appel"}})

    codes = {r.get("code_http") for r in resultats if r.get("code_http")}
    reussies = sum(1 for r in resultats if r["ok"])
    ignorees = sum(1 for r in resultats if r["ok"] is None)
    echouees = sum(1 for r in resultats if r["ok"] is False)

    plan = agent.plans_par_alias(cle).get(modele) or agent.plan_de(adresse)
    print()
    print("  servi par : %s [%s]%s" % (servi, plan, "" if adresse == "?" else " " + adresse))
    if plan != "local":
        print("  [!] La releve n'a PAS ete servie en local : le test ne prouve rien")
        print("      sur l'autonomie de la machine.")
    if codes:
        motifs = {
            400: "alias absent du catalogue de la passerelle",
            401: "cle refusee",
            402: "palier non souscrit",
            404: "route inconnue",
            429: "quota epuise",
            500: "moteur en erreur",
            502: "moteur injoignable",
            504: "moteur trop lent",
        }
        print(
            "  codes HTTP rencontres : %s"
            % ", ".join("%s (%s)" % (c, motifs.get(c, "voir le detail")) for c in sorted(codes))
        )
    print(
        "  %d/4 epreuves reussies%s"
        % (
            reussies,
            "" if not ignorees else " (%d echec(s), %d non mesurable(s))" % (echouees, ignorees),
        )
    )
    if reussies == 4:
        print("  => La releve peut orchestrer : outils demandes, resultats exploites,")
        print("     enchainement tenu.")
    elif ignorees and not echouees:
        print("  => Mesure incomplete : aucune epreuve n'a echoue, mais %d n'a pas" % ignorees)
        print("     pu etre tentee. Rien n'est prouve, rien n'est infirme.")
    elif reussies >= 2:
        print("  => La releve repond mais n'orchestre pas de bout en bout.")
        print("     Elle peut servir de repondeur, pas de remplacant.")
    else:
        print("  => La releve ne tient pas. Le travail s'arreterait avec l'abonnement.")
    print()
    rapport = {
        "modele": modele,
        "servi": servi,
        "reussies": reussies,
        # Ce que le script distinguait deja a l'ecran, et perdait a l'ecriture.
        "echouees": echouees,
        "ignorees": ignorees,
        # La mesure a-t-elle seulement ATTEINT le modele ?
        #
        # Le signal est `servi` : le nom du modele qui a REELLEMENT repondu.
        # Un « ? » signifie qu'aucune reponse n'est revenue -- absence de
        # verdict, non verdict d'absence.
        #
        # Le premier jet ajoutait `adresse != "?"`, et c'etait FAUX : l'adresse
        # amont n'est pas toujours resolvable meme quand l'appel aboutit.
        # Mesure du 2026-08-30 : qwen2.5-0.5b-local a rendu 3/4, servi par
        # ollama_chat/qwen2.5:0.5b, et se voyait marquer « concluante: false ».
        #
        # La consequence n'etait pas cosmetique. `deja_mesures()` ne reprend
        # que les verdicts concluants : ces modeles auraient ete remesures
        # INDEFINIMENT, et la reprise posee une heure plus tot n'aurait servi
        # a rien pour eux.
        "concluante": bool(servi and servi != "?" and plan and plan != "inconnu"),
        "plan": plan,
        "adresse": adresse,
        "epreuves": resultats,
        "version": "1.1",
    }
    consigner(rapport)
    return rapport


# La racine de la PLATEFORME, pas celle du projet appelant. `agent.ROOT` suit
# le projet courant, ce qui est juste pour lire des fichiers a analyser et
# faux pour ecrire un registre partage : depuis un projet tiers, l'epreuve
# serait consignee chez lui et le generateur ne la verrait jamais.
PLATEFORME = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# Les deux sortes de guillemets, nommees plutot qu'echappees : un
# echappement traverse mal les couches d'outillage qui ecrivent ce
# fichier, et a deja produit ici des caracteres de controle.
GUILLEMETS = chr(34) + chr(39)


def alias_expose(servi: str | None) -> str | None:
    """
    Remonter du modele amont (`ollama_chat/glm-4.7-flash`) a l'alias que la
    passerelle expose (`glm-4.7-flash-local`).

    L'en-tete x-litellm-model-name donne l'amont, pas l'alias. Le generateur,
    lui, ne connait que l'alias : sans cette traduction les deux ne se
    rencontrent jamais.

    Rend None plutot que de deviner. Un alias invente serait pire qu'absent :
    il accorderait une derogation a un modele qui n'a rien passe.
    """
    if not servi or servi == "?":
        return None
    chemin = os.path.join(PLATEFORME, "litellm_config.yaml")
    try:
        with open(chemin, encoding="utf-8") as f:
            texte = f.read()
    except Exception:
        return None
    # Lecture textuelle volontaire : PyYAML n'est pas une dependance de ce
    # script, et l'exiger ferait echouer une consignation pour une commodite.
    nom = None
    for ligne in texte.splitlines():
        depouille = ligne.strip()
        if depouille.startswith("- model_name:"):
            nom = depouille.split(":", 1)[1].strip()
        elif depouille.startswith("model:") and nom:
            valeur = depouille.split(chr(58), 1)[1].strip()
            if valeur.strip(GUILLEMETS) == servi:
                return nom
    return None


def consigner(rapport: dict) -> None:
    """
    Inscrire le verdict dans .nexus/epreuves.json.

    Ce registre existe parce que le banc de latence (nexus_bench.py) et cette
    releve ne mesurent pas la meme chose. Le banc demande seize jetons : il
    chronometre le DEMARRAGE. La releve fait passer quatre epreuves reelles :
    protocole, demande d'outil, exploitation du resultat, enchainement. Elle
    prouve la CAPACITE.

    Correction du 2026-08-30 : ce registre a d'abord ete justifie par
    glm-4.7-flash-local, donne pour « sortant du pool a 61,8 s ». Verification
    faite dans litellm_config.yaml, c'est faux -- ce modele est declare a la
    main, hors zone AUTOGEN, et le critere de latence ne le juge jamais.

    Le registre garde sa raison d'etre pour les modeles AUTO-EXPOSES : un
    modele lent a demarrer mais prouve capable doit pouvoir entrer, et
    relever le seuil pour l'accueillir ferait entrer du meme geste des
    modeles n'ayant rien prouve. Aucun cas de ce type n'existe a ce jour.

    N'echoue jamais : un registre non ecrit ne doit pas faire echouer une
    releve qui, elle, a abouti. Mais il le DIT, sur stderr.

    Mesure du 2026-08-30 : une releve de 1004 s a rendu 4/4 et n'a ecrit
    aucun registre. Le filet etait un `except: pass` muet, si bien que la
    cause a ete perdue avec l'erreur -- il a fallu rejouer la consignation a
    la main pour constater qu'elle marchait, sans jamais apprendre pourquoi
    elle avait echoue.

    Ne pas faire echouer et ne rien dire sont deux choses differentes. La
    premiere est voulue, la seconde etait un defaut.
    """
    try:
        dossier = os.path.join(PLATEFORME, ".nexus")
        os.makedirs(dossier, exist_ok=True)
        chemin = os.path.join(dossier, "epreuves.json")
        try:
            with open(chemin, encoding="utf-8") as f:
                registre = json.load(f)
            if not isinstance(registre, dict):
                registre = {}
        except Exception:
            registre = {}
        registre.setdefault("modeles", {})
        # Le total est lu depuis EPREUVES et non fige a 4 : le jour ou une
        # cinquieme epreuve est ajoutee, un « 4/5 » ne doit pas continuer de
        # passer pour un sans-faute.
        # LAQUELLE a echoue, et pas seulement combien.
        #
        # Le registre gardait le score et rien d'autre. Mesure du
        # 2026-08-30 : sept modeles partiels, dont TROIS a 3/4 -- a une seule
        # epreuve d'etre promouvables -- et rien ne disait laquelle leur
        # manquait. Or les quatre epreuves mesurent des capacites
        # differentes : parler le protocole, demander un outil, exploiter le
        # resultat, enchainer. Un modele qui echoue sur la premiere est
        # inutilisable ; un modele qui echoue sur la quatrieme sert deja de
        # repondeur.
        #
        # Sans ce detail, on ne peut ni choisir quel modele ajouter pour
        # combler une lacune, ni savoir laquelle est la plus repandue. Le
        # rapport le portait deja ; seule l'ecriture le perdait.
        detail = rapport.get("epreuves") or []
        entree = {
            "reussies": rapport["reussies"],
            "total": len(EPREUVES),
            "complet": rapport["reussies"] >= len(EPREUVES),
            "echouees": rapport.get("echouees"),
            "ignorees": rapport.get("ignorees"),
            "concluante": rapport.get("concluante", True),
            "epreuves_echouees": [r.get("epreuve") for r in detail
                                  if r.get("ok") is False],
            "epreuves_non_mesurees": [r.get("epreuve") for r in detail
                                      if r.get("ok") is None],
            "plan": rapport["plan"],
            "servi": rapport.get("servi"),
            "date": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }
        # Sous les DEUX noms : celui demande et celui reellement servi.
        #
        # L'epreuve porte sur l'alias `releve-locale`, tandis que le pool
        # raisonne sur l'alias expose -- `glm-4.7-flash-local`. Ne consigner
        # que le premier laissait la derogation chercher un nom jamais ecrit :
        # elle n'aurait servi a rien, sans que rien ne le signale.
        for nom in {rapport["modele"], alias_expose(rapport.get("servi"))}:
            if not nom:
                continue
            # UNE MESURE RATEE N'EFFACE PAS UNE PREUVE ACQUISE.
            #
            # Mesure du 2026-08-30, et le defaut etait invisible dans le
            # fichier : `releve-locale` avait passe 4/4, et comme cette
            # boucle ecrit sous les DEUX noms, `glm-4.7-flash-local` portait
            # 4/4 lui aussi -- a juste titre, c'est le meme modele. Puis
            # `--tous` a interroge `glm-4.7-flash-local` directement, l'appel
            # n'a jamais abouti, et le 0/4 a ECRASE le 4/4.
            #
            # Le registre affirmait donc simultanement que le meme modele
            # orchestre et n'orchestre pas. 105.2 est explicite : l'absence
            # de preuve n'est pas une preuve d'absence. Une tentative qui
            # n'atteint pas le modele est consignee A PART, sans toucher au
            # verdict existant.
            precedent = registre["modeles"].get(nom)
            if not entree["concluante"] and precedent and precedent.get("concluante", True):
                precedent = dict(precedent)
                precedent["derniere_tentative_vaine"] = entree["date"]
                registre["modeles"][nom] = precedent
                continue
            registre["modeles"][nom] = dict(entree, demande=rapport["modele"])
        registre["mesure_le"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        with open(chemin, "w", encoding="utf-8") as f:
            json.dump(registre, f, indent=2, ensure_ascii=False)
    except Exception as exc:
        # stderr, jamais stdout : --json doit rester analysable.
        print("  [!] registre d'epreuves non ecrit : %s: %s"
              % (type(exc).__name__, exc), file=sys.stderr)


def candidats_locaux(cle: str) -> list[str]:
    """Alias locaux exposés, hors embeddings et hors modèles de vision."""
    requete = urllib.request.Request(
        PASSERELLE + "/v1/model/info", headers={"Authorization": "Bearer " + cle}
    )
    try:
        with urllib.request.urlopen(requete, timeout=30) as reponse:
            donnees = json.loads(reponse.read().decode("utf-8")).get("data", [])
    except urllib.error.URLError as exc:
        print("  Catalogue injoignable sur %s : %s" % (PASSERELLE, exc))
        print("  Verifier la passerelle : python scripts/nexus_conformite.py")
        return []
    except json.JSONDecodeError as exc:
        print("  Reponse JSON invalide du catalogue : %s" % exc)
        return []
    except Exception as exc:
        print("  Erreur inattendue lors du catalogue : %s" % exc)
        return []
    noms = []
    for entree in donnees:
        nom = entree.get("model_name", "")
        params = entree.get("litellm_params") or {}
        cible = str(params.get("model", ""))
        if not cible.startswith("ollama"):
            continue
        if "ollama.com" in str(params.get("api_base", "")):
            continue
        # La modalite DECLAREE prime sur le nom.
        #
        # Le filtre ne jugeait que le nom : « embed|minilm|llava|-vl-|vision ».
        # `bge-m3-local` n'en contient aucun, et un modele d'embedding s'est
        # donc retrouve soumis a une epreuve d'ORCHESTRATION, ou il a
        # enregistre 0/4 -- un score qu'il ne pouvait pas obtenir autrement,
        # par construction. C'est le meme angle mort que le contrat dit avoir
        # deja ete corrige DEUX FOIS ailleurs qu'a sa source.
        #
        # La source etait la declaration : `mode` n'y figurait pas, et LiteLLM
        # retombe alors sur « chat ». Elle est corrigee ; ce filtre lit
        # desormais ce qu'elle dit, et ne garde le nom que comme filet pour
        # un modele encore non declare.
        infos = entree.get("model_info") or {}
        mode = str(infos.get("mode") or "").lower()
        if mode and mode != "chat":
            continue
        if infos.get("supports_vision"):
            continue
        if any(m in nom for m in ("embed", "minilm", "llava", "-vl-", "vision")):
            continue
        noms.append(nom)
    return sorted(set(noms))


def deja_mesures() -> dict:
    """
    Les verdicts CONCLUANTS deja acquis, pour ne pas les refaire.

    Sans cela, `--tous` repartait du premier candidat a chaque lancement.
    Mesure du 2026-08-30 : trois lancements successifs, interrompus chacun
    avant la fin, ont remesure les MEMES douze premiers modeles par ordre
    alphabetique -- codegemma, codestral, command-r, deepseek, gemma, glm --
    et ne sont jamais alles au-dela. Le parc en compte soixante-et-onze.

    Une epreuve dure des minutes et coute une place en memoire du moteur :
    la refaire quand le verdict est acquis n'ajoute rien et empeche le reste
    d'etre mesure.

    Seuls les verdicts CONCLUANTS comptent. Une tentative qui n'a pas atteint
    le modele ne prouve rien et doit etre rejouee.
    """
    try:
        with open(os.path.join(PLATEFORME, ".nexus", "epreuves.json"),
                  encoding="utf-8") as f:
            registre = json.load(f)
        modeles = registre.get("modeles") or {}
        return {n: v for n, v in modeles.items() if v.get("concluante", True)}
    except Exception:
        # Registre absent ou illisible : on mesure tout, ce qui est le
        # comportement d'avant. Ne jamais empecher une mesure faute d'archive.
        return {}


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--modele", help="Alias a eprouver. Defaut : " + RELEVE)
    p.add_argument(
        "--tous", action="store_true", help="Eprouver tous les candidats locaux (long)."
    )
    p.add_argument("--json", action="store_true")
    p.add_argument(
        "--refaire", action="store_true",
        help="Rejouer meme les modeles deja mesures. Par defaut, --tous "
             "REPREND la ou il en etait.")
    a = p.parse_args()

    cle = agent.cle_maitre()
    if a.tous:
        cibles = candidats_locaux(cle)
        if not cibles:
            print("Aucun candidat local a eprouver.")
            return 1
        if not a.refaire:
            acquis = deja_mesures()
            restants = [m for m in cibles if m not in acquis]
            # Le saut est DIT, jamais silencieux : une reprise muette se
            # lirait comme « tout a ete mesure », ce qui est le contraire.
            if len(restants) != len(cibles):
                print("  %d modele(s) deja mesure(s), repris la ou on en etait."
                      % (len(cibles) - len(restants)))
                print("  --refaire pour tout rejouer.")
            cibles = restants
            if not cibles:
                print("  Tous les candidats ont deja un verdict concluant.")
                return 0
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
    return 0 if aptes else 1


if __name__ == "__main__":
    sys.exit(main())
