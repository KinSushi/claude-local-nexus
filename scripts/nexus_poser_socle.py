import os
import sys
import json
import shutil
import datetime
import glob
import re

def get_repo_root():
    """Remonte depuis __file__ jusqu'au repertoire contenant scripts/."""
    current = os.path.dirname(os.path.abspath(__file__))
    while True:
        if os.path.basename(current) == 'scripts':
            return os.path.dirname(current)
        parent = os.path.dirname(current)
        if parent == current:
            return None
        current = parent

def load_json(path):
    """Charge un fichier JSON, retourne le dict ou None si erreur."""
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"[RATE] lecture de {path} : {e}")
        return None

def save_json(path, data):
    """Ecrit un dict dans un fichier JSON, retourne True si succes."""
    try:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"[RATE] ecriture de {path} : {e}")
        return False

def backup_file(path):
    """Cree une sauvegarde du fichier path vers path.avant_socle_<timestamp>.
    Retourne le chemin de sauvegarde ou None si echec."""
    timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = f"{path}.avant_socle_{timestamp}"
    try:
        if os.path.exists(path):
            shutil.copy2(path, backup_path)
        else:
            # Fichier cible inexistant : on cree une sauvegarde vide
            with open(backup_path, 'w', encoding='utf-8') as f:
                pass
        print(f"[OK  ] sauvegarde : {backup_path}")
        return backup_path
    except Exception as e:
        print(f"[RATE] sauvegarde de {path} : {e}")
        return None

def find_latest_backup(path):
    """Trouve la sauvegarde la plus recente pour un chemin donne.
    Retourne le chemin de la sauvegarde ou None si aucune."""
    pattern = f"{path}.avant_socle_*"
    backups = glob.glob(pattern)
    if not backups:
        return None
    # Trier par timestamp dans le nom (format AAAAMMJJ-HHMMSS)
    def extract_timestamp(p):
        m = re.search(r'\.avant_socle_(\d{8}-\d{6})$', p)
        return m.group(1) if m else ''
    backups.sort(key=extract_timestamp, reverse=True)
    return backups[0]

def merge_permissions(source_data, target_data):
    """Fusionne les permissions de source dans target.
    Retourne (new_target, deny_added, ask_added) ou None si erreur."""
    if not isinstance(source_data, dict) or 'permissions' not in source_data:
        print("[RATE] source invalide : cle 'permissions' absente")
        return None
    src_perms = source_data['permissions']
    if not isinstance(src_perms, dict):
        print("[RATE] source invalide : 'permissions' n'est pas un objet")
        return None
    src_deny = src_perms.get('deny', [])
    src_ask = src_perms.get('ask', [])
    if not isinstance(src_deny, list) or not isinstance(src_ask, list):
        print("[RATE] source invalide : 'deny' ou 'ask' n'est pas une liste")
        return None

    # Copie profonde de la cible existante ou creation d'un nouveau dict
    if target_data is None:
        new_target = {}
    else:
        if not isinstance(target_data, dict):
            print("[RATE] cible invalide : le fichier ne contient pas un objet JSON")
            return None
        new_target = json.loads(json.dumps(target_data))  # deep copy

    # S'assurer que 'permissions' existe dans la cible
    if 'permissions' not in new_target:
        new_target['permissions'] = {}
    target_perms = new_target['permissions']
    if not isinstance(target_perms, dict):
        print("[RATE] cible invalide : 'permissions' n'est pas un objet")
        return None

    # Fusion deny
    target_deny = target_perms.get('deny', [])
    if not isinstance(target_deny, list):
        print("[RATE] cible invalide : 'deny' n'est pas une liste")
        return None
    deny_added = []
    for rule in src_deny:
        if rule not in target_deny:
            target_deny.append(rule)
            deny_added.append(rule)
    target_perms['deny'] = target_deny

    # Fusion ask
    target_ask = target_perms.get('ask', [])
    if not isinstance(target_ask, list):
        print("[RATE] cible invalide : 'ask' n'est pas une liste")
        return None
    ask_added = []
    for rule in src_ask:
        if rule not in target_ask:
            target_ask.append(rule)
            ask_added.append(rule)
    target_perms['ask'] = target_ask

    return new_target, deny_added, ask_added

