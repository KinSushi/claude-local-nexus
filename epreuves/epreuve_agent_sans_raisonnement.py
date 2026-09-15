import importlib.util
import inspect
import os
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Tuple

# ----------------------------------------------------------------------
# Pré‑configuration de l’environnement avant le chargement du module cible
# ----------------------------------------------------------------------
os.environ["NEXUS_GATEWAY"] = "http://127.0.0.1:9"

_temp_dir = tempfile.TemporaryDirectory()
os.environ["NEXUS_ETAT_DISJONCTEUR"] = str(Path(_temp_dir.name) / "etat.txt")

# ----------------------------------------------------------------------
# Chargement du module `scripts/nexus_agent.py`
# ----------------------------------------------------------------------
_root = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    "_epreuve_nexus_agent", _root / "scripts" / "nexus_agent.py"
)
if _spec is None or _spec.loader is None:  # pragma: no cover
    raise ImportError("Impossible de charger le module nexus_agent")
module = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = module
_spec.loader.exec_module(module)  # type: ignore[attr-defined]

# ----------------------------------------------------------------------
# Faux appelant utilisé par les tests
# ----------------------------------------------------------------------
VIDE: Dict[str, Any] = {
    "texte": "",
    "tronque": True,
    "cause_vide": "raisonnement_21535",
    "tokens": 5000,
    "adresse": "https://ollama.com",
    "servi_par": "ollama_chat/faux",
}
PLEIN: Dict[str, Any] = {
    "texte": "391",
    "tronque": False,
    "cause_vide": "contenu_present",
    "tokens": 3,
    "adresse": "https://ollama.com",
    "servi_par": "ollama_chat/faux",
}


class FauxAppeler:
    def __init__(self, reponses: List[Dict[str, Any]]):
        self._reponses = list(reponses)
        self.appels: List[Tuple[str, int, bool]] = []

    def __call__(
        self,
        modele: str,
        messages: List[Dict[str, Any]],
        max_tokens: int,
        cle: str,
        temperature: Any = None,
        delai: Any = None,
        outils: Any = None,
        sans_raisonnement: bool = False,
        **_: Any,
    ) -> Dict[str, Any]:
        self.appels.append((modele, max_tokens, bool(sans_raisonnement)))
        if not self._reponses:
            # répéter la dernière réponse si la liste est épuisée
            return self._reponses[-1].copy()
        resp = self._reponses.pop(0)
        return resp.copy()


def jouer(
    module: Any,
    reponses: List[Dict[str, Any]],
    **extra_tache: Any,
) -> Tuple[Dict[str, Any], List[Tuple[str, int, bool]]]:
    faux = FauxAppeler(reponses)
    original_appeler = getattr(module, "appeler", None)
    original_cache = getattr(module, "_cache_plans", None)
    original_replis = getattr(module, "replis_gratuits", None)
    try:
        module.appeler = faux
        module._cache_plans = {"faux-cloud": "cloud"}
        module.replis_gratuits = lambda cle: []  # type: ignore[assignment]
        tache = {
            "nom": "t",
            "modele": "faux-cloud",
            "tache": "Combien font 17 fois 23 ?",
            "max_tokens": 5000,
            "sans_repli": True,
        }
        tache.update(extra_tache)
        resultat = module.executer(tache, "cle-factice")
        return resultat, faux.appels
    finally:
        if original_appeler is not None:
            module.appeler = original_appeler
        else:
            delattr(module, "appeler")
        if original_cache is not None:
            module._cache_plans = original_cache
        else:
            if hasattr(module, "_cache_plans"):
                delattr(module, "_cache_plans")
        if original_replis is not None:
            module.replis_gratuits = original_replis
        else:
            if hasattr(module, "replis_gratuits"):
                delattr(module, "replis_gratuits")


# ----------------------------------------------------------------------
# Exécution des cas de test
# ----------------------------------------------------------------------
def _affiche_ok(nom: str, mesure: str) -> None:
    print(f"[OK  ] {nom} : {mesure}")


def _affiche_rate(nom: str, mesure: str) -> None:
    print(f"[RATE] {nom} : {mesure}")


total = 0
rate = 0

# C1 – Contre‑épreuve (signature)
total += 1
try:
    params = inspect.signature(module.appeler).parameters
    if "sans_raisonnement" not in params:
        raise AssertionError(f"Paramètre manquant, signature = {list(params)}")
    _affiche_ok("C1", "signature correcte")
except Exception as exc:  # pragma: no cover
    rate += 1
    _affiche_rate("C1", str(exc))

# R1 – Réponse vide puis pleine
total += 1
try:
    resultat, appels = jouer(module, [VIDE, PLEIN])
    if resultat.get("texte") != "391":
        raise AssertionError("Texte attendu absent")
    if "relance_sans_raisonnement" not in resultat:
        raise AssertionError("Clé relance_sans_raisonnement manquante")
    if [a[2] for a in appels] != [False, True]:
        raise AssertionError(f"Valeurs sans_raisonnement = {[a[2] for a in appels]}")
    _affiche_ok("R1", "comportement attendu")
except Exception as exc:  # pragma: no cover
    rate += 1
    _affiche_rate("R1", str(exc))

# R2 – Deux réponses vides
total += 1
try:
    resultat, appels = jouer(module, [VIDE, VIDE])
    if resultat.get("texte"):
        raise AssertionError("Texte non vide alors qu’il doit être vide")
    if "erreur" not in resultat:
        raise AssertionError("Clé erreur attendue absente")
    if len(appels) != 2:
        raise AssertionError(f"Nombre d’appels = {len(appels)}")
    if [a[2] for a in appels] != [False, True]:
        raise AssertionError("Ordre sans_raisonnement incorrect")
    _affiche_ok("R2", "comportement attendu")
except Exception as exc:  # pragma: no cover
    rate += 1
    _affiche_rate("R2", str(exc))

# R3 – Tâche déjà marquée sans_raisonnement
total += 1
try:
    resultat, appels = jouer(module, [PLEIN], sans_raisonnement=True)
    if len(appels) != 1:
        raise AssertionError(f"Appels attendus = 1, obtenus = {len(appels)}")
    if not appels[0][2]:
        raise AssertionError("sans_raisonnement doit être True")
    if "relance_sans_raisonnement" in resultat:
        raise AssertionError("Clé relance_sans_raisonnement ne doit pas apparaître")
    _affiche_ok("R3", "comportement attendu")
except Exception as exc:  # pragma: no cover
    rate += 1
    _affiche_rate("R3", str(exc))

# R4 – Fuite de relance (seuil)
total += 1
try:
    resultat, appels = jouer(module, [VIDE, PLEIN], max_tokens=1000)
    for _modele, max_tok, sans_r in appels:
        if sans_r and max_tok < getattr(module, "SEUIL_RAISONNEMENT", 0):
            raise AssertionError(
                f"Appel sous le seuil : max_tokens={max_tok}, sans_raisonnement={sans_r}"
            )
    _affiche_ok("R4", "aucune fuite détectée")
except Exception as exc:  # pragma: no cover
    rate += 1
    _affiche_rate("R4", str(exc))

# R5 – Fuite réseau (passerelle)
total += 1
try:
    if getattr(module, "PASSERELLE", None) != "http://127.0.0.1:9":
        raise AssertionError(
            f"PASSERELLE = {getattr(module, 'PASSERELLE', None)}"
        )
    _affiche_ok("R5", "PASSERELLE correctement isolée")
except Exception as exc:  # pragma: no cover
    rate += 1
    _affiche_rate("R5", str(exc))

print(f"{total} cas, {rate} RATE")
sys.exit(1 if rate else 0)
