# -*- coding: utf-8 -*-
"""Verifie si la machine est assez libre pour qu'une mesure de latence LOCALE soit interpretable.

Le besoin derive d'une mesure erronee : une comparaison local vs cloud a ete retiree
car elle a ete effectuee alors que deux processus Python occupaient 1,93 coeur et
saturaient la bande passante memoire (ressource critique pour l'inference iGPU sans VRAM).
La mesure a ete lue comme 'local vs cloud' alors qu'elle etait 'local sous charge vs cloud'.

Un rapport entre grandeurs du meme appel (ex: ratio) survit a la contention car
le ralentissement affecte le numerateur et le denominateur. Une duree absolue, non.

Codes de sortie :
0 : Machine au repos (libre)
1 : Machine chargee
2 : Mesure impossible (verdict INCONNU)

Formule : une mesure impossible n'est PAS une mesure a zero ; un garde qui confond 
« rien trouve » et « pas pu chercher » autorise precisement ce qu'il ne sait pas voir.
"""
import os
import sys
import subprocess
import json
import argparse
import urllib.request

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if os.name != 'nt':
        # Ce n'est pas un echec de mesure, c'est une absence de besoin
        print("Plateforme non Windows : diagnostic ignore")
        return 0

    try:
        # Seuil CPU en minutes
        cpu_seuil_min = float(os.environ.get("NEXUS_CHARGE_SEUIL_MIN", 2))
        # Seuil RAM libre en Go
        ram_seuil_go = float(os.environ.get("NEXUS_CHARGE_RAM_MIN", 30))

        # 1. Interroger les processus Python
        cmd_proc = (
            'powershell -NoProfile -NonInteractive -Command "'
            'Get-CimInstance Win32_Process | Where-Object { $_.Name -eq \'python.exe\' } | '
            'Select-Object ProcessId, UserModeTime, KernelModeTime, WorkingSetSize, CommandLine | ConvertTo-Json"'
        )
        res_proc = subprocess.check_output(cmd_proc, shell=True, stderr=subprocess.DEVNULL, encoding='utf-8', errors='replace')
        procs_data = json.loads(res_proc)
        if isinstance(procs_data, dict):
            procs_data = [procs_data]
        elif procs_data is None:
            procs_data = []

        # 2. Interroger la RAM
        cmd_ram = (
            'powershell -NoProfile -NonInteractive -Command "'
            'Get-CimInstance Win32_OperatingSystem | '
            'Select-Object FreePhysicalMemory, TotalVisibleMemorySize | ConvertTo-Json"'
        )
        res_ram = subprocess.check_output(cmd_ram, shell=True, stderr=subprocess.DEVNULL, encoding='utf-8', errors='replace')
        ram_data = json.loads(res_ram)

        # Interroger les modèles résidents du moteur d'inférence
        ram_modeles_residents_go = 0.0
        etat_moteur = "injoignable"
        inference_url = os.environ.get("NEXUS_INFERENCE_URL", "http://localhost:11434/api/ps")
        try:
            with urllib.request.urlopen(inference_url, timeout=8) as response:
                modeles_data = json.loads(response.read().decode('utf-8'))
            # Normaliser en liste
            if isinstance(modeles_data, dict):
                modeles_data = modeles_data.get('models', [modeles_data] if 'models' not in modeles_data else [])
            elif modeles_data is None:
                modeles_data = []
            
            if not modeles_data:
                etat_moteur = "joignable_vide"
            else:
                etat_moteur = "joignable_avec_modeles"
                for m in modeles_data:
                    taille = m.get('size', 0) if isinstance(m, dict) else 0
                    ram_modeles_residents_go += taille / (1024**3)
        except Exception:
            etat_moteur = "injoignable"
            ram_modeles_residents_go = 0.0

        # Filtrage et calculs
        pid_courant = os.getpid()
        
        significatifs = []
        for p in procs_data:
            pid = p.get("ProcessId")
            if pid == pid_courant:
                continue
            
            # CPU = (User + Kernel) en 100 nanosecondes
            cpu_total_ticks = p.get("UserModeTime", 0) + p.get("KernelModeTime", 0)
            cpu_min = (cpu_total_ticks / 10_000_000) / 60
            mem_mo = p.get("WorkingSetSize", 0) / (1024 * 1024)
            
            if cpu_min > cpu_seuil_min:
                cmd_line = p.get("CommandLine") or ""
                cmd_clean = cmd_line.replace('\r', ' ').replace('\n', ' ')
                cmd_short = cmd_clean[-60:]
                
                # Devinette Projet
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
                    "command_line": cmd_short,
                    "projet": projet
                })

        # RAM (valeurs en Ko)
        ram_libre_go = ram_data.get("FreePhysicalMemory", 0) / (1024 * 1024)
        ram_totale_go = ram_data.get("TotalVisibleMemorySize", 0) / (1024 * 1024)
        ram_disponible_inference_go = ram_libre_go + ram_modeles_residents_go

        # Verdict
        raison = []
        if significatifs:
            raison.append("processus significatifs")
        if ram_disponible_inference_go < ram_seuil_go:
            raison.append("RAM insuffisante pour l'inférence")

        est_au_repos = len(raison) == 0
        etat = 'repos' if est_au_repos else 'chargee'
        if etat_moteur == "injoignable":
            info_modeles = "modèles résidents: inconnu (moteur injoignable)"
        elif etat_moteur == "joignable_vide":
            info_modeles = "modèles résidents: 0.00 Go (moteur joignable, aucun modèle)"
        else:
            info_modeles = "modèles résidents: %.2f Go" % ram_modeles_residents_go
        verdict = "machine AU REPOS (%s)" % info_modeles if est_au_repos else "machine CHARGEE : " + ", ".join(raison) + " (%s)" % info_modeles

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
                "etat_moteur": etat_moteur
            }))
        else:
            print("%-10s %-15s %-15s %-10s %-60s" % ("PID", "CPU (min)", "RAM (Mo)", "PROJET", "COMMAND LINE"))
            for s in significatifs:
                print("%-10d %-15.2f %-15.2f %-10s %-60s" % (s["pid"], s["cpu_min"], s["mem_mo"], s["projet"], s["command_line"]))
            if etat_moteur == "injoignable":
                print("\nRAM Libre: %.2f Go / Modèles résidents: inconnu / Disponible pour inference: %.2f Go / Totale: %.2f Go" % (ram_libre_go, ram_disponible_inference_go, ram_totale_go))
            else:
                print("\nRAM Libre: %.2f Go / Modèles résidents: %.2f Go / Disponible pour inference: %.2f Go / Totale: %.2f Go" % (ram_libre_go, ram_modeles_residents_go, ram_disponible_inference_go, ram_totale_go))
            print(verdict)

        return 0 if est_au_repos else 1

    except Exception as e:
        print("Erreur lors du diagnostic : %s. Verdict INCONNU, l'appelant doit decider en connaissance de cause." % e)
        if args.json:
            print(json.dumps({
                "au_repos": False,
                "etat": "inconnu",
                "verdict": "ERREUR : mesure impossible"
            }))
        return 2

if __name__ == "__main__":
    sys.exit(main())