# 06 User Stories

> Document type: User Stories Catalog
> Companion to: `01 Project Charter.md`, `02 Business Requirements Document.md`, `03 Product Requirements Document.md`, `04 Functional Requirements.md`, `05 Non-Functional Requirements.md`
> Status: Draft v0.1 · Owner: Product · Last updated: 2026-06-05
> This document is the implementation-ready story catalog. The PRD §6 contains
> the high-level epics and features; this document expands every story with
> full Given/When/Then acceptance criteria, dependencies, estimates, and
> traceability to functional (FR) and business (BR) requirements.

---

## 1. Document Control

| Field | Value |
|---|---|
| Project codename | CourseForge |
| Document version | 0.1 (Draft) |
| Author | Product Management |
| Reviewers | Engineering Leads, UX, QA |
| Approvers | Head of Product, Head of Engineering |
| Cadence | Updated at sprint planning |

---

## 2. Personas (summary — see PRD §4 for detail)

| ID | Name | Role |
|---|---|---|
| P-1 | Maria | Instructional Designer |
| P-2 | David | Subject Matter Expert |
| P-3 | Sofia | Independent Educator |
| P-4 | Alex | Content Operations Lead |
| P-5 | Riley | Reviewer / Editor |
| P-6 | Sponsor | Executive / sponsor |
| P-7 | Admin | DevOps / IT Admin |
| P-8 | AI Lead | AI Engineering |

---

## 3. Conventions

### 3.1 Story ID
`US-<EPIC>-<NNN>` where `<EPIC>` is the epic code from the PRD.

### 3.2 Story points
Fibonacci: 1, 2, 3, 5, 8, 13, 21.

### 3.3 Priority (MoSCoW)
- **M** — Must (MVP)
- **S** — Should (GA)
- **C** — Could (post-GA)
- **W** — Won't (this release)

### 3.4 Definition of Done (per story)
- Code implemented and merged.
- Unit tests pass; coverage meets NFR-MAINT-002.
- Integration or contract tests pass in CI.
- Acceptance criteria pass manual QA.
- Documentation updated (if user-facing change).
- Telemetry / metrics / structured logs added.
- UX review signed off (if user-facing change).
- Security review signed off (if security-relevant).
- The linked FR is met (verifiable per its `Verification` clause).

---

## 4. Story Map

| Epic | Must (MVP) | Should (GA) | Could (post-GA) |
|---|---|---|---|
| E1 Generation | US-1.1.1, 1.1.2, 1.1.3 | 1.2.1 | — |
| E2 Monitoring | US-2.1.1 | 2.1.2, 2.1.3, 2.1.4, 2.2.1 | — |
| E3 Review/Navigate | US-3.1.1, 3.1.3 | 3.1.2, 3.2.1, 3.2.2, 3.2.3 | — |
| E4 Editing | US-4.1.1, 4.1.2, 4.1.3, 4.2.1 | 4.1.4, 4.2.2, 4.5.1 | — |
| E5 Granular Regen | — | 5.1.1, 5.1.2, 5.1.3, 5.1.4, 5.2.1, 5.2.2, 5.3.1, 5.6.1 | — |
| E6 Personalization | US-6.1.1 | 6.1.2, 6.2.1, 6.3.1 | — |
| E7 Context Injection | — | 7.1.1, 7.2.1, 7.2.2, 7.3.1, 7.4.1, 7.5.1 | — |
| E8 Feedback | — | 8.1.1, 8.2.1, 8.3.1, 8.4.1 | — |
| E9 Versioning | — | 9.1.1, 9.1.2, 9.2.1, 9.3.1 | — |
| E10 Export | — | 10.1.1, 10.1.2, 10.2.1 | — |
| E11 Provider | US-11.1.1, 11.2.1 | 11.1.2 | — |
| E12 Block Extensibility | — | — | 12.1.1, 12.1.2 |
| E13 Curriculum Review | — | — | 13.1.1, 13.1.2, 13.2.1 |
| E14 Dashboard | — | 14.1.1, 14.1.2, 14.2.1 | — |

---

## 5. Stories by Epic

### Epic E1 — Course Generation Request

#### US-1.1.1 — Generate a course from a topic
- **Persona:** Maria (P-1)
- **Priority:** M · **Points:** 8
- **As a:** Maria · **I want:** to start a new course by entering a topic and basic parameters · **So that:** I can get a structured draft without filling in a long form
- **Description:** The user opens "New Course", enters a topic (min 3 characters), selects audience and difficulty, adds ≥ 1 learning outcome, and clicks Generate. The system creates a job and routes to the monitoring view.
- **Acceptance Criteria:**
  - **AC-1** — *Given I am on "New Course", when I enter a topic of ≥ 3 chars and click Generate, then a `job_id` is returned and I am routed to the monitoring view within 1 s.*
  - **AC-2** — *Given required fields are empty, when I view the form, then the Generate button is disabled and a tooltip names the missing field.*
  - **AC-3** — *Given the job is created, when I refresh the monitoring page, then I am returned to the same job (no duplicate job).*
  - **AC-4** — *Given a generation completes, when the result is returned, then the JSON document validates against the published `schema_version` (FR-JC-001).*
- **Dependencies:** FR-CG-001, FR-CG-003, FR-CG-004, FR-JC-001, FR-AG-001.
- **Related BR:** BR-001, BO-001.

#### US-1.1.2 — Specify learning outcomes up front
- **Persona:** Sofia (P-3)
- **Priority:** M · **Points:** 3
- **As a:** Sofia · **I want:** to specify learning outcomes when creating a course · **So that:** the generated course is aligned with what my students should achieve
- **Acceptance Criteria:**
  - **AC-1** — *Given I am on the New Course form, when I click "Add outcome", then a new text field appears.*
  - **AC-2** — *Given I add 0 outcomes, when I click Generate, then the system rejects the request with a clear message (FR-CG-003).*
  - **AC-3** — *Given I add N outcomes, when the course is generated, then the `outcome_coverage` map lists at least one section per outcome (FR-CS-006).*
- **Dependencies:** FR-CG-003, FR-CS-005, FR-CS-006, FR-CX-005.
- **Related BR:** BR-004, BO-002.

#### US-1.1.3 — Attach an existing document as context
- **Persona:** David (P-2)
- **Priority:** S · **Points:** 5
- **As a:** David · **I want:** to attach an existing document as context · **So that:** the generated course reflects my company's standards
- **Acceptance Criteria:**
  - **AC-1** — *Given I click "Attach document", when I select a supported file (PDF/MD/TXT), then a confirmation appears with a short auto-generated summary.*
  - **AC-2** — *Given the file is unsupported or too large, when I attempt to upload, then the system rejects it with a clear error (NFR-SEC-005).*
  - **AC-3** — *Given the document is ingested, when the course is generated, then the document's content is reflected in the produced material (spot-checkable) and the document is recorded in `generation.context_documents` (FR-CX-002).*
