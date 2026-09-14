import os
import sys

# Ajouter le dossier scripts au chemin de recherche des modules
dossier_scripts = os.path.join(os.path.dirname(__file__), '../scripts')
sys.path.insert(0, dossier_scripts)

import nexus_agent


def verifier_cas(nom, condition):
    if condition:
        print(f"[OK] {nom}")
        return True
    print(f"[RATE] {nom}")
    return False

def main():
    tous_ok = True

    # Cas 1
    resultat1 = nexus_agent.composer_systeme(None, False)
    condition1 = (resultat1.startswith(nexus_agent.SYSTEME_DEFAUT) and
                  'AUCUN acces au web' in resultat1)
    tous_ok &= verifier_cas("Cas 1", condition1)

    # Cas 2
    resultat2 = nexus_agent.composer_systeme('Consigne X.', False)
    condition2 = (resultat2.startswith('Consigne X.') and
                  'AUCUN acces au web' in resultat2)
    tous_ok &= verifier_cas("Cas 2", condition2)

    # Cas 3
    resultat3 = nexus_agent.composer_systeme('Consigne X.', True)
    condition3 = (resultat3 == 'Consigne X.')
    tous_ok &= verifier_cas("Cas 3", condition3)

    # Cas 4
    resultat4 = nexus_agent.composer_systeme('', False)
    condition4 = (resultat4.startswith(nexus_agent.SYSTEME_DEFAUT) and
                  'AUCUN acces au web' in resultat4)
    tous_ok &= verifier_cas("Cas 4", condition4)

    sys.exit(0 if tous_ok else 1)

if __name__ == "__main__":
    main()
