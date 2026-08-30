# Cockpit — sujets ouverts

> Tenu à jour pendant la refonte du 29 août 2026. Sert de mémoire externe :
> rien d'important ne doit dépendre du fil de conversation.
>
> Statuts : `FAIT` vérifié par un test · `PRÊT` livré, pas encore exécuté ·
> `OUVERT` à traiter · `DÉCIDÉ` tranché, sans action requise.
>
> **Les correctifs identifiés mais non appliqués sont détaillés dans
> [`RESTE-A-FAIRE.md`](RESTE-A-FAIRE.md)** — 27 entrées, chacune vérifiée par
> exécution lors des audits, avec sa gravité et sa correction.

---

## Session du 30 août 2026 — sujets ouverts

> Trente-cinq commits. Ce qui suit est ce qui **reste**, pas ce qui a été fait :
> l'historique est dans git, le cockpit ne sert qu'à ne rien perdre.

### Bloqué sur une décision qui ne m'appartient pas

| Sujet | État | Ce qui manque |
|---|---|---|
| Réglages du moteur Ollama | `OUVERT` | `OLLAMA_KEEP_ALIVE` non défini → défaut 5 min. Une session parallèle a montré que **les 61,8 s attribuées à `glm-4.7-flash` sont du rechargement disque**, pas de l'inférence. Décision d'environnement hôte. |
| Taille du pool local | `OUVERT` | **Couplé au point ci-dessus.** Borné à 4 modèles alors que le moteur en gardait 3 résidents. Si `OLLAMA_MAX_LOADED_MODELS=1`, il faut 1–2, sinon chaque choix évince. Les deux réglages sont **une** décision. |

### Mesures incomplètes

| Sujet | État | Reste |
|---|---|---|
| Débit (jetons/s) | `OUVERT` | 7 modèles mesurés sur 58. Le tri des pools en dépend. |
| Fidélité des embeddings | `PRÊT` | `mesurer_embedding()` écrite et intégrée, **jamais exécutée** — toutes les tentatives ont expiré sous charge. |
| Coût fixe binaire | `PRÊT` | `mesurer_binaire()` écrite, **jamais exécutée**. C'est elle qui prouvera qu'un modèle local minuscule bat le cloud, sans aller-retour réseau. |
| Qualité de résumé | `OUVERT` | Grandeur manquante pour trancher `DEFAULT_CHAT_MODEL`. Piste retenue : similarité sémantique résumé↔source par embedding local, sans référence humaine. |

### Capacités déclarées, non exploitées

| Sujet | État | Reste |
|---|---|---|
| `tools` | `PRÊT` | 19 modèles sur 54 ne l'ont pas ; 6 sont dans les profils MCP, **annotés mais pas triés dessus**. |
| `thinking` | `OUVERT` | Déclarée par le moteur, lue nulle part. |
| Niveau de qualité | `OUVERT` | 21 modèles sur 36 restent à `tier 0` — jamais déclaré, jamais déduit. |

### Traque mécanique

| Sujet | État | Reste |
|---|---|---|
| 38 constats | `OUVERT` | Classe 1 examinée : **1 vrai défaut sur 9**, corrigé. Restent 21 constats classe 2, 5 classe 3, 3 classe 4. |
| Taux de faux positifs | `DÉCIDÉ` | Classe 1 : 5 faux positifs sur 6 examinés. Trop large, mais conservée — elle a trouvé le défaut réel. Le taux est écrit pour qui la lit. |

### Vérifications jamais faites

| Sujet | État |
|---|---|
| `Start-Claude.ps1` | `OUVERT` — corrigé, **jamais exécuté de bout en bout** |
| Suite complète après tous les changements | `OUVERT` — trois lancements interrompus ; dernier état connu 24 PASS, 0 FAIL |
| 9 appels Anthropic sur 9 échouent | `OUVERT` — le plan de dernier ressort ne répond pas. Non testé par appel réel : ce serait facturé. |

---

## Reprise immédiate — à lire en premier dans une nouvelle session

Trois commandes suffisent à savoir où l'on en est. Aucune ne suppose quoi
que ce soit :

```powershell
python scripts/nexus_conformite.py    # peut-on démarrer ? et sinon, pourquoi
python scripts/nexus_releve.py        # le local remplace-t-il l'orchestrateur ?
python scripts/nexus_pull_host.py     # ce qui manque encore, relançable
```