- **Dependencies:** FR-CX-002, NFR-SEC-005.
- **Related BR:** BR-005, BO-005.

#### US-1.2.1 — Start from a quick-start template
- **Persona:** Sofia (P-3)
- **Priority:** S · **Points:** 3
- **As a:** Sofia · **I want:** to start from a template · **So that:** I don't re-enter the same defaults for every course
- **Acceptance Criteria:**
  - **AC-1** — *Given I am on "New Course", when I select a template, then the form is pre-filled with that template's values (FR-CG-002).*
  - **AC-2** — *Given a template is applied, when I click Generate, then the request body matches the (overridden) values, not the template defaults.*
- **Dependencies:** FR-CG-002.
- **Related BR:** BO-001.

---

### Epic E2 — Generation Monitoring

#### US-2.1.1 — See live agent status during generation
- **Persona:** Maria (P-1)
- **Priority:** M · **Points:** 5
- **As a:** Maria · **I want:** to see what's happening while the AI is working · **So that:** I trust the system and know roughly how long it will take
- **Acceptance Criteria:**
  - **AC-1** — *Given a job is running, when I view the monitoring page, then I see a list of agents and the current phase (e.g. "SectionAuthor — section 3 of 8") updating at least every 2 s (NFR-PERF-002).*
  - **AC-2** — *Given the job terminates, when I view the page, then I see the termination reason explicitly (`quality_threshold | max_iterations | budget_exhausted | user_aborted`) (FR-AG-010).*
  - **AC-3** — *Given I close the browser during generation, when I return, then the monitoring view reconnects and shows current state (no new job is started).*
- **Dependencies:** FR-AG-001, FR-AG-010, FR-JC-003, FR-JC-006.
- **Related BR:** BR-010, BR-012, BO-011.

#### US-2.1.2 — See per-iteration quality scores
- **Persona:** Alex (P-4)
- **Priority:** S · **Points:** 3
- **As a:** Alex · **I want:** to see per-iteration quality scores · **So that:** I can confirm the system is actually improving the draft
- **Acceptance Criteria:**
  - **AC-1** — *Given a job has ≥ 1 refinement iteration, when I view the monitoring page, then I see a small line chart of overall quality score per iteration (FR-EV-005).*
  - **AC-2** — *Given the job completes, when I view the final report, then `evaluation.iteration_scores` lists one entry per iteration.*
- **Dependencies:** FR-EV-001, FR-EV-005, FR-JC-001.
- **Related BR:** BR-013, BO-011.

#### US-2.1.3 — Cancel a running job
- **Persona:** Maria (P-1)
- **Priority:** S · **Points:** 2
- **As a:** Maria · **I want:** to cancel a running job · **So that:** I can stop a generation that is going in the wrong direction or is taking too long
- **Acceptance Criteria:**
  - **AC-1** — *Given a job is running, when I click "Cancel", then the job terminates with `termination_reason=user_aborted`.*
  - **AC-2** — *Given the job has terminated, when I view the result, then partial results are preserved and visible.*
- **Dependencies:** FR-AG-010, FR-NE-001.
- **Related BR:** BR-010, BO-012.

#### US-2.1.4 — See a per-iteration cost breakdown
- **Persona:** Alex (P-4)
- **Priority:** S · **Points:** 3
- **As a:** Alex · **I want:** to see token spend per job, per agent, per iteration · **So that:** I can control cost across my team
- **Acceptance Criteria:**
  - **AC-1** — *Given a job is running, when I view the monitoring page, then I see input tokens, output tokens, and a per-iteration breakdown (NFR-COST-004).*
  - **AC-2** — *Given a job has completed, when I view the detail page, then the per-agent token usage and total cost are shown.*
- **Dependencies:** FR-JC-003, NFR-COST-004.
- **Related BR:** BO-011.

#### US-2.2.1 — See a notification on job completion
- **Persona:** Riley (P-5)
- **Priority:** S · **Points:** 2
- **As a:** Riley · **I want:** to be notified when a job completes · **So that:** I can move to review without polling
- **Acceptance Criteria:**
  - **AC-1** — *Given a job of mine completes, when I am on any page, then an in-app notification appears (FR-NE-001).*
  - **AC-2** — *Given the job failed terminally, when the notification appears, then it includes the structured failure reason (FR-NE-002).*
- **Dependencies:** FR-NE-001, FR-NE-002.
- **Related BR:** BO-011.

---

### Epic E3 — Course Review & Navigation

#### US-3.1.1 — View the course structure as a tree
- **Persona:** Maria (P-1)
- **Priority:** M · **Points:** 5
- **As a:** Maria · **I want:** to see the course structure at a glance · **So that:** I can decide which sections to focus on first
- **Acceptance Criteria:**
  - **AC-1** — *Given I open a course, when I view the curriculum tree, then I see all modules, sections, and blocks in a collapsible hierarchy in the correct order (FR-CS-001, FR-CS-002).*
  - **AC-2** — *Given the course has 200 blocks, when I open the tree, then it renders in ≤ 1 s on a mid-range laptop (NFR-PERF-004).*
  - **AC-3** — *Given a block has outstanding issues, when I view the tree, then the block node shows a warning icon and the issue category on hover (FR-EV-004).*
- **Dependencies:** FR-CS-001, FR-CS-002, FR-EV-004.
- **Related BR:** BR-002, BO-002.

#### US-3.1.2 — Filter the tree by issue severity
- **Persona:** Riley (P-5)
- **Priority:** S · **Points:** 3
- **As a:** Riley · **I want:** to filter the tree by issue severity · **So that:** I can focus on blockers first
- **Acceptance Criteria:**
  - **AC-1** — *Given I am on the tree, when I select "blockers", then only nodes with `severity=blocker` are highlighted.*
  - **AC-2** — *Given I clear the filter, when the tree re-renders, then all nodes are visible again.*
- **Dependencies:** FR-EV-004.
- **Related BR:** BO-011.

#### US-3.1.3 — Click a block to see its rendered content
- **Persona:** Maria (P-1)
- **Priority:** M · **Points:** 3
- **As a:** Maria · **I want:** to click a block and see its content rendered properly · **So that:** I can review the actual material
- **Acceptance Criteria:**
  - **AC-1** — *Given I click a block, when the selection changes, then the right pane shows the block content rendered with the type-specific component (FR-ED-002).*
  - **AC-2** — *Given a Code block is selected, when the right pane renders, then syntax highlighting is applied per the `language` field.*
- **Dependencies:** FR-ED-002, FR-BL-002.
- **Related BR:** BR-003, BO-002.

#### US-3.2.1 — Read a section end-to-end
- **Persona:** Sofia (P-3)
- **Priority:** S · **Points:** 5
- **As a:** Sofia · **I want:** to read a generated section naturally · **So that:** I can judge quality and flow
- **Acceptance Criteria:**
  - **AC-1** — *Given I am reading a section, when blocks are rendered, then each block uses the type-specific renderer (FR-ED-002).*
  - **AC-2** — *Given the section has a Quiz block, when I view it, then the quiz is rendered as a real assessment component (selectable choices, feedback on answer).*
