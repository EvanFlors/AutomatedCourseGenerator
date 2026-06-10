# 12 Coding Standards

> Document type: Engineering — Coding Standards
> Companion to: `08 C4 Architecture.md`, `09 Architecture Decision Records.md`, `11 Testing Strategy.md`
> Status: Draft v0.1 · Owner: Engineering · Last updated: 2026-06-05
> This document defines how code is written in CourseForge. It is enforced
> by tooling (`ruff`, `mypy`, `eslint`, `tsc`, `importlinter`) wherever
> possible; review fills the gaps.

---

## 1. Document Control

| Field | Value |
|---|---|
| Project codename | CourseForge |
| Document version | 0.1 (Draft) |
| Author | Engineering |
| Reviewers | Backend Lead, AI Lead, Frontend Lead, DevOps Lead |
| Approvers | Head of Engineering |
| Cadence | Reviewed at the end of each sprint; PRs that change rules must update this document. |

---

## 2. Purpose

Establish a single, enforceable set of rules so that:

- Code is **readable** by the team, not just the author.
- Code is **safe to change** — layers, contracts, and tests protect us.
- Code is **portable** across providers, storage backends, and UI
  components without rewrites.
- Code is **testable** without exotic setups.

Rules are enforced by tooling first, by review second, by documentation
last.

---

## 3. General Principles

| # | Principle |
|---|---|
| GP-1 | **Boring is better.** Prefer clear, conventional code over clever code. |
| GP-2 | **Names are documentation.** Choose names that read like the domain. |
| GP-3 | **Small surfaces.** Functions, classes, and PRs should be small. |
| GP-4 | **Explicit over implicit.** No magic; no hidden globals. |
| GP-5 | **Fail loud, fail structured.** Errors must be typed, not strings. |
| GP-6 | **No side effects in domain code.** Domain is pure; effects live in adapters. |
| GP-7 | **No comments unless asked** (per repo conventions). Self-documenting code is the goal. |
| GP-8 | **Tooling over convention.** If `ruff` can enforce a rule, never argue about it in review. |

---

## 4. Repository Layout

```
course-automation/
├── docs/                          # Architecture, ADRs (this folder's siblings)
├── Documentation/                 # Business + product + engineering docs
├── src/
│   ├── domain/                    # Pure business logic (no infra imports)
│   ├── application/               # Use cases
│   ├── infrastructure/            # Adapters
│   ├── interfaces/                # Delivery (API, WS, CLI)
│   └── bootstrap/                 # Wiring
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── contract/
│   ├── e2e/
│   ├── eval/
│   ├── perf/
│   ├── security/
│   ├── a11y/
│   └── fixtures/
├── web/                           # Frontend (Vite + React + TS)
│   ├── src/
│   │   ├── app/                   # App shell, routing
│   │   ├── features/              # Feature folders
│   │   ├── components/            # Shared UI components
│   │   ├── lib/                   # Utilities, hooks, types
│   │   └── contracts/             # Generated JSON-schema types
│   └── tests/
├── scripts/                       # Dev / CI / ops scripts
├── docker/                        # Dockerfiles, compose
├── .github/                       # CI workflows
├── pyproject.toml
├── package.json
└── README.md
```

Rule: every folder has a single, clear purpose. If a folder's purpose
is unclear, refactor before adding code.

---

## 5. Python Standards

### 5.1 Versions and tools
- Python **3.11+** (matches `pyproject.toml`).
- Type-checked with `mypy --strict`.
- Linted with `ruff` (rules `E, F, I, B, UP, N, W`).
- Formatted with `ruff format` (Black-compatible).
- Tested with `pytest`, `pytest-asyncio` (asyncio_mode=`auto`).

### 5.2 Style
- PEP 8 with `line-length = 100`.
- Imports sorted by `ruff` (`I`).
- `from __future__ import annotations` is unnecessary on 3.11+; do not
  add it.
- One statement per line. No semicolons.

### 5.3 Type hints
- **All** public functions and methods are annotated.
- `mypy --strict` is the gate; no `# type: ignore` without a
  justification comment.
- Prefer `from collections.abc import Iterable, Mapping` over `from
  typing import ...` for collection types.
- Use `TypeAlias` for non-trivial aliases.
- `Optional[X]` is written as `X | None`.
- Use `NewType` for IDs that must not be confused (`CourseId`,
  `BlockId`, `JobId`).
- Use `dataclass(frozen=True, slots=True)` for value objects.
- Use `Pydantic BaseModel` for DTOs and validated inputs (not for
  domain entities — those are dataclasses).

