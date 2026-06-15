# Project Charter — AI-Powered Course Generator Platform

> Status: Draft v0.2 · Owner: Product · Last updated: 2026-06-05
> This charter is the single source of truth for project scope, goals, stakeholders, success criteria, and constraints. Changes require Product + Engineering sign-off.

---

## 1. Document Control

| Field | Value |
|---|---|
| Project codename | CourseForge |
| Document version | 0.2 (Draft) |
| Author | Product Management |
| Reviewers | Backend Lead, Frontend Lead, AI Lead, DevOps Lead |
| Approvers | Sponsor, Head of Engineering |
| Cadence | Reviewed at end of each sprint; re-baselined on scope changes |

---

## 2. Executive Summary

The **AI-Powered Course Generator Platform** (working name: *CourseForge*) is a full-stack system that turns a topic specification — augmented with audience, pedagogy, and organizational context — into a complete, hierarchically structured course. Content is generated as **typed instructional blocks** (concept, example, code, exercise, quiz, etc.), not as monolithic text, which enables rich rendering, fine-grained editing, multi-format export, and incremental refinement.

Unlike one-shot generators, CourseForge is a **collaborative course design environment**: users guide, review, and continuously refine the curriculum through structured feedback at the curriculum, section, and block level. The platform is **LLM-provider-agnostic** and built on Hexagonal Architecture + DDD, so new providers and new block types are plug-ins, not rewrites.

---

## 3. Vision & Purpose

**Vision.** Make high-quality, pedagogically coherent course creation a matter of minutes — and make refining that course as natural as editing a document.

**Purpose.** Design and operate a platform that:

1. Automates generation of structured educational courses using LLMs.
2. Produces content as a **Course → Module → Section → ContentBlock** hierarchy
   with explicit block semantics.
3. Exposes that content through APIs and a web application optimized for
   navigation, review, editing, and publishing.
4. Reduces the cost, time, and expertise required to design and maintain
   educational programs at scale.

---

## 4. Problem Statement

Creating high-quality educational content is labor-intensive. It requires subject matter expertise, instructional design knowledge, and significant production effort. Organizations and educators routinely need to:

- Design complete learning paths aligned with specific outcomes.
- Define curriculum structures that progress from foundations to mastery.
- Produce content at multiple levels of detail (overview, deep dive, exercise).
- Maintain consistency across large collections of courses.
- Update and expand materials efficiently as domains evolve.

Current manual approaches are slow, costly, and difficult to scale. Existing AI generators tend to produce large unstructured text blobs, which are hard to review, edit, render richly, export, or adapt to different audiences.

---

## 5. Objectives

#### 5.1 Business Objectives

| ID | Objective | Measure |
|---|---|---|
| B1 | Accelerate course creation from weeks/months to minutes | Time from topic input to first reviewable draft |
| B2 | Reduce content production cost | Hours of human effort per course |
| B3 | Standardize course structure across domains | % of courses passing structural validation |
| B4 | Enable scaling of content production | Courses generated per quarter |
| B5 | Avoid LLM vendor lock-in | Providers integrated behind a common abstraction |

#### 5.2 Technical Objectives

| ID | Objective | Measure |
|---|---|---|
| T1 | Provider-agnostic LLM orchestration | New provider integrated in ≤ N dev-days, no domain changes |
| T2 | Modular, extensible architecture | New block type or new context added without core changes |
| T3 | Enforce predefined educational structures | 100% of generated content conforms to the content model |
| T4 | API-first delivery | All capabilities reachable via versioned REST APIs |
| T5 | Reproducible, traceable, versioned generations | Every course has a lineage record of inputs, prompts, and provider versions |

---

## 6. Scope

#### 6.1 In Scope (v1)

**Backend platform** — Hexagonal Architecture (Ports & Adapters) + DDD.

