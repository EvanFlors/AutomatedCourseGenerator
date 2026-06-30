from __future__ import annotations

import threading
import time

import pytest

from cogenai.application.agents.base import BaseAgent
from cogenai.application.agents.config import AgentAssignmentPolicy, AgentConfig
from cogenai.domain.ports.llm import AgentCancelled, SupportsCancellation
from cogenai.domain.value_objects.llm import (
    CompletionRequest,
    CompletionResponse,
    CompletionUsage,
)


class _SlowProvider:
    def __init__(self, delay: float = 0.5):
        self.delay = delay
        self.cancelled = False

    def health_check(self) -> bool:
        return True

    def complete(self, request: CompletionRequest) -> CompletionResponse:
        # Simulate a slow call; respects `self.cancelled` flag.
        end = time.monotonic() + self.delay
        while time.monotonic() < end:
            if self.cancelled:
                raise AgentCancelled()
            time.sleep(0.01)
        return CompletionResponse(
            text="done", model=request.model,
            usage=CompletionUsage(10, 10, 20), finish_reason="stop",
        )


class _CancelableProvider(_SlowProvider, SupportsCancellation):
    def cancel(self) -> None:
        self.cancelled = True


class _NonCancelProvider:
    def health_check(self) -> bool:
        return True

    def complete(self, request: CompletionRequest) -> CompletionResponse:
        return CompletionResponse(
            text="static", model=request.model,
            usage=CompletionUsage(0, 0, 0), finish_reason="stop",
        )


def _config() -> AgentConfig:
    return AgentConfig.default(
        model_name="stub",
        timeout_seconds=1.0,
    )


class TestAgentCancelledException:
    def test_can_be_raised(self):
        with pytest.raises(AgentCancelled):
            raise AgentCancelled()

    def test_is_an_exception(self):
        assert issubclass(AgentCancelled, Exception)


class TestBaseAgentCancel:
    def test_cancel_in_flight_calls_provider_cancel(self):
        provider = _CancelableProvider()
        agent = BaseAgent(name="t", config=_config(), llm_provider=provider)
        agent.cancel_in_flight()
        # Provider's flag is set.
        assert provider.cancelled is True

    def test_cancel_in_flight_no_op_on_non_cancelable(self):
        provider = _NonCancelProvider()
        agent = BaseAgent(name="t", config=_config(), llm_provider=provider)
        # Should not raise even though the provider doesn't implement cancel().
        agent.cancel_in_flight()

    def test_complete_raises_on_cancellation(self):
        provider = _SlowProvider(delay=0.05)
        # Schedule cancellation after a short delay.
        def _cancel_soon():
            time.sleep(0.01)
            provider.cancelled = True
        threading.Thread(target=_cancel_soon, daemon=True).start()
        agent = BaseAgent(name="t", config=_config(), llm_provider=provider)
        with pytest.raises(AgentCancelled):
            agent.llm_provider.complete(CompletionRequest(
                prompt="x", model=_config().model_for("t"),
            ))


class TestAgentConfigTimeout:
    def test_default_timeout_is_60(self):
        cfg = AgentConfig.default(model_name="stub")
        assert cfg.timeout_seconds == 60.0

    def test_custom_timeout(self):
        cfg = AgentConfig.default(model_name="stub", timeout_seconds=5.0)
        assert cfg.timeout_seconds == 5.0

    def test_zero_timeout_rejected(self):
        from pydantic import ValidationError
        # Wait — AgentConfig is a frozen dataclass, not Pydantic.
        # Validation happens in __post_init__.
        with pytest.raises(ValueError, match="timeout_seconds"):
            AgentConfig(model=None, timeout_seconds=0)  # type: ignore[arg-type]

    def test_negative_timeout_rejected(self):
        with pytest.raises(ValueError, match="timeout_seconds"):
            AgentConfig(model=None, timeout_seconds=-1.0)  # type: ignore[arg-type]


class TestJobStoreCancelEvent:
    def test_cancel_event_set_on_cancel(self):
        from cogenai.application.jobs import JobStore
        store = JobStore()
        job = store.create({"x": 1})
        event = store.cancel_event(job.job_id)
        assert not event.is_set()
        store.cancel(job.job_id)
        assert event.is_set()

    def test_cancel_event_set_for_already_cancelled_job(self):
        from cogenai.application.jobs import JobStore
        store = JobStore()
        job = store.create({"x": 1})
        store.cancel(job.job_id)
        # Late subscriber still sees the event set.
        event = store.cancel_event(job.job_id)
        assert event.is_set()

    def test_cancel_event_unknown_job_returns_unset(self):
        from cogenai.application.jobs import JobStore
        store = JobStore()
        event = store.cancel_event("does-not-exist")
        assert not event.is_set()

    def test_is_cancelled(self):
        from cogenai.application.jobs import JobStore
        store = JobStore()
        job = store.create({"x": 1})
        assert store.is_cancelled(job.job_id) is False
        store.cancel(job.job_id)
        assert store.is_cancelled(job.job_id) is True

    def test_clear_resets_cancel_events(self):
        from cogenai.application.jobs import JobStore
        store = JobStore()
        job = store.create({"x": 1})
        store.cancel_event(job.job_id)
        store.clear()
        assert job.job_id not in store._cancel_events


class TestSupportsCancellationProtocol:
    def test_checkruntime_protocol(self):
        # Static check: an adapter that implements `cancel` satisfies the protocol.
        class _Adapter(_NonCancelProvider):
            def cancel(self) -> None:
                pass
        adapter = _Adapter()
        assert isinstance(adapter, SupportsCancellation)

    def test_provider_without_cancel_fails_isinstance(self):
        # The base provider does NOT implement cancel(); the protocol
        # check must report this as not satisfying `SupportsCancellation`.
        provider = _NonCancelProvider()
        assert not isinstance(provider, SupportsCancellation)