#!/usr/bin/env python3
"""
Outil de veille des quotas Ollama Cloud et calcul d'usage.

Lit la table LiteLLM_SpendLogs via psql dans le conteneur Docker de la passerelle.
"""

import argparse
import json
import subprocess
import sys
import typing
from datetime import datetime, timezone
from pathlib import Path

# ----------------------------------------------------------------------
# Constantes SQL (requêtes paramétrées, jamais de concaténation)
# ----------------------------------------------------------------------
SQL_ETAT = """
SELECT COUNT(*) FILTER (WHERE COALESCE(status,'success')='success'),
       COUNT(*) FILTER (WHERE (metadata::jsonb->'error_information'->>'error_message') ILIKE '%usage limit%'),
       COUNT(*) FILTER (WHERE (metadata::jsonb->'error_information'->>'error_message') ILIKE '%concurrent request slot%')
FROM "LiteLLM_SpendLogs"
WHERE "startTime" > NOW() - INTERVAL '{minutes} minutes'
AND api_base ILIKE '%ollama.com%'
"""

SQL_USAGE = """
SELECT model_group, to_char(date_trunc('hour', "startTime"),'HH24'), COUNT(*),
       COALESCE(SUM(prompt_tokens), 0),
       COALESCE(SUM(completion_tokens), 0)
FROM "LiteLLM_SpendLogs"
WHERE "startTime" >= NOW() - INTERVAL '{heures} hours'
AND api_base ILIKE '%ollama.com%'
AND COALESCE(status,'success')='success'
GROUP BY model_group, to_char(date_trunc('hour', "startTime"),'HH24')
"""

# ----------------------------------------------------------------------
# Chemin vers le fichier de tarifs JSON (déposé dans outillage/)
# ----------------------------------------------------------------------
TARIFS_PATH = Path(__file__).parent.parent / "outillage" / "tarifs_ollama_cloud.json"

# ----------------------------------------------------------------------
# Types de données
# ----------------------------------------------------------------------
class EtatQuota(typing.NamedTuple):
    """Résultat de la requête d'état."""
    reussites: int
    usage_limit: int
    concurrent_slot: int

class UsageModele(typing.NamedTuple):
    """Usage par modèle et par heure."""
    modele: str
    heure: str
    requetes: int
    prompt_tokens: int
    completion_tokens: int

# ----------------------------------------------------------------------
# Fonctions utilitaires
# ----------------------------------------------------------------------
def exec_psql(conteneur: str, utilisateur: str, base: str, requete: str) -> str:
    """Exécute une requête psql dans le conteneur Docker."""
    cmd = [
        "docker", "exec", conteneur,
        "psql", "-U", utilisateur, "-d", base,
        "-At", "-F", "|", "-c", requete
    ]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, check=True
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"psql échoué (code {e.returncode}) : {e.stderr}") from e
    except FileNotFoundError as e:
        raise RuntimeError("docker non trouvé") from e

def parse_etat(stdout: str) -> EtatQuota:
    """Parse le résultat de la requête d'état."""
    try:
        reussites, usage_limit, concurrent_slot = map(int, stdout.split("|"))
        return EtatQuota(reussites, usage_limit, concurrent_slot)
    except ValueError as e:
        raise ValueError(f"Format inattendu pour l'état : {stdout}") from e

def parse_usage(stdout: str) -> tuple[list[UsageModele], list[str]]:
    """Parse le résultat de la requête d'usage."""
    usages: list[UsageModele] = []
    erreurs: list[str] = []
    for line in stdout.splitlines():
        if not line.strip():
            continue
        try:
            parts = line.split("|")
            if len(parts) != 5:
                erreurs.append(line)
                continue
            modele, heure, requetes, prompt, completion = parts
            usages.append(
                UsageModele(
                    modele=modele,
                    heure=heure,
                    requetes=int(requetes),
                    prompt_tokens=int(prompt),
                    completion_tokens=int(completion),
                )
            )
        except ValueError:
            erreurs.append(line)
    return usages, erreurs