- **Dependencies:** FR-ED-002, FR-BL-006.
- **Related BR:** BR-003, BO-002.

#### US-3.2.2 — Take a quiz inline
- **Persona:** Sofia (P-3)
- **Priority:** S · **Points:** 3
- **As a:** Sofia · **I want:** to take a quiz inline while reading · **So that:** I can validate the quiz from a learner's perspective
- **Acceptance Criteria:**
  - **AC-1** — *Given a Quiz block is rendered, when I select a choice and submit, then feedback (`explanation`) is shown and the correctness indicator is displayed.*
- **Dependencies:** FR-BL-006.
- **Related BR:** BR-003.

#### US-3.2.3 — Toggle a solution reveal
- **Persona:** David (P-2)
- **Priority:** S · **Points:** 2
- **As a:** David · **I want:** to reveal a solution only when I want it · **So that:** I can use exercises for actual practice
- **Acceptance Criteria:**
  - **AC-1** — *Given an Exercise block has a `solution_ref`, when I click "Show solution", then the Solution block is revealed (FR-BL-005).*
- **Dependencies:** FR-BL-005.
- **Related BR:** BR-003.

---

### Epic E4 — Block-Level Editing

#### US-4.1.1 — Edit a Concept block
- **Persona:** David (P-2)
- **Priority:** M · **Points:** 5
- **As a:** David · **I want:** to fix a technical inaccuracy in a Concept block · **So that:** the course reflects correct information
- **Acceptance Criteria:**
  - **AC-1** — *Given I am in edit mode on a Concept block, when I change `markdown` and click Save, then a new version is created and the previous version is preserved (FR-ED-001, FR-VC-006).*
  - **AC-2** — *Given I saved an edit, when I view the block, its content matches exactly what I entered — no silent AI rewrite (FR-ED-003).*
  - **AC-3** — *Given I have unsaved changes, when I navigate away, then I am warned (FR-ED-004).*
  - **AC-4** — *Given the edit is saved, when I view the new version, then `last_modified_by`, source (`manual_edit`), and timestamp are recorded (FR-ED-005).*
- **Dependencies:** FR-ED-001, FR-ED-003, FR-ED-004, FR-ED-005, FR-VC-006.
- **Related BR:** BR-001, BO-008, BC-001.

#### US-4.1.2 — Edit a Code block
- **Persona:** Riley (P-5)
- **Priority:** M · **Points:** 5
- **As a:** Riley · **I want:** to edit a Code block with a code editor · **So that:** I can fix syntax issues and add comments
- **Acceptance Criteria:**
  - **AC-1** — *Given I am editing a Code block, when the language is set, the editor provides syntax highlighting (FR-ED-002).*
  - **AC-2** — *Given I save, the new version validates against the Code block JSON Schema (FR-BL-002).*
- **Dependencies:** FR-ED-002, FR-BL-002, FR-BL-007.
- **Related BR:** BR-003, BC-003.

#### US-4.1.3 — Edit a Quiz block
- **Persona:** Riley (P-5)
- **Priority:** M · **Points:** 5
- **As a:** Riley · **I want:** to edit a Quiz block with a structured editor · **So that:** I can add questions, choices, and explanations
- **Acceptance Criteria:**
  - **AC-1** — *Given I add a question, when I save, then I can define ≥ 2 choices, mark the correct `answer_index`, and write an `explanation` (FR-BL-006).*
  - **AC-2** — *Given I save an invalid quiz, the editor prevents save and shows a validation message.*
- **Dependencies:** FR-BL-006, FR-ED-002.
- **Related BR:** BR-003.

#### US-4.1.4 — Edit a Key Points block
- **Persona:** Riley (P-5)
- **Priority:** S · **Points:** 2
- **As a:** Riley · **I want:** to edit a Key Points list · **So that:** I can refine the summary
- **Acceptance Criteria:**
  - **AC-1** — *Given I am editing a Key Points block, when I add/remove/reorder items, the new version validates against the block's JSON Schema (FR-BL-002).*
- **Dependencies:** FR-BL-002.
- **Related BR:** BR-003.

#### US-4.2.1 — Manual edits are not silently re-evaluated
- **Persona:** David (P-2)
- **Priority:** M · **Points:** 2
- **As a:** David · **I want:** my manual edits saved verbatim · **So that:** the system does not "correct" what I just fixed
- **Acceptance Criteria:**
  - **AC-1** — *Given I saved a manual edit, when I view the block, its content matches what I entered exactly (FR-ED-003).*
  - **AC-2** — *Given I want a quality check, when I click "Re-evaluate block", then the Evaluator runs and reports issues (FR-EV-001).*
- **Dependencies:** FR-ED-003, FR-EV-001.
- **Related BR:** BC-001, BO-008.

#### US-4.2.2 — Re-evaluate a single block on demand
- **Persona:** Riley (P-5)
- **Priority:** S · **Points:** 3
- **As a:** Riley · **I want:** to re-evaluate a block I just edited · **So that:** I can confirm it still passes the rubric
- **Acceptance Criteria:**
  - **AC-1** — *Given I click "Re-evaluate", then the Evaluator scores the current block and any issues appear in the block panel (FR-EV-001, FR-EV-004).*
  - **AC-2** — *Given the re-evaluation finishes, then the `evaluation` object on the block version is updated.*
- **Dependencies:** FR-EV-001, FR-EV-004.
- **Related BR:** BR-011.

#### US-4.5.1 — See who edited a block and when
- **Persona:** Alex (P-4)
- **Priority:** S · **Points:** 2
- **As a:** Alex · **I want:** to see who edited a block and when · **So that:** I can audit the course's evolution
- **Acceptance Criteria:**
  - **AC-1** — *Given I open the version history for a block, when it loads, then I see a chronological list with timestamp, author (human or AI), and source (FR-VC-001, FR-ED-005).*
- **Dependencies:** FR-VC-001, FR-ED-005.
- **Related BR:** BO-008.

---

### Epic E5 — Granular Regeneration

#### US-5.1.1 — Regenerate a single block
- **Persona:** Riley (P-5)
- **Priority:** S · **Points:** 5
- **As a:** Riley · **I want:** to regenerate only the Exercise block that has a clarity issue · **So that:** I don't risk breaking other content
- **Acceptance Criteria:**
  - **AC-1** — *Given I am viewing a block with an issue, when I click Regenerate, only that block is sent through the refinement loop (FR-RG-001).*
  - **AC-2** — *Given the regeneration completes, I see the previous and new version side by side with the Evaluator's score for each (FR-RG-004).*
  - **AC-3** — *Given I click Accept, the new version becomes current and the previous is moved to history (FR-RG-005, FR-VC-006).*
  - **AC-4** — *Given I click Discard, the new version is preserved in history but the previous remains current (FR-RG-005).*
