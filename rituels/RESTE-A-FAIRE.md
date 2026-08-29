# Reste à faire — correctifs identifiés, non appliqués

> Issus de quatre audits conduits en worktrees isolés le 29 août 2026, sur
> des périmètres disjoints : sécurité, robustesse du serveur MCP, correction
> de la chaîne génération/validation, qualité perçue du dépôt.
>
> **Chaque entrée a été vérifiée par exécution**, pas supposée. Elles sont
> écrites ici pour qu'aucune ne dépende d'une mémoire de session.
>
> Ce qui a déjà été corrigé figure dans [`PROGRESS.md`](PROGRESS.md).

---

## Serveur MCP — `tools/nexus-mcp/server.js`

| # | Défaut | Gravité | Correction |
|---|---|---|---|
| M1 | `spawnSync` dans `nexus_profile` et `nexus_savings` **gèle la boucle d'événements** — mesuré : un `ping` envoyé à t+0,7 s honoré à t+10,8 s. Deux interpréteurs essayés × 300 s = jusqu'à **600 s** sans lire stdin | MOYEN | `spawn` asynchrone, un seul interpréteur résolu une fois |
| M2 | `mapReduce` **dégénère** quand deux analyses ne tiennent pas ensemble : chaque groupe n'a qu'un élément, aucun appel REDUCE, résultat = concaténation brute **plus grosse que l'entrée**. Constaté à `context_tokens: 3000` — 20 148 caractères pour 12 000 en entrée. Seuil ≲ 5 500 | MOYEN | Réduire un élément seul s'il dépasse le budget ; ne compter une passe que si un appel a eu lieu ; signaler « fusion impossible » |
| M3 | `nexus_summarize` annonce « puis les synthèses sont fusionnées » — **aucune fusion n'existe**, la boucle empile `### fichier` et joint. Troncature muette à 24 000 caractères au lieu de passer par `mapReduce` | ÉLEVÉ | Ajouter une passe REDUCE finale, **ou** corriger la description ; router les fichiers > 24 Ko vers `mapReduce` |
| M4 | `nexus_compare` annonce « avec le temps **et le coût** » — n'imprime que secondes et jetons. Le coût réel est désormais disponible dans `result.cout` | FAIBLE | Afficher `result.cout` et `planOf(model)` |
| M5 | L'index est **relu et reparsé à chaque recherche**. Mesuré : 54 994 octets par extrait ; un index complet du dépôt ≈ **97 Mo rechargés par appel**. Au-delà de ~9 700 extraits, `JSON.stringify` dépasse la limite de chaîne V8 et l'indexation échoue **après** des heures d'embeddings | MOYEN | Cache mémoire invalidé sur `mtime` ; vecteurs en binaire ou JSONL ligne à ligne |
| M6 | `notifications/cancelled` accepté puis ignoré : **aucune annulation**. Combiné à la survie après fermeture de stdin, un serveur orphelin peut solliciter la passerelle partagée pendant des dizaines de minutes | MOYEN | Registre `id → AbortController`, `req.destroy()` sur annulation, borne à la fermeture de stdin |
| M7 | `nexus_vision` est le **seul outil sans `withRetry`** ; `fs.statSync` y est appelé deux fois | FAIBLE | Passer par `chat`/`withRetry` |
| M8 | Outil inconnu → `isError: true` au lieu de l'erreur JSON-RPC `-32602` que la spécification MCP réserve aux erreurs de protocole | FAIBLE | `-32602` pour outil inconnu et argument manquant |
| M9 | `masterKey` ne retire ni guillemets ni commentaire de fin de ligne : `KEY="sk-…"` produirait un 401 opaque — exactement ce que son commentaire veut éviter | FAIBLE | Même traitement que `nexus_test.py:master_key` |
| M10 | `spawnSync` sans `PYTHONIOENCODING` : la sortie Python revient en page de codes locale, accents corrompus. `run.stderr` est jeté, le message accuse « Python introuvable » alors que Python fonctionne | FAIBLE | `env: {...process.env, PYTHONIOENCODING: "utf-8"}` et remonter `stderr.slice(0, 500)` |

## Génération — `scripts/nexus_generate.py`

