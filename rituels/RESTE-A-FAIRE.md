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
| ~~M1~~ | `spawnSync` dans `nexus_profile` et `nexus_savings` **gèle la boucle d'événements** — mesuré : un `ping` envoyé à t+0,7 s honoré à t+10,8 s. Deux interpréteurs essayés × 300 s = jusqu'à **600 s** sans lire stdin | MOYEN | **Fait** — `runPython` asynchrone, interpréteur mémorisé au premier succès. Remesuré : `ping` honoré en **1 ms** pendant `nexus_profile`. `ENOENT` est le seul motif de passer au candidat suivant |
| M2 | `mapReduce` **dégénère** quand deux analyses ne tiennent pas ensemble : chaque groupe n'a qu'un élément, aucun appel REDUCE, résultat = concaténation brute **plus grosse que l'entrée**. Constaté à `context_tokens: 3000` — 20 148 caractères pour 12 000 en entrée. Seuil ≲ 5 500 | MOYEN | Réduire un élément seul s'il dépasse le budget ; ne compter une passe que si un appel a eu lieu ; signaler « fusion impossible » |
| M3 | `nexus_summarize` annonce « puis les synthèses sont fusionnées » — **aucune fusion n'existe**, la boucle empile `### fichier` et joint. Troncature muette à 24 000 caractères au lieu de passer par `mapReduce` | ÉLEVÉ | Ajouter une passe REDUCE finale, **ou** corriger la description ; router les fichiers > 24 Ko vers `mapReduce` |
| M4 | `nexus_compare` annonce « avec le temps **et le coût** » — n'imprime que secondes et jetons. Le coût réel est désormais disponible dans `result.cout` | FAIBLE | Afficher `result.cout` et `planOf(model)` |
| M5 | ~~L'index est **relu et reparsé à chaque recherche**~~ · **reste** : au-delà de ~9 700 extraits, `JSON.stringify` dépasse la limite de chaîne V8 et l'indexation échoue **après** des heures d'embeddings | MOYEN | **Partiel** — cache mémoire invalidé sur `(mtime, taille)`, jamais sur une durée. Mesuré sur l'index de 591 Ko : 6,4 ms au premier appel, **0,014 ms** ensuite, réécriture vue immédiatement. **Reste** : passer les vecteurs en binaire ou JSONL, seul moyen de lever le plafond des 512 Mo de chaîne V8 |
| ~~M6~~ | `notifications/cancelled` accepté puis ignoré : **aucune annulation**. Combiné à la survie après fermeture de stdin, un serveur orphelin peut solliciter la passerelle partagée pendant des dizaines de minutes | MOYEN | **Fait** — registre `id → AbortController`, signal porté par `AsyncLocalStorage` jusqu'à `http.request` et au `spawn` Python. Aucune réponse n'est émise pour un appel annulé, comme le demande MCP. Borne `NEXUS_GRACE_MS` (120 s) à la fermeture de stdin : mesuré, sortie en 3 026 ms pour une grâce de 3 000 ms |
| ~~M7~~ | `nexus_vision` est le **seul outil sans `withRetry`** ; `fs.statSync` y est appelé deux fois | FAIBLE | **Fait** — passe par `chat()`, donc par `withRetry` ; un seul `statSync`. Gain annexe : le modèle réellement servi est lu dans `x-litellm-adaptive-router-model`, et la troncature à `max_tokens` est signalée |
| ~~M8~~ | Outil inconnu → `isError: true` au lieu de l'erreur JSON-RPC `-32602` que la spécification MCP réserve aux erreurs de protocole | FAIBLE | **Fait** — classe `ErreurProtocole` (`code: -32602`) pour outil inconnu, argument absent ou du mauvais type ; les échecs d'exécution restent dans le résultat avec `isError`. Vérifié sur stdio : les trois cas rendent `-32602` |
| ~~M9~~ | `masterKey` ne retire ni guillemets ni commentaire de fin de ligne : `KEY="sk-…"` produirait un 401 opaque — exactement ce que son commentaire veut éviter | FAIBLE | **Fait** — même traitement que `nexus_test.py:master_key`, à une nuance près : le commentaire n'est retiré que d'une valeur **non citée**, car entre guillemets un `#` appartient à la clé (`"sk-a#b"` est préservé, là où le Python le tronque) |
| ~~M10~~ | `spawnSync` sans `PYTHONIOENCODING` : la sortie Python revient en page de codes locale, accents corrompus. `run.stderr` est jeté, le message accuse « Python introuvable » alors que Python fonctionne | FAIBLE | **Fait** — mesuré : sans la variable, `sys.stdout.encoding` vaut `cp1252` et `éèàç` revient en `e9 e8 e0 e7`, illisible en UTF-8 ; avec, `c3a9 c3a8`. `stderr` est remonté (500 caractères) et « Python introuvable » n'est plus dit que si les deux candidats donnent `ENOENT` |

