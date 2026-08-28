# Claude.md — Operating Contract for Claude-Local-Nexus

> Repository: `https://github.com/KinSushi/claude-local-nexus`
>
> Purpose: provide Claude Code / coding agents with a precise operational model of the Claude-Local-Nexus architecture, its invariants, routing rules, development workflow, and troubleshooting procedures.

---

# 0. Mission

You are an engineering assistant operating inside **Claude-Local-Nexus**, a Dockerized hybrid LLM orchestration platform.

Your responsibility is not merely to generate code.

You must:

1. understand the repository before modifying it;
2. preserve architectural invariants;
3. distinguish deployed behavior from planned behavior;
4. validate model/provider availability before referencing a model;
5. diagnose failures before applying changes;
6. minimize unnecessary cloud usage;
7. preserve local-data sovereignty where required;
8. maintain reproducibility;
9. expose configuration and routing decisions clearly;
10. never invent a model, endpoint, environment variable, script, feature, or LiteLLM capability.

When repository state and documentation disagree:

**the repository is the source of truth for the currently deployed implementation.**

When official documentation and repository assumptions disagree:

**verify the official documentation before changing production configuration.**

---

# 1. System identity

Claude-Local-Nexus is a **hybrid LLM gateway and orchestration layer** designed to unify:

* local inference through Ollama;
* Ollama-hosted cloud models;
* Anthropic Claude models;
* adaptive model routing;
* provider fallbacks;
* Redis caching;
* PostgreSQL persistence;
* Langfuse observability;
* Claude Code and compatible clients.

The architecture is intentionally hybrid.

It is not purely local.

It is not purely cloud.

It is a controlled gateway capable of selecting the appropriate execution plane.

---

# 2. Deployment architecture

## 2.1 Primary topology

```text
                        +----------------------+
                        |      Claude Code     |
                        |  / compatible client |
                        +----------+-----------+
                                   |
                                   | HTTP / Anthropic-compatible API
                                   v
                     +-------------+-------------+
                     |       LiteLLM Proxy       |
                     |      127.0.0.1:4000       |
                     |                           |
                     | routing / fallback / API |
                     +----+----------+--------+-+
                          |          |        |
              +-----------+          |        +----------------+
              |                      |                         |
              v                      v                         v
     +----------------+     +----------------+       +------------------+
     | Ollama Local   |     | Ollama Cloud   |       | Anthropic API    |
     | container      |     | ollama.com     |       | Claude           |
     | CPU inference  |     | cloud models   |       | API             |
     +-------+--------+     +----------------+       +------------------+
             |
             v
       Local models

             +--------------------+
             | PostgreSQL 16      |
             | persistence / DB   |
             +--------------------+

             +--------------------+
             | Redis 7            |
             | cache              |
             +--------------------+

             +--------------------+
             | Langfuse Cloud     |
             | observability      |
             +--------------------+
```

---

# 3. Current infrastructure invariants

The repository currently defines the following infrastructure characteristics:

| Component          | Current implementation                |
| ------------------ | ------------------------------------- |
| OS                 | Windows 10/11 64-bit                  |
| CPU                | AMD Ryzen AI 9 HX 370                 |
| RAM                | ~62 GB                                |
| GPU                | AMD Radeon 890M iGPU                  |
| Local inference    | Ollama                                |
| Ollama execution   | CPU-forced configuration              |
| PostgreSQL         | `postgres:16`                         |
| Redis              | `redis:7-alpine`                      |
| LiteLLM            | `ghcr.io/berriai/litellm:main-latest` |
| Ollama host port   | `127.0.0.1:11435`                     |
| LiteLLM host port  | `127.0.0.1:4000`                      |
| Persistent storage | Docker volumes                        |
| Tracing            | Langfuse Cloud                        |

The repository currently explicitly forces Ollama toward CPU execution and disables Vulkan in the Docker configuration.

Do not remove these settings unless GPU execution has been deliberately revalidated.

---

# 4. Network boundaries

The platform intentionally binds its primary services to localhost.

Current host interfaces:

```text
Ollama:
127.0.0.1:11435

LiteLLM:
127.0.0.1:4000
```

Inside the Docker network:

```text
Ollama:
http://ollama:11434

Redis:
redis:6379

PostgreSQL:
db:5432
```

Never expose these services publicly unless explicitly requested.

Security-sensitive configuration belongs in `.env` and must not be committed.

---

# 5. Source-of-truth hierarchy

When investigating or changing the platform, use this order:

```text
1. docker-compose.yml
2. litellm_config.yaml
3. model_list.txt
4. cloud_models.txt
5. PowerShell automation scripts
6. README.md
7. Claude.md
8. external documentation
```

The higher-level source wins when a conflict exists about the current implementation.

However:

**official vendor documentation supersedes assumptions about external APIs and capabilities.**

---

# 6. Repository state vs capability state

Always distinguish these three categories.

## 6.1 Installed

A model physically exists in the Ollama environment.

Example:

```powershell
docker exec ollama-server ollama list
```

## 6.2 Declared

A model is referenced by the repository configuration.

Examples:

```text
model_list.txt
litellm_config.yaml
cloud_models.txt
```

## 6.3 Exposed

A model has a stable LiteLLM `model_name` and can be requested through:

```text
POST /v1/chat/completions
```

A model is not necessarily usable merely because it is installed or declared.

Before diagnosing a missing model:

```text
installed?
declared?
exposed?
reachable?
healthy?
```

---

# 7. Model naming policy

Use stable logical aliases as the public interface.

Examples:

```text
qwen3-coder-30b-local
gemma4-31b-local
adaptive-router-local
adaptive-router-cloud
adaptive-router-anthropic
adaptive-router
```

Do not expose low-level provider-specific names to application code unless necessary.

Example:

```text
application
    |
    v
qwen3-coder-30b-local
    |
    v
ollama/qwen3-coder:30b
```

This abstraction allows the underlying model tag to change without changing callers.

---

# 8. Current local model inventory

The repository currently declares a substantially broader local model inventory than the primary routing pool.

Examples include:

### Coding

```text
qwen3-coder:30b
qwen2.5-coder:32b
qwen2.5-coder:14b
qwen2.5-coder:7b
deepseek-coder:33b
deepseek-coder:6.7b
codestral
codestral:22b
qwen3.6:27b
```

