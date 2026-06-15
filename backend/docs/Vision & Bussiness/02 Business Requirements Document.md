# Business Requirements Document (BRD)

## AI-Powered Course Generator Platform

> Document type: Business Requirements Document (BRD)
> Companion to: `project-charter.md`
> Status: Draft v0.3 · Owner: Product · Last updated: 2026-06-05
> This BRD is the business-facing specification of what the platform must do.
> Engineering-facing architecture lives in `docs/03-architecture.md` and ADRs.

---

## 1. Executive Summary

The AI-Powered Course Generator Platform is a system designed to accelerate and standardize the creation of educational content through the use of Large Language Models (LLMs) and AI-driven curriculum design workflows.

The platform enables educators, instructional designers, technical experts, organizations, and content creators to generate complete educational programs from a set of requirements, learning objectives, customization preferences, and domain-specific knowledge.

Unlike traditional content generation tools, the platform focuses on generating **structured learning experiences** composed of courses, modules, sections, and **typed instructional content blocks**. Users can continuously refine generated content through feedback mechanisms and customization controls, creating a collaborative **human-in-the-loop** curriculum design process.

**Generation is multi-agent and self-refining.** A folder of specialized agents (Planner, Author, PersonaAdapter, Evaluator, Refiner, ConsistencyChecker, PrerequisiteValidator, ContextSynthesizer) collaborate in an explicit **draft → evaluate → refine** loop, so the platform does not stop at the first LLM response — it improves the draft until it passes a quality rubric or a budget is exhausted.

**The final response is a structured JSON document** consumed by the web frontend, so course content, generation lineage, quality scores, outstanding issues, and recommended next actions are all machine-readable and renderable.

The platform's primary goal is to reduce the time, cost, and complexity associated with designing high-quality educational programs while maintaining consistency, scalability, and instructional quality.

---

## 2. Business Problem

Creating educational content is often a slow, expensive, and highly manual process requiring collaboration between:

- Subject Matter Experts (SMEs)
- Instructional Designers
- Technical Writers
- Educators
- Reviewers

Current challenges include:

##### 2.1 Time-Intensive Content Creation
Developing a complete course may require weeks or months of effort.

##### 2.2 Inconsistent Course Structures
Different authors often produce content with varying levels of depth,
organization, and quality.

##### 2.3 Limited Scalability
Organizations struggle to create large numbers of courses across multiple
domains.

##### 2.4 Knowledge Bottlenecks
Course quality often depends on the availability of a small number of experts.

##### 2.5 Difficulty Maintaining Content
Updating educational content to reflect new technologies, regulations, or
methodologies requires significant manual effort.

##### 2.6 Lack of Standardization
Organizations often lack a consistent framework for course design and content
organization.

##### 2.7 Single-Shot Generation Is Not Enough
Most existing AI generators emit one LLM response and stop. Educational content
demands pedagogical coherence, factual accuracy, audience fit, and internal
consistency — properties that are not reliably produced in a single pass and
require **evaluation and refinement**.

---

## 3. Business Opportunity

Advances in AI and LLM technologies create an opportunity to transform educational content production through:

- Automated curriculum generation
- Automated instructional content generation
- Standardized educational structures
- **Iterative, agent-driven content refinement**
- **Rubric-based quality evaluation at multiple granularities**
- Personalized learning content design
- Scalable content production workflows

This creates the possibility of generating high-quality educational content at a fraction of the cost and time required by traditional methods, with **observable quality signals** rather than opaque single-shot outputs.

---

## 4. Business Goals

#### Goal 1: Accelerate Course Creation
Reduce course creation time from weeks or months to hours or minutes.

**Success Indicators**
- Significant reduction in content creation effort.
- Faster curriculum development cycles.
- Rapid generation of new educational offerings.

#### Goal 2: Improve Content Consistency
Establish standardized educational structures across all generated courses.

**Success Indicators**
- Consistent curriculum organization.
- Standardized learning progression.
- Uniform instructional quality.

#### Goal 3: Increase Content Production Capacity
Enable organizations to create significantly more educational content without
proportional increases in staffing.

**Success Indicators**
- Increased number of courses produced.
- Reduced dependency on individual experts.
- Faster expansion into new domains.

#### Goal 4: Improve Content Maintainability
Enable efficient updates and regeneration of educational materials.

**Success Indicators**
- Faster content updates.
- Simplified revision workflows.
- Reduced maintenance costs.