def charger_tarifs() -> tuple[dict[str, tuple[float, float]], datetime]:
    """Charge les tarifs depuis le fichier JSON.

    Le format attendu : {"prix": {"alias": [entree, sortie], ...}, "releve_le": "2026-09-14T14:25:00"}.
    """
    try:
        with open(TARIFS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)

        tarifs: dict[str, tuple[float, float]] = {}
        for alias, prix in data["prix"].items():
            # Le fichier de référence fournit une liste [entree, sortie]
            if isinstance(prix, list) and len(prix) >= 2:
                entree, sortie = float(prix[0]), float(prix[1])
                tarifs[alias] = (entree, sortie)
            else:
                # Structure inattendue : on ignore l'entrée
                continue

        date_releve = datetime.fromisoformat(data["releve_le"])
        return tarifs, date_releve
    except (FileNotFoundError, json.JSONDecodeError, KeyError) as e:
        raise RuntimeError(f"Fichier de tarifs invalide : {e}") from e

def calculer_cout(
    usages: list[UsageModele],
    tarifs: dict[str, tuple[float, float]],
) -> tuple[dict[str, float], dict[str, float], list[str]]:
    """Calcule le coût total par modèle et par heure, et renvoie les modèles sans tarif."""
    couts_modele: dict[str, float] = {}
    couts_heure: dict[str, float] = {}
    sans_tarif: list[str] = []

    for usage in usages:
        alias = usage.modele
        tarif = None
        if alias in tarifs:
            tarif = tarifs[alias]
        elif alias.endswith("-cloud"):
            alias_sans_suffix = alias[:-6]
            if alias_sans_suffix in tarifs:
                tarif = tarifs[alias_sans_suffix]

        if tarif is not None:
            entree, sortie = tarif
            cout = (
                (usage.prompt_tokens / 1_000_000) * entree
                + (usage.completion_tokens / 1_000_000) * sortie
            )
            couts_modele[alias] = couts_modele.get(alias, 0.0) + cout
            cle_heure = f"{alias}|{usage.heure}"
            couts_heure[cle_heure] = couts_heure.get(cle_heure, 0.0) + cout
        else:
            sans_tarif.append(alias)

    return couts_modele, couts_heure, sans_tarif

def convertir_utc_local(utc_dt: datetime) -> datetime:
    """Convertit une datetime UTC en heure locale."""
    return utc_dt.replace(tzinfo=timezone.utc).astimezone()

def formater_etat(etat: EtatQuota, json_output: bool) -> str:
    """Formate le résultat de l'état."""
    if etat.usage_limit > 0:
        statut = "EPUISE"
        code = 3
        print(statut)
        return json.dumps({"statut": statut, "code": code}) if json_output else statut
    if etat.concurrent_slot > 0:
        statut = "PLAFOND"
        code = 4
        print(statut)
        return json.dumps({"statut": statut, "code": code}) if json_output else statut
    if etat.reussites > 0:
        statut = "SAIN"
        code = 0
    else:
        statut = "MUET"
        code = 0
    print(statut)
    return json.dumps({"statut": statut, "code": code}) if json_output else statut

