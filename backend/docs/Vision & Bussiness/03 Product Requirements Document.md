# Product Requirements Document (PRD)

## AI-Powered Course Generator Platform

> Document type: Product Requirements Document (PRD)
> Companion to: `project-charter.md`, `BRD.md`
> Status: Draft v0.1 · Owner: Product · Last updated: 2026-06-05
> This PRD is the user-facing specification of what the product does.
> It defines features, user stories, and acceptance criteria.
> Business context lives in `BRD.md`; vision and scope live in `project-charter.md`.

---

## 1. Document Control

| Field | Value |
|---|---|
| Product name | CourseForge |
| Document version | 0.1 (Draft) |
| Author | Product Management |
| Reviewers | UX, AI Lead, Backend Lead, Frontend Lead |
| Approvers | Sponsor, Head of Product |
| Cadence | Reviewed at end of each sprint; re-baselined on scope changes |
| Source of truth | This document supersedes informal feature lists |

---

## 2. Product Overview

### 2.1 What it is
CourseForge is a web-based, AI-assisted course design environment. Users describe a topic, configure audience and pedagogy, and the platform generates a **structured course** composed of typed instructional blocks (concept, example, code, exercise, quiz, etc.). The system runs a **multi-agent, self-refining pipeline** internally and returns a single **JSON document** that the UI renders into navigable, editable course material.

### 2.2 What it is not
- It is not a one-shot text generator. Every generation is evaluated against a quality rubric and refined before being shown to the user.
- It is not an LMS. It does not deliver courses to learners in v1.
- It is not a free-form chat tool. The frontend is purpose-built for
  course structure, block-level editing, and quality feedback.

### 2.3 Value proposition
For a course that would have taken weeks to author, CourseForge delivers a **reviewable, structured, auditable draft in minutes**, with visible quality scores and explicit next actions the user can take to improve it.

---

## 3. Goals & Non-Goals

### 3.1 Product Goals (PG)
- **PG-1** — Reduce time from "topic idea" to "reviewable structured draft" to minutes.
- **PG-2** — Make the AI's confidence and quality **observable**, not opaque.
- **PG-3** — Give users **granular control** — regenerate one block, one section, or one module without touching the rest.
- **PG-4** — Make refinement a **first-class loop**, not a "regenerate everything" button.
- **PG-5** — Keep the platform **provider-agnostic** at the user-facing layer.
- **PG-6** — Output is **structured data**, not free-form prose, so the UI can render and edit intelligently.

### 3.2 Non-Goals (v1)
- Delivering courses to end-learners (no LMS, no enrollment, no progress tracking).
- Auto-publishing without human review.
- Mobile-native applications.
- Real-time multi-user collaborative editing.
- Adaptive, closed-loop personalization from learner behavior.
- Full RAG over an organizational knowledge base.

---

## 4. Target Users & Personas

### 4.1 Primary personas

#### P-1 Maria · Instructional Designer
- **Role:** Designs learning experiences for a corporate training company.
- **Goals:** Produce consistent, well-structured curricula across many topics.
- **Pain today:** SMEs hand her raw notes; she manually structures them into modules, sections, exercises. Slow and inconsistent.
- **Wants from CourseForge:** A first-draft structure she can edit, with consistent block types and pacing.

#### P-2 David · Subject Matter Expert
- **Role:** Senior engineer at a software company, also responsible for internal training.
- **Goals:** Turn his knowledge into onboarding material for new hires.
- **Pain today:** Writing educational material takes time away from engineering; structure and pedagogical quality are uneven.
- **Wants from CourseForge:** A draft that follows a known pedagogical structure; he refines the technical accuracy.

#### P-3 Sofia · Independent Educator
- **Role:** Creates and sells online courses.
- **Goals:** Produce more courses faster, maintain quality across her catalog.
- **Pain today:** Each course is a multi-week project; she can't keep up with demand.
- **Wants from CourseForge:** Generate a complete course from a topic, customize it for her audience, and export it cleanly to her platform.

#### P-4 Alex · Content Operations Lead
- **Role:** Manages a portfolio of courses at a consulting firm.
- **Goals:** Track course quality, ensure standardization, coordinate reviewers.
- **Pain today:** No visibility into which courses are reviewed, which are stale, how quality varies.
- **Wants from CourseForge:** A dashboard, version history, comparison views, and consistent structure across courses.

