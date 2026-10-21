"""Circuit breaker, adaptive throttling and a retry helper for third-party APIs."""
from __future__ import annotations

import random
import time
from typing import Callable

import requests

RETRYABLE = frozenset({429, 500, 502, 503, 504})


class CircuitBreaker:
    """Opens after `threshold` consecutive failures; after `cooldown` seconds lets one probe through."""

    def __init__(self, threshold: int, cooldown: float) -> None:
        self.threshold, self.cooldown = threshold, cooldown
        self.failures = 0
        self.opened_at: float | None = None

    def allow(self) -> bool:
        return self.opened_at is None or time.monotonic() - self.opened_at >= self.cooldown

    def record(self, ok: bool) -> None:
        if ok:
            self.failures, self.opened_at = 0, None
            return
        self.failures += 1
        if self.failures >= self.threshold:
            self.opened_at = time.monotonic()


class AdaptiveThrottle:
    """Multiplies the per-host delay on errors/latency spikes and decays back. Never below the base delay."""

    def __init__(self, enabled: bool = True, max_delay: float = 60.0) -> None:
        self.enabled, self.max_delay = enabled, max_delay
        self._factor: dict[str, float] = {}
        self._latency: dict[str, float] = {}

    def delay(self, origin: str, base: float) -> float:
        return min(base * self._factor.get(origin, 1.0), max(self.max_delay, base)) if self.enabled else base

    def observe(self, origin: str, status: int | None, elapsed: float, failed: bool) -> None:
        if not self.enabled:
            return
        factor, avg = self._factor.get(origin, 1.0), self._latency.get(origin)
        if failed or status == 429:
            factor *= 2.0
        elif avg is not None and elapsed > 1.0 and elapsed > 3 * avg:
            factor *= 1.5
        else:
            factor = max(1.0, factor * 0.9)
        self._factor[origin] = min(factor, 64.0)
        self._latency[origin] = elapsed if avg is None else 0.8 * avg + 0.2 * elapsed


def call_with_retry(fn: Callable[[], requests.Response], attempts: int = 4,
                    base: float = 2.0, max_wait: float = 60.0) -> requests.Response:
    for attempt in range(attempts):
        last = attempt == attempts - 1
        try:
            resp = fn()
        except (requests.ConnectionError, requests.Timeout):
            if last:
                raise
            time.sleep(min(base * 2 ** attempt + random.uniform(0, base), max_wait))
            continue
        if resp.status_code not in RETRYABLE or last:
            return resp
        ra = resp.headers.get("retry-after", "")
        wait = float(ra) if ra.replace(".", "", 1).isdigit() else base * 2 ** attempt + random.uniform(0, base)
        time.sleep(min(wait, max_wait))
    raise RuntimeError("unreachable")
