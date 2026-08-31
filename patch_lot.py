# -*- coding: utf-8 -*-
"""Un lot qui ne rend rien avant la fin perd tout ce qu'une interruption coupe."""
import io

chemin = r"C:\local-llm-docker\scripts\nexus_agent.py"
src = io.open(chemin, encoding="utf-8").read()

ancien = '''    resultats: List[dict] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=largeur) as pool:
        futurs = {pool.submit(executer, t, cle): t for t in taches}
        for futur in concurrent.futures.as_completed(futurs):
            resultats.append(futur.result())
'''

nouveau = '''    resultats: List[dict] = []
    # CHAQUE RESULTAT EST ECRIT DES QU'IL TOMBE.
    #
    # Le lot accumulait tout en memoire et ne rendait rien avant la fin :
    # une interruption perdait l'integralite du travail deja paye, et un
    # fichier de sortie vide se lisait comme « rien ne se passe » alors que
    # les reponses arrivaient. Mesure du 2026-08-31 : un lot de dix-sept
    # taches a laisse un fichier a ZERO octet pendant six minutes, huit
    # processus vivants et douze reponses 200 deja servies.
    #
    # `--sortie` ecrit une ligne JSON par tache achevee. Le fichier est
    # ouvert en ajout et vide a chaque ecriture : ce qui est tombe est
    # acquis, meme si la suite ne vient jamais.
    flux = None
    if getattr(args, "sortie", None):
        try:
            flux = io.open(args.sortie, "w", encoding="utf-8", newline="\\n")
        except Exception as exc:
            print("[!] sortie incrementale impossible : %s" % exc, file=sys.stderr)
            flux = None
    faits = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=largeur) as pool:
        futurs = {pool.submit(executer, t, cle): t for t in taches}
        for futur in concurrent.futures.as_completed(futurs):
            r = futur.result()
            resultats.append(r)
            faits += 1
            if flux is not None:
                flux.write(json.dumps(r, ensure_ascii=False) + "\\n")
                flux.flush()
            # L'AVANCEMENT VA SUR STDERR, jamais sur stdout : celui-ci porte
            # le JSON du rapport, et le polluer le rendrait illisible a un
            # appelant qui le parse.
            print("  [%d/%d] %s" % (faits, len(taches),
                                    r.get("nom") or r.get("modele") or "?"),
                  file=sys.stderr)
    if flux is not None:
        flux.close()
'''

assert src.count(ancien) == 1, "boucle du lot introuvable"
src = src.replace(ancien, nouveau)

ancien_opt = '''    parser.add_argument("--parallele", type=int, default=3,'''
nouveau_opt = '''    parser.add_argument(
        "--sortie", default=None, metavar="FICHIER",
        help="Ecrire une ligne JSON par tache DES QU'ELLE ABOUTIT. Sans "
             "cela, rien ne sort avant la fin du lot et une interruption "
             "perd tout le travail deja paye.")
    parser.add_argument("--parallele", type=int, default=3,'''
assert src.count(ancien_opt) == 1, "option --parallele introuvable"
src = src.replace(ancien_opt, nouveau_opt)

io.open(chemin, "w", encoding="utf-8", newline="\n").write(src)
print("sortie incrementale posee sur le lot")
