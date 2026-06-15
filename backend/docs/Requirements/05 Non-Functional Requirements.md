# 05 Non-Functional Requirements

> Document type: Non-Functional Requirements (NFRs)
> Companion to: `01 Project Charter.md`, `02 Business Requirements Document.md`, `03 Product Requirements Document.md`, `04 Functional Requirements.md`
> Status: Draft v0.1 · Owner: Engineering + Product · Last updated: 2026-06-05
> This document specifies the quality attributes of the system:
> performance, scalability, reliability, security, usability, etc.
> Functional behavior is defined in `04 Functional Requirements.md`.

---

## 1. Document Control

| Field | Value |
|---|---|
| Project codename | CourseForge |
| Document version | 0.1 (Draft) |
| Author | Engineering + Product |
| Reviewers | Backend Lead, AI Lead, Frontend Lead, DevOps Lead, Security Lead |
| Approvers | Head of Engineering, Sponsor |
| Cadence | Reviewed at the end of each sprint |

---

## 2. Overview

Non-functional requirements (NFRs) describe **how well** the system must
behave. They constrain architecture, infrastructure, and operational
process. Each NFR is:

- **Measurable** — has a target and a measurement method.
- **Verifiable** — has a verification approach (test, observation, audit).
- **Scoped** — names the conditions under which the target applies.

### 2.1 Identifier format
- `NFR-<CAT>-<NNN>` where `<CAT>` is the category code.

### 2.2 Priority
- **M** = Must
- **S** = Should
- **C** = Could

### 2.3 Target conventions
- Latency targets are p50 / p95 / p99 unless stated otherwise.
- "Default" refers to the default configuration unless stated otherwise.
- "Tenant" refers to the isolation unit (single-tenant by default in v1).

---

## 3. Performance

### NFR-PERF-001 — Course generation end-to-end latency
- **Priority:** M
- **Statement:** A typical course (8 modules × 6 sections × 4 blocks) shall
  be generated end-to-end in ≤ **15 minutes** (p95) on the default
  provider at default settings.
- **Measurement:** Synthetic job run, wall-clock from request to
  `status=completed` in the JSON contract.
- **Verification:** Load-test harness; assert p95 ≤ 15 min.

### NFR-PERF-002 — Monitoring view update cadence
- **Priority:** M
- **Statement:** The generation monitoring view shall update at least every **2 seconds** during a running job.
- **Verification:** Browser timing trace; assert update interval ≤ 2 s.

### NFR-PERF-003 — API response time (non-generation)
- **Priority:** S
- **Statement:** Non-generation REST endpoints (read, list, export trigger)
  shall respond within **500 ms** p95 and **1 s** p99.
- **Verification:** k6 / Locust load test.

### NFR-PERF-004 — Curriculum tree render time
- **Priority:** S
- **Statement:** The curriculum tree for a course with up to 200 blocks
  shall render in **≤ 1 s** on a mid-range laptop.
- **Verification:** Frontend performance test with throttled CPU.

### NFR-PERF-005 — JSON contract size budget
- **Priority:** S
- **Statement:** The final JSON response for a typical course shall not
  exceed **5 MB** uncompressed.
- **Verification:** Synthetic job; assert size ≤ 5 MB.

### NFR-PERF-006 — Targeted regeneration latency
- **Priority:** S
- **Statement:** Block-level regeneration shall complete in ≤ **60 s** p95
  on the default provider; section-level in ≤ **3 min** p95; module-level
  in ≤ **8 min** p95.
- **Verification:** Targeted regen load test per scope.

### NFR-PERF-007 — Database read latency
- **Priority:** M
- **Statement:** Single-row lookups by id (course, module, section, block,
  job) shall complete in **≤ 20 ms** p95.
- **Verification:** DB benchmarking suite.

---

## 4. Scalability

### NFR-SCALE-001 — Concurrent jobs per user
- **Priority:** S
- **Statement:** The system shall support at least **3 concurrent
  generation jobs** per user without degradation of NFR-PERF-001.
- **Verification:** Synthetic load with 3 parallel jobs per user.

### NFR-SCALE-002 — Concurrent users
- **Priority:** S
- **Statement:** The system shall support at least **100 concurrent
  active users** (mix of generating, editing, reviewing) on the
  reference deployment.
