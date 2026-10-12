import asyncio
import pytest
from automation.network_resilience import (
    UserAgentRotator,
    DomainRateLimiter,
    CircuitBreaker,
    RetryPolicy,
    USER_AGENT_POOL,
)


def test_user_agent_rotator():
    rotator = UserAgentRotator()
    ua1 = rotator.get_next()
    ua2 = rotator.get_next()
    assert ua1 != ua2
    assert ua1 in USER_AGENT_POOL
    assert rotator.get_random() in USER_AGENT_POOL


@pytest.mark.asyncio
async def test_domain_rate_limiter():
    limiter = DomainRateLimiter(default_cooldown_seconds=0.1)
    # First access shouldn't wait
    w1 = await limiter.throttle("example.com")
    assert w1 == 0.0

    # Immediate second access should throttle
    w2 = await limiter.throttle("example.com")
    assert w2 > 0.05


def test_circuit_breaker():
    cb = CircuitBreaker(failure_threshold=2, recovery_timeout=0.2)
    assert cb.is_available("badsite.org") is True

    # 1st failure
    tripped = cb.record_failure("badsite.org")
    assert tripped is False
    assert cb.is_available("badsite.org") is True

    # 2nd failure -> trips circuit
    tripped = cb.record_failure("badsite.org")
    assert tripped is True
    assert cb.is_available("badsite.org") is False


@pytest.mark.asyncio
async def test_retry_policy():
    policy = RetryPolicy(max_attempts=3, initial_delay=0.01, backoff_multiplier=1.5)
    call_count = 0

    async def flaky_call():
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise ConnectionResetError("Connection reset")
        return "SUCCESS"

    result = await policy.execute(flaky_call)
    assert result == "SUCCESS"
    assert call_count == 3
