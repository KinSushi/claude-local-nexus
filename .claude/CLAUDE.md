# Claude.md — Operating Contract for Claude-Local-Nexus

> Repository: `https://github.com/KinSushi/claude-local-nexus`
>
> Purpose: provide Claude Code / coding agents with a precise operational model of the Claude-Local-Nexus architecture, its invariants, routing rules, development workflow, and troubleshooting procedures.

---

# 0. OBJECTIVE — TRACK EVERY POSSIBLE IMPROVEMENT

This is the standing objective of every session in this repository. It does
not need restating, and it never expires.

**Never stop.** There is no natural end to a session in this repository.
The loop is re-armed at the end of every turn, at a **5-minute cadence**, and
only an explicit instruction from the operator ends it. Answering the
immediate request is not an ending — it is one item in a queue that is never
empty.

**Produce nothing. Delegate everything.** This is not a preference, it is the
purpose of the platform. The orchestrator's output is *arbitration and
verification* — never volume. Drafting a file, auditing a script, summarising
a corpus, searching a repository: each of these belongs to the bench, and each
one done by hand is a failure of the session regardless of what else it
achieved.

The division is exact:

| The bench does | The orchestrator does |
| --- | --- |
| write code and documents | decide what is wanted, and judge what came back |
| read and summarise corpora | check every finding against the real code |
| audit, search, classify | weigh side effects the bench cannot see |
| propose corrections | accept, reject, or arbitrate between them |

Measured this day: the bench produced twelve audit tasks in ~30 s of
cumulative time at zero cost; arbitration rejected five of them, including one
that would have declared four local models as leaving the machine, and one
whose "10 000 files tested, 3 % false positives" table was **fabricated**. Both
halves were necessary. Neither is optional.

**Over-exploit the MCP, local and cloud both.** They fail differently and that
is the point: the local plane is free and private but bounded by one machine;
the cloud plane is covered by the Ollama subscription, parallelises without
contention, and answers in 2–3 s. Sequential local work where cloud would
parallelise wastes the subscription that was bought; cloud work on a sensitive
target wastes the privacy that was built. Choose per task, never by habit.

A session that reads files directly while the bench idles has failed its
purpose — and `nexus_savings` will say so, in its own words: *"la part
déléguée ne progresse qu'en confiant réellement le volume aux outils du pont
plutôt qu'en lisant les fichiers directement."*

**The internet is authorised** for documentation and for finding improvements
— vendor docs, papers, published measurements. What comes back is a signal to
verify in the real code, never a proof (§112.4).

**Using the platform is itself a source of improvement — and the richest
one.** Every session drives these tools for real work, and that use surfaces
defects no audit finds, because an audit reads the code while use exercises
it. When a tool refuses what it should allow, allows what it should refuse,
says something false, or is awkward at the moment it matters, that is a
finding: record it and fix it, in the same turn, rather than working around
it. Working around a defect is how it survives.

Measured on 2026-08-30, in one session, entirely from use rather than from
reading:

* the secret detector blocked three placeholders and zero secrets — found by
  running the very first publication, not by reviewing the pattern;
* the edit guard was structurally blind on Windows (`py_compile` with
  `cfile=os.devnull` raises `FileExistsError`, never `PyCompileError`) —
  found by deliberately feeding it a broken file, and invisible otherwise;
* the wiring check counted a mention in a comment as a call, then its first
  remedy produced eighteen false negatives — both found by running it on
  this repository rather than by reasoning about it;
* the shell mutilated four commands, one of them a commit message that went
  out stripped of its technical names — found by reading back what had
  actually been committed.

None of these came from an audit. All came from use, and each became a check
that now fails when the defect returns.

**THIS PROJECT TAKES PRIORITY over the neighbouring repositories'
mechanisms.** It does not follow them: it is the source. What is built here —
guards, ratchets, trials, checks — is meant to flow *down* to them, never the
reverse. Where a mechanism here and a mechanism there disagree, the one here
decides.

Drawing on them is not forbidden — **on the contrary**, it is expected: what
has already been paid for once must not be paid for twice. But an idea is
borrowed, not submitted to. A mechanism taken from elsewhere is rewritten to
this repository's rules, put through its trials, and enters only if it
neither duplicates nor competes with what already exists here.

**Borrowing from the neighbouring repositories is authorised — and expected.**
Two repositories on this machine solved problems this one still has. Their
mechanisms were already paid for once; reinventing them would pay the same
price twice. The paths, written down so no session has to rediscover them:

```text
D:\SAS\sovereign-ai-system\v1.104\sovereign-ai-system
D:\EA MT5 PYTHON RENTABLE ROBUSTE
```

**Read-only.** Draw on their tools, mechanisms, hooks and ACLs; never write
into them. The second one carries a standing instruction of its own — fix the
script, not that project.

The SAS repository declares four hook events and 101 `deny` rules. What has
been taken from it, and what is still open, is tracked in the cockpit rather
than here, because that list changes and this contract should not. Taken so
far: the `SessionStart` resume, the secret and irreversible-gesture ACLs, the
read-before-write guard, the heredoc guard, and the wiring ratchet. Still
open: agent-perimeter, anti-drift, and the automatic harvest of worker
worktrees.