- **Verification:** Load test (k6) with mixed workload.

### NFR-SCALE-003 — Course catalog size
- **Priority:** S
- **Statement:** The system shall support a single tenant with at least
  **10,000 courses** and **5 million blocks** without degradation of
  read performance (NFR-PERF-003).
- **Verification:** Synthetic catalog load; assert dashboard / read paths
  remain within budget.

### NFR-SCALE-004 — Provider throughput
- **Priority:** S
- **Statement:** The system shall fan out LLM calls in parallel up to a
  per-provider concurrency limit (configurable; default 8) and shall
  not exceed provider rate limits.
- **Verification:** Load test; assert no `429` errors from the provider.

### NFR-SCALE-005 — Horizontal scaling
- **Priority:** C
- **Statement:** The API tier and the worker tier shall scale
  horizontally with no shared local state.
- **Verification:** Add a second worker node; assert jobs distribute and
  p95 latency does not regress.

---

## 5. Availability & Reliability

### NFR-AVAIL-001 — Service availability target
- **Priority:** S
- **Statement:** The platform shall target **99.5% monthly availability**
  for the web UI and synchronous APIs in production.
- **Measurement:** Uptime monitoring (synthetic checks every 60 s).
- **Verification:** Production observability dashboard; 30-day rolling SLO.

### NFR-AVAIL-002 — Job durability
- **Priority:** M
- **Statement:** A running job that is interrupted (worker crash,
  deploy, infra failure) shall be **resumable** to a deterministic
  point: either restart from the last successful agent invocation or
  terminate with `termination_reason=infra_failure` and partial
  results preserved.
- **Verification:** Kill the worker mid-job; assert resume/restart
  behavior and that no data is lost.

### NFR-AVAIL-003 — Graceful degradation
- **Priority:** S
- **Statement:** When a non-critical agent fails (e.g.
  PrerequisiteValidator), the job shall continue with a structured
  warning issue rather than aborting.
- **Verification:** Inject agent failure; assert job completes with
  a warning issue.

### NFR-AVAIL-004 — No silent data loss
- **Priority:** M
- **Statement:** The system shall not silently lose a saved version,
  a feedback entry, or an uploaded document.
- **Verification:** Chaos test: kill worker between persistence calls;
  assert that committed state is consistent and the agent trace
  reflects the failure.

### NFR-AVAIL-005 — Provider failover
- **Priority:** C
- **Statement:** When a provider's circuit breaker is open, the system
  shall fail over to a configured backup provider (when available) and
  record the failover in the agent trace.
- **Verification:** Open breaker; assert failover or fast-fail with
  structured error.

### NFR-AVAIL-006 — Backups
- **Priority:** M
- **Statement:** Persistent stores (Postgres, Neo4j, object storage)
  shall be backed up at least daily with a retention of **30 days**
  and a recovery time objective (RTO) of **4 hours**.
- **Verification:** Restore drill from a backup into a clean
  environment.

---

## 6. Maintainability

### NFR-MAINT-001 — Architecture conformance
- **Priority:** M
- **Statement:** The codebase shall conform to the Hexagonal
  Architecture + DDD layout: domain code shall not import from
  infrastructure packages; provider SDKs shall not appear outside
  adapter modules.
- **Verification:** Static dependency check in CI (`importlinter` or
  equivalent) fails the build on violation.

### NFR-MAINT-002 — Test coverage
- **Priority:** M
- **Statement:** Domain and application layers shall have **≥ 90%**
  line coverage; infrastructure adapters shall have **≥ 70%**.
- **Verification:** `pytest --cov` in CI; coverage gate.

### NFR-MAINT-003 — Lint and typecheck
- **Priority:** M
- **Statement:** All Python code shall pass `ruff` and `mypy --strict`;
  all TypeScript code shall pass `eslint` and `tsc --strict`.
- **Verification:** CI gates.

### NFR-MAINT-004 — Prompt and rubric versioning
- **Priority:** M
- **Statement:** Every prompt and the rubric shall be versioned in the
  repository; the active version is referenced by the application's
  configuration; bumping the version is a single, reviewable change.
- **Verification:** Inspect the prompt registry; assert all versions
  are in git history with a changelog entry.