- **Dependencies:** FR-RG-001, FR-RG-004, FR-RG-005, FR-RG-006.
- **Related BR:** BO-012, BR-014.

#### US-5.1.2 — Side-by-side comparison of old and new
- **Persona:** Maria (P-1)
- **Priority:** S · **Points:** 5
- **As a:** Maria · **I want:** to see the old and new version of a block side by side · **So that:** I can decide which one to keep
- **Acceptance Criteria:**
  - **AC-1** — *Given a regeneration completes, both versions are shown with diff highlighting and the Evaluator score for each (FR-RG-004).*
  - **AC-2** — *Given I am comparing a Code block, syntax highlighting is preserved on both sides.*
- **Dependencies:** FR-RG-004, FR-VC-003.
- **Related BR:** BO-012.

#### US-5.1.3 — Targeted regeneration does not touch the rest
- **Persona:** David (P-2)
- **Priority:** S · **Points:** 3
- **As a:** David · **I want:** confidence that regenerating one block won't quietly change other blocks · **So that:** my previously reviewed content stays intact
- **Acceptance Criteria:**
  - **AC-1** — *Given I regenerate block B, when the job completes, the version IDs of all other blocks are unchanged (verifiable in history) (FR-RG-001, FR-VC-006).*
- **Dependencies:** FR-RG-001, FR-VC-006.
- **Related BR:** BO-012.

#### US-5.1.4 — Targeted regen runs the same evaluate–refine loop
- **Persona:** Riley (P-5)
- **Priority:** S · **Points:** 3
- **As a:** Riley · **I want:** targeted regeneration to also self-refine · **So that:** the new block passes the same rubric
- **Acceptance Criteria:**
  - **AC-1** — *Given a targeted regeneration runs, when the Evaluator reports issues, the Refiner is invoked and the loop continues until pass / cap / budget (FR-RG-006).*
  - **AC-2** — *Given the loop terminates, the per-iteration scores are visible for the targeted scope.*
- **Dependencies:** FR-RG-006, FR-AG-010.
- **Related BR:** BR-014.

#### US-5.2.1 — Regenerate a section
- **Persona:** Sofia (P-3)
- **Priority:** S · **Points:** 5
- **As a:** Sofia · **I want:** to regenerate an entire section · **So that:** I can apply a new instructional style
- **Acceptance Criteria:**
  - **AC-1** — *Given I select a section and click Regenerate, only the blocks within that section are rewritten and re-evaluated (FR-RG-002).*
  - **AC-2** — *Given the section-level regeneration completes, the side-by-side comparison shows the section as a whole.*
- **Dependencies:** FR-RG-002, FR-RG-006.
- **Related BR:** BO-012, BR-014.

#### US-5.2.2 — Regenerate a module
- **Persona:** Sofia (P-3)
- **Priority:** S · **Points:** 5
- **As a:** Sofia · **I want:** to regenerate an entire module · **So that:** I can pivot the whole thematic area at once
- **Acceptance Criteria:**
  - **AC-1** — *Given I select a module and click Regenerate, only sections and blocks within that module are regenerated (FR-RG-003).*
- **Dependencies:** FR-RG-003.
- **Related BR:** BO-012, BR-014.

#### US-5.3.1 — Verify other blocks are untouched
- **Persona:** David (P-2)
- **Priority:** S · **Points:** 2
- **As a:** David · **I want:** to verify a regeneration did not change other blocks · **So that:** I have auditable assurance
- **Acceptance Criteria:**
  - **AC-1** — *Given I open version history, when I compare the "before" and "after" of a targeted regen, only the target aggregate has new versions (FR-RG-001, FR-RG-002, FR-RG-003, FR-VC-006).*
- **Dependencies:** FR-RG-001, FR-VC-006.
- **Related BR:** BO-012.

#### US-5.6.1 — Cancel a targeted regeneration
- **Persona:** Riley (P-5)
- **Priority:** S · **Points:** 2
- **As a:** Riley · **I want:** to cancel a running targeted regeneration · **So that:** I can stop work that's going in the wrong direction
- **Acceptance Criteria:**
  - **AC-1** — *Given a targeted regen is running, when I click Cancel, the job terminates with `user_aborted` and partial results are preserved (FR-AG-010).*
- **Dependencies:** FR-AG-010.
- **Related BR:** BO-012.

---

### Epic E6 — Personalization Controls

#### US-6.1.1 — Set audience and difficulty on a new course
- **Persona:** Maria (P-1)
- **Priority:** M · **Points:** 3
- **As a:** Maria · **I want:** to set the audience to "Engineers" and difficulty to "Intermediate" · **So that:** the generated content is calibrated correctly
- **Acceptance Criteria:**
  - **AC-1** — *Given I set the audience and difficulty, when I save, the values are persisted on the course (FR-PZ-001).*
  - **AC-2** — *Given the values are set, when a generation runs, they appear in the `GenerationContext` (FR-AG-002).*
  - **AC-3** — *Given I select an unknown profile, the system rejects it (FR-PZ-006).*
- **Dependencies:** FR-PZ-001, FR-PZ-006, FR-AG-002.
- **Related BR:** BR-004, BO-003.

#### US-6.1.2 — Override depth on a single module
- **Persona:** David (P-2)
- **Priority:** S · **Points:** 3
- **As a:** David · **I want:** to mark the depth as "Industry-Oriented" for a specific module · **So that:** the rest of the course can stay academic
- **Acceptance Criteria:**
  - **AC-1** — *Given I override depth on module M, when M is regenerated, the override applies to M only (FR-PZ-002).*
  - **AC-2** — *Given sibling modules are not regenerated, their depth setting is unchanged.*
- **Dependencies:** FR-PZ-002.
- **Related BR:** BR-004, BO-003.

#### US-6.2.1 — Define a block composition rule
- **Persona:** Sofia (P-3)
- **Priority:** S · **Points:** 3
- **As a:** Sofia · **I want:** to specify that every section should include a Concept, Example, Exercise, and Key Points block · **So that:** the structure is consistent
- **Acceptance Criteria:**
  - **AC-1** — *Given I configure a composition rule, when a section is generated, the section contains at least the configured block types in the configured order (FR-PZ-003).*
- **Dependencies:** FR-PZ-003, FR-AG-004.
- **Related BR:** BR-004, BO-003.

#### US-6.3.1 — Choose an instructional strategy
- **Persona:** Maria (P-1)
- **Priority:** S · **Points:** 3
- **As a:** Maria · **I want:** to choose "example-driven" as the instructional strategy · **So that:** the generated course leads with worked examples
- **Acceptance Criteria:**
  - **AC-1** — *Given I set the strategy, when a course is generated, the resulting blocks reflect that strategy (verifiable by spot-check) (FR-PZ-004).*
- **Dependencies:** FR-PZ-004, FR-AG-005.
- **Related BR:** BR-004, BO-003.

---

