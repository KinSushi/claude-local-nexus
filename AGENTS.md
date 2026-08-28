# AGENTS.md — Universal Agent Contract

## 1. Purpose

This repository hosts an AI execution platform.

Any coding agent operating here must preserve:

* correctness;
* security;
* privacy;
* reproducibility;
* configuration integrity;
* provider boundaries;
* model compatibility;
* observability.

The agent must never treat the repository as a disposable workspace.

---

## 2. Core rule

Always follow:

```text
INSPECT
→ CLASSIFY
→ VALIDATE
→ PLAN
→ MODIFY
→ TEST
→ OBSERVE
→ DOCUMENT
```

Never use:

```text
GUESS
→ MODIFY
→ HOPE
```

---

## 3. Repository authority

Priority:

```text
runtime state
>
source configuration
>
generated configuration
>
validated documentation
>
historical documentation
>
model assumptions
```

When runtime behavior contradicts documentation:

inspect runtime first.

---

## 4. No hallucinated infrastructure

Never invent:

* a model name;
* an endpoint;
* an environment variable;
* a provider;
* a Docker service;
* a script;
* a configuration key;
* a routing feature.

Every such object must be verified from the repository or official provider documentation.

---

## 5. Change discipline

Prefer the smallest change that solves the actual problem.

Avoid:

* unnecessary rewrites;
* broad refactors;
* unrelated formatting changes;
* replacing working infrastructure without evidence.

---

## 6. Destructive operations

Treat the following as high-risk:

```text
git reset --hard
git clean
docker compose down -v
docker volume rm
database deletion
model deletion
credential replacement
irreversible migrations
```

Before execution:

```text
identify impact
check backup
define rollback
validate necessity
```

---

## 7. Secrets

Never:

* expose secrets;
* print secrets;
* commit secrets;
* include secrets in generated documentation;
* copy API keys into logs.

Secrets belong in environment variables or secret-management infrastructure.

---

## 8. Network boundaries

Every cloud call is a data-boundary crossing.

Before sending data externally, evaluate:

```text
classification
provider authorization
user intent
policy
```

Never silently move an L3 workload from local inference to a cloud provider.

---

## 9. Model selection

Do not select models solely by:

* parameter count;
* benchmark score;
* recency;
* popularity.

Evaluate:

```text
capability
context
modality
privacy
latency
resource requirement
cost
reliability
```

---

## 10. Fallback integrity

Fallbacks must preserve:

```text
modality
task semantics
context capability
tool capability
privacy policy
```

No fallback may point to an undefined model alias.

---

## 11. Verification

After infrastructure changes, verify both:

```text
configuration state
```

and:

```text
runtime state
```

A syntactically valid configuration is not proof of a valid deployment.

---

## 12. Agent autonomy

Autonomous operation is acceptable for low-risk actions.

Human review is required for:

```text
destructive operations
production deployment
credential changes
privacy-policy changes
database migrations
external publication
financially consequential actions
```

---

## 13. Completion criterion

A task is not complete until:

```text
implementation
+
validation
+
observability
+
documentation
```

are addressed at the required risk level.
