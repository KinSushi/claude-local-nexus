import os
import sys
import json
import hashlib

DEPOTS = [
    ("local-llm-docker", "C:/local-llm-docker/rituels/SOCLE_UNIVERSEL.json"),
    ("sovereign", "D:/SAS/sovereign-ai-system/v1.104/sovereign-ai-system/SOCLE_UNIVERSEL.json"),
    ("ea-mt5", "D:/EA MT5 PYTHON RENTABLE ROBUSTE/SOCLE_UNIVERSEL.json"),
]

MOTIFS = [
    'rm *',
    'filter-branch',
    'gc --prune',
    'Set-ExecutionPolicy',
    'curl * | sh',
    'cat *.env*',
    'Read(**/.env)',
]

def regles(obj):
    if not isinstance(obj, dict):
        return [], []
    source = obj.get('permissions', obj)
    if not isinstance(source, dict):
        return [], []
    deny = source.get('deny', [])
    ask = source.get('ask', [])
    if not isinstance(deny, list):
        deny = []
    if not isinstance(ask, list):
        ask = []
    return deny, ask

def lire_json(chemin):
    try:
        with open(chemin, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data, None
    except FileNotFoundError:
        return None, "fichier absent"
    except json.JSONDecodeError as e:
        return None, f"JSON illisible: {e}"
    except Exception as e:
        return None, f"erreur lecture: {e}"

def sha256_fichier(chemin):
    try:
        with open(chemin, 'rb') as f:
            contenu = f.read()
        return hashlib.sha256(contenu).hexdigest()
    except Exception:
        return None

def motif_present(motif, deny, ask):
    for regle in deny + ask:
        if motif in str(regle):
            return True
    return False

def main():
    resultats = []  # liste de (ok, libelle, detail)
    tous_ok = True

    # Controle 1: empreintes
    empreintes = {}
    absents = []
    for nom, chemin in DEPOTS:
        emp = sha256_fichier(chemin)
        if emp is None:
            absents.append(nom)
        else:
            empreintes[nom] = emp

    if absents:
        detail_absents = ", ".join(absents)
        print(f"[INFO] fichiers absents: {detail_absents}")

    if not empreintes:
        resultats.append((False, "empreintes", "aucun fichier present"))
        tous_ok = False
    elif len(empreintes) == 1:
        nom_seul = list(empreintes.keys())[0]
        emp_courte = empreintes[nom_seul][:8]
        resultats.append((True, "empreintes", f"un seul depot, rien a comparer ({nom_seul}: {emp_courte})"))
    else:
        emps = list(empreintes.values())
        if all(e == emps[0] for e in emps):
            emp_courte = emps[0][:8]
            resultats.append((True, "empreintes", f"concordance sur {len(empreintes)} depots, empreinte {emp_courte}"))
        else:
            divergents = [nom for nom, emp in empreintes.items() if emp != emps[0]]
            detail = "divergence: " + ", ".join(f"{nom} ({empreintes[nom][:8]})" for nom in divergents)
            resultats.append((False, "empreintes", detail))
            tous_ok = False

    # Controle 2: contenu
    manquants = []
    for nom, chemin in DEPOTS:
        if nom in absents:
            continue
        data, err = lire_json(chemin)
        if err:
            manquants.append(f"{nom}: lecture impossible ({err})")
            continue
        deny, ask = regles(data)
        nb_deny = len(deny)
        nb_ask = len(ask)
        for motif in MOTIFS:
            if not motif_present(motif, deny, ask):
                manquants.append(f"motif '{motif}' manquant dans {nom}")
    if manquants:
        resultats.append((False, "contenu", "; ".join(manquants)))
        tous_ok = False
    else:
        resultats.append((True, "contenu", "tous les motifs presents dans tous les fichiers presents"))

    # Controle 3: pose
    userprofile = os.environ.get('USERPROFILE')
    if not userprofile:
        resultats.append((False, "pose", "USERPROFILE non defini"))
        tous_ok = False
    else:
        settings_path = os.path.join(userprofile, '.claude', 'settings.json')
        data, err = lire_json(settings_path)
        if err:
            resultats.append((False, "pose", f"settings.json: {err}"))
            tous_ok = False
        else:
            deny, _ = regles(data)
            nb_deny = len(deny)
            if nb_deny < 50:
                resultats.append((False, "pose", f"socle non pose, {nb_deny} deny"))
                tous_ok = False
            else:
                resultats.append((True, "pose", f"{nb_deny} deny"))

    # Controle 4: structure fusionnable
    non_fusionnables = []
    for nom, chemin in DEPOTS:
        if nom in absents:
            continue
        data, err = lire_json(chemin)
        if err:
            non_fusionnables.append(f"{nom}: lecture impossible ({err})")
            continue
        if not isinstance(data, dict) or 'permissions' not in data:
            non_fusionnables.append(nom)
    if non_fusionnables:
        detail = ", ".join(non_fusionnables)
        resultats.append((False, "structure fusionnable", f"non fusionnable tel quel, envelopper deny et ask dans une cle permissions ({detail})"))
        tous_ok = False
    else:
        resultats.append((True, "structure fusionnable", "tous les fichiers presents ont la cle permissions"))

    # Controle 5: effet
    print("a jouer a la main : rm -rf /tmp/temoin_socle_inexistant_2026 -- un refus du harnais prouve que les regles mordent, un rc=0 prouve qu elles sont inertes")
    resultats.append((False, "effet", "non mesure par ce script"))
    tous_ok = False

    # Affichage des resultats
    for ok, libelle, detail in resultats:
        marqueur = "[OK  ]" if ok else "[RATE]"
        print(f"{marqueur} {libelle} : {detail}")

    # Verdict
    if tous_ok:
        print("VERDICT: OK")
        return 0
    else:
        print("VERDICT: RATE")
        return 1

if __name__ == '__main__':
    sys.exit(main())
