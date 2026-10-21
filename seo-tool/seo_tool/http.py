"""Polite HTTP fetching: robots.txt (RFC 9309 via protego), per-host rate limiting, adaptive throttling,
circuit breaker, retries with exponential backoff + jitter, Retry-After, manual redirect tracking."""
from __future__ import annotations

import logging
import random
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urljoin

import requests
from protego import Protego

from .config import Config
from .logging_setup import log
from .resilience import AdaptiveThrottle, CircuitBreaker
from .urls import origin_of

logger = logging.getLogger("seo_tool.http")
RETRY_STATUS = frozenset({429, 500, 502, 503, 504})
REDIRECT_STATUS = frozenset({301, 302, 303, 307, 308})
MAX_REDIRECTS = 10
_DISALLOW_ALL = "User-agent: *\nDisallow: /"

try:  # requests/urllib3 decode brotli automatically when one of these is installed
    import brotli  # noqa: F401
    _ENCODINGS = "gzip, deflate, br"
except ImportError:
    try:
        import brotlicffi  # noqa: F401
        _ENCODINGS = "gzip, deflate, br"
    except ImportError:
        _ENCODINGS = "gzip, deflate"


@dataclass
class FetchResult:
    url: str
    final_url: str
    status: int | None = None
    headers: dict[str, str] = field(default_factory=dict)
    body: bytes = b""
    redirect_chain: list[tuple[str, int]] = field(default_factory=list)
    elapsed: float = 0.0
    ttfb: float = 0.0
    error: str | None = None
    blocked_by_robots: bool = False
    truncated: bool = False

    @property
    def content_type(self) -> str:
        return self.headers.get("content-type", "").split(";")[0].strip().lower()

    @property
    def charset(self) -> str | None:
        for part in self.headers.get("content-type", "").split(";")[1:]:
            key, _, val = part.partition("=")
            if key.strip().lower() == "charset" and val.strip():
                return val.strip().strip("\"'")
        return None

    def text(self) -> str:
        try:
            return self.body.decode(self.charset or "utf-8", errors="replace")
        except LookupError:
            return self.body.decode("utf-8", errors="replace")


