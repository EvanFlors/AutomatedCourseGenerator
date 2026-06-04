from enum import Enum


class JobStatus(str, Enum):
    """Lifecycle state of a `CourseGenerationJob`.

    The transitions are:

    * PENDING -> RUNNING  (the service starts the job)
    * RUNNING -> COMPLETED (the service finished all stages)
    * RUNNING -> FAILED   (any stage raised)
    * FAILED  -> RUNNING  (a retry is initiated)
    """

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
