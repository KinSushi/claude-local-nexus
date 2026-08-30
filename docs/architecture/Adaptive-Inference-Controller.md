# Adaptive Inference Controller (AIC)

> **Note reçue verbatim de l'opérateur, 30 août 2026.** Reproduite sans
> reformulation : c'est une spécification d'architecture, pas un résumé.
> Rien ici n'est implémenté à ce jour — voir « État » en fin de document.

---

Oui. Et dans **Claude-Local-Nexus**, je ne ferais surtout pas un simple `temperature` fixé dans `litellm_config.yaml`.

Le bon design est un **Temperature Controller adaptatif**, placé entre le profil de tâche et le modèle réellement sélectionné.

Le dépôt a déjà les briques nécessaires : profils `coding / reasoning / rapide / multimodal`, routage par capacité, benchmark de latence, pools générés, et `nexus_ask` qui peut accepter un profil plutôt qu'un modèle.

## 1. Le principe

Il faut séparer :

    T = f(modèle, tâche, complexité, historique, objectif)

et non :

    T = constante par modèle

| Tâche              | Température initiale |
| ------------------ | -------------------: |
| Code déterministe  |            0.05–0.15 |
| Refactoring        |            0.10–0.25 |
| Extraction         |            0.00–0.10 |
| Classification     |            0.00–0.10 |
| SQL                |            0.00–0.15 |
| Reasoning          |            0.20–0.45 |
| Brainstorming      |            0.60–0.90 |
| Rédaction créative |            0.70–1.00 |
| Multimodal         |            0.15–0.40 |

Mais ce ne sont que des **points de départ**.

Le système doit ensuite apprendre ce qui fonctionne **pour chaque modèle local**.

## 2. Le vrai mécanisme : température par modèle × tâche

```yaml
temperature_policy:
  default:
    coding: 0.10
    reasoning: 0.30
    rapide: 0.05
    multimodal: 0.25

  model_overrides:
    glm-4.7-flash-local:
      reasoning:
        base: 0.35
        min: 0.10
        max: 0.65

    granite3.3-8b-local:
      reasoning:
        base: 0.30
        min: 0.05
        max: 0.60
```

Cela devient le **prior** du système.

## 3. Ensuite : le modèle s'auto-adapte

Chaque exécution produit un événement :

```json
{
  "model": "glm-4.7-flash-local",
  "task": "reasoning",
  "temperature": 0.35,
  "latency_ms": 4200,
  "tokens_in": 8120,
  "tokens_out": 1330,
  "success": true,
  "quality_score": 0.91,
  "retry": false,
  "human_feedback": null
}
```

Fonction d'utilité :

    U = αQ − βL − γC − δR

avec Q = qualité, L = latence, C = coût, R = taux de retry/échec.
Pour le local C ≈ 0, donc le contrôleur optimise `U = αQ − βL − γR`.

## 4. Ne pas faire du *reinforcement learning* dès le départ

Ce serait inutilement complexe. Je commencerais par un **contextual bandit**.

Pour chaque `(model, task_profile)`, le système explore plusieurs températures :

    0.05  0.10  0.15  0.20  0.30  0.40  0.50  0.60  0.80

et mesure la performance.

```text
Task classifier → Profile → Temperature Controller → Model Router
    → Local model → evaluation → feedback store → controller
```

## 5. Adaptation conditionnelle à la complexité

Une même tâche `reasoning` peut être `complexity = 0.12` ou `0.94`.

    T = T_base + ΔT(complexity)

```python
temperature = base_temperature + complexity * exploration_gain
temperature = min(max(temperature, t_min), t_max)
```

Mais pour le code, augmenter la température avec la complexité n'est pas
nécessairement souhaitable. Donc une **policy par profil** :

```yaml
adaptation:
  coding:      { complexity_effect: negative }
  reasoning:   { complexity_effect: positive }
  rapide:      { complexity_effect: negative }
  multimodal:  { complexity_effect: neutral }
```

## 6. Adapter la température selon l'incertitude

