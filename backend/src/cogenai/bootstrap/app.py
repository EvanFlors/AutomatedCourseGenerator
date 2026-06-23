import uuid
from datetime import datetime
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

from cogenai.agents.config import AgentConfig
from cogenai.bootstrap import get_settings
from cogenai.bootstrap.container import get_llm_provider
from cogenai.bootstrap.logging import configure_logging, get_logger
from cogenai.domain.course.entities import Course

logger = get_logger(__name__)

# Store for jobs (in-memory for MVP)
jobs_store = {}


def create_app() -> FastAPI:

    # Configure logging
    configure_logging()

    # Settings
    settings = get_settings()

    # Create app
    app = FastAPI(
        title=settings.app_name,
        debug=settings.debug,
        version="1.0.0",
    )

    # Health check endpoint
    @app.get("/health")
    async def health_check():
        return {"status": "healthy", "environment": settings.app_env}

    # Generate course endpoint
    @app.post("/v1/courses/generate")
    async def generate_course(request: dict):
        try:
            # Extract parameters
            topic = request.get("topic", "")
            audience = request.get("audience", "beginner")
            difficulty = request.get("difficulty", "beginner")
            learning_outcomes = request.get("learning_outcomes", [])
            text_instructions = request.get("text_instructions", "")

            if not topic:
                raise HTTPException(status_code=400, detail="Topic is required")
            if not learning_outcomes:
                raise HTTPException(status_code=400, detail="At least one learning outcome is required")

            # Get LLM provider
            llm_provider = get_llm_provider()

            # Create agent config
            agent_config = AgentConfig.default(model_name=settings.model or "gpt-4")

            # Step 0: Check availability (Fail fast)
            llm_provider.health_check()

            # Step 1: ContextSynthesizer
            from cogenai.agents_implementations.context_synthesizer import (
                ContextSynthesizerAgent,
                ContextSynthesizerInput,
            )
            ctx_input = ContextSynthesizerInput(
                topic=topic,
                audience=audience,
                difficulty=difficulty,
                learning_outcomes=tuple(learning_outcomes),
                text_instructions=text_instructions,
            )
            ctx_agent = ContextSynthesizerAgent(agent_config, llm_provider)
            context = ctx_agent.run(ctx_input)

            # Step 2: CurriculumPlanner
            from cogenai.agents_implementations.curriculum_planner import (
                CurriculumPlannerAgent,
                CurriculumPlannerInput,
            )
            planner_input = CurriculumPlannerInput(
                context=context,
                num_modules=request.get("num_modules", 4),
                sections_per_module=request.get("sections_per_module", 4),
            )
            planner_agent = CurriculumPlannerAgent(agent_config, llm_provider)
            skeleton = planner_agent.run(planner_input)

            # Step 3: Generate sections
            all_sections = []
            from cogenai.agents_implementations.content_block_generator import (
                ContentBlockGeneratorAgent,
                ContentBlockGeneratorInput,
            )
            from cogenai.agents_implementations.persona_adapter import (
                PersonaAdapterAgent,
                PersonaAdapterInput,
            )
            from cogenai.agents_implementations.section_author import (
                SectionAuthorAgent,
                SectionAuthorInput,
            )

            for section_spec in skeleton.sections:
                author_input = SectionAuthorInput(
                    section_spec=section_spec,
                    context=context,
                    skeleton=skeleton,
                )
                author_agent = SectionAuthorAgent(agent_config, llm_provider)
                draft = author_agent.run(author_input)

                # Persona adapter
                adapter_input = PersonaAdapterInput(
                    draft=draft,
                    audience=audience,
                    strategy=request.get("strategy", "example_driven"),
                )
                adapter_agent = PersonaAdapterAgent(agent_config, llm_provider)
                adapted = adapter_agent.run(adapter_input)

                # ContentBlockGenerator
                block_input = ContentBlockGeneratorInput(
                    section_spec=section_spec,
                    adapted_section=adapted,
                    context=context,
                )
                block_agent = ContentBlockGeneratorAgent(agent_config, llm_provider)
                generated_blocks = block_agent.run(block_input)

                all_sections.append((section_spec, adapted, generated_blocks.blocks))

            # Step 4: Create course with modules
            from cogenai.domain.course.entities import Module, Section
            from cogenai.domain.shared.value_objects import new_module_id, new_section_id

            sections_per_module = request.get("sections_per_module", 4)
            modules = []

            sorted_sections = sorted(skeleton.sections, key=lambda s: s.order)
            sorted_modules = sorted(skeleton.modules, key=lambda m: m.order)

            blocks_by_title = {spec.title: blocks for spec, _, blocks in all_sections}

            for module_idx, module_spec in enumerate(sorted_modules):
                start_idx = module_idx * sections_per_module
                end_idx = start_idx + sections_per_module
                module_section_specs = sorted_sections[start_idx:end_idx]

                module_sections = []
                for section_idx, section_spec in enumerate(module_section_specs):
                    blocks = blocks_by_title.get(section_spec.title, tuple())
                    section = Section(
                        id=new_section_id(),
                        title=section_spec.title,
                        order=section_idx,
                        learning_objectives=list(section_spec.learning_objectives),
                        blocks=blocks,
                    )
                    module_sections.append(section)

                module = Module(
                    id=new_module_id(),
                    title=module_spec.title,
                    order=module_spec.order,
                    sections=tuple(module_sections),
                )
                modules.append(module)

            course = Course(
                title=f"Course on {topic}",
                summary=f"A comprehensive course about {topic}",
                learning_outcomes=tuple(learning_outcomes),
                modules=tuple(modules),
            )

            # Step 5: Evaluate
            from cogenai.agents_implementations.evaluator import EvaluatorAgent, EvaluatorInput
            eval_input = EvaluatorInput(
                course=course,
                rubric_version="1.0.0",
            )
            eval_agent = EvaluatorAgent(agent_config, llm_provider)
            report = eval_agent.run(eval_input)

            # Create response
            job_id = str(uuid.uuid4())
            now = datetime.now().isoformat()

            # Build response as dict
            response = {
                "schema_version": "1.0.0",
                "course": {
                    "id": job_id,
                    "title": f"Course on {topic}",
                    "summary": f"A comprehensive course about {topic}",
                    "language": "en",
                    "version": 1,
                    "learning_outcomes": learning_outcomes,
                    "metadata": {
                        "estimated_duration_minutes": 0,
                        "difficulty": difficulty,
                        "tags": []
                    },
                    "modules": [
                        {
                            "id": str(m.id),
                            "title": m.title,
                            "summary": m.summary,
                            "order": m.order,
                            "sections": [
                                {
                                    "id": str(s.id),
                                    "title": s.title,
                                    "order": s.order,
                                    "learning_objectives": list(s.learning_objectives),
                                    "blocks": [
                                        {
                                            "id": str(b.id),
                                            "type": b.type,
                                            "order": b.order,
                                            "content": b.content,
                                            "estimated_time_minutes": b.estimated_time_minutes,
                                            "difficulty": b.difficulty,
                                        }
                                        for b in s.blocks
                                    ],
                                }
                                for s in m.sections
                            ]
                        }
                        for m in course.modules
                    ]
                },
                "generation": {
                    "job_id": job_id,
                    "provider": settings.llm_provider,
                    "model": settings.model or "gpt-4",
                    "prompt_version": "1.0.0",
                    "rubric_version": "1.0.0",
                    "started_at": now,
                    "completed_at": now,
                    "tokens": {
                        "input_tokens": 0,
                        "output_tokens": 0
                    },
                    "agent_trace": [
                        {"agent": "context_synthesizer", "phase": "draft", "iteration": 0, "status": "success"},
                        {"agent": "curriculum_planner", "phase": "draft", "iteration": 0, "status": "success"},
                        {"agent": "section_author", "phase": "draft", "iteration": 0, "status": "success"},
                        {"agent": "persona_adapter", "phase": "draft", "iteration": 0, "status": "success"},
                        {"agent": "content_block_generator", "phase": "draft", "iteration": 0, "status": "success"},
                        {"agent": "evaluator", "phase": "evaluate", "iteration": 0, "status": "success"},
                    ],
                    "refinement": {
                        "iterations": 1,
                        "max_iterations": settings.max_iterations,
                        "termination_reason": "quality_threshold" if report.passed else "max_iterations"
                    }
                },
                "evaluation": {
                    "overall_score": report.overall_score,
                    "passed": report.passed,
                    "rubric": {
                        "accuracy": report.rubric.accuracy,
                        "pedagogical_clarity": report.rubric.pedagogical_clarity,
                        "structure_compliance": report.rubric.structure_compliance,
                        "depth_appropriateness": report.rubric.depth_appropriateness,
                        "audience_alignment": report.rubric.audience_alignment,
                        "consistency": report.rubric.consistency,
                        "completeness": report.rubric.completeness
                    },
                    "iteration_scores": [report.overall_score]
                },
                "issues": [
                    {
                        "id": issue.id,
                        "severity": issue.severity,
                        "scope": issue.scope,
                        "target_id": issue.target_id,
                        "category": issue.category,
                        "message": issue.message,
                        "suggestion": issue.suggestion,
                        "auto_fixable": issue.auto_fixable
                    }
                    for issue in report.issues
                ],
                "next_actions": []
            }

            return response

        except Exception as e:
            logger.error("generation_failed", error=str(e))
            raise HTTPException(status_code=500, detail=str(e))

    logger.info(
        "application_started",
        environment=settings.app_env,
        provider=settings.llm_provider,
    )

    return app

# Create the app instance
app = create_app()
