# 11 Testing Strategy

> Document type: Engineering — Testing Strategy
> Companion to: `04 Functional Requirements.md`, `05 Non-Functional Requirements.md`, `06 User Stories.md`, `08 C4 Architecture.md`
> Status: Draft v0.1 · Owner: QA Lead + Engineering · Last updated: 2026-06-05
> This document defines how CourseForge is tested end-to-end: principles,
> test pyramid, tooling, fixtures, and CI gates. Project-level coding
> standards are in `12 Coding Standards.md`.

---

## 1. Document Control

| Field | Value |
|---|---|
| Project codename | CourseForge |
| Document version | 0.1 (Draft) |
| Author | QA Lead + Engineering |
| Reviewers | Backend Lead, AI Lead, Frontend Lead, DevOps Lead |
| Approvers | Head of Engineering |
| Cadence | Reviewed at the end of each sprint |

---

## 2. Purpose and Scope

### 2.1 Purpose
Define a single, executable strategy for verifying that CourseForge
behaves correctly, is safe to change, and meets its non-functional
requirements. The strategy must be:

- **Executable** — every test runs in CI on every PR.
- **Deterministic** — non-LLM-dependent tests have no flakiness.
- **Bounded** — the full suite finishes in a predictable time budget.
- **Traceable** — every requirement is covered by a named test class
  or marker.

### 2.2 Scope
- Backend: domain, application, infrastructure, interfaces, agents.
- Frontend: components, hooks, state, routing, accessibility.
- Cross-cutting: the JSON output contract, the agent folder, observability.
- Operational: load tests, security scans, dependency audits.

### 2.3 Out of scope
- Production traffic monitoring (lives in observability stack).
- Manual user-acceptance testing (lives in QA procedures).
- Customer-side integration (lives in customer success).

---

## 3. Testing Principles

| # | Principle |
|---|---|
| P-1 | **Test the domain first.** The domain has the highest logic density and the lowest cost of test. |
| P-2 | **Fast feedback at the bottom of the pyramid.** Unit tests run in seconds; integration tests in minutes; e2e in tens of minutes. |
| P-3 | **No free-form LLM output in tests.** Tests assert against the JSON contract, not against LLM prose. |
| P-4 | **Determinism over realism.** Prefer in-memory fakes and recorded fixtures over real services for unit/integration. |
| P-5 | **Coverage is a floor, not a goal.** Coverage gates catch obvious gaps; review catches real ones. |
| P-6 | **Flaky tests block merges.** A flaky test is treated as a bug; it must be fixed or deleted within 24 h. |
| P-7 | **Tests document intent.** A test name should read like a sentence describing the behavior under test. |
| P-8 | **One assertion concept per test.** Multiple asserts are fine if they verify one behavior. |
| P-9 | **Test names reference requirements.** `test_FR_ED_003_manual_edit_not_re_evaluated` is preferred to `test_save`. |
| P-10 | **Tests are part of the deliverable.** A feature is not "done" until its tests are merged and green. |

---

## 4. Test Pyramid

```
                ┌──────────────────────┐
                │  E2E & Contract       │  Few; slow; high-fidelity
                ├──────────────────────┤
                │  Integration          │  Moderate; testcontainers
                ├──────────────────────┤
                │  Unit                 │  Many; fast; no I/O
                └──────────────────────┘
```

| Layer | What it covers | Tools | Target time | Target count |
|---|---|---|---|---|
| Unit | Domain logic, application use cases, pure functions, validators, mappers | `pytest` | < 5 s total | thousands |
| Integration | Adapters: Postgres, Neo4j, Redis, S3, SMTP, LLM stubs | `pytest` + `testcontainers` | < 5 min total | hundreds |
| Contract | JSON output schema, OpenAPI, agent contracts, port contracts | `pytest` + `jsonschema` + `schemathesis` | < 1 min | dozens |
| E2E | Full HTTP/WebSocket journey; UI happy paths | `pytest` + `httpx` + Playwright | < 10 min | dozens |
| Eval (agents) | Agent quality on a golden course set | Custom runner + LLM stub or recorded | < 15 min | dozens |
| Performance | Latency, throughput, scalability targets (`05` §3, §4) | `k6`, `locust` | scheduled | few |
| Security | SAST, SCA, secret scan, dep audit | `ruff`, `bandit`, `pip-audit`, `gitleaks`, `npm audit` | < 2 min | gates |
| Accessibility | WCAG 2.1 AA on key UI flows | `axe-core` (Playwright) | < 1 min | per flow |