#### Goal 5: Enable Personalized Course Design
Allow users to tailor generated courses according to audience needs, learning
objectives, domain requirements, and instructional preferences.

**Success Indicators**
- High degree of customization.
- Reduced manual editing effort.
- Improved user satisfaction.

#### Goal 6: Deliver Evaluable, Self-Refining Output
Move from "best-effort single response" to **measured, iterative improvement**.

**Success Indicators**
- Quality score uplift between draft and final response.
- Percentage of generations that pass the rubric on the first refinement cycle.
- Per-iteration quality trajectory is exposed to the user.

---

## 5. Business Objectives

The platform must enable users to:

| ID | Objective |
|---|---|
| BO-001 | Generate complete courses from a topic or learning objective. |
| BO-002 | Generate structured curricula consisting of modules, sections, and instructional content blocks. |
| BO-003 | Customize generated courses based on audience, difficulty, depth, instructional style, and learning goals. |
| BO-004 | Provide feedback and iteratively refine generated content. |
| BO-005 | Incorporate organizational knowledge and domain-specific context into generation workflows. |
| BO-006 | Support multiple AI providers without requiring curriculum redesign. |
| BO-007 | Enable reuse of generated content across different delivery formats. |
| BO-008 | Maintain version history and traceability throughout the content lifecycle. |
| BO-009 | Run a multi-agent generation pipeline that evaluates and refines its own output against a quality rubric. |
| BO-010 | Emit a structured, machine-readable JSON response consumable by the web frontend (course content + lineage + quality + issues + next actions). |
| BO-011 | Make per-iteration quality scores and outstanding issues visible to the user. |
| BO-012 | Allow targeted regeneration at course, module, section, or block granularity without regenerating unaffected content. |

---

## 6. Stakeholders

### 6.1 Primary Stakeholders (end users)
- **Content Creators** — individuals responsible for producing educational materials.
- **Instructional Designers** — professionals responsible for designing learning experiences.
- **Subject Matter Experts (SMEs)** — domain experts providing specialized knowledge.
- **Educators** — individuals delivering educational content.
- **Technical Writers** — professionals responsible for content clarity and documentation.
- **Corporate Training Teams** — organizations developing internal training programs.

### 6.2 Internal Stakeholders
- **Product Management** — defines product vision and priorities.
- **AI Engineering** — develops the agent folder, prompts, evaluation rubrics, and refinement loop.
- **Backend Engineering** — develops platform services and business logic.
- **Frontend Engineering** — consumes the JSON output contract and renders courses.
- **DevOps Engineering** — responsible for infrastructure, observability, and deployment.

### 6.3 Decision rights
- **Sponsor** — final scope and priority calls.
- **Product** — requirements, acceptance, trade-offs.
- **AI Lead** — owns the agent folder, evaluation rubric, and quality thresholds.
- **Engineering leads (BE/FE/AI)** — architecture, technical debt, quality.

---

## 7. Target Users

- **Individual Educators** — create courses for teaching and training purposes.
- **Technical Trainers** — develop technical learning materials.
- **Educational Institutions** — generate and maintain academic content.
- **Corporate Training Departments** — develop internal employee training programs.
- **Consulting Organizations** — produce client-specific training content.
- **Content Production Teams** — scale educational content creation workflows.

---

## 8. Business Capabilities

#### 8.1 Curriculum Design
Ability to generate and manage educational structures.
- Course generation
- Module generation
- Section generation
- Learning path design
- Learning objective generation

#### 8.2 Content Generation
Ability to generate instructional content.
- Explanations
- Examples
- Code samples
- Exercises
- Assessments
- Projects
- Visual descriptions

#### 8.3 Course Personalization
Ability to customize generated content.
- Audience targeting
- Difficulty selection
- Technical depth adjustment
- Learning style preferences
- Instructional strategy selection

#### 8.4 Feedback-Driven Refinement
Ability to iteratively improve generated content.
- Curriculum feedback
- Section feedback
- Block feedback
- Global feedback

#### 8.5 Context Management
Ability to enrich generation workflows with additional information.
- Text instructions
- Existing documentation
- Reference courses
- Domain knowledge
- Learning outcomes

#### 8.6 Version Management
Ability to track content evolution.
- Draft versions
- Revision history
- Regeneration history
- Change tracking

#### 8.7 Multi-Agent Self-Refinement (NEW)
Ability to produce higher-quality content than a single LLM call by orchestrating
specialized agents in an evaluate–refine loop.
- See §10 for the full specification.

