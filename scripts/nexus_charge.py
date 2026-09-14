# -*- coding: utf-8 -*-
"""Vérifie si la machine est assez libre pour qu'une mesure de latence LOCALE soit interprétable.

Le besoin dérive d'une mesure erronée : une comparaison local vs cloud a été retirée
car elle a été effectuée alors que deux processus Python occupaient 1,93 cœur et
saturaient la bande passante mémoire (ressource critique pour l'inférence iGPU sans VRAM).
La mesure a été lue comme « local vs cloud » alors qu'elle était « local sous charge vs cloud ».

Un rapport entre grandeurs du même appel (ex : ratio) survit à la contention car
le ralentissement affecte le numérateur et le dénominateur. Une durée absolue, non.

Codes de sortie :
0 : Machine au repos (libre)
1 : Machine chargée
2 : Mesure impossible (verdict INCONNU)

Formule : une mesure impossible n'est PAS une mesure à zéro ; un garde qui confond
« rien trouvé » et « pas pu chercher » autorise précisément ce qu'il ne sait pas voir.
"""
import os
import sys
import subprocess
import json
import argparse
import urllib.request
import time
from datetime import datetime

# Reconfiguration de l'encodage stdout/stderr si disponible
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def _nombre(valeur, defaut=0):
    """
    Convertit *valeur* en float.
    - Si *valeur* est ``None`` ou non convertible, retourne *defaut*.
    - Sinon retourne ``float(valeur)``.
    Cette fonction pure remplace les usages de ``.get(..., 0)`` qui ne protègent
    pas contre les ``null`` JSON (ConvertTo-Json rend ``null`` pour une propriété
    inaccessible). Elle est employée partout où l'on lit une donnée numérique.
    """
    if valeur is None:
        return defaut
    try:
        return float(valeur)
    except (ValueError, TypeError):
        return defaut


def mesurer_ram() -> dict:
    """
    Mesure la RAM libre, totale et la consommation des modèles résidents.
    Retourne un dict avec les clés ``libre_go``, ``totale_go``, ``residents_go``,
    ``engagement_go``, ``total_vm`` et ``engagement_pct``.
    En cas d'échec de chaque mesure, la valeur correspondante est ``None``.
    """
    ram_libre_go = None
    ram_totale_go = None
    ram_modeles_residents_go = None
    total_vm = None
    engagement_go = None
    engagement_pct = None

    # Mesure de la RAM via PowerShell
    try:
        cmd_ram = (
            'powershell -NoProfile -NonInteractive -Command "'
            'Get-CimInstance Win32_OperatingSystem | '
            'Select-Object FreePhysicalMemory, TotalVisibleMemorySize, '
            'TotalVirtualMemorySize, FreeVirtualMemory | ConvertTo-Json"'
        )
        res_ram = subprocess.check_output(
            cmd_ram,
            shell=True,
            stderr=subprocess.DEVNULL,
            encoding='utf-8',
            errors='replace'
        )
        ram_data = json.loads(res_ram)

        # Utilisation de _nombre pour chaque champ
        ram_libre_go = _nombre(ram_data.get("FreePhysicalMemory")) / (1024 * 1024)
        ram_totale_go = _nombre(ram_data.get("TotalVisibleMemorySize")) / (1024 * 1024)
        total_vm = _nombre(ram_data.get("TotalVirtualMemorySize")) / (1024 * 1024)
        free_vm = _nombre(ram_data.get("FreeVirtualMemory")) / (1024 * 1024)

        engagement_go = total_vm - free_vm
        engagement_pct = (engagement_go / total_vm) * 100 if total_vm > 0 else 0
    except Exception as exc:
        print("mesurer_ram : subprocess.check_output impossible : %s" % exc,
              file=sys.stderr)
        pass

    # Interrogation des modèles résidents
    try:
        inference_url = os.environ.get(
            "NEXUS_INFERENCE_URL",
            "http://localhost:11434/api/ps"
        )
        with urllib.request.urlopen(inference_url, timeout=8) as response:
            modeles_data = json.loads(response.read().decode('utf-8'))

        # Normaliser en liste
        if isinstance(modeles_data, dict):
            modeles_data = modeles_data.get(
                'models',
                [modeles_data] if 'models' not in modeles_data else []
            )
        elif modeles_data is None:
            modeles_data = []

        ram_modeles_residents_go = 0.0
        for m in modeles_data:
            if isinstance(m, dict):
                taille = _nombre(m.get('size'), 0)
                ram_modeles_residents_go += taille / (1024 ** 3)
    except Exception as exc:
        print("mesurer_ram : urllib.request.urlopen impossible : %s" % exc,
              file=sys.stderr)
        ram_modeles_residents_go = None

    return {
        "libre_go": ram_libre_go,
        "totale_go": ram_totale_go,
        "residents_go": ram_modeles_residents_go,
        "engagement_go": engagement_go,
        "total_vm": total_vm,
        "engagement_pct": engagement_pct,
    }


