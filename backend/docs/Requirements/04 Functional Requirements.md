# 04 Functional Requirements

> Document type: Functional Requirements Specification (FRS)
> Companion to: `01 Project Charter.md`, `02 Business Requirements Document.md`, `03 Product Requirements Document.md`
> Status: Draft v0.1 · Owner: Product + Engineering · Last updated: 2026-06-05
> This document decomposes business and product requirements into specific, testable functional requirements (FRs) for engineering and QA.

---

## 1. Document Control

| Field | Value |
|---|---|
| Project codename | CourseForge |
| Document version | 0.1 (Draft) |
| Author | Product Management + Engineering |
| Reviewers | Backend Lead, AI Lead, Frontend Lead, QA Lead |
| Approvers | Head of Product, Head of Engineering |
| Cadence | Reviewed at the end of each sprint |

---

## 2. Overview & Scope

This document describes **what the system shall do** (functional behavior) in
implementation-ready detail. It does **not** describe performance, security, or quality attributes — those are in `05 Non-Functional Requirements.md`.

**In scope:** every capability listed in the BRD §8 and PRD §6 epics.
**Out of scope:** items in the charter §6.2 / BRD §6.2 / PRD §10 (LMS, RAG,
mobile, payments, certification, video generation, etc.).

---

## 3. Conventions

### 3.1 Identifier format
- `FR-<AREA>-<NNN>` where `<AREA>` is a two- or three-letter code (e.g. `CG` for
  Course Generation, `AG` for Agent system, `EV` for Evaluation).
- `<NNN>` is a zero-padded sequence number scoped to the area.
- Examples: `FR-CG-001`, `FR-AG-014`, `FR-JC-003`.

### 3.2 Priority
- **M** = Must (MVP)
- **S** = Should (GA)
- **C** = Could (post-GA)
- **W** = Won't (this release)

### 3.3 Status
- **Proposed** — drafted, not yet reviewed.
- **Accepted** — reviewed and baselined.
- **Deferred** — moved to a later release.
- **Superseded** — replaced by another FR (cross-reference provided).

### 3.4 Requirement shape
Each FR contains:
- **Statement** — single normative sentence ("The system shall…").
- **Description** — context and rationale.
- **Inputs / Outputs** — the data contract involved.
- **Behavior** — normal flow, branches, error paths.
- **Dependencies** — other FRs that must be in place.
- **Verification** — how QA will test it.

---

## 4. Functional Requirements

### 4.1 Course Generation (FR-CG)

#### FR-CG-001 — Create course from topic
- **Priority:** M
- **Statement:** The system shall accept a topic specification and produce a
  complete course draft.
- **Description:** The user submits a `GenerationRequest` containing topic,
  audience, difficulty, learning outcomes, and optional context. The system
  creates a `GenerationJob` and returns its `job_id`.
- **Inputs:** `GenerationRequest` per `BRD §11` (subset).
- **Outputs:** `GenerationJob` (status `queued`).
- **Behavior:** Idempotent on identical `request_id` (re-submission returns
  the same job). On invalid input, returns `400` with a structured error.
- **Dependencies:** `FR-JC-001` (JSON contract), `FR-AG-001` (orchestrator).
- **Verification:** Submit a valid request; assert `job_id` returned and is
  queryable. Submit invalid request; assert `400`.

#### FR-CG-002 — Quick-start templates
- **Priority:** S
- **Statement:** The system shall support predefined templates that pre-fill
  topic, audience, block composition, and outcomes.
- **Inputs:** `template_id`.
- **Outputs:** Pre-filled `GenerationRequest` (returned, not yet submitted).
- **Verification:** Apply template; verify all pre-filled fields match
  template definition.

#### FR-CG-003 — Required field validation
- **Priority:** M
- **Statement:** The system shall reject generation requests missing required
  fields (topic, audience, difficulty, at least one learning outcome).
- **Verification:** Omit each required field in turn; assert `400` with a
  machine-readable error code.

#### FR-CG-004 — Asynchronous job lifecycle
- **Priority:** M
- **Statement:** The system shall process generation jobs asynchronously and
  expose a status endpoint for polling.
- **Statuses:** `queued`, `running`, `completed`, `failed`, `partial`.
- **Verification:** Submit a job; poll status; assert transitions follow
  the state machine in `FR-AG-010`.

---

### 4.2 Curriculum Structuring (FR-CS)

#### FR-CS-001 — Enforce Course → Module → Section → Block hierarchy
- **Priority:** M
- **Statement:** The system shall model courses as a strict hierarchy with
  the relationship `Course 1—N Module 1—N Section 1—N Block`.
- **Verification:** Attempt to create a section without a parent module;
  assert rejection. Attempt to create a block without a parent section;
  assert rejection.

#### FR-CS-002 — Ordering within each level
- **Priority:** M
- **Statement:** The system shall preserve an explicit `order` field at
  module, section, and block levels.
- **Verification:** Create 3 sections; assign orders 2, 0, 1; read back;
  assert re-ordered output is sorted ascending by `order`.

#### FR-CS-003 — Module/section/block identifiers
- **Priority:** M
- **Statement:** The system shall assign stable, unique identifiers (UUIDv7)
  to every course, module, section, and block.
- **Verification:** Create entities; assert IDs are unique, stable across
  reads, and survive regeneration.

#### FR-CS-004 — Learning objectives on sections
- **Priority:** M
- **Statement:** The system shall allow one or more learning objectives per
  section and shall require at least one.
- **Verification:** Create a section with empty `learning_objectives`; assert
  rejection.

#### FR-CS-005 — Learning outcomes on courses
- **Priority:** M
- **Statement:** The system shall allow one or more learning outcomes per
  course and shall require at least one.
- **Verification:** Create a course with no outcomes; assert rejection.

#### FR-CS-006 — Curriculum coverage map
- **Priority:** S
- **Statement:** The system shall maintain an internal mapping from each
  learning outcome to the sections that cover it.