**Conséquence de M8, à traiter dans un autre fichier.** `scripts/nexus_test.py`,
au test « MCP : outil inconnu signale sans crash » (~ligne 656), affirme encore
`unknown["result"].get("isError") is True`. Un outil inconnu rendant désormais
`error.code == -32602`, la clé `result` est absente : le `KeyError` est avalé
par le `except Exception` et le test **échoue**. L'assertion doit devenir
`unknown["error"]["code"] == -32602`, la survie du serveur restant vérifiée par
`tools/list`. Non corrigé ici : ce fichier est hors du périmètre de cette passe.

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

| # | Défaut | Gravité | État au 29/08 |
|---|---|---|---|
| C1 | `host_memory_gb()` renvoie des **GiB** étiquetés Go, `parse_size()` convertit en **Go décimaux**. Le mode `docker+host` soustrait l'un de l'autre : écart de ~7 % sur tous les budgets. Accessoirement `"kib": 1.049e-6` devrait être `1.024e-6` | FAIBLE | **Corrigé** |
| C2 | `can_download()` est du **code mort** — seul `nexus_test.py` l'appelle. `Update-NexusModels.ps1 -SyncLocal` tire tout ce qui manque dans `model_list.txt`, **sans contrôle disque ni mémoire**, or ce fichier contient les trois modèles REJECT | MOYEN | **Moitié faite** : le garde-fou est devenu appelable, l'appel reste à poser |
| C3 | Le module interrogeait encore le conteneur `ollama-server`, supprimé : `docker stats` pour le plafond mémoire, `docker exec … ollama list` **en premier** pour l'inventaire | MOYEN | **Corrigé** |

### C1 — une seule unité, décimale

Le sens de l'erreur, vérifié avant de la corriger : elle **sous-estimait**
la mémoire, donc dans le sens prudent. `TotalPhysicalMemory` vaut ici
66 161 848 320 octets, soit 61,6 Gio ou 66,2 Go décimaux ; le module
retenait 61,6 et le comparait à des poids que `ollama list` publie en Go
décimaux. Tous les budgets étaient rétrécis de 7 %.

Une exception à cette prudence justifiait à elle seule la correction : en
mode `docker+host`, `host_ram - container_limit_gb` soustrayait une valeur
décimale d'une valeur binaire. Là, rien ne garantissait plus le sens de
l'écart.

Le module compte désormais en gigaoctets décimaux partout — RAM, VRAM,
disque libre — et le rapport rappelle l'équivalent en Gio sur les deux
lignes que le lecteur compare à Windows, faute de quoi un changement
d'unité se lit comme une erreur de mesure. `"kib"` passe à `1.024e-6` ;
`"mib": 1.049e-3` était **juste** (1 Mio = 1 048 576 octets) et n'a pas
bougé.

Effet mesuré : budget pool 37,0 → 39,7 Go, budget maximal 52,4 → 56,2 Go.
Aucun verdict ne bascule sur l'inventaire actuel — le plus lourd des 22
modèles de l'hôte pèse 19 Go.

### C2 — le garde-fou est appelable, l'appel manque encore

```powershell
python scripts/nexus_capability.py --can-download qwen3-coder:30b
python scripts/nexus_capability.py --can-download 42
```

Codes de sortie : `0` autorisé, `1` refusé, `2` poids inconnu donc
indécidable. Le module se tait plutôt que d'arbitrer un modèle qu'il n'a
jamais mesuré — refuser par défaut bloquerait tout premier
téléchargement, accepter par défaut ne serait plus un garde-fou.

**Reste à poser l'appel**, dans un fichier non touché ici :
`scripts/Update-NexusModels.ps1`, boucle `foreach ($model in $missing)`
(≈ l. 117), qui lance `ollama pull` sans arbitrage. Deux remarques pour qui
s'en chargera :

* ce bloc `-SyncLocal` est **entièrement inerte** depuis la sortie du
  moteur hors de Docker : il teste `docker inspect ollama-server`, ne le
  trouve plus et journalise « synchronisation ignoree ». Le téléchargement
  non arbitré est masqué, pas supprimé — il reviendra avec la réécriture du
  bloc ;
* `scripts/nexus_pull_host.py` contrôle déjà le disque, mais avec sa propre
  arithmétique en Gio et sans passer par `can_download()`. Deux
  arithmétiques pour une même décision finiront par diverger.

### C3 — le moteur qui sert, et lui seul

Vérification demandée après la sortie d'Ollama hors de Docker : le module
interrogeait toujours le conteneur disparu.