def verdict_charge(disponible_go: float, seuil_go: float) -> tuple:
    """
    Rend (étiquette, message) : ``CHARGEE`` sous le seuil, ``LIBRE`` sinon.
    Le message porte la grandeur ET le seuil.
    """
    etiquette = "CHARGEE" if disponible_go < seuil_go else "LIBRE"
    message = "%.1f Go disponibles pour l'inférence, seuil %.1f Go" % (disponible_go, seuil_go)
    return etiquette, message


def _age_minutes(chaine, maintenant=None):
    """
    Convertit une chaîne de date en âge (minutes) de façon pure.

    1. Tente d’abord le format ISO‑8601 accepté par ``datetime.fromisoformat``.
       - Gère les offsets (ex. ``-05:00``) et les microsecondes à 6 chiffres.
       - Si la partie fractionnaire comporte 7 chiffres, on la tronque à 6 avant
         le fuseau horaire.
    2. Calcule l’écart en minutes :
       - Si la date possède un fuseau (``tzinfo``), on compare à
         ``datetime.now(datetime.timezone.utc)`` (ou à ``maintenant`` s’il est fourni).
       - Sinon on compare à ``datetime.now()`` (ou ``maintenant``).
    3. En repli, conserve les deux formats déjà supportés :
       - CIM ``yyyyMMddHHmmss.ffffff±UUU`` (on ne garde que les 14 premiers caractères).
       - JSON .NET ``/Date(ms)/``.
    4. Retourne ``None`` uniquement si toutes les tentatives échouent.
    """
    if not chaine:
        return None

    # ------------------------------------------------------------------
    # 1. Essai du format ISO‑8601
    # ------------------------------------------------------------------
    try:
        iso_str = chaine
        if isinstance(iso_str, str):
            # Séparer la partie timezone éventuelle (+/-) pour pouvoir tronquer
            # les microsecondes à 6 chiffres sans toucher au signe.
            tz_pos = max(iso_str.find('+', 10), iso_str.find('-', 10))
            if tz_pos != -1:
                base_part = iso_str[:tz_pos]
                tz_part = iso_str[tz_pos:]
            else:
                base_part = iso_str
                tz_part = ''

            # Troncature des microsecondes à 6 chiffres si nécessaire
            if '.' in base_part:
                sec, frac = base_part.split('.', 1)
                if len(frac) > 6:
                    frac = frac[:6]
                base_part = f"{sec}.{frac}"

            iso_clean = base_part + tz_part
            dt = datetime.fromisoformat(iso_clean)

            # 2. Calcul de l’âge en minutes
            if dt.tzinfo is not None:
                now = maintenant or datetime.now(datetime.timezone.utc)
            else:
                now = maintenant or datetime.now()
            delta = now - dt
            return delta.total_seconds() / 60
    except Exception:
        pass

    # ------------------------------------------------------------------
    # 3. Repli – format CIM (yyyyMMddHHmmss...)
    # ------------------------------------------------------------------
    try:
        if isinstance(chaine, str) and len(chaine) >= 14:
            dt = datetime.strptime(chaine[:14], "%Y%m%d%H%M%S")
            now = maintenant or datetime.now()
            return (now - dt).total_seconds() / 60
    except Exception:
        pass

    # ------------------------------------------------------------------
    # 3. Repli – format JSON .NET (/Date(ms)/)
    # ------------------------------------------------------------------
    try:
        if isinstance(chaine, str) and chaine.startswith("/Date("):
            ms_part = chaine[6:-2]
            ts = int(ms_part) / 1000.0
            dt = datetime.fromtimestamp(ts)
            now = maintenant or datetime.now()
            return (now - dt).total_seconds() / 60
    except Exception:
        pass

    # ------------------------------------------------------------------
    # 4. Aucun format reconnu
    # ------------------------------------------------------------------
    return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if os.name != 'nt':
        # Ce n'est pas un échec de mesure, c'est une absence de besoin
        print("Plateforme non Windows : diagnostic ignoré")
        return 0

    try:
        # Paramètres d'environnement
        cpu_seuil_min = float(os.environ.get("NEXUS_CHARGE_SEUIL_MIN", 2))
        prive_seuil_mo = float(os.environ.get("NEXUS_CHARGE_PRIVE_MO", 1024))
        processus_surveilles = os.environ.get(
            "NEXUS_CHARGE_PROCESSUS",
            "python.exe,llama-server.exe,ollama.exe,MetaTester64.exe,pwsh.exe,node.exe"
        ).split(",")
        ram_seuil_go = float(os.environ.get("NEXUS_CHARGE_RAM_MIN", 30))

        # 1. Première interrogation des processus
        cmd_proc = (
            'powershell -NoProfile -NonInteractive -Command "'
            'Get-CimInstance Win32_Process | '
            'Select-Object ProcessId, ParentProcessId, Name, UserModeTime, KernelModeTime, '
            'WorkingSetSize, PrivatePageCount, PageFileUsage, CommandLine, CreationDate, '
            'ReadTransferCount, WriteTransferCount | ConvertTo-Json"'
        )
        res_proc = subprocess.check_output(
            cmd_proc,
            shell=True,
            stderr=subprocess.DEVNULL,
            encoding='utf-8',
            errors='replace'
        )
        procs_data_1 = json.loads(res_proc)
        if isinstance(procs_data_1, dict):
            procs_data_1 = [procs_data_1]
        elif procs_data_1 is None:
            procs_data_1 = []

        # 2. Pause d'une seconde puis deuxième relevé
        time.sleep(1)
        res_proc_2 = subprocess.check_output(
            cmd_proc,
            shell=True,
            stderr=subprocess.DEVNULL,
            encoding='utf-8',
            errors='replace'
        )
        procs_data_2 = json.loads(res_proc_2)
        if isinstance(procs_data_2, dict):
            procs_data_2 = [procs_data_2]
        elif procs_data_2 is None:
            procs_data_2 = []

        # Indexation du second relevé par ProcessId
        second_snapshot = {p.get("ProcessId"): p for p in procs_data_2}

        # 3. Mesure de la RAM
        _ram = mesurer_ram()
        ram_modeles_residents_go = _ram["residents_go"] if _ram["residents_go"] is not None else 0.0
        if _ram["residents_go"] is None:
            etat_moteur = "injoignable"
        elif ram_modeles_residents_go > 0:
            etat_moteur = "joignable_avec_modeles"
        else:
            etat_moteur = "joignable_vide"

        # Cartes auxiliaires
        pid_courant = os.getpid()
        parent_map = {p.get("ProcessId"): p.get("ParentProcessId") for p in procs_data_1}

        significatifs = []
        for p in procs_data_1:
            if p.get("Name") not in processus_surveilles:
                continue
            pid = p.get("ProcessId")
            if pid == pid_courant:
                continue

            # CPU en minutes
            cpu_total_ticks = _nombre(p.get("UserModeTime")) + _nombre(p.get("KernelModeTime"))
            cpu_min = (cpu_total_ticks / 10_000_000) / 60

            # Mémoire physique (Mo)
            mem_mo = _nombre(p.get("WorkingSetSize")) / (1024 * 1024)

            # Mémoire privée (Mo) – PrivatePageCount ou fallback PageFileUsage×1024
            prive_bytes = _nombre(p.get("PrivatePageCount"))
            if prive_bytes == 0:
                prive_bytes = _nombre(p.get("PageFileUsage")) * 1024
            prive_mo = prive_bytes / (1024 * 1024)

            # Statut du parent
            parent_pid = p.get("ParentProcessId")
            parent_statut = str(parent_pid) if parent_pid and parent_pid in parent_map else "MORT"

            # Age en minutes
            age_min = _age_minutes(p.get("CreationDate"))

            # Débits de lecture/écriture (Mo/s) entre les deux relevés
            second = second_snapshot.get(pid, {})
            read_diff = _nombre(second.get("ReadTransferCount")) - _nombre(p.get("ReadTransferCount"))
            write_diff = _nombre(second.get("WriteTransferCount")) - _nombre(p.get("WriteTransferCount"))
            lecture_mo_s = (read_diff / (1024 * 1024)) if read_diff > 0 else 0.0
            ecriture_mo_s = (write_diff / (1024 * 1024)) if write_diff > 0 else 0.0

            if cpu_min > cpu_seuil_min or prive_mo > prive_seuil_mo:
                cmd_line = p.get("CommandLine") or ""
                cmd_clean = cmd_line.replace('\r', ' ').replace('\n', ' ')
                cmd_short = cmd_clean[-60:]

                # Détermination du projet (devinette)
                cmd_lower = cmd_line.lower()
                if "sas" in cmd_lower or "sovereign" in cmd_lower:
                    projet = "SAS"
                elif "ea mt5" in cmd_lower or "rentable" in cmd_lower:
                    projet = "EA-MT5"
                elif "local-llm-docker" in cmd_lower or "nexus" in cmd_lower:
                    projet = "NEXUS"
                else:
                    projet = "?"

                significatifs.append({
                    "pid": pid,
                    "cpu_min": cpu_min,
                    "mem_mo": mem_mo,
                    "prive_mo": prive_mo,
                    "parent": parent_statut,
                    "command_line": cmd_short,
                    "projet": projet,
                    "age_min": age_min,
                    "lecture_mo_s": lecture_mo_s,
                    "ecriture_mo_s": ecriture_mo_s,
                })

        ram_libre_go = _ram["libre_go"] or 0.0
        ram_totale_go = _ram["totale_go"] or 0.0
        ram_disponible_inference_go = ram_libre_go + ram_modeles_residents_go

        # Verdict global
        raisons = []
        if significatifs:
            raisons.append("processus significatifs")
        etiquette_ram, message_ram = verdict_charge(ram_disponible_inference_go, ram_seuil_go)
        if etiquette_ram == "CHARGEE":
            raisons.append("RAM insuffisante pour l'inférence : " + message_ram)

        est_au_repos = len(raisons) == 0
        etat = 'repos' if est_au_repos else 'chargee'

        if etat_moteur == "injoignable":
            info_modeles = "modèles résidents: inconnu (moteur injoignable)"
        elif etat_moteur == "joignable_vide":
            info_modeles = "modèles résidents: 0.00 Go (moteur joignable, aucun modèle)"
        else:
            info_modeles = "modèles résidents: %.2f Go" % ram_modeles_residents_go

        verdict = (
            "machine AU REPOS (%s)" % info_modeles
            if est_au_repos else
            "machine CHARGEE : " + ", ".join(raisons) + " (%s)" % info_modeles
        )

        if args.json:
            print(json.dumps({
                "au_repos": est_au_repos,
                "etat": etat,
                "verdict": verdict,
                "processus_significatifs": significatifs,
                "ram_libre_go": ram_libre_go,
                "ram_totale_go": ram_totale_go,
                "ram_modeles_residents_go": ram_modeles_residents_go,
                "ram_disponible_inference_go": ram_disponible_inference_go,
                "criteres": {
                    "noms_processus": processus_surveilles,
                    "seuil_cpu_min": cpu_seuil_min,
                    "seuil_prive_mo": prive_seuil_mo
                },
                "engagement_go": _ram.get("engagement_go"),
                "engagement_total_go": _ram.get("total_vm"),
                "engagement_pct": _ram.get("engagement_pct"),
                "etat_moteur": etat_moteur
            }))
        else:
            print("# processus retenus : noms=%s, cpu>=%.1f min ou prive>=%.0f Mo" %
                  (",".join(processus_surveilles), cpu_seuil_min, prive_seuil_mo))
            header = ("%-10s %-15s %-15s %-10s %-10s %-6s %-6s %-6s %-15s %-60s" %
                      ("PID", "AGE (min)", "CPU (min)", "RAM (Mo)", "PRIVE (Mo)",
                       "LECT", "ECR", "PARENT", "PROJET", "COMMAND LINE"))
            print(header)
            for s in significatifs:
                print("%-10d %-15s %-15.2f %-15.2f %-10.0f %-6.2f %-6.2f %-10s %-15s %-60s" %
                      (s["pid"],
                       f"{s['age_min']:.1f}" if s["age_min"] is not None else "N/A",
                       s["cpu_min"],
                       s["mem_mo"],
                       s["prive_mo"],
                       s["lecture_mo_s"],
                       s["ecriture_mo_s"],
                       s["parent"],
                       s["projet"],
                       s["command_line"]))

            if etat_moteur == "injoignable":
                print("\nRAM Libre: %.2f Go / Modèles résidents: inconnu / Disponible pour inference: %.2f Go / Totale: %.2f Go" %
                      (ram_libre_go, ram_disponible_inference_go, ram_totale_go))
            else:
                print("\nRAM Libre: %.2f Go / Modèles résidents: %.2f Go / Disponible pour inference: %.2f Go / Totale: %.2f Go" %
                      (ram_libre_go, ram_modeles_residents_go, ram_disponible_inference_go, ram_totale_go))
            if _ram.get("engagement_go") is not None:
                print("Engagement: %.1f / %.1f Go (%.0f %%)" %
                      (_ram["engagement_go"], _ram["total_vm"], _ram["engagement_pct"]))
            print(verdict)

        return 0 if est_au_repos else 1

    except Exception as e:
        print("Erreur lors du diagnostic : %s. Verdict INCONNU, l'appelant doit décider en connaissance de cause." % e)
        if args.json:
            print(json.dumps({
                "au_repos": False,
                "etat": "inconnu",
                "verdict": "ERREUR : mesure impossible"
            }))
        return 2


if __name__ == "__main__":
    sys.exit(main())