#### P-5 Riley · Reviewer / Editor
- **Role:** Edits and approves AI-generated drafts.
- **Goals:** Quickly identify what needs fixing; suggest precise edits; approve final versions.
- **Pain today:** Reviewing long unstructured text is slow; corrections cascade through the whole document.
- **Wants from CourseForge:** Issue lists with one-click "regenerate this block", side-by-side version comparison, targeted feedback.

### 4.2 Secondary personas
- **Sponsor / Executive** — wants adoption metrics, ROI on content production.
- **DevOps / IT Admin** — wants provider configuration, usage limits, audit logs.
- **AI Engineering** — wants prompt versions, rubric versions, agent traces, eval results.

---

## 5. User Journeys

### 5.1 First-time course creation (Maria)
1. Maria signs in and lands on the dashboard.
2. She clicks **New Course** and enters "Data Engineering for Analysts".
3. She picks the audience (analysts with basic SQL), difficulty (intermediate), and a few learning outcomes.
4. She adds a reference document (internal standards PDF) and writes a short text instruction.
5. She clicks **Generate**.
6. Within minutes, a course draft appears, with **overall quality score = 0.84**, passing the rubric.
7. She opens the curriculum view, scans module titles, jumps into Section 3, edits one Example block, and regenerates one Exercise block.
8. She exports the course to Markdown and PDF.

### 5.2 Iterative refinement (Riley)
1. Riley opens a course in review state.
2. The UI shows a list of 12 outstanding issues (5 warnings, 7 info).
3. Riley clicks **Regenerate** on a flagged Exercise block.
4. The block is rewritten by the Refiner agent and re-evaluated.
5. The new block appears in a side-by-side view; Riley accepts or edits manually.
6. Riley adds a global feedback note ("Add more analogies"); the platform applies it across the course.

### 5.3 Maintaining a portfolio (Alex)
1. Alex opens the dashboard and sees 24 courses with their quality scores, last-edit dates, and pending review counts.
2. He filters for courses below 0.7 and opens them in batch.
3. He triggers a "global refresh" — re-evaluate all blocks against the latest rubric.
4. He exports a CSV of course quality metrics.

---

## 6. Epics & Features

Features are grouped into epics. Each feature has: description, user stories,
and acceptance criteria. Stories follow the format **As a [persona], I want [capability], so that [value]**. Acceptance criteria follow the **Given / When / Then** format.

### Epic Map

| Epic | Name | Primary value |
|---|---|---|
| E1 | Course Generation Request | First-draft creation |
| E2 | Generation Monitoring | Transparency during generation |
| E3 | Course Review & Navigation | Read & audit the draft |
| E4 | Block-Level Editing | Human authorship |
| E5 | Granular Regeneration | Targeted AI improvements |
| E6 | Personalization Controls | Audience-fit content |
| E7 | Context Injection | Domain-aware generation |
| E8 | Feedback at All Levels | Continuous refinement |
| E9 | Version History & Comparison | Traceability & rollback |
| E10 | Export & Publishing | Reuse across formats |
| E11 | Provider Configuration | Multi-provider support |
| E12 | Block-Type Extensibility | Future-proofing |
| E13 | AI-Assisted Curriculum Review | Pre-generation gap analysis |
| E14 | Course Design Dashboard | Portfolio-level visibility |

---

### Epic E1 — Course Generation Request

#### Feature F1.1 — Create a new course from a topic

**Description**
The user starts a new course by providing a topic, audience, difficulty,
learning outcomes, and (optionally) context. The platform submits a
generation job and returns a course draft.

**User stories**
- **US-1.1.1** — *As Maria, I want to start a new course by entering a topic and basic parameters, so that I can get a structured draft without filling in a long form.*
- **US-1.1.2** — *As Sofia, I want to specify learning outcomes up front, so that the generated course is aligned with what I want my students to achieve.*
- **US-1.1.3** — *As David, I want to attach an existing document as context, so that the generated course reflects my company's standards.*