- **Outputs:** `outcome_coverage` map on the course payload.
- **Verification:** Inspect generated course; assert every learning outcome
  is covered by at least one section; assert no section claims to cover an
  outcome not present on the course.

---

### 4.3 Content Blocks (FR-BL)

#### FR-BL-001 — Block type registry
- **Priority:** M
- **Statement:** The system shall support the v1 block type taxonomy:
  `concept`, `example`, `code`, `exercise`, `solution`, `challenge`, `quiz`,
  `key_points`, `best_practices`, `common_mistakes`, `visual_explanation`,
  `analogy`, `reference`.
- **Verification:** For each type, generate at least one block; assert the
  output schema validates.

#### FR-BL-002 — Type-specific content shape
- **Priority:** M
- **Statement:** The system shall validate the `content` field of each block
  against the JSON Schema for its declared `type` (per BRD §11.2.1).
- **Verification:** Submit a Code block with a non-string `source`; assert
  validation failure. Submit a Quiz block with `answer_index` out of range;
  assert failure.

#### FR-BL-003 — Block metadata
- **Priority:** M
- **Statement:** The system shall store `estimated_time_minutes` and
  `difficulty` per block.
- **Verification:** Persist values; read back; assert round-trip equality.

#### FR-BL-004 — Block ordering within a section
- **Priority:** M
- **Statement:** The system shall order blocks within a section by an
  explicit `order` field, contiguous from 0.
- **Verification:** Insert a block with `order=5` into a section of size 3;
  assert rejection with a clear error.

#### FR-BL-005 — Reference resolution
- **Priority:** S
- **Statement:** The system shall resolve `exercise → solution_ref`
  references within the same section.
- **Verification:** Create an exercise that references a non-existent block;
  assert validation failure. Create a valid reference; assert it resolves.

#### FR-BL-006 — Quiz schema validation
- **Priority:** M
- **Statement:** The system shall validate that every quiz question has at
  least two choices, a valid `answer_index`, and a non-empty `explanation`.
- **Verification:** Submit invalid quizzes; assert rejection. Submit valid
  one; assert acceptance.

#### FR-BL-007 — Code block language allowlist
- **Priority:** S
- **Statement:** The system shall restrict the `language` field on Code
  blocks to a configurable allowlist (defaulting to common languages).
- **Verification:** Submit an unknown language; assert rejection.

---

### 4.4 Multi-Agent Pipeline (FR-AG)

#### FR-AG-001 — Orchestrator agent
- **Priority:** M
- **Statement:** The system shall implement an `Orchestrator` agent that
  coordinates the agent folder and is the only agent authorized to write
  to persistence.
- **Description:** See `BRD §10.1`.
- **Verification:** Inspect the agent trace in the JSON output; assert all
  `persistence_writes` originate from the orchestrator.

#### FR-AG-002 — ContextSynthesizer agent
- **Priority:** M
- **Statement:** The system shall implement a `ContextSynthesizer` agent
  that normalizes and merges all user inputs into a single
  `GenerationContext` payload.
- **Inputs:** topic, audience, difficulty, outcomes, instructions,
  documents, reference courses, domain knowledge, feedback history.
- **Outputs:** `GenerationContext` (typed, versioned).
- **Verification:** Submit a request with all input kinds; assert the
  emitted context contains a normalized entry for each.

#### FR-AG-003 — CurriculumPlanner agent
- **Priority:** M
- **Statement:** The system shall implement a `CurriculumPlanner` agent
  that produces a `CourseSkeleton` (modules, section topics, objectives,
  prerequisite graph).
- **Outputs:** `CourseSkeleton` (validated against skeleton schema).
- **Verification:** Run planner with a fixed context; assert skeleton
  conforms to schema and respects audience/difficulty constraints.

#### FR-AG-004 — SectionAuthor agent
- **Priority:** M
- **Statement:** The system shall implement a `SectionAuthor` agent that
  produces the typed content blocks of a single section.
- **Inputs:** `SectionSpec` (from skeleton), `GenerationContext`.
- **Outputs:** `SectionDraft` with typed blocks.
- **Verification:** For each block type, assert the produced block validates
  against its JSON Schema.

#### FR-AG-005 — PersonaAdapter agent
- **Priority:** S
- **Statement:** The system shall implement a `PersonaAdapter` agent that
  rewrites/adapt section content to the target audience profile.
- **Inputs:** `SectionDraft`, audience profile, instructional strategy.
- **Outputs:** `AdaptedSection`.
- **Verification:** Compare adapted section to draft; assert tone/terminology
  differences consistent with persona (spot-check eval set).

#### FR-AG-006 — ConsistencyChecker agent
- **Priority:** S
- **Statement:** The system shall implement a `ConsistencyChecker` agent
  that detects cross-section and cross-block inconsistencies
  (terminology, ordering, contradictions).
- **Outputs:** `ConsistencyReport` with paired findings.
- **Verification:** Inject a known contradiction between two sections; assert
  the report contains the pair with severity ≥ warning.

#### FR-AG-007 — PrerequisiteValidator agent
- **Priority:** S
- **Statement:** The system shall implement a `PrerequisiteValidator` agent
  that verifies the learning progression is well-ordered and that
  prerequisites are introduced before they are needed.
- **Outputs:** `ProgressionReport`.
- **Verification:** Generate a course on a known topic; assert no concept
  is used before it is introduced in the curriculum order.

#### FR-AG-008 — Evaluator (Critic) agent
- **Priority:** M
- **Statement:** The system shall implement an `Evaluator` agent that scores
  the current draft against the rubric and emits structured issues.
- **Inputs:** Course payload (or module/section/block payload for targeted
  evaluation), rubric version.
- **Outputs:** `EvaluationReport` (scores + issues).
- **Verification:** Submit a draft with a known structural defect; assert
  the report includes the issue with the correct scope and category.