`installed_models()` lisait **deux** inventaires et les fusionnait par
`setdefault`, en donnant la priorité à Docker. Un modèle présent dans le
seul volume du conteneur était donc attribué au moteur de l'hôte, qui ne
l'a pas : un verdict rendu sur un poids que ce moteur-là n'aurait jamais pu
charger. Un seul moteur est désormais interrogé, celui que
`ollama_location()` désigne comme servant, et `build_profile()` prend son
budget au même endroit — inventaire et budget ne peuvent plus décrire deux
machines différentes.

La sonde `docker stats` est **conservée à dessein** : `docker-compose.yml`
déclare toujours le service sous le profil `embedded`, qui est le chemin de
retour documenté. Elle coûte 0,13 s quand le conteneur n'existe plus, et
son absence est une information, pas une panne. Rapport courant vérifié :
`Moteur Ollama : host`, 66,2 Go, 22 modèles, tous ACCEPT.

## Configuration

| # | Défaut | Gravité | État au 29/08 |
|---|---|---|---|
| K1 | `phi3-mini-local` et `ultime-recourse-local` ont des `litellm_params` **identiques**. Le dernier bond de la chaîne locale réessaie donc le même backend sous un autre nom : **zéro résilience** | FAIBLE | **Confirmé et instruit** — correctif ci-dessous, à appliquer dans `litellm_config.yaml` |
| K2 | Le verdict matériel est calculé **à l'instant de la génération** puis figé. Selon que Docker tourne ou non, `usable` vaut 32 ou 62 Go, et quatre modèles basculent de DEGRADED à ACCEPT — pour être ensuite servis par un moteur de 32 Go | MOYEN | **Racine supprimée**, l'empreinte reste à inscrire et à comparer |

### K1 — le dernier recours n'en est pas un

Défaut confirmé dans `litellm_config.yaml` : `phi3-mini-local` (l. 319) et
`ultime-recourse-local` (l. 335) déclarent le même `model:
ollama_chat/phi3:mini`, le même `api_base`, les mêmes `num_ctx` et
`num_predict`. La chaîne locale se termine par
`llama3.2-3b-local → phi3-mini-local → ultime-recourse-local` (l. 857-862) :
les deux derniers bonds interrogent le même modèle sur le même moteur. Une
défaillance propre à `phi3:mini` — poids corrompus, éviction mémoire,
format refusé après une montée de version d'Ollama — emporte le recours
avec elle. Le repli existe dans le fichier et nulle part ailleurs.

**Remplaçant recommandé : `llama3.2:1b`.** Trois raisons, dans cet ordre :

1. il est **réellement installé sur l'hôte** — 1,3 Go, vérifié par
   `ollama list` le 29/08 ;
2. c'est le plus léger de l'inventaire, donc celui qui se charge encore
   quand plus rien d'autre ne tient — ce qu'on attend d'un dernier recours,
   et non une qualité de réponse ;
3. il vient d'une **autre famille** que `phi3:mini`. C'est la propriété qui
   manquait : un défaut de famille ne peut plus faire tomber les deux
   derniers bonds. La chaîne alterne alors Meta → Microsoft → Meta.

Correctif, **non appliqué ici** (`litellm_config.yaml` est édité en
parallèle) :

* dans le bloc `ultime-recourse-local`, remplacer
  `model: ollama_chat/phi3:mini` par `model: ollama_chat/llama3.2:1b`, et
  la description en conséquence. L'`api_base` de ce bloc est déjà
  `http://host.docker.internal:11434`, donc correct après la bascule ;
* faire porter la règle par `nexus_validate.py` : une cible de repli doit
  différer de sa source par le couple `(model, api_base)`. Sans cette
  vérification mécanique, la duplication reviendra à la prochaine
  génération, exactement comme elle est arrivée.

Remarque relevée au passage, hors K1 : l'alias `llama3.2-1b-local`
(l. 477), comme tous les blocs de la zone AUTOGEN, porte encore
`api_base: http://ollama:11434` — le point d'entrée du conteneur supprimé.
La zone n'a pas été régénérée depuis la bascule.

### K2 — le verdict figé

La cause immédiate n'existe plus. `build_profile()` retenait le **maximum**
des deux budgets en mode `docker+host` : le verdict dépendait donc de
l'état du démon Docker à l'instant de la génération. Le budget suit
maintenant le moteur qui sert, celui d'où vient l'inventaire. Mesuré après
correction : `host`, 66,2 Go, que Docker tourne ou non.

Reste la dérive lente, celle que rien ne détecte : une configuration
générée reste valable **en apparence** après un changement de matériel, de
moteur ou de machine. `nexus_capability.py --json` expose pour cela une clé
`signature`, volontairement lisible plutôt que hachée — une divergence doit
dire *quelle* valeur a bougé, pas seulement qu'il y en a une :

