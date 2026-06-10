# 10 Sequence Diagrams

> Document type: Architecture — Sequence Diagrams
> Companion to: `07 System Context Diagram.md`, `08 C4 Architecture.md`, `09 Architecture Decision Records.md`
> Status: Draft v0.1 · Owner: Architecture · Last updated: 2026-06-05
> Each diagram uses Mermaid `sequenceDiagram`. Diagrams are illustrative —
> implement with optimistic concurrency, retries, and structured errors.

---

## 1. Document Control

| Field | Value |
|---|---|
| Project codename | CourseForge |
| Document version | 0.1 (Draft) |
| Author | Architecture |
| Reviewers | Backend Lead, AI Lead, Frontend Lead, QA |
| Approvers | Head of Engineering |
| Cadence | Reviewed at the end of each sprint |

---

## 2. Index

| # | Use case | Source FR |
|---|---|---|
| UC1 | Generate a course end-to-end | FR-AG-001, FR-AG-002, FR-AG-010, FR-CG-001 |
| UC2 | Targeted block regeneration | FR-RG-001, FR-RG-004, FR-RG-006 |
| UC3 | Manual edit (no auto-eval) | FR-ED-001, FR-ED-003, FR-VC-006 |
| UC4 | Block-level feedback | FR-FB-001, FR-RG-001 |
| UC5 | Global feedback | FR-FB-004, FR-VC-004 |
| UC6 | Curriculum regeneration | FR-FB-003, FR-AG-003 |
| UC7 | Export to Markdown | FR-EX-001, FR-EX-004 |
| UC8 | Job cancellation | FR-AG-010, FR-NE-001 |
| UC9 | Document upload and ingestion | FR-CX-002, NFR-SEC-005 |
| UC10 | Provider failover | FR-PR-005, ADR-0012 |

---

## 3. UC1 — Generate a course end-to-end

```mermaid
sequenceDiagram
    autonumber
    actor User
    participant Web as Web (React)
    participant API as API (FastAPI)
    participant Q as Queue (Redis)
    participant W as Worker
    participant Orch as Orchestrator
    participant CS as ContextSynthesizer
    participant CP as CurriculumPlanner
    participant SA as SectionAuthor
    participant PA as PersonaAdapter
    participant CC as ConsistencyChecker
    participant PV as PrerequisiteValidator
    participant EV as Evaluator
    participant LLM as LLMProvider
    participant PG as Postgres
    participant NEO as Neo4j

    User->>Web: Click "Generate"
    Web->>API: POST /v1/courses (GenerationRequest)
    API->>API: Validate (FR-CG-003), build GenerationJob
    API->>Q: Enqueue job
    API-->>Web: 202 { job_id } → redirect to monitoring

    Q->>W: Deliver job
    W->>Orch: Run(job)
    Orch->>CS: Synthesize(inputs)
    CS->>LLM: Summarize documents / references
    LLM-->>CS: Summaries
    CS-->>Orch: GenerationContext

    Orch->>CP: Plan(context)
    CP->>LLM: Generate skeleton
    LLM-->>CP: CourseSkeleton
    CP-->>Orch: CourseSkeleton

    loop For each section
        Orch->>SA: Author(section_spec)
        SA->>LLM: Generate typed blocks
        LLM-->>SA: SectionDraft
        SA-->>Orch: SectionDraft
        Orch->>PA: Adapt(section_draft, persona)
        PA->>LLM: Adapt to audience
        LLM-->>PA: AdaptedSection
        PA-->>Orch: AdaptedSection
    end

    Orch->>CC: Check(course)
    CC->>LLM: Detect inconsistencies
    LLM-->>CC: ConsistencyReport
    Orch->>PV: Validate(course)
    PV->>LLM: Check progression
    LLM-->>PV: ProgressionReport
    Orch->>EV: Evaluate(course)
    EV->>LLM: Score against rubric
    LLM-->>EV: EvaluationReport
    EV-->>Orch: evaluation.passed?

    alt passed
        Orch->>PG: Persist course + versions + trace
        Orch->>NEO: Persist concept graph
        Orch-->>W: COMPLETED
    else not passed, iterations < cap, budget remains
        Orch->>W: continue refine loop (see UC2 for refine iteration shape)
    else max_iterations or budget_exhausted
        Orch->>PG: Persist partial + issues
        Orch-->>W: PARTIAL
    end

    W-->>Q: Ack
    W-->>API: Final result (or via /v1/jobs/{id})
    API-->>Web: JSON contract (BRD §11)
    Web-->>User: Render course + iteration chart
```

