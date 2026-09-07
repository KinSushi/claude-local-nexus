# PLAN UNIQUE  

**Réversibilité** – les trois sources restent dans le dépôt au commit `95715b3`.  
Ce plan unique est un commit distinct ; il peut être annulé avec `git revert` du présent commit.  

---  

## Acquis (FAIT) – tirés de **174.6**  

| Rang | Sujet | État |
|------|-------|------|
| 19 | l'arbre n'a pas son propre `.git` | **PORTE POSEE** [174.6] |
| 23 | dix‑sept outils du produit dans `outillage/` | **NOMMES, non deplaces** [174.6] |
| 24 | classificateur d'appartenance – 14/14, 6 gardes orphelines | **COMPLET** [174.6] |
| 25 | `pyproject.toml` a la forme d'`ai‑trader` | **EN ATTENTE** [174.6] |
| 26 | `--sortie-brute` écrit les clôtures markdown | **DISPONIBLE** [174.6] |
| 27 | `--sortie-brute` ne sait pas écrire DEPUIS un rendu existant | **NON IMPLEMENTÉ** [174.6] |
| 16 | `nexus_appliquer.py` : tolérance au retrait | **ECARTE 3 FOIS** [174.6] |
| 21 | 25 occurrences de `SIM105` | **OUVERT** [174.6] |
| 22 | le cliquet de câblage sans porte de rebasement | **OUVERT** [174.6] |
| 11 | fusion du plan unique – point de retour `95715b3` | **EN COURS** [174.6] |
| 19b | `rituels/STATE.md`, résidu à la racine | **NON RETIRE** [174.6] |

---  

## Plan détaillé (ordonné selon les rangs de **174.6**)  

### Rang 11 – Fusion du plan unique  

| Voulu | Fermeture (contrôle) | État |
|-------|----------------------|------|
| Intégrer les trois sources dans un seul document | Vérification d’un diff unique contenant les sections `MAITRE`, `A`, `B`, `174.6` | **EN COURS** [174.6] |

### Rang 16 – Tolérance au retrait (`nexus_appliquer.py`)  

| Voulu | Fermeture (contrôle) | État |
|-------|----------------------|------|
| Gérer les suppressions de fichiers sans échec | Test d’application sur un lot contenant 3 suppressions → aucune erreur | **ECARTE 3 FOIS** [174.6] |

### Rang 19 – Arbre Git manquant  

| Voulu | Fermeture (contrôle) | État |
|-------|----------------------|------|
| Ajouter un dépôt Git dédié à l’arbre de travail | `git status` doit indiquer un dépôt initialisé | **PORTE POSEE** [174.6] |

### Rang 19b – Résidu `rituels/STATE.md`  

| Voulu | Fermeture (contrôle) | État |
|-------|----------------------|------|
| Supprimer le fichier résiduel | Vérifier l’absence du fichier après `git rm` | **NON RETIRE** [174.6] |

### Rang 21 – Occurrences `SIM105`  

| Voulu | Fermeture (contrôle) | État |
|-------|----------------------|------|
| Corriger les 25 occurrences de `SIM105` | Linter `ruff` doit rendre 0 violations pour ce code | **OUVERT** [174.6] |

### Rang 22 – Cliquet de câblage sans porte de rebasement  

| Voulu | Fermeture (contrôle) | État |
|-------|----------------------|------|
| Implémenter une porte de rebasement pour le cliquet | Test d’exécution du script `nexus_cablage.py` → succès | **OUVERT** [174.6] |

### Rang 23 – Outils du produit dans `outillage/`  

| Voulu | Fermeture (contrôle) | État |
|-------|----------------------|------|
| Déplacer les 17 outils vers leur dépôt dédié | Vérifier que `outillage/` ne contient plus aucun de ces outils | **NOMMES, non deplaces** [174.6] |

### Rang 24 – Classificateur d’appartenance  

| Voulu | Fermeture (contrôle) | État |
|-------|----------------------|------|
| Valider le classificateur (14/14) et résoudre 6 gardes orphelines | Test unitaire du classificateur → succès, garde → détectée et liée | **COMPLET** [174.6] |

### Rang 25 – `pyproject.toml`  

| Voulu | Fermeture (contrôle) | État |
|-------|----------------------|------|
| Adapter le fichier à la forme `ai‑trader` | `toml‑check` doit valider le schéma | **EN ATTENTE** [174.6] |

### Rang 26 – `--sortie-brute` écrit les clôtures  

| Voulu | Fermeture (contrôle) | État |
|-------|----------------------|------|
| Générer des fichiers markdown de clôture via `--sortie-brute` | Vérifier la présence du fichier `.md` contenant le champ `texte` | **DISPONIBLE** [174.6] |