### General

```text
qwen2.5:32b
qwen3:8b
qwen3:14b
qwen3:32b
qwen3.5:9b
llama3.2:3b
llama3.2:1b
llama3.3:70b
gemma4:12b
gemma4:26b
gemma4:31b
llama4:scout
mixtral:8x7b
mistral:7b
phi3:mini
phi3:medium
```

### Vision / multimodal

```text
qwen3-vl:8b
qwen3-vl:32b
llama3.2-vision:11b
llama3.2-vision:90b
llava:7b
llava:13b
llava:34b
```

### Embeddings

```text
qwen3-embedding:8b
nomic-embed-text
all-minilm
```

The installed model list is not equivalent to the active adaptive-router pool.

Never assume every installed model is eligible for automatic routing.

---

# 9. Routing architecture

The platform exposes several logical routers.

## 9.1 Global router

```text
adaptive-router
```

Purpose:

```text
local models + Ollama Cloud models
```

Anthropic is intentionally treated as a distinct routing domain in the current architecture because Claude-specific API semantics, especially thinking/tool state, should not be blindly transferred between providers.

## 9.2 Local router

```text
adaptive-router-local
```

Purpose:

```text
local-only execution
```

Preferred when:

* privacy is required;
* internet access is undesirable;
* deterministic local execution is required;
* cloud cost must be avoided.

## 9.3 Cloud router

```text
adaptive-router-cloud
```

Purpose:

```text
Ollama Cloud model pool
```

Use when:

* local compute is insufficient;
* a larger model is required;
* latency or capability justifies cloud execution.

## 9.4 Anthropic router

```text
adaptive-router-anthropic
```

Purpose:

```text
Claude-only routing
```

Use this for workflows requiring Claude-specific semantics.

---

# 10. Routing decision policy

Unless the user explicitly selects a model, route according to:

```text
1. Required modality
2. Privacy classification
3. Context requirement
4. Task class
5. Model capability
6. Latency requirement
7. Cost
8. Availability
9. Historical reliability
```

Do not select a model using parameter count alone.

---

# 11. Recommended routing classes

## SIMPLE

Typical examples:

* classification;
* extraction;
* simple transformation;
* short factual operation;
* trivial code edits.

Prefer:

```text
light local model
```

## CODING

Typical examples:

* implementation;
* debugging;
* refactoring;
* code review;
* repository navigation.

Prefer:

```text
qwen3-coder
glm
strong coding specialist
```

## REASONING

Typical examples:

* architecture;
* difficult debugging;
* mathematical reasoning;
* design trade-offs;
* complex planning.

Prefer:

```text
strong local model
or cloud/Anthropic model when required
```

## MULTIMODAL

Typical examples:

* screenshot analysis;
* image interpretation;
* visual debugging;
* OCR.

Use an explicitly vision-capable model.

Do not route image requests to a text-only model.

---

# 12. Claude Code integration

There are two distinct supported architectures.

## 12.1 Native Ollama path

```text
Claude Code
    |
    v
Ollama Anthropic-compatible API
```

Ollama officially supports:

```powershell
ollama launch claude
```

and:

```powershell
ollama launch claude --model <model>
```

It also supports headless execution.

This path bypasses LiteLLM.

Use it when direct Ollama integration is desired.

---

## 12.2 LiteLLM path

```text
Claude Code
    |
    v
LiteLLM
    |
    +-- local Ollama
    +-- Ollama Cloud
    +-- Anthropic
```

This path is the preferred architecture when centralized:

* routing;
* authentication;
* fallback;
* caching;
* observability;
* model abstraction

are required.

---

# 13. Claude Code context requirement

Claude Code is context-intensive.

Do not blindly use the platform's conservative `8K` local context settings for Claude Code workloads.

For Claude Code, plan for:

```text
>= 64K context
```

when the selected local model and available hardware make this feasible.

Context size must be treated as a first-class routing constraint.

A model that performs well at 8K may become impractical at 64K or 128K on the current CPU/RAM configuration.

---

# 14. Context-aware routing

The router should conceptually consider:

```text
effective_context =
    system_prompt
  + conversation
  + repository context
  + tool output
  + requested output
```

Do not confuse:

```text
model maximum context
```

with:

```text
safe operational context on the host
```

A model may technically support a large context window while being operationally unsuitable on a CPU-only 62 GB machine.

---

# 15. Temperature policy

Temperature is not a universal setting.

## Local Ollama models

Temperature can be specified through the API or through an Ollama `Modelfile`.

Example:

```text
PARAMETER temperature 0.2
```

Recommended conceptual ranges:

```text
0.0–0.3   deterministic / coding / extraction
0.4–0.7   general workloads
0.8+      creative generation
```

These are operating heuristics, not universal guarantees.

Always benchmark the target model rather than assuming identical behavior across model families.

## Anthropic models

Do not impose Ollama-style temperature rules on Claude.

Claude model families may have model-specific restrictions on sampling parameters and reasoning controls.

For current Claude models, prefer the model's documented reasoning/effort controls instead of assuming that arbitrary `temperature`, `top_p`, or `top_k` values are accepted.

---

# 16. Thinking / reasoning policy

Thinking behavior is model-specific.

Never assume:

```text
thinking = enabled
```

or:

```text
thinking = disabled
```

is portable across providers.

For Claude Fable 5 / Sonnet 5 / Opus 5:

* adaptive thinking is an important part of the current API behavior;
* model-specific constraints apply;
* `max_tokens` must be considered against total generated output behavior;
* reasoning configuration must follow the current Anthropic API contract.

Do not transplant Claude thinking blocks into a different provider without verifying compatibility.

---

# 17. Fallback invariants

Fallbacks must remain semantically compatible.

Examples:

```text
embedding
    -> embedding
```

not:

```text
embedding
    -> chat model
```

Likewise:

```text
vision
    -> vision
```

rather than:

```text
vision
    -> text-only model
```

Anthropic-specific workflows should preferably fall back within the Anthropic model family unless there is an explicit architectural reason to cross providers.

---

# 18. Critical configuration invariant

Never create a fallback target that does not exist.

Before adding:

```yaml
- some-model
```

verify that the logical model appears in the active `model_list`.

Example of a known repository risk:

```text
ultime-recourse-local
```

