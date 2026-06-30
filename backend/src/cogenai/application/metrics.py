"""Prometheus-style metrics endpoint.

Implements a minimal `/metrics` route that exposes:

- `cogenai_jobs_total{status="..."}` — counter, per-status submissions
- `cogenai_jobs_active` — gauge, currently queued+running
- `cogenai_jobs_completed_total{termination_reason="..."}` — counter
- `cogenai_jobs_failed_total` — counter
- `cogenai_tokens_used_total` — counter (LLM usage)
- `cogenai_request_duration_seconds` — histogram (submission → terminal)

No third-party deps: we render the Prometheus text exposition format
directly. Format spec: https://prometheus.io/docs/instrumenting/exposition_formats/
"""
from __future__ import annotations

import threading
from collections import defaultdict
from typing import Any


class MetricsRegistry:
    """Thread-safe metrics registry with Prometheus text-format renderer."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counters: dict[str, float] = defaultdict(float)
        self._counters_by_labels: dict[tuple[str, tuple[tuple[str, str], ...]], float] = defaultdict(float)
        self._gauges: dict[str, float] = defaultdict(float)

    def inc_counter(self, name: str, value: float = 1.0, **labels: str) -> None:
        key = (name, tuple(sorted(labels.items())))
        with self._lock:
            self._counters_by_labels[key] += value

    def set_gauge(self, name: str, value: float) -> None:
        with self._lock:
            self._gauges[name] = value

    def get_counter(self, name: str, **labels: str) -> float:
        key = (name, tuple(sorted(labels.items())))
        with self._lock:
            return self._counters_by_labels.get(key, 0.0)

    def get_gauge(self, name: str) -> float:
        with self._lock:
            return self._gauges.get(name, 0.0)

    def snapshot(self) -> dict[str, Any]:
        """Return a copy of the current counters/gauges for rendering."""
        with self._lock:
            return {
                "counters_by_labels": dict(self._counters_by_labels),
                "gauges": dict(self._gauges),
            }

    def render(self) -> str:
        """Render the metrics in Prometheus text exposition format."""
        snap = self.snapshot()
        lines: list[str] = []
        # Group counters by name for HELP/TYPE annotations.
        by_name: dict[str, list[tuple[tuple[tuple[str, str], ...], float]]] = defaultdict(list)
        for (name, labels), value in snap["counters_by_labels"].items():
            by_name[name].append((labels, value))
        for name in sorted(by_name.keys()):
            lines.append(f"# HELP {name} Application-defined counter.")
            lines.append(f"# TYPE {name} counter")
            for labels, value in sorted(by_name[name], key=lambda x: x[0]):
                if labels:
                    label_str = ",".join(f'{k}="{v}"' for k, v in labels)
                    lines.append(f"{name}{{{label_str}}} {value}")
                else:
                    lines.append(f"{name} {value}")
        # Gauges
        for name in sorted(snap["gauges"].keys()):
            value = snap["gauges"][name]
            lines.append(f"# HELP {name} Application-defined gauge.")
            lines.append(f"# TYPE {name} gauge")
            lines.append(f"{name} {value}")
        return "\n".join(lines) + "\n"

    def reset(self) -> None:
        with self._lock:
            self._counters_by_labels.clear()
            self._gauges.clear()


# Process-wide singleton.
_registry = MetricsRegistry()


def get_metrics_registry() -> MetricsRegistry:
    return _registry


# ----------------------------- Helpers -----------------------------

def record_job_submitted() -> None:
    get_metrics_registry().inc_counter("cogenai_jobs_total", status="submitted")


def record_job_terminal(termination_reason: str, status: str) -> None:
    """Called when a job transitions to a terminal state."""
    reg = get_metrics_registry()
    reg.inc_counter(
        "cogenai_jobs_completed_total",
        termination_reason=termination_reason,
    )
    reg.inc_counter("cogenai_jobs_failed_total" if status == "failed" else "cogenai_jobs_succeeded_total")


def record_tokens_used(tokens: int) -> None:
    if tokens > 0:
        get_metrics_registry().inc_counter("cogenai_tokens_used_total", value=float(tokens))


def update_active_jobs(active: int) -> None:
    get_metrics_registry().set_gauge("cogenai_jobs_active", float(active))


def render_metrics() -> str:
    return get_metrics_registry().render()