### NFR-MAINT-005 — Eval suite
- **Priority:** S
- **Statement:** The system shall ship with an evaluation suite
  (golden courses) runnable in CI; rubric changes that degrade
  scores beyond a threshold shall fail the build.
- **Verification:** CI run of the eval suite.

### NFR-MAINT-006 — Documentation
- **Priority:** S
- **Statement:** The repository shall contain architecture docs,
  ADRs, and per-context READMEs; the docs shall be kept current as
  part of "definition of done".
- **Verification:** Docs review in sprint review.

### NFR-MAINT-007 — Dependency updates
- **Priority:** S
- **Statement:** The project shall use automated dependency update
  tooling (Dependabot or equivalent); security updates shall be
  merged within **7 days** of release.
- **Verification:** Audit PR queue; assert age of security PRs.

---

## 7. Security & Privacy

### NFR-SEC-001 — Authentication
- **Priority:** S
- **Statement:** The system shall authenticate all users via a
  standard identity provider (OIDC or SAML); passwords shall never
  be stored by the application.
- **Verification:** Auth test suite; pen-test report.

### NFR-SEC-002 — Authorization
- **Priority:** S
- **Statement:** The system shall enforce role-based access control
  (`user`, `admin`) and per-tenant resource isolation. Authorization
  decisions shall be centralized and audit-logged.
- **Verification:** RBAC test suite; cross-tenant access attempts
  return `403`.

### NFR-SEC-003 — Data isolation
- **Priority:** M
- **Statement:** All persistent data (courses, documents, feedback,
  generations) shall be isolated per tenant; no cross-tenant data
  flow at the application, database, or storage level.
- **Verification:** Cross-tenant test suite; storage policy review.

### NFR-SEC-004 — Secrets management
- **Priority:** M
- **Statement:** API keys (LLM providers, DB, Neo4j) shall be stored
  in a secrets manager; they shall never be logged, returned in API
  responses, or persisted in the repository.
- **Verification:** Log scan; secret-scan in CI (`gitleaks` or
  equivalent).

### NFR-SEC-005 — Document upload safety
- **Priority:** S
- **Statement:** Uploaded documents shall be scanned for malware,
  size-limited per plan, and stored in tenant-isolated object
  storage with server-side encryption.
- **Verification:** Upload an EICAR test string; assert rejection.

### NFR-SEC-006 — Prompt injection mitigation
- **Priority:** S
- **Statement:** User-supplied context (text instructions, document
  contents) shall be treated as untrusted input. The system shall
  apply input sanitization, length caps, and structural validation
  before content is included in prompts. Suspected injection
  patterns shall be flagged as `issues` with
  `category=security` and shall not abort generation silently.
- **Verification:** Inject a known prompt-injection payload; assert
  the system either rejects it or surfaces a structured issue.

### NFR-SEC-007 — PII handling
- **Priority:** S
- **Statement:** The system shall not require PII to operate. Any
  PII present in user-provided content shall be flagged in the
  pre-generation review and shall be redactable by the user.
- **Verification:** Submit content with synthetic PII; assert it is
  flagged.

### NFR-SEC-008 — Transport security
- **Priority:** M
- **Statement:** All client-server and server-provider traffic shall
  use TLS ≥ 1.2; HSTS shall be enabled on the public domain.
- **Verification:** TLS scan; HSTS header check.

### NFR-SEC-009 — Audit log
- **Priority:** S
- **Statement:** Generation, edit, export, and configuration events
  shall be recorded in an append-only audit log with actor,
  timestamp, target, and outcome.
- **Verification:** Perform each event; assert the audit log
  contains the entry.

### NFR-SEC-010 — Data residency
- **Priority:** C
- **Statement:** Customers in regulated regions shall be able to
  pin their tenant's data (DB, object storage, backups) to a
  specific region.
- **Verification:** Provision a tenant in region A; assert all
  resources reside in region A.

---

## 8. Usability & Accessibility

### NFR-UX-001 — Time to first draft
- **Priority:** M
- **Statement:** A new user shall be able to produce a first reviewable
  course draft within **5 minutes** of account creation (excluding
  generation time).
- **Verification:** UX benchmark with 5 representative users.