def formater_usage(
    couts_modele: dict[str, float],
    couts_heure: dict[str, float],
    sans_tarif: list[str],
    date_releve: datetime,
    json_output: bool,
    erreurs: list[str],
) -> str:
    """Formate le résultat de l'usage."""
    date_local = convertir_utc_local(date_releve)
    date_str = date_local.strftime("%Y-%m-%d %H:%M (heure locale)")

    if json_output:
        return json.dumps(
            {
                "cout_total": sum(couts_modele.values()),
                "couts_modele": couts_modele,
                "couts_heure": dict(sorted(couts_heure.items())),
                "sans_tarif": sans_tarif,
                "date_releve": date_str,
                "lignes_mal_formees": erreurs,
            }
        )

    lignes = [
        f"Relevé des tarifs: {date_str}",
        f"Coût total: {sum(couts_modele.values()):.2f} $",
        "Coût par heure et par modèle:",
    ]
    for cle_heure, cout in sorted(couts_heure.items()):
        modele, heure = cle_heure.split("|")
        lignes.append(f"- {modele} à {heure}h: {cout:.2f} $")
    lignes.append("Coût par modèle:")
    for modele, cout in sorted(couts_modele.items(), key=lambda x: (-x[1], x[0])):
        lignes.append(f"- {modele}: {cout:.2f} $")

    if sans_tarif:
        print(f"Modèles sans tarif: {', '.join(sans_tarif)}", file=sys.stderr)
    if erreurs:
        lignes.append(f"Lignes mal formées ({len(erreurs)}):")
        lignes.extend(f"- {e}" for e in erreurs)
    return "\n".join(lignes)

def valider_entier(val: str, min_val: int, max_val: int) -> int:
    """Valide qu'une valeur est un entier dans l'intervalle donné."""
    try:
        ival = int(val)
    except ValueError as e:
        raise argparse.ArgumentTypeError("doit être un entier") from e
    if not (min_val <= ival <= max_val):
        raise argparse.ArgumentTypeError(f"doit être entre {min_val} et {max_val}")
    return ival

# ----------------------------------------------------------------------
# Point d'entrée principal
# ----------------------------------------------------------------------
def main(argv: typing.Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)

    # Options mutuellement exclusives : --etat ou --usage (obligatoire)
    groupe = parser.add_mutually_exclusive_group(required=True)
    groupe.add_argument("--etat", action="store_true", help="Vérifie l'état des quotas")
    groupe.add_argument("--usage", action="store_true", help="Calcule l'usage en dollars")

    # Options communes
    parser.add_argument(
        "--conteneur", default="litellm-db", help="Nom du conteneur Docker (défaut: litellm-db)"
    )
    parser.add_argument(
        "--utilisateur", default="litellm_user", help="Utilisateur PostgreSQL (défaut: litellm_user)"
    )
    parser.add_argument(
        "--base", default="litellm", help="Nom de la base PostgreSQL (défaut: litellm)"
    )
    parser.add_argument(
        "--minutes",
        type=lambda x: valider_entier(x, 1, 10080),
        default=5,
        help="Nombre de minutes à considérer (défaut: 5, max: 10080)",
    )
    parser.add_argument(
        "--heures",
        type=lambda x: valider_entier(x, 1, 10080),
        default=24,
        help="Nombre d'heures à considérer (défaut: 24, max: 10080)",
    )
    parser.add_argument("--json", action="store_true", help="Sortie au format JSON")

    args = parser.parse_args(argv)

    try:
        if args.etat:
            requete = SQL_ETAT.format(minutes=args.minutes)
            stdout = exec_psql(args.conteneur, args.utilisateur, args.base, requete)
            etat = parse_etat(stdout)
            formater_etat(etat, args.json)
            if etat.usage_limit > 0:
                return 3
            if etat.concurrent_slot > 0:
                return 4
            return 0

        if args.usage:
            requete = SQL_USAGE.format(heures=args.heures)
            stdout = exec_psql(args.conteneur, args.utilisateur, args.base, requete)
            usages, erreurs = parse_usage(stdout)
            tarifs, date_releve = charger_tarifs()
            couts_modele, couts_heure, sans_tarif = calculer_cout(usages, tarifs)
            print(formater_usage(couts_modele, couts_heure, sans_tarif, date_releve, args.json, erreurs))
            return 0 if not erreurs else 1

    except argparse.ArgumentError as e:
        print(f"Erreur: {e}")
        return 2
    except RuntimeError as e:
        # Erreur liée à Docker ou à la base → code 5
        print(f"Erreur: {e}")
        return 5
    except Exception as e:
        # Toute autre erreur → code 1
        print(f"Erreur: {e}")
        return 1

    return 2

if __name__ == "__main__":
    sys.exit(main())
