# NextSteps.md — CourseForge Implementation Plan

> Document type: Implementation Roadmap
> Status: Approved v0.1 · Owner: Engineering · Last updated: 2026-06-19
> Companion to: `docs/Requirements/04 Functional Requirements.md`, `docs/Requirements/05 Non-Functional Requirements.md`, `docs/Requirements/06 User Stories.md`, `docs/Engineering/11 Testing Strategy.md`, `docs/Engineering/12 Coding Standards.md`

This plan converts the locked-in decisions and the documentation into a concrete, KISS-first build order. Every phase is sized for a single sprint and produces a working, demoable artifact.

---

## 1. Locked-In Decisions

| # | Decision | Implication |
|---|---|---|
| D1 | **SQLite local + Postgres-in-CI** | One SQLAlchemy 2.0 async code path; only the DSN changes. No conditional SQL. |
| D2 | **In-memory `asyncio.Queue` first, Redis later** | One `JobQueue` port, one in-memory adapter. The Redis adapter lands in Phase 5. |
| D3 | **`agent.py` stays as a demo CLI** | The CLI calls the orchestrator and runs the human-feedback loop. It becomes a smoke-test fixture. |
| D4 | **`contracts/json_output.v1.json` + `jsonschema` gate** | Hand-authored schema. The orchestrator's output is validated against it in CI. |
| D5 | **`src/cogenai/agents/prompts/*.yml` with free-text `description`** | YAML carries `name`, `version`, `description`, `system_prompt`, `user_prompt`. |
| D6 | **KISS** | No premature abstractions; no ports we don't yet need; smallest change that satisfies each FR. |
| D7 | **YAML carries `version: "1.0.0"`** | Pinned in the `agent_trace`; bumping is a single reviewable change (NFR-MAINT-004). |
| D8 | **Tests at the end of each phase** | No tests in earlier phases (speed). First test lands at the end of S1 (the YAML loader). |
| D9 | **Jobs lost on restart** | In-memory queue + repo. SQLite-backed repo arrives in Phase 3. |

---

## 2. What We Will *Not* Do (KISS Guardrails)

- ❌ No new `application/` use-case classes for agents that already work as-is.
- ❌ No DI framework; module-level `get_*` factory functions in `bootstrap/container.py`.
- ❌ No event-sourcing / outbox; simple `await repo.save()` is fine.
- ❌ No `importlinter` in CI yet (add only when a real violation is about to land).
- ❌ No separate `Worker` container; the API process runs the consumer as a background task.
- ❌ No `tenants` column yet (Phase 5).
- ❌ No multi-agent model routing (Phase 5).
- ❌ No partial mocking of LLM responses inside S1–S3; tests use a deterministic stub.

---

## 3. Phased Roadmap

### Phase 1 — Orchestrator wires the pipeline (Sprint 1)

> Single goal: `agent.py` and `app.py` route through `OrchestratorAgent`.

**Tasks:**

1. **Move prompts to YAML** at `src/cogenai/agents/prompts/*.yml` (one file per agent, 10 total):
   - `context_synthesizer.yml`, `curriculum_planner.yml`, `section_author.yml`, `persona_adapter.yml`, `content_block_generator.yml`, `consistency_checker.yml`, `prerequisite_validator.yml`, `evaluator.yml`, `refiner.yml`, `orchestrator.yml`
   - Schema (per file):
     ```yaml
     name: context_synthesizer
     version: "1.0.0"
     description: |
       Free-text multi-line description of what this agent does and why.
     system_prompt: |
       You are a ContextSynthesizer agent. ...
     user_prompt: |
       Topic: {topic}
       Audience: {audience}
       ...
     ```
2. **New `agents/yaml_prompt_registry.py`**:
   - `load_from_directory(path: Path)` at startup.
   - `get(agent, version) -> PromptBundle(system: str, user: str)`.
   - `version` is read from YAML, not hardcoded.