#### FR-AG-009 — Refiner agent
- **Priority:** M
- **Statement:** The system shall implement a `Refiner` agent that
  consumes the Evaluator's issues (and other agents' reports) and produces
  a revised draft.
- **Inputs:** Current draft, evaluation report, optional feedback.
- **Outputs:** `RefinedDraft`.
- **Verification:** Apply refinement to a draft with a known issue; assert
  the next Evaluator run no longer reports the same issue (or reports it
  with reduced severity).

#### FR-AG-010 — Refinement loop state machine
- **Priority:** M
- **Statement:** The system shall implement the refinement loop described
  in `BRD §10.2` with the termination rules in `BRD §10.3`.
- **Behavior:**
  1. `ContextSynthesizer` → context
  2. `CurriculumPlanner` → skeleton
  3. For each section: `SectionAuthor` → `PersonaAdapter`
  4. `ConsistencyChecker`, `PrerequisiteValidator` (initial pass)
  5. `Evaluator` (initial pass)
  6. While not passed and iterations < max and budget remains:
     `Refiner` → `ConsistencyChecker` → `PrerequisiteValidator` → `Evaluator`
  7. `Orchestrator` → final JSON contract
- **Verification:** Drive a synthetic job; assert the agent trace matches
  the sequence; assert termination reason is recorded.

#### FR-AG-011 — Per-iteration iteration cap
- **Priority:** M
- **Statement:** The system shall enforce a configurable per-course
  iteration cap (default 3) and stop refinement when reached.
- **Verification:** Force a draft that never passes; assert the loop stops
  at the cap and `termination_reason=max_iterations`.

#### FR-AG-012 — Token & wall-clock budget
- **Priority:** M
- **Statement:** The system shall enforce a per-job token budget and a
  wall-clock budget; reaching either terminates the loop with
  `termination_reason=budget_exhausted`.
- **Verification:** Configure a tiny budget; run a job; assert termination
  with `budget_exhausted` and a partial result returned.

#### FR-AG-013 — Provider-agnostic agent port
- **Priority:** M
- **Statement:** The system shall define a `LLMProvider` port and shall
  implement at least two adapters (OpenAI, Anthropic, or Google) by GA.
- **Verification:** Swap the configured provider; assert a regeneration
  run completes without changes to agent code, prompts, or rubric.

#### FR-AG-014 — Per-agent model assignment
- **Priority:** S
- **Statement:** The system shall allow an admin to assign different models
  to different agent roles (planner, author, evaluator, refiner, etc.).
- **Verification:** Set Evaluator to provider A and Author to provider B;
  run a job; assert the agent trace shows the correct model per agent.

#### FR-AG-015 — Agent failure routing
- **Priority:** S
- **Statement:** The system shall record agent failures in the agent trace
  and, when possible, route around them (e.g. skip a non-critical agent
  with a deterministic fallback) rather than aborting the job.
- **Verification:** Force PrerequisiteValidator to fail; assert the job
  completes with a structured warning issue, not an outright failure.

---

### 4.5 Quality Evaluation (FR-EV)

#### FR-EV-001 — Multi-dimensional rubric
- **Priority:** M
- **Statement:** The system shall evaluate drafts against the 7-dimension
  rubric defined in `BRD §10.4`: `accuracy`, `pedagogical_clarity`,
  `structure_compliance`, `depth_appropriateness`, `audience_alignment`,
  `consistency`, `completeness`.
- **Outputs:** Per-dimension score (0.0–1.0) and overall score.
- **Verification:** Evaluate a synthetic draft; assert all 7 dimensions
  present in the report.

#### FR-EV-002 — Rubric thresholds
- **Priority:** M
- **Statement:** The system shall apply a configurable threshold per
  dimension and an overall threshold; passing requires all configured
  thresholds to be met.
- **Verification:** Set a high threshold; assert a borderline draft fails;
  lower threshold; assert it passes.

#### FR-EV-003 — Rubric versioning
- **Priority:** M
- **Statement:** The system shall version the rubric and record the
  version used for every evaluation.
- **Verification:** Bump rubric version; assert the version appears in
  `evaluation.rubric_version` on subsequent jobs.

#### FR-EV-004 — Issue taxonomy
- **Priority:** M
- **Statement:** The system shall emit issues with the fields
  `severity` (`info|warning|error|blocker`), `scope`
  (`course|module|section|block`), `target_id`, `category`
  (`factual|pedagogical|structural|style|completeness|consistency`),
  `message`, `suggestion`, `auto_fixable`.
- **Verification:** Trigger a known issue; assert the emitted issue has
  all required fields and matches the taxonomy.

#### FR-EV-005 — Per-iteration score trajectory
- **Priority:** S
- **Statement:** The system shall record the overall score per iteration
  in `evaluation.iteration_scores`.
- **Verification:** Run a job with N iterations; assert
  `iteration_scores.length == N` and scores are monotonically non-decreasing
  on the eval set (best-effort).

#### FR-EV-006 — Block-level groundedness check
- **Priority:** C
- **Statement:** The system shall, where context documents are provided,
  verify factual claims in blocks against the supplied context.
- **Verification:** Inject a document with a specific fact; assert a block
  contradicting the fact is flagged under `category=factual`.

---

### 4.6 Editing (FR-ED)

#### FR-ED-001 — Inline block editing
- **Priority:** M
- **Statement:** The system shall allow the user to edit any block's
  `content` field through a type-appropriate editor and save a new version.
- **Verification:** Edit a Code block; save; assert new version created,
  old version preserved, `last_modified_by` recorded.

#### FR-ED-002 — Type-specific editors
- **Priority:** M
- **Statement:** The system shall provide editors matched to block type
  (rich text for Concept, code editor for Code, structured editor for
  Quiz, list editor for Key Points, etc.).
