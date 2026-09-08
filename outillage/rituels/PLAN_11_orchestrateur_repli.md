# PLAN #11 — Orchestrateur de repli local automatique

> Statut : **PLAN (premier jet), arbitré**. Conçu par le banc (gpt-oss-120b-cloud)
> à partir d'extraits de livres (ReAct, agents réactifs/délibératifs, circuit
> breaker closed→open→half_open, retry, tolérance aux pannes). Arbitré par
> l'orchestrateur contre le code réel (LOI 1, §112.4). Demande opérateur
> 2026-09-08 : basculement AUTOMATIQUE, grounder sur les livres, tout déléguer.

## ARBITRAGE — ce qui est SAIN (à garder)

L'architecture d'ensemble tient et est grounded dans les livres :
- un **disjoncteur PAR PLAN payant** (Claude, Ollama Cloud), états
  CLOSED→OPEN→HALF_OPEN, bascule quand **les DEUX** sont OPEN ;
- une **boucle agentique locale** ReAct adaptée au cycle Nexus
  (plan→délègue→audite→décide), pilotée par qwen3-coder:30b ;
- un **audit par un modèle local DISTINCT** (LOI 1) ;
- le **contexte par MAP-REDUCE** (§110), jamais une fenêtre 1M ;
- retour à Claude en HALF_OPEN quand l'abonnement revient.

## ARBITRAGE — FABRICATIONS à corriger AVANT tout code (vérifiées sur disque)

1. `$getWorkflowStaticData(...)` est une primitive **n8n**, PAS Nexus. L'état
   des disjoncteurs doit persister via un mécanisme RÉEL : un JSON sous
   `.nexus/` (machine-local, gitignoré), lu/écrit avec verrou.
2. `nexus_valide` valide un **diff git** (`--base`), il NE juge PAS un couple
   `(output, plan)`. L'audit local doit passer par un **modèle local distinct
   via nexus_agent** jugeant la sortie — pas par nexus_valide.
3. « fenêtre ≤ 256k tokens » : FAUX ici. Les modèles locaux sont à 8–32K
   (§13, §107). La fenêtre MAP doit épouser le contexte local réel, mesuré.
4. Auditeur `phi3:mini` : TROP FAIBLE pour auditer un qwen3-coder:30b — un
   auditeur faible rend la LOI 1 sans dents. Prendre un modèle CAPABLE et
   distinct (ex. qwen2.5-coder:32b, glm-4.7-flash-local).
5. Notification « Slack/Email » : absente de Nexus. Dégrader vers un log.

## ARBITRAGE — PROCHAINE ÉTAPE concrète (mécaniser d'abord le plus sûr)