Three of its principles are worth restating because they are general: derive
everything and hard-code nothing, since a frozen measurement lies the next
day; a start-up hook must never run anything long, only *say* what to run; and
it must never fail, because a guard that crashes stops the work it was meant
to protect.

**Standing research leads**, to be pursued rather than waited for:

* **metaheuristics** and **hybrid metaheuristics** — the routing, pool
  selection and temperature problems in this repository are search problems
  under constraint, and are currently solved by hand-written heuristics;
* **scientific work on adaptive inference** — bandits, Bayesian optimisation,
  and the measurement protocols that make them honest;
* **MQL5 work on metaheuristics** — a large body of published, measured
  implementations of exactly these algorithms, worth mining for method even
  where the domain differs.

Three rules follow, and each was learned by breaking it here:

**Arm the loop.** A tracking effort that depends on being reminded is not a
tracking effort. `NexusTraque` runs every ten minutes without a session, and
`ScheduleWakeup` carries this objective in its own wake reason so it is
reconducted without anyone repeating it.

**Mechanise, do not document.** A rule that is not mechanised protects no one
— not even its author, the same day (§106.1). When a lesson matters, the
deliverable is a check that fails, not a paragraph.

**Close threads, do not open them.** An open task is not progress; a closed
one is. Record what remains in `rituels/CHECKLIST_COCKPIT.MD`, which
regenerates itself with each update, so nothing depends on remembering.

The measure of a session is not what was explained. It is what is now
impossible to get wrong.

---

## 0.2 End-of-turn ritual — every turn, without exception

Not a checklist to consult: a sequence to execute before the turn ends. Each
item exists because it was once forgotten here, and the omission cost
something.

**1 — Have a third party validate.** LAW 1: never validate your own work.
`python scripts/nexus_valide.py --base HEAD~1`, billed cost zero. It found a
real regression on its first use, and a false positive on its second — both
worth knowing.

**2 — Commit with the measurement, not the intention.** The message states
what was false, what proves it, and what remains uncertain. A commit that says
what was done and not what was measured is a commit nobody can audit later.

**3 — Record what is still open.** `rituels/CHECKLIST_COCKPIT.MD`. A defect
seen and then dropped is worse than a defect unseen: it was known, and the
knowledge was lost. Under the standing rule, an entry closes only when a check
fails if the rule is broken — never when a paragraph is written.

**4 — Re-arm the loop.** `ScheduleWakeup`, 5 minutes, with the objective in
the wake reason so it is carried forward without anyone restating it. A turn
that ends without re-arming ends the session, and the session is not meant to
end.

**5 — State what was delegated and what was arbitrated.** If nothing went to
the bench this turn, say so plainly: it means the turn produced volume the
platform exists to avoid.

**6 — Never leave a mechanism unwired.** Mechanise what must be mechanised,
and wire what must be wired — in the same turn. A script nobody calls is not
a mechanism, it is a file; a rule with no check behind it is a paragraph. The
six links of §0.2.1 are the list, and the *caller* is the one most often
missing, because nothing asks for it at the moment you believe you have
finished. `nexus_rituel.py` now runs `nexus_cablage.py` rather than reminding
you to: the ratchet refuses to let the orphan list grow.

The regenerating parts — `rituels/STATE.md`, the `NexusTraque` task — are not
in this list. They run without being asked, which is precisely why they are
not rituals.

---

# 0.2.1 MECHANISE EVERYTHING, WIRE NOTHING BY HALVES

A rule that is not mechanised protects no one — not even the person who wrote
it that morning. This was proved here on 2026-08-30: a rule written before
lunch was broken four times the same afternoon by its own author, once while
documenting its correction.

So the deliverable of any decision is **a check that fails when the rule is
broken**, never a paragraph. If a change cannot be expressed as a check, it is
not finished; say so rather than closing it.

**And wire it to the end.** A mechanism half-wired is worse than none, because
it reads as protection. Every wiring has a checklist of its own, and forgetting
one link has cost real damage here:

| Link | Question to answer before closing |
| --- | --- |
| the script | does it exist, and does it exit non-zero on the defect? |
| its own proof | does a positive trial show it *detects*? Silence on a clean repository proves nothing — a broken pattern is just as silent |
| the caller | is it invoked by a hook, a scheduled task, or another check — not only by hand? |
| the gate | does something REFUSE to proceed when it fails? |
| the documentation | contract, `MEMORY.md`, cockpit |
| the regression | is there a test that fails if the wiring is removed? |

Measured omissions: `nexus_bench.py` wrote its readings under a key its own
readers did not look for — the next regeneration would have dropped 58 models
from every pool, silently. `run_validator_on` restored the real configuration
in a `finally`, and a `finally` does not run when the process is killed; the
recovery that existed then deleted the real file because it read
`CONFIG present` as `CONFIG sane`.

---

# 0.3 SHOWCASE BACKUP — STABLE AND SANE MEANS PUBLISH

The repository is the professional showcase. When everything is stable and
sane, the state goes to GitHub — and it must stay presentable at all times.

Never by a bare `git push`. Publication goes through the one gesture that
verifies first:

```powershell
python scripts/nexus_vitrine.py --simulation   # verify everything, publish nothing
python scripts/nexus_vitrine.py                # publish if, and only if, sane
python scripts/nexus_vitrine.py --epreuve      # does the secret detector detect?
```