3. **Delete `prompt_registry.register(...)`** calls from every agent module.
4. **Wire the orchestrator** (`agents_implementations/orchestator.py`):
   - Accept a `dict[str, BaseAgent]` of already-constructed agents.
   - `run()` calls: `ContextSynthesizer → CurriculumPlanner → for each section: SectionAuthor → PersonaAdapter → ContentBlockGenerator`.
   - Then: `ConsistencyChecker → PrerequisiteValidator → Evaluator`.
   - If report fails and `iterations < max`, call `Refiner` and re-run per-section agents whose blocks were flagged.
   - `user_feedback` flows through `OrchestratorInput` into the next iteration's `user_prompt`.
5. **`bootstrap/container.build_agents()` factory** — constructs all 9 agents + the orchestrator, returns them.
6. **Refactor `agent.py` to ~50 lines**: call the orchestrator, run the `input()` loop.
7. **First test** (`tests/unit/test_yaml_prompt_registry.py`):
   - Asserts all 10 YAMLs load.
   - Asserts `version` is `"1.0.0"` on every one.
   - Asserts `system_prompt` and `user_prompt` are non-empty.

**Acceptance:**
- `python agent.py` produces the same score trajectory as today.
- `agent.py` ≤ 50 lines.
- Orchestrator's `agent_trace` contains every agent invocation.
- `pytest tests/unit/test_yaml_prompt_registry.py` is green.

### Phase 2 — Async jobs + status endpoint (Sprint 2)

> Goal: `POST /v1/courses/generate` returns 202 + `job_id`; `GET /v1/jobs/{id}` returns status.

**Tasks:**

1. **Define `Job` aggregate** in `src/cogenai/domain/jobs/entities.py`:
   ```python
   @dataclass(frozen=True)
   class Job:
       id: str
       status: Literal["queued", "running", "completed", "failed", "partial"]
       progress: float
       input: OrchestratorInput
       output: JSONOutputContract | None
       iteration_scores: tuple[float, ...]
       started_at: datetime
       completed_at: datetime | None
       termination_reason: str
   ```
2. **`JobRepository` port** in `domain/ports/jobs.py`:
   ```python
   class JobRepository(Protocol):
       async def save(self, job: Job) -> None: ...
       async def get(self, job_id: str) -> Job | None: ...
       async def list(self, limit: int = 20) -> list[Job]: ...
   ```
3. **In-memory adapter** in `bootstrap/` (no new folder): `dict[str, Job]` behind an `asyncio.Lock`.
4. **In-memory `asyncio.Queue` consumer** started as a `BackgroundTask` in `create_app()`:
   - Reads jobs from the queue.
   - Calls the orchestrator with a `progress_callback(job_id, phase, progress)`.
   - Writes progress at each phase boundary (planner → sections → evaluation).
5. **API endpoints**:
   - `POST /v1/courses/generate` → 202 `{job_id, status_url}`; enqueues.
   - `GET /v1/jobs/{id}` → status + progress + `iteration_scores`.
   - `GET /v1/jobs/{id}/result` → full `JSONOutputContract` when `completed`.
   - `DELETE /v1/jobs/{id}` → cancel flag; orchestrator checks between iterations.
6. **WebSocket `/v1/jobs/{id}/stream`** — in-process pub/sub keyed by `job_id`; orchestrator publishes per-agent events.
7. **`agent.py` becomes a smoke test** — calls `build_agents()`, runs one job synchronously against the in-memory queue, prints the trace.
8. **Tests** (`tests/integration/test_job_lifecycle.py`):
   - `POST /v1/courses/generate` returns 202 + `job_id`.
   - `GET /v1/jobs/{id}` transitions `queued → running → completed`.
   - `GET /v1/jobs/{id}/result` returns the `JSONOutputContract`.

**Acceptance:**
- All four endpoints work end-to-end.
- WebSocket streams agent events.
- `pytest tests/integration/` is green.

### Phase 3 — SQLite (local) + Postgres (CI) persistence (Sprint 3)

> Goal: jobs survive a process restart; the JSON output contract is persisted.

**Tasks:**

1. **SQLAlchemy 2.0 async** with one env var: `DATABASE_URL=sqlite+aiosqlite:///./cogenai.db` (dev) or `postgresql+asyncpg://...` (CI).
2. **Alembic** for migrations (NFR-PORT-004). One initial migration creates:
   - `jobs (id PK, status, input_json, output_json, progress, iteration_scores JSON, started_at, completed_at, termination_reason)`
   - `agent_trace_entries (job_id FK, agent, phase, iteration, started_at, completed_at, tokens_in, tokens_out, status)`
   - Courses/blocks persistence is **not** in MVP (Phase 5).