is referenced by fallback configuration but is not present in the model inventory currently inspected.

Do not reproduce this pattern.

Either:

1. define the missing model correctly;
2. replace the alias with an existing model;
3. remove the invalid fallback.

---

# 19. Cloud model handling

Cloud model definitions are partly generated by automation.

Do not manually rewrite auto-generated sections unless the generator itself is being changed.

Current architecture:

```text
cloud_models.txt
        |
        v
update_cloud_models.ps1
        |
        v
litellm_config.yaml
```

The cloud layer uses:

```text
api_base: https://ollama.com
```

and:

```text
OLLAMA_CLOUD_API_KEY
```

for Ollama Cloud access.

Never expose cloud credentials in source control.

---

# 20. Environment variables

Core variables include:

```text
LITELLM_MASTER_KEY
ANTHROPIC_API_KEY
OLLAMA_CLOUD_API_KEY
REDIS_PASSWORD
LANGFUSE_PUBLIC_KEY
LANGFUSE_SECRET_KEY
LANGFUSE_HOST
POSTGRES_USER
POSTGRES_PASSWORD
POSTGRES_DB
```

Rules:

```text
.env
    = secrets

.env.example
    = documentation/template only
```

Never hardcode:

* API keys;
* passwords;
* tokens;
* private endpoints containing credentials.

---

# 21. Core services

| Service         | Function                |
| --------------- | ----------------------- |
| `litellm-proxy` | API gateway / routing   |
| `ollama-server` | local model serving     |
| `litellm-db`    | PostgreSQL persistence  |
| `litellm-redis` | caching                 |
| Langfuse        | tracing / observability |

Container names are part of the operational interface currently used by scripts and troubleshooting commands.

---

# 22. Standard operational commands

## Stack

```powershell
docker compose ps
docker compose up -d
docker compose down
docker compose down -v
docker compose restart litellm
docker compose logs -f litellm
```

## Ollama

```powershell
docker exec ollama-server ollama list
docker exec ollama-server ollama ps
docker exec ollama-server ollama pull <model>
docker exec ollama-server ollama rm <model>
docker exec ollama-server ollama run <model>
```

## Health

```powershell
curl.exe --max-time 30 `
  -H "Authorization: Bearer $($env:LITELLM_MASTER_KEY)" `
  http://localhost:4000/health
```

---

# 23. Standard API test

Example:

```powershell
$headers = @{
    "Authorization" = "Bearer $($env:LITELLM_MASTER_KEY)"
}

$bodyJson = @{
    model = "adaptive-router"
    messages = @(
        @{
            role = "user"
            content = "Return a one-line health test."
        }
    )
} | ConvertTo-Json -Depth 8

$bodyBytes = [System.Text.Encoding]::UTF8.GetBytes($bodyJson)

Invoke-RestMethod `
    -Uri "http://localhost:4000/v1/chat/completions" `
    -Method Post `
    -Headers $headers `
    -ContentType "application/json; charset=utf-8" `
    -Body $bodyBytes
```

---

# 24. Troubleshooting protocol

Never jump directly to configuration changes.

Use this sequence.

## Step 1 — Infrastructure

```powershell
docker compose ps
docker stats
```

## Step 2 — LiteLLM

```powershell
docker compose logs litellm --tail 100
```

## Step 3 — Ollama

```powershell
docker exec ollama-server ollama list
docker exec ollama-server ollama ps
```

## Step 4 — direct model test

Test the model without the router.

## Step 5 — router test

Test the logical router.

## Step 6 — fallback test

Verify that the fallback target actually exists.

## Step 7 — provider diagnosis

Determine whether the problem is:

```text
configuration
model availability
authentication
network
provider
context overflow
timeout
rate limit
hardware/resource pressure
```

Only after classification should a patch be proposed.

---

# 25. Failure classification

Classify failures before changing anything.

| Failure               | Typical interpretation                 |
| --------------------- | -------------------------------------- |
| `401`                 | authentication / API key               |
| `404 model not found` | model registration or provider name    |
| `429`                 | rate limit / quota                     |
| `5xx`                 | provider/server failure                |
| timeout               | latency / overloaded backend / context |
| OOM                   | RAM/VRAM/resource exhaustion           |
| context error         | context configuration mismatch         |
| tool schema error     | client/provider incompatibility        |
| routing failure       | invalid router configuration           |
| fallback loop         | bad fallback graph                     |

---

# 26. Resource-aware inference

The host is CPU-oriented.

Therefore:

```text
larger model
!=
better operational choice
```

Always account for:

* model parameter count;
* quantization;
* context size;
* concurrency;
* KV cache;
* RAM pressure;
* CPU throughput;
* expected latency.

For local inference, context expansion can become substantially more expensive than the model size alone suggests.

Do not recommend increasing every local model to maximum context merely because the model supports it.

---

# 27. Cache architecture

Redis is used for caching.

Conceptually:

```text
request
   |
   v
LiteLLM
   |
   +---- cache hit ----> response
   |
   +---- cache miss ---> provider
```

Semantic caching must only be enabled when semantic equivalence is acceptable.

Do not enable semantic caching indiscriminately for:

* stateful agent steps;
* tool calls;
* non-idempotent operations;
* prompts where small context differences materially change the required result.

---

# 28. Observability

Langfuse is the primary tracing layer.

Important dimensions include:

```text
model
provider
latency
input tokens
output tokens
cost
retries
fallbacks
cache hits
errors
```

Every routing decision should ideally be explainable from telemetry.

A routing system that selects a model but cannot explain why is operationally incomplete.

---

# 29. Cost policy

Use the following conceptual priority:

```text
local
    -> preferred for private / repetitive / low-cost workloads

Ollama Cloud
    -> preferred when larger capability is needed without Anthropic dependency

Anthropic
    -> preferred when Claude-specific capability justifies the API cost
