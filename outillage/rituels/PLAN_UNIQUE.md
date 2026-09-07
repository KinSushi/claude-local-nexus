# PLAN UNIQUE — frappes cloud, checklist, progress

**Réversibilité** — ce fichier est suivi par git ; tout état antérieur se
retrouve par `git log -- outillage/rituels/PLAN_UNIQUE.md` et `git revert`.
Point de fusion initial des trois sources : `95715b3`.

**Règle du plan** — un item n'est CLOUD que s'il se rend en patch ancré
`<<<AVANT>>>/<<<APRES>>>/<<<FIN>>>` borné, avec une contre-épreuve mécanique.
Ce qui pèse un jugement d'effet de bord est ARBITRAGE, jamais délégué. Ce dont
l'état n'est pas mesuré ce tour est MESURER-D'ABORD, jamais frappé sur mémoire.

---

## 1. FAIT — ce tour (2026-09-07), mesuré et commité

| commit | sujet | preuve |
|---|---|---|
| `864e45b` | agent : `--sortie-brute` décape la clôture, `--depuis-jsonl` écrit sans re-tirer (rangs 26, 27) | forward/reverse verts |
| `c7de0b9` | séparation : 18 outils du produit reviennent sous `scripts/` (rang 23) | hooks 8/8, py_compile 17/17, intégrité 0 |
| `d8dc141` | réparation régression : 5 chemins morts des fichiers déplacés | porte 0 |
| `ee18174` | réparation régression 2 : `nexus_capability` était une copie intentionnelle | conformite verte |
| `97b8b7b` | agent : 3 défauts trouvés par audit tiers dans `decaper_cloture_englobante` | forward/reverse verts |
| `1ca6e8f` | SIM112 de la copie-paire corrigé à la source (1→0) | ruff All checks passed |

Vérifié aussi ce tour, contre le code réel : **`controle_hooks_cables` compte 8**
(le rang A « 5 au lieu de 8 » est CLOS), intégrité `Test-NexusConfig` code 0.

---

## 2. FRAPPES CLOUD — vagues (≤15 agents chacune)

Cycle par vague : frappe → récolte → audit tiers → si correction, re-frappe →
audit. Un seul lot en vol. Le banc rend un PATCH, jamais un fichier entier.

### Vague 0 — POSER ce qui est déjà rendu (pas une frappe)
Rendus propres dans `scratchpad/v18.md`, en attente d'application + épreuve.

- [ ] **11** `scripts/nexus_valide.py` — faux vert : ignore un fichier SUPPRIMÉ dans la plage **et** sort 0 sur erreur mécanique. Contre-épreuve : plage qui supprime un fichier → code non nul. (cockpit 175.1)
- [ ] **13** `tools/nexus-mcp/server.js` + `scripts/nexus_verrou_tenir.py` — le motif du refus de verrou remonte à l'appelant (REFUS/ERREUR nommés). Contre-épreuve : contention → message nommant la classe.

### Vague 1 — mécanique lint (bornée, patch sûr)
- [ ] **21** `SIM105` ×25 : `try/except/pass` → `contextlib.suppress`. Contre-épreuve : ruff SIM105 → 0, py_compile inchangé. (PLAN rang 21)
- [ ] **ruff** ~100 violations comptées non corrigées (E9,F,B,C4,SIM,RET). Par lots ; chaque lot : ruff baisse, comportement préservé. (cockpit 14)
- [ ] **W292** saut de ligne final manquant. Contre-épreuve : ruff W292 → 0. (C1)

### Vague 2 — gardes & porte (raffinements bornés)
- [ ] **175.2** la porte compte une EXÉCUTION sur un commentaire `# outillage/`. Ne détecter que les vraies formes d'appel. Contre-épreuve : un fichier à commentaire seul → 0 exécution.
- [ ] **22** cliquet de câblage sans porte de rebasement (distinguer régression vs élargissement de périmètre). Contre-épreuve : périmètre élargi + motif → accepté ; régression → refusé.
- [ ] **garde_agent** écrire le motif sur `stderr` avant sortie 2. Contre-épreuve : capture stderr → motif présent. (C1)
- [ ] **motif refus garde** (cockpit 13847). Même forme.

### Vague 3 — MESURER D'ABORD, puis frapper le résidu réel (source A)
`Test-NexusConfig` passe déjà (code 0) ; plusieurs items A sont probablement
clos. **Frappe interdite avant mesure.** Mesure = une passe locale, gratuite.
- [ ] chemins PowerShell assemblés / chemins gravés restants → mesurer combien subsistent, frapper le reste
- [ ] `nexus_chemins.py` (tout chemin nommé existe) + `nexus_racine.py` (deux marqueurs) → existent-ils ? sinon les faire produire
- [ ] contrôle d'identité des paires copiées (la régression `nexus_capability` de ce tour prouve le besoin — 175.4 lié)

---

## 3. ARBITRAGE SEUL — hors cloud (jugement d'effet de bord)

- **175.4** 6 dépendances produit → outillage subsistent (`conformite` → `cablage/traque/...`). Conception : les outils transitifs deviennent-ils produit, ou start.ps1 cesse-t-il d'appeler conformite au démarrage ? Décision de l'orchestrateur.
- **25** `pyproject.toml` forme `ai-trader` : dépend de 175.4 (le périmètre du paquet).
- **C3** registre modèles : trancher `qwen3.5-397b-cloud`, nommer le 4ᵉ état cloud — mesures réelles + décision.
- **CONTRADICTION** port : **résolu = 11434** (mesuré, §3.1 du contrat). Le 11435 était l'engine conteneurisé non démarré. À purger des sources restantes.

---

## 4. NE PAS RE-FRAPPER — pièges mesurés ce tour

- **175.5 / rang 16 — `nexus_appliquer.py` tolérances** : le banc rend un FICHIER ENTIER, pas un patch → inapplicable (écarté 4 fois). L'outil attend un patch. Approche cloud à revoir (extraits plus petits, ou arbitrage manuel borné), PAS une n-ième frappe identique. 6 applicateurs privés restent une dette.
- **175.3 / rang 24 — classificateur d'appartenance** : la cascade transitive classe 19 outils purs (dont la porte) comme « produit mal placé ». Garde NON câblée : elle défairait la séparation. À NE PAS armer tant que « appelé au démarrage » ≠ « fait partie du produit ».

---

## 5. CHECKLIST vivante & PROGRESS

- Cette section 2 EST la checklist (cases `[ ]`/`[x]`), cochée à mesure des frappes.
- `PROGRESS.MD` (racine, régénéré par `nexus_progres.py` à chaque tour) porte l'état git, les mécanismes et les sujets ouverts — source vivante, jamais éditée à la main.
- Rituel de fin de tour OBLIGATOIRE : validation tierce, commit avec la mesure, cockpit, boussole, boucle réarmée.

---

*Fin du plan unique. Réorganisé le 2026-09-07 : périmé purgé, frappes cloud ordonnées, pièges nommés.*