#### 8.8 Structured JSON Output (NEW)
Ability to return generation results in a single, versioned JSON document that
the frontend can render directly and that contains course content, generation
lineage, evaluation results, outstanding issues, and next actions.
- See §11 for the contract.

---

## 9. Business Requirements

#### BR-001 — Course Generation
The platform shall generate complete courses from user-defined inputs.

#### BR-002 — Curriculum Structuring
The platform shall organize generated content into:

```
Course
 └── Module
      └── Section
           └── Content Block
```

#### BR-003 — Content Block Generation
The platform shall support generation of multiple instructional block types,
including at minimum:

Concept, Example, Code, Exercise, Solution, Challenge, Quiz, Key Points, Best Practices, Common Mistakes, Visual Explanation, Analogy, Reference.

#### BR-004 — Course Personalization
The platform shall support customization based on: audience, difficulty, learning objectives, technical depth, topic coverage, and instructional preferences.

#### BR-005 — Context Injection
The platform shall allow users to provide contextual information to guide generation (text instructions, documents, reference courses, domain knowledge, learning outcomes).

#### BR-006 — Feedback Processing
The platform shall allow users to iteratively modify generated content through structured feedback at the curriculum, section, block, and global levels.

#### BR-007 — Multi-Provider Support
The platform shall support multiple LLM providers behind a common abstraction, with no provider-specific concepts in the domain layer.

#### BR-008 — Version Control
The platform shall maintain historical versions of generated content with full lineage (inputs, prompt version, model version, agent trace).

#### BR-009 — Content Export
The platform shall support exporting generated content into multiple formats (Web, Markdown, PDF, LMS-compatible formats).

#### BR-010 — Multi-Agent Self-Refinement
The platform shall orchestrate a folder of specialized agents that collaboratively produce, evaluate, and refine content. The Creator agent drafts; the Evaluator agent scores and emits structured issues; the Refiner agent applies fixes. The loop terminates when the draft passes the quality rubric, a per-course iteration cap is reached, or a token/time budget is exhausted.

#### BR-011 — Evaluator-Critic Loop
The platform shall score every draft against a multi-dimensional rubric (accuracy, pedagogical clarity, structural compliance, depth appropriateness, audience alignment, consistency, completeness) and surface the score and outstanding issues to the user.

#### BR-012 — JSON Output Contract
The platform shall return a single, versioned JSON document on every completed
generation. The document must include the course payload, generation metadata
(including the full agent trace), evaluation results, outstanding issues, and
machine-readable next actions. The frontend shall not need to parse free-form
LLM output.

#### BR-013 — Per-Iteration Quality Visibility
The platform shall expose per-iteration quality scores and issue counts so the user can see the refinement trajectory (e.g. "iteration 1: 0.62 → iteration 2: 0.81 → pass").

#### BR-014 — Granular Regeneration
The platform shall allow targeted regeneration at the module, section, or block level without regenerating unaffected content. Targeted regeneration must run the same evaluate–refine loop on the targeted aggregate only.

#### BR-015 — Evaluation Rubric Versioning
The platform shall version the evaluation rubric and store the rubric version used for every generation, so quality scores are comparable over time.

#### BR-016 — Provider-Agnostic Agents
The agents in the agent folder shall be implemented behind ports. Swapping LLM providers (OpenAI, Anthropic, Google, others) shall not require changes to agent logic, prompts, or evaluation criteria.

---

## 10. Multi-Agent Self-Refinement Architecture

> Engineering-level detail lives in `docs/03-architecture.md` and the
> corresponding ADRs. This section is the business specification of the
> agent folder and the refinement loop.

### 10.1 The Agent Folder
A **folder of agents** is the organizational unit for all generation-time AI work. Each agent has a single responsibility, a typed input, a typed output, and a contract that does not depend on any specific LLM provider.

| Agent | Responsibility | Output |
|---|---|---|
| **ContextSynthesizer** | Normalize and merge all user inputs (topic, audience, outcomes, references, domain knowledge, feedback history) into a single context payload. | `GenerationContext` |
| **CurriculumPlanner** | Design the high-level course structure: modules, section topics, learning objectives, prerequisite graph. | `CourseSkeleton` |
| **SectionAuthor** | Author the content blocks within a single section according to its type composition rules. | `SectionDraft` |
| **PersonaAdapter** | Rewrite/adapt drafted content for the target audience profile and instructional style. | `AdaptedSection` |
| **ConsistencyChecker** | Detect cross-section and cross-block inconsistencies (terminology, ordering, contradictions). | `ConsistencyReport` |
| **PrerequisiteValidator** | Verify the learning progression is well-ordered and that prerequisites are introduced before they are needed. | `ProgressionReport` |
| **Evaluator** (Critic) | Score the current draft against the rubric and emit structured issues with severity, scope, and category. | `EvaluationReport` |
| **Refiner** | Apply the Evaluator's issues (and other agents' reports) to produce a revised draft. | `RefinedDraft` |
| **Orchestrator** | Coordinate the agent folder: schedule agents, manage the refinement loop, enforce budgets, emit the final JSON contract. | `GenerationResult` |