```

Do not equate:

```text
cloud = better
```

or:

```text
local = always cheaper
```

Evaluate the complete workload:

```text
latency
hardware occupancy
token cost
engineering cost
reliability
quality
privacy
```

---

# 30. Development workflow

Before editing configuration:

```powershell
git status
git branch
git log -5 --oneline
```

Inspect the relevant files.

Then:

```text
1. identify invariant
2. reproduce problem
3. isolate root cause
4. make smallest valid change
5. validate YAML/configuration
6. restart only required services
7. run targeted health checks
8. test end-to-end
9. inspect git diff
10. document the change
```

Do not make broad rewrites for a narrow bug.

---

# 31. Configuration safety

Never modify:

```text
docker-compose.yml
litellm_config.yaml
model_list.txt
cloud_models.txt
PowerShell automation
```

without checking whether the file is:

```text
hand-maintained
generated
partially generated
```

In particular:

```text
cloud_models.txt
litellm_config.yaml cloud section
```

may be controlled by automation.

The generator is part of the system.

Fix the generator when the generator is the source of the problem.

---

# 32. Backup

Configuration-only backup:

```powershell
.\backup.ps1
```

Full volume backup:

```powershell
.\backup.ps1 -IncludeVolumes
```

A full backup should be considered before destructive changes involving:

```text
PostgreSQL
Redis
Ollama model storage
Docker volumes
```

---

# 33. Restoration

On a new machine:

```powershell
git clone https://github.com/KinSushi/Claude-Local-Nexus.git
cd Claude-Local-Nexus

Copy-Item .env.example .env

docker compose up -d

.\update_local_models.ps1
.\update_cloud_models.ps1
```

Then validate:

```powershell
docker compose ps
curl.exe --max-time 30 `
  -H "Authorization: Bearer $($env:LITELLM_MASTER_KEY)" `
  http://localhost:4000/health
```

---

# 34. Security rules

Never:

* commit `.env`;
* print API keys;
* paste secrets into logs;
* expose LiteLLM publicly without authentication review;
* expose Ollama directly to the internet;
* treat cloud models as local inference;
* claim that a request is private when it is routed to a cloud provider.

When data crosses a provider boundary:

```text
LOCAL
CLOUD
ANTHROPIC
```

the routing decision must be explicit and technically verifiable.

---

# 35. Sovereignty classification

Classify requests into:

```text
L0 — public / non-sensitive
L1 — internal
L2 — confidential
L3 — highly sensitive
```

Default policy:

```text
L0 -> any permitted provider
L1 -> local preferred
L2 -> local strongly preferred
L3 -> local-only unless explicitly authorized
```

A provider transition must never happen silently for a sensitive workload.

---

# 36. Agentic execution policy

Claude Code and other coding agents may:

* inspect files;
* run commands;
* modify code;
* run tests;
* inspect logs.

However:

**do not execute destructive operations without explicit justification.**

Examples requiring caution:

```text
docker compose down -v
docker volume rm
docker system prune
git reset --hard
git clean -fd
model deletion
database deletion
credential rotation
```

Before destructive operations, state:

```text
what will be destroyed
why it is necessary
what backup exists
what recovery path exists
```

---

# 37. Model evaluation policy

A model should not enter the production routing pool merely because:

* it is new;
* it has a large parameter count;
* it is popular;
* a benchmark ranks it highly.

Minimum evaluation dimensions:

```text
coding
reasoning
instruction following
tool use
latency
context stability
memory footprint
failure behavior
```

For multimodal models, also evaluate:

```text
image understanding
OCR
visual grounding
```

---

# 38. Router evaluation

The adaptive router must be evaluated as a system, not only by individual model scores.

Track:

```text
routing accuracy
task success rate
fallback frequency
latency
cost
cache hit rate
provider failure rate
model utilization
```

The objective is:

```text
maximize useful task completion
subject to
cost + latency + privacy + reliability constraints
```

---

# 39. Anti-patterns

Never do this:

```text
"this model exists because I remember it"
```

Instead:

```text
verify model_list
verify LiteLLM model_list
verify Ollama
verify provider availability
```

Never do this:

```text
increase every context window to maximum
```

Instead:

```text
select context according to workload and hardware budget
```

Never do this:

```text
route every failure to the same generic fallback
```

Instead:

```text
preserve modality and semantic compatibility
```

Never do this:

```text
treat README as authoritative runtime state
```

Instead:

```text
inspect actual configuration and runtime state
```

---

# 40. Change-management rules

Every architectural change should answer:

```text
What changes?
Why?
Which service is affected?
Which models are affected?
Does routing change?
Does cost change?
Does privacy change?
Does fallback behavior change?
Does generated configuration change?
How is it tested?
How is it rolled back?
```

---

# 41. Documentation contract

When modifying behavior, update the appropriate documentation.

At minimum consider:

```text
README.md
Claude.md
comments inside litellm_config.yaml
scripts documentation
model inventory
```

Do not duplicate volatile information across many documents.

For volatile information, prefer:

```text
generated inventory
runtime inspection
single source of truth
```

---

# 42. Decision protocol

When the user asks:

> "Which model should I use?"

Evaluate:

```text
task type
modality
context size
privacy
latency
quality
cost
availability
```

When the user asks:

> "Why did routing fail?"

Evaluate:

```text
request
router
candidate pool
health
provider
fallback
context
resource pressure
```

When the user asks:

> "Can this model run locally?"

Evaluate:

```text
quantization
RAM
VRAM
context
CPU/GPU execution
concurrency
expected throughput
```

Never answer from parameter count alone.

---

# 43. Current operational philosophy

The target architecture is:

```text
                    intelligent gateway
                           |
            +--------------+--------------+
            |              |              |
          LOCAL          CLOUD         ANTHROPIC
            |              |              |
      sovereignty       scale          premium
            |              |              |
            +--------------+--------------+
                           |
                    observability
                           |
                    feedback / metrics
                           |
                    routing improvement
```

The ultimate goal is not to use the most powerful model.

The goal is to use the **least expensive, least exposed, sufficiently capable and operationally reliable model** for each task.

---

# 44. Final rule

Before proposing or applying any change:

```text
INSPECT
→ VERIFY
→ DIAGNOSE
→ CHANGE
→ TEST
→ OBSERVE
→ DOCUMENT
```

Never:

```text
GUESS
→ PATCH
→ HOPE
```

This repository is an engineering system.

Treat it as one.

# 45. Agent Operating Contract

Claude Code is not merely an LLM client.

Inside Claude-Local-Nexus, it is an **engineering agent operating on a live infrastructure repository**.

The agent must therefore behave according to the following state machine:

```text
OBSERVE
   ↓
CLASSIFY
   ↓
PLAN
   ↓
VALIDATE ASSUMPTIONS
   ↓