- **Verification:** For each type, assert the editor enforces the type's
  JSON Schema on save.

#### FR-ED-003 — Manual edit is not silently re-evaluated
- **Priority:** M
- **Statement:** The system shall not invoke the Evaluator on a manual
  edit unless the user explicitly requests re-evaluation.
- **Verification:** Save a manual edit; assert no Evaluator invocation is
  recorded for that block until the user clicks "Re-evaluate block".

#### FR-ED-004 — Unsaved-changes guard
- **Priority:** S
- **Statement:** The system shall warn the user when navigating away from
  an editor with unsaved changes.
- **Verification:** Make an edit; attempt to navigate; assert a
  confirmation dialog appears.

#### FR-ED-005 — Edit attribution
- **Priority:** S
- **Statement:** The system shall record, for every saved edit, the
  author identity, source (`manual_edit`), and timestamp.
- **Verification:** Save an edit; inspect the new version; assert
  attribution fields are populated.

---

### 4.7 Granular Regeneration (FR-RG)

#### FR-RG-001 — Block-level regeneration
- **Priority:** S
- **Statement:** The system shall allow the user to regenerate a single
  block; only that block's content is rewritten and re-evaluated.
- **Verification:** Regenerate block B; assert all other block versions
  are unchanged in version history.

#### FR-RG-002 — Section-level regeneration
- **Priority:** S
- **Statement:** The system shall allow the user to regenerate an entire
  section; only blocks within that section are rewritten and
  re-evaluated.
- **Verification:** Regenerate section S; assert no block outside S has a
  new version.

#### FR-RG-003 — Module-level regeneration
- **Priority:** S
- **Statement:** The system shall allow the user to regenerate an entire
  module; only sections/blocks within that module are rewritten and
  re-evaluated.
- **Verification:** Regenerate module M; assert no block outside M has a
  new version.

#### FR-RG-004 — Side-by-side comparison
- **Priority:** S
- **Statement:** The system shall present the previous and new version of
  a regenerated block/section/module side by side, with diff highlighting
  and the Evaluator's score for each.
- **Verification:** Trigger a regeneration; assert the comparison view
  shows both versions, their scores, and a structural/textual diff.

#### FR-RG-005 — Accept / discard new version
- **Priority:** S
- **Statement:** The system shall let the user accept (replace current
  version) or discard (keep current) the new version; in both cases the
  new version is preserved in history.
- **Verification:** Accept new version; assert the new version is now
  current. Discard new version; assert previous version remains current
  and the new version is in history.

#### FR-RG-006 — Targeted regeneration runs the same evaluate–refine loop
- **Priority:** S
- **Statement:** The system shall run the same evaluate–refine loop on the
  targeted aggregate as on a full course, with the same iteration cap and
  budget rules (per-scope).
- **Verification:** Force a non-passing target; assert the loop iterates
  and terminates according to its own budget; assert the agent trace is
  scoped to the target.

---

### 4.8 Feedback Processing (FR-FB)

#### FR-FB-001 — Block feedback
- **Priority:** S
- **Statement:** The system shall accept a free-form feedback note
  attached to a specific block; subsequent regeneration of that block
  shall address the feedback.
- **Verification:** Submit feedback "Add a real-world example";
  regenerate; assert the new block contains an example consistent with
  the feedback.

#### FR-FB-002 — Section feedback
- **Priority:** S
- **Statement:** The system shall accept feedback attached to a section
  and apply it across the section's blocks during regeneration.
- **Verification:** Submit section feedback; regenerate section; assert
  the change set is contained within the section.

#### FR-FB-003 — Curriculum feedback
- **Priority:** S
- **Statement:** The system shall accept feedback attached to the course
  as a whole; the CurriculumPlanner is re-invoked and the resulting
  skeleton is presented for approval before any section content is
  regenerated.
- **Verification:** Submit curriculum feedback "Add a deployment
  module"; assert the new skeleton includes a deployment module and
  no section content has been modified yet.

#### FR-FB-004 — Global feedback
- **Priority:** S
- **Statement:** The system shall accept a global feedback note and apply
  it across every block; the operation is reversible from version
  history.
- **Verification:** Apply a global note ("Use AWS in cloud examples");
  assert the change is reversible by restoring the prior version.

#### FR-FB-005 — Feedback history
- **Priority:** S
- **Statement:** The system shall persist all feedback entries and make
  them visible in the agent trace / version history.
- **Verification:** Submit feedback; regenerate; inspect the trace;
  assert the feedback is recorded with the iteration it influenced.

---

### 4.9 Context Injection (FR-CX)

#### FR-CX-001 — Text instructions as context
- **Priority:** M
- **Statement:** The system shall accept a free-form text instruction
  that is included in the `GenerationContext` and is visible in the
  generation metadata.
- **Verification:** Submit a request with text instructions; assert the
  instruction appears in the agent trace metadata and in the
  `GenerationContext`.

#### FR-CX-002 — Document upload
- **Priority:** S
- **Statement:** The system shall accept uploads of PDF, Markdown, and
  plain text files; the `ContextSynthesizer` shall ingest, chunk, and
  summarize them into the context.
- **Inputs:** File (PDF, MD, TXT), max size enforced per plan.
- **Verification:** Upload a file; assert ingestion completes; assert
  the summary appears in the context; assert the file is rejected
  (size/type) when invalid.

#### FR-CX-003 — Reference course analysis
- **Priority:** S
- **Statement:** The system shall accept one or more reference courses
  and analyze their structure and pedagogy (not their content) to
  influence the new course.
- **Verification:** Attach a reference; assert the resulting course
  exhibits the reference's structure (module count, pacing) but does
  not contain copied prose.

#### FR-CX-004 — Domain knowledge items
- **Priority:** S
- **Statement:** The system shall accept domain knowledge items
  (standards, regulations, terminology) that are stored as structured
  context entries and applied during generation.