### 4.1 Markers
Tests are tagged with `pytest` markers so contributors and CI can run
subsets:

| Marker | Meaning |
|---|---|
| `unit` | Pure, no I/O. Always runs. |
| `integration` | Spins up real services via testcontainers. |
| `contract` | Validates schemas / API contracts. |
| `e2e` | Full-stack journey. |
| `eval` | Agent quality suite. |
| `requires_docker` | Needs Docker for testcontainers. Skip in restricted CI. |
| `requires_llm` | Hits a real LLM (or stub). Gated; not in default CI. |
| `slow` | Long-running; run on a schedule, not on every PR. |

### 4.2 Default invocations
- `pytest` — runs `unit`, `contract`. Target: < 30 s.
- `pytest -m "not slow and not requires_docker"` — default CI lane.
- `pytest -m "integration or contract or e2e"` — full pre-merge lane.
- `pytest -m eval` — weekly + on rubric / prompt changes.
- `k6 run ...` — nightly + on releases.

---

## 5. Test Types in Detail

### 5.1 Unit tests
- **What they cover:** domain aggregates, value objects, application use
  cases with all ports mocked.
- **Tools:** `pytest`, `pytest-asyncio` (asyncio_mode=auto).
- **Determinism:** No real time, no network, no filesystem, no I/O.
- **Style:** Arrange–Act–Assert; explicit fakes; no shared state.
- **Naming:** `test_<unit>_<behavior>_<expected>()`.

### 5.2 Integration tests
- **What they cover:** adapter correctness against real Postgres,
  Neo4j, Redis, S3 (localstack), SMTP (mailpit), and a stubbed LLM
  provider that returns recorded responses.
- **Tools:** `testcontainers[postgres,neo4j]`, `localstack`, `mailpit`,
  `httpx` against FastAPI in-process.
- **Scope:** per adapter; per bounded context repository.
- **Cleanup:** each test uses a transactional rollback or a per-test
  schema; never assume a clean DB.

### 5.3 Contract tests
- **What they cover:**
  - The JSON output contract (BRD §11) — `schema_version`-pinned.
  - The OpenAPI stub is reachable and matches the routes.
  - Port contracts: every adapter passes the contract test for its port.
  - Event contracts: domain events serialized as documented.
- **Tools:** `jsonschema`, `pydantic` (round-trip), `schemathesis` for
  OpenAPI fuzz.
- **Gate:** breaking changes require a major version bump and an
  explicit PR label (`contract-break`).

### 5.4 End-to-end tests
- **What they cover:** a complete user journey through HTTP and
  WebSocket — generate a course, observe agent trace, edit a block,
  regenerate, export, verify Markdown output.
- **Tools:** `pytest` + `httpx` (API) + Playwright (UI) + a stub LLM
  provider with deterministic, versioned fixtures.
- **Scope:** a small set of golden journeys; not a substitute for unit
  or integration tests.
- **Determinism:** stub LLM provider only; never the real network.

### 5.5 Agent evaluation suite (eval)
- **What it covers:** end-to-end quality of the agent folder on a
  **golden course set** — known topics with reference quality scores
  per dimension, and known issues that the Evaluator should flag.
- **Tools:** a custom runner that:
  1. Loads the golden set.
  2. Runs the Orchestrator end-to-end with a stub LLM provider whose
     responses are recorded from real runs.
  3. Asserts rubric scores within tolerance.
  4. Asserts that specific known issues are surfaced.
- **Cadence:**
  - Weekly scheduled run.
  - On every change to: prompts, rubric, model assignments, agent code.
- **Gate:** regressions beyond the configured threshold fail the PR
  (NFR-TEST-004, FR-EV-005).

### 5.6 Performance tests
- **What they cover:** NFR-PERF-001 (end-to-end latency), NFR-PERF-003
  (API response time), NFR-PERF-004 (curriculum tree render), NFR-SCALE-*
  (concurrency and catalog size).
- **Tools:** `k6` (HTTP), `locust` (optional), Playwright tracing
  (frontend), `pgbench` / `EXPLAIN ANALYZE` (DB).
- **Cadence:** nightly; on releases; on architectural changes.
- **Gate:** p95 / p99 regressions beyond the threshold fail the release.