Seven blocking controls before anything leaves: clean tree, `.env` untracked,
no secret pattern among tracked files, `nexus_conformite.py` at 0,
`nexus_rituel.py` at 0, an `origin` remote, a branch with an upstream.

Pushing to a **public** repository is the only action here that is both
outbound and irreversible: what leaves is indexable, and deleting it later does
not remove it from caches. A `.env` committed once stays in history even when
erased by the next commit — hence a control that blocks absolutely rather than
warns.

`--epreuve` exists because zero detections on this repository (121 tracked
files) proves nothing on its own: a badly written pattern yields exactly the
same silence. Four fabricated secrets must be seen, and one innocuous sentence
must stay silent.

The verdict reads the RESULT before the mode. The first draft read the mode
first and announced « SIMULATION » over a block — a report that claims success
on a failure is worse than no report.

---

# 0.4 THE LOCAL WORKERS ARE THE SUBCONTRACTORS

The local bench models **are** what Haiku and Sonnet would be, at zero cost.
They are not a fallback for when the budget is tight; they are where the volume
goes. The orchestrator keeps arbitration and keeps nothing else.

Three rules, and they are indivisible:

1. **Never hand the original files to the MCP.** A worker gets a copy, never
   the source. It may truncate, rewrite or invent — and the repository must not
   be able to suffer for it.
2. **Every worker in an isolated worktree** (`scripts/nexus_worktree.py`).
   Isolated means its own working copy, its own commits, no collision with the
   others or with the main tree.
3. **Preserve the orchestrator's context.** Whatever can be read, summarised,
   searched or compared by the MCP must not come back into the billed context.
   `nexus_search`, `nexus_summarize`, `nexus_context` exist for exactly that.

The metric is not "was the free plane used" but **how many billed tokens were
spent driving free ones**. Measured on 2026-08-29: ~475 000 billed to drive
~126 000 free. That is the inverse of the goal.

---

# 0.1 Mission

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
ollama list
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

This invariant is now enforced mechanically rather than by discipline.

```powershell
.\scripts\Test-NexusConfig.ps1
```

fails with exit code 1 on any dangling reference, any fallback cycle, any
modality mismatch, any empty router pool and any missing environment
variable. `Update-NexusModels.ps1` refuses to restart LiteLLM when it fails.

Historical note, corrected: earlier revisions of this document stated that
`ultime-recourse-local` was referenced without being declared. It **is**
declared (`ollama_chat/phi3:mini`). The real defects were elsewhere and are
now fixed:

* eleven Ollama Cloud aliases referenced by the routers and never declared;
* five vision models falling back to a text-only model;
* eight cycles in the fallback graph.

Fallback graphs are no longer written by hand at all. They are derived from
the declared inventory, which makes them acyclic by construction and
incapable of crossing a modality or provider boundary. See section 105.

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

The engine runs on the HOST, not in Docker. The `ollama` service exists in
the compose file but sits behind the `embedded` profile and is not started,
so `docker exec ollama-server ...` fails with "no such container".

```powershell
ollama list
ollama ps
ollama pull <model>
ollama rm <model>
ollama run <model>
```

Only when the embedded profile is deliberately started
(`docker compose --profile embedded up -d`) do the `docker exec
ollama-server ...` forms apply instead.

The engine has no automatic start of its own, unlike Docker Desktop. After a
reboot the stack comes back alone and the engine does not; `scripts/start.ps1`
relights it before the conformity check that would otherwise refuse to start.

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
ollama list
ollama ps
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
.\scripts\backup.ps1
```

Full volume backup:

```powershell
.\scripts\backup.ps1 -IncludeVolumes
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

.\scripts\update_local_models.ps1
.\scripts\update_cloud_models.ps1
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
.\scripts\update_local_models.ps1 -WhatIf
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

---

# 105. Generated configuration contract

`litellm_config.yaml` is now part hand-maintained and part generated. The
boundary is explicit and must be respected.

## 105.1 Generated zones

Delimited by markers. Never edit between them — the next update overwrites.

```text
# >>> AUTOGEN:<NAME>
        ... generated ...
# <<< AUTOGEN:<NAME>
```

| Marker | Content |
| --- | --- |
| `LOCAL_MODELS_EXTRA` | every Ollama model not declared by hand |
| `CLOUD_MODELS` | Ollama Cloud model blocks |
| `CLOUD_POOL_CLOUD` / `CLOUD_POOL_GLOBAL` | cloud candidates of the routers |
| `ANTHROPIC_FALLBACKS` / `LOCAL_FALLBACKS` / `CLOUD_FALLBACKS` | fallback chains |
| `ROUTER_FALLBACKS` | router fallbacks |
| `*_CTX_FALLBACKS` | context-window fallbacks |

## 105.2 Hand-maintained

Capability profiles, context windows and router pool membership. Being
installed does not make a model eligible for automatic routing (§76):
auto-exposed models carry `model_info.nexus_pool: false` and stay out of
every pool and every fallback chain. Promote one by declaring it by hand.

**Correction, 2026-08-30 — pool membership is no longer hand-maintained.**
`nexus_pool` is now computed, from two measurements that answer different
questions:

| Source | Question | Written by |
| --- | --- | --- |
| `.nexus/latences.json` | how long before it *starts* answering? | `nexus_bench.py` |
| `.nexus/epreuves.json` | can it actually do the work? | `nexus_releve.py` |

The rule: `ACCEPT` on hardware (§107) **and** under `SEUIL_POOL_MS`, **or** a
complete pass on the real epreuves — protocol, tool request, result use,
chaining. Never measured means never promoted: absence of evidence is not
evidence.

The second clause is not a softening of the first: raising the threshold to
accommodate a slow-but-capable model would admit, in the same gesture, models
that have proven nothing. The derogation is anchored to a proof; a threshold
is anchored to nothing.

**Correction, same day.** This clause was first justified by
`glm-4.7-flash-local` — 61.8 s to start, 1.8 s over the threshold, 4/4 on the
epreuves — said to be "excluded from the pool" without it. Checked against
`litellm_config.yaml`, that is false: the model is declared **by hand**,
outside the AUTOGEN zone and with no `nexus_pool` field, so the latency
criterion never judges it at all.

The error came from a script that called `eligible_au_pool()` on every alias
in the reading, without checking which aliases actually travel that code
path — analysis mistaken for proof, the one thing §112.4 forbids.

The mechanism stands, and is kept: the day an **auto-exposed** model proves
slow to start yet capable, the strong measurement must win. It simply has no
demonstrated case today, and saying so is worth more than letting one be
assumed.

So the derogation is anchored to the proof, never to the number. An
incomplete pass grants nothing, and the total is read from `EPREUVES` rather
than fixed at four, so a future fifth epreuve does not let `4/5` keep passing
for a clean sheet.

Both files live under `.nexus/`, which is gitignored — and must stay so. They
measure *this* machine. Committing them would ship one host's verdicts to
every other.

## 105.3 Live sources of truth

```text
ollama list                             ->  local inventory (no ceiling)
https://ollama.com/api/tags             ->  cloud catalogue
a real request per cloud model          ->  what the account may actually run
```

Entitlement is re-tested on every run. A `402` excludes a model; a `429`,
a `5xx` or a timeout does **not** — a momentarily exhausted quota proves
nothing about entitlement, and shrinking the pool over a finished incident
would be wrong. Subscribing to a higher Ollama Cloud tier therefore widens
the pool by itself at the next update.

## 105.4 Operating commands

```powershell
.\scripts\Update-NexusModels.ps1 -DryRun              # simulate
.\scripts\Update-NexusModels.ps1 -Validate -Restart   # full cycle
.\scripts\Test-NexusConfig.ps1                        # integrity gate
.\scripts\Test-NexusSmoke.ps1 -IncludeRouters         # runtime check
python scripts/nexus_valide.py --base main            # validation, cout zero
.\scripts\Register-NexusAutoUpdate.ps1                # daily task, 04:00
python scripts/nexus_test.py                          # full test suite

.\scripts\start.ps1 [-Verifier]                       # bring the stack up
.\scripts\Install-NexusCommande.ps1                   # `nexus` in the profile
.\scripts\Register-NexusDemarrage.ps1                 # start at logon
```

`scripts/nexus.ps1` is the single entry point: `start` (default), `check`,
`status`, `stop`, `mcp`, `ask`, `valide`, `help`. It derives the platform
root from `$PSScriptRoot`, so file paths handed to it stay relative to the
CALLING project. `nexus mcp` writes the `.mcp.json` a foreign project needs,
with an absolute server path -- copying the platform's own file would not
work, it refers to the server through `${CLAUDE_PROJECT_DIR}`.

A scheduled task brings the stack up at logon, 120 s in, and writes
`logs/demarrage.log`. Note for whoever registers such a task: `pwsh -File`
passes everything after the script path AS ARGUMENTS, so a `*>` redirection
never reaches PowerShell. Use `-Command "& 'script' *> 'log'"` instead.
Measured with `-File`: LastTaskResult 1, and no log at all -- a silent
failure, precisely what the log existed to prevent.

## 105.5 Observability of routing decisions

Behind an adaptive router, the response body reports only the router name.
The selected model is in the headers:

```text
x-litellm-adaptive-router-model   model the router selected
x-litellm-model-name              upstream model that actually answered
x-litellm-model-api-base          endpoint actually contacted
x-litellm-attempted-fallbacks     whether a fallback was used
```

`x-litellm-model-api-base` is the direct proof of non-leakage: it shows
whether a request left the machine, whatever alias was chosen.

---

# 106. Subscription boundary

`ANTHROPIC_BASE_URL` alone does **not** replace the claude.ai subscription;
`ANTHROPIC_AUTH_TOKEN` (or `apiKeyHelper`) does, and switches billing to
per-token API credits. Anthropic does not support routing Claude Code to
non-Claude models through a gateway.

Consequence: the supported way to combine the subscription with local models
is the `nexus-local` MCP server (`.mcp.json`). Claude Code stays on the
subscription and orchestrates; the gateway becomes a bench of models it calls
as tools — `nexus_ask`, `nexus_route`, `nexus_summarize`, `nexus_search`,
`nexus_index_build`, `nexus_models`. Those six are a deliberate baseline and
are expected to grow.

Never state that a request is local without checking the endpoint actually
contacted.


---

# 107. Hardware budget is a hard constraint

The machine is measured, never assumed. `scripts/nexus_capability.py`
produces a profile and a verdict per model:

| Verdict | Condition | Effect |
| --- | --- | --- |
| `ACCEPT` | weights <= 60% of engine memory | eligible for automatic routing |
| `DEGRADED` | <= 85% | addressable, but out of pools and fallback chains |
| `REJECT` | > 85% | not declared at all, and not downloaded |

A model heavier than the engine's memory does not fail cleanly: it pages,
and the answer never usefully arrives. Leaving it automatically selectable
is drawing lots for a response that will not come. This was observed here:
the router had picked `llama3.3:70b` (42 GB) while the engine had 32.

The verdict gates declaration, pool membership, fallback chains and
downloads. It is not advisory.

---

# 107.3 Throughput does not follow size either — first readings

`nexus_bench.py --debit` measures tokens per second on a real generation task.
First three readings on this host, 2026-08-30:

| Model | Size | Throughput |
| --- | --- | --- |
| `qwen3-coder-30b-local` | 30 B | **20.22 tok/s** |
| `llama3.2-3b-local` | 3 B | 11.84 tok/s |
| `qwen2.5-coder-14b-local` | 14 B | 7.05 tok/s |

After the first two readings the obvious sentence was "throughput falls with
size". The third refutes it: the largest model is the fastest, by a factor of
three over the middle one. The likely reason is architecture — `qwen3-coder:30b`
is a mixture-of-experts, few parameters active per token — but that is a
hypothesis, not a measurement, and it is written here as such.

So the same rule holds on both benches: **size predicts neither start-up delay
nor throughput.** It was already true of time-to-first-token (§112.3); it is now
measured true of generation speed.

Two cautions on these figures:

* Three readings are three readings. They refute "throughput falls with size" —
  one counter-example suffices for that — but they establish no ordering of
  their own.
* A model whose weights are not resident pays the load. The bench wakes the
  model first, on a separate and generous budget, precisely so that cost is not
  charged to throughput. That separation had to be added after the fact:
  `mistral-7b-local`, benched at 2.5 s to start, was failing its wake-up at 50 s
  because it was paying the eviction of whatever held memory before it.

# 107.2 The start-up bench cannot settle a default — a case in point

The bench's own warning (§112.3) says its reading is necessary and not
sufficient: sixteen tokens measure the delay before a model *starts*, never
its throughput on real work. On 2026-08-30 that warning stopped a change that
looked obviously right.

The MCP server's `DEFAULT_CHAT_MODEL` is `glm-4.7-flash-local`, benched at
**61.8 s** to start — by far the slowest default in the repository, every other
one sitting between 2.4 and 2.9 s. The obvious replacement was
`qwen2.5-32b-local`: same declared quality tier, benched at **3.8 s**, sixteen
times faster.

Put to a real task — summarise 3000 characters in three sentences — it did not
finish in **110 s**. The model that starts in 3.8 s does not deliver.

So the default was **left unchanged**, for want of evidence to choose a
replacement.

**Then the evidence arrived, and it reversed the verdict.** Measured on the new
throughput bench, `glm-4.7-flash-local` returns **19.85 tok/s** — the best on
this host, tied with `qwen3-coder-30b-local`. The default that looked like the
worst in the repository is one of the two best at what it actually does.

The arithmetic that settles it, on a 500-token summary:

| Model | Start-up | Throughput | First call | Once resident |
| --- | --- | --- | --- | --- |
| `glm-4.7-flash-local` | 61.8 s | 19.85 tok/s | ~87 s | **25 s** |
| `llama3.2-3b-local` | 2.3 s | 11.84 tok/s | ~44 s | 42 s |

Start-up is paid once, when the weights are not resident. Throughput is paid on
every token. For a tool that generates long output — which is exactly what
`nexus_summarize` and `nexus_context` do — the second dominates, and the
"slowest default in the repository" is the fastest choice available.

Two things follow. The default stands, now on evidence rather than for want of
it. And the criticism levelled at it repeatedly through 2026-08-30 — including
in commit messages — was **wrong**: it judged a generation tool by a start-up
reading, the very confusion §112.3 warns against, committed by the same hand
that wrote the warning.

---

# 106.1 A rule that is not mechanised protects no one — not even its author

Stated by the operator on 2026-08-30, after watching it happen all day. It is
the session's central finding, and the evidence is this session itself.

That morning, §112.3 was corrected: a rule had generalised **two readings into
a whole class** of models. The correction was written, committed, and
explained at length.

That afternoon, the same hand looked at `ollama ps`, saw one resident model,
and wrote into the doctrine that the engine **keeps one model resident**. One
observation raised to a property — the identical error, committed while
documenting its correction, then propagated into four files including a
conformity check that repeated it on every run.

It happened three more times the same day:

* the load-vs-measurement confusion, corrected on the latency bench, was
  **reproduced on the throughput bench** built afterwards;
* the `bge-m3` blind spot was fixed in two files before being fixed at its
  source, so the same wrong regex kept shipping;
* the "measure nothing under load" warning in the manual was violated by
  measuring during a 28 GB download.

None of these were failures of understanding. The rules were written, recent,
and by the same author. **Discipline did not survive contact with a long
session** — and there is no reason to expect it to survive contact with a
different author, or with the same one a month later.