- **Verification:** Add "We use AWS, not GCP"; assert generated cloud
  examples use AWS by default.

#### FR-CX-005 — Learning outcomes as drivers
- **Priority:** M
- **Statement:** The system shall treat learning outcomes as first-class
  inputs that drive topic selection, exercise generation, and
  assessment, and shall produce an `outcome_coverage` map.
- **Verification:** Define 3 outcomes; assert the curriculum contains
  at least one section that demonstrably covers each.

#### FR-CX-006 — Context isolation per tenant
- **Priority:** M
- **Statement:** The system shall ensure that context (documents,
  domain knowledge, reference courses, feedback) is isolated per
  tenant; no leakage across tenants.
- **Verification:** Attempt to read another tenant's uploaded document;
  assert `403`.

---

### 4.10 Personalization (FR-PZ)

#### FR-PZ-001 — Audience & difficulty
- **Priority:** M
- **Statement:** The system shall accept and persist audience profile
  and difficulty at the course level.
- **Verification:** Set values; assert they appear on the course
  payload and in the `GenerationContext`.

#### FR-PZ-002 — Per-module depth override
- **Priority:** S
- **Statement:** The system shall allow a depth override on a single
  module without affecting sibling modules.
- **Verification:** Override depth on module M; regenerate M; assert
  M's content reflects the override and sibling modules are unchanged.

#### FR-PZ-003 — Block composition rules
- **Priority:** S
- **Statement:** The system shall allow the user to define a block
  composition rule (set of block types and order) that applies to
  generated sections.
- **Verification:** Define a rule "Concept, Example, Exercise, Key
  Points"; generate a section; assert the section's block sequence
  matches the rule.

#### FR-PZ-004 — Instructional strategy
- **Priority:** S
- **Statement:** The system shall accept a configurable instructional
  strategy (e.g. `example_driven`, `theory_first`, `project_based`)
  that influences block ordering and content shape.
- **Verification:** Set strategy; generate; assert (spot-check) the
  resulting blocks lead with the strategy's preferred block type.

#### FR-PZ-005 — Technical vs. practical balance
- **Priority:** S
- **Statement:** The system shall accept a balance parameter
  (theoretical/practical/academic/industry/research/certification) and
  apply it to the generated content.
- **Verification:** Set balance to "industry-oriented"; assert
  generated examples use industry tooling (spot-check).

#### FR-PZ-006 — Audience profile enum
- **Priority:** M
- **Statement:** The system shall restrict `audience.profile` to a
  closed set:
  `beginner | professional | engineer | architect | manager | researcher | student`.
- **Verification:** Submit an unknown profile; assert `400`.

---

### 4.11 Versioning & Lineage (FR-VC)

#### FR-VC-001 — Per-aggregate version history
- **Priority:** S
- **Statement:** The system shall maintain a version history for every
  course, module, section, and block.
- **Verification:** Create 3 versions of a block; assert history lists
  3 entries in chronological order with timestamps and authors.

#### FR-VC-002 — Lineage capture
- **Priority:** M
- **Statement:** The system shall record, for every generated version,
  the lineage: `inputs`, `prompt_version`, `model_version`,
  `rubric_version`, `agent_trace`, and `seed` (where supported).
- **Verification:** Run a job; assert all lineage fields are present
  in the `generation` block of the JSON output.

#### FR-VC-003 — Version comparison
- **Priority:** S
- **Statement:** The system shall support side-by-side comparison of
  any two versions of a block, section, module, or course, with
  character-level diff for text and structural diff for arrays/objects.
- **Verification:** Compare two versions; assert diff highlights
  appear and the rendering matches the block-type-specific
  component.

#### FR-VC-004 — Rollback
- **Priority:** S
- **Statement:** The system shall allow rollback of a block, section,
  module, or course to any prior version; the rollback itself is
  recorded as a new event in the history.
- **Verification:** Rollback to v1; assert v1 is now current and a
  rollback event is in the history.

#### FR-VC-005 — Reproducibility
- **Priority:** C
- **Statement:** Where the underlying provider supports it, the
  system shall expose a `seed` for runs; the same inputs + seed +
  prompt version + model version shall produce the same outputs.
- **Verification:** Run a job twice with the same seed; assert
  identical block content (where provider supports deterministic
  sampling).

#### FR-VC-006 — Immutability of historical versions
- **Priority:** M
- **Statement:** Historical versions shall be immutable; edits and
  regenerations create new versions rather than mutating the old.
- **Verification:** Edit a block; assert the prior version's content
  is unchanged in storage.

---

### 4.12 Export & Publishing (FR-EX)

#### FR-EX-001 — Markdown export
- **Priority:** S
- **Statement:** The system shall export a course to one or more
  Markdown files where block types map to appropriate Markdown
  structures (headings, code fences, lists, tables).
- **Verification:** Export to MD; open file; assert structure is
  valid Markdown and block types are represented.

#### FR-EX-002 — PDF export
- **Priority:** S
- **Statement:** The system shall export a course to a single PDF
  whose visual layout matches the section reading view.
- **Verification:** Export to PDF; open; assert all sections and
  block types are present and rendered.

#### FR-EX-003 — Pre-export validation
- **Priority:** S
- **Statement:** The system shall run the Evaluator over the current
  state before export and surface any blocker issues.
- **Verification:** Inject a blocker issue; click Export; assert the
  user is warned and offered "Export anyway" or "Fix first".

#### FR-EX-004 — Block-type fidelity on export
- **Priority:** S
- **Statement:** The system shall preserve block-type semantics in
  exports to the extent supported by the target format; loss of
  fidelity is reported, not silent.
- **Verification:** Export a Quiz block to MD; assert the quiz
  question and choices are preserved (and a fidelity note is shown
  for any non-rendering fields).

#### FR-EX-005 — Export provenance
- **Priority:** S
- **Statement:** Exported artifacts shall include a header/footer
  with the course id, version, and generation timestamp.