| # | Défaut | Gravité | Correction |
|---|---|---|---|
| G1 | Le générateur **écrit `litellm_config.yaml` avant la validation**. Si elle échoue, le fichier invalide reste sur disque ; LiteLLM tourne encore sur sa copie chargée, et le chargera au prochain redémarrage **sans repasser par aucune validation** | ÉLEVÉ | Générer dans un temporaire, valider **celui-là**, ne déplacer qu'ensuite |
| G2 | La règle « échec passager ⇒ modèle conservé » s'applique aussi aux **entrants**. Une coupure réseau, ou le `timeout=120` sur 19 sondes, fait entrer **tout le catalogue publié** ; `cloud[0]` devient `qwen3.5-397b-cloud`, donc `default_model` **et** tête de chaîne. Biais défavorable : les plus gros sont les plus susceptibles de dépasser le délai **et** les mieux classés | ÉLEVÉ | Ne conserver sur échec inconcluant que les modèles **déjà présents dans le pool précédent** |
| G3 | `render_chain` greffe le `terminal` (modèles **locaux textuels**) sur n'importe quelle chaîne trop courte, **modalité comprise** ; `cloud_chain` fige `modality="text"` pour tout modèle cloud. Inerte aujourd'hui — **un seul embedding publié sur ollama.com suffit** | ÉLEVÉ | Dériver la modalité cloud avec `EMBED_HINT`/`VISION_HINT`, filtrer `terminal` par modalité de groupe |
| G4 | Le générateur **réécrit deux lignes hors de tout marqueur** par regex sur le fichier entier : `adaptive_router_default_model: *-cloud` et `# NEXUS-ROUTER-VERSION:`. Le docstring « Ne réécrit que les zones délimitées » est donc **faux** | MOYEN | Encadrer ces deux valeurs par leurs propres zones AUTOGEN, ou corriger l'énoncé |
| G5 | `aliases_inside()` balaie **toutes** les zones d'un nom, `set_block()` n'en réécrit **qu'une**. Une zone dupliquée (merge raté) produit **18 alias en double**, sans erreur | FAIBLE | Lever si un nom de marqueur apparaît plus d'une fois |
| G6 | `local_context()` devine la fenêtre depuis le **nombre de paramètres lu dans le nom**, alors que le poids réel est dans `sizes`. `mixtral:8x7b` → « 7 » ≤ 9 → 16 384 pour un modèle de 26 Go classé DEGRADED | FAIBLE | Budgéter depuis le poids mesuré et la mémoire du moteur |
| G7 | `if len(targets) >= width + 1` au lieu de `>= width` : l'éventail vaut 2, **3**, 2 selon les successeurs restants | FAIBLE | Corriger l'indice |

## Validation — `scripts/nexus_validate.py`

| # | Défaut | Gravité | Correction |
|---|---|---|---|
| V1 | `graph` n'est alimenté que depuis `fallbacks`. Un cycle `A→B`, `B→A` dans **`context_window_fallbacks`** passe : code 0 | MOYEN | Alimenter depuis les deux listes |
| V2 | `selectable` n'agrège que pools et `fallbacks` : un modèle REJECT reste accepté comme **cible de `context_window_fallbacks`** et comme **`adaptive_router_default_model`** — or c'est le chemin le plus servi quand le routeur ne tranche pas | MOYEN | Ajouter cibles de contexte et tous les `default_model` |
| V3 | La règle de modalité n'est que **descendante** : `gemma4-12b-local → all-minilm-local` (texte → embedding) est accepté | MOYEN | `if src_kind != dst_kind` sans condition de sens |
| V4 | Seules `fallbacks` et `context_window_fallbacks` sont inspectées. `default_fallbacks` et `content_policy_fallbacks` passent avec alias pendants **et** fuite `local → cloud` | MOYEN | Parcourir toutes les listes de repli de LiteLLM |
| V5 | **Deux inventaires** dans le même validateur : la section 6 lit par son propre `subprocess` sans vérifier le code retour, la section 7 passe par `capability`. En panne, l'un voyait 39 modèles pendant que l'autre n'en voyait aucun | FAIBLE | Un seul inventaire, partagé |
| V6 | `cloud_models.txt` annonce 19 modèles « actifs » quand la configuration n'en déclare que 6 : le fichier enregistre le catalogue **publié** comme s'il était le catalogue **autorisé**. Jamais croisé par le validateur | MOYEN | Croiser entrées actives ↔ alias de `AUTOGEN:CLOUD_MODELS` |

## Profil matériel — `scripts/nexus_capability.py`