### NFR-UX-002 — Learnability
- **Priority:** S
- **Statement:** A new user shall be able to (a) generate a course,
  (b) read the curriculum tree, (c) edit a block, and (d) export
  to Markdown, without external documentation, in their first
  session.
- **Verification:** UX benchmark.

### NFR-UX-003 — Error messages
- **Priority:** M
- **Statement:** All user-visible errors shall be human-readable,
  suggest a remediation, and link to relevant documentation where
  applicable. No raw stack traces, exception messages, or
  provider-specific error codes shall leak to the UI.
- **Verification:** Manual review of error catalog; snapshot tests
  in the frontend.

### NFR-UX-004 — Accessibility
- **Priority:** M
- **Statement:** The web UI shall meet **WCAG 2.1 AA**: keyboard
  navigability, sufficient color contrast, ARIA roles on dynamic
  components, screen-reader support, focus management, and
  captions/transcripts for any media.
- **Verification:** Automated scan (axe) + manual audit with a
  screen reader; release blocked on AA violations.

### NFR-UX-005 — Color independence
- **Priority:** M
- **Statement:** Quality indicators and severity badges shall use
  icons and text in addition to color.
- **Verification:** Visual review; axe checks.

### NFR-UX-006 — Localization-ready
- **Priority:** S
- **Statement:** All user-facing strings shall be externalized; the
  application shall render correctly for **left-to-right** languages
  in v1 and shall be structured to admit **right-to-left** languages
  in a future release.
- **Verification:** Pseudolocale build; manual review.

### NFR-UX-007 — Performance perception
- **Priority:** S
- **Statement:** Long-running operations shall expose progress
  (per-agent status, iteration scores, terminal reason) and shall
  be cancellable.
- **Verification:** UX benchmark.

---

## 9. Internationalization

### NFR-I18N-001 — Course language selection
- **Priority:** S
- **Statement:** The system shall allow a course to be generated in a
  user-selected language (default `en`).
- **Verification:** Generate the same course in two languages; assert
  the language differs in the output.

### NFR-I18N-002 — Locale-aware formatting
- **Priority:** S
- **Statement:** Dates, numbers, and durations in the UI shall be
  formatted per the user's locale.
- **Verification:** Pseudolocale build; manual review.

### NFR-I18N-003 — Externalized strings
- **Priority:** M
- **Statement:** No hard-coded user-facing strings shall appear in
  the frontend codebase.
- **Verification:** CI check for hard-coded strings.

---

## 10. Observability

### NFR-OBS-001 — Structured logging
- **Priority:** M
- **Statement:** All services shall emit structured logs
  (`structlog` JSON) with correlation ids, job ids, user ids (where
  safe), and agent context. Logs shall not contain secrets, raw
  prompts in production, or PII.
- **Verification:** Log schema validation; log scan in CI.

### NFR-OBS-002 — Metrics
- **Priority:** M
- **Statement:** The system shall emit metrics for: generation
  latency (per scope), token usage (per agent, per provider), rubric
  pass rate, iterations to pass, error rates, and SLO indicators
  (NFR-PERF-001, NFR-PERF-003, NFR-AVAIL-001).
- **Verification:** Metrics dashboard exists and is populated.

### NFR-OBS-003 — Tracing
- **Priority:** S
- **Statement:** The system shall propagate trace context across
  API, worker, agent, and provider boundaries, enabling end-to-end
  traces of a generation job.
- **Verification:** Open a trace for a job; assert all agent
  invocations appear as spans.

### NFR-OBS-004 — Agent trace persistence
- **Priority:** M
- **Statement:** The full agent trace for every generation shall be
  persisted with the course payload (per `BRD §11.3`) and shall be
  queryable by `job_id`.
- **Verification:** Run a job; query by `job_id`; assert full trace.

### NFR-OBS-005 — Alerting
- **Priority:** S
- **Statement:** SLO-violating conditions (latency, error rate,
  provider health) shall produce alerts with runbook links.
- **Verification:** Trigger a synthetic SLO breach; assert alert
  fires.

---

## 11. Testability

### NFR-TEST-001 — Test pyramid
- **Priority:** M
- **Statement:** The test suite shall consist of:
  - unit tests for the domain and application layers (fast, no I/O)
  - integration tests for adapters (testcontainers for Postgres,
    Neo4j, and a mocked provider)
  - end-to-end tests for the API and the JSON contract
  - an evaluation suite for the agent folder
