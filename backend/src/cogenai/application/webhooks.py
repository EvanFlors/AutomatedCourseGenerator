"""Webhook notifications (Sprint 12).

A simple in-process webhook registry: clients register a URL to receive
HTTP POSTs when jobs reach certain statuses. The dispatcher fires on
every job transition. For production, this should be replaced with a
durable queue (e.g., Redis, Celery, or Kafka); the in-process version
is best-effort and thread-safe.
"""
from __future__ import annotations

import threading
from typing import Any
from urllib.parse import urlparse


class WebhookRegistry:
    """Thread-safe registry of webhook subscriptions, keyed by job_id."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        # job_id -> set of URLs.
        self._subscribers: dict[str, set[str]] = {}
        # url -> total deliveries (counter for /metrics).
        self.delivery_attempts: dict[str, int] = {}
        self.delivery_successes: dict[str, int] = {}

    def subscribe(self, job_id: str, url: str) -> None:
        """Subscribe `url` to events for `job_id`."""
        if not _is_safe_url(url):
            raise ValueError(f"refusing to subscribe to unsafe URL: {url!r}")
        with self._lock:
            self._subscribers.setdefault(job_id, set()).add(url)
            self.delivery_attempts.setdefault(url, 0)
            self.delivery_successes.setdefault(url, 0)

    def unsubscribe(self, job_id: str, url: str) -> None:
        with self._lock:
            subs = self._subscribers.get(job_id)
            if subs is not None:
                subs.discard(url)
                if not subs:
                    del self._subscribers[job_id]

    def subscribers_for(self, job_id: str) -> set[str]:
        with self._lock:
            return set(self._subscribers.get(job_id, ()))

    def notify(self, job_id: str, payload: dict[str, Any]) -> list[tuple[str, bool]]:
        """Fire-and-forget delivery. Returns list of (url, success).

        Failures are silently recorded but never raised. Best-effort.
        """
        import json
        try:
            import urllib.request
        except ImportError:  # pragma: no cover
            return []
        results: list[tuple[str, bool]] = []
        body = json.dumps(payload, default=str).encode("utf-8")
        for url in self.subscribers_for(job_id):
            self.delivery_attempts[url] = self.delivery_attempts.get(url, 0) + 1
            try:
                req = urllib.request.Request(
                    url, data=body,
                    headers={"Content-Type": "application/json",
                             "User-Agent": "CourseForge-Webhook/1.0"},
                )
                with urllib.request.urlopen(req, timeout=5) as resp:
                    ok = 200 <= resp.status < 300
            except Exception:
                ok = False
            self.delivery_successes[url] = self.delivery_successes.get(url, 0) + int(ok)
            results.append((url, ok))
        return results

    def clear(self) -> None:
        with self._lock:
            self._subscribers.clear()
            self.delivery_attempts.clear()
            self.delivery_successes.clear()


def _is_safe_url(url: str) -> bool:
    """Allow only http(s) URLs to localhost or RFC1918 ranges in dev.

    Production deployments should override this with an allowlist of
    webhook hosts.
    """
    try:
        parsed = urlparse(url)
    except Exception:
        return False
    if parsed.scheme not in ("http", "https"):
        return False
    host = (parsed.hostname or "").lower()
    if host in ("localhost", "127.0.0.1", "::1", "0.0.0.0"):
        return True
    if host.startswith(("10.", "192.168.", "172.16.", "172.17.", "172.18.",
                         "172.19.", "172.20.", "172.21.", "172.22.", "172.23.",
                         "172.24.", "172.25.", "172.26.", "172.27.", "172.28.",
                         "172.29.", "172.30.", "172.31.")):
        return True
    return False


# Process-wide singleton.
_registry = WebhookRegistry()


def get_webhook_registry() -> WebhookRegistry:
    return _registry