**La seule action qui vous revient** : approuver le serveur MCP
`nexus-local` au démarrage de `claude` dans ce dossier. Tant qu'il est en
`⏸ Pending approval`, l'orchestrateur lit les fichiers lui-même — sur
l'abonnement — au lieu de les faire lire gratuitement en local. C'est le
plus gros levier d'économie encore fermé.

**Deux secrets à faire tourner**, passés en clair dans une conversation :
la clé Ollama Cloud (ollama.com) et un jeton GitHub.

**Travailler gratuitement**, en arbre isolé, sans toucher l'arbre principal :

```powershell
python scripts/nexus_worktree.py --fichiers <cible.py> `
    --consigne "..." --modele qwen3-coder-30b-local
python scripts/nexus_worktree.py --fusionner <nom>   # retenir
python scripts/nexus_worktree.py --jeter <nom>       # jeter
```

Ce que valent réellement ces relectures est mesuré dans
[`EVALUATION-LOCALE.md`](EVALUATION-LOCALE.md) : **5 propositions retenues
sur 15**, et **3 des 10 rejets auraient introduit une panne**. La règle qui
en découle : le local détecte, l'orchestrateur arbitre — et l'analyse d'un
modèle ne garantit pas que son diff porte sur la même chose.

---

## 0. Objectif directeur

Trois exigences, dans cet ordre :

1. **Économiser ~93 % de l'abonnement Claude** — déléguer le volume au local
   et au cloud, ne payer que le raisonnement.
2. **Rester opérationnel sans abonnement** — un modèle local doit pouvoir
   remplacer l'orchestrateur dès l'expiration ou le dépassement de quota.
3. **Plateforme multi-tâche et multimodale, sans limitation** — y compris un
   contexte effectif de 1 M, obtenu par distribution.

Contrainte transverse : **contraintes machine opposables**, acceptation ou
rejet automatique selon CPU, GPU, RAM et disque.

---

## 1. Migration du moteur hors de Docker

**Migration terminée.** Le moteur sert depuis l'hôte, le volume Docker
est supprimé, le disque virtuel est compacté.

| # | Sujet | Statut | Preuve |
|---|---|---|---|
| 1.1 | Plan de migration chiffré | `FAIT` | `model_list.host.txt` |
| 1.2 | Bascule du moteur | `FAIT` | `x-litellm-model-api-base: http://host.docker.internal:11434` sur une inférence réelle |
| 1.3 | Téléchargement sur l'hôte | `FAIT` | 19 téléchargés, 0 échec |
| 1.4 | Vérification post-bascule | `FAIT` | forward 11/0, reverse 15/0, policy 5/0, relève 5/0 |
| 1.5 | Suppression du volume Docker | `FAIT` — irréversible | 541 Go, après vérification que les 17 modèles restants sont publiés au registre |
| 1.6 | Compaction du disque virtuel | `FAIT` | 553 Go → 12,9 Go, **540 Go rendus** |
| 1.7 | Retéléchargement des 6 modèles reportés | `EN COURS` | `python scripts/nexus_pull_host.py` — relançable, il reprend où il s'est arrêté |

**Ce qu'il reste à voir arriver seul** : les 4 derniers modèles
(`deepseek-coder:33b`, `codestral`, `qwen2.5:32b`, `llava:34b`). Tant
qu'ils manquent, `nexus_conformite.py` marque la configuration **non
conforme**, ce qui interdit tout redémarrage — comportement voulu, la
panne étant réelle. Elle se résout d'elle-même à la fin du téléchargement.

**Deux enseignements de la compaction**, à ne pas réapprendre :

* `Optimize-VHD` seul ne libère **rien** — Windows ignore quels blocs sont
  libres dans l'ext4. Il faut `fstrim` depuis l'intérieur d'abord. Mesuré :
  553 Go avant, 553 Go après, sans erreur ;
* sans élévation, `Optimize-VHD` échoue **silencieusement** en rendant un
  code de succès. `Compact-NexusDisk.ps1` refuse donc de démarrer plutôt
  que d'abandonner le disque entre deux états.

---

## 1 bis. Critère de reproductibilité — tranché

La question n'est jamais « est-ce volumineux » mais **« existe-t-il une
source pour le reconstruire »**. Mesuré :