**Acceptance criteria**
- **AC-1.1.1** — *Given I am on the "New Course" page, when I enter a topic string of at least 3 characters and click Generate, then a generation job is created and I am taken to the Generation Monitoring view.*
- **AC-1.1.2** — *Given I am filling in course parameters, when I leave a required field empty, then the Generate button is disabled and a tooltip names the missing field.*
- **AC-1.1.3** — *Given I have entered audience, difficulty, and at least one learning outcome, when I click Generate, then the request body includes all of those fields in the JSON contract expected by the backend.*
- **AC-1.1.4** — *Given the generation is in progress, when I refresh the page, then I am returned to the monitoring view for the same job, with progress intact.*

#### Feature F1.2 — Quick-start templates

**Description**
The user can start from a template (e.g. "Onboarding course", "Certification prep") that pre-fills topic, audience, block composition, and outcomes.

**User stories**
- **US-1.2.1** — *As Sofia, I want to start from a template, so that I don't re-enter the same defaults for every course.*

**Acceptance criteria**
- **AC-1.2.1** — *Given I am on the "New Course" page, when I select a template, then the form is pre-filled with that template's values and I can override any of them before generating.*

---

### Epic E2 — Generation Monitoring

#### Feature F2.1 — Real-time generation progress

**Description**
While a generation job is running, the user sees a live view of the
multi-agent pipeline: which agent is running, which phase, and a
quality-score trajectory.

**User stories**
- **US-2.1.1** — *As Maria, I want to see what's happening while the AI is working, so that I trust the system and know roughly how long it will take.*
- **US-2.1.2** — *As Alex, I want to see per-iteration quality scores, so that I can confirm the system is actually improving the draft.*

**Acceptance criteria**
- **AC-2.1.1** — *Given a job is running, when I am on the monitoring view, then I see a list of agents and the current phase (e.g. "SectionAuthor — section 3 of 8") updating at least every 2 seconds.*
- **AC-2.1.2** — *Given a job has completed at least one refinement iteration, when I view the monitoring page, then I see a small line chart of overall quality score per iteration.*
- **AC-2.1.3** — *Given the user closes the browser during generation, when they return, then the monitoring view reconnects and shows current state (does not start a new job).*
- **AC-2.1.4** — *Given the job terminates, when I view the monitoring page, then the termination reason (quality_threshold / max_iterations / budget_exhausted / user_aborted) is shown explicitly.*

#### Feature F2.2 — Cost & budget transparency

**Description**
The user sees tokens used, estimated cost, and remaining budget for the
current job.

**User stories**
- **US-2.2.1** — *As Alex, I want to see token spend per job, so that I can control cost across my team.*

**Acceptance criteria**
- **AC-2.2.1** — *Given a job is running, when I view the monitoring page, then I see input tokens, output tokens, and a per-iteration breakdown.*

---

### Epic E3 — Course Review & Navigation

#### Feature F3.1 — Curriculum tree view

**Description**
A hierarchical view of Course → Module → Section → Block, with collapsible nodes, badges for block type, and quality indicators.

**User stories**
- **US-3.1.1** — *As Maria, I want to scan the course structure at a glance, so that I can decide which sections to focus on first.*
- **US-3.1.2** — *As Riley, I want to see which blocks have outstanding issues, so that I can prioritize review.*

**Acceptance criteria**
- **AC-3.1.1** — *Given I open a course, when I view the curriculum tree, then I see all modules, sections, and blocks in a collapsible hierarchy, in the correct order.*
- **AC-3.1.2** — *Given a block has an outstanding issue, when I view the tree, then the block node shows a warning icon and the issue category on hover.*
- **AC-3.1.3** — *Given I click a block node, when the selection changes, then the right pane shows the block content rendered with the block-type-specific component.*

#### Feature F3.2 — Section & block reading view

**Description**
A reading-optimized view of a section, where each block is rendered with
its block-type component (Concept, Example, Code, Quiz, etc.).

**User stories**
- **US-3.2.1** — *As Sofia, I want to read through a generated section naturally, so that I can judge quality and flow.*

**Acceptance criteria**
- **AC-3.2.2** — *Given I am reading a section, when blocks are rendered, then each block uses the type-specific renderer defined in the JSON contract (e.g. Code uses a syntax-highlighted editor in read-only mode).*
- **AC-3.2.3** — *Given I am reading a section, when the section includes a Quiz block, then the quiz is rendered as a real assessment component (with selectable choices) and feedback is shown on answer.*

---

