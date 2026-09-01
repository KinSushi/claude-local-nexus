# -*- coding: utf-8 -*-
"""
Genere le fichier PROGRESS.MD a la racine du depot.

Ce script repond a l'ordre de l'operateur : "je te conseille aussi de maintenir 
PROGRESS.MD pour savoir OU tu en es dans le projet". Il respecte l'interdiction 
de repondre de memoire : "tu ne peux pas agir et repondre de memoire. IMPOSSIBLE. 
C'est NON NEGOCIABLE". 

Le contenu est entierement derive de l'etat reel du depot : mesures git, 
analyse statique des scripts, lecture de checklists et interrogation du 
planificateur de taches Windows.

Ce qu'il ne sait pas mesurer : l'intention, la qualite du code ou l'etat 
psychologique du developpeur.

LIMITE : Ce fichier est une photographie instantanee. Il porte un horodatage 
car une photo n'est pas fausse, mais elle est datee.
"""

import os
import sys
import subprocess
import re
import datetime
import tempfile

def main():
    # Racine derivee de __file__
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    scripts_dir = os.path.join(root_dir, "scripts")
    progress_path = os.path.join(root_dir, "PROGRESS.MD")
    
    lines = []
    
    # UN : Entete
    now = datetime.datetime.now().isoformat()
    script_name = os.path.basename(__file__)
    lines.append("# PROGRESS.MD")
    lines.append(f"*GENERE AUTOMATIQUEMENT le {now} par {script_name}*")
    lines.append("*AVERTISSEMENT : Toute edition manuelle sera ecrasee.*\n")

    # DEUX : Etat du depot
    lines.append("## ETAT DU DEPOT")
    try:
        branch = subprocess.check_output(["git", "rev-parse", "--abbrev-ref", "HEAD"], 
                                         cwd=root_dir, stderr=subprocess.DEVNULL, encoding='utf-8').strip()
        status = subprocess.check_output(["git", "status", "--porcelain"], 
                                        cwd=root_dir, stderr=subprocess.DEVNULL, encoding='utf-8').strip()
        uncommitted = len(status.splitlines()) if status else 0
        commits = subprocess.check_output(["git", "log", "-n", "5", "--oneline"], 
                                           cwd=root_dir, stderr=subprocess.DEVNULL, encoding='utf-8').strip()
        
        lines.append(f"- Branche : {branch}")
        lines.append(f"- Fichiers non commites : {uncommitted}")
        lines.append("- Derniers commits :")
        for c in commits.splitlines():
            lines.append(f"  - {c}")
    except Exception:
        lines.append("- Git non disponible ou erreur de lecture du depot.")
    lines.append("")

    # TROIS : Mecanismes
    lines.append("## MECANISMES")
    try:
        all_scripts = os.listdir(scripts_dir)
        nexus_count = len([f for f in all_scripts if f.startswith("nexus_")])
        epreuve_count = len([f for f in all_scripts if f.startswith("epreuve_")])
        
        # Regex pour choices dans nexus_test.py
        test_file_path = os.path.join(scripts_dir, "nexus_test.py")
        choices_count = 0
        if os.path.exists(test_file_path):
            with open(test_file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                match = re.search(r"choices=\[(.*?)\]", content, re.DOTALL)
                if match:
                    # On compte les elements quotes dans la liste
                    choices_count = len(re.findall(r"['\"].*?['\"]", match.group(1)))
        
        lines.append(f"- Scripts nexus_ : {nexus_count}")
        lines.append(f"- Scripts epreuve_ : {epreuve_count}")
        lines.append(f"- Options --only (nexus_test.py) : {choices_count}")
    except Exception as e:
        lines.append(f"- Erreur mesure mecanismes : {e}")
    lines.append("")

    # QUATRE : Sujets Ouverts
    lines.append("## SUJETS OUVERTS")
    try:
        checklist_path = os.path.join(root_dir, "rituels", "CHECKLIST_COCKPIT.MD")
        if os.path.exists(checklist_path):
            with open(checklist_path, 'r', encoding='utf-8') as f:
                content = f.read()
                sections = re.split(r'(^#+ .*)$', content, flags=re.MULTILINE)
                
                open_count = 0
                last_title = "Inconnu"
                
                for i in range(len(sections)):
                    if sections[i].startswith('#'):
                        last_title = sections[i].strip('# ').strip()
                        # Si le titre contient "ouvert", on compte les lignes de tableau dans la section suivante
                        if "ouvert" in sections[i].lower() and i + 1 < len(sections):
                            body = sections[i+1]
                            # Lignes de tableau commencent souvent par |
                            open_count += len([l for l in body.splitlines() if l.strip().startswith('|') and '---' not in l])
                
                lines.append(f"- Sujets ouverts : {open_count}")
                lines.append(f"- Dernier etat : {last_title}")
        else:
            lines.append("- CHECKLIST_COCKPIT.MD introuvable.")
    except Exception as e:
        lines.append(f"- Erreur lecture checklist : {e}")
    lines.append("")

    # CINQ : Taches Planifiees
    lines.append("## TACHES PLANIFIEES")
    if os.name == 'nt':
        try:
            cmd = 'powershell -NoProfile -NonInteractive -Command "Get-ScheduledTask | Where-Object { $_.TaskName -match \'Nexus\' -or $_.TaskName -match \'Claude\' } | Select-Object TaskName, State | ConvertTo-Json"'
            res = subprocess.check_output(cmd, shell=True, stderr=subprocess.DEVNULL, encoding='utf-8')
            if not res.strip():
                lines.append("- Aucune tache Nexus/Claude trouvee.")
            else:
                import json
                data = json.loads(res)
                tasks = data if isinstance(data, list) else [data]
                for t in tasks:
                    lines.append(f"- {t.get('TaskName')}: {t.get('State')}")
        except Exception as e:
            lines.append(f"- Mesure impossible : {e}")
    else:
        lines.append("- Mesure impossible (plateforme non Windows).")
    lines.append("")

    # SIX : Non Mecanise
    lines.append("## CE QUI N'EST PAS MECANISE")
    try:
        nexus_scripts = [f for f in os.listdir(scripts_dir) if f.startswith("nexus_") and f != script_name]
        non_mecanise = []
        
        # Fichiers a scanner pour references
        scan_files = []
        for f in os.listdir(scripts_dir):
            if f.endswith(".py") and f != script_name:
                scan_files.append(os.path.join(scripts_dir, f))
        
        settings_json = os.path.join(root_dir, ".claude", "settings.json")
        if os.path.exists(settings_json):
            scan_files.append(settings_json)

        for ns in nexus_scripts:
            found = False
            for sf in scan_files:
                # On ignore les tests pour la definition de "mecanise"
                if "nexus_test.py" in sf: continue 
                try:
                    with open(sf, 'r', encoding='utf-8', errors='ignore') as f:
                        if ns in f.read():
                            found = True
                            break
                except: pass
            if not found:
                non_mecanise.append(ns)
        
        if non_mecanise:
            for nm in non_mecanise:
                lines.append(f"- {nm}")
        else:
            lines.append("- Tout est mecanise.")
    except Exception as e:
        lines.append(f"- Erreur analyse mecanisation : {e}")

    # Ecriture atomique
    try:
        with tempfile.NamedTemporaryFile('w', dir=root_dir, delete=False, encoding='utf-8') as tf:
            tf.write("\n".join(lines))
            temp_name = tf.name
        os.replace(temp_name, progress_path)
        return 0
    except Exception:
        return 1

if __name__ == "__main__":
    sys.exit(main())
