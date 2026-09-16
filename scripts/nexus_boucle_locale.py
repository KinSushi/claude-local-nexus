import os
import json
import time
import argparse
import sys


def decision_suivante(verdict, echecs, max_echecs):
    if verdict == "OK":
        return "APPLIQUER"
    if verdict == "REJET" or (echecs + 1) >= max_echecs:
        return "ABANDONNER"
    return "REPENSER"


def parser_verdict(texte):
    if not texte:
        return "RETRY"
    txt = texte.lower()
    if "verdict: ok" in txt:
        return "OK"
    if "verdict: rejet" in txt:
        return "REJET"
    if "verdict: retry" in txt:
        return "RETRY"
    return "RETRY"


def consigne_pilote(tache):
    av = "<" * 3 + "AVANT" + ">" * 3
    ap = "<" * 3 + "APRES" + ">" * 3
    fn = "<" * 3 + "FIN" + ">" * 3
    return "Task: %s\nProvide a patch using the markers %s/%s/%s." % (tache.get("tache", ""), av, ap, fn)


def consigne_auditeur(tache, patch):
    return ("Evaluate the following patch for the task:\n%s\n\nPatch:\n%s\n"
            "Respond on the LAST line exactly with one of:\n"
            "VERDICT: OK\nVERDICT: RETRY\nVERDICT: REJET") % (tache.get("tache", ""), patch)


def un_cycle(tache, pilote, auditeur, appel_fn, disjoncteur=None):
    if pilote == auditeur:
        raise ValueError("pilote et auditeur doivent etre distincts (LOI 1)")
    if disjoncteur is not None and (not disjoncteur.is_available(pilote) or not disjoncteur.is_available(auditeur)):
        return (None, "REJET", "disjoncteur ouvert")
    try:
        patch = appel_fn(pilote, consigne_pilote(tache), tache.get("fichiers", []))
        if disjoncteur is not None:
            disjoncteur.record_success(pilote)
    except Exception as exc:
        if disjoncteur is not None:
            disjoncteur.record_failure(pilote)
        return (None, "RETRY", str(exc)[:80])
    try:
        verdict_txt = appel_fn(auditeur, consigne_auditeur(tache, patch), tache.get("fichiers", []))
        if disjoncteur is not None:
            disjoncteur.record_success(auditeur)
    except Exception as exc:
        if disjoncteur is not None:
            disjoncteur.record_failure(auditeur)
        return (None, "RETRY", str(exc)[:80])
    return (patch, parser_verdict(verdict_txt), "")


def deposer_proposition(tache, patch, verdict, dossier):
    try:
        ts = int(time.time())
        nom = tache.get("nom", "sans_nom")
        fichier = "%s_%d.json" % (nom, ts)
        chemin_final = os.path.join(dossier, fichier)
        os.makedirs(dossier, exist_ok=True)
        tmp = os.path.join(dossier, ".tmp_%s_%d.json" % (nom, ts))
        data = {
            "nom": nom,
            "tache": tache.get("tache", ""),
            "fichiers": tache.get("fichiers", []),
            "patch": patch,
            "verdict": verdict,
            "timestamp": ts
        }
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=True)
        os.replace(tmp, chemin_final)
        return chemin_final
    except Exception as exc:
        print("scripts/nexus_boucle_locale.py : deposer_proposition impossible : %s" % exc, file=sys.stderr)
        return None


def boucle(taches, lire_pouls_fn, appel_fn, pilote, auditeur, deposer_fn, disjoncteur=None, max_echecs=3, max_steps=5):
    rapport = {"traitees": 0, "deposees": 0, "abandonnees": 0, "retrait": False, "raison": ""}
    for tache in taches:
        if lire_pouls_fn():
            rapport["retrait"] = True
            rapport["raison"] = "claude vivant, retrait"
            break
        # echecs vaut l'index d'iteration : il ne s'incremente que sur REPENSER,
        # et APPLIQUER/ABANDONNER sortent de la boucle -- donc range() suffit.
        for echecs in range(max_steps):
            patch, verdict, detail = un_cycle(tache, pilote, auditeur, appel_fn, disjoncteur)
            action = decision_suivante(verdict, echecs, max_echecs)
            if action == "APPLIQUER":
                if deposer_fn(tache, patch, verdict) is not None:
                    rapport["deposees"] += 1
                break
            if action == "ABANDONNER":
                rapport["abandonnees"] += 1
                break
        else:
            rapport["abandonnees"] += 1
        rapport["traitees"] += 1
    return rapport


def charger_file(chemin):
    try:
        with open(chemin, "r", encoding="utf-8") as f:
            lignes = f.readlines()
    except FileNotFoundError:
        # Absence du fichier est l'état normal d'un fichier vide : renvoie [] sans alerte
        return []
    except Exception as exc:
        print("scripts/nexus_boucle_locale.py : charger_file (open) impossible : %s" % exc, file=sys.stderr)
        return []
    taches = []
    for ligne in lignes:
        ligne = ligne.strip()
        if not ligne:
            continue
        try:
            obj = json.loads(ligne)
            if isinstance(obj, dict):
                taches.append(obj)
        except Exception as exc:
            print("scripts/nexus_boucle_locale.py : charger_file (json.loads) impossible : %s" % exc, file=sys.stderr)
            continue
    return taches


