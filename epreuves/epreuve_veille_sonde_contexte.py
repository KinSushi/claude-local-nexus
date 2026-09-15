# -*- coding: utf-8 -*-
"""Épreuve fonctionnelle pour la fonction ``executer`` de ``nexus_veille_moteur.py``,
vérifiant la gestion du paramètre ``num_ctx`` lors de la sonde du résidant."""

import importlib.util
import json
import pathlib
import sys
import urllib.request

# mesure du 2026-09-15 : console cp1252, le signe different faisait planter un cas reussi
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

def _load_module():
    """Charge ``outillage/nexus_veille_moteur.py`` depuis la racine du dépôt."""
    base_dir = pathlib.Path(__file__).resolve().parents[1]  # repository root
    script_path = base_dir / "outillage" / "nexus_veille_moteur.py"
    spec = importlib.util.spec_from_file_location("nexus_veille_moteur", script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module, base_dir

def check(nom, condition, detail=""):
    """Affiche le résultat d’un cas de test et renvoie le booléen."""
    if condition:
        print(f"[OK  ] {nom} : {detail}")
    else:
        print(f"[RATE] {nom} : {detail}")
    return condition

def main():
    ok = True
    module, _ = _load_module()

    # Remplacement des fonctions réseau par des faux
    captured_requests = []
    def fake_urlopen(req, timeout=None):
        captured_requests.append({
            'url': req.full_url,
            'data': json.loads(req.data.decode('utf-8')) if req.data else None,
            'headers': dict(req.headers)
        })
        class FakeResponse:
            status = 200
            def read(self):
                return b'{"message": {"content": "pong"}}'
            def __enter__(self):
                return self
            def __exit__(self, *args):
                pass
        return FakeResponse()

    # Sauvegarde et remplacement de urllib.request.urlopen
    original_urlopen = urllib.request.urlopen
    urllib.request.urlopen = fake_urlopen

    # Faux pour les autres fonctions réseau
    def fake_version_repond(url):
        return True
    def fake_lire_ps(url):
        return {
            'models': [{
                'name': 'test-model',
                'context_length': 8192,
                'expires_at': '2030-01-01T00:00:00Z'
            }]
        }
    def fake_relancer_moteur(racine):
        return True

    module.version_repond = fake_version_repond
    module.lire_ps = fake_lire_ps
    module.relancer_moteur = fake_relancer_moteur

    # ------------------------------------------------------------------
    # Cas forward : résidant avec context_length 8192 et expires_at futur
    # ------------------------------------------------------------------
    captured_requests.clear()
    result = module.executer('http://fake', None, 5, 120, False)
    ok &= check(
        "forward_residant_ctx",
        len(captured_requests) == 1 and
        captured_requests[0]['data']['options'].get('num_ctx') == 8192 and
        captured_requests[0]['data']['options'].get('num_predict') == 1,
        f"requête capturée: {captured_requests[0]['data']['options']}"
    )

    # ------------------------------------------------------------------
    # Cas reverse : context_length absent
    # ------------------------------------------------------------------
    captured_requests.clear()
    module.lire_ps = lambda url: {'models': [{'name': 'test-model'}]}
    result = module.executer('http://fake', None, 5, 120, False)
    ok &= check(
        "reverse_ctx_absent",
        len(captured_requests) == 0 and
        result["sonde"].startswith("sautee"),
        f"sonde: {result['sonde']}"
    )

    # ------------------------------------------------------------------
    # Cas reverse : modèle explicite
    # ------------------------------------------------------------------
    captured_requests.clear()
    result = module.executer('http://fake', "phi:latest", 5, 120, False)
    ok &= check(
        "reverse_modele_explicite",
        len(captured_requests) == 1 and
        'num_ctx' not in captured_requests[0]['data']['options'],
        f"options: {captured_requests[0]['data']['options']}"
    )

    # ------------------------------------------------------------------
    # Cas fuite : aucune requête sans num_ctx ou avec num_ctx ≠ context_length
    # ------------------------------------------------------------------
    # Sous-cas 1 : context_length non entier
    captured_requests.clear()
    module.lire_ps = lambda url: {
        'models': [{
            'name': 'test-model',
            'context_length': "invalid",  # NON VERIFIE: type attendu
            'expires_at': '2030-01-01T00:00:00Z'
        }]
    }
    result = module.executer('http://fake', None, 5, 120, False)
    ok &= check(
        "fuite_ctx_invalide",
        len(captured_requests) == 0,
        "requête émise malgré context_length invalide"
    )

    # Sous-cas 2 : num_ctx ≠ context_length
    # (Simulé en modifiant le faux lire_ps pour retourner un context_length différent)
    captured_requests.clear()
    def fake_lire_ps_ctx_mismatch(url):
        return {
            'models': [{
                'name': 'test-model',
                'context_length': 4096,  # différent de 8192
                'expires_at': '2030-01-01T00:00:00Z'
            }]
        }
    module.lire_ps = fake_lire_ps_ctx_mismatch
    # On force num_ctx à 8192 dans la requête pour simuler une fuite
    def fake_sonder_with_mismatch(*args, **kwargs):
        if kwargs.get('num_ctx') != 4096:
            captured_requests.append({'fuite': True})
        return True
    module.sonder = fake_sonder_with_mismatch
    result = module.executer('http://fake', None, 5, 120, False)
    ok &= check(
        "fuite_ctx_mismatch",
        len(captured_requests) == 0,
        "requête avec num_ctx ≠ context_length"
    )

    # Restauration de urllib.request.urlopen
    urllib.request.urlopen = original_urlopen

    sys.exit(0 if ok else 1)

if __name__ == "__main__":
    main()