- **Verification:** Export; assert the provenance header is present.

---

### 4.13 Provider Configuration (FR-PR)

#### FR-PR-001 — Provider registry
- **Priority:** M
- **Statement:** The system shall maintain a provider registry
  supporting at minimum: `openai`, `anthropic`, `google`.
- **Verification:** Configure each provider; assert a smoke-test
  generation completes with each.

#### FR-PR-002 — Admin-only configuration
- **Priority:** M
- **Statement:** Provider and model configuration shall be accessible
  only to admin users; non-admin users shall not see provider
  selectors in the UI.
- **Verification:** Log in as a non-admin; assert no provider
  selector is rendered.

#### FR-PR-003 — Provider-agnostic domain layer
- **Priority:** M
- **Statement:** The domain layer shall have no dependency on
  provider-specific concepts; provider-specific code shall be
  confined to adapters behind the `LLMProvider` port.
- **Verification:** Inspect the dependency graph; assert the
  domain package does not import from any provider SDK.

#### FR-PR-004 — Prompt version management
- **Priority:** M
- **Statement:** The system shall version every prompt used by
  agents and shall record the version used in the generation
  metadata.
- **Verification:** Update a prompt; assert a new version is
  recorded; assert subsequent jobs reference the new version.

#### FR-PR-005 — Provider health and circuit breaking
- **Priority:** S
- **Statement:** The system shall track per-provider error rates
  and open a circuit breaker for a provider whose error rate
  exceeds a configured threshold; calls during the open state
  fail fast and may be retried on a backup provider if configured.
- **Verification:** Force provider errors; assert the breaker
  opens and the system fails fast.

---

### 4.14 Block-Type Extensibility (FR-BT)

#### FR-BT-001 — Block type registry API
- **Priority:** C
- **Statement:** The system shall allow an admin to register a new
  block type by providing a name, a JSON-Schema for the `content`
  field, a default renderer hint, and (optionally) agent prompts.
- **Verification:** Register a "flashcard" type; assert it is
  usable in the curriculum tree within the same session.

#### FR-BT-002 — Validator on registration
- **Priority:** C
- **Statement:** The system shall reject block-type registrations
  with invalid JSON-Schema, missing required metadata, or name
  collisions with the built-in taxonomy.
- **Verification:** Submit invalid registrations; assert rejection
  with structured error.

#### FR-BT-003 — Evaluator support for custom types
- **Priority:** C
- **Statement:** The system shall evaluate blocks of custom types
  using the registered schema as a structural check and any
  registered prompts as part of the rubric scoring.
- **Verification:** Register a type; generate a block of that
  type; assert the Evaluator scores it.

#### FR-BT-004 — Renderer plug-in contract
- **Priority:** C
- **Statement:** The system shall look up the renderer for a block
  type from the registry and shall fail gracefully (with a
  structured warning issue) if no renderer is registered.
- **Verification:** Reference a type with no renderer; assert the
  UI degrades gracefully and the issue is recorded.

---

### 4.15 AI-Assisted Curriculum Review (FR-AR)

#### FR-AR-001 — Pre-generation gap analysis
- **Priority:** C
- **Statement:** The system shall analyze the user's inputs before
  generation and emit recommendations such as "missing topics",
  "progression too steep", "outcome-difficulty mismatch".
- **Verification:** Submit inputs with a known gap; assert the
  recommendation appears in the pre-generation review.

#### FR-AR-002 — Post-generation overlap detection
- **Priority:** S
- **Statement:** The system shall detect sections or modules whose
  content overlaps significantly and emit a paired warning.
- **Verification:** Inject overlapping sections; assert the
  paired warning is in the issues list.

#### FR-AR-003 — Recommendation dismissal
- **Priority:** C
- **Statement:** The system shall allow the user to dismiss a
  recommendation; a dismissed recommendation is not re-shown
  unless inputs change.
- **Verification:** Dismiss a recommendation; rerun review; assert
  the recommendation is not re-shown.

---

### 4.16 Dashboard & Metrics (FR-DS)

#### FR-DS-001 — Course portfolio dashboard
- **Priority:** S
- **Statement:** The system shall provide a dashboard listing all
  courses in the user's scope with columns: title, status, overall
  quality score, last edited, number of issues, owner.
- **Verification:** Open dashboard; assert columns are present
  and sortable.

#### FR-DS-002 — Filters and persistence
- **Priority:** S
- **Statement:** The system shall support filters on the dashboard
  (e.g. quality < 0.7) and shall persist the active filter in the
  URL for shareable views.
- **Verification:** Apply a filter; copy the URL; open in a new
  tab; assert the filter is reapplied.

#### FR-DS-003 — Aggregate metrics
- **Priority:** S
- **Statement:** The system shall expose aggregate metrics: rubric
  pass rate, average quality uplift, iterations to pass, cost per
  course, courses generated over time.
- **Verification:** Open the metrics view; assert each metric is
  present with a time-series chart.

#### FR-DS-004 — Per-user metrics
- **Priority:** C
- **Statement:** The system shall expose per-user activity metrics
  (courses generated, refinement cycles, exports).
- **Verification:** Generate a course as user A; assert A's
  metrics reflect the activity.

---

### 4.17 JSON Output Contract (FR-JC)

#### FR-JC-001 — Single JSON response
- **Priority:** M
- **Statement:** On every completed generation, the system shall
  return a single JSON document conforming to the schema in
  `BRD §11`.
- **Verification:** Submit a request; assert response is valid
  JSON and validates against the published schema for the
  declared `schema_version`.

#### FR-JC-002 — Schema versioning
- **Priority:** M
- **Statement:** The system shall version the JSON schema; breaking
  changes bump the major version of `schema_version`.
- **Verification:** Bump the major version; assert the new schema
  is served and old clients are signaled via `schema_version`.