### 5.4 Async / await
- All I/O is `async`. There is no `sync` I/O in the request path.
- The domain is **synchronous** (pure). Effects are wrapped at the
  application/infrastructure boundary.
- Use `asyncio.TaskGroup` for concurrent fan-out (e.g. parallel agent
  calls when independent).
- `await` is mandatory; never call coroutines without it.
- No `asyncio.gather` of unbounded lists; bound concurrency with
  `asyncio.Semaphore`.

### 5.5 Error handling
- Define a domain error hierarchy in `domain/shared/errors.py`:
  `DomainError` (base), `ValidationError`, `NotFoundError`,
  `ConflictError`, `PolicyError`, `InfrastructureError`.
- Adapters translate external errors into domain errors at the port
  boundary. No provider-specific exception type leaks past the
  adapter.
- Never `except Exception:`. Catch the specific exception you handle.
- Never swallow exceptions silently. Log with context or re-raise.
- Use the `Result` type for recoverable failures where the caller
  should pattern-match; raise for unexpected/programmer errors.

### 5.6 Logging
- All services use `structlog` (configured per `05` NFR-OBS-001).
- Logs are **structured JSON** in non-dev environments.
- Mandatory context fields (via contextvars): `request_id`, `job_id`,
  `tenant_id`, `user_id` (where safe).
- Log levels: `debug` for development, `info` for lifecycle events,
  `warning` for recoverable issues, `error` for failures, `critical`
  for take-a-page outages.
- Never log secrets, PII, or full prompts in production
  (NFR-SEC-004, NFR-SEC-007).

### 5.7 Pydantic v2
- Pydantic is used at the **edges** (DTOs, configuration, validated
  inputs) and **not** in the domain.
- Domain entities are dataclasses; Pydantic models live in
  `interfaces/api/dto/` and `bootstrap/settings.py`.
- Use `model_config = ConfigDict(frozen=True, extra="forbid")` on
  DTOs by default.
- Validate at the boundary; do not re-validate inside the domain.

### 5.8 SQLAlchemy 2.0 (async)
- Use the **async** API throughout.
- Use the **declarative + mapped_column** style.
- Use `select()` (not legacy `Query`).
- Always pass `session` as an argument; no module-level sessions.
- Repositories own the session lifecycle; use cases call a single
  repository method per transaction.
- Use Alembic for all schema changes; one migration per logical
  change; never edit a committed migration.

### 5.9 Hexagonal architecture enforcement

Layer rules (enforced by `importlinter`, NFR-MAINT-001):

```
domain          →  (nothing outside stdlib + pydantic + sqlalchemy core types)
application     →  domain
infrastructure  →  domain, application
interfaces      →  domain, application
bootstrap       →  domain, application, infrastructure, interfaces
```

Forbidden imports:

- `domain` MUST NOT import from `infrastructure`, `interfaces`,
  `bootstrap`, or any provider SDK.
- `application` MUST NOT import from `infrastructure`, `interfaces`,
  `bootstrap`, or any provider SDK.
- `infrastructure` MUST NOT be imported by `domain` or `application`.
- Provider SDKs (`openai`, `anthropic`, `google.*`) MAY be imported
  only by `infrastructure/llm/<provider>.py` and `infrastructure/agents/`
  when explicitly documented as the only consumer.

CI check:

```ini
# importlinter.ini
[importlinter:contract:domain-purity]
type = layers
layers =
    domain
    application | infrastructure | interfaces | bootstrap
```

### 5.10 Naming conventions
- Modules: `snake_case.py`. One concept per module.
- Classes: `PascalCase`. Dataclasses for entities, BaseModel for DTOs.
- Functions / methods: `snake_case`. Verbs for actions, nouns for
  queries.
- Constants: `UPPER_SNAKE_CASE`. Module-level only.
- IDs: `NewType` aliases ending in `Id` (`CourseId`, `BlockId`).
- Ports: noun ending in `Port` or `Gateway` (`CourseRepository`,
  `LLMProvider`).
- Adapters: `<Technology><Port>` (`PostgresCourseRepository`,
  `OpenAIAdapter`).
- Agents: `<Role>Agent` (`Orchestrator`, `CurriculumPlanner`).
- Domain events: past tense (`CourseCreated`, `BlockRegenerated`).
- Tests: `test_<unit>_<behavior>_<expected>` (see Testing Strategy).

### 5.11 Docstrings
- Public modules and classes get a one-line docstring stating purpose.
- Docstrings are **not** required on every function (per repo
  convention). When present, they explain **why**, not **what**.
