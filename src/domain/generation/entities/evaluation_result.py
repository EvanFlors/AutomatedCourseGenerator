from src.domain.generation.value_objects.evaluation_action import EvaluationAction
from src.domain.shared.exceptions.validation_error import ValidationError


class EvaluationChange:
    """A single change recommended by the evaluator."""

    def __init__(
        self,
        action: EvaluationAction,
        target_id: str | None = None,
        new_value: dict | None = None,
        reason: str | None = None,
    ):
        self.action = action
        self.target_id = target_id
        self.new_value = new_value
        self.reason = reason.strip() if reason else None
        self._validate()

    def _validate(self) -> None:
        if not isinstance(self.action, EvaluationAction):
            raise ValidationError(
                f"action must be an EvaluationAction, got {type(self.action).__name__}."
            )


class EvaluationResult:
    """The output of the `CourseEvaluatorAgent`.

    The evaluator reviews the draft course and returns a list of
    recommended changes (which may be empty if the course is approved).
    """

    def __init__(
        self,
        approved: bool,
        changes: list[EvaluationChange] | None = None,
        overall_feedback: str | None = None,
        iteration: int = 0,
    ):
        self.approved = approved
        self.changes = list(changes) if changes else []
        self.overall_feedback = (
            overall_feedback.strip() if overall_feedback else None
        )
        self.iteration = iteration
        self._validate()

    def _validate(self) -> None:
        if self.approved and self.changes:
            raise ValidationError(
                "A course cannot be approved and have pending changes at the same time."
            )
        if self.iteration < 0:
            raise ValidationError("iteration cannot be negative.")

    @property
    def is_approved(self) -> bool:
        return self.approved

    def to_dict(self) -> dict:
        return {
            "approved": self.approved,
            "iteration": self.iteration,
            "overall_feedback": self.overall_feedback,
            "changes": [
                {
                    "action": c.action.value,
                    "target_id": c.target_id,
                    "new_value": c.new_value,
                    "reason": c.reason,
                }
                for c in self.changes
            ],
        }