### Rang 27 – `--sortie-brute` ne sait pas écrire depuis un rendu existant  

| Voulu | Fermeture (contrôle) | État |
|-------|----------------------|------|
| Ajouter la capacité d’écrire à partir d’un rendu existant | Test d’appel avec un rendu préexistant → fichier mis à jour | **NON IMPLEMENTÉ** [174.6] |

---  

## Non classé (tâches provenant de **MAITRE** et **A** qui ne sont pas réfutées et ne figurent pas dans **174.6**)  

### Sécurité mesurée (MAITRE)  

| Voulu | Fermeture (contrôle) | État |
|-------|----------------------|------|
| Vérifier l’absence de fuite `local → cloud` (5/5) | Test d’accès réseau → échec sur toutes les tentatives | **OK** [MAITRE] |
| S’assurer que les chemins interdits échouent proprement (15/15) | Exécution de scénarios interdits → retour d’erreur | **OK** [MAITRE] |
| Garantir 0 échec des gardes et ACL | Lancer la campagne complète → 0 échecs | **OK** [MAITRE] |
| Détecter 4 secrets, 3 silences corrects | `detecteur de secrets` doit rendre 4/3 | **OK** [MAITRE] |
| Confirmer que aucun port n’est publié hors de `127.0.0.1` (11435 & 4000) | Scan de ports → seuls 11435/4000 ouverts | **OK** [MAITRE] |

### Ressources mesurées (MAITRE)  

| Voulu | Fermeture (contrôle) | État |
|-------|----------------------|------|
| Corpus documentaire : 33 771 fichiers | Comptage via script `nexus_doc.py` | **OK** [MAITRE] |
| Dépôt SAS : 40 310 .md, 11 215 .py, 10 135 .json, 1 922 .js | Listing du dépôt | **OK** [MAITRE] |
| Modèles locaux résidents : 53 | `ollama list` → 53 entrées | **OK** [MAITRE] |
| Catalogue cloud accessible : 19 modèles | Console Ollama → 19 modèles | **OK** [MAITRE] |
| Index documentaire : 166 507 symboles Python + 24 073 annexes | `nexus_doc.py` → compte exact | **OK** [MAITRE] |

### Chantier C1 – Canal de retour (MAITRE)  

| Voulu | Fermeture (contrôle) | État |
|-------|----------------------|------|
| Exposer `max_tokens` dans le schéma MCP (`nexus_summarize`/`nexus_context`) | Épreuve appelant l’outil avec budget explicite → budget honoré | **EN COURS** [MAITRE] |
| Distinguer trois états de rendu (complet / tronqué / vide) | Test de chaque état → libellé correct | **EN COURS** [MAITRE] |
| Avertir sous le seuil où les modèles rendent vide | Épreuve demandant un budget insuffisant → message d’avertissement | **EN COURS** [MAITRE] |
| Rendre le partiel plutôt que la section vide | Épreuve sur rendu tronqué → contenu non vide | **EN COURS** [MAITRE] |
| `nexus_garde_agent` : écrire le motif sur `stderr` avant sortie 2 | Capture `stderr` → motif présent | **EN COURS** [MAITRE] |
| Clarifier le libellé « Aucun fragment pertinent » de `nexus_context` | Test sur corpus non vide → libellé non ambigu | **EN COURS** [MAITRE] |
| `--sortie` écrit JSON dans fichier `.md`; ajouter `--sortie-brute` | Vérifier que le champ `texte` seul est écrit | **EN COURS** [MAITRE] |
| Conserver le saut de ligne final (`W292`) | Lancer `ruff` → pas d’avertissement `W292` | **EN COURS** [MAITRE] |

### Chantier C2 – Gardes (MAITRE)  

| Voulu | Fermeture (contrôle) | État |
|-------|----------------------|------|
| Déclarer `nexus_garde_shell` dans le settings global (opérateur) | Contrôle comparant portée déclarée vs voulue | **EN ATTENTE** [MAITRE] |
| Vérifier que `nexus_garde_isolation.py` est armé globalement | Test d’appel du hook → succès | **EN COURS** [MAITRE] |
| Remplacer chemin absolu dur dans `nexus_armer_hook.py:123` par dérivation dynamique | Exécution depuis répertoire différent → chemin correct | **EN COURS** [MAITRE] |
| Uniformiser le protocole de refus entre `garde_shell` (exit 0 + hookEventName) et `garde_agent` (exit 2) | Épreuve séparée → comportement conforme | **EN COURS** [MAITRE] |
| Vérifier la présence de `.env.example` pour le contrôle `controle_secrets_documentes` | Suppression du fichier → échec du contrôle | **EN COURS** [MAITRE] |