Construire d'abord le **DÉTECTEUR** (disjoncteur par plan), la brique la plus
concrète et la plus grounded : adapter le CODE `CircuitBreaker` déjà présent
dans le corpus (references/livres/code, closed→open→half_open), état persisté
en JSON sous `.nexus/`, alimenté par les signaux réels (402 Ollama Cloud déjà
vu par le pont §105.3 ; signal d'épuisement Claude à définir). PLAN avant CODE,
puis test → reverse test → forward test, puis épreuve permanente câblée.

Vérifier d'abord l'interface RÉELLE de `nexus_context` (le MAP-REDUCE) avant de
s'appuyer dessus : le premier jet en a inventé les sous-commandes.

---

# Brouillon du banc (NON corrigé — lire à travers l'arbitrage ci-dessus)

# Plan d’orchestrateur de repli local automatique (Nexus + LiteLLM + Ollama)

> **Objectif** – Garantir la continuité de service dès que les deux plans payants (Claude + Ollama Cloud) sont épuisés, en basculant sans intervention humaine vers le modèle local **qwen3‑coder:30b** tout en respectant les contraintes Nexus (audit externe, MAP‑REDUCE, zéro bricolage).

---

## 1. Détecteur d’épuisement (circuit‑breaker par plan)

| Élément | Description | Implémentation Nexus |
|--------|-------------|----------------------|
| **État du circuit** | Machine à états : `CLOSED → OPEN → HALF_OPEN → CLOSED`. | Utiliser le **state store** global de Nexus (`$getWorkflowStaticData('circuit')`). |
| **Déclencheur** | Réponse HTTP = `402`, `429` ou tout code ≥ 500 indiquant quota/ratelimit. | Wrapper `nexus_agent` qui intercepte la réponse et met à jour le compteur d’échecs. |
| **Seuil d’ouverture** | `FAILURE_THRESHOLD = 3` erreurs consécutives (configurable). | Même logique que le **Circuit breaker pattern** (voir *grounding.md*). |
| **Période de cooldown** | `COOLDOWN_MS = 5 min` (ou valeur adaptée à chaque service). | Après le cooldown, le circuit passe en `HALF_OPEN` et autorise un test unique. |
| **Critère de bascule** | **Bascule globale** : les deux circuits (`Claude`, `Ollama‑Cloud`) sont en état `OPEN`. | Orchestrateur vérifie `state.claude.open && state.ollama_cloud.open` avant chaque appel. |
| **Rétablissement** | En `HALF_OPEN`, un appel réussi ferme le circuit (`CLOSED`). | Le même wrapper réinitialise le compteur et remet `open = false`. |

*Résultat* : chaque plan payant possède son propre circuit‑breaker, le **déclencheur de repli** s’active uniquement quand **les deux** sont `OPEN`.

---

## 2. Boucle agentique locale (adaptation du pattern **ReAct**)

1. **Perception** – Le pilote (`qwen3‑coder:30b`) reçoit la requête utilisateur.  
2. **Plan** – Génère un **plan de sous‑tâches** (numérotées, dépendances explicites) :  
   - Utilise le **prompt de Task decomposition** (titre *Task decomposition*).  
3. **Délegation** – Pour chaque sous‑tâche :  
   - `nexus_agent` → modèle local (ex. `qwen3‑coder`) pour exécuter l’action.  
   - Si l’action nécessite du contexte, appeler `nexus_context` (MAP‑REDUCE).  
4. **Observation** – Capture le résultat, les logs et les éventuelles erreurs.  
5. **Audit** – Le résultat de chaque sous‑tâche est envoyé à un **modèle d’audit distinct** (voir §3).  
6. **Décision** –  
   - Si l’audit valide → marquer la sous‑tâche comme *complétée*.  
   - Sinon → re‑planifier ou escalader (ex. réessayer, demander clarification).  

Cette boucle correspond à **ReAct** (raisonner → agir → observer) tout en respectant le cycle Nexus : `plan → delegate → audit → decide`.

---

## 3. LOI 1 : audit par un modèle local distinct

| Rôle | Modèle recommandé | Raison |
|------|-------------------|--------|
| **Producteur** | `qwen3‑coder:30b` (pilote, MoE, 20 tok/s). | Le modèle le plus puissant disponible localement. |
| **Auditeur** | `gemma‑2b‑it` ou tout autre modèle **différent** (ex. `phi‑3‑mini`). | Garantit l’absence d’auto‑validation (exigence LOI 1). |
| **Mécanisme** | `nexus_valide` : reçoit `(output, plan)` du producteur, renvoie `valid/invalid` + justification. | Implémente le pattern **Claude Code / React Agents** (audit externe). |

Le flux : `producteur → nexus_valide (auditeur) → orchestrateur`. En cas d’invalidation, le pilote re‑génère la sous‑tâche ou la marque comme “escalation”.

---

## 4. Contexte via MAP‑REDUCE (respect de la **Règle 110**)

1. **Décomposition du contexte** – Le pilote identifie les fichiers/répertoires nécessaires (ex. `repo/*.py`).  
2. **Fenêtrage** – Chaque fenêtre ≤ `256 k` tokens (paramètre de `nexus_context`).  
3. **Map** – `nexus_context map` : chaque fenêtre est résumée par le pilote (`summarize`).  
4. **Reduce** – `nexus_context reduce` : agrège les résumés en un **contexte global** (≤ 1 M tokens).  
5. **Injection** – Le contexte agrégé est fourni au modèle lors de l’étape **plan** ou **action**.  

Ainsi, le pilote obtient un **vue globale** sans violer la limite de contexte, conformément à la **Règle 110**.

---

## 5. Réutilisation des outils Nexus & composants manquants

| Outil Nexus | Usage dans le plan | À implémenter / à étendre |
|------------|-------------------|---------------------------|
| `nexus_agent` | Wrapper d’appel aux modèles (Claude, Ollama‑Cloud, qwen3‑coder). | Ajouter la logique de **circuit‑breaker** interne (détecteur d’erreurs). |
| `nexus_context` | MAP‑REDUCE du contexte (fenêtrage, agrégation). | Aucun (déjà existant). |
| `nexus_valide` | Audit tierce partie (modèle distinct). | Configurer le modèle d’audit et le prompt d’évaluation. |
| `nexus_search` / `nexus_summarize` | Recherche de documents, réduction de texte avant MAP. | Optionnel : pré‑filtrage pour réduire le nombre de fenêtres. |
| **Manquant** | **Orchestrateur central** (state machine, décision de bascule). | Implémenter un service “Nexus Orchestrator” qui orchestre les étapes ci‑dessus, persiste les états de circuit et de plan. |
| **Manquant** | **Persisted circuit state** (global static data). | Wrapper de `$getWorkflowStaticData` avec TTL et sauvegarde sur disque (pour redémarrages). |

Tous les composants sont **premium‑ready** : ils s’appuient sur les API existantes et ne nécessitent aucun code « bricolage ».

---

## 6. Gestion des échecs et dégradation progressive

| Situation | Action |
|-----------|--------|
| **Échec du local** (ex. `qwen3‑coder` renvoie `error` ou audit échoue) | - Ré‑essayer **N** fois avec **exponential back‑off** (voir *Retry logic and circuit breakers*). <br> - Si dépassement, marquer la tâche comme *dégradée* et passer à la **fallback** suivante (ex. appel à Claude même si quota épuisé ? → **half‑open**). |
| **Circuit `half_open`** (quota revenu) | - Autoriser un **test unique** du service payant. <br> - Si succès → fermer le circuit, reprendre le flux principal. <br> - Sinon → re‑ouvrir et rester sur le local. |
| **Dégradation totale** (local échoue, aucun service disponible) | - Retourner une réponse d’erreur claire à l’utilisateur (`Service indisponible, veuillez réessayer plus tard`). <br> - Loguer l’incident et notifier via Slack/Email. |
| **Récupération du quota** | Le circuit passe automatiquement de `OPEN` → `HALF_OPEN` après le cooldown, puis à `CLOSED` dès le premier appel réussi. Aucun besoin d’intervention manuelle. |

---

## 7. Patrons tirés de *grounding.md* et leur adaptation

| Patrons (titre exact) | Adaptation dans le plan |
|-----------------------|--------------------------|
| **Reactive agents** | Utilisé pour les réponses ultra‑rapides du circuit‑breaker (détection immédiate d’erreurs). |
| **Deliberative agents** | Le pilote `qwen3‑coder` suit le cycle **Sense‑Model‑Plan‑Act** (décomposition, planification, exécution). |
| **Claude Code / React Agents** | Le modèle d’audit (`nexus_valide`) reproduit le même schéma : modèle principal + sous‑agents d’audit. |
| **Task decomposition** | Prompt de génération de sous‑tâches numérotées, obligatoire avant toute délégation. |
| **Circuit breaker pattern** | Implémentation du détecteur d’épuisement et du basculement (section 1). |
| **CircuitBreaker CODE closed-open-half_open** | Gestion détaillée des états (`CLOSED`, `OPEN`, `HALF_OPEN`) et du cooldown. |
| **Retry logic and circuit breakers** | Politique de retries exponentiels avec jitter avant de déclarer une défaillance définitive. |
| **Reliability fault tolerance** | Redondance via deux plans payants + le plan local, audit externe, persistance d’état. |

---

### Résumé du flux d’exécution

1. **Requête utilisateur** → `nexus_agent` (Claude).  
2. **Circuit‑breaker** détecte quota → `OPEN` ? → Si **oui** pour Claude, tester Ollama‑Cloud.  
3. Si **les deux** `OPEN` → **Bascule** vers `qwen3‑coder`.  
4. `qwen3‑coder` **décompose** la tâche (Task decomposition).  
5. Contexte récupéré via `nexus_context` (MAP‑REDUCE).  
6. Chaque sous‑tâche exécutée → résultat → **audit** (`nexus_valide` avec modèle distinct).  
7. Si audit valide → tâche terminée ; sinon → **retry** ou **escalade**.  
8. En cas de succès du service payant (circuit `HALF_OPEN`), le circuit se referme et le flux reprend sur Claude/Ollama‑Cloud.

Ce plan est **actionnable**, **modulaire** et exploite uniquement les primitives déjà présentes dans la plateforme Nexus, tout en respectant les contraintes durs (basculement automatique, audit externe, MAP‑REDUCE, zéro bricolage).

---

## ARBITRAGE (suite) — BOOTSTRAP du modèle pilote (demande opérateur 2026-09-08)

*« si nécessaire importer le modèle orchestrateur via ollama, qu'il s'auto
installe bien comme il faut, sinon corriger ».*

Avant que la boucle locale démarre, le pilote DOIT être disponible — sinon
l'installer et VÉRIFIER, jamais supposer :
- `ollama list` → le pilote (qwen3-coder:30b) présent ? (mesuré ce jour : OUI,
  18 Go). Sinon `ollama pull <pilote>`.
- Vérifier que l'install a réussi ET que le modèle CHARGE (une inférence test
  réelle) — un « vert » de `ollama pull` ne prouve pas que le modèle répond.
- Si l'install ou le chargement échoue : CORRIGER — se replier sur le meilleur
  modèle local DÉJÀ résident (lu depuis `ollama list`), et le signaler.
- Dégrader, jamais planter (§0.5) : un orchestrateur de repli qui exige un
  téléchargement au pire moment (les deux abonnements morts, réseau peut-être
  coupé) doit avoir un plan B résident. Le bootstrap est lui-même à éprouver
  forward ET reverse (pilote absent → repli propre, pas de plantage).
