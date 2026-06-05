from enum import Enum


class JobStatus(str, Enum):
    """Lifecycle state of a `CourseGenerationJob`.

    The transitions are:

    * PENDING  -> RUNNING   (the service starts the job)
    * RUNNING  -> EVALUATING (the draft is being evaluated)
    * RUNNING  -> FAILED    (any stage raised)
    * EVALUATING -> RUNNING (evaluator returned changes, generator re-runs)
    * EVALUATING -> COMPLETED (evaluator approved)
    * EVALUATING -> FAILED  (max iterations reached)
    * FAILED   -> RUNNING   (a retry is initiated)
    """

    PENDING = "pending"
    RUNNING = "running"
    EVALUATING = "evaluating"
    COMPLETED = "completed"
    FAILED = "failed"