### 5.7 Security tests
- **SAST:** `ruff` (Python), `bandit` (Python), `eslint` security
  plugin (TS).
- **SCA:** `pip-audit` (Python), `npm audit` (TS), `osv-scanner`.
- **Secret scan:** `gitleaks` in CI.
- **Container scan:** `trivy` on built images.
- **DAST (optional):** OWASP ZAP against a staging environment.
- **Prompt-injection test set:** known payloads that must be rejected
  or surfaced as `issues` (NFR-SEC-006).

### 5.8 Accessibility tests
- **Tool:** `axe-core` via Playwright, run on each key UI flow.
- **Gate:** any AA violation on a key flow fails the PR.
- **Manual audit:** screen-reader (VoiceOver / NVDA) walkthrough on a
  quarterly cadence.

### 5.9 Property-based tests
- **What they cover:** invariant properties that must hold for any
  input — e.g. "a course that passes the rubric cannot have a section
  that violates ordering", "an `agent_trace` is acyclic", "version
  pointers always reference an existing version".
- **Tool:** `hypothesis` (Python) for the most critical invariants.
- **Scope:** limited to invariants whose violation is a class of bug.

---

## 6. Test Doubles Strategy

| Double | When to use | Example |
|---|---|---|
| **Fake** | In-memory implementation of a port for unit tests | `InMemoryCourseRepository` |
| **Stub** | Returns canned responses; does not record | `StubLLMProvider` returning a recorded draft |
| **Mock** | Records calls and asserts on them | `mock.patch` for time, randomness, env |
| **Spy** | Records calls without asserting | Wrapper around a real adapter |
| **Testcontainers** | Real DB / cache / queue for integration | `testcontainers[postgres,neo4j]` |
| **Localstack** | Real S3-compatible API for integration | Object storage adapter |
| **Recorded responses** | Stub LLM with golden responses | `tests/fixtures/llm/<name>.json` |

### 6.1 LLM stubbing
The LLM provider is **stubbed by default** in all tests except the
scheduled eval suite. The stub:

- Returns recorded responses keyed by `(agent_role, prompt_version,
  inputs_hash)`.
- Has a "fault injection" mode for testing the Orchestrator's error
  paths (timeout, 5xx, malformed JSON).
- Never hits the network.

### 6.2 Time and randomness
- Time is controlled via `freezegun` or a `Clock` port; production code
  uses the port, not `datetime.now()`.
- Randomness is controlled via a `Random` port; production code uses
  the port with a configurable seed.

---

## 7. Test Data and Fixtures

### 7.1 Fixture layout
```
tests/
├── unit/                  # No I/O; fast
├── integration/           # testcontainers
├── contract/              # JSON schema, OpenAPI, port contracts
├── e2e/                   # Full journey
├── eval/                  # Agent evaluation suite
├── perf/                  # k6 / locust scripts
├── security/              # SAST/SCA configs and prompt-injection set
├── a11y/                  # axe-core flows
├── fixtures/
│   ├── courses/           # Golden courses (JSON)
│   ├── llm/               # Recorded LLM responses
│   ├── documents/         # Sample PDFs, MD, TXT
│   └── users/             # Synthetic users
└── conftest.py
```

### 7.2 Golden course set
A small, versioned set of courses (e.g. 5 topics across difficulty
levels) used by the eval suite. Each golden course has:

- A reference `course.json` (the expected payload).
- Reference `evaluation` scores per dimension.
- A list of expected `issues` (some passing, some failing deliberately).
- A `seed` for reproducibility.

### 7.3 Synthetic users
Tests use synthetic, non-PII user identities. Real emails are never
used; test auth uses a backdoor that is only available when
`APP_ENV=test`.

### 7.4 Documents
- Sample PDFs (≤ 1 MB) with known content used to assert document
  ingestion.
- Sample Markdown and text files.
- One EICAR test file for malware rejection (NFR-SEC-005).

---

## 8. CI Gates