def modeles_derives():
    """Pilote et auditeur DERIVES des epreuves mesurees, jamais graves.

    Mesure du 2026-09-16 : ce fichier gravait deux modeles de 18 et 19 Go pour
    une boucle de fond tournant toutes les dix minutes.

    Le critere n est PAS le poids seul, et c est le point delicat. Le releve
    .nexus/epreuves.json montre que les plus legers echouent aux epreuves
    reelles -- smollm2:360m, tinyllama et llama3.2:1b rendent 1 sur 4, tous
    sur « demande un outil » et « enchaine deux outils ». Deriver sur le poids
    aurait remplace un mauvais choix grave par un choix derive incapable.

    On retient donc les modeles dont l epreuve est COMPLETE et STABLE, puis
    les deux plus legers parmi eux. Rend (None, None) si moins de deux
    qualifient : l appelant decide, plutot qu un defaut invente ici.
    """
    racine = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    try:
        with open(os.path.join(racine, ".nexus", "epreuves.json"), encoding="utf-8") as f:
            releve = json.load(f).get("modeles", {})
    except Exception:
        return (None, None)
    try:
        import importlib.util
        chemin = os.path.join(racine, "scripts", "nexus_capability.py")
        spec = importlib.util.spec_from_file_location("_boucle_capability", chemin)
        cap = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cap)
        tailles = cap.installed_models() or {}
    except Exception:
        return (None, None)
    qualifies = []
    for alias, mesure in releve.items():
        if not isinstance(mesure, dict):
            continue
        if not (mesure.get("complet") and mesure.get("stable")):
            continue
        if mesure.get("plan") != "local":
            continue
        servi = (mesure.get("servi") or "").split("/", 1)[-1]
        poids = tailles.get(servi)
        if not poids or poids <= 0:
            continue
        qualifies.append((poids, alias))
    if len(qualifies) < 2:
        return (None, None)
    qualifies.sort()
    return (qualifies[0][1], qualifies[1][1])


def tour_si_pouls_mort(chemin_file, seuil_s=900.0, pilote=None, auditeur=None, simuler=False):
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    # Les valeurs non fournies se DERIVENT des epreuves mesurees. Sans cet
    # appel, pilote et auditeur restaient None jusqu'a un_cycle, ou la garde
    # LOI 1 « distincts » levait sur None == None : une fonction correcte mais
    # non appelee est indiscernable d'une fonction absente.
    if pilote is None or auditeur is None:
        derives = modeles_derives()
        pilote = pilote or derives[0]
        auditeur = auditeur or derives[1]
    if not pilote or not auditeur or pilote == auditeur:
        return {"retrait": True,
                "raison": "modeles indisponibles : derivation rend %r" % (( pilote, auditeur),)}
    from nexus_pouls import lire, est_vivant, _chemin_defaut
    pouls = lire(_chemin_defaut())
    if pouls is not None and est_vivant(pouls, time.time(), seuil_s):
        return {"retrait": True, "raison": "claude vivant"}
    taches = charger_file(chemin_file)
    if not taches:
        return {"retrait": False, "raison": "file vide", "traitees": 0}
    if simuler:
        def appel_sim(modele, consigne, fichiers):
            return "PATCH_SIMULATED\nVERDICT: OK"
        appel_fn = appel_sim
        disjoncteur = None
    else:
        from nexus_agent import executer, cle_maitre
        def appel_real(modele, consigne, fichiers):
            res = executer({
                "nom": "boucle-locale",
                "tache": consigne,
                "fichiers": fichiers,
                "modele": modele,
                "max_tokens": 2000
            }, cle_maitre())
            return res.get("texte", "")
        appel_fn = appel_real
        from nexus_disjoncteur import CircuitBreaker
        disjoncteur = CircuitBreaker()
    def deposer_fn(t, p, v):
        prop_dir = os.path.join(root, ".nexus", "propositions")
        return deposer_proposition(t, p, v, prop_dir)
    lire_pouls_fn = lambda: est_vivant(lire(_chemin_defaut()), time.time(), seuil_s)
    return boucle(taches, lire_pouls_fn, appel_fn, pilote, auditeur, deposer_fn, disjoncteur)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Boucle agentique locale Nexus")
    parser.add_argument("--tour", action="store_true", help="Execute un seul tour")
    parser.add_argument("--file", default=os.path.join(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")), ".nexus", "file_locale.jsonl"))
    parser.add_argument("--seuil", type=float, default=900.0, help="Seuil de pouls mort (secondes)")
    parser.add_argument("--simuler", action="store_true", help="Mode simulation sans appel reseau")
    # Defaut DERIVE des epreuves mesurees, jamais grave : voir
    # modeles_derives(). Une valeur passee en ligne de commande l emporte.
    parser.add_argument("--pilote", default=None)
    parser.add_argument("--auditeur", default=None)
    args = parser.parse_args()
    if args.tour:
        rapport = tour_si_pouls_mort(args.file, args.seuil, args.pilote, args.auditeur, args.simuler)
        sys.stdout.write(json.dumps(rapport, ensure_ascii=True))
        sys.exit(0)
    parser.print_help()