3. **`SQLAlchemyJobRepository`** implements the port from Phase 2; the in-memory adapter stays as a test fixture.
4. **Lineage fields** (FR-VC-002, FR-JC-003) stored on the `Job` row: `prompt_version`, `model_version`, `rubric_version`, `provider`, `seed`.
5. **CI workflow**:
   - Postgres service container.
   - `alembic upgrade head`.
   - Full test matrix.
   - Local dev continues to use SQLite via the same code path.
6. **Tests** (`tests/integration/test_sqlalchemy_repo.py`):
   - Round-trip a `Job` via SQLite (in-process) and Postgres (CI only).
   - Assert `agent_trace_entries` are linked correctly.

**Acceptance:**
- A job started on SQLite survives a process restart.
- CI is green against Postgres.
- `pytest tests/integration/` is green locally (SQLite) and in CI (Postgres).

### Phase 4 — Test pyramid + JSON contract gate (Sprint 4)

> Goal: tests catch regressions; the JSON contract cannot drift.

**Tasks:**

1. **Test layout** (per the testing strategy, kept minimal):
   ```
   tests/
   ├── unit/                       # agents, domain, value objects
   ├── integration/                # SQLite repo via aiosqlite, in-memory queue
   ├── contract/
   │   ├── test_json_contract.py   # ← gates json_output.v1.json
   │   └── test_ports.py           # stub LLM satisfies LLMProvider port
   ├── e2e/
   │   └── test_job_lifecycle.py
   ├── eval/
   │   └── test_golden_courses.py
   ├── fixtures/
   │   ├── llm/stub_provider.py
   │   └── golden_courses/
   │       ├── python_beginner.json
   │       ├── python_advanced.json
   │       └── ml_intermediate.json
   └── conftest.py
   ```
2. **`contracts/json_output.v1.json`** — hand-authored, versioned.
3. **`contracts/test_json_contract.py`** — runs the orchestrator end-to-end with the stub LLM and validates the output via `jsonschema`.
4. **Stub LLM provider** with deterministic responses per `(agent_name, prompt_version, inputs_hash)`.
5. **Golden course eval** (NFR-MAINT-005): 3 topics × 2 difficulties, run on stub LLM, assert score ≥ threshold and known issues surface.
6. **CI gates**:
   - `ruff` + `mypy --strict`
   - `pytest -m "unit or contract"`
   - `pip-audit`
   - `alembic upgrade head` on clean Postgres
   - Coverage gate: domain 90% / infra 70%
7. **No `importlinter` in CI yet** (KISS).

**Acceptance:**
- `pytest` runs in < 30 s for unit+contract.
- A deliberate schema change requires a version bump and a contract-test update.
- Eval suite is green; rubric/prompt changes are gated.

### Phase 5 — Polish (post-MVP)

Out-of-scope for Sprints 1–4. Listed so the order is clear:

1. Redis-backed `JobQueue` (replace in-memory adapter).
2. Markdown/PDF export (FR-EX-001..005).
3. Granular regeneration (block / section / module) (FR-RG-*).
4. Feedback at all levels (FR-FB-*).
5. Provider health + circuit breaker (FR-PR-005).
6. Cost & metrics dashboard (FR-DS-*).
7. Per-agent model assignment (FR-AG-014).
8. Multi-tenant isolation (FR-CX-006, FR-UM-003).
9. AuthN/Z (FR-UM-001, FR-UM-002).

---

## 4. FR Coverage Matrix (Sprints 1–4)