- **Verification:** CI test report; coverage gates (NFR-MAINT-002).

### NFR-TEST-002 — Deterministic tests
- **Priority:** M
- **Statement:** All non-LLM-dependent tests shall be deterministic
  (no real time, no network, no provider calls). LLM-dependent tests
  shall be marked and may use recorded responses or a local stub.
- **Verification:** `pytest` runs without network access.

### NFR-TEST-003 — Contract tests
- **Priority:** M
- **Statement:** The JSON output contract shall be enforced by a
  schema test (consumer-driven contract test) in CI; breaking
  changes to the schema require a major version bump and an
  explicit PR label.
- **Verification:** CI gate; PR label policy.

### NFR-TEST-004 — Eval suite gate
- **Priority:** S
- **Statement:** The agent evaluation suite shall run in CI on every
  PR; a regression beyond the configured threshold shall fail the
  build.
- **Verification:** CI run; threshold check.

---

## 12. Compatibility

### NFR-COMPAT-001 — Browser support
- **Priority:** M
- **Statement:** The web UI shall support the latest two stable
  versions of **Chrome, Firefox, Safari, and Edge**.
- **Verification:** Cross-browser smoke test in CI.

### NFR-COMPAT-002 — JSON schema compatibility
- **Priority:** M
- **Statement:** Consumers of the JSON output contract shall be
  able to pin to a `schema_version` and shall not be required to
  accept newer major versions.
- **Verification:** Major-version bump test; consumer pinning
  scenario.

### NFR-COMPAT-003 — Provider SDK isolation
- **Priority:** M
- **Statement:** Upgrading a provider SDK shall not require changes
  to the domain or to other providers' adapters.
- **Verification:** Bump one SDK; assert no changes outside its
  adapter; CI green.

### NFR-COMPAT-004 — Forward compatibility
- **Priority:** S
- **Statement:** The frontend shall ignore unknown fields in the
  JSON contract and shall degrade gracefully when optional fields
  are missing.
- **Verification:** Send a payload with extra/missing optional
  fields; assert the UI renders.

---

## 13. Data Integrity

### NFR-INT-001 — Aggregates are consistent
- **Priority:** M
- **Statement:** A course payload returned by the API shall always
  be internally consistent: every section belongs to a module on
  the course, every block to a section, every reference resolves.
- **Verification:** Generate a course; assert the consistency
  invariant holds; assert mutation that would break the invariant
  is rejected.

### NFR-INT-002 — Idempotent writes
- **Priority:** M
- **Statement:** Idempotency keys (request ids) shall guarantee
  that retries do not create duplicate jobs or duplicate versions.
- **Verification:** Replay the same request; assert a single job
  exists.

### NFR-INT-003 — Optimistic concurrency
- **Priority:** M
- **Statement:** Concurrent updates to the same aggregate shall be
  detected via a `version` field; stale writes return a structured
  conflict error.
- **Verification:** Two concurrent updates; assert one succeeds and
  one returns `409`.

### NFR-INT-004 — Soft delete semantics
- **Priority:** S
- **Statement:** Deletion shall be soft: deleted entities remain
  queryable (with a `deleted_at` timestamp) for a configurable
  retention period (default 30 days) before hard deletion.
- **Verification:** Delete a course; assert it is removed from
  listings but restorable within the retention window.

---

## 14. Compliance

### NFR-COMP-001 — License compliance
- **Priority:** S
- **Statement:** All third-party dependencies shall be permissively
  licensed (MIT, Apache-2.0, BSD) unless an exception is approved
  and recorded.
- **Verification:** `pip-licenses` / `license-checker` report in
  CI; PR label for exceptions.

### NFR-COMP-002 — SOC 2 readiness
- **Priority:** C
- **Statement:** The platform's controls (access, logging, change
  management) shall be designed to be SOC 2-auditable.
- **Verification:** Control matrix review.

### NFR-COMP-003 — Data subject rights
- **Priority:** C
- **Statement:** Users shall be able to export and delete their
  data on request; deletion is irreversible and propagates to
  backups within the documented window.
- **Verification:** Submit a deletion request; assert the data is
  removed from primary stores and from backups on schedule.