Hence the standing rule: when a lesson matters, the deliverable is not a
paragraph, it is a check that fails. `nexus_traque.py`, the blocking
conformity controls, the guard in the generator, the pool bound derived from a
measured budget — each exists because the corresponding written rule had
already been broken by the person who wrote it.

A paragraph documents. Only a check protects.

---

# 106.2 Metaheuristics: where they are warranted here, and where they are not

The standing research lead (§0) asks for metaheuristics. Applied honestly, it
splits the repository's optimisation problems in two — and rules the method
out of one of them.

**Pool selection: exact, not heuristic.** Choosing 4–6 models out of 40 that
minimise expected latency under a 40 GB memory bound is a 0-1 knapsack with a
cardinality constraint. Measured on this host: 4 587 778 admissible
combinations for 40 models, 3 930 511 for the 39 currently eligible, and a
full sweep of sizes 2–4 completes in **0.00 s**. Branch-and-bound or plain
enumeration returns the *guaranteed optimum* in milliseconds.

A metaheuristic here would be strictly worse: more code, more parameters to
tune, and an approximate answer to a problem that has an exact one. The lead
was pursued, the problem was sized, and the method was **rejected on
measurement** — which is the useful outcome of pursuing a lead.

**Temperature learning: metaheuristic territory, genuinely.** The other
problem has none of those properties. The search space is continuous, the
objective is *noisy* — the same input yields different outputs — and every
evaluation costs seconds of real compute. That is the exact regime where
exhaustive search is impossible and where the method earns its place.

Three candidates, and their failure modes in this specific setting:

| Approach | Fits when | Fails on |
| --- | --- | --- |
| Contextual bandit (UCB, Thompson) | many repeated trials per (model, profile) | assumes stationarity; noisy rewards keep exploration local |
| Bayesian optimisation | each trial is very expensive | surrogate degrades with dimensions and non-stationarity |
| Simulated annealing | refining around a known-good start | no global guarantee, and evaluation count explodes |

**Two traps of noisy, expensive online optimisation**, which apply whichever
is chosen: treating a single evaluation as reliable — the remedy is confidence
intervals or a surrogate before accepting a point; and sizing the algorithm
without regard to evaluation cost — the remedy is a fixed evaluation budget
that the algorithm must respect, not aim at.

The observation store (§AIC brique 8) exists precisely to make the first
remedy possible: without accumulated repeats, no confidence interval can be
computed, and any of the three methods would be optimising noise.

---

# 107.0 The engine's own settings come first — they change every reading below

Established 2026-08-30 by a parallel session, and it reframes §107.1 to §107.3.

`OLLAMA_KEEP_ALIVE` is unset on this host, so the engine's default applies:
**five minutes**. `ollama ps` shows it live — one model "About a minute from
now", another "Stopping…". Every call after a pause therefore repays the load
of 20 GB from disk.

**That is where the 61.8 s attributed to `glm-4.7-flash-local` comes from.** It
was never a property of the model: it is disk, and it is avoidable. Every
"start-up" figure in §107.3 and §112.3 measures a reload the engine could have
been told not to perform.

Second fact, equally consequential: the Radeon 890M is an **iGPU with no
dedicated VRAM** — it shares the same 61.6 GB. Two 20 GB models resident at
once do not merely fill memory, they contend for the same bandwidth. That is
why `nexus_batch` runs sequentially, and the same reasoning applies to the pool.

**The coupling that must be stated.** §107.1 bounds the local pool by cumulative
weight against a 40 GB budget, which yields four models. That bound was derived
while the engine kept three residents. If `OLLAMA_MAX_LOADED_MODELS` is set to
**1**, a four-model pool becomes actively harmful: every router choice evicts
the previous model and pays a full load. The bound and the engine setting are
one decision, not two, and changing either without the other degrades the
result.

So the order of work is: settle the engine's settings first, then re-measure,
then re-derive the pool. Doing it the other way — which is what happened —
produces figures that describe a misconfiguration rather than a machine.

---

# 107.1 A pool is bounded by memory, not by taste

Measured 2026-08-30, and each figure below corrected a decision that had
looked obviously right.

**Opening the local pool to everything eligible made it slower.** Twenty-nine
models, all measured fast, and three consecutive router calls took 78 s, 41 s
and 60 s — for models benched at 22 s, 4 s and 12 s. The gap is weight
loading, paid again on every call.

**The cause is physical.** The engine keeps only a handful of models resident
— measured the same day, `ollama ps` showed **three** coexisting
(qwen2.5-coder:14b 10 GB, mistral:7b 6.7 GB, glm-4.7-flash 20 GB = 36.7 GB),
each expiring four minutes after its last use. A pool far wider than that
therefore disperses calls onto cold models, and the wider it is, the more
certain the reload. Theoretical choice is paid in real seconds.

*Corrected the same day.* This paragraph first read "one model resident at a
time". That was a single observation turned into a property — the exact error
§112.3 corrects, committed again while documenting the fix for it. One model
was resident because one was in use, not because the engine keeps one; Ollama's
own default is three. The **decision** to bound by memory stands, since the
78/41/60 s against 4/5/1 s readings are empirical. Only the explanation was
wrong, and a wrong reason is worth correcting even when it led somewhere right.

