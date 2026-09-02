import sys
import os
import json
import shutil
import glob
import datetime
import tempfile

TARGET_PATH = os.environ.get('NEXUS_SETTINGS_PATH', os.path.join(os.environ['USERPROFILE'], '.claude', 'settings.json'))
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
        raise Exception("Fichier settings introuvable") from None
    except json.JSONDecodeError:
        raise Exception("JSON invalide") from None
    except Exception as e:
        raise Exception(f"Erreur lecture: {e}") from e

def atomic_save_settings(data):
    """Écrit atomiquement : fichier temporaire dans le même répertoire, validation, puis os.replace."""
    directory = os.path.dirname(TARGET_PATH)
    try:
        # Créer un fichier temporaire dans le même répertoire
        fd, temp_path = tempfile.mkstemp(dir=directory, suffix='.tmp')
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        # Relecture pour valider le JSON
        with open(temp_path, 'r', encoding='utf-8') as f:
            json.load(f)
        # Remplacement atomique
        os.replace(temp_path, TARGET_PATH)
    except Exception as e:
        # Nettoyer le fichier temporaire en cas d'échec
        if 'temp_path' in locals() and os.path.exists(temp_path):
            os.unlink(temp_path)
        raise Exception(f"Erreur écriture atomique: {e}") from e

def backup():
    timestamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    backup_path = f"{TARGET_PATH}.avant_hook_{timestamp}"
    try:
        shutil.copy2(TARGET_PATH, backup_path)
        return backup_path
    except Exception as e:
        raise Exception(f"Echec sauvegarde: {e}") from e

def restore_latest_backup():
    backups = sorted(glob.glob(BACKUP_PATTERN))
    if not backups:
        raise Exception("Aucune sauvegarde trouvée")
    latest = backups[-1]
    try:
        shutil.copy2(latest, TARGET_PATH)
        return latest
    except Exception as e:
        raise Exception(f"Echec restauration: {e}") from e

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
                    break
    except Exception:
        pass
    return groups

def find_groups_by_matcher_and_command(settings, matcher, command_substring):
    """Retourne les groupes ayant le matcher exact et contenant command_substring dans un hook."""
    groups = []
    try:
        pretooluse = settings.get('hooks', {}).get('PreToolUse', [])
        if not isinstance(pretooluse, list):
            return groups
        for group in pretooluse:
            if not isinstance(group, dict):
                continue
            if group.get('matcher') != matcher:
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
                    break
    except Exception:
        pass
    return groups

def snapshot_hooks(settings):
    """Retourne une liste de tuples (matcher, command) pour tous les hooks PreToolUse existants."""
    snapshot = []
    try:
        pretooluse = settings.get('hooks', {}).get('PreToolUse', [])
        if not isinstance(pretooluse, list):
            return snapshot
        for group in pretooluse:
            if not isinstance(group, dict):
                continue
            matcher = group.get('matcher', '')
            hooks = group.get('hooks', [])
            if not isinstance(hooks, list):
                continue
            for hook in hooks:
                if not isinstance(hook, dict):
                    continue
                command = hook.get('command', '')
                if isinstance(command, str):
                    snapshot.append((matcher, command))
    except Exception:
        pass
    return snapshot

def verify_hooks_preserved(settings, snapshot):
    """Vérifie que tous les hooks de la snapshot existent toujours."""
    current = snapshot_hooks(settings)
    # On compare en tant qu'ensembles (l'ordre n'importe pas)
    return set(snapshot) == set(current)

