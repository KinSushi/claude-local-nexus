import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / 'scripts'))

import nexus_generate as g

def _print_ok(name, detail):
    print(f"[OK  ] {name} : {detail}")

def _print_rate(name, detail):
    print(f"[RATE] {name} : {detail}")

def case_pool_under_budget():
    name = "pool sous budget"
    candidats = [
        {'alias': 'a-cloud', 'tier': 3, 'debit': 20.0, 'poids': 18.0},
        {'alias': 'b-local', 'tier': 3, 'debit': 20.0, 'poids': 18.0},
        {'alias': 'c-local', 'tier': 2, 'debit': 10.0, 'poids': 6.0},
        {'alias': 'd-local', 'tier': 1, 'debit': 5.0, 'poids': 0.5},
    ]
    pool, _, poids_total, _ = g.choisir_pool_exact(candidats, 40.0)
    if set(pool) == {'a-cloud', 'b-local', 'd-local'} and poids_total <= 40.0:
        _print_ok(name, f"pool={pool} poids_total={poids_total}")
        return True
    _print_rate(name, f"pool={pool} poids_total={poids_total}")
    return False

def case_trop_lourd_exclu():
    name = "trop lourd exclu"
    candidats = [
        {'alias': 'a-cloud', 'tier': 3, 'debit': 20.0, 'poids': 18.0},
        {'alias': 'b-local', 'tier': 3, 'debit': 20.0, 'poids': 18.0},
        {'alias': 'c-local', 'tier': 2, 'debit': 10.0, 'poids': 6.0},
        {'alias': 'd-local', 'tier': 1, 'debit': 5.0, 'poids': 0.5},
        {'alias': 'gros-local', 'tier': 3, 'debit': 30.0, 'poids': 50.0},
    ]
    pool, _, _, _ = g.choisir_pool_exact(candidats, 40.0)
    if 'gros-local' not in pool:
        _print_ok(name, f"pool={pool}")
        return True
    _print_rate(name, f"gros-local present in pool={pool}")
    return False

def case_departage_par_le_poids():
    name = "departage par le poids"
    candidats = [
        {'alias': 'leger-local', 'tier': 3, 'debit': 20.0, 'poids': 5.0},
        {'alias': 'lourd-local', 'tier': 3, 'debit': 20.0, 'poids': 15.0},
    ]
    pool, _, _, _ = g.choisir_pool_exact(candidats, 20.0, taille_min=1, taille_max=1)
    if pool == ['leger-local']:
        _print_ok(name, f"pool={pool}")
        return True
    _print_rate(name, f"pool={pool}")
    return False

def case_deterministe():
    name = "deterministe"
    candidats = [
        {'alias': 'a-cloud', 'tier': 3, 'debit': 20.0, 'poids': 18.0},
        {'alias': 'b-local', 'tier': 3, 'debit': 20.0, 'poids': 18.0},
        {'alias': 'c-local', 'tier': 2, 'debit': 10.0, 'poids': 6.0},
        {'alias': 'd-local', 'tier': 1, 'debit': 5.0, 'poids': 0.5},
    ]
    pool1, _, _, _ = g.choisir_pool_exact(candidats, 40.0)
    pool2, _, _, _ = g.choisir_pool_exact(candidats, 40.0)
    if pool1 == pool2:
        _print_ok(name, f"pool1={pool1}")
        return True
    _print_rate(name, f"pool1={pool1} pool2={pool2}")
    return False

def case_cloud_alias():
    name = "cloud_alias"
    result = g.cloud_alias('qwen3:30b')
    if result == 'qwen3-30b-cloud':
        _print_ok(name, f"result={result}")
        return True
    _print_rate(name, f"result={result}")
    return False

def case_quality_tier():
    name = "quality_tier"
    v50, v100, v200 = g.quality_tier(50), g.quality_tier(100), g.quality_tier(200)
    if v50 == 3 and v100 == 2 and v200 == 1:
        _print_ok(name, f"50->{v50} 100->{v100} 200->{v200}")
        return True
    _print_rate(name, f"50->{v50} 100->{v100} 200->{v200}")
    return False

def main():
    results = [
        case_pool_under_budget(),
        case_trop_lourd_exclu(),
        case_departage_par_le_poids(),
        case_deterministe(),
        case_cloud_alias(),
        case_quality_tier(),
    ]
    sys.exit(0 if all(results) else 1)

if __name__ == '__main__':
    main()