The **Orchestrator is the only agent that writes to persistence** and is the only component the frontend talks to directly. All other agents are stateless and exchange typed documents.

### 10.2 The Refinement Loop
For every generation request, the Orchestrator runs:

```
1. ContextSynthesizer       → GenerationContext
2. CurriculumPlanner        → CourseSkeleton
3. for each section:
       SectionAuthor        → SectionDraft
       PersonaAdapter       → AdaptedSection
4. ConsistencyChecker       → ConsistencyReport
5. PrerequisiteValidator    → ProgressionReport
6. Evaluator                → EvaluationReport
7. while not passed and iterations < max and budget remains:
       Refiner              → RefinedDraft
       ConsistencyChecker   → ConsistencyReport
       PrerequisiteValidator→ ProgressionReport
       Evaluator            → EvaluationReport
8. Orchestrator             → GenerationResult (JSON contract)
```

### 10.3 Termination Criteria
The loop terminates when **any** of the following is true:
- All rubric dimensions meet their configured thresholds (success).
- A per-course iteration cap is reached (partial success, returned with issues).
- A token or wall-clock budget is exhausted (partial success, returned with issues).
- The user aborts the job (partial success, draft is preserved).

In every termination case, the final JSON document is returned with the termination reason recorded in `generation.refinement.termination_reason`.

### 10.4 Quality Rubric (business-owned)
The Evaluator scores every draft on these dimensions. Thresholds and weights are versioned and configurable, but the dimensions themselves are stable.

| Dimension | What it measures |
|---|---|
| Accuracy | Factual correctness, no hallucinations within the supported domain. |
| Pedagogical clarity | Concepts are introduced before they are used; explanations are unambiguous. |
| Structure compliance | Course conforms to the Course → Module → Section → Block hierarchy and to the block-type taxonomy. |
| Depth appropriateness | Depth matches the audience profile and the configured depth level. |
| Audience alignment | Tone, examples, and prerequisites fit the target learner. |
| Consistency | Terminology, notation, and style are coherent across modules/sections/blocks. |
| Completeness | All required topics, learning outcomes, and block types are present. |

### 10.5 Failure Handling
- If any agent fails, the Orchestrator records the failure in the agent trace and routes around it when possible (e.g. skip PrerequisiteValidator, fall back to a deterministic structural check).
- The platform never returns free-form error text to the frontend. All failures surface as structured `issues` entries with a stable error code.

---

## 11. JSON Output Contract (Frontend-Facing)

> The frontend **must not parse free-form LLM output**. Every completed
> generation returns a single JSON document conforming to the schema below.
> The schema is versioned; breaking changes bump `schema_version` and the
> major version of the API.

### 11.1 Top-Level Shape

```jsonc
{
  "schema_version": "1.0.0",
  "course": { /* Course payload, see §11.2 */ },
  "generation": { /* Generation metadata + agent trace, see §11.3 */ },
  "evaluation": { /* Quality rubric results, see §11.4 */ },
  "issues": [ /* Outstanding issues, see §11.5 */ ],
  "next_actions": [ /* Machine-readable actions for the UI, see §11.6 */ ]
}
```

### 11.2 `course` — Course Payload

```jsonc
{
  "id": "uuid",
  "title": "string",
  "summary": "string",
  "language": "en",
  "version": 1,
  "audience": {
    "profile": "beginner | professional | engineer | architect | manager | researcher | student",
    "prerequisites": ["string"]
  },
  "learning_outcomes": ["string"],
  "metadata": {
    "estimated_duration_minutes": 0,
    "difficulty": "beginner | intermediate | advanced | expert",
    "tags": ["string"]
  },
  "modules": [
    {
      "id": "uuid",
      "title": "string",
      "summary": "string",
      "order": 0,
      "sections": [
        {
          "id": "uuid",
          "title": "string",
          "order": 0,
          "learning_objectives": ["string"],
          "blocks": [
            {
              "id": "uuid",
              "type": "concept | example | code | exercise | solution | challenge | quiz | key_points | best_practices | common_mistakes | visual_explanation | analogy | reference",
              "order": 0,
              "content": { "/* type-specific shape, see §11.2.1 */" },
              "metadata": {
                "estimated_time_minutes": 0,
                "difficulty": "beginner | intermediate | advanced"
              }
            }
          ]
        }
      ]
    }
  ]
}
```

