import contextlib
import os, sys, tempfile, importlib.util
from pathlib import Path

# --- Environnement requis avant tout import des modules testés ---
os.environ["NEXUS_GATEWAY"] = "http://127.0.0.1:9"
# garder le TemporaryDirectory en vie pendant toute l'exécution du script
_temp_dir_disjoncteur = tempfile.TemporaryDirectory()
os.environ["NEXUS_ETAT_DISJONCTEUR"] = _temp_dir_disjoncteur.name

# --- Chargement dynamique des modules à tester ---
_base_path = Path(__file__).resolve().parents[1]

_spec_vitrine = importlib.util.spec_from_file_location(
    "nexus_vitrine", _base_path / "outillage" / "nexus_vitrine.py"
)
nexus_vitrine = importlib.util.module_from_spec(_spec_vitrine)
_spec_vitrine.loader.exec_module(nexus_vitrine)

_spec_conformite = importlib.util.spec_from_file_location(
    "nexus_conformite", _base_path / "scripts" / "nexus_conformite.py"
)
nexus_conformite = importlib.util.module_from_spec(_spec_conformite)
_spec_conformite.loader.exec_module(nexus_conformite)

# --- Infrastructure de comptage et d'exécution des cas ---
total_cases = 0
failed_cases = 0


def run_case(nom, fonction):
    global total_cases, failed_cases
    total_cases += 1
    try:
        resultat = fonction()
        print(f"[OK  ] {nom} : {resultat!r}")
    except Exception as e:
        failed_cases += 1
        print(f"[RATE] {nom} : {type(e).__name__}: {e}")


# ----------------------------------------------------------------------
# Cas de test
# ----------------------------------------------------------------------


def C0():
    """Vérifier que la fonction journaliser_verdict existe."""
    assert hasattr(nexus_vitrine, "journaliser_verdict"), "fonction manquante"
    assert callable(nexus_vitrine.journaliser_verdict), "pas callable"
    return "presente"


def F1():
    """Écriture simple dans un répertoire logs inexistant."""
    verdict = "VERDICT : vitrine publiee (1 avertissement(s))."
    with tempfile.TemporaryDirectory() as tmp:
        racine = Path(tmp)
        nexus_vitrine.journaliser_verdict(racine, verdict)

        log_path = racine / "logs" / "vitrine.log"
        assert log_path.is_file(), "fichier de log absent"

        with log_path.open(encoding="utf-8") as f:
            lignes = f.read().splitlines()

        assert len(lignes) == 2, f"nombre de lignes attendu 2, trouvé {len(lignes)}"
        assert lignes[0].startswith("=== ") and lignes[0].endswith(" ==="), "format horodatage incorrect"
        assert lignes[1] == verdict, "verdict incorrect"

        return tuple(lignes)


def F2():
    """Vérifier la compatibilité avec etat_journal_vitrine."""
    verdict = "VERDICT : vitrine publiee (1 avertissement(s))."
    with tempfile.TemporaryDirectory() as tmp:
        racine = Path(tmp)
        nexus_vitrine.journaliser_verdict(racine, verdict)

        log_path = racine / "logs" / "vitrine.log"
        with log_path.open(encoding="utf-8") as f:
            texte = f.read()

        etat = nexus_conformite.etat_journal_vitrine(texte)
        assert etat == (1, 1, 0), f"état attendu (1,1,0), obtenu {etat}"
        return etat


def F3():
    """Deux appels successifs, vérification de l'append et du comptage."""
    verdict1 = "VERDICT : publication REFUSEE. Rien n est parti."
    verdict2 = "VERDICT : vitrine publiee (0 avertissement(s))."
    with tempfile.TemporaryDirectory() as tmp:
        racine = Path(tmp)
        nexus_vitrine.journaliser_verdict(racine, verdict1)
        nexus_vitrine.journaliser_verdict(racine, verdict2)

        log_path = racine / "logs" / "vitrine.log"
        with log_path.open(encoding="utf-8") as f:
            lignes = f.read().splitlines()

        assert len(lignes) == 4, f"nombre de lignes attendu 4, trouvé {len(lignes)}"

        texte = "\n".join(lignes) + "\n"
        etat = nexus_conformite.etat_journal_vitrine(texte)
        assert etat == (2, 1, 0), f"état attendu (2,1,0), obtenu {etat}"
        return etat


def R1():
    """Vérifier l'absence de CRLF dans le fichier binaire."""
    verdict = "VERDICT : vitrine publiee (1 avertissement(s))."
    with tempfile.TemporaryDirectory() as tmp:
        racine = Path(tmp)
        nexus_vitrine.journaliser_verdict(racine, verdict)

        log_path = racine / "logs" / "vitrine.log"
        with log_path.open("rb") as f:
            contenu = f.read()

        assert b"\r\n" not in contenu, "présence de CRLF"
        return len(contenu)


def R2():
    """Passer un chemin de fichier comme racine, aucune exception ne doit remonter."""
    verdict = "VERDICT : vitrine publiee (1 avertissement(s))."
    with tempfile.NamedTemporaryFile(delete=False) as tf:
        chemin_fichier = Path(tf.name)

    try:
        # L'appel doit être silencieux même si la création échoue
        nexus_vitrine.journaliser_verdict(chemin_fichier, verdict)
    except Exception as e:
        raise AssertionError(f"exception inattendue : {e}") from e
    finally:
        # Nettoyage du fichier temporaire
        with contextlib.suppress(Exception):
            chemin_fichier.unlink()

    return "aucune exception"


def L1():
    """Vérifier la valeur de PASSERELLE ou de la variable d'environnement."""
    if hasattr(nexus_conformite, "PASSERELLE"):
        valeur = nexus_conformite.PASSERELLE
    else:
        valeur = os.getenv("NEXUS_GATEWAY")
    assert valeur == "http://127.0.0.1:9", f"valeur inattendue {valeur}"
    return valeur


# ----------------------------------------------------------------------
# Exécution des cas
# ----------------------------------------------------------------------
run_case("C0", C0)
run_case("F1", F1)
run_case("F2", F2)
run_case("F3", F3)
run_case("R1", R1)
run_case("R2", R2)
run_case("L1", L1)

print(f"{total_cases} cas, {failed_cases} RATE")
sys.exit(1 if failed_cases > 0 else 0)
