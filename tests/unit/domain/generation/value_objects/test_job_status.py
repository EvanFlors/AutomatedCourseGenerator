from src.domain.generation.value_objects.job_status import JobStatus


class TestJobStatus:
    def test_values(self):
        assert JobStatus.PENDING.value == "pending"
        assert JobStatus.RUNNING.value == "running"
        assert JobStatus.COMPLETED.value == "completed"
        assert JobStatus.FAILED.value == "failed"

    def test_iteration(self):
        statuses = {s.value for s in JobStatus}
        assert statuses == {"pending", "running", "completed", "failed"}