#### 11.2.1 Block content shapes (per `type`)

| `type` | `content` shape |
|---|---|
| `concept` | `{ "markdown": "string", "key_takeaways": ["string"] }` |
| `example` | `{ "markdown": "string", "scenario": "string" }` |
| `code` | `{ "language": "string", "source": "string", "explanation": "string", "runnable": false }` |
| `exercise` | `{ "prompt": "string", "hints": ["string"], "solution_ref": "block_id" }` |
| `solution` | `{ "markdown": "string", "walkthrough": "string" }` |
| `challenge` | `{ "prompt": "string", "criteria": ["string"] }` |
| `quiz` | `{ "questions": [ { "question": "string", "choices": ["string"], "answer_index": 0, "explanation": "string" } ] }` |
| `key_points` | `{ "items": ["string"] }` |
| `best_practices` | `{ "items": ["string"] }` |
| `common_mistakes` | `{ "items": [ { "mistake": "string", "fix": "string" } ] }` |
| `visual_explanation` | `{ "description": "string", "asset_ref": "string|null" }` |
| `analogy` | `{ "markdown": "string", "maps_to": "string" }` |
| `reference` | `{ "items": [ { "title": "string", "url": "string", "kind": "article | book | video | doc" } ] }` |

### 11.3 `generation` — Metadata & Agent Trace

```jsonc
{
  "job_id": "uuid",
  "provider": "openai | anthropic | google",
  "model": "string",
  "prompt_version": "string",
  "rubric_version": "string",
  "started_at": "ISO-8601",
  "completed_at": "ISO-8601",
  "tokens": { "input": 0, "output": 0 },
  "agent_trace": [
    {
      "agent": "context_synthesizer | curriculum_planner | section_author | persona_adapter | consistency_checker | prerequisite_validator | evaluator | refiner | orchestrator",
      "phase": "draft | evaluate | refine | finalize",
      "iteration": 0,
      "started_at": "ISO-8601",
      "completed_at": "ISO-8601",
      "tokens_in": 0,
      "tokens_out": 0,
      "status": "success | failed | skipped"
    }
  ],
  "refinement": {
    "iterations": 0,
    "max_iterations": 0,
    "termination_reason": "quality_threshold | max_iterations | budget_exhausted | user_aborted"
  }
}
```

### 11.4 `evaluation` — Quality Rubric Results

```jsonc
{
  "overall_score": 0.0,            // 0.0 – 1.0
  "passed": true,
  "rubric": {
    "accuracy": 0.0,
    "pedagogical_clarity": 0.0,
    "structure_compliance": 0.0,
    "depth_appropriateness": 0.0,
    "audience_alignment": 0.0,
    "consistency": 0.0,
    "completeness": 0.0
  },
  "thresholds": {
    "overall": 0.0,
    "per_dimension": { "accuracy": 0.0, "completeness": 0.0 }
  },
  "iteration_scores": [ 0.62, 0.74, 0.81 ]   // one entry per iteration
}
```

### 11.5 `issues` — Outstanding Problems

```jsonc
[
  {
    "id": "uuid",
    "severity": "info | warning | error | blocker",
    "scope": "course | module | section | block",
    "target_id": "uuid",
    "category": "factual | pedagogical | structural | style | completeness | consistency",
    "message": "string",
    "suggestion": "string",
    "auto_fixable": true
  }
]
```

### 11.6 `next_actions` — UI-Available Actions

```jsonc
[
  {
    "type": "regenerate_block | regenerate_section | regenerate_module | request_user_input | export | publish | refine_again",
    "target_id": "uuid",
    "label": "string",          // human-readable button text
    "description": "string"
  }
]
```

### 11.7 Frontend Contract Guarantees
- The document is returned in a **single response** at the end of a generation (or as the final frame of a streaming channel). Intermediate iterations may be streamed as progress events but are not authoritative until finalized.
- The schema is **versioned**. The frontend pins to a `schema_version` and refuses to render unknown major versions.
- `issues` and `next_actions` are **the primary UI surface for quality**. The frontend renders them as inline warnings, fix suggestions, and one-click action buttons.

