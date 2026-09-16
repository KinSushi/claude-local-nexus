import os, sys, re, importlib.util, tempfile
from pathlib import Path

# ------------------------------------------------------------
# Environnement requis avant tout import supplémentaire
# ------------------------------------------------------------
os.environ["NEXUS_GATEWAY"] = "http://127.0.0.1:9"
_temp_dir = tempfile.TemporaryDirectory()
os.environ["NEXUS_ETAT_DISJONCTEUR"] = _temp_dir.name

# ------------------------------------------------------------
# Lecture du source du script testé (sans import)
# ------------------------------------------------------------
_source_path = Path(__file__).resolve().parents[1] / "scripts" / "nexus_boucle_locale.py"
try:
    _source_text = _source_path.read_text(encoding="utf-8")
except Exception:
    _source_text = ""

# ------------------------------------------------------------
# Chargement dynamique de scripts/nexus_capability.py
# ------------------------------------------------------------
_cap_path = Path(__file__).resolve().parents[1] / "scripts" / "nexus_capability.py"
_spec = importlib.util.spec_from_file_location("nexus_capability", _cap_path)
_cap_mod = None
if _spec and _spec.loader:
    try:
        _cap_mod = importlib.util.module_from_spec(_spec)
        _spec.loader.exec_module(_cap_mod)
    except Exception:
        _cap_mod = None

_build_profile = getattr(_cap_mod, "build_profile", None) if _cap_mod else None
_installed_models = getattr(_cap_mod, "installed_models", None) if _cap_mod else None

# ------------------------------------------------------------
# Infrastructure de comptage et d'exécution des cas
# ------------------------------------------------------------
total_cases = 0
failed_cases = 0


def run_case(name, func):
    global total_cases, failed_cases
    total_cases += 1
    try:
        result = func()
        print(f"[OK  ] {name} : {result!r}")
    except Exception as e:
        failed_cases += 1
        print(f"[RATE] {name} : {type(e).__name__}: {e}")


# ------------------------------------------------------------
# Cas de test
# ------------------------------------------------------------

def C0():
    """Vérifie l'existence du fichier et rend sa taille en octets."""
    if not _source_path.is_file():
        raise AssertionError("scripts/nexus_boucle_locale.py introuvable")
    return _source_path.stat().st_size


def F1():
    """
    Extrait tous les noms de modèles graves (default="...-local",
    pilote="..." ou auditeur="...") via expression régulière.
    Retourne la liste triée.
    """
    pattern = re.compile(r'(default|pilote|auditeur)\s*=\s*"([^"]+)"')
    matches = pattern.findall(_source_text)
    graves = [val for _, val in matches if val.endswith("-local")]
    return sorted(set(graves))


def F2():
    """
    Cliquet : aucun modèle local ne doit être grave en valeur par défaut.
    Lève AssertionError si des modèles sont trouvés.
    """
    graves = F1()
    if graves:
        raise AssertionError(f"Modèles graves trouvés : {graves}")
    return "aucun modele grave"


def F3():
    """
    Pour chaque nom grave trouvé en F1, récupère son poids via installed_models().
    Essaye plusieurs formes de nom.
    Retourne la liste des couples (nom, poids en Go) réellement trouvés.
    """
    if not callable(_installed_models):
        return "DEGRADE: installed_models indisponible"

    try:
        model_dict = _installed_models()
    except Exception as e:
        return f"DEGRADE: appel installed_models échoué ({e})"

    if not isinstance(model_dict, dict):
        return "DEGRADE: installed_models ne retourne pas un dict"

    result = []
    for name in F1():
        weight = None
        base = name.removesuffix("-local")
        # Mesure du 2026-09-16 : les alias du depot ne sont pas les noms du
        # moteur. glm-4.7-flash-local vaut glm-4.7-flash:latest, et
        # qwen3-coder-30b-local vaut qwen3-coder:30b. On essaie donc plusieurs
        # formes, de la plus stricte a la plus large, sans rien graver.
        candidats = [name, base, base + ":latest"]
        if "-" in base:
            tete, queue = base.rsplit("-", 1)
            candidats.append(f"{tete}:{queue}")
        for candidat in candidats:
            if candidat in model_dict:
                weight = model_dict[candidat]
                break
        if weight is None:
            for cle in model_dict:
                if cle.split(":", 1)[0] == base:
                    weight = model_dict[cle]
                    break
        if weight is not None:
            # on suppose que le poids est exprimé en Go ou convertible
            try:
                weight_gb = float(weight)
            except Exception:
                weight_gb = weight
            result.append((name, weight_gb))
    return result


def D1():
    """La derivation rend-elle un RESULTAT, et non deux None ?

    Mesure du 2026-09-16 : ce cliquet est passe au vert alors que
    modeles_derives() n'etait appelee nulle part et que pilote et auditeur
    valaient None jusqu'a la garde LOI 1. Un cliquet qui mesure une ABSENCE
    passe au vert des qu'on retire la chose, meme sans rien mettre a la place.
    """
    import importlib.util
    chemin = Path(__file__).resolve().parents[1] / "scripts" / "nexus_boucle_locale.py"
    spec = importlib.util.spec_from_file_location("_boucle_locale", chemin)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert hasattr(module, "modeles_derives"), "modeles_derives absente"
    pilote, auditeur = module.modeles_derives()
    assert pilote and auditeur, "la derivation rend %r : aucun modele choisi" % ((pilote, auditeur),)
    assert pilote != auditeur, "pilote et auditeur identiques : la garde LOI 1 leverait"
    return (pilote, auditeur)


def D2():
    """La derivation est-elle reellement APPELEE par tour_si_pouls_mort ?"""
    import inspect, importlib.util
    chemin = Path(__file__).resolve().parents[1] / "scripts" / "nexus_boucle_locale.py"
    spec = importlib.util.spec_from_file_location("_boucle_locale2", chemin)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    source = inspect.getsource(module.tour_si_pouls_mort)
    assert "modeles_derives" in source, (
        "tour_si_pouls_mort n appelle pas modeles_derives : cablage creux, "
        "pilote et auditeur resteraient None")
    return "derivation appelee"


def R1():
    """
    Cliquet mémoire : la somme des poids retrouvés en F3 doit être < budget.
    Le budget provient de build_profile()["pool_budget_gb"].
    """
    poids = F3()
    if isinstance(poids, str) and poids.startswith("DEGRADE"):
        return poids
    if not poids:
        return "poids non mesurables"

    total = sum(p for _, p in poids if isinstance(p, (int, float)))
    if not callable(_build_profile):
        return "DEGRADE: build_profile indisponible"

    try:
        profile = _build_profile()
    except Exception as e:
        return f"DEGRADE: appel build_profile échoué ({e})"

    if not isinstance(profile, dict) or "pool_budget_gb" not in profile:
        return "DEGRADE: build_profile ne fournit pas pool_budget_gb"

    budget = profile["pool_budget_gb"]
    try:
        budget_val = float(budget)
    except Exception:
        budget_val = budget

    if total > budget_val:
        raise AssertionError(f"Somme des poids {total} > budget {budget_val}")
    return (total, budget_val)


# ------------------------------------------------------------
# Exécution des cas
# ------------------------------------------------------------
run_case("C0", C0)
run_case("F1", F1)
run_case("F2", F2)
run_case("F3", F3)
run_case("D1", D1)
run_case("D2", D2)
run_case("R1", R1)

# ------------------------------------------------------------
# Résultat final
# ------------------------------------------------------------
print(f"{total_cases} cas, {failed_cases} RATE")
sys.exit(1 if failed_cases > 0 else 0)