**Bounding by a count was still wrong.** A count assumes the chosen ones can
coexist; the first four weighed 19 + 18 + 19 + 18 = 74 GB against 66.2 GB of
host memory. Measured with those four: 61, 39, 34, 69 s, the router alternating
between two 20 GB models that evict each other.

So the bound is on **cumulative weight**, against `pool_budget_gb` from the
hardware profile (§107). It adapts on its own — heavy models, narrow pool;
light models, wide pool; a bigger machine, a wider pool with no line changed.
A minimum of two is kept: with one member there is no routing, only an alias
in disguise.

The resulting pool is better in kind, not merely smaller: two large coding
specialists plus two small fast models that absorb trivial requests without
evicting anything.

**The complementary lever is outside the YAML.** `OLLAMA_MAX_LOADED_MODELS` is
unset on this host, so the engine keeps one. Raising it would let the bound
widen by as much, memory permitting. Until it is raised, widening the pool
hurts — and that is a property of the engine, not of the models.

---

# 108. Fallback direction

The earlier rule — "no fallback crosses a provider boundary" — was too
rigid: it removed the very fallback that matters when a quota runs out.

| Direction | Verdict | Reason |
| --- | --- | --- |
| `cloud -> local` | allowed | costs only capability |
| `anthropic -> local` | allowed | same, and avoids an outage |
| `local -> cloud` | forbidden | data would leave the machine |
| `local -> anthropic` | forbidden | same, and commits spend |

A fallback is **suffered, never chosen**. It must not widen data exposure,
nor decide on spending in the user's place. Both the validator and the
policy tests enforce the direction, not the absence of crossing.

---

# 109. Execution profiles

`nexus_ask` accepts a `profile` instead of a `model`, so a caller asks for
a class of task rather than naming a model:

```text
coding      implementation, debugging, refactoring
reasoning   architecture, trade-offs
rapide      classification, extraction, short transformation
multimodal  image, screenshot, OCR
```

The first candidate actually exposed wins, local first, and the hardware
verdict applies. Remote models come last, so spend is committed only for
lack of a local alternative.

---

# 110. Distributed context

No local model offers 1M context, and allocating it would cost memory the
machine does not have. `nexus_context` gets the equivalent differently: the
corpus is cut into windows that actually fit, each is analysed separately
(MAP), then results are merged in tiers until one window suffices (REDUCE).

The ceiling is therefore no longer the window but the time — which, locally,
costs nothing else. This is what makes the platform usable without any
subscription.

---

# 111. Measuring what delegation saves

`scripts/nexus_savings.py` reports volume by plane and the counterfactual
cost on Claude.

Two honesty constraints, both learned the hard way:

* Internal health-check traffic is excluded. On an ordinary day it was
  2552 requests out of 2730 — including it produced a flattering rate that
  measured the platform observing itself.
* Subscription traffic never passes through the gateway, so it is invisible
  here. The figure is "volume diverted from the subscription", not
  "subscription remaining". There is no threshold to reach: the delegated
  share is a quantity to maximise.

---

# 112. Token economy is the product, not a preference

The platform exists to move volume off a paid subscription and onto free
models. A change that improves everything else while degrading that ratio has
made the system worse.

Three rules follow, and they are enforced mechanically because discipline
already failed: the instruction had to be repeated four times in one session
before it was wired in.

```text
1. Any unnecessary use of paid tokens violates the purpose of the project.
2. The orchestrator arbitrates and audits. It does not draft.
   Corrections are produced by the free plane, then arbitrated.
3. LAW 1 — never validate your own work. Validation belongs to an
   independent agent that did not author the change.
```

Law 1 paid for itself on first use. It found a real regression: `switch()` in
`scripts/nexus_switch_engine.py` still treated an unreachable engine as an
engine with no models, and printed that claim as the last message before
rewriting the configuration.

## 112.1 The trap is the orchestration shell, not the model

A Claude subagent costs **twice**: its own reasoning, billed per token, and
what it delegates, free. Only the second half serves the purpose.

Launched without an explicit `model`, a subagent **inherits the parent's
model** — the most expensive one — and nothing says so.

Measured 2026-08-29, across four subagents:

| | Tokens |
| --- | --- |
| Billed, spent on subagent reasoning | ~475 000 |
| Free, delegated to Ollama Cloud | ~126 000 |

That is the inverse of the goal. The metric to watch is therefore not
"was the free plane used" but **how many billed tokens were spent driving
free ones**.

## 112.2 Mechanisms

| Mechanism | What it enforces |
| --- | --- |
| `scripts/nexus_garde_agent.py` | `PreToolUse` hook. Refuses a subagent whose `model` is absent or not allowed, and refuses `subagent_type: fork`, whose parent model is inherited whatever is requested — letting it through while believing it capped would be a false guarantee, worse than none. Any anomaly (unreadable JSON, missing field) passes: a guard that crashes must never stop work. Override: `NEXUS_AGENT_LIBRE=1`. |
| `.claude/settings.json` | Wires the hook. |
| `.claude/agents/nexus-delegue.md` | The economical agent, cheap by construction: fixed model, delegation protocol, caps on tool calls and report length. |
| `controle_delegation` in `scripts/nexus_conformite.py` | Measures the delegated share over 7 days. Floor 90%, WARNING and never BLOCKING — a falling share does not prevent starting, and refusing to start would punish the operator who came to fix it. Reports `anthropic` requests separately: they alone are billed per token, and a flattering average is carried by free volume. |