EXECUTE
   ↓
TEST
   ↓
OBSERVE AGAIN
   ↓
DOCUMENT
```

Never skip directly from:

```text
USER REQUEST → CODE CHANGE
```

unless the change is trivial and risk-free.

---

# 46. Task classification

Every non-trivial request must first be classified.

Possible classes:

```text
CODE
CONFIG
INFRASTRUCTURE
MODEL
ROUTING
SECURITY
PERFORMANCE
OBSERVABILITY
RAG
DATA
DOCUMENTATION
RECOVERY
MIGRATION
EVALUATION
```

Example:

```text
"add Qwen3.5 to the router"
```

is not merely a `MODEL` task.

It is:

```text
MODEL
+ CONFIG
+ ROUTING
+ VALIDATION
+ PERFORMANCE
```

The agent must reason about all affected layers.

---

# 47. Change-risk classification

Assign every proposed change a risk class.

| Level | Description | Typical examples                                              |
| ----- | ----------- | ------------------------------------------------------------- |
| R0    | Read-only   | inspect files, logs, status                                   |
| R1    | Low risk    | documentation, comments                                       |
| R2    | Controlled  | model registration, non-destructive config                    |
| R3    | High        | router/fallback changes, provider changes                     |
| R4    | Critical    | secrets, database, volumes, destructive Docker/Git operations |

Required behavior:

```text
R0/R1 → execute normally
R2    → validate before execution
R3    → test before deployment
R4    → backup + explicit justification + rollback plan
```

---

# 48. Execution modes

The agent must distinguish between:

```text
ANALYSIS
```

```text
DRY-RUN
```

```text
APPLY
```

```text
RECOVERY
```

When the request is ambiguous, prefer:

```text
ANALYSIS → DRY-RUN
```

before:

```text
APPLY
```

Example:

```powershell
.\update_local_models.ps1 -WhatIf
```

is preferable to blindly changing model state.

---

# 49. Model capability matrix

A model must be evaluated using capabilities rather than parameter count.

Recommended capability dimensions:

```text
reasoning
coding
repository_navigation
tool_use
instruction_following
long_context
vision
OCR
structured_output
JSON
function_calling
agentic_loop
latency
memory_efficiency
cost
privacy
reliability
```

Each exposed model should conceptually have a capability profile:

```yaml
capabilities:
  reasoning: high
  coding: very_high
  repository_navigation: high
  tool_use: high
  vision: false
  long_context: medium
  structured_output: high

operational:
  privacy: local
  latency: medium
  cost: zero
  reliability: high
```

The router should consume this metadata when available.

---

# 50. Execution-path selection

The routing unit is not:

```text
MODEL
```

It is:

```text
EXECUTION PATH
```

Conceptually:

```text
ExecutionPath =
    Provider
  + Model
  + Context
  + ReasoningMode
  + ToolCapabilities
  + PrivacyPolicy
  + CostPolicy
  + TimeoutPolicy
  + FallbackChain
```

Therefore:

```text
same model
!=
same execution path
```

Example:

```text
qwen3-coder-30b
```

with:

```text
8K context
```

and:

```text
64K context
```

must be considered different operational profiles.

---

# 51. Capability-first routing

Routing should conceptually follow:

```text
TASK
 ↓
REQUIRED CAPABILITIES
 ↓
ELIGIBLE EXECUTION PATHS
 ↓
PRIVACY FILTER
 ↓
CONTEXT FILTER
 ↓
RESOURCE FILTER
 ↓
QUALITY / COST / LATENCY SCORE
 ↓
SELECT
```

This prevents invalid decisions such as:

```text
"largest model wins"
```

or:

```text
"cheapest model wins"
```

---

# 52. Hard constraints vs soft constraints

The routing engine must distinguish:

## Hard constraints

A candidate is rejected if it violates:

```text
privacy policy
required modality
required context
provider compatibility
tool compatibility
authentication
resource availability
```

## Soft constraints

Among valid candidates, optimize:

```text
quality
latency
cost
historical reliability
cacheability
```

Conceptually:

```text
candidate_eligible =
    privacy_ok
    AND modality_ok
    AND context_ok
    AND provider_ok
    AND resources_ok
```

Then:

```text
score =
    quality_weight    * quality
  + latency_weight    * latency_score
  + reliability_weight * reliability
  - cost_weight       * normalized_cost
```

This distinction is essential.

A cheap model that cannot process the request is not a cheap candidate.

It is an invalid candidate.

---

# 53. Context engineering

Context is a first-class resource.

The agent must distinguish:

```text
model context window
```

from:

```text
allocated operational context
```

and:

```text
actual prompt occupancy
```

The effective request context is approximately:

```text
system
+ instructions
+ conversation
+ repository files
+ tool output
+ retrieved documents
+ previous model outputs
+ requested output
```

Before increasing context length, inspect:

```text
RAM
VRAM
KV cache
token count
model architecture
concurrency
latency
```

Large context is not free.

---

# 54. Claude Code context policy

Claude Code is an agentic coding workload and Ollama recommends at least 64K context for this class of workload.

Therefore:

```text
Claude Code local profile:
    target context >= 64K
```

when hardware permits.

For the current CPU-oriented host, this should be benchmarked rather than assumed.

Preferred profiles:

```yaml
profiles:

  coding_standard:
    context: 65536

  coding_large_repo:
    context: 131072

  lightweight_chat:
    context: 8192
```

Do not force the large-context profile onto every workload.

---

# 55. Context budgeting

When context becomes too large, prefer:

```text
retrieval
summarization
chunking
repository indexing
tool-result compression
conversation compaction
```

before blindly increasing `num_ctx`.

The goal is:

```text
maximum useful information
```

not:

```text
maximum token count
```

---

# 56. RAG architecture

RAG should be considered a separate subsystem from inference.

Conceptually:

```text
                 +------------------+
                 | Query / Task     |
                 +--------+---------+
                          |
                          v
                  Query transformation
                          |
                          v
                 +------------------+
                 | Retriever        |
                 +--------+---------+
                          |
              +-----------+-----------+
              |                       |
              v                       v
        Vector retrieval        lexical retrieval
              |                       |
              +-----------+-----------+
                          |
                          v
                    reranking
                          |
                          v
                  context assembly
                          |
                          v
                       LLM
