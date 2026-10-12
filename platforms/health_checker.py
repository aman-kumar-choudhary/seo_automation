"""Automated platform availability, HTTP reachability, and SSL health validation."""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from urllib.parse import urlparse

import httpx

logger = logging.getLogger(__name__)


@dataclass
class PlatformHealthStatus:
    domain: str
    is_reachable: bool = False
    status_code: int = 0
    latency_ms: float = 0.0
    ssl_valid: bool = True
    error_message: str | None = None
    checked_at: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


class PlatformHealthChecker:
    """Pre-screens platform candidates to ensure domains are alive before launching browser automation."""

    def __init__(self, timeout_seconds: float = 6.0):
        self.timeout = timeout_seconds

    async def check_platform(self, domain: str, submission_url: str | None = None) -> PlatformHealthStatus:
        """Pings a platform and validates HTTP status, SSL certificate, and latency."""
        ts = datetime.now(timezone.utc).isoformat()
        clean_domain = domain.strip().lower().removeprefix("www.")
        target_url = submission_url or f"https://{clean_domain}"

        # Handle local demo domains instantly
        if "127.0.0.1" in clean_domain or "localhost" in clean_domain or "local" in clean_domain:
            return PlatformHealthStatus(
                domain=clean_domain,
                is_reachable=True,
                status_code=200,
                latency_ms=1.5,
                ssl_valid=True,
                checked_at=ts,
            )

        headers = {
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 InnovionsHealth/1.0",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }

        start = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True, verify=True) as client:
                resp = await client.head(target_url, headers=headers)
                latency = round((time.perf_counter() - start) * 1000, 2)
                # Some servers return 405 Method Not Allowed for HEAD, fallback to GET
                if resp.status_code == 405:
                    resp = await client.get(target_url, headers=headers)
                    latency = round((time.perf_counter() - start) * 1000, 2)

                is_ok = resp.status_code < 500
                return PlatformHealthStatus(
                    domain=clean_domain,
                    is_reachable=is_ok,
                    status_code=resp.status_code,
                    latency_ms=latency,
                    ssl_valid=True,
                    error_message=None if is_ok else f"HTTP Server Error: {resp.status_code}",
                    checked_at=ts,
                )
        except httpx.ConnectError as exc:
            latency = round((time.perf_counter() - start) * 1000, 2)
            return PlatformHealthStatus(
                domain=clean_domain,
                is_reachable=False,
                status_code=0,
                latency_ms=latency,
                ssl_valid=False,
                error_message=f"Connection refused or DNS resolution failed: {exc}",
                checked_at=ts,
            )
        except httpx.TimeoutException:
            latency = round((time.perf_counter() - start) * 1000, 2)
            return PlatformHealthStatus(
                domain=clean_domain,
                is_reachable=False,
                status_code=408,
                latency_ms=latency,
                ssl_valid=True,
                error_message=f"Connection timed out after {self.timeout}s",
                checked_at=ts,
            )
        except Exception as exc:
            latency = round((time.perf_counter() - start) * 1000, 2)
            return PlatformHealthStatus(
                domain=clean_domain,
                is_reachable=False,
                status_code=0,
                latency_ms=latency,
                ssl_valid=False,
                error_message=str(exc),
                checked_at=ts,
            )

    async def check_batch(self, platforms: list[dict], concurrency: int = 5) -> list[PlatformHealthStatus]:
        """Validates availability across multiple platforms concurrently."""
        semaphore = asyncio.Semaphore(concurrency)

        async def worker(item: dict) -> PlatformHealthStatus:
            async with semaphore:
                return await self.check_platform(item["domain"], item.get("submission_url"))

        tasks = [worker(p) for p in platforms]
        return await asyncio.gather(*tasks)
