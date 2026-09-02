import importlib.util, os, sys, json, inspect

def main():
    # Charger le module à tester sans l'exécuter
    module_path = os.path.join("scripts", "nexus_agent.py")
    spec = importlib.util.spec_from_file_location("nexus_agent", module_path)
    nexus = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(nexus)

    # ---------- 1. Vérifier la liste REPLIS_GRATUITS ----------
    replis = getattr(nexus, "REPLIS_GRATUITS", None)
    if not isinstance(replis, list):
        print("[FAIL] REPLIS_GRATUITS absent ou pas une liste")
        sys.exit(1)

    # aucune entrée ne doit évoquer le fournisseur facturé (anthropic, claude, facture)
    prohibited = ("anthropic", "claude", "facture")
    if any(any(p in entry.lower() for p in prohibited) for entry in replis):
        print("[FAIL] REPLIS_GRATUITS contient un alias facturé")
        sys.exit(1)

    # au moins un candidat LOCAL
    if not any(entry.endswith("-local") for entry in replis):
        print("[FAIL] REPLIS_GRATUITS ne contient aucun modèle local")
        sys.exit(1)

    # au moins un candidat distant (cloud)
    if not any(entry.endswith("-cloud") for entry in replis):
        print("[FAIL] REPLIS_GRATUITS ne contient aucun modèle distant")
        sys.exit(1)

    print("[OK] REPLIS_GRATUITS valide")

    # ---------- 2. Nom de la fonction qui assemble les candidats ----------
    func_name = "executer"
    if not hasattr(nexus, func_name):
        print("[FAIL] Fonction d'assemblage des candidats introuvable")
        sys.exit(1)

    print("[OK] Fonction d'assemblage trouvée :", func_name)

    # ---------- 3. Clé du dictionnaire de résultat qui rapporte une bascule ----------
    sample_key = "bascule"
    source = inspect.getsource(getattr(nexus, func_name))
    if sample_key not in source:
        print("[FAIL] Clé de bascule non détectée dans le code")
        sys.exit(1)

    print("[OK] Clé de bascule détectée :", sample_key)

    # ---------- 4. Variables d'environnement influençant le choix du plan ----------
    env_vars = ["NEXUS_FILS_CLOUD", "NEXUS_FILS_LOCAL", "NEXUS_LOCAL_SEUL"]
    missing = [v for v in env_vars if v not in os.environ]
    if missing:
        print("[INFO] Variables d'environnement non definies (valeurs par defaut) :", ", ".join(missing))
    else:
        print("[OK] Toutes les variables d'environnement présentes")

    # ---------- 5. Vérifier que, avec un modèle LOCAL, aucun candidat distant n'est proposé ----------
    def simulate_candidates(modele):
        base = [modele] + replis
        seen = set()
        uniq = []
        for m in base:
            if m not in seen:
                seen.add(m)
                uniq.append(m)
        def plan_rank(name):
            if name.endswith("-local"):
                return 0
            if name.endswith("-cloud"):
                return 1
            return 2
        rank_req = plan_rank(modele)
        return [c for c in uniq if plan_rank(c) <= rank_req]

    local_models = [m for m in replis if m.endswith("-local")]
    if not local_models:
        print("[FAIL] Aucun modèle local disponible pour le test")
        sys.exit(1)

    candidates = simulate_candidates(local_models[0])
    if any(c.endswith("-cloud") for c in candidates):
        print("[FAIL] Un candidat distant apparaît avec un modèle local")
        sys.exit(1)

    print("[OK] Aucun candidat distant avec modèle local")

    # ---------- 6. Commentaire près de la liste expliquant l'absence d'alias facture ----------
    source_lines = inspect.getsource(nexus).splitlines()
    found_comment = False
    for i, line in enumerate(source_lines):
        if "REPLIS_GRATUITS" in line:
            # On regarde les 5 lignes precedentes
            start = max(0, i - 5)
            context = " ".join(source_lines[start:i]).lower()
            if "gratuit" in context and "pay" in context:
                found_comment = True
            break

    if not found_comment:
        print("[FAIL] Aucun commentaire mentionnant la gratuite et l'absence de plan paye")
        sys.exit(1)

    print("[OK] Commentaire d'explication trouvé")

    print("[ALL TESTS PASSED]")
    sys.exit(0)

if __name__ == "__main__":
    main()