| Stage | Gate | Blocks merge? |
|---|---|---|
| Lint & types | `ruff`, `mypy --strict`, `eslint`, `tsc --strict` | Yes |
| Unit + contract | `pytest -m "unit or contract"` | Yes |
| Security | `gitleaks`, `pip-audit`, `npm audit`, `bandit` | Yes (on critical/high) |
| Domain import check | `importlinter` enforces `domain/` has no infra imports | Yes |
| Integration (default lane) | `pytest -m "integration and not requires_docker"` | Yes |
| E2E (default lane) | `pytest -m e2e` | Yes |
| Coverage | ≥ 90% domain/application, ≥ 70% infrastructure | Yes |
| Eval suite (PR lane) | `pytest -m eval` on prompt/rubric/agent changes | Yes (those changes) |
| A11y on key flows | `axe-core` zero AA violations on key flows | Yes |
| Container build | `docker build` succeeds; image scan clean | Yes |
| Performance (scheduled) | `k6` within budget | No (advisory) |
| Eval suite (full) | `pytest -m eval` against golden set | No (advisory; weekly) |

### 8.1 Pipeline shape
```
PR open / push
  ├── lint & types ──── (parallel)
  ├── unit & contract ─┐
  ├── security ────────┤
  ├── domain import ───┤
  ├── integration ─────┤── all required
  ├── e2e ─────────────┘
  ├── a11y (key flows)
  └── coverage gate

scheduled (nightly)
  ├── performance
  ├── full eval suite
  └── dependency audit

on release
  ├── performance (extended)
  ├── security (deep)
  └── full eval
```

---

## 9. Coverage and Quality Targets

| Layer | Line coverage | Branch coverage | Notes |
|---|---|---|---|
| Domain | ≥ 90% | ≥ 85% | NFR-MAINT-002 |
| Application | ≥ 90% | ≥ 85% | NFR-MAINT-002 |
| Infrastructure (adapters) | ≥ 70% | ≥ 60% | NFR-MAINT-002 |
| Interfaces (API/UI) | ≥ 70% | ≥ 60% | NFR-MAINT-002 |
| Agents | ≥ 80% | ≥ 75% | Critical path; higher bar |

Coverage is **necessary but not sufficient**. Reviewers look at the
quality of the tests, not just their existence.

---

## 10. Definition of Done — Tests

A test is "done" when:

- It is **named** for the requirement it covers.
- It is **deterministic** (no flake, no real time, no real network).
- It is **fast** for its layer (unit < 100 ms, integration < 5 s).
- It is **readable** (Arrange–Act–Assert; one behavior; clear failure).
- It is **maintained** (updated when the requirement changes; deleted
  when the requirement is removed).
- It is **CI-runnable** (no manual setup; no external dependencies
  beyond what `testcontainers` provides).
- It is **documented** in the test name or a one-line docstring.

---

## 11. Risk-Based Testing Priorities

| Risk (from BRD §13 / Charter §16) | Test emphasis |
|---|---|
| Hallucinations / factual errors | Eval suite with golden courses; `category=factual` issue fixtures |
| Refinement loop stalls | Loop dynamics tests; trajectory assertions; budget-cap tests |
| Provider instability | Fault-injection tests; circuit-breaker tests; failover tests |
| Cost overruns | Budget-cap tests; per-scope iteration tests; cost-telemetry tests |
| Scope creep | Story-to-FR traceability is enforced by naming; missed FRs surface in review |
| Rubric drift | Versioned rubric; eval suite regression test on every rubric change |
| Security / prompt injection | Prompt-injection set; secret scan; tenant isolation tests |
| Data loss | Chaos tests: kill worker between writes; lineage integrity tests |
| Non-determinism | Determinism tests; seed reproducibility (where provider supports) |

---

## 12. Test Anti-Patterns (Banned)

- **Asserting on LLM prose** — assert on the JSON contract.
- **Real network in tests** — no real LLM calls, no real YouTube, no
  real web fetch.
- **`time.sleep`** — use the `Clock` port.
- **Shared mutable state between tests** — every test owns its data.
- **Tests that pass by accident** — every green test must fail when
  the code under test is broken.
- **Mocks that re-implement the system** — fakes, not replicas.
- **Coverage-only tests** — a test with no assertion is not a test.
- **Snapshot tests of LLM output** — captures non-determinism, hides
  regressions.

---

## 13. Cross-References

- **Coding Standards** — `12 Coding Standards.md`
- **Functional Requirements** — `04 Functional Requirements.md`
- **Non-Functional Requirements** — `05 Non-Functional Requirements.md`
- **User Stories** — `06 User Stories.md`
- **Architecture** — `08 C4 Architecture.md`
- **ADRs** — `09 Architecture Decision Records.md`
- **JSON Output Contract** — `02 Business Requirements Document.md` §11
- **Test Guide (operational)** — `PYTEST_GUIDE.md` (existing)