### Epic E4 — Block-Level Editing

#### Feature F4.1 — Edit any block inline

**Description**
Every block is editable in place, with type-appropriate editors (rich text,
code editor, quiz editor, etc.). Edits are saved to a new version of the
block.

**User stories**
- **US-4.1.1** — *As David, I want to fix a technical inaccuracy in a Concept block, so that the course reflects correct information.*
- **US-4.1.2** — *As Riley, I want to reword an Exercise prompt, so that it matches our house style.*

**Acceptance criteria**
- **AC-4.1.1** — *Given I am viewing a block in edit mode, when I make a change and click Save, then a new version of the block is created and the previous version is preserved in history.*
- **AC-4.1.2** — *Given I am editing a Code block, when the language is set, then the editor provides syntax highlighting for that language.*
- **AC-4.1.3** — *Given I am editing a Quiz block, when I add a question, then I can define choices, mark the correct answer, and write an explanation; the block content matches the JSON contract shape.*
- **AC-4.1.4** — *Given I make edits across multiple blocks, when I navigate away, then I am warned about unsaved changes.*

#### Feature F4.2 — Manual edit does not trigger regeneration

**Description**
Edits are not silently re-evaluated. The Evaluator runs only when the user
explicitly asks for an evaluation or a regeneration.

**User stories**
- **US-4.2.1** — *As David, I want my manual edits to be saved verbatim, so that the system does not "correct" what I just fixed.*

**Acceptance criteria**
- **AC-4.2.1** — *Given I have just saved a manual edit to a block, when I view the block, then its content matches exactly what I entered — no silent AI rewrite.*
- **AC-4.2.2** — *Given I want a quality check on my manual edit, when I click "Re-evaluate block", then the Evaluator scores the current block content and reports issues.*

---

### Epic E5 — Granular Regeneration

#### Feature F5.1 — Regenerate a single block

**Description**
The user can regenerate one block. The Refiner agent (or a fresh
SectionAuthor + Evaluator pass on that single block) produces a new
version, and the user is shown a diff/side-by-side before accepting.

**User stories**
- **US-5.1.1** — *As Riley, I want to regenerate only the Exercise block that has a clarity issue, so that I don't risk breaking other content.*
- **US-5.1.2** — *As Maria, I want to see the old and new version of a block side by side, so that I can decide which one to keep.*

**Acceptance criteria**
- **AC-5.1.1** — *Given I am viewing a block with an outstanding issue, when I click Regenerate, then only that block is sent through the refinement loop; no other block in the course is re-generated.*
- **AC-5.1.2** — *Given a regeneration completes, when I view the result, then I see the previous version and the new version side by side, with the Evaluator's score for each.*
- **AC-5.1.3** — *Given I am reviewing a regenerated block, when I click Accept, then the new version becomes the current version and the old version is moved to history.*
- **AC-5.1.4** — *Given I am reviewing a regenerated block, when I click Discard, then the new version is discarded and the previous version remains current.*

#### Feature F5.2 — Regenerate a section or module

**Description**
Same as F5.1 but at the section or module level.

**User stories**
- **US-5.2.1** — *As Sofia, I want to regenerate an entire section, so that I can apply a new instructional style without rewriting each block manually.*

**Acceptance criteria**
- **AC-5.2.1** — *Given I select a section and click Regenerate, when the job runs, then only the blocks within that section are sent through the refinement loop.*
- **AC-5.2.2** — *Given I select a module and click Regenerate, when the job runs, then only the sections and blocks within that module are regenerated.*

#### Feature F5.3 — Targeted regeneration preserves the rest of the course

**Description**
A targeted regeneration must not change any content outside its target.
The version lineage makes this verifiable.

**User stories**
- **US-5.3.1** — *As David, I want confidence that regenerating one block won't quietly change other blocks, so that my previously reviewed content stays intact.*

**Acceptance criteria**
- **AC-5.3.1** — *Given I regenerate a block, when the job completes, then the version IDs of all other blocks in the course are unchanged (verifiable in the version history).*

---

### Epic E6 — Personalization Controls

#### Feature F6.1 — Audience & difficulty

**Description**
The user can set audience profile, difficulty, depth, and the
technical-vs-practical balance for a course (or per module).

