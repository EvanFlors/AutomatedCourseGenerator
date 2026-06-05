from abc import ABC, abstractmethod

from src.domain.generation.entities.course_draft import CourseDraft
from src.domain.generation.entities.evaluation_result import EvaluationResult


class CourseEvaluatorAgent(ABC):
    """Port for the LLM pass that evaluates a course draft.

    The evaluator reviews the draft and returns an `EvaluationResult`
    describing what changes are needed, or `approved=True` if the
    draft meets quality criteria.

    Pluggable adapters allow swapping between a real Gemini-powered
    evaluator and a deterministic fake for testing.
    """

    @abstractmethod
    async def evaluate(
        self,
        draft: CourseDraft,
        iteration: int = 0,
    ) -> EvaluationResult:
        """Return an evaluation result for the given draft.

        Parameters
        ----------
        draft:
            The course draft to evaluate.
        iteration:
            Which pass this is (0 = first evaluation of this draft).
            Useful for the evaluator to know whether the draft has
            been revised or is brand new.
        """
