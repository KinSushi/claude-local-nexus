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
        
        # LES CLES --only SE DERIVENT COMME nexus_test.py LES DERIVE.
        #
        # CE QUI ETAIT FAUX, mesure le 2026-09-02 : ce bloc cherchait
        # « choices=[...] », une liste litterale que nexus_test.py n'ecrit
        # pas -- il passe `choices=_choix`, variable derivee de sa propre
        # source par le motif `args.only in (None, "cle")`. Le motif ne
        # trouvait rien et PROGRESS.MD affichait « Options --only : 0 » :
        # un zero faux, pire qu'un inconnu, sur un depot qui en compte
        # plusieurs dizaines. On lit desormais le meme motif que
        # nexus_test.py (son main, variable `pattern`).
        test_file_path = os.path.join(scripts_dir, "nexus_test.py")
        choices_count = "inconnu"
        if os.path.exists(test_file_path):
            with open(test_file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            cles = re.findall(r'args\.only\s+in\s+\(None,\s*"([^"]+)"\)', content)
            choices_count = len(set(cles))
        
        lines.append(f"- Scripts nexus_ : {nexus_count}")
        lines.append(f"- Scripts epreuve_ : {epreuve_count}")
        lines.append(f"- Options --only (nexus_test.py) : {choices_count}")
    except Exception as e:
        lines.append(f"- Erreur mesure mecanismes : {e}")
    lines.append("")

    # QUATRE : Sujets Ouverts
    lines.append("## SUJETS OUVERTS")
    try:
        checklist_path = os.path.join(root_dir, "outillage", "rituels", "CHECKLIST_COCKPIT.MD")
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
                        if "ouverts actuels" in sections[i].lower() and i + 1 < len(sections):
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
    # UNE SEULE SOURCE DE VERITE : le cliquet de cablage.
    #
    # CE QUI ETAIT FAUX, mesure le 2026-09-02 : ce bloc reimplementait la
    # question « qui appelle ce script ? » avec sa propre regle (un nom cite
    # dans scripts/*.py ou settings.json, tests exclus) et rendait SIX noms,
    # quand nexus_cablage.py -- l'instrument que le contrat §0.2.1 designe
    # pour ce maillon -- en rend TREIZE : un orphelin que ce bloc ne voyait
    # pas, et un script qu'il listait a tort parce qu'il ne lisait pas les
    # .ps1 qui l'appellent. (Les noms ne sont pas ecrits ici : le cliquet
    # lit toute mention comme une citation, limite qu'il documente
    # lui-meme, et un commentaire ferait passer un orphelin pour prouve.)
    # Deux instruments, deux
    # reponses : c'est la regle de non-concurrence du rituel (« deux sources
    # de verite divergent au premier changement »). On lit donc le cliquet,
    # et une mesure impossible se DIT -- jamais « Tout est mecanise ».
    try:
        if scripts_dir not in sys.path:
            sys.path.insert(0, scripts_dir)
        import nexus_cablage
        categories = nexus_cablage.etat()["categories"]
        faibles = [(cat, os.path.basename(c))
                   for cat in ("orphelin", "preuve_seule")
                   for c in categories[cat]]
        if faibles:
            for cat, nom in faibles:
                lines.append(f"- {nom} ({cat})")
        else:
            lines.append("- Aucun script orphelin ni seulement prouve (nexus_cablage).")
    except (Exception, SystemExit) as e:
        # SystemExit : nexus_cablage sort en 2 quand git ne repond pas.
        lines.append(f"- Mesure impossible (nexus_cablage) : {e}")

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