| # | Défaut | Gravité | Correction |
|---|---|---|---|
| C1 | `host_memory_gb()` renvoie des **GiB** étiquetés Go, `parse_size()` convertit en **Go décimaux**. Le mode `docker+host` soustrait l'un de l'autre : écart de ~7 % sur tous les budgets. Accessoirement `"kib": 1.049e-6` devrait être `1.024e-6` | FAIBLE | Une seule unité, explicitée |
| C2 | `can_download()` est du **code mort** — seul `nexus_test.py` l'appelle. `Update-NexusModels.ps1 -SyncLocal` tire tout ce qui manque dans `model_list.txt`, **sans contrôle disque ni mémoire**, or ce fichier contient les trois modèles REJECT | MOYEN | Appeler `can_download()` avant chaque `ollama pull` |

## Configuration

| # | Défaut | Gravité | Correction |
|---|---|---|---|
| K1 | `phi3-mini-local` et `ultime-recourse-local` ont des `litellm_params` **identiques**. Le dernier bond de la chaîne locale réessaie donc le même backend sous un autre nom : **zéro résilience** | FAIBLE | Vérifier qu'une cible diffère de sa source par `(model, api_base)` ; choisir un vrai dernier recours |
| K2 | Le verdict matériel est calculé **à l'instant de la génération** puis figé. Selon que Docker tourne ou non, `usable` vaut 32 ou 62 Go, et quatre modèles basculent de DEGRADED à ACCEPT — pour être ensuite servis par un moteur de 32 Go | MOYEN | Enregistrer le profil utilisé dans la configuration ; le validateur compare au profil courant et signale la divergence |

## Dépôt public

| # | Sujet | Effort | Impact |
|---|---|---|---|
| P1 | **Badges** — licence, CI, nombre de vérifications. Le lecteur des trente premières secondes ne descend pas jusqu'à la section Vérification | 15 min | fort |
| P2 | **Capture d'écran** — la sortie de `Initialize-Nexus.ps1 -CheckOnly` (profil matériel, verdicts) est déjà visuellement convaincante | 20 min | fort |
| P3 | `SECURITY.md` — justifié ici : le projet manipule clés d'API, clé maîtresse et frontières de confidentialité | 30 min | moyen |
| P4 | `README.en.md` — README, docs et commentaires sont en français ; un recruteur non francophone ne peut pas évaluer le travail | 2 h | fort si cible internationale |
| P5 | Nommage de `docs/architecture/` : casse incohérente, langues mêlées, **accents dans les noms de fichiers**, double extension `execution-policy.yaml.txt` | 30 min | faible |
| P6 | `nexus_state.py` affiche `digest[:32]` sous un titre « SHA-256 » — 128 bits, pas 256 | 5 min | faible |

## Migration hors de Docker — en cours

| Étape | État | Commande |
|---|---|---|
| 1. Télécharger les 21 modèles retenus sur l'hôte | **en cours** — 12/21, 101 Go libres | `python scripts/nexus_pull_host.py` (relançable) |
| 2. Basculer le moteur | à faire | `python scripts/nexus_switch_engine.py --to host` |
| 3. Régénérer et vérifier | à faire | `$env:NEXUS_OLLAMA_ENDPOINT="http://host.docker.internal:11434"` puis `.\scripts\Update-NexusModels.ps1 -Restart` |
| 4. Suite complète | à faire | `python scripts/nexus_test.py` |
| 5. **Seulement si tout passe** : retirer `COMPOSE_PROFILES` de `.env`, puis supprimer le volume `ollama_data` | à faire — **irréversible** | libère 541 Go |
| 6. Retélécharger les modèles reportés | à faire | avec la place libérée |

## Autres sujets ouverts

- **`.wslconfig` absent** — WSL2 applique 50 % de la RAM. `memory=52GB` rendrait 20 Go au moteur immédiatement, au prix d'un `wsl --shutdown` qui coupe Docker. Devient sans objet après la migration.
- **Langfuse** — `turn_off_message_logging: true` est actif et vérifié dans le conteneur, mais je n'ai pas ouvert une trace pour confirmer que le contenu en est absent. À vérifier une fois.
- **Approbation MCP** — `nexus-local` attend une approbation au prochain lancement de `claude`.
- **`.env` hors dépôt** — non copié dans `backups/` à dessein. À sauvegarder ailleurs, délibérément.
- **`backups/` sur le même disque** — protège de l'effacement, **pas d'une panne de disque**.
- **Mesure des économies** — 178 requêtes réelles, échantillon trop faible et dominé par quelques grosses requêtes. Le taux n'est pas encore significatif.
