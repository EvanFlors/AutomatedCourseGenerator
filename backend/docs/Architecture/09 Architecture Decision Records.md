# 09 Architecture Decision Records

> Document type: Architecture Decision Records (ADRs)
> Companion to: `07 System Context Diagram.md`, `08 C4 Architecture.md`
> Status: Draft v0.1 · Owner: Architecture · Last updated: 2026-06-05
> Each ADR follows the MADR template: Context / Decision / Consequences.

---

## 1. Document Control

| Field | Value |
|---|---|
| Project codename | CourseForge |
| Document version | 0.1 (Draft) |
| Author | Architecture + Tech Leads |
| Reviewers | All engineering leads |
| Approvers | Head of Engineering |
| Cadence | New ADRs are added when a non-trivial decision is made; superseded ADRs are marked as such. |

---

## 2. Index

| ID | Title | Status |
|---|---|---|
| [0001](#adr-0001--hexagonal-architecture--ddd) | Hexagonal Architecture + DDD | Accepted |
| [0002](#adr-0002--multi-agent-folder-with-self-refinement-loop) | Multi-Agent Folder with Self-Refinement Loop | Accepted |
| [0003](#adr-0003--provider-agnostic-llm-layer) | Provider-Agnostic LLM Layer | Accepted |
| [0004](#adr-0004--json-output-contract-as-single-frontend-interface) | JSON Output Contract as Single Frontend Interface | Accepted |
| [0005](#adr-0005--postgres-for-metadata-neo4j-for-knowledge-graph) | Postgres for Metadata, Neo4j for Knowledge Graph | Accepted |
| [0006](#adr-0006--typed-content-blocks-as-core-domain) | Typed Content Blocks as Core Domain | Accepted |
| [0007](#adr-0007--rubric-versioning) | Rubric Versioning | Accepted |
| [0008](#adr-0008--refinement-loop-termination-policy) | Refinement Loop Termination Policy | Accepted |
| [0009](#adr-0009--per-scope-iteration-cap-and-budget) | Per-Scope Iteration Cap and Budget | Accepted |
| [0010](#adr-0010--manual-edits-are-not-silently-re-evaluated) | Manual Edits Are Not Silently Re-Evaluated | Accepted |
| [0011](#adr-0011--document-versioning-with-full-lineage) | Document Versioning with Full Lineage | Accepted |
| [0012](#adr-0012--provider-circuit-breaker-and-failover) | Provider Circuit Breaker and Failover | Accepted |

---

## ADR-0001 — Hexagonal Architecture + DDD

**Status:** Accepted · **Date:** 2026-06-05

### Context
We need an architecture that supports multiple LLM providers, multiple
storage backends, and an evolving agent folder, without leaking any of
those concerns into the business logic. We expect frequent changes to
prompts, providers, and storage. Testability is critical because the
domain (course design) **is** the product.

### Decision
Adopt **Hexagonal Architecture (Ports & Adapters)** combined with
**Domain-Driven Design**. The codebase is layered:

- `domain/` — pure business logic, no external imports.
- `application/` — use cases, orchestrates the domain.
- `infrastructure/` — adapters (Postgres, Neo4j, providers, etc.).
- `interfaces/` — delivery mechanisms (FastAPI, CLI, WebSocket).
- `bootstrap/` — wiring.

The architecture is **enforced** by `importlinter` in CI
(NFR-MAINT-001).

### Consequences
- (+) Domain is testable without any I/O.
- (+) New providers, storage backends, and block types are plug-ins.
- (+) Clear ownership by bounded context.
- (−) Requires discipline; layering is enforced by tooling, not by
  code review alone.
- (−) More boilerplate up-front; the team must internalize the
  boundaries.

---

## ADR-0002 — Multi-Agent Folder with Self-Refinement Loop

**Status:** Accepted · **Date:** 2026-06-05

### Context
Single-shot LLM generation produces content that is inconsistent,
sometimes incorrect, and not calibrated to audience. We need to produce
higher-quality drafts without manual intervention per block, and we need
to make quality **observable** to the user.

### Decision
Organize generation as a **folder of specialized agents** collaborating
in an explicit **evaluate–refine loop** (BRD §10):

- **Creator agents** (CurriculumPlanner, SectionAuthor, PersonaAdapter)
  draft content.
- **Critic agents** (ConsistencyChecker, PrerequisiteValidator,
  Evaluator) score drafts and emit structured issues.
- A **Refiner** agent applies the issues to produce a revised draft.
- An **Orchestrator** coordinates the loop and is the **only** component
  authorized to write to persistence (FR-AG-001).

The loop terminates on pass, iteration cap, budget exhaustion, or user
abort (ADR-0008).

### Consequences
- (+) Quality is observable, not opaque.
- (+) Per-iteration scores give users confidence in the system.
- (+) Per-agent model assignment lets us balance cost and quality.
- (−) Multi-agent loops multiply token spend (mitigated by per-scope
  budgets — ADR-0009 — and caching).
- (−) Non-determinism across runs; lineage is required for
  traceability (ADR-0011).
- (−) More moving parts to monitor (FR-AG-015, graceful degradation).

---

## ADR-0003 — Provider-Agnostic LLM Layer

**Status:** Accepted · **Date:** 2026-06-05

### Context
We need to support multiple LLM providers (OpenAI, Anthropic, Google,
others) without coupling the domain to any provider's API. Provider
behavior, pricing, and quality change frequently. New providers
should be addable without changes to the agent folder, prompts, or
evaluation criteria.

### Decision
Define a single **`LLMProvider` port** in the domain layer. Each
provider is an **adapter** in `infrastructure/llm/`. Agents depend
only on the port. Configuration selects the provider and model per
agent role (FR-AG-014).

The domain layer is **forbidden** from importing any provider SDK; the
rule is enforced by `importlinter` (NFR-MAINT-001, FR-PR-003).

### Consequences
- (+) New provider integration does not require domain or agent
  changes.
- (+) Per-agent model assignment enables cost optimization.
- (+) The frontend is provider-agnostic — end users never see provider
  choice (FR-PR-002).
- (−) Each provider has slightly different capabilities; the port must
  remain a lowest common denominator or expose feature flags.
- (−) Provider outages are a class of failure that must be designed for
  (ADR-0012).

---

## ADR-0004 — JSON Output Contract as Single Frontend Interface

**Status:** Accepted · **Date:** 2026-06-05

### Context
The frontend must be able to render a generated course, surface
quality issues, and offer next actions **without parsing free-form LLM
output**. The LLM is non-deterministic; trusting its raw output is a
contract violation and a security risk.

### Decision
The backend returns a **single, versioned JSON document** on every
completed generation. The contract is defined in `BRD §11` and includes:

- `course` — the course payload.
- `generation` — metadata, prompt / model / rubric versions, and the
  full **agent trace**.
- `evaluation` — per-iteration scores, rubric thresholds, pass/fail.
- `issues` — outstanding problems with severities, categories, and
  suggestions.
- `next_actions` — machine-readable actions for the UI.

The frontend pins to a `schema_version` and refuses to render unknown
major versions (FR-JC-002).

### Consequences
- (+) The frontend is a pure consumer of structured data.
- (+) Quality issues and next actions become a first-class UI surface.
- (+) Schema versioning allows safe evolution.
- (−) Schema is a public contract; breaking changes require
  coordination.
- (−) Frontend must gracefully handle missing optional fields
  (NFR-COMPAT-004).

---

## ADR-0005 — Postgres for Metadata, Neo4j for Knowledge Graph

**Status:** Accepted · **Date:** 2026-06-05

### Context
We have two distinct data shapes:

- **Aggregate-oriented** (courses, jobs, versions, audit, feedback) —
  relational.
- **Graph-oriented** (concepts and prerequisites, course-to-concept
  relations) — graph.

Forcing both into a single store would either compromise the relational
queries (in a graph store) or the graph traversals (in a relational
store).

### Decision
- **Postgres** stores metadata, jobs, audit, lineage, and versions.
- **Neo4j** stores the concept graph (concepts, prerequisites,
  related-to relations, course-to-concept edges).
- The **Orchestrator** is the only component authorized to write to
  both stores; cross-store writes are sequenced and the lineage
  records the ordering (FR-AG-001, BRD §10.1).

### Consequences
- (+) Each store is used for what it is best at.
- (+) Schema is clearer; the two stores do not duplicate concerns.
- (+) Graph queries are first-class (e.g. prerequisite traversal).
- (−) Two databases to operate, back up, and migrate (NFR-AVAIL-006).
- (−) Eventual consistency between stores is possible; the
  Orchestrator enforces write ordering.

---

## ADR-0006 — Typed Content Blocks as Core Domain

**Status:** Accepted · **Date:** 2026-06-05

### Context
Treating all generated content as opaque text makes rendering,
editing, export, and regeneration much harder, and forces the UI to
parse free-form LLM output. It also makes the Evaluator blind to
structural properties (a Quiz has a correct answer; a Code block has
a runnable flag; an Exercise has a solution reference).

### Decision
Each `ContentBlock` carries an explicit `type` (`concept`, `example`,
`code`, `exercise`, `solution`, `challenge`, `quiz`, `key_points`,
`best_practices`, `common_mistakes`, `visual_explanation`, `analogy`,
`reference`) and a typed `content` shape validated by a **JSON Schema
per type** (BRD §11.2.1). Block types are a **domain concept**, not a
UI affordance.

New block types can be added via the **block-type registry**
(FR-BT-001) without changes to the core domain model.

### Consequences
- (+) Rendering, editing, and export can be type-specific.
- (+) The Evaluator can apply type-specific structural checks.
- (+) New block types are plug-ins.
- (−) The schema must be versioned with the same care as the JSON
  contract.
- (−) Type explosion is possible; we keep a closed v1 set and add
  cautiously.

---

## ADR-0007 — Rubric Versioning

**Status:** Accepted · **Date:** 2026-06-05

### Context
The Evaluator's quality rubric will evolve. To make quality scores
comparable over time and to support regression testing, every score
must be tied to a specific rubric version.

### Decision
The rubric is a **versioned artifact** stored in the repository
(ADR-0001's `infrastructure/rubric/`). Every generation records the
`rubric_version` used (`generation.rubric_version` in the JSON
contract). Changing the rubric is a reviewable change and triggers
the **eval suite** in CI (NFR-TEST-004, FR-EV-003).

### Consequences
- (+) Scores are comparable over time.
- (+) Regressions are caught in CI before they ship.
- (+) Old scores can be re-evaluated if we need to re-baseline
  (best-effort).
- (−) More discipline required: every change is a versioned commit.
- (−) Reproducing historical scores requires replaying with the same
  rubric version (and provider version).

---

## ADR-0008 — Refinement Loop Termination Policy

**Status:** Accepted · **Date:** 2026-06-05

### Context
A self-refining loop that never terminates is dangerous (cost,
latency, staleness). The loop must terminate **predictably** and the
termination reason must be visible to the user.

### Decision
The loop terminates when **any** of the following is true
(FR-AG-010, FR-AG-011, FR-AG-012):

1. All rubric dimensions meet their configured thresholds
   (`termination_reason=quality_threshold`).
2. A per-scope iteration cap is reached
   (`termination_reason=max_iterations`).
3. A token or wall-clock budget is exhausted
   (`termination_reason=budget_exhausted`).
4. The user aborts the job (`termination_reason=user_aborted`).

The termination reason is recorded in
`generation.refinement.termination_reason` and surfaced in the UI and
in monitoring (NFR-OBS-004).

### Consequences
- (+) Predictable upper bounds on cost and latency.
- (+) Clear semantics for partial success.
- (+) Users can see why a generation stopped.
- (−) "Quality threshold not met" results may be returned; the UI must
  make this visible (it does, via `issues` and `evaluation.passed`).

---

## ADR-0009 — Per-Scope Iteration Cap and Budget

**Status:** Accepted · **Date:** 2026-06-05

### Context
A coarse global cap (one cap for all scopes) is wasteful: a targeted
block regeneration usually needs far fewer iterations than a full
course. A single budget also makes per-scope cost control impossible.

### Decision
Maintain **per-scope iteration caps and budgets** (FR-AG-011, FR-AG-012,
NFR-COST-001):

| Scope   | Default iterations | Default token budget (in + out) |
|---------|--------------------|----------------------------------|
| Course  | 3                  | 500,000 + 200,000               |
| Module  | 2                  | proportional                    |
| Section | 2                  | proportional                    |
| Block   | 2                  | proportional                    |

Defaults are configurable per tenant and **overridable per request**.
The cap and budget used are recorded in the agent trace.

### Consequences
- (+) Targeted regen is fast and cheap.
- (+) The system can serve more concurrent users at the same spend.
- (−) Defaults must be tuned over time; we ship reasonable defaults
  and adjust from metrics (FR-DS-003).

---

## ADR-0010 — Manual Edits Are Not Silently Re-Evaluated

**Status:** Accepted · **Date:** 2026-06-05

### Context
If the system silently re-evaluates every manual edit, it will
"correct" what the user just fixed. This destroys trust and breaks the
human-in-the-loop model.

### Decision
**Manual edits are saved verbatim.** The Evaluator is invoked only when
the user explicitly clicks **Re-evaluate block** or triggers a
regeneration (FR-ED-003, US-4.2.1). This is a hard rule in the
application layer and is enforced by tests (US-4.2.1 AC-1, AC-2).

### Consequences
- (+) Human authorship is preserved.
- (+) The system is predictable.
- (−) A user-edited block could in principle violate the rubric; the
  UI surfaces the violation only on explicit re-evaluation.

---

## ADR-0011 — Document Versioning with Full Lineage

**Status:** Accepted · **Date:** 2026-06-05

### Context
We must be able to answer **"where did this content come from?"** for
any version of any aggregate. This is non-negotiable for trust,
reproducibility, and audit. Without lineage, debugging a bad
generation is guesswork.

### Decision
Every persisted version records (FR-VC-002, FR-VC-006, NFR-OBS-004):

- The `inputs` hash and content snapshot.
- The `prompt_version`, `model_version`, and `rubric_version` used.
- The full `agent_trace` (which agents ran, in what order, with what
  output, status, timing, and token usage).
- The `seed` where supported.
- A monotonic `version` field for **optimistic concurrency** (FR-INT-003).

**Historical versions are immutable** (FR-VC-006). New edits and
regenerations create new versions rather than mutating the old.

### Consequences
- (+) Full traceability and reproducibility.
- (+) Per-iteration quality trajectories are visible in history.
- (+) Enables a re-eval mode for re-baselining old content.
- (−) Higher storage cost (mitigated by retention policies and
  selective summarization of trace blobs).

---

## ADR-0012 — Provider Circuit Breaker and Failover

**Status:** Accepted · **Date:** 2026-06-05

### Context
LLM providers have outages and rate limits. A single-provider failure
must not take down the platform or hang the user with no feedback.

### Decision
The system tracks per-provider error rates (FR-PR-005). When a
provider's error rate exceeds a configured threshold, a **circuit
breaker** opens; calls during the open state fail fast. If a backup
provider is configured for the affected agent role, calls are routed
to the backup. Both the breaker opening and the failover are recorded
in the agent trace.

### Consequences
- (+) Bounded blast radius for provider failures.
- (+) Faster failure for the user (no long waits).
- (+) Optional automatic failover for high availability.
- (−) Failover may produce different outputs; lineage captures which
  provider actually served the call (ADR-0011).
- (−) Operationally more complex; needs runbooks and monitoring.

---

## 3. ADR Lifecycle

- **Proposed** — drafted, not yet reviewed.
- **Accepted** — reviewed and baselined.
- **Deprecated** — superseded by a newer ADR; cross-reference provided.
- **Superseded by ADR-NNNN** — see the newer ADR for the current rule.

---

## 4. Cross-References

- **System Context** — `07 System Context Diagram.md`
- **C4 Container & Component** — `08 C4 Architecture.md`
- **Sequence Diagrams** — `10 Sequence Diagrams.md`
- **JSON Output Contract** — `02 Business Requirements Document.md` §11
- **Functional Requirements** — `04 Functional Requirements.md`
- **Non-Functional Requirements** — `05 Non-Functional Requirements.md`