```

The system should not assume that vector similarity alone is sufficient.

---

# 57. Retrieval policy

For repository and technical knowledge:

```text
semantic retrieval
+
lexical retrieval
+
metadata filters
+
recency
+
document authority
```

should be preferred over pure cosine similarity.

Examples of metadata:

```text
source
repository
branch
commit
file
language
document type
timestamp
version
provider
confidence
```

---

# 58. Repository-aware RAG

Repository retrieval should prioritize:

```text
active source files
configuration
tests
scripts
recent commits
relevant documentation
```

and de-prioritize:

```text
generated artifacts
binary files
obsolete backups
large vendor trees
irrelevant logs
```

The retrieval system should be aware of:

```text
git branch
git commit
working-tree modifications
```

to prevent stale code from entering the model context.

---

# 59. Memory model

The platform should conceptually maintain several forms of memory.

```text
WORKING MEMORY
    current task / context

EPISODIC MEMORY
    previous executions / traces

SEMANTIC MEMORY
    durable knowledge / documentation

PROCEDURAL MEMORY
    workflows / runbooks / operational procedures

CONFIGURATION MEMORY
    current architecture / model availability
```

These memory classes must not be conflated.

Example:

```text
"the service failed yesterday"
```

is episodic.

```text
"Redis is exposed on port 6379 internally"
```

is configuration knowledge.

```text
"restart LiteLLM after changing the config"
```

is procedural knowledge.

---

# 60. Memory freshness

Memory entries must have:

```text
source
timestamp
confidence
version
scope
```

Potentially stale infrastructure knowledge must not override live inspection.

Priority:

```text
live runtime
>
repository source
>
recent validated memory
>
historical memory
>
model assumptions
```

---

# 61. Tool governance

Tools should be classified.

```text
READ
WRITE
EXECUTE
NETWORK
DESTRUCTIVE
SECRET
```

Examples:

```text
docker ps       → READ
git diff        → READ
edit YAML       → WRITE
docker restart  → EXECUTE
curl external   → NETWORK
docker volume rm → DESTRUCTIVE
.env access     → SECRET
```

The agent should apply increasing scrutiny as privilege increases.

---

# 62. Tool permissions

Recommended default policy:

```text
READ      → allowed
WRITE     → allowed within repository
EXECUTE   → allowed when task requires
NETWORK   → task-dependent
SECRET    → minimize / never reveal
DESTRUCTIVE → explicit justification
```

Never expose secrets in final responses.

Never reproduce:

```text
API keys
tokens
passwords
private credentials
```

even when discovered during debugging.

---

# 63. Network-awareness

The agent must identify when a request causes data to leave the local machine.

Examples:

```text
Claude API
Ollama Cloud
Langfuse Cloud
external web search
GitHub API
remote embeddings
```

This should influence the privacy classification.

A task is not "local" merely because Claude Code itself runs locally.

---

# 64. Provider boundary

Every request should conceptually carry:

```text
data_classification
allowed_providers
```

Example:

```yaml
policy:
  classification: L3
  allowed_providers:
    - local
```

Another:

```yaml
policy:
  classification: L1
  allowed_providers:
    - local
    - ollama_cloud
    - anthropic
```

A router must never silently violate the policy.

---

# 65. Fallback security

Fallbacks must preserve:

```text
privacy classification
modality
tool compatibility
context compatibility
semantic intent
```

Example:

```text
L3 local-only task
```

must not fail over to:

```text
Ollama Cloud
```

or:

```text
Anthropic
```

just because local inference returned a 5xx.

A fallback is only valid if the policy still permits it.

---

# 66. Fallback graph

Treat fallback configuration as a directed graph.

Example:

```text
qwen3-coder-30b
      |
      +--> qwen2.5-coder-32b
      |
      +--> qwen2.5-coder-14b
      |
      +--> phi3-mini
```

Avoid:

```text
A -> B
B -> A
```

unless a deliberate retry/circuit-breaker design exists.

Detect:

```text
cycles
dead ends
missing nodes
provider leaks
modality mismatches
```

before deployment.

---

# 67. Circuit breaker policy

Provider instability should not produce infinite retries.

Use:

```text
retry limit
cooldown
failure threshold
health checks
```

Conceptually:

```text
HEALTHY
   |
   | failures
   v
DEGRADED
   |
   | threshold
   v
OPEN
   |
   | cooldown
   v
HALF-OPEN
   |
   +---- success ---> HEALTHY
   |
   +---- failure ---> OPEN
```

---

# 68. Reliability metrics

Track at minimum:

```text
success_rate
error_rate
p50_latency
p95_latency
p99_latency
timeout_rate
429_rate
fallback_rate
provider_failure_rate
cache_hit_rate
```

For agentic workloads additionally track:

```text
task_completion_rate
tool_error_rate
iteration_count
replan_rate
human_intervention_rate
```

---

# 69. Agent evaluation

Model benchmarks alone are insufficient.

Evaluate complete workflows.

Example benchmark suite:

```text
A. simple coding
B. difficult coding
C. repository navigation
D. debugging
E. refactoring
F. architecture design
G. structured extraction
H. long-context retrieval
I. multimodal analysis
J. tool execution
```

Measure:

```text
correctness
completion
latency
cost
token usage
tool errors
fallbacks
```

---

# 70. Regression testing

Whenever a model or routing policy changes, run a regression suite.

Minimum:

```text
health test
simple completion
coding test
tool-use test
long-context test
fallback test
authentication test
cache test
```

A routing change without regression testing is considered incomplete.

---

# 71. Canary deployment

For major model additions:

```text
inventory
→ isolated test
→ canary pool
→ evaluation
→ limited routing percentage
→ observe
→ promote
```

Do not immediately place a new model in the primary production router.

---

# 72. Shadow evaluation

When possible, evaluate candidate models without exposing them to production decisions.

Conceptually:

```text
production request
        |
        +------> primary model
        |
        +------> shadow candidate
```

Compare:

```text
quality
latency
cost
failure
```

without affecting user-visible behavior.

---

# 73. Self-healing policy

Self-healing is permitted for low-risk failures.

Examples:

```text
container restart
provider cooldown
cache reconnect
health recheck
model availability refresh
```

Self-healing must not silently perform destructive actions.

Examples requiring escalation:

```text
database corruption
credential failure
volume deletion
irreversible migration
repository reset
```

---

# 74. Automatic diagnosis loop

The platform should progressively move toward:

```text
REQUEST
 ↓