class Fetcher:
    def __init__(self, cfg: Config) -> None:
        self.cfg = cfg
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": cfg.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Encoding": _ENCODINGS,
        })
        self._robots: dict[str, Protego] = {}
        self.robots_raw: dict[str, FetchResult] = {}
        self._next_allowed: dict[str, float] = {}
        self.request_count = 0
        self.throttle = AdaptiveThrottle(cfg.adaptive_throttle, cfg.max_backoff)
        self._breakers: dict[str, CircuitBreaker] = {}

    # ---------- robots.txt ----------
    def robots_for(self, url: str) -> Protego:
        origin = origin_of(url)
        rp = self._robots.get(origin)
        if rp is not None:
            return rp
        res = self._request(origin + "/robots.txt", max_bytes=500_000)
        for _ in range(5):  # RFC 9309: follow at least five redirects
            loc = res.headers.get("location")
            if res.status in REDIRECT_STATUS and loc:
                res = self._request(urljoin(res.url, loc), max_bytes=500_000)
            else:
                break
        self.robots_raw[origin] = res
        if res.status is not None and 200 <= res.status < 300:
            rp = Protego.parse(res.text())
        elif res.status is not None and 400 <= res.status < 500 and res.status != 429:
            rp = Protego.parse("")  # "unavailable" -> allowed (RFC 9309, Google behaviour)
        else:
            rp = Protego.parse(_DISALLOW_ALL)  # "unreachable" -> assume full disallow
            log(logger, logging.WARNING, "robots.txt unreachable; treating origin as disallowed",
                origin=origin, status=res.status, error=res.error)
        self._robots[origin] = rp
        return rp

    def allowed(self, url: str) -> bool:
        return bool(self.robots_for(url).can_fetch(url, self.cfg.user_agent))

    def _delay(self, url: str) -> float:
        rd = self.robots_for(url).crawl_delay(self.cfg.user_agent)
        return max(self.cfg.crawl_delay, float(rd) if rd else 0.0)

    def wait_turn(self, url: str) -> None:
        """Respect rate limits for requests made outside this class (e.g. JS rendering)."""
        origin = origin_of(url)
        self._throttle(origin, self.throttle.delay(origin, self._delay(url)))

    # ---------- public fetch API ----------
    def fetch(self, url: str, method: str = "GET", read_body: bool = True,
              max_bytes: int | None = None) -> FetchResult:
        chain: list[tuple[str, int]] = []
        current = url
        for _ in range(MAX_REDIRECTS + 1):
            if not self.allowed(current):
                return FetchResult(url=url, final_url=current, redirect_chain=chain,
                                   error="blocked by robots.txt", blocked_by_robots=True)
            res = self._request(current, method, read_body, max_bytes, delay=self._delay(current))
            location = res.headers.get("location")
            if res.status in REDIRECT_STATUS and location:
                chain.append((current, res.status))
                nxt = urljoin(current, location)
                if nxt in (u for u, _ in chain):
                    res.url, res.redirect_chain, res.error = url, chain, "redirect loop"
                    return res
                current = nxt
                continue
            res.url, res.final_url, res.redirect_chain = url, current, chain
            return res
        return FetchResult(url=url, final_url=current, redirect_chain=chain,
                           error=f"more than {MAX_REDIRECTS} redirects")

    def check_link(self, url: str) -> FetchResult:
        res = self.fetch(url, method="HEAD", read_body=False)
        if res.status in (403, 405, 501) or (res.status is None and not res.blocked_by_robots):
            res = self.fetch(url, method="GET", read_body=False)
        return res

    def close(self) -> None:
        self.session.close()

    # ---------- internals ----------
    def _request(self, url: str, method: str = "GET", read_body: bool = True,
                 max_bytes: int | None = None, delay: float | None = None) -> FetchResult:
        origin = origin_of(url)
        base = self.cfg.crawl_delay if delay is None else delay
        breaker = self._breakers.setdefault(
            origin, CircuitBreaker(self.cfg.breaker_threshold, self.cfg.breaker_cooldown))
        attempt = 0
        while True:
            if not breaker.allow():
                return FetchResult(url=url, final_url=url,
                                   error="circuit open: host failing repeatedly, backing off")
            self._throttle(origin, self.throttle.delay(origin, base))
            result, transient = self._once(url, method, read_body, max_bytes or self.cfg.max_response_bytes)
            failed = transient or result.status in RETRY_STATUS
            breaker.record(not failed)
            self.throttle.observe(origin, result.status, result.elapsed, failed)
            if not failed or attempt >= self.cfg.max_retries:
                return result
            wait = self._backoff(attempt, result.headers.get("retry-after"))
            log(logger, logging.WARNING, "retrying request", url=url, status=result.status,
                error=result.error, attempt=attempt + 1, wait_s=round(wait, 2))
            time.sleep(wait)
            attempt += 1

    def _once(self, url: str, method: str, read_body: bool, max_bytes: int) -> tuple[FetchResult, bool]:
        start = time.monotonic()
        self.request_count += 1
        try:
            with self.session.request(method, url, timeout=self.cfg.timeout,
                                      allow_redirects=False, stream=True) as resp:
                body, truncated = (self._read(resp, max_bytes) if read_body and method != "HEAD"
                                   else (b"", False))
                return FetchResult(
                    url=url, final_url=url, status=resp.status_code,
                    headers={k.lower(): v for k, v in resp.headers.items()}, body=body,
                    elapsed=time.monotonic() - start, ttfb=resp.elapsed.total_seconds(),
                    truncated=truncated,
                ), False
        except requests.exceptions.SSLError as exc:
            return FetchResult(url=url, final_url=url, error=f"SSL error: {exc}",
                               elapsed=time.monotonic() - start), False
        except (requests.ConnectionError, requests.Timeout,
                requests.exceptions.ChunkedEncodingError) as exc:
            return FetchResult(url=url, final_url=url, error=f"{type(exc).__name__}: {exc}",
                               elapsed=time.monotonic() - start), True
        except requests.RequestException as exc:
            return FetchResult(url=url, final_url=url, error=f"{type(exc).__name__}: {exc}",
                               elapsed=time.monotonic() - start), False

    @staticmethod
    def _read(resp: requests.Response, max_bytes: int) -> tuple[bytes, bool]:
        chunks, size = [], 0
        for chunk in resp.iter_content(chunk_size=65536):
            chunks.append(chunk)
            size += len(chunk)
            if size >= max_bytes:
                return b"".join(chunks)[:max_bytes], True
        return b"".join(chunks), False

    def _throttle(self, origin: str, delay: float) -> None:
        wait = self._next_allowed.get(origin, 0.0) - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        self._next_allowed[origin] = time.monotonic() + delay

    def _backoff(self, attempt: int, retry_after: str | None) -> float:
        if retry_after:
            try:
                secs = float(retry_after)
            except ValueError:
                try:
                    secs = (parsedate_to_datetime(retry_after) - datetime.now(timezone.utc)).total_seconds()
                except (TypeError, ValueError):
                    secs = 0.0
            if secs > 0:
                return min(secs, self.cfg.max_backoff)
        base = self.cfg.backoff_base * (2 ** attempt)
        return min(base + random.uniform(0, self.cfg.backoff_base), self.cfg.max_backoff)