def process_armer(guard_script_name, matcher, simulate=False):
    """Arme le garde spécifié comme hook PreToolUse. Retourne (code, messages)."""
    messages = []
    script_dir = os.path.dirname(os.path.abspath(__file__))
    guard_path = os.path.join(script_dir, guard_script_name)

    # 1. Vérifier que le script de garde existe
    if not os.path.isfile(guard_path):
        log_rate("Existence", f"Script de garde introuvable : {guard_path}")
        return 1, messages

    # 2. Vérifier si déjà armé (avant de charger les settings pour éviter une lecture inutile)
    guard_filename = os.path.basename(guard_script_name)
    try:
        settings = load_settings()
        existing_groups = find_groups_by_command(settings, guard_filename)
        if existing_groups:
            existing_matcher = existing_groups[0].get('matcher', 'inconnu')
            log_rate("Déjà armé", f"Le garde {guard_filename} est déjà armé avec le matcher '{existing_matcher}'")
            return 1, messages
    except Exception as e:
        log_rate("Chargement", str(e))
        return 1, messages

    # 4. Snapshot des hooks existants
    hooks_snapshot = snapshot_hooks(settings)

    # 5. Créer le nouveau groupe
    command = f'python "{guard_path}"'
    new_group = {
        "matcher": matcher,
        "hooks": [
            {
                "type": "command",
                "command": command
            }
        ]
    }

    if simulate:
        messages.append(f"Le garde {guard_script_name} serait armé avec le matcher '{matcher}'")
        for msg in messages:
            print(f"[OK  ] Simulation : {msg}")
        return 0, messages

    # 6. Ajouter le groupe aux settings
    if 'hooks' not in settings:
        settings['hooks'] = {}
    if 'PreToolUse' not in settings['hooks']:
        settings['hooks']['PreToolUse'] = []
    settings['hooks']['PreToolUse'].append(new_group)

    # 7. Sauvegarde avant écriture
    try:
        backup_path = backup()
        messages.append(f"Sauvegarde créée : {backup_path}")
    except Exception as e:
        log_rate("Sauvegarde", str(e))
        return 1, messages

    # 8. Écriture atomique
    try:
        atomic_save_settings(settings)
        messages.append("Fichier settings mis à jour")
    except Exception as e:
        log_rate("Écriture", str(e))
        return 1, messages

    # 9. Vérification après écriture
    try:
        verify_settings = load_settings()
        # Vérifier que le nouveau hook est présent
        new_groups = find_groups_by_matcher_and_command(verify_settings, matcher, guard_script_name)
        if len(new_groups) != 1:
            log_rate("Vérification", "Le nouveau hook n'est pas présent après écriture")
            restore_latest_backup()
            return 2, messages
        # Vérifier que tous les hooks préexistants sont toujours là
        if not verify_hooks_preserved(verify_settings, hooks_snapshot):
            log_rate("Vérification", "Des hooks préexistants ont disparu après écriture")
            restore_latest_backup()
            return 2, messages
        log_ok("Vérification", "Nouveau hook présent et hooks préexistants conservés")
    except Exception as e:
        log_rate("Vérification", str(e))
        try:
            restore_latest_backup()
        except Exception as restore_e:
            log_rate("Restauration", str(restore_e))
        return 2, messages

    # Succès
    for msg in messages:
        print(f"[OK  ] {msg}")
    print("REDÉMARRER LA SESSION : les permissions mordent tout de suite, les hooks non")
    return 0, messages

def process_restaurer():
    try:
        backups = sorted(glob.glob(BACKUP_PATTERN))
        if not backups:
            raise Exception("Aucune sauvegarde trouvée")
        latest = backups[-1]

        # Lecture et affichage du contenu de la sauvegarde
        try:
            with open(latest, 'r', encoding='utf-8') as f:
                backup_settings = json.load(f)
            log_ok("Sauvegarde à restaurer", f"{latest}")
            guards = find_groups_by_command(backup_settings, "nexus_garde_")
            if guards:
                log_ok("Gardes dans la sauvegarde", ", ".join(g['matcher'] for g in guards))
            else:
                log_ok("Gardes dans la sauvegarde", "Aucun garde actif")
        except Exception as e:
            log_rate("Lecture sauvegarde", f"Impossible de lire le contenu: {e}")

        # Restauration
        current_settings = load_settings()
        current_guards = find_groups_by_command(current_settings, "nexus_garde_")
        shutil.copy2(latest, TARGET_PATH)
        log_ok("Restauration", f"Sauvegarde restaurée : {latest}")

        # Vérification post-restauration
        restored_settings = load_settings()
        restored_guards = find_groups_by_command(restored_settings, "nexus_garde_")
        if set(g['matcher'] for g in current_guards) != set(g['matcher'] for g in restored_guards):
            removed = set(g['matcher'] for g in current_guards) - set(g['matcher'] for g in restored_guards)
            if removed:
                log_rate("Gardes retirés", f"Attention: {', '.join(removed)}")
        return 0
    except Exception as e:
        log_rate("Restauration", str(e))
        return 1

def usage():
    print("Usage: python nexus_armer_garde.py <script_garde> <matcher> [--simulation|--armer|--restaurer]")
    print("  script_garde : nom du script de garde (sans répertoire), ex: nexus_garde_ecriture.py")
    print("  matcher      : chaîne de matcher, ex: Bash|PowerShell")
    print("  --simulation : affiche les actions sans écrire")
    print("  --armer      : applique l'armement")
    print("  --restaurer  : restaure la dernière sauvegarde")

def main():
    if len(sys.argv) < 4:
        usage()
        return 64

    guard_script_name = sys.argv[1]
    matcher = sys.argv[2]
    mode = sys.argv[3]

    if mode in ('--simulation', '--armer'):
        script_dir = os.path.dirname(os.path.abspath(__file__))
        guard_path = os.path.join(script_dir, guard_script_name)
        if not os.path.isfile(guard_path):
            log_rate("Existence", f"Script de garde introuvable : {guard_path}")
            return 1
        guard_filename = os.path.basename(guard_script_name)
        try:
            settings = load_settings()
            existing_groups = find_groups_by_command(settings, guard_filename)
            if existing_groups:
                existing_matcher = existing_groups[0].get('matcher', 'inconnu')
                log_rate("Déjà armé", f"Le garde {guard_filename} est déjà armé avec le matcher '{existing_matcher}'")
                return 1
        except Exception as e:
            log_rate("Chargement", str(e))
            return 1

    if mode == '--simulation':
        code, _ = process_armer(guard_script_name, matcher, simulate=True)
        return code
    if mode == '--armer':
        code, _ = process_armer(guard_script_name, matcher, simulate=False)
        return code
    if mode == '--restaurer':
        return process_restaurer()
    usage()
    return 0

if __name__ == '__main__':
    sys.exit(main())
