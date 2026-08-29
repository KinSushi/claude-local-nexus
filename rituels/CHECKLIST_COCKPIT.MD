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

| # | Sujet | Statut | Prochaine action |
|---|---|---|---|
| 1.1 | Plan de migration chiffré | `FAIT` | `python scripts/nexus_migration_plan.py` |
| 1.2 | Bascule du moteur, réversible | `PRÊT` | `python scripts/nexus_switch_engine.py --to host` |
| 1.3 | Téléchargement des 22 modèles retenus (128 Go) sur l'hôte | `OUVERT` | `--write model_list.host.txt` puis `ollama pull` |
| 1.4 | Vérification post-bascule | `OUVERT` | `Update-NexusModels.ps1 -Restart` + suite de tests |
| 1.5 | Suppression du service et du volume Docker (541 Go) | `OUVERT` | **Seulement après 1.4 validée** — irréversible |
| 1.6 | Retéléchargement des 240 Go reportés | `OUVERT` | Après 1.5, avec la place libérée |

**Chiffres établis** — volume Docker 541 Go (`docker_data.vhdx` : 553 Go),
disque C: 155 Go libres, budget de migration 130 Go après réserve.
On ne peut donc pas tout sortir d'un coup : l'ordre des étapes est ce qui
rend la migration possible.

**Ordre impératif** : télécharger → basculer → vérifier → *seulement alors*
supprimer. Tant que 1.5 n'est pas franchie, le retour arrière est immédiat.

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