- No inline comments unless asked (per repo convention).
- ADRs and `docs/` carry the "why"; code carries the "what".

---

## 6. TypeScript / React Standards

### 6.1 Versions and tools
- Node.js **20 LTS** or **22 LTS**.
- TypeScript **5.x** with `strict: true` (and
  `noUncheckedIndexedAccess`, `exactOptionalPropertyTypes`).
- Linted with `eslint` (typescript-eslint, react, react-hooks,
  a11y, security).
- Formatted with `prettier`.
- Tested with `vitest` (unit) and `playwright` (e2e + a11y).

### 6.2 Style
- 2-space indentation; `;` required.
- Single quotes for strings; backticks for templates.
- Prefer named exports; no default exports except for React components
  (lazy loading).
- No `any`. Use `unknown` and narrow.
- Prefer `interface` for object types, `type` for unions/aliases.

### 6.3 React patterns
- Function components only. No class components.
- Hooks rules enforced by `eslint-plugin-react-hooks`.
- Effects are explicit; do not hide side effects in custom hooks
  without clear naming and tests.
- Data fetching: a single, typed client wrapping `fetch` (or
  `axios`) — no ad-hoc calls in components.
- State: prefer server state (React Query / SWR) for remote data;
  local state for UI state only. No global mutable stores beyond
  what is justified.
- Components are **small and focused**; co-locate styles, tests, and
  stories.

### 6.4 Folder layout (frontend)
```
web/src/
├── app/                # App shell, router, providers
├── features/
│   ├── generation/
│   ├── review/
│   ├── editing/
│   ├── feedback/
│   ├── versioning/
│   ├── export/
│   ├── dashboard/
│   └── admin/
├── components/         # Shared, presentational
├── lib/
│   ├── api/            # Typed client
│   ├── hooks/
│   ├── types/          # Generated from JSON schema
│   └── utils/
├── contracts/          # Generated JSON-schema types and validators
└── styles/
```

Rule: `features/<x>/` owns everything specific to that feature
(components, hooks, types, tests). `components/` and `lib/` are
shared and must not import from `features/`.

### 6.5 Accessibility (NFR-UX-004)
- All interactive components are keyboard-navigable.
- Color is never the only signal (NFR-UX-005).
- ARIA roles on dynamic widgets; live regions for progress.
- Form fields have associated labels.
- `prefers-reduced-motion` respected for animations.
- `axe-core` runs on every PR for key flows.

### 6.6 Naming conventions (TS)
- Components: `PascalCase.tsx`. Default export.
- Hooks: `useXxx.ts`. Named export.
- Types: `PascalCase`. Interfaces prefixed with `I` only when needed
  for disambiguation (avoid by default).
- Constants: `UPPER_SNAKE_CASE`.
- Files match the primary export (`CourseCard.tsx` exports
  `CourseCard`).

---

## 7. Git Workflow

### 7.1 Branches
- `main` — always green, always releasable.
- `feat/<short-name>` — feature work.
- `fix/<short-name>` — bug fixes.
- `chore/<short-name>` — non-functional changes.
- `docs/<short-name>` — documentation only.
- `release/<version>` — release prep.

### 7.2 Commits
- Conventional Commits (`feat:`, `fix:`, `chore:`, `docs:`, `refactor:`,
  `test:`, `perf:`).
- Subject line ≤ 72 chars; imperative mood.
- Body explains **why**; reference the FR/US it implements
  (`Refs FR-ED-001, US-4.1.1`).
- One logical change per commit.

### 7.3 Pull Requests
- Title is a complete sentence describing the change.
- Description includes: **what**, **why**, **how to verify**,
  **risk**, **links to FR / US / ADR**.
- Small PRs (< 400 lines of diff, excluding generated code) are
  strongly preferred.
- At least **one** approval from a code owner of the affected module.
- CI must be green before merge; "I'll fix it after merge" is not
  acceptable.
- Squash-merge by default; commit message becomes the PR title +
  body.

### 7.4 Code owners
- `CODEOWNERS` file at repo root maps directories to required
  reviewers.
- Changes touching the agent folder require AI Lead review.
- Changes touching the JSON output contract require AI Lead + Frontend
  Lead review.
- Changes touching security or auth require Security review.

---

## 8. Documentation Requirements

Code changes that **must** update docs in the same PR:

| Change | Doc to update |
|---|---|
| New or changed FR | `04 Functional Requirements.md` |
| New or changed NFR | `05 Non-Functional Requirements.md` |
| New or changed story | `06 User Stories.md` |
| New or changed component / context | `08 C4 Architecture.md` |
| New or changed decision | `09 Architecture Decision Records.md` |
| New or changed sequence | `10 Sequence Diagrams.md` |
| New or changed test layer / rule | `11 Testing Strategy.md` |
| New or changed coding rule | `12 Coding Standards.md` (this doc) |
| Public contract change | `02 Business Requirements Document.md` §11 |

"Definition of done" includes a docs check.

---

## 9. Dependency Management

- Pin all versions; lockfiles are committed.
- New dependencies require a short justification in the PR.
- Prefer libraries already in the stack; adding a new one is a
  discussion, not a default.
- `pip-audit` and `npm audit` run on every PR; critical/high CVEs
  block merge.
- `Dependabot` (or equivalent) opens weekly PRs; security PRs are
  merged within 7 days of release (NFR-MAINT-007).
- License compliance (NFR-COMP-001): only MIT, Apache-2.0, BSD
  unless an exception is recorded in the PR.

---

## 10. Security Standards

- No secrets in code; secrets manager only (NFR-SEC-004).
- User input is untrusted; validate at the boundary; never trust
  client-side values for authorization.
- All HTTP responses use TLS ≥ 1.2; HSTS enabled (NFR-SEC-008).
- Tenant isolation is enforced at the data access layer; cross-tenant
  access is a P0 bug.
- Prompt-injection payloads are tested explicitly (NFR-SEC-006).
- No raw stack traces in user-facing errors (FR-JC-005, NFR-UX-003).
- All auth events are written to the audit log (NFR-SEC-009).

---

## 11. Observability Standards

- Every service emits structured logs (NFR-OBS-001).
- Every request gets a `request_id`; jobs get a `job_id`; agents
  record `agent`, `phase`, `iteration` in trace context.
- Metrics: RED (rate, errors, duration) for HTTP, plus domain metrics
  (NFR-OBS-002).
- Trace context propagates API → worker → LLM (NFR-OBS-003).
- Agent trace is persisted with the course payload (NFR-OBS-004).

---

## 12. Performance Standards

- Hot paths are profiled before optimization; "premature optimization
  is the root of all evil".
- DB queries are reviewed for N+1 patterns; the default is eager
  loading where the join is cheap.
- Indexes are added with the data; missing-index regressions fail in
  CI when they cross the threshold.
- Frontend code is split per route; no single bundle > 500 KB gzipped
  for the initial route.
- Performance budgets (NFR-PERF-*) are part of the release gate.

---

## 13. Banned Patterns (Python)

- `from foo import *`
- `eval`, `exec`
- Mutable default arguments
- `print` (use `structlog.get_logger(__name__).info(...)`)
- Bare `except:` or `except Exception:` without re-raise
- `assert` for runtime checks (stripped with `-O`)
- `subprocess.run(shell=True)`
- Hard-coded secrets or environment-specific paths
- `os.system` / `os.popen`
- Provider SDK imports outside `infrastructure/llm/` and
  `infrastructure/agents/` (where explicitly allowed)

## 14. Banned Patterns (TypeScript)

- `any`
- `// @ts-ignore` (use `// @ts-expect-error: <reason>`)
- `eval`, `new Function(...)`
- `dangerouslySetInnerHTML` without a documented sanitizer and review
- `localStorage` for tokens
- Hard-coded secrets or environment-specific URLs
- Direct DOM manipulation outside React
- Mixing default and named exports arbitrarily
- `console.log` in production (use a logger; debug is fine in dev)

---

## 15. Pull Request Checklist (template)

A PR is "ready for review" only when:

- [ ] Title and description are complete.
- [ ] Linked FR / US / ADR are referenced.
- [ ] Tests are added/updated; coverage gate is green.
- [ ] Lint, types, and contract tests are green.
- [ ] Docs are updated (if applicable).
- [ ] No secrets, no PII, no `print`/`console.log`, no commented-out code.
- [ ] No new dependency without justification.
- [ ] Migration is included (if schema change).
- [ ] A11y, observability, and security implications are considered.
- [ ] At least one local run-through has been performed by the author.

---

## 16. Cross-References

- **Architecture** — `08 C4 Architecture.md`
- **ADRs** — `09 Architecture Decision Records.md`
- **Testing Strategy** — `11 Testing Strategy.md`
- **Functional Requirements** — `04 Functional Requirements.md`
- **Non-Functional Requirements** — `05 Non-Functional Requirements.md`
- **JSON Output Contract** — `02 Business Requirements Document.md` §11
- **Test Guide (operational)** — `PYTEST_GUIDE.md` (existing)