#### FR-JC-003 — Agent trace completeness
- **Priority:** M
- **Statement:** The JSON `generation.agent_trace` shall list every
  agent invocation with timestamps, token usage, and status.
- **Verification:** Run a multi-iteration job; assert the trace
  contains an entry per agent per iteration.

#### FR-JC-004 — Issues & next_actions as UI surface
- **Priority:** S
- **Statement:** The JSON shall include `issues` and `next_actions`
  as the primary UI surface for quality, with stable codes,
  severities, and action types.
- **Verification:** Trigger known issues; assert they appear with
  the expected codes and severities.

#### FR-JC-005 — No free-form error text to frontend
- **Priority:** M
- **Statement:** The system shall not return free-form error text
  to the frontend; all errors surface as structured
  `issues` entries with stable codes.
- **Verification:** Trigger a backend error; assert the response
  is structured (no leaked stack traces, no raw exception
  messages).

#### FR-JC-006 — Streaming progress events
- **Priority:** S
- **Statement:** The system shall support streaming progress events
  (WebSocket or SSE) carrying intermediate iteration scores and
  agent statuses; only the final frame is authoritative.
- **Verification:** Open a streaming connection; assert progress
  events arrive during the job; assert the final event matches
  the synchronous response.

---

### 4.18 User & Workspace Management (FR-UM)

> Minimal scope for v1: single-tenant by default; multi-tenant
> behind a flag.

#### FR-UM-001 — Authentication
- **Priority:** S
- **Statement:** The system shall authenticate users via a standard
  identity provider; sessions expire per configurable policy.
- **Verification:** Log in with valid and invalid credentials;
  assert correct success/failure and session expiration.

#### FR-UM-002 — Authorization roles
- **Priority:** S
- **Statement:** The system shall enforce at least two roles:
  `user` (create/edit/review courses) and `admin` (provider
  configuration, metrics, block-type registration).
- **Verification:** Attempt admin actions as a user; assert `403`.

#### FR-UM-003 — Tenant isolation
- **Priority:** M
- **Statement:** The system shall isolate all data (courses,
  documents, feedback, generations) per tenant.
- **Verification:** Attempt cross-tenant access; assert `403`.

#### FR-UM-004 — Audit log
- **Priority:** S
- **Statement:** The system shall record an audit log of
  generation, edit, export, and configuration events, with
  actor, timestamp, and target.
- **Verification:** Perform each event type; assert the audit
  log contains the corresponding entry.

---

### 4.19 Notifications & Events (FR-NE)

#### FR-NE-001 — Job completion notification
- **Priority:** S
- **Statement:** The system shall emit a notification (in-app and
  optional email/webhook) when a generation job completes.
- **Verification:** Run a job; assert the notification is emitted
  and visible in the user's notification center.

#### FR-NE-002 — Failure notification
- **Priority:** S
- **Statement:** The system shall emit a notification when a
  generation job fails terminally, including the structured
  failure reason.
- **Verification:** Force a job failure; assert the notification
  is emitted and includes a structured reason.

---

## 5. Cross-Cutting Functional Rules

### 5.1 Idempotency
- Generation requests with the same `request_id` and identical
  input hash shall return the same `job_id` and shall not create
  duplicate jobs.

### 5.2 Concurrency
- Two concurrent requests on the same course (or by the same
  user) shall not corrupt state; the system shall apply
  optimistic concurrency on the `version` field of each aggregate.

### 5.3 Data lifecycle
- Soft-deleted courses shall be retained for a configurable
  period (default 30 days) before hard deletion.

---

## 6. Traceability Matrix (FR → BR → US)