def process_target(source_path, target_path, mode):
    """Traite une cible selon le mode. Retourne un code (0,1,2)."""
    # Charger la source
    source_data = load_json(source_path)
    if source_data is None:
        return 1

    # Charger la cible existante (si elle existe)
    target_data = None
    if os.path.exists(target_path):
        target_data = load_json(target_path)
        if target_data is None:
            return 1

    if mode == '--simulation':
        # Calculer la fusion sans ecrire
        result = merge_permissions(source_data, target_data)
        if result is None:
            return 1
        new_target, deny_added, ask_added = result
        if not deny_added and not ask_added:
            print(f"[OK  ] {target_path} : aucune regle a ajouter (deja idempotent)")
        else:
            if deny_added:
                print(f"[OK  ] {target_path} : deny a ajouter : {deny_added}")
            if ask_added:
                print(f"[OK  ] {target_path} : ask a ajouter : {ask_added}")
        return 0

    elif mode == '--poser':
        # Sauvegarde avant ecriture
        backup_path = backup_file(target_path)
        if backup_path is None:
            return 1

        # Fusion
        result = merge_permissions(source_data, target_data)
        if result is None:
            return 1
        new_target, deny_added, ask_added = result

        # Ecrire la cible
        if not save_json(target_path, new_target):
            return 1

        # Afficher les ajouts
        if not deny_added and not ask_added:
            print(f"[OK  ] {target_path} : aucune regle ajoutee (deja idempotent)")
        else:
            if deny_added:
                print(f"[OK  ] {target_path} : deny ajoute : {deny_added}")
            if ask_added:
                print(f"[OK  ] {target_path} : ask ajoute : {ask_added}")

        # Verification apres pose
        # Recharger la cible
        verify_data = load_json(target_path)
        if verify_data is None:
            return 1
        # Compter les deny
        if 'permissions' not in verify_data or 'deny' not in verify_data['permissions']:
            print(f"[RATE] verification : {target_path} : cle 'permissions.deny' absente")
            return 2
        actual_deny_count = len(verify_data['permissions']['deny'])
        # Calculer l'attendu : nombre de deny apres fusion
        # On peut le calculer a partir de new_target
        expected_deny_count = len(new_target['permissions']['deny'])
        if actual_deny_count < expected_deny_count:
            print(f"[RATE] verification : {target_path} : deny compte {actual_deny_count} < attendu {expected_deny_count}")
            return 2
        else:
            print(f"[OK  ] verification : {target_path} : deny compte {actual_deny_count} (attendu {expected_deny_count})")
        return 0

    elif mode == '--restaurer':
        # Trouver la sauvegarde la plus recente
        latest_backup = find_latest_backup(target_path)
        if latest_backup is None:
            print(f"[RATE] restauration : {target_path} : aucune sauvegarde trouvee")
            return 1
        # Restaurer : copier la sauvegarde vers la cible
        try:
            shutil.copy2(latest_backup, target_path)
            print(f"[OK  ] restauration : {target_path} : restaure depuis {latest_backup}")
            return 0
        except Exception as e:
            print(f"[RATE] restauration : {target_path} : {e}")
            return 1

    else:
        print(f"[RATE] mode inconnu : {mode}")
        return 1

def main():
    if len(sys.argv) != 2:
        print("Usage : python scripts/nexus_poser_socle.py [--simulation|--poser|--restaurer]")
        return 0

    mode = sys.argv[1]
    if mode not in ('--simulation', '--poser', '--restaurer'):
        print("Usage : python scripts/nexus_poser_socle.py [--simulation|--poser|--restaurer]")
        return 0

    repo_root = get_repo_root()
    if repo_root is None:
        print("[RATE] impossible de determiner la racine du depot")
        return 1

    # Chemins des sources
    global_source = os.path.join(repo_root, 'rituels', 'A_POSER_global.json')
    local_source = os.path.join(repo_root, 'rituels', 'A_POSER_local.json')

    # Chemins des cibles
    userprofile = os.environ.get('USERPROFILE')
    if not userprofile:
        print("[RATE] variable USERPROFILE non definie")
        return 1
    global_target = os.path.join(userprofile, '.claude', 'settings.json')
    local_target = os.path.join(repo_root, '.claude', 'settings.json')

    # Traiter les deux cibles
    codes = []
    # Cible globale
    code_global = process_target(global_source, global_target, mode)
    codes.append(code_global)
    if code_global == 1:
        return 1  # anomalie, on arrete

    # Cible locale
    code_local = process_target(local_source, local_target, mode)
    codes.append(code_local)
    if code_local == 1:
        return 1

    # Si mode --poser et tout s'est bien passe, imprimer les lignes finales
    if mode == '--poser' and all(c == 0 for c in codes):
        print("a mesurer maintenant : rm -rf /tmp/temoin_socle_inexistant_2026")
        print("a mesurer maintenant : ecrire par l outil Write un fichier neuf sous un chemin couvert par une regle Write")
        print("a rejouer : python scripts/nexus_socle.py")

    # Retourner 2 si une verification a echoue
    if any(c == 2 for c in codes):
        return 2
    return 0

if __name__ == '__main__':
    sys.exit(main())