---

## 12. Business Constraints

- **BC-001** — Generated content must remain editable by users.
- **BC-002** — The platform must remain provider-agnostic (applies to agents
  as well: agents must not contain provider-specific logic).
- **BC-003** — Generated content must be structured and machine-readable
  (i.e. valid against the JSON contract in §11).
- **BC-004** — The system must support future expansion of instructional
  block types and of the agent folder.
- **BC-005** — The platform must support iterative refinement workflows
  (user-driven and agent-driven).
- **BC-006** — Evaluation criteria must be versioned and reproducible.
- **BC-007** — All generation lineage (prompts, models, agent trace, rubric
  version) must be persisted with the generated course.

---

## 13. Risks

| Risk | Description | Mitigation |
|---|---|---|
| Content Accuracy | AI-generated content may contain inaccuracies. | Evaluator agent + human-in-the-loop review + per-claim scoring. |
| Hallucinations | Models may generate incorrect information. | Evaluator-driven loop + block-level grounding checks. |
| Provider Dependency | External AI services may change behavior. | Provider port + multi-provider agents + rubric stability tests. |
| Curriculum Quality | Generated learning paths may require human review. | AI-Assisted Curriculum Review + visible quality scores + suggested fixes. |
| Cost Control | Multi-agent loops can multiply token spend. | Per-course token budget, iteration cap, tiered models by agent role, caching of intermediate results. |
| User Expectations | Users may expect fully autonomous course creation. | UI clearly shows quality scores, outstanding issues, and next actions. |
| Refinement Loop Stalls | Refiner may not improve the Evaluator's score. | Iteration cap, score-trajectory monitoring, escalation to user. |
| Non-Deterministic Quality | Quality may vary run-to-run. | Rubric versioning, seeded runs where supported, lineage capture for every run. |
| Prompt / Rubric Drift | Evaluation criteria may drift over time. | Versioned rubrics, eval suite regression tests, change log. |
| Agent Coupling | Tight coupling between agents slows evolution. | Strict typed contracts between agents; Orchestrator is the only writer to persistence. |

---

## 14. Key Success Metrics

### 14.1 Operational Metrics
- Course generation time (end-to-end)
- Refinement iterations to pass
- Token spend per course (and per agent)
- Export completion rate
- Feedback processing time

### 14.2 Adoption Metrics
- Number of generated courses
- Number of active users
- Number of refinement cycles per course
- Usage of per-aggregate regeneration (block / section / module)

### 14.3 Quality Metrics
- **Rubric pass rate** (percentage of generations passing on first refinement cycle)
- **Average quality uplift** (final score − initial draft score)
- **Issue density** (issues per block, per category)
- **User satisfaction** (CSAT)
- **Curriculum acceptance rate** (draft → published without manual rewrite)
- **Manual editing reduction** (% of blocks edited by humans)
- **Content reuse rate** (blocks reused across courses)

### 14.4 Business Metrics
- Reduction in content creation effort
- Reduction in content production cost
- Increase in course production volume
- Increase in curriculum development speed
- Provider-agnosticism score (e.g. swap to a new provider with no domain changes)

---

## 15. Business Vision Statement

The platform will become a comprehensive AI-assisted course design ecosystem that enables organizations and individuals to **generate, customize, refine, maintain, and scale** educational content through:

- Structured curriculum design
- A folder of cooperating AI agents that draft, evaluate, and refine
- Human-in-the-loop feedback workflows at every level of granularity
- Provider-agnostic AI capabilities
- Versioned quality evaluation with transparent, machine-readable output

Its long-term objective is not merely to automate content generation, but to establish a **standardized operating model for educational content creation, management, and continuous improvement** — one in which every generated course arrives with its lineage, its quality score, and a clear set of next actions a human can take.

---

## 16. Cross-References

- **Project Charter** — `project-charter.md` (vision, scope, architecture principles, milestones).
- **Glossary** — `docs/01-glossary.md` (ubiquitous language for the domain).
- **Architecture** — `docs/03-architecture.md` (Hexagonal + DDD layout, ports, adapters, agent folder as a subdomain).
- **API Contract** — `docs/06-api.md` (REST endpoints that wrap the JSON output contract in §11).
- **ADRs** — `docs/adr/` (Hexagonal layout, provider-agnostic agents, evaluation rubric versioning, refinement loop termination policy, JSON contract as the single frontend interface).