| FR | BR | US (PRD) |
|---|---|---|
| FR-CG-001 | BR-001, BO-001 | US-1.1.1, US-1.1.2, US-1.1.3 |
| FR-CG-002 | BO-001 | US-1.2.1 |
| FR-CG-003 | BR-001 | US-1.1.1 (AC-1.1.2) |
| FR-CG-004 | BR-001, BO-008 | US-2.1.1 |
| FR-CS-001 | BR-002 | — |
| FR-CS-002 | BR-002 | US-3.1.1 |
| FR-CS-003 | BR-001 | US-3.1.1 |
| FR-CS-004 | BR-002 | — |
| FR-CS-005 | BR-002 | — |
| FR-CS-006 | BR-001, BO-001 | US-3.1.1, US-7.5.1 |
| FR-BL-001 | BR-003 | US-3.2.1 |
| FR-BL-002 | BC-003 | US-4.1.1 |
| FR-BL-003 | BR-001 | US-3.2.1 |
| FR-BL-004 | BR-002 | US-3.1.1 |
| FR-BL-005 | BR-001 | — |
| FR-BL-006 | BR-003 | US-3.2.3 |
| FR-BL-007 | BC-003 | — |
| FR-AG-001 | BO-009, BO-010 | US-2.1.1 |
| FR-AG-002 | BO-005 | US-7.1.1, US-7.2.1 |
| FR-AG-003 | BO-001, BO-002 | US-3.1.1 |
| FR-AG-004 | BO-001, BO-002 | US-3.2.1 |
| FR-AG-005 | BO-003 | US-6.3.1 |
| FR-AG-006 | BO-009 | US-2.1.1 |
| FR-AG-007 | BO-001 | US-3.1.1 |
| FR-AG-008 | BO-009, BR-011 | US-2.1.1, US-2.1.2 |
| FR-AG-009 | BO-009, BR-010 | US-5.1.1 |
| FR-AG-010 | BR-010 | US-2.1.1 |
| FR-AG-011 | BR-010 | US-2.1.2 |
| FR-AG-012 | BR-010 | — |
| FR-AG-013 | BR-007, BR-016 | US-11.1.1 |
| FR-AG-014 | BR-016 | US-11.1.1 |
| FR-AG-015 | BR-010 | — |
| FR-EV-001 | BR-011 | US-2.1.2 |
| FR-EV-002 | BR-011 | US-2.1.2 |
| FR-EV-003 | BR-015, BC-006 | — |
| FR-EV-004 | BR-011 | US-2.1.1 |
| FR-EV-005 | BR-013 | US-2.1.2 |
| FR-EV-006 | BR-011 | — |
| FR-ED-001 | BR-001, BO-008 | US-4.1.1, US-4.1.2 |
| FR-ED-002 | BC-003 | US-4.1.1, US-4.1.3 |
| FR-ED-003 | BO-008, BC-001 | US-4.2.1 |
| FR-ED-004 | BC-001 | US-4.1.1 |
| FR-ED-005 | BO-008 | US-4.1.1 |
| FR-RG-001 | BO-012, BR-014 | US-5.1.1, US-5.1.2 |
| FR-RG-002 | BO-012, BR-014 | US-5.2.1 |
| FR-RG-003 | BO-012, BR-014 | US-5.2.1 |
| FR-RG-004 | BR-014 | US-5.1.2 |
| FR-RG-005 | BO-012 | US-5.1.1 |
| FR-RG-006 | BR-014 | US-5.1.1 |
| FR-FB-001 | BO-004, BR-006 | US-8.1.1 |
| FR-FB-002 | BO-004, BR-006 | US-8.2.1 |
| FR-FB-003 | BO-004, BR-006 | US-8.3.1 |
| FR-FB-004 | BO-004, BR-006 | US-8.4.1 |
| FR-FB-005 | BO-008 | US-8.1.1 |
| FR-CX-001 | BO-005, BR-005 | US-7.1.1 |
| FR-CX-002 | BO-005, BR-005 | US-7.2.1 |
| FR-CX-003 | BO-005, BR-005 | US-7.3.1 |
| FR-CX-004 | BO-005, BR-005 | US-7.4.1 |
| FR-CX-005 | BO-005, BR-005 | US-7.5.1 |
| FR-CX-006 | BO-005 | — |
| FR-PZ-001 | BO-003, BR-004 | US-6.1.1 |
| FR-PZ-002 | BO-003, BR-004 | US-6.1.2 |
| FR-PZ-003 | BO-003, BR-004 | US-6.2.1 |
| FR-PZ-004 | BO-003, BR-004 | US-6.3.1 |
| FR-PZ-005 | BO-003, BR-004 | — |
| FR-PZ-006 | BO-003, BR-004 | US-6.1.1 |
| FR-VC-001 | BO-008, BR-008 | US-9.1.1 |
| FR-VC-002 | BO-008, BC-007 | US-9.1.1 |
| FR-VC-003 | BO-008, BR-008 | US-9.2.1 |
| FR-VC-004 | BO-008 | — |
| FR-VC-005 | BO-008, BC-006 | — |
| FR-VC-006 | BO-008 | US-4.1.1 |
| FR-EX-001 | BR-009, BO-007 | US-10.1.1 |
| FR-EX-002 | BR-009, BO-007 | US-10.1.2 |
| FR-EX-003 | BR-009 | US-10.1.1 |
| FR-EX-004 | BR-009, BC-003 | US-10.1.1 |
| FR-EX-005 | BO-008 | US-10.1.1 |
| FR-PR-001 | BR-007, BR-016 | US-11.1.1 |
| FR-PR-002 | BR-007 | US-11.2.1 |
| FR-PR-003 | BR-007, BC-002 | — |
| FR-PR-004 | BC-006 | — |
| FR-PR-005 | BR-007 | — |
| FR-BT-001 | BC-004 | US-12.1.1 |
| FR-BT-002 | BC-004 | US-12.1.1 |
| FR-BT-003 | BC-004 | US-12.1.2 |
| FR-BT-004 | BC-004 | — |
| FR-AR-001 | BR-011 | US-13.1.1, US-13.1.2 |
| FR-AR-002 | BR-011 | US-13.2.1 |
| FR-AR-003 | BR-011 | — |
| FR-DS-001 | BR-011 | US-14.1.1 |
| FR-DS-002 | BR-011 | US-14.1.2 |
| FR-DS-003 | BR-011 | US-14.2.1 |
| FR-DS-004 | BR-011 | — |
| FR-JC-001 | BR-012, BO-010 | US-2.1.1 |
| FR-JC-002 | BR-012 | US-2.1.1 |
| FR-JC-003 | BR-012 | US-2.1.1 |
| FR-JC-004 | BR-012, BO-011 | US-2.1.1 |
| FR-JC-005 | BC-003 | — |
| FR-JC-006 | BO-011 | US-2.1.1 |
| FR-UM-001 | — | — |
| FR-UM-002 | — | — |
| FR-UM-003 | BC-002 | — |
| FR-UM-004 | BO-008 | — |
| FR-NE-001 | BO-011 | US-2.1.1 |
| FR-NE-002 | BO-011 | US-2.1.1 |

---

## 7. Open Questions

| ID | Question | Owner | Needed by |
|---|---|---|---|
| FR-OQ-1 | What is the default iteration cap per scope (course/module/section/block)? | AI Lead | M2 |
| FR-OQ-2 | What is the default per-job token budget? | AI Lead + DevOps | M2 |
| FR-OQ-3 | Should the platform support concurrent jobs per user, and what is the cap? | Backend Lead | M1 |
| FR-OQ-4 | How long are generations and their full agent traces retained? | DevOps + Sponsor | M0 |

---

## 8. Cross-References

- **Project Charter** — `01 Project Charter.md`
- **Business Requirements** — `02 Business Requirements Document.md`
- **Product Requirements** — `03 Product Requirements Document.md`
- **User Stories** — `06 User Stories.md`
- **Non-Functional Requirements** — `05 Non-Functional Requirements.md`
- **JSON Output Contract** — `02 Business Requirements Document.md` §11
- **ADRs** — `docs/adr/`