| Artefact | Taille | Source de reconstruction |
|---|---|---|
| `ollama_data` | **541,2 Go** | `ollama pull`, piloté par `model_list.txt` |
| images Docker | 10,7 Go | `docker pull`, déclarées dans le compose |
| `redis_data` | 9 Mo | cache — se reconstitue à l'usage, par définition |
| fichiers du dépôt | 1 Mo | git : l'historique **est** la sauvegarde |
| `.nexus/index.json` | 1 Mo | `nexus_index_build` — lent, mais refaisable |
| **`pgdata`** | **83,8 Mo** | **aucune** — dépense, sessions, clés |
| **`.git`** | **1,2 Mo** | **partielle** — un `clone` ne ramène que ce que le distant a reçu |
| **`.env`** | 1 Ko | **aucune** — exclu de git à dessein |

`.git` mérite une mention particulière : le dépôt distant existe
(`github.com/KinSushi/Claude-Local-Nexus`), mais **aucun amont n'est
configuré pour `main`**, **2 commits ne sont pas poussés**, et **40 entrées
ne sont pas commitées**. Un `git clone` ne ramènerait donc pas le travail le
plus récent — c'est-à-dire le plus coûteux à refaire.

**L'irremplaçable représente 0,015 % du volume.** 84 Mo méritent une
sauvegarde ; 552 Go n'en méritent aucune.

| # | Sujet | Statut | Détail |
|---|---|---|---|
| 1.7 | Audit reconstructible / irremplaçable | `FAIT` | `nexus_preserve.py` |
| 1.8 | Sauvegarde de l'irremplaçable | `FAIT` | Dump SQL de 18,2 Mo — lisible, comparable, restaurable sur une autre version de PostgreSQL |
| 1.9 | `backup.ps1` tentait d'archiver 541 Go | `FAIT` | Volume Ollama retiré : l'archivage aurait échoué faute de disque, et n'aurait rien préservé |
| 1.10 | Ollama sous profil Docker | `FAIT` | `COMPOSE_PROFILES=embedded` — comportement inchangé aujourd'hui, sortie en retirant une ligne |
| 1.11 | `depends_on: ollama` retiré de LiteLLM | `FAIT` | Exiger sa santé au démarrage empêcherait de tourner avec un Ollama sur l'hôte |
| 1.12 | `.env` à sauvegarder hors dépôt | `OUVERT` | **Action utilisateur** — non copié dans `backups/` à dessein : dupliquer un secret sur le même disque multiplie les endroits où il peut fuir |
| 1.13 | Historique git sauvegardé | `FAIT` | Bundle de 1,2 Mo, vérifié « complete history », clonable directement |
| 1.14 | Travail non commité sauvegardé | `FAIT` | 38 fichiers, 0,2 Mo — un bundle ne contient que ce qui est commité |
| 1.15 | Aucun amont configuré pour `main` | `OUVERT` | **Action utilisateur** — `git push -u origin main` ; sans cela le distant reste en retard de 2 commits et de tout le travail du jour |
| 1.16 | `backups/` vit sur le même disque | `OUVERT` | Protège de l'effacement accidentel, **pas d'une panne de disque**. Copier hors machine |

Reste donc dans Docker : **PostgreSQL** (seul volume irremplaçable), **Redis**
(cache, mais lié à LiteLLM et minuscule), **LiteLLM** (sa valeur est sa
configuration, versionnée). Sort de Docker : **Ollama** et ses 541 Go.

---

## 2. Limites matérielles

| # | Sujet | Statut | Détail |
|---|---|---|---|
| 2.1 | Garde-fou ACCEPT / DEGRADED / REJECT | `FAIT` | `nexus_capability.py`, câblé au générateur et au validateur |
| 2.2 | Docker plafonne le moteur à 32 Go sur 61,6 | `DÉCIDÉ` | 29 Go de la machine hors d'atteinte — motif principal de la migration |
| 2.3 | `.wslconfig` absent → WSL2 applique 50 % | `OUVERT` | Palliatif immédiat : `memory=52GB` + `wsl --shutdown` (coupe Docker) |
| 2.4 | 3 modèles inexécutables ici (163 Go) | `OUVERT` | `llama4:scout` 67 Go, `llama3.2-vision:90b` 54 Go, `llama3.3:70b` 42 Go |
| 2.5 | 4 modèles dégradés | `DÉCIDÉ` | `mixtral:8x7b`, `qwen3:32b`, `qwen3-vl:32b`, `llava:34b` — adressables, hors pools |
| 2.6 | GPU Radeon 890M via Vulkan | `OUVERT` | Non listé officiellement ; à tester sur l'Ollama natif — seul gain de vitesse structurel possible |
| 2.7 | Docker comme extension mémoire | `DÉCIDÉ` | **Mirage** pour la mémoire (la VM prélève sur la même RAM) ; **réel** pour la résidence simultanée et la continuité pendant la migration |