---

## 4. UC2 — Targeted block regeneration

```mermaid
sequenceDiagram
    autonumber
    actor User
    participant Web as Web (React)
    participant API as API
    participant Q as Queue
    participant W as Worker
    participant Orch as Orchestrator
    participant SA as SectionAuthor
    participant EV as Evaluator
    participant RF as Refiner
    participant LLM as LLMProvider
    participant PG as Postgres

    User->>Web: Click "Regenerate" on block B
    Web->>API: POST /v1/blocks/{B}/regenerate
    API->>API: Validate scope=block, create job
    API->>Q: Enqueue targeted regen
    API-->>Web: 202 { job_id }

    Q->>W: Deliver job
    W->>Orch: RunRegen(block_id=B)
    Orch->>PG: Load current block version + section context
    PG-->>Orch: Block + context

    Orch->>SA: Author(section_spec) [scoped to block]
    SA->>LLM: Generate new block
    LLM-->>SA: New block draft
    SA-->>Orch: New draft

    loop Evaluate–Refine (scoped to block)
        Orch->>EV: Evaluate(block)
        EV->>LLM: Score
        LLM-->>EV: EvaluationReport
        alt passed
            Orch->>PG: Persist new version (FR-VC-006 immutability)
            Orch-->>W: COMPLETED
        else not passed, iterations < block_cap
            Orch->>RF: Refine(block, issues)
            RF->>LLM: Apply issues
            LLM-->>RF: Refined block
        else
            Orch->>PG: Persist best-so-far with issues
            Orch-->>W: PARTIAL
        end
    end

    W-->>API: Result
    API-->>Web: New version + side-by-side payload
    Web-->>User: Show comparison (old vs new with scores)
    User->>Web: Accept / Discard
    Web->>API: POST /v1/blocks/{B}/versions/{v}/accept
    API->>PG: Update current pointer, preserve old in history
```

---

## 5. UC3 — Manual edit (no auto-eval)

```mermaid
sequenceDiagram
    autonumber
    actor User
    participant Web as Web (React)
    participant API as API
    participant PG as Postgres
    participant EV as Evaluator

    User->>Web: Edit a Concept block, click Save
    Web->>API: PATCH /v1/blocks/{B} (new content, version=expected)
    API->>PG: SELECT current version
    alt version mismatch
        API-->>Web: 409 Conflict (FR-INT-003)
    else ok
        API->>PG: INSERT new version (immutable, FR-VC-006)
        API->>PG: UPDATE current pointer to new version
        API-->>Web: 200 { new_version_id }
    end
    Note over API,EV: The Evaluator is NOT invoked on save (FR-ED-003, ADR-0010)
    Web-->>User: "Saved" + new version id

    User->>Web: Click "Re-evaluate block"
    Web->>API: POST /v1/blocks/{B}/evaluate
    API->>EV: Evaluate(block, rubric_version)
    EV-->>API: EvaluationReport
    API-->>Web: Scores + issues
    Web-->>User: Render quality panel for the block
```

---

## 6. UC4 — Block-level feedback