Capabilities:
- Course / curriculum / module / section / block generation orchestration
- Content validation and refinement workflows
- Version management (course, section, block levels)
- Prompt management system
- Generation pipelines with retry, partial completion, and traceability
- AI provider abstraction layer

AI providers (initial set, pluggable):
- OpenAI
- Anthropic
- Google
- Additional providers via adapters

**Frontend application** — web-based interface supporting:
- Course creation requests
- Generation workflow monitoring
- Content review and editing
- Version comparison
- Curriculum visualization
- Export and publishing workflows

**Educational content model** — typed content blocks are a first-class
domain concept (see §8).

#### 6.2 Out of Scope (v1)

- LMS functionality (SCORM/xAPI, enrollment, grading workflows)
- Retrieval-Augmented Generation (RAG) over a knowledge base
- Student accounts, enrollment, or progress tracking
- Payments, billing, certification issuance
- Video or audio generation
- Real-time collaborative editing
- Mobile applications
- Learning analytics dashboards
- Adaptive learning systems (closed-loop personalization from learner behavior)

These may be considered in future releases; see §13.

---

## 7. Educational Content Model

#### 7.1 Hierarchy

```
Course
 └── Module
      └── Section
           ├── Content Block
           ├── Content Block
           └── Content Block
```

Each layer is a first-class aggregate with its own identity, validation rules,
and version history.

#### 7.2 Content Blocks (v1 set)

| Block | Purpose | Default render |
|---|---|---|
| Concept | Introduce / explain a theoretical concept | Rich-text article |
| Example | Practical demonstration | Highlighted example panel |
| Code | Executable source code | Syntax-highlighted editor |
| Exercise | Practice activity | Interactive activity |
| Solution | Reference solution for an exercise | Reveal-on-demand panel |
| Challenge | Advanced mastery problem | Project/task card |
| Quiz | Knowledge validation | Assessment component |
| Key Points | Summary of critical information | Summary card |
| Best Practices | Recommended approaches | Card list |
| Common Mistakes | Frequent errors to avoid | Warning list |
| Visual Explanation | Diagrams, charts, illustrations | Diagram viewer |
| Analogy | Comparison to simplify a concept | Aside callout |
| Reference | External resources | Resources section |

#### 7.3 Why typed blocks
Typed blocks are a **core domain decision** because they affect:
- Generation (block-specific prompts and constraints)
- Storage (typed schema, not opaque text)
- Rendering (block-specific components)
- Editing (block-specific validators)
- Export (multi-format: Web, PDF, LMS, Markdown)
- Future AI workflows (regenerate *one* block, not the whole course)

#### 7.4 Extensibility
New block types (Video, Audio, Interactive Simulation, Flashcard, AI Tutor
Conversation, Lab Environment, Dataset, Case Study, Project, Peer Review)
are added by implementing a block-type port — **no changes to the core domain
model**.

---

## 8. Platform Capabilities

### 8.1 Generation
- End-to-end course generation from a topic specification
- Per-aggregate regeneration (course, module, section, block)
- Deterministic, reproducible runs given the same inputs and provider version

### 8.2 Customization
Users can shape every dimension of generation:

- **Topic customization** — include/exclude topics, mandatory/optional concepts, ordering, terminology, required tools/frameworks
- **Curriculum structure** — number of modules, sections per module, lessons per section, learning path, learning objectives, prerequisites, capstone, assessment strategy
- **Content depth** — level of detail
- **Technical vs. practical balance** — theoretical, practical, academic, industry-oriented, research-oriented, certification-oriented
- **Audience profile** — beginners, professionals, engineers, architects, managers, researchers, students
- **Learning style preferences**
- **Content block composition** — which block types to generate, and in what proportion
- **Technology & tooling preferences**
- **Organizational standards** — injected as generation constraints

#### 8.3 Context Injection
Generation is driven by more than a topic string. Supported context sources:

- **Text instructions** — free-form guidance, preferences, constraints
- **Existing documentation** — technical specs, internal docs, KB articles, design docs, product docs, training manuals, architecture docs
- **Reference courses** — internal training, university syllabi, certification programs, online platforms, corporate learning paths (analyzed for *structure and pedagogy*, not duplicated)
- **Domain knowledge** — company standards, regulations, methodologies, frameworks, processes, terminology, compliance, best practices
- **Learning outcomes** — explicit, measurable goals that drive topic selection, exercise generation, and assessment

#### 8.4 Feedback-Driven Refinement
Four levels of feedback, each acting at a different granularity:

- **Curriculum feedback** — structure, learning path, topic coverage, sequencing
- **Section feedback** — depth, flow, balance of theory and practice
- **Block feedback** — targeted edits to a single block
- **Global feedback** — course-wide style, standards, audience adjustments

Feedback must be implementable **without regenerating unaffected content**;
this is a non-functional requirement (see §11 / T2).

#### 8.5 AI-Assisted Curriculum Review
Before generation, the platform may emit recommendations such as:
- "This course may be missing: testing, deployment, monitoring."
- "The learning progression may be too steep."
- "Module overlap detected in §3.2 and §5.1."

This positions the platform as an **active instructional design assistant**,
not a passive text generator.

#### 8.6 New Core Capabilities (engineered as named subdomains)

| Capability | Responsibility |
|---|---|
| Course Personalization Engine | Learning preferences, audience, difficulty, pedagogy, content composition |
| Feedback Processing Engine | Curriculum mods, regeneration requests, refinements, incremental updates |
| Context Management System | Instructions, supplemental docs, organizational standards, constraints |
| Curriculum Validation Engine | Coverage, progression, prerequisites, redundancy, quality checks |

---

## 9. Architecture Principles

1. **Hexagonal Architecture (Ports & Adapters)** — domain has zero dependency on infrastructure; all I/O lives behind ports.
2. **DDD** — Course, Module, Section, ContentBlock, GenerationJob, Context, Feedback are bounded aggregates; ubiquitous language is enforced in code.
3. **Provider-agnostic LLM layer** — providers are adapters behind a `LLMProvider` port; prompts are first-class artifacts.
4. **Typed content blocks** — block types are domain concepts, not UI affordances.
5. **Reproducibility by default** — every generation records inputs, prompt version, model version, and seed where applicable.
6. **API-first** — all capabilities are exposed via versioned REST APIs; the frontend is a consumer, not a privileged client.
7. **Observability from day one** — structured logs, traces, and metrics for every generation phase.

---

## 10. Key Deliverables

### Backend
- Domain model (Course / Module / Section / ContentBlock aggregates)
- Course Generation Engine
- AI Agents (planner, drafter, validator, refiner)
- LLM Abstraction Layer
- REST APIs (generation, management, publishing)
- Persistence layer
- Workflow orchestration
- Prompt management system
- Context management system
- Feedback processing engine
- Curriculum validation engine

### Frontend
- Course generation interface
- Course visualization interface
- Content editing interface
- Administrative dashboard

### Infrastructure
- Deployment pipelines (CI/CD)
- Monitoring and observability
- Centralized logging
- Configuration management
- Secrets management

---

## 11. Success Criteria

The project is successful when **all** of the following hold:

- A complete course can be generated from a topic specification.
- Generated content follows the predefined hierarchical structure (Course → Module → Section → ContentBlock) **and** the agreed block-type taxonomy.
- The system supports multiple LLM providers through a common abstraction.
- A new AI provider can be integrated without changes to the domain layer.
- Generated content can be reviewed, edited, and displayed through the web interface.
- Course generation workflows are reproducible, traceable, and versioned.
- Users can customize curriculum structure, depth, audience, and instructional style.
- Users can inject additional context and domain knowledge into generation.
- Users can iteratively refine generated content through structured feedback at curriculum, section, block, and global levels.
- Course modifications can be performed **without regenerating the entire curriculum** for unaffected aggregates.
- Generated content remains traceable, reproducible, and versioned across refinement cycles.
- The system can adapt content to different audiences, learning objectives, and pedagogical strategies.
- New customization dimensions can be introduced without modifying the core domain model.

