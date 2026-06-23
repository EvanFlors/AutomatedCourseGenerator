from dataclasses import dataclass, field
from datetime import datetime

from cogenai.agents.base import BaseAgent
from cogenai.agents.config import AgentConfig
from cogenai.agents.context import AgentContext
from cogenai.agents.registry import prompt_registry
from cogenai.agents_implementations.consistency_checker import (
    ConsistencyCheckerInput,
    ConsistencyReport,
)
from cogenai.agents_implementations.context_synthesizer import (
    ContextSynthesizerInput,
    GenerationContext,
)
from cogenai.agents_implementations.curriculum_planner import (
    CourseSkeleton,
    CurriculumPlannerInput,
)
from cogenai.agents_implementations.evaluator import (
    EvaluationReport,
    EvaluatorInput,
)
from cogenai.agents_implementations.persona_adapter import (
    AdaptedSection,
    PersonaAdapterInput,
)
from cogenai.agents_implementations.prerequisite_validator import (
    PrerequisiteValidatorInput,
    ProgressionReport,
)
from cogenai.agents_implementations.refiner import (
    RefinedDraft,
    RefinerInput,
)
from cogenai.agents_implementations.section_author import (
    SectionAuthorInput,
    SectionDraft,
)
from cogenai.bootstrap.logging import get_logger
from cogenai.bootstrap.settings import settings
from cogenai.domain.course.entities import Course
from cogenai.interfaces.dto.contract import JSONOutputContract
from cogenai.interfaces.dto.course import CourseDTO
from cogenai.interfaces.dto.evaluation import EvaluationDTO, RubricScoresDTO
from cogenai.interfaces.dto.generation import (
    AgentTraceEntryDTO,
    GenerationMetadataDTO,
    RefinementDTO,
    TokenUsageDTO,
)
from cogenai.interfaces.dto.issue import IssueDTO, NextActionDTO

logger = get_logger(__name__)


# Define the input type
@dataclass
class OrchestratorInput:
    topic: str
    audience: str = "beginner"
    difficulty: str = "beginner"
    learning_outcomes: tuple[str, ...] = tuple()
    text_instructions: str = ""


# Define the output type
@dataclass
class OrchestratorOutput:
    contract: JSONOutputContract
    termination_reason: str
    iterations: int = 0


# Register the prompt (minimal - this is the coordinator)
ORCHESTRATOR_PROMPT = """
You are an Orchestrator agent.

Your task is to coordinate the multi-agent course generation pipeline.

Pipeline:
1. ContextSynthesizer → normalize inputs
2. CurriculumPlanner → create structure
3. For each section:
   - SectionAuthor → generate blocks
   - PersonaAdapter → adapt to audience
4. ConsistencyChecker → check consistency
5. PrerequisiteValidator → validate progression
6. Evaluator → score quality
7. While not passed and iterations < max:
   - Refiner → improve content
   - Evaluator → re-score
8. Return JSONOutputContract

You are the ONLY agent authorized to write to persistence.
All other agents are stateless.
"""

prompt_registry.register(
    "orchestrator",
    "1.0.0",
    ORCHESTRATOR_PROMPT,
)


@dataclass
class OrchestratorState:
    job_id: str = ""
    provider: str = "stub"
    model: str = "gemini-2.5-flash"
    started_at: str = ""
    agent_trace: list[AgentTraceEntryDTO] = field(default_factory=list)
    iteration_scores: list[float] = field(default_factory=list)


