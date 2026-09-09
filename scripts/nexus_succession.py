#!/usr/bin/env python3
import argparse
import sys

def _order_for_sensitivity(sens):
    """Return the preference order list for a given sensitivity."""
    if sens in ("L0", "L1"):
        return ["opus", "fable", "cloud", "local"]
    if sens == "L2":
        return ["opus", "fable", "local"]
    if sens == "L3":
        return ["local"]
    # unknown sensitivity
    return ["opus", "fable", "cloud", "local"]

_ROLE_MAP = {
    "opus": "orchestrateur premium (Claude)",
    "fable": "orchestrateur premium (Claude)",
    "cloud": "le banc orchestre et execute (boucle locale)",
    "local": "le banc orchestre et execute (boucle locale)",
}

def decider(disponibilites, sensibilite="L1"):
    """
    Pure decision function.

    disponibilites: dict with keys "opus", "fable", "cloud", "local" -> bool.
    sensibilite: "L0", "L1", "L2", "L3".
    Returns dict {"niveau": str or None, "role": str, "raison": str}.
    """
    sens = sensibilite if sensibilite in ("L0", "L1", "L2", "L3") else "L1"
    order = _order_for_sensitivity(sens)

    # Build reason components
    unavailable = []
    chosen = None

    for level in order:
        # local defaults to True if key missing
        available = disponibilites.get(level, level == "local")
        if available:
            chosen = level
            break
        unavailable.append(level)

    if chosen is None:
        raison = "aucun niveau disponible pour sensibilite {}".format(sensibilite)
        return {"niveau": None, "role": "aucun", "raison": raison}

    # Determine role
    role = _ROLE_MAP.get(chosen, "inconnu")

    # Build reason string
    if sensibilite not in ("L0", "L1", "L2", "L3"):
        base = "sensibilite inconnue '{}', traite comme L1".format(sensibilite)
    else:
        base = ""

    if not unavailable:
        # first in order is available
        if base:
            raison = "{} -> choix direct: {}".format(base, chosen)
        else:
            raison = "choix direct: {}".format(chosen)
    else:
        parts = ["{} epuise".format(lvl) for lvl in unavailable]
        transition = " -> {} prend le relais".format(chosen)
        raison = ", ".join(parts) + transition
        if base:
            raison = base + " ; " + raison

    return {"niveau": chosen, "role": role, "raison": raison}


def disponibilites_depuis_pouls(pouls_vivant, cloud_ok=True, local_ok=True):
    """
    Mappe le signal de presence Claude vers le dict de disponibilites de decider.
    pouls_vivant (bool): la session Claude est-elle vivante (pouls frais) ?
      -> opus et fable sont disponibles si et seulement si Claude est vivant.
    cloud_ok, local_ok (bool): disponibilite du banc (defaut True, optimiste ;
      le raffinement par disjoncteur viendra).
    Retourne {"opus": pouls_vivant, "fable": pouls_vivant, "cloud": cloud_ok, "local": local_ok}.
    """
    return {
        "opus": pouls_vivant,
        "fable": pouls_vivant,
        "cloud": cloud_ok,
        "local": local_ok,
    }


def plan_disponible(plans, est_dispo, plan_cible):
    # Au moins un alias du plan cible est-il disponible ?
    # est_dispo: callable(alias) -> bool (ex: CircuitBreaker.is_available).
    return any(est_dispo(alias) for alias, plan in plans.items() if plan == plan_cible)


def collecter_banc():
    # Disponibilite reelle de cloud et local via la passerelle et le disjoncteur.
    # Degrade en (True, True, True) si la passerelle est indisponible : dans ce cas
    # cloud et local sont supposes disponibles (optimiste) plutot que de bloquer.
    try:
        import nexus_agent
        import nexus_disjoncteur
        plans = nexus_agent.plans_par_alias(nexus_agent.cle_maitre())
        dj = nexus_disjoncteur.CircuitBreaker()
        cloud_ok = plan_disponible(plans, dj.is_available, "cloud")
        local_ok = plan_disponible(plans, dj.is_available, "local")
        return (cloud_ok, local_ok, False)
    except Exception:
        return (True, True, True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Diagnostic de la politique de succession de l'orchestrateur."
    )
    parser.add_argument("--opus-epuise", action="store_true", help="Marquer opus comme indisponible")
    parser.add_argument("--fable-epuise", action="store_true", help="Marquer fable comme indisponible")
    parser.add_argument("--cloud-epuise", action="store_true", help="Marquer cloud comme indisponible")
    parser.add_argument("--local-epuise", action="store_true", help="Marquer local comme indisponible")
    parser.add_argument(
        "--sensibilite",
        choices=["L0", "L1", "L2", "L3"],
        default="L1",
        help="Niveau de sensibilite (defaut L1)",
    )
    parser.add_argument(
        "--reel",
        action="store_true",
        help="Lire l'etat reel (pouls de presence Claude) au lieu des flags",
    )
    parser.add_argument(
        "--seuil",
        type=float,
        default=900.0,
        help="fraicheur du pouls en secondes",
    )
    args = parser.parse_args()

    if args.reel:
        # Lecture du pouls reel de presence Claude
        import time
        import nexus_pouls

        pouls = nexus_pouls.lire(nexus_pouls._chemin_defaut())
        vivant = nexus_pouls.est_vivant(pouls, time.time(), args.seuil)
        cloud_ok, local_ok, degrade = collecter_banc()
        disponibilites = disponibilites_depuis_pouls(vivant, cloud_ok, local_ok)
        if degrade:
            print("(banc non mesure : passerelle indisponible, cloud/local supposes disponibles)")
        print("Pouls Claude :", "VIVANT" if vivant else "MORT")
    else:
        disponibilites = {
            "opus": not args.opus_epuise,
            "fable": not args.fable_epuise,
            "cloud": not args.cloud_epuise,
            "local": not args.local_epuise,
        }

    result = decider(disponibilites, sensibilite=args.sensibilite)

    print("Niveau choisi :", result["niveau"])
    print("Role           :", result["role"])
    print("Raison         :", result["raison"])

    sys.exit(0 if result["niveau"] is not None else 1)