### Epic E7 — Context Injection

#### US-7.1.1 — Add a free-form text instruction
- **Persona:** Maria (P-1)
- **Priority:** S · **Points:** 3
- **As a:** Maria · **I want:** to write a note like "Always include a real-world case study in the introduction of each module" · **So that:** the AI honors that across the course
- **Acceptance Criteria:**
  - **AC-1** — *Given I enter an instruction, when a course is generated, the instruction is in the `GenerationContext` and visible in the generation metadata (FR-CX-001).*
- **Dependencies:** FR-CX-001, FR-AG-002.
- **Related BR:** BR-005, BO-005.

#### US-7.2.1 — Upload a document
- **Persona:** David (P-2)
- **Priority:** S · **Points:** 5
- **As a:** David · **I want:** to upload our internal "Engineering Standards" PDF · **So that:** generated courses use our terminology and patterns
- **Acceptance Criteria:**
  - **AC-1** — *Given I upload a supported file, ingestion completes and a short summary is shown (FR-CX-002).*
  - **AC-2** — *Given the file is unsupported or oversized, the system rejects it with a clear error (NFR-SEC-005).*
- **Dependencies:** FR-CX-002, NFR-SEC-005.
- **Related BR:** BR-005, BO-005.

#### US-7.2.2 — Verify document influence in the course
- **Persona:** David (P-2)
- **Priority:** S · **Points:** 3
- **As a:** David · **I want:** the generated course to reflect the uploaded document · **So that:** I know the document actually shaped the output
- **Acceptance Criteria:**
  - **AC-1** — *Given a document is uploaded, when the course is generated, the document's content is reflected in the produced material (e.g. specific terms appear, specific patterns are used) (FR-CX-002).*
- **Dependencies:** FR-CX-002.
- **Related BR:** BR-005.

#### US-7.3.1 — Attach a reference course
- **Persona:** Sofia (P-3)
- **Priority:** S · **Points:** 5
- **As a:** Sofia · **I want:** to attach a previous course of mine as a reference · **So that:** the new course has the same pacing and pedagogical style
- **Acceptance Criteria:**
  - **AC-1** — *Given I attach a reference course, when the new course is generated, the structure (module count, section types, pacing) is visibly influenced by the reference (FR-CX-003).*
  - **AC-2** — *Given the reference is attached, the new course does not contain copied prose from the reference.*
- **Dependencies:** FR-CX-003, FR-AG-002.
- **Related BR:** BR-005, BO-005.

#### US-7.4.1 — Inject a domain knowledge item
- **Persona:** Alex (P-4)
- **Priority:** S · **Points:** 3
- **As a:** Alex · **I want:** to inject "We use AWS, not GCP, as our default cloud" · **So that:** examples consistently use AWS
- **Acceptance Criteria:**
  - **AC-1** — *Given I add a domain knowledge item, when the course is generated, examples in the new course use AWS by default (where cloud examples appear) (FR-CX-004).*
- **Dependencies:** FR-CX-004.
- **Related BR:** BR-005, BO-005.

#### US-7.5.1 — Define measurable learning outcomes
- **Persona:** Sofia (P-3)
- **Priority:** S · **Points:** 3
- **As a:** Sofia · **I want:** to list 3–5 learning outcomes · **So that:** the course is structured around achieving them
- **Acceptance Criteria:**
  - **AC-1** — *Given I have defined N outcomes, the curriculum's sections collectively cover each (FR-CS-006, FR-CX-005).*
- **Dependencies:** FR-CS-006, FR-CX-005.
- **Related BR:** BR-005, BO-005.

---

### Epic E8 — Feedback at All Levels

#### US-8.1.1 — Add block-level feedback
- **Persona:** Riley (P-5)
- **Priority:** S · **Points:** 3
- **As a:** Riley · **I want:** to write a comment on a specific Example block · **So that:** the next regeneration of that block addresses my note
- **Acceptance Criteria:**
  - **AC-1** — *Given I attach feedback to a block, when I click Regenerate, the new version addresses the feedback (verifiable by reading the new content) (FR-FB-001).*
  - **AC-2** — *Given feedback is submitted, it appears in the feedback history tied to the iteration that consumed it (FR-FB-005).*
- **Dependencies:** FR-FB-001, FR-FB-005, FR-RG-001.
- **Related BR:** BR-006, BO-004.

#### US-8.2.1 — Add section-level feedback
- **Persona:** Maria (P-1)
- **Priority:** S · **Points:** 3
- **As a:** Maria · **I want:** to write feedback on a section · **So that:** the section as a whole can be refined
- **Acceptance Criteria:**
  - **AC-1** — *Given I attach section feedback, when I click Regenerate, all blocks within that section are revised (FR-FB-002).*
  - **AC-2** — *Given the regeneration completes, no block outside the section is changed (FR-FB-002, FR-RG-002).*
- **Dependencies:** FR-FB-002, FR-RG-002.
- **Related BR:** BR-006, BO-004.

#### US-8.3.1 — Add curriculum-level feedback
- **Persona:** Alex (P-4)
- **Priority:** S · **Points:** 5
- **As a:** Alex · **I want:** to suggest "Add a deployment module" at the curriculum level · **So that:** the structure can be adjusted before content is regenerated
- **Acceptance Criteria:**
  - **AC-1** — *Given I attach curriculum feedback, when I click Regenerate, the new course skeleton is presented in a diff view before any section content is regenerated (FR-FB-003).*
  - **AC-2** — *Given I approve the new skeleton, section content is then regenerated; if I reject, no content is changed.*
- **Dependencies:** FR-FB-003, FR-AG-003.
- **Related BR:** BR-006, BO-004.

#### US-8.4.1 — Add global feedback
- **Persona:** Maria (P-1)
- **Priority:** S · **Points:** 3
- **As a:** Maria · **I want:** to add a global note "Add more analogies" · **So that:** the entire course is consistent in style
- **Acceptance Criteria:**
  - **AC-1** — *Given I attach a global note, when I click Apply globally, all blocks are re-evaluated and revised where the note applies (FR-FB-004).*
  - **AC-2** — *Given the global apply completes, the operation is reversible from version history (FR-FB-004, FR-VC-004).*
- **Dependencies:** FR-FB-004, FR-VC-004.
- **Related BR:** BR-006, BO-004.

---

### Epic E9 — Version History & Comparison

#### US-9.1.1 — View the version history of a block
- **Persona:** Alex (P-4)
- **Priority:** S · **Points:** 3
- **As a:** Alex · **I want:** to see when each block was last edited and by whom · **So that:** I can audit the course's evolution
- **Acceptance Criteria:**
  - **AC-1** — *Given I open the history for a block, I see a chronological list with timestamp, author, source, and quality score (FR-VC-001, FR-ED-005).*
  - **AC-2** — *Given I am at the course level, when I select a version, I can drill down to the block-level diff (FR-VC-001).*
- **Dependencies:** FR-VC-001, FR-ED-005.
- **Related BR:** BR-008, BO-008.

