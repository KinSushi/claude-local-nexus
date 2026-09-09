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
    except Exception:
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
    except Exception:
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
        except Exception:
            continue
    return taches


def tour_si_pouls_mort(chemin_file, seuil_s=900.0, pilote="qwen3-coder-30b-local", auditeur="glm-4.7-flash-local", simuler=False):
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
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
    parser.add_argument("--pilote", default="qwen3-coder-30b-local")
    parser.add_argument("--auditeur", default="glm-4.7-flash-local")
    args = parser.parse_args()
    if args.tour:
        rapport = tour_si_pouls_mort(args.file, args.seuil, args.pilote, args.auditeur, args.simuler)
        sys.stdout.write(json.dumps(rapport, ensure_ascii=True))
        sys.exit(0)
    parser.print_help()