```text
"signature": "host/66.2/39.7/56.2/cpu"
               mode / mémoire moteur / budget pool / budget max / offload
```

**Reste à faire**, dans deux fichiers non touchés ici : que
`nexus_generate.py` inscrive cette empreinte dans `litellm_config.yaml`, et
que `nexus_validate.py` la recompare au profil courant et signale l'écart.

## Dépôt public

| # | Sujet | Effort | Impact |
|---|---|---|---|
| P1 | **Badges** — licence, CI, nombre de vérifications. Le lecteur des trente premières secondes ne descend pas jusqu'à la section Vérification | 15 min | fort |
| P2 | **Capture d'écran** — la sortie de `Initialize-Nexus.ps1 -CheckOnly` (profil matériel, verdicts) est déjà visuellement convaincante | 20 min | fort |
| P3 | `SECURITY.md` — justifié ici : le projet manipule clés d'API, clé maîtresse et frontières de confidentialité | 30 min | moyen |
| P4 | `README.en.md` — README, docs et commentaires sont en français ; un recruteur non francophone ne peut pas évaluer le travail | 2 h | fort si cible internationale |
| P5 | Nommage de `docs/architecture/` : casse incohérente, langues mêlées, **accents dans les noms de fichiers**, double extension `execution-policy.yaml.txt` | 30 min | faible |
| P6 | `nexus_state.py` affiche `digest[:32]` sous un titre « SHA-256 » — 128 bits, pas 256 | 5 min | faible |

## Migration hors de Docker — faite, sauf le disque

| Étape | État | Preuve |
|---|---|---|
| 1. Télécharger les modèles sur l'hôte | **fait** — 19 téléchargés, 0 échec | 22 modèles servis par l'hôte |
| 2. Basculer le moteur | **fait** | `x-litellm-model-api-base: http://host.docker.internal:11434` sur une inférence réelle |
| 3. Régénérer et vérifier | **fait** | 30 déclarations vers l'hôte, 0 vers le conteneur |
| 4. Suite complète | forward/reverse/policy/relève passent ; **code : 2 échecs** | tous deux dus au point 6 |
| 5. Supprimer le volume `ollama_data` | **fait** — irréversible, après vérification que les 17 modèles restants sont publiés au registre | volume supprimé, `COMPOSE_PROFILES` retiré de `.env` |
| 6. Retélécharger les modèles reportés | **bloqué** — 46 Go libres, 111 Go requis | voir ci-dessous |

### Le seul blocage restant

Le disque virtuel WSL2 occupe **553 Go pour ~52 Go réellement utilisés**.
`Optimize-VHD` seul ne libère rien : Windows ignore quels blocs sont libres
à l'intérieur de l'ext4 — mesuré, 553 Go avant, 553 Go après. Le `fstrim`
depuis l'intérieur a été fait (**995 Gio marqués libres**) ; il ne reste
que la rétraction, qui **exige l'élévation**, et `Optimize-VHD` échoue
alors *silencieusement* en rendant un code de succès.

```powershell
# dans un PowerShell ADMINISTRATEUR
cd C:\local-llm-docker
.\scripts\Compact-NexusDisk.ps1
```

Ensuite, et sans intervention :

```powershell
python scripts/nexus_pull_host.py --manquants
python scripts/nexus_conformite.py
```

Six alias restent déclarés sans poids d'ici là : `gemma4-31b`,
`qwen2.5-coder-32b`, `deepseek-coder-33b`, `codestral`, `qwen2.5-32b`,
`llava-34b`. La configuration est donc marquée **non conforme**, ce qui
interdit tout redémarrage — comportement voulu.

## Autres sujets ouverts

- **`.wslconfig`** — sans objet depuis la migration : le moteur n'est plus dans WSL2 et dispose de toute la RAM (66,2 Go mesurés).
- **Langfuse** — `turn_off_message_logging: true` est actif et vérifié dans le conteneur, mais je n'ai pas ouvert une trace pour confirmer que le contenu en est absent. À vérifier une fois.
- **Approbation MCP** — `nexus-local` attend une approbation au prochain lancement de `claude`.
- **`.env` hors dépôt** — non copié dans `backups/` à dessein. À sauvegarder ailleurs, délibérément.
- **`backups/` sur le même disque** — protège de l'effacement, **pas d'une panne de disque**.
- **Mesure des économies** — 2 467 787 tokens sur la journée, dont **97,3 % délégués** hors abonnement (5,37 $ évités au tarif `claude-sonnet-5`). L'échantillon est désormais exploitable ; il reste dominé par les relectures locales, donc représentatif du travail réellement en cours et non d'un usage moyen.