| FR | Sprint | Notes |
|---|---|---|
| FR-AG-001 Orchestrator | S1 | Single writer |
| FR-AG-002..009 Agents | S1 | Already built; wire through orchestrator |
| FR-AG-010 Refinement loop | S1 | Already in `agent.py`; moves to orchestrator |
| FR-AG-011 Iteration cap | S1 | Enforced in orchestrator |
| FR-CG-004 Async job lifecycle | S2 | New endpoint + queue |
| FR-CS-003 Stable IDs | S2 | UUIDs already; persist in S3 |
| FR-VC-002 Lineage | S3 | Persisted on `Job` row |
| FR-JC-001 Single JSON response | S4 | Contract test |
| FR-JC-002 Schema versioning | S4 | `schema_version` in contract |
| FR-JC-003 Agent trace | S3 + S4 | Persisted (S3), validated (S4) |
| NFR-MAINT-001 Hexagonal | S4 | `importlinter` deferred (KISS) |
| NFR-MAINT-002 Coverage | S4 | Enforced from S4 onward |
| NFR-MAINT-003 Lint/types | S4 | `ruff` + `mypy --strict` |
| NFR-MAINT-004 Prompt versioning | S1 | YAML carries `version` |
| NFR-MAINT-005 Eval suite | S4 | Golden courses |
| NFR-OBS-001 Structured logs | S1 | Already done |
| NFR-OBS-004 Agent trace persisted | S3 | New table |
| NFR-PORT-001 Local dev | S3 | SQLite via docker-compose-free setup |
| NFR-PORT-004 Migrations | S3 | Alembic |
| NFR-TEST-001..003 Test pyramid | S4 | Unit, contract, e2e |
| NFR-TEST-004 Eval gate | S4 | Golden course regressions fail CI |

---

## 5. File-by-File Impact (Sprint 1)

| File | Action | Why |
|---|---|---|
| `src/cogenai/agents/prompts/*.yml` (10 new files) | **create** | D5, D7 |
| `src/cogenai/agents/yaml_prompt_registry.py` | **create** | Loads YAML at startup |
| `src/cogenai/agents/registry.py` | **delete** | Replaced by YAML registry |
| `src/cogenai/agents_implementations/*.py` (10) | **edit** | Drop `register()`; use YAML loader |
| `src/cogenai/agents_implementations/orchestator.py` | **rewrite** | Real pipeline + feedback loop |
| `src/cogenai/bootstrap/container.py` | **edit** | Add `build_agents()` factory |
| `src/cogenai/bootstrap/app.py` | **edit** | Routes through orchestrator |
| `agent.py` | **rewrite** | Thin demo CLI (≤ 50 lines) |
| `pyproject.toml` | **edit** | Add `pyyaml`, `jsonschema` |
| `tests/unit/test_yaml_prompt_registry.py` | **create** | First test (D8) |

**Net: ~12 files touched, 11 new. No new architectural layer.**

---

## 6. Sprint 1 Acceptance Checklist

- [ ] `prompts/` exists with 10 YAML files using the agreed schema.
- [ ] `agents/yaml_prompt_registry.py` loads all 10 at startup; `version` is read from YAML.
- [ ] `agent.py` ≤ 50 lines and produces a valid course through the orchestrator.
- [ ] Orchestrator's `agent_trace` shows every agent call (one entry per agent per iteration).
- [ ] Human feedback via `input()` flows into the next iteration's `user_prompt`.
- [ ] `pytest tests/unit/test_yaml_prompt_registry.py` is green.
- [ ] `ruff` and `mypy` are clean for changed files.
- [ ] `agent.py`'s output (course + score trajectory) is the same as before the refactor.

---

## 7. Out-of-Scope Reminders

When a Phase 5 task is mentioned in conversation, defer it to a follow-up:

- Auth, tenants, per-agent models, Redis, exports, granular regen, dashboards, circuit breaker, multi-provider health, observability beyond structured logs.

---

## 8. Cross-References

- `docs/Requirements/04 Functional Requirements.md` — source of FR IDs in §4.
- `docs/Requirements/05 Non-Functional Requirements.md` — source of NFR IDs in §4.
- `docs/Requirements/06 User Stories.md` — US traceability for each sprint.
- `docs/Engineering/11 Testing Strategy.md` — drives §3.4 (test layout).
- `docs/Engineering/12 Coding Standards.md` — drives file-naming and the KISS guardrails.
- `docs/Architecture/08 C4 Architecture.md` — drives container boundaries (API process + in-process worker).
- `docs/Architecture/09 Architecture Decision Records.md` — capture each locked-in decision as an ADR.
