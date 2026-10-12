"""Network resilience, rate limiting, user-agent rotation, and exponential backoff retry."""
from __future__ import annotations

import asyncio
import logging
import random
import time
from dataclasses import dataclass, field
from typing import Callable, Coroutine, Any

logger = logging.getLogger(__name__)

USER_AGENT_POOL = [
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0",
]


class UserAgentRotator:
    """Rotates realistic browser user-agent signatures across sessions."""

    def __init__(self, pool: list[str] | None = None):
        self.pool = pool or USER_AGENT_POOL
        self._index = 0

    def get_random(self) -> str:
        return random.choice(self.pool)

    def get_next(self) -> str:
        ua = self.pool[self._index % len(self.pool)]
        self._index += 1
        return ua


class DomainRateLimiter:
    """Per-domain throttling and submission cooldown to prevent spam flags and rate limits."""

    def __init__(self, default_cooldown_seconds: float = 1.5):
        self.default_cooldown = default_cooldown_seconds
        self.last_access: dict[str, float] = {}

    async def throttle(self, domain: str, cooldown: float | None = None) -> float:
        """Enforces spacing between consecutive visits to the same domain."""
        cooldown_target = cooldown if cooldown is not None else self.default_cooldown
        now = time.perf_counter()
        elapsed = now - self.last_access.get(domain, 0.0)
        waited = 0.0
        if elapsed < cooldown_target:
            to_wait = cooldown_target - elapsed
            await asyncio.sleep(to_wait)
            waited = to_wait
        self.last_access[domain] = time.perf_counter()
        return waited


@dataclass
class CircuitBreaker:
    """Protects against cascade failures by temporarily tripping when a domain repeatedly fails."""
    failure_threshold: int = 3
    recovery_timeout: float = 60.0
    failures: dict[str, int] = field(default_factory=dict)
    tripped_at: dict[str, float] = field(default_factory=dict)

    def is_available(self, domain: str) -> bool:
        if domain in self.tripped_at:
            if time.perf_counter() - self.tripped_at[domain] > self.recovery_timeout:
                # Half-open recovery
                del self.tripped_at[domain]
                self.failures[domain] = 0
                return True
            return False
        return True

    def record_success(self, domain: str) -> None:
        self.failures[domain] = 0
        if domain in self.tripped_at:
            del self.tripped_at[domain]

    def record_failure(self, domain: str) -> bool:
        """Records failure and returns True if circuit is now tripped."""
        count = self.failures.get(domain, 0) + 1
        self.failures[domain] = count
        if count >= self.failure_threshold:
            self.tripped_at[domain] = time.perf_counter()
            logger.warning("Circuit breaker tripped for domain '%s' after %d failures", domain, count)
            return True
        return False


class RetryPolicy:
    """Exponential backoff retry with full jitter for async operations."""

    def __init__(
        self,
        max_attempts: int = 3,
        initial_delay: float = 0.5,
        backoff_multiplier: float = 2.0,
        max_delay: float = 5.0,
    ):
        self.max_attempts = max_attempts
        self.initial_delay = initial_delay
        self.backoff_multiplier = backoff_multiplier
        self.max_delay = max_delay

    async def execute(
        self,
        coro_func: Callable[[], Coroutine[Any, Any, Any]],
        should_retry: Callable[[Exception], bool] | None = None,
    ) -> Any:
        last_exception: Exception | None = None
        delay = self.initial_delay

        for attempt in range(1, self.max_attempts + 1):
            try:
                return await coro_func()
            except Exception as exc:
                last_exception = exc
                if attempt == self.max_attempts:
                    break
                if should_retry and not should_retry(exc):
                    break

                # Apply exponential backoff with full jitter
                jittered_delay = random.uniform(0.1, delay)
                logger.info(
                    "Retry attempt %d/%d after exception: %s. Sleeping %.2fs",
                    attempt,
                    self.max_attempts,
                    exc,
                    jittered_delay,
                )
                await asyncio.sleep(jittered_delay)
                delay = min(self.max_delay, delay * self.backoff_multiplier)

        if last_exception:
            raise last_exception