---

## 15. Cost Efficiency

### NFR-COST-001 — Per-course token budget
- **Priority:** M
- **Statement:** The system shall enforce a per-course token budget
  (default 500,000 input + 200,000 output tokens, configurable).
  Reaching the budget terminates the refinement loop with
  `termination_reason=budget_exhausted`.
- **Verification:** Configure a tiny budget; assert the loop
  terminates with the expected reason.

### NFR-COST-002 — Caching of intermediate results
- **Priority:** S
- **Statement:** The system shall cache deterministic intermediate
  results (e.g. plan, skeleton, summary embeddings) per
  `(context_hash, prompt_version, model_version)` to avoid
  redundant LLM calls.
- **Verification:** Re-run with identical inputs; assert cache hits
  in the agent trace.

### NFR-COST-003 — Tiered model selection
- **Priority:** S
- **Statement:** The default configuration shall use lower-cost
  models for high-volume agents (e.g. PersonaAdapter) and
  higher-cost models for high-leverage agents (e.g. Evaluator).
- **Verification:** Inspect the default per-agent model table.

### NFR-COST-004 — Cost observability
- **Priority:** S
- **Statement:** The system shall expose per-job, per-agent, and
  per-user cost (input + output tokens × configured price) on the
  job detail page.
- **Verification:** Run a job; assert cost figures are present and
  match a manual calculation.

---

## 16. Portability & Deployment

### NFR-PORT-001 — Local development
- **Priority:** M
- **Statement:** The system shall be runnable locally with
  `docker-compose` (Postgres, Neo4j, API, worker, and a stub
  provider) with a single command; cold start to a healthy API
  shall be **≤ 5 minutes** on a developer laptop.
- **Verification:** Onboarding benchmark; CI smoke test.

### NFR-PORT-002 — Container images
- **Priority:** M
- **Statement:** All services shall be shipped as container images
  with pinned base images, multi-stage builds, and non-root users.
- **Verification:** Image scan; build pipeline.

### NFR-PORT-003 — Configuration via environment
- **Priority:** M
- **Statement:** All configuration shall be environment-driven
  (12-factor); no configuration shall be hard-coded in the
  application.
- **Verification:** Config audit; documented `.env.example`.

### NFR-PORT-004 — Migrations
- **Priority:** M
- **Statement:** Database and Neo4j schema changes shall be applied
  via versioned migrations; forward-only by default; down-migrations
  are not required for production safety.
- **Verification:** Migration dry-run; CI migration step.

---

## 17. Recoverability

### NFR-REC-001 — Job resume
- **Priority:** S
- **Statement:** A job interrupted by an infra failure shall be
  resumable: on restart, the orchestrator continues from the last
  successful agent invocation.
- **Verification:** Kill the worker mid-job; restart; assert the
  job completes and the trace is contiguous.

### NFR-REC-002 — Bad-version recovery
- **Priority:** S
- **Statement:** If a version of a course payload is later found
  to be corrupted or invalid, the user shall be able to roll back
  to any prior valid version.
- **Verification:** Corrupt a block version; assert rollback
  succeeds and the course becomes valid again.

### NFR-REC-003 — Provider outage recovery
- **Priority:** C
- **Statement:** When a provider is unavailable, the system shall
  return structured `issues` with a `code` identifying the
  provider outage, and shall not silently hang.
- **Verification:** Take the provider offline; assert bounded
  failure.

---

## 18. Traceability Matrix (NFR → source)

