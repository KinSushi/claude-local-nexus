# Gabarit d'audit en quarantaine

Document de structure pour l'audit d'un fichier modifié par un agent en worktree.

---

## Exemple minimal (rempli)

**Fichier:** `scripts/exemple.py`  
**Agent:** `agent-abc123`  
**Modèle:** `gpt-oss-120b-cloud`  
**Branche:** `main`  
**Tête:** `a1b2c3d`  
**État:** commité  

### 1. Identité

Fichier modifié dans le dépôt: `scripts/exemple.py`  
Chemin relatif depuis la racine: `scripts/exemple.py`  
**Nouveau ou remplaçant?** Remplaçant (fichier existait avant)

### 2. Provenance

Produit par l'agent: `agent-abc123`  
Modèle utilisé: `gpt-oss-120b-cloud`  
Worktree: `.claude/worktrees/agent-abc123`  
Branche HEAD: `main`  
Commit HEAD (court): `a1b2c3d`  
État au moment du tri: commité (a passé par `git add` + `git commit`)

### 3. L'original

Copie de l'original (ce qu'il remplace):  
```
_ORIGINAL/scripts/exemple.py  [142 lignes, 3421 octets]
```

**Présent?** Oui. Sans l'original, aucun diff n'est possible — l'audit ne peut pas avoir lieu.

### 4. Les trois épreuves

#### 4a. TEST — chemin autorisé passe

Commande lancée:
```bash
python scripts/exemple.py --test
```

Sortie réelle:
```
OK: test passed
Code de sortie: 0
```

**Verdict:** La fonction principale répond sans erreur.

#### 4b. REVERSE-TEST — chemin interdit échoue

Commande lancée:
```bash
python scripts/exemple.py --forbidden
```

Sortie réelle:
```
Error: --forbidden not permitted
Code de sortie: 1
```

**Verdict:** Le refus fonctionne. Code non nul, message explicite, aucun effet de bord.

#### 4c. FORWARD-TEST — confronter le résultat au monde par un moyen indépendant

Observation réelle (moyen indépendant, jamais l'instrument jugé):
```
Comptage manuel des alias dans litellm_config.yaml:
  - declared:   54
  - exposed:    54
  - YAML count: 54
```

ou

```
Audit croisé sur les fichiers modifiés:
  - Dossier `scripts/`, fichiers changés: 3
  - Périmètre déclaré: « affecte pool_manager seulement »
  - Vérification indépendante: git grep pool_manager
  - Résultat: 23 mentions, 19 dans pool_manager, 4 dans tests
  - Périmètre réel vs déclaré: concordant
```

**Verdict:** Le résultat déclaré se vérifie par un moyen indépendant du filtre. Les épreuves 4a et 4b jugent l'instrument; 4c juge ce qu'il produit.

### 5. Couleur proposée

- 🔴 **ROUGE** — le travail casse quelque chose  
- 🟡 **JAUNE** — le travail fonctionne mais avec des réserves  
- 🟢 **VERT** — le travail est acceptable  

**Proposé:** 🟢 VERT

**Note:** Un auteur ne peut pas s'attribuer le vert. Cette proposition n'est valide que si elle vient du tiers qui audite.

### 6. Non-vérifié par l'auteur

Ce que l'auteur n'a pas pu prouver ou testé:

```
[ ] Compatibilité avec Python 3.8
[ ] Impact sur la performance en contexte 64K
[ ] Cas limites avec fichiers de plus de 10 MB
```

**Raison:** Le contrôle d'environnement n'était pas disponible lors de la génération.

### 7. Effets de bord

Fichiers MODIFIÉS en dehors du périmètre prévu:

```
(aucun)
```

ou

```
outillage/rituels/CHECKLIST_COCKPIT.md  [modifié, 2 lignes ajoutées]
```

**Impact?** Listé pour vérification. Si liste vide, le dire explicitement.

### 8. Audit du tiers

À remplir par quelqu'un qui n'a écrit ni le diagnostic ni le correctif.

**Auditeur:** `[nom]`  
**Date d'audit:** `[date ISO]`  
**Verdict:** `[ROUGE/JAUNE/VERT]`  
**Observations:**

```
[Espace à remplir librement. Aucun verdict n'est valide sans ce champ.]
```

---

## Gabarit vide (à utiliser pour chaque entrée)

**Fichier:** `[chemin relatif]`  
**Agent:** `[nom du worktree]`  
**Modèle:** `[modèle utilisé]`  
**Branche:** `[branche HEAD]`  
**Tête:** `[commit court]`  
**État:** `[commité / non-commité]`

### 1. Identité

Fichier modifié: `[ ]`  
Chemin relatif depuis la racine: `[ ]`  
**Nouveau ou remplaçant?** `[ ]`

### 2. Provenance

Produit par l'agent: `[ ]`  
Modèle utilisé: `[ ]`  
Worktree: `[ ]`  
Branche HEAD: `[ ]`  
Commit HEAD (court): `[ ]`  
État au moment du tri: `[ commité / non-commité ]`

### 3. L'original

Copie de l'original:  
```
[ chemin relatif ou « FICHIER NEUF » ]
```

### 4. Les trois épreuves

#### 4a. TEST — le chemin autorisé passe

Valide que l'instrument fonctionne sur son cas nominal.

Commande:
```
[ ]
```

Sortie:
```
[ ]
```

#### 4b. REVERSE-TEST — le chemin interdit échoue proprement

Valide que le refus fonctionne: code non-zéro, message explicite, aucun effet de bord ni fuite.

Commande:
```
[ ]
```

Sortie:
```
[ ]
```

#### 4c. FORWARD-TEST — confronter le résultat à un moyen indépendant

Valide le RÉSULTAT, jamais l'instrument. Moyen indépendant du filtre jugé: comptage, audit croisé, mesure par d'autres outils.

Commande (moyen indépendant):
```
[ ]
```

Résultat:
```
[ ]
```

### 5. Couleur proposée

`[ ROUGE / JAUNE / VERT ]`

**Note:** Un auteur ne peut pas s'attribuer le vert.

### 6. Non-vérifié par l'auteur

```
[ ]
```

### 7. Effets de bord

```
[ ]
```

### 8. Audit du tiers

**Auditeur:** `[ ]`  
**Date d'audit:** `[ ]`  
**Verdict:** `[ ROUGE / JAUNE / VERT ]`  
**Observations:**  
```
[ ]
```

---

## Règles du gabarit

1. **Une rubrique = une question.** Toute rubrique exige une réponse explicite.
2. **Pas de crochet vide.** Si une réponse n'existe pas, le dire clairement: "N/A — raison", "FICHIER NEUF", "Non applicable — détail". L'absence d'une réponse doit être énoncée, jamais cachée dans un crochet.
3. **Commandes réelles.** Les épreuves doivent porter des commandes exactes et des sorties réelles, jamais synthétiques.
4. **Audit tiers obligatoire.** Aucune entrée n'est auditable sans la rubrique 8 remplie par un tiers.
5. **Couleur sans tiers = invalide.** Un VERT proposé par l'auteur est un avis, pas un verdict. Seul le tiers juge.