**User stories**
- **US-6.1.1** — *As Maria, I want to set the audience to "Engineers" and difficulty to "Intermediate", so that the generated content is calibrated correctly.*
- **US-6.1.2** — *As David, I want to mark the depth as "Industry-Oriented" for a specific module, so that the rest of the course can stay academic.*

**Acceptance criteria**
- **AC-6.1.1** — *Given I am on course parameters, when I set the audience and difficulty, then these values are stored on the course and are part of the context sent to the generation pipeline.*
- **AC-6.1.2** — *Given I override depth on a single module, when the module is regenerated, then the override applies to that module only and does not affect sibling modules.*

#### Feature F6.2 — Block composition

**Description**
The user defines which block types are generated and in what proportion
per section.

**User stories**
- **US-6.2.1** — *As Sofia, I want to specify that every section should include a Concept, an Example, an Exercise, and a Key Points block, so that the structure is consistent.*

**Acceptance criteria**
- **AC-6.2.1** — *Given I configure a block composition rule, when a section is generated, then the section contains at least the configured block types in the configured order.*

#### Feature F6.3 — Learning style & instructional strategy

**Description**
The user can choose between instructional strategies (e.g. project-based, example-driven, theory-first) and learning style preferences (visual, hands-on, reading-heavy).

**User stories**
- **US-6.3.1** — *As Maria, I want to choose "example-driven" as the instructional strategy, so that the generated course leads with worked examples.*

**Acceptance criteria**
- **AC-6.3.1** — *Given I set the instructional strategy, when a course is generated, then the resulting blocks reflect that strategy in their content and ordering (verifiable by spot-check).*

---

### Epic E7 — Context Injection

#### Feature F7.1 — Text instructions

**Description**
The user provides a free-form text instruction that becomes a high-priority directive for the generation pipeline.

**User stories**
- **US-7.1.1** — *As Maria, I want to write a note like "Always include a real-world case study in the introduction of each module", so that the AI honors that across the course.*

**Acceptance criteria**
- **AC-7.1.1** — *Given I have entered a text instruction, when a course is generated, then the instruction is included in the GenerationContext and is visible in the generation metadata for traceability.*

#### Feature F7.2 — Existing documents as context

**Description**
The user uploads PDFs, Markdown, or text files that the Context Synthesizer ingests and summarizes into the generation context.

**User stories**
- **US-7.2.1** — *As David, I want to upload our internal "Engineering Standards" PDF, so that generated courses use our terminology and patterns.*

**Acceptance criteria**
- **AC-7.2.1** — *Given I upload a supported document, when the file is processed, then I see a confirmation that it was ingested and a short summary is shown.*
- **AC-7.2.2** — *Given I have uploaded a document, when the course is generated, then the document's content is reflected in the produced material (e.g. our specific terms appear, our specific patterns are used).*

#### Feature F7.3 — Reference courses

**Description**
The user can attach one or more existing courses as references. The platform analyzes their structure and pedagogy (not their literal content) and applies the patterns to the new course.

**User stories**
- **US-7.3.1** — *As Sofia, I want to attach a previous course of mine as a reference, so that the new course has the same pacing and pedagogical style.*

**Acceptance criteria**
- **AC-7.3.1** — *Given I attach a reference course, when the new course is generated, then the structure (module count, section types, pacing) is visibly influenced by the reference — without copying the reference's content verbatim.*

#### Feature F7.4 — Domain knowledge

**Description**
The user provides domain-specific knowledge (company standards, regulations, terminology) that becomes part of the context.

**User stories**
- **US-7.4.1** — *As Alex, I want to inject "We use AWS, not GCP, as our default cloud" as a domain constraint, so that examples consistently use AWS.*

**Acceptance criteria**
- **AC-7.4.1** — *Given I have added a domain knowledge item, when the course is generated, then examples in the new course use AWS by default (where cloud examples appear).*

#### Feature F7.5 — Learning outcomes

**Description**
The user defines measurable learning outcomes that drive topic selection,
exercise generation, and assessment.

**User stories**
- **US-7.5.1** — *As Sofia, I want to list 3–5 learning outcomes, so that the course is structured around achieving them.*

**Acceptance criteria**
- **AC-7.5.1** — *Given I have defined N learning outcomes, when the course is generated, then the curriculum's sections collectively cover each outcome (verifiable in the curriculum view).*

