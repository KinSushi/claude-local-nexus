import sys
import os
import json
import shutil
import glob
import datetime

TARGET_PATH = os.path.join(os.environ['USERPROFILE'], '.claude', 'settings.json')
BACKUP_PATTERN = TARGET_PATH + '.avant_hook_*'

def log_ok(label, detail):
    print(f"[OK  ] {label} : {detail}")

def log_rate(label, detail):
    print(f"[RATE] {label} : {detail}")

def load_settings():
    try:
        with open(TARGET_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        raise Exception("Fichier settings introuvable")
    except json.JSONDecodeError:
        raise Exception("JSON invalide")
    except Exception as e:
        raise Exception(f"Erreur lecture: {e}")

def save_settings(data):
    try:
        with open(TARGET_PATH, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        raise Exception(f"Erreur ecriture: {e}")

def backup():
    timestamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    backup_path = f"{TARGET_PATH}.avant_hook_{timestamp}"
    try:
        shutil.copy2(TARGET_PATH, backup_path)
        return backup_path
    except Exception as e:
        raise Exception(f"Echec sauvegarde: {e}")

def restore_latest_backup():
    backups = sorted(glob.glob(BACKUP_PATTERN))
    if not backups:
        raise Exception("Aucune sauvegarde trouvee")
    latest = backups[-1]
    try:
        shutil.copy2(latest, TARGET_PATH)
        return latest
    except Exception as e:
        raise Exception(f"Echec restauration: {e}")

def find_groups_by_command(settings, command_substring):
    """Retourne la liste des groupes (dict) dont un hook a une command contenant command_substring."""
    groups = []
    try:
        pretooluse = settings.get('hooks', {}).get('PreToolUse', [])
        if not isinstance(pretooluse, list):
            return groups
        for group in pretooluse:
            if not isinstance(group, dict):
                continue
            hooks = group.get('hooks', [])
            if not isinstance(hooks, list):
                continue
            for hook in hooks:
                if not isinstance(hook, dict):
                    continue
                command = hook.get('command', '')
                if isinstance(command, str) and command_substring in command:
                    groups.append(group)
                    break  # un seul hook suffit pour ce groupe
    except Exception:
        pass
    return groups

def process_armer(simulate=False):
    """Effectue les deux modifications. Retourne (code, messages)."""
    messages = []
    try:
        settings = load_settings()
    except Exception as e:
        log_rate("Chargement", str(e))
        return 1, messages

    # Modification 1 : corriger le matcher du groupe nexus_garde_agent
    agent_groups = find_groups_by_command(settings, 'nexus_garde_agent')
    if len(agent_groups) == 0:
        log_rate("Matcher", "Aucun groupe avec nexus_garde_agent trouve")
        return 1, messages
    if len(agent_groups) > 1:
        names = []
        for g in agent_groups:
            # essayer d'obtenir un identifiant, sinon index
            matcher = g.get('matcher', '?')
            names.append(f"matcher={matcher}")
        log_rate("Matcher", f"Plusieurs groupes trouves: {', '.join(names)}")
        return 1, messages

    agent_group = agent_groups[0]
    old_matcher = agent_group.get('matcher', '')
    if old_matcher != 'Agent|Task|Workflow':
        if simulate:
            messages.append(f"Matcher serait corrige de '{old_matcher}' vers 'Agent|Task|Workflow'")
        else:
            agent_group['matcher'] = 'Agent|Task|Workflow'
            messages.append(f"Matcher corrige de '{old_matcher}' vers 'Agent|Task|Workflow'")
    else:
        messages.append("Matcher deja correct")

    # Modification 2 : ajouter le hook d'isolation si absent
    isolation_groups = find_groups_by_command(settings, 'nexus_garde_isolation')
    if isolation_groups:
        messages.append("Hook d'isolation deja present, aucun ajout")
    else:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        isolation_script = os.path.join(script_dir, 'nexus_garde_isolation.py')
        command = f'python "{isolation_script}"'
        new_group = {
            "matcher": "Agent|Task|Workflow",
            "hooks": [
                {
                    "type": "command",
                    "command": command
                }
            ]
        }
        if simulate:
            messages.append("Groupe d'isolation serait ajoute")
        else:
            # s'assurer que hooks et PreToolUse existent
            if 'hooks' not in settings:
                settings['hooks'] = {}
            if 'PreToolUse' not in settings['hooks']:
                settings['hooks']['PreToolUse'] = []
            settings['hooks']['PreToolUse'].append(new_group)
            messages.append("Groupe d'isolation ajoute")

    if simulate:
        for msg in messages:
            print(f"[OK  ] Simulation : {msg}")
        return 0, messages

    # Sauvegarde avant ecriture
    try:
        backup_path = backup()
        messages.append(f"Sauvegarde creee: {backup_path}")
    except Exception as e:
        log_rate("Sauvegarde", str(e))
        return 1, messages

    # Ecriture
    try:
        save_settings(settings)
        messages.append("Fichier settings mis a jour")
    except Exception as e:
        log_rate("Ecriture", str(e))
        return 1, messages

    # Verification apres ecriture
    try:
        verify_settings = load_settings()
        # verifier matcher du groupe agent
        agent_groups_after = find_groups_by_command(verify_settings, 'nexus_garde_agent')
        if len(agent_groups_after) != 1:
            log_rate("Verification", "Groupe nexus_garde_agent introuvable apres ecriture")
            return 2, messages
        matcher_ok = agent_groups_after[0].get('matcher') == 'Agent|Task|Workflow'
        # verifier presence isolation
        isolation_after = find_groups_by_command(verify_settings, 'nexus_garde_isolation')
        isolation_ok = len(isolation_after) > 0
        if not (matcher_ok and isolation_ok):
            log_rate("Verification", f"Matcher correct: {matcher_ok}, Isolation present: {isolation_ok}")
            return 2, messages
        log_ok("Verification", "Matcher et hook d'isolation confirmes")
    except Exception as e:
        log_rate("Verification", str(e))
        return 2, messages

    # Succès
    for msg in messages:
        print(f"[OK  ] {msg}")
    print("REDEMARRER LA SESSION : les permissions mordent tout de suite, les hooks non")
    return 0, messages

def process_restaurer():
    try:
        backup_path = restore_latest_backup()
        log_ok("Restauration", f"Sauvegarde restauree: {backup_path}")
        return 0
    except Exception as e:
        log_rate("Restauration", str(e))
        return 1

def usage():
    print("Usage: python nexus_armer_hook.py [--simulation|--armer|--restaurer]")
    print("  --simulation : affiche les actions sans ecrire")
    print("  --armer       : applique les modifications")
    print("  --restaurer   : restaure la derniere sauvegarde")

def main():
    if len(sys.argv) != 2:
        usage()
        return 0

    mode = sys.argv[1]
    if mode == '--simulation':
        code, _ = process_armer(simulate=True)
        return code
    elif mode == '--armer':
        code, _ = process_armer(simulate=False)
        return code
    elif mode == '--restaurer':
        return process_restaurer()
    else:
        usage()
        return 0

if __name__ == '__main__':
    sys.exit(main())