Collectively, these turn the platform into a **Course Design Operating System**: generation, customization, review, feedback, and continuous refinement are first-class domain concepts.

---

## 12. Future Extensibility (informational, not committed)

- New block types (Video, Audio, Simulation, Flashcard, AI Tutor, Lab, Dataset, Case Study, Project, Peer Review)
- LMS export (SCORM / xAPI)
- RAG over organizational knowledge bases
- Adaptive learning (closed-loop personalization from learner behavior)
- Mobile clients
- Multi-tenant SaaS mode

---

## 13. Assumptions

- LLM providers offer APIs with sufficient reliability and rate limits for the target throughput.
- A single-tenant deployment is sufficient for v1; multi-tenant is a future concern.
- Generated content will be reviewed by a human before publication; the platform does not auto-publish.
- The team has access to subject matter experts for evaluation and prompt iteration.
- The frontend will be a SPA; no native mobile in v1.

## 14. Constraints

- **Provider neutrality**: no provider-specific concepts in the domain layer.
- **Data residency**: content is stored in the customer's selected region (to be confirmed in the technical design).
- **Reproducibility**: the same inputs, prompt version, and model version must yield the same outputs (best-effort with non-deterministic providers is acceptable if the lineage is fully recorded).
- **Security**: no prompt or context may leak across courses or tenants.
- **Budget**: v1 must be deliverable within agreed runway; provider cost is a first-class design concern (caching, token budgets, prompt sizing).

## 15. Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Provider API instability / rate limits | Med | High | Provider abstraction, retries, circuit breakers, prompt caching |
| Hallucinated or low-quality content | Med | High | Block-level validation, human-in-the-loop review, Curriculum Validation Engine |
| Prompt drift across versions | Med | Med | Prompt management system with versioning and eval suite |
| Cost overruns from large generations | Med | Med | Token budgets per course, caching, tiered models by task |
| Scope creep (LMS / RAG / mobile) | High | Med | Hard "out of scope" gate in §6.2; re-charter required to add |
| Team capacity vs. ambition | Med | High | MVP-first slicing, vertical slicing, defined Definition of Done |

## 16. High-Level Milestones (indicative)

| Milestone | Outcome |
|---|---|
| M0 — Foundations | Domain model, ports, persistence, one mocked provider, OpenAPI stub |
| M1 — First vertical slice | Topic → course draft in DB, CLI + Swagger only, single provider |
| M2 — Provider abstraction live | ≥ 2 providers behind the port, prompt management v1 |
| M3 — Web app v1 | Generation UI, review, edit, version compare, block rendering |
| M4 — Customization & context | All §9.2 and §9.3 capabilities reachable from UI |
| M5 — Feedback loops | §9.4 implemented at all four levels, partial regeneration |
| M6 — Hardening | Observability, evals, security review, performance budget |
| GA | v1 launch readiness review passed |

## 17. Glossary

- **Course** — top-level learning unit; owns modules.
- **Module** — major thematic grouping within a course; owns sections.
- **Section** — focused instructional unit on a single topic; owns content blocks.
- **Content Block** — typed, semantically meaningful unit of instructional content.
- **GenerationJob** — orchestrated run that produces or refines a course aggregate.
- **Context** — the set of inputs (topic, audience, outcomes, reference materials, etc.) that drive a generation run.
- **Feedback** — structured user input that drives targeted regeneration.
- **Provider** — an external LLM service, accessed through the abstraction layer.
- **Port** — a domain-defined interface that infrastructure adapters implement.
- **Adapter** — infrastructure-side implementation of a port (e.g. OpenAI adapter).