---

### Epic E8 — Feedback at All Levels

#### Feature F8.1 — Block feedback

**Description**
The user provides targeted feedback on a single block. The Refiner applies the feedback to produce a new version.

**User stories**
- **US-8.1.1** — *As Riley, I want to write a comment on a specific Example block, so that the next regeneration of that block addresses my note.*

**Acceptance criteria**
- **AC-8.1.1** — *Given I attach feedback to a block, when I click Regenerate, then the new version of the block addresses the feedback (verifiable by reading the new content).*

#### Feature F8.2 — Section feedback

**Description**
The user provides feedback on a section. The Refiner applies it across the section's blocks.

**Acceptance criteria**
- **AC-8.2.1** — *Given I attach feedback to a section, when I click Regenerate, then all blocks within that section are revised in light of the feedback; no other section is touched.*

#### Feature F8.3 — Curriculum feedback

**Description**
The user provides feedback on the overall course structure. The CurriculumPlanner is re-invoked and the new structure is shown for approval.

**Acceptance criteria**
- **AC-8.3.1** — *Given I attach curriculum-level feedback, when I click Regenerate, then the new course skeleton is presented in a diff view against the old skeleton before any section content is regenerated.*

#### Feature F8.4 — Global feedback

**Description**
The user provides course-wide feedback (style, tone, organizational standards). The Refiner applies it across every block.

**Acceptance criteria**
- **AC-8.4.1** — *Given I attach a global feedback note, when I click Apply globally, then all blocks are re-evaluated and revised where the note applies; the operation is reversible from version history.*

---

### Epic E9 — Version History & Comparison

#### Feature F9.1 — Version history per aggregate

**Description**
Every Course, Module, Section, and Block has a version history. The user can view the timeline of changes.

**User stories**
- **US-9.1.1** — *As Alex, I want to see when each block was last edited and by whom, so that I can audit the course's evolution.*

**Acceptance criteria**
- **AC-9.1.1** — *Given I open the version history for a block, when the history loads, then I see a chronological list of versions, each with timestamp, author (human or AI), source (manual edit / generation / refinement), and a quality score.*
- **AC-9.1.2** — *Given I am viewing version history at the course level, when I select a version, then I can drill down to the block-level diff for that version.*

#### Feature F9.2 — Side-by-side version comparison

**Description**
The user can compare two versions of a block (or section, or course) side by side, with diff highlighting.

**User stories**
- **US-9.2.1** — *As Riley, I want to compare the current version of a block with the previous one, so that I can review what the AI changed.*

**Acceptance criteria**
- **AC-9.2.1** — *Given I select two versions of a block, when the comparison view loads, then both versions are shown side by side with character-level diff highlighting for text fields and structural diffs for arrays/objects.*

#### Feature F9.3 — Rollback

**Description**
The user can revert a block, section, module, or entire course to a previous version.

**Acceptance criteria**
- **AC-9.3.1** — *Given I am viewing a previous version, when I click "Restore this version", then the current version is replaced and the previous version is preserved in history (rollback is itself an event in the history).*

---

### Epic E10 — Export & Publishing

#### Feature F10.1 — Export to multiple formats

**Description**
The user can export a course to Markdown, PDF, and (in a future release) LMS-compatible formats. Exports preserve block types as much as the target format allows.

**User stories**
- **US-10.1.1** — *As Sofia, I want to export a course to Markdown, so that I can publish it on my own platform.*

**Acceptance criteria**
- **AC-10.1.1** — *Given I select Markdown export, when the export completes, then I receive a valid Markdown document (or zip of one file per section) where block types map to appropriate Markdown structures (headings, code fences, lists).*
- **AC-10.1.2** — *Given I select PDF export, when the export completes, then I receive a PDF that visually matches the section reading view (block-type-specific rendering).*

#### Feature F10.2 — Pre-publish validation

**Description**
Before publishing/exporting, the platform runs the full Evaluator on the current state and surfaces any blocker issues.

**Acceptance criteria**
- **AC-10.2.1** — *Given I click Export, when any blocker issue exists, then I am shown a list of blockers and given the choice to "Export anyway" or "Fix first".*

---

### Epic E11 — Provider Configuration

#### Feature F11.1 — Multi-provider support (admin)