---

## 3. Contexte et relève

| # | Sujet | Statut | Détail |
|---|---|---|---|
| 3.1 | Profil `releve-locale` à 64K | `FAIT` | Exposé et vérifié |
| 3.2 | Coût mémoire mesuré à 64K | `FAIT` | glm-4.7-flash = 23 Go (19 poids + ~4 KV), relevé par `ollama ps` |
| 3.3 | Test réel de la relève via LiteLLM | `FAIT` | 143+208 = 351 en 61 s à 65 536 de contexte, 23 Go chargés, endpoint local prouvé |
| 3.4 | Contexte distribué (1 M par map-reduce) | `FAIT` | Éprouvé sur un corpus réel : 24 fichiers lus pour 5 464 tokens à coût nul |
| 3.5 | Modèles locaux encore à 8K | `OUVERT` | À relever après migration ; 8K est inexploitable pour une charge agentique |
| 3.6 | Distribution multi-moteur du map-reduce | `OUVERT` | Aujourd'hui séquentiel ; parallélisable une fois deux moteurs disponibles |
| 3.7 | Bascule automatique de l'orchestrateur | `PRÊT` | `Start-Claude.ps1` — relance en relève locale sur motif de quota. La bascule est **entre** deux sessions, pas au milieu de l'une |

---

## 4. Pont Claude Code ↔ modèles locaux

| # | Sujet | Statut | Détail |
|---|---|---|---|
| 4.1 | Serveur MCP `nexus-local`, 12 outils | `FAIT` | Quatre familles : exécution, contexte, modalité, inspection |
| 4.2 | Approbation du serveur dans Claude Code | `OUVERT` | **Action utilisateur** : lancer `claude` et approuver |
| 4.3 | `nexus_vision` multimodal | `FAIT` | Testé ; **llava-7b est instable** sur la même image : lecture correcte une fois, description erronée la suivante |
| 4.7 | Amorçage sur machine neuve | `PRÊT` | `Initialize-Nexus.ps1` — prérequis, secrets, profil, services, config, vérification |
| 4.4 | Index RAG sur le dépôt complet | `OUVERT` | Construit sur `docs/` et vérifié (recherche hybride pertinente) ; reste à étendre au dépôt |
| 4.8 | Profils d'exécution | `FAIT` | `coding`→releve-locale, `reasoning`→glm-4.7-flash, `rapide`→llama3.2-3b, `multimodal`→llava-7b |
| 4.9 | Reprise sur incident passager | `FAIT` | Un `socket hang up` ne jette plus une phase MAP de quinze minutes |
| 4.5 | Portabilité de `.mcp.json` | `FAIT` | `${CLAUDE_PROJECT_DIR}` — plus aucun chemin en dur |
| 4.6 | Extension à d'autres classes de tâches | `OUVERT` | Les 8 outils sont une base, pas la cible |

---

## 5. Configuration et automatisation

| # | Sujet | Statut | Détail |
|---|---|---|---|
| 5.1 | Zones AUTOGEN, générateur idempotent | `FAIT` | Test d'idempotence dans la suite |
| 5.2 | Validation bloquante avant redémarrage | `FAIT` | `Test-NexusConfig.ps1`, code 1 = pas de redémarrage |
| 5.3 | Tâche planifiée quotidienne 04:00 | `FAIT` | `Register-NexusAutoUpdate.ps1` |
| 5.4 | Anciens `update_*.ps1` neutralisés | `FAIT` | Garde-fou après incident réel de corruption |
| 5.5 | Pool cloud variable (6 → 9 modèles) | `DÉCIDÉ` | 402 écarte, 429/timeout conserve — un quota épuisé ne prouve rien |
| 5.6 | Suppression des anciens scripts | `OUVERT` | Après une période de confiance |
| 5.7 | Redémarrage LiteLLM | `FAIT` | Cycle complet rejoué, smoke test 8/8 |
| 5.8 | Health checks en boucle continue | `FAIT` | Cycles de 60 s pour un intervalle de 30 s : la sonde tournait sans arrêt et chargeait les modèles. Intervalle porté à 900 s |
| 5.9 | Validation des droits par défaut | `FAIT` | Générer sans elle remplissait le pool de modèles inexécutables |
| 5.10 | Version de politique de routage | `FAIT` | `NEXUS-ROUTER-VERSION`, empreinte des pools et des chaînes — rattache un résultat aux règles qui l'ont produit |
| 5.11 | Portabilité HTTPS du pont | `FAIT` | Le transport suit l'URL au lieu de supposer HTTP et le port 80 |