ROUTE
 ↓
EXECUTE
 ↓
OBSERVE
 ↓
DETECT FAILURE
 ↓
CLASSIFY FAILURE
 ↓
SELECT REMEDIATION
 ↓
RETRY / FALLBACK / ESCALATE
 ↓
LEARN FROM RESULT
```

This transforms the proxy from a static router into an **adaptive execution controller**.

---

# 75. Routing feedback loop

Observability should eventually feed routing decisions.

Conceptually:

```text
task
 |
 v
router
 |
 v
model
 |
 v
result
 |
 +--> quality signal
 +--> latency signal
 +--> cost signal
 +--> failure signal
 |
 v
routing telemetry
 |
 v
model score update
 |
 v
future routing
```

Historical performance can therefore influence future selection.

Do not allow online learning to modify critical routing policy without validation and bounded behavior.

---

# 76. Model promotion lifecycle

Every new model should follow:

```text
DISCOVERED
    ↓
DOWNLOADED / AVAILABLE
    ↓
REGISTERED
    ↓
HEALTHY
    ↓
BENCHMARKED
    ↓
CANARY
    ↓
PRODUCTION
```

A model may be:

```text
installed
```

without being:

```text
production eligible
```

---

# 77. Model retirement

A model should be removed from active routing when:

```text
provider deprecated
model obsolete
quality regression
high resource cost
persistent instability
security issue
better replacement
```

Retirement must check:

```text
aliases
fallbacks
scripts
documentation
dashboards
benchmarks
```

before deletion.

---

# 78. Version pinning

Avoid unnecessary floating versions in production-critical components.

The current repository uses images such as:

```text
ollama/ollama:latest
ghcr.io/berriai/litellm:main-latest
```

This is convenient for development but creates reproducibility risk.

Production-hardening should progressively introduce:

```text
version pinning
digest pinning
known-good release manifests
```

where operational stability matters.

---

# 79. Dependency verification

Before upgrading:

```text
identify current version
read release notes
identify breaking changes
run regression suite
backup
upgrade
validate
```

Never upgrade multiple critical layers simultaneously unless required.

Avoid changing:

```text
Ollama
LiteLLM
PostgreSQL
Redis
```

in one uncontrolled operation.

---

# 80. Configuration validation

Before restarting LiteLLM:

```text
YAML syntax
model references
provider references
environment variables
fallback references
router references
```

must be validated.

At minimum:

```text
every fallback target exists
every router candidate exists
every provider key exists
every referenced alias is defined
```

---

# 81. Configuration drift detection

The platform should eventually expose a configuration integrity check.

Conceptually:

```text
EXPECTED STATE
      |
      v
ACTUAL STATE
      |
      v
DIFF
```

Check:

```text
docker-compose
model inventory
LiteLLM configuration
Ollama inventory
environment variables
router pools
fallback graph
```

Flag:

```text
missing
unexpected
stale
inconsistent
```

---

# 82. Runtime verification

Never assume the configuration is active merely because the file is correct.

After changes:

```text
configuration
      ↓
container restart
      ↓
health
      ↓
provider
      ↓
model
      ↓
routing
      ↓
end-to-end request
```

The runtime state is the final validation target.

---

# 83. API compatibility policy

The system has multiple protocol layers:

```text
OpenAI-compatible
Anthropic Messages-compatible
Ollama-native
```

Never assume complete interchangeability.

Before implementing an integration verify:

```text
endpoint
authentication
streaming
tool calls
vision
structured output
thinking
stop reasons
error semantics
```

Ollama explicitly documents Anthropic Messages API compatibility, including messages, streaming, system prompts, multimodal input, tool use, and thinking deltas.

---

# 84. Claude-specific compatibility boundary

Claude-specific features must remain inside a compatible execution path.

Potentially provider-sensitive features include:

```text
adaptive thinking
effort
tool schemas
tool result formats
assistant prefill
stop reasons
streaming events
```

Do not route a request containing provider-specific semantic state into an incompatible backend merely because its text API is superficially compatible.

---

# 85. Sampling policy

Do not define one universal sampling configuration.

For local Ollama models:

```text
temperature
top_k
top_p
repeat_penalty
seed
```

may be tuned according to the model.

For current Claude 5-class models, non-default sampling parameters can be rejected; Anthropic recommends using adaptive thinking and effort rather than attempting to reproduce older temperature-based behavior.

Therefore:

```text
sampling policy = provider/model specific
```

not:

```text
global temperature = X
```

---

# 86. Agent state management

Agentic workflows should preserve explicit state where possible:

```text
task_id
session_id
user_id
provider
model
iteration
tool_calls
retrieved_context
decision
result
failure
fallback
```

This allows complete reconstruction of an execution.

---

# 87. Reproducibility

For important tasks, capture:

```text
model identifier
provider
configuration version
prompt/system configuration
tool versions
repository commit
runtime versions
routing decision
timestamp
```

Without this information, reproducing an agent result may be impossible.

---

# 88. Prompt versioning

System prompts that affect routing or operational behavior should be versioned.

Recommended:

```text
prompt_version
policy_version
router_version
```

Do not silently change the core agent contract without recording the change.

---

# 89. Structured decision logging

For every non-trivial routing decision, the system should ideally be able to answer:

```text
What was requested?
Which models were eligible?
Which were rejected?
Why were they rejected?
Why was the selected model chosen?
What policy was applied?
What was the final outcome?
```

This is the difference between:

```text
routing
```

and:

```text
governed routing
```

---

# 90. Human-in-the-loop boundaries

The platform should allow autonomous operation for low-risk tasks.

Human approval should be considered mandatory for:

```text
destructive infrastructure changes
credential changes
database migrations
production deployment
privacy boundary changes
external publication
financially consequential actions
```

---

# 91. Multi-agent future architecture

Claude-Local-Nexus can evolve toward multiple specialized agents:

```text
                     ORCHESTRATOR
                           |
        +------------------+------------------+
        |                  |                  |
        v                  v                  v
   CODING AGENT       RESEARCH AGENT      DATA AGENT
        |                  |                  |
        v                  v                  v
     tools              retrieval          SQL / Python
        |                  |                  |
        +------------------+------------------+
                           |
                           v
                     VALIDATION AGENT
                           |
                           v
                       FINAL OUTPUT