**Description**
An admin can configure which LLM providers are available and which provider/model is used per agent role (planner, author, evaluator, refiner).

**User stories**
- **US-11.1.1** — *As DevOps, I want to set the default Evaluator model to one provider and the default Author model to another, so that we balance cost and quality.*

**Acceptance criteria**
- **AC-11.1.1** — *Given I am an admin, when I open Provider Configuration, then I can see a list of configured providers and a per-agent model assignment table.*
- **AC-11.1.2** — *Given I change a per-agent model, when a new generation is run, then the agent trace shows the new model.*

#### Feature F11.2 — Provider abstraction is invisible to end users

**Description**
End users (Maria, David, Sofia, Riley, Alex) never select a provider explicitly. They experience a single, consistent product.

**Acceptance criteria**
- **AC-11.2.1** — *Given I am a non-admin user, when I generate a course, then I do not see any provider selection UI; provider choice is made by configuration, not by the user.*

---

### Epic E12 — Block-Type Extensibility

#### Feature F12.1 — Block type registry (admin)

**Description**
An admin can register a new block type by providing a name, schema (JSON-Schema for the `content` field), default renderer, and any block-specific prompts.

**User stories**
- **US-12.1.1** — *As a Product Manager, I want to add a "Flashcard" block type without an engineering release, so that we can experiment quickly.*

**Acceptance criteria**
- **AC-12.1.1** — *Given I am an admin, when I register a new block type with a valid JSON-Schema, then the type becomes available in the curriculum tree and the section composer within the same session.*
- **AC-12.1.2** — *Given a new block type is registered, when the Evaluator runs, then it can score blocks of the new type using the registered schema as a structural check.*

---

### Epic E13 — AI-Assisted Curriculum Review

#### Feature F13.1 — Pre-generation gap analysis

**Description**
Before generation, the platform analyzes the user's inputs (topic, outcomes, audience) and emits recommendations for things that may be missing or misaligned.

**User stories**
- **US-13.1.1** — *As Maria, I want to be warned that my course on "Microservices" may be missing "Observability", so that I can add it as a topic before generation.*
- **US-13.1.2** — *As Sofia, I want to be told that my defined learning outcomes don't align with the chosen difficulty, so that I can adjust.*

**Acceptance criteria**
- **AC-13.1.1** — *Given I am on the "New Course" page with parameters filled in, when I click "Review", then I see a list of AI-generated recommendations such as "Missing topics", "Progression too steep", "Outcome-difficulty mismatch".*
- **AC-13.1.2** — *Given I dismiss a recommendation, when I run the review again, then it is not shown again unless inputs change.*

#### Feature F13.2 — Module overlap detection

**Description**
After a draft is generated, the ConsistencyChecker flags sections or modules whose content overlaps significantly.

**Acceptance criteria**
- **AC-13.2.1** — *Given a course draft exists, when I view issues, then any two sections flagged as overlapping appear as a paired warning with both section IDs.*

---

### Epic E14 — Course Design Dashboard

#### Feature F14.1 — Portfolio overview

**Description**
A landing dashboard that lists all courses in the user's scope with key metadata: title, status, quality score, last edit, pending issues, owner.

**User stories**
- **US-14.1.1** — *As Alex, I want a single dashboard to see all courses, so that I can prioritize my work.*
- **US-14.1.2** — *As Riley, I want to filter the dashboard for "courses with pending review", so that I can focus on those.*

**Acceptance criteria**
- **AC-14.1.1** — *Given I open the dashboard, when it loads, then I see a table of courses with columns: title, status, overall quality score, last edited, # of issues, owner.*
- **AC-14.1.2** — *Given I apply a filter (e.g. "quality < 0.7"), when the table refreshes, then only matching courses are shown and the filter is persisted in the URL.*

#### Feature F14.2 — Quality & adoption metrics

**Description**
Aggregate metrics: rubric pass rate, average quality uplift, iterations to pass, cost per course, courses generated over time.

**Acceptance criteria**
- **AC-14.2.1** — *Given I am an admin or sponsor, when I open the metrics view, then I see time-series charts for the metrics defined in BRD §14.*

---

## 7. Cross-Cutting Requirements

### 7.1 Performance
- A typical course (8 modules, 6 sections each, 4 blocks per section) must
  be generated within **15 minutes** end-to-end on the default provider.