## 112.3 The bench, as measured

| Model | Latency | Cost | Note |
| --- | --- | --- | --- |
| `gpt-oss-120b-cloud` | 20–35 s for 10–30k tokens | 0 | Ollama Cloud subscription. Data leaves to ollama.com; the repository is public, so this is acceptable. The workhorse. |
| `glm-4.7-flash-local` | slower | 0 | Free **and** private. Also the declared local relay: 4/4 on protocol, tool request, result use, chaining. |
| `qwen3-coder-30b-local` | 2.4 s to first tokens | 0 | See the correction below: the earlier "times out at 900 s" was a task measurement read as a model property. |
| `qwen2.5-coder-32b-local` | 3.4 s to first tokens | 0 | Same. |
| `gemma4-12b-local` | **51 s** to first tokens | 0 | Twelve billion parameters, and the slowest of the bench. Size does not predict speed. |

### Correction, 2026-08-30 — and the limit of the correction

An earlier revision of this table stated that **any** local model of 30B or
more "times out at 900 s", naming those two. Re-measured with the Redis exact
cache neutralised (`no-cache` / `no-store`) and load and steady state timed
separately, they answer in 2.4 s and 3.4 s.

Two errors were compounded, and both are worth naming:

* A **generalisation from two readings to a whole class**. The rule said "any
  local >= 30B". Nothing measured the class; two models were measured.
* A **cache-contaminated, single-phase reading**. The first call pays for
  loading the weights; every subsequent one does not. Timing them together
  attributes the load to the model, permanently.

The measured order of the bench, sorted, refutes the parameter count outright:

| Model | Parameters | Steady state |
| --- | --- | --- |
| `qwen3-coder-30b` | 30 B | 2.4 s |
| `codestral-22b` | 22 B | 2.8 s |
| `qwen2.5-coder-32b` | 32 B | 3.4 s |
| `gpt-oss-20b` | 20 B | 7.7 s |
| `phi3-medium` | 14 B | 20.2 s |
| `gemma4-12b` | 12 B | 51.5 s |

A threshold on parameter count would have excluded `codestral-22b` and admitted
`gemma4-12b` — exactly backwards. Hence `scripts/nexus_bench.py`, and hence
`SEUIL_POOL_MS` in `scripts/nexus_generate.py` gating on the reading rather
than on the size.

**What this measurement does not say.** The bench asks for sixteen tokens. It
measures the time to *start* answering, not the throughput of a real task. A
model quick to reply "PRET" may still crawl on two thousand tokens, and the
900 s figure it replaces very probably came from exactly such a task. The two
statements are therefore not contradictory: they measure different things, and
the old one was wrong only in presenting a task result as a property of the
model.

So the promotion criterion built on this reading is **necessary and not
sufficient**: a model too slow to start is unusable, but a model quick to start
is not thereby proven usable. Any model this bench admits and that then proves
slow in production is a defect of the criterion, not of the reading — the
remedy is a second bench measuring tokens per second, not a return to counting
parameters.

The call path that survives a broken MCP root, because it derives its own root
from `__file__`:

```powershell
python scripts/nexus_agent.py --tache "..." --fichiers f1 f2 `
    --modele gpt-oss-120b-cloud --max-tokens 2000
```

### The 20–35 s figure is the CLOUD plane's, and the MCP default is not cloud

`gpt-oss-120b-cloud` answers 10–30k tokens in 20–35 s. That number is quoted
often enough to read as the bench's speed. It is not: the MCP server's default
chat model is `glm-4.7-flash-local` (`tools/nexus-mcp/server.js`), and that
model was measured today at **61.8 s just to start answering**.

MAP-REDUCE pays that start-up once per window. So on a large corpus the
default plane does not merely run slower — it runs slower by a factor that
grows with the document. Measured from a neighbouring project: `nexus_context`
timed out at 600 s on four files, and `nexus_summarize` on this very file
(84 KB) exceeded 120 s.

The ceiling for a large document is therefore **time, not context** (§110
already says the window is not the limit; this names what is).

What follows is NOT "so allow the cloud". Whether data may leave for
ollama.com is a sovereignty decision (§35, §64), and it is the operator's,
never the agent's — this repository being public is what makes the cloud
acceptable *here*, and that reasoning does not travel to another repository.

What does follow: **a silent timeout is not an arbitration.** Falling back to
cloud on its own would cross a provider boundary unasked, which §108 forbids.
Expiring without explanation hides the choice instead. The correct behaviour
is to fail loudly and name the option, so the operator arbitrates at the
moment it matters.

## 112.4 What the free plane cannot replace

A model is often wrong, and wrong in ways that read as right. Rejected in one
session: a comment that described the code instead of the damage avoided; an
empty anchor that matched nothing; a nine-commit split presented as
independently revertible when five touched the same file; and — worst — a
documentation section that **invented its measurements**, including a blocked
invocation count, a token saving, a wrong delegated share and a code excerpt
that was not the repository's.

Hence: the analysis is the signal, never the proof. Verify every finding in
the real code. Doctrine that states measured facts must be written by whoever
holds the measurements. The choice of remedy stays with the orchestrator,
which alone weighs side effects.