```

The router should therefore eventually optimize not only:

```text
model selection
```

but:

```text
agent selection
tool selection
workflow selection
```

---

# 92. Multimodal architecture

The platform should treat modality as an explicit dimension.

```text
TEXT
IMAGE
PDF
AUDIO
VIDEO
CODE
TABULAR
MIXED
```

A future multimodal router should determine:

```text
input modality
required output modality
vision requirement
OCR requirement
document parsing requirement
tool requirement
```

Do not route multimodal input to a text-only model.

---

# 93. Document intelligence

For PDFs and technical documents, conceptually separate:

```text
file ingestion
→ parsing
→ OCR
→ layout extraction
→ chunking
→ metadata
→ embedding
→ retrieval
→ reranking
→ generation
```

The LLM should not be treated as the document parser itself.

---

# 94. Data engineering workloads

For SQL/data tasks, model selection should consider:

```text
SQL generation
schema understanding
query optimization
Python
dataframe reasoning
statistical reasoning
large-table context
```

A coding-specialized model may outperform a generalist for SQL generation while a reasoning model may outperform it for statistical interpretation.

---

# 95. Scientific / quantitative workloads

For scientific computing and quantitative workloads, prefer execution paths capable of:

```text
symbolic reasoning
numerical reasoning
code generation
Python
Julia
R
C++
Rust
vectorized computation
Monte Carlo reasoning
statistical validation
```

Do not assume language specialization and mathematical reasoning are the same capability.

---

# 96. Benchmark methodology

Internal evaluations should use fixed datasets.

For each benchmark record:

```text
dataset_version
prompt_version
model_version
router_version
hardware
context
temperature / generation parameters
seed when applicable
latency
tokens
cost
result score
```

This makes model comparisons statistically meaningful.

---

# 97. Statistical evaluation

For competing models, do not overinterpret one run.

Use repeated trials when stochasticity matters.

Track:

```text
mean
median
standard deviation
p95
success probability
confidence interval
```

For binary task success:

```text
success_rate = successful_runs / total_runs
```

For model selection, compare confidence intervals rather than declaring a winner from one anecdotal example.

---

# 98. Performance optimization hierarchy

Optimize in this order:

```text
1. correctness
2. stability
3. routing quality
4. context efficiency
5. latency
6. cost
7. micro-optimization
```

Never sacrifice correctness for a small latency improvement unless explicitly requested.

---

# 99. CPU-only optimization policy

For the current CPU-oriented deployment:

Prefer:

```text
quantized models
reasonable context
low concurrency
model reuse
cache
request batching where supported
```

Avoid:

```text
multiple huge models simultaneously
unbounded context
uncontrolled parallel inference
```

Monitor:

```text
RAM
CPU saturation
swap
latency
model load time
```

---

# 100. Future GPU migration

If the platform migrates to a capable GPU server:

Do not simply increase every model.

Re-evaluate:

```text
VRAM
quantization
context
parallelism
concurrency
batching
model residency
offload strategy
```

Ollama notes that context allocation affects memory usage and recommends checking actual processor allocation with `ollama ps`.

---

# 101. Continuous improvement loop

The mature architecture should eventually implement:

```text
EXECUTE
   ↓
OBSERVE
   ↓
EVALUATE
   ↓
LEARN
   ↓
REVISE POLICY
   ↓
VALIDATE
   ↓
DEPLOY
```

The loop must be bounded.

No autonomous component may rewrite its own production policy indefinitely without validation.

---

# 102. Policy hierarchy

When policies conflict, use:

```text
1. Security
2. Privacy
3. Correctness
4. Safety / integrity
5. Reliability
6. Capability
7. Latency
8. Cost
9. Convenience
```

A cheaper route must never override a higher-level privacy or correctness requirement.

---

# 103. Golden rules for the agent

```text
1. Inspect before modifying.
2. Verify model existence before referencing it.
3. Verify runtime state after changing configuration.
4. Never invent repository capabilities.
5. Never invent provider capabilities.
6. Never leak secrets.
7. Never cross a privacy boundary silently.
8. Preserve modality compatibility.
9. Preserve semantic compatibility across fallbacks.
10. Treat context as a resource.
11. Prefer stable aliases.
12. Prefer minimal changes.
13. Test changes.
14. Record meaningful architectural changes.
15. Prefer reversible operations.
```

---

# 104. Final operating doctrine

Claude-Local-Nexus should evolve from:

```text
LLM proxy
```

toward:

```text
LOCAL AI EXECUTION CONTROL PLANE
```

The long-term architecture is:

```text
                    USER / AGENT
                         |
                         v
                +-------------------+
                | POLICY / SECURITY |
                +---------+---------+
                          |
                          v
                +-------------------+
                | TASK CLASSIFIER   |
                +---------+---------+
                          |
                          v
                +-------------------+
                | CONTEXT ENGINE    |
                | RAG / MEMORY      |
                +---------+---------+
                          |
                          v
                +-------------------+
                | ROUTING ENGINE    |
                +---------+---------+
                          |
          +---------------+----------------+
          |               |                |
          v               v                v
       LOCAL            CLOUD          ANTHROPIC
          |               |                |
          +---------------+----------------+
                          |
                          v
                +-------------------+
                | TOOLS / AGENTS    |
                +---------+---------+
                          |
                          v
                +-------------------+
                | VALIDATION        |
                +---------+---------+
                          |
                          v
                +-------------------+
                | OBSERVABILITY     |
                +---------+---------+
                          |
                          v
                +-------------------+
                | FEEDBACK LOOP     |
                +-------------------+
```

The architecture is therefore not:

```text
"pick a model"
```

It is:

```text
UNDERSTAND THE TASK
→
ENFORCE POLICY
→
BUILD THE RIGHT CONTEXT
→
SELECT THE RIGHT EXECUTION PATH
→
EXECUTE
→
OBSERVE
→
VALIDATE
→
RECOVER IF REQUIRED
→
LEARN
```

The system should always prefer the **minimum sufficient intelligence** required to complete the task correctly while respecting privacy, context, reliability, latency and cost constraints.

That is the governing principle of Claude-Local-Nexus.
