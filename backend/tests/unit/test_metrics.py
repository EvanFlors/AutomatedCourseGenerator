from __future__ import annotations

import pytest

from cogenai.application.metrics import (
    MetricsRegistry,
    get_metrics_registry,
    record_job_submitted,
    record_job_terminal,
    record_tokens_used,
    render_metrics,
    update_active_jobs,
)


@pytest.fixture(autouse=True)
def _clean():
    get_metrics_registry().reset()
    yield
    get_metrics_registry().reset()


class TestMetricsRegistry:
    def test_initial_state_is_zero(self):
        reg = MetricsRegistry()
        assert reg.get_counter("cogenai_jobs_total") == 0
        assert reg.get_gauge("cogenai_jobs_active") == 0

    def test_inc_counter_with_no_labels(self):
        reg = MetricsRegistry()
        reg.inc_counter("foo")
        reg.inc_counter("foo")
        assert reg.get_counter("foo") == 2.0

    def test_inc_counter_with_labels(self):
        reg = MetricsRegistry()
        reg.inc_counter("foo", status="queued")
        reg.inc_counter("foo", status="queued")
        reg.inc_counter("foo", status="failed")
        assert reg.get_counter("foo", status="queued") == 2.0
        assert reg.get_counter("foo", status="failed") == 1.0
        assert reg.get_counter("foo", status="unknown") == 0.0

    def test_inc_counter_with_value(self):
        reg = MetricsRegistry()
        reg.inc_counter("foo", value=5.0)
        reg.inc_counter("foo", value=2.5)
        assert reg.get_counter("foo") == 7.5

    def test_set_gauge(self):
        reg = MetricsRegistry()
        reg.set_gauge("active", 3)
        reg.set_gauge("active", 7)
        assert reg.get_gauge("active") == 7.0

    def test_render_includes_help_and_type(self):
        reg = MetricsRegistry()
        reg.inc_counter("test_counter", status="ok")
        reg.set_gauge("test_gauge", 42)
        out = reg.render()
        assert "# HELP test_counter" in out
        assert "# TYPE test_counter counter" in out
        assert 'test_counter{status="ok"} 1.0' in out
        assert "# TYPE test_gauge gauge" in out
        assert "test_gauge 42" in out

    def test_render_handles_empty_registry(self):
        reg = MetricsRegistry()
        out = reg.render()
        # Empty registry still ends with a newline.
        assert out == "\n"

    def test_render_labels_are_sorted(self):
        reg = MetricsRegistry()
        reg.inc_counter("c", z="1", a="2")
        out = reg.render()
        # `a` comes before `z` in label order.
        assert 'c{a="2",z="1"}' in out


class TestMetricsHelpers:
    def test_record_job_submitted(self):
        record_job_submitted()
        record_job_submitted()
        assert get_metrics_registry().get_counter(
            "cogenai_jobs_total", status="submitted"
        ) == 2.0

    def test_record_job_terminal(self):
        record_job_terminal("quality_threshold", "completed")
        record_job_terminal("budget_exhausted", "partial")
        assert get_metrics_registry().get_counter(
            "cogenai_jobs_completed_total", termination_reason="quality_threshold"
        ) == 1.0
        assert get_metrics_registry().get_counter(
            "cogenai_jobs_completed_total", termination_reason="budget_exhausted"
        ) == 1.0

    def test_record_tokens_used_ignores_zero(self):
        record_tokens_used(0)
        assert get_metrics_registry().get_counter("cogenai_tokens_used_total") == 0
        record_tokens_used(100)
        record_tokens_used(50)
        assert get_metrics_registry().get_counter("cogenai_tokens_used_total") == 150

    def test_update_active_jobs(self):
        update_active_jobs(5)
        assert get_metrics_registry().get_gauge("cogenai_jobs_active") == 5

    def test_render_metrics_is_callable(self):
        record_job_submitted()
        out = render_metrics()
        assert "cogenai_jobs_total" in out


class TestMetricsEndpoint:
    def test_metrics_endpoint_returns_prometheus_text(self):
        from fastapi.testclient import TestClient
        from cogenai.interfaces.api.app import create_app
        client = TestClient(create_app())
        resp = client.get("/metrics")
        assert resp.status_code == 200
        assert "text/plain" in resp.headers["content-type"]
        assert "# HELP" in resp.text
        assert "# TYPE" in resp.text
        assert "cogenai_jobs_active" in resp.text