---

## 6. Vérification

| # | Sujet | Statut | Détail |
|---|---|---|---|
| 6.1 | Suite forward / reverse / policy / code | `FAIT` | 12+10+4+12 au dernier passage complet |
| 6.2 | Passage complet après les derniers changements | `FAIT` | **44/44** — forward 11, reverse 12, policy 5, code 16 |
| 6.8 | Faux négatifs corrigés dans les tests | `FAIT` | Appel d'outil vérifié avec ses arguments ; image refusée par un modèle textuel (HTTP 400, pas de description hallucinée) |
| 6.9 | Tests d'implantation | `FAIT` | Pile minimale valide sans Ollama, profil réversible, sauvegarde ciblée — **19/19** en famille code |
| 6.7 | Règle asymétrique de repli | `FAIT` | Policy 5/5 : 8 replis vers le local, aucun vers l'extérieur |
| 6.3 | Cache neutralisé dans les tests | `FAIT` | Sans quoi les tests validaient Redis, pas les modèles |
| 6.4 | Preuve de non-fuite par `x-litellm-model-api-base` | `FAIT` | Plus forte que le nom du modèle |
| 6.5 | Test Anthropic réel | `OUVERT` | Non joué : consomme des crédits API — `-IncludeAnthropic` |
| 6.6 | Langfuse configuré mais jamais vérifié | `OUVERT` | L'observabilité conditionne la mesure des 93 % |

---

## 7. Mesure de l'objectif des 93 %

| # | Sujet | Statut | Détail |
|---|---|---|---|
| 7.1 | Rapport de délégation | `FAIT` | `nexus_savings.py` — ventilation par plan et coût contrefactuel |
| 7.4 | Échantillon encore trop faible | `OUVERT` | 178 requêtes réelles, dominées par quelques grosses : le taux n'est pas encore significatif |
| 7.5 | Health checks faussaient la mesure | `FAIT` | 2552 requêtes sur 2730 étaient la sonde ; désormais exclues du rapport |
| 7.2 | Comptabiliser par plan | `OUVERT` | Les outils MCP annoncent déjà modèle, plan et coût par appel |
| 7.3 | Exploiter Langfuse pour l'agrégat | `OUVERT` | Dépend de 6.6 |

---

## 7 bis. Doctrine de repli — tranchée

La règle initiale « aucun fallback ne franchit une frontière de
fournisseur » était trop rigide : elle interdisait précisément ce qu'il
fallait obtenir, un repli vers le local quand un quota s'épuise.

Règle retenue, **asymétrique** :

| Sens | Verdict | Raison |
|---|---|---|
| `cloud → local` | autorisé | ne fait perdre que de la capacité |
| `anthropic → local` | autorisé | idem, et évite l'interruption |
| `local → cloud` | interdit | les données sortiraient |
| `local → anthropic` | interdit | idem, et engage une dépense |

Un repli est **subi**, jamais choisi : il ne doit ni élargir l'exposition
des données, ni décider d'une dépense à la place de l'utilisateur.

---

## 7 ter. Ce que la délégation a déjà produit

Premiers usages réels des outils, à coût nul :

| Tâche déléguée | Volume | Résultat |
|---|---|---|
| Relecture de `server.js` (38 Ko) | 12 531 tokens | 7 défauts signalés, **4 réels** et corrigés |
| Lecture des 24 notes d'architecture | 5 464 tokens | Backlog de 20 capacités décrites mais non implémentées |
| Relecture de `nexus_test.py` (40 Ko) | 12 180 tokens | Faux négatifs identifiés dans 3 tests, corrigés |

Enseignement : la délégation trouve de vrais défauts, **et se trompe aussi**.
Sur les sept points du premier retour, trois étaient infondés — un `||` jugé
dangereux qui fait ce qu'il doit, une boucle infinie impossible, un
compteur mal analysé. Le rendement vient du tri, pas de l'acceptation.

---

## 8. Dettes et vigilances

- **Faux positifs `:latest`** dans le validateur — corrigés, à surveiller.
- **`nexus_test.py` déplace la configuration** le temps d'un test ; une
  récupération automatique existe, mais l'opération reste sensible.
- **Deux moteurs Ollama actifs simultanément** (Docker et hôte) : état
  transitoire acceptable pour la migration, à ne pas laisser s'installer
  sans décision.
- **`llava-34b` et assimilés** sortis des chaînes de fallback par le
  garde-fou : à réévaluer après la migration, la mémoire changeant.