#### US-9.1.2 — View a course-level version timeline
- **Persona:** Alex (P-4)
- **Priority:** S · **Points:** 3
- **As a:** Alex · **I want:** to see the course's version timeline · **So that:** I can identify when structural changes happened
- **Acceptance Criteria:**
  - **AC-1** — *Given I open course history, I see a timeline showing structural events (planner runs, section regenerations, manual edits) and the version of the course at each event (FR-VC-001).*
- **Dependencies:** FR-VC-001.
- **Related BR:** BO-008.

#### US-9.2.1 — Compare two versions of a block
- **Persona:** Riley (P-5)
- **Priority:** S · **Points:** 5
- **As a:** Riley · **I want:** to compare the current and previous version of a block · **So that:** I can review what the AI changed
- **Acceptance Criteria:**
  - **AC-1** — *Given I select two versions, both are shown side by side with character-level diff highlighting for text and structural diff for arrays/objects (FR-VC-003).*
- **Dependencies:** FR-VC-003.
- **Related BR:** BR-008.

#### US-9.3.1 — Roll back a block
- **Persona:** Riley (P-5)
- **Priority:** S · **Points:** 3
- **As a:** Riley · **I want:** to restore a previous version of a block · **So that:** I can revert an unwanted change
- **Acceptance Criteria:**
  - **AC-1** — *Given I am viewing a previous version, when I click "Restore", the current version is replaced and the previous version is preserved (FR-VC-004, FR-VC-006).*
  - **AC-2** — *Given the restore completes, the rollback is recorded as an event in the history (FR-VC-004).*
- **Dependencies:** FR-VC-004.
- **Related BR:** BO-008.

---

### Epic E10 — Export & Publishing

#### US-10.1.1 — Export to Markdown
- **Persona:** Sofia (P-3)
- **Priority:** S · **Points:** 3
- **As a:** Sofia · **I want:** to export a course to Markdown · **So that:** I can publish it on my own platform
- **Acceptance Criteria:**
  - **AC-1** — *Given I select Markdown export, I receive a valid Markdown document (or a zip of one file per section) where block types map to appropriate Markdown structures (FR-EX-001).*
  - **AC-2** — *Given the export includes a Quiz block, the question and choices are preserved (FR-EX-004).*
- **Dependencies:** FR-EX-001, FR-EX-004.
- **Related BR:** BR-009, BO-007.

#### US-10.1.2 — Export to PDF
- **Persona:** Sofia (P-3)
- **Priority:** S · **Points:** 5
- **As a:** Sofia · **I want:** to export a course to PDF · **So that:** I can distribute it as a printable artifact
- **Acceptance Criteria:**
  - **AC-1** — *Given I select PDF export, I receive a PDF whose visual layout matches the section reading view (FR-EX-002).*
  - **AC-2** — *Given the export runs, the provenance header is present (FR-EX-005).*
- **Dependencies:** FR-EX-002, FR-EX-005.
- **Related BR:** BR-009.

#### US-10.2.1 — Be warned of blockers before export
- **Persona:** Riley (P-5)
- **Priority:** S · **Points:** 2
- **As a:** Riley · **I want:** to be warned about blocker issues before export · **So that:** I can fix or knowingly override them
- **Acceptance Criteria:**
  - **AC-1** — *Given I click Export, when any blocker issue exists, I am shown the blockers and offered "Export anyway" or "Fix first" (FR-EX-003).*
- **Dependencies:** FR-EX-003, FR-EV-004.
- **Related BR:** BR-009.

---

### Epic E11 — Provider Configuration

#### US-11.1.1 — Configure providers and per-agent models (admin)
- **Persona:** Admin (P-7)
- **Priority:** M · **Points:** 5
- **As a:** DevOps · **I want:** to set the default Evaluator model to one provider and the default Author model to another · **So that:** we balance cost and quality
- **Acceptance Criteria:**
  - **AC-1** — *Given I am an admin, when I open Provider Configuration, then I can see a list of configured providers and a per-agent model assignment table (FR-PR-001, FR-AG-014).*
  - **AC-2** — *Given I change a per-agent model, when a new generation is run, the agent trace shows the new model (FR-JC-003, FR-AG-014).*
- **Dependencies:** FR-PR-001, FR-AG-014, FR-JC-003.
- **Related BR:** BR-007, BR-016, BO-006.

#### US-11.1.2 — Swap providers without code changes
- **Persona:** AI Lead (P-8)
- **Priority:** S · **Points:** 3
- **As a:** AI Lead · **I want:** to swap the configured provider · **So that:** I can test a new model without code changes
- **Acceptance Criteria:**
  - **AC-1** — *Given I swap the configured provider, when a regeneration run completes, no agent code, prompt, or rubric was changed (FR-AG-013, NFR-MAINT-001).*
- **Dependencies:** FR-AG-013, NFR-MAINT-001.
- **Related BR:** BR-007, BR-016.

#### US-11.2.1 — End users never see provider choice
- **Persona:** Maria (P-1)
- **Priority:** M · **Points:** 2
- **As a:** Maria · **I want:** a single, consistent product · **So that:** I don't have to think about providers
- **Acceptance Criteria:**
  - **AC-1** — *Given I am a non-admin user, when I generate a course, then I do not see any provider selection UI; provider choice is made by configuration (FR-PR-002).*
- **Dependencies:** FR-PR-002.
- **Related BR:** BR-007.

---

### Epic E12 — Block-Type Extensibility

#### US-12.1.1 — Register a new block type (admin)
- **Persona:** Product (P-6)
- **Priority:** C · **Points:** 5
- **As a:** Product Manager · **I want:** to add a "Flashcard" block type without an engineering release · **So that:** we can experiment quickly
- **Acceptance Criteria:**
  - **AC-1** — *Given I am an admin, when I register a new block type with a valid JSON-Schema, then the type becomes available in the curriculum tree and the section composer within the same session (FR-BT-001).*
  - **AC-2** — *Given I submit an invalid registration (bad schema, missing fields, name collision), then the system rejects it with a structured error (FR-BT-002).*
- **Dependencies:** FR-BT-001, FR-BT-002.
- **Related BR:** BC-004.

#### US-12.1.2 — Evaluator supports custom block types
- **Persona:** AI Lead (P-8)
- **Priority:** C · **Points:** 3
- **As a:** AI Lead · **I want:** custom block types to be scorable by the Evaluator · **So that:** quality is enforced for new types too
- **Acceptance Criteria:**
  - **AC-1** — *Given a custom type is registered, when the Evaluator runs, it scores blocks of the new type using the registered schema as a structural check (FR-BT-003).*
- **Dependencies:** FR-BT-003.
- **Related BR:** BC-004.

---

### Epic E13 — AI-Assisted Curriculum Review