- The monitoring view must update at least every **2 seconds**.

### 7.2 Reliability
- A failed agent does not abort the entire job when a graceful fallback
  exists. The system returns partial success with structured `issues`.
- All generations are persisted with full lineage and remain reproducible
  by replaying inputs + prompt version + model version + rubric version.

### 7.3 Security & Privacy
- Course content, prompts, and context are isolated per tenant.
- Document uploads are scanned for malware and size-limited per plan.
- Provider API keys are never logged.

### 7.4 Accessibility
- The web UI must meet WCAG 2.1 AA.
- All interactive components must be keyboard-navigable.
- Color is not the only signal for quality indicators (icons + text accompany).

### 7.5 Internationalization
- The UI is English-first in v1, but all user-facing strings are externalized
  to support future locales.
- Course content language is selectable per course (default: en).

---

## 8. Prioritization (MoSCoW)

| Epic | Must have | Should have | Could have | Won't have (v1) |
|---|---|---|---|---|
| E1 Course Generation Request | ✅ | | | |
| E2 Generation Monitoring | | ✅ (basic); ✅ (full) | | |
| E3 Course Review & Navigation | ✅ | | | |
| E4 Block-Level Editing | ✅ | | | |
| E5 Granular Regeneration | | ✅ | | |
| E6 Personalization Controls | | ✅ | | |
| E7 Context Injection | | ✅ | | |
| E8 Feedback at All Levels | | ✅ | | |
| E9 Version History & Comparison | | ✅ | | |
| E10 Export & Publishing | | ✅ (MD/PDF) | | LMS (out) |
| E11 Provider Configuration | ✅ (admin) | | | |
| E12 Block-Type Extensibility | | | ✅ | |
| E13 AI-Assisted Curriculum Review | | | ✅ | |
| E14 Course Design Dashboard | | ✅ | | |

**v1 must-haves (MVP):** E1, E3, E4, E11 (admin) — these are the smallest
vertical slice that delivers "topic → reviewable structured draft".

---

## 9. Release Phases

| Phase | Scope | Definition of Done |
|---|---|---|
| **Alpha (internal)** | E1, E2 (basic), E3, E4 (read-only), F11.1 | One provider, mocked refinement loop, no feedback yet. |
| **Beta (closed)** | + E4 (editable), E5, E6 (subset), E7 (subset), E8 (block), E9 (history), E10 (MD) | Self-refinement loop live, one non-admin can complete the full journey. |
| **GA (v1)** | All ✅ and ✅ rows above, with E12, E13, E14 as beta-flagged. | Acceptance criteria for all Must + Should features pass. |

---

## 10. Out-of-Scope (for the avoidance of doubt)
- LMS features (enrollment, progress, grading).
- RAG over a knowledge base.
- Real-time collaborative editing.
- Mobile native apps.
- Adaptive learning (closed-loop personalization from learner behavior).
- Video/audio generation.
- Payment and certification.

---

## 11. Open Questions

| ID | Question | Owner | Needed by |
|---|---|---|---|
| OQ-1 | Should per-aggregate regeneration (E5) be a single click, or gated behind a confirmation that explains the scope? | Product + UX | M3 |
| OQ-2 | What is the default quality threshold per rubric dimension, and who can change it? | AI Lead + Product | M2 |
| OQ-3 | For E8 global feedback, do we cap the number of blocks revised per "Apply globally" to control cost? | Product + AI Lead | M5 |
| OQ-4 | What is the retention policy for generations and their full agent traces? | DevOps + Sponsor | M0 |
| OQ-5 | Should the dashboard (E14) include per-user metrics, or only portfolio-level? | Product | M3 |
| OQ-6 | For E12 block-type extensibility, can the schema be edited after blocks of that type exist (and if so, how do we migrate)? | Backend Lead | M5 |

---

## 13. Cross-References

- **Project Charter** — `project-charter.md`
- **Business Requirements** — `BRD.md`
- **Glossary** — `docs/01-glossary.md` (forthcoming)
- **Bounded Context Map** — `docs/02-context-map.md` (forthcoming)
- **Architecture** — `docs/03-architecture.md` (forthcoming)
- **JSON Output Contract** — `BRD.md` §11
- **ADRs** — `docs/adr/` (forthcoming)