### Chantier C3 – Registre des modèles (MAITRE)  

| Voulu | Fermeture (contrôle) | État |
|-------|----------------------|------|
| Trancher l’existence de `qwen3.5-397b-cloud` | Requête réelle → réponse positive ou négative | **EN COURS** [MAITRE] |
| Éprouver chaque identifiant `*:cloud` avant écriture YAML | `Test‑NexusConfig.ps1` refuse toute référence pendante | **EN COURS** [MAITRE] |
| Nommer le quatrième état (cloud) dans le contrat §6 | Contrôle comparant catalogue cloud, déclaré et exposé | **EN COURS** [MAITRE] |
| Appliquer la matrice de capacités Local × Cloud × Anthropic par mesure | Modèle passe de DISCOVERED → PRODUCTION uniquement après mesures | **EN COURS** [MAITRE] |

### Chantier C4 – Plan local (MAITRE)  

| Voulu | Fermeture (contrôle) | État |
|-------|----------------------|------|
| Implémenter `nexus_preload` pour charger un alias une fois | Préchargement + mesure → débit stable | **EN COURS** [MAITRE] |
| Régler `OLLAMA_KEEP_ALIVE` et `OLLAMA_MAX_LOADED_MODELS` avant re‑dérivation du pool | Contrôle de réglage → pool redérivé automatiquement | **EN COURS** [MAITRE] |
| Re‑mesurer le débit local après préchargement et réglages | Deux colonnes (chargement, débit) mesurées séparément | **EN COURS** [MAITRE] |

### Chantier C5 – Corpus jamais exploités (MAITRE)  

| Voulu | Fermeture (contrôle) | État |
|-------|----------------------|------|
| Indexer les deux corpus par embeddings locaux (par copie) | Index existant, recherche fonctionnelle, aucune écriture sur dépôts voisins | **EN COURS** [MAITRE] |
| Cartographier le contenu des PDF, notebooks, txt (délegué au banc) | Carte interrogeable disponible | **EN COURS** [MAITRE] |
| Extraire les métaheuristiques du corpus MQL5 vers le problème de température | Implémentation éprouvée sur banc, budget d’évaluation fixé | **EN COURS** [MAITRE] |

### Partie A – Isolation (source **A**)  

| Voulu | Fermeture (contrôle) | État |
|-------|----------------------|------|
| Réparer les 13 chemins PowerShell assemblés | Patch appliqué → `Test‑NexusConfig.ps1` passe | **EN COURS** [A] |
| Corriger le hook aveugle (`controle_hooks_cables`) | Compter 8 hooks au lieu de 5 | **EN COURS** [A] |
| Réparer `controle_gardes_accordes` | Linter passe, alerte disparue | **EN COURS** [A] |
| Ajuster les périmètres des 3 linters (ruff, PSScriptAnalyzer) | Violations passent de 21 à ~99, rebaseline motivé | **EN COURS** [A] |
| Supprimer les 4 chemins gravés restants | Aucun chemin dur dans le code | **EN COURS** [A] |
| Corriger `model_list.txt` recherché à côté | Script `update_local_models.ps1` ne génère plus d’erreur | **EN COURS** [A] |
| Mettre à jour `outillage/nexus_chemins.py` pour valider l’existence de chaque chemin | Épreuve réussie → 0 morts | **EN COURS** [A] |
| Mettre à jour `outillage/nexus_racine.py` pour remonter deux marqueurs | Test réussit → racine correcte | **EN COURS** [A] |
| Détecter les paires copiées et garantir l’identité | Contrôle d’identité passe | **EN COURS** [A] |
| Remplacer les 92 occurrences gravées par appels dynamiques (`nexus_racine.chemin`) | Aucun texte dur restant | **EN COURS** [A] |
| Nettoyer le préambule `sys.path` des 7 gardes | 4 modules libérés, `scripts/` passe de 29 à 25 | **EN COURS** [A] |
| Découper `scripts/nexus.ps1` en commandes distinctes | Produit 5 commandes produit + 4 orchestration séparées | **EN COURS** [A] |

---  

## CONTRADICTION  

| Sujet | Source 1 | Source 2 |
|-------|----------|----------|
| Port utilisé : 11435 vs 11434 | MAITRE indique le port **11435** (corrigé depuis en **11434**) | 174.6 mesure réelle **11434** [MAITRE][174.6] |
| Nombre de mécanismes aveugles | A affirme **3** mécanismes aveugles | Audit tiers (référencé dans A) indique **au moins 7** [A] |

---  

*Fin du plan unique.*