#### US-13.1.1 — Get a pre-generation review
- **Persona:** Maria (P-1)
- **Priority:** C · **Points:** 3
- **As a:** Maria · **I want:** to be warned that my course on "Microservices" may be missing "Observability" · **So that:** I can add it as a topic before generation
- **Acceptance Criteria:**
  - **AC-1** — *Given I am on the "New Course" page with parameters filled in, when I click "Review", then I see a list of AI-generated recommendations (FR-AR-001).*
- **Dependencies:** FR-AR-001.
- **Related BR:** BR-011.

#### US-13.1.2 — See outcome-difficulty mismatch
- **Persona:** Sofia (P-3)
- **Priority:** C · **Points:** 2
- **As a:** Sofia · **I want:** to be told that my defined learning outcomes don't align with the chosen difficulty · **So that:** I can adjust
- **Acceptance Criteria:**
  - **AC-1** — *Given I define outcomes and a difficulty, when I run the pre-generation review, then any mismatch is surfaced as a recommendation (FR-AR-001).*
- **Dependencies:** FR-AR-001.
- **Related BR:** BR-011.

#### US-13.2.1 — See module overlap warnings
- **Persona:** Riley (P-5)
- **Priority:** S · **Points:** 3
- **As a:** Riley · **I want:** overlapping sections to be flagged · **So that:** I can decide whether to merge or differentiate them
- **Acceptance Criteria:**
  - **AC-1** — *Given a course draft exists, when I view issues, then any two sections flagged as overlapping appear as a paired warning with both section IDs (FR-AR-002).*
- **Dependencies:** FR-AR-002, FR-EV-004.
- **Related BR:** BR-011.

---

### Epic E14 — Course Design Dashboard

#### US-14.1.1 — See the course portfolio dashboard
- **Persona:** Alex (P-4)
- **Priority:** S · **Points:** 5
- **As a:** Alex · **I want:** a single dashboard to see all courses · **So that:** I can prioritize my work
- **Acceptance Criteria:**
  - **AC-1** — *Given I open the dashboard, when it loads, then I see a table of courses with columns: title, status, overall quality score, last edited, # of issues, owner (FR-DS-001).*
- **Dependencies:** FR-DS-001.
- **Related BR:** BR-011.

#### US-14.1.2 — Filter the dashboard
- **Persona:** Riley (P-5)
- **Priority:** S · **Points:** 3
- **As a:** Riley · **I want:** to filter the dashboard for "courses with pending review" · **So that:** I can focus on those
- **Acceptance Criteria:**
  - **AC-1** — *Given I apply a filter (e.g. "quality < 0.7"), when the table refreshes, then only matching courses are shown and the filter is persisted in the URL (FR-DS-002).*
- **Dependencies:** FR-DS-002.
- **Related BR:** BR-011.

#### US-14.2.1 — View aggregate metrics
- **Persona:** Sponsor (P-6)
- **Priority:** S · **Points:** 5
- **As a:** Sponsor · **I want:** to see adoption and quality metrics · **So that:** I can track the platform's value
- **Acceptance Criteria:**
  - **AC-1** — *Given I am an admin or sponsor, when I open the metrics view, then I see time-series charts for the metrics defined in BRD §14 (FR-DS-003).*
- **Dependencies:** FR-DS-003.
- **Related BR:** BR-011.

---

## 6. Cross-Epic / System Stories

### US-SYS-001 — Backend never returns free-form error text
- **Persona:** Frontend (system)
- **Priority:** M · **Points:** 2
- **Acceptance Criteria:**
  - **AC-1** — *Given any backend error, when the response is constructed, no raw stack trace or provider-specific exception is included (FR-JC-005, NFR-UX-003).*
- **Dependencies:** FR-JC-005, NFR-UX-003.

### US-SYS-002 — Domain layer has no provider imports
- **Persona:** AI Lead (P-8)
- **Priority:** M · **Points:** 2
- **Acceptance Criteria:**
  - **AC-1** — *Given the dependency graph, when CI runs the import check, the domain package does not import from any provider SDK (FR-PR-003, NFR-MAINT-001).*
- **Dependencies:** FR-PR-003, NFR-MAINT-001.

### US-SYS-003 — Generation produces a valid JSON contract
- **Persona:** Frontend (system)
- **Priority:** M · **Points:** 3
- **Acceptance Criteria:**
  - **AC-1** — *Given any completed generation, when the response is parsed, it validates against the published `schema_version` (FR-JC-001, FR-JC-002).*
- **Dependencies:** FR-JC-001, FR-JC-002.

### US-SYS-004 — Lineage is captured for every generation
- **Persona:** AI Lead (P-8)
- **Priority:** M · **Points:** 3
- **Acceptance Criteria:**
  - **AC-1** — *Given a generation runs, when it completes, `generation.agent_trace`, `prompt_version`, `rubric_version`, and `model_version` are populated (FR-JC-003, FR-VC-002).*
- **Dependencies:** FR-JC-003, FR-VC-002.

---

## 7. Story Backlog Summary

| Epic | Stories | Must | Should | Could |
|---|---|---|---|---|
| E1 | 4 | 3 | 1 | 0 |
| E2 | 5 | 1 | 4 | 0 |
| E3 | 6 | 2 | 4 | 0 |
| E4 | 7 | 4 | 3 | 0 |
| E5 | 8 | 0 | 8 | 0 |
| E6 | 4 | 1 | 3 | 0 |
| E7 | 6 | 0 | 6 | 0 |
| E8 | 4 | 0 | 4 | 0 |
| E9 | 4 | 0 | 4 | 0 |
| E10 | 3 | 0 | 3 | 0 |
| E11 | 3 | 2 | 1 | 0 |
| E12 | 2 | 0 | 0 | 2 |
| E13 | 3 | 0 | 1 | 2 |
| E14 | 3 | 0 | 3 | 0 |
| SYS | 4 | 4 | 0 | 0 |
| **Total** | **62** | **17** | **45** | **4** |

### 7.1 MVP (Must-have) story list
1. US-1.1.1, US-1.1.2, US-1.1.3 — Generation
2. US-2.1.1 — Live monitoring
3. US-3.1.1, US-3.1.3 — Curriculum tree + block render
4. US-4.1.1, US-4.1.2, US-4.1.3, US-4.2.1 — Edit Concept/Code/Quiz, no silent re-eval
5. US-6.1.1 — Audience & difficulty
6. US-11.1.1, US-11.2.1 — Provider config (admin) + invisible to users
7. US-SYS-001..004 — System guarantees

This is the smallest vertical slice that delivers "topic → reviewable structured draft".

---

## 8. Traceability (Story → FR → BR)