Le système peut demander au modèle sa confiance — mais je préfère ne **pas**
utiliser exclusivement l'auto-évaluation, trop facilement biaisée.
Estimation composite :

    I = f(entropy, self-consistency, validation, tool errors, retry, critic score)
    T = g(I)

    incertitude faible → température basse → réponse rapide et déterministe
    incertitude élevée → température supérieure → exploration → critique

## 7. Modification de l'architecture Nexus

Actuel :

```text
Claude Code → MCP → nexus-local → LiteLLM → router
```

Proposé :

```text
Claude Code → nexus-local → Task Classifier → Task Profile
    → Complexity Estimator → Temperature Controller → Capability Router
    → Model → Validator / Critic → Telemetry → Adaptive Policy Store
```

Le routeur ne choisirait plus `model = X` mais :

```json
{
  "model": "glm-4.7-flash-local",
  "temperature": 0.27,
  "top_p": 0.92,
  "max_tokens": 4096,
  "reason": {
    "profile": "reasoning",
    "complexity": 0.71,
    "confidence": 0.63,
    "policy_version": "TCTRL-7"
  }
}
```

## 8. Le « champ de température »

```text
.nexus/temperature/
    policy.yaml
    observations.jsonl
    posterior.json
    experiments.jsonl
```

```json
{
  "model": "granite3.3-8b-local",
  "profile": "reasoning",
  "temperature": 0.30,
  "n": 184,
  "quality_mean": 0.914,
  "latency_mean_ms": 3812,
  "retry_rate": 0.021,
  "confidence": 0.88
}
```

Le système détermine alors :

```text
T=0.20 → score 0.81
T=0.30 → score 0.91   ← winner
T=0.40 → score 0.88
T=0.50 → score 0.74
```

et converge vers T ≈ 0.30.

## 9. Ne jamais laisser l'adaptation corrompre le benchmark

Tu as justement découvert aujourd'hui que le cache pouvait fausser les
mesures. Même logique ici. Il faut distinguer **BENCHMARK** et **ONLINE
ADAPTATION**.

Le benchmark doit être : température fixée, cache désactivé, machine
contrôlée, corpus contrôlé. L'adaptation peut ensuite apprendre à partir du
trafic réel.

Sinon tu ne sauras plus si le modèle est meilleur, ou la température a
changé, ou le cache a changé, ou la charge CPU a changé.

## 10. Architecture finale recommandée

**Nexus Adaptive Inference Control.** Ce n'est plus « plusieurs LLM avec un
routeur » mais « un système qui apprend quelles conditions d'inférence
produisent le meilleur compromis qualité / latence / coût pour chaque classe
de tâche et chaque modèle ».

    θ* = argmax_θ  E[ Q − λL − μR − νC ]

où θ est le vecteur d'inférence, pas seulement la température :

    θ = (T, top_p, top_k, max_tokens, context_window, repetition_penalty, seed)

**La température n'est donc que le premier paramètre que le système apprend.**

---

## État au 30 août 2026

Rien de cette architecture n'est implémenté. Ce qui existe déjà :

| Brique de l'AIC | État dans le dépôt |
|---|---|
| Profils de tâche | **existe** — `coding / reasoning / rapide / multimodal` |
| Température par profil | **existe** — 0.0 / 0.1 / 0.2 / 0.4, figée, non apprise |
| Température journalisée | **existe** — `T=` dans l'en-tête de chaque réponse |
| Routage par capacité | **existe** — lit `ollama show`, pas le nom du modèle |
| Benchmark isolé | **existe** — cache neutralisé, chargement séparé |
| Télémétrie | **partiel** — LiteLLM et Langfuse journalisent, rien n'est relu |
| Task Classifier | absent |
| Complexity Estimator | absent |
| Validator / Critic | absent |
| Policy Store | absent |
| Bandit | absent |

Le point 9 est déjà la doctrine du dépôt (§112.3, MANUEL « Mesurer une durée »)
et vient d'être payé **trois fois dans la même journée**. Il devra rester la
première contrainte de toute implémentation : le banc mesure à température
fixe, l'adaptation apprend ailleurs.
