import pytest
from platforms.health_checker import PlatformHealthChecker, PlatformHealthStatus


@pytest.mark.asyncio
async def test_health_checker_local_domain():
    checker = PlatformHealthChecker(timeout_seconds=2.0)
    status = await checker.check_platform("demo-bookmarking.local")
    assert status.is_reachable is True
    assert status.status_code == 200
    assert status.ssl_valid is True
    assert status.domain == "demo-bookmarking.local"


@pytest.mark.asyncio
async def test_health_checker_batch():
    checker = PlatformHealthChecker(timeout_seconds=2.0)
    platforms = [
        {"domain": "127.0.0.1"},
        {"domain": "localhost"},
        {"domain": "local-test.local"},
    ]
    results = await checker.check_batch(platforms)
    assert len(results) == 3
    for res in results:
        assert res.is_reachable is True
        assert res.status_code == 200