class OrchestratorAgent(BaseAgent[OrchestratorInput, OrchestratorOutput]):

    def __init__(self, config: AgentConfig, llm_provider, agents: dict):
        super().__init__(
            name="orchestrator",
            config=config,
            llm_provider=llm_provider,
        )
        self.agents = agents
        self.state = OrchestratorState()

    def run(self, input_data: OrchestratorInput) -> OrchestratorOutput:
        # Initialize state
        self._init_state(input_data)

        # Step 1: Synthesize context
        context = self._run_context_synthesizer(input_data)

        # Step 2: Create skeleton
        skeleton = self._run_curriculum_planner(context)

        # Step 3-4: Generate sections
        sections = self._run_section_generation(skeleton, context)

        # Step 5-6: Initial evaluation
        report = self._run_evaluation(sections)

        # Step 7: Refinement loop
        termination_reason = "quality_threshold"
        max_iterations = settings.max_iterations

        iteration = 0
        while iteration < max_iterations and not report.passed:
            # Refine
            refined = self._run_refiner(sections, report)

            # Re-evaluate
            report = self._run_evaluation(refined)

            self.state.iteration_scores.append(report.overall_score)
            iteration += 1

        if not report.passed and iteration >= max_iterations:
            termination_reason = "max_iterations"

        # Step 8: Create final contract
        contract = self._create_contract(
            sections=sections,
            report=report,
            termination_reason=termination_reason,
            iterations=iteration,
        )

        return OrchestratorOutput(
            contract=contract,
            termination_reason=termination_reason,
            iterations=iteration,
        )

    def _init_state(self, input_data: OrchestratorInput) -> None:
        import uuid
        self.state.job_id = str(uuid.uuid4())
        self.state.started_at = datetime.utcnow().isoformat()
        self.state.provider = settings.llm_provider
        self.state.model = settings.default_model

    def _run_context_synthesizer(
        self,
        input_data: OrchestratorInput
    ) -> GenerationContext:
        ctx_input = ContextSynthesizerInput(
            topic=input_data.topic,
            audience=input_data.audience,
            difficulty=input_data.difficulty,
            learning_outcomes=input_data.learning_outcomes,
            text_instructions=input_data.text_instructions,
        )

        agent = self.agents.get("context_synthesizer")
        if not agent:
            raise ValueError("ContextSynthesizer agent is not registered")
        result = agent.run(ctx_input)

        self._trace_agent("context_synthesizer", "draft", 0, "success")
        return result

    def _run_curriculum_planner(
        self,
        context: GenerationContext
    ) -> CourseSkeleton:
        planner_input = CurriculumPlannerInput(
            context=context,
            num_modules=4,
            sections_per_module=4,
        )

        agent = self.agents.get("curriculum_planner")
        if not agent:
            raise ValueError("CurriculumPlanner agent is not registered")
        result = agent.run(planner_input)

        self._trace_agent("curriculum_planner", "draft", 0, "success")
        return result

    def _run_section_generation(
        self,
        skeleton: CourseSkeleton,
        context: GenerationContext,
    ) -> list:
        sections = []

        for section_spec in skeleton.sections:
            # SectionAuthor
            author_input = SectionAuthorInput(
                section_spec=section_spec,
                context=context,
                skeleton=skeleton,
            )

            author_agent = self.agents.get("section_author")
            if not author_agent:
                raise ValueError("SectionAuthor agent is not registered")
            draft = author_agent.run(author_input)

            # PersonaAdapter
            adapter_input = PersonaAdapterInput(
                draft=draft,
                audience=context.audience,
                strategy="example_driven",
            )

            adapter_agent = self.agents.get("persona_adapter")
            if not adapter_agent:
                raise ValueError("PersonaAdapter agent is not registered")
            adapted = adapter_agent.run(adapter_input)
            sections.append(adapted)

        self._trace_agent("section_author", "draft", 0, "success")
        self._trace_agent("persona_adapter", "draft", 0, "success")
        return sections

    def _run_evaluation(self, sections) -> EvaluationReport:
        course = Course(
            title="Generated Course",
            learning_outcomes=("Outcome 1",),
        )

        eval_input = EvaluatorInput(
            course=course,
            rubric_version="1.0.0",
        )

        agent = self.agents.get("evaluator")
        if not agent:
            raise ValueError("Evaluator agent is not registered")
        result = agent.run(eval_input)

        self._trace_agent("evaluator", "evaluate", 0, "success")
        return result

    def _run_refiner(self, sections, report) -> list:
        refiner_input = RefinerInput(
            course=None,
            evaluation_report=report,
        )

        agent = self.agents.get("refiner")
        if not agent:
            raise ValueError("Refiner agent is not registered")
        result = agent.run(refiner_input)

        self._trace_agent("refiner", "refine", 0, "success")
        return sections

    def _trace_agent(
        self,
        agent: str,
        phase: str,
        iteration: int,
        status: str,
    ) -> None:
        self.state.agent_trace.append(
            AgentTraceEntryDTO(
                agent=agent,
                phase=phase,
                iteration=iteration,
                started_at=datetime.utcnow().isoformat(),
                completed_at=datetime.utcnow().isoformat(),
                status=status,
            )
        )

    def _create_contract(
        self,
        sections,
        report: EvaluationReport,
        termination_reason: str,
        iterations: int,
    ) -> JSONOutputContract:
        from cogenai.interfaces.dto.course import CourseDTO, ModuleDTO, SectionDTO

        # Create simple course DTO
        course_dto = CourseDTO(
            id=self.state.job_id,
            title="Generated Course",
            summary="",
            version=1,
            learning_outcomes=[],
            modules=[],
        )

        # Create generation metadata
        generation_dto = GenerationMetadataDTO(
            job_id=self.state.job_id,
            provider=self.state.provider,
            model=self.state.model,
            started_at=self.state.started_at,
            completed_at=datetime.utcnow().isoformat(),
            tokens=TokenUsageDTO(0, 0),
            agent_trace=self.state.agent_trace,
            refinement=RefinementDTO(
                iterations=iterations,
                max_iterations=settings.max_iterations,
                termination_reason=termination_reason,
            ),
        )

        # Create evaluation
        evaluation_dto = EvaluationDTO(
            overall_score=report.overall_score,
            passed=report.passed,
            rubric=RubricScoresDTO(
                accuracy=report.rubric.accuracy,
                pedagogical_clarity=report.rubric.pedagogical_clarity,
                structure_compliance=report.rubric.structure_compliance,
                depth_appropriateness=report.rubric.depth_appropriateness,
                audience_alignment=report.rubric.audience_alignment,
                consistency=report.rubric.consistency,
                completeness=report.rubric.completeness,
            ),
            iteration_scores=self.state.iteration_scores,
        )

        # Create issues
        issues = [
            IssueDTO(
                id=issue.id,
                severity=issue.severity,
                scope=issue.scope,
                target_id=issue.target_id,
                category=issue.category,
                message=issue.message,
                suggestion=issue.suggestion,
                auto_fixable=issue.auto_fixable,
            )
            for issue in report.issues
        ]

        return JSONOutputContract(
            schema_version="1.0.0",
            course=course_dto,
            generation=generation_dto,
            evaluation=evaluation_dto,
            issues=issues,
            next_actions=[],
        )
