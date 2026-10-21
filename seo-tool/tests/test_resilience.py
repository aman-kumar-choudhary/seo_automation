from seo_tool import resilience
from seo_tool.ai import unsupported_facts
from seo_tool.resilience import AdaptiveThrottle, CircuitBreaker


def test_breaker_opens_and_half_opens(monkeypatch):
    now = [0.0]
    monkeypatch.setattr(resilience.time, "monotonic", lambda: now[0])
    b = CircuitBreaker(2, 10)
    b.record(False)
    assert b.allow()
    b.record(False)
    assert not b.allow()
    now[0] = 11
    assert b.allow()
    b.record(True)
    assert b.allow() and b.failures == 0


def test_throttle_never_faster_than_base():
    t = AdaptiveThrottle()
    t.observe("o", 429, 0.2, True)
    assert t.delay("o", 1.0) == 2.0
    for _ in range(50):
        t.observe("o", 200, 0.2, False)
    assert t.delay("o", 1.0) == 1.0


def test_ai_fact_guard():
    assert unsupported_facts("Save 50% today", "Our shoes are comfortable")
    assert not unsupported_facts("Founded in 1998", "We were founded in 1998.")