| Story | FR | BR |
|---|---|---|
| US-1.1.1 | FR-CG-001, FR-CG-003, FR-CG-004, FR-JC-001, FR-AG-001 | BR-001, BO-001 |
| US-1.1.2 | FR-CG-003, FR-CS-005, FR-CS-006, FR-CX-005 | BR-004, BO-002 |
| US-1.1.3 | FR-CX-002, NFR-SEC-005 | BR-005, BO-005 |
| US-1.2.1 | FR-CG-002 | BO-001 |
| US-2.1.1 | FR-AG-001, FR-AG-010, FR-JC-003, FR-JC-006 | BR-010, BR-012, BO-011 |
| US-2.1.2 | FR-EV-001, FR-EV-005, FR-JC-001 | BR-013, BO-011 |
| US-2.1.3 | FR-AG-010, FR-NE-001 | BR-010, BO-012 |
| US-2.1.4 | FR-JC-003, NFR-COST-004 | BO-011 |
| US-2.2.1 | FR-NE-001, FR-NE-002 | BO-011 |
| US-3.1.1 | FR-CS-001, FR-CS-002, FR-EV-004 | BR-002, BO-002 |
| US-3.1.2 | FR-EV-004 | BO-011 |
| US-3.1.3 | FR-ED-002, FR-BL-002 | BR-003, BO-002 |
| US-3.2.1 | FR-ED-002, FR-BL-006 | BR-003, BO-002 |
| US-3.2.2 | FR-BL-006 | BR-003 |
| US-3.2.3 | FR-BL-005 | BR-003 |
| US-4.1.1 | FR-ED-001, FR-ED-003, FR-ED-004, FR-ED-005, FR-VC-006 | BR-001, BO-008, BC-001 |
| US-4.1.2 | FR-ED-002, FR-BL-002, FR-BL-007 | BR-003, BC-003 |
| US-4.1.3 | FR-BL-006, FR-ED-002 | BR-003 |
| US-4.1.4 | FR-BL-002 | BR-003 |
| US-4.2.1 | FR-ED-003, FR-EV-001 | BC-001, BO-008 |
| US-4.2.2 | FR-EV-001, FR-EV-004 | BR-011 |
| US-4.5.1 | FR-VC-001, FR-ED-005 | BO-008 |
| US-5.1.1 | FR-RG-001, FR-RG-004, FR-RG-005, FR-RG-006 | BO-012, BR-014 |
| US-5.1.2 | FR-RG-004, FR-VC-003 | BO-012 |
| US-5.1.3 | FR-RG-001, FR-VC-006 | BO-012 |
| US-5.1.4 | FR-RG-006, FR-AG-010 | BR-014 |
| US-5.2.1 | FR-RG-002, FR-RG-006 | BO-012, BR-014 |
| US-5.2.2 | FR-RG-003 | BO-012, BR-014 |
| US-5.3.1 | FR-RG-001, FR-RG-002, FR-RG-003, FR-VC-006 | BO-012 |
| US-5.6.1 | FR-AG-010 | BO-012 |
| US-6.1.1 | FR-PZ-001, FR-PZ-006, FR-AG-002 | BR-004, BO-003 |
| US-6.1.2 | FR-PZ-002 | BR-004, BO-003 |
| US-6.2.1 | FR-PZ-003, FR-AG-004 | BR-004, BO-003 |
| US-6.3.1 | FR-PZ-004, FR-AG-005 | BR-004, BO-003 |
| US-7.1.1 | FR-CX-001, FR-AG-002 | BR-005, BO-005 |
| US-7.2.1 | FR-CX-002, NFR-SEC-005 | BR-005, BO-005 |
| US-7.2.2 | FR-CX-002 | BR-005 |
| US-7.3.1 | FR-CX-003, FR-AG-002 | BR-005, BO-005 |
| US-7.4.1 | FR-CX-004 | BR-005, BO-005 |
| US-7.5.1 | FR-CS-006, FR-CX-005 | BR-005, BO-005 |
| US-8.1.1 | FR-FB-001, FR-FB-005, FR-RG-001 | BR-006, BO-004 |
| US-8.2.1 | FR-FB-002, FR-RG-002 | BR-006, BO-004 |
| US-8.3.1 | FR-FB-003, FR-AG-003 | BR-006, BO-004 |
| US-8.4.1 | FR-FB-004, FR-VC-004 | BR-006, BO-004 |
| US-9.1.1 | FR-VC-001, FR-ED-005 | BR-008, BO-008 |
| US-9.1.2 | FR-VC-001 | BO-008 |
| US-9.2.1 | FR-VC-003 | BR-008 |
| US-9.3.1 | FR-VC-004 | BO-008 |
| US-10.1.1 | FR-EX-001, FR-EX-004 | BR-009, BO-007 |
| US-10.1.2 | FR-EX-002, FR-EX-005 | BR-009 |
| US-10.2.1 | FR-EX-003, FR-EV-004 | BR-009 |
| US-11.1.1 | FR-PR-001, FR-AG-014, FR-JC-003 | BR-007, BR-016, BO-006 |
| US-11.1.2 | FR-AG-013, NFR-MAINT-001 | BR-007, BR-016 |
| US-11.2.1 | FR-PR-002 | BR-007 |
| US-12.1.1 | FR-BT-001, FR-BT-002 | BC-004 |
| US-12.1.2 | FR-BT-003 | BC-004 |
| US-13.1.1 | FR-AR-001 | BR-011 |
| US-13.1.2 | FR-AR-001 | BR-011 |
| US-13.2.1 | FR-AR-002, FR-EV-004 | BR-011 |
| US-14.1.1 | FR-DS-001 | BR-011 |
| US-14.1.2 | FR-DS-002 | BR-011 |
| US-14.2.1 | FR-DS-003 | BR-011 |
| US-SYS-001 | FR-JC-005, NFR-UX-003 | — |
| US-SYS-002 | FR-PR-003, NFR-MAINT-001 | — |
| US-SYS-003 | FR-JC-001, FR-JC-002 | — |
| US-SYS-004 | FR-JC-003, FR-VC-002 | — |

---

## 9. Open Questions

| ID | Question | Owner | Needed by |
|---|---|---|---|
| US-OQ-1 | What is the default per-course iteration cap for the MVP? | AI Lead | M1 |
| US-OQ-2 | Should Story US-5.1.1 (regenerate block) require a confirmation step ("this will rewrite the block")? | UX + Product | M3 |
| US-OQ-3 | What is the upper bound on document upload size in v1? | DevOps | M2 |
| US-OQ-4 | How are concurrent regenerations on the same block reconciled? | Backend Lead | M5 |

---

## 10. Sign-off

| Role | Name | Signature | Date |
|---|---|---|---|
| Head of Product | | | |
| Head of Engineering | | | |
| AI Lead | | | |
| UX Lead | | | |
| QA Lead | | | |

---

## 11. Cross-References

- **Project Charter** — `01 Project Charter.md`
- **Business Requirements** — `02 Business Requirements Document.md`
- **Product Requirements** — `03 Product Requirements Document.md`
- **Functional Requirements** — `04 Functional Requirements.md`
- **Non-Functional Requirements** — `05 Non-Functional Requirements.md`
- **JSON Output Contract** — `02 Business Requirements Document.md` §11
- **ADRs** — `docs/adr/`