| NFR | Source |
|---|---|
| NFR-PERF-001 | Charter §17 (M1), PRD §7.1 |
| NFR-PERF-002 | PRD §7.1 |
| NFR-PERF-003 | PRD §7.1 |
| NFR-PERF-004 | PRD §7.1 |
| NFR-PERF-005 | BRD §11.7 |
| NFR-PERF-006 | BRD §10.2, PRD §6 (E5) |
| NFR-PERF-007 | Implicit |
| NFR-SCALE-001 | PRD §7.1 |
| NFR-SCALE-002 | PRD §7.1 |
| NFR-SCALE-003 | Charter §17 (M6) |
| NFR-SCALE-004 | BRD §10.2 |
| NFR-SCALE-005 | Charter §17 (M6) |
| NFR-AVAIL-001 | Charter §17 (M6) |
| NFR-AVAIL-002 | Charter §17 (M0) |
| NFR-AVAIL-003 | BRD §10.5 |
| NFR-AVAIL-004 | Charter §17 (M0) |
| NFR-AVAIL-005 | FR-PR-005 |
| NFR-AVAIL-006 | Charter §17 (M0) |
| NFR-MAINT-001 | Charter §10, BRD §10 |
| NFR-MAINT-002 | Charter §11 |
| NFR-MAINT-003 | Charter §11 |
| NFR-MAINT-004 | BRD §15, BC-006 |
| NFR-MAINT-005 | BRD §15 |
| NFR-MAINT-006 | Charter §11 |
| NFR-MAINT-007 | Charter §11 |
| NFR-SEC-001 | Implicit |
| NFR-SEC-002 | Charter §15 |
| NFR-SEC-003 | BC-002 |
| NFR-SEC-004 | Charter §15 |
| NFR-SEC-005 | PRD §7.3 |
| NFR-SEC-006 | BRD §10.5 |
| NFR-SEC-007 | Charter §15 |
| NFR-SEC-008 | Charter §15 |
| NFR-SEC-009 | FR-UM-004 |
| NFR-SEC-010 | Charter §15 |
| NFR-UX-001 | PRD §7.1 |
| NFR-UX-002 | PRD §7.1 |
| NFR-UX-003 | BRD §10.5, FR-JC-005 |
| NFR-UX-004 | PRD §7.4 |
| NFR-UX-005 | PRD §7.4 |
| NFR-UX-006 | PRD §7.4 |
| NFR-UX-007 | PRD §7.1 |
| NFR-I18N-001 | PRD §7.5 |
| NFR-I18N-002 | PRD §7.5 |
| NFR-I18N-003 | PRD §7.5 |
| NFR-OBS-001 | Charter §10 |
| NFR-OBS-002 | Charter §11 |
| NFR-OBS-003 | Charter §10 |
| NFR-OBS-004 | BRD §11.3, BC-007 |
| NFR-OBS-005 | Charter §11 |
| NFR-TEST-001 | Charter §11 |
| NFR-TEST-002 | Charter §11 |
| NFR-TEST-003 | BRD §11.7, BC-003 |
| NFR-TEST-004 | BRD §15 |
| NFR-COMPAT-001 | PRD §7.4 |
| NFR-COMPAT-002 | BRD §11.7 |
| NFR-COMPAT-003 | BRD BC-002 |
| NFR-COMPAT-004 | BRD §11.7 |
| NFR-INT-001 | FR-CS-001 |
| NFR-INT-002 | FR-CG-001 |
| NFR-INT-003 | §5.2 (Concurrency) |
| NFR-INT-004 | §5.3 (Data lifecycle) |
| NFR-COMP-001 | Charter §11 |
| NFR-COMP-002 | Charter §17 (post-GA) |
| NFR-COMP-003 | Charter §15 |
| NFR-COST-001 | BRD §10.3, FR-AG-012 |
| NFR-COST-002 | BRD §10.5 |
| NFR-COST-003 | BRD §10.1 (per-agent model) |
| NFR-COST-004 | BRD §14 |
| NFR-PORT-001 | Charter §11 |
| NFR-PORT-002 | Charter §11 |
| NFR-PORT-003 | Charter §11 |
| NFR-PORT-004 | Charter §11 |
| NFR-REC-001 | Charter §17 (M0) |
| NFR-REC-002 | FR-VC-004 |
| NFR-REC-003 | FR-PR-005 |

---

## 19. Sign-off

| Role | Name | Signature | Date |
|---|---|---|---|
| Head of Engineering | | | |
| AI Lead | | | |
| DevOps Lead | | | |
| Security Lead | | | |
| Sponsor | | | |

---

## 20. Cross-References

- **Project Charter** — `01 Project Charter.md`
- **Business Requirements** — `02 Business Requirements Document.md`
- **Product Requirements** — `03 Product Requirements Document.md`
- **Functional Requirements** — `04 Functional Requirements.md`
- **User Stories** — `06 User Stories.md`
- **JSON Output Contract** — `02 Business Requirements Document.md` §11
- **ADRs** — `docs/adr/`
