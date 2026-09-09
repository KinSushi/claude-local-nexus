import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / 'scripts'))
import nexus_capability as cap

profile = {
    "runnable_budget_gb": 40.0,
    "pool_budget_gb": 24.0,
    "inference_memory_gb": 48.0,
}

CONST_NAME = {
    cap.ACCEPT: "ACCEPT",
    cap.DEGRADED: "DEGRADED",
    cap.REJECT: "REJECT",
    cap.UNKNOWN: "UNKNOWN",
}

# (taille_gb, verdict attendu, libelle)
cas = [
    (0.0, cap.UNKNOWN, "poids nul = non mesure"),
    (-5.0, cap.UNKNOWN, "poids negatif = non mesure"),
    (50.0, cap.REJECT, "au-dela du runnable"),
    (40.0, cap.DEGRADED, "pile au runnable, depasse le pool"),
    (30.0, cap.DEGRADED, "entre pool et runnable"),
    (24.0, cap.ACCEPT, "pile au pool"),
    (10.0, cap.ACCEPT, "sous le pool"),
]

all_ok = True
for taille, attendu, libelle in cas:
    obtenu, motif = cap.verdict(taille, profile)
    nom_obtenu = CONST_NAME.get(obtenu, str(obtenu))
    nom_attendu = CONST_NAME.get(attendu, str(attendu))
    if obtenu == attendu:
        print("[OK  ] %s (%.1f Go) : verdict=%s" % (libelle, taille, nom_obtenu))
    else:
        all_ok = False
        print("[RATE] %s (%.1f Go) : verdict=%s, attendu %s" % (libelle, taille, nom_obtenu, nom_attendu))

sys.exit(0 if all_ok else 1)