```mermaid
sequenceDiagram
    autonumber
    actor User
    participant Web as Web (React)
    participant API as API
    participant PG as Postgres
    participant W as Worker
    participant Orch as Orchestrator
    participant RF as Refiner
    participant LLM as LLMProvider

    User->>Web: Write feedback on block B, click "Regenerate"
    Web->>API: POST /v1/blocks/{B}/regenerate { feedback }
    API->>PG: Persist feedback entry (FR-FB-005)
    API->>W: Enqueue targeted regen with feedback payload
    API-->>Web: 202 { job_id }

    W->>Orch: RunRegen(block_id=B, feedback=...)
    Orch->>PG: Load current block + feedback history
    Orch->>RF: Refine(block, issues, feedback)
    RF->>LLM: Apply feedback + issues
    LLM-->>RF: Refined block
    Orch->>PG: Persist new version + mark feedback consumed
    Orch-->>W: COMPLETED
    W-->>API: Result
    API-->>Web: New version + comparison view
```

---

## 7. UC5 — Global feedback

```mermaid
sequenceDiagram
    autonumber
    actor User
    participant Web as Web (React)
    participant API as API
    participant W as Worker
    participant Orch as Orchestrator
    participant RF as Refiner
    participant LLM as LLMProvider
    participant PG as Postgres

    User->>Web: Add global note "Add more analogies", click "Apply globally"
    Web->>API: POST /v1/courses/{C}/feedback/global
    API->>W: Enqueue global feedback job (scope=course)
    W->>Orch: RunGlobalFeedback(course, note)
    loop For each block
        Orch->>RF: Refine(block, global_note)
        RF->>LLM: Apply global note
        LLM-->>RF: Refined block
        Orch->>PG: Persist new version (immutable)
    end
    Orch->>PG: Persist rollback point (course version snapshot)
    Orch-->>W: COMPLETED
    W-->>API: Result
    API-->>Web: Summary + per-block diffs
    Note over Web,User: User can roll back the entire global apply from version history (FR-VC-004)
```

---

## 8. UC6 — Curriculum regeneration

```mermaid
sequenceDiagram
    autonumber
    actor User
    participant Web as Web (React)
    participant API as API
    participant W as Worker
    participant Orch as Orchestrator
    participant CP as CurriculumPlanner
    participant LLM as LLMProvider

    User->>Web: Add curriculum feedback "Add a deployment module"
    Web->>API: POST /v1/courses/{C}/feedback/curriculum
    API->>W: Enqueue curriculum regen
    W->>Orch: RunCurriculumRegen(course, feedback)
    Orch->>CP: Plan(context, feedback)
    CP->>LLM: New skeleton
    LLM-->>CP: New CourseSkeleton
    CP-->>Orch: New skeleton
    Orch-->>W: Skeleton ready for approval (no content changes)
    W-->>API: Skeleton diff
    API-->>Web: Skeleton diff view
    User->>Web: Approve skeleton
    Web->>API: POST /v1/courses/{C}/skeleton/approve
    API->>W: Continue with content regen using new skeleton
    Note over Orch,W: Content regen reuses the evaluate–refine loop scoped to the affected sections
```

---

## 9. UC7 — Export to Markdown

```mermaid
sequenceDiagram
    autonumber
    actor User
    participant Web as Web (React)
    participant API as API
    participant EV as Evaluator
    participant W as Worker
    participant EX as MarkdownExporter
    participant S3 as Object Storage

    User->>Web: Click "Export → Markdown"
    Web->>API: POST /v1/courses/{C}/exports/markdown
    API->>EV: Pre-export validation (FR-EX-003)
    alt blockers present
        EV-->>API: blockers
        API-->>Web: 200 { blockers, options: "Export anyway" / "Fix first" }
        User->>Web: Choose "Export anyway" or fix and retry
    end
    API->>W: Enqueue export job
    W->>EX: Export(course)
    EX->>EX: Map block types → Markdown (FR-EX-001, FR-EX-004)
    EX->>S3: Upload artifacts
    S3-->>EX: Object url
    EX-->>W: ExportResult
    W-->>API: ExportResult
    API-->>Web: { download_url, expires_at }
    Web-->>User: Trigger download
```

---

## 10. UC8 — Job cancellation

```mermaid
sequenceDiagram
    autonumber
    actor User
    participant Web as Web (React)
    participant API as API
    participant PG as Postgres
    participant W as Worker
    participant Orch as Orchestrator

    User->>Web: Click "Cancel" on a running job
    Web->>API: POST /v1/jobs/{id}/cancel
    API->>PG: Set cancellation flag
    API-->>Web: 200 { status=cancelling }

    Note over W,Orch: On next checkpoint (between agent invocations)
    Orch->>PG: Check cancellation flag
    Orch->>PG: Persist partial result with termination_reason=user_aborted
    Orch-->>W: CANCELLED
    W-->>API: Status update
    API-->>Web: Status=cancelled, partial preserved
    Web-->>User: Show partial + offer to "Resume" or "Discard"
```

---

## 11. UC9 — Document upload and ingestion

```mermaid
sequenceDiagram
    autonumber
    actor User
    participant Web as Web (React)
    participant API as API
    participant S3 as Object Storage
    participant IN as Ingestor
    participant CS as ContextSynthesizer
    participant LLM as LLMProvider
    participant PG as Postgres

    User->>Web: Upload PDF
    Web->>API: POST /v1/documents (multipart, max-size enforced NFR-SEC-005)
    alt unsupported or oversized
        API-->>Web: 400 structured error (no raw text)
    else
        API->>S3: Store encrypted (tenant-isolated)
        S3-->>API: object_key
        API->>IN: Ingest(object_key)
        IN->>IN: Parse (pypdf / trafilatura)
        IN->>LLM: Summarize + chunk
        LLM-->>IN: chunks + summary
        IN->>PG: Persist DocumentRef + summary + chunks
        IN-->>API: document_id + summary
        API-->>Web: 201 { document_id, summary }
    end
    Note over CS,LLM: At generation time, ContextSynthesizer pulls DocumentRefs into the GenerationContext (FR-CX-002, FR-AG-002)
```

---

## 12. UC10 — Provider failover

```mermaid
sequenceDiagram
    autonumber
    participant W as Worker
    participant Orch as Orchestrator
    participant CB as CircuitBreaker
    participant LLM as LLMProvider (primary)
    participant Backup as LLMProvider (backup)
    participant PG as Postgres

    W->>Orch: Run agent X
    Orch->>CB: Call(primary, request)
    CB->>LLM: dispatch
    LLM-->>CB: error (rate-limited / 5xx)
    CB->>CB: increment error count
    alt error rate > threshold
        CB->>CB: open breaker for primary
        Note over CB: Subsequent calls fail fast
        alt backup configured for role X
            Orch->>Backup: Call(backup, request)
            Backup-->>Orch: response
            Orch->>PG: Persist trace with provider=backup
        else
            Orch->>PG: Persist structured issue code=PROVIDER_OUTAGE
            Orch-->>W: terminate with budget_exhausted or partial
        end
    else
        CB-->>Orch: response
    end
```

---

## 13. Notes

- All persistence writes (Postgres, Neo4j) are performed by the
  **Orchestrator**; other components are stateless
  (ADR-0002, FR-AG-001).
- All cross-cutting concerns — idempotency, optimistic concurrency,
  retries, structured errors — are enforced in the application layer
  (FR-INT-002, FR-INT-003, FR-JC-005, NFR-AVAIL-003).
- The agent trace is the **single source of truth** for what actually
  happened during a job (ADR-0011, NFR-OBS-004).

---

## 14. Cross-References

- **System Context** — `07 System Context Diagram.md`
- **C4 Container & Component** — `08 C4 Architecture.md`
- **ADRs** — `09 Architecture Decision Records.md`
- **JSON Output Contract** — `02 Business Requirements Document.md` §11
- **Functional Requirements** — `04 Functional Requirements.md`
- **Non-Functional Requirements** — `05 Non-Functional